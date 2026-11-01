"""`repolife integration`: install, update, status and remove with a receipt, never touching what the user wrote."""

import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from helpers import TempRepo, write_tree

from repolife import integration, templates
from repolife.cli import main
from repolife.integration import LOCK, PROFILES, RECEIPT, IntegrationError, run, status
from repolife.mount import BEGIN, END, mount

PROJECT = {"src/app.py": "import src.lib\n", "src/lib.py": "x = 1\n", "README.md": "# demo\n", ".gitignore": "dist/\n"}
SKILL = ".claude/skills/repolife/SKILL.md"
CODEX = ".agents/skills/repolife/SKILL.md"


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def tree(root: Path) -> dict[str, bytes]:
    """Every file under `root` with its bytes, for before/after comparisons."""
    out = {}
    for base, dirs, files in os.walk(root):
        for name in files:
            p = Path(base) / name
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


class Project(TempRepo):
    def setUp(self):
        super().setUp()
        write_tree(self.root, PROJECT)

    def receipt(self) -> dict:
        return json.loads((self.root / RECEIPT).read_text())

    def actions(self, doc: dict) -> dict[str, str]:
        return {a["profile"]: a["action"] for a in doc["actions"]}

    def conflicts(self, doc: dict) -> dict[str, str]:
        return {c["profile"]: c["reason"] for c in doc["conflicts"]}


