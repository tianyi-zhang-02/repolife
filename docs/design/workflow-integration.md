# repolife workflow integration design

Design reviewed on 2026-10-30; structured queries, reversible integration and portable change reports are implemented in the local working tree on 2026-10-31. Implementation baseline: `7e90477bcd83e4de470528a2e3869d61e89b6c59`. See [first-stage acceptance](first-stage-acceptance.md), [second-stage acceptance](second-stage-acceptance.md) and [third-stage acceptance](third-stage-acceptance.md) for the tested scope and results. Broader coverage reporting, live host discovery, caching and MCP remain future work.

repolife helps people and coding agents decide where to look before a change, what the change reaches, and what it leaves behind. Its reusable unit is a repository query with inspectable evidence. Existing build, test, review and agent workflows keep control of execution and policy.

The delivered interoperability increment is specified in [tool interoperability](tool-interoperability.md), with [copyable workflow recipes](../workflow-recipes.md). It adds a SARIF view of existing change findings for report consumers, without another analysis engine or workflow runtime. [Third-stage acceptance](third-stage-acceptance.md) records its verification separately from live hosted integration.

The first delivery should make the existing commands easier to compose: structured explanations, explicit analysis coverage and concise task instructions. A new orchestration framework, universal risk score or hosted service is outside this design.

**Division of work:** Codex owns repository-root design documentation, integration behavior, contract proposals and independent acceptance. Claude Code owns `repolife/*.py`, `tests/`, `README.md`, `repolife/templates.py` and `skills/` for both implementation stages. Codex does not edit those files. This document lives outside the Python package so the documented zipapp build does not bundle it.

**1. Product scope and evidence**

The primary starting audience is maintainers and agent builders working in Python or JS/TS repositories with local filesystem access. The product is useful for human-authored changes too. Agent-heavy development explains the attention problem; it is not a prerequisite for adoption.

| Moment | Question | Existing query |
| --- | --- | --- |
| Understand a repository | Where are the modules and entry points? | `scan`, `graph` |
| Plan an edit | Which importers and tests relate to this target? | `impact` |
| Prepare review | Which changed files deserve attention first, and who has maintained them? | `triage` |
| Finish an edit | Which structural findings did this change introduce or resolve? | `check` |
| Inspect a claim | Why did this file receive this verdict? | `why` |

Preserve the existing triage order: recent commit activity, then change size. Ownership, fix history and import reach remain context. The documented backtest covers one repository and does not establish general bug prediction, review capacity or incident severity. No composite score is introduced.

An import relation is evidence of a structural relationship. Related tests are candidates for validation; they are not a complete test selection guarantee. Absence of a static path is not proof of absence of runtime or external use. Ownership describes observed maintenance, not authority or an assignment.

**2. Integration commitments**

| Commitment | Observable behavior |
| --- | --- |
| Use before installing integration | Queries run without `init`; no account, model or service is required by the built-in analysis core. |
| Preserve repository state | Queries do not modify source, index, branches or project instructions. Explicit output files and temporary comparison trees remain supported. |
| Keep costs visible | Broad scans are explicit; routine task outputs are bounded and disclose truncation. No mandatory background daemon or per-edit scan. |
| Respect caller policy | Findings and analysis failures are distinct. Blocking is enabled explicitly by the caller. |
| Support removal | Generated integrations identify their own content and can be removed without deleting user edits. |
| Retain local operation | Adapters do not upload repository contents implicitly. A separately installed analyzer may have additional requirements that must be disclosed. |
| Degrade explicitly | Missing history, unsupported languages and incomplete analysis are represented as unavailable or partial, never as zero findings. |

Zero dependency applies to the current built-in core. Optional protocol adapters may use optional dependencies without changing the installation path for core users. A Python runtime is still required; one-shot package retrieval also needs network access unless the artifact is already available.

**3. Query and output contract**

CLI plus JSON is the first composition interface. Skills, CI and a possible MCP adapter call the same analysis/query functions rather than reproduce verdict logic. A supported Python embedding API can follow demonstrated demand; internal dataclasses are not declared stable by this draft.

