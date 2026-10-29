"""Command line entry point: `repolife scan | why | init`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, config
from .analyze import analyze
from .explain import TargetError, explain
from .render import markdown
from .report import build_report

# Not on PyPI yet: a bare `repolife` would install whatever package owns that name there.
DEFAULT_INSTALL_SPEC = "git+https://github.com/tianyi-zhang-02/repolife"


def _add_analysis_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--active-days", type=int, metavar="N", help="touched within N days => ACTIVE (default 90)")
    p.add_argument("--dormant-days", type=int, metavar="N", help="untouched for N days and barely used => DORMANT (default 365)")
    p.add_argument("--owner-inactive-days", type=int, metavar="N", help="an author silent in the whole repository for N days no longer counts as an owner (default 180)")
    p.add_argument("--ignore-author", dest="ignore_authors", action="append", default=[], metavar="GLOB", help="never credit commits whose author name or email matches (repeatable; bots are ignored already)")
    p.add_argument("--keep", action="append", default=[], metavar="GLOB", help="never report matching files as orphans (repeatable)")
    p.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="skip matching files entirely (repeatable)")
    p.add_argument("--entry", action="append", default=[], metavar="MODULE_OR_PATH", help="extra entry point (repeatable)")
    p.add_argument("--depth", type=int, metavar="N", help="directory depth for the per-directory table (default 1)")
    p.add_argument("--top", type=int, metavar="N", help="rows in the largest-files and hotspots tables (default 15)")


def _config_for(root: Path, args: argparse.Namespace) -> config.Config:
    cfg = config.load(root)
    for key in ("active_days", "dormant_days", "owner_inactive_days", "depth", "top"):
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


def _cmd_scan(args: argparse.Namespace) -> int:
    root = _root(args.path)
    analysis = analyze(root, _config_for(root, args))
    report = build_report(analysis, full=args.full)
    text = json.dumps(report, indent=2) + "\n" if args.format == "json" else markdown(report, args.limit)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"repolife: wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
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
    scan.add_argument("--format", choices=("md", "json"), default="md")
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
