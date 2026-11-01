# First stage workflow integration acceptance

The first stage makes repolife easier to call from an existing agent or CI workflow. Acceptance checks the public CLI against the pre-change implementation and exercises states that an unattended caller must distinguish.

Baseline: `7e90477bcd83e4de470528a2e3869d61e89b6c59`. Validation uses Python 3.12 and the built-in analyzers. The operating system's `python3` may be older than the project's Python 3.11 minimum; use an explicitly supported interpreter.

**Compatibility fixture**

Use a repository whose root contains spaces, with a production entry point, a service importing a helper, a test importing the service, an unreachable Python module and a Rust file without a reachability analyzer. Give the initial commit one author and a subsequent commit another. Preserve the first commit as the comparison base. Delete the helper in the working tree without editing its importer and add a new untracked module.

This produces three distinct states: the comparison base, current HEAD and uncommitted contents. The deleted helper gives an existing deterministic dangling-import finding, so exit-code behavior can be checked without introducing a new rule.

| Check | Acceptance criterion |
| --- | --- |
| Default `why` for entry point, service, orphan, unsupported language and untracked file | Text remains byte-for-byte compatible with the baseline on the same fixture. |
| JSON scan, graph, impact and triage | Existing keys and values retain their meanings; new keys are allowed. Generated timestamps are excluded from direct value comparison. |
| JSON change check in advisory mode | Findings are returned and the command exits 0. |
| The same check with `--fail-on block` | Findings remain readable JSON and the command exits 1. |
| Invalid comparison base for check or triage | Exit 2, diagnostic on stderr and no JSON on stdout. |
| Structured `why` for each file category | A single object identifies the resolved path and includes inspectable facts; unsupported reachability stays unavailable. |
| Change-query metadata | Full current HEAD differs from the full history revision/base; neither is substituted for the other. |
| Analyzed repository after queries | Source, working-tree files and Git metadata bytes are unchanged. No configuration or agent instruction file is installed. |
| Standalone zipapp built from the package | Structured `why` works without an editable install or repository-specific `PYTHONPATH`, with the same target and HEAD identity. |

Compare baseline JSON recursively: every old key must remain present and every old value must match, allowing additive keys. Keep list contents and ordering unless a change is explicitly part of the approved contract. This checks public behavior independently of how the new implementation is factored.

**Unavailable history fixture**

| Environment | Required metadata outcome |
| --- | --- |
| Plain directory containing a Python entry point | Structure query succeeds, `meta.git.available` is false and reason is `not-a-repository`. |
| Initialized repository with files but no commits | Structure query succeeds, history is unavailable with `no-commits`. |
| Valid Python process with no Git executable on PATH | Structure query succeeds, history is unavailable with `git-not-found`. |
| Valid repository where Git discovery works but history reads fail | Structure query succeeds with `git-error`; do not label it an empty repository. |
| Repository with an empty first commit and no files | A normal empty inventory is not `git-error`; history is either read or explicitly `not-requested`. |
| Change query with no code changes | Successful result identifies structure as skipped with `no-code-changes`, and history as `not-requested`. |
| Local shallow clone | Metadata preserves the shallow-history limitation and the full current HEAD. |
| Nonexistent explanation target | Exit 2 and no successful JSON result. |

Simulate executable/history failures in temporary test directories. Do not change the developer's global Git configuration or remove their installed Git. Run the Python executable by absolute path when testing a restricted PATH.

**Host behavior**

A consuming agent or CI wrapper handles result availability before interpreting findings. Exit 0 means the requested advisory query completed; it is not approval to merge or skip ordinary tests. Exit 1 is a completed, explicitly enabled gate failure with a result. Exit 2 from a handled query error supplies no result and must remain unavailable rather than clean.

For a change-check consumer, the essential handling can be expressed without replacing the surrounding workflow:

```python
completed = subprocess.run(
    ["repolife", "check", "--repo", repo_root, "--since", base_ref,
     "--format", "json", "--fail-on", "block"],
    capture_output=True, text=True, check=False,
)
try:
    report = json.loads(completed.stdout)
except json.JSONDecodeError:
    report = None
valid_result = isinstance(report, dict) and report.get("kind") == "change-check"
if completed.returncode not in (0, 1) or not valid_result:
    outcome = "unavailable"
elif completed.returncode == 1:
    outcome = "blocked-by-selected-policy"
else:
    outcome = "reported"
```

This is the outcome-handling portion of an adapter, not a complete runner. The host also handles process-launch failures and timeouts as unavailable, validates the supported schema version, and applies its own policy to each outcome. An exit-1 crash without valid result JSON is unavailable, not a successfully evaluated gate failure.

The generic skill may recommend escalation for missing maintenance coverage. It must not require every unattended edit to wait for a newly assigned human. Existing team instructions and caller policy remain authoritative.

**Scope of this acceptance**

These checks cover local CLI composition and compatibility for the first-stage changes. They do not validate every language feature, all possible Git failures, remote MCP access, host skill discovery, reversible uninstall or the accuracy of triage predictions. The repository's regression suite remains required for analysis behavior beyond these integration fixtures.

**Execution record**

2026-10-31, Python 3.12.2: 13 baseline CLI cases and 14 additional interface scenarios passed against the working implementation. The CLI comparisons preserve old text and JSON values while allowing additive keys. The checks distinguish current HEAD from base/history, advisory from gate failure from unavailable results, and unsupported analysis from an empty result. Standalone zipapp execution passed. Source and Git metadata bytes in the analyzed fixture remained unchanged.

The final repository suite contains 281 tests, including 28 new explanation/metadata regressions. Claude Code's test log reports all 281 passing on Python 3.12 and 3.11, with ResourceWarning treated as an error. Plugin validation passed. Codex independently ran the pre-existing 253 tests, both new test modules after their fixture fixes, and the 27 CLI compatibility/integration scenarios.

Two implementation issues found during independent review were corrected and retained as regressions: failed Git probes being mistaken for a missing repository, and a valid repository with an empty commit being mistaken for a Git error. The default text and legacy JSON comparisons passed after those corrections. New test fixtures were also corrected to use explicit commit dates and a real entry point for their reachable-file expectation.

The first-stage acceptance is complete for the features described here. The implementation remains in the local working tree, without a commit or push. Full commit IDs describe Git commits; the current metadata does not provide an immutable working-tree snapshot or content fingerprint. Callers must refresh results after edits, as described in the broader design.
