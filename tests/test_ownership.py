import contextlib
import io
import json
import time
import unittest
from datetime import datetime, timezone
from unittest import mock

from helpers import TempRepo, git, write_tree
from repolife import config, gitlog, ownership
from repolife.analyze import analyze
from repolife.cli import main
from repolife.explain import explain
from repolife.render import markdown
from repolife.report import build_report

ALICE = ("Alice Adams", "alice@example.com")
ALICE_HOME = ("Alice Adams", "alice@home.example")  # same person, another address
BOB = ("Bob Brown", "7+bob-brown@users.noreply.github.com")
BOT = ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com")


class History(TempRepo):
    """A repository whose commits happened a chosen number of days before `self.now`."""

    def setUp(self):
        super().setUp()
        self.now = time.time()
        git(self.root, "init", "-q", "-b", "main")

    def commit(self, files, who, days_ago):
        write_tree(self.root, files)
        git(self.root, "add", "-A")
        when = datetime.fromtimestamp(self.now - days_ago * 86400, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
        git(self.root, "commit", "-q", "-m", "change", when=when, author=who)

    def scan(self, **settings):
        cfg = config.load(self.root)
        for key, value in settings.items():
            setattr(cfg, key, value)
        return analyze(self.root, cfg, now=self.now)


class Scenario(History):
    """Bob wrote legacy/ and shared/ long ago and never came back; Alice took over, a bot touches things."""

    def setUp(self):
        super().setUp()
        self.commit(
            {
                "legacy/__init__.py": "",
                "legacy/old.py": "def old():\n    return 1\n",
                "legacy/more.py": "def more():\n    return 2\n",
                "shared/__init__.py": "",
                "shared/x.py": "def x():\n    return 3\n",
            },
            BOB,
            800,
        )
        a = "def a():\n    total = 1\n    total += 1\n    return total\n"
        self.commit({"core/__init__.py": "", "core/b.py": a.replace("def a", "def b")}, ALICE_HOME, 30)
        self.commit(
            {
                "core/a.py": a,
                "core/dead.py": "def dead():\n    return 0\n",
                "shared/x.py": "def x():\n    return 4\n",
                "main.py": "from core import a, b\nfrom legacy import old, more\nfrom shared import x\n\nif __name__ == '__main__':\n    a.a()\n",
            },
            ALICE,
            20,
        )
        self.commit({"core/a.py": a.replace("total\n", "total + 1\n")}, ALICE, 10)
        self.commit({"core/a.py": a.replace("total\n", "total + 2\n")}, BOT, 5)


class OwnershipTest(Scenario):
    def test_owner_is_whoever_maintains_it_lately(self):
        recs = self.scan().records
        a = recs["core/a.py"]
        self.assertEqual((a.owner, a.owner_share, a.ownership), ("Alice Adams", 100, "owned"))
        self.assertEqual(a.owner_idle_days, 10)  # the bot's later commit is not hers and does not count as anyone's
        shared = recs["shared/x.py"]  # Bob 800 days ago (weight 0.22) against Alice 20 days ago (0.96)
        self.assertEqual((shared.owner, shared.owner_share), ("Alice Adams", 81))

    def test_one_person_with_two_addresses_is_one_author(self):
        own = self.scan().ownership
        self.assertEqual(sorted(x.name for x in own.authors.values()), ["Alice Adams", "Bob Brown"])  # no bot, no second Alice
        self.assertEqual(self.scan().records["core/b.py"].owner, "Alice Adams")

    def test_files_whose_maintainers_are_gone_have_no_active_owner(self):
        a = self.scan()
        old = a.records["legacy/old.py"]
        self.assertEqual((old.owner, old.owner_idle_days, old.ownership), ("Bob Brown", 800, "no-active-owner"))
        rep = build_report(a)
        section = rep["ownership"]
        self.assertEqual(section["no_active_owner"], {"files": 2, "code": 4, "share": 19.0})
        self.assertEqual(section["authors"], {"total": 2, "active": 1})
        self.assertEqual(section["bus_factor"], 1)
        self.assertEqual({f["path"] for f in section["needs_owner_files"]}, {"legacy/old.py", "legacy/more.py"})
        rows = {r["path"]: r for r in rep["directories"]}
        self.assertEqual((rows["legacy"]["ownership"], rows["legacy"]["no_active_owner_code"]), ("no-active-owner", 4))
        self.assertEqual((rows["core"]["ownership"], rows["core"]["no_active_owner_code"]), ("owned", 0))
        self.assertEqual(rows["core"]["owners"], [{"name": "Alice Adams", "share": 100, "idle_days": 10}])

    def test_orphans_name_who_to_ask_but_are_not_assignment_work(self):
        self.commit({"legacy/stray.py": "def stray():\n    return 9\n"}, BOB, 790)  # unreachable, and its author is long gone
        rep = build_report(self.scan())
        orphans = {r["path"]: r for r in rep["cleanup"]["orphan_files"]}
        self.assertEqual(orphans["core/dead.py"]["owner"], "Alice Adams")
        self.assertEqual((orphans["legacy/stray.py"]["owner"], orphans["legacy/stray.py"]["owner_idle_days"]), ("Bob Brown", 790))
        needs = [f["path"] for f in rep["ownership"]["needs_owner_files"]]
        self.assertNotIn("legacy/stray.py", needs)  # deleting it needs no new owner
        self.assertIn("legacy/old.py", needs)

    def test_the_silence_threshold_is_configurable(self):
        self.assertEqual(self.scan(owner_inactive_days=900).records["legacy/old.py"].ownership, "owned")
        self.assertEqual(self.scan(owner_inactive_days=5).records["core/a.py"].ownership, "no-active-owner")

    def test_ignored_authors_are_never_credited(self):
        a = self.scan(ignore_authors=["alice*"])
        self.assertEqual(a.records["core/a.py"].ownership, "unknown")  # nobody left to credit
        self.assertIsNone(a.records["core/a.py"].owner)
        self.assertEqual(a.records["shared/x.py"].owner, "Bob Brown")
        self.assertGreater(build_report(a)["ownership"]["unattributed"]["code"], 0)
        self.assertEqual(self.scan(ignore_authors=["*example.com"]).records["core/a.py"].ownership, "unknown")  # the email counts too

    def test_markdown_and_why_say_who(self):
        a = self.scan()
        md = markdown(build_report(a), 40)
        self.assertIn("## Ownership", md)
        self.assertIn("Bob Brown 100% (silent 800d)", md)
        self.assertIn("| Owner |", md)  # the orphan table says who to ask
        text = explain(a, "legacy/old.py")
        self.assertIn("owners:        Bob Brown 100% (silent 800d); NO ACTIVE OWNER", text)

    def test_json_names_people_but_never_addresses(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["scan", str(self.root), "--format", "json", "--full", "--owner-inactive-days", "900"]), 0)
        rep = json.loads(out.getvalue())
        self.assertEqual(rep["ownership"]["no_active_owner"]["files"], 0)  # the flag reached the analysis
        self.assertEqual(rep["settings"]["owner_inactive_days"], 900)
        self.assertNotIn("example.com", out.getvalue())
        self.assertNotIn("noreply", out.getvalue())

    def test_options_come_from_the_config_file_and_the_command_line(self):
        write_tree(self.root, {".repolife.toml": 'owner_inactive_days = 900\nignore_authors = ["alice*"]\n'})
        cfg = config.load(self.root)
        self.assertEqual((cfg.owner_inactive_days, cfg.ignore_authors), (900, ["alice*"]))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["scan", str(self.root), "--format", "json", "--full", "--ignore-author", "bob*"]), 0)
        rep = json.loads(out.getvalue())
        self.assertEqual(rep["settings"]["ignore_authors"], ["alice*", "bob*"])  # the flag adds to the file
        self.assertEqual({f["path"]: f["ownership"] for f in rep["files"]}["core/a.py"], "unknown")

