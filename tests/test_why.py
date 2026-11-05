"""`tessri why` as data: `facts` holds everything the text says, the text is rendered from it, and
`--format json` prints it with the metadata block."""

import contextlib
import io
import json
import time
import unittest

from helpers import TempRepo, git, write_tree

from tessri import config
from tessri.analyze import analyze
from tessri.cli import main
from tessri.explain import ORPHAN_ADVICE, TargetError, explain, facts, render, why_json

ALICE = ("Alice", "alice@example.com")
BOB = ("Bob", "bob@example.com")
TREE = {
    "pkg/__init__.py": "",
    "pkg/core.py": "import pkg.util\n",
    "pkg/util.py": "x = 1\n",
    "pkg/dead.py": "y = 2\n",
    "pkg/loader.py": 'NAME = "pkg.plugin"\n',  # names pkg/plugin.py in a string
    "pkg/plugin.py": "z = 3\n",
    "scripts/run.py": 'import pkg.core\nLOADER = "pkg.loader"\n',
    "tests/test_core.py": "import pkg.core\n",
    "docs/guide.md": "See pkg/core.py.\n",
    "CODEOWNERS": "pkg/ @alice\n",
    ".tessri.toml": 'entry = ["scripts/run.py"]\n',
}


def run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


class Repo(TempRepo):
    """Alice wrote everything 400 days ago and went quiet; Bob maintains pkg/util.py; pkg/new.py is untracked."""

    def setUp(self):
        super().setUp()
        self.now = time.time()
        write_tree(self.root, TREE)
        git(self.root, "init", "-q")
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "start", when=self.stamp(400), author=ALICE)
        write_tree(self.root, {"pkg/util.py": "x = 1\nz = 2\n"})
        git(self.root, "commit", "-qam", "fix: util", when=self.stamp(10), author=BOB)
        write_tree(self.root, {"pkg/new.py": "w = 1\n"})
        self.a = analyze(self.root, config.load(self.root), now=self.now)

    def stamp(self, days_ago: int) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime(self.now - days_ago * 86400))


