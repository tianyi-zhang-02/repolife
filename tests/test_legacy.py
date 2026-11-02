"""The old name keeps working through 0.2.x: the `repolife` command and module, the old configuration names, an
integration written by an older version, the old AGENTS.md markers and the old plugin entry-point group. And the new
package never spells the old name outside `tessri/legacy.py`."""

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import unittest
import warnings
from pathlib import Path
from unittest import mock

from helpers import TempRepo, write_tree

from tessri import __version__, config, legacy, templates
from tessri.cli import legacy_main, main
from tessri.integration import RECEIPT, run, status, text
from tessri.mount import BEGIN, END, mount

ROOT = Path(__file__).resolve().parent.parent
OLD_SKILL = legacy.SKILL_PATHS["claude"]
OLD_SPAN = f"\n{legacy.BEGIN}\n## Repository health (repolife)\n\nold text\n{legacy.END}\n"
OLD_SKILL_TEXT = b"old skill text\n"


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def tree(root: Path) -> dict[str, bytes]:
    out = {}
    for base, _dirs, files in os.walk(root):
        for name in files:
            p = Path(base) / name
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ShimTest(TempRepo):
    def test_import_repolife_warns_and_forwards_to_tessri(self):
        sys.modules.pop("repolife", None)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            import repolife  # noqa: F401  (the shim)
        self.assertTrue(any(w.category is DeprecationWarning and "tessri" in str(w.message) for w in caught))
        self.assertEqual(repolife.__version__, __version__)
        import tessri.cli

        self.assertIs(repolife.cli, tessri.cli)
        with self.assertRaises(AttributeError):
            repolife.no_such_module  # noqa: B018

    def test_the_old_command_runs_the_program_after_a_notice(self):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        old = subprocess.run([sys.executable, "-m", "repolife", "--version"], cwd=ROOT, env=env, capture_output=True, text=True)
        new = subprocess.run([sys.executable, "-m", "tessri", "--version"], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual((old.returncode, old.stdout), (0, f"tessri {__version__}\n"))
        self.assertIn(legacy.NOTICE, old.stderr)
        self.assertEqual((new.returncode, new.stdout, new.stderr), (0, f"tessri {__version__}\n", ""))

    def test_legacy_main_is_main_with_a_notice(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = legacy_main(["integration", "status", str(self.root)])
        self.assertEqual(code, 0)
        self.assertTrue(err.getvalue().startswith(f"tessri: {legacy.NOTICE}\n"))
        self.assertIn("No Tessri integration receipt", out.getvalue())


class ConfigTest(TempRepo):
    def test_the_old_dotfile_is_read_when_the_new_is_absent(self):
        write_tree(self.root, {legacy.CONFIG_FILE: "active_days = 7\n"})
        cfg = config.load(self.root)
        self.assertEqual(cfg.active_days, 7)
        self.assertEqual(cfg.notes, [f"read {legacy.CONFIG_FILE}; rename it to .tessri.toml (the old name is read through 0.2.x)"])

    def test_the_new_dotfile_wins_and_the_old_is_noted(self):
        write_tree(self.root, {legacy.CONFIG_FILE: "active_days = 7\n", ".tessri.toml": "active_days = 9\n"})
        cfg = config.load(self.root)
        self.assertEqual((cfg.active_days, cfg.notes), (9, [f"{legacy.CONFIG_FILE} ignored because .tessri.toml exists"]))

    def test_the_old_pyproject_section(self):
        write_tree(self.root, {"pyproject.toml": f"[tool.{legacy.CONFIG_SECTION}]\ntop = 3\n"})
        cfg = config.load(self.root)
        self.assertEqual(cfg.top, 3)
        self.assertEqual(cfg.notes, [f"pyproject.toml: read [tool.{legacy.CONFIG_SECTION}]; rename the section to [tool.tessri] (the old name is read through 0.2.x)"])
        write_tree(self.root, {"pyproject.toml": f"[tool.{legacy.CONFIG_SECTION}]\ntop = 3\n[tool.tessri]\ntop = 4\n"})
        cfg = config.load(self.root)
        self.assertEqual((cfg.top, cfg.notes), (4, [f"pyproject.toml: [tool.{legacy.CONFIG_SECTION}] ignored because [tool.tessri] exists"]))

    def test_new_names_make_no_note(self):
        write_tree(self.root, {".tessri.toml": "top = 3\n", "pyproject.toml": "[tool.tessri]\ndepth = 2\n"})
        cfg = config.load(self.root)
        self.assertEqual((cfg.top, cfg.depth, cfg.notes), (3, 2, []))

    def test_the_cli_says_so_on_stderr(self):
        write_tree(self.root, {legacy.CONFIG_FILE: "active_days = 7\n", "a.py": "x = 1\n"})
        code, out, err = run_cli("scan", str(self.root), "--format", "json")
        self.assertEqual(code, 0)
        self.assertIn(f"tessri: read {legacy.CONFIG_FILE}", err)
        self.assertEqual(json.loads(out)["settings"]["active_days"], 7)
        (self.root / legacy.CONFIG_FILE).rename(self.root / ".tessri.toml")
        code, _, err = run_cli("scan", str(self.root), "--format", "json")
        self.assertEqual((code, err), (0, ""))


def old_project(root: Path) -> None:
    """A project as 0.1.x left it: skill under the old path, old markers in AGENTS.md, a receipt under the old name."""
    write_tree(root, {"src/app.py": "x = 1\n", "AGENTS.md": "# demo\n" + OLD_SPAN})
    skill = root / OLD_SKILL
    skill.parent.mkdir(parents=True)
    skill.write_bytes(OLD_SKILL_TEXT)
    receipt = {
        "manifest_version": 1,
        "tool": {"name": legacy.OLD_NAME, "version": "0.1.0"},
        "profiles": ["claude", "agents"],
        "targets": [
            {"profile": "claude", "path": OLD_SKILL, "kind": "file", "sha256": sha(OLD_SKILL_TEXT), "created": True, "dirs_created": [".claude", ".claude/skills", ".claude/skills/repolife"]},
            {"profile": "agents", "path": "AGENTS.md", "kind": "span", "sha256": sha(OLD_SPAN.encode()), "created": False, "dirs_created": [], "span": OLD_SPAN},
        ],
    }
    (root / legacy.RECEIPT).write_text(json.dumps(receipt, indent=2) + "\n")


class OldIntegrationTest(TempRepo):
    def setUp(self):
        super().setUp()
        old_project(self.root)

    def test_status_reads_the_old_receipt_under_its_recorded_paths(self):
        doc = status(self.root)
        self.assertEqual((doc["installed"], doc["installed_by"], doc["receipt_path"], doc["profiles"]), (True, "0.1.0", legacy.RECEIPT, ["claude", "agents"]))
        rows = {r["profile"]: (r["path"], r["state"], r["recorded"]) for r in doc["targets"]}
        self.assertEqual(rows["claude"], (OLD_SKILL, "installed-outdated", True))
        self.assertEqual(rows["agents"], ("AGENTS.md", "installed-outdated", True))
        self.assertTrue(doc["attention"])
        self.assertIn(f"Receipt {legacy.RECEIPT}: profiles claude, agents, installed by 0.1.0.", text(doc))

    def test_a_dry_run_shows_the_move_and_writes_nothing(self):
        before = tree(self.root)
        doc = run(self.root, "update", None, dry_run=True)
        self.assertEqual([(a["profile"], a["action"], a["path"]) for a in doc["actions"]], [("claude", "create", ".claude/skills/tessri/SKILL.md"), ("claude", "remove", OLD_SKILL), ("agents", "update", "AGENTS.md")])
        self.assertEqual(doc["receipt"], {"path": RECEIPT, "action": "create", "replaces": legacy.RECEIPT})
        self.assertEqual(tree(self.root), before)
        shown = text(doc)
        self.assertIn(f"would create  {RECEIPT}", shown)
        self.assertIn(f"would remove  {legacy.RECEIPT}", shown)

    def test_update_moves_everything_to_the_new_names_in_one_run(self):
        doc = run(self.root, "update", None)
        self.assertTrue(doc["applied"])
        new_skill = self.root / ".claude/skills/tessri/SKILL.md"
        self.assertEqual(new_skill.read_text(), templates.SKILL)
        self.assertFalse((self.root / OLD_SKILL).exists())
        self.assertFalse((self.root / OLD_SKILL).parent.exists())  # the old leaf directory is cleaned up
        agents = (self.root / "AGENTS.md").read_text()
        self.assertTrue(agents.startswith("# demo\n\n" + BEGIN + "\n"))
        self.assertEqual((agents.count(BEGIN), agents.count(END), legacy.BEGIN in agents, legacy.END in agents), (1, 1, False, False))
        self.assertFalse((self.root / legacy.RECEIPT).exists())
        receipt = json.loads((self.root / RECEIPT).read_text())
        self.assertEqual(receipt["tool"]["name"], "tessri")
        by = {t["profile"]: t for t in receipt["targets"]}
        self.assertEqual((by["claude"]["path"], by["claude"]["dirs_created"]), (".claude/skills/tessri/SKILL.md", [".claude", ".claude/skills", ".claude/skills/tessri"]))
        self.assertIn(BEGIN, by["agents"]["span"])
        after = status(self.root)
        self.assertEqual({r["profile"]: r["state"] for r in after["targets"]}, {"claude": "installed-current", "agents": "installed-current"})
        self.assertEqual(after["receipt_path"], RECEIPT)
        # and the whole thing comes out again, directories included
        doc = run(self.root, "remove", None)
        self.assertTrue(doc["applied"])
        self.assertEqual((self.root / "AGENTS.md").read_text(), "# demo\n")
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / RECEIPT).exists())

    def test_a_modified_old_file_is_a_conflict_and_nothing_moves(self):
        (self.root / OLD_SKILL).write_bytes(OLD_SKILL_TEXT + b"my note\n")
        before = tree(self.root)
        doc = run(self.root, "update", None)
        self.assertFalse(doc["applied"])
        self.assertEqual([(c["profile"], c["reason"], c["path"]) for c in doc["conflicts"]], [("claude", "modified", OLD_SKILL)])
        self.assertEqual(tree(self.root), before)

    def test_a_file_already_at_the_new_path_is_a_conflict(self):
        write_tree(self.root, {".claude/skills/tessri/SKILL.md": "mine\n"})
        before = tree(self.root)
        doc = run(self.root, "update", ["claude"])
        self.assertEqual([(c["profile"], c["reason"], c["path"]) for c in doc["conflicts"]], [("claude", "unmanaged", ".claude/skills/tessri/SKILL.md")])
        self.assertEqual(tree(self.root), before)

    def test_remove_takes_an_old_integration_out_without_creating_the_new_receipt(self):
        doc = run(self.root, "remove", None)
        self.assertTrue(doc["applied"])
        self.assertEqual([(a["profile"], a["action"], a["path"]) for a in doc["actions"]], [("claude", "remove", OLD_SKILL), ("agents", "remove", "AGENTS.md")])
        self.assertEqual(doc["receipt"], {"path": RECEIPT, "action": "remove", "replaces": legacy.RECEIPT})
        self.assertEqual((self.root / "AGENTS.md").read_text(), "# demo\n")
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / legacy.RECEIPT).exists())
        self.assertFalse((self.root / RECEIPT).exists())

    def test_installing_another_profile_keeps_the_old_target_and_renames_the_receipt(self):
        doc = run(self.root, "install", ["codex"])
        self.assertTrue(doc["applied"])
        self.assertFalse((self.root / legacy.RECEIPT).exists())
        receipt = json.loads((self.root / RECEIPT).read_text())
        self.assertEqual({t["profile"]: t["path"] for t in receipt["targets"]}, {"claude": OLD_SKILL, "agents": "AGENTS.md", "codex": ".agents/skills/tessri/SKILL.md"})
        self.assertTrue((self.root / OLD_SKILL).exists())  # not touched: only the selected profile was installed
        doc = run(self.root, "update", None)  # the next update moves it
        self.assertTrue(doc["applied"])
        self.assertFalse((self.root / OLD_SKILL).exists())
        self.assertTrue((self.root / ".claude/skills/tessri/SKILL.md").exists())

    def test_an_unrecorded_old_skill_file_shows_as_unmanaged(self):
        (self.root / legacy.RECEIPT).unlink()
        rows = {(r["profile"], r["path"]): r["state"] for r in status(self.root)["targets"]}
        self.assertEqual(rows, {("claude", OLD_SKILL): "unmanaged", ("agents", "AGENTS.md"): "unmanaged"})


