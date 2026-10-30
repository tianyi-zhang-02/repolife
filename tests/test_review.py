import json
import os
import subprocess
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

from helpers import TempRepo, git
from repolife import config, gitlog, review
from repolife.analyze import analyze
from repolife.render import markdown
from repolife.report import build_report
from test_htmlreport import page_for, parse
from test_modules import run_cli

ALICE = ("Alice Adams", "alice@example.com")
BOB = ("Bob Brown", "bob@example.com")
CAROL = ("Carol Chen", "carol@example.com")
BOT = ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com")


def stamp(now, days_ago):
    return datetime.fromtimestamp(now - days_ago * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")


class Churn(TempRepo):
    """A repository whose commits happened a chosen number of days before `self.now`."""

    def setUp(self):
        super().setUp()
        self.now = time.time()
        self.serial = 0
        git(self.root, "init", "-q", "-b", "main")

    def lines(self, n):
        out = "".join(f"v{self.serial + i} = {self.serial + i}\n" for i in range(n))
        self.serial += n
        return out

    def commit(self, who, days_ago, message="change", new=None, append=None, binary=None):
        """new: path -> number of lines; append: path -> number of lines to add to an existing file."""
        for rel, n in (new or {}).items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.lines(n), encoding="utf-8")
        for rel, n in (append or {}).items():
            with open(self.root / rel, "a", encoding="utf-8") as handle:
                handle.write(self.lines(n))
        for rel, data in (binary or {}).items():
            (self.root / rel).write_bytes(data)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", message, when=stamp(self.now, days_ago), author=who)

    def scan(self, **settings):
        cfg = config.load(self.root)
        for key, value in settings.items():
            setattr(cfg, key, value)
        return analyze(self.root, cfg, now=self.now)

    def review(self, **settings):
        return build_report(self.scan(**settings))["review"]


class Scenario(Churn):
    """Alice owns core/, Bob left legacy/ behind long ago, and the last 30 days bring:
    Carol 4 lines into core (outside), Alice 6 into core (owner), a bot 2 into legacy (nobody active there),
    Carol a new web/app.js of 7 lines, and docs, a lock file, vendored code and an image that do not count."""

    def setUp(self):
        super().setUp()
        self.commit(ALICE, 300, new={"core/__init__.py": 0, "core/a.py": 20, "core/b.py": 10})
        self.commit(BOB, 290, new={"legacy/__init__.py": 0, "legacy/old.py": 10, "legacy/more.py": 5})
        for days in range(250, 69, -15):  # 13 commits: enough that Carol's one commit later stays below the owner threshold
            self.commit(ALICE, days, append={"core/a.py": 1})
        self.commit(ALICE, 45, append={"core/a.py": 3})  # the window before
        self.commit(CAROL, 10, append={"core/a.py": 4})
        self.commit(ALICE, 8, append={"core/b.py": 6})
        self.commit(BOT, 5, append={"legacy/old.py": 2})
        self.commit(CAROL, 3, new={"docs/readme.md": 3, "package-lock.json": 100, "node_modules/x.js": 5}, binary={"logo.png": b"\x89PNG\r\n\x1a\n\x00\x01"})
        self.commit(CAROL, 2, message="add the web app", new={"web/app.js": 7})


