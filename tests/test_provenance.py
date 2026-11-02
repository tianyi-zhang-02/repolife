"""Edge provenance and `impact --edges`: which evidence an edge rests on, and a walk that follows only recognized
dependency syntax. The default walk and every field it had before provenance existed stay the same."""

import contextlib
import io
import json
import unittest

from helpers import TempRepo, write_tree
from tessri import analyze, cli, config, graphview, modules
from tessri.analyzers import KINDS, Analyzer, LanguageResult, note
from tessri.analyzers.python import PythonAnalyzer

# One real import, a dotted string, a transitive importer of the string holder, a literal import_module() call, a
# file with both kinds of evidence for the same target, and a test on each route.
PYTHON = {
    "pkg/__init__.py": "",
    "pkg/sub/__init__.py": "",
    "pkg/sub/leaf.py": "VALUE = 1\n",
    "explicit.py": "import pkg.sub.leaf\n",
    "heuristic.py": 'VALUE = "pkg.sub.leaf"\n',
    "bridge.py": "import heuristic\n",
    "loader.py": 'import importlib\nmodule = importlib.import_module("pkg.sub.leaf")\n',
    "both.py": 'import pkg.sub.leaf\nVALUE = "pkg.sub.leaf"\n',
    "tests/test_import.py": "import explicit\n",
    "tests/test_guess.py": "import bridge\n",
}

# The same shape for the JS/TS scanner: a literal import, a path string, a transitive importer, a literal import(),
# a computed import(), a glob, a file with both import and string evidence, and a test on each route.
TYPESCRIPT = {
    "src/leaf.ts": "export const value = 1;\n",
    "src/explicit.ts": 'import {value} from "./leaf"; console.log(value);\n',
    "src/heuristic.ts": 'export const text = "./leaf.ts";\n',
    "src/bridge.ts": 'import "./heuristic";\n',
    "src/literal.ts": 'export const promise = import("./leaf");\n',
    "src/computed.ts": "export const promise = import(`./${name}.ts`);\n",
    "src/glob.ts": 'export const modules = import.meta.glob("./*.ts");\n',
    "src/both.ts": 'import "./leaf"; export const text = "./leaf.ts";\n',
    "tests/import.test.ts": 'import "../src/explicit";\n',
    "tests/guess.test.ts": 'import "../src/bridge";\n',
}


def scan(root, analyzers=None):
    return analyze.analyze(root, config.load(root), analyzers=analyzers)


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class KindsTest(unittest.TestCase):
    def test_strongest_evidence_wins_for_a_pair(self):
        prov = {}
        note(prov, "x", "string")
        note(prov, "x", "package")
        note(prov, "x", "dynamic")
        self.assertEqual(prov, {"x": "package"})
        note(prov, "x", "import")
        note(prov, "x", "unknown")
        self.assertEqual(prov, {"x": "import"})
        self.assertEqual(KINDS, ("import", "package", "dynamic", "string", "unknown"))

    def test_language_result_keeps_its_positional_parameters(self):
        res = LanguageResult({"a": {"b"}}, {"a": {"b"}}, {"a": ["main-guard"]}, set(), set(), {}, lambda ref: set())
        self.assertEqual((res.edges, res.indirect, res.roots), ({"a": {"b"}}, {"a": {"b"}}, {"a": ["main-guard"]}))
        self.assertEqual(res.provenance, {})


