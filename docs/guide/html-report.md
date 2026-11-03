# The HTML report

One self-contained page: the overview, the module graph, an impact explorer, ownership and cleanup, offline, in
light and dark.

```bash
tessri scan . --format html --out report.html
```

One self-contained file: styles, script and data are inside it, nothing is fetched, and Python renders all
sections, so it reads without scripts and prints. With scripts enabled, four primary navigation entries open
one focused view at a time; additional sections are under **More views**. Use **⌘K / Ctrl+K** to find a view,
analyzed file or directory; choosing a path opens its impact
analysis. Escape closes quick navigation, and the arrow keys and Enter select a result. Section links and
browser Back/Forward work, and switching views preserves the current query and filters. Impact queries are
carried in the URL fragment, including relationship policy and step limit, so refreshing or reopening the
same report at that URL restores the query. Typing updates the current entry without adding history per
keystroke. The repository and
snapshot revision remain visible; the report is a captured analysis, not a live workspace connection.

| Section | What it is for |
|---|---|
| Overview | lines of code, how much is unreachable or recently changed, people and bus factor, module cycles, and the code split by status |
| Where to look first | the top of three longer tables: probably unused, nobody active maintains, dependencies to untangle |
| Directories | size, status mix and owners per directory; click a heading to sort |
| Modules | the dependency graph (users on the left, what they build on to the right, cuts that break a cycle in red; click a module to highlight what it uses and what uses it), the cycles with their cut lists, and every module in a table |
| Impact | type an analyzed file or directory; compare all relationships with recognized imports and Python parent packages, limit the number of steps, inspect inferred evidence and candidate tests |
| Review load | a bar per area for the lines changed, split by an owner, someone else and bots; who the changes land on; the largest changes |
| Ownership, hotspots, cleanup | the same tables as the Markdown report, with filters on the long ones |

The impact explorer walks the relationship graph embedded in the page. Its evidence selector corresponds to
`tessri impact --edges all|imports`; its step limit corresponds to `--hops`. Tests compare both policies with
the Python implementation for every analyzed file and directory of this repository, including the evidence
counts and bounded reference examples. Inferred links are disclosed rather than presented as confirmed runtime
dependencies, and candidate test paths do not record test execution. Two differences: it names the top
owner of each affected file rather than a rolled-up share, and it is left out (with a note) past 20,000 analysed
files, where `tessri impact` still works. Status colours are four hues chosen to stay apart under common colour
blindness, and every one is repeated in text. Names are escaped everywhere, and emails never reach the page.
