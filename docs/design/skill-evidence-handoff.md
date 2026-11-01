# Carry impact evidence into existing agent workflows

2026-11-01. Follow-up to [impact provenance](impact-provenance.md). This iteration updates the instructions shipped to existing agent surfaces; it adds no command, installation target, runtime dependency or analysis rule.

**Problem and decision**

The installed skill still described impact relationships as static imports, told the agent to run returned test paths, and omitted the new relationship policy. The shared `AGENTS.md` block also prescribed a full scan before refactoring. Those instructions would conceal the evidence distinction that the reviewer experiment exposed.

Keep the existing single-file skill and shared instruction block. `templates.SKILL` remains the installation source, with the bundled `skills/repolife/SKILL.md` synchronized byte-for-byte. No supporting-resource hierarchy or extra discovery surface is needed for this correction.

- Choose queries by the task: impact for a path change, triage for review attention, advisory check for structural effects, and scan/graph for orientation or cleanup. A routine edit does not require a full scan.
- Keep default broad impact evidence visible. Its `edges` block explains the policy, hop limit, inferred-reference examples and import-based comparison. Use `--edges imports` when that view answers the review question; it retains Python parent packages and excludes string, dynamic and unknown evidence encountered by the walk.
- State that syntax is evidence, not execution. Document the Python literal `import_module` versus JS literal `import()` distinction, capped frontier examples and the separate legacy graph rules. Heuristic cycle cuts are inspection candidates, not authored architecture decisions.
- Treat returned test paths as candidates for the project's runner. Preserve required checks, do not infer execution from paths, and do not treat an empty, narrowed or capped list as a complete test plan. Maintenance history informs the existing review process rather than assigning reviewers.
- Select the intended repository root and check report metadata before combining saved results. HEAD, the history revision and the comparison base can differ; unavailable or skipped analysis is not an empty success.
- If an older CLI lacks the new flag or fields, state the limitation and retain the available broad facts. A routine query does not authorize installation, downloads, workflow changes or a claim of import-only evidence.

These are instructions for consuming existing data. They do not force an additional query for every task, introduce a gate, grant execution permissions or automatically contact maintainers. The surrounding project still supplies its comparison base, runner and review policy.

**Upgrade behavior**

Updating the package does not rewrite installed files. Receipt-managed installations report `installed-outdated` when their unchanged installed content differs from the current template. The caller can inspect `integration update --dry-run` and explicitly run `integration update`; subset updates continue to work. User-modified managed content remains a conflict, including when another profile could otherwise be updated. Text outside the owned block stays byte-preserved.

Legacy `init` installations without a receipt remain unmanaged and are not adopted or rewritten by `integration update`. Fresh installations use the new instructions. No integration was installed into the user's actual projects for this acceptance. File status does not prove that an already running host has loaded the new instructions.

**Acceptance**

The independent upgrade collector uses the public CLI from clean commit `f8d4219c3fe5a574c9560aa247a84a5cf7e76297` to create old installations, then the current implementation to inspect, preview, update and remove them. It does not fabricate an old receipt or patch the installer.

Thirteen scenario groups cover all three profiles; read-only outdated status; a write-free preview; a Codex-only update; complete update with CRLF/Unicode, permission and unrelated-file preservation; one owned block; repeated no-op update; removal after upgrade; edited-skill and edited-block conflicts; unmanaged legacy `init`; fresh non-Git installation; and upgrading an old receipt from a standalone zipapp. The projects live under temporary directories, including paths containing spaces.

Existing installation and mounting regressions also pass on Python 3.12: 49 tests in `test_integration.py` and 27 in `test_repolife.py`. The skill-creator validator accepts the bundled skill. These checks validate format, distribution consistency and upgrade mechanics. They do not demonstrate live host discovery, an agent's choice of query, or reduced human review time. No new tests merely match the revised wording.

Temporary reproducibility records are in `/private/tmp/repolife-skill-acceptance/`, with the collector at `/private/tmp/repolife-skill-upgrade-acceptance.py`. Source hashes confirm that only `templates.py` changed in the Python package during this iteration; configuration and GitHub workflow template values remain identical. Analysis, lifecycle behavior and the previous iteration's accepted results remain unchanged.