Keep current schema version 1 payloads and meanings. Additive fields are allowed; removing, renaming or changing existing meanings requires a schema change. Avoid wrapping existing payloads inside a new `data` object. Keep machine JSON on stdout and diagnostics on stderr.

The first delivery adds `repolife why <path> --format json`. It serializes the same resolved target, reachability, roots, importers, config/doc references, maintenance evidence and caveats used by the text explanation. Facts are collected once and rendered as text or JSON, without parsing rendered text back into data. Text output remains the default. The first delivery returns a single-target object; batch queries can follow with a separately specified result shape rather than changing the root type according to argument count.

Claude Code also proposed a shared metadata helper. The current scan already exposes `tool`, `generated_at`, `git`, `settings`, reachability coverage and analysis caveats. Keep those existing fields. If a new `meta` block is added across commands, generate both it and legacy projections from the same facts; distinguish the current HEAD from the history revision used for ownership/activity and the resolved comparison base. A missing Git repository and a repository with no commits need different reason values.

The first metadata contract uses the following names inside the additive `meta` block. Preserve existing top-level scan fields and the abbreviated `change.head`/`change.base` fields of triage/check; do not repurpose them or silently change their presentation.

| Proposed field | Meaning |
| --- | --- |
| `meta.git.head` | Full current checkout HEAD object ID, independently resolved; null without a resolvable HEAD. |
| `meta.git.history_rev` | Full resolved commit used for history-derived activity/ownership; null when unavailable or not requested. |
| `meta.change.base` | Full merge-base used by a change query; absent for a path query. |
| `meta.git.available` | Whether usable history was available to the requested analysis, with the same broad meaning as the legacy scan field. |
| `meta.git.reason` | Null when available; otherwise `not-a-repository`, `no-commits`, `git-not-found`, `git-error` or `not-requested`. |

Probe repository membership, executable availability and HEAD separately when needed; the current `Activity | None` return does not distinguish these cases. A failed history read in a valid repository must not be mislabeled `no-commits`. The current `Activity.head` is the analyzed revision, which may be the merge-base; it must not populate `meta.git.head` indiscriminately. Exact coverage counters can follow in an additive stage without delaying this distinction.

Coverage metadata should distinguish capabilities rather than flatten them into a single confidence number:

| Dimension | Required distinction |
| --- | --- |
| Reachability | Analyzed files versus files without an analyzer |
| Parsing | Successfully parsed files versus fallback or unparsed files |
| Inventory | Included files versus excluded, oversized, binary, symlink or submodule content |
| Git history | Available, no commits, shallow/truncated, or unavailable |
| Ownership | Observed result versus unavailable history |
| Change comparison | Exact resolved base versus unavailable comparison |

Some of these facts already exist in different outputs. Reuse them and add missing reasons; do not introduce conflicting parallel definitions. Coverage limitations belong beside the result as machine-readable data, not only in a README paragraph.

Represent capabilities that were not run separately from capabilities that ran and found nothing. For example, `check` currently returns early when no code files changed; metadata for that path must not claim a full structural analysis took place. Reasons may include `no-code-changes`, `not-requested`, `no-commits` or an actual analysis error.

Keep severity separate from evidence strength and coverage. Existing `block` findings have analyzer assumptions; clients must not interpret the label as proof of runtime failure. An empty findings list means no reported findings within the stated analysis scope, not approval of the change.

Existing change findings already have IDs. Preserve those IDs and kinds in the first iteration. A canonical explanation for a finding must retain its base, target and relevant files. Evidence paths and repository strings are data; adapters must not promote them into agent instructions or executable commands.

For large outputs, return total count, returned count and an explicit truncation indicator. A short response must have a way to request more evidence. A future generic row limit must not silently change graph traversal or the meaning of existing `--hops` options.

**4. Analysis identity and concurrent edits**

A branch name or HEAD SHA alone cannot identify uncommitted contents. Results intended for reuse should describe what was analyzed:

