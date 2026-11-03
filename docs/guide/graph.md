# How the modules fit together

`tessri graph` rolls the file-level import graph up into modules and finds the cycles and the few dependencies to
cut to break them.

`tessri graph` rolls the file-level import graph up into modules. A module is a directory; unless you pass
`--module-depth N`, directories are split until none holds much more than a twelfth of the code files, so one
big package still shows its parts. Test files are left out (every module is imported by its tests); add
`--include-tests` to draw them.

```text
$ tessri graph
**4 modules**, **5 dependencies** between them and **1 cycle**, from 5 imports across 8 code files. ...

**Cycle 1**: `billing` ⇄ `core`. 2 imports among them; 1 dependency (1 import) to cut:

| From | To | Imports | For example |
|---|---|---:|---|
| `core` | `billing` | 1 | `core/engine.py` imports `billing/invoices.py` |

| Module | Files | Code | Uses | Used by | Cycle |
|---|---:|---:|---:|---:|---|
| `billing` | 2 | 5 | 1 | 2 | 1 |
| `core` | 2 | 4 | 2 | 2 | 1 |
| `util` | 2 | 2 | 0 | 1 | - |
| `app` | 2 | 5 | 2 | 0 | - |
```

| Output | What it gives |
|---|---|
| `tessri graph` | Markdown: cycles, then modules (size, *uses*, *used by*, owners), then the heaviest dependencies |
| `--format json` | `modules` (with `uses`, `used_by`, `instability`, `owners`, `cycle`), `edges` (`imports`, `files`, example imports, `cut`), `cycles` |
| `--format mermaid` / `dot` | a diagram of the heaviest ~80 dependencies, cuts drawn red; `--min-imports N` to choose the threshold |
| `--level file --format json` | every import as a `[from, to]` pair, each file with its module, status and owner |

An *import* is one file importing one other file, so `from pkg import a, b` counts twice. Only what an import
statement names is an edge: importing `a.b.c` also runs `a/__init__.py`, which keeps that file reachable but
does not make the importer depend on the package, and paths or dotted names found in strings, config or
dynamic imports are not edges either.

A cycle comes with a list of the dependencies that point against its dominant direction. Removing or
inverting exactly those leaves no cycle, and putting any one back makes one again. It is a heuristic for a few,
light edges (the true minimum is NP-hard), but it is deterministic, and the tests check it is acyclic and
irredundant.
