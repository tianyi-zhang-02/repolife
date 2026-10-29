"""Text written into a repository by `repolife init`. Kept as strings so the tool works from a zipapp too."""

CONFIG = """\
# repolife configuration. Every option is optional; see `repolife scan --help`.

# A file touched within this many days is ACTIVE.
# active_days = 90

# A file untouched this long that few others use is DORMANT.
# dormant_days = 365

# Files that look unused but must stay: public API of a library, plugin entry
# points, anything loaded by name from outside the repository. Globs, `*` crosses `/`.
# keep = ["src/mypkg/api/*", "plugins/*"]

# Files to leave out of the analysis entirely.
# exclude = ["vendor/*", "**/generated/*"]

# Extra entry points: a module name or a file path.
# entry = ["mypkg.cli", "scripts/release.py"]

# Ownership: an author with no commit anywhere in the repository for this many days
# no longer counts as someone who maintains the code.
# owner_inactive_days = 180

# Commit authors that never own code, matched against name or email, ignoring case.
# Bots such as dependabot are ignored already. A .mailmap merges one person's addresses.
# ignore_authors = ["release-script*", "*@ci.example.com"]
"""

SKILL = """\
---
name: repolife
description: Check which parts of a repository are alive, how its modules depend on each other and who maintains them before refactoring, cleaning up or asking for a review - code volume, git activity, unreachable (orphan) files, import cycles, what a change can break, and code nobody active owns. Use when asked about dead or unused code, repository health, what is safe to delete, what depends on a file, how modules relate, who owns or should review a path, or where to start a cleanup.
---

# repolife

repolife reports five things about a repository: how much code there is, how recently it
changed, whether anything still reaches it, who has been maintaining it, and how its modules depend on
each other. It only reads; it never edits code.

## Run it

```bash
repolife scan . --format json --out .repolife/report.json
```

If `repolife` is not on PATH, use `python3 -m repolife ...` or `uvx --from git+https://github.com/tianyi-zhang-02/repolife repolife ...`.
Add `--format md` (the default) for a report meant to be read by a person.

Read in this order: `summary` (sizes, status counts, orphan share), `cleanup.orphan_files`,
`cleanup.test_only_files`, then `hotspots` and `directories` for where change is concentrated,
and `ownership` for who maintains what.

## Dependencies and blast radius

```bash
repolife graph . --format json --out .repolife/graph.json
repolife impact <file-or-directory>
```

`graph` rolls the import graph up into modules (directories, split by size; `--module-depth N` fixes the
depth). Read `cycles` first: modules that depend on each other cannot be understood or released alone, and
each cycle lists the dependencies to cut or invert to break it (`cut`, with an example import to look at).
`modules[].used_by` is how many modules depend on one: a change in a module with a high `used_by` needs
more care. `--level file` gives every import as a pair, `--format mermaid` or `dot` draws the modules.

Before changing a widely used file, run `repolife impact <path>`. `dependents` are the code files that import
it directly or through others (`by_distance` says how far; `--hops 1` keeps only direct importers),
`tests.paths` are the tests that reach it (run those), `owners` are the people who maintain the affected code
(tell them), and `depends_on` is what it relies on.

Edges are static imports. Importing `a.b.c` does not make a file depend on the package `a`; names in strings,
dynamic imports and registries are not edges, so a missing edge is not proof that nothing depends on a file.

## Ownership

`ownership` is inferred from git: each commit credits its author with the files it touched, recent
commits weighing more, so an owner is whoever has maintained a file lately. It says who has been
changing the code, not who is accountable, and git cannot tell who reviewed.

- `directories[].owners` lists the people behind each directory with their share and `idle_days`
  (days since their last commit anywhere in the repository). `ownership` is `owned`,
  `no-active-owner` (the people still active hold under 20% of the maintenance) or `unknown`.
- `ownership.needs_owner_files` is live code nobody active maintains: ask a human to assign it
  before changing it, and do not pick a reviewer from it. `ownership.codeowners` compares CODEOWNERS
  with the commit history (`uncovered_files`, `differing_files`).
- Orphan rows carry `owner` and `owner_idle_days`: that is who to ask before deleting. An owner who
  is gone is a reason to be careful, not permission to delete.
- To find who to ask about a path, use `repolife why <path>`: its `owners:` line lists who maintains it
  and marks anyone who has gone silent.
- Authors are matched by name; a `.mailmap` fixes merged or split people. Bots are ignored.

## Statuses

- ACTIVE: touched in the last `active_days` (default 90).
- STABLE: not touched recently, but other code depends on it. Normal; leave it alone.
- DORMANT: untouched for `dormant_days` (default 365) and barely used.
- ORPHAN: no entry point, test or config reaches it. A cleanup candidate, not a verdict.

## Cleanup workflow

1. Start with orphan files whose `confidence` is `high`. `medium` and `low` carry a reason in
   `notes` (recently modified, mentioned in docs, lives under `scripts/`); show those to a human first.
2. For each candidate run `repolife why <path>`. It shows who depends on the file, what config names
   it, and what else would be stranded by deleting it.
3. Search the repository yourself for the module name and its public symbols: string lookups,
   registries, entry points and consumers outside this repository are invisible to a static scan.
4. If it is really unused, delete it in a small change (one cluster of related files per change)
   and run the tests. If it is intentionally kept, add it to `keep` in `.repolife.toml` with a comment.
5. For `test_only_files`, ask whether production code lost its caller. Do not delete tests to make
   the number go down.

## Do not

- Delete anything from a single scan without step 2 and step 3.
- Treat DORMANT or low activity as proof of anything. Only reachability says a file is unused.
- Remove files a library exports to its users; list them under `keep` instead.
"""

AGENTS_BLOCK = """\
## Repository health (repolife)

Before refactoring or deleting code, run `repolife scan . --format json` to see which files are
ACTIVE, STABLE, DORMANT or ORPHAN (nothing reaches them). Verify a candidate with
`repolife why <path>` and a repository-wide search before removing it; the scan is static and
cannot see dynamic loading or external consumers. Files that must stay go under `keep` in
`.repolife.toml`. Delete in small, separate changes and run the tests. To find who maintains a path,
read the `ownership` section of the scan or run `repolife why <path>`. Before changing a widely used file,
run `repolife impact <path>`: it lists the files that import it, the tests that reach it and who maintains
them. `repolife graph` shows how modules depend on each other and where the cycles are.
"""

GITHUB_WORKFLOW = """\
name: repolife

on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * 1"

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # activity needs full git history
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "__INSTALL_SPEC__"
      - name: Scan
        run: |
          repolife scan . --format json --out repolife-report.json
          repolife scan . | tee -a "$GITHUB_STEP_SUMMARY" > /dev/null
      - uses: actions/upload-artifact@v4
        with:
          name: repolife-report
          path: repolife-report.json
"""
