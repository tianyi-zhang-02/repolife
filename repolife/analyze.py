"""The pipeline: discover -> read -> analyzers -> reachability -> git activity -> verdicts."""

from __future__ import annotations

import posixpath
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from . import gitlog, graph, inventory, ownership, textrefs
from .analyzers import Analyzer, Repo, load_analyzers
from .config import Config
from .gitlog import Activity
from .model import FileRecord
from .ownership import Ownership

# Directories whose contents are often run by hand rather than imported.
HINT_DIRS = frozenset({"examples", "example", "scripts", "tools", "benchmarks", "bin", "notebooks", "experiments", "research", "docs"})


@dataclass
class Analysis:
    root: Path
    cfg: Config
    now: float
    records: dict[str, FileRecord]
    graph: graph.Graph
    activity: Activity | None
    used_git: bool
    analyzers: list[str]
    skipped: dict[str, int]
    unparsed: list[str]
    ownership: Ownership | None = None  # None without git history
    changes: list[gitlog.Change] | None = None  # commits of the last two review windows; None without git history or with review_days = 0


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _apply_activity(rec: FileRecord, act, now: float) -> None:
    if act is None:
        return
    rec.tracked = True
    rec.first_commit, rec.last_commit = _day(act.first), _day(act.last)
    rec.age_days = int((now - act.last) // 86400)
    rec.commits_active, rec.commits_year, rec.authors_year = act.commits_active, act.commits_year, act.authors_year


def _apply_ownership(rec: FileRecord, own: Ownership) -> None:
    found = own.files.get(rec.path)
    if found is None:
        return
    rec.ownership = found.state
    if found.shares:
        top = own.owners(found.shares)[0]
        rec.owner, rec.owner_share, rec.owner_idle_days = top.name, round(100 * top.share), top.idle_days
    rec.declared_owners = None if found.declared is None else list(found.declared)
    rec.declared_match = found.declared_match


def _orphan_verdict(rec: FileRecord, g: graph.Graph, cfg: Config, now: float, have_git: bool) -> tuple[str, list[str]]:
    """Confidence drops one level per reason the file might still be wanted."""
    doubts: list[str] = []
    if have_git:
        if not rec.tracked:
            doubts.append("not in git history yet (uncommitted or untracked)")
        elif rec.age_days is not None and rec.age_days <= cfg.active_days:
            doubts.append(f"modified {rec.age_days}d ago; may be work in progress")
        elif rec.first_commit and (date.fromtimestamp(now) - date.fromisoformat(rec.first_commit)).days <= cfg.active_days:
            doubts.append(f"added within the last {cfg.active_days}d")
    docs = g.doc_refs.get(rec.path)
    if docs:
        doubts.append("mentioned in docs: " + ", ".join(sorted(docs)[:3]))
    hint = next((d for d in rec.path.split("/")[:-1] if d in HINT_DIRS), None)
    if hint:
        doubts.append(f"lives under {hint}/; may be run by hand")
    notes = list(doubts)
    if g.inbound.get(rec.path):
        notes.append("only referenced by other unreachable files")
    return ("high", "medium", "low")[min(len(doubts), 2)], notes


def _judge(rec: FileRecord, g: graph.Graph, cfg: Config, now: float, have_git: bool) -> None:
    if rec.kind != "code":
        return
    if rec.reachability == "none" and not rec.is_test and rec.code > 0:
        rec.status = "ORPHAN"
        rec.confidence, rec.notes = _orphan_verdict(rec, g, cfg, now, have_git)
        return
    if rec.reachability == "test" and not rec.is_test:
        rec.notes.append("only reached from tests")
    if not have_git:
        rec.status = "UNKNOWN"
    elif not rec.tracked:
        rec.status = "ACTIVE"
        rec.notes.append("not in git history yet")
    elif rec.age_days <= cfg.active_days:
        rec.status = "ACTIVE"
    elif rec.age_days >= cfg.dormant_days and (rec.reachability is None or rec.inbound < 2):
        rec.status = "DORMANT"
    else:
        rec.status = "STABLE"


def analyze(root: Path, cfg: Config, now: float | None = None, analyzers: list[Analyzer] | None = None) -> Analysis:
    root = Path(root).resolve()
    now = time.time() if now is None else now

    paths, used_git = inventory.discover(root, [*inventory.DEFAULT_EXCLUDES, *cfg.exclude])
    skipped: Counter[str] = Counter()
    langs: dict[str, inventory.Lang] = {}
    texts: dict[str, str] = {}
    for path in paths:
        lang = inventory.language_of(path)
        if lang is None:
            skipped["unknown_type"] += 1
            continue
        text = inventory.read_text(root / path)
        if text is None:
            skipped["too_large_or_binary"] += 1
            continue
        langs[path], texts[path] = lang, text

    extra: dict[str, str | None] = {}

    def read(path: str) -> str | None:
        if path in texts:
            return texts[path]
        if path not in extra:
            extra[path] = inventory.read_text(root / path) if path in known else None
        return extra[path]

    known = frozenset(paths)
    repo = Repo(paths=known, read=read)
    plugins = load_analyzers() if analyzers is None else analyzers
    results = []
    analyzed: dict[str, str] = {}
    for plugin in plugins:
        mine = {p: t for p, t in texts.items() if p not in analyzed and plugin.handles(p)}
        if not mine:
            continue
        results.append(plugin.run(mine, repo))
        analyzed.update({p: plugin.name for p in mine})

    unparsed = set().union(*(r.unparsed for r in results)) if results else set()
    scans: dict[str, textrefs.TextScan] = {}
    for path, lang in langs.items():
        if path in unparsed:
            scans[path] = textrefs.scan_text(texts[path])
        elif path in analyzed:
            continue
        elif posixpath.basename(path) == "pyproject.toml":
            scans[path] = textrefs.scan_pyproject(texts[path])
        elif posixpath.basename(path) == "setup.cfg":
            scans[path] = textrefs.scan_setup_cfg(texts[path])
        else:
            mode = textrefs.scan_mode(path, lang.name, lang.kind)
            if mode:
                scans[path] = textrefs.scan_text(texts[path], weak=mode == "weak")

    g = graph.build(results, analyzed, scans, cfg.keep, cfg.entry)
    activity = gitlog.load(root, now, cfg.active_days, cfg.ignore_authors) if used_git else None

    changes = gitlog.changes(root, now, cfg.review_days, cfg.ignore_authors) if used_git and cfg.review_days > 0 else None

    extra_comments: dict[str, set[int]] = {}
    for res in results:
        extra_comments.update(res.comment_lines)

    records: dict[str, FileRecord] = {}
    for path, lang in langs.items():
        code, comment, blank = inventory.count_lines(texts[path], lang, extra_comments.get(path, frozenset()))
        rec = FileRecord(path=path, language=lang.name, kind=lang.kind, code=code, comment=comment, blank=blank)
        rec.analyzer = analyzed.get(path)
        rec.is_test = path in g.tests
        rec.reachability = g.reachability(path)
        rec.inbound = len(g.inbound.get(path, ())) + len(g.config_refs.get(path, ()))
        rec.roots = list(g.roots.get(path, []))
        _apply_activity(rec, activity.files.get(path) if activity else None, now)
        records[path] = rec
    for rec in records.values():
        _judge(rec, g, cfg, now, activity is not None)

    owners = None
    if activity is not None:
        owners = ownership.compute(activity, cfg.owner_inactive_days, now, records, ownership.find_codeowners(known, read))
        for rec in records.values():
            _apply_ownership(rec, owners)

    return Analysis(
        root=root,
        cfg=cfg,
        now=now,
        records=records,
        graph=g,
        activity=activity,
        used_git=used_git,
        analyzers=sorted({r for r in analyzed.values()}),
        skipped=dict(skipped),
        unparsed=sorted(unparsed),
        ownership=owners,
        changes=changes,
    )
