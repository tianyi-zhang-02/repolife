"""Project knowledge for the JS/TS analyzer: how a specifier becomes a file, and which files are entry points.

Mirrors what a bundler or the TypeScript compiler does with the project: relative paths with
extension probing, tsconfig `paths`/`baseUrl`, package.json `imports`, workspace packages (with
built `dist/` entries mapped back to sources), plus the framework conventions that make a file
an entry point without anything importing it (pages, routes, config files).
"""

from __future__ import annotations

import fnmatch
import json
import posixpath
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Collection, Iterator

from . import Repo

PROBE = (".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro")
SWAP = {".js": (".ts", ".tsx"), ".jsx": (".tsx",), ".mjs": (".mts",), ".cjs": (".cts",)}  # `./x.js` is written for a `x.ts` source
DECLARATION = {"ts": ".js", "mts": ".mjs", "cts": ".cjs"}
BUILD_DIRS = frozenset({"dist", "build", "lib", "out", "esm", "cjs", "es", "es6", "types", "typings", "output", "bundle", "umd", "compiled"})

_TSCONFIG = re.compile(r"(?:ts|js)config(?:\.[\w-]+)?\.json")

# (dependency names, label, paths relative to the package that are entry points by convention)
_FRAMEWORKS = (
    (("next", "vinext"), "Next.js", (
        r"(?:src/)?pages/.*",
        r"(?:src/)?app/(?:.*/)?(?:page|layout|template|loading|error|global-error|not-found|default|route|forbidden|unauthorized|opengraph-image|twitter-image|icon|apple-icon|sitemap|robots|manifest)\.[^/]+",
        r"(?:src/)?(?:middleware|proxy|instrumentation|instrumentation-client|mdx-components)\.[^/]+",
    )),
    (("nuxt",), "Nuxt", (r"(?:app/)?(?:pages|layouts|middleware|plugins|components|composables|utils|stores|server)/.*", r"(?:app/)?(?:app|error)\.[^/]+")),
    (("astro",), "Astro", (r"src/(?:pages|actions)/.*", r"src/(?:middleware|content/config)\.[^/]+")),
    (("@sveltejs/kit",), "SvelteKit", (r"src/routes/.*", r"src/(?:hooks(?:\.\w+)?|service-worker)\.[^/]+", r"src/params/.*")),
    (("@remix-run/react", "@remix-run/node", "@react-router/dev", "react-router"), "Remix / React Router", (
        r"app/(?:routes/.*|root\.[^/]+|routes\.[^/]+|entry\.(?:client|server)\.[^/]+)",
    )),
    (("gatsby",), "Gatsby", (r"src/(?:pages|api)/.*", r"gatsby-(?:config|node|browser|ssr)\.[^/]+")),
    (("@tanstack/react-router", "@tanstack/react-start"), "TanStack Router", (r"(?:src/)?routes/.*", r"(?:src/)?router\.[^/]+")),
    (("expo-router",), "Expo Router", (r"app/.*",)),
    (("expo", "react-native"), "React Native", (r"(?:index|App)\.[^/]+",)),
    (("react-scripts",), "Create React App", (r"src/(?:index|setupTests)\.[^/]+",)),
    (("@vue/cli-service",), "Vue CLI", (r"src/main\.[^/]+",)),
    (("@angular/core",), "Angular", (r"src/(?:main|polyfills|test)\.ts", r"src/main\.server\.ts")),
    (("@nestjs/core",), "NestJS", (r"src/main\.ts",)),
    (("@docusaurus/core",), "Docusaurus", (r"src/(?:pages|theme|plugins)/.*", r"sidebars\.[^/]+")),
    (("vitepress", "vuepress"), "VitePress", (r"\.vitepress/.*",)),
    (("vercel", "@vercel/node"), "Vercel functions", (r"api/.*",)),
)  # fmt: skip
FRAMEWORKS = tuple((frozenset(names), label, tuple(re.compile(p) for p in patterns)) for names, label, patterns in _FRAMEWORKS)


