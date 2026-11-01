# Compose repolife with existing tools

Use the queries at the relevant moments in an existing workflow. No `init`, integration receipt, account or model is required to run them. Use an already available repolife executable and Python 3.11+; package installation is a separate choice. The examples below do not execute repository code, assign reviewers or upload reports.

**Before an edit: related code and test candidates**

Let the host supply a repository root and a target from the task. Use `impact` to narrow the reading list, and `why` to inspect a particular claim:

```bash
repolife impact "$TARGET_PATH" --repo "$REPO_ROOT" --format json
repolife why "$TARGET_PATH" --repo "$REPO_ROOT" --format json
```

`impact.tests.paths` contains related test files, not runner commands. `tests.files` is the total number found by the static traversal; the returned path list is bounded. A smaller list than the total is a partial list. An empty list is not a coverage proof. Keep the project's usual test/build checks, including tests that dynamic loading or external consumers may require.

The following stdlib adapter prints candidate paths as JSON and checks the available metadata. It does not start pytest or another runner. Pass the installed CLI path, analysis root and target as three arguments. Keeping argument arrays and JSON avoids treating a repository filename as shell syntax.

```python
import json
import subprocess
import sys

executable, root, target = sys.argv[1:]
try:
    completed = subprocess.run(
        [executable, "impact", target, "--repo", root, "--format", "json"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if completed.returncode != 0:
        raise ValueError("impact query did not complete")
    report = json.loads(completed.stdout)
    if report["meta"]["schema_version"] != 1 or report["kind"] not in ("file", "directory"):
        raise ValueError("unsupported impact schema")
    tests = report["tests"]
    candidates = tests["paths"]
    total = tests["files"]
    if not isinstance(candidates, list) or not all(isinstance(p, str) for p in candidates):
        raise ValueError("invalid candidate paths")
    if type(total) is not int or total < len(candidates) or not isinstance(report["target"], str):
        raise ValueError("invalid candidate metadata")
    selection = {
        "target": report["target"],
        "candidates": candidates,
        "reported_total": total,
        "list_is_partial": len(candidates) < total,
        "complete_test_selection": False,
    }
except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
    print("repolife test candidates unavailable; use project validation policy", file=sys.stderr)
    sys.exit(2)

print(json.dumps(selection, ensure_ascii=False))
```

The caller must still choose runner syntax, interpret options such as pytest node IDs, and decide which tests to run. Never turn arbitrary report values into `sh -c`, `eval` or an executable command string. Missing executable, timeout or malformed output means unavailable evidence.

**During review: order attention, keep other diagnostics**

```bash
repolife triage --repo "$REPO_ROOT" --since "$BASE_REF" --format json
```

Use the task's or CI event's actual base; a branch named `main` is not assumed. Ensure that the selected Git objects are present in shallow checkouts. The result orders attention using recent commit count and change size. Import reach, ownership and fix history add context. Ruff, ESLint, type checkers and tests keep their own diagnostics and results; no combined risk score is calculated.

Observed maintainers and declared `CODEOWNERS` are evidence to consider. They do not authorize messaging or assigning someone. The surrounding project and host decide review ownership and escalation.

**After an edit: portable structural report**

```bash
repolife check --repo "$REPO_ROOT" --since "$BASE_REF" \
  --format sarif --fail-on never --out "$REPORT_PATH"
```

`REPORT_PATH` is an explicit artifact path supplied by the caller. The report can be saved with the task's existing build/test artifacts or opened in a SARIF-aware viewer. Preserve the exit code before consuming it: 0 is a completed advisory query, 1 is a completed check blocked by an explicitly selected gate, and 2 from a handled analysis failure provides no result. A pre-existing output file is not automatically erased after a failed query, so its existence alone does not prove the latest check succeeded.

For a project that has deliberately enabled a `block` gate, this POSIX shell pattern preserves the report and gate outcome separately. Run the code as a script; `exit` returns its status to the parent workflow:

```sh
if structural_report=$(repolife check --repo "$REPO_ROOT" --since "$BASE_REF" \
    --format sarif --fail-on block); then
  check_status=0
else
  check_status=$?
fi

case "$check_status" in
  0|1) : ;;
  *) printf 'Structural check unavailable; do not consume an old report\n' >&2
     exit "$check_status" ;;
esac

if ! printf '%s\n' "$structural_report" | python3 -c '
import json, sys
try:
    report = json.load(sys.stdin)
    run = report["runs"][0]
    valid = (report["version"] == "2.1.0" and len(report["runs"]) == 1
             and run["tool"]["driver"]["name"] == "repolife"
             and run["properties"]["repolife/check"]["kind"] == "change-check"
             and isinstance(run["results"], list))
except (ValueError, KeyError, TypeError, IndexError):
    valid = False
sys.exit(0 if valid else 2)
'; then
  printf 'Structural check unavailable: no valid report from this run\n' >&2
  exit 2
fi

printf '%s\n' "$structural_report" > "$REPORT_PATH" || exit 2
printf 'Structural report available: %s\n' "$REPORT_PATH"

# The host can now preserve REPORT_PATH using its existing artifact mechanism.
# Ordinary tests and build checks remain separate jobs or steps.
exit "$check_status"
```

This captures the current process's output and checks its identity before replacing an older artifact. An exit-1 crash without a readable report is unavailable, not a completed gate. This small identity check is not full SARIF schema validation; consumers with stricter requirements can additionally validate the artifact.

Choose JSON instead when the consumer needs the complete structured orphan/cycle/dependency tables. All output formats use the same comparison and findings; changing format does not change the gate policy.

**SARIF consumer boundaries**

The export records file-level evidence without invented line numbers. It keeps grouped findings grouped, adds related locations where available, and retains locationless repository-level observations. Resolved or purely descriptive observations are informational, not new failures. A viewer's filters may show only problem results; the original finding remains in its properties.

Reports include the selected local project URI and metadata, which may disclose local paths and observed maintainer names. They do not embed source contents or environment variables. Review artifacts using the destination's existing sharing policy.

[GitHub code scanning](https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support) accepts a subset of SARIF and requires a location to display an alert; PR annotations have additional diff and line requirements. A schema-valid export does not establish upload acceptance, complete inline coverage or stable hosted alert matching. These host interactions have not been tested in this project iteration.

Keep persistent alert scope consistent if separately integrating an uploader. A change-only comparison against one base is not a full-repository scan; a narrower comparison can omit an earlier finding without proving it was resolved. Start with artifacts, verify category/base behavior in the chosen consumer, and enable uploads explicitly. repolife does not change CI configuration, acquire credentials or upload on its own.

**Reusing evidence in an agent task**

Start with the smallest relevant query: path edit to `impact`, review to `triage`, completed change to `check`, disputed claim to `why`, broad discovery to `scan`/`graph`. Avoid requiring every task to run all commands. Refresh after edits or base changes: the full commit IDs identify history, not an immutable snapshot of uncommitted files.

If the available CLI or module cannot run, report the capability as unavailable and follow the host's policy. Do not silently install a dependency, substitute an empty report or make the task wait unless project policy requires it. Use the optional [reversible integration](design/reversible-integration.md) to register task instructions when desired; it supplies neither shell permissions nor repository access by itself.
