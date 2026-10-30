"""Change triage: for a branch, a range or uncommitted work, which files deserve a human first, what else the
change can ripple into, and who is able to look.

The order is the one a backtest on one large repository found hard to beat: files that were committed to most in the
last 90 days first, then by how much this change touches. Which of those commits were fixes added nothing, so fix
history is shown but does not move a file; blast radius and ownership are shown too, and neither improved the
prediction: they describe what a mistake would cost and who can catch it, not how likely one is. History is read up
to the base of the change, so the change's own commits neither count as activity nor make their author an owner.
"""

from __future__ import annotations

import dataclasses
import subprocess
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, gitlog, inventory
from .analyze import Analysis, analyze
from .config import Config
from .model import SCHEMA_VERSION
from .modules import assign
from .ownership import LISTED_MIN, UNOWNED, owner_rows, rollup

RIPPLE_HOPS = 2  # explicit imports predicted what changes together well at one hop and about as well as the same directory at two
TEST_HOPS = 3
EXAMPLES = 3
REVIEWERS_LISTED = 3
LISTED = 8


class TriageError(ValueError):
    pass


def _git(root: Path, *args: str, check: bool = True) -> str:
    try:
        res = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise TriageError(f"git could not run: {exc}") from exc
    if check and res.returncode != 0:
        raise TriageError((res.stderr.strip().splitlines() or ["git failed"])[-1])
    return res.stdout


def resolve_base(root: Path, since: str) -> tuple[str, str]:
    """(commit to compare with, HEAD): the point where `since` and HEAD part, as a pull request would be judged."""
    if _git(root, "rev-parse", "--is-inside-work-tree", check=False).strip() != "true":
        raise TriageError("triage needs a git repository")
    found = _git(root, "rev-parse", "--verify", "--quiet", f"{since}^{{commit}}", check=False).strip()
    if not found:
        raise TriageError(f"`{since}` is not a commit, branch or tag in this repository")
    head = _git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", check=False).strip()
    if not head:
        raise TriageError("this repository has no commits yet")
    base = _git(root, "merge-base", found, head, check=False).strip()
    if not base:
        raise TriageError(f"`{since}` and HEAD share no history")
    return base, head


def _diff(root: Path, base: str) -> dict[str, tuple[int, int, str]]:
    """path -> (added, deleted, "modified" | "added" | "deleted") between `base` and the working tree, untracked files included."""
    out: dict[str, tuple[int, int, str]] = {}
    names = _git(root, "diff", "--relative", "--name-status", "--no-renames", "-z", base).split("\0")
    kind = {}
    for i in range(0, len(names) - 1, 2):
        kind[names[i + 1]] = {"A": "added", "D": "deleted"}.get(names[i][:1], "modified")
    numstat = _git(root, "diff", "--relative", "--numstat", "--no-renames", "-z", base).split("\0")
    for record in numstat:
        added, _, rest = record.partition("\t")
        deleted, _, path = rest.partition("\t")
        if path:
            moved = (int(added), int(deleted)) if added.isdigit() and deleted.isdigit() else (0, 0)
            out[path] = (*moved, kind.get(path, "modified"))
    for path in _git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if path and path not in out:
            text = inventory.read_text(root / path)
            out[path] = (len(text.splitlines()) if text else 0, 0, "added")
    return out


def _authors(root: Path, base: str, dirty: bool) -> dict[str, str]:
    """identity -> name for the people who wrote the change: its commits, and whoever is configured here when work is uncommitted."""
    found: dict[str, str] = {}
    for line in _git(root, "log", "--no-merges", "--format=%aN%x09%aE", f"{base}..HEAD").splitlines():
        name, _, email = line.partition("\t")
        if name and not gitlog.is_ignored(name, email, ()):
            found.setdefault(gitlog.identity(name, email), name)
    if dirty:
        name = _git(root, "config", "user.name", check=False).strip()
        email = _git(root, "config", "user.email", check=False).strip()
        if name:
            found.setdefault(gitlog.identity(name, email), name)
    return found


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _reverse(a: Analysis) -> dict[str, set[str]]:
    """file -> files that import it by statement (a package's `__init__` running on the way does not count)."""
    g = a.graph
    rev: dict[str, set[str]] = defaultdict(set)
    for src, targets in g.edges.items():
        for dst in targets - g.indirect.get(src, set()) - {src}:
            rev[dst].add(src)
    return rev


