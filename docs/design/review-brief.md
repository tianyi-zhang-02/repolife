# Review brief: first product experiment

2026-11-01. This follows the author's [product direction](product-direction.md). Codex owns the brief design, sample and evidence audit; Claude Code independently reviews the selected change and checks the sample. This iteration does not introduce a command, API schema or new analysis rule.

The deliverable is a concise reading aid for a real review: what changed, what it reaches, where attention is useful, which validation actually ran and what is unresolved. The first sample uses repolife's own `f8d4219` commit against its parent, in a clean isolated checkout. It is a curated prototype using existing queries, not proof of reduced human review time.

**Minimum content**

| Section | Required content | Evidence boundary |
| --- | --- | --- |
| Scope | Explicit root, full base and HEAD, dirty/clean state, capture time | A commit ID does not identify uncommitted contents. The prototype uses a clean checkout and checks its state before and after collection. |
| Change | Counts, authored purpose and feature boundaries | Attribute purpose to the commit/author or project decision; do not infer architectural intent from file names. |
| Attention | Existing triage order with reasons, plus clearly labeled authored review questions | Keep tool ranking distinct from a person's review priorities. New files cannot be dismissed because they have no prior activity. |
| Consequences | Introduced structural findings, direct/transitive relationships and missing analysis | Zero findings are a bounded observation. Static imports do not establish runtime behavior or external compatibility. |
| Validation | Candidate tests separately from executed checks, with scope/state, argv and exit status for executions | Neither related paths nor a historical passing suite establishes a current result. |
| Follow-up | Concrete unresolved questions, uncertainty and any separately reported defects | A suggested reviewer is not an assignment; a recorded concern is not automatically accepted policy. |

Aim for at most 800 words in the primary brief. Keep detailed evidence outside that reading budget and link it. Show counts whenever lists are shortened. All existing findings remain available in the linked evidence; selecting a few reading topics does not silently filter the analysis result.

**Evidence collection**

Use the current public CLI: `triage` and advisory `check` against the same explicit base; selected `impact`/`why` queries only where they answer a review question. Capture result availability, stderr, elapsed time and comparison identity. Argument arrays keep repository paths as data. Save artifacts outside the selected repository and check that collection did not change its files.

Path queries normally use current history, while change queries use history up to the base. Both may describe the same HEAD correctly. Preserve that distinction rather than combining ownership/activity fields as if they had an identical historical scope. A report must not mix different checkouts or stale worktree states merely because the paths match.

Run only validation deliberately selected for this experiment, in the isolated checkout. Preserve raw logs and record what was not executed. The collection adapter is temporary development tooling; it is not a supported Python embedding API or installed workflow.

**First sample and observed gaps**

- [Curated brief](../examples/review-brief-f8d4219.md), with [full captured query evidence](../examples/review-brief-f8d4219.evidence.json).
- The triage order puts a new lifecycle implementation at rank 10 because it has no activity before the base. Its write/ownership behavior still deserves explicit human review. No alternative composite rank is introduced.
- Global test candidates are bounded: the sample has 12 candidates with 8 shown. A target-specific query exposes the selected SARIF test module, and an actual execution is recorded separately.
- Structural check finds no new orphan, cycle, dangling import or inactive-owner warning in this comparison. That does not answer compatibility, concurrent-write recovery or external-consumer questions.
- Independent review exposed a provenance problem: `impact` traverses inferred edges as well as explicit imports. On this self-analysis, the Python analyzer's `"__main__.py"` path string creates an inferred path back to the CLI. Raw all-hop production counts of 17/18/17 become 1/2/10 when traversing explicit-import edges only. Both views and their scope are retained in the sample; raw output must not be presented as confirmed import dependents. This diagnosis does not alter the algorithm or create a new ranking. A later minimal fixture isolated the path string as the trigger; the bare `"__main__"` guard literal alone creates no edge.

**Evaluation and next decision**

Check factual agreement with the raw query reports, correct scope identity, visible truncation, separation of observed facts and authored questions, and separation of candidates and executions. Independent agent review can find reporting errors; it is not a substitute for observing a human reviewer.

For a subsequent task trial, compare the ordinary diff/query workflow with the brief using the same review questions. Record time spent gathering context, files reopened, requests for clarification, important issues missed, added latency and artifact size. Test a JS/TS change as well as Python before deciding whether the composition warrants a first-class command. Keep authored architecture decisions and unresolved maintenance work connected to the team's existing records.

Promote a recurring composition only when the trial shows a useful reviewer outcome and a stable input/output need. The current prototype is complete when its evidence and sample are independently checked; product benefit remains unmeasured until that trial.

**Execution record**

The first collection used six public CLI calls at the exact recorded HEAD and base, with bytecode writes disabled and artifacts outside the selected checkout. All six completed successfully; the checkout's content hashes and Git status were unchanged after collection and validation. A separate, deliberately selected `test_sarif.py` execution passed all 15 tests at that HEAD. No full-suite or hosted-consumer result is inferred from it.

The portable evidence file was checked against every original query object and test log. Only the declared temporary root/interpreter paths are normalized. Scope identity, result availability, shortened-list counts and local evidence links pass the audit. The primary brief remains below its 800-word budget. Collection timings are a single local run and exclude checkout setup, diagnosis and manual authoring.

Claude Code independently reviewed the change, reran the same six queries on the clean checkout and checked the commit's file/line counts against Git. The numbers, scope isolation and executed-test account agreed. That review identified the inferred-edge problem described above. Codex separately reproduced its path and the explicit-edge counts, added the diagnostic evidence and corrected the sample's interpretation. The review also prompted explicit context on unchanged legacy markers, history-read behavior, skipped-history reasons and the historical text-compatibility claim.

The evidence-backed prototype and fact-check are complete. Human reviewer-time benefit, a new supported command and a cross-language task outcome remain unmeasured. Inferred-edge provenance and separately reported hosted-SARIF compatibility are recorded follow-ups; this iteration changes no production behavior.

A subsequent implementation iteration delivered [impact evidence provenance](impact-provenance.md), addressing the ambiguous relationship source found by this experiment. The historical sample and its captured query evidence continue to describe the original commit and are not regenerated with a newer engine.
