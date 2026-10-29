# repolife

**Which parts of a repository are alive?**

repolife reads a repository and reports three things in one pass: how much code there is,
how recently each file changed, and whether anything still reaches it. It is built for coding
agents (stable JSON, an agent skill, a `why` command to verify every claim) and is just as
readable by a person.

- **Zero dependencies.** Pure Python 3.11+ standard library.
- **Mounts into any repo** in one command, existing or brand new: `repolife init`.
- **Python and JavaScript/TypeScript** (including `.vue`, `.svelte`, `.astro`, `.mdx`) get a reachability verdict.
- **Config-aware.** Understands that code is wired by name, not only by `import`: hydra
  `_target_`, console-script entry points, `python scripts/x.py` in CI, registries filled by
  `import_module(f"pkg.{name}")` loops, tsconfig `paths`, `package.json` entries, Next.js pages, `import.meta.glob`.
- **Honest about what it cannot see.** Languages without an analyzer get volume and activity,
  never a guessed verdict. Every orphan carries a confidence and the reasons it might still be wanted.
- **Never edits code.**

## Quick start

```bash
pip install git+https://github.com/tianyi-zhang-02/repolife   # or run once: uvx --from git+https://github.com/tianyi-zhang-02/repolife repolife scan .
repolife scan .                 # markdown report
repolife scan . --format json   # machine-readable
repolife why path/to/file.py    # the evidence behind one verdict
```

No install at all: build a single 110 KB file and drop it into any repository.

```bash
mkdir build && cp -r repolife build/       # from a checkout of this repository
python3 -m zipapp build -m repolife.cli:main -o repolife.pyz
python3 repolife.pyz scan /path/to/any/repo
```

## Mount it into a repository

```bash
repolife init                   # .repolife.toml, .claude/skills/repolife/SKILL.md, AGENTS.md block, .gitignore line
repolife init --ci github       # plus a weekly workflow that uploads the report
repolife init --dry-run         # show what would change
```

`init` is safe to repeat. Files it owns are created once and never overwritten without `--force`;
shared files (`AGENTS.md`, `.gitignore`) only get a marked block or one line that later runs update
in place. It works in an empty repository. As a Claude Code plugin, this repository also ships
`.claude-plugin/plugin.json` and `skills/repolife/SKILL.md`.

## What it tells you

Every code file gets one status:

| Status | Meaning |
|---|---|
| `ACTIVE` | touched in the last `active_days` (90), or not in git yet |
| `STABLE` | not touched recently, but other code depends on it. Normal. |
| `DORMANT` | untouched for `dormant_days` (365) and barely used |
| `ORPHAN` | no entry point, test or config reaches it: a cleanup candidate |

Only reachability says a file is unused. Activity orders and qualifies the candidates; it never
decides them. Files reached **only from tests** are listed separately: either production code
lost its caller, or it is test support.

```text
$ repolife why pkg/dead_dep.py
pkg/dead_dep.py  (Python, 1 code lines)
status:        ORPHAN (confidence high)
reachability:  NOT reachable from any entry point, test or config reference
depended on by: pkg/dead.py
named in config/scripts: none
mentioned in docs: none
depends on:    none
note:          only referenced by other unreachable files
```

The report's candidate table, most confident first:

| File | Code | Confidence | Last commit | Notes |
|---|---:|---|---|---|
| `pkg/dead_dep.py` | 1 | high | - | only referenced by other unreachable files |
| `pkg/dyn/z.py` | 1 | high | - | - |
| `pkg/dead.py` | 3 | medium | - | mentioned in docs: docs/guide.md |

Confidence drops one level per reason a file may still be wanted: modified recently, added
recently, not yet committed, mentioned in docs, lives under `scripts/`/`examples/`/`tools/`.

### How reachability is decided

A file is reachable if an **entry point** leads to it through imports, or a **config reference** names it.
Tests are entry points of their own: code reached only from tests is reported as test-only.

**Python**

- Entry points: files with an `if __name__ == "__main__"` guard, `__main__.py`, `setup.py`/`conf.py`
  and similar, console-script entry points in `pyproject.toml`/`setup.cfg`, files named by
  CI/YAML/shell/Makefile (`pkg.mod.Class`, `scripts/run.py`), `entry` and `keep` from the config,
  and any Python file that cannot be parsed (so nothing it might import is blamed).
- Dynamic loading it understands: `import_module("pkg.mod")`, `"pkg.mod." + name`, and loops over
  a literal list of names (`for n in ("a", "b"): import_module(f".{n}", __name__)`).

**JavaScript / TypeScript** (the scanner reads `import`, `export ... from`, `require()`, `import()`,
`new URL("./x", import.meta.url)` and `/// <reference path>`; a `.vue`/`.svelte`/`.astro` file contributes its script blocks)

- Resolution follows the compiler: relative paths with extension probing (`./x.js` finds `x.ts`),
  directory `index` files, tsconfig `paths`/`baseUrl`/`extends` (JSONC is fine), `package.json`
  `imports`, workspace packages by name (`@acme/ui` and `@acme/ui/sub`, with a built `dist/index.js`
  mapped back to `src/index.ts`), and the `@/` and `~/` alias conventions.
