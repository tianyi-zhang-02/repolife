"""Markdown rendering of the JSON report."""

from __future__ import annotations

from .model import STATUSES


def _table(headers: list[str], rows: list[list], right: set[int] | None = None) -> list[str]:
    right = right or set()
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---:" if i in right else "---" for i in range(len(headers))) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out + [""]


_STATE_TEXT = {"owned": "owned", "no-active-owner": "no active owner", "unknown": "no history"}


def _n(value: int) -> str:
    return f"{value:,}"


def _cell(text: str) -> str:
    return text.replace("|", "/")


def _idle(days: int | None, limit: int) -> str:
    return f" (silent {days}d)" if days is not None and days > limit else ""


def _owners(owners: list[dict], limit: int, contributors: int = 0) -> str:
    text = ", ".join(f"{o['name']} {o['share']}%{_idle(o['idle_days'], limit)}" for o in owners)
    if text and sum(o["share"] for o in owners) < 50 and contributors > len(owners):  # nobody clearly owns it: say so
        text += f" + {contributors - len(owners)} others"
    return _cell(text or "-")


def _owner(name: str | None, idle: int | None, limit: int) -> str:
    return _cell(f"{name}{_idle(idle, limit)}") if name else "-"


def _ownership(own: dict, directories: list[dict], limit: int) -> list[str]:
    gone = own["inactive_days"]
    people, unowned = own["authors"], own["no_active_owner"]
    lines = ["## Ownership", ""]
    lines += [
        f"- **{people['total']}** authors in the commit history, **{people['active']}** with a commit in the last {gone} days; "
        f"the fewest people who together hold half the code: **{own['bus_factor']}**",
        f"- **{_n(unowned['code'])}** lines (**{unowned['share']}%**) in {_n(unowned['files'])} files have no active owner: "
        f"nobody who maintains them has committed anywhere in the last {gone} days",
    ]
    if own["unattributed"]["code"]:
        lines.append(f"- {_n(own['unattributed']['code'])} lines have no usable history (uncommitted, or only touched by bots)")
    lines.append("")
    rows = [
        [f"`{r['path']}`", _n(r["code"]), _owners(r["owners"], gone, r["contributors"]), _STATE_TEXT[r["ownership"]], _n(r["no_active_owner_code"])]
        for r in directories[:limit]
        if "owners" in r
    ]
    if rows:
        lines += ["Who maintains each directory (share of recent commits, recent ones weighing more):", ""]
        lines += _table(["Directory", "Code", "Owners", "State", "Code with no active owner"], rows, {1, 4})
    needs = own["needs_owner_files"]
    if needs:
        lines += ["Live code nobody active maintains, largest first. Someone needs to be assigned:", ""]
        lines += _table(
            ["File", "Code", "Status", "Last maintainer"],
            [[f"`{r['path']}`", _n(r["code"]), r["status"] or "-", _owner(r["last_owner"], r["owner_idle_days"], gone)] for r in needs],
            {1},
        )
    co = own["codeowners"]
    if co:
        lines += [
            f"CODEOWNERS (`{co['file']}`, {co['rules']} rules): **{_n(co['uncovered']['files'])}** code files ({co['uncovered']['share']}% of code) have no declared owner; "
            f"**{_n(co['differs']['files'])}** have a declared owner who does not appear among the people maintaining them.",
            "",
        ]
        if co["uncovered_files"]:
            lines += ["Without a declared owner:", ""]
            lines += _table(["File", "Code", "Maintained by"], [[f"`{r['path']}`", _n(r["code"]), _cell(r["owner"] or "-")] for r in co["uncovered_files"]], {1})
        if co["differing_files"]:
            lines += ["Declared owner differs from who maintains it:", ""]
            lines += _table(
                ["File", "Code", "Declared", "Maintained by"],
                [[f"`{r['path']}`", _n(r["code"]), _cell(" ".join(r["declared"])), _cell(r["observed"] or "-")] for r in co["differing_files"]],
                {1},
            )
    return lines


def _count(n: int, one: str, many: str | None = None) -> str:
    return f"{_n(n)} {one if n == 1 else many or one + 's'}"


