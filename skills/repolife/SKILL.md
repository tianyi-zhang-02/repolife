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
Add `--format md` (the default) for a report meant to be read by a person, or `--format html --out report.html` for one
self-contained page with the module graph and an impact explorer to open or share.

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

## Triage a change

```bash
repolife triage --since <base> --format json     # a branch against its base; without --since, uncommitted work
```

Run it before you open a change and before you review one. `files` is the changed code, most active first: files
that were committed to most in the last 90 days, then by lines changed. Fix and revert history (`fixes_90`),
`dependents`, `owners` and `flags` are context shown beside the order, not part of it. `ripple` is code outside the
change that imports the changed files, `tests.nearest` are the tests to run, `reviewers` are the people who maintain the
files other than the authors, and `nobody_else_can_look` lists files only the author maintains. A flag
`no active owner` means nobody who maintains the file has committed lately: ask a human to assign someone. History is
read up to the base, so the change's own commits do not count. It is a prompt about where to look, not a verdict.

## Check a change's structure

```bash
repolife check --since <base> --format json --fail-on block     # without --since, uncommitted work
```

Run it when a task is done and before the change is opened. It compares the base of the change with the working
tree and lists what the change did to the structure, `findings` ordered by `severity`. `block` is certain breakage:
`dangling-import` means a file the change deleted is still imported by files it did not touch, so restore it or
update the importers. `warn` needs a decision: `new-cycle` and `cycle-grew` name the new dependency that closed the
loop, `new-orphan` is a new file nothing reaches (`how: stranded` is a file the change cut the last link to, with
`was_reached_from`), and `no-active-owner` is changed code nobody active maintains (`needs_human`: ask a person, do not
pick a reviewer from its last maintainers). `info` is the rest. Static imports only: a clean result is not proof.

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

## Review load

`review` counts the lines that changed in code files over the last `review_days` days (30) against the days before,
per area (a directory, split by size). It measures how much review the changes ask for, not who reviewed: git
cannot see that.

- `areas[]` has `lines`, `previous_lines`, `commits`, `authors`, `outside_share` (the share of the people's lines
  written by someone who is not among the area's owners) and `ownership`. Read `outside_share` with `owners`:
  where ownership is spread thin, most changes are by "outsiders".
- `unowned` is the lines that landed where nobody active maintains the code. Raise it with a human; do not pick a
  reviewer there.
- `reviewers[]` are the people who maintain the areas others changed, by `inbound_lines`; `active: false` means
  they have gone quiet. Use it to decide whom to ask or tell, not as an assignment.
- `largest_changes[]` are the biggest single commits: where to start when review time is short. Commits touching
  `totals.bulk.threshold` or more files are reported apart under `totals.bulk`.

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
