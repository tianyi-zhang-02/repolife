"""Language analyzer plugin API.

The reachability engine (graph.py) knows nothing about any language. It consumes the
`LanguageResult` that an analyzer returns for the files it handles:

  edges      file -> files it depends on (imports, includes, requires ...)
  roots      file -> why it is an entry point (script guard, main(), CLI entry ...)
  tests      files that are tests; code reached only from these is "test-only"
  unparsed   files the analyzer could not parse; they are treated as entry points
             so that nothing they might import is wrongly reported as unused
  resolve_reference
             maps a name found in config/scripts (`pkg.mod.Class`) to files

To support a new language, subclass `Analyzer` and register it, either in
`BUILTIN` below or from a third-party package through the `repolife.analyzers`
entry-point group (the entry point must resolve to an `Analyzer` subclass).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from importlib import metadata
from typing import Callable, Mapping


@dataclass(frozen=True)
class Repo:
    """What an analyzer may know beyond the files it handles: every path, and any file's text.

    Project metadata lives in files no analyzer owns (`tsconfig.json`, `package.json`,
    `go.mod`), so resolution needs to read them.
    """

    paths: frozenset[str]
    read: Callable[[str], str | None]  # None when the file is missing, binary or too large


@dataclass
class LanguageResult:
    edges: dict[str, set[str]] = field(default_factory=dict)
    roots: dict[str, list[str]] = field(default_factory=dict)
    tests: set[str] = field(default_factory=set)
    unparsed: set[str] = field(default_factory=set)
    comment_lines: dict[str, set[int]] = field(default_factory=dict)  # extra lines to count as comments (docstrings)
    resolve_reference: Callable[[str], set[str]] = lambda ref: set()


class Analyzer(ABC):
    name: str = ""

    @abstractmethod
    def handles(self, path: str) -> bool:
        """Whether this analyzer covers the file at repo-relative posix `path`."""

    @abstractmethod
    def run(self, files: Mapping[str, str], repo: Repo) -> LanguageResult:
        """Analyse every handled file at once. `files` maps path -> text."""


def load_analyzers() -> list[Analyzer]:
    from .javascript import JavaScriptAnalyzer
    from .python import PythonAnalyzer

    classes: list[type[Analyzer]] = [PythonAnalyzer, JavaScriptAnalyzer]
    try:
        for ep in metadata.entry_points(group="repolife.analyzers"):
            try:
                cls = ep.load()
            except Exception:  # a broken third-party plugin must not break the scan
                continue
            if isinstance(cls, type) and issubclass(cls, Analyzer) and cls not in classes:
                classes.append(cls)
    except Exception:
        pass
    return [cls() for cls in classes]
