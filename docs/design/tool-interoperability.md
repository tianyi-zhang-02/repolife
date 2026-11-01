# Tool interoperability

Third-stage design, 2026-10-31. Codex owns this document, workflow recipes and independent acceptance. Claude Code owns the implementation, regression tests, README and packaged skill text. Preserve the first two stages and leave the working tree uncommitted.

The local implementation now supplies this view and the [workflow recipes](../workflow-recipes.md); see [third-stage acceptance](third-stage-acceptance.md) for verified behavior and host boundaries.

repolife supplies repository evidence at the point another tool needs it. Git supplies change identity, linters and type checkers validate language rules, test runners execute tests, and the agent or CI runner decides what to do. The product's contribution is the connection between changed code, structural consequences and observed maintenance. It should not become a second task runner, reviewer assignment system or package manager.

**1. Where tools meet**

| Existing tool or surface | Evidence from repolife | Responsibility retained by the caller |
| --- | --- | --- |
| Git / worktree | Full HEAD and comparison-base identity, uncommitted-state flag | Select the intended checkout and base; refresh after edits. |
| Search / editor | `impact` paths, importers and `why` evidence | Read the relevant code and decide the edit. |
| pytest / another test runner | Related test paths and disclosed counts | Choose valid runner arguments and execute the project's normal validation. |
| Ruff / ESLint / type checker | Structural findings beside language diagnostics | Keep each tool's findings identifiable; do not merge them into a new score. |
| CI / review artifacts | Advisory `check` JSON, Markdown and proposed SARIF | Handle unavailable analysis separately from findings; retain normal build/test jobs. |
| Shell-capable coding agent | Task-routed queries and small evidence payloads | Own execution, approval, escalation and context budget. |
| Future protocol client | An adapter over the same queries | Supply authorized repository access and client-specific lifecycle. |

The first interoperability implementation is a new renderer for `check`, not another analysis command. A CLI and file artifact are sufficient to exercise a real integration without a server or additional runtime dependency. A future MCP adapter should follow demonstrated client demand and reuse the same facts.

**2. SARIF command contract**

```bash
repolife check --repo "$REPO_ROOT" --since "$BASE_REF" \
  --format sarif --fail-on never --out "$REPORT_PATH"
```

Only `check` gains `--format sarif`. Markdown stays the default; JSON fields, ordering, comparison semantics and gate policy stay compatible. `--limit` continues to limit Markdown tables only. SARIF serializes every existing finding, including informational and resolution findings, without rerunning analysis or reading source files to invent locations.

The renderer consumes the already-computed change-check object plus the explicit analysis root. Use only the Python standard library. It must not run Git, execute tools, install packages, make network requests, create configuration or write files itself. The CLI's existing `--out` path performs the explicit artifact write.

Return codes retain their existing meaning: 0 for a completed advisory check, 1 only when the caller's `--fail-on` selection matches findings, and 2 for a handled analysis error. Gate exit 1 still emits a complete SARIF document; an invalid base emits no successful document. An empty or skipped check remains distinguishable through the preserved metadata.

**3. Result mapping**

Produce SARIF 2.1.0 with its schema URI, one run and `tool.driver` identifying repolife and its version. Use a fixed descriptor for each existing finding kind: `new-orphan`, `dangling-import`, `new-cycle`, `cycle-grew`, `new-dependency`, `no-active-owner`, `orphan-resolved`, `cycle-resolved`. Rule identifiers use `repolife/<kind>` and do not contain a path, result count or comparison commit. Descriptor descriptions remain independent of the particular repository.

| Source fact | SARIF representation |
| --- | --- |
| Finding kind | Stable `ruleId` with a matching descriptor. |
| `block`, `warn`, `info` | `error`, `warning`, `note`, respectively, for unresolved findings. |
| `new-dependency`, `orphan-resolved`, `cycle-resolved` | `kind: informational`, `level: none`; they are observations, not asserted failures or proof that a rule passes everywhere. |
| Title, detail and suggested action | A readable `message.text` containing the existing evidence and action. |
| Full original finding, including `id`, `files` and `needs_human` | `result.properties["repolife/finding"]`, so grouped evidence is not lost. |
| Check schema version, kind, metadata, comparison, summary and notes | `run.properties["repolife/check"]`. Preserve full HEAD/base/history identity and skipped-analysis reasons. |

One existing finding yields one SARIF result in the same order. Other finding kinds use `kind: fail` with the mapped severity; SARIF permits a `note` to describe an improvement opportunity. Do not expand an aggregate into many apparently independent alerts, omit a finding because it has no file, or mark a positive resolution as an error. This is an alternative presentation of the existing comparison, not a new finding engine or persistent baseline database. The ordinary JSON report remains the complete format for the detailed orphan/cycle/dependency tables.

