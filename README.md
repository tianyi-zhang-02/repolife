# repolife

**Which parts of a repository are alive?**

repolife reads a repository and reports four things in one pass: how much code there is,
how recently each file changed, whether anything still reaches it, and who has been maintaining it.
It is built for coding agents (stable JSON, an agent skill, a `why` command to verify every claim)
and is just as readable by a person. When a codebase outgrows what anyone can review, it answers
where the volume is, what is unused, and which corners nobody looks after. Two more commands read the same
import graph: `graph` shows how the modules depend on each other, and `impact` shows what a change can reach.

- **Zero dependencies.** Pure Python 3.11+ standard library.
- **Mounts into any repo** in one command, existing or brand new: `repolife init`.
- **Python and JavaScript/TypeScript** (including `.vue`, `.svelte`, `.astro`, `.mdx`) get a reachability verdict.
- **Config-aware.** Understands that code is wired by name, not only by `import`: hydra
  `_target_`, console-script entry points, `python scripts/x.py` in CI, registries filled by
  `import_module(f"pkg.{name}")` loops, tsconfig `paths`, `package.json` entries, Next.js pages, `import.meta.glob`.
- **Knows who looks after what.** Owners come from git history (and are compared with `CODEOWNERS`),
  and code whose maintainers have all gone quiet is listed as needing an owner.
- **One page to open.** `repolife scan --format html` writes a single self-contained file (no network, works
  offline, light and dark): the overview, the module graph, an impact explorer, owners and cleanup candidates.
- **Shows the structure.** `repolife graph` rolls imports up into modules, finds the cycles and the few
  dependencies to cut to break them; `repolife impact` lists what a change reaches, the tests to run and who
  maintains the affected code. Static imports only, no model in the loop.
- **Honest about what it cannot see.** Languages without an analyzer get volume and activity,
  never a guessed verdict. Every orphan carries a confidence and the reasons it might still be wanted.
- **Never edits code.**

## Quick start

```bash
pip install git+https://github.com/tianyi-zhang-02/repolife   # or run once: uvx --from git+https://github.com/tianyi-zhang-02/repolife repolife scan .
repolife scan .                 # markdown report
repolife scan . --format json   # machine-readable
repolife scan . --format html --out report.html   # one page to open or share
repolife why path/to/file.py    # the evidence behind one verdict
repolife graph .                # how modules depend on each other, and the cycles
repolife impact path/to/file.py # what a change can reach, the tests to run, who to tell
```

No install at all: build a single 230 KB file and drop it into any repository.

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

## Who maintains it

Ownership is read from git. Each commit credits its author with the files it touched, and a commit
loses half its weight per year, so a file's owner is whoever has been maintaining it lately, not whoever
wrote it first. An owner counts as **gone** after `owner_inactive_days` (180) without a commit anywhere in the
repository. A file or directory with no active person holding at least 20% of the maintenance has
**no active owner**.

```text
$ repolife why legacy/old.py
legacy/old.py  (Python, 2 code lines)
status:        DORMANT
reachability:  reachable from a production entry point
owners:        Bob Brown 100% (silent 800d); NO ACTIVE OWNER
CODEOWNERS:    @someone-else (none of them maintains it)
```

The report's ownership section answers the questions a large codebase makes hard:

| Question | Where |
|---|---|
| Who maintains each directory, and are they still around? | table of directories: owners, share, `silent Nd`, state |
| What live code has nobody looking after it? | "Live code nobody active maintains", largest first |
| How concentrated is knowledge? | `bus_factor`: the fewest people who together hold half the code |
| Who should I ask before deleting an orphan? | an `Owner` column on every cleanup candidate |
| Does `CODEOWNERS` match reality? | files with no declared owner, and files whose declared owner is not among their maintainers |

A directory nobody clearly owns is shown honestly, e.g. `Dana 10% + 25 others`. Bots (`[bot]`,
dependabot, renovate, github-actions) never own code, and neither do authors matching `ignore_authors`.
A commit touching 300 or more files (a reformat, a vendor drop) is ignored for ownership unless it is all
a file has. Authors are matched by name, so one person committing from two addresses is one author; add a
`.mailmap` for anything this gets wrong. Emails are used to identify people and never appear in a report.

`CODEOWNERS` is read from `.github/`, the root, `docs/` or `.gitlab/` (first found), last matching rule wins.
A declared `@login` can be compared with the people who maintain a file only when they commit from a GitHub
noreply address, and git knows nothing about `@org/team`, so those comparisons are reported as undecidable
rather than as a mismatch.

## How the modules fit together

`repolife graph` rolls the file-level import graph up into modules. A module is a directory; unless you pass
`--module-depth N`, directories are split until none holds much more than a twelfth of the code files, so one
big package still shows its parts. Test files are left out (every module is imported by its tests); add
`--include-tests` to draw them.

```text
$ repolife graph
**4 modules**, **5 dependencies** between them and **1 cycle**, from 5 imports across 8 code files. ...

**Cycle 1**: `billing` ⇄ `core`. 2 imports among them; 1 dependency (1 import) to cut:

| From | To | Imports | For example |
|---|---|---:|---|
| `core` | `billing` | 1 | `core/engine.py` imports `billing/invoices.py` |

| Module | Files | Code | Uses | Used by | Cycle |
|---|---:|---:|---:|---:|---|
| `billing` | 2 | 5 | 1 | 2 | 1 |
| `core` | 2 | 4 | 2 | 2 | 1 |
| `util` | 2 | 2 | 0 | 1 | - |
| `app` | 2 | 5 | 2 | 0 | - |
```

