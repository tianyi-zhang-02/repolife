---
name: repolife
description: Check which parts of a repository are alive before refactoring or cleaning up - code volume, git activity and unreachable (orphan) files. Use when asked about dead or unused code, repository health, what is safe to delete, or where to start a cleanup.
---

# repolife

repolife reports three things about a repository: how much code there is, how recently it
changed, and whether anything still reaches it. It only reads; it never edits code.

## Run it

```bash
repolife scan . --format json --out .repolife/report.json
```

If `repolife` is not on PATH, use `python3 -m repolife ...` or `uvx repolife ...`.
Add `--format md` (the default) for a report meant to be read by a person.

Read in this order: `summary` (sizes, status counts, orphan share), `cleanup.orphan_files`,
`cleanup.test_only_files`, then `hotspots` and `directories` for where change is concentrated.

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
