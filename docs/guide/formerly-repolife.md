# Formerly repolife

Tessri was called repolife until 0.2.0. The 0.2.x versions kept the old name working, with notices; 0.3.0 removed
it, so upgrading from 0.1.x or 0.2.x means:

- Run `tessri` instead of `repolife`, and `python -m tessri` instead of `python -m repolife`; `import repolife` is
  an ImportError.
- Rename `.repolife.toml` to `.tessri.toml` and `[tool.repolife]` to `[tool.tessri]`. 0.3.0 does not read the old
  names and does not notice them, so a stale old file is silently not in force, where 0.2.x said so on every run.
- Register analyzer plugins under the `tessri.analyzers` entry-point group.
- An integration that 0.1.x installed (a `.repolife-integration.json` receipt, `.claude/skills/repolife/SKILL.md` or
  `.agents/skills/repolife/SKILL.md`, `<!-- repolife:begin -->` markers in `AGENTS.md`): run
  `tessri integration update` on 0.2.x first, which moves it to the current names in one run, or delete those files
  and the block by hand and run `tessri integration install` again. 0.3.0 does not read the old receipt, and
  `tessri integration status` does not list the old paths.

What changed for readers of the output in 0.2.0 is listed in [CHANGELOG.md](../../CHANGELOG.md): `tool.name` is
`tessri` (the schema version is unchanged), SARIF rule ids are `tessri/<kind>` under the driver `tessri` with the
base id `TESSRI_ROOT`, the scan heading is `# Tessri report`, and stderr lines start with `tessri:`.
