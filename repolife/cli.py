"""Command line entry point: `repolife scan | why | graph | impact | triage | check | init`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, config, graphview, htmlreport, modules, since, sinceview
from .analyze import analyze
from .explain import TargetError, explain
from .render import markdown
from .report import build_report
from .triage import TriageError, compute as triage_compute, markdown as triage_markdown

# Not on PyPI yet: a bare `repolife` would install whatever package owns that name there.
DEFAULT_INSTALL_SPEC = "git+https://github.com/tianyi-zhang-02/repolife"


def _add_analysis_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--active-days", type=int, metavar="N", help="touched within N days => ACTIVE (default 90)")
    p.add_argument("--dormant-days", type=int, metavar="N", help="untouched for N days and barely used => DORMANT (default 365)")
    p.add_argument("--owner-inactive-days", type=int, metavar="N", help="an author silent in the whole repository for N days no longer counts as an owner (default 180)")
    p.add_argument("--ignore-author", dest="ignore_authors", action="append", default=[], metavar="GLOB", help="never credit commits whose author name or email matches (repeatable; bots are ignored already)")
    p.add_argument("--review-days", type=_non_negative, metavar="N", help="review load: changes in the last N days against the N before (default 30, 0 turns it off)")
    p.add_argument("--keep", action="append", default=[], metavar="GLOB", help="never report matching files as orphans (repeatable)")
    p.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="skip matching files entirely (repeatable)")
    p.add_argument("--entry", action="append", default=[], metavar="MODULE_OR_PATH", help="extra entry point (repeatable)")
    p.add_argument("--depth", type=int, metavar="N", help="directory depth for the per-directory table (default 1)")
    p.add_argument("--top", type=int, metavar="N", help="rows in the largest-files and hotspots tables (default 15)")


def _positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _non_negative(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return value


def _config_for(root: Path, args: argparse.Namespace) -> config.Config:
    cfg = config.load(root)
    for key in ("active_days", "dormant_days", "owner_inactive_days", "review_days", "depth", "top"):
        value = getattr(args, key)
        if value is not None:
            setattr(cfg, key, value)
    for key in ("keep", "exclude", "entry", "ignore_authors"):
        current = getattr(cfg, key)
        current.extend(v for v in getattr(args, key) if v not in current)
    return cfg


def _root(path: str) -> Path:
    root = Path(path).expanduser()
    if not root.is_dir():
        raise SystemExit(f"repolife: {path}: not a directory")
    return root.resolve()


def _emit(text: str, out_path: str | None) -> None:
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"repolife: wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def _cmd_scan(args: argparse.Namespace) -> int:
    root = _root(args.path)
    analysis = analyze(root, _config_for(root, args))
    report = build_report(analysis, full=args.full)
    if args.format == "json":
        text = json.dumps(report, indent=2) + "\n"
    elif args.format == "html":
        text = htmlreport.build_html(analysis, report)
    else:
        text = markdown(report, args.limit)
    _emit(text, args.out)
    return 0


def _cmd_why(args: argparse.Namespace) -> int:
    root = _root(args.repo)
    analysis = analyze(root, _config_for(root, args))
    try:
        print(explain(analysis, args.target))
    except TargetError as exc:
        print(f"repolife: {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    root = _root(args.path)
    if args.level == "file" and args.format != "json":
        print("repolife: --level file is only available as --format json (a file-level picture is too large to read)", file=sys.stderr)
        return 2
    graph = modules.build_graph(analyze(root, _config_for(root, args)), args.module_depth, args.include_tests, args.level)
    if args.format == "json":
        text = json.dumps(graph, indent=2) + "\n"
    elif args.format == "mermaid":
        text = graphview.mermaid(graph, args.min_imports)
    elif args.format == "dot":
        text = graphview.dot(graph, args.min_imports)
    else:
        text = graphview.markdown(graph, args.limit)
    _emit(text, args.out)
    return 0


def _cmd_triage(args: argparse.Namespace) -> int:
    root = _root(args.repo)
    cfg = _config_for(root, args)
    try:
        result = triage_compute(root, cfg, args.since)
    except TriageError as exc:
        print(f"repolife: {exc}", file=sys.stderr)
        return 2
    _emit(json.dumps(result, indent=2) + "\n" if args.format == "json" else triage_markdown(result, args.limit, cfg.active_days), args.out)
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    root = _root(args.repo)
    try:
        result = since.check(root, _config_for(root, args), args.since)
    except since.CheckError as exc:
        print(f"repolife: {exc}", file=sys.stderr)
        return 2
    _emit(json.dumps(result, indent=2) + "\n" if args.format == "json" else sinceview.markdown(result, args.limit), args.out)
    return 1 if since.failing(result, args.fail_on) else 0


def _cmd_impact(args: argparse.Namespace) -> int:
    root = _root(args.repo)
    analysis = analyze(root, _config_for(root, args))
    try:
        found = modules.impact(analysis, args.target, args.module_depth, hops=args.hops)
    except TargetError as exc:
        print(f"repolife: {exc}", file=sys.stderr)
        return 2
    _emit(json.dumps(found, indent=2) + "\n" if args.format == "json" else graphview.impact_text(found), args.out)
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    from .mount import mount

    root = _root(args.path)
    agents = {"claude", "agents"} if args.agent == "all" else set() if args.agent == "none" else {args.agent}
    actions = mount(root, agents=agents, ci=None if args.ci == "none" else args.ci, install_spec=args.install_spec, force=args.force, dry_run=args.dry_run)
    dry = {"created": "would create", "updated": "would update", "skipped": "would skip"}
    for act in actions:
        verb = dry.get(act.verb, act.verb) if args.dry_run else act.verb
        print(f"{verb:<13} {act.path}")
    print("\nNext: run `repolife scan .` to see the first report." if not args.dry_run else "\nDry run: nothing was written.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repolife", description="Which parts of a repository are alive? Volume, git activity and reachability in one report.")
    parser.add_argument("--version", action="version", version=f"repolife {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="analyse a repository and print the report")
    scan.add_argument("path", nargs="?", default=".", help="repository root (default: .)")
    scan.add_argument("--format", choices=("md", "json", "html"), default="md", help="html: one self-contained page with the module graph and an impact explorer")
    scan.add_argument("--out", metavar="FILE", help="write the report to FILE instead of stdout")
    scan.add_argument("--full", action="store_true", help="json: include the per-file table")
    scan.add_argument("--limit", type=int, default=40, metavar="N", help="md: rows per candidate table (default 40)")
    _add_analysis_options(scan)
    scan.set_defaults(func=_cmd_scan)

    why = sub.add_parser("why", help="show the evidence behind one file's verdict")
    why.add_argument("target", help="file path, or dotted module name")
    why.add_argument("--repo", default=".", help="repository root (default: .)")
    _add_analysis_options(why)
    why.set_defaults(func=_cmd_why)

    graph = sub.add_parser("graph", help="module dependency graph: who imports whom, cycles, owners")
    graph.add_argument("path", nargs="?", default=".", help="repository root (default: .)")
    graph.add_argument("--format", choices=("md", "json", "mermaid", "dot"), default="md")
    graph.add_argument("--level", choices=("module", "file"), default="module", help="file: every import as a pair, json only (default: module)")
    graph.add_argument("--module-depth", type=_positive, metavar="N", help="a module is the first N directories of a path (default: split by size)")
    graph.add_argument("--include-tests", action="store_true", help="draw test files too (hidden by default: every module is imported by its tests)")
    graph.add_argument("--min-imports", type=_positive, metavar="N", help="mermaid, dot: leave out dependencies made of fewer than N imports (default: as many as fit about 80 arrows)")
    graph.add_argument("--out", metavar="FILE", help="write the graph to FILE instead of stdout")
    graph.add_argument("--limit", type=int, default=40, metavar="N", help="md: rows per table (default 40)")
    _add_analysis_options(graph)
    graph.set_defaults(func=_cmd_graph)

    impact = sub.add_parser("impact", help="what a change to one file or directory can reach: dependents, tests, owners")
    impact.add_argument("target", help="file path, directory, or dotted package name")
    impact.add_argument("--repo", default=".", help="repository root (default: .)")
    impact.add_argument("--format", choices=("text", "json"), default="text")
    impact.add_argument("--hops", type=_positive, metavar="N", help="follow imports at most N steps away (default: all of them)")
    impact.add_argument("--module-depth", type=_positive, metavar="N", help="group dependents by the first N directories (default: split by size)")
    impact.add_argument("--out", metavar="FILE", help="write the result to FILE instead of stdout")
    _add_analysis_options(impact)
    impact.set_defaults(func=_cmd_impact)

    triage = sub.add_parser("triage", help="which files of a change deserve a human first, what it can ripple into, who can look")
    triage.add_argument("--since", default="HEAD", metavar="REF", help="compare with the point where REF and HEAD part, plus uncommitted work (default: HEAD, i.e. only uncommitted work)")
    triage.add_argument("--repo", default=".", help="repository root (default: .)")
    triage.add_argument("--format", choices=("md", "json"), default="md")
    triage.add_argument("--limit", type=int, default=20, metavar="N", help="md: files listed (default 20)")
    triage.add_argument("--out", metavar="FILE", help="write the result to FILE instead of stdout")
    _add_analysis_options(triage)
    triage.set_defaults(func=_cmd_triage)

    check = sub.add_parser("check", help="what a change did to the structure: new orphans and cycles, imports of deleted files, changed code nobody maintains")
    check.add_argument("--since", default="HEAD", metavar="REF", help="compare with the point where REF and HEAD part, plus uncommitted work (default: HEAD, i.e. only uncommitted work)")
    check.add_argument("--repo", default=".", help="repository root (default: .)")
    check.add_argument("--format", choices=("md", "json"), default="md")
    check.add_argument("--limit", type=int, default=20, metavar="N", help="md: rows per table (default 20)")
    check.add_argument("--fail-on", choices=("never", "warn", "block"), default="never", help="exit 1 when a finding is at least this serious: block = deleted files still imported, warn = also new orphans, cycles and unowned code (default: never)")
    check.add_argument("--out", metavar="FILE", help="write the result to FILE instead of stdout")
    _add_analysis_options(check)
    check.set_defaults(func=_cmd_check)

    init = sub.add_parser("init", help="mount repolife into a repository: config, agent skill, AGENTS.md block, optional CI")
    init.add_argument("path", nargs="?", default=".", help="repository root (default: .)")
    init.add_argument("--agent", choices=("claude", "agents", "all", "none"), default="all", help="which agent integrations to write (default: all)")
    init.add_argument("--ci", choices=("none", "github"), default="none", help="also write a CI workflow (default: none)")
    init.add_argument("--install-spec", default=DEFAULT_INSTALL_SPEC, metavar="SPEC", help=f"what `pip install` should receive in generated files (default: {DEFAULT_INSTALL_SPEC})")
    init.add_argument("--force", action="store_true", help="overwrite files repolife would otherwise leave alone")
    init.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    init.set_defaults(func=_cmd_init)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except config.ConfigError as exc:
        print(f"repolife: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
