"""`tessri integration install|update|status|remove`: a project integration that can be previewed, updated and
removed without touching anything the user wrote.

The lifecycle keeps a receipt, `.tessri-integration.json`, at the project root: which profiles are installed,
the hash of every file it wrote, the exact span it inserted into a shared `AGENTS.md`, whether it created each
file and which directories it made. Only what the receipt records is ever updated or removed. A file that is
already there, even one byte-identical to the template, is a conflict and is left alone; so is a recorded file
the user has edited. Every mutation is planned and checked in full before the first write, a dry run writes
nothing, single files are replaced atomically and an ordinary failure is rolled back. This is not a cross-file
transaction. `tessri init` (mount.py) is unchanged and leaves no receipt, so its files are never claimed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import __version__, templates
from .model import SCHEMA_VERSION
from .mount import BEGIN, END

RECEIPT = ".tessri-integration.json"
LOCK = ".tessri-integration.lock"
MANIFEST_VERSION = 1
RESULT_VERSION = 1
ACTIONS = ("create", "update", "remove", "unchanged", "forget")
STATES = ("installed-current", "installed-outdated", "user-modified", "missing", "unmanaged", "symlink")
_BEGIN, _END = BEGIN.encode("utf-8"), END.encode("utf-8")
_HEX = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Profile:
    name: str
    path: str  # project-relative posix path; the fixed allowlist of what the lifecycle may touch
    kind: str  # "file": the whole file is ours | "span": one marked span inside a shared file
    note: str  # what the user has to do for a running host to see the change

    def content(self) -> bytes:
        return (templates.SKILL if self.kind == "file" else templates.AGENTS_BLOCK).encode("utf-8")


PROFILES = {
    "claude": Profile("claude", ".claude/skills/tessri/SKILL.md", "file", "start a new Claude Code session in this project so it discovers the skill"),
    "codex": Profile("codex", ".agents/skills/tessri/SKILL.md", "file", "restart Codex in this project so it discovers the skill"),
    "agents": Profile("agents", "AGENTS.md", "span", "hosts that read AGENTS.md pick the block up on their next read"),
}


class IntegrationError(Exception):
    """Invalid arguments, an unusable receipt, a symlinked receipt or an I/O failure: exit 2, no result object."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise IntegrationError(f"cannot read {path}: {exc.strerror}") from exc


def _symlink_in(root: Path, rel: str) -> str | None:
    """The first component of `rel` (under `root`) that is a symlink, dangling ones included, or None."""
    cur = root
    for part in PurePosixPath(rel).parts:
        cur = cur / part
        if cur.is_symlink():
            return cur.relative_to(root).as_posix()
    return None


def _missing_dirs(root: Path, rel: str) -> list[str]:
    """Ancestors of `rel` that do not exist yet, top-down: the directories an install would create."""
    out = []
    for parent in reversed(PurePosixPath(rel).parents):
        if parent.as_posix() != "." and not (root / parent).exists():
            out.append(parent.as_posix())
    return out


# --- the receipt -----------------------------------------------------------------------------------------------


