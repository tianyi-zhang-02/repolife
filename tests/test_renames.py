"""History follows a file through the renames git detects: activity, authors, fix counts, ownership credit and the
review windows are read under the file's current name. A file rewritten when moved, or a path re-created after a
move, is a new file."""

import time
import unittest
from datetime import datetime, timezone

from helpers import TempRepo, git, write_tree

from tessri import config, gitlog
from tessri.analyze import analyze
from tessri.explain import explain

ALICE = ("Alice Adams", "alice@example.com")
BOB = ("Bob Brown", "bob@example.com")
BODY = "".join(f"line {i} = {i}\n" for i in range(12))


class Moves(TempRepo):
    def setUp(self):
        super().setUp()
        self.now = time.time()
        git(self.root, "init", "-q", "-b", "main")

    def commit(self, files, who, days_ago, message="change"):
        write_tree(self.root, files)
        git(self.root, "add", "-A")
        when = datetime.fromtimestamp(self.now - days_ago * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
        git(self.root, "commit", "-q", "-m", message, when=when, author=who)

    def move(self, old, new, who, days_ago, extra=""):
        git(self.root, "mv", old, new)
        if extra:
            with open(self.root / new, "a", encoding="utf-8") as fh:
                fh.write(extra)
        self.commit({}, who, days_ago)

    def load(self, **kw):
        act = gitlog.load(self.root, self.now, 90, **kw)
        self.assertIsNotNone(act)
        return act

    def days(self, stamp):
        return round((self.now - stamp) / 86400)


class FollowTest(Moves):
    def test_a_moved_file_keeps_its_history(self):
        self.commit({"a.py": BODY}, ALICE, 400)
        self.commit({"a.py": BODY + "x = 1\n"}, ALICE, 100, "fix: off by one")
        self.move("a.py", "b.py", BOB, 20)
        self.commit({"b.py": BODY + "x = 2\n"}, BOB, 10)
        act = self.load()
        self.assertNotIn("a.py", act.files)
        b = act.files["b.py"]
        self.assertEqual((self.days(b.first), self.days(b.last)), (400, 10))
        self.assertEqual((b.commits_year, b.authors_year, b.fixes_year, b.fixes_90, b.commits_active), (3, 2, 1, 0, 2))
        self.assertEqual(set(act.credit["b.py"]), {"alice adams", "bob brown"})

    def test_a_chain_of_moves_is_one_history(self):
        self.commit({"a.py": BODY}, ALICE, 300)
        self.move("a.py", "b.py", ALICE, 200)
        self.move("b.py", "c.py", BOB, 100)
        act = self.load()
        self.assertEqual(sorted(act.files), ["c.py"])
        self.assertEqual((self.days(act.files["c.py"].first), act.files["c.py"].commits_year), (300, 3))

    def test_a_directory_move_follows_every_file(self):
        self.commit({"pkg/__init__.py": "", "pkg/x.py": BODY, "pkg/y.py": BODY.replace("line", "row")}, ALICE, 300)
        git(self.root, "mv", "pkg", "lib")
        self.commit({}, BOB, 30)
        act = self.load()
        self.assertEqual(sorted(act.files), ["lib/__init__.py", "lib/x.py", "lib/y.py"])
        self.assertEqual((self.days(act.files["lib/x.py"].first), self.days(act.files["lib/x.py"].last)), (300, 30))
        self.assertEqual(set(act.credit["lib/x.py"]), {"alice adams"})  # the move is activity, not maintenance

    def test_a_re_created_old_path_is_a_new_file(self):
        self.commit({"a.py": BODY}, ALICE, 300)
        self.move("a.py", "b.py", BOB, 50)
        self.commit({"a.py": "something = 'else'\n"}, BOB, 10)
        act = self.load()
        self.assertEqual((self.days(act.files["a.py"].first), act.files["a.py"].commits_year, set(act.credit["a.py"])), (10, 1, {"bob brown"}))
        self.assertEqual((self.days(act.files["b.py"].first), set(act.credit["b.py"])), (300, {"alice adams"}))  # a pure move credits nobody

    def test_an_older_file_under_the_new_name_is_another_file(self):
        self.commit({"b.py": "old b\n", "a.py": BODY}, ALICE, 300)
        git(self.root, "rm", "-q", "b.py")
        self.commit({}, ALICE, 200)
        self.move("a.py", "b.py", BOB, 50)
        act = self.load()
        self.assertEqual((self.days(act.files["b.py"].first), act.files["b.py"].commits_year), (300, 2))  # created 300d ago as a.py and moved 50d ago; the deletion of the old b.py is not its history
        self.assertNotIn("a.py", act.files)

    def test_a_move_with_small_edits_is_followed_and_a_rewrite_is_not(self):
        self.commit({"a.py": BODY, "c.py": BODY.replace("line", "row")}, ALICE, 300)
        self.move("a.py", "b.py", BOB, 20, extra="tail = 1\n")
        git(self.root, "mv", "c.py", "d.py")
        self.commit({"d.py": "".join(f"other {i}\n" for i in range(12))}, BOB, 10)
        act = self.load()
        self.assertEqual(self.days(act.files["b.py"].first), 300)
        self.assertEqual(self.days(act.files["d.py"].first), 10)  # nothing of c.py survived, so git saw a delete and an add
        self.assertEqual(self.days(act.files["c.py"].last), 10)

    def test_history_up_to_a_base_uses_the_names_at_that_base(self):
        self.commit({"a.py": BODY}, ALICE, 300)
        git(self.root, "tag", "base")
        self.move("a.py", "b.py", BOB, 20)
        self.assertEqual(sorted(self.load(rev="base").files), ["a.py"])
        self.assertEqual(sorted(self.load().files), ["b.py"])

    def test_the_verdict_and_why_see_the_whole_history(self):
        self.commit({"a.py": BODY, "main.py": "import a\n"}, ALICE, 400)
        self.move("a.py", "b.py", BOB, 20)
        self.commit({"main.py": "import b\n"}, BOB, 20)
        analysis = analyze(self.root, config.load(self.root), now=self.now)
        rec = analysis.records["b.py"]
        self.assertEqual(rec.owner, "Alice Adams")  # Bob only moved it; the content is Alice's
        self.assertIn("first", explain(analysis, "b.py"))


class ReviewWindowTest(Moves):
    def test_lines_moved_before_a_rename_count_under_the_new_name(self):
        self.commit({"a.py": BODY}, ALICE, 20)
        self.move("a.py", "b.py", BOB, 5, extra="tail = 1\n")
        found = gitlog.changes(self.root, self.now, 30)
        self.assertEqual([(c.name, c.files) for c in found], [("Bob Brown", {"b.py": 1}), ("Alice Adams", {"b.py": 12})])

    def test_a_pure_move_in_the_window_moves_no_lines(self):
        self.commit({"a.py": BODY}, ALICE, 100)
        self.move("a.py", "b.py", BOB, 5)
        found = gitlog.changes(self.root, self.now, 30)
        self.assertEqual([(c.name, c.files) for c in found], [("Bob Brown", {"b.py": 0})])


if __name__ == "__main__":
    unittest.main()
