# Tessri workspace experience

Design updated 2026-11-01. A focused, offline repository viewer, trialing the **Tessri** identity after
[official name checks](tessri-name-check.json). Package, command, configuration and integration identifiers
remain `repolife`. The author's priorities are better interaction and a simpler overall product.

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
| Primary navigation | Four entries: Overview, System map, Impact, Maintenance. One section is visible with scripts; every section remains in the generated HTML. |
| Secondary views | A native More views disclosure contains Directories, Change volume, Maintainers, Hotspots, Cleanup and Analysis notes. All original section IDs remain. |
| Start with a question | Three text links on the overview lead to structure, impact and maintenance evidence. They add no launcher cards. Metrics use unframed rows. |
| Quick navigation | Cmd/Ctrl+K searches view names and the analyzed file/directory index in this snapshot. Arrow keys select; Enter opens; Escape closes and returns focus. At most 60 matches are displayed, with an explicit count. |
| Choose a path | Opens the impact view with the selected path. The relationship policy and hop limit stay selected. |
| Compare evidence | All relationships is the compatible default. Import-based relationships follows `import` and `package` evidence. The broad view reports the narrower totals at the same hop limit. Inferred and unknown references can be expanded. |
| Return to context | Section fragments and browser Back/Forward switch views. An impact fragment carries the path, relationship policy and hop limit; reloading restores them. Typing replaces the current entry rather than adding history per keystroke. Table filters remain in document memory. Plain legacy `#impact` retains an existing in-page query; it does not carry a query on its own. |
| Scope | Repository name and history HEAD are visible. A date is shown on larger layouts. Analysis notes disclose the full repository path, capture time, history reference and that code was read from current files. “Local snapshot” describes a generated file, without suggesting a running analysis, live agent or clean worktree. |
| Offline and degraded use | No network assets, libraries, font downloads or service are required. Without scripts, all sections remain readable. Printing exposes all sections. Without an explorer payload, quick navigation still finds views and explicitly says the file index is unavailable. |

Only analyzed code paths are indexed. The existing 20,000-file explorer limit remains; the CLI still handles
queries when the report omits its embedded graph. Current selection and results are kept in document memory,
not synchronized across tools. The impact query is also represented in the fragment. The theme uses the existing local preference.

## Visual direction

Use a quiet developer workbench: a stable rail, a compact context header, neutral surfaces, and purple for
identity, selection and navigation. The existing four status hues and their text labels remain. Purple does
not carry a new risk score. The connected-tile T mark suggests separate pieces forming a coherent whole.

The current wordmark is **tessri.**, with the working promise **Keep code understandable.** It is a visual
trial in the actual report. Brand color is reserved for identity and selection; navigation uses text without
decorative icons. The rail becomes a compact primary row on small screens, with secondary links under the
same disclosure. Reduced-motion preferences remove the view transition. Quick navigation uses a native modal
dialog, a labeled combobox and listbox, and restores focus on dismissal.

## Simplicity boundary

Keep one working surface for the selected question. Put evidence qualifications next to results and details
behind native disclosures. Avoid extra scorecards, onboarding steps, agent chat, copy-link buttons or live
sync indicators. Link restoration lets a normal browser URL carry context
without adding another action to the interface.

Naming rationale, availability limits and future migration requirements live in the [naming study](brand-naming.md).

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

Joint acceptance for the simplified viewer: Python 3.11 and 3.12 each passed all **371 tests**. Claude Code
implemented the URL state in an isolated checkout; Codex reviewed and integrated that JS with the simplified
HTML/CSS, then ran both suites on the combined source. Browser checks confirmed initial-load and refresh
restoration, Back/Forward after multiple input edits, file selection from quick navigation, automatic opening
of secondary navigation, the skip link and a nested cycle link. An analyzed fixture verified spaces, `&`, `#`,
`?`, Unicode and a seven-step limit not initially present in the select. Malformed parameters produced a normal
lookup error and safe defaults, with no console error. A long repository name caused no document overflow at
390px. Light and dark themes were visually inspected at the default preview size.
