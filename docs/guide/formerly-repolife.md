# Formerly repolife

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

What changed for readers of the output is listed in [CHANGELOG.md](../../CHANGELOG.md): `tool.name` is `tessri` (the
schema version is unchanged), SARIF rule ids are `tessri/<kind>` under the driver `tessri` with the base id
`TESSRI_ROOT`, the scan heading is `# Tessri report`, and stderr lines start with `tessri:`.