class PythonProvenanceTest(TempRepo):
    def setUp(self):
        super().setUp()
        write_tree(self.root, PYTHON)
        self.a = scan(self.root)
        self.g = self.a.graph

    def test_every_edge_has_the_kind_of_its_evidence(self):
        kind = self.g.kind
        self.assertEqual(kind("explicit.py", "pkg/sub/leaf.py"), "import")
        self.assertEqual(kind("explicit.py", "pkg/__init__.py"), "package")
        self.assertEqual(kind("explicit.py", "pkg/sub/__init__.py"), "package")
        self.assertEqual(kind("heuristic.py", "pkg/sub/leaf.py"), "string")
        self.assertEqual(kind("loader.py", "pkg/sub/leaf.py"), "string")  # the analyzer does not read the call around the literal
        self.assertEqual(kind("both.py", "pkg/sub/leaf.py"), "import")  # the string does not weaken the import
        self.assertEqual(kind("bridge.py", "heuristic.py"), "import")
        self.assertEqual(kind("tests/test_import.py", "explicit.py"), "import")
        self.assertEqual(kind("nobody.py", "pkg/sub/leaf.py"), "unknown")  # no edge recorded at all

    def test_edges_and_indirect_are_what_they_were(self):
        # `indirect` still lumps the package run and the string together: the module graph, check and the explorer read it.
        self.assertEqual(self.g.edges["heuristic.py"], {"pkg/__init__.py", "pkg/sub/__init__.py", "pkg/sub/leaf.py"})
        self.assertEqual(self.g.indirect["heuristic.py"], self.g.edges["heuristic.py"])
        self.assertEqual(self.g.indirect["explicit.py"], {"pkg/__init__.py", "pkg/sub/__init__.py"})

    def test_default_walk_is_unchanged_and_declares_itself(self):
        imp = modules.impact(self.a, "pkg/sub/leaf.py")
        d, t, e = imp["dependents"], imp["tests"], imp["edges"]
        self.assertEqual((d["direct"], d["files"], d["by_distance"]), (4, 5, [4, 1]))
        self.assertEqual((t["files"], t["direct"], t["paths"]), (2, 0, ["tests/test_import.py", "tests/test_guess.py"]))
        self.assertEqual((e["policy"], e["hops"], e["kinds"]), ("all", None, list(KINDS)))
        # explicit, both -> leaf; bridge -> heuristic; test_import -> explicit; test_guess -> bridge
        self.assertEqual(e["followed"], {"import": 5, "package": 0, "dynamic": 0, "string": 2, "unknown": 0})
        self.assertEqual(e["excluded"], {})
        self.assertEqual(e["references"]["count"], 2)
        self.assertEqual(e["references"]["limit"], modules.REFERENCES_LISTED)
        self.assertEqual(
            e["references"]["listed"],
            [{"from": "heuristic.py", "to": "pkg/sub/leaf.py", "kind": "string"}, {"from": "loader.py", "to": "pkg/sub/leaf.py", "kind": "string"}],
        )
        self.assertEqual(e["unclassified"], {"edges": 0, "analyzers": []})
        self.assertEqual(e["imports_only"], {"files": 2, "tests": 1})

    def test_imports_view_drops_the_string_routes_and_their_test(self):
        imp = modules.impact(self.a, "pkg/sub/leaf.py", edges="imports")
        d, t, e = imp["dependents"], imp["tests"], imp["edges"]
        self.assertEqual((d["direct"], d["files"], d["by_distance"]), (2, 2, [2]))
        self.assertEqual((t["files"], t["direct"], t["paths"]), (1, 0, ["tests/test_import.py"]))
        self.assertEqual((e["policy"], e["kinds"]), ("imports", ["import", "package"]))
        self.assertEqual(e["followed"], {"import": 3, "package": 0})
        self.assertEqual(e["excluded"], {"dynamic": 0, "string": 2, "unknown": 0})
        self.assertEqual(e["references"]["count"], 2)  # the excluded edges stay visible
        self.assertNotIn("imports_only", e)

    def test_package_initializer_is_reached_through_package_edges(self):
        imp = modules.impact(self.a, "pkg/__init__.py", edges="imports")
        e = imp["edges"]
        self.assertEqual((imp["dependents"]["direct"], imp["dependents"]["files"], imp["tests"]["files"]), (2, 2, 1))
        self.assertEqual(e["followed"], {"import": 1, "package": 2})
        self.assertEqual(e["excluded"]["string"], 2)

    def test_hop_limit_applies_to_the_selected_edges(self):
        one = modules.impact(self.a, "pkg/sub/leaf.py", hops=1, edges="imports")
        self.assertEqual((one["dependents"]["files"], one["tests"]["files"], one["edges"]["hops"]), (2, 0, 1))
        self.assertEqual(one["edges"]["followed"], {"import": 2, "package": 0})  # nodes at the limit are not expanded
        two = modules.impact(self.a, "pkg/sub/leaf.py", hops=2)
        self.assertEqual((two["dependents"]["files"], two["tests"]["files"]), (5, 1))
        self.assertEqual(two["edges"]["imports_only"], {"files": 2, "tests": 1})

    def test_directory_target_excludes_its_own_seeds(self):
        imp = modules.impact(self.a, "pkg/sub", edges="imports")
        self.assertEqual((imp["dependents"]["direct"], imp["dependents"]["files"]), (2, 2))
        self.assertEqual(imp["edges"]["followed"], {"import": 3, "package": 2})
        self.assertEqual(imp["edges"]["excluded"]["string"], 4)

    def test_unknown_policy_is_refused(self):
        with self.assertRaises(ValueError):
            modules.impact(self.a, "pkg/sub/leaf.py", edges="explicit")


