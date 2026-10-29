"""Differential test for the JS/TS scanner: compare the module specifiers repolife finds with the TypeScript compiler's.

The scanner reads imports without a parser, so the only way to trust it is to check it against one.
Point it at any directory of real code (a `node_modules` is ideal) and at a TypeScript install:

    python3 tools/diff_js_scanner.py path/to/node_modules --typescript path/to/node_modules/typescript --sample 5000

Needs `node`. Prints how many files match exactly and lists every specifier one side missed.
`/// <reference path>` lines are dropped before scanning because the compiler does not call them module specifiers.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repolife.analyzers.jslex import scan  # noqa: E402

EXTS = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".mts", ".cts"}

ORACLE = """
const ts = require(process.argv[1]);  // with `node -e`, argv[0] is node and the first extra argument is argv[1]
const fs = require("fs");
const kind = (f) => /\\.tsx$/.test(f) ? ts.ScriptKind.TSX : /\\.[cm]?ts$/.test(f) ? ts.ScriptKind.TS : /\\.jsx$/.test(f) ? ts.ScriptKind.JSX : ts.ScriptKind.JS;
const lit = (n) => n && (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) ? n.text : null;
const out = {};
for (const f of fs.readFileSync(0, "utf8").split("\\n").filter(Boolean)) {
  const sf = ts.createSourceFile(f, fs.readFileSync(f, "utf8"), ts.ScriptTarget.Latest, true, kind(f));
  const specs = [];
  const visit = (n) => {
    if ((ts.isImportDeclaration(n) || ts.isExportDeclaration(n)) && lit(n.moduleSpecifier) !== null) specs.push(lit(n.moduleSpecifier));
    else if (ts.isImportEqualsDeclaration(n) && ts.isExternalModuleReference(n.moduleReference) && lit(n.moduleReference.expression) !== null) specs.push(lit(n.moduleReference.expression));
    else if (ts.isCallExpression(n) && n.arguments.length >= 1 && lit(n.arguments[0]) !== null) {
      const e = n.expression;
      if (e.kind === ts.SyntaxKind.ImportKeyword || (ts.isIdentifier(e) && e.text === "require")) specs.push(lit(n.arguments[0]));
      else if (ts.isPropertyAccessExpression(e) && e.name.text === "resolve" && ts.isIdentifier(e.expression) && e.expression.text === "require") specs.push(lit(n.arguments[0]));
    } else if (ts.isImportTypeNode(n) && ts.isLiteralTypeNode(n.argument) && lit(n.argument.literal) !== null) specs.push(lit(n.argument.literal));
    ts.forEachChild(n, visit);
  };
  visit(sf);
  out[f] = specs;
}
process.stdout.write(JSON.stringify(out));
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("corpus", type=Path, help="directory of real JS/TS code")
    ap.add_argument("--typescript", type=Path, required=True, help="directory of an installed `typescript` package")
    ap.add_argument("--sample", type=int, default=3000, help="files to compare (default 3000)")
    ap.add_argument("--max-bytes", type=int, default=300_000, help="skip bigger files (default 300000)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    files = sorted(p for p in args.corpus.rglob("*") if p.suffix in EXTS and p.is_file() and p.stat().st_size <= args.max_bytes)
    random.Random(args.seed).shuffle(files)
    names = [str(p) for p in files[: args.sample]]
    run = subprocess.run(["node", "-e", ORACLE, str(args.typescript.resolve())], input="\n".join(names), capture_output=True, text=True)
    if run.returncode != 0:
        print(run.stderr, file=sys.stderr)
        return 2
    oracle = json.loads(run.stdout)

    identical = unparsed = 0
    diffs: list[tuple[str, str, str]] = []
    for name in names:
        text = "\n".join(line for line in Path(name).read_text(encoding="utf-8", errors="replace").split("\n") if not line.startswith("///"))
        mine = scan(text)
        if mine is None:
            unparsed += 1
            diffs.append(("UNPARSED", name, ""))
            continue
        want, got = Counter(oracle[name]), Counter(mine.specs)
        if want == got:
            identical += 1
        diffs += [("MISSED", name, s) for s in (want - got)] + [("SPURIOUS", name, s) for s in (got - want)]
    print(f"files={len(names)} identical={identical} unparsed={unparsed} missed={sum(d[0] == 'MISSED' for d in diffs)} spurious={sum(d[0] == 'SPURIOUS' for d in diffs)}")
    for kind, name, spec in diffs[:40]:
        print(f"  {kind:8} {Path(name).relative_to(args.corpus)}  {spec}")
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
