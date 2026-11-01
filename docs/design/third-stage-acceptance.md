# Tool interoperability acceptance

Third stage, 2026-10-31. Codex owns independent acceptance and this record; Claude Code owns the implementation and permanent regression tests. The accepted second-stage package was copied before implementation, so existing JSON and Markdown behavior can be compared directly.

The scope is local, standard-format export and executable workflow recipes. No actual repository receives a CI job, editor extension, uploaded result or extra tool configuration.

**Independent checks**

The fixture runner lives at `/private/tmp/repolife-stage3-20261031/acceptance.py`, with adjacent results and sample reports. The official OASIS SARIF 2.1.0 Errata 01 schema was downloaded from its authoritative URL and is validated using the development environment's existing `jsonschema` package. Neither the schema nor the validator becomes a runtime dependency.

| Scenario group | Required evidence |
| --- | --- |
| Mixed real findings | A real Git fixture yields dangling import, new orphan, new cycle, ownership, dependency and resolution observations; SARIF preserves finding count, order, facts and metadata. |
| Gate parity | Advisory 0 and explicitly enabled warn/block 1 produce equivalent result documents. |
| Cycle growth | The eighth kind retains a stable descriptor and warning semantics. |
| URI encoding | Spaces, Unicode, `#`, `%`, literal colon/backslash and newline filenames round-trip through primary/related locations. |
| Nested analysis root | Relative file URIs resolve against the actual selected project subdirectory. |
| Clean / documentation-only | Empty findings retain explicit skipped-structure metadata rather than claiming analysis ran. |
| Unavailable comparison | Invalid base and non-Git roots diagnose failure; a pre-existing output file is not replaced by a misleading empty success. |
| Explicit artifact / limits | Export to an external path leaves project bytes unchanged; Markdown row limits do not truncate SARIF. |
| Existing format compatibility | JSON and Markdown match the copied second-stage package on the same fixture, allowing only generated-time differences. |
| Standalone zipapp | The same schema-valid export works from the documented standalone artifact. |
| Test-candidate recipe | The actual documented Python snippet returns related paths as data, discloses a partial list, handles unavailable/malformed output and does not execute filename text. |
| Explicit-gate recipe | The actual documented shell snippet retains a report and exit 1, refuses to consume a stale artifact after comparison failure, and treats an exit-1 crash without a current report as unavailable. |
| Offline renderer / unsafe paths | The pure view renders without source reads or tool calls, keeps its input unchanged, and excludes traversing, absolute, deleted and duplicate location paths without dropping original evidence. |

Every exported document is checked against the complete official schema. Additional semantic assertions reject invented source regions, fingerprints, fixes, scores or security severity; distinguish informational observations from failures; and verify the original grouped finding evidence remains accessible. Schema validity alone cannot establish these semantics.

Snapshots compare file bytes, permission modes, directory existence and symlink destinations, including Git metadata. Timestamps are excluded. Independent fixtures include a new Git project with historic maintenance activity, current uncommitted changes and project paths containing spaces and non-ASCII characters.

**Host boundary**

GitHub upload, hosted deduplication, PR annotations and live editor interaction are not covered by local validation. No line precision is invented to satisfy a consumer. Locationless results and grouped related files remain in the artifact even when a consumer does not display them as separate alerts. A change-only result must not be presented as a complete persistent repository-wide alert baseline.

Prior query and lifecycle acceptance remain required. Compare test scope with [the contract](tool-interoperability.md) and [workflow recipes](../workflow-recipes.md) before marking the stage complete.

**Execution record**

2026-10-31, Python 3.12.2: all 13 independent scenario groups pass. Every real CLI export validates against the complete official schema, including the standalone zipapp and special-path fixtures. The documented Python and shell snippets were extracted from the Markdown and executed, rather than replaced by approximations in the runner.

The preceding stages were also rerun against the combined working tree: all 27 first-stage CLI cases and all 20 lifecycle scenario groups pass. The analyzed fixtures' source and Git metadata bytes remain unchanged. Existing JSON and Markdown also match the second-stage snapshot in a direct comparison.

Claude Code's final test-tool output was independently inspected: all 15 SARIF regressions pass, and the complete 345-test suite passes on Python 3.12 and Python 3.11 with `ResourceWarning` treated as an error. Plugin validation also passes. The runtime remains standard-library-only.

An additional URI check identified a legitimate POSIX filename, `a:valid.py`, being mistaken for a Windows drive path. The implementation now distinguishes drive-absolute paths from relative literal-colon names, retains the latter as encoded locations and has a permanent regression. All 13 independent groups pass again with this case included. The gate recipe also passes an added exit-1 crash experiment without replacing the older valid artifact.

Acceptance is complete for the local exporter and workflow recipes described here. No commit, push, automatic project integration or hosted upload has been performed. Live consumer behavior remains outside this acceptance as described above.
