"""The `meta` block every JSON output carries: what was analysed and what git could say about it, under one set of
names. The older top-level fields (`git` in scan, the short `change.base` and `change.head` of triage and check)
stay as they are; this block is where the full object ids and the reasons live."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from . import __version__
from .gitlog import GitState
from .model import SCHEMA_VERSION

if TYPE_CHECKING:
    from .analyze import Analysis


def stamp(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def block(
    now: float,
    root: Path,
    git: GitState,
    shallow: bool | None = None,
    commits: int | None = None,
    change: dict | None = None,
    analysis: dict | None = None,
) -> dict:
    """`change` is the full-id base and head of a change query, absent for a path query. `analysis` says which step
    ran, for a result that answered before analysing anything, so that an empty result never looks like a clean one."""
    out = {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "repolife", "version": __version__},
        "generated_at": stamp(now),
        "repo": {"name": root.name, "root": str(root)},
        "git": {
            "available": git.available,
            "reason": git.reason,
            "head": git.head,
            "history_rev": git.history_rev,
            "shallow": shallow,
            "commits": commits,
        },
    }
    if change is not None:
        out["change"] = change
    if analysis is not None:
        out["analysis"] = analysis
    return out


def of(a: Analysis, change: dict | None = None, analysis: dict | None = None) -> dict:
    act = a.activity
    return block(a.now, a.root, a.git, act.shallow if act else None, act.commits if act else None, change, analysis)
