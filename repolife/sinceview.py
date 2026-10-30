"""Markdown for `repolife check`."""

from __future__ import annotations

from .render import _table
from .since import SEVERITIES


def _many(n: int, one: str, many: str | None = None) -> str:
    return f"{n:,} {one if n == 1 else many or one + 's'}"


def markdown(result: dict, limit: int = 20) -> str:
    c, s = result["change"], result["summary"]
    target = "the working tree" if c["uncommitted"] else c["head"]
    out = [f"# Change check: {result['repo']['name']}", ""]
    out += [
        f"`{c['since']}` ({c['base']}) to {target}: {_many(s['files'], 'file')} changed, {s['code_files']} of them code "
        f"({s['added']} added, {s['modified']} modified, {s['deleted']} deleted), **{s['lines']:,}** lines.",
        "",
    ]
    if not s["code_files"]:
        return "\n".join(out + ["No code changed, so there is nothing to compare.", ""] + _notes(result))
    counts = s["findings"]
    tally = ", ".join(f"{counts[sev]} {sev}" for sev in reversed(SEVERITIES) if counts[sev])
    out += [f"**{tally}.**" if tally else "No structural findings: the change adds no orphan, cycle, dangling import or unowned code that this analysis can see.", ""]

    if result["findings"]:
        out += ["## Findings", ""]
        for f in result["findings"]:
            out.append(f"- **{f['severity']}**: {f['title']}")
            if f["detail"]:
                out.append(f"  {f['detail']}")
            if f["files"]:
                shown = ", ".join(f"`{p}`" for p in f["files"][:5])
                out.append(f"  Files: {shown}" + (f" and {len(f['files']) - 5} more" if len(f["files"]) > 5 else ""))
            if f["action"]:
                out.append(f"  Do: {f['action']}" + (" A person has to decide this." if f["needs_human"] else ""))
        out.append("")

    new_deps = result["dependencies"]["new"]
    if new_deps:
        out += ["New dependencies between modules:", ""]
        out += _table(
            ["From", "To", "Imports", "Files", "Note"],
            [[f"`{e['from']}`", f"`{e['to']}`", e["imports"], e["files"], "points against the dominant direction" if e["against_flow"] else ""] for e in new_deps[:limit]],
            {2, 3},
        )
    if result["unowned"]:
        out += ["Changed code nobody active maintains:", ""]
        out += _table(
            ["File", "Lines", "Last maintainer", "Silent for"],
            [[f"`{r['path']}`", r["lines"], r["last_owner"] or "-", f"{r['owner_idle_days']} days" if r["owner_idle_days"] is not None else "-"] for r in result["unowned"][:limit]],
            {1},
        )
    code = [f for f in result["changed_files"] if f["code"]]
    code.sort(key=lambda f: (-f["lines"], f["path"]))
    out += ["Changed code, largest first:", ""]
    out += _table(["File", "Change", "Lines"], [[f"`{f['path']}`", f["change"], f"+{f['added']} -{f['deleted']}"] for f in code[:limit]])
    if len(code) > limit:
        out += [f"{len(code) - limit} more files in the JSON output.", ""]
    return "\n".join(out + _notes(result))


def _notes(result: dict) -> list[str]:
    return ["## Read this with care", ""] + [f"- {n}" for n in result["notes"]] + [""]