def _delta(now: int, before: int) -> str:
    if not before:
        return "new" if now else "-"
    return f"{round(100 * (now - before) / before):+d}%"


def _review(rev: dict, gone: int, limit: int) -> list[str]:
    t, w = rev["totals"], rev["window"]
    lines = [
        "## Review load",
        "",
        f"The last {rev['days']} days ({w['from']} to {w['to']}) against the {rev['days']} before. Git records who changed code, not who "
        "reviewed it, so this is how much review the changes ask for, not how much happened.",
        "",
        f"- **{_n(t['lines'])}** lines changed in code files ({_delta(t['lines'], t['previous_lines'])} against {_n(t['previous_lines'])} before), "
        f"in {_count(t['commits'], 'commit')} across {_count(t['areas'], 'area')} by {_count(t['authors'], 'person', 'people')}",
    ]
    if t["automated_lines"]:
        lines.append(f"- {_n(t['automated_lines'])} of those lines came from bots or ignored authors")
    unowned = rev["unowned"]
    if unowned["lines"]:
        lines.append(f"- **{_n(unowned['lines'])}** lines ({unowned['share']}%) landed in {_count(unowned['areas'], 'area')} that nobody active maintains: nobody who knows that code is around to look")
    if t["other_lines"]:
        lines.append(f"- {_n(t['other_lines'])} lines of configuration and docs are not counted")
    if t["bulk"]["commits"]:
        lines.append(
            f"- {_n(t['bulk']['commits'])} commit{'s' if t['bulk']['commits'] != 1 else ''} touching {_n(t['bulk']['threshold'])} or more files ({_n(t['bulk']['lines'])} lines) "
            "are left out: a reformat or vendor drop is not reviewed line by line"
        )
    lines.append("")
    if not rev["areas"]:
        return lines + ["No code changed in this window.", ""]
    lines += ["Where the changes landed (areas are directories, split by size):", ""]
    lines += _table(
        ["Area", "Changed lines", "Against before", "Commits", "People", "By outsiders", "Owners", "State"],
        [
            [
                f"`{r['path']}`",
                _n(r["lines"]),
                _delta(r["lines"], r["previous_lines"]),
                _n(r["commits"]),
                r["authors"],
                "-" if r["outside_share"] is None else f"{r['outside_share']}%",
                _owners(r["owners"], gone),
                _STATE_TEXT[r["ownership"]],
            ]
            for r in rev["areas"][:limit]
        ],
        {1, 2, 3, 4, 5},
    )
    lines += ["*By outsiders* is the share of the people's lines written by someone who is not among the area's owners; those changes are the ones an owner should see.", ""]
    if rev["reviewers"]:
        lines += ["Who the changes land on: the people who maintain the areas that others changed, by lines changed by someone else:", ""]
        lines += _table(
            ["Person", "Lines from others", "Areas", "State"],
            [[_cell(r["name"]), _n(r["inbound_lines"]), r["areas"], "active" if r["active"] else f"silent for {r['idle_days']} days"] for r in rev["reviewers"]],
            {1, 2},
        )
    if rev["largest_changes"]:
        lines += ["Largest changes, the hardest to review:", ""]
        lines += _table(
            ["Commit", "Date", "Author", "Lines", "Files", "Mostly in", "Subject"],
            [[f"`{r['sha']}`", r["date"], _cell(r["author"]), _n(r["lines"]), r["files"], f"`{r['area']}`", _cell(r["subject"])] for r in rev["largest_changes"][:limit]],
            {3, 4},
        )
    return lines