@dataclass
class Target:
    """One owned thing, as the receipt records it."""

    profile: str
    path: str
    kind: str
    sha256: str  # of the file (kind file) or of the inserted span (kind span)
    created: bool  # the installer created the file; a span appended to an existing file has False
    dirs_created: list[str] = field(default_factory=list)  # top-down, only directories the installer made
    span: str | None = None  # kind span: the exact bytes inserted, separators included

    def to_json(self) -> dict:
        out = {"profile": self.profile, "path": self.path, "kind": self.kind, "sha256": self.sha256, "created": self.created, "dirs_created": list(self.dirs_created)}
        if self.kind == "span":
            out["span"] = self.span
        return out

    @classmethod
    def from_json(cls, raw: object) -> Target:
        if not isinstance(raw, dict):
            raise IntegrationError(f"{RECEIPT}: a target is not an object")
        profile = raw.get("profile")
        prof = PROFILES.get(profile) if isinstance(profile, str) else None
        if prof is None:
            raise IntegrationError(f"{RECEIPT}: unknown profile {profile!r}")
        if raw.get("path") != prof.path or raw.get("kind") != prof.kind:
            raise IntegrationError(f"{RECEIPT}: target of profile {profile} names {raw.get('path')!r} ({raw.get('kind')!r}); only {prof.path} ({prof.kind}) is allowed")
        sha = raw.get("sha256")
        if not isinstance(sha, str) or not _HEX.match(sha):
            raise IntegrationError(f"{RECEIPT}: target {prof.path} has no valid sha256")
        created = raw.get("created")
        if not isinstance(created, bool):
            raise IntegrationError(f"{RECEIPT}: target {prof.path} has no boolean `created`")
        dirs = raw.get("dirs_created", [])
        if not isinstance(dirs, list) or not all(isinstance(d, str) for d in dirs):
            raise IntegrationError(f"{RECEIPT}: target {prof.path} has an invalid `dirs_created`")
        for d in dirs:
            if not prof.path.startswith(d + "/") or ".." in PurePosixPath(d).parts or PurePosixPath(d).is_absolute():
                raise IntegrationError(f"{RECEIPT}: directory {d!r} is not a parent of {prof.path}")
        span = raw.get("span")
        if prof.kind == "span":
            if not isinstance(span, str):
                raise IntegrationError(f"{RECEIPT}: target {prof.path} records no span")
            data = span.encode("utf-8")
            if data.count(_BEGIN) != 1 or data.count(_END) != 1 or data.find(_BEGIN) > data.find(_END):
                raise IntegrationError(f"{RECEIPT}: the recorded span for {prof.path} does not hold one marker pair")
            if _sha(data) != sha:
                raise IntegrationError(f"{RECEIPT}: the recorded span for {prof.path} does not match its hash")
        else:
            span = None
        return cls(profile, prof.path, prof.kind, sha, created, list(dirs), span)


@dataclass
class Receipt:
    targets: list[Target]
    tool_version: str = __version__

    def get(self, profile: str) -> Target | None:
        return next((t for t in self.targets if t.profile == profile), None)

    def profiles(self) -> list[str]:
        return [p for p in PROFILES if self.get(p)]

    def to_bytes(self) -> bytes:
        doc = {
            "manifest_version": MANIFEST_VERSION,
            "tool": {"name": "tessri", "version": self.tool_version},
            "profiles": self.profiles(),
            "targets": [self.get(p).to_json() for p in self.profiles()],  # type: ignore[union-attr]
        }
        return (json.dumps(doc, indent=2) + "\n").encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> Receipt:
        try:
            doc = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise IntegrationError(f"{RECEIPT} is not valid JSON: {exc}") from exc
        if not isinstance(doc, dict):
            raise IntegrationError(f"{RECEIPT}: the document is not an object")
        if doc.get("manifest_version") != MANIFEST_VERSION:
            raise IntegrationError(f"{RECEIPT}: manifest_version {doc.get('manifest_version')!r} is not supported (this Tessri reads {MANIFEST_VERSION})")
        raw = doc.get("targets")
        if not isinstance(raw, list):
            raise IntegrationError(f"{RECEIPT}: `targets` is not a list")
        targets = [Target.from_json(t) for t in raw]
        seen = [t.profile for t in targets]
        if len(set(seen)) != len(seen):
            raise IntegrationError(f"{RECEIPT}: a profile is recorded twice")
        tool = doc.get("tool")
        version = tool.get("version") if isinstance(tool, dict) and isinstance(tool.get("version"), str) else "unknown"
        return cls(targets, version)


