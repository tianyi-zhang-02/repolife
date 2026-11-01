# Reversible integration acceptance

This stage is accepted when an explicit project integration can be installed, inspected, upgraded and removed while preserving user content. Codex owns independent acceptance and this record; Claude Code owns implementation and regression tests. The first-stage source and its accepted 27 CLI scenarios remain the compatibility baseline.

**Independent scenarios**

All lifecycle experiments run in temporary projects whose paths contain spaces. Filesystem snapshots include file bytes, permission modes, directory existence and symlink destinations. They exclude timestamps, which are not a rollback guarantee. No actual user repository receives an installation receipt or host skill during acceptance.

| Group | What the caller must observe |
| --- | --- |
| Exact round trip, preview and idempotence | Source, configuration, ignore rules, Unicode/CRLF instructions and permissions are restored after removal. Preview creates nothing; repeated install/update adds no duplicate blocks or gratuitous receipt changes. |
| Invalid requests | Missing/unknown profile arguments and a missing or non-directory project root fail with no installed state. |
| Multiple hosts | Adding a host extends the receipt; removing one keeps the others installed and managed. Repeating selected removal is a no-op. |
| Foreign identical skill | An existing unrecorded file is a conflict even if byte-identical to the template; no other target is written. |
| Edited owned skill | Update/remove preserve both the edited content and its ownership record; selected unrelated profiles can still be removed. |
| Shared file external edits | Prefix/footer edits survive update and removal, for no-final-newline, LF and CRLF originals. |
| Edited owned block | Modification or malformed markers block the selected multi-target operation without partial writes. |
| User files in generated folders | Remove only the owned targets; retain new user files and their containing directories. |
| Pre-existing empty folders | Do not remove directories that happened to exist before installation. |
| Missing owned file | Status identifies the missing file; update can recreate it and removal can clear its receipt entry. |
| Invalid receipt | Invalid JSON and unsupported structure produce an error without mutation. |
| Forged paths | A receipt cannot redirect deletion to a path outside the project or to a target outside the fixed allowlist. |
| Symlink boundaries | Reject target/parent/receipt symlinks without changing their referents. |
| Busy lifecycle lock | A second mutator reports a conflict and leaves the existing lock intact; status stays read-only. |
| Foreign temporary-file collision | Atomic-write setup never deletes a pre-existing file when exclusive creation fails. |
| Lock-write failure | Failure after creating the lock closes its descriptor and removes only the operation's own lock. |
| Ordinary I/O failure | Inject failure in the second atomic replacement and verify earlier writes are rolled back to the original snapshot. |
| Real template upgrade | Install using a copied older template package, then update with the current package while preserving independent edits. |
| Legacy init | Old `init` installs no new ownership receipt; the lifecycle does not adopt or delete its files automatically. |
| Standalone archive | Build the documented zipapp, then install/status/remove successfully without an editable package installation. |

Some groups contain multiple operations and assertions; group counts do not represent an exhaustive count of supported failure modes. In particular, the I/O experiment covers an ordinary caught failure, not power loss or a filesystem transaction across paths.

**Host scope**

Claude Code and Codex target paths are checked against their official discovery documentation. A successful layout check verifies the files the installer creates. It does not by itself verify that a running host has reloaded the skill, that a cloud session sees local files, or that the model invokes the skill for every suitable task. Those claims require separate live-host evidence and are not part of the lifecycle acceptance.

**Execution record**

2026-10-31: all 20 independent scenario groups pass on Python 3.12.2, covering both new Git projects and ordinary directories. The first pass identified six boundary corrections: foreign temporary-file preservation, empty-directory cleanup after a missing target, invalid-root exit status, symlink validation before reads, failed lock-write cleanup and repeated selected removal. All six pass on independent rerun after implementation fixes.

The runner is `/private/tmp/repolife-stage2-20261031/acceptance.py`; its adjacent `acceptance-results.json` records the result. These temporary paths are local verification artifacts, not repository dependencies. The first-stage runner was also rerun against the combined working tree: all 13 legacy compatibility cases and 14 additional interface scenarios pass, and analyzed project bytes remain unchanged.

Claude Code's actual test-tool output was independently inspected: 49 lifecycle regressions pass, and the complete 330-test suite passes on Python 3.12 and 3.11 with `ResourceWarning` treated as an error. Plugin validation passes.

Final design review checked that the installed and plugin skills share one source, route queries by task, print ordinary JSON to stdout, do not download an unavailable CLI, and use advisory `check --fail-on never` in the routine example. Blocking is reserved for an explicitly enabled project gate. Installation notes identify the written profile and its discovery step; removal and unchanged operations produce no installation note. These refinements have regression assertions in the lifecycle tests.

Acceptance is complete for the local lifecycle and instruction behavior described here. No commit, push or installation into the user's repositories is part of this verification.
