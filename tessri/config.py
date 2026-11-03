"""Configuration: `.tessri.toml`, or `[tool.tessri]` in pyproject.toml. CLI flags extend or override. The old names
(see `legacy`) are still read when the new ones are absent; `Config.notes` says when that happened."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import legacy

_INT_KEYS = ("active_days", "dormant_days", "owner_inactive_days", "review_days", "depth", "top")
_LIST_KEYS = ("keep", "exclude", "entry", "ignore_authors")


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    active_days: int = 90  # touched within this many days => ACTIVE
    dormant_days: int = 365  # untouched for this long (and little used) => DORMANT
    owner_inactive_days: int = 180  # an author with no commit anywhere in the repository for this long no longer counts as an owner
    review_days: int = 30  # review load: changes in this many days, against the same number before (0 turns it off)
    depth: int = 1  # directory depth for the per-directory rollup
    top: int = 15  # rows in "largest files" and "hotspots"
    keep: list[str] = field(default_factory=list)  # globs never reported as orphans (public API, plugins)
    exclude: list[str] = field(default_factory=list)  # globs skipped entirely
    entry: list[str] = field(default_factory=list)  # extra entry points: module names or paths
    ignore_authors: list[str] = field(default_factory=list)  # globs on commit author name or email that never own code (bots are ignored already)
    notes: list[str] = field(default_factory=list)  # how the configuration was assembled, when a caller should know (an old file name was read, or ignored)


def _read(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def _apply(cfg: Config, data: dict, origin: str) -> None:
    for key, value in data.items():
        if key in _INT_KEYS:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ConfigError(f"{origin}: `{key}` must be a non-negative integer")
            setattr(cfg, key, value)
        elif key in _LIST_KEYS:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ConfigError(f"{origin}: `{key}` must be a list of strings")
            getattr(cfg, key).extend(v for v in value if v not in getattr(cfg, key))
        else:
            raise ConfigError(f"{origin}: unknown option `{key}`")


def load(root: Path) -> Config:
    """pyproject.toml first, then the dotfile on top. Under each, the new name wins; the old one is read only when the
    new is absent, and either way a note records what happened, so that a stale old file is never silently in force."""
    cfg = Config()
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        tool = _read(pyproject).get("tool", {})
        section, old = tool.get("tessri"), tool.get(legacy.CONFIG_SECTION)
        if section:
            _apply(cfg, section, f"{pyproject.name} [tool.tessri]")
            if old:
                cfg.notes.append(f"{pyproject.name}: [tool.{legacy.CONFIG_SECTION}] ignored because [tool.tessri] exists")
        elif old:
            _apply(cfg, old, f"{pyproject.name} [tool.{legacy.CONFIG_SECTION}]")
            cfg.notes.append(f"{pyproject.name}: read [tool.{legacy.CONFIG_SECTION}]; rename the section to [tool.tessri] (the old name is read through 0.2.x)")
    dotfile, old_dotfile = root / ".tessri.toml", root / legacy.CONFIG_FILE
    if dotfile.is_file():
        _apply(cfg, _read(dotfile), dotfile.name)
        if old_dotfile.is_file():
            cfg.notes.append(f"{old_dotfile.name} ignored because {dotfile.name} exists")
    elif old_dotfile.is_file():
        _apply(cfg, _read(old_dotfile), old_dotfile.name)
        cfg.notes.append(f"read {old_dotfile.name}; rename it to {dotfile.name} (the old name is read through 0.2.x)")
    return cfg
