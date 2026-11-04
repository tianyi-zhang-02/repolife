"""A change that moves a file is read under the file's new name. `check` sees one file with the edits made on the way,
not a deletion and an addition, so a renamed package keeps its cycles, its dependencies and its orphans instead of
reporting them gone and new again; a moved file that an untouched file still imports under its old name is a dangling
import; `triage` ranks a moved file by the history of its old name instead of as a new file; and history read for a
dirty tree follows an uncommitted `git mv`."""

import tempfile
import time
import unittest
from pathlib import Path

from helpers import TempRepo, git, write_tree

from tessri import config, gitlog, sinceview, triage
from tessri import since as sincemod
from tessri.analyze import analyze

ALICE = ("Alice Adams", "alice@example.com")
BOB = ("Bob Brown", "bob@example.com")
CAROL = ("Carol Chen", "carol@example.com")
BODY = "".join(f"line {i} = {i}\n" for i in range(12))
HELPERS = "def go():\n    return 1\n" + "".join(f"K{i} = {i}\n" for i in range(10))  # long enough for an edit to stay a move
A0 = "".join(f"def f{i}():\n    return {i}\n" for i in range(5))

BASE = {
    "app/__init__.py": "",
    "app/main.py": "from core import engine\n\nif __name__ == '__main__':\n    engine.run()\n",
    "core/__init__.py": "",
    "core/engine.py": "from util import helpers\n\n\ndef run():\n    return helpers.go()\n",
    "util/__init__.py": "",
    "util/helpers.py": HELPERS,
    "tests/test_engine.py": "from core import engine\n\n\ndef test_run():\n    assert engine.run()\n",
}

# a and b depend on each other; c stands apart
CYCLIC = {
    "a/__init__.py": "",
    "a/x.py": "from b import y\n\nif __name__ == '__main__':\n    print(y)\n",
    "b/__init__.py": "",
    "b/y.py": "from a import x\n",
    "c/__init__.py": "",
    "c/z.py": "def z():\n    return 1\n",
}


class Moving(TempRepo):
    def setUp(self):
        super().setUp()
        self.now = time.time()
        git(self.root, "init", "-q", "-b", "main")

    def commit(self, files, who=ALICE, days_ago=0, message="change"):
        write_tree(self.root, files)
        git(self.root, "add", "-A")
        when = time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime(self.now - days_ago * 86400))
        git(self.root, "commit", "-q", "--allow-empty", "-m", message, when=when, author=who)

    def days(self, stamp):
        return round((self.now - stamp) / 86400)

    def check(self, since="HEAD"):
        return sincemod.check(self.root, config.load(self.root), since, now=self.now)

    def finding(self, result, finding_id):
        return next(f for f in result["findings"] if f["id"] == finding_id)


class DiffTest(Moving):
    def test_what_the_diff_says_about_each_file(self):
        self.commit({"a.py": BODY, "b.py": BODY.replace("line", "row"), "c.py": "x = 1\n"}, days_ago=10)
        git(self.root, "mv", "a.py", "moved.py")
        git(self.root, "mv", "b.py", "edited.py")
        with open(self.root / "edited.py", "a", encoding="utf-8") as fh:
            fh.write("tail = 1\n")
        (self.root / "c.py").unlink()
        write_tree(self.root, {"new.py": "y = 2\n"})  # untracked
        found = gitlog.diff(self.root, "HEAD")
        self.assertEqual(
            {p: (c.state, c.origin, c.added, c.deleted) for p, c in found.items()},
            {
                "moved.py": ("moved", "a.py", 0, 0),  # a pure move changes no lines
                "edited.py": ("moved", "b.py", 1, 0),
                "c.py": ("deleted", None, 0, 1),
                "new.py": ("added", None, 1, 0),
            },
        )
        self.assertEqual(found["edited.py"].lines, 1)
        self.assertEqual(gitlog.renames(self.root, "HEAD"), {"a.py": "moved.py", "b.py": "edited.py"})

    def test_a_directory_that_is_not_a_repository_has_no_diff(self):
        with tempfile.TemporaryDirectory() as plain:
            self.assertIsNone(gitlog.diff(Path(plain), "HEAD"))
            self.assertEqual(gitlog.renames(Path(plain)), {})


