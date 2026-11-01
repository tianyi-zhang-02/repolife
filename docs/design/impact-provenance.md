# Impact evidence: separate imports from inferred references

2026-11-01. Follow-up to the [review brief experiment](review-brief.md). Codex owns the design and independent acceptance; Claude Code owns the implementation, regression tests and user documentation. Both agents reviewed the analyzer/plugin contract and agreed the bounded implementation below.

**Problem and intended outcome**

The first real-commit brief exposed a misleading distinction: the module graph removes Python edges marked `indirect`, while `impact` traverses them. That bucket contains both Python parent-package execution and speculative string references. In repolife's own source, an ordinary `"__main__.py"` path string creates a route from the analyzer back to the CLI and expands a small change's apparent reach. The text renderer currently calls all of this static imports. A subsequent minimal fixture isolated the path string as the trigger; the usual `if __name__ == "__main__"` guard alone creates no such edge. This corrects the first diagnostic's attribution to the bare name, without changing its observed edge or counts.

A reviewer needs to choose a narrower source of relationships and see what was excluded. An agent or CI adapter needs that choice in the result itself so that saved JSON remains interpretable outside the chat that produced it. Neither view establishes runtime execution or proves that an excluded file is unaffected.

**Constraints agreed before implementation**

- Preserve the existing default reachability result. The narrower view must be an explicit choice; existing callers must not silently lose candidate tests or affected modules.
- Distinguish recognized imports, Python parent packages implied by those imports, and inferred references. Do not discard the parent `__init__` relationship as a false positive: importing `a.b.c` can execute those packages.
- Check both built-in analyzers. JavaScript/TypeScript currently combines recognized specifiers, path strings, computed imports and glob/context expansion; Python's existing `indirect` flag alone cannot classify both languages correctly.
- If the same source/target pair has a recognized import and a speculative reference, retain it in the import view. One weaker observation does not cancel stronger evidence.
- State the selected relationship policy in text and JSON. A direct relationship means one selected edge, not necessarily an explicit import statement.
- Keep candidate tests separate from actual executions. Narrower candidate lists do not justify skipping all other checks.
- Preserve third-party analyzer compatibility and disclose unclassified evidence. An old plugin must keep working; unknown provenance must not become a promise of verified imports.
- Keep the change bounded. Do not change triage ordering, gate policy, installation behavior or the historical review sample's captured evidence.

**Independent acceptance prepared before code changes**

Codex captured the old implementation at `f8d4219c3fe5a574c9560aa247a84a5cf7e76297` on two small, independently authored fixtures. Fifteen impact queries cover a file, a directory, a package initializer and all/one/two-hop traversal; two file-graph queries capture the surrounding behavior. Every query runs through the public CLI and leaves fixture content unchanged.

The Python fixture combines a real import, a dotted string, a transitive importer of that string holder, a literal `import_module` call, a source with both import and string evidence, and separate tests through the real and inferred paths. The TypeScript fixture combines a literal import, path string, transitive importer, literal `import()`, computed `import()`, glob expansion, overlapping import/string evidence, and separate tests. These are language behavior fixtures, not a measured human review task or a real JS/TS project trial.

Acceptance must establish:

1. Default impact counts, distances, ordering, ownership and existing fields match the captured baseline; only documented additive metadata and corrected prose may differ.
2. Narrow traversal excludes the string-only route and its transitive tests while retaining recognized imports and supported parent-package behavior.
3. Hop limits apply to the selected edge set. A cycle terminates and directory targets exclude their own seed files.
4. Overlapping observations remain one relationship with the strongest applicable classification.
5. Missing plugin provenance is visible and cannot silently enter a view described as imports only.
6. Text, JSON, help and invalid-option behavior agree. The existing file/module graph, structural checks and default HTML explorer remain compatible unless a separate behavior change is explicitly documented and tested.
7. On the frozen real-commit checkout, the narrower view removes the analyzer's string-only route. Compare the same target state with old and new engines; do not compare counts from different source trees as if only the policy changed.

**Implementation decision**

Keep provenance beside the existing `edges` and `indirect` data. Changing the old `indirect` flag would also change module graphs, structural comparisons and the HTML explorer, especially for JS/TS; those changes need their own decision and are outside this iteration. Default reachability remains unchanged.

The additive analyzer result maps each source/target pair to one kind, choosing the strongest available evidence in this order:

| Kind | Meaning in this version | Included by `imports` |
| --- | --- | --- |
| `import` | A Python import statement names the target; for JS/TS, an existing recognized literal specifier/dependency syntax resolves to it | Yes |
| `package` | A Python import statement implies execution of a parent package initializer | Yes |
| `dynamic` | A supported computed import, glob or context pattern expands to the target | No |
| `string` | An ordinary dotted-name or path string resolves to the target | No |
| `unknown` | The analyzer supplied an edge without recognized provenance | No |

These names describe analysis evidence. They do not establish that a statement executes or that a file will change behavior. JS/TS literal dependency syntax includes `import`, `export from`, `require`, literal `import()`, and the scanner's supported `new URL`/reference-path forms. Python literal `import_module("pkg.mod")` remains a `string` observation because the current Python analyzer does not classify the surrounding call. This language difference is explicit; no new dynamic-call parser is added.

The public CLI gains `--edges all|imports`, with `all` as the default. `imports` keeps `import` and `package` edges and excludes the other three kinds. A package initializer therefore remains a valid impact target even when the source statement names only its child. Third-party analyzers keep working without supplying the new field: their unclassified edges remain in `all` and are excluded from `imports`. Preserve the old positional constructor parameters when extending the analyzer dataclass.

