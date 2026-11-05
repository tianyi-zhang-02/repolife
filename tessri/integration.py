"""`tessri integration install|update|status|remove`: a project integration that can be previewed, updated and
removed without touching anything the user wrote.

The lifecycle keeps a receipt, `.tessri-integration.json`, at the project root: which profiles are installed,
the hash of every file it wrote, the exact span it inserted into a shared `AGENTS.md`, the entry it added to a
shared MCP configuration file, whether it created each file and which directories it made. Only what the receipt records is ever updated or removed. A file that is
already there, even one byte-identical to the template, is a conflict and is left alone; so is a recorded file
the user has edited. Every mutation is planned and checked in full before the first write, a dry run writes
nothing, single files are replaced atomically and an ordinary failure is rolled back. This is not a cross-file
transaction. `tessri init` (mount.py) is unchanged and leaves no receipt, so its files are never claimed.

A receipt, skill files and AGENTS.md markers written by an older version under the project's old name are read as
they are (`status` reports them under their recorded paths) and moved to the current names by the next `install`,
`update` or `remove`: the skill file is created at its new path and the old one removed in the same run, the span
is rewritten with the current markers, and the receipt is written under its new name and the old file deleted.
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

from . import __version__, legacy, templates
from .model import SCHEMA_VERSION
from .mount import BEGIN, END

RECEIPT = ".tessri-integration.json"
LOCK = ".tessri-integration.lock"
MANIFEST_VERSION = 1
RESULT_VERSION = 1
ACTIONS = ("create", "update", "remove", "unchanged", "forget")
STATES = ("installed-current", "installed-outdated", "user-modified", "missing", "unmanaged", "symlink")
_BEGIN, _END = BEGIN.encode("utf-8"), END.encode("utf-8")
_MARKERS = ((_BEGIN, _END), (legacy.BEGIN.encode("utf-8"), legacy.END.encode("utf-8")))  # current first, then the old name's
_HEX = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Profile:
    name: str
    path: str  # project-relative posix path; the fixed allowlist of what the lifecycle may touch
    kind: str  # "file": the whole file is ours | "span": one marked span inside a shared file | "key": one entry in a shared JSON object
    note: str  # what the user has to do for a running host to see the change
    old_path: str | None = None  # where an older version installed this profile, when that differs; still recognised
    body: str = "SKILL"  # the attribute of `templates` that is the file's text (file) or the entry's value (key)
    key: tuple[str, str] | None = None  # kind key: the entry, as parent key and name (`mcpServers`, `tessri`)

    def value(self) -> dict:
        """Kind key: the entry's value, as the template has it."""
        return getattr(templates, self.body)

    def content(self) -> bytes:
        """The bytes the receipt hashes: the file's text, the AGENTS.md block, or the entry's canonical JSON."""
        if self.kind == "span":
            return templates.AGENTS_BLOCK.encode("utf-8")
        if self.kind == "key":
            return _canon(self.value())
        return getattr(templates, self.body).encode("utf-8")

    def paths(self) -> tuple[str, ...]:
        """Every path a receipt may record for this profile: the current one and, if different, the old one."""
        return (self.path, self.old_path) if self.old_path else (self.path,)


PROFILES = {
    "claude": Profile("claude", ".claude/skills/tessri/SKILL.md", "file", "start a new Claude Code session in this project so it discovers the skill", legacy.SKILL_PATHS["claude"]),
    "codex": Profile("codex", ".agents/skills/tessri/SKILL.md", "file", "restart Codex in this project so it discovers the skill", legacy.SKILL_PATHS["codex"]),
    "agents": Profile("agents", "AGENTS.md", "span", "hosts that read AGENTS.md pick the block up on their next read"),
    "copilot": Profile("copilot", ".github/instructions/tessri.instructions.md", "file", "Copilot reads the file on its next request in this repository", body="COPILOT_INSTRUCTIONS"),
    "mcp": Profile("mcp", ".mcp.json", "key", "a host that reads .mcp.json starts the server on its next session, after asking you to approve the project's servers", body="MCP_SERVER", key=("mcpServers", "tessri")),
    "vscode": Profile("vscode", ".vscode/mcp.json", "key", "an editor that reads .vscode/mcp.json starts the server on its next agent request", body="VSCODE_SERVER", key=("servers", "tessri")),
}