def markdown(rep: dict, limit: int = 40) -> str:
    s = rep["summary"]
    git = rep["git"]
    lines = [f"# repolife report: {rep['repo']['name']}", ""]
    meta = [f"generated {rep['generated_at']}", f"repolife {rep['tool']['version']}"]
    if git["available"]:
        meta.append(f"git {git['head']} ({git['commits']:,} commits)")
    lines += [" · ".join(meta), ""]

    cov = s["reachability_coverage"]
    lines += ["## Summary", ""]
    lines += [
        f"- **{_n(s['code_lines'])}** lines of code in **{_n(s['files'])}** files "
        f"(reachability analysed for {cov['share_of_code']}% of code: {', '.join(cov['analyzers']) or 'no analyzer'})",
        f"- **{s['orphans']['files']}** orphan files, **{_n(s['orphans']['code'])}** lines "
        f"(**{s['orphans']['share_of_analyzed']}%** of analysed code)",
        f"- **{s['test_only']['files']}** files only reached from tests, {_n(s['test_only']['code'])} lines",
        "",
    ]
    total = s["code_lines"] or 1
    rows = [[st, _n(v["files"]), _n(v["code"]), f"{round(100 * v['code'] / total, 1)}%"] for st, v in s["by_status"].items() if v["files"] or st in STATUSES]
    lines += _table(["Status", "Files", "Code lines", "Share"], rows, {1, 2, 3})
    lines += [
        "ACTIVE: touched recently · STABLE: untouched but depended on · DORMANT: untouched and barely used · "
        "ORPHAN: nothing reaches it",
        "",
    ]

    lines += ["## Volume", ""]
    lines += _table(
        ["Language", "Kind", "Files", "Code", "Comment", "Blank", "Reachability"],
        [[r["language"], r["kind"], _n(r["files"]), _n(r["code"]), _n(r["comment"]), _n(r["blank"]), r["reachability"] or "-"] for r in rep["languages"]],
        {2, 3, 4, 5},
    )
    lines += ["By directory (code files):", ""]
    lines += _table(
        ["Directory", "Files", "Code", "Active", "Stable", "Dormant", "Orphan"],
        [[f"`{r['path']}`", _n(r["files"]), _n(r["code"]), _n(r["active"]), _n(r["stable"]), _n(r["dormant"]), _n(r["orphan"])] for r in rep["directories"][:limit]],
        {1, 2, 3, 4, 5, 6},
    )
    lines += ["Largest files:", ""]
    lines += _table(["File", "Code", "Status"], [[f"`{r['path']}`", _n(r["code"]), r["status"] or "-"] for r in rep["largest_files"]], {1})

    if git["available"]:
        lines += ["## Hotspots (most commits in the last 365 days)", ""]
        lines += _table(
            ["File", "Commits", "Authors", "Code", "Last commit", "Status", "Owner"],
            [[f"`{r['path']}`", r["commits_year"], r["authors_year"], _n(r["code"]), r["last_commit"], r["status"], _cell(r.get("owner") or "-")] for r in rep["hotspots"]],
            {1, 2, 3},
        )

    own = rep["ownership"]
    gone = own.get("inactive_days", 0)
    if own["available"]:
        lines += _ownership(own, rep["directories"], limit)

    if rep["review"]["available"]:
        lines += _review(rep["review"], gone, limit)

    cleanup = rep["cleanup"]
    lines += ["## Cleanup candidates", ""]
    orphans = cleanup["orphan_files"]
    if orphans:
        lines += [f"Orphan files, most confident first (showing {min(limit, len(orphans))} of {len(orphans)}):", ""]
        with_owner = own["available"]
        lines += _table(
            ["File", "Code", "Confidence", "Last commit", *(["Owner"] if with_owner else []), "Notes"],
            [
                [f"`{r['path']}`", _n(r["code"]), r["confidence"], r["last_commit"] or "-", *([_owner(r["owner"], r["owner_idle_days"], gone)] if with_owner else []), "; ".join(r["notes"]) or "-"]
                for r in orphans[:limit]
            ],
            {1},
        )
    else:
        lines += ["No orphan files found.", ""]
    if cleanup["test_only_files"]:
        tests = cleanup["test_only_files"]
        lines += [f"Only reached from tests (showing {min(limit, len(tests))} of {len(tests)}). Either production code lost its caller, or this is test support:", ""]
        lines += _table(["File", "Code", "Last commit"], [[f"`{r['path']}`", _n(r["code"]), r["last_commit"] or "-"] for r in tests[:limit]], {1})

    lines += ["## Caveats", ""] + [f"- {c}" for c in rep["caveats"]] + [""]
    lines += ["Verify a candidate with `repolife why <file>` before touching it.", ""]
    return "\n".join(lines)