class ScenarioTest(unittest.TestCase):
    """Read-only checks on one shared repository: building it takes a few dozen commits."""

    @classmethod
    def setUpClass(cls):
        cls.case = Scenario()
        cls.case.setUp()
        cls.report = cls.case.review()
        cls.areas = {r["path"]: r for r in cls.report["areas"]}

    @classmethod
    def tearDownClass(cls):
        cls.case.doCleanups()

    now = property(lambda self: self.case.now)

    def scan(self, **settings):
        return self.case.scan(**settings)

    def review(self, **settings):
        return self.case.review(**settings)

    def test_window_and_totals(self):
        r = self.report
        self.assertEqual(r["days"], 30)
        self.assertEqual(r["window"]["to"], stamp(self.now, 0)[:10])
        t = r["totals"]
        self.assertEqual((t["lines"], t["previous_lines"], t["other_lines"]), (19, 3, 3))
        self.assertEqual((t["commits"], t["files"], t["areas"], t["authors"], t["automated_lines"]), (4, 4, 3, 2, 2))
        self.assertEqual(t["bulk"], {"threshold": gitlog.BULK_FILES, "commits": 0, "lines": 0, "largest": []})

    def test_areas_are_sorted_by_the_lines_that_changed(self):
        self.assertEqual([r["path"] for r in self.report["areas"]], ["core", "web", "legacy"])
        self.assertEqual([r["lines"] for r in self.report["areas"]], [10, 7, 2])

    def test_changes_by_someone_who_does_not_own_the_area_are_counted_as_outside(self):
        core = self.areas["core"]
        self.assertEqual((core["lines"], core["previous_lines"], core["commits"], core["files"], core["authors"]), (10, 3, 2, 2, 2))
        self.assertEqual((core["owner_lines"], core["outside_lines"], core["outside_share"], core["automated_lines"]), (6, 4, 40.0, 0))
        self.assertEqual(core["ownership"], "owned")
        self.assertEqual([o["name"] for o in core["owners"]], ["Alice Adams"])
        self.assertEqual([(c["name"], c["share"]) for c in core["contributors"]], [("Alice Adams", 60.0), ("Carol Chen", 40.0)])

    def test_a_person_changing_their_own_area_is_not_an_outsider(self):
        web = self.areas["web"]
        self.assertEqual((web["lines"], web["owner_lines"], web["outside_lines"], web["outside_share"]), (7, 7, 0, 0.0))

    def test_bots_are_automation_not_people(self):
        legacy = self.areas["legacy"]
        self.assertEqual((legacy["lines"], legacy["automated_lines"], legacy["authors"], legacy["contributors"]), (2, 2, 0, []))
        self.assertIsNone(legacy["outside_share"])  # no person changed it, so there is nobody to be an outsider
        self.assertEqual(legacy["outside_lines"], 0)
        self.assertNotIn("dependabot[bot]", [a["name"] for a in self.report["authors"]])

    def test_changes_where_nobody_active_maintains_the_code_are_called_out(self):
        self.assertEqual(self.areas["legacy"]["ownership"], "no-active-owner")
        self.assertEqual(self.report["unowned"], {"areas": 1, "lines": 2, "share": 10.5})

    def test_changes_land_on_the_people_who_own_the_area(self):
        by_name = {r["name"]: r for r in self.report["reviewers"]}
        self.assertIn(by_name["Alice Adams"]["inbound_lines"], (3, 4))  # 94% of the 4 lines Carol added
        self.assertTrue(by_name["Alice Adams"]["active"])
        self.assertEqual(by_name["Bob Brown"]["inbound_lines"], 2)
        self.assertFalse(by_name["Bob Brown"]["active"])
        self.assertIn(by_name["Bob Brown"]["idle_days"], (290, 291))
        self.assertNotIn("Carol Chen", by_name)  # she only changed her own code and a sliver of Alice's

    def test_authors_and_the_largest_changes(self):
        authors = {a["name"]: a for a in self.report["authors"]}
        self.assertEqual((authors["Carol Chen"]["lines"], authors["Carol Chen"]["commits"], authors["Carol Chen"]["areas"]), (11, 2, 2))
        self.assertEqual((authors["Alice Adams"]["lines"], authors["Alice Adams"]["commits"]), (6, 1))
        self.assertEqual(self.report["authors"][0]["name"], "Carol Chen")
        changes = self.report["largest_changes"]
        self.assertEqual([c["lines"] for c in changes], [7, 6, 4, 2])
        self.assertEqual((changes[0]["author"], changes[0]["subject"], changes[0]["area"], changes[0]["files"]), ("Carol Chen", "add the web app", "web", 1))
        self.assertEqual(changes[3]["author"], "dependabot[bot]")

    def test_docs_lock_files_vendored_code_and_images_do_not_count_as_code(self):
        paths = {p for r in self.report["areas"] for p in [r["path"]]}
        self.assertEqual(paths, {"core", "web", "legacy"})  # no docs, node_modules, package-lock.json
        self.assertEqual(self.report["totals"]["other_lines"], 3)

    def test_the_report_never_carries_an_address(self):
        text = json.dumps(self.report)
        for address in ("@example.com", "noreply"):
            self.assertNotIn(address, text)

    def test_it_is_part_of_the_json_report_and_its_settings(self):
        report = build_report(self.scan())
        self.assertEqual(report["settings"]["review_days"], 30)
        self.assertTrue(report["review"]["available"])
        self.assertEqual(report["review"], self.report)

    def test_markdown_has_a_review_section(self):
        text = markdown(build_report(self.scan()))
        for want in ("## Review load", "**19** lines changed", "(+533% against 3 before)", "By outsiders", "landed in 1 area that nobody active maintains", "Largest changes", "`web`", "add the web app"):
            self.assertIn(want, text)

    def test_html_has_a_review_section_that_parses(self):
        html = page_for(self.scan())
        page = parse(html)
        self.assertEqual(page.problems, [])
        self.assertIn("review", page.ids)
        self.assertIn("#review", page.hrefs)
        self.assertIn("Changing fastest", html)
        self.assertIn("Who the changes land on", html)

    def test_the_ignore_authors_setting_turns_a_person_into_automation(self):
        r = self.review(ignore_authors=["Carol*"])
        self.assertEqual(r["totals"]["automated_lines"], 13)
        self.assertNotIn("Carol Chen", [a["name"] for a in r["authors"]])
        self.assertEqual(r["totals"]["lines"], 19)


