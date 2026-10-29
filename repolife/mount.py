"""`repolife init`: mount repolife into any repository, new or existing.

Safe to run repeatedly. Files repolife owns outright are created once and never overwritten
without --force. Shared files (AGENTS.md, .gitignore) only ever get a clearly marked block or
a single line, which later runs update in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import templates

BEGIN = "<!-- repolife:begin -->"
END = "<!-- repolife:end -->"


@dataclass
class Action:
    path: str
    verb: str  # created | updated | unchanged | skipped


def _write(path: Path, text: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _owned_file(root: Path, rel: str, content: str, force: bool, dry_run: bool) -> Action:
    path = root / rel
    if not path.exists():
        _write(path, content, dry_run)
        return Action(rel, "created")
    if path.read_text(encoding="utf-8", errors="replace") == content:
        return Action(rel, "unchanged")
    if not force:
        return Action(rel, "skipped")  # a user-edited file: leave it alone
    _write(path, content, dry_run)
    return Action(rel, "updated")


def _marked_block(root: Path, rel: str, body: str, dry_run: bool) -> Action:
    path = root / rel
    block = f"{BEGIN}\n{body.rstrip()}\n{END}"
    if not path.exists():
        _write(path, block + "\n", dry_run)
        return Action(rel, "created")
    text = path.read_text(encoding="utf-8", errors="replace")
    start, end = text.find(BEGIN), text.find(END)
    if start != -1 and end > start:
        new = text[:start] + block + text[end + len(END) :]
    else:
        new = text.rstrip("\n") + ("\n\n" if text.strip() else "") + block + "\n"
    if new == text:
        return Action(rel, "unchanged")
    _write(path, new, dry_run)
    return Action(rel, "updated")


def _ignore_line(root: Path, line: str, dry_run: bool) -> Action:
    path = root / ".gitignore"
    if not path.exists():
        _write(path, line + "\n", dry_run)
        return Action(".gitignore", "created")
    text = path.read_text(encoding="utf-8", errors="replace")
    if line in (entry.strip() for entry in text.splitlines()):
        return Action(".gitignore", "unchanged")
    _write(path, text.rstrip("\n") + "\n" + line + "\n", dry_run)
    return Action(".gitignore", "updated")


def mount(root: Path, agents: set[str], ci: str | None, install_spec: str, force: bool = False, dry_run: bool = False) -> list[Action]:
    actions = [_owned_file(root, ".repolife.toml", templates.CONFIG, force, dry_run)]
    if "claude" in agents:
        actions.append(_owned_file(root, ".claude/skills/repolife/SKILL.md", templates.SKILL, force, dry_run))
    if "agents" in agents:
        actions.append(_marked_block(root, "AGENTS.md", templates.AGENTS_BLOCK, dry_run))
    if ci == "github":
        workflow = templates.GITHUB_WORKFLOW.replace("__INSTALL_SPEC__", install_spec)
        actions.append(_owned_file(root, ".github/workflows/repolife.yml", workflow, force, dry_run))
    actions.append(_ignore_line(root, ".repolife/", dry_run))
    return actions