def _reach(rev: dict[str, set[str]], start: str, hops: int) -> dict[str, int]:
    seen = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if seen[node] >= hops:
            continue
        for nxt in rev.get(node, ()):
            if nxt not in seen:
                seen[nxt] = seen[node] + 1
                queue.append(nxt)
    del seen[start]
    return seen


def compute(root: Path, cfg: Config, since: str = "HEAD", now: float | None = None) -> dict:
    """The triage of the change between `since` and the working tree, as the JSON-ready dict the commands print."""
    root = Path(root).resolve()
    base, head = resolve_base(root, since)
    diff = _diff(root, base)
    dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=normal").strip())
    a = analyze(root, dataclasses.replace(cfg, review_days=0), now=now, rev=base)
    if a.activity is None or a.ownership is None:
        raise TriageError("triage needs git history")
    own, g = a.ownership, a.graph
    authors = _authors(root, base, dirty)
    skip = [*inventory.DEFAULT_EXCLUDES, *cfg.exclude]

    code: dict[str, tuple[int, int, str]] = {}
    other_files = other_lines = 0
    for path, (added, deleted, state) in diff.items():
        if inventory.matches(path, skip):
            continue
        lang = inventory.language_of(path)
        if lang is not None and lang.kind == "code":
            code[path] = (added, deleted, state)
        else:
            other_files += 1
            other_lines += added + deleted

    def is_test(path: str) -> bool:
        return a.records[path].is_test if path in a.records else path in g.tests

    rev = _reverse(a)
    pool = [p for p, r in a.records.items() if r.kind == "code" and r.analyzer and not r.is_test]
    module_of = assign(pool)
    changed = set(code)
    ripple: dict[str, int] = {}
    tests: dict[str, int] = {}
    rows = []
    for path, (added, deleted, state) in code.items():
        rec = a.records.get(path)
        act = a.activity.files.get(path)
        fixes = act.fixes_90 if act else 0
        busy = act.commits_active if act else 0
        found = own.files.get(path) if rec else None
        shares = found.shares if found else {}
        holders = {who for who, s in shares.items() if s >= LISTED_MIN} or ({max(shares, key=lambda w: (shares[w], w))} if shares else set())
        direct = deeper = 0
        if rec and rec.analyzer:
            for other, dist in _reach(rev, path, max(RIPPLE_HOPS, TEST_HOPS)).items():
                if is_test(other):
                    if dist <= TEST_HOPS:
                        tests[other] = min(tests.get(other, 99), dist)
                    continue
                if dist <= RIPPLE_HOPS:
                    if dist == 1:
                        direct += 1
                    else:
                        deeper += 1
                    if other not in changed:
                        ripple[other] = min(ripple.get(other, 99), dist)
        flags = []
        if state == "added" or (rec is not None and act is None):
            flags.append("new file")
        if state == "deleted":
            flags.append("deleted")
        if found is not None and found.state == UNOWNED:
            flags.append("no active owner")
        if authors and holders and not (holders & set(authors)):
            flags.append("author is not among the owners")
        if rec and rec.status == "ORPHAN":
            flags.append("orphan: nothing reaches it")
        if rec is not None and rec.is_test:
            flags.append("test file")
        fresh = state == "added" or (rec is not None and act is None)
        tier = "busy" if busy else "new" if fresh else "quiet"
        lang = rec.language if rec else (found_lang.name if (found_lang := inventory.language_of(path)) else None)
        row = {
            "path": path,
            "change": state,
            "added": added,
            "deleted": deleted,
            "lines": added + deleted,
            "language": lang,
            "test": bool(rec.is_test) if rec else False,
            "tier": tier,
            "fixes_90": fixes,
            "fixes_year": act.fixes_year if act else 0,
            "commits_active": busy,
            "commits_year": act.commits_year if act else 0,
            "last_commit": _day(act.last) if act else None,
            "owners": owner_rows(own.owners(shares)) if shares else [],
            "ownership": found.state if found else None,
            "dependents": {"direct": direct, "within_2": direct + deeper},
            "flags": flags,
        }
        rows.append(row)
    rows.sort(key=lambda r: (-r["commits_active"], -r["lines"], r["path"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank

    # who can look: the people, other than the authors, who hold the changed files
    weight: dict[str, float] = defaultdict(float)
    covers: dict[str, set[str]] = defaultdict(set)
    nobody_else: list[str] = []
    for row in rows:
        found = own.files.get(row["path"])
        shares = found.shares if found else {}
        able = [who for who, s in shares.items() if s >= LISTED_MIN and own.is_active(who) and who not in authors]
        if shares and not able:
            nobody_else.append(row["path"])
        for who in able:
            weight[who] += row["lines"] * shares[who]
            covers[who].add(row["path"])
    reviewers = [
        {"name": own.authors[who].name, "files": len(covers[who]), "idle_days": own.idle_days(who), "weight": round(w, 1)}
        for who, w in sorted(weight.items(), key=lambda kv: (-kv[1], own.authors[kv[0]].name))[:REVIEWERS_LISTED]
    ]

    by_module: dict[str, dict[str, int]] = defaultdict(lambda: {"direct": 0, "second": 0})
    for other, dist in ripple.items():
        by_module[module_of.get(other, ".")]["direct" if dist == 1 else "second"] += 1
    areas: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "lines": 0})
    area_of = assign({*pool, *code})
    for row in rows:
        slot = areas[area_of.get(row["path"], ".")]
        slot["files"] += 1
        slot["lines"] += row["lines"]
    nearest = sorted(tests, key=lambda p: (tests[p], p))

    notes = [
        "Files are ordered by how many commits touched them in the last 90 days, then by how much this change touches. In a backtest on one large repository "
        "that predicted later fixes about as well as anything simple, and better than the size of the change alone; it says where trouble tends to be, not that this change is wrong. "
        "Fix and revert history is shown but does not reorder: it added nothing beyond activity.",
        "Dependents, tests and owners are context: they show what a mistake could reach and who is able to look, and they did not improve the prediction. "
        "Dependents are static imports; dynamic loading and consumers outside the repository are invisible.",
        "History is read up to the base of the change, so its own commits do not count as trouble and its authors do not count as owners.",
    ]
    if not a.activity.files:
        notes.append("The repository has little history, so the ordering falls back to the size of the change.")
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "repolife", "version": __version__},
        "generated_at": datetime.fromtimestamp(a.now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": {"name": root.name},
        "kind": "triage",
        "change": {"since": since, "base": base[:9], "head": head[:9], "uncommitted": dirty, "authors": sorted(authors.values())},
        "summary": {
            "files": len(rows),
            "lines": sum(r["lines"] for r in rows),
            "recently_fixed": sum(1 for r in rows if r["fixes_90"]),
            "busy": sum(1 for r in rows if r["tier"] == "busy"),
            "new": sum(1 for r in rows if "new file" in r["flags"]),
            "no_active_owner": sum(1 for r in rows if "no active owner" in r["flags"]),
            "nobody_else_can_look": len(nobody_else),
            "other_files": other_files,
            "other_lines": other_lines,
            "areas": len(areas),
            "ripple": {"direct": sum(1 for d in ripple.values() if d == 1), "second": sum(1 for d in ripple.values() if d == 2)},
            "tests": len(tests),
        },
        "files": rows,
        "areas": [{"path": k, **v} for k, v in sorted(areas.items(), key=lambda kv: (-kv[1]["lines"], kv[0]))],
        "ripple": [{"module": k, **v} for k, v in sorted(by_module.items(), key=lambda kv: (-(kv[1]["direct"] + kv[1]["second"]), kv[0]))],
        "ripple_examples": sorted(ripple, key=lambda p: (ripple[p], p))[: 2 * LISTED],
        "tests": {"count": len(tests), "nearest": nearest[:LISTED]},
        "reviewers": reviewers,
        "nobody_else_can_look": sorted(nobody_else)[:LISTED],
        "inactive_days": own.inactive_days,
        "notes": notes,
    }


