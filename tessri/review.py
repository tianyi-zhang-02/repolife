"""Review load: how much code changed recently, where, who changed it, and whether anyone who knows that
code is still around to look at it.

Git records who changed code, not who reviewed it, so this measures *demand* for review, not review done.
A change is a line added or deleted in a code file during the last `review_days` days, set against the same
number of days before that. Areas are directories, split by size like the modules of the graph. A change
counts as made by an owner when its author is among the people who maintain the area (see ownership.py);
the rest lands on people who know the area less well. Commits touching hundreds of files (a reformat, a vendor
drop) are reported apart: they would swamp everything and nobody reads them line by line.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from . import gitlog, inventory
from .analyze import Analysis
from .modules import assign
from .ownership import LISTED_MIN, UNKNOWN, UNOWNED, owner_rows, rollup

SUBJECT_MAX = 100
CONTRIBUTORS_LISTED = 3
REVIEWERS_LISTED = 8
BULK_LISTED = 3


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _pct(part: float, whole: float) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


class _Area:
    def __init__(self) -> None:
        self.lines = 0
        self.previous = 0
        self.automated = 0
        self.commits: set[str] = set()
        self.files: set[str] = set()
        self.by_person: dict[str, int] = defaultdict(int)


def section(a: Analysis) -> dict:
    """The `review` part of the report. `{"available": False}` without git history or when `review_days` is 0."""
    days = a.cfg.review_days
    if a.changes is None or a.ownership is None or days < 1:
        return {"available": False}
    own = a.ownership
    top = a.cfg.top
    start = a.now - days * 86400
    skip = [*inventory.DEFAULT_EXCLUDES, *a.cfg.exclude]
    kinds: dict[str, str | None] = {}

    def kind(path: str) -> str | None:
        """"code", "other" (config, docs, anything else) or None for files the scan leaves out."""
        if path not in kinds:
            if inventory.matches(path, skip):
                kinds[path] = None
            else:
                lang = inventory.language_of(path)
                kinds[path] = "code" if lang is not None and lang.kind == "code" else "other"
        return kinds[path]

    recent: list[tuple[gitlog.Change, dict[str, int]]] = []
    earlier: list[dict[str, int]] = []
    bulk: list[gitlog.Change] = []
    other = 0
    for change in a.changes:
        now_window = change.when >= start
        if change.when < start - days * 86400:
            continue
        if len(change.files) >= gitlog.BULK_FILES:
            if now_window:
                bulk.append(change)
            continue
        code = {p: n for p, n in change.files.items() if kind(p) == "code"}
        if now_window:
            other += sum(n for p, n in change.files.items() if kind(p) == "other")
            recent.append((change, code))
        else:
            earlier.append(code)

    paths = {p for p, r in a.records.items() if r.kind == "code"}
    for _, code in recent:
        paths.update(code)
    for code in earlier:
        paths.update(code)
    area_of = assign(paths)

    areas: dict[str, _Area] = defaultdict(_Area)
    person_lines: dict[str, int] = defaultdict(int)
    person_commits: dict[str, set[str]] = defaultdict(set)
    person_areas: dict[str, set[str]] = defaultdict(set)
    commits_seen: set[str] = set()
    for change, code in recent:
        for path, moved in code.items():
            area = areas[area_of[path]]
            area.lines += moved
            area.commits.add(change.sha)
            area.files.add(path)
            if change.identity is None:
                area.automated += moved
            else:
                area.by_person[change.identity] += moved
                person_lines[change.identity] += moved
                person_commits[change.identity].add(change.sha)
                person_areas[change.identity].add(area_of[path])
        if code:
            commits_seen.add(change.sha)
    previous = 0
    for code in earlier:
        for path, moved in code.items():
            previous += moved
            areas[area_of[path]].previous += moved
    areas = {k: v for k, v in areas.items() if v.commits}

    members: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for p, r in a.records.items():
        if r.kind == "code" and area_of.get(p) in areas:
            members[area_of[p]].append((p, r.code))

    rows = []
    inbound: dict[str, float] = defaultdict(float)
    owned: dict[str, set[str]] = defaultdict(set)
    unowned_lines = unowned_areas = 0
    for key, acc in areas.items():
        held = rollup(own, members[key])
        shares = {who: lines / held.code for who, lines in held.lines.items()} if held.code else {}
        owners = {who for who, share in shares.items() if share >= LISTED_MIN} or ({max(shares, key=lambda w: (shares[w], w))} if shares else set())
        made = sum(n for who, n in acc.by_person.items() if who in owners)
        people = sum(acc.by_person.values())
        state = held.state if held.code else UNKNOWN
        if state == UNOWNED:
            unowned_lines += acc.lines
            unowned_areas += 1
        for who in owners:
            inbound[who] += shares[who] * (acc.lines - acc.by_person.get(who, 0))
            owned[who].add(key)
        ranked = sorted(acc.by_person.items(), key=lambda kv: (-kv[1], own.authors[kv[0]].name))
        rows.append(
            {
                "path": key,
                "commits": len(acc.commits),
                "files": len(acc.files),
                "lines": acc.lines,
                "previous_lines": acc.previous,
                "authors": len(acc.by_person),
                "automated_lines": acc.automated,
                "owner_lines": made if owners else 0,
                "outside_lines": people - made if owners else 0,
                "outside_share": _pct(people - made, people) if owners and people else None,
                "contributors": [{"name": own.authors[who].name, "share": _pct(n, people)} for who, n in ranked[:CONTRIBUTORS_LISTED]],
                "owners": owner_rows(held.owners),
                "ownership": state,
            }
        )
    rows.sort(key=lambda r: (-r["lines"], r["path"]))
    total = sum(r["lines"] for r in rows)

    biggest = []
    for change, code in recent:
        moved = sum(code.values())
        if moved:
            where = defaultdict(int)
            for path, n in code.items():
                where[area_of[path]] += n
            biggest.append((moved, change, len(code), max(where, key=lambda k: (where[k], k))))
    biggest.sort(key=lambda t: (-t[0], t[1].sha))

    def describe(change: gitlog.Change, files: int, lines: int, where: str | None = None) -> dict:
        row = {"sha": change.sha, "date": _day(change.when), "author": change.name, "subject": change.subject[:SUBJECT_MAX], "files": files, "lines": lines}
        if where is not None:
            row["area"] = where
        return row

    bulk.sort(key=lambda c: (-sum(c.files.values()), c.sha))
    reviewers = sorted(
        ((who, lines) for who, lines in inbound.items() if round(lines) >= 1),
        key=lambda kv: (-kv[1], own.authors[kv[0]].name),
    )
    authors = sorted(person_lines.items(), key=lambda kv: (-kv[1], own.authors[kv[0]].name))
    people_total = sum(person_lines.values())
    return {
        "available": True,
        "days": days,
        "window": {"from": _day(start), "to": _day(a.now)},
        "totals": {
            "commits": len(commits_seen),
            "lines": total,
            "previous_lines": previous,
            "files": sum(r["files"] for r in rows),
            "areas": len(rows),
            "authors": len(person_lines),
            "automated_lines": sum(r["automated_lines"] for r in rows),
            "other_lines": other,
            "bulk": {
                "threshold": gitlog.BULK_FILES,
                "commits": len(bulk),
                "lines": sum(sum(c.files.values()) for c in bulk),
                "largest": [describe(c, len(c.files), sum(c.files.values())) for c in bulk[:BULK_LISTED]],
            },
        },
        "unowned": {"areas": unowned_areas, "lines": unowned_lines, "share": _pct(unowned_lines, total)},
        "areas": rows,
        "authors": [
            {"name": own.authors[who].name, "commits": len(person_commits[who]), "lines": lines, "share": _pct(lines, people_total), "areas": len(person_areas[who])}
            for who, lines in authors[:top]
        ],
        "reviewers": [
            {
                "name": own.authors[who].name,
                "inbound_lines": round(lines),
                "areas": len(owned[who]),
                "idle_days": own.idle_days(who),
                "active": own.is_active(who),
            }
            for who, lines in reviewers[:REVIEWERS_LISTED]
        ],
        "largest_changes": [describe(c, files, moved, where) for moved, c, files, where in biggest[:top]],
    }
