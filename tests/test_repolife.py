import contextlib
import io
import json
import time
import unittest
from pathlib import Path

from helpers import TempRepo, git, write_tree
from repolife import config, inventory, templates
from repolife.analyze import analyze
from repolife.cli import main
from repolife.explain import TargetError, explain
from repolife.model import SCHEMA_VERSION
from repolife.mount import BEGIN, END, mount
from repolife.report import build_report

TREE = {
    "pkg/__init__.py": "",
    "pkg/core.py": "from pkg import util\n\ndef run():\n    return util.x\n",
    "pkg/util.py": "x = 1\n",
    "pkg/dead.py": "from pkg import dead_dep\n\ndef f():\n    return dead_dep.y\n",
    "pkg/dead_dep.py": "y = 2\n",
    "pkg/only_tested.py": "z = 3\n",
    "pkg/plugin_a.py": "class Plugin:\n    pass\n",
    "pkg/api.py": "def public():\n    return 1\n",
    "pkg/cli.py": "def main():\n    return 0\n",
    "pkg/backend.py": "class W:\n    pass\n",
    "pkg/worker.py": 'def load(name):\n    return "pkg.backend." + name\n',
    "pkg/dyn/__init__.py": 'import importlib\nfor n in ("x", "y"):\n    importlib.import_module(f".{n}", __name__)\n',
    "pkg/dyn/x.py": "a = 1\n",
    "pkg/dyn/y.py": "b = 1\n",
    "pkg/dyn/z.py": "c = 1\n",
    "scripts/run.py": "from pkg import core, worker, dyn\n\nif __name__ == '__main__':\n    core.run()\n",
    "tests/test_core.py": "from pkg import core, only_tested\n\ndef test_x():\n    assert core and only_tested\n",
    "conf/plugins.yaml": "plugin:\n  _target_: pkg.plugin_a.Plugin\n",
    "pyrefly.toml": 'project-includes = ["pkg/dead.py", "pkg/dead_dep.py"]\n',
    "docs/guide.md": "See pkg.dead for details.\n",
    "pyproject.toml": '[project]\nname = "demo"\nversion = "0"\n[project.scripts]\ncli = "pkg.cli:main"\n[tool.repolife]\nkeep = ["pkg/api.py"]\n',
    "lib/x.go": "package lib\n",
}


class LineCountTest(unittest.TestCase):
    def test_python_docstring_lines_are_comments(self):
        lang = inventory.language_of("a.py")
        code, comment, blank = inventory.count_lines('"""doc\nmore"""\n# c\n\nx = 1\n', lang, {1, 2})
        self.assertEqual((code, comment, blank), (1, 3, 1))

    def test_c_block_comments(self):
        lang = inventory.language_of("a.c")
        self.assertEqual(inventory.count_lines("/* a\n b */\nint x;\n// c\n", lang), (1, 3, 0))

    def test_variant_suffix_keeps_config_but_not_code(self):
        self.assertEqual(inventory.language_of("recipe.yaml.disabled").name, "YAML")
        self.assertIsNone(inventory.language_of("script.py.disabled"))


