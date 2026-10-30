"""Stylesheet and script of the HTML report. Kept as strings so the tool still works from a zipapp.

Colours follow a validated palette (see the notes in htmlreport.py): the four code statuses use four
categorical hues that pass the adjacent-pair colour-vision checks in both themes, and every colour
is also carried by a text label, so nothing relies on hue alone.
"""

_LIGHT = """
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,.10); --wash: rgba(11,11,11,.05);
  --accent: #2a78d6; --link: #1c5cab;
  --st-active: #2a78d6; --st-stable: #1baf7a; --st-dormant: #eda100; --st-orphan: #d03b3b;
  --edge: #a9a79f; --edge-hot: #2a78d6;
"""

_DARK = """
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,.10); --wash: rgba(255,255,255,.06);
  --accent: #3987e5; --link: #6da7ec;
  --st-active: #3987e5; --st-stable: #199e70; --st-dormant: #c98500; --st-orphan: #d03b3b;
  --edge: #4d4c48; --edge-hot: #6da7ec;
"""

CSS = (
    ":root {"
    + _LIGHT
    + "}\n@media (prefers-color-scheme: dark) {\n  :root:where(:not([data-theme=\"light\"])) {"
    + _DARK
    + "}\n}\n:root[data-theme=\"dark\"] {"
    + _DARK
    + "}\n"
    + """
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--link); }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .92em; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 16px; }

.top { position: sticky; top: 0; z-index: 5; background: var(--page); border-bottom: 1px solid var(--grid); }
.bar { display: flex; align-items: center; gap: 12px; min-height: 48px; }
.bar strong { font-weight: 650; }
.bar nav { display: flex; gap: 2px; flex: 1; overflow-x: auto; white-space: nowrap; scrollbar-width: none; }
.bar nav a { padding: 6px 10px; border-radius: 6px; color: var(--ink2); text-decoration: none; }
.bar nav a:hover { background: var(--wash); color: var(--ink); }
.btn { font: inherit; font-size: 13px; padding: 5px 10px; border: 1px solid var(--axis); border-radius: 6px; background: var(--surface); color: var(--ink2); cursor: pointer; white-space: nowrap; }
.btn:hover { background: var(--wash); color: var(--ink); }

section { padding: 30px 0 2px; scroll-margin-top: 56px; }
h1 { font-size: 30px; line-height: 1.2; margin: 0 0 4px; font-weight: 650; }
h2 { font-size: 20px; line-height: 1.3; margin: 0 0 4px; font-weight: 650; }
h3 { font-size: 15px; margin: 0 0 8px; font-weight: 650; }
.lede { color: var(--ink2); margin: 0 0 16px; max-width: 74ch; }
.sub { color: var(--ink2); font-size: 13px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; }
.card + .card { margin-top: 12px; }
.grid > .card, .tiles > .card { margin-top: 0; }
.grid { display: grid; gap: 12px; }
.g3 { grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 12px; }
.tile .label { color: var(--ink2); font-size: 13px; }
.tile .value { font-size: 26px; font-weight: 600; line-height: 1.25; }
.tile .note { color: var(--ink2); font-size: 12.5px; }
.hero { font-size: 56px; font-weight: 600; line-height: 1.05; }

.stack { display: flex; gap: 2px; height: 14px; }
.stack.thin { height: 8px; min-width: 90px; }
.stack span { flex: var(--v) 1 0; min-width: 2px; background: var(--c); }
.stack span:first-child { border-radius: 4px 0 0 4px; }
.stack span:last-child { border-radius: 0 4px 4px 0; }
.stack span:only-child { border-radius: 4px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 10px 0 0; padding: 0; list-style: none; font-size: 13.5px; }
.legend b { font-weight: 600; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: var(--c); margin-right: 6px; vertical-align: baseline; }
.bar1 { display: block; height: 8px; border-radius: 0 4px 4px 0; background: var(--accent); min-width: 2px; }
.s-active { --c: var(--st-active); } .s-stable { --c: var(--st-stable); } .s-dormant { --c: var(--st-dormant); } .s-orphan { --c: var(--st-orphan); }

.items { margin: 0; padding: 0; list-style: none; }
.items li { padding: 6px 0; border-top: 1px solid var(--grid); }
.items li:first-child { border-top: 0; padding-top: 0; }
.items .p { display: block; overflow-wrap: break-word; }
.empty { color: var(--ink2); }

.tools { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 10px; }
input[type=search], input[type=text], select { font: inherit; font-size: 14px; padding: 7px 10px; border: 1px solid var(--axis); border-radius: 8px; background: var(--surface); color: var(--ink); }
input[type=search], .tools input { flex: 1 1 220px; max-width: 420px; }
.tablewrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th { font-weight: 600; color: var(--ink2); text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--axis); white-space: nowrap; font-size: 12.5px; }
th[data-sort] { cursor: pointer; user-select: none; }
th[data-sort]:hover { color: var(--ink); }
th[aria-sort=ascending]::after { content: " \\25B2"; font-size: 10px; }
th[aria-sort=descending]::after { content: " \\25BC"; font-size: 10px; }
td { padding: 7px 10px; border-bottom: 1px solid var(--grid); vertical-align: top; }
tr:last-child td { border-bottom: 0; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.path { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; overflow-wrap: break-word; min-width: 150px; }
td.wide { min-width: 220px; }
tr.more, tr[hidden] { display: none; }
.chip { display: inline-block; padding: 0 8px; border: 1px solid var(--axis); border-radius: 999px; font-size: 12px; color: var(--ink2); white-space: nowrap; }
.chip.warn { border-color: var(--st-dormant); color: var(--ink); }
.chip.bad { border-color: var(--st-orphan); color: var(--ink); }
.more-row { margin-top: 8px; display: flex; align-items: center; gap: 12px; }
.silent { color: var(--ink2); }
details summary { cursor: pointer; color: var(--ink2); margin: 8px 0; }

.graph { overflow: auto; border: 1px solid var(--grid); border-radius: 8px; background: var(--page); }
.graph svg { display: block; max-width: none; }
.graph.fit svg { width: 100%; height: auto; }
.graph text { fill: var(--ink); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.node { cursor: pointer; }
.node rect.box { fill: var(--surface); stroke: var(--axis); stroke-width: 1; }
.node.noowner rect.box { stroke-dasharray: 4 3; }
.node:hover rect.box, .node.sel rect.box, .node:focus-visible rect.box { stroke: var(--accent); stroke-width: 2; }
.node:focus-visible { outline: none; }
.node .name { font-size: 12.5px; font-weight: 600; }
.node .where { font-size: 10.5px; fill: var(--ink2); }
.node rect.seg { fill: var(--c); }
.edge .line { fill: none; stroke: var(--edge); }
.edge .hit { fill: none; stroke: transparent; stroke-width: 12; }
.edge.cut .line { stroke: var(--st-orphan); }
.edge.hot .line { stroke: var(--edge-hot); }
.edge.cut.hot .line { stroke: var(--st-orphan); }
.arrow path { fill: var(--edge); } .arrow.cut path { fill: var(--st-orphan); }
.dim { opacity: .16; }
.detail { margin: 0 0 12px; min-height: 3.2em; }
.detail dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px 16px; margin: 8px 0 0; }
.detail dt { color: var(--ink2); font-size: 12.5px; }
.detail dd { margin: 0; font-weight: 600; }
.key { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--ink2); margin: 0 0 10px; }
.key i { display: inline-block; width: 22px; height: 0; border-top: 2px solid var(--edge); vertical-align: middle; margin-right: 6px; }
.key i.cut { border-top-color: var(--st-orphan); }
.key i.box { width: 16px; height: 10px; border: 1px dashed var(--axis); border-radius: 3px; }

.explorer input { width: 100%; max-width: 620px; }
.result h3 { font-weight: 600; margin-top: 14px; }
.result ul { margin: 6px 0; padding-left: 20px; }
.err { color: var(--ink); border-left: 3px solid var(--st-orphan); padding-left: 10px; }
footer { padding: 28px 0 40px; color: var(--ink2); font-size: 13px; }
.caveats li { margin: 4px 0; }

@media (max-width: 640px) {
  h1 { font-size: 24px; } .hero { font-size: 44px; }
  .tiles { grid-template-columns: repeat(2, 1fr); }
  .card { padding: 14px; }
}
@media print {
  .top, .tools, .more-row, .explorer { display: none; }
  tr.more { display: table-row; }
  section { break-inside: avoid-page; }
}
@media (forced-colors: active) {
  .stack span, .dot, .node rect.seg { forced-color-adjust: none; }
  .stack span { border: 1px solid CanvasText; }
}
"""
)

