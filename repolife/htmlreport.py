"""The report as one self-contained HTML page: no network, no build step, nothing to install.

Everything is rendered on the server so the page reads without scripts (and prints); a small script adds
sorting, filtering, the module graph's highlighting and an impact explorer that answers `repolife impact`
for any file or directory from the import graph embedded in the page.

Colours: the four statuses use categorical hues ordered so that neighbours stay distinguishable under the
common kinds of colour blindness (checked in both themes), and every colour is repeated in text.
"""

from __future__ import annotations

import html
import json
from collections import defaultdict, deque

from . import __version__, modules
from .analyze import Analysis
from .graphview import drawn
from .htmlassets import CSS, JS, THEME_BOOT
from .model import STATUSES
from .render import _STATE_TEXT, _owners
from .report import build_report

_STATUS_NAME = {"ACTIVE": "Active", "STABLE": "Stable", "DORMANT": "Dormant", "ORPHAN": "Orphan", "UNKNOWN": "Unknown"}
_STATUS_CLASS = {"ACTIVE": "s-active", "STABLE": "s-stable", "DORMANT": "s-dormant", "ORPHAN": "s-orphan"}
_CHIP = {"high": "chip bad", "medium": "chip warn", "low": "chip"}

NODE_W, NODE_H, COL_GAP, ROW_GAP, PAD = 190, 54, 96, 14, 18


def e(value) -> str:
    return html.escape(str(value), quote=True)


def n(value) -> str:
    return f"{value:,}"