class AutomationTest(Churn):
    def test_bots_are_not_part_of_the_share_of_outsiders(self):
        self.commit(ALICE, 300, new={"a.py": 10})
        for days in range(250, 69, -15):
            self.commit(ALICE, days, append={"a.py": 1})
        self.commit(CAROL, 10, append={"a.py": 2})
        self.commit(ALICE, 8, append={"a.py": 2})
        self.commit(BOT, 5, append={"a.py": 4})
        area = self.review()["areas"][0]
        self.assertEqual((area["lines"], area["automated_lines"], area["owner_lines"], area["outside_lines"], area["authors"]), (8, 4, 2, 2, 2))
        self.assertEqual(area["outside_share"], 50.0)  # of the people's lines, not of the bot's too
        self.assertEqual([(c["name"], c["share"]) for c in area["contributors"]], [("Alice Adams", 50.0), ("Carol Chen", 50.0)])
        self.assertEqual(area["commits"], 3)


class WindowTest(Churn):
    def test_the_window_is_cut_by_author_date_to_the_second(self):
        self.commit(ALICE, 100, new={"a.py": 3})
        for days, lines in ((29.9, 1), (30.1, 2), (59.9, 4), (60.1, 8)):
            self.commit(ALICE, days, append={"a.py": lines})
        r = self.review()
        self.assertEqual((r["totals"]["lines"], r["totals"]["previous_lines"], r["totals"]["commits"]), (1, 6, 1))

    def test_deleted_lines_count_as_much_as_added_ones(self):
        self.commit(ALICE, 100, new={"a.py": 5})
        self.commit(ALICE, 4, message="rewrite")
        (self.root / "a.py").write_text(self.lines(2))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "rewrite", when=stamp(self.now, 3), author=ALICE)
        self.assertEqual(self.review()["totals"]["lines"], 7)  # 2 added, 5 deleted

    def test_a_shorter_window_changes_what_counts(self):
        self.commit(ALICE, 100, new={"a.py": 3})
        self.commit(ALICE, 10, append={"a.py": 5})
        self.assertEqual(self.review(review_days=30)["totals"]["lines"], 5)
        self.assertEqual(self.review(review_days=7)["totals"]["lines"], 0)
        self.assertEqual(self.review(review_days=7)["totals"]["previous_lines"], 5)

    def test_a_commit_dated_long_ago_does_not_count_even_if_it_was_made_today(self):
        self.commit(ALICE, 100, new={"a.py": 3})
        (self.root / "a.py").write_text((self.root / "a.py").read_text() + self.lines(9))
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        env = dict(os.environ, GIT_AUTHOR_DATE=stamp(self.now, 100), GIT_COMMITTER_DATE=stamp(self.now, 0), GIT_AUTHOR_NAME="A", GIT_AUTHOR_EMAIL="a@e", GIT_COMMITTER_NAME="A", GIT_COMMITTER_EMAIL="a@e")
        subprocess.run(["git", "commit", "-q", "-m", "rebased"], cwd=self.root, env=env, check=True, capture_output=True)
        r = self.review()
        self.assertEqual((r["totals"]["lines"], r["totals"]["previous_lines"], r["totals"]["commits"]), (0, 0, 0))

    def test_a_quiet_repository_has_an_empty_but_valid_section(self):
        self.commit(ALICE, 100, new={"a.py": 3})
        r = self.review()
        self.assertEqual((r["available"], r["totals"]["lines"], r["areas"], r["reviewers"], r["largest_changes"], r["authors"]), (True, 0, [], [], [], []))
        self.assertEqual(r["unowned"], {"areas": 0, "lines": 0, "share": 0.0})
        self.assertIn("No code changed in this window", markdown(build_report(self.scan())))
        html = page_for(self.scan())
        self.assertEqual(parse(html).problems, [])
        self.assertIn("No code changed in this window", html)