THEME_BOOT = """try{var t=localStorage.getItem('repolife-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;}catch(e){}"""

JS = r"""(function () {
'use strict';

// ---- impact: the same walk `repolife impact` does, over the data embedded in the page --------------------

function norm(name) {
  name = String(name).trim();
  while (name.startsWith('./')) name = name.slice(2);
  return name.replace(/\/+$/, '');
}

function indexOf(E) {
  if (E._ix) return E._ix;
  const byPath = new Map(E.files.map((f, i) => [f[0], i]));
  const rev = E.files.map(() => []);
  const fwd = E.files.map(() => []);
  for (const [s, t, indirect] of E.edges) {
    rev[t].push(s);
    if (!indirect) fwd[s].push(t);
  }
  E._ix = {byPath, rev, fwd};
  return E._ix;
}

function resolve(E, input) {
  const name = norm(input);
  if (!name) return {error: 'Type a file or a directory.'};
  const {byPath} = indexOf(E);
  if (byPath.has(name)) return {label: name, kind: 'file', seeds: [byPath.get(name)]};
  for (const folder of new Set([name, name.split('.').join('/')])) {
    const prefix = folder + '/';
    const seeds = [];
    E.files.forEach((f, i) => { if (f[0].startsWith(prefix)) seeds.push(i); });
    if (folder && seeds.length) return {label: folder, kind: 'directory', seeds};
  }
  const dotted = name.split('.').join('/');
  const tail = [], module = [];
  E.files.forEach((f, i) => {
    if (f[0].endsWith('/' + name)) tail.push(i);
    if (f[0] === dotted + '.py' || f[0] === dotted + '/__init__.py') module.push(i);
  });
  if (tail.length === 1) return {label: E.files[tail[0]][0], kind: 'file', seeds: tail};
  if (module.length === 1) return {label: E.files[module[0]][0], kind: 'file', seeds: module};
  const options = tail.length ? tail : module;
  if (options.length) return {error: name + ' is ambiguous: ' + options.map(i => E.files[i][0]).sort().slice(0, 8).join(', ')};
  return {error: name + ' is not a file or directory in the analysed set (excluded, binary or an unknown type?)'};
}

function impactOf(E, input, hops, testLimit) {
  const target = resolve(E, input);
  if (target.error) return target;
  const {rev, fwd} = indexOf(E);
  const dist = new Int32Array(E.files.length).fill(-1);
  const queue = [];
  for (const s of target.seeds) { dist[s] = 0; queue.push(s); }
  for (let head = 0; head < queue.length; head++) {
    const node = queue[head];
    if (hops != null && dist[node] >= hops) continue;
    for (const d of rev[node]) if (dist[d] < 0) { dist[d] = dist[node] + 1; queue.push(d); }
  }
  const seeds = new Set(target.seeds);
  const prod = [], tests = [];
  for (const i of queue) if (!seeds.has(i)) (E.files[i][3] ? tests : prod).push(i);

  const modules = new Map(), counts = {};
  let code = 0;
  for (const i of prod) {
    const f = E.files[i], row = modules.get(f[1]) || {module: E.modules[f[1]], files: 0, direct: 0, code: 0};
    row.files++; row.code += f[2]; if (dist[i] === 1) row.direct++;
    modules.set(f[1], row);
    counts[dist[i]] = (counts[dist[i]] || 0) + 1;
    code += f[2];
  }
  const far = prod.reduce((m, i) => Math.max(m, dist[i]), 0);
  const people = new Map();
  for (const i of prod) {
    const f = E.files[i];
    if (f[4] >= 0) people.set(f[4], (people.get(f[4]) || 0) + f[2]);
  }
  const pool = E.files.filter(f => !f[3]).length;
  const needs = new Map();
  for (const s of target.seeds) for (const t of fwd[s]) {
    const f = E.files[t];
    if (seeds.has(t) || f[3]) continue;
    if (!needs.has(f[1])) needs.set(f[1], new Set());
    needs.get(f[1]).add(t);
  }
  const ordered = tests.slice().sort((a, b) => dist[a] - dist[b] || (E.files[a][0] < E.files[b][0] ? -1 : 1));
  return {
    target: target.label,
    kind: target.kind,
    files: target.seeds.length,
    code: target.seeds.reduce((n, i) => n + E.files[i][2], 0),
    dependents: {
      direct: prod.filter(i => dist[i] === 1).length,
      files: prod.length,
      code,
      share: pool ? Math.round(1000 * prod.length / pool) / 10 : 0,
      by_distance: Array.from({length: far}, (_, k) => counts[k + 1] || 0),
      modules: Array.from(modules.values()).sort((a, b) => b.files - a.files || (a.module < b.module ? -1 : 1)),
    },
    tests: {files: tests.length, direct: tests.filter(i => dist[i] === 1).length, paths: ordered.slice(0, testLimit == null ? 40 : testLimit).map(i => E.files[i][0])},
    depends_on: Array.from(needs, ([m, set]) => ({module: E.modules[m], files: set.size})).sort((a, b) => b.files - a.files || (a.module < b.module ? -1 : 1)),
    owners: Array.from(people, ([p, lines]) => ({name: E.people[p].name, idle_days: E.people[p].idle_days, share: code ? Math.round(100 * lines / code) : 0}))
      .sort((a, b) => b.share - a.share || (a.name < b.name ? -1 : 1)),
  };
}

const root = typeof globalThis !== 'undefined' ? globalThis : window;
root.RepolifeCore = {resolve, impactOf};
if (typeof document === 'undefined') return;

// ---- page ------------------------------------------------------------------------------------------------

const $ = (sel, from) => (from || document).querySelector(sel);
const $$ = (sel, from) => Array.from((from || document).querySelectorAll(sel));
const DATA = JSON.parse($('#data').textContent);
const n = v => Number(v).toLocaleString('en-US');

function el(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) e.append(kid);
  return e;
}

// theme
const themeButton = $('#theme');
let mode = 'auto';
try { mode = localStorage.getItem('repolife-theme') || 'auto'; } catch (e) { /* storage may be blocked */ }
function applyTheme() {
  if (mode === 'auto') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = mode;
  themeButton.textContent = 'Theme: ' + mode;
}
themeButton.addEventListener('click', () => {
  mode = {auto: 'light', light: 'dark', dark: 'auto'}[mode] || 'auto';
  try { localStorage.setItem('repolife-theme', mode); } catch (e) { /* ignore */ }
  applyTheme();
});
applyTheme();

// tables: sort, filter, collapse
$$('table.t').forEach(table => {
  const body = table.tBodies[0];
  const limit = Number(table.dataset.limit || 0);
  const rows = Array.from(body.rows);
  const state = {q: '', cat: '', open: false};
  const holder = table.closest('.tablewrap');
  const foot = el('div', {class: 'more-row'});
  const toggle = el('button', {class: 'btn', type: 'button'});
  const note = el('span', {class: 'sub'});
  foot.append(toggle, note);
  holder.after(foot);

  function refresh() {
    const filtering = state.q !== '' || state.cat !== '';
    let matched = 0, shown = 0;
    for (const r of Array.from(body.rows)) {
      const ok = (!state.q || r.textContent.toLowerCase().includes(state.q)) && (!state.cat || r.dataset.cat === state.cat);
      r.hidden = !ok;
      if (!ok) continue;
      matched++;
      const extra = limit > 0 && !filtering && !state.open && matched > limit;
      r.classList.toggle('more', extra);
      if (!extra) shown++;
    }
    foot.hidden = !(limit > 0 && rows.length > limit) && !filtering;
    toggle.hidden = filtering || rows.length <= limit;
    toggle.textContent = state.open ? 'Show fewer' : 'Show all ' + n(rows.length);
    note.textContent = filtering ? n(matched) + ' of ' + n(rows.length) + ' match' : 'Showing ' + n(shown) + ' of ' + n(rows.length);
  }
  toggle.addEventListener('click', () => { state.open = !state.open; refresh(); });

  $$('th[data-sort]', table).forEach(th => th.addEventListener('click', () => {
    const asc = th.getAttribute('aria-sort') !== 'ascending';
    $$('th', table).forEach(h => h.removeAttribute('aria-sort'));
    th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
    const col = th.cellIndex, numeric = th.dataset.sort === 'num';
    const key = r => { const c = r.cells[col], v = c.dataset.v !== undefined ? c.dataset.v : c.textContent.trim(); return numeric ? Number(v) : v.toLowerCase(); };
    const sorted = Array.from(body.rows).sort((a, b) => { const x = key(a), y = key(b); return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1); });
    sorted.forEach(r => body.append(r));
    refresh();
  }));
  $$('[data-for="' + table.id + '"]').forEach(ctl => ctl.addEventListener('input', () => {
    if (ctl.tagName === 'SELECT') state.cat = ctl.value; else state.q = ctl.value.trim().toLowerCase();
    refresh();
  }));
  refresh();
});

// module graph
const svg = $('#graph svg');
const detail = $('#graph-detail');
const mods = new Map((DATA.graph ? DATA.graph.modules : []).map(m => [m.id, m]));
function showModule(id) {
  const m = mods.get(id);
  if (!m) return;
  const facts = [
    ['Files', n(m.files)], ['Code lines', n(m.code)], ['Uses', m.uses + ' modules'], ['Used by', m.used_by + ' modules'],
    ['Changes in the last year', n(m.commits_year) + ' commits'], ['In a cycle', m.cycle ? 'cycle ' + m.cycle : 'no'],
  ];
  if (m.owners) facts.push(['Owners', m.owners.length ? m.owners.map(o => o.name + ' ' + o.share + '%' + (o.idle_days > DATA.inactive_days ? ' (silent ' + o.idle_days + 'd)' : '')).join(', ') : '-'], ['Ownership', {'owned': 'owned', 'no-active-owner': 'no active owner', 'unknown': 'no history'}[m.ownership] || m.ownership]);
  const dl = el('dl', {}, facts.flatMap(([k, v]) => [el('dt', {text: k}), el('dd', {text: v})]));
  const ask = el('button', {class: 'btn', type: 'button', text: 'What does a change here reach?'});
  ask.addEventListener('click', () => window.showImpact(id));
  detail.replaceChildren(el('h3', {class: 'mono', text: id}), dl, el('p', {}, ask));
}
if (svg) {
  const nodes = $$('.node', svg), edges = $$('.edge', svg);
  let selected = null;
  function paint() {
    const keep = new Set();
    for (const e of edges) {
      const on = selected && (e.dataset.from === selected || e.dataset.to === selected);
      e.classList.toggle('hot', !!on);
      e.classList.toggle('dim', !!selected && !on);
      if (on) { keep.add(e.dataset.from); keep.add(e.dataset.to); }
    }
    for (const nd of nodes) {
      nd.classList.toggle('sel', nd.dataset.id === selected);
      nd.classList.toggle('dim', !!selected && !keep.has(nd.dataset.id) && nd.dataset.id !== selected);
    }
  }
  function select(id) { selected = selected === id ? null : id; paint(); if (selected) showModule(selected); else detail.replaceChildren(el('p', {class: 'sub', text: 'Select a module to see its details and highlight what it uses and what uses it.'})); }
  for (const nd of nodes) {
    nd.addEventListener('click', () => select(nd.dataset.id));
    nd.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); select(nd.dataset.id); } });
  }
  detail.replaceChildren(el('p', {class: 'sub', text: 'Select a module to see its details and highlight what it uses and what uses it.'}));
}

const fit = $('#fit');
if (fit) fit.addEventListener('click', () => { const on = $('#graph').classList.toggle('fit'); fit.textContent = on ? 'Actual size' : 'Fit width'; });

// impact explorer
const E = DATA.explorer;
const input = $('#impact-q'), out = $('#impact-out'), hopsBox = $('#impact-hops');
function renderImpact() {
  if (!E) return;
  const q = input.value;
  if (!q.trim()) { out.replaceChildren(el('p', {class: 'sub', text: 'Type a file or a directory from this repository.'})); return; }
  const hops = hopsBox.value ? Number(hopsBox.value) : null;
  const r = impactOf(E, q, hops);
  if (r.error) { out.replaceChildren(el('p', {class: 'err', text: r.error})); return; }
  const d = r.dependents, t = r.tests, kids = [];
  kids.push(el('h3', {}, 'Changing ', el('code', {text: r.target}), ' (' + n(r.files) + (r.files === 1 ? ' file, ' : ' files, ') + n(r.code) + ' code lines) can affect:'));
  if (!d.files && !t.files) {
    kids.push(el('p', {text: 'Nothing imports it: no file in the analysed set depends on it' + (hops ? ' within ' + hops + (hops === 1 ? ' hop.' : ' hops.') : ', directly or through others.')}));
  } else {
    kids.push(el('ul', {},
      el('li', {text: n(d.files) + ' code files in ' + d.modules.length + ' modules (' + d.share + '% of the code), ' + n(d.direct) + ' importing it directly'}),
      el('li', {text: n(t.files) + ' test files, ' + n(t.direct) + ' importing it directly'}),
      d.by_distance.length > 1 ? el('li', {text: 'code files by number of imports away: ' + d.by_distance.map((c, k) => (k + 1) + ': ' + n(c)).join(', ')}) : null));
    if (d.modules.length) {
      const rows = d.modules.slice(0, 15).map(m => el('tr', {}, el('td', {class: 'path', text: m.module}), el('td', {class: 'num', text: n(m.files)}), el('td', {class: 'num', text: n(m.direct)}), el('td', {class: 'num', text: n(m.code)})));
      kids.push(el('div', {class: 'tablewrap'}, el('table', {}, el('thead', {}, el('tr', {}, el('th', {text: 'Affected module'}), el('th', {class: 'num', text: 'Files'}), el('th', {class: 'num', text: 'Direct'}), el('th', {class: 'num', text: 'Code'}))), el('tbody', {}, rows))));
      if (d.modules.length > 15) kids.push(el('p', {class: 'sub', text: (d.modules.length - 15) + ' more modules.'}));
    }
    if (r.owners.length) kids.push(el('p', {}, el('b', {text: 'Top owner of each affected file: '}), r.owners.slice(0, 5).map(o => o.name + ' ' + o.share + '%' + (o.idle_days > E.inactive_days ? ' (silent ' + o.idle_days + 'd)' : '')).join(', ') + '. Tell them, or ask them to review.'));
    if (t.paths.length) kids.push(el('details', {}, el('summary', {text: 'Tests that reach it, nearest first (' + n(t.files) + ')'}), el('ul', {}, t.paths.map(p => el('li', {class: 'mono', text: p}))), t.files > t.paths.length ? el('p', {class: 'sub', text: 'and ' + n(t.files - t.paths.length) + ' more'}) : null));
  }
  if (r.depends_on.length) kids.push(el('p', {}, el('b', {text: 'It depends on: '}), r.depends_on.slice(0, 10).map(m => m.module + ' (' + m.files + ')').join(', ')));
  out.replaceChildren(...kids);
}
window.showImpact = function (name) {
  if (!E) return;
  input.value = name;
  renderImpact();
  $('#impact').scrollIntoView({behavior: 'smooth'});
};
if (E && input) {
  const list = $('#impact-list');
  const names = new Set(E.modules);
  const dirs = new Set();
  for (const f of E.files) { const parts = f[0].split('/'); for (let k = 1; k < parts.length; k++) dirs.add(parts.slice(0, k).join('/')); }
  dirs.forEach(d => names.add(d));
  const opts = Array.from(names).sort();
  if (E.files.length <= 4000) E.files.forEach(f => opts.push(f[0]));
  opts.forEach(v => list.append(el('option', {value: v})));
  input.addEventListener('input', renderImpact);
  hopsBox.addEventListener('change', renderImpact);
  renderImpact();
}
})();
"""
