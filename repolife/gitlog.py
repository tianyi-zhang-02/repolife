"""Per-file git activity and per-author credit from a single `git log` pass."""

from __future__ import annotations

import fnmatch
import re
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

HALF_LIFE_DAYS = 365  # when crediting ownership, a commit loses half its weight per year
BULK_FILES = 300  # a commit touching this many files (mass reformat, vendor drop, first import) says little about who maintains each one
_BOT = re.compile(r"\[bot\]|^(?:dependabot|renovate|github-actions|pre-commit-ci)\b", re.I)


@dataclass
class FileActivity:
    first: int  # epoch seconds of the oldest commit touching the file
    last: int  # epoch seconds of the newest commit touching the file
    commits_active: int  # commits inside the active window
    commits_year: int  # commits in the last 365 days
    authors_year: int  # distinct authors in the last 365 days


@dataclass
class Author:
    name: str  # as written on their newest commit
    emails: set[str]  # every address they committed from, lowercase; identifies the person and never goes in a report
    last: int  # epoch seconds of their newest commit anywhere in the repository


@dataclass
class Activity:
    files: dict[str, FileActivity]
    head: str | None
    shallow: bool
    commits: int
    authors: dict[str, Author]  # identity -> author; bots and ignored authors are left out
    credit: dict[str, dict[str, float]]  # path -> identity -> commits, recent ones weighing more


def _git_line(root: Path, *args: str) -> str | None:
    try:
        res = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def identity(name: str, email: str) -> str:
    """One key per person. People commit from several addresses (work, personal, GitHub noreply), and keying by
    address made a maintainer look gone whenever their recent commits used another one, so the name is the key.
    Two people sharing a name get merged, which hides a gap rather than inventing one; a `.mailmap` entry is
    the exact fix either way. A name that is empty or is itself an address says nothing, so the address is used."""
    name = " ".join(name.split()).casefold()
    return name if name and "@" not in name else (email or name).lower()


def is_ignored(name: str, email: str, patterns: Sequence[str]) -> bool:
    """Bots never own code; `ignore_authors` globs are matched against the name and the email, ignoring case."""
    if _BOT.search(name) or _BOT.search(email):
        return True
    return any(fnmatch.fnmatchcase(v.lower(), p.lower()) for p in patterns for v in (name, email))


def _commits(lines) -> Iterator[tuple[int, str, str, list[str]]]:
    """(epoch, author name, author email, files) for each commit in a `git log --name-only` stream."""
    head: tuple[int, str, str] | None = None
    files: list[str] = []
    for line in lines:
        line = line.rstrip("\n")
        if line.startswith("\x1e"):
            if head:
                yield (*head, files)
            stamp, _, rest = line[1:].partition("\t")
            name, _, email = rest.partition("\t")
            try:
                head = (int(stamp), name, email)
            except ValueError:
                head = (0, name, email)
            files = []
        elif line:
            files.append(line)
    if head:
        yield (*head, files)


def load(root: Path, now: float, active_days: int, ignore_authors: Sequence[str] = ()) -> Activity | None:
    """Return None when `root` is not a git work tree or has no commits.

    Paths are relative to `root` (`--relative`), so a sub-directory of a larger
    repository is analysed on its own history. Merge commits list no files and
    renames are not followed, which keeps counts deterministic. Names and emails
    go through `.mailmap`, so one person with several addresses can be merged.
    """
    cmd = [
        "git", "-c", "core.quotepath=false", "-C", str(root), "log",
        "--relative", "--no-renames", "--name-only", "--format=%x1e%at%x09%aN%x09%aE",
    ]  # fmt: skip
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None

    active_cut = now - active_days * 86400
    year_cut = now - 365 * 86400
    stats: dict[str, list] = {}  # path -> [first, last, active, year, {authors}]
    authors: dict[str, Author] = {}
    credit: dict[str, dict[str, float]] = {}
    bulk: dict[str, dict[str, float]] = {}  # credit from bulk commits, used only for files nothing else touched
    commits = 0
    assert proc.stdout is not None
    with proc:  # closes the pipe and reaps the process
        for when, who, email, files in _commits(proc.stdout):
            commits += 1
            person = None if is_ignored(who, email, ignore_authors) else identity(who, email)
            weight = 0.5 ** (max(0.0, now - when) / (HALF_LIFE_DAYS * 86400))
            if person:
                known = authors.get(person)
                if known is None:  # the log is newest first, so the first sighting is the newest commit
                    authors[person] = Author(who, {email.lower()}, when)
                else:
                    known.emails.add(email.lower())
                    known.last = max(known.last, when)
            target = bulk if len(files) >= BULK_FILES else credit
            for path in files:
                entry = stats.get(path)
                if entry is None:
                    entry = stats[path] = [when, when, 0, 0, set()]
                entry[0] = min(entry[0], when)
                entry[1] = max(entry[1], when)
                if when >= active_cut:
                    entry[2] += 1
                if when >= year_cut:
                    entry[3] += 1
                    entry[4].add(who)
                if person:
                    slot = target.setdefault(path, {})
                    slot[person] = slot.get(person, 0.0) + weight
    if proc.returncode != 0 or commits == 0:
        return None
    for path, slot in bulk.items():
        credit.setdefault(path, slot)

    return Activity(
        files={p: FileActivity(s[0], s[1], s[2], s[3], len(s[4])) for p, s in stats.items()},
        head=_git_line(root, "rev-parse", "--short", "HEAD"),
        shallow=_git_line(root, "rev-parse", "--is-shallow-repository") == "true",
        commits=commits,
        authors=authors,
        credit=credit,
    )