class TypeScriptProvenanceTest(TempRepo):
    def setUp(self):
        super().setUp()
        write_tree(self.root, TYPESCRIPT)
        self.a = scan(self.root)
        self.g = self.a.graph

    def test_kinds_of_the_scanner_forms(self):
        kind = self.g.kind
        self.assertEqual(kind("src/explicit.ts", "src/leaf.ts"), "import")
        self.assertEqual(kind("src/literal.ts", "src/leaf.ts"), "import")  # a literal import() is recognized syntax
        self.assertEqual(kind("src/both.ts", "src/leaf.ts"), "import")
        self.assertEqual(kind("src/heuristic.ts", "src/leaf.ts"), "string")
        self.assertEqual(kind("src/computed.ts", "src/leaf.ts"), "dynamic")
        self.assertEqual(kind("src/glob.ts", "src/leaf.ts"), "dynamic")

    def test_js_edges_are_what_they_were(self):
        # The scanner never marked anything `indirect`; provenance is beside that, so graph and check keep their JS edges.
        self.assertIn("src/leaf.ts", self.g.edges["src/heuristic.ts"])
        self.assertEqual(self.g.indirect.get("src/heuristic.ts", set()), set())
        self.assertEqual(self.g.indirect.get("src/glob.ts", set()), set())

    def test_views_on_the_leaf(self):
        every = modules.impact(self.a, "src/leaf.ts")
        self.assertEqual((every["dependents"]["direct"], every["dependents"]["files"], every["tests"]["files"]), (6, 7, 2))
        self.assertEqual(every["edges"]["followed"], {"import": 6, "package": 0, "dynamic": 14, "string": 1, "unknown": 0})
        self.assertEqual(every["edges"]["imports_only"], {"files": 3, "tests": 1})
        narrow = modules.impact(self.a, "src/leaf.ts", edges="imports")
        self.assertEqual((narrow["dependents"]["direct"], narrow["dependents"]["files"], narrow["tests"]["files"]), (3, 3, 1))
        self.assertEqual(narrow["edges"]["excluded"], {"dynamic": 8, "string": 1, "unknown": 0})
        self.assertEqual(narrow["edges"]["references"]["count"], 9)
        self.assertEqual(len(narrow["edges"]["references"]["listed"]), modules.REFERENCES_LISTED)  # cut, and the count says so

    def test_depends_on_is_filtered_under_imports_and_kept_under_all(self):
        self.assertEqual(modules.impact(self.a, "src/heuristic.ts")["depends_on"], [{"module": "src", "files": 1}])
        self.assertEqual(modules.impact(self.a, "src/heuristic.ts", edges="imports")["depends_on"], [])
        self.assertEqual(modules.impact(self.a, "src/both.ts", edges="imports")["depends_on"], [{"module": "src", "files": 1}])


class PathStringTest(TempRepo):
    def test_a_bare_dunder_file_name_in_a_string_is_a_string_edge(self):
        write_tree(self.root, {"pkg/__init__.py": "", "pkg/__main__.py": "print(1)\n", "pkg/names.py": 'SPECIAL = {"__main__.py", "setup.py"}\n', "pkg/guard.py": 'if __name__ == "__main__":\n    pass\n'})
        a = scan(self.root)
        self.assertEqual(a.graph.kind("pkg/names.py", "pkg/__main__.py"), "string")
        self.assertNotIn("pkg/__main__.py", a.graph.edges.get("pkg/guard.py", set()))  # the idiom alone makes no edge
        every = modules.impact(a, "pkg/__main__.py")
        narrow = modules.impact(a, "pkg/__main__.py", edges="imports")
        self.assertEqual((every["dependents"]["files"], narrow["dependents"]["files"]), (1, 0))
        self.assertEqual(narrow["edges"]["references"]["listed"], [{"from": "pkg/names.py", "to": "pkg/__main__.py", "kind": "string"}])


class DynamicLoadingTest(TempRepo):
    def test_a_literal_list_loop_is_dynamic_evidence(self):
        write_tree(self.root, {
            "pkg/__init__.py": "", "pkg/plugins/__init__.py": "", "pkg/plugins/alpha.py": "X = 1\n", "pkg/plugins/beta.py": "X = 2\n",
            "pkg/loader.py": 'from importlib import import_module\nfor n in ("alpha", "beta"):\n    import_module(f"pkg.plugins.{n}")\n',
        })
        a = scan(self.root)
        self.assertEqual(a.graph.kind("pkg/loader.py", "pkg/plugins/alpha.py"), "dynamic")
        every = modules.impact(a, "pkg/plugins/alpha.py")
        narrow = modules.impact(a, "pkg/plugins/alpha.py", edges="imports")
        self.assertEqual((every["dependents"]["files"], narrow["dependents"]["files"]), (1, 0))
        self.assertEqual(narrow["edges"]["excluded"]["dynamic"], 1)