# --- Markdown ---------------------------------------------------------------------------------------------


def _many(n: int, one: str, many: str | None = None) -> str:
    return f"{n:,} {one if n == 1 else many or one + 's'}"


def _why(row: dict, active_days: int) -> str:
    if row["commits_active"]:
        text = _many(row["commits_active"], "commit") + f" in {active_days} days"
        if row["fixes_90"]:
            text += f", {row['fixes_90']} of them fixes or reverts"
        return text
    if "new file" in row["flags"]:
        return "new file"
    return f"quiet since {row['last_commit']}" if row["last_commit"] else "no history"


def markdown(t: dict, limit: int = 20, active_days: int = 90) -> str:
    from .render import _owners, _table  # the report tables, shared

    c, s = t["change"], t["summary"]
    out = [f"# Change triage: {t['repo']['name']}", ""]
    scope = f"`{c['since']}` (base {c['base']}) to {'the working tree' if c['uncommitted'] else 'HEAD ' + c['head']}"
    out += [f"{scope}. {_many(s['files'], 'code file')} changed, **{s['lines']:,}** lines, in {_many(s['areas'], 'area')}"
            + (f"; {_many(s['other_files'], 'other file')} ({s['other_lines']:,} lines of config, docs and the like) not ranked." if s["other_files"] else "."), ""]
    if not t["files"]:
        return "\n".join(out + ["No code changed.", ""])
    def count(n: int, one: str, many: str) -> str:
        return f"**{n}** file {one}" if n == 1 else f"**{n}** files {many}"

    bullets = []
    if s["recently_fixed"]:
        bullets.append(count(s["recently_fixed"], "was fixed or reverted in the last 90 days", "were fixed or reverted in the last 90 days"))
    if s["no_active_owner"]:
        bullets.append(count(s["no_active_owner"], "has no active owner", "have no active owner") + ": nobody who maintains the code has committed lately")
    if s["nobody_else_can_look"]:
        bullets.append(count(s["nobody_else_can_look"], "is maintained by nobody but the author", "are maintained by nobody but the author"))
    if s["ripple"]["direct"] or s["ripple"]["second"]:
        bullets.append(f"code outside the change that imports it: **{_many(s['ripple']['direct'], 'file')}** directly, {_many(s['ripple']['second'], 'file')} through one more step")
    if s["tests"]:
        bullets.append(f"**{s['tests']}** test {'file reaches' if s['tests'] == 1 else 'files reach'} it")
    if bullets:
        out += [f"- {b}" for b in bullets] + [""]

    gone = t["inactive_days"]
    rows = []
    for r in t["files"][:limit]:
        who = _owners(r["owners"], gone) if r["owners"] else "-"
        rows.append([r["rank"], f"`{r['path']}`", _why(r, active_days), f"+{r['added']} -{r['deleted']}", who, r["dependents"]["direct"], "; ".join(r["flags"]) or "-"])
    out += ["Look at these first:", ""]
    out += _table(["#", "File", "Why", "This change", "Owners", "Imported by", "Flags"], rows, {0, 5})
    if len(t["files"]) > limit:
        out += [f"{len(t['files']) - limit} more files in the JSON output.", ""]
    if t["reviewers"]:
        people = ", ".join(f"{r['name']} ({_many(r['files'], 'file')})" for r in t["reviewers"])
        out += [f"Who can look, other than the authors: {people}. Git cannot see who reviewed; these are the people who maintain the changed files.", ""]
    if t["nobody_else_can_look"]:
        out += ["Only the author maintains: " + ", ".join(f"`{p}`" for p in t["nobody_else_can_look"][:5]) + (" ..." if s["nobody_else_can_look"] > 5 else ""), ""]
    if t["ripple"]:
        out += ["Not in the change, but importing it (by area):", ""]
        out += _table(["Area", "Directly", "One more step"], [[f"`{r['module']}`", r["direct"], r["second"]] for r in t["ripple"][:10]], {1, 2})
    if t["tests"]["nearest"]:
        out += ["Tests that reach it, nearest first: " + ", ".join(f"`{p}`" for p in t["tests"]["nearest"][:5]) + (f" and {t['tests']['count'] - 5} more" if t["tests"]["count"] > 5 else ""), ""]
    out += ["## Read this with care", ""] + [f"- {n}" for n in t["notes"]] + [""]
    return "\n".join(out)