The reverse walk and the forward `depends_on` list have different existing scopes. `depends_on` is a one-step named-dependency summary using the legacy module-graph selection; Python parent initializers are absent there. Preserve that field under `all`. Under `imports`, additionally filter its legacy candidates by the selected provenance so a JS string-only reference cannot appear as an import dependency. This does not turn the field into a forward traversal or add parent packages to its historical scope. The older JS/TS module graph can still contain inferred edges; correcting that separate graph remains deferred.

The new top-level `edges` block records the policy, hop limit and included kinds. It counts followed and excluded edges by kind and provides a bounded, counted list of non-import references with source, target and kind. Unknown provenance also identifies the source analyzers. Under `all`, `imports_only` summarizes the code/test counts that the narrower policy would reach using the same seeds and hop limit. Existing result fields describe the selected policy; metadata is additive under schema version 1.

Counts refer to source/target pairs encountered while expanding the selected walk, once per pair. A node at the hop boundary is not expanded. A retained edge may lead to a node already visited; edge counts are not counts of unique affected files or discovery-tree edges. Excluded edges and unknown-origin counts describe the visited frontier, not every excluded or unknown edge in the repository. Their presence does not recursively expand an excluded route. Reference lists show their total and truncation explicitly.

Text must state the policy and define direct relationships as one selected edge away. Replace the misleading import-only disclaimer and the claim that no dependencies exist with statements bounded by the selected view and hop limit. A zero in `imports` can coexist with excluded string or unknown evidence. Candidate tests remain suggestions, never execution records.

The all-mode summary makes the reviewer distinction immediately useful: a broad candidate set can be compared with the import-based set without treating inferred expansion as confirmed dependency. It adds one bounded graph traversal over an already computed analysis, not a second repository scan. No `why` option, explorer toggle, new triage rank, PathIndex heuristic change or review-brief command is added.

**Independent acceptance results**

Codex ran 54 independent acceptance groups against the working implementation on 2026-11-01: 44 fixture/baseline/real-target groups, five legacy-plugin groups and five CLI groups. The fixture set includes both built-in analyzers. The old implementation's 15 impact cases and two file graphs agree with the new default after excluding capture timestamps and normalizing temporary root paths. The three real-target default comparisons also preserve the old fields, including history/ownership. Reference truncation reports its complete count and limit; cycles terminate; stronger import evidence wins; the import view excludes string-only forward dependencies; fixture contents remain unchanged.

For the real-target comparison, both engines analyzed the same clean `f8d4219c3fe5a574c9560aa247a84a5cf7e76297` checkout. The new engine came from the uncommitted implementation in this iteration; its Python source hashes accompany the local acceptance record. These are new-engine queries on old target content, not a replacement for the historical brief's original query objects.

| Target at the frozen commit | Default code files | Import-policy code files | Default candidate tests | Import-policy candidate tests |
| --- | ---: | ---: | ---: | ---: |
| `repolife/cli.py` | 17 | 1 | 12 | 11 |
| `repolife/integration.py` | 18 | 2 | 12 | 11 |
| `repolife/meta.py` | 17 | 10 | 12 | 12 |

The narrower walk exposes and excludes the `python.py` → `__main__.py` string edge at its visited frontier. Broad code counts shrink, but many tests still have recognized import paths. The outcome supports a more precise account of relationship evidence; it does not measure reviewer time saved or justify dropping the remaining candidate tests.

The legacy-plugin checks use the old positional `LanguageResult` constructor without provenance: default traversal preserves its code/test relations, the import view excludes them, and both views identify the unknown source analyzer. The CLI checks cover help, an invalid policy returning exit 2 without a report, paths containing spaces, JSON written through `--out` with clean stdout, and text disclosing an excluded reference even when the selected result is empty. The normal `--out` acknowledgement on stderr remains compatible.

Local reproducibility records are in `/private/tmp/repolife-impact-acceptance/`: `baseline.json`, `acceptance.json`, `plugin-acceptance.json`, `cli-acceptance.json` and `final-source-audit.json`. Their collectors are the sibling `/private/tmp/repolife-impact-{baseline,acceptance,plugin-acceptance,cli-acceptance}.py` scripts. These are temporary development evidence, not installed commands or a supported embedding API. Nineteen permanent regressions now live in `tests/test_provenance.py`.

The final text displays `at most N steps` or `any number of steps`. Codex reran the five CLI groups after that text-only revision, including explicit finite/unlimited assertions. A source-hash comparison confirms that only `graphview.py` changed after the 44-group JSON acceptance; the traversal and analyzer code remained identical.

Claude Code ran the complete suite on Python 3.11.15 and 3.12.2: **364 tests pass on each**. Codex read both logs, checked the interpreter headers and verified that the completed logs postdate the final Python source/test edits. The implementation note and exact log paths are recorded in `/private/tmp/repolife-impact-implementation.md`; the log names are `suite-3.11.log` and `suite-3.12.log` in that note's scratchpad directory. Both agents also compared the frozen default impact/file-graph results; whitespace checks pass. Production code, regression tests and documentation remain local and uncommitted.

This bounded implementation and its acceptance are complete. Human-review time saved, a real JS/TS task outcome, live plugin-host behavior and external-consumer results remain unmeasured. Installed skill instructions, `why` provenance labels, a narrower HTML explorer view and the older JS module-graph inconsistency are separate follow-ups; this change does not silently upgrade existing installations.

The subsequent [skill evidence handoff](skill-evidence-handoff.md) updates the shipped instructions and verifies explicit upgrades from an old receipt. It preserves the installation lifecycle and leaves live host adoption unmeasured.
