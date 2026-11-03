# Changelog

Dates are the day a version was tagged. Until 0.2.0 is tagged, its entry describes the `main` branch.

## 0.2.0 (unreleased)

**Tessri is the new name of repolife.** The project, the Python package, the command, the configuration, the
integration receipt, the bundled skill, the SARIF output and the repository are all called `tessri` now. The old
name keeps working through 0.2.x and goes away in 0.3.0:

- `repolife ...` and `python -m repolife ...` run the same program after a one-line notice on stderr.
  `import repolife` works with a `DeprecationWarning`, and `repolife.<module>` resolves to `tessri.<module>` as an
  attribute.
- `.repolife.toml` and `[tool.repolife]` are read when `.tessri.toml` and `[tool.tessri]` are absent, with a notice
  on stderr. When both exist the new one is in force and the old one is ignored, also with a notice.
- An integration receipt, skill files and AGENTS.md markers written by 0.1.x are recognised by
  `tessri integration status` and moved to the new names by the next `install`, `update` or `remove`: the skill is
  created at `.claude/skills/tessri/SKILL.md` (or `.agents/skills/tessri/SKILL.md`) and the old file removed in the
  same run, the AGENTS.md block is rewritten in place with the new markers, and the receipt is written as
  `.tessri-integration.json` with the old file deleted. A user-modified old file is a conflict, as before, and then
  nothing is written.
- `tessri init` replaces an AGENTS.md block that `repolife init` wrote instead of adding a second one.
- Analyzer plugins registered under the `repolife.analyzers` entry-point group keep loading.

What a reader of the output sees change:

- JSON: `meta.tool.name`, and the top-level `tool.name` of scan and integration results, is `tessri`.
  `schema_version` stays 1: no key changed its name or meaning.
- SARIF: the driver is `tessri`, rule ids are `tessri/<kind>`, the property bags are `tessri/finding`,
  `tessri/check` and `tessri/locationless`, and the URI base id is `TESSRI_ROOT`. Code-scanning alert continuity
  from a `repolife/<kind>` rule does not carry over.
- Markdown: the scan heading is `# Tessri report: <repo>`. Error lines on stderr start with `tessri:`.

Also in this version:

- `check --format sarif --locationless keep|omit`. GitHub code scanning rejects a log that contains a result
  without a location; `omit` moves such findings out of `results` and whole into
  `run.properties["tessri/locationless"].omitted`, next to their `count` and the `policy`, which are recorded under
  both policies. Nothing is invented and nothing is dropped; `--fail-on` counts findings, not displayed results.
- A GitHub Actions workflow runs the test suite on Python 3.11 and 3.12 for every push to `main` and every pull
  request.

## 0.1.0

repolife: `scan` (Markdown, JSON and a self-contained HTML report), `why`, `graph`, `impact` with edge provenance
and `--edges imports`, `triage`, `check` (Markdown, JSON and SARIF), `init` and `integration` with a receipt, a
bundled agent skill and a `meta` block on every JSON output. Never tagged; see the git history.
