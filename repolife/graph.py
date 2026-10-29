"""Language-agnostic reachability engine.

Inputs come from analyzer plugins (edges, roots, tests) plus references found in
config and scripts (textrefs). A file is:

  prod  - reachable from an entry point that is not a test
  test  - a test, or reachable only from tests
  none  - reachable from nothing: an orphan candidate
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Collection, Iterable, Mapping

from . import inventory
from .analyzers import LanguageResult
from .textrefs import PathIndex, TextScan


def _bfs(roots: Iterable[str], edges: Mapping[str, set[str]], skip: str | None = None) -> dict[str, str | None]:
    """Breadth-first search; returns node -> predecessor (None for roots)."""
    parent: dict[str, str | None] = {r: None for r in roots if r != skip}
    queue = deque(parent)
    while queue:
        node = queue.popleft()
        for nxt in sorted(edges.get(node, ())):
            if nxt != skip and nxt not in parent:
                parent[nxt] = node
                queue.append(nxt)
    return parent


@dataclass
class Graph:
    analyzed: set[str] = field(default_factory=set)
    edges: dict[str, set[str]] = field(default_factory=dict)
    roots: dict[str, list[str]] = field(default_factory=dict)  # entry points -> reasons; never test files
    tests: set[str] = field(default_factory=set)
    config_refs: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # file -> configs/scripts naming it
    doc_refs: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # file -> docs mentioning it
    inbound: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # file -> files depending on it
    prod_parent: dict[str, str | None] = field(default_factory=dict)
    test_parent: dict[str, str | None] = field(default_factory=dict)

    def reachability(self, path: str) -> str | None:
        if path not in self.analyzed:
            return None
        if path in self.tests:
            return "test"
        if path in self.prod_parent:
            return "prod"
        return "test" if path in self.test_parent else "none"

    def chain(self, path: str) -> list[str]:
        """Entry point -> ... -> path, preferring a production route."""
        parents = self.prod_parent if path in self.prod_parent else self.test_parent
        route: list[str] = []
        node: str | None = path
        while node is not None and node in parents:
            route.append(node)
            node = parents[node]
        return route[::-1]

    def stranded_if_removed(self, path: str) -> list[str]:
        """Production files that would become unreachable if `path` were deleted."""
        if path not in self.prod_parent:
            return []
        roots = [r for r in self.roots if r not in self.tests]
        still = _bfs(roots, self.edges, skip=path)
        return sorted(set(self.prod_parent) - set(still) - {path})


def build(
    results: list[LanguageResult],
    analyzed: Collection[str],
    scans: Mapping[str, TextScan],
    keep: Collection[str] = (),
    entry: Collection[str] = (),
) -> Graph:
    g = Graph(analyzed=set(analyzed))
    for res in results:
        for path, targets in res.edges.items():
            g.edges.setdefault(path, set()).update(targets)
        for path, why in res.roots.items():
            g.roots.setdefault(path, []).extend(why)
        g.tests |= res.tests

    def resolve(ref: str) -> set[str]:
        found: set[str] = set()
        for res in results:
            found |= res.resolve_reference(ref)
        return found

    paths = PathIndex(g.analyzed)
    for src, scan in scans.items():
        targets: set[str] = set()
        for ref in scan.dotted:
            targets |= resolve(ref)
        for token in scan.paths:
            targets |= paths.resolve(token)
        targets.discard(src)
        bucket = g.doc_refs if scan.weak else g.config_refs
        for t in targets:
            bucket[t].add(src)

    for target, sources in g.config_refs.items():
        g.roots.setdefault(target, []).append(f"config-ref: {sorted(sources)[0]}")
    for path in g.analyzed:
        if inventory.matches(path, keep):
            g.roots.setdefault(path, []).append("keep")
    for item in entry:
        for path in resolve(item) | paths.resolve(item):
            g.roots.setdefault(path, []).append(f"entry: {item}")

    for src, targets in g.edges.items():
        for t in targets:
            if t != src:
                g.inbound[t].add(src)

    g.roots = {p: why for p, why in g.roots.items() if p not in g.tests}
    g.prod_parent = _bfs(g.roots, g.edges)
    g.test_parent = _bfs(g.tests, g.edges)
    return g