class BulkTest(Churn):
    def test_a_commit_touching_many_files_is_reported_apart(self):
        self.commit(ALICE, 100, new={"a.py": 3})
        self.commit(ALICE, 6, message="reformat everything", new={"x.py": 4, "y.py": 5, "z.py": 6})
        self.commit(ALICE, 5, append={"a.py": 2})
        with mock.patch.object(gitlog, "BULK_FILES", 3):
            r = build_report(self.scan())["review"]
        t = r["totals"]
        self.assertEqual((t["lines"], t["commits"]), (2, 1))
        self.assertEqual((t["bulk"]["commits"], t["bulk"]["lines"]), (1, 15))
        self.assertEqual([(b["subject"], b["files"], b["lines"]) for b in t["bulk"]["largest"]], [("reformat everything", 3, 15)])
        self.assertEqual([a["path"] for a in r["areas"]], ["."])
        self.assertIn("left out", markdown(_with(self, 3)))

    def test_the_bulk_notice_names_the_threshold(self):
        self.commit(ALICE, 100, new={"a.py": 3})
        self.commit(ALICE, 6, new={"x.py": 4, "y.py": 5, "z.py": 6})
        with mock.patch.object(gitlog, "BULK_FILES", 3):
            text = markdown(build_report(self.scan()))
        self.assertIn("3 or more files (15 lines) are left out", text)


def _with(case, threshold):
    with mock.patch.object(gitlog, "BULK_FILES", threshold):
        return build_report(case.scan())


class SwitchesTest(Churn):
    def test_without_git_there_is_no_review(self):
        plain = self.root / "plain"
        plain.mkdir()
        (plain / "a.py").write_text("x = 1\n")
        a = analyze(plain, config.load(plain))
        self.assertIsNone(a.changes)
        self.assertEqual(build_report(a)["review"], {"available": False})
        self.assertNotIn("## Review load", markdown(build_report(a)))
        self.assertNotIn('id="review"', page_for(a))

    def test_review_days_zero_turns_it_off(self):
        self.commit(ALICE, 5, new={"a.py": 3})
        a = self.scan(review_days=0)
        self.assertIsNone(a.changes)
        self.assertEqual(build_report(a)["review"], {"available": False})
        html = page_for(a)
        self.assertNotIn('id="review"', html)
        self.assertEqual(parse(html).problems, [])
        self.assertIn("Review window", html)

    def test_a_repository_without_commits_has_no_review(self):
        (self.root / "a.py").write_text("x = 1\n")
        self.assertEqual(build_report(self.scan())["review"], {"available": False})

    def test_the_config_file_sets_the_window(self):
        self.commit(ALICE, 100, new={"a.py": 3})
        (self.root / ".repolife.toml").write_text("review_days = 7\n")
        self.assertEqual(config.load(self.root).review_days, 7)
        self.assertEqual(self.review()["days"], 7)
        (self.root / ".repolife.toml").write_text("review_days = -1\n")
        with self.assertRaises(config.ConfigError):
            config.load(self.root)

    def test_the_flag_sets_the_window_and_a_negative_one_is_refused(self):
        self.commit(ALICE, 100, new={"a.py": 3})
        self.commit(ALICE, 10, append={"a.py": 5})
        code, out, _ = run_cli("scan", str(self.root), "--format", "json", "--review-days", "7")
        self.assertEqual(code, 0)
        self.assertEqual((json.loads(out)["review"]["days"], json.loads(out)["review"]["totals"]["lines"]), (7, 0))
        code, out, _ = run_cli("scan", str(self.root), "--format", "json")
        self.assertEqual((json.loads(out)["review"]["days"], json.loads(out)["review"]["totals"]["lines"]), (30, 5))
        self.assertEqual(run_cli("scan", str(self.root), "--review-days", "-1")[0], 2)
        code, out, _ = run_cli("scan", str(self.root), "--format", "json", "--review-days", "0")
        self.assertEqual(json.loads(out)["review"], {"available": False})


class TextTest(Churn):
    def test_subjects_are_cut_and_markup_is_escaped_in_the_page(self):
        dan = ('Dan "D" & Co', "dan@example.com")
        self.commit(ALICE, 100, new={"a.py": 3})
        self.commit(dan, 4, message="<script>alert(1)</script> " + "x" * 200, append={"a.py": 5})
        r = self.review()
        subject = r["largest_changes"][0]["subject"]
        self.assertEqual(len(subject), review.SUBJECT_MAX)
        self.assertTrue(subject.startswith("<script>"))
        self.assertNotIn("dan@example.com", json.dumps(r))
        html = page_for(self.scan())
        self.assertNotIn("<script>alert(1)", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("Dan &quot;D&quot; &amp; Co", html)
        self.assertEqual(parse(html).problems, [])


if __name__ == "__main__":
    unittest.main()