def load_receipt(root: Path) -> Receipt | None:
    """The receipt, None when there is none; a symlinked or malformed receipt is an error, never ignored."""
    path = root / RECEIPT
    if path.is_symlink():
        raise IntegrationError(f"{RECEIPT} is a symlink; refusing to read or write through it")
    data = _read(path)
    return None if data is None else Receipt.from_bytes(data)


# --- spans in a shared file --------------------------------------------------------------------------------------


def _block(nl: bytes) -> bytes:
    body = templates.AGENTS_BLOCK.rstrip("\n").encode("utf-8").replace(b"\n", nl)
    return _BEGIN + nl + body + nl + _END + nl


def _span_for(existing: bytes | None) -> bytes:
    """The bytes to insert: the marked block, preceded by the separator that leaves one blank line after what is
    there, in the file's own line endings. Nothing that exists is changed, so removing the span restores the file."""
    if not existing:
        return _block(b"\n")
    nl = b"\r\n" if b"\r\n" in existing else b"\n"
    if existing.endswith(nl + nl):
        prefix = b""
    elif existing.endswith(nl):
        prefix = nl
    else:
        prefix = nl + nl
    return prefix + _block(nl)


def _refreshed_span(old: bytes) -> bytes:
    """The recorded span with the current block text, keeping its separators and line endings."""
    prefix = old[: old.index(_BEGIN)]
    return prefix + _block(b"\r\n" if b"\r\n" in old else b"\n")


def _span_state(data: bytes | None, span: bytes) -> str:
    if data is None:
        return "missing"
    if data.count(span) == 1 and data.count(_BEGIN) == 1 and data.count(_END) == 1:
        return "ok"
    return "modified"


# --- plans -----------------------------------------------------------------------------------------------------


@dataclass
class Step:
    profile: str
    path: str
    kind: str
    action: str  # one of ACTIONS
    new: bytes | None = None  # bytes the file will hold (create, update, remove-span-but-keep-file)
    delete: bool = False  # remove the file itself
    dirs: list[str] = field(default_factory=list)  # create: directories to make; remove: candidates to clean
    target: Target | None = None  # the receipt entry afterwards; None when the entry is dropped

    def row(self) -> dict:
        return {"profile": self.profile, "path": self.path, "kind": self.kind, "action": self.action}


@dataclass
class Conflict:
    profile: str
    path: str
    reason: str  # unmanaged | markers | modified | symlink | changed | busy
    detail: str

    def row(self) -> dict:
        return {"profile": self.profile, "path": self.path, "reason": self.reason, "detail": self.detail}


@dataclass
class Plan:
    op: str
    profiles: list[str]
    steps: list[Step]
    conflicts: list[Conflict]
    receipt_after: Receipt | None
    receipt_action: str
    snapshot: dict[str, bytes | None]  # what every involved path held when the plan was made


def _snapshot(root: Path, paths: list[str]) -> dict[str, bytes | None]:
    return {rel: _read(root / rel) for rel in paths}


def _select(receipt: Receipt | None, profiles: list[str] | None, op: str) -> list[str]:
    """The recorded profiles `op` acts on. Without a receipt there is nothing recorded, so update and remove are
    no-ops: ownership is never inferred from a familiar file name or marker."""
    if receipt is None or not receipt.targets:
        return []
    if not profiles:
        return receipt.profiles()
    missing = [p for p in profiles if receipt.get(p) is None]
    if missing and op == "update":
        raise IntegrationError(f"profile {', '.join(missing)} is not recorded in {RECEIPT}; recorded: {', '.join(receipt.profiles()) or 'none'}")
    return [p for p in PROFILES if p in profiles and p not in missing]  # removing what is not recorded is a no-op