class InstallTest(Project):
    def test_dry_run_plans_everything_and_writes_nothing(self):
        before = tree(self.root)
        doc = run(self.root, "install", ["claude", "agents"], dry_run=True)
        self.assertEqual(self.actions(doc), {"claude": "create", "agents": "create"})
        self.assertEqual((doc["dry_run"], doc["applied"], doc["receipt"]["action"], doc["conflicts"]), (True, False, "create", []))
        self.assertEqual(tree(self.root), before)
        self.assertFalse((self.root / LOCK).exists())

    def test_install_writes_only_its_targets_and_a_receipt(self):
        before = tree(self.root)
        doc = run(self.root, "install", ["claude", "codex", "agents"])
        self.assertEqual((doc["applied"], doc["conflicts"]), (True, []))
        after = tree(self.root)
        self.assertEqual({k: v for k, v in after.items() if k in before}, before)  # nothing that existed changed
        self.assertEqual(set(after) - set(before), {SKILL, CODEX, "AGENTS.md", RECEIPT})
        self.assertEqual(after[SKILL].decode(), templates.SKILL)
        self.assertEqual(after[CODEX].decode(), templates.SKILL)
        self.assertTrue(after["AGENTS.md"].startswith(BEGIN.encode()) and after["AGENTS.md"].rstrip(b"\n").endswith(END.encode()))
        rec = self.receipt()
        self.assertEqual((rec["manifest_version"], rec["profiles"]), (1, ["claude", "codex", "agents"]))
        by = {t["profile"]: t for t in rec["targets"]}
        self.assertEqual(by["claude"]["dirs_created"], [".claude", ".claude/skills", ".claude/skills/repolife"])
        self.assertTrue(by["claude"]["created"] and by["agents"]["created"])
        self.assertEqual(by["agents"]["span"].encode(), after["AGENTS.md"])
        self.assertNotIn(str(self.root), (self.root / RECEIPT).read_text())  # no machine paths in the receipt
        self.assertIn("claude: start a new Claude Code session", " ".join(doc["notes"]))

    def test_repeated_install_changes_no_byte(self):
        run(self.root, "install", ["claude", "agents"])
        before = tree(self.root)
        doc = run(self.root, "install", ["claude", "agents"])
        self.assertEqual(self.actions(doc), {"claude": "unchanged", "agents": "unchanged"})
        self.assertEqual((doc["receipt"]["action"], doc["notes"]), ("unchanged", []))
        self.assertEqual(tree(self.root), before)
        self.assertEqual(before["AGENTS.md"].count(BEGIN.encode()), 1)

    def test_install_adds_a_profile_to_an_existing_receipt(self):
        run(self.root, "install", ["claude"])
        doc = run(self.root, "install", ["codex"])
        self.assertEqual(self.actions(doc), {"codex": "create"})
        self.assertEqual(self.receipt()["profiles"], ["claude", "codex"])

    def test_install_needs_a_profile(self):
        with self.assertRaises(IntegrationError):
            run(self.root, "install", None)
        code, out, err = run_cli("integration", "install", str(self.root))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("--agent", err)

    def test_existing_skill_is_a_conflict_even_when_identical(self):
        write_tree(self.root, {SKILL: templates.SKILL})
        before = tree(self.root)
        doc = run(self.root, "install", ["claude", "agents"])
        self.assertEqual(self.conflicts(doc), {"claude": "unmanaged"})
        self.assertEqual(self.actions(doc), {"agents": "create"})  # planned, but not applied
        self.assertEqual((doc["applied"], tree(self.root)), (False, before))
        self.assertFalse((self.root / RECEIPT).exists())

    def test_legacy_init_block_is_a_conflict(self):
        mount(self.root, {"agents"}, None, "repolife")
        before = tree(self.root)
        doc = run(self.root, "install", ["agents"])
        self.assertEqual(self.conflicts(doc), {"agents": "markers"})
        self.assertEqual(tree(self.root), before)

    def test_span_appended_to_crlf_file_without_trailing_newline(self):
        original = "# Agents\r\n\r\nKeep me é中".encode("utf-8")
        (self.root / "AGENTS.md").write_bytes(original)
        mode = 0o640
        os.chmod(self.root / "AGENTS.md", mode)
        doc = run(self.root, "install", ["agents"])
        self.assertEqual(self.actions(doc), {"agents": "update"})
        data = (self.root / "AGENTS.md").read_bytes()
        self.assertTrue(data.startswith(original + b"\r\n\r\n" + BEGIN.encode() + b"\r\n"))
        self.assertNotIn(b"\n\n", data.replace(b"\r\n", b""))  # the block itself uses CRLF
        self.assertEqual(os.stat(self.root / "AGENTS.md").st_mode & 0o777, mode)
        self.assertFalse(self.receipt()["targets"][0]["created"])
        run(self.root, "remove", None)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), original)
        self.assertEqual(os.stat(self.root / "AGENTS.md").st_mode & 0o777, mode)
        self.assertFalse((self.root / RECEIPT).exists())

    def test_span_after_trailing_newline_leaves_one_blank_line(self):
        (self.root / "AGENTS.md").write_bytes(b"# Agents\n")
        run(self.root, "install", ["agents"])
        self.assertTrue((self.root / "AGENTS.md").read_bytes().startswith(b"# Agents\n\n" + BEGIN.encode()))

    @unittest.skipIf(sys.platform == "win32", "symlinks")
    def test_symlinked_parent_is_refused_without_touching_the_referent(self):
        elsewhere = self.root.parent / (self.root.name + "-elsewhere")
        elsewhere.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(elsewhere, ignore_errors=True))
        (self.root / ".claude").symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(IntegrationError, "symlink"):
            run(self.root, "install", ["claude", "agents"])
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertFalse((self.root / RECEIPT).exists() or (self.root / "AGENTS.md").exists())
        code, out, err = run_cli("integration", "install", str(self.root), "--agent", "claude", "--format", "json")
        self.assertEqual((code, out), (2, ""))
        self.assertIn(".claude", err)

    @unittest.skipIf(sys.platform == "win32", "symlinks")
    def test_dangling_symlink_target_is_refused_before_any_read(self):
        (self.root / "AGENTS.md").symlink_to(self.root / "nowhere.md")
        real_read = integration._read

        def guarded(path):
            if path.name == "AGENTS.md":
                raise AssertionError("read through a link")
            return real_read(path)

        with mock.patch.object(integration, "_read", guarded):
            with self.assertRaisesRegex(IntegrationError, "symlink"):
                run(self.root, "install", ["agents"])
        self.assertFalse((self.root / "nowhere.md").exists())

    def test_user_file_with_a_temp_like_name_survives(self):
        mine = self.root / ".claude/skills/repolife/.SKILL.md.repolife-tmp"
        write_tree(self.root, {mine.relative_to(self.root).as_posix(): "mine\n"})
        run(self.root, "install", ["claude"])
        self.assertEqual((mine.read_text(), (self.root / SKILL).read_text()), ("mine\n", templates.SKILL))
        run(self.root, "remove", None)
        self.assertEqual(mine.read_text(), "mine\n")  # the directory it lives in is kept too
        self.assertFalse((self.root / SKILL).exists())