- resolved HEAD and comparison base when available;
- analysis time/reference time for activity and ownership calculations;
- tool and analyzer versions;
- effective configuration identity;
- working-tree state, including relevant untracked files;
- whether consistency across the read was verified.

Stage this work. Initially expose facts already available and label working-tree consistency as unverified. Do not call `git status` a content fingerprint or claim an atomic snapshot. A later content identity must include relevant source and project/config inputs; its scope and computation cost need measurement.

For multiple worktrees, consumers supply the target root explicitly and never reuse dirty-worktree results merely because HEAD matches. A later cache key must include content/config/analyzer identity and reference time where time affects results. Write caches outside the repository by default, or use an explicit location. Preserve a no-cache path.

If the tree changes during analysis, report that consistency could not be established or ask the caller to rerun. A start/end check can detect some races but does not create a transactional snapshot. Parallel agents can share a verified immutable snapshot; they still need fresh verification after edits. Dependency overlap does not prove that tasks can safely run concurrently.

**5. Advisory behavior and policy**

Preserve the current `check --fail-on never|warn|block` behavior. Keep exit 1 for a successfully evaluated, caller-selected failing condition; usage or analysis errors are separate from findings. Audit existing error handling before promising a uniform structured error contract across all commands.

| Outcome | Advisory integration | Explicit gate |
| --- | --- | --- |
| Complete analysis, no selected findings | Continue with ordinary validation | Pass the selected structural rule |
| Complete analysis, selected findings | Present concise evidence | Fail according to `--fail-on` |
| Partial analysis | Disclose missing coverage | Caller chooses whether coverage is required |
| Analysis unavailable | Report failure and continue the surrounding advisory workflow | Mark the gate unavailable or fail according to the caller's explicit policy |

Failing to analyze must never be displayed as a clean scan. An advisory wrapper may continue other work, while preserving the failed result. An explicit invocation with an invalid base or invalid configuration remains an error; adapters must not silently choose a different base or ignore broken configuration.

Today caught `TriageError`/`CheckError` failures print to stderr, return exit 2 and emit no JSON on stdout. Callers must recognize that missing result as unavailable rather than parse an empty redirected file as no findings. This describes those caught failures, not a promise that all commands already return structured errors. A valid JSON result with exit 1 is still a successfully evaluated gate failure and should remain readable by the host.

`no-active-owner` and `needs_human` are evidence/escalation signals. A generic skill should not create an unconditional requirement to assign a human before any edit. Teams may opt into that policy. The same principle applies to choosing reviewers, sending messages, deleting files and deciding whether to merge: the host retains those decisions and permissions.

**6. Integration surfaces**

| Surface | Responsibility | First delivery |
| --- | --- | --- |
| CLI/JSON | Stable query inputs, results and errors | Improve existing commands |
| Skill | Trigger selection and interpretation | Short task router with on-demand references |
| Project instruction block | Point to available capability | Small optional block |
| CI | Compare the event's intended base and head | Opt-in differential recipe |
| Lifecycle hook | Trigger selected cheap queries | Optional, measured, host-specific |
| MCP | Expose the same read-only queries | Add when a real client requires it |

The shared skill should route by intent: target edit to `impact`, review to `triage`, change completion to `check`, claim inspection to `why`, broad discovery to `scan`/`graph`. Do not begin every task with a full scan. Put detailed schema and cleanup guidance in references. Keep dependency installation explicit; routine analysis must not unexpectedly install or update software.

An existing shell workflow can already use the following calls independently at the relevant task moments. `REPO_ROOT`, `TARGET_PATH` and `BASE_REF` are supplied by the host; the base is selected from the task or CI event, not guessed by repolife.

```bash
repolife impact "$TARGET_PATH" --repo "$REPO_ROOT" --format json
repolife triage --repo "$REPO_ROOT" --since "$BASE_REF" --format json
repolife check --repo "$REPO_ROOT" --since "$BASE_REF" --format json --fail-on never
```

