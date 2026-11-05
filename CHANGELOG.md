# Changelog

Dates are the day a version was tagged.

## Unreleased

- `tessri mcp`: the questions as Model Context Protocol tools over stdin/stdout, with nothing installed. Seven
  read-only tools mirror the commands (`tessri_repos`, `tessri_scan`, `tessri_why`, `tessri_impact`,
  `tessri_graph`, `tessri_triage`, `tessri_check`); each returns the command's `--format json` object as
  `structuredContent` and its text as `content`, from one analysis. `--root` is repeatable, so one server serves
  several checkouts and a tool names one with `root`. A mistake in the arguments is a tool result in the sentence
  the command prints; a malformed request is a JSON-RPC error. Both the 2026-07-28 revision of the protocol
  (`_meta` version, `server/discover`) and the earlier `initialize` handshake are spoken.
- `tessri integration` gains three profiles: `mcp` (the `mcpServers.tessri` entry in `.mcp.json`), `vscode` (the
  `servers.tessri` entry in `.vscode/mcp.json`) and `copilot` (`.github/instructions/tessri.instructions.md`, the
  skill under Copilot's frontmatter). An entry profile records the entry, not the file: an existing file keeps its
  other entries; one that cannot be read as JSON, or already has the entry, is a conflict. `status` says per host
  which file carries its instructions, which points it at the server, and what is left to do, with the line to run
  for Codex and the JSON to paste for Copilot's coding agent. The skill and `AGENTS.md` block name the tools.
- JSON: the scan object carries `kind: "scan"` and the impact object `schema_version`, which the JSON guide said it
  had; nothing else changed and `schema_version` stays 1.
- A page (`.html`) wires in what it loads and only mentions what it says. Its `src` attributes, `<link href>` and
  inline `<script>` code are wiring, as before (`<script src="/src/main.tsx">` makes that file an entry point);
  its text, its hyperlinks and its other attributes are now a mention, like a README's, where every path in the
  file used to count as wiring. On this repository the landing page's sentence about `tessri/graph.py` had made
  that file and `tessri/config.py` "reachable from a production entry point" through `config-ref: site/index.html`;
  `why` now shows the import route and lists the page under `mentioned in docs`. A page under `docs/` is all
  mention, as before.
- `why` says what evidence each edge rests on, with the names `impact` uses: `pkg/loader.py (string)` under
  `depended on by` or `depends on`, and `-(string)->` for a hop of the `reached via` route; an import statement
  goes unmarked. The JSON carries the same under `graph.kinds` (`reached_via`, `dependents`, `depends_on`); no
  existing key changed.

## 0.2.0 (2026-11-04)

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
- Git history follows the renames git detects: activity, authors, fix counts, ownership credit and the review
  windows are read under a file's current name, so a move no longer restarts its history (this repository's own
  rename had made every file look one commit old). A pure move is activity but credits nobody with maintenance.
  A file rewritten beyond git's similarity threshold when moved starts over; a path re-created after a move is a new file.
- A file name that several files share names none of them. A bare `utils.py` in a config, a script or a string used
  to resolve to every `utils.py` in the repository (on one 2,000-file repository, fourteen such names fanned out to
  701 files, `__init__.py` alone to 432), making them all reachable and giving each a `string` edge; now such a name
  resolves to nothing, the scan's caveats list the names configs and scripts used with how many files each fits, and
  an `entry` in the configuration still means every file it fits. The bare `__init__.py` and `__main__.py` never
  name a file. Verdicts on that repository did not change; a third of its `string` edges were this.
- `check` and `triage` follow the renames git detects. A moved file is one changed file under its new name, with the
  lines edited on the way (a pure move has none) and its old path as `from`; the summary counts it under `moved`.
  `check` compares the two sides under the new names, so a renamed package keeps its cycles, dependencies and orphans
  instead of reporting them gone and new again; a file moved but still imported under its old name by a file the change
  did not touch is a `dangling-import` (`moved_to` names the new path); and moved code keeps its maintainers for the
  no-active-owner check, which used to pass it over for lack of history. `triage` ranks a moved file by the history of
  its old name instead of as a new file. History read for a dirty tree follows an uncommitted `git mv` the same way,
  and history read up to the base of a change is read under the names the tree has now. Across this repository's own
  rename, `check` went from 84 code files (37 added, 31 deleted), 17,292 lines, a false new cycle and a false resolved
  one to 53 code files (6 added, 16 modified, 31 moved), 1,790 lines and no finding; `triage` had ranked the twelve
  deleted `repolife/*.py` paths first and now ranks the moved files by their history.
- A site: the landing page and the guide at https://tianyi-zhang-02.github.io/tessri/, built from the README and
  `docs/guide/` by `tools/build_site.py` with nothing installed (no framework, no webfont, no request to anyone
  else), and published by a workflow on every push to `main` that touches them.

## 0.1.0

repolife: `scan` (Markdown, JSON and a self-contained HTML report), `why`, `graph`, `impact` with edge provenance
and `--edges imports`, `triage`, `check` (Markdown, JSON and SARIF), `init` and `integration` with a receipt, a
bundled agent skill and a `meta` block on every JSON output. Never tagged; see the git history.