class UpdateTest(Project):
    def setUp(self):
        super().setUp()
        (self.root / "AGENTS.md").write_text("# Agents\n\nHouse rules.\n")
        run(self.root, "install", ["claude", "agents"])

    def test_update_is_a_no_op_when_current(self):
        before = tree(self.root)
        doc = run(self.root, "update", None)
        self.assertEqual(self.actions(doc), {"claude": "unchanged", "agents": "unchanged"})
        self.assertEqual(tree(self.root), before)

    def test_update_refreshes_an_outdated_skill_and_block(self):
        with mock.patch.object(templates, "SKILL", templates.SKILL + "\nNew paragraph.\n"), mock.patch.object(templates, "AGENTS_BLOCK", "## Repository health (repolife)\n\nNew text.\n"):
            self.assertEqual({r["profile"]: r["state"] for r in status(self.root)["targets"]}, {"claude": "installed-outdated", "agents": "installed-outdated"})
            doc = run(self.root, "update", None)
            self.assertEqual(self.actions(doc), {"claude": "update", "agents": "update"})
            self.assertTrue((self.root / SKILL).read_text().endswith("New paragraph.\n"))
            agents = (self.root / "AGENTS.md").read_bytes()
            self.assertTrue(agents.startswith(b"# Agents\n\nHouse rules.\n\n" + BEGIN.encode()))
            self.assertIn(b"New text.", agents)
            self.assertEqual(agents.count(BEGIN.encode()), 1)
            self.assertEqual({r["state"] for r in status(self.root)["targets"]}, {"installed-current"})

    def test_edits_outside_the_block_survive_an_update(self):
        agents = self.root / "AGENTS.md"
        agents.write_bytes(agents.read_bytes() + b"\nMy own section after the block.\n")
        with mock.patch.object(templates, "AGENTS_BLOCK", "## Repository health (repolife)\n\nNew text.\n"):
            doc = run(self.root, "update", ["agents"])
        self.assertEqual(self.actions(doc), {"agents": "update"})
        data = agents.read_bytes()
        self.assertTrue(data.startswith(b"# Agents\n\nHouse rules.\n\n") and data.endswith(b"\nMy own section after the block.\n"))
        self.assertIn(b"New text.", data)

    def test_edited_skill_is_a_conflict_and_nothing_is_written(self):
        skill = self.root / SKILL
        skill.write_text(skill.read_text() + "my note\n")
        before = tree(self.root)
        with mock.patch.object(templates, "AGENTS_BLOCK", "## Repository health (repolife)\n\nNew text.\n"):
            doc = run(self.root, "update", None)
        self.assertEqual(self.conflicts(doc), {"claude": "modified"})
        self.assertEqual(self.actions(doc), {"agents": "update"})
        self.assertEqual((doc["applied"], tree(self.root)), (False, before))  # one conflict blocks the other target too

    def test_edited_block_is_a_conflict(self):
        agents = self.root / "AGENTS.md"
        agents.write_bytes(agents.read_bytes().replace(b"repolife scan", b"repolife SCAN", 1))
        doc = run(self.root, "update", None)
        self.assertEqual(self.conflicts(doc), {"agents": "modified"})
        self.assertEqual(status(self.root)["targets"][1]["state"], "user-modified")

    def test_missing_skill_is_recreated(self):
        (self.root / SKILL).unlink()
        (self.root / SKILL).parent.rmdir()
        self.assertEqual({r["profile"]: r["state"] for r in status(self.root)["targets"]}["claude"], "missing")
        doc = run(self.root, "update", ["claude"])
        self.assertEqual(self.actions(doc), {"claude": "create"})
        self.assertEqual((self.root / SKILL).read_text(), templates.SKILL)
        self.assertEqual(self.receipt()["targets"][0]["dirs_created"], [".claude", ".claude/skills", ".claude/skills/repolife"])

    def test_unrecorded_profile_is_an_error(self):
        with self.assertRaises(IntegrationError):
            run(self.root, "update", ["codex"])
        code, out, _ = run_cli("integration", "update", str(self.root), "--agent", "codex", "--format", "json")
        self.assertEqual((code, out), (2, ""))