The host checks command success before consuming the result. It runs its usual tests/build independently and may select `--fail-on block` when it deliberately enables that gate. These calls are an integration recipe, not a requirement to run all three for every task. `why --format json` is available in the first-stage implementation.

Keep one semantic skill source and small host-specific installation adapters. Supported discovery directories and manifest formats must be verified for each host. Lifecycle acceptance verifies the generated filesystem layout; claiming live host support additionally requires evidence that the target host discovers and invokes the skill. Do not claim all agents support the same hooks or instruction files.

CI should pass an explicit base from its event rather than assume a branch named `main`. When the base is missing in a shallow checkout, explain the missing history. Pin tool versions in reproducible CI examples. Leave existing test/build jobs intact and start with reporting unless the team explicitly enables a gate. Fork-PR analysis needs no write credentials or execution of repository code.

MCP is a transport adapter, not repository access by itself. A local adapter reads an explicitly selected root; a remote deployment needs an explicit checkout or artifact source and its own access boundary. Keep the core usable without an MCP dependency or server. For embeddings that load third-party analyzer entry points, extension discovery is a trust decision and should be configurable before advertising a strict read-only execution boundary.

**7. Reversible installation**

The second stage adds `repolife integration install|status|update|remove` while preserving legacy `init` defaults and behavior. Installation requires explicit `--agent claude`, `--agent codex` or `--agent agents` profiles. See [the lifecycle design](reversible-integration.md) for command examples and the full ownership contract.

A visible root-level `.repolife-integration.json` receipt records fixed managed paths, exact inserted spans, generating version, content hashes and installer-created directories. On update/remove:

1. Preview the affected paths and blocks without writing.
2. Compare current managed content with its recorded generated hash.
3. Update or remove unchanged managed content only.
4. Preserve edited content and report a conflict with a manual recovery path.
5. Delete only owned files or exact inserted spans; reclaim only recorded installer-created directories that are empty.

Malformed/duplicate markers and user modifications block the selected plan. Invalid paths, symlinked destinations and unusable receipts are errors checked before mutation. Repeated installation and removal are idempotent. Preflight, an exclusive mutation lock, individual atomic replacements and ordinary-error rollback guard writes; this is not a power-loss transaction. The lifecycle does not manage `.gitignore`, configuration, CI or hooks, and never automatically adopts legacy `init` files.

**8. Existing and new repository behavior**

| Environment | Expected behavior |
| --- | --- |
| Existing repository with old findings | `check` foregrounds change-introduced findings; full scan stays available. |
| Repository with no commits | Structure queries remain useful; history/ownership are unavailable; a base-dependent query explains that it cannot compare. |
| No Git repository | Supported filesystem structure queries work; history-dependent capabilities are unavailable. |
| Library/public API | Exported entry points and explicit `keep` improve reachability; external consumers remain invisible. |
| Unsupported language | Volume/activity when available, no fabricated reachability verdict. |
| Multi-worktree task | Explicit root and state metadata prevent accidental cross-worktree reuse. |
| Agent without shell access | Needs an adapter with authorized repository access; installing a skill alone does not supply execution. |
| Unattended task | Receives bounded evidence and explicit outcomes; follows the host's escalation policy. |

**9. Delivery and acceptance**

| Stage | Deliverable | Acceptance |
| --- | --- | --- |
| Delivered: first | Structured `why`, additive metadata, intent-routing instructions | Compatible text/JSON meanings; HEAD, history revision and base distinguished; unavailable-history reasons explicit. |
| Delivered: second | Existing-workflow recipe and reversible integration lifecycle | Preview, repeated installation/removal, user-edit protection, guarded updates and owned-content cleanup pass independent acceptance. |
| Delivered: third | Standard SARIF change report and executable workflow recipes | Real exports validate against the official schema; original findings and gate outcomes remain compatible; candidate/artifact handoffs pass executable checks. |
| Future | Broader capability coverage and stronger state identity | Parsing, inventory and unsupported-language gaps are machine-readable; measure reuse needs before adding caching. |
| After observed demand | Bounded context query, caching or MCP | Measurable workflow gain exceeds integration/runtime/context overhead. |