class NoGitTest(TempRepo):
    def test_without_git_there_is_no_ownership(self):
        write_tree(self.root, {"a.py": "x = 1\n"})
        a = analyze(self.root, config.load(self.root))
        self.assertIsNone(a.ownership)
        rep = build_report(a)
        self.assertEqual(rep["ownership"], {"available": False})
        self.assertNotIn("## Ownership", markdown(rep))
        self.assertIsNone(a.records["a.py"].ownership)


class MailmapTest(History):
    def test_mailmap_merges_authors_with_different_names(self):
        self.commit({"a.py": "x = 1\n"}, ("Al", "al@old.example"), 100)
        self.commit({"b.py": "y = 1\n"}, ("Alice Adams", "alice@example.com"), 50)
        self.assertEqual(len(self.scan().ownership.authors), 2)
        write_tree(self.root, {".mailmap": "Alice Adams <alice@example.com> <al@old.example>\n"})
        merged = self.scan()
        self.assertEqual([x.name for x in merged.ownership.authors.values()], ["Alice Adams"])
        self.assertEqual(merged.records["a.py"].owner, "Alice Adams")


    def test_a_one_word_name_on_two_addresses_is_one_author(self):
        # Real case: a maintainer's recent commits used a new address; keyed by address she looked gone for 400 days.
        self.commit({"a.py": "x = 1\n"}, ("Rayen", "rayen@old.example"), 400)
        self.commit({"b.py": "y = 1\n"}, ("Rayen", "rayen@new.example"), 10)
        a = self.scan()
        self.assertEqual(len(a.ownership.authors), 1)
        self.assertEqual((a.records["a.py"].owner, a.records["a.py"].owner_idle_days, a.records["a.py"].ownership), ("Rayen", 10, "owned"))

    def test_a_name_that_is_an_address_falls_back_to_the_address(self):
        self.commit({"a.py": "x = 1\n"}, ("one@example.com", "one@example.com"), 5)
        self.commit({"b.py": "y = 1\n"}, ("two@example.com", "two@example.com"), 5)
        self.assertEqual(len(self.scan().ownership.authors), 2)


