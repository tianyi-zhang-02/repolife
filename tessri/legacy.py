"""The old name. Tessri was called repolife until 0.2.0, and this module is the one place the old identifiers live,
so that nothing else in the package has to spell them. Everything here, and the `repolife` shim package next to
`tessri`, goes away in 0.3.0.

What still works under the old name through 0.2.x: the `repolife` command and `python -m repolife` (with a notice on
stderr), `import repolife` (with a DeprecationWarning), `.repolife.toml` and `[tool.repolife]` (read when the new
names are absent, with a notice), an integration receipt, skill files and AGENTS.md markers written by an older
version (recognised by `integration status`, and moved to the new names by the next `install`, `update` or `remove`),
and analyzer plugins registered under the old entry-point group.
"""

OLD_NAME = "repolife"
FORMERLY = "formerly repolife"
NOTICE = "repolife is now tessri: the `repolife` command keeps working through 0.2.x and goes away in 0.3.0. Use `tessri`."
IMPORT_NOTICE = "repolife is now tessri: `import tessri` (the repolife name goes away in 0.3.0)"

CONFIG_FILE = ".repolife.toml"
CONFIG_SECTION = "repolife"  # [tool.repolife] in pyproject.toml

RECEIPT = ".repolife-integration.json"
BEGIN = "<!-- repolife:begin -->"
END = "<!-- repolife:end -->"
SKILL_PATHS = {"claude": ".claude/skills/repolife/SKILL.md", "codex": ".agents/skills/repolife/SKILL.md"}

ENTRY_POINT_GROUP = "repolife.analyzers"