class HistoryTest(Moving):
    def test_an_uncommitted_move_keeps_the_history_under_the_new_name(self):
        self.commit({"a.py": BODY}, ALICE, 100)
        git(self.root, "mv", "a.py", "b.py")
        act = gitlog.load(self.root, self.now, 90)
        self.assertEqual(sorted(act.files), ["b.py"])
        self.assertEqual(self.days(act.files["b.py"].first), 100)
        self.assertEqual(set(act.credit["b.py"]), {"alice adams"})

    def test_history_up_to_a_base_is_read_under_the_names_the_tree_has_now(self):
        self.commit({"a.py": BODY}, ALICE, 300, "feat: a")
        self.commit({"a.py": BODY + "x = 1\n"}, ALICE, 100, "fix: a")
        git(self.root, "checkout", "-q", "-b", "feature")
        git(self.root, "mv", "a.py", "b.py")
        self.commit({}, BOB, 10, "move a to b")
        act = gitlog.load(self.root, self.now, 90, rev="main")
        self.assertEqual(sorted(act.files), ["b.py"])
        b = act.files["b.py"]
        self.assertEqual((self.days(b.first), self.days(b.last), b.commits_year, b.fixes_year), (300, 100, 2, 1))
        self.assertEqual(set(act.credit["b.py"]), {"alice adams"})  # Bob's move is after the base
        a = analyze(self.root, config.load(self.root), now=self.now, rev="main")
        self.assertEqual((a.records["b.py"].owner, a.records["b.py"].commits_year), ("Alice Adams", 2))


class CheckTest(Moving):
    def test_a_moved_file_is_one_file_with_the_edits_made_on_the_way(self):
        self.commit(BASE, days_ago=30)
        git(self.root, "mv", "util/helpers.py", "util/aid.py")
        write_tree(self.root, {"util/aid.py": HELPERS + "\n\ndef go2():\n    return 2\n", "core/engine.py": "from util import aid\n\n\ndef run():\n    return aid.go()\n"})
        r = self.check()
        rows = {f["path"]: f for f in r["changed_files"]}
        self.assertNotIn("util/helpers.py", rows)
        self.assertEqual((rows["util/aid.py"]["change"], rows["util/aid.py"]["from"], rows["util/aid.py"]["added"], rows["util/aid.py"]["deleted"]), ("moved", "util/helpers.py", 4, 0))
        self.assertNotIn("from", rows["core/engine.py"])
        s = r["summary"]
        self.assertEqual((s["files"], s["added"], s["modified"], s["moved"], s["deleted"], s["lines"]), (2, 0, 1, 1, 0, 8))
        self.assertEqual(r["findings"], [])
        text = sinceview.markdown(r)
        self.assertIn("0 added, 1 modified, 1 moved, 0 deleted", text)
        self.assertIn("| `util/aid.py` | moved from `util/helpers.py` | +4 -0 |", text)

    def test_the_summary_does_not_mention_moves_when_there_are_none(self):
        self.commit(BASE, days_ago=30)
        write_tree(self.root, {"util/helpers.py": HELPERS + "x = 1\n"})
        r = self.check()
        self.assertEqual(r["summary"]["moved"], 0)
        self.assertIn("(0 added, 1 modified, 0 deleted)", sinceview.markdown(r))

    def test_a_renamed_package_keeps_its_cycle_its_dependencies_and_its_orphans(self):
        self.commit(CYCLIC, days_ago=30)
        git(self.root, "checkout", "-q", "-b", "feature")
        git(self.root, "mv", "a", "alpha")
        self.commit({"b/y.py": "from alpha import x\n"}, BOB, 1, "rename a to alpha")
        r = self.check("main")
        s = r["summary"]
        self.assertEqual((s["added"], s["modified"], s["moved"], s["deleted"]), (0, 1, 2, 0))
        self.assertEqual(r["cycles"], {"new": [], "grown": [], "resolved": []})
        self.assertEqual(r["dependencies"], {"new": [], "removed": []})
        self.assertEqual(r["orphans"], {"new": [], "resolved": []})  # c/z.py was an orphan before and still is
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["modules_touched"], ["alpha", "b"])

    def test_a_moved_file_still_imported_under_its_old_name_blocks(self):
        self.commit(BASE, days_ago=30)
        git(self.root, "mv", "util/helpers.py", "util/aid.py")
        r = self.check()
        self.assertEqual(r["dangling_imports"], [{"deleted": "util/helpers.py", "importers": ["core/engine.py"], "moved_to": "util/aid.py"}])
        f = self.finding(r, "dangling-import:util/helpers.py")
        self.assertEqual((f["severity"], f["files"]), ("block", ["core/engine.py"]))
        self.assertEqual(f["title"], "`util/helpers.py` was moved to `util/aid.py` but is still imported under its old name")
        self.assertIn("new path", f["action"])
        self.assertEqual([(o["path"], o["how"], o["was_reached_from"]) for o in r["orphans"]["new"]], [("util/aid.py", "stranded", ["core/engine.py"])])  # reached before, under its old name

    def test_a_moved_orphan_is_not_a_new_one(self):
        self.commit({**BASE, "util/spare.py": "def spare():\n    return 1\n"}, days_ago=30)
        git(self.root, "mv", "util/spare.py", "util/extra.py")
        r = self.check()
        self.assertEqual(r["orphans"], {"new": [], "resolved": []})
        self.assertEqual(r["findings"], [])

    def test_moved_code_keeps_the_maintainers_it_had(self):
        self.commit({"legacy/__init__.py": "", "legacy/old.py": HELPERS}, BOB, 400)
        self.commit(BASE, ALICE, 5)
        git(self.root, "mv", "legacy/old.py", "legacy/older.py")
        write_tree(self.root, {"legacy/older.py": HELPERS + "\n\ndef more():\n    return 2\n"})
        r = self.check()
        self.assertEqual([(u["path"], u["last_owner"], u["lines"]) for u in r["unowned"]], [("legacy/older.py", "Bob Brown", 4)])
        self.assertEqual(self.finding(r, "no-active-owner:changed")["files"], ["legacy/older.py"])


