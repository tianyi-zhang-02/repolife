"""Language-neutral references found in non-code text: configs, scripts, CI files, docs.

Frameworks wire code together by name: hydra `_target_: pkg.mod.Class`, registries,
console-script entry points, `python examples/run.py` in a shell script. A pure import
graph misses all of that, so these references are extracted separately and resolved
against the analyzers' module indexes.
"""

from __future__ import annotations

import configparser
import posixpath
import re
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

# A dotted (or `pkg.mod:func`) name that is not the tail of a longer path.
DOTTED = re.compile(r"(?<![\w/.\-])[A-Za-z_]\w*(?:[.:][A-Za-z_]\w*)+")
DOTTED_FULL = re.compile(r"[A-Za-z_]\w*(?:[.:][A-Za-z_]\w*)+")
PYPATH = re.compile(r"[\w./\-]+\.py\b")
# A source file path in any supported language: `scripts/run.py`, `node scripts/build.mjs`, `/src/main.tsx`.
CODEPATH = re.compile(r"[\w./@\-]+\.(?:py|[cm]?[jt]sx?|vue|svelte|astro)\b")

# `config.yaml` looks like module `config` + attribute `yaml`; it is a file name.
_FILE_EXTS = frozenset(
    "py pyi yaml yml json toml cfg ini md rst mdx txt sh bash zsh js ts tsx jsx mjs cjs mts cts vue svelte astro html css csv jsonl log lock sql so whl gz zip tar png jpg svg pdf ipynb".split()
)


# Configs that *enumerate* modules for a tool (type checker include lists, lint
# per-file ignores, coverage omit lists). Naming a module there is not evidence
# that anything uses it, so these files are not scanned at all.
TOOLING_CONFIGS = frozenset(
    {
        "pyrefly.toml", "mypy.ini", ".mypy.ini", "pyrightconfig.json", "ruff.toml", ".ruff.toml", ".flake8",
        ".pylintrc", "pylintrc", "tox.ini", ".coveragerc", "codecov.yml", ".codecov.yml", "codecov.yaml",
        ".importlinter", ".pyre_configuration", ".bandit", "bandit.yaml", ".isort.cfg",
    }
)  # fmt: skip

# The JSON files that do wire code together: scripts and entry points, extension manifests, build targets.
WIRING_JSON = frozenset({"package.json", "manifest.json", "angular.json", "project.json", "deno.json", "vercel.json", "firebase.json"})

# Output and documentation areas: a mention there is not a use.
WEAK_DIRS = frozenset({"docs", "doc", "reports", "report", "results", "logs", "outputs", "artifacts"})


def scan_mode(path: str, lang_name: str, kind: str) -> str | None:
    """How a non-code file's references count: "strong" (real wiring), "weak" (a mention) or None (ignore)."""
    name = posixpath.basename(path)
    if name in TOOLING_CONFIGS:
        return None
    if kind == "docs" or any(d in WEAK_DIRS for d in path.split("/")[:-1]):
        return "weak"
    if lang_name == "JSON" and name not in WIRING_JSON:
        return "weak"  # JSON is overwhelmingly data and generated output
    if kind == "config" or lang_name in ("Shell", "HTML"):  # <script src="/src/main.tsx"> is wiring
        return "strong"
    return None


@dataclass
class TextScan:
    dotted: set[str] = field(default_factory=set)
    paths: set[str] = field(default_factory=set)
    weak: bool = False  # documentation: counts as a mention, not as a use


def scan_text(text: str, weak: bool = False) -> TextScan:
    scan = TextScan(weak=weak)
    for m in DOTTED.finditer(text):
        token = m.group()
        if re.split(r"[.:]", token)[-1].lower() not in _FILE_EXTS:
            scan.dotted.add(token)
    scan.paths.update(CODEPATH.findall(text))
    return scan


def scan_pyproject(text: str) -> TextScan:
    """Only entry-point tables count; lint/coverage config names modules without using them."""
    scan = TextScan()
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return scan
    tables = [
        data.get("project", {}).get("scripts"),
        data.get("project", {}).get("gui-scripts"),
        data.get("tool", {}).get("poetry", {}).get("scripts"),
        *(data.get("project", {}).get("entry-points", {}) or {}).values(),
    ]
    for table in tables:
        if isinstance(table, dict):
            for value in table.values():
                if isinstance(value, str):
                    scan.dotted.add(value.split()[0])
    return scan


def scan_setup_cfg(text: str) -> TextScan:
    """Only `[options.entry_points]` counts; `[flake8]`/`[mypy]` sections list modules without using them."""
    scan = TextScan()
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read_string(text)
    except configparser.Error:
        return scan
    for section in parser.sections():
        if section.startswith("options.entry_points"):
            for _, value in parser.items(section):
                for line in value.splitlines():
                    _, _, target = line.partition("=")
                    if target.strip():
                        scan.dotted.add(target.split()[0])
    return scan


class PathIndex:
    """Resolve a path-like token (`./examples/run.py`, `run.py`) to repository files."""

    def __init__(self, paths: Iterable[str]):
        self.paths = set(paths)
        self._by_name: dict[str, list[str]] = defaultdict(list)
        for p in self.paths:
            self._by_name[posixpath.basename(p)].append(p)

    def resolve(self, token: str) -> set[str]:
        while token.startswith(("./", "../", "/")):  # the config file's own directory is unknown, so match by suffix
            token = token[token.index("/") + 1 :]
        if token in self.paths:
            return {token}
        suffix = "/" + token
        return {p for p in self._by_name.get(posixpath.basename(token), ()) if p.endswith(suffix)}