- Entry points: `main`/`module`/`bin`/`exports` in any `package.json`, files named by `package.json`
  scripts, CI or HTML (`<script src="/src/main.tsx">`), shebang and `require.main === module` scripts,
  tool configs (`vite.config.ts`, `.eslintrc.js` ...), `.d.ts` files, Storybook stories, `.mdx` pages, and the
  file-based routes of a framework that is a dependency of the package: Next.js, Nuxt, Astro, SvelteKit,
  Remix / React Router, Gatsby, TanStack Router, Expo / React Native, Create React App, Vue CLI, Angular,
  NestJS, Docusaurus, VitePress, Vercel functions. The table is `_FRAMEWORKS` in `jsproject.py`.
- Dynamic loading it understands: ``import(`./pages/${name}.tsx`)``, `require("./x/" + name)`,
  `import.meta.glob("./routes/*.ts")`, `require.context(dir, recursive, /regex/)`.
- Tests: `*.test.*`, `*.spec.*`, `*.e2e.*`, `*.cy.*`, and `test/`, `tests/`, `__tests__/`, `e2e/`, `cypress/` directories.

Deliberately **not** evidence of use, for any language: tool configs that merely list files (`pyrefly.toml`,
`mypy.ini`, `.coveragerc`, lint sections), JSON data, docs, and anything under `docs/`/`reports/`.
Docs and data count as a *mention*, which lowers confidence but does not rescue a file.

## Configuration

`.repolife.toml` (or `[tool.repolife]` in `pyproject.toml`); every flag has a CLI equivalent.

```toml
active_days = 90
dormant_days = 365
keep = ["src/mypkg/api/*"]    # public API, plugins: never reported as orphans
exclude = ["vendor/*"]        # skipped entirely
entry = ["mypkg.cli"]         # extra entry points (module or path)
```

If the repository is a library, modules that only outside users import will look orphaned.
List them under `keep`.

## JSON report

`repolife scan --format json` prints one object, versioned by `schema_version` (currently `1`; adding
fields does not bump it). Top-level keys: `summary` (sizes, `by_status`, `orphans`, `test_only`,
`reachability_coverage`), `languages`, `directories`, `largest_files`, `hotspots`, `cleanup`
(`orphan_files`, `test_only_files`), `analysis`, `caveats`, and with `--full` a per-file `files` table.

## Supporting another language

The engine in `repolife/graph.py` knows nothing about any language. An analyzer maps files to
`edges` (what each depends on), `roots` (entry points), `tests`, and a `resolve_reference` for names
found in config. Subclass `repolife.analyzers.Analyzer`, implement `handles(path)` and
`run(files, repo)`, return a `LanguageResult`, and register it from a package through the
`repolife.analyzers` entry-point group. `repo.paths` lists every file and `repo.read(path)` returns
any file's text, for project metadata such as `tsconfig.json` or `go.mod`.

Two reference implementations, written against the same interface: `repolife/analyzers/python.py`
(about 250 lines, uses `ast`) and `repolife/analyzers/javascript.py` (a hand-written scanner in
`jslex.py` plus tsconfig/package.json resolution in `jsproject.py`, because there is no parser to import).

## Limits

- Reachability is static. Reflection, plugin discovery by directory scan, and consumers outside the
  repository are invisible; that is why `ORPHAN` is a candidate and `why` exists.
- Only Python and JavaScript/TypeScript have analyzers today. Everything else (Go, Rust, Java ...) gets volume and activity.
- JavaScript specifics it cannot see: aliases defined only in a bundler config (`vite.config`, `webpack.config`;
  `@/` and `~/` are guessed), `exports` wildcard patterns as entry points (list those under `keep`), auto-imports
  (`unplugin-auto-import`, Nuxt-style component directories outside the frameworks above), a `require()` written
  inside a template literal's `${}`, and scripts in extensionless hook files such as `.husky/pre-commit`.
- Git activity needs history: a shallow clone truncates it, and a repository with no commits yet
  reports statuses as `UNKNOWN`. Renames are not followed.
- Symbol-level dead code (unused functions inside live files) is out of scope; use a tool like
  [vulture](https://github.com/jendrikseipp/vulture). For multi-language dead-code detection see
  [fossil-mcp](https://docs.rs/crate/fossil-mcp/latest/source/README.md); for churn x complexity on
  JS/TS see [fallow](https://docs.rs/crate/fallow-cli/2.94.0).

## Development

```bash
python3 -m unittest discover -s tests
```

The JavaScript scanner is checked against the TypeScript compiler rather than trusted. Given any directory of
real code (a `node_modules` works) and an installed `typescript` package, this compares the module specifiers
both find and lists every disagreement (needs `node`):

```bash
python3 tools/diff_js_scanner.py path/to/node_modules --typescript path/to/node_modules/typescript --sample 5000
```

## License

MIT