Before adding a `context` command, try a recipe using existing `impact`, `triage`, `check` and structured `why`. Add a command only if callers repeatedly need the same composition. Filtering a result to a target does not imply that analyzing only that subtree is sound; external importers still matter.

The initial consumers are shell-capable agents using a skill and CI wrappers; streaming and a remote service are deferred. Keep two request scopes explicit: a path query without a base uses `impact`/`why`; a change query uses the existing `triage`/`check` base semantics. A requested path can narrow returned evidence but must not silently narrow the change being checked. Any future combined query must declare whether it returns path context or change context.

Claude Code identified repeated full analyses when callers compose commands. Reuse inside one request is a useful candidate before persistent caching. Reuse must respect filesystem contents, history revision, configuration and reference time: triage reads current files with historical ownership/activity, while check also reads the base tree. Two objects cannot be shared merely because their repository path matches. Measure the actual cost before committing to a combined command or a fixed number of analysis passes.

In the current check implementation, the extracted base tree has no Git history; the current-tree analysis reads history up to the base. Compare graph-derived reachability, orphan membership, cycles and edges across them. Do not compare their generic activity statuses or orphan confidence as if both had equivalent history. Maintenance evidence comes from the current-tree analysis with its explicit historical revision. A future finding that needs historical base-side ownership must obtain that history explicitly.

Use real task comparisons to measure missed related edits, false-positive structural findings, relevant-file discovery time, bytes/tokens read, added latency and unwanted interruptions. Record cold/warm behavior and history requirements on representative small and large repositories. Set performance budgets from those measurements rather than claiming unmeasured timings.

The first implementation review should settle the structured explanation shape, command coverage for metadata, minimum state identity, and exact file ownership. Preserve the existing algorithms until separate evidence supports changing them.

Claude Code's read-only review on 2026-10-30 confirmed the file split and first-stage feasibility. The agreed candidate implementation scope is single-target `why --format json`, unavailable-history reasons, distinct HEAD/history/base metadata and revised generic skill escalation wording. Coverage unification can follow. No implementation, commit or push was performed during this design review.

The first-stage implementation adds shared metadata to all JSON query outputs and identifies the no-code-change check path as skipped. Its acceptance recorded 281 passing tests on each of Python 3.11 and 3.12, plugin validation and 27 independent CLI scenarios. The second stage adds the explicit lifecycle for Claude, Codex and shared instructions; its 20 independent scenario groups include byte-preserving round trips, failure recovery, template upgrades and zipapp operation. See the separate acceptance records for current validation and limits. Broader coverage reporting, immutable worktree identity, caching, live host discovery and protocol adapters remain later work. Source changes and design documents are local and uncommitted.

The third stage adds `check --format sarif` and documented adapters for test candidates and report/gate handling. All 13 independent interoperability groups pass official-schema and semantic checks, including real special-path and nested-root fixtures; the prior 27 CLI cases and 20 lifecycle groups also pass. The complete suite now contains 345 passing tests on each of Python 3.11 and 3.12, plus plugin validation. Hosted uploads, alert continuity and live editor behavior remain unverified rather than implied by artifact validity.

**10. References**

- Current CLI, explanation and installation behavior: `repolife/cli.py`, `repolife/explain.py`, `repolife/mount.py`, `repolife/templates.py` at the baseline above.
- Public schema compatibility: `repolife/model.py` and `repolife/report.py`.
- Existing product and backtest limits: `README.md`, especially triage, ownership and limits.
- [Agent Skills specification](https://agentskills.io/specification): metadata, instructions and references support progressive disclosure.
- [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills): skill discovery and on-demand loading.
- [Claude Code hooks](https://code.claude.com/docs/en/hooks): host-specific lifecycle integration; startup hooks should stay fast.
- [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture): tool transport and local/remote deployment boundaries.