class ReachabilityTest(TempRepo):
    def setUp(self):
        super().setUp()
        write_tree(self.root, TREE)
        self.a = analyze(self.root, config.load(self.root))

    def status(self, path):
        return self.a.records[path].status

    def test_orphans_and_their_private_dependencies(self):
        orphans = {p for p, r in self.a.records.items() if r.status == "ORPHAN"}
        self.assertEqual(orphans, {"pkg/dead.py", "pkg/dead_dep.py", "pkg/dyn/z.py"})

    def test_tooling_config_does_not_rescue_a_module(self):
        self.assertEqual(self.a.records["pkg/dead.py"].reachability, "none")

    def test_docs_mention_lowers_confidence_but_does_not_rescue(self):
        self.assertEqual(self.a.records["pkg/dead.py"].confidence, "medium")
        self.assertEqual(self.a.records["pkg/dead_dep.py"].confidence, "high")
        self.assertIn("only referenced by other unreachable files", self.a.records["pkg/dead_dep.py"].notes)

    def test_entry_points_and_wiring_keep_files_alive(self):
        for path in ("pkg/cli.py", "pkg/plugin_a.py", "pkg/api.py", "scripts/run.py"):
            self.assertEqual(self.a.records[path].reachability, "prod", path)
        self.assertEqual(self.a.records["pkg/cli.py"].roots, ["config-ref: pyproject.toml"])
        self.assertIn("keep", self.a.records["pkg/api.py"].roots)

    def test_dynamic_imports(self):
        self.assertEqual(self.a.records["pkg/backend.py"].reachability, "prod")  # "pkg.backend." + name
        self.assertEqual(self.a.records["pkg/dyn/x.py"].reachability, "prod")  # loop over literal names
        self.assertEqual(self.a.records["pkg/dyn/y.py"].reachability, "prod")

    def test_test_only_code(self):
        self.assertEqual(self.a.records["pkg/only_tested.py"].reachability, "test")
        self.assertTrue(self.a.records["tests/test_core.py"].is_test)
        self.assertNotEqual(self.status("pkg/only_tested.py"), "ORPHAN")

    def test_languages_without_an_analyzer_are_not_guessed(self):
        rec = self.a.records["lib/x.go"]
        self.assertIsNone(rec.reachability)
        self.assertIsNone(rec.analyzer)
        self.assertNotEqual(rec.status, "ORPHAN")

    def test_unparsable_python_is_an_entry_point(self):
        write_tree(self.root, {"legacy.py": "print 'py2'\n"})
        a = analyze(self.root, config.load(self.root))
        self.assertEqual(a.records["legacy.py"].reachability, "prod")
        self.assertIn("legacy.py", a.unparsed)

    def test_stranded_if_removed(self):
        self.assertEqual(self.a.graph.stranded_if_removed("pkg/core.py"), ["pkg/util.py"])

    def test_why_explains_both_sides(self):
        self.assertIn("NOT reachable", explain(self.a, "pkg/dead_dep.py"))
        text = explain(self.a, "pkg.core")
        self.assertIn("scripts/run.py -> pkg/core.py", text)
        self.assertIn("deleting it would also strand: pkg/util.py", text)
        with self.assertRaises(TargetError):
            explain(self.a, "does/not/exist.py")


class ActivityTest(TempRepo):
    def test_status_follows_git_history(self):
        write_tree(self.root, {"old.py": "a = 1\n"})
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "old", when="2022-01-01T00:00:00")
        write_tree(self.root, {"new.py": "b = 1\n", "main.py": "import old, new\nif __name__ == '__main__':\n    pass\n"})
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "new")
        write_tree(self.root, {"fresh_orphan.py": "c = 1\n"})  # never committed

        a = analyze(self.root, config.load(self.root), now=time.time())
        self.assertEqual(a.records["old.py"].status, "DORMANT")
        self.assertEqual(a.records["new.py"].status, "ACTIVE")
        self.assertEqual(a.records["old.py"].first_commit, "2022-01-01")
        rec = a.records["fresh_orphan.py"]
        self.assertEqual((rec.status, rec.confidence), ("ORPHAN", "medium"))
        self.assertIn("not in git history yet", rec.notes[0])

    def test_without_git_activity_is_unknown(self):
        write_tree(self.root, {"a.py": "x = 1\n", "b.py": "import a\nif __name__ == '__main__':\n    pass\n"})
        a = analyze(self.root, config.load(self.root))
        self.assertEqual(a.records["a.py"].status, "UNKNOWN")
        self.assertIsNone(a.activity)