class RemoveTest(Project):
    def test_install_then_remove_restores_the_project(self):
        (self.root / "AGENTS.md").write_bytes(b"# Agents\n\nHouse rules.")
        before = tree(self.root)
        run(self.root, "install", ["claude", "codex", "agents"])
        doc = run(self.root, "remove", None)
        self.assertEqual(self.actions(doc), {"claude": "remove", "codex": "remove", "agents": "remove"})
        self.assertEqual((doc["receipt"]["action"], doc["notes"]), ("remove", []))
        self.assertEqual(tree(self.root), before)
        self.assertFalse((self.root / ".claude").exists() or (self.root / ".agents").exists())

    def test_remove_keeps_directories_it_did_not_create(self):
        write_tree(self.root, {".claude/settings.json": "{}\n"})
        run(self.root, "install", ["claude"])
        self.assertEqual(self.receipt()["targets"][0]["dirs_created"], [".claude/skills", ".claude/skills/repolife"])
        run(self.root, "remove", None)
        self.assertEqual(sorted(p.name for p in (self.root / ".claude").iterdir()), ["settings.json"])

    def test_remove_keeps_a_directory_that_gained_other_files(self):
        run(self.root, "install", ["claude"])
        write_tree(self.root, {".claude/skills/other/SKILL.md": "---\nname: other\n---\n"})
        run(self.root, "remove", None)
        self.assertFalse((self.root / SKILL).exists())
        self.assertFalse((self.root / ".claude/skills/repolife").exists())
        self.assertTrue((self.root / ".claude/skills/other/SKILL.md").exists())

    def test_subset_removal_keeps_the_rest(self):
        run(self.root, "install", ["claude", "codex"])
        doc = run(self.root, "remove", ["claude"])
        self.assertEqual(self.actions(doc), {"claude": "remove"})
        self.assertFalse((self.root / SKILL).exists())
        self.assertEqual((self.root / CODEX).read_text(), templates.SKILL)
        self.assertEqual(self.receipt()["profiles"], ["codex"])

    def test_edited_target_is_kept_and_stays_recorded(self):
        run(self.root, "install", ["claude", "agents"])
        (self.root / SKILL).write_text("mine now\n")
        before = tree(self.root)
        doc = run(self.root, "remove", None)
        self.assertEqual(self.conflicts(doc), {"claude": "modified"})
        self.assertEqual((doc["applied"], tree(self.root)), (False, before))
        self.assertEqual(self.receipt()["profiles"], ["claude", "agents"])

    def test_missing_target_is_forgotten_and_its_empty_directories_reclaimed(self):
        run(self.root, "install", ["claude"])
        (self.root / SKILL).unlink()
        doc = run(self.root, "remove", None)
        self.assertEqual((self.actions(doc), doc["receipt"]["action"]), ({"claude": "forget"}, "remove"))
        self.assertFalse((self.root / RECEIPT).exists())
        self.assertFalse((self.root / ".claude").exists())

    def test_forget_keeps_a_created_directory_that_is_no_longer_empty(self):
        run(self.root, "install", ["claude"])
        (self.root / SKILL).unlink()
        write_tree(self.root, {".claude/skills/other.md": "x\n"})
        run(self.root, "remove", None)
        self.assertFalse((self.root / ".claude/skills/repolife").exists())
        self.assertTrue((self.root / ".claude/skills/other.md").exists())

    def test_removing_a_profile_that_is_not_recorded_is_a_no_op(self):
        run(self.root, "install", ["claude", "codex"])
        run(self.root, "remove", ["codex"])
        before = tree(self.root)
        doc = run(self.root, "remove", ["codex"])
        self.assertEqual((doc["actions"], doc["conflicts"], doc["receipt"]["action"]), ([], [], "unchanged"))
        self.assertEqual(tree(self.root), before)
        self.assertEqual(self.receipt()["profiles"], ["claude"])
        code, _, _ = run_cli("integration", "remove", str(self.root), "--agent", "codex")
        self.assertEqual(code, 0)
        run(self.root, "remove", None)
        self.assertEqual(run_cli("integration", "remove", str(self.root), "--agent", "codex")[0], 0)

    def test_created_agents_file_with_user_additions_is_kept(self):
        run(self.root, "install", ["agents"])
        agents = self.root / "AGENTS.md"
        agents.write_bytes(agents.read_bytes() + b"\nMine.\n")
        run(self.root, "remove", None)
        self.assertEqual(agents.read_bytes(), b"\nMine.\n")

    def test_pre_existing_agents_file_is_never_deleted(self):
        (self.root / "AGENTS.md").write_bytes(b"")
        run(self.root, "install", ["agents"])
        run(self.root, "remove", None)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), b"")

    def test_remove_without_a_receipt_is_a_no_op(self):
        mount(self.root, {"claude", "agents"}, None, "repolife")  # legacy init: familiar files, no receipt
        before = tree(self.root)
        for profiles in (None, ["claude"]):
            doc = run(self.root, "remove", profiles)
            self.assertEqual((doc["actions"], doc["conflicts"], doc["receipt"]["action"]), ([], [], "unchanged"))
        self.assertEqual(tree(self.root), before)
        code, out, _ = run_cli("integration", "remove", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("Nothing to do.", out)


class StatusTest(Project):
    def test_nothing_installed(self):
        doc = status(self.root)
        self.assertEqual((doc["installed"], doc["targets"], doc["attention"]), (False, [], False))
        code, out, _ = run_cli("integration", "status", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("No repolife integration receipt", out)

    def test_legacy_files_are_unmanaged(self):
        mount(self.root, {"claude", "agents"}, None, "repolife")
        doc = status(self.root)
        self.assertEqual(doc["installed"], False)
        self.assertEqual({r["profile"]: r["state"] for r in doc["targets"]}, {"claude": "unmanaged", "agents": "unmanaged"})

    def test_states(self):
        run(self.root, "install", ["claude", "codex", "agents"])
        doc = status(self.root)
        self.assertEqual(({r["state"] for r in doc["targets"]}, doc["attention"], doc["installed_by"]), ({"installed-current"}, False, integration.__version__))
        (self.root / SKILL).write_text("edited\n")
        (self.root / CODEX).unlink()
        doc = status(self.root)
        self.assertEqual({r["profile"]: r["state"] for r in doc["targets"]}, {"claude": "user-modified", "codex": "missing", "agents": "installed-current"})
        self.assertTrue(doc["attention"])
        code, out, _ = run_cli("integration", "status", str(self.root), "--format", "json")
        self.assertEqual((code, json.loads(out)["kind"]), (0, "integration-status"))


class ReceiptTest(Project):
    def write_receipt(self, text: str) -> None:
        (self.root / RECEIPT).write_text(text)

    def test_corrupt_receipt_blocks_every_operation(self):
        run(self.root, "install", ["claude"])
        self.write_receipt("{not json")
        before = tree(self.root)
        for op, profiles in (("install", ["codex"]), ("update", None), ("remove", None)):
            with self.assertRaises(IntegrationError):
                run(self.root, op, profiles)
        with self.assertRaises(IntegrationError):
            status(self.root)
        self.assertEqual(tree(self.root), before)
        code, out, err = run_cli("integration", "status", str(self.root), "--format", "json")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("not valid JSON", err)

    def test_unsupported_version(self):
        self.write_receipt(json.dumps({"manifest_version": 99, "targets": []}))
        with self.assertRaisesRegex(IntegrationError, "manifest_version 99"):
            status(self.root)

    def test_forged_target_path(self):
        target = {"profile": "claude", "path": "../outside.md", "kind": "file", "sha256": "0" * 64, "created": True, "dirs_created": []}
        self.write_receipt(json.dumps({"manifest_version": 1, "targets": [target]}))
        with self.assertRaisesRegex(IntegrationError, "only .claude/skills/repolife/SKILL.md"):
            run(self.root, "remove", None)

    def test_forged_directory_and_duplicate_profile(self):
        good = {"profile": "claude", "path": SKILL, "kind": "file", "sha256": "0" * 64, "created": True, "dirs_created": ["src"]}
        self.write_receipt(json.dumps({"manifest_version": 1, "targets": [good]}))
        with self.assertRaisesRegex(IntegrationError, "not a parent"):
            status(self.root)
        good["dirs_created"] = []
        self.write_receipt(json.dumps({"manifest_version": 1, "targets": [good, dict(good)]}))
        with self.assertRaisesRegex(IntegrationError, "recorded twice"):
            status(self.root)

    def test_span_must_match_its_hash(self):
        target = {"profile": "agents", "path": "AGENTS.md", "kind": "span", "sha256": "0" * 64, "created": True, "dirs_created": [], "span": f"{BEGIN}\nx\n{END}\n"}
        self.write_receipt(json.dumps({"manifest_version": 1, "targets": [target]}))
        with self.assertRaisesRegex(IntegrationError, "does not match its hash"):
            status(self.root)

    @unittest.skipIf(sys.platform == "win32", "symlinks")
    def test_symlinked_receipt_is_an_error(self):
        (self.root / "real.json").write_text(json.dumps({"manifest_version": 1, "targets": []}))
        (self.root / RECEIPT).symlink_to(self.root / "real.json")
        with self.assertRaisesRegex(IntegrationError, "symlink"):
            run(self.root, "install", ["claude"])
        self.assertFalse((self.root / SKILL).exists())


class ConcurrencyTest(Project):
    def test_existing_lock_is_a_reported_conflict_and_is_kept(self):
        (self.root / LOCK).write_text("12345\n")
        before = tree(self.root)
        doc = run(self.root, "install", ["claude"])
        self.assertEqual([c["reason"] for c in doc["conflicts"]], ["busy"])
        self.assertEqual(tree(self.root), before)
        self.assertEqual((self.root / LOCK).read_text(), "12345\n")
        code, _, _ = run_cli("integration", "install", str(self.root), "--agent", "claude")
        self.assertEqual(code, 1)

    def test_lock_is_released_and_dry_run_takes_none(self):
        run(self.root, "install", ["claude"], dry_run=True)
        self.assertFalse((self.root / LOCK).exists())
        run(self.root, "install", ["claude"])
        self.assertFalse((self.root / LOCK).exists())

    def test_lock_write_failure_leaves_no_lock_behind(self):
        with mock.patch.object(integration.os, "write", side_effect=OSError(28, "No space left on device")):
            with self.assertRaisesRegex(IntegrationError, "cannot write"):
                run(self.root, "install", ["claude"])
        self.assertFalse((self.root / LOCK).exists())
        self.assertFalse((self.root / SKILL).exists())

    def test_input_changed_between_plan_and_apply_is_a_conflict(self):
        real_plan = integration.plan
        calls = []

        def racing_plan(root, op, profiles):
            calls.append(1)
            if len(calls) == 2:  # the recheck sees a file that appeared after the first plan
                write_tree(root, {SKILL: "someone else's\n"})
            return real_plan(root, op, profiles)

        with mock.patch.object(integration, "plan", racing_plan):
            doc = run(self.root, "install", ["claude"])
        self.assertIn("changed", [c["reason"] for c in doc["conflicts"]])
        self.assertEqual((doc["applied"], (self.root / SKILL).read_text()), (False, "someone else's\n"))
        self.assertFalse((self.root / RECEIPT).exists() or (self.root / LOCK).exists())


class RollbackTest(Project):
    def failing_codex_write(self):
        real = integration._atomic_write

        def flaky(path, data, mode):
            if ".agents" in path.parts:  # the second target's write fails after the first one succeeded
                raise OSError(28, "No space left on device", str(path))
            return real(path, data, mode)

        return mock.patch.object(integration, "_atomic_write", flaky)

    def test_failure_on_a_later_target_rolls_the_earlier_one_back(self):
        (self.root / "AGENTS.md").write_bytes(b"# Agents\n")
        before = tree(self.root)
        with self.failing_codex_write():
            with self.assertRaisesRegex(IntegrationError, "No space left on device; every earlier change was rolled back"):
                run(self.root, "install", ["claude", "codex", "agents"])
        self.assertEqual(tree(self.root), before)
        self.assertFalse((self.root / ".claude").exists() or (self.root / ".agents").exists())
        self.assertFalse((self.root / LOCK).exists())
        with self.failing_codex_write():
            code, out, err = run_cli("integration", "install", str(self.root), "--agent", "claude", "--agent", "codex", "--format", "json")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("rolled back", err)

    def test_unreadable_target_is_an_error_before_any_write(self):
        (self.root / ".agents").write_text("not a directory\n")  # the codex target cannot even be read
        before = tree(self.root)
        with self.assertRaisesRegex(IntegrationError, "cannot read"):
            run(self.root, "install", ["claude", "codex"])
        self.assertEqual(tree(self.root), before)


class CliTextTest(Project):
    def test_dry_run_text(self):
        code, out, _ = run_cli("integration", "install", str(self.root), "--agent", "claude", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would create  .claude/skills/repolife/SKILL.md (claude)", out)
        self.assertIn(f"would create  {RECEIPT}", out)
        self.assertIn("Dry run: nothing was written.", out)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [".gitignore", "README.md", "src"])

    def test_conflict_text_and_exit_code(self):
        write_tree(self.root, {CODEX: "foreign\n"})
        code, out, _ = run_cli("integration", "install", str(self.root), "--agent", "codex")
        self.assertEqual(code, 1)
        self.assertIn("conflict      .agents/skills/repolife/SKILL.md (codex): a file already exists", out)
        self.assertIn("nothing was written", out)

    def test_missing_or_non_directory_project_exits_2(self):
        for path in (str(self.root / "nope"), str(self.root / "README.md")):
            code, out, err = run_cli("integration", "status", path)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("not a directory", err)

    def test_skill_profiles_share_one_source(self):
        self.assertEqual(PROFILES["claude"].content(), PROFILES["codex"].content())
        self.assertNotIn(".repolife/report.json", templates.SKILL)
        self.assertNotIn("uvx", templates.SKILL)
        self.assertIn("unavailable", templates.SKILL)
        self.assertNotIn("--fail-on block     #", templates.SKILL)  # the routine example does not gate
        self.assertIn("do not start every task with a full scan", templates.SKILL)
        self.assertLess(templates.SKILL.index("repolife impact <path>"), templates.SKILL.index("## Run it"))


if __name__ == "__main__":
    unittest.main()
