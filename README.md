# tessri.

**Keep code understandable.**

Tessri is an embeddable maintainability layer for codebases where agents write most of the code. Offline, with
nothing installed and no model, it shows how a system fits together, what a change can reach, who is able to review
it and what nobody maintains. Every claim can be traced to its evidence: `tessri why` shows what a verdict rests on,
Python imports come from Python's own parser, ownership and churn are read from git history, and the order `triage`
puts files in was backtested on real history. That is also why there is no risk score: the composite we tried did
not beat its parts, so it was left out. What the analysis cannot see, it says it cannot see.

| When you… | Ask | It answers with |
| --- | --- | --- |
| enter or return to a project | `tessri scan`, `tessri graph` | how much code there is and where, how the modules depend on each other, the cycles and the few dependencies that would break them |
| prepare a change | `tessri impact <path>` | what the change can reach, the tests that reach it, who maintains the affected code, and which kind of evidence each step rests on |
| review a change | `tessri triage --since main` | which changed files deserve a person first, and who is able to look |
| finish a change | `tessri check --since main` | what the change did to the structure, as Markdown, JSON or SARIF, with an exit code for CI |
| doubt a claim | `tessri why <path>` | the evidence behind one verdict |

It is built for coding agents (stable JSON, an agent skill, a `meta` block that says which commit and which history
every object describes) and is just as readable by a person, in the terminal or in one offline HTML page. It fits
into what a team already runs rather than asking for a new place: `check` writes SARIF for tools that read it, and
`integration` installs the agent skill with a receipt and takes it out again. Tessri was called repolife until
0.2.0; the old name [keeps working through 0.2.x](#formerly-repolife).

- **Zero dependencies.** Pure Python 3.11+ standard library.
- **Mounts into any repo, and unmounts again.** `tessri integration install --agent claude` writes the project skill
  with a receipt; `status`, `update` and `remove` act only on what the receipt records, so nothing you wrote is ever
  overwritten or deleted. Works in an empty or non-git project too.
- **Python and JavaScript/TypeScript** (including `.vue`, `.svelte`, `.astro`, `.mdx`) get a reachability verdict.
- **Config-aware.** Understands that code is wired by name, not only by `import`: hydra
  `_target_`, console-script entry points, `python scripts/x.py` in CI, registries filled by
  `import_module(f"pkg.{name}")` loops, tsconfig `paths`, `package.json` entries, Next.js pages, `import.meta.glob`.
- **Knows who looks after what.** Owners come from git history (and are compared with `CODEOWNERS`),
  and code whose maintainers have all gone quiet is listed as needing an owner.
- **One page to open.** `tessri scan --format html` writes a single self-contained file (no network, works
  offline, light and dark): the overview, the module graph, an impact explorer, owners and cleanup candidates.
- **Counts the review the changes ask for.** How much code changed lately, where, by whom, and whether anyone who knows
  that code is still around to look at it.
- **Shows the structure.** `tessri graph` rolls imports up into modules, finds the cycles and the few
  dependencies to cut to break them; `tessri impact` lists what a change reaches, the tests that reach it and who
  maintains the affected code, and says which kind of evidence each step rests on. Static analysis only, no model in the loop.
- **Triages a change.** `tessri triage --since main` ranks the files of a branch, or of uncommitted work, by recent
  activity, and shows what outside the change imports them, which tests reach them and who is able to look. Its order
  was backtested, and what did not help was left out of the order.
- **Checks what a change did to the structure.** `tessri check --since main` compares a branch with its base:
  files the change left unreachable, modules now in a cycle, deleted files still imported, and changed code nobody
  active maintains, with an exit code for CI.
- **Honest about what it cannot see.** Languages without an analyzer get volume and activity,
  never a guessed verdict. Every orphan carries a confidence and the reasons it might still be wanted.
- **Never edits code.**

## Quick start

```bash
pip install git+https://github.com/tianyi-zhang-02/tessri   # or run once: uvx --from git+https://github.com/tianyi-zhang-02/tessri tessri scan .
tessri scan .                 # markdown report
tessri scan . --format json   # machine-readable
tessri scan . --format html --out report.html   # one page to open or share
tessri why path/to/file.py    # the evidence behind one verdict
tessri graph .                # how modules depend on each other, and the cycles
tessri impact path/to/file.py # what a change can reach, the tests that reach it, who to tell
tessri triage --since main    # the files of a change to look at first, and who can look
tessri check --since main     # what a change did to the structure, with an exit code for CI
```

No install at all: build a single 300 KB file and drop it into any repository.

```bash
mkdir build && cp -r tessri build/       # from a checkout of this repository
python3 -m zipapp build -m tessri.cli:main -o tessri.pyz
python3 tessri.pyz scan /path/to/any/repo
```

## Mount it into a repository

```bash
tessri integration install . --agent claude --agent codex --dry-run   # show the plan, write nothing
tessri integration install . --agent claude --agent codex             # project skills for Claude Code and Codex
tessri integration install . --agent agents                           # one marked block in AGENTS.md
tessri integration status .                                           # what is installed and whether it changed
tessri integration update .                                           # refresh files that are still as installed
tessri integration remove .                                           # take everything out again
```

`integration` keeps a receipt, `.tessri-integration.json`, at the project root: which profiles are installed
(`claude` writes `.claude/skills/tessri/SKILL.md`, `codex` writes `.agents/skills/tessri/SKILL.md`, `agents`
inserts one marked block into `AGENTS.md`), the hash of every file it wrote, the exact bytes it inserted into
`AGENTS.md` and the directories it created. Only what the receipt records is ever updated or removed. A file that
already exists is a conflict, even when it is byte-identical to the template; a recorded file you edited is yours
and is left alone; text you add outside the block survives `update` and `remove`; a shared file that was there
before is never deleted. Every command plans and checks all its targets first and writes nothing when any of them
conflicts (exit 1, with the plan); `--dry-run` shows the same plan without writing; `--format json` gives it as
data; single files are replaced atomically and an ordinary failure is rolled back, which is not a cross-file
transaction. Installing files does not prove a running host has discovered them: start a new session in the
project afterwards. Nothing else is touched: no CI, hooks, configuration file, `.gitignore` line or network.

Updating Tessri itself does not rewrite installed instructions. For receipt-managed integrations,
`tessri integration status .` reports `installed-outdated` when the bundled instructions have changed.
Preview with `tessri integration update . --dry-run`, then run `tessri integration update .` to refresh
unchanged managed files and blocks. User-modified content remains a conflict; review and reconcile it yourself.
The updated skill explains impact's evidence sources and `--edges imports`, while candidate tests remain
subject to the project's runner and required checks.

The older `tessri init` still works as before and leaves no receipt, so `integration` never claims or removes
its files:

```bash
tessri init                   # .tessri.toml, .claude/skills/tessri/SKILL.md, AGENTS.md block, .gitignore line
tessri init --ci github       # plus a weekly workflow that uploads the report
tessri init --dry-run         # show what would change
```

`init` is safe to repeat. Files it owns are created once and never overwritten without `--force`;
shared files (`AGENTS.md`, `.gitignore`) only get a marked block or one line that later runs update
in place. It works in an empty repository. As a Claude Code plugin, this repository also ships
`.claude-plugin/plugin.json` and `skills/tessri/SKILL.md`.

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
$ tessri why pkg/dead_dep.py
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
$ tessri why legacy/old.py
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

## Review load

When a codebase grows faster than anyone can read it, the useful question is how much review the recent changes ask
for, and from whom. Every report has a `review` section for the last `review_days` days (30) against the same number
of days before:

| Question | Where |
|---|---|
| How much code changed, and is that more than before? | lines added plus deleted in code files, with the change against the previous window |
| Where did it change? | areas (directories, split by size like the modules), with commits, people and the change per area |
| Who made the changes? | per area: who changed it, and *by outsiders*, the share of the people's lines written by someone who is not among the area's owners |
| Did it land where nobody can look? | lines that landed in areas with no active owner |
| Who is it landing on? | the people who maintain the areas that others changed, by lines from others, with those who went quiet marked |
| What is hardest to review? | the largest single commits, with their subject and the area they mostly touched |

```text
$ tessri scan . --review-days 30
## Review load

- **19** lines changed in code files (+533% against 3 before), in 4 commits across 3 areas by 2 people
- 2 of those lines came from bots or ignored authors
- **2** lines (10.5%) landed in 1 area that nobody active maintains: nobody who knows that code is around to look

| Area | Changed lines | Against before | Commits | People | By outsiders | Owners | State |
|---|---:|---:|---:|---:|---:|---|---|
| `core` | 10 | +233% | 2 | 2 | 40.0% | Alice Adams 94% | owned |
| `web` | 7 | new | 1 | 1 | 0.0% | Carol Chen 100% | owned |
| `legacy` | 2 | new | 1 | 0 | - | Bob Brown 100% (silent 290d) | no active owner |

| Person | Lines from others | Areas | State |
|---|---:|---:|---|
| Alice Adams | 4 | 1 | active |
| Bob Brown | 2 | 1 | silent for 290 days |
```

This measures *demand* for review. Git records who changed code, not who reviewed it, so nothing here says a change
was or was not looked at. Only code files count: configuration and docs are summed apart, and files the scan
leaves out (`node_modules`, lock files, generated code, anything under `exclude`) are ignored. Bots and
`ignore_authors` still count as changes that need a look but never as people. A commit touching 300 or more files
(a reformat, a vendor drop) is left out of the areas and reported under `totals.bulk`, since nobody reads it line by
line. The window is cut by author date, so a rebased commit keeps the date it was written. In the HTML report the
section has a bar per area split into changes by an owner, by someone else, and by bots.

*By outsiders* leans on who counts as an owner, which is everyone holding at least 10% of an area's recent
maintenance. Where ownership is spread thin, most changes are by "outsiders" simply because the owners are many and
each holds little; read it together with the *Owners* column.

## How the modules fit together

`tessri graph` rolls the file-level import graph up into modules. A module is a directory; unless you pass
`--module-depth N`, directories are split until none holds much more than a twelfth of the code files, so one
big package still shows its parts. Test files are left out (every module is imported by its tests); add
`--include-tests` to draw them.

```text
$ tessri graph
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
| `tessri graph` | Markdown: cycles, then modules (size, *uses*, *used by*, owners), then the heaviest dependencies |
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
$ tessri impact util/helpers.py
Changing util/helpers.py  (1 file, 2 code lines) can affect:

- **3 code files** in **3 modules** (37.5% of the code), 1 of them directly (one followed edge away)
- **1 test file** reaching it (candidates to run, not runs), 0 directly
- code files by number of followed edges away: 1: 1, 2: 2
- edges followed, any number of steps: recognized dependency syntax, package files, and 0 references found in strings, dynamic loading or unclassified evidence; syntax and package files alone reach 3 code files and 1 test file

| Affected module | Files | Direct |
|---|---:|---:|
| `app` | 1 | 0 |
| `billing` | 1 | 0 |
| `core` | 1 | 1 |

Tests that reach it, nearest first: `tests/test_engine.py`
```

`impact` takes a file, a directory or a dotted package name and walks the dependency graph backwards, through
cycles without looping. With git history it also lists who maintains the affected code, which is who to tell or
ask for a review. `--hops 1` keeps only direct dependents. A package `__init__` is affected by any import
beneath it, because Python runs it.

Every edge carries the kind of evidence it rests on, strongest first: `import` (recognized literal dependency
syntax names the file: a Python import statement; for JavaScript and TypeScript an `import`, `export ... from`,
`require()`, a literal `import()`, `new URL(...)` or a reference path), `package` (a parent `__init__.py` that
Python runs for such a statement), `dynamic` (a supported computed import, glob or `require.context` pattern
expands to the file), `string` (a dotted name or path in an ordinary string resolves to it) and `unknown` (an
analyzer from before this field reported the edge without saying why). When one pair has both an import and a
string, it is an import. A Python `import_module("pkg.mod")` with a literal argument counts as a `string`,
because the analyzer does not look at the call around the literal; a JavaScript `import("./x")` with a literal
is recognized syntax. The names describe evidence, not what runs.

By default `impact` follows every kind, as it always has, and says so. The `edges` block of the JSON carries
`policy`, `hops`, the `kinds` followed, `followed` and `excluded` counted by kind, `references` (the total and a
capped list of the string, dynamic and unknown edges met, with the cap stated), `unclassified` (such edges and
the analyzers that gave no provenance) and, under the default only, `imports_only`: what the narrower policy
would reach from the same seeds under the same hop limit. The text has one line for the same facts.
`--edges imports` follows `import` and `package` edges only; the string, dynamic and unknown edges met at the
frontier are counted and listed, not followed, and *direct* means one followed edge away under either policy. The
line names the hop limit it ran under, `at most N steps` or `any number of steps`.
Counts are per source/target pair met while expanding the walk, so they describe the frontier the walk saw, not
every such edge in the repository, and an excluded edge is never expanded. `depends_on` is the other direction,
the dependencies the target itself names, and never the result of the reverse walk: under `--edges imports`
only `import` and `package` edges count; under the default it is the set it always was, which for Python is
what import statements name and for JavaScript everything the scanner resolved, path strings and globs included.
Tests are listed because they reach the target; nothing here records what ran. Neither policy shows that a file
outside the result is unaffected.

## Triage a change

```bash
tessri triage --since main                 # a branch, judged from where it parted from main, plus uncommitted work
tessri triage                              # only uncommitted work
tessri triage --since main --format json   # for an agent
```

Given a change, which of its files should a human look at first, what outside the change can it ripple into, and who
is able to look? The answer is a ranked list of the changed code files, each with why it is there, what imports it, and
who maintains it, followed by the code outside the change that imports the changed files (one and two steps away),
the tests that reach them, and the people who maintain them other than the authors.

```text
$ tessri triage --since main
# Change triage: demo

`main` (base 8f9c528cc) to HEAD fc97f1a93. 4 code files changed, **21** lines, in 2 areas; 2 other files (2 lines of config, docs and the like) not ranked.

- **1** file was fixed or reverted in the last 90 days
- **1** file has no active owner: nobody who maintains the code has committed lately
- **1** file is maintained by nobody but the author
- code outside the change that imports it: **1 file** directly, 0 files through one more step
- **1** test file reaches it

Look at these first:

| # | File | Why | This change | Owners | Imported by | Flags |
|---:|---|---|---|---|---:|---|
| 1 | `core/a.py` | 3 commits in 90 days, 2 of them fixes or reverts | +4 -0 | Alice Adams 100% | 2 | author is not among the owners |
| 2 | `util/c.py` | quiet since 2026-01-03 | +8 -0 | Bob Brown 100% (silent 300d) | 1 | no active owner; author is not among the owners |
| 3 | `core/d.py` | new file | +6 -0 | - | 0 | new file; orphan: nothing reaches it |
| 4 | `core/b.py` | quiet since 2026-04-13 | +2 -1 | Alice Adams 100% | 1 | author is not among the owners |

Who can look, other than the authors: Alice Adams (2 files). Git cannot see who reviewed; these are the people who maintain the changed files.

Only the author maintains: `util/c.py`

Not in the change, but importing it (by area):

| Area | Directly | One more step |
|---|---:|---:|
| `.` | 1 | 0 |

Tests that reach it, nearest first: `tests/test_a.py`
```

**How the order is decided.** Files are ordered by how many commits touched them in the last 90 days, then by how much
this change touches. We tested that rather than assuming it: on one large repository (nemo-rl, eleven monthly
snapshots, no information from after each snapshot), the files a change touched were ordered this way and compared with
which of them needed a fix over the following 30 days. The order scored an AUC of about 0.72, against 0.64 for
"largest diff first". Three things we expected to help did not, so they are shown but do not move a file: knowing which
of those commits were fixes or reverts (`fixes_90`), how many files import it, and who owns it. The first two describe
trouble that already happened and what a mistake could reach; ownership describes who can catch it, which a
"will it need a fix" score does not measure. One repository and eleven snapshots is a hint, not a proof. The backtest scripts are not
in this repository yet, and the same check on other repositories has not been done.

History is read up to the base of the change, so the change's own commits count neither as activity nor as making its
author an owner, and a file the change adds has no history and sorts by its size. *Who can look* lists the people
who maintain the changed files, excluding the authors (the commits of the change, or whoever `git config user.name` is
when the work is uncommitted); git cannot see who reviewed. Dependents are static imports only: importing `a.b.c`
does not make a file depend on the package `a`, and dynamic loading and consumers outside the repository are invisible.

## Check a change's structure

```bash
tessri check --since main                  # a branch, judged from where it parted from main, plus uncommitted work
tessri check                               # only uncommitted work
tessri check --since main --fail-on block  # exit 1 when something is certain to break
tessri check --since main --format sarif --out check.sarif   # the same findings for tools that read SARIF
```

`scan` describes a repository as it is; `check` says what a change did to it. It reads the base of the change straight
from git objects into a scratch directory (the repository is not touched), analyses it and the working tree with the
same settings, and compares them. Triage says which files to look at first; this says what the change did to the
structure. They answer different questions and work together.

| Finding | Severity | What it means |
|---|---|---|
| `dangling-import` | block | a file the change deleted or moved is still imported by a file the change did not touch |
| `new-cycle`, `cycle-grew` | warn | modules that were not in a loop now are, or a cycle absorbed more modules; the new dependency that closed it is named |
| `new-orphan` | warn | a new file nothing reaches, or a file the change cut the last link to (`stranded`, with what used to reach it); under `scripts/`, `examples/` and the like it is only a note, since those are run by hand |
| `no-active-owner` | warn | changed code nobody active maintains. History is read up to the base, so the author's own commits do not make them the owner |
| `new-dependency`, `orphan-resolved`, `cycle-resolved` | info | the other differences, the good ones too |

```text
$ tessri check --since main
# Change check: demo-check

`main` (9a0025443) to d6d893879: 4 files changed, 4 of them code (2 added, 1 modified, 1 deleted), **11** lines.

**1 block, 3 warn, 1 info.**

- **block**: `util/money.py` was deleted but is still imported
  Untouched by this change, still importing it: `billing/invoices.py`
  Do: Restore the file, or update every importer in the same change.
- **warn**: Modules `billing`, `util` now depend on each other
  Because of the new dependency `util` → `billing`, 1 import (for example `util/tax.py` imports `billing/invoices.py`).
- **warn**: 2 new files that nothing reaches
  Files: `billing/helpers.py`, `util/tax.py`
- **warn**: 1 changed file nobody active maintains
  Files: `legacy/rates.py`
  Do: Have a human who knows the code look before merging, or assign an owner. A person has to decide this.
```

`--fail-on block` exits 1 for `dangling-import` only; `--fail-on warn` also for the warnings; the default never fails.
`--format json` gives the same findings with their evidence (`orphans`, `cycles`, `dependencies`, `dangling_imports`,
`unowned`, `changed_files`; `kind` is `change-check`) for an agent to act on.

`--format sarif` writes the same check as a [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
log, for editors and services that already read that format. It is a rendering, not a second analysis: one finding
becomes one result, in the same order, under a fixed rule per kind (`tessri/dangling-import`, `tessri/new-orphan`,
…); `block`, `warn` and `info` become `error`, `warning` and `note`, and the observations (`new-dependency`,
`orphan-resolved`, `cycle-resolved`) are `kind: informational` with `level: none` rather than failures. The whole
finding, `files` and `needs_human` included, sits in the result's `properties["tessri/finding"]`, and the check's
`meta`, `change`, `summary` and `notes` in the run's `properties["tessri/check"]`, so the identity of the comparison
travels with the file. The evidence is file-level, so a location names a file and never a line: the first path of a
finding that still exists and stays inside the analysed root is the primary location, the others are related
locations, and a finding with no usable path has no location at all rather than an invented one. Paths are URI-encoded
relative to `originalUriBaseIds.TESSRI_ROOT`, the directory that was analysed. Nothing is uploaded or configured, and
no fingerprints are generated. Two limits to know before wiring it anywhere. First, GitHub code scanning rejects a
whole log that contains a result without a location (observed on a real upload, 2026-11-01), and `new-dependency`,
`cycle-resolved` and a cycle finding with no example file have none. For that consumer add `--locationless omit`: those
findings leave `results` and move whole into the run's `properties["tessri/locationless"].omitted`, which also
records their `count` and the `policy` in force, so nothing is dropped and nothing gets an invented location. The
default `keep` leaves them in `results`, and `--fail-on` counts findings, not displayed results, so the exit code is the
same under both. Second, a check compares one change with one base, so feeding it into a persistent alert category can
make an old repository-wide problem look fixed when a later change simply did not touch it. `--fail-on` keeps its
meaning: with `block` the exit code is 1 and the document is still complete. Copyable shell and Python recipes for CI
artifacts, test selection and gates are in [docs/workflow-recipes.md](docs/workflow-recipes.md).

Only what static imports show is compared, so a clean result is not proof that nothing else depends on the change, and
a `block` is certain only for importers the change left untouched. Both sides are cut into modules the same way, so a
file added or removed cannot move a boundary and create a dependency that is not there. Renames are not followed: a
moved file is a deletion and an addition. Files the analysis does not read (symlinks, submodules, anything above the
size limit, anything excluded) are not part of either side.

## The HTML report

```bash
tessri scan . --format html --out report.html
```

One self-contained file: styles, script and data are inside it, nothing is fetched, and Python renders all
sections, so it reads without scripts and prints. The viewer trials the **Tessri** identity; the package,
command and configuration remain `tessri`. With scripts enabled, four primary navigation entries open
one focused view at a time; additional sections are under **More views**. Use **⌘K / Ctrl+K** to find a view,
analyzed file or directory; choosing a path opens its impact
analysis. Escape closes quick navigation, and the arrow keys and Enter select a result. Section links and
browser Back/Forward work, and switching views preserves the current query and filters. Impact queries are
carried in the URL fragment, including relationship policy and step limit, so refreshing or reopening the
same report at that URL restores the query. Typing updates the current entry without adding history per
keystroke. The repository and
snapshot revision remain visible; the report is a captured analysis, not a live workspace connection.

| Section | What it is for |
|---|---|
| Overview | lines of code, how much is unreachable or recently changed, people and bus factor, module cycles, and the code split by status |
| Where to look first | the top of three longer tables: probably unused, nobody active maintains, dependencies to untangle |
| Directories | size, status mix and owners per directory; click a heading to sort |
| Modules | the dependency graph (users on the left, what they build on to the right, cuts that break a cycle in red; click a module to highlight what it uses and what uses it), the cycles with their cut lists, and every module in a table |
| Impact | type an analyzed file or directory; compare all relationships with recognized imports and Python parent packages, limit the number of steps, inspect inferred evidence and candidate tests |
| Review load | a bar per area for the lines changed, split by an owner, someone else and bots; who the changes land on; the largest changes |
| Ownership, hotspots, cleanup | the same tables as the Markdown report, with filters on the long ones |

The impact explorer walks the relationship graph embedded in the page. Its evidence selector corresponds to
`tessri impact --edges all|imports`; its step limit corresponds to `--hops`. Tests compare both policies with
the Python implementation for every analyzed file and directory of this repository, including the evidence
counts and bounded reference examples. Inferred links are disclosed rather than presented as confirmed runtime
dependencies, and candidate test paths do not record test execution. Two differences: it names the top
owner of each affected file rather than a rolled-up share, and it is left out (with a note) past 20,000 analysed
files, where `tessri impact` still works. Status colours are four hues chosen to stay apart under common colour
blindness, and every one is repeated in text. Names are escaped everywhere, and emails never reach the page.

## Configuration

`.tessri.toml` (or `[tool.tessri]` in `pyproject.toml`); every flag has a CLI equivalent. The old names,
`.repolife.toml` and `[tool.repolife]`, are still read when the new ones are absent, with a notice on stderr
([details](#formerly-repolife)).

```toml
active_days = 90
dormant_days = 365
keep = ["src/mypkg/api/*"]    # public API, plugins: never reported as orphans
exclude = ["vendor/*"]        # skipped entirely
entry = ["mypkg.cli"]         # extra entry points (module or path)
owner_inactive_days = 180     # no commit anywhere in the repository for this long => no longer an owner
review_days = 30              # review load: changes in this many days against the same number before (0 = off)
ignore_authors = ["ci-*"]     # author name or email globs that never own code
```

If the repository is a library, modules that only outside users import will look orphaned.
List them under `keep`.

## JSON report

`tessri scan --format json` prints one object, versioned by `schema_version` (currently `1`; adding
fields does not bump it). Top-level keys: `summary` (sizes, `by_status`, `orphans`, `test_only`,
`reachability_coverage`), `languages`, `directories` (with `owners` and `ownership` per directory), `ownership`
(`authors`, `bus_factor`, `no_active_owner`, `top_authors`, `needs_owner_files`, `codeowners`; `{"available": false}`
without git), `review` (`window`, `totals` with `bulk`, `unowned`, `areas`, `authors`, `reviewers`, `largest_changes`;
`{"available": false}` without git or with `review_days = 0`), `largest_files`, `hotspots`, `cleanup` (`orphan_files` with `owner`, `test_only_files`), `analysis`,
`caveats`, and with `--full` a per-file `files` table.

`tessri graph --format json` and `tessri impact --format json` print their own objects (`kind` is `module-graph`,
`file-graph`, or has `target` for an impact) with the same `schema_version`. `tessri why <path> --format json`
prints the same facts the text shows, as data: `file`, `verdict` (`status`, `confidence`, `reachability`,
`entry_points`, `notes`), `git`, `owners`, `graph` (`reached_via`, `dependents`, `config_refs`, `doc_refs`,
`depends_on`, `stranded_if_removed`) and `advice`; `git`, `owners` and `graph` are `null` when the analysis had
nothing to say.

Every JSON object also carries a `meta` block with the same names everywhere: `tool`, `generated_at`, `repo`
(`name`, `root`), and `git` with `available`, `reason` (`null`, or `not-a-repository`, `no-commits`,
`git-not-found`, `git-error`, `not-requested`), `head` (the checkout's HEAD, resolved on its own), `history_rev`
(the commit history was read up to: HEAD for a scan, the base for `triage` and `check`), `shallow` and `commits`.
All ids are full object ids. `triage` and `check` add `meta.change` (`since`, `base`, `head`, `uncommitted`), and
`check` adds `meta.analysis`, which says `skipped` with reason `no-code-changes` when nothing was compared, so an
empty `findings` list is never mistaken for a clean comparison. The older top-level fields (`git` in a scan, the
short `change.base` and `change.head` of `triage` and `check`) keep their meaning. A caught error (an unknown base,
a directory that is not a repository) exits 2 and prints nothing on stdout; exit 1 is reserved for `check
--fail-on`, a result that was computed and failed the chosen gate.

## Architecture

One pass over a repository builds one `Analysis`; every command is a view of it, and no view reads the files again.
The package is standard library only, about 6,000 lines of code in 32 files. The table is the import graph of this
checkout as `tessri graph . --level file --format json` reads it, and `tessri graph .` reports the one thing the
layering does not keep: `analyzers/python.py` imports the dotted-name patterns of `textrefs` and
`analyzers/__init__.py` takes the old plugin group name from `legacy`, so `tessri` and `tessri/analyzers` depend on
each other, a cycle the tool lists against itself.

```text
repository ─► inventory ─► analyzers ─► graph ─► analyze ─► Analysis ─► one view per command ─► cli
 (files, git)      │       (python, javascript)   ▲            ▲                  │
                   └─► textrefs (config, CI, docs) ┘   gitlog ─► ownership         meta (on every JSON object)
```

| Stage | Modules | What happens |
|---|---|---|
| Discover | `inventory` | lists the files (`git ls-files`, or a walk without git), detects the language, reads the text and counts code, comment and blank lines; binaries, build output and oversized files are skipped |
| Understand code | `analyzers/python` (on `ast`), `analyzers/javascript` (`jslex` scanner, `jsproject` resolution), `textrefs` | each analyzer turns its files into edges, entry points, tests and a resolver for names found elsewhere; `textrefs` finds the names that config, CI, shell scripts and docs mention |
| Reachability | `graph` | walks from entry points and config references; tests are roots of their own, so test-only code stays visible |
| History | `gitlog`, `ownership` | history is read once up to a rev for per-file activity and fix commits, and once more for the two review windows; `GitState` says why history is or is not there; ownership credits authors with yearly decay, marks owners who went quiet and compares with `CODEOWNERS` |
| Verdict | `analyze`, `model` | one `FileRecord` per file, the status rules, and the `Analysis` everything below reads |
| Views | `report` + `render` (scan, Markdown and JSON), `htmlreport` + `htmlassets` + `graphview` (HTML, mermaid, dot), `explain` (why), `modules` (graph, impact), `review` (review load), `triage`, `since` + `sinceview` + `sarifview` (check) | each computes its own tables from an `Analysis` and renders them; `render` is the shared Markdown, `meta` the shared `meta` block |
| Front door | `cli` | argparse, `--format` and `--out`, and the exit codes: 0; 1 for a `--fail-on` gate that failed or an integration plan blocked by conflicts, always with the complete result; 2 for a caught error, with nothing on stdout |
| Into other repositories | `templates`, `mount`, `integration` | the skill text, the legacy `init`, and the receipt-based install, update, status and remove |

Two commands run the pipeline against another revision. `triage` analyses the working tree with history read up to the
base of the change, so the change's own commits count neither as activity nor as ownership. `check` extracts the base
from git objects into a scratch directory (`cat-file --batch`, never `git archive`, which honours export-ignore),
analyses both sides with the same settings and compares only the import graph and the reachability of each file;
status, confidence and owners are never compared between the two analyses. Only `inventory`, `gitlog`, `triage` and
`since` run git; the analyzers and views never shell out, and nothing fetches, caches or calls a model, so the same tree
and history give the same output. The tests in `tests/`, one file per area, build small repositories in temporary
directories with fixed commit dates and assert on the output, so the suite needs git and nothing else, except `node`
for the one test that runs the HTML page's script, which is skipped without it.

## Supporting another language

The engine in `tessri/graph.py` knows nothing about any language. An analyzer maps files to
`edges` (what each depends on), `roots` (entry points), `tests`, and a `resolve_reference` for names
found in config. Subclass `tessri.analyzers.Analyzer`, implement `handles(path)` and
`run(files, repo)`, return a `LanguageResult`, and register it from a package through the
`tessri.analyzers` entry-point group (the `repolife.analyzers` group an older version used is read too, through
0.2.x). `repo.paths` lists every file and `repo.read(path)` returns
any file's text, for project metadata such as `tsconfig.json` or `go.mod`.

Two reference implementations, written against the same interface: `tessri/analyzers/python.py`
(about 250 lines, uses `ast`) and `tessri/analyzers/javascript.py` (a hand-written scanner in
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
- A dotted name or path in a string is an edge of kind `string`, and `impact` follows it by default. A tool that
  names files in strings links itself to them: Tessri's own Python analyzer holds the string `__main__.py`, so
  on this repository `impact tessri/cli.py` reaches the analyzers from the CLI by default and `--edges imports`
  does not. The bare `if __name__ == "__main__"` idiom makes no edge.
- Review load counts lines changed, not effort: a generated file that is not excluded, or a mechanical rename of one
  symbol, weighs as much as careful work. It cannot see who reviewed, and it follows neither renames nor branches
  that never reached the history it reads.
- Ownership says who has been *changing* code, not who is accountable, and git cannot tell who *reviewed* it.
  Squash merges credit the person who merged, a person with different names on different machines counts as
  several, and two people with one name count as one. Work done in another repository or before a history
  rewrite is invisible. Read it as a prompt to ask, not as an assignment.
- Symbol-level dead code (unused functions inside live files) is out of scope; use a tool like
  [vulture](https://github.com/jendrikseipp/vulture). For multi-language dead-code detection see
  [fossil-mcp](https://docs.rs/crate/fossil-mcp/latest/source/README.md); for churn x complexity on
  JS/TS see [fallow](https://docs.rs/crate/fallow-cli/2.94.0).

## Formerly repolife

Tessri was called repolife until 0.2.0. The old name keeps working through 0.2.x and goes away in 0.3.0:

- `repolife …` and `python -m repolife …` run the same program after a one-line notice on stderr, and
  `import repolife` works with a `DeprecationWarning`.
- `.repolife.toml` and `[tool.repolife]` are read when `.tessri.toml` and `[tool.tessri]` are absent, with a notice
  on stderr; when both exist the new one is in force and the old one is ignored, also with a notice.
- A receipt, skill files and AGENTS.md markers that 0.1.x installed are recognised by `tessri integration status`
  under their recorded paths, and the next `install`, `update` or `remove` moves them: the skill file is created at
  its new path and the old one removed in the same run, the AGENTS.md block is rewritten in place with the new
  markers, and the receipt becomes `.tessri-integration.json` with the old file deleted. A user-modified old file is
  a conflict, as always, and then nothing is written.
- `tessri init` replaces an AGENTS.md block that `repolife init` wrote instead of adding a second one.
- Analyzer plugins registered under the `repolife.analyzers` entry-point group keep loading.

What changed for readers of the output is listed in [CHANGELOG.md](CHANGELOG.md): `tool.name` is `tessri` (the
schema version is unchanged), SARIF rule ids are `tessri/<kind>` under the driver `tessri` with the base id
`TESSRI_ROOT`, the scan heading is `# Tessri report`, and stderr lines start with `tessri:`.

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
