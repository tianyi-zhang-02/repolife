"""File discovery, language detection and line counting. Language-neutral."""

from __future__ import annotations

import fnmatch
import os
import posixpath
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

MAX_FILE_BYTES = 2_000_000

DEFAULT_EXCLUDES = (
    "**/node_modules/**",
    "**/.git/**",
    "**/__pycache__/**",
    "**/.venv/**",
    "**/venv/**",
    "**/build/**",
    "**/dist/**",
    "**/target/**",
    "**/.tox/**",
    "**/*.egg-info/**",
    "**/*.min.js",
    "**/*.min.css",
    "**/*_pb2.py",
    "**/*_pb2_grpc.py",
    "**/*.lock",
    "**/package-lock.json",
    "**/pnpm-lock.yaml",
)

_WALK_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist", "target", ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


@dataclass(frozen=True)
class Lang:
    name: str
    kind: str  # "code" | "config" | "docs"
    line: tuple[str, ...] = ()  # line-comment prefixes
    block: tuple[str, str] | None = None  # block-comment delimiters


_C_BLOCK = ("/*", "*/")
_HTML_BLOCK = ("<!--", "-->")
EXT: dict[str, Lang] = {}
NAMES: dict[str, Lang] = {}


def _reg(lang: Lang, *keys: str) -> None:
    for key in keys:
        (EXT if key.startswith(".") else NAMES)[key] = lang


_reg(Lang("Python", "code", ("#",)), ".py")
_reg(Lang("Python stub", "code", ("#",)), ".pyi")
_reg(Lang("JavaScript", "code", ("//",), _C_BLOCK), ".js", ".jsx", ".mjs", ".cjs")
_reg(Lang("TypeScript", "code", ("//",), _C_BLOCK), ".ts", ".tsx", ".mts", ".cts")
_reg(Lang("Vue", "code", (), _HTML_BLOCK), ".vue")
_reg(Lang("Svelte", "code", (), _HTML_BLOCK), ".svelte")
_reg(Lang("Astro", "code", (), _HTML_BLOCK), ".astro")
_reg(Lang("Java", "code", ("//",), _C_BLOCK), ".java")
_reg(Lang("Kotlin", "code", ("//",), _C_BLOCK), ".kt", ".kts")
_reg(Lang("Scala", "code", ("//",), _C_BLOCK), ".scala")
_reg(Lang("Go", "code", ("//",), _C_BLOCK), ".go")
_reg(Lang("Rust", "code", ("//",), _C_BLOCK), ".rs")
_reg(Lang("C", "code", ("//",), _C_BLOCK), ".c", ".h")
_reg(Lang("C++", "code", ("//",), _C_BLOCK), ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx")
_reg(Lang("CUDA", "code", ("//",), _C_BLOCK), ".cu", ".cuh")
_reg(Lang("C#", "code", ("//",), _C_BLOCK), ".cs")
_reg(Lang("Swift", "code", ("//",), _C_BLOCK), ".swift")
_reg(Lang("PHP", "code", ("//", "#"), _C_BLOCK), ".php")
_reg(Lang("Ruby", "code", ("#",)), ".rb")
_reg(Lang("Shell", "code", ("#",)), ".sh", ".bash", ".zsh")
_reg(Lang("SQL", "code", ("--",), _C_BLOCK), ".sql")
_reg(Lang("Lua", "code", ("--",)), ".lua")
_reg(Lang("HTML", "code"), ".html", ".htm")
_reg(Lang("CSS", "code", (), _C_BLOCK), ".css", ".scss")
_reg(Lang("YAML", "config", ("#",)), ".yaml", ".yml")
_reg(Lang("TOML", "config", ("#",)), ".toml")
_reg(Lang("JSON", "config"), ".json")
_reg(Lang("INI", "config", ("#", ";")), ".ini", ".cfg")
_reg(Lang("XML", "config"), ".xml")
_reg(Lang("Dockerfile", "config", ("#",)), "Dockerfile")
_reg(Lang("Makefile", "config", ("#",)), "Makefile", ".mk")
_reg(Lang("CMake", "config", ("#",)), "CMakeLists.txt", ".cmake")
_reg(Lang("Markdown", "docs"), ".md")
_reg(Lang("MDX", "docs"), ".mdx")
_reg(Lang("reStructuredText", "docs"), ".rst")
_reg(Lang("Text", "docs"), ".txt")


# `recipe.yaml.disabled`, `config.toml.example`: still wiring, just switched off or templated.
_VARIANT_SUFFIXES = (".disabled", ".example", ".sample", ".template", ".tmpl")


def _lookup(name: str) -> Lang | None:
    if name in NAMES:
        return NAMES[name]
    return EXT.get(os.path.splitext(name)[1].lower())


def language_of(path: str) -> Lang | None:
    name = posixpath.basename(path)
    lang = _lookup(name)
    if lang is None:
        for suffix in _VARIANT_SUFFIXES:
            if name.endswith(suffix) and len(name) > len(suffix):
                variant = _lookup(name[: -len(suffix)])
                # Only config and docs variants count; a disabled source file is just a stray file.
                return variant if variant is not None and variant.kind != "code" else None
    return lang


def matches(path: str, patterns: Iterable[str]) -> bool:
    """fnmatch-style globbing where `*` also crosses `/`. A leading `/` is tried so `**/x/**` matches top-level `x/`."""
    return any(fnmatch.fnmatchcase(path, p) or fnmatch.fnmatchcase("/" + path, p) for p in patterns)


def _git_files(root: Path) -> list[str] | None:
    cmd = ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def _walk(root: Path) -> list[str]:
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _WALK_SKIP_DIRS]
        for name in files:
            found.append(os.path.relpath(os.path.join(base, name), root))
    return found


def discover(root: Path, excludes: Sequence[str]) -> tuple[list[str], bool]:
    """Return (sorted repo-relative posix paths, whether git supplied the list).

    Under git the list is tracked plus untracked-but-not-ignored files, so a
    brand-new repo (or a not-yet-committed change) is analysed too.
    """
    listed = _git_files(root)
    used_git = bool(listed)
    if not listed:
        listed = _walk(root)
    out: dict[str, None] = {}
    for rel in listed:
        rel = rel.replace(os.sep, "/")
        if rel in out or matches(rel, excludes):
            continue
        full = root / rel
        if full.is_symlink() or not full.is_file():
            continue
        out[rel] = None
    return sorted(out), used_git


def read_text(path: Path) -> str | None:
    """File contents, or None when the file is too large, binary or unreadable."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", "replace")


def count_lines(text: str, lang: Lang, extra_comment_lines: frozenset[int] | set[int] = frozenset()) -> tuple[int, int, int]:
    """Return (code, comment, blank). `extra_comment_lines` lets an analyzer add e.g. docstring lines."""
    code = comment = blank = 0
    in_block = False
    for number, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s:
            blank += 1
        elif number in extra_comment_lines:
            comment += 1
        elif in_block:
            comment += 1
            if lang.block and lang.block[1] in s:
                in_block = False
        elif lang.block and s.startswith(lang.block[0]):
            comment += 1
            if lang.block[1] not in s[len(lang.block[0]) :]:
                in_block = True
        elif lang.line and s.startswith(lang.line):
            comment += 1
        else:
            code += 1
    return code, comment, blank
