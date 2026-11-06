# Integration: skills, AGENTS.md, MCP, configuration, CI

`tessri integration` installs the agent skill for Claude Code or Codex, one marked block in `AGENTS.md`, Copilot's
instructions file, the entry that points a host at the [MCP server](mcp.md), a starter configuration file or a
weekly report workflow, with a receipt, and takes it out again.

```bash
tessri integration install --agent claude --agent codex --dry-run   # show the plan, write nothing
tessri integration install --agent claude --agent codex             # project skills for Claude Code and Codex
tessri integration install --agent agents                           # one marked block in AGENTS.md
tessri integration install --agent copilot                          # Copilot's instructions file
tessri integration install --agent mcp --agent vscode               # .mcp.json and .vscode/mcp.json entries for the server
tessri integration install --agent config                           # a .tessri.toml with every option commented out, to start from
tessri integration install --agent report                           # a weekly scan workflow that keeps the report
tessri integration status                                           # what is installed and whether it changed
tessri integration update                                           # refresh files that are still as installed
tessri integration remove                                           # take everything out again
```

Every form takes the project root as `--repo PATH` or as its first argument (default: the current directory).

`integration` keeps a receipt, `.tessri-integration.json`, at the project root: which profiles are installed
(`claude` writes `.claude/skills/tessri/SKILL.md`, `codex` writes `.agents/skills/tessri/SKILL.md`, `agents`
inserts one marked block into `AGENTS.md`, `copilot` writes `.github/instructions/tessri.instructions.md`, `mcp`
adds the `mcpServers.tessri` entry to `.mcp.json`, `vscode` the `servers.tessri` entry to `.vscode/mcp.json`,
`config` writes `.tessri.toml` and `report` writes `.github/workflows/tessri-report.yml`),
the hash of every file it wrote, the exact bytes it inserted into `AGENTS.md`, the entry it added to a JSON file
and the directories it created. Only what the receipt records is ever updated or removed. A file that
already exists is a conflict, even when it is byte-identical to the template; a recorded file you edited is yours
and is left alone; text you add outside the block survives `update` and `remove`; a shared file that was there
before is never deleted. Every command plans and checks all its targets first and writes nothing when any of them
conflicts (exit 1, with the plan); `--dry-run` shows the same plan without writing; `--format json` gives it as
data; single files are replaced atomically and an ordinary failure is rolled back, which is not a cross-file
transaction. Installing files does not prove a running host has discovered them: start a new session in the
project afterwards. Nothing else is touched: no hooks, `.gitignore` line or network. It works in an empty or
non-git project too.

`tessri integration status .` also says, per host (Claude Code, Codex, Copilot's coding agent, editors reading
`.vscode/mcp.json`), which installed file carries its instructions, which one points it at the server, and what
is left to do; for a host whose server configuration is not in the project it prints the line to run or the JSON
to paste. The MCP guide has the [profiles and what each host reads](mcp.md#pointing-each-agent-at-it).

Updating Tessri itself does not rewrite installed instructions. For receipt-managed integrations,
`tessri integration status .` reports `installed-outdated` when the bundled instructions have changed.
Preview with `tessri integration update . --dry-run`, then run `tessri integration update .` to refresh
unchanged managed files and blocks. User-modified content remains a conflict; review and reconcile it yourself.
The updated skill explains impact's evidence sources and `--edges imports`, while candidate tests remain
subject to the project's runner and required checks.

Two profiles are not an agent's. `config` seeds `.tessri.toml` with every option commented out, and the file is
yours from the moment it is written: `status` reports it `installed-current` whatever it says, `update` never
rewrites it, a deleted one is forgotten rather than recreated, and `remove` deletes it only while it is untouched
and otherwise just stops recording it. An existing `.tessri.toml` is a conflict for `install` and is never listed as
unmanaged. `report` writes a workflow that scans the repository every Monday and on demand, summarises the report on
the run and keeps the JSON and the HTML page as an artifact; it is managed like a skill, so an edited workflow is
yours and `update` leaves it alone. As a Claude Code plugin, this repository also ships `.claude-plugin/plugin.json`
and `skills/tessri/SKILL.md`.

Copyable recipes for CI artifacts, SARIF uploads, gates and test selection are in
[workflow-recipes.md](../workflow-recipes.md).
