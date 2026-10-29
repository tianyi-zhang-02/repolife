"""Build the JSON report. This dict is the tool's public interface: see SCHEMA_VERSION in model.py."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone

from . import __version__
from .analyze import Analysis
from .model import SCHEMA_VERSION, STATUSES

_CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def _dir_key(path: str, depth: int) -> str:
    return "/".join(path.split("/")[:-1][:depth]) or "."


def build_report(a: Analysis, full: bool = False) -> dict:
    recs = list(a.records.values())
    code_recs = [r for r in recs if r.kind == "code"]
    top = a.cfg.top

    languages: dict[tuple[str, str], dict] = {}
    for r in recs:
        row = languages.setdefault(
            (r.language, r.kind),
            {"language": r.language, "kind": r.kind, "files": 0, "code": 0, "comment": 0, "blank": 0, "reachability": r.analyzer},
        )
        row["files"] += 1
        row["code"] += r.code
        row["comment"] += r.comment
        row["blank"] += r.blank

    by_status = {s: {"files": 0, "code": 0} for s in STATUSES}
    for r in code_recs:
        if r.status:
            slot = by_status.setdefault(r.status, {"files": 0, "code": 0})
            slot["files"] += 1
            slot["code"] += r.code

    analyzed_code = sum(r.code for r in code_recs if r.reachability is not None and not r.is_test)
    orphans = [r for r in code_recs if r.status == "ORPHAN"]
    test_only = [r for r in code_recs if r.reachability == "test" and not r.is_test]

    directories: dict[str, dict] = {}
    for r in code_recs:
        row = directories.setdefault(_dir_key(r.path, a.cfg.depth), {"path": _dir_key(r.path, a.cfg.depth), "files": 0, "code": 0, **{s.lower(): 0 for s in STATUSES}})
        row["files"] += 1
        row["code"] += r.code
        if r.status in STATUSES:
            row[r.status.lower()] += r.code

    unanalyzed = defaultdict(lambda: {"files": 0, "code": 0})
    for r in code_recs:
        if r.analyzer is None and r.language != "Python stub":
            unanalyzed[r.language]["files"] += 1
            unanalyzed[r.language]["code"] += r.code

    roots = Counter(why.split(":")[0] for r in recs for why in r.roots)

    caveats = [
        "Reachability is static. Dynamic dispatch, plugin discovery and consumers outside this repository are invisible: "
        "treat ORPHAN as a candidate, and run `repolife why <file>` before deleting anything.",
        "If this repository is a library, public modules that nothing inside it imports look orphaned. "
        "List them under `keep` in .repolife.toml.",
    ]
    if a.activity is None:
        caveats.append("No git history was available, so activity statuses are UNKNOWN.")
    elif a.activity.shallow:
        caveats.append("The git clone is shallow: activity numbers cover only the fetched history.")
    if unanalyzed:
        caveats.append("No reachability analyzer for: " + ", ".join(sorted(unanalyzed)) + ". Those files only get volume and activity.")

    report = {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "repolife", "version": __version__},
        "generated_at": datetime.fromtimestamp(a.now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": {"name": a.root.name},
        "git": {
            "available": a.activity is not None,
            "head": a.activity.head if a.activity else None,
            "shallow": a.activity.shallow if a.activity else None,
            "commits": a.activity.commits if a.activity else None,
        },
        "settings": {
            "active_days": a.cfg.active_days,
            "dormant_days": a.cfg.dormant_days,
            "keep": a.cfg.keep,
            "exclude": a.cfg.exclude,
            "entry": a.cfg.entry,
        },
        "summary": {
            "files": len(recs),
            "code_lines": sum(r.code for r in code_recs),
            "by_status": by_status,
            "orphans": {"files": len(orphans), "code": sum(r.code for r in orphans), "share_of_analyzed": _pct(sum(r.code for r in orphans), analyzed_code)},
            "test_only": {"files": len(test_only), "code": sum(r.code for r in test_only)},
            "reachability_coverage": {
                "analyzers": a.analyzers,
                "analyzed_code": analyzed_code,
                "share_of_code": _pct(analyzed_code, sum(r.code for r in code_recs if not r.is_test)),
            },
        },
        "languages": sorted(languages.values(), key=lambda row: -row["code"]),
        "directories": sorted(directories.values(), key=lambda row: -row["code"]),
        "largest_files": [
            {"path": r.path, "language": r.language, "code": r.code, "status": r.status}
            for r in sorted(code_recs, key=lambda r: -r.code)[:top]
        ],
        "hotspots": [
            {"path": r.path, "commits_year": r.commits_year, "authors_year": r.authors_year, "code": r.code, "last_commit": r.last_commit, "status": r.status}
            for r in sorted((r for r in code_recs if r.commits_year), key=lambda r: (-r.commits_year, -r.code))[:top]
        ],
        "cleanup": {
            "orphan_files": [
                {
                    "path": r.path,
                    "language": r.language,
                    "code": r.code,
                    "confidence": r.confidence,
                    "last_commit": r.last_commit,
                    "commits_year": r.commits_year,
                    "notes": r.notes,
                }
                for r in sorted(orphans, key=lambda r: (_CONFIDENCE_RANK.get(r.confidence or "low", 2), -r.code, r.path))
            ],
            "test_only_files": [
                {"path": r.path, "code": r.code, "last_commit": r.last_commit}
                for r in sorted(test_only, key=lambda r: (-r.code, r.path))
            ],
        },
        "analysis": {
            "roots": dict(sorted(roots.items())),
            "unanalyzed_languages": {k: v for k, v in sorted(unanalyzed.items())},
            "unparsed_files": a.unparsed,
            "skipped": a.skipped,
        },
        "caveats": caveats,
    }
    if full:
        report["files"] = [asdict(r) for r in sorted(recs, key=lambda r: r.path)]
    return report
