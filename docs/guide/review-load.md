# Review load

How much review do the recent changes ask for, where did they land, and on whom? Every `scan` has a `review`
section that answers it for the last `review_days` days.

When a codebase grows faster than anyone can read it, the useful question is how much review the recent changes ask
for, and from whom. Every report has a `review` section for the last `review_days` days (30) against the same number
of days before:

| Question | Where |
|---|---|
| How much code changed, and is that more than before? | lines added plus deleted in code files, with the change against the previous window |
| Where did it change? | areas (directories, split by size like the modules), with commits, people and the change per area |
| Who made the changes? | per area: who changed it, and *by outsiders*, the share of the people's lines written by someone who is not among the area's owners |
| Did it land where nobody can look? | lines that landed in areas with no active owner |
| Who is it landing on? | the people who maintain the areas that others changed, by lines from others, with those who went quiet marked |
| What is hardest to review? | the largest single commits, with their subject and the area they mostly touched |

```text
$ tessri scan . --review-days 30
## Review load

- **19** lines changed in code files (+533% against 3 before), in 4 commits across 3 areas by 2 people
- 2 of those lines came from bots or ignored authors
- **2** lines (10.5%) landed in 1 area that nobody active maintains: nobody who knows that code is around to look

| Area | Changed lines | Against before | Commits | People | By outsiders | Owners | State |
|---|---:|---:|---:|---:|---:|---|---|
| `core` | 10 | +233% | 2 | 2 | 40.0% | Alice Adams 94% | owned |
| `web` | 7 | new | 1 | 1 | 0.0% | Carol Chen 100% | owned |
| `legacy` | 2 | new | 1 | 0 | - | Bob Brown 100% (silent 290d) | no active owner |

| Person | Lines from others | Areas | State |
|---|---:|---:|---|
| Alice Adams | 4 | 1 | active |
| Bob Brown | 2 | 1 | silent for 290 days |
```

This measures *demand* for review. Git records who changed code, not who reviewed it, so nothing here says a change
was or was not looked at. Only code files count: configuration and docs are summed apart, and files the scan
leaves out (`node_modules`, lock files, generated code, anything under `exclude`) are ignored. Bots and
`ignore_authors` still count as changes that need a look but never as people. A commit touching 300 or more files
(a reformat, a vendor drop) is left out of the areas and reported under `totals.bulk`, since nobody reads it line by
line. The window is cut by author date, so a rebased commit keeps the date it was written. In the HTML report the
section has a bar per area split into changes by an owner, by someone else, and by bots.

*By outsiders* leans on who counts as an owner, which is everyone holding at least 10% of an area's recent
maintenance. Where ownership is spread thin, most changes are by "outsiders" simply because the owners are many and
each holds little; read it together with the *Owners* column.