No security severity, CVSS, confidence score, fabricated source-line fingerprint, automatic suppression or fix edit is generated. Do not manufacture GitHub's `primaryLocationLineHash` from a finding ID; it has a different meaning. Fingerprint generation and actual uploaded-alert continuity require separate validation.

**4. Locations and portability**

Existing findings are file-level or repository-level. Use the first eligible path in the finding's recorded file order as the primary location and additional distinct paths as related locations. Give related locations numeric IDs and descriptions. The original grouped file list remains in properties. Omit locations when none are available. Do not choose an arbitrary README or line 1 to make a consumer display a repository-level finding.

Do not emit a primary location known to be deleted in `changed_files`; resolution findings may retain those paths only in their original evidence. The renderer otherwise trusts the supplied check facts rather than consulting a possibly different worktree. Reject unsafe absolute/traversing paths as locations while preserving their original evidence in properties. An omitted location is preferable to a URI pointing outside the declared analysis root.

Represent paths as URI-encoded, root-relative references using forward slashes from the report. Spaces, Unicode, `#`, `%` and literal filename backslashes must round-trip; a literal backslash on a POSIX filesystem is not a directory separator. Declare the actual selected root in `originalUriBaseIds` using its absolute file URI and a trailing slash, and reference that base ID from locations. This makes a report usable when saved outside the source directory or when analyzing a project subdirectory. The file URI discloses the local project path; the export does not embed source contents or environment variables.

Omit `region`, columns and snippets because the current evidence does not supply them. Generic SARIF consumers can retain file-level and locationless results. GitHub requires a location to display an alert and imposes additional requirements for PR annotations; this stage must not claim every grouped or repository-level finding appears inline. Local schema validation is not proof of upload acceptance or editor behavior.

**5. Workflow recipes and rollout**

Document copyable shell/stdlib recipes separately from installation. Start with report artifacts so the surrounding workflow can adopt one surface at a time. The lifecycle installer does not generate CI jobs, upload SARIF, install an editor extension or grant credentials.

For CI, the caller supplies the comparison base from its event and makes the necessary Git objects available. Keep reports separate from test results. An unavailable check must not become an empty success artifact. An explicitly enabled gate must preserve its report before propagating exit 1. Existing artifact handling may attach the SARIF file for review; no account is needed to generate it locally.

Uploading a change-only check into a persistent code-scanning category needs deliberate scoping: a different comparison base or a narrower invocation can produce an empty result without proving an earlier repository-wide issue was fixed. Do not recommend this renderer as a full-repository security scan. Keep comparison scope/category consistent and verify consumer behavior before enabling persistent alerts. Hosted upload and editor discovery remain separate integration tests.

For test tooling, show how to read candidate paths safely as data. Never shell-join repository filenames, auto-run returned commands, or treat an empty/capped static candidate list as permission to skip normal tests. File paths are hints; runner syntax and coverage belong to the host project.

**6. Acceptance**

Validate real CLI exports against the official OASIS JSON schema using a validator already available in the development environment; add no runtime dependency. Cover mixed finding kinds, positive resolutions, locationless aggregates, Unicode/special paths, nested analysis roots, skipped/no-code changes, gate 0/1 parity, unavailable comparison errors, explicit output files, standalone zipapp and project immutability. Compare the unmodified JSON/Markdown behavior against the accepted second-stage package. Retain the prior lifecycle acceptance.

Permanent tests should exercise meaningful mapping and CLI behavior. Independent acceptance validates the produced artifact and cross-format semantics, not the renderer's implementation helpers. Do not label a hosted upload or editor interaction as tested without observing it.

**7. Next evidence to collect**

Prioritize a real consumer trial over another adapter: open an export in a selected SARIF viewer and record how it presents file-level, grouped and locationless results. Test hosted uploads separately only when a project deliberately adopts them, including category, comparison-base changes and alert continuity. A successful schema check cannot settle those user-experience questions.

For agent tasks, compare the current task-routed recipe against the host's ordinary search-and-test workflow on both Python and JS/TS projects. Measure relevant-file discovery, missed related tests, extra context, interruptions and latency. Measure repeated `impact`/`why`/`check` analysis before deciding whether request-local reuse or a combined context query earns its complexity. Any reuse must invalidate on worktree, configuration and comparison changes.

Choose a protocol adapter when an actual client cannot use the shell/file path and its repository access model is known. Keep transport packaging optional and retain the CLI as the composition baseline. Do not add hooks or an always-running service merely to increase the number of supported integrations.

**8. Sources**

- [OASIS SARIF 2.1.0 plus Errata 01](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html): format, result kinds, optional locations and URI bases.
- [Official JSON schema](https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json): independent artifact validation.
- [GitHub SARIF support](https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support): supported subset, display requirements and fingerprinting.
- [Microsoft SARIF Viewer](https://github.com/microsoft/sarif-vscode-extension): an existing consumer; live behavior is not yet verified here.