class Stub(Analyzer):
    """An analyzer written before provenance existed: edges only."""

    name = "stub"

    def handles(self, path):
        return path.endswith(".go")

    def run(self, files, repo):
        return LanguageResult(edges={"main.go": {"pkg/sub/leaf.py"}}, roots={"main.go": ["main"]})


class UnknownProvenanceTest(TempRepo):
    def setUp(self):
        super().setUp()
        write_tree(self.root, {**PYTHON, "main.go": "package main\n"})
        self.a = scan(self.root, analyzers=[PythonAnalyzer(), Stub()])

    def test_an_old_plugin_keeps_working_and_its_edges_are_visibly_unknown(self):
        self.assertEqual(self.a.graph.kind("main.go", "pkg/sub/leaf.py"), "unknown")
        every = modules.impact(self.a, "pkg/sub/leaf.py")
        self.assertEqual(every["dependents"]["direct"], 5)
        self.assertEqual(every["edges"]["followed"]["unknown"], 1)
        self.assertEqual(every["edges"]["unclassified"], {"edges": 1, "analyzers": ["stub"]})
        narrow = modules.impact(self.a, "pkg/sub/leaf.py", edges="imports")
        self.assertEqual(narrow["dependents"]["direct"], 2)
        self.assertEqual(narrow["edges"]["excluded"]["unknown"], 1)
        self.assertEqual(narrow["edges"]["unclassified"], {"edges": 1, "analyzers": ["stub"]})
        self.assertIn({"from": "main.go", "to": "pkg/sub/leaf.py", "kind": "unknown"}, narrow["edges"]["references"]["listed"])


class CliTest(TempRepo):
    def setUp(self):
        super().setUp()
        write_tree(self.root, PYTHON)

    def test_flag_json_text_and_errors_agree(self):
        code, out, _ = run_cli(["impact", "pkg/sub/leaf.py", "--repo", str(self.root), "--format", "json", "--edges", "imports"])
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual((doc["edges"]["policy"], doc["dependents"]["files"]), ("imports", 2))
        code, out, _ = run_cli(["impact", "pkg/sub/leaf.py", "--repo", str(self.root), "--format", "json"])
        self.assertEqual((code, json.loads(out)["edges"]["policy"]), (0, "all"))
        code, text, _ = run_cli(["impact", "pkg/sub/leaf.py", "--repo", str(self.root), "--edges", "imports"])
        self.assertEqual(code, 0)
        self.assertIn("edges followed, any number of steps: recognized dependency syntax and the package files Python runs for it; 2 string, dynamic or unclassified edges met at the frontier not followed (for example `heuristic.py` → `pkg/sub/leaf.py`, string)", text)
        self.assertIn("2 of them directly (one followed edge away)", text)
        self.assertIn("candidates to run, not runs", text)
        self.assertIn("under the selected edge policy and hop limit", text)
        self.assertNotIn("Static imports only", text)
        code, text, _ = run_cli(["impact", "pkg/sub/leaf.py", "--repo", str(self.root)])
        self.assertIn("edges followed, any number of steps: recognized dependency syntax, package files, and 2 references found in strings, dynamic loading or unclassified evidence (for example `heuristic.py` → `pkg/sub/leaf.py`, string); syntax and package files alone reach 2 code files and 1 test file", text)
        code, text, _ = run_cli(["impact", "pkg/sub/leaf.py", "--repo", str(self.root), "--hops", "1", "--edges", "imports"])
        self.assertIn("edges followed, at most 1 step: recognized dependency syntax", text)
        code, text, _ = run_cli(["impact", "pkg/sub/leaf.py", "--repo", str(self.root), "--hops", "2"])
        self.assertIn("edges followed, at most 2 steps: recognized dependency syntax, package files", text)
        self.assertIn("syntax and package files alone reach 2 code files and 1 test file", text)  # the same hop limit, so the same reach here
        with self.assertRaises(SystemExit) as stop:
            run_cli(["impact", "pkg/sub/leaf.py", "--repo", str(self.root), "--edges", "explicit"])
        self.assertEqual(stop.exception.code, 2)

    def test_text_for_a_target_nothing_reaches(self):
        text = graphview.impact_text(modules.impact(scan(self.root), "tests/test_guess.py", edges="imports"))
        self.assertIn("no file in the analysed set depends on it through the followed edges", text)
        self.assertIn("edges followed, any number of steps: recognized dependency syntax", text)


if __name__ == "__main__":
    unittest.main()