class FactsTest(Repo):
    def test_text_is_rendered_from_facts(self):
        for path in self.a.records:
            with self.subTest(path):
                self.assertEqual(explain(self.a, path), render(facts(self.a, path)))

    def test_orphan(self):
        f = facts(self.a, "pkg/dead.py")
        self.assertEqual((f["path"], f["query"]), ("pkg/dead.py", "pkg/dead.py"))
        self.assertEqual((f["verdict"]["status"], f["verdict"]["reachability"], f["verdict"]["confidence"]), ("ORPHAN", "none", "high"))
        self.assertEqual(f["graph"]["dependents"], [])
        self.assertEqual(f["advice"], ORPHAN_ADVICE)
        text = explain(self.a, "pkg/dead.py")
        self.assertIn("status:        ORPHAN (confidence high)", text)
        self.assertTrue(text.endswith(ORPHAN_ADVICE))

    def test_reachable_file_with_history_owners_and_graph(self):
        f = facts(self.a, "pkg.core")  # resolved from a module name
        self.assertEqual(f["path"], "pkg/core.py")
        self.assertEqual(f["verdict"]["status"], "STABLE")  # 400 days old, but two files still import it
        self.assertEqual(f["advice"], None)
        self.assertEqual((f["git"]["tracked"], f["git"]["commits_year"], f["git"]["authors_year"]), (True, 0, 0))
        self.assertEqual(f["graph"]["reached_via"], ["scripts/run.py", "pkg/core.py"])
        self.assertEqual(f["graph"]["dependents"], ["scripts/run.py", "tests/test_core.py"])
        self.assertEqual(f["graph"]["doc_refs"], ["docs/guide.md"])
        self.assertEqual([d["path"] for d in f["graph"]["depends_on"]], ["pkg/__init__.py", "pkg/util.py"])
        self.assertEqual(f["graph"]["depends_on"][1]["status"], "ACTIVE")
        self.assertEqual(f["graph"]["stranded_if_removed"], ["pkg/util.py"])
        owners = f["owners"]
        self.assertEqual(owners["state"], "no-active-owner")
        self.assertEqual([(p["name"], p["share"], p["silent"]) for p in owners["people"]], [("Alice", 100, True)])
        self.assertEqual(owners["codeowners"], {"declared": ["@alice"], "match": None})
        text = explain(self.a, "pkg/core.py")
        self.assertIn("owners:        Alice 100% (silent 400d); NO ACTIVE OWNER", text)
        self.assertIn("reached via:   scripts/run.py -> pkg/core.py", text)
        self.assertIn("deleting it would also strand: pkg/util.py", text)

    def test_every_edge_says_what_evidence_it_rests_on(self):
        f = facts(self.a, "pkg/plugin.py")  # named in a string by pkg/loader.py, itself named in a string by the script
        self.assertEqual(f["graph"]["reached_via"], ["scripts/run.py", "pkg/loader.py", "pkg/plugin.py"])
        self.assertEqual(f["graph"]["kinds"], {"reached_via": ["string", "string"], "dependents": {"pkg/loader.py": "string"}, "depends_on": {}})
        text = explain(self.a, "pkg/plugin.py")
        self.assertIn("reached via:   scripts/run.py -(string)-> pkg/loader.py -(string)-> pkg/plugin.py", text)
        self.assertIn("depended on by: pkg/loader.py (string)", text)
        core = facts(self.a, "pkg/core.py")["graph"]["kinds"]
        self.assertEqual(core["reached_via"], ["import"])
        self.assertEqual(core["dependents"], {"scripts/run.py": "import", "tests/test_core.py": "import"})
        self.assertEqual(core["depends_on"], {"pkg/__init__.py": "package", "pkg/util.py": "import"})
        text = explain(self.a, "pkg/core.py")
        self.assertIn("reached via:   scripts/run.py -> pkg/core.py\n", text)  # an import statement goes unmarked
        self.assertIn("depended on by: scripts/run.py, tests/test_core.py\n", text)
        self.assertRegex(text, r"depends on:    pkg/__init__\.py \[\w+\] \(package\), pkg/util\.py \[ACTIVE\]\n")

    def test_active_owner_is_not_silent(self):
        f = facts(self.a, "pkg/util.py")
        bob = next(p for p in f["owners"]["people"] if p["name"] == "Bob")
        self.assertEqual((bob["silent"], f["owners"]["state"], f["git"]["fixes_90"]), (False, "owned", 1))
        self.assertNotIn("silent 10d", explain(self.a, "pkg/util.py"))

    def test_untracked_file(self):
        f = facts(self.a, "pkg/new.py")
        self.assertEqual((f["git"]["tracked"], f["git"]["last_commit"]), (False, None))
        self.assertIn("git:           no history for this file (new or untracked)", explain(self.a, "pkg/new.py"))

    def test_test_file(self):
        f = facts(self.a, "tests/test_core.py")
        self.assertEqual((f["file"]["test"], f["verdict"]["status"]), (True, "DORMANT"))
        self.assertIn("kind:          test file", explain(self.a, "tests/test_core.py"))

    def test_json_is_serialisable_and_carries_meta(self):
        doc = json.loads(json.dumps(why_json(self.a, "pkg/core.py")))
        self.assertEqual((doc["schema_version"], doc["kind"], doc["path"]), (1, "why", "pkg/core.py"))
        self.assertEqual(doc["meta"]["git"]["available"], True)
        for key in ("file", "verdict", "git", "owners", "graph", "advice"):
            self.assertIn(key, doc)

    def test_unknown_target(self):
        with self.assertRaises(TargetError):
            facts(self.a, "nope.py")


class WithoutGitTest(TempRepo):
    def test_no_history_means_no_git_and_no_owner_facts(self):
        write_tree(self.root, {"a.py": "import b\n", "b.py": "x = 1\n"})
        a = analyze(self.root, config.load(self.root))
        f = facts(a, "b.py")
        # Without entry points nothing is reached, so the verdict is ORPHAN; without history it has no git doubts.
        self.assertEqual((f["git"], f["owners"], f["verdict"]["status"], f["verdict"]["confidence"]), (None, None, "ORPHAN", "high"))
        text = explain(a, "b.py")
        self.assertNotIn("git:", text)
        self.assertNotIn("owners:", text)
        doc = why_json(a, "b.py")
        self.assertEqual(doc["meta"]["git"]["reason"], "not-a-repository")


class CliTest(Repo):
    def test_text_is_the_default(self):
        code, out = run_cli("why", "pkg/dead.py", "--repo", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(out, explain(self.a, "pkg/dead.py") + "\n")

    def test_json(self):
        code, out = run_cli("why", "pkg/dead.py", "--repo", str(self.root), "--format", "json")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual((doc["kind"], doc["verdict"]["status"], doc["meta"]["git"]["available"]), ("why", "ORPHAN", True))

    def test_out_file(self):
        target = self.root / "out" / "why.json"
        code, out = run_cli("why", "pkg/dead.py", "--repo", str(self.root), "--format", "json", "--out", str(target))
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(json.loads(target.read_text())["path"], "pkg/dead.py")

    def test_unknown_target_exits_2_without_output(self):
        code, out = run_cli("why", "nope.py", "--repo", str(self.root), "--format", "json")
        self.assertEqual((code, out), (2, ""))


if __name__ == "__main__":
    unittest.main()