class TriageTest(Moving):
    def setUp(self):
        super().setUp()
        self.commit({"core/__init__.py": "", "core/a.py": A0, "core/b.py": "from core import a\n\n\ndef b():\n    return a.f0()\n", "tests/test_a.py": "from core import a\n\n\ndef test_a():\n    assert a.f0() == 0\n"}, ALICE, 300, "feat: core")
        self.commit({"core/a.py": A0 + "def g():\n    return 1\n"}, ALICE, 60, "fix: empty input")
        a1 = A0 + "def g():\n    return 1\n\n\ndef h():\n    return 2\n"
        self.commit({"core/a.py": a1}, ALICE, 20, "feat: more")
        git(self.root, "checkout", "-q", "-b", "feature")
        git(self.root, "mv", "core/a.py", "core/alpha.py")
        self.commit(
            {"core/alpha.py": a1 + "\n\ndef carol():\n    return 3\n", "core/b.py": "from core import alpha\n\n\ndef b():\n    return alpha.f0()\n", "tests/test_a.py": "from core import alpha\n\n\ndef test_a():\n    assert alpha.f0() == 0\n"},
            CAROL, 1, "move a to alpha",
        )
        self.t = triage.compute(self.root, config.load(self.root), "main", now=self.now)
        self.by = {r["path"]: r for r in self.t["files"]}

    def test_a_moved_file_keeps_its_history_and_its_rank(self):
        self.assertNotIn("core/a.py", self.by)
        row = self.by["core/alpha.py"]
        self.assertEqual((row["change"], row["from"], row["tier"], row["rank"]), ("moved", "core/a.py", "busy", 1))
        self.assertEqual((row["commits_active"], row["commits_year"], row["fixes_90"]), (2, 3, 1))
        self.assertEqual([o["name"] for o in row["owners"]], ["Alice Adams"])
        self.assertIn("moved", row["flags"])
        self.assertNotIn("new file", row["flags"])
        self.assertEqual((self.t["summary"]["moved"], self.t["summary"]["new"]), (1, 0))

    def test_the_move_counts_only_the_edits_made_on_the_way(self):
        row = self.by["core/alpha.py"]
        self.assertEqual((row["added"], row["deleted"]), (4, 0))
        self.assertNotIn("from", self.by["core/b.py"])

    def test_markdown_names_the_old_path(self):
        text = triage.markdown(self.t)
        self.assertIn("| 1 | `core/alpha.py` | 2 commits in 90 days, 1 of them fixes or reverts | +4 -0 |", text)
        self.assertIn("moved from `core/a.py`", text)
        self.assertNotIn("new file", text)


if __name__ == "__main__":
    unittest.main()