# Who reads what: the profiles that carry a host's instructions and the one that points it at the server, in the
# order `status` tries them; a host with no project-side server configuration gets the line to run instead.
HOSTS = (
    ("Claude Code", ("claude", "agents"), "mcp", None),
    ("Codex", ("codex", "agents"), None, f"run `{templates.CODEX_MCP_COMMAND}` (Codex keeps MCP servers in your own configuration)"),
    ("Copilot coding agent", ("agents", "copilot"), None, "paste into the repository's settings, Copilot, Coding agent, MCP configuration: " + json.dumps(templates.COPILOT_AGENT_SERVERS) + "; put `pip install tessri` in copilot-setup-steps.yml"),
    ("editors reading .vscode/mcp.json", ("agents", "copilot", "claude", "codex"), "vscode", None),
)


def _markers_of(span: bytes) -> tuple[bytes, bytes]:
    """The marker pair a span uses: the current one, or the one an older version wrote under the old name."""
    for begin, end in _MARKERS:
        if begin in span:
            return begin, end
    return _BEGIN, _END


class IntegrationError(Exception):
    """Invalid arguments, an unusable receipt, a symlinked receipt or an I/O failure: exit 2, no result object."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- one entry in a shared JSON file -------------------------------------------------------------------------------


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _load_object(data: bytes) -> dict | None:
    """The file as a JSON object, or None when it is not one (comments, a list, broken JSON)."""
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _dump_object(obj: dict) -> bytes:
    return (json.dumps(obj, indent=2) + "\n").encode("utf-8")


def _entry(obj: dict | None, key: tuple[str, str]) -> object | None:
    parent = obj.get(key[0]) if obj else None
    return parent.get(key[1]) if isinstance(parent, dict) else None


def _with_entry(obj: dict, key: tuple[str, str], value: object) -> dict:
    out = dict(obj)
    out[key[0]] = {**out.get(key[0], {}), key[1]: value}  # type: ignore[dict-item]
    return out


def _without_entry(obj: dict, key: tuple[str, str]) -> dict:
    out = dict(obj)
    parent = {k: v for k, v in out.get(key[0], {}).items() if k != key[1]}  # type: ignore[union-attr]
    if parent:
        out[key[0]] = parent
    else:
        out.pop(key[0], None)
    return out


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
        if self.kind in ("span", "key"):
            out["span"] = self.span
        return out

    @classmethod
    def from_json(cls, raw: object, name: str = RECEIPT) -> Target:
        if not isinstance(raw, dict):
            raise IntegrationError(f"{name}: a target is not an object")
        profile = raw.get("profile")
        prof = PROFILES.get(profile) if isinstance(profile, str) else None
        if prof is None:
            raise IntegrationError(f"{name}: unknown profile {profile!r}")
        path = raw.get("path")
        if path not in prof.paths() or raw.get("kind") != prof.kind:
            raise IntegrationError(f"{name}: target of profile {profile} names {path!r} ({raw.get('kind')!r}); only {' or '.join(prof.paths())} ({prof.kind}) is allowed")
        sha = raw.get("sha256")
        if not isinstance(sha, str) or not _HEX.match(sha):
            raise IntegrationError(f"{name}: target {path} has no valid sha256")
        created = raw.get("created")
        if not isinstance(created, bool):
            raise IntegrationError(f"{name}: target {path} has no boolean `created`")
        dirs = raw.get("dirs_created", [])
        if not isinstance(dirs, list) or not all(isinstance(d, str) for d in dirs):
            raise IntegrationError(f"{name}: target {path} has an invalid `dirs_created`")
        for d in dirs:
            if not path.startswith(d + "/") or ".." in PurePosixPath(d).parts or PurePosixPath(d).is_absolute():
                raise IntegrationError(f"{name}: directory {d!r} is not a parent of {path}")
        span = raw.get("span")
        if prof.kind == "span":
            if not isinstance(span, str):
                raise IntegrationError(f"{name}: target {path} records no span")
            data = span.encode("utf-8")
            begin, end = _markers_of(data)
            if data.count(begin) != 1 or data.count(end) != 1 or data.find(begin) > data.find(end):
                raise IntegrationError(f"{name}: the recorded span for {path} does not hold one marker pair")
            if _sha(data) != sha:
                raise IntegrationError(f"{name}: the recorded span for {path} does not match its hash")
        elif prof.kind == "key":
            if not isinstance(span, str) or _load_object(span.encode("utf-8")) is None:
                raise IntegrationError(f"{name}: target {path} records no entry")
            if _sha(_canon(json.loads(span))) != sha:
                raise IntegrationError(f"{name}: the recorded entry for {path} does not match its hash")
        else:
            span = None
        return cls(profile, path, prof.kind, sha, created, list(dirs), span)


@dataclass
class Receipt:
    targets: list[Target]
    tool_version: str = __version__
    path: str = RECEIPT  # the file it was read from: the current name, or the old one an older version wrote

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
    def from_bytes(cls, data: bytes, name: str = RECEIPT) -> Receipt:
        try:
            doc = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise IntegrationError(f"{name} is not valid JSON: {exc}") from exc
        if not isinstance(doc, dict):
            raise IntegrationError(f"{name}: the document is not an object")
        if doc.get("manifest_version") != MANIFEST_VERSION:
            raise IntegrationError(f"{name}: manifest_version {doc.get('manifest_version')!r} is not supported (this Tessri reads {MANIFEST_VERSION})")
        raw = doc.get("targets")
        if not isinstance(raw, list):
            raise IntegrationError(f"{name}: `targets` is not a list")
        targets = [Target.from_json(t, name) for t in raw]
        seen = [t.profile for t in targets]
        if len(set(seen)) != len(seen):
            raise IntegrationError(f"{name}: a profile is recorded twice")
        tool = doc.get("tool")
        version = tool.get("version") if isinstance(tool, dict) and isinstance(tool.get("version"), str) else "unknown"
        return cls(targets, version, name)


def load_receipt(root: Path) -> Receipt | None:
    """The receipt, None when there is none; a symlinked or malformed receipt is an error, never ignored. The file
    under the current name wins; one left by an older version under the old name is read when there is no other."""
    for name in (RECEIPT, legacy.RECEIPT):
        path = root / name
        if path.is_symlink():
            raise IntegrationError(f"{name} is a symlink; refusing to read or write through it")
        data = _read(path)
        if data is not None:
            return Receipt.from_bytes(data, name)
    return None


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
    """The recorded span with the current block text and markers, keeping its separators and line endings."""
    begin, _ = _markers_of(old)
    prefix = old[: old.index(begin)]
    return prefix + _block(b"\r\n" if b"\r\n" in old else b"\n")


def _span_state(data: bytes | None, span: bytes) -> str:
    if data is None:
        return "missing"
    begin, end = _markers_of(span)
    if data.count(span) == 1 and data.count(begin) == 1 and data.count(end) == 1:
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
    receipt_from: str = RECEIPT  # the receipt file that was read; the old name when an older version wrote it


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
        raise IntegrationError(f"profile {', '.join(missing)} is not recorded in {receipt.path}; recorded: {', '.join(receipt.profiles()) or 'none'}")
    return [p for p in PROFILES if p in profiles and p not in missing]  # removing what is not recorded is a no-op


def _key_target(prof: Profile, created: bool, dirs: list[str]) -> Target:
    value = _canon(prof.value())
    return Target(prof.name, prof.path, "key", _sha(value), created, dirs, value.decode("utf-8"))


def _install_key(root: Path, prof: Profile, data: bytes | None) -> Step | Conflict:
    """Add the entry to a JSON object file: the whole file when there is none, one entry when the file parses."""
    assert prof.key is not None
    if data is None:
        dirs = _missing_dirs(root, prof.path)
        return Step(prof.name, prof.path, "key", "create", _dump_object(_with_entry({}, prof.key, prof.value())), dirs=dirs, target=_key_target(prof, True, dirs))
    obj = _load_object(data)
    if obj is None or (prof.key[0] in obj and not isinstance(obj[prof.key[0]], dict)):
        return Conflict(prof.name, prof.path, "unmanaged", f"the file is not a JSON object Tessri can add to (comments, or `{prof.key[0]}` is not an object); add the entry by hand: {json.dumps(_with_entry({}, prof.key, prof.value()))}")
    if _entry(obj, prof.key) is not None:
        return Conflict(prof.name, prof.path, "markers", f"the file already has a `{prof.key[0]}.{prof.key[1]}` entry that no receipt installed; remove it by hand or leave the file unmanaged")
    return Step(prof.name, prof.path, "key", "update", _dump_object(_with_entry(obj, prof.key, prof.value())), target=_key_target(prof, False, []))


def _update_key(root: Path, prof: Profile, old: Target, data: bytes | None) -> list[Step] | Conflict:
    assert prof.key is not None
    if data is None:
        dirs = sorted(set(old.dirs_created) | set(_missing_dirs(root, prof.path)), key=lambda d: d.count("/"))
        return [Step(prof.name, prof.path, "key", "create", _dump_object(_with_entry({}, prof.key, prof.value())), dirs=_missing_dirs(root, prof.path), target=_key_target(prof, True, dirs))]
    obj = _load_object(data)
    current = _entry(obj, prof.key)
    if current is None or _canon(current) != _canon(json.loads(old.span or "null")):
        return Conflict(prof.name, prof.path, "modified", "the entry Tessri installed is no longer there as recorded (edited, removed, or the file no longer parses); it is not updated or removed")
    if _canon(current) == _canon(prof.value()):
        return [Step(prof.name, prof.path, "key", "unchanged", target=old)]
    return [Step(prof.name, prof.path, "key", "update", _dump_object(_with_entry(obj or {}, prof.key, prof.value())), target=_key_target(prof, old.created, old.dirs_created))]


def _remove_key(prof: Profile, old: Target, data: bytes) -> list[Step] | Conflict:
    assert prof.key is not None
    obj = _load_object(data)
    current = _entry(obj, prof.key)
    if current is None or _canon(current) != _canon(json.loads(old.span or "null")):
        return Conflict(prof.name, old.path, "modified", f"the entry Tessri installed is no longer there as recorded; nothing in {old.path} is removed (the receipt keeps recording it)")
    remaining = _without_entry(obj or {}, prof.key)
    if old.created and not remaining:
        return [Step(prof.name, old.path, "key", "remove", delete=True, dirs=list(old.dirs_created))]
    return [Step(prof.name, old.path, "key", "remove", _dump_object(remaining))]


def _install_step(root: Path, prof: Profile, data: bytes | None) -> Step | Conflict:
    if prof.kind == "key":
        return _install_key(root, prof, data)
    if prof.kind == "file":
        if data is not None:
            return Conflict(prof.name, prof.path, "unmanaged", "a file already exists here and no receipt records it; Tessri does not claim files it did not install (move it away, or keep using it unmanaged)")
        content = prof.content()
        dirs = _missing_dirs(root, prof.path)
        return Step(prof.name, prof.path, "file", "create", content, dirs=dirs, target=Target(prof.name, prof.path, "file", _sha(content), True, dirs))
    if data is None:
        span = _span_for(None)
        return Step(prof.name, prof.path, "span", "create", span, target=Target(prof.name, prof.path, "span", _sha(span), True, [], span.decode("utf-8")))
    if any(b in data or e in data for b, e in _MARKERS):
        return Conflict(prof.name, prof.path, "markers", "AGENTS.md already carries Tessri markers (under the current or the old name) that no receipt installed (an `init` block, or another tool); remove them by hand or leave AGENTS.md unmanaged")
    span = _span_for(data)
    return Step(prof.name, prof.path, "span", "update", data + span, target=Target(prof.name, prof.path, "span", _sha(span), False, [], span.decode("utf-8")))


def _move_step(root: Path, prof: Profile, old: Target, data: bytes | None, old_data: bytes | None) -> list[Step] | Conflict:
    """A file target recorded under the old path: create it at the current path, then remove the old file, in that
    order so that the directories the old install made and the new path still needs are never emptied in between.
    Those directories stay recorded as made by the installer; only the old leaf directory is cleaned up."""
    if data is not None:
        return Conflict(prof.name, prof.path, "unmanaged", "a file already exists where the skill now lives and no receipt records it; Tessri does not claim files it did not install (move it away, or keep using it unmanaged)")
    if old_data is not None and _sha(old_data) != old.sha256:
        return Conflict(prof.name, old.path, "modified", "the file differs from what Tessri installed under its old name; it is yours now, so it is not moved or removed")
    content = prof.content()
    inherited = [d for d in old.dirs_created if prof.path.startswith(d + "/")]
    dirs = sorted(set(inherited) | set(_missing_dirs(root, prof.path)), key=lambda d: d.count("/"))
    create = Step(prof.name, prof.path, "file", "create", content, dirs=_missing_dirs(root, prof.path), target=Target(prof.name, prof.path, "file", _sha(content), True, dirs))
    leaf = [d for d in old.dirs_created if d not in inherited]
    if old_data is None:
        return [create, Step(prof.name, old.path, "file", "forget", dirs=leaf)]
    return [create, Step(prof.name, old.path, "file", "remove", delete=True, dirs=leaf)]


def _update_step(root: Path, prof: Profile, old: Target, data: bytes | None, old_data: bytes | None) -> list[Step] | Conflict:
    if prof.kind == "key":
        return _update_key(root, prof, old, data)
    if prof.kind == "file":
        if old.path != prof.path:
            return _move_step(root, prof, old, data, old_data)
        content = prof.content()
        if data is None:
            dirs = sorted(set(old.dirs_created) | set(_missing_dirs(root, prof.path)), key=lambda d: d.count("/"))
            return [Step(prof.name, prof.path, "file", "create", content, dirs=_missing_dirs(root, prof.path), target=Target(prof.name, prof.path, "file", _sha(content), True, dirs))]
        if _sha(data) != old.sha256:
            return Conflict(prof.name, prof.path, "modified", "the file differs from what Tessri installed; it is yours now, so it is not updated or removed")
        if data == content:
            return [Step(prof.name, prof.path, "file", "unchanged", target=old)]
        return [Step(prof.name, prof.path, "file", "update", content, target=Target(prof.name, prof.path, "file", _sha(content), old.created, old.dirs_created))]
    span = (old.span or "").encode("utf-8")
    if data is None:
        new = _span_for(None)
        return [Step(prof.name, prof.path, "span", "create", new, target=Target(prof.name, prof.path, "span", _sha(new), True, [], new.decode("utf-8")))]
    if _span_state(data, span) != "ok":
        return Conflict(prof.name, prof.path, "modified", "the block Tessri inserted is no longer there as recorded (edited, duplicated or moved); it is not updated or removed")
    fresh = _refreshed_span(span)
    if fresh == span:
        return [Step(prof.name, prof.path, "span", "unchanged", target=old)]
    return [Step(prof.name, prof.path, "span", "update", data.replace(span, fresh, 1), target=Target(prof.name, prof.path, "span", _sha(fresh), old.created, [], fresh.decode("utf-8")))]


def _remove_step(prof: Profile, old: Target, data: bytes | None) -> list[Step] | Conflict:
    """`data` is what the recorded path holds; for a target recorded under the old path that is the old file."""
    if data is None:
        return [Step(prof.name, old.path, prof.kind, "forget", dirs=list(old.dirs_created))]  # the dirs it made may still be empty
    if prof.kind == "key":
        return _remove_key(prof, old, data)
    if prof.kind == "file":
        if _sha(data) != old.sha256:
            return Conflict(prof.name, old.path, "modified", "the file differs from what Tessri installed; it is yours now, so it is not removed (the receipt keeps recording it)")
        return [Step(prof.name, old.path, "file", "remove", delete=True, dirs=list(old.dirs_created))]
    span = (old.span or "").encode("utf-8")
    if _span_state(data, span) != "ok":
        return Conflict(prof.name, old.path, "modified", "the block Tessri inserted is no longer there as recorded; nothing in AGENTS.md is removed (the receipt keeps recording it)")
    remaining = data.replace(span, b"", 1)
    if old.created and remaining == b"":
        return [Step(prof.name, old.path, "span", "remove", delete=True)]
    return [Step(prof.name, old.path, "span", "remove", remaining)]


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
            raise IntegrationError(f"install needs at least one --agent ({', '.join(PROFILES)})")
        selected = [p for p in PROFILES if p in profiles]
    else:
        selected = _select(receipt, profiles, op)
    # Links are refused before anything is read, so nothing outside the project is ever read, written or deleted.
    recorded = {p: receipt.get(p) for p in selected if receipt and receipt.get(p)}
    involved = sorted({PROFILES[p].path for p in selected} | {t.path for t in recorded.values()})
    linked = sorted({bad for bad in (_symlink_in(root, rel) for rel in involved) if bad})
    if linked:
        raise IntegrationError(f"{', '.join(linked)}: a symlink in the path of a managed target; Tessri does not read, write or delete through links")
    snapshot = _snapshot(root, involved + [RECEIPT, legacy.RECEIPT])

    steps: list[Step] = []
    conflicts: list[Conflict] = []
    for name in selected:
        prof = PROFILES[name]
        data = snapshot[prof.path]
        old = recorded.get(name)
        if op == "install":
            out = _update_step(root, prof, old, data, snapshot[old.path]) if old else [_install_step(root, prof, data)]
        elif op == "update":
            out = _update_step(root, prof, old, data, snapshot[old.path])  # type: ignore[union-attr]
        else:
            out = _remove_step(prof, old, snapshot[old.path])  # type: ignore[union-attr]
        if isinstance(out, Conflict):
            conflicts.append(out)
        else:
            for item in out:
                (conflicts if isinstance(item, Conflict) else steps).append(item)  # type: ignore[arg-type]

    kept = [t for t in (receipt.targets if receipt else []) if t.profile not in {s.profile for s in steps}]
    after = Receipt(kept + [s.target for s in steps if s.target is not None])
    if not after.targets:
        receipt_after, action = None, ("remove" if receipt is not None else "unchanged")
    else:
        receipt_after = after
        before = snapshot[RECEIPT]
        action = "unchanged" if before == after.to_bytes() else ("update" if before is not None else "create")
    return Plan(op, selected, steps, conflicts, receipt_after, action, snapshot, receipt.path if receipt else RECEIPT)


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
        receipt, origin = root / RECEIPT, root / plan.receipt_from
        if plan.receipt_action == "remove":
            old = origin.read_bytes()
            origin.unlink()
            undo.append(("recreate", origin, old, None))
        elif plan.receipt_action != "unchanged" and plan.receipt_after is not None:
            old = _read(receipt)
            _atomic_write(receipt, plan.receipt_after.to_bytes(), None)
            undo.append(("unlink", receipt) if old is None else ("restore", receipt, old, None))
            if origin != receipt:  # written under the current name: the old file has nothing left to say
                stale = origin.read_bytes()
                origin.unlink()
                undo.append(("recreate", origin, stale, None))
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
        "receipt": {"path": RECEIPT, "action": plan.receipt_action, **({"replaces": plan.receipt_from} if plan.receipt_from != RECEIPT else {})},
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
        if recorded is None:
            for rel in prof.paths():
                if _symlink_in(root, rel):
                    if (root / rel).is_symlink():
                        rows.append({"profile": name, "path": rel, "kind": prof.kind, "state": "symlink", "recorded": False})
                    continue
                data = _read(root / rel)
                if data is None:
                    continue
                if prof.kind == "file" or (prof.kind == "span" and any(b in data or e in data for b, e in _MARKERS)) or (prof.kind == "key" and _entry(_load_object(data), prof.key) is not None):  # type: ignore[arg-type]
                    rows.append({"profile": name, "path": rel, "kind": prof.kind, "state": "unmanaged", "recorded": False})
            continue
        rel = recorded.path
        if _symlink_in(root, rel):
            rows.append({"profile": name, "path": rel, "kind": prof.kind, "state": "symlink", "recorded": True})
            continue
        data = _read(root / rel)
        if data is None:
            state = "missing"
        elif prof.kind == "file":
            state = "user-modified" if _sha(data) != recorded.sha256 else ("installed-current" if rel == prof.path and data == prof.content() else "installed-outdated")
        elif prof.kind == "key":
            current = _entry(_load_object(data), prof.key)  # type: ignore[arg-type]
            state = "user-modified" if current is None or _sha(_canon(current)) != recorded.sha256 else ("installed-current" if _canon(current) == prof.content() else "installed-outdated")
        else:
            span = (recorded.span or "").encode("utf-8")
            state = "user-modified" if _span_state(data, span) != "ok" else ("installed-current" if _refreshed_span(span) == span else "installed-outdated")
        rows.append({"profile": name, "path": rel, "kind": prof.kind, "state": state, "recorded": True})
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "integration-status",
        "result_version": RESULT_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "tool": {"name": "tessri", "version": __version__},
        "repo": {"name": root.name},
        "installed": receipt is not None,
        "installed_by": receipt.tool_version if receipt else None,
        "receipt_path": receipt.path if receipt else None,
        "profiles": receipt.profiles() if receipt else [],
        "targets": rows,
        "hosts": _hosts(rows),
        "attention": any(r["state"] != "installed-current" for r in rows),
    }


def _hosts(rows: list[dict]) -> list[dict]:
    """Per host: which installed file carries its instructions, which one points it at the MCP server, and what is
    left to do. `None` means nothing installed for that part."""
    installed = {r["profile"]: r["path"] for r in rows if r["recorded"] and r["state"] != "missing"}
    out = []
    for host, reads, server, by_hand in HOSTS:
        instructions = next((installed[p] for p in reads if p in installed), None)
        pointed = installed.get(server) if server else None
        todo = []
        if instructions is None:
            todo.append(f"tessri integration install --agent {reads[0]}")
        if server and pointed is None:
            todo.append(f"tessri integration install --agent {server}")
        if by_hand:
            todo.append(by_hand)
        out.append({"host": host, "instructions": instructions, "server": pointed, "next": "; ".join(todo) or None})
    return out


# --- text --------------------------------------------------------------------------------------------------------


def text(doc: dict) -> str:
    out = []
    if doc["kind"] == "integration-status":
        if not doc["installed"]:
            out.append(f"No Tessri integration receipt ({RECEIPT}) in this project.")
        else:
            out.append(f"Receipt {doc.get('receipt_path', RECEIPT)}: profiles {', '.join(doc['profiles']) or 'none'}, installed by {doc['installed_by']}.")
        for row in doc["targets"]:
            out.append(f"{row['state']:<18} {row['path']} ({row['profile']})")
        if not doc["targets"]:
            out.append("No managed or unmanaged integration files found.")
        out.append("")
        for host in doc.get("hosts", []):
            out.append(f"{host['host']}: instructions {host['instructions'] or 'none'}; server {host['server'] or 'none'}" + (f"; next: {host['next']}" if host["next"] else ""))
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
        if doc["receipt"].get("replaces") and action != "remove":
            out.append(f"{verb.get('remove', 'remove'):<13} {doc['receipt']['replaces']}")
    if not doc["actions"] and not doc["conflicts"]:
        out.append("Nothing to do.")
    out.extend(["", *doc["notes"]] if doc["notes"] else [])
    return "\n".join(out) + "\n"