class BulkCommitTest(History):
    def test_a_mass_edit_does_not_take_ownership_from_the_people_who_maintain_the_files(self):
        self.commit({"a.py": "x = 1\n", "b.py": "y = 1\n"}, ALICE, 10)
        self.commit({"a.py": "x = 2\n", "b.py": "y = 2\n", "c.py": "z = 1\n"}, BOB, 5)
        with mock.patch.object(gitlog, "BULK_FILES", 3):
            recs = self.scan().records
        self.assertEqual(recs["a.py"].owner, "Alice Adams")
        self.assertEqual(recs["c.py"].owner, "Bob Brown")  # nobody else touched it, so the bulk commit is all there is
        recs = self.scan().records  # without the rule the reformat wins
        self.assertEqual(recs["a.py"].owner, "Bob Brown")


class CodeownersParseTest(unittest.TestCase):
    RULES = ownership.parse_codeowners(
        """
# a comment
[Docs] 2
*                        @org/everyone
*.md                     docs@example.com   # trailing comment
/src/                    @alice
/src/api/*.py            @bob @org/api
/guide/*                 @guide
docs/                    @carol
/legacy
\\#odd.txt                @hash
"""
    )

    def owners(self, path):
        return ownership.declared_for(self.RULES, path)

    def test_later_rules_win_and_unanchored_patterns_match_at_any_depth(self):
        self.assertEqual(self.owners("setup.py"), ("@org/everyone",))
        self.assertEqual(self.owners("README.md"), ("docs@example.com",))
        self.assertEqual(self.owners("a/b/notes.md"), ("docs@example.com",))

    def test_directories_cover_everything_below_but_a_wildcard_does_not_recurse(self):
        self.assertEqual(self.owners("src/x/y.py"), ("@alice",))
        self.assertEqual(self.owners("src/api/h.py"), ("@bob", "@org/api"))
        self.assertEqual(self.owners("src/api/sub/h.py"), ("@alice",))
        self.assertEqual(self.owners("guide/a.md"), ("@guide",))
        self.assertEqual(self.owners("guide/sub/a.md"), ("docs@example.com",))  # `*` stops at a slash: the earlier *.md rule is the last to match
        self.assertEqual(self.owners("pkg/docs/guide.rst"), ("@carol",))

    def test_a_rule_without_owners_leaves_paths_unowned_and_escapes_work(self):
        self.assertEqual(self.owners("legacy/x.py"), ())
        self.assertEqual(self.owners("#odd.txt"), ("@hash",))

    def test_first_location_found_wins(self):
        texts = {".github/CODEOWNERS": "* @a\n", "CODEOWNERS": "* @b\n"}
        path, rules = ownership.find_codeowners(set(texts), texts.get)
        self.assertEqual((path, rules[0].owners), (".github/CODEOWNERS", ("@a",)))
        self.assertIsNone(ownership.find_codeowners({"README.md"}, texts.get))


class CodeownersScenarioTest(Scenario):
    def declare(self, text):
        write_tree(self.root, {".github/CODEOWNERS": text})
        return self.scan()

    def test_declared_owners_are_compared_with_the_people_who_maintain_the_files(self):
        a = self.declare("/core/ alice@example.com\n/shared/ @bob-brown\n/legacy/old.py @someone-else\n")
        recs = a.records
        self.assertEqual((recs["core/a.py"].declared_owners, recs["core/a.py"].declared_match), (["alice@example.com"], True))
        self.assertIsNone(recs["shared/x.py"].declared_match)  # Alice maintains it and her address reveals no GitHub login: cannot say
        self.assertEqual((recs["legacy/old.py"].declared_owners, recs["legacy/old.py"].declared_match), (["@someone-else"], False))
        co = build_report(a)["ownership"]["codeowners"]
        self.assertEqual((co["file"], co["rules"]), (".github/CODEOWNERS", 3))
        self.assertEqual({f["path"] for f in co["uncovered_files"]}, {"legacy/more.py", "main.py"})
        self.assertEqual([f["path"] for f in co["differing_files"]], ["legacy/old.py"])
        self.assertEqual(co["differing_files"][0]["observed"], "Bob Brown")

    def test_a_declared_login_is_matched_through_noreply_addresses(self):
        recs = self.declare("/legacy/ @Bob-Brown\n").records
        self.assertTrue(recs["legacy/old.py"].declared_match)

    def test_teams_cannot_be_compared(self):
        recs = self.declare("* @org/team\n").records
        self.assertEqual(recs["core/a.py"].declared_owners, ["@org/team"])
        self.assertIsNone(recs["core/a.py"].declared_match)
        self.assertIsNone(recs["legacy/old.py"].declared_match)  # Bob's login is known, yet git cannot tell whether he is in the team

    def test_without_a_codeowners_file_nothing_is_declared(self):
        a = self.scan()
        self.assertIsNone(a.records["core/a.py"].declared_owners)
        self.assertIsNone(build_report(a)["ownership"]["codeowners"])
        self.assertIn("CODEOWNERS", markdown(build_report(self.declare("* @org/team\n")), 40))


if __name__ == "__main__":
    unittest.main()
