"""Who is responsible for each part of the code.

Observed ownership comes from git. Every commit credits its author with the files it touched and
recent commits count more (see gitlog.HALF_LIFE_DAYS), so a file's owner is whoever has been maintaining
it lately, not whoever wrote it first. Whether an owner is still around is judged by their newest commit
anywhere in the repository. Declared ownership comes from CODEOWNERS. Git cannot say who reviewed or who
is accountable; this reports who has been changing the code and whether they still are.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, field

from .gitlog import Activity, Author

OWNED, UNOWNED, UNKNOWN = "owned", "no-active-owner", "unknown"

ACTIVE_SHARE_MIN = 0.20  # people still active must hold this much of the maintenance for a file or area to count as owned
LISTED_MIN = 0.10  # owners below this share are left out of lists (the largest one is always listed)
CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS", ".gitlab/CODEOWNERS")  # first one found wins

_NOREPLY = re.compile(r"^(?:\d+\+)?([^@+]+)@users\.noreply\.github\.com$", re.I)


@dataclass(frozen=True)
class Owner:
    name: str
    share: float  # 0..1 of the file's (or area's) maintenance
    idle_days: int  # days since this person last committed anywhere in the repository


@dataclass
class FileOwnership:
    shares: dict[str, float]  # identity -> share; sums to 1, empty when git has no usable history for the file
    state: str  # OWNED | UNOWNED | UNKNOWN
    declared: tuple[str, ...] | None = None  # CODEOWNERS owners; None when the repository has no CODEOWNERS file
    declared_match: bool | None = None  # whether a declared owner is among the people who maintain it; None when undecidable


@dataclass
class Ownership:
    authors: dict[str, Author]
    files: dict[str, FileOwnership]
    inactive_days: int
    now: float
    codeowners: str | None = None  # path of the CODEOWNERS file that was used
    rules: int = 0

    def idle_days(self, who: str) -> int:
        return max(0, int((self.now - self.authors[who].last) // 86400))

    def is_active(self, who: str) -> bool:
        return self.idle_days(who) <= self.inactive_days

    def owners(self, shares: Mapping[str, float]) -> list[Owner]:
        ranked = sorted(shares.items(), key=lambda kv: (-kv[1], self.authors[kv[0]].name, kv[0]))
        listed = [kv for kv in ranked if kv[1] >= LISTED_MIN] or ranked[:1]
        return [Owner(self.authors[k].name, s, self.idle_days(k)) for k, s in listed]

    def state(self, shares: Mapping[str, float]) -> str:
        if not shares:
            return UNKNOWN
        return OWNED if sum(s for k, s in shares.items() if self.is_active(k)) >= ACTIVE_SHARE_MIN else UNOWNED


@dataclass
class Area:
    """Ownership of a set of files, weighted by their lines of code."""

    owners: list[Owner]
    state: str
    code: int  # code lines with a usable history
    unattributed: int  # code lines without one
    lines: dict[str, float] = field(default_factory=dict)  # identity -> code lines attributed


def rollup(own: Ownership, items: Iterable[tuple[str, int]]) -> Area:
    """Combine files, given as (path, code lines), into one area: each file's lines are split by its shares."""
    lines: dict[str, float] = defaultdict(float)
    attributed = unattributed = 0
    for path, code in items:
        if code <= 0:
            continue
        found = own.files.get(path)
        if found is None or not found.shares:
            unattributed += code
            continue
        attributed += code
        for who, share in found.shares.items():
            lines[who] += code * share
    shares = {who: n / attributed for who, n in lines.items()} if attributed else {}
    return Area(own.owners(shares), own.state(shares), attributed, unattributed, dict(lines))


def bus_factor(area: Area) -> int:
    """The fewest people who together hold at least half of the attributed code (0 when nothing is attributed)."""
    held = 0.0
    for count, lines in enumerate(sorted(area.lines.values(), reverse=True), 1):
        held += lines
        if held * 2 >= area.code:
            return count
    return 0


# --- CODEOWNERS ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    regex: re.Pattern[str]
    owners: tuple[str, ...]