def _ancestors(directory: str) -> Iterator[str]:
    """`a/b` -> `a/b`, `a`, `` (the repository root)."""
    while True:
        yield directory
        if not directory:
            return
        directory = posixpath.dirname(directory)


def _join(base: str, rel: str) -> str | None:
    """Normalised `base/rel`, or None when it escapes the repository."""
    path = posixpath.normpath(posixpath.join(base, rel))
    if path == ".":
        return ""
    return None if path == ".." or path.startswith("../") else path


def _match(pattern: str, spec: str) -> str | None:
    """What `*` captured when `spec` matches an `exports` / `paths` pattern (`""` for an exact match), else None."""
    if "*" not in pattern:
        return "" if pattern == spec else None
    head, tail = pattern.split("*", 1)
    if len(spec) >= len(head) + len(tail) and spec.startswith(head) and spec.endswith(tail):
        return spec[len(head) : len(spec) - len(tail)]
    return None


def _jsonc(text: str) -> object:
    """Parse JSON with comments and trailing commas (tsconfig style); None when it still is not JSON."""
    text = re.sub(r'("(?:[^"\\]|\\.)*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", text, flags=re.S)
    text = re.sub(r'("(?:[^"\\]|\\.)*")|,(?=\s*[}\]])', lambda m: m.group(1) or "", text)
    try:
        return json.loads(text)
    except ValueError:
        return None


def _leaves(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [t for v in value for t in _leaves(v)]
    if isinstance(value, dict):
        return [t for v in value.values() for t in _leaves(v)]
    return []


def _subpaths(value: object) -> dict[str, list[str]]:
    """Normalise a package.json `exports` / `imports` field to {subpath: [targets of every condition]}."""
    if isinstance(value, dict) and value and all(k.startswith((".", "#")) for k in value):
        return {k: _leaves(v) for k, v in value.items()}
    return {".": _leaves(value)}


def _variants(rel: str) -> list[str]:
    """`dist/cli.js` is built from `src/cli.ts`: spellings of a (possibly built) path to try, as written first."""
    rel = rel[2:] if rel.startswith("./") else rel
    found = [rel]
    parts = rel.split("/")
    while len(parts) > 1 and parts[0] in BUILD_DIRS:
        parts = parts[1:]
        found += ["/".join(parts), "src/" + "/".join(parts)]
    return found


@dataclass
class Package:
    path: str  # the package.json
    dir: str
    name: str = ""
    deps: frozenset[str] = frozenset()
    fields: list[tuple[str, str]] = field(default_factory=list)  # (field, target) for main, bin, exports ...
    exports: dict[str, list[str]] = field(default_factory=dict)
    imports: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Rules:
    base_urls: list[str] = field(default_factory=list)
    paths: list[tuple[str, list[str]]] = field(default_factory=list)  # (pattern, repo-relative target patterns)


class Resolver:
    def __init__(self, repo: Repo, files: Collection[str]):
        self.files = frozenset(files)
        self.sorted_files = sorted(self.files)
        self.paths = repo.paths
        self.read = repo.read
        self.packages: dict[str, Package] = {}
        self.rules: dict[str, Rules] = {}
        for path in sorted(self.paths):
            name = posixpath.basename(path)
            if name == "package.json":
                self._add_package(path)
            elif _TSCONFIG.fullmatch(name):
                self._add_tsconfig(path)
        for rules in self.rules.values():
            rules.paths.sort(key=lambda r: -len(r[0]))  # the longest pattern is the most specific
        self.by_name = {p.name: p for p in self.packages.values() if p.name}
        self._deps: dict[str, frozenset[str]] = {}

    # --- project files -------------------------------------------------------------------

    def _add_package(self, path: str) -> None:
        data = _jsonc(self.read(path) or "")
        if not isinstance(data, dict):
            return
        pkg = Package(path=path, dir=posixpath.dirname(path), name=data.get("name") if isinstance(data.get("name"), str) else "")
        deps: set[str] = set()
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            if isinstance(data.get(key), dict):
                deps.update(data[key])
        pkg.deps = frozenset(deps)
        for key in ("main", "module", "browser", "types", "typings"):
            if isinstance(data.get(key), str):
                pkg.fields.append((key, data[key]))
        bins = data.get("bin")
        for target in [bins] if isinstance(bins, str) else bins.values() if isinstance(bins, dict) else []:
            if isinstance(target, str):
                pkg.fields.append(("bin", target))
        pkg.exports = _subpaths(data["exports"]) if "exports" in data else {}
        for sub, targets in pkg.exports.items():
            pkg.fields.extend((f"exports {sub}", t) for t in targets)
        if isinstance(data.get("imports"), dict):
            pkg.imports = _subpaths(data["imports"])
        self.packages[pkg.dir] = pkg

    def _tsconfig(self, path: str, seen: tuple[str, ...]) -> tuple[str | None, dict | None, str]:
        """(baseUrl, paths, directory `paths` is relative to), following relative `extends`."""
        here = posixpath.dirname(path)
        data = _jsonc(self.read(path) or "")
        if not isinstance(data, dict):
            return None, None, here
        base_url, paths, paths_dir = None, None, here
        parents = data.get("extends")
        for ref in parents if isinstance(parents, list) else [parents]:
            target = _join(here, ref) if isinstance(ref, str) and ref.startswith(".") else None
            for candidate in (target, f"{target}.json") if target else ():
                if candidate in self.paths and candidate not in seen:
                    base_url, paths, paths_dir = self._tsconfig(candidate, (*seen, path))
                    break
        options = data.get("compilerOptions")
        if isinstance(options, dict):
            if isinstance(options.get("baseUrl"), str):
                base_url = _join(here, options["baseUrl"])
            if isinstance(options.get("paths"), dict):
                paths, paths_dir = options["paths"], here
        return base_url, paths, paths_dir

    def _add_tsconfig(self, path: str) -> None:
        base_url, paths, paths_dir = self._tsconfig(path, ())
        rules = self.rules.setdefault(posixpath.dirname(path), Rules())
        if base_url is not None:
            rules.base_urls.append(base_url)
        root = base_url if base_url is not None else paths_dir  # `paths` is relative to baseUrl when there is one
        for pattern, targets in (paths or {}).items():
            if isinstance(targets, list):
                joined = [j for t in targets if isinstance(t, str) and (j := _join(root, t)) is not None]
                rules.paths.append((pattern, joined))

    def package_dir(self, path: str) -> str:
        return next((d for d in _ancestors(posixpath.dirname(path)) if d in self.packages), "")

    # --- resolution ----------------------------------------------------------------------

    def probe(self, base: str | None) -> str | None:
        """The file `base` names: as written, with a TypeScript source for a `.js` spelling, with an extension, or as a directory index."""
        if base is None or base == "":
            return None
        if base in self.files:
            return base
        stem, ext = posixpath.splitext(base)
        if ".d." in base and base.rsplit(".", 1)[1] in DECLARATION:
            stem, ext = base[: base.rindex(".d.")], DECLARATION[base.rsplit(".", 1)[1]]
        for swapped in SWAP.get(ext, ()):
            if stem + swapped in self.files:
                return stem + swapped
        for suffix in PROBE:
            if base + suffix in self.files:
                return base + suffix
        for suffix in PROBE:
            if f"{base}/index{suffix}" in self.files:
                return f"{base}/index{suffix}"
        return None

    def _alias_targets(self, src: str, spec: str) -> list[str]:
        """Repo-relative spellings `spec` can take through tsconfig `paths` and `baseUrl` (and `@/`, `~/` conventions)."""
        found: list[str] = []
        for directory in _ancestors(posixpath.dirname(src)):
            rules = self.rules.get(directory)
            if rules is None:
                continue
            for pattern, targets in rules.paths:
                cap = _match(pattern, spec)
                if cap is not None:
                    found += [t.replace("*", cap, 1) for t in targets]
            for base in rules.base_urls:
                joined = _join(base, spec)
                if joined is not None:
                    found.append(joined + ("/" if spec.endswith("/") else ""))
        if spec.startswith(("@/", "~/")):  # a scope needs a name after `@`, so this is an alias even without tsconfig
            root = self.package_dir(src)
            for prefix in ("src/", "", "app/"):
                joined = _join(root, prefix + spec[2:])
                if joined is not None:
                    found.append(joined + ("/" if spec.endswith("/") else ""))
        return found

    def candidates(self, src: str, spec: str) -> list[str]:
        """Repo-relative spellings of a path-like specifier, which may end in `/` or be a partial name."""
        slash = "/" if spec.endswith("/") else ""
        if spec.startswith("."):
            joined = _join(posixpath.dirname(src), spec)
            return [] if joined is None else [joined + slash]
        if spec.startswith("/"):
            joined = _join(self.package_dir(src), spec.lstrip("/"))
            return [] if joined is None else [joined + slash]
        return self._alias_targets(src, spec)

    def _mapped(self, base_dir: str, mapping: dict[str, list[str]], key: str) -> str | None:
        """Look `key` up in a package.json `exports` / `imports` map and probe the targets (built paths mapped to sources)."""
        for pattern in sorted(mapping, key=lambda p: (p != key, -len(p))):
            cap = _match(pattern, key)
            if cap is None:
                continue
            for target in mapping[pattern]:
                for variant in _variants(target.replace("*", cap, 1)):
                    hit = self.probe(_join(base_dir, variant))
                    if hit:
                        return hit
        return None

    def _target(self, pkg: Package, target: str) -> str | None:
        """The source file a package.json field points at; wildcard patterns name no single file."""
        if "*" in target:
            return None
        return next(filter(None, (self.probe(_join(pkg.dir, v)) for v in _variants(target))), None)

    def _entry_files(self, pkg: Package, wanted: tuple[str, ...]) -> set[str]:
        return {hit for name, target in pkg.fields if name in wanted and (hit := self._target(pkg, target))}

    def _package(self, spec: str) -> set[str]:
        parts = spec.split("/")
        name = "/".join(parts[:2]) if spec.startswith("@") else parts[0]
        pkg = self.by_name.get(name)
        if pkg is None:
            return set()
        sub = spec[len(name) :].lstrip("/")
        if not sub:
            found = self._entry_files(pkg, ("main", "module", "browser", "types", "typings", "exports ."))
            fallback = self.probe(_join(pkg.dir, "src/index")) or self.probe(_join(pkg.dir, "index"))
            return found or ({fallback} if fallback else set())
        hit = self._mapped(pkg.dir, pkg.exports, "./" + sub)
        for prefix in ("", "src/", "lib/"):
            hit = hit or self.probe(_join(pkg.dir, prefix + sub))
        return {hit} if hit else set()

    def resolve(self, src: str, spec: str) -> set[str]:
        """Files that `import spec` in `src` can load; empty for external packages."""
        if not spec or ":" in spec.split("/")[0]:  # node:fs, https://..., virtual:module
            return set()
        if spec.startswith("#"):
            pkg = self.packages.get(self.package_dir(src))
            hit = self._mapped(pkg.dir, pkg.imports, spec) if pkg else None
            return {hit} if hit else set()
        hits: set[str] = set()
        if spec.startswith((".", "/")):
            hits = {h for c in self.candidates(src, spec) if (h := self.probe(c.rstrip("/")))}
            if spec.startswith("/") and not hits:
                hit = self.probe(spec.lstrip("/"))
                hits = {hit} if hit else set()
            return hits
        for target in self._alias_targets(src, spec):
            hit = self.probe(target.rstrip("/"))
            if hit:
                return {hit}
        return self._package(spec)

    def resolve_string(self, src: str, value: str) -> set[str]:
        """A string literal that names a file: relative to the importer, `<rootDir>/x`, or a path from the project root."""
        if value.startswith(("./", "../")):
            return self.resolve(src, value)
        root = self.package_dir(src)
        if value.startswith("<rootDir>/"):
            hit = self.probe(_join(root, value[len("<rootDir>/") :]))
            return {hit} if hit else set()
        value = value.lstrip("/")
        bases = (posixpath.dirname(src), root, "") if "/" not in value else (root, "")
        for base in bases:
            hit = self.probe(_join(base, value))
            if hit:
                return {hit}
        return self._by_suffix(value) if "/" in value else set()

    def _by_suffix(self, value: str) -> set[str]:
        return {f for f in self.files if f.endswith("/" + value)}

    # --- computed specifiers ---------------------------------------------------------------

    def dynamic(self, src: str, head: str, tail: str, deep: bool) -> set[str]:
        """`import(`./pages/${name}.tsx`)`: every file that fits the literal head and tail."""
        found: set[str] = set()
        ext = next((e for e in sorted(PROBE, key=len, reverse=True) if tail.endswith(e)), "")  # splitext(".ts") finds no extension
        tail_stem = tail[: len(tail) - len(ext)]  # `${n}.js` is written for `n.ts`, so only the stem is compared
        for candidate in self.candidates(src, head) if head else ():
            directory, _, prefix = candidate.rpartition("/")
            lead = directory + "/" if directory else ""
            for path in self.sorted_files:
                if not path.startswith(lead):
                    continue
                rest = path[len(lead) :]
                if not deep and "/" in rest and not (rest.count("/") == 1 and posixpath.splitext(rest.split("/")[1])[0] == "index"):
                    continue
                if rest.startswith(prefix) and posixpath.splitext(rest)[0].endswith(tail_stem):
                    found.add(path)
        return found

    def glob(self, src: str, pattern: str) -> set[str]:
        """`import.meta.glob("./pages/*.tsx")`."""
        if pattern.startswith("!"):
            return set()
        found: set[str] = set()
        for candidate in self.candidates(src, pattern):
            for expanded in _expand_braces(candidate.replace("**/", "").replace("**", "*")):
                found.update(f for f in self.sorted_files if fnmatch.fnmatchcase(f, expanded))
        return found

    def context(self, src: str, directory: str, deep: bool, regex: str | None) -> set[str]:
        """`require.context("./icons", true, /\\.js$/)`."""
        matcher = None
        if regex:
            body, _, flags = regex[1:].rpartition("/")
            try:
                matcher = re.compile(body, re.I if "i" in flags else 0)
            except re.error:
                matcher = None
        found: set[str] = set()
        for candidate in self.candidates(src, directory.rstrip("/") + "/"):
            lead = "" if candidate == "/" else candidate  # candidates keep the trailing slash
            for path in self.sorted_files:
                if path.startswith(lead) and (deep or "/" not in path[len(lead) :]) and (matcher is None or matcher.search("./" + path[len(lead) :])):
                    found.add(path)
        return found

    # --- entry points ----------------------------------------------------------------------

    def package_entries(self) -> dict[str, list[str]]:
        """Files that package.json publishes or runs (main, bin, exports ...): file -> reasons."""
        found: dict[str, list[str]] = defaultdict(list)
        for pkg in self.packages.values():
            for name, target in pkg.fields:
                hit = self._target(pkg, target)
                if hit:
                    found[hit].append(f"{pkg.path}: {name}")
        return found

    def framework_entry(self, path: str) -> str | None:
        """Why `path` is an entry point by framework convention (a Next.js page, a SvelteKit route ...), if it is."""
        directory = self.package_dir(path)
        if directory not in self._deps:
            deps: set[str] = set()
            for d in _ancestors(directory):
                if d in self.packages:
                    deps |= self.packages[d].deps
            self._deps[directory] = frozenset(deps)
        rel = path[len(directory) + 1 :] if directory else path
        for names, label, patterns in FRAMEWORKS:
            if names & self._deps[directory] and any(p.fullmatch(rel) for p in patterns):
                return label
        return None


def _expand_braces(pattern: str) -> list[str]:
    """`a/*.{ts,tsx}` -> [`a/*.ts`, `a/*.tsx`]."""
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    return [out for option in m.group(1).split(",") for out in _expand_braces(pattern[: m.start()] + option + pattern[m.end() :])]
