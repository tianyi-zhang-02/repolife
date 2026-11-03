# Limits

What the analysis cannot see, it says it cannot see. This is the list.

- Reachability is static. Reflection, plugin discovery by directory scan, and consumers outside the
  repository are invisible; that is why `ORPHAN` is a candidate and `why` exists.
- Only Python and JavaScript/TypeScript have analyzers today. Everything else (Go, Rust, Java ...) gets volume and activity.
- JavaScript specifics it cannot see: aliases defined only in a bundler config (`vite.config`, `webpack.config`;
  `@/` and `~/` are guessed), `exports` wildcard patterns as entry points (list those under `keep`), auto-imports
  (`unplugin-auto-import`, Nuxt-style component directories outside the frameworks above), a `require()` written
  inside a template literal's `${}`, and scripts in extensionless hook files such as `.husky/pre-commit`.
- Git activity needs history: a shallow clone truncates it, and a repository with no commits yet
  reports statuses as `UNKNOWN`. A moved file keeps its history when git recognises the move (its default
  similarity threshold); a file rewritten beyond recognition when moved starts over, and a path re-created after a
  move is a new file. `triage` and `check` still see a move as a deletion and an addition.
- The HTML explorer's script is exercised against the Python implementation, but the page's sorting and filtering
  are checked by hand in a browser, not by an automated test.
- The module graph is static imports between Python and JavaScript/TypeScript files. A package that re-exports
  everything (a busy `__init__.py` or `index.ts`) makes the modules importing through it look more tangled than
  their real call graph, and registries, dependency injection and dynamic loading leave no edge, so a missing
  dependency is not proof there is none.
- A dotted name or path in a string is an edge of kind `string`, and `impact` follows it by default. A tool that
  names files in strings links itself to them: Tessri's own Python analyzer holds the string `__main__.py`, so
  on this repository `impact tessri/cli.py` reaches the analyzers from the CLI by default and `--edges imports`
  does not. The bare `if __name__ == "__main__"` idiom makes no edge.
- Review load counts lines changed, not effort: a generated file that is not excluded, or a mechanical rename of one
  symbol, weighs as much as careful work. It cannot see who reviewed, and it does not see branches that never
  reached the history it reads.
- Ownership says who has been *changing* code, not who is accountable, and git cannot tell who *reviewed* it.
  Squash merges credit the person who merged, a person with different names on different machines counts as
  several, and two people with one name count as one. Work done in another repository or before a history
  rewrite is invisible. Read it as a prompt to ask, not as an assignment.
- Symbol-level dead code (unused functions inside live files) is out of scope; use a tool like
  [vulture](https://github.com/jendrikseipp/vulture). For multi-language dead-code detection see
  [fossil-mcp](https://docs.rs/crate/fossil-mcp/latest/source/README.md); for churn x complexity on
  JS/TS see [fallow](https://docs.rs/crate/fallow-cli/2.94.0).