class ReportAndCliTest(TempRepo):
    def setUp(self):
        super().setUp()
        write_tree(self.root, TREE)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_json_report_contract(self):
        code, out = self.run_cli("scan", str(self.root), "--format", "json", "--full")
        self.assertEqual(code, 0)
        rep = json.loads(out)
        self.assertEqual(rep["schema_version"], SCHEMA_VERSION)
        for key in ("tool", "generated_at", "repo", "git", "settings", "summary", "languages", "directories",
                    "largest_files", "hotspots", "cleanup", "analysis", "caveats", "files"):
            self.assertIn(key, rep)
        self.assertEqual(rep["summary"]["orphans"]["files"], 3)
        self.assertEqual(rep["cleanup"]["orphan_files"][0]["confidence"], "high")  # most confident first
        self.assertEqual(rep["analysis"]["unanalyzed_languages"], {"Go": {"files": 1, "code": 1}})

    def test_markdown_report_and_why(self):
        code, out = self.run_cli("scan", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("## Cleanup candidates", out)
        self.assertIn("`pkg/dyn/z.py`", out)
        code, out = self.run_cli("why", "pkg/dyn/z.py", "--repo", str(self.root))
        self.assertEqual((code, "ORPHAN" in out), (0, True))

    def test_cli_flags_extend_config(self):
        code, out = self.run_cli("scan", str(self.root), "--format", "json", "--keep", "pkg/dyn/z.py")
        rep = json.loads(out)
        self.assertNotIn("pkg/dyn/z.py", [o["path"] for o in rep["cleanup"]["orphan_files"]])
        self.assertIn("pkg/api.py", rep["settings"]["keep"])  # from pyproject [tool.repolife]

    def test_bad_config_is_a_clean_error(self):
        (self.root / ".repolife.toml").write_text("bogus = 1\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["scan", str(self.root)])
        self.assertEqual(code, 2)
        self.assertIn("unknown option `bogus`", err.getvalue())

    def test_report_is_deterministic(self):
        cfg = config.load(self.root)
        now = time.time()
        first = build_report(analyze(self.root, cfg, now=now))
        second = build_report(analyze(self.root, cfg, now=now))
        self.assertEqual(first, second)


class MountTest(TempRepo):
    def test_init_is_idempotent_and_non_destructive(self):
        (self.root / "AGENTS.md").write_text("# Agents\n\nExisting guidance.\n")
        (self.root / ".gitignore").write_text("node_modules/\n")

        first = {a.path: a.verb for a in mount(self.root, {"claude", "agents"}, "github", "git+https://example.com/repolife", False, False)}
        self.assertEqual(first[".repolife.toml"], "created")
        self.assertEqual(first["AGENTS.md"], "updated")
        agents = (self.root / "AGENTS.md").read_text()
        self.assertTrue(agents.startswith("# Agents\n\nExisting guidance."))
        self.assertEqual(agents.count(BEGIN), 1)
        self.assertIn("git+https://example.com/repolife", (self.root / ".github/workflows/repolife.yml").read_text())
        self.assertEqual((self.root / ".gitignore").read_text(), "node_modules/\n.repolife/\n")

        second = {a.verb for a in mount(self.root, {"claude", "agents"}, "github", "git+https://example.com/repolife", False, False)}
        self.assertEqual(second, {"unchanged"})

    def test_edited_files_are_left_alone_unless_forced(self):
        mount(self.root, {"claude"}, None, "repolife")
        skill = self.root / ".claude/skills/repolife/SKILL.md"
        skill.write_text("my edits\n")
        self.assertEqual({a.path: a.verb for a in mount(self.root, {"claude"}, None, "repolife")}[".claude/skills/repolife/SKILL.md"], "skipped")
        self.assertEqual(skill.read_text(), "my edits\n")
        mount(self.root, {"claude"}, None, "repolife", force=True)
        self.assertEqual(skill.read_text(), templates.SKILL)

    def test_marked_block_is_updated_in_place(self):
        (self.root / "AGENTS.md").write_text(f"top\n{BEGIN}\nstale\n{END}\nbottom\n")
        mount(self.root, {"agents"}, None, "repolife")
        text = (self.root / "AGENTS.md").read_text()
        self.assertTrue(text.startswith("top\n") and text.endswith("\nbottom\n"))
        self.assertNotIn("stale", text)

    def test_dry_run_writes_nothing(self):
        actions = mount(self.root, {"claude", "agents"}, "github", "repolife", dry_run=True)
        self.assertTrue(actions)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_works_in_an_empty_new_repo(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["init", str(self.root), "--agent", "none"]), 0)
        self.assertTrue((self.root / ".repolife.toml").exists())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["scan", str(self.root), "--format", "json"]), 0)
        self.assertEqual(json.loads(out.getvalue())["summary"]["orphans"]["files"], 0)


class PluginFilesTest(unittest.TestCase):
    def test_bundled_skill_matches_template(self):
        bundled = Path(__file__).resolve().parent.parent / "skills/repolife/SKILL.md"
        self.assertEqual(bundled.read_text(), templates.SKILL)


if __name__ == "__main__":
    unittest.main()