def _bracket(body: str, i: int) -> tuple[str, int] | None:
    close = body.find("]", i + 2)
    if close < 0:
        return None
    inner = body[i + 1 : close]
    if inner.startswith("!"):
        inner = "^" + inner[1:]
    return "[" + inner.replace("\\", "\\\\") + "]", close + 1


def _compile(pattern: str) -> re.Pattern[str]:
    """A CODEOWNERS pattern as a regex over repository-relative paths.

    Like .gitignore, except that a wildcard in the last segment does not reach into subdirectories:
    `docs/*` owns the files directly in docs/, `docs/` owns everything below it.
    """
    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    only_dir = pattern.endswith("/")
    body = pattern.strip("/")
    out: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[" and (cls := _bracket(body, i)):
            out.append(cls[0])
            i = cls[1]
        elif c == "\\" and i + 1 < len(body):
            out.append(re.escape(body[i + 1]))
            i += 2
        else:
            out.append(re.escape(c))
            i += 1
    last = body.rsplit("/", 1)[-1]
    tail = "/.*" if only_dir else "" if any(ch in last for ch in "*?[") else "(?:/.*)?"
    return re.compile("^" + ("" if anchored else "(?:.*/)?") + "".join(out) + tail + "$", re.S)


def parse_codeowners(text: str) -> list[Rule]:
    """Rules in file order. GitLab section headers are skipped; a rule without owners leaves its paths unowned."""
    rules = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "[", "^[")):
            continue
        pattern, *rest = line.split()
        owners = []
        for token in rest:
            if token.startswith("#"):
                break
            owners.append(token)
        try:
            rules.append(Rule(_compile(pattern[1:] if pattern.startswith("\\#") else pattern), tuple(owners)))
        except re.error:
            continue
    return rules


def declared_for(rules: list[Rule], path: str) -> tuple[str, ...]:
    """Owners from the last rule that matches `path`; empty when none does."""
    for rule in reversed(rules):
        if rule.regex.match(path):
            return rule.owners
    return ()


def find_codeowners(paths: Collection[str], read: Callable[[str], str | None]) -> tuple[str, list[Rule]] | None:
    for candidate in CODEOWNERS_PATHS:
        if candidate in paths:
            text = read(candidate)
            if text is not None:
                return candidate, parse_codeowners(text)
    return None


def _handle(email: str) -> str | None:
    """The GitHub login behind a `<id>+<login>@users.noreply.github.com` address; other addresses reveal none."""
    found = _NOREPLY.match(email)
    return found.group(1).lower() if found else None


def _declared_match(own: Ownership, declared: tuple[str, ...], shares: Mapping[str, float]) -> bool | None:
    """Is a declared owner among the people who maintain the file? None when the evidence cannot decide.

    A `@login` can only be compared with authors who committed from a GitHub noreply address, an email with
    any author, and a `@org/team` with nobody, because git does not know teams.
    """
    if not declared or not shares:
        return None
    main = [who for who, share in shares.items() if share >= ACTIVE_SHARE_MIN] or sorted(shares, key=lambda w: -shares[w])[:3]
    undecided = False
    for owner in declared:
        wanted = owner.lower()
        if wanted.startswith("@") and "/" in wanted:
            undecided = True
            continue
        for who in main:
            emails = own.authors[who].emails
            if wanted.startswith("@"):
                handles = {h for e in emails if (h := _handle(e))}
                if wanted[1:] in handles:
                    return True
                if not handles:
                    undecided = True
            elif wanted in emails:
                return True
    return None if undecided else False


def compute(
    activity: Activity,
    inactive_days: int,
    now: float,
    paths: Iterable[str],
    codeowners: tuple[str, list[Rule]] | None = None,
) -> Ownership:
    own = Ownership(activity.authors, {}, inactive_days, now)
    rules: list[Rule] = []
    if codeowners:
        own.codeowners, rules = codeowners[0], codeowners[1]
        own.rules = len(rules)
    for path in paths:
        weights = activity.credit.get(path) or {}
        total = sum(weights.values())
        shares = {who: w / total for who, w in weights.items()} if total > 0 else {}
        declared = declared_for(rules, path) if own.codeowners else None
        own.files[path] = FileOwnership(
            shares=shares,
            state=own.state(shares),
            declared=declared,
            declared_match=_declared_match(own, declared, shares) if declared else None,
        )
    return own