def _install_step(root: Path, prof: Profile, data: bytes | None) -> Step | Conflict:
    if prof.kind == "file":
        if data is not None:
            return Conflict(prof.name, prof.path, "unmanaged", "a file already exists here and no receipt records it; Tessri does not claim files it did not install (move it away, or keep using it unmanaged)")
        content = prof.content()
        dirs = _missing_dirs(root, prof.path)
        return Step(prof.name, prof.path, "file", "create", content, dirs=dirs, target=Target(prof.name, prof.path, "file", _sha(content), True, dirs))
    if data is None:
        span = _span_for(None)
        return Step(prof.name, prof.path, "span", "create", span, target=Target(prof.name, prof.path, "span", _sha(span), True, [], span.decode("utf-8")))
    if _BEGIN in data or _END in data:
        return Conflict(prof.name, prof.path, "markers", "AGENTS.md already carries tessri markers that no receipt installed (a legacy `tessri init` block, or another tool); remove them by hand or leave AGENTS.md unmanaged")
    span = _span_for(data)
    return Step(prof.name, prof.path, "span", "update", data + span, target=Target(prof.name, prof.path, "span", _sha(span), False, [], span.decode("utf-8")))


def _update_step(root: Path, prof: Profile, old: Target, data: bytes | None) -> Step | Conflict:
    if prof.kind == "file":
        content = prof.content()
        if data is None:
            dirs = sorted(set(old.dirs_created) | set(_missing_dirs(root, prof.path)), key=lambda d: d.count("/"))
            return Step(prof.name, prof.path, "file", "create", content, dirs=_missing_dirs(root, prof.path), target=Target(prof.name, prof.path, "file", _sha(content), True, dirs))
        if _sha(data) != old.sha256:
            return Conflict(prof.name, prof.path, "modified", "the file differs from what Tessri installed; it is yours now, so it is not updated or removed")
        if data == content:
            return Step(prof.name, prof.path, "file", "unchanged", target=old)
        return Step(prof.name, prof.path, "file", "update", content, target=Target(prof.name, prof.path, "file", _sha(content), old.created, old.dirs_created))
    span = (old.span or "").encode("utf-8")
    if data is None:
        new = _span_for(None)
        return Step(prof.name, prof.path, "span", "create", new, target=Target(prof.name, prof.path, "span", _sha(new), True, [], new.decode("utf-8")))
    if _span_state(data, span) != "ok":
        return Conflict(prof.name, prof.path, "modified", "the block Tessri inserted is no longer there as recorded (edited, duplicated or moved); it is not updated or removed")
    fresh = _refreshed_span(span)
    if fresh == span:
        return Step(prof.name, prof.path, "span", "unchanged", target=old)
    return Step(prof.name, prof.path, "span", "update", data.replace(span, fresh, 1), target=Target(prof.name, prof.path, "span", _sha(fresh), old.created, [], fresh.decode("utf-8")))


def _remove_step(prof: Profile, old: Target, data: bytes | None) -> Step | Conflict:
    if data is None:
        return Step(prof.name, prof.path, prof.kind, "forget", dirs=list(old.dirs_created))  # the dirs it made may still be empty
    if prof.kind == "file":
        if _sha(data) != old.sha256:
            return Conflict(prof.name, prof.path, "modified", "the file differs from what Tessri installed; it is yours now, so it is not removed (the receipt keeps recording it)")
        return Step(prof.name, prof.path, "file", "remove", delete=True, dirs=list(old.dirs_created))
    span = (old.span or "").encode("utf-8")
    if _span_state(data, span) != "ok":
        return Conflict(prof.name, prof.path, "modified", "the block Tessri inserted is no longer there as recorded; nothing in AGENTS.md is removed (the receipt keeps recording it)")
    remaining = data.replace(span, b"", 1)
    if old.created and remaining == b"":
        return Step(prof.name, prof.path, "span", "remove", delete=True)
    return Step(prof.name, prof.path, "span", "remove", remaining)