def _json(data) -> str:
    """JSON that is safe inside a <script> element: no tag or entity can start inside a string."""
    return json.dumps(data, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _status_note(report: dict) -> dict[str, str]:
    s = report["settings"]
    return {
        "ACTIVE": f"touched in the last {s['active_days']} days",
        "STABLE": "unchanged lately, but other code depends on it",
        "DORMANT": f"untouched for {s['dormant_days']} days and barely used",
        "ORPHAN": "nothing reaches it",
        "UNKNOWN": "no git history",
    }


def _stack(parts: list[tuple[str, int, str]], thin: bool = False) -> str:
    """A stacked bar. parts are (css class, value, text for assistive technology)."""
    live = [(c, v, t) for c, v, t in parts if v > 0]
    if not live:
        return ""
    label = "; ".join(t for _, _, t in live)
    spans = "".join(f'<span class="{c}" style="--v:{v}"></span>' for c, v, _ in live)
    return f'<div class="stack{" thin" if thin else ""}" role="img" aria-label="{e(label)}" title="{e(label)}">{spans}</div>'


def _status_stack(values: dict[str, int], thin: bool = False) -> str:
    return _stack([(_STATUS_CLASS[s], values.get(s, 0), f"{_STATUS_NAME[s]} {n(values.get(s, 0))} lines") for s in STATUSES], thin)


def _owner_name(name: str | None, idle: int | None, gone: int) -> str:
    if not name:
        return "-"
    return e(name) + (f' <span class="silent">(silent {idle}d)</span>' if idle is not None and idle > gone else "")


def _table(table_id: str, headers: list[tuple[str, str]], rows: list[str], limit: int = 0, label: str = "") -> str:
    """headers are (text, kind): kind is "num" or "text" to make the column sortable and right-aligned for numbers, "" for neither."""
    head = "".join(
        f'<th{" class=num" if kind == "num" else ""}{f" data-sort={kind}" if kind else ""}>{e(text)}</th>' for text, kind in headers
    )
    aria = f' aria-label="{e(label)}"' if label else ""
    return (
        f'<div class="tablewrap"><table class="t" id="{e(table_id)}" data-limit="{limit}"{aria}>'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _num(value: int, text: str | None = None) -> str:
    return f'<td class="num" data-v="{value}">{e(text if text is not None else n(value))}</td>'


def wb(value: str) -> str:
    """Escaped text that may wrap after each slash, so a path breaks between segments rather than inside one."""
    return e(value).replace("/", "/<wbr>")


def _path(value: str) -> str:
    return f'<td class="path">{wb(value)}</td>'


# --- sections --------------------------------------------------------------------------------------------


def _overview(report: dict, graph: dict | None) -> str:
    s, git = report["summary"], report["git"]
    own = report["ownership"]
    total = sum(v["code"] for v in s["by_status"].values())
    note = _status_note(report)
    langs = ", ".join(f"{e(r['language'])} {n(r['code'])}" for r in report["languages"][:3] if r["kind"] == "code")
    meta = [report["generated_at"].replace("T", " ").replace("Z", " UTC")]
    if git["available"]:
        meta.append(f"commit {e(git['head'])}, {n(git['commits'])} commits" + (" (shallow clone)" if git["shallow"] else ""))
    else:
        meta.append("no git history")

    def tile(label: str, value: str, sub: str) -> str:
        return f'<div class="card tile"><div class="label">{e(label)}</div><div class="value">{value}</div><div class="note">{sub}</div></div>'

    active = s["by_status"].get("ACTIVE", {"code": 0})["code"]
    tiles = [
        tile("Unreachable code", f"{s['orphans']['share_of_analyzed']}%", f"{n(s['orphans']['files'])} orphan files, {n(s['orphans']['code'])} lines"),
        tile(f"Changed in {report['settings']['active_days']} days", f"{round(100 * active / total) if total else 0}%", f"{n(active)} lines are active"),
    ]
    if own["available"]:
        tiles += [
            tile("People", f"{own['authors']['active']} of {own['authors']['total']}", f"committed in the last {own['inactive_days']} days; bus factor {own['bus_factor']}"),
            tile("No active owner", f"{own['no_active_owner']['share']}%", f"{n(own['no_active_owner']['files'])} files, {n(own['no_active_owner']['code'])} lines"),
        ]
    else:
        tiles.append(tile("Ownership", "-", "needs git history"))
    if graph and graph["summary"]["modules"]:
        cycles = graph["cycles"]
        tiles.append(tile("Module cycles", str(len(cycles)), f"{sum(len(c['modules']) for c in cycles)} of {graph['summary']['modules']} modules are in one" if cycles else "no module depends on itself"))
    cov = s["reachability_coverage"]
    tiles.append(tile("Reachability coverage", f"{cov['share_of_code']}%", "of production code could be analysed" if cov["analyzers"] else "no analyzer for these languages"))

    legend = "".join(
        f'<li><span class="dot {_STATUS_CLASS.get(k, "")}"></span><b>{e(_STATUS_NAME.get(k, k))}</b> {n(v["code"])} lines ({round(100 * v["code"] / total) if total else 0}%) <span class="sub">{e(note.get(k, ""))}</span></li>'
        for k, v in s["by_status"].items()
        if v["code"]
    )
    bar = _status_stack({k: v["code"] for k, v in s["by_status"].items()})
    return f"""<section id="overview">
<h1>{e(report['repo']['name'])}</h1>
<p class="lede">{' · '.join(meta)}</p>
<div class="card">
  <div class="hero">{n(s['code_lines'])}</div>
  <div class="sub">lines of code in {n(s['files'])} files{f' ({langs})' if langs else ''}</div>
  <h3 style="margin-top:14px">Code by status</h3>
  {bar}
  <ul class="legend">{legend}</ul>
</div>
<div class="tiles">{''.join(tiles)}</div>
</section>"""


def _attention(report: dict, graph: dict | None) -> str:
    orphans = report["cleanup"]["orphan_files"][:5]
    own = report["ownership"]
    gone = own.get("inactive_days", 0)

    def items(rows: list[str], empty: str) -> str:
        return f'<ul class="items">{"".join(rows)}</ul>' if rows else f'<p class="empty">{e(empty)}</p>'

    unused = items(
        [f'<li><code class="p">{wb(r["path"])}</code><span class="sub">{n(r["code"])} lines, <span class="{_CHIP[r["confidence"]]}">{e(r["confidence"])} confidence</span>, owner {_owner_name(r["owner"], r["owner_idle_days"], gone)}</span></li>' for r in orphans],
        "No orphan files: everything analysed is reached from an entry point or a test.",
    )
    if own["available"]:
        unowned = items(
            [f'<li><code class="p">{wb(r["path"])}</code><span class="sub">{n(r["code"])} lines, last maintained by {_owner_name(r["last_owner"], r["owner_idle_days"], gone)}</span></li>' for r in own["needs_owner_files"][:5]],
            "Every live file has someone active maintaining it.",
        )
    else:
        unowned = '<p class="empty">Needs git history.</p>'
    if graph and graph["summary"]["modules"]:
        cuts = [(c, x) for c in graph["cycles"] for x in c["cut"]]
        cuts.sort(key=lambda cx: (-cx[1]["imports"], cx[1]["from"], cx[1]["to"]))
        tangled = items(
            [f'<li><code class="p">{wb(x["from"])} → {wb(x["to"])}</code><span class="sub">{n(x["imports"])} imports; cut to break cycle {c["id"]}</span></li>' for c, x in cuts[:5]],
            "No cycles between modules.",
        )
    else:
        tangled = '<p class="empty">No import graph: no analyzer covers these languages.</p>'
    return f"""<section id="attention">
<h2>Where to look first</h2>
<p class="lede">Each list is the top of a longer table further down. Treat them as questions to check, not verdicts.</p>
<div class="grid g3">
  <div class="card"><h3>Probably unused</h3>{unused}<p class="sub"><a href="#cleanup">All {n(report['summary']['orphans']['files'])} candidates</a></p></div>
  <div class="card"><h3>Nobody active maintains</h3>{unowned}<p class="sub"><a href="#ownership">Ownership</a></p></div>
  <div class="card"><h3>Dependencies to untangle</h3>{tangled}<p class="sub"><a href="#modules">Module graph</a></p></div>
</div>
</section>"""


def _directories(report: dict) -> str:
    rows_in = report["directories"]
    if not rows_in:
        return ""
    gone = report["ownership"].get("inactive_days", 0)
    has_owners = "owners" in rows_in[0]
    top = max(r["code"] for r in rows_in) or 1
    rows = []
    for r in rows_in:
        cells = [
            _path(r["path"]),
            f'<td class="num" data-v="{r["code"]}">{n(r["code"])}<span class="bar1" style="width:{max(2, round(100 * r["code"] / top))}%"></span></td>',
            f'<td data-v="{r["orphan"]}">{_status_stack({"ACTIVE": r["active"], "STABLE": r["stable"], "DORMANT": r["dormant"], "ORPHAN": r["orphan"]}, thin=True)}</td>',
        ]
        if has_owners:
            cells += [f'<td class="wide">{e(_owners(r["owners"], gone, r["contributors"]))}</td>', f'<td>{e(_STATE_TEXT[r["ownership"]])}</td>']
        rows.append(f"<tr>{''.join(cells)}</tr>")
    headers = [("Directory", "text"), ("Code", "num"), ("Status mix (orphan share sorts)", "num")] + ([("Owners", "text"), ("State", "text")] if has_owners else [])
    return f"""<section id="directories">
<h2>Directories</h2>
<p class="lede">Where the code is, how much of it is alive, and who maintains it. Click a heading to sort.</p>
<div class="card">{_table('dir-table', headers, rows, limit=20, label='Directories')}</div>
</section>"""


# module graph ---------------------------------------------------------------------------------------------


def _layout(mods: list[dict], edges: list[dict]) -> tuple[dict[str, tuple[int, int]], int, int]:
    """Columns by longest path with the cut edges removed (users on the left, foundations on the right), rows
    by a few barycentre sweeps to keep arrows short. Returns positions, width and height."""
    ids = [m["id"] for m in mods]
    cut = {(x["from"], x["to"]) for x in edges if x["cut"]}
    succ: dict[str, list[str]] = {i: [] for i in ids}
    indegree = dict.fromkeys(ids, 0)
    near: dict[str, set[str]] = {i: set() for i in ids}
    for x in edges:
        near[x["from"]].add(x["to"])
        near[x["to"]].add(x["from"])
        if (x["from"], x["to"]) not in cut:
            succ[x["from"]].append(x["to"])
            indegree[x["to"]] += 1
    layer = dict.fromkeys(ids, 0)
    queue = deque(sorted(i for i in ids if indegree[i] == 0))
    while queue:
        u = queue.popleft()
        for v in sorted(succ[u]):
            layer[v] = max(layer[v], layer[u] + 1)
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    depth = max(layer.values(), default=0)
    cols: list[list[str]] = [sorted(i for i in ids if layer[i] == k) for k in range(depth + 1)]

    def sweep(order: list[int]) -> None:
        pos = {i: r for col in cols for r, i in enumerate(col)}
        for k in order:
            side = k - 1 if order[0] == 1 else k + 1
            def key(i: str) -> tuple[float, str]:
                around = [pos[j] for j in near[i] if layer[j] == side]
                return (sum(around) / len(around) if around else pos[i], i)
            cols[k] = sorted(cols[k], key=key)
            for r, i in enumerate(cols[k]):
                pos[i] = r

    for _ in range(4):
        sweep(list(range(1, depth + 1)))
        sweep(list(range(depth - 1, -1, -1)))
    where = {i: (PAD + k * (NODE_W + COL_GAP), PAD + r * (NODE_H + ROW_GAP)) for k, col in enumerate(cols) for r, i in enumerate(col)}
    rows = max((len(c) for c in cols), default=1)
    return where, 2 * PAD + (depth + 1) * NODE_W + depth * COL_GAP, 2 * PAD + rows * NODE_H + (rows - 1) * ROW_GAP


def _clip(text: str, size: int, left: bool = False) -> str:
    if len(text) <= size:
        return text
    return "…" + text[-(size - 1) :] if left else text[: size - 1] + "…"


def _edge_path(src: tuple[int, int], dst: tuple[int, int], same_column: bool) -> str:
    sx, sy = src[0], src[1] + NODE_H / 2
    tx, ty = dst[0], dst[1] + NODE_H / 2
    if same_column:  # leave and enter on the right, bulging outwards
        x1, x2 = sx + NODE_W, tx + NODE_W
        return f"M{x1},{sy} C{x1 + 46},{sy} {x2 + 46},{ty} {x2},{ty}"
    if sx < tx:
        x1, x2 = sx + NODE_W, tx
    else:  # an arrow against the flow leaves on the left and arrives on the right
        x1, x2 = sx, tx + NODE_W
    mid = (x2 - x1) / 2
    return f"M{x1},{sy} C{x1 + mid},{sy} {x2 - mid},{ty} {x2},{ty}"


def _graph_svg(graph: dict) -> tuple[str, int, int]:
    mods, edges, floor = drawn(graph, None)
    where, width, height = _layout(mods, edges)
    by_id = {m["id"]: m for m in mods}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="group" aria-label="Module dependency graph">',
        '<defs><marker id="ah" class="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z"/></marker>'
        '<marker id="ah-cut" class="arrow cut" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z"/></marker></defs>',
    ]
    for x in edges:
        src, dst = where[x["from"]], where[x["to"]]
        d = _edge_path(src, dst, src[0] == dst[0])
        weight = round(min(3.5, 0.8 + 0.45 * x["imports"] ** 0.5), 2)
        tip = f"{x['from']} → {x['to']}: {n(x['imports'])} imports from {n(x['files'])} files" + (f" (cut to break cycle {x['cycle']})" if x["cut"] else "")
        parts.append(
            f'<g class="edge{" cut" if x["cut"] else ""}" data-from="{e(x["from"])}" data-to="{e(x["to"])}"><title>{e(tip)}</title>'
            f'<path class="hit" d="{d}"/><path class="line" d="{d}" stroke-width="{weight}" marker-end="url(#{"ah-cut" if x["cut"] else "ah"})"/></g>'
        )
    for i, (x0, y0) in where.items():
        m = by_id[i]
        name = i.rsplit("/", 1)[-1] if i != "." else "(top level)"
        parent = i.rpartition("/")[0]
        status = m["status"]
        inner = NODE_W - 24
        total = sum(status.values())
        segs, cursor = [], 12
        if total:
            live = [(s, status[s.lower()]) for s in STATUSES if status.get(s.lower())]
            room = inner - 2 * (len(live) - 1)
            for s, v in live:
                w = max(2, round(room * v / total))
                segs.append(f'<rect class="seg {_STATUS_CLASS[s]}" x="{x0 + cursor}" y="{y0 + NODE_H - 12}" width="{w}" height="5" rx="2"/>')
                cursor += w + 2
        tip = f"{i}: {n(m['files'])} files, {n(m['code'])} lines; uses {m['uses']} modules, used by {m['used_by']}" + (f"; in cycle {m['cycle']}" if m["cycle"] else "")
        cls = "node" + (" noowner" if m.get("ownership") == "no-active-owner" else "")
        subtitle = _clip(parent, 30, left=True) if parent else f"{n(m['files'])} files, {n(m['code'])} lines"
        parts.append(
            f'<g class="{cls}" data-id="{e(i)}" tabindex="0" role="button" aria-label="{e(tip)}"><title>{e(tip)}</title>'
            f'<rect class="box" x="{x0}" y="{y0}" width="{NODE_W}" height="{NODE_H}" rx="8"/>'
            f'<text class="name" x="{x0 + 12}" y="{y0 + 19}">{e(_clip(name, 24))}</text>'
            f'<text class="where" x="{x0 + 12}" y="{y0 + 33}">{e(subtitle)}</text>'
            + "".join(segs)
            + "</g>"
        )
    parts.append("</svg>")
    return "".join(parts), len(edges), floor


def _modules_section(report: dict, graph: dict | None) -> str:
    if not graph or not graph["summary"]["modules"]:
        return """<section id="modules"><h2>Module graph</h2>
<div class="card"><p class="empty">No import graph: no analyzer covers the languages in this repository.</p></div></section>"""
    s = graph["summary"]
    gone = report["settings"]["owner_inactive_days"]
    svg, shown, floor = _graph_svg(graph)
    cut_note = " Red arrows are the cuts that break a cycle." if graph["cycles"] else ""
    thinning = f" The {n(shown)} heaviest of {n(s['dependencies'])} dependencies are drawn (at least {floor} {'import' if floor == 1 else 'imports'}); the table has all modules." if shown < s["dependencies"] else ""
    cycle_html = ""
    for c in graph["cycles"]:
        rows = [
            f'<tr>{_path(x["from"])}{_path(x["to"])}{_num(x["imports"])}<td class="path">{wb(x["examples"][0][0])} → {wb(x["examples"][0][1])}</td></tr>'
            for x in sorted(c["cut"], key=lambda x: (-x["imports"], x["from"], x["to"]))
        ]
        names = ", ".join(e(m) for m in c["modules"][:6]) + (f" and {len(c['modules']) - 6} more" if len(c["modules"]) > 6 else "")
        cycle_html += (
            f'<div class="card"><h3>Cycle {c["id"]}: {len(c["modules"])} modules</h3>'
            f'<p class="sub">{names}. {n(c["imports"])} imports among them. Removing or inverting these {len(c["cut"])} dependencies ({n(c["cut_imports"])} imports) leaves no cycle; '
            f"it is a heuristic for a few, light edges, not a proof of the minimum.</p>"
            + _table(f"cycle-{c['id']}", [("From", "text"), ("To", "text"), ("Imports", "num"), ("For example", "text")], rows, limit=10, label=f"Cycle {c['id']}")
            + "</div>"
        )
    has_owners = any("owners" in m for m in graph["modules"])
    rows = []
    for m in sorted(graph["modules"], key=lambda m: (-m["used_by"], -m["code"], m["id"])):
        cells = [_path(m["id"]), _num(m["files"]), _num(m["code"]), _num(m["uses"]), _num(m["used_by"]), _num(m["cycle"] or 0, str(m["cycle"]) if m["cycle"] else "-")]
        if has_owners:
            state = _STATE_TEXT[m["ownership"]] if m["code"] else "no code"
            cells += [f'<td class="wide">{e(_owners(m["owners"], gone, m["contributors"]))}</td>', f"<td>{e(state)}</td>"]
        rows.append(f"<tr>{''.join(cells)}</tr>")
    headers = [("Module", "text"), ("Files", "num"), ("Code", "num"), ("Uses", "num"), ("Used by", "num"), ("Cycle", "num")] + ([("Owners", "text"), ("State", "text")] if has_owners else [])
    return f"""<section id="modules">
<h2>How the modules fit together</h2>
<p class="lede">{n(s['modules'])} modules, {n(s['dependencies'])} dependencies, {len(graph['cycles'])} cycles, from {n(s['imports'])} imports. An arrow A → B means a file in A imports a file in B. Users sit on the left, what they build on to the right.{e(cut_note)}{e(thinning)}</p>
<div class="card">
  <div class="key"><span><i></i>dependency (thicker = more imports)</span><span><i class="cut"></i>cut to break a cycle</span><span><i class="box"></i>no active owner</span><span>bar under a name: code by status</span><button class="btn" id="fit" type="button">Fit width</button></div>
  <div class="detail" id="graph-detail"></div>
  <div class="graph" id="graph">{svg}</div>
</div>
{cycle_html}
<div class="card"><h3>All modules</h3>{_table('mod-table', headers, rows, limit=20, label='Modules')}</div>
</section>"""


def _impact_section(explorer: dict | None) -> str:
    if explorer is None:
        return """<section id="impact"><h2>What does a change reach?</h2>
<div class="card"><p class="empty">Not available: there are no analysed code files, or too many to carry in one page. Run <code>repolife impact</code> instead.</p></div></section>"""
    return """<section id="impact">
<h2>What does a change reach?</h2>
<p class="lede">Pick a file or a directory to see which code imports it, directly or through others, which tests reach it and who maintains the affected files. It follows static imports only.</p>
<div class="card explorer">
  <div class="tools">
    <input type="text" id="impact-q" list="impact-list" placeholder="src/app/main.py or src/app" autocomplete="off" spellcheck="false" aria-label="File or directory">
    <select id="impact-hops" aria-label="How far to follow imports"><option value="">All imports</option><option value="1">Direct importers only</option><option value="2">Two steps</option><option value="3">Three steps</option></select>
  </div>
  <datalist id="impact-list"></datalist>
  <div class="result" id="impact-out"><noscript>This explorer needs scripts. Run <code>repolife impact &lt;path&gt;</code> for the same answer.</noscript></div>
</div>
</section>"""


def _ownership_section(report: dict) -> str:
    own = report["ownership"]
    if not own["available"]:
        return """<section id="ownership"><h2>Who maintains it</h2>
<div class="card"><p class="empty">Ownership is read from git history, and this directory has none.</p></div></section>"""
    gone = own["inactive_days"]
    people = own["authors"]
    total = own["top_authors"][0]["code"] if own["top_authors"] else 1
    author_rows = []
    for a in own["top_authors"]:
        share, idle = f"{a['share']}%", f"{a['idle_days']}d ago"
        state = "active" if a["active"] else f"silent for over {gone} days"
        author_rows.append(
            f'<tr><td>{e(a["name"])}</td><td class="num" data-v="{a["code"]}">{n(a["code"])}<span class="bar1" style="width:{max(2, round(100 * a["code"] / total))}%"></span></td>'
            f'{_num(a["share"], share)}<td data-v="{e(a["last_commit"])}">{e(a["last_commit"])}</td>{_num(a["idle_days"], idle)}<td>{state}</td></tr>'
        )
    needs = [
        f'<tr>{_path(r["path"])}{_num(r["code"])}<td>{e(_STATUS_NAME.get(r["status"], r["status"] or "-"))}</td><td>{_owner_name(r["last_owner"], r["owner_idle_days"], gone)}</td></tr>'
        for r in own["needs_owner_files"]
    ]
    unowned = own["no_active_owner"]
    out = f"""<section id="ownership">
<h2>Who maintains it</h2>
<p class="lede">Read from git: every commit credits its author with the files it touched, and a commit loses half its weight per year, so an owner is whoever has been maintaining a file lately. It shows who changed the code, not who is accountable, and it cannot see who reviewed. {n(people['total'])} authors, {n(people['active'])} committed in the last {gone} days; the fewest people who together hold half the code: {own['bus_factor']}.</p>
<div class="card"><h3>Who holds the code</h3>{_table('author-table', [('Person', 'text'), ('Code held', 'num'), ('Share', 'num'), ('Last commit', 'text'), ('Silent for', 'num'), ('State', 'text')], author_rows, limit=12, label='People')}</div>
<div class="card"><h3>Live code nobody active maintains</h3>
<p class="sub">{n(unowned['code'])} lines ({unowned['share']}%) in {n(unowned['files'])} files. Someone needs to be assigned before it is changed.</p>
{_table('needs-table', [('File', 'text'), ('Code', 'num'), ('Status', 'text'), ('Last maintainer', 'text')], needs, limit=15, label='Files with no active owner') if needs else '<p class="empty">None: every live file has an active maintainer.</p>'}</div>"""
    co = own["codeowners"]
    if co:
        unc = [f'<tr>{_path(r["path"])}{_num(r["code"])}<td>{_owner_name(r["owner"], None, gone)}</td></tr>' for r in co["uncovered_files"]]
        diff = [f'<tr>{_path(r["path"])}{_num(r["code"])}<td>{e(" ".join(r["declared"]) or "-")}</td><td>{e(r["observed"] or "-")}</td></tr>' for r in co["differing_files"]]
        out += f"""
<div class="card"><h3>CODEOWNERS (<code>{e(co['file'])}</code>, {n(co['rules'])} rules)</h3>
<p class="sub">{n(co['uncovered']['files'])} files ({co['uncovered']['share']}% of the code) have no declared owner; for {n(co['differs']['files'])} files none of the declared owners is among the people who maintain them. A team handle cannot be compared with commit authors, so those files are not counted as mismatches.</p>
{_table('uncovered-table', [('Not covered', 'text'), ('Code', 'num'), ('Maintained by', 'text')], unc, limit=10, label='Files without a declared owner') if unc else ''}
{_table('differs-table', [('Declared differently', 'text'), ('Code', 'num'), ('Declared', 'text'), ('Maintained by', 'text')], diff, limit=10, label='Files whose declared owner differs') if diff else ''}</div>"""
    return out + "\n</section>"


def _hotspots(report: dict) -> str:
    rows_in = report["hotspots"]
    if not rows_in:
        return ""
    gone = report["ownership"].get("inactive_days", 0)
    rows = [
        f'<tr>{_path(r["path"])}{_num(r["commits_year"])}{_num(r["authors_year"])}{_num(r["code"])}<td data-v="{e(r["last_commit"] or "")}">{e(r["last_commit"] or "-")}</td>'
        f'<td>{e(_STATUS_NAME.get(r["status"], r["status"] or "-"))}</td><td>{_owner_name(r["owner"], None, gone)}</td></tr>'
        for r in rows_in
    ]
    return f"""<section id="hotspots">
<h2>Where the change is</h2>
<p class="lede">The files changed most often in the last year: where review effort goes, and where a small mistake is most likely to be touched again.</p>
<div class="card">{_table('hot-table', [('File', 'text'), ('Commits in a year', 'num'), ('Authors', 'num'), ('Code', 'num'), ('Last commit', 'text'), ('Status', 'text'), ('Owner', 'text')], rows, limit=15, label='Most changed files')}</div>
</section>"""


def _cleanup(report: dict) -> str:
    orphans = report["cleanup"]["orphan_files"]
    test_only = report["cleanup"]["test_only_files"]
    gone = report["ownership"].get("inactive_days", 0)
    if not orphans and not test_only:
        return """<section id="cleanup"><h2>Cleanup candidates</h2>
<div class="card"><p class="empty">No orphan files and nothing reachable only from tests.</p></div></section>"""
    rows = []
    for r in orphans:
        notes = "; ".join(r["notes"])
        rows.append(
            f'<tr data-cat="{e(r["confidence"])}">{_path(r["path"])}{_num(r["code"])}<td data-v="{e(r["confidence"])}"><span class="{_CHIP[r["confidence"]]}">{e(r["confidence"])}</span></td>'
            f'<td data-v="{e(r["last_commit"] or "")}">{e(r["last_commit"] or "-")}</td><td>{_owner_name(r["owner"], r["owner_idle_days"], gone)}</td><td class="wide">{e(notes) or "-"}</td></tr>'
        )
    table = _table(
        "orphan-table",
        [("File", "text"), ("Code", "num"), ("Confidence", "text"), ("Last commit", "text"), ("Owner", "text"), ("Why it might still be wanted", "text")],
        rows,
        limit=25,
        label="Orphan files",
    )
    tools = (
        '<div class="tools"><input type="search" data-for="orphan-table" placeholder="Filter files, owners, notes" aria-label="Filter orphan files">'
        '<select data-for="orphan-table" aria-label="Confidence"><option value="">Any confidence</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></div>'
    )
    tests = ""
    if test_only:
        trows = [f'<tr>{_path(r["path"])}{_num(r["code"])}<td data-v="{e(r["last_commit"] or "")}">{e(r["last_commit"] or "-")}</td></tr>' for r in test_only]
        tests = f'<details><summary>{n(len(test_only))} files reached only from tests: production code may have lost its caller</summary>{_table("testonly-table", [("File", "text"), ("Code", "num"), ("Last commit", "text")], trows, limit=15, label="Test-only files")}</details>'
    return f"""<section id="cleanup">
<h2>Cleanup candidates</h2>
<p class="lede">Nothing in the repository reaches these files: no entry point, test or config names them. That makes them candidates, not verdicts: check with <code>repolife why &lt;file&gt;</code> and a search for dynamic use before deleting, and ask the owner.</p>
<div class="card">{tools if orphans else ''}{table if orphans else '<p class="empty">No orphan files.</p>'}{tests}</div>
</section>"""


def _notes(report: dict) -> str:
    s = report["settings"]
    an = report["analysis"]
    facts = [
        ("Analyzers", ", ".join(report["summary"]["reachability_coverage"]["analyzers"]) or "none"),
        ("Active window", f"{s['active_days']} days"),
        ("Dormant after", f"{s['dormant_days']} days"),
        ("Owner gone after", f"{s['owner_inactive_days']} days without a commit"),
    ]
    if an["unanalyzed_languages"]:
        facts.append(("Volume and activity only", ", ".join(f"{k} ({n(v['files'])})" for k, v in an["unanalyzed_languages"].items())))
    for key in ("keep", "exclude", "entry", "ignore_authors"):
        if s[key]:
            facts.append((key.replace("_", " ").capitalize(), ", ".join(s[key])))
    dl = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in facts)
    return f"""<section id="notes">
<h2>Read this with care</h2>
<div class="card"><ul class="caveats">{''.join(f'<li>{e(c)}</li>' for c in report['caveats'])}</ul>
<details><summary>Settings used</summary><div class="detail"><dl>{dl}</dl></div></details></div>
</section>"""


