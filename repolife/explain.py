"""`repolife why <file>`: the evidence behind a file's verdict, for agents and humans verifying a candidate."""

from __future__ import annotations

from .analyze import Analysis

_REACH_TEXT = {
    "prod": "reachable from a production entry point",
    "test": "reachable only from tests",
    "none": "NOT reachable from any entry point, test or config reference",
}


class TargetError(LookupError):
    pass


def resolve_target(a: Analysis, target: str) -> str:
    target = target.strip()
    while target.startswith("./"):
        target = target[2:]
    if target in a.records:
        return target
    suffix = [p for p in a.records if p.endswith("/" + target)]
    if len(suffix) == 1:
        return suffix[0]
    dotted = target.replace(".", "/")
    by_module = [p for p in a.records if p in (dotted + ".py", dotted + "/__init__.py")]
    if len(by_module) == 1:
        return by_module[0]
    options = suffix or by_module
    if options:
        raise TargetError(f"`{target}` is ambiguous: " + ", ".join(sorted(options)[:8]))
    raise TargetError(f"`{target}` is not a file in the analysed set (excluded, binary or unknown type?)")


def _fmt(items, empty="none", cap=12) -> str:
    items = sorted(items)
    if not items:
        return empty
    shown = ", ".join(items[:cap])
    return shown + (f" (+{len(items) - cap} more)" if len(items) > cap else "")


def explain(a: Analysis, target: str) -> str:
    path = resolve_target(a, target)
    rec = a.records[path]
    g = a.graph
    out = [f"{path}  ({rec.language}, {rec.code} code lines)"]

    if rec.status:
        verdict = rec.status + (f" (confidence {rec.confidence})" if rec.confidence else "")
        out.append(f"status:        {verdict}")
    if rec.analyzer is None:
        out.append(f"reachability:  not analysed (no analyzer for {rec.language})")
    else:
        out.append(f"reachability:  {_REACH_TEXT[rec.reachability]}")
    if rec.roots:
        out.append(f"entry point:   {'; '.join(rec.roots)}")
    if rec.is_test:
        out.append("kind:          test file")

    if rec.tracked:
        out.append(
            f"git:           last commit {rec.last_commit} ({rec.age_days}d ago), first {rec.first_commit}; "
            f"{rec.commits_year} commits / {rec.authors_year} authors in the last 365d"
        )
    elif a.activity is not None:
        out.append("git:           no history for this file (new or untracked)")

    if rec.analyzer:
        route = g.chain(path)
        if len(route) > 1:
            out.append("reached via:   " + " -> ".join(route))
        out.append(f"depended on by: {_fmt(g.inbound.get(path, ()))}")
        out.append(f"named in config/scripts: {_fmt(g.config_refs.get(path, ()))}")
        out.append(f"mentioned in docs: {_fmt(g.doc_refs.get(path, ()))}")
        deps = sorted(g.edges.get(path, ()))
        out.append("depends on:    " + _fmt(f"{d} [{a.records[d].status}]" if d in a.records and a.records[d].status else d for d in deps))
        stranded = g.stranded_if_removed(path)
        if stranded:
            out.append(f"deleting it would also strand: {_fmt(stranded)}")

    for note in rec.notes:
        out.append(f"note:          {note}")
    if rec.status == "ORPHAN":
        out += [
            "",
            "Before deleting: search the repo for the file's module name and public symbols (dynamic lookups, "
            "registries, external consumers), and run the test suite. If the file is intentionally public, add it "
            "to `keep` in .repolife.toml.",
        ]
    return "\n".join(out)