def plan(root: Path, op: str, profiles: list[str] | None) -> Plan:
    """The complete, checked plan for `op`; it changes nothing. Any conflict means nothing may be applied."""
    if op not in ("install", "update", "remove"):
        raise IntegrationError(f"unknown operation {op!r}")
    for p in profiles or []:
        if p not in PROFILES:
            raise IntegrationError(f"unknown profile {p!r}; choose from {', '.join(PROFILES)}")
    receipt = load_receipt(root)
    if op == "install":
        if not profiles:
            raise IntegrationError("install needs at least one --agent (claude, codex or agents)")
        selected = [p for p in PROFILES if p in profiles]
    else:
        selected = _select(receipt, profiles, op)
    # Links are refused before anything is read, so nothing outside the project is ever read, written or deleted.
    linked = sorted({bad for bad in (_symlink_in(root, PROFILES[p].path) for p in selected) if bad})
    if linked:
        raise IntegrationError(f"{', '.join(linked)}: a symlink in the path of a managed target; Tessri does not read, write or delete through links")
    snapshot = _snapshot(root, [PROFILES[p].path for p in selected] + [RECEIPT])

    steps: list[Step] = []
    conflicts: list[Conflict] = []
    for name in selected:
        prof = PROFILES[name]
        data = snapshot[prof.path]
        old = receipt.get(name) if receipt else None
        if op == "install":
            out = _update_step(root, prof, old, data) if old else _install_step(root, prof, data)
        elif op == "update":
            out = _update_step(root, prof, old, data)  # type: ignore[arg-type]
        else:
            out = _remove_step(prof, old, data)  # type: ignore[arg-type]
        (conflicts if isinstance(out, Conflict) else steps).append(out)  # type: ignore[arg-type]

    kept = [t for t in (receipt.targets if receipt else []) if t.profile not in {s.profile for s in steps}]
    after = Receipt(kept + [s.target for s in steps if s.target is not None])
    if not after.targets:
        receipt_after, action = None, ("remove" if receipt is not None else "unchanged")
    else:
        receipt_after = after
        before = snapshot[RECEIPT]
        action = "unchanged" if before == after.to_bytes() else ("update" if before is not None else "create")
    return Plan(op, selected, steps, conflicts, receipt_after, action, snapshot)


# --- applying --------------------------------------------------------------------------------------------------


def _atomic_write(path: Path, data: bytes, mode: int | None) -> None:
    """Write `data` next to `path` under a fresh exclusive name and move it into place. Only the temporary file this
    call created is ever cleaned up; a user's file that happens to carry a similar name is not touched."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tessri-tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, stat.S_IMODE(mode) if mode is not None else 0o666 & ~_umask())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _umask() -> int:
    current = os.umask(0)
    os.umask(current)
    return current


class _Lock:
    """One mutating lifecycle operation per project at a time. Fail fast; never remove another process's lock."""

    def __init__(self, root: Path):
        self.path = root / LOCK
        self.fd: int | None = None

    def acquire(self) -> Conflict | None:
        if self.path.is_symlink():
            raise IntegrationError(f"{LOCK} is a symlink; refusing to continue")
        try:
            self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return Conflict("", LOCK, "busy", f"{LOCK} exists: another Tessri lifecycle operation is running on this project. If none is, the lock is stale; remove it by hand and retry")
        except OSError as exc:
            raise IntegrationError(f"cannot create {LOCK}: {exc.strerror}") from exc
        try:
            os.write(self.fd, f"{os.getpid()}\n".encode())
        except OSError as exc:
            self.release()  # the lock is ours: do not leave it behind
            raise IntegrationError(f"cannot write {LOCK}: {exc.strerror}") from exc
        return None

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            try:
                self.path.unlink()
            except OSError:
                pass