# --- page --------------------------------------------------------------------------------------------------


def render(report: dict, graph: dict | None, explorer: dict | None) -> str:
    """The page for a report (build_report), a module graph (modules.build_graph) and explorer data (modules.explorer)."""
    has_graph = bool(graph and graph["summary"]["modules"])
    data = {
        "inactive_days": report["settings"]["owner_inactive_days"],
        "graph": {"modules": graph["modules"]} if has_graph else None,
        "explorer": explorer,
    }
    nav = [("overview", "Overview"), ("attention", "Look first"), ("directories", "Directories"), ("modules", "Modules"), ("impact", "Impact"), ("ownership", "Ownership"), ("hotspots", "Hotspots"), ("cleanup", "Cleanup"), ("notes", "Notes")]
    body = "\n".join(
        part
        for part in (
            _overview(report, graph if has_graph else None),
            _attention(report, graph if has_graph else None),
            _directories(report),
            _modules_section(report, graph if has_graph else None),
            _impact_section(explorer),
            _ownership_section(report),
            _hotspots(report),
            _cleanup(report),
            _notes(report),
        )
        if part
    )
    links = "".join(f'<a href="#{i}">{t}</a>' for i, t in nav)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="generator" content="repolife {e(__version__)}">
<title>repolife: {e(report['repo']['name'])}</title>
<script>{THEME_BOOT}</script>
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="wrap bar"><strong>repolife</strong><nav aria-label="Sections">{links}</nav><button class="btn" id="theme" type="button">Theme: auto</button></div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap">Generated by repolife {e(__version__)}. A static analysis of this repository: it reads code and git history and never edits anything.</footer>
<script type="application/json" id="data">{_json(data)}</script>
<script id="app">{JS}</script>
</body>
</html>
"""


def build_html(a: Analysis, report: dict | None = None) -> str:
    report = report if report is not None else build_report(a)
    return render(report, modules.build_graph(a), modules.explorer(a))