| Output | What it gives |
|---|---|
| `repolife graph` | Markdown: cycles, then modules (size, *uses*, *used by*, owners), then the heaviest dependencies |
| `--format json` | `modules` (with `uses`, `used_by`, `instability`, `owners`, `cycle`), `edges` (`imports`, `files`, example imports, `cut`), `cycles` |
| `--format mermaid` / `dot` | a diagram of the heaviest ~80 dependencies, cuts drawn red; `--min-imports N` to choose the threshold |
| `--level file --format json` | every import as a `[from, to]` pair, each file with its module, status and owner |

An *import* is one file importing one other file, so `from pkg import a, b` counts twice. Only what an import
statement names is an edge: importing `a.b.c` also runs `a/__init__.py`, which keeps that file reachable but
does not make the importer depend on the package, and paths or dotted names found in strings, config or
dynamic imports are not edges either.

A cycle comes with a list of the dependencies that point against its dominant direction. Removing or
inverting exactly those leaves no cycle, and putting any one back makes one again. It is a heuristic for a few,
light edges (the true minimum is NP-hard), but it is deterministic, and the tests check it is acyclic and
irredundant.

```text
$ repolife impact util/helpers.py
Changing util/helpers.py  (1 file, 2 code lines) can affect:

- **3 code files** in **3 modules** (37.5% of the code), 1 of them importing it directly
- **1 test file**, 0 importing it directly
- code files by number of imports away: 1: 1, 2: 2

| Affected module | Files | Direct |
|---|---:|---:|
| `app` | 1 | 0 |
| `billing` | 1 | 0 |
| `core` | 1 | 1 |

Tests that reach it, nearest first: `tests/test_engine.py`
```

`impact` takes a file, a directory or a dotted package name and follows imports backwards, through cycles
without looping. With git history it also lists who maintains the affected code, which is who to tell or
ask for a review. `--hops 1` keeps only direct importers. A package `__init__` is affected by any import
beneath it, because Python runs it.

## The HTML report

```bash
repolife scan . --format html --out report.html
```

One file, about 250 KB for a repository of two thousand files: styles, script and data are inside it, nothing is
fetched, and it is rendered on the server, so it reads without scripts and prints. The script only adds sorting,
filtering, highlighting in the module graph and the impact explorer.

| Section | What it is for |
|---|---|
| Overview | lines of code, how much is unreachable or recently changed, people and bus factor, module cycles, and the code split by status |
| Where to look first | the top of three longer tables: probably unused, nobody active maintains, dependencies to untangle |
| Directories | size, status mix and owners per directory; click a heading to sort |
| Modules | the dependency graph (users on the left, what they build on to the right, cuts that break a cycle in red; click a module to highlight what it uses and what uses it), the cycles with their cut lists, and every module in a table |
| Impact | type any file or directory: the code that imports it directly or through others, the tests that reach it, and who owns the affected files |
| Ownership, hotspots, cleanup | the same tables as the Markdown report, with filters on the long ones |

The impact explorer walks the import graph embedded in the page, and the tests check that it gives the same
numbers as `repolife impact` for every file and directory of this repository. Two differences: it names the top
owner of each affected file rather than a rolled-up share, and it is left out (with a note) past 20,000 analysed
files, where `repolife impact` still works. Status colours are four hues chosen to stay apart under common colour
blindness, and every one is repeated in text. Names are escaped everywhere, and emails never reach the page.

## Configuration

`.repolife.toml` (or `[tool.repolife]` in `pyproject.toml`); every flag has a CLI equivalent.

```toml
active_days = 90
dormant_days = 365
keep = ["src/mypkg/api/*"]    # public API, plugins: never reported as orphans
exclude = ["vendor/*"]        # skipped entirely
entry = ["mypkg.cli"]         # extra entry points (module or path)
owner_inactive_days = 180     # no commit anywhere in the repository for this long => no longer an owner
ignore_authors = ["ci-*"]     # author name or email globs that never own code
```

If the repository is a library, modules that only outside users import will look orphaned.
List them under `keep`.

## JSON report

`repolife scan --format json` prints one object, versioned by `schema_version` (currently `1`; adding
fields does not bump it). Top-level keys: `summary` (sizes, `by_status`, `orphans`, `test_only`,
`reachability_coverage`), `languages`, `directories` (with `owners` and `ownership` per directory), `ownership`
(`authors`, `bus_factor`, `no_active_owner`, `top_authors`, `needs_owner_files`, `codeowners`; `{"available": false}`
without git), `largest_files`, `hotspots`, `cleanup` (`orphan_files` with `owner`, `test_only_files`), `analysis`,
`caveats`, and with `--full` a per-file `files` table.

`repolife graph --format json` and `repolife impact --format json` print their own objects (`kind` is `module-graph`,
`file-graph`, or has `target` for an impact) with the same `schema_version`.

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
- The HTML explorer's script is exercised against the Python implementation, but the page's sorting and filtering
  are checked by hand in a browser, not by an automated test.
- The module graph is static imports between Python and JavaScript/TypeScript files. A package that re-exports
  everything (a busy `__init__.py` or `index.ts`) makes the modules importing through it look more tangled than
  their real call graph, and registries, dependency injection and dynamic loading leave no edge, so a missing
  dependency is not proof there is none.
- Ownership says who has been *changing* code, not who is accountable, and git cannot tell who *reviewed* it.
  Squash merges credit the person who merged, a person with different names on different machines counts as
  several, and two people with one name count as one. Work done in another repository or before a history
  rewrite is invisible. Read it as a prompt to ask, not as an assignment.
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