class MountTest(TempRepo):
    def test_init_replaces_a_block_written_under_the_old_markers(self):
        write_tree(self.root, {"AGENTS.md": "# demo\n" + OLD_SPAN + "\nmore\n"})
        actions = {a.path: a.verb for a in mount(self.root, {"agents"}, None, "tessri")}
        self.assertEqual(actions["AGENTS.md"], "updated")
        agents = (self.root / "AGENTS.md").read_text()
        self.assertEqual((agents.count(BEGIN), agents.count(END), legacy.BEGIN in agents), (1, 1, False))
        self.assertTrue(agents.startswith("# demo\n\n" + BEGIN) and agents.endswith(END + "\n\nmore\n"))
        self.assertEqual({a.path: a.verb for a in mount(self.root, {"agents"}, None, "tessri")}["AGENTS.md"], "unchanged")


class PluginGroupTest(unittest.TestCase):
    def test_plugins_registered_under_the_old_group_still_load(self):
        from tessri.analyzers import load_analyzers
        from tessri.analyzers.python import PythonAnalyzer

        class Plugin(PythonAnalyzer):
            name = "plugin-under-the-old-group"

        class EntryPoint:
            def load(self):
                return Plugin

        def fake_entry_points(group):
            return [EntryPoint()] if group == legacy.ENTRY_POINT_GROUP else []

        with mock.patch("tessri.analyzers.metadata.entry_points", fake_entry_points):
            names = [a.name for a in load_analyzers()]
        self.assertIn("plugin-under-the-old-group", names)


class GuardTest(unittest.TestCase):
    def test_the_old_name_lives_only_in_the_legacy_module(self):
        offenders = []
        for path in sorted((ROOT / "tessri").rglob("*.py")):
            if path.name != "legacy.py" and legacy.OLD_NAME in path.read_text(encoding="utf-8").lower():
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])
        self.assertNotIn(legacy.OLD_NAME, (ROOT / "skills/tessri/SKILL.md").read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