def _apply(root: Path, plan: Plan) -> None:
    """Write the plan: each file replaced atomically, the receipt last, every step undone in reverse on failure."""
    undo: list[tuple] = []
    try:
        for step in plan.steps:
            path = root / step.path
            if step.action == "unchanged":
                continue
            if step.action == "forget":
                _clean_dirs(root, step.dirs, undo)
            elif step.action == "create":
                for rel in step.dirs:
                    d = root / rel
                    if not d.exists():
                        d.mkdir()
                        undo.append(("rmdir", d))
                _atomic_write(path, step.new or b"", None)
                undo.append(("unlink", path))
            elif step.action == "update":
                old, mode = path.read_bytes(), path.stat().st_mode
                _atomic_write(path, step.new or b"", mode)
                undo.append(("restore", path, old, mode))
            elif step.action == "remove":
                old, mode = path.read_bytes(), path.stat().st_mode
                if step.delete:
                    path.unlink()
                    undo.append(("recreate", path, old, mode))
                    _clean_dirs(root, step.dirs, undo)
                else:
                    _atomic_write(path, step.new or b"", mode)
                    undo.append(("restore", path, old, mode))
        receipt = root / RECEIPT
        if plan.receipt_action == "remove":
            old = receipt.read_bytes()
            receipt.unlink()
            undo.append(("recreate", receipt, old, None))
        elif plan.receipt_action != "unchanged" and plan.receipt_after is not None:
            old = _read(receipt)
            _atomic_write(receipt, plan.receipt_after.to_bytes(), None)
            undo.append(("unlink", receipt) if old is None else ("restore", receipt, old, None))
    except OSError as exc:
        failed = _rollback(undo)
        where = f"{exc.filename}: " if getattr(exc, "filename", None) else ""
        if failed:
            raise IntegrationError(f"{where}{exc.strerror}; rollback left these paths changed: {', '.join(failed)}") from exc
        raise IntegrationError(f"{where}{exc.strerror}; every earlier change was rolled back") from exc


def _clean_dirs(root: Path, dirs: list[str], undo: list[tuple]) -> None:
    """Remove the recorded directories deepest first while they are empty; the first one that is not stops the
    climb, and a directory that is already gone is simply skipped."""
    for rel in reversed(dirs):
        d = root / rel
        if not d.exists():
            continue
        try:
            d.rmdir()
        except OSError:
            break
        undo.append(("mkdir", d))


def _rollback(undo: list[tuple]) -> list[str]:
    failed = []
    for entry in reversed(undo):
        try:
            what, path = entry[0], entry[1]
            if what == "unlink":
                path.unlink()
            elif what == "rmdir":
                path.rmdir()
            elif what == "mkdir":
                path.mkdir()
            elif what in ("restore", "recreate"):
                _atomic_write(path, entry[2], entry[3])
        except OSError:
            failed.append(str(entry[1]))
    return failed


def run(root: Path, op: str, profiles: list[str] | None, dry_run: bool = False) -> dict:
    """Plan, and unless `dry_run` or a conflict stops it, lock, recheck and apply. Returns the result object."""
    root = Path(root).resolve()
    first = plan(root, op, profiles)
    if dry_run or first.conflicts:
        return _result(root, first, dry_run, applied=False)
    lock = _Lock(root)
    busy = lock.acquire()
    if busy:
        first.conflicts.append(busy)
        return _result(root, first, dry_run, applied=False)
    try:
        current = plan(root, op, profiles)
        if current.snapshot != first.snapshot:
            changed = sorted(p for p in first.snapshot if first.snapshot[p] != current.snapshot.get(p))
            current.conflicts.append(Conflict("", ", ".join(changed), "changed", "these paths changed while the plan was being made; nothing was written, run the command again"))
        if current.conflicts:
            return _result(root, current, dry_run, applied=False)
        _apply(root, current)
        return _result(root, current, dry_run, applied=True)
    finally:
        lock.release()


