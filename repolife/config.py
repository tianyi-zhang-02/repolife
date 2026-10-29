"""Configuration: `.repolife.toml`, or `[tool.repolife]` in pyproject.toml. CLI flags extend or override."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_INT_KEYS = ("active_days", "dormant_days", "owner_inactive_days", "depth", "top")
_LIST_KEYS = ("keep", "exclude", "entry", "ignore_authors")


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    active_days: int = 90  # touched within this many days => ACTIVE
    dormant_days: int = 365  # untouched for this long (and little used) => DORMANT
    owner_inactive_days: int = 180  # an author with no commit anywhere in the repository for this long no longer counts as an owner
    depth: int = 1  # directory depth for the per-directory rollup
    top: int = 15  # rows in "largest files" and "hotspots"
    keep: list[str] = field(default_factory=list)  # globs never reported as orphans (public API, plugins)
    exclude: list[str] = field(default_factory=list)  # globs skipped entirely
    entry: list[str] = field(default_factory=list)  # extra entry points: module names or paths
    ignore_authors: list[str] = field(default_factory=list)  # globs on commit author name or email that never own code (bots are ignored already)


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
    cfg = Config()
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        section = _read(pyproject).get("tool", {}).get("repolife")
        if section:
            _apply(cfg, section, f"{pyproject.name} [tool.repolife]")
    dotfile = root / ".repolife.toml"
    if dotfile.is_file():
        _apply(cfg, _read(dotfile), dotfile.name)
    return cfg
