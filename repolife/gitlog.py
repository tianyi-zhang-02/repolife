"""Per-file git activity from a single `git log` pass."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileActivity:
    first: int  # epoch seconds of the oldest commit touching the file
    last: int  # epoch seconds of the newest commit touching the file
    commits_active: int  # commits inside the active window
    commits_year: int  # commits in the last 365 days
    authors_year: int  # distinct authors in the last 365 days


@dataclass
class Activity:
    files: dict[str, FileActivity]
    head: str | None
    shallow: bool
    commits: int


def _git_line(root: Path, *args: str) -> str | None:
    try:
        res = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def load(root: Path, now: float, active_days: int) -> Activity | None:
    """Return None when `root` is not a git work tree or has no commits.

    Paths are relative to `root` (`--relative`), so a sub-directory of a larger
    repository is analysed on its own history. Merge commits list no files and
    renames are not followed, which keeps counts deterministic.
    """
    cmd = [
        "git", "-c", "core.quotepath=false", "-C", str(root), "log",
        "--relative", "--no-renames", "--name-only", "--format=%x1e%at%x09%aN",
    ]  # fmt: skip
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None

    active_cut = now - active_days * 86400
    year_cut = now - 365 * 86400
    stats: dict[str, list] = {}  # path -> [first, last, active, year, {authors}]
    commits = 0
    when, who = 0, ""
    assert proc.stdout is not None
    with proc:  # closes the pipe and reaps the process
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line.startswith("\x1e"):
                stamp, _, who = line[1:].partition("\t")
                try:
                    when = int(stamp)
                except ValueError:
                    when = 0
                commits += 1
            elif line:
                entry = stats.get(line)
                if entry is None:
                    entry = stats[line] = [when, when, 0, 0, set()]
                entry[0] = min(entry[0], when)
                entry[1] = max(entry[1], when)
                if when >= active_cut:
                    entry[2] += 1
                if when >= year_cut:
                    entry[3] += 1
                    entry[4].add(who)
    if proc.returncode != 0 or commits == 0:
        return None

    files = {p: FileActivity(s[0], s[1], s[2], s[3], len(s[4])) for p, s in stats.items()}
    return Activity(
        files=files,
        head=_git_line(root, "rev-parse", "--short", "HEAD"),
        shallow=_git_line(root, "rev-parse", "--is-shallow-repository") == "true",
        commits=commits,
    )
