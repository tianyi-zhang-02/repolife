# Review brief: repolife tooling integration

Curated prototype, 2026-11-01. Observed facts come from [captured CLI reports and execution logs](review-brief-f8d4219.evidence.json). Review questions below are authored guidance. This example does not measure human review time.

**Scope and change**

Compare base `7e90477bcd83e4de470528a2e3869d61e89b6c59` with HEAD `f8d4219c3fe5a574c9560aa247a84a5cf7e76297` in a clean isolated checkout. No uncommitted product-direction documents are included. Query collection and the selected test execution left its files and Git status unchanged.

The commit describes three intentions: structured explanations/shared metadata, reversible project integration, and SARIF export. It changes 25 files: 16 code/test files with 2,266 added/deleted lines, plus 9 other files with 878 changed lines. Seven code/test files are new. These are change-volume counts, not quality scores.

**Where to focus**

The first three entries in the existing triage order are:

| Rank | File | Commits in activity window, before base | Lines changed |
| --- | --- | ---: | ---: |
| 1 | `repolife/cli.py` | 7 | 50 |
| 2 | `repolife/templates.py` | 6 | 39 |
| 3 | `repolife/report.py` | 5 | 3 |

Thirteen further code/test entries remain in the evidence. Activity then change size determines this order. The new 653-line `integration.py` is rank 10 because it has no pre-base history; that does not make its write behavior low priority.

Authored review questions:

| Mechanism | What to inspect | Evidence to open |
| --- | --- | --- |
| Protect user content | Trace receipt validation, preflight, lock/recheck and rollback. Compare unchanged legacy markers; keep crash recovery, real concurrent writers and Windows as separate validation tasks. | [integration.py](../../repolife/integration.py), [mount.py](../../repolife/mount.py), [contract](../design/reversible-integration.md), [regressions](../../tests/test_integration.py). |
| Preserve query meanings | Distinguish HEAD/history/base and legacy fields. Analysis now attempts history even with an empty inventory; docs-only `check` uses `available: false, reason: not-requested` for skipped history. | [analyze.py](../../repolife/analyze.py), [meta.py](../../repolife/meta.py), [since.py](../../repolife/since.py), [explain.py](../../repolife/explain.py). |
| Export usable evidence | Do grouping, file-level locations and informational observations survive rendering? Which consumers accept locationless results? | [sarifview.py](../../repolife/sarifview.py), [SARIF tests](../../tests/test_sarif.py), consumer follow-up below. |

The commit's 2,080-file text-equivalence claim is historical; current unit tests do not recreate the old renderer. Reverification requires a baseline comparison.

**Consequences and limits**

`check` reports **0 block, 0 warn, 0 info findings** for this comparison. It completed structural analysis and found no introduced condition among its supported checks. Compatibility and recovery questions above still need review.

| Target | Raw direct production count | Raw all-hop count | Audit: explicit-import-only count | Test candidates |
| --- | ---: | ---: | ---: | ---: |
| `cli.py` | 1 | 17 | 1 | 12 |
| `integration.py` | 1 | 18 | 2 | 12 |
| `meta.py` | 5 | 17 | 10 | 12 |

The audit found an inferred edge from the analyzer's `"__main__.py"` path string to the package entry point. `impact` traverses inferred edges too; the explicit-import view excludes them. Raw all-hop counts above are therefore **not confirmed import dependents** and must not set review scope. Audit counts are a separate development diagnosis, recorded in the evidence, not a changed ranking or runtime guarantee.

Path queries use HEAD history; triage/check use history through the base. Their maintenance fields have different scopes. Triage identifies no eligible alternative reviewer from observed history; this does not establish that nobody else can review.

**Validation**

Global triage finds **12 candidate tests but lists 8**. Target-specific impact reports list all 12 candidates. Candidates indicate relationships, not test execution or complete coverage.

This experiment actually ran:

```bash
python3.12 -W error::ResourceWarning -m unittest discover -s tests -p test_sarif.py
```

All **15 selected tests passed**, exit 0, at the exact HEAD above in the clean checkout. The full suite, lifecycle tests, build and hosted upload were **not executed in this experiment**. Historical suite results are not substituted for current execution evidence.

**Remaining decisions**

- Review the ownership/rollback contract and metadata compatibility across callers.
- Resolve inferred-edge provenance before using broad impact counts to direct attention.
- Claude Code separately reported that GitHub rejected a SARIF export containing a locationless result. That host experiment is not rerun or independently verified by this brief; retain it as a reported compatibility defect requiring source evidence and a deliberate fix. A passing local test is not hosted acceptance.
- Architectural intent, external consumers and actual review assignment need project context; the static graph cannot establish them.

Collection: six CLI calls, 2.59 s; selected tests, 2.44 s. Setup, diagnosis and authoring are excluded. No reviewer-time benefit is measured. Reproduce via the evidence manifest and read source links at the recorded HEAD.
