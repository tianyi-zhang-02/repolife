"""Markdown rendering of the JSON report."""

from __future__ import annotations

from .model import STATUSES


def _table(headers: list[str], rows: list[list], right: set[int] | None = None) -> list[str]:
    right = right or set()
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---:" if i in right else "---" for i in range(len(headers))) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return out + [""]


def _n(value: int) -> str:
    return f"{value:,}"


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
            ["File", "Commits", "Authors", "Code", "Last commit", "Status"],
            [[f"`{r['path']}`", r["commits_year"], r["authors_year"], _n(r["code"]), r["last_commit"], r["status"]] for r in rep["hotspots"]],
            {1, 2, 3},
        )

    cleanup = rep["cleanup"]
    lines += ["## Cleanup candidates", ""]
    orphans = cleanup["orphan_files"]
    if orphans:
        lines += [f"Orphan files, most confident first (showing {min(limit, len(orphans))} of {len(orphans)}):", ""]
        lines += _table(
            ["File", "Code", "Confidence", "Last commit", "Notes"],
            [[f"`{r['path']}`", _n(r["code"]), r["confidence"], r["last_commit"] or "-", "; ".join(r["notes"]) or "-"] for r in orphans[:limit]],
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
