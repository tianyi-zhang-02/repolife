# Reversible project integration

Second-stage design, 2026-10-31. Codex owns this design and independent acceptance; Claude Code owns implementation, regression tests, templates and README changes. Preserve the accepted first-stage working tree and leave changes uncommitted.

The goal is a project integration that can be previewed, updated and removed without overwriting user work. Installing repolife as a package and registering a workflow integration are separate operations. Ordinary analysis queries remain usable without either a receipt or a project configuration file.

**1. User flow and scope**

Use one lifecycle namespace rather than adding flags to every analysis command:

```bash
repolife integration install . --agent claude --dry-run
repolife integration install . --agent claude --agent codex
repolife integration status . --format json
repolife integration update . --dry-run
repolife integration remove . --agent claude --dry-run
repolife integration remove .
```

These commands are implemented in the local working tree; see [second-stage acceptance](second-stage-acceptance.md) for validation. Install requires at least one explicit, repeatable `--agent`. Update and remove select all recorded profiles by default, or a specified subset. Repeating install for a managed profile behaves like a guarded update, not a reset. Status reads the recorded installation without running repository analysis.

| Profile | Managed content | Support boundary |
| --- | --- | --- |
| `claude` | `.claude/skills/repolife/SKILL.md` | Project skill layout for local Claude Code. |
| `codex` | `.agents/skills/repolife/SKILL.md` | Repository skill layout for Codex. |
| `agents` | A marked repolife instruction block in `AGENTS.md` | For hosts that read this file; this profile does not claim every agent does. |

The skill profiles use the same semantic source. Default skill examples should print JSON to stdout rather than automatically create `.repolife/report.json` or a graph file; explicit `--out` remains available when a task needs an artifact. If neither the installed CLI nor an available Python module can run, report the capability as unavailable and follow host policy. Do not silently download a package to make a routine query work. This keeps the lifecycle independent of `.gitignore` edits.

This stage changes installation lifecycle, not the analysis algorithms or task policies. No automatic package installation, network call, global user-directory write, background daemon, hook, CI workflow, gate, configuration file or `.gitignore` edit occurs. Optional CI and broader host configuration remain separate future choices.

Installing files is not proof that an already running host discovered them. Output should say which project files were installed and direct the user to reload/restart the relevant host if needed. Actual host discovery and invocation must be recorded separately from filesystem-layout checks; do not advertise untested cloud or remote-session support.

**2. Ownership receipt**

Store one versioned receipt at the project root, `.repolife-integration.json`. Keep it outside the legacy `.repolife/` report directory, which `init` ignores, so the lifecycle state is visible and can travel with the integration when a team commits it. It records only fixed, allowlisted integration targets, selected profiles, generated-content hashes, exact owned marked spans, whether target files were newly created, and directories the installer created. Record a manifest version separately from the public result schema and include the generating tool version.

Do not add the receipt to `.gitignore` automatically. Teams may track or ignore it using their existing conventions. A receipt is constrained local/project state, not an authenticated proof against a malicious editor. Avoid absolute machine paths and do not copy unrelated user instructions into the receipt.

| Target at installation | Behavior |
| --- | --- |
| Missing target, safe parents | Plan a new owned target and record its hash after creation. |
| Existing target without a receipt | Preserve it and report an unmanaged conflict, even if its contents equal the current template. |
| Existing shared `AGENTS.md` without repolife markers | Append an owned marked span and preserve every existing byte. |
| Existing unrecorded repolife markers | Conflict; do not claim an installation created by legacy `init` or another tool. |
| Recorded target matching its last installed hash/span | Safe to update or remove the owned content. |
| Recorded target edited by the user | Report a conflict; leave content and receipt unchanged. |
| Recorded target missing | Status reports missing. Update may recreate it; removal may forget the missing owned target. |

No adopt or force-overwrite option is included in this stage. A legacy installation without a receipt stays usable but cannot be automatically uninstalled by the new lifecycle command. Existing `init` behavior and defaults remain compatible; do not add a receipt that retrospectively claims its targets.

**3. Shared instructions and byte preservation**

Use a pair of distinct repolife markers in `AGENTS.md`. Exactly one matching, correctly ordered pair is allowed for a managed block. Duplicate, incomplete, reversed or nested markers conflict before any write.

Record the exact inserted span, including separators the installer added. Update replaces that span only after validating its recorded hash, retaining any text before and after it. Remove deletes only the owned span. This permits independent edits elsewhere in the shared file without making the entire file immutable.

Round-trip acceptance covers existing files with no trailing newline, LF and CRLF line endings, Unicode text and new user content outside the span. Preserve the permission mode of a pre-existing shared file when replacing or restoring it. Do not use lossy decoding, newline normalization or whole-file trimming. If the span no longer matches exactly, stop and explain the conflict rather than guessing which text belongs to the user.

A newly created `AGENTS.md` can be removed only if deleting its owned span leaves no bytes. If the user has added anything else, keep the resulting file. Never delete a pre-existing shared file, even when its remaining content is empty.

**4. Planning and mutation**

Every mutating operation follows the same sequence:

1. Validate the requested profiles, receipt schema and every stored target against the fixed target allowlist.
2. Validate path containment and reject links before reading the relevant targets as bytes; then validate markers and ownership.
3. Build the complete operation plan, including receipt changes and directory creation/removal.
4. If any selected target conflicts, return the plan without changing any file.
5. For `--dry-run`, return the same validated plan without creating directories, lockfiles, temporary files or a receipt.
6. Before applying, recheck the observed target/receipt contents. A changed input becomes a conflict. Serialize mutating lifecycle operations per project with a fail-fast exclusive lock at `.repolife-integration.lock`; never overwrite a different process's lock. Dry-run and status create no lock. A stale lock is reported, not silently removed. A busy operation is a reported conflict, not permission to proceed without serialization.
7. Apply with atomic replacement of individual files and best-effort rollback of ordinary I/O failures. Write the receipt only when the corresponding file changes have succeeded.

This is preflight plus guarded writes, not a claim of a cross-file transactional filesystem. If rollback itself fails, report the paths that remain changed; never report success. Process termination or power loss is outside the first implementation's recovery guarantee. A future journal can strengthen recovery without changing ownership semantics.

Mutations reject symlinks in the target, receipt or any managed parent path, including dangling symlinks. Reject path traversal, unexpected target paths, unsupported receipt versions and malformed receipt data. A legitimate symlink used only to name the selected project root can be resolved once; descendants must stay inside that resolved root. Do not follow repository-local links while reading target contents, writing or deleting.

Only remove directories recorded as created by the installer, using nonrecursive removal when empty. User-created parents, unrelated files and nonempty directories remain. The project root is never a cleanup target. A transient root-level lock may be used; it is not a profile or persistent receipt entry.

**5. Status and result contract**

All lifecycle commands support text output by default and `--format json`. A successful JSON result has a stable operation kind, result schema version, selected profiles, proposed actions, conflicts and whether anything was applied. Plans use action names such as `create`, `update`, `remove` and `unchanged`; dry-run does not encode an alternate schema using different action verbs.

Status distinguishes installed-current, installed-outdated, user-modified, missing and unmanaged targets. A recorded target behind a link is reported as `symlink` without reading its contents; a symlinked receipt remains an error. A valid status query exits 0 even when it reports attention needed. Install/update/remove exit 0 on success or a conflict-free preview, 1 for a valid plan blocked by ownership/content conflicts, and 2 for invalid arguments, an invalid receipt or an I/O failure. Exit 1 retains a readable result; handled exit-2 failures diagnose the problem without emitting a success object.

For a subset removal, preserve other profiles and their receipt entries. Repeating removal for an already absent selected profile is a no-op, including when no receipt remains. For a complete removal, remove the receipt after all managed targets have been removed or confirmed absent. A removal of an edited target must not silently forget its ownership evidence. Without a receipt, status reports no managed installation and remove is an idempotent no-op; it must not infer ownership from a familiar filename or marker.

**6. Acceptance**

| Scenario | Required result |
| --- | --- |
| Existing project with source, instructions and ignore rules | Install touches only the selected integration targets and receipt. |
| Empty, new or non-Git project | Same lifecycle works; no Git history required. |
| Dry-run for each mutation | Same proposed actions, no filesystem changes. |
| Repeated installation | No duplicate blocks or gratuitous byte changes. |
| Foreign existing skill, even byte-identical | Conflict and zero writes. |
| User-edited managed skill or block | Update/remove conflict and zero writes. |
| User edits outside a managed block | Preserve edits through update/remove. |
| Multiple profiles and subset removal | Other profiles remain functional and recorded. |
| Missing managed target | Update can recreate; remove can clean its receipt entry. |
| Corrupt, unsupported or path-forged receipt | Error and zero writes outside or inside the project. |
| Symlinked target/parent/receipt | Refuse without modifying its referent. |
| One conflict in a multi-target plan | No other target is installed, updated or removed. |
| Ordinary I/O failure after an earlier write | Restore prior bytes when rollback is possible; report any incomplete rollback. |
| Two lifecycle mutations for one project | Serialize or fail one clearly; do not lose a profile's receipt entry. |
| Fresh install followed by complete remove | Original project bytes restored, including shared instructions and ignore rules. |
| Existing legacy `init` installation | Keep its files; no automatic adoption or deletion. |
| Standalone zipapp | Same installation lifecycle and no optional runtime dependency. |

Retain the first-stage 27 CLI scenarios and all existing regression tests. Independent acceptance uses temporary projects and does not install integrations into the user's actual repositories. Record what was tested, including host-layout versus live-discovery checks, before marking this stage complete.

**7. Sources and implementation boundaries**

- [Codex skill discovery](https://learn.chatgpt.com/docs/build-skills): repository discovery uses `.agents/skills` between the current directory and repository root.
- [Claude Code skill locations](https://code.claude.com/docs/en/skills): local project skills use `.claude/skills`; remote/cloud session behavior differs.
- Existing behavior: `repolife/mount.py`, `repolife/cli.py` and the mounting tests in `tests/test_repolife.py`.

Claude Code's read-only feasibility review supports the separate namespace and a pure-standard-library implementation, with legacy `init` unchanged. The design adopts a visible root-level receipt and preserves exact inserted bytes for shared files. It deliberately excludes `--force`, `--adopt`, `--config` and automatic ignore-line management from this stage. Directory cleanup is based on recorded creation, not an assumption that an empty directory belongs to the installer. Implementation should follow these decisions without broadening into CI management, automatic repair, global installation or agent orchestration.