def _result(root: Path, plan: Plan, dry_run: bool, applied: bool) -> dict:
    notes = []
    if plan.conflicts:
        notes.append("Blocked by a conflict: nothing was written.")
    elif dry_run:
        notes.append("Dry run: nothing was written.")
    elif applied:  # only a profile whose files were written gets a note; a removal or a no-op speaks through its actions
        for name in plan.profiles:
            if any(s.profile == name and s.action in ("create", "update") for s in plan.steps):
                notes.append(f"{name}: {PROFILES[name].note}; the files being there does not prove a running host has seen them.")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": f"integration-{plan.op}",
        "result_version": RESULT_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "tool": {"name": "tessri", "version": __version__},
        "repo": {"name": root.name},
        "profiles": plan.profiles,
        "dry_run": dry_run,
        "applied": applied,
        "actions": [s.row() for s in plan.steps],
        "conflicts": [c.row() for c in plan.conflicts],
        "receipt": {"path": RECEIPT, "action": plan.receipt_action},
        "notes": notes,
    }


# --- status ----------------------------------------------------------------------------------------------------


def status(root: Path) -> dict:
    """What the receipt records against what is on disk; reads only, never locks, never analyses the repository."""
    root = Path(root).resolve()
    receipt = load_receipt(root)
    rows = []
    for name, prof in PROFILES.items():
        recorded = receipt.get(name) if receipt else None
        if _symlink_in(root, prof.path):
            if recorded or (root / prof.path).is_symlink():
                rows.append({"profile": name, "path": prof.path, "kind": prof.kind, "state": "symlink", "recorded": recorded is not None})
            continue
        data = _read(root / prof.path)
        if recorded is None:
            if data is not None and (prof.kind == "file" or _BEGIN in data or _END in data):
                rows.append({"profile": name, "path": prof.path, "kind": prof.kind, "state": "unmanaged", "recorded": False})
            continue
        if data is None:
            state = "missing"
        elif prof.kind == "file":
            state = "user-modified" if _sha(data) != recorded.sha256 else ("installed-current" if data == prof.content() else "installed-outdated")
        else:
            span = (recorded.span or "").encode("utf-8")
            state = "user-modified" if _span_state(data, span) != "ok" else ("installed-current" if _refreshed_span(span) == span else "installed-outdated")
        rows.append({"profile": name, "path": prof.path, "kind": prof.kind, "state": state, "recorded": True})
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "integration-status",
        "result_version": RESULT_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "tool": {"name": "tessri", "version": __version__},
        "repo": {"name": root.name},
        "installed": receipt is not None,
        "installed_by": receipt.tool_version if receipt else None,
        "profiles": receipt.profiles() if receipt else [],
        "targets": rows,
        "attention": any(r["state"] != "installed-current" for r in rows),
    }


# --- text --------------------------------------------------------------------------------------------------------


def text(doc: dict) -> str:
    out = []
    if doc["kind"] == "integration-status":
        if not doc["installed"]:
            out.append(f"No tessri integration receipt ({RECEIPT}) in this project.")
        else:
            out.append(f"Receipt {RECEIPT}: profiles {', '.join(doc['profiles']) or 'none'}, installed by tessri {doc['installed_by']}.")
        for row in doc["targets"]:
            out.append(f"{row['state']:<18} {row['path']} ({row['profile']})")
        if not doc["targets"]:
            out.append("No managed or unmanaged integration files found.")
        return "\n".join(out) + "\n"
    verb = {"create": "would create", "update": "would update", "remove": "would remove", "forget": "would forget", "unchanged": "unchanged"} if doc["dry_run"] or doc["conflicts"] else {}
    for row in doc["actions"]:
        out.append(f"{verb.get(row['action'], row['action']):<13} {row['path']} ({row['profile']})")
    for row in doc["conflicts"]:
        where = f"{row['path']} ({row['profile']})" if row["profile"] else row["path"]
        out.append(f"{'conflict':<13} {where}: {row['detail']}")
    action = doc["receipt"]["action"]
    if action != "unchanged":
        out.append(f"{verb.get(action, action):<13} {RECEIPT}")
    if not doc["actions"] and not doc["conflicts"]:
        out.append("Nothing to do.")
    out.extend(["", *doc["notes"]] if doc["notes"] else [])
    return "\n".join(out) + "\n"
