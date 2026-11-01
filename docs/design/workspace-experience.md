# Workspace experience and brand exploration

Iteration dated 2026-11-01. The author asked to improve the interface and interaction, taking inspiration from
Kiro, and to reconsider the repolife name and design. This records the implemented HTML viewer iteration and
the naming options still under discussion. It does not rename the package, command or configuration files.

## A place to understand the system

The product purpose remains [keeping growing codebases understandable](product-direction.md). The viewer
should make it easy to enter with a question, inspect the relevant evidence, and return to a change with useful
context. The first screen offers three starting points: understand the system, explore a change, and find
maintenance work.

The public [Kiro documentation](https://kiro.dev/docs/) and its [spec workflow](https://kiro.dev/docs/specs/)
are references for stable navigation and a focused task space. The report uses its own navigation, wording and
line mark. No Kiro artwork or branding is included. The viewer does not introduce an editor, agent chat, spec
generator or additional required workflow.

## Implemented interaction

| Interaction | Behavior |
| --- | --- |
| Grouped navigation | Understand, Explore change, Maintain, and Report group the existing sections. One section is visible with scripts; every section remains in the generated HTML. |
| Start with a question | Three overview links open the corresponding views. Current evidence and metrics remain available below them. |
| Quick navigation | Cmd/Ctrl+K searches view names and the analyzed file/directory index in this snapshot. Arrow keys select; Enter opens; Escape closes and returns focus. At most 60 matches are displayed, with an explicit count. |
| Choose a path | Opens the impact view with the selected path. The relationship policy and hop limit stay selected. |
| Compare evidence | All relationships is the compatible default. Import-based relationships follows `import` and `package` evidence. The broad view reports the narrower totals at the same hop limit. Inferred and unknown references can be expanded. |
| Return to context | Section fragments and browser Back/Forward switch views. Queries and table filters survive switching views within the loaded document. Reloading resets queries; file queries are not shareable URLs in this iteration. |
| Scope | Repository name and history HEAD are visible. A date is shown on larger layouts. Analysis notes disclose the full repository path, capture time, history reference and that code was read from current files. “Local snapshot” describes a generated file, without suggesting a running analysis, live agent or clean worktree. |
| Offline and degraded use | No network assets, libraries, font downloads or service are required. Without scripts, all sections remain readable. Printing exposes all sections. Without an explorer payload, quick navigation still finds views and explicitly says the file index is unavailable. |

Only analyzed code paths are indexed. The existing 20,000-file explorer limit remains; the CLI still handles
queries when the report omits its embedded graph. Current selection and results are kept in document memory,
not synchronized across tools. The theme uses the existing local preference.

## Visual direction

Use a quiet developer workbench: a stable rail, a compact context header, neutral surfaces, and purple for
identity, selection and navigation. The existing four status hues and their text labels remain. Purple does
not carry a new risk score. The original line mark suggests a continuing thread joining parts of a system.

The current wordmark is **repolife.**, with the working promise **Keep code understandable.** It is a visual
trial in the actual report, not a finalized identity. The rail becomes a horizontally scrollable section list
on small screens. Reduced-motion preferences remove the view transition. Quick navigation uses a native modal
dialog, a labeled combobox and listbox, and restores focus on dismissal.

## Naming directions

The author subsequently selected **explore a shorter, more distinctive new brand**. This supersedes the
initial recommendation below to prioritize the Repolife identity. Repolife remains the implementation name
during exploration; RepoKind is no longer the leading alternative. See the [new naming study](brand-naming.md).

Names should be easy to say and type, fit a CLI and an embedded panel, and express lasting understanding or
care. Avoid promising runtime correctness, autonomous review approval, or support for languages the analyzers
do not cover. Compare names in ordinary sentences such as “open X,” “X found this relationship,” and “include
X evidence in the PR.”

| Direction | Meaning and strengths | Concern |
| --- | --- | --- |
| **Repolife** | The repository has a life after code generation. Already matches the package, command and maintenance purpose. The clearer promise gives the name a specific job. | Broad meaning, three spoken syllables, and search ambiguity. An unrelated developer identity also uses repolife; see the [Agent Board listing](https://glama.ai/mcp/servers/repolife/agent-board). |
| **RepoKind** | A shorter candidate centered on care for code and the people maintaining it. Works as a quiet, approachable tool identity. | “Kind” is ambiguous and does not directly explain system understanding. Initial search did not establish availability; package, repository, domain and trademark checks are still required before selection. |

The initial recommendation was to evaluate the improved Repolife identity in this real viewer while testing
RepoKind as a naming alternative. Keep compatibility-sensitive identifiers until the author selects a name
and a migration is designed. A branding decision should update the UI, README and positioning together;
changing every identifier now would make the experiment harder to reverse.

Other explored names were dropped from this shortlist because of visible uses: [RepoWeave](https://github.com/cwalv/repoweave),
[Repora](https://github.com/hackelia-micrantha/repora), and [Repolume](https://ai-resume-github-analyzer.vercel.app/privacy).
This is preliminary product naming research, not a determination of legal availability.

## Validation and next trial

The Node-executed browser core is compared with Python `impact` for both policies and hop limits. Fixtures cover
Python parent packages, JS/TS imports and inferred paths, cycles, old analyzer plugins with unknown provenance,
and reference lists longer than the eight-example display limit. The repository itself is also checked.

Manual browser checks cover view changes, file navigation, relationship selection, keyboard navigation,
empty search results, Escape focus restoration, theme changes, history navigation, and the script-free report.
Responsive layout checks inspect the 390px and 1440px breakpoints. Test results establish behavior and
consistency; they do not yet show that the interface saves reviewer time. The next product trial should ask
a maintainer to locate a module, investigate a changed file, and explain which relationships are inferred,
then record where they hesitated or lost context.
