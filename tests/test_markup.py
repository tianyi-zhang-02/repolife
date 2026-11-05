"""A page wires in what it loads and mentions what it says: `<script src>` makes an entry point, while a file named in
the page's text or linked from it is documented, not used, like a file named in a README."""

import unittest

from helpers import TempRepo, write_tree

from tessri import config
from tessri.analyze import analyze
from tessri.explain import explain
from tessri.textrefs import scan_html

PAGE = """<!doctype html><!-- tools/gen.py -->
<head><link rel="stylesheet" href="site.css"><link rel="modulepreload" href="/src/boot.ts"></head>
<body>
<script type="module" src='/src/main.tsx'></script>
<script>import("./app.js"); const x = "pkg.dyn";</script>
<style>.a { background: url(theme.py) }</style>
<p>See <code>pkg/core.py</code> and <a href="scripts/run.py">the script</a>, or <b>pkg.util.helper</b>.</p>
<img src=static/logo.png alt="pkg/alt.py">
</body>
"""


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.wiring, self.mentions = scan_html(PAGE)

    def test_what_the_page_loads_and_its_inline_script_are_wiring(self):
        self.assertEqual(self.wiring.paths, {"/src/main.tsx", "/src/boot.ts", "./app.js"})  # src, <link href>, import() in a script
        self.assertEqual(self.wiring.dotted, {"pkg.dyn"})
        self.assertFalse(self.wiring.weak)

    def test_its_text_its_links_and_its_other_attributes_are_a_mention(self):
        self.assertEqual(self.mentions.paths, {"pkg/core.py", "scripts/run.py", "pkg/alt.py"})
        self.assertEqual(self.mentions.dotted, {"pkg.util.helper"})
        self.assertTrue(self.mentions.weak)

    def test_comments_and_styles_say_nothing(self):
        for found in (self.wiring, self.mentions):
            self.assertNotIn("tools/gen.py", found.paths)
            self.assertNotIn("theme.py", found.paths)


TREE = {
    "pkg/__init__.py": "",
    "pkg/core.py": "x = 1\n",
    "pkg/dead.py": "y = 2\n",
    "pkg/linked.py": "z = 3\n",
    "static/app.js": "console.log(1);\n",
    "static/boot.js": "console.log(2);\n",
    "scripts/run.py": "import pkg.core\n",
    "site/index.html": (
        '<link rel="modulepreload" href="/static/boot.js">\n'
        '<script src="static/app.js"></script>\n'
        '<p>Delete <code>pkg/dead.py</code>; see <a href="../pkg/linked.py">the linked file</a>.</p>\n'
    ),
    ".tessri.toml": 'entry = ["scripts/run.py"]\n',
}


class PageTest(TempRepo):
    def setUp(self):
        super().setUp()
        write_tree(self.root, TREE)
        self.a = analyze(self.root, config.load(self.root))

    def test_what_the_page_loads_is_an_entry_point(self):
        for path in ("static/app.js", "static/boot.js"):
            self.assertEqual(self.a.records[path].roots, ["config-ref: site/index.html"], path)
            self.assertEqual(self.a.records[path].reachability, "prod", path)

    def test_what_the_page_says_or_links_to_is_a_mention(self):
        for path in ("pkg/dead.py", "pkg/linked.py"):
            rec = self.a.records[path]
            self.assertEqual((rec.status, rec.confidence, rec.roots), ("ORPHAN", "medium", []), path)
            self.assertIn("mentioned in docs: site/index.html", rec.notes)
        text = explain(self.a, "pkg/dead.py")
        self.assertIn("named in config/scripts: none", text)
        self.assertIn("mentioned in docs: site/index.html", text)


class DocsPageTest(TempRepo):
    def test_a_page_under_docs_only_mentions_even_what_it_loads(self):
        write_tree(self.root, {"static/app.js": "console.log(1);\n", "docs/page.html": '<script src="../static/app.js"></script>\n'})
        a = analyze(self.root, config.load(self.root))
        rec = a.records["static/app.js"]
        self.assertEqual((rec.status, rec.roots), ("ORPHAN", []))
        self.assertIn("mentioned in docs: docs/page.html", rec.notes)


if __name__ == "__main__":
    unittest.main()
