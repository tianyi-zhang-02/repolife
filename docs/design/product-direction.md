# Product direction: keep up with the code

Clarified by the project author on 2026-11-01. This document sets product priorities; existing capabilities and accepted test results remain described in their own contracts.

**Purpose**

Keep growing codebases understandable, reviewable and maintainable as AI increases the rate of change.

The author's concern is that code can accumulate faster than maintainers can understand the whole system, review changes and refine its design. repolife should help people allocate limited attention and keep a working understanding of an evolving system. Tool interoperability serves this purpose: the same repository evidence should be usable wherever people and agents already work.

A working positioning statement:

> repolife is an embeddable maintainability layer that helps people and agents understand a codebase, focus review and check how changes affect the system.

This is the product direction. The current implementation supplies static structure, Git-derived maintenance evidence, change triage and structural comparisons. Reduced reviewer effort and better long-term maintainability are outcomes to demonstrate through real tasks, not results established by passing format tests.

**The user experience to build toward**

| Moment | What a maintainer should be able to answer | Current foundation / next need |
| --- | --- | --- |
| Enter or return to a project | How does the system fit together, and where is my understanding incomplete? | `scan`, `graph`, `why`; distinguish observed links from architectural intent. |
| Prepare a change | What could this touch, and which context should I read? | `impact`, related tests and maintenance history; disclose static-analysis gaps. |
| Review a change | What needs my attention, why, and what can be checked mechanically? | `triage`, `check`, inspectable explanations; evaluate a concise review brief using existing evidence. |
| Finish a change | What structural effects remain, and what validation actually ran? | `check` plus the host's real test/build results; keep candidate tests separate from executed tests. |
| Revisit maintenance work | Which concerns were addressed, deliberately accepted or left for later? | Future explicit decision references and follow-up handling; existing scans alone do not provide this. |

These moments form a continuing loop: understand the system, focus the change, review its consequences, verify, and carry forward the relevant context. A new maintainer or agent should be able to re-enter that loop without reconstructing everything from old chat transcripts.

Architectural intent and accepted exceptions require authored or explicitly reviewed evidence. When useful, link existing ADRs, issues, tests and project instructions. Preserve the distinction between observed facts, inferred explanations and team decisions. Do not manufacture a rationale from an import graph or create a competing copy of a team's decision record.

**What “any system can interact” means here**

Start with people, coding agents, editors, CI and other analysis tools sharing evidence about an explicitly selected repository state. Each surface can request the relevant facts, trace a claim to its evidence and understand the analysis limits. The caller retains its workflow, execution permissions and policy.

The useful common unit is an evidence-backed answer: its scope and state, observations, limitations, and relevant next checks. Existing JSON and SARIF are ways to carry that answer. A skill, protocol adapter or viewer is valuable when it makes the answer easier to use at a real task moment. The current Python/JS/TS reachability scope remains explicit; a generic integration format does not add language-analysis capability.

**Priority for the next iteration**

Use a real reviewer task as the next product test. Assemble a small review brief from the existing queries before committing to a new command or service. It should make clear:

1. What changed and which base/worktree the evidence describes.
2. Which changed areas deserve attention first, with the existing ordering and reasons.
3. Which structural relationships and related tests matter for those areas.
4. Which introduced findings remain, what evidence is unavailable, and what needs a person or project policy.
5. Which checks actually ran, supplied by the host rather than inferred from test paths.

The first [review brief experiment](review-brief.md) now has a [real-commit sample](../examples/review-brief-f8d4219.md) and linked query evidence. It evaluates whether the composition can be accurate and traceable; human reviewer benefit still requires a task trial.

That experiment led to the first [impact provenance improvement](impact-provenance.md): relationship sources are visible, and a caller can compare the existing broad result with a view limited to recognized dependencies and Python parent packages. The default remains compatible. This is an evidence-quality improvement motivated by a review task; it does not establish time saved.

Inspect the source when needed; a brief should help a reviewer choose and understand their work. It does not establish that unread code is safe. Missing history or analysis must remain unavailable instead of producing reassuring empty sections.

Measure whether the brief reduces repeated context gathering, unnecessary reading and clarification while retaining important review findings. Test both Python and JS/TS projects and compare with the team's ordinary workflow. Record setup effort, added latency, context size and interruptions as part of the result. Change the product based on those observations rather than the number of supported adapters.

This priority follows the author's clarification. Viewer trials and repeated-query profiling remain useful supporting work when they answer questions raised by the reviewer task. Broader protocols, caching and persistent decision management should follow demonstrated needs and separately specified contracts.

**Feature filter**

Before expanding the product, identify the maintainer's task, the decision made easier, the evidence supplied, and how improvement will be observed. Prefer changes that reduce the work of understanding, reviewing or maintaining the system while fitting the existing workflow. Preserve explicit uncertainty, caller control and reversible installation.

Product success is a maintainer spending less effort reconstructing context and more of their limited time making informed changes and refining the system. The existing test suite verifies software behavior; task evaluation is needed to establish that benefit.
