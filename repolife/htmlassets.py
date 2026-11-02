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
  --r-owner: #6250d6; --r-outside: #eb6834; --r-auto: #898781;
  --rail: #f1f0f7; --accent-soft: #e7e3fa; --brand: #6652cb;
"""

_DARK = """
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,.10); --wash: rgba(255,255,255,.06);
  --accent: #3987e5; --link: #6da7ec;
  --st-active: #3987e5; --st-stable: #199e70; --st-dormant: #c98500; --st-orphan: #d03b3b;
  --edge: #4d4c48; --edge-hot: #6da7ec;
  --r-owner: #9085e9; --r-outside: #d95926; --r-auto: #898781;
  --rail: #131319; --accent-soft: #2c2546; --brand: #b0a0ff;
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
.g3 { grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }
.g2 { grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }
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
.r-owner { --c: var(--r-owner); } .r-outside { --c: var(--r-outside); } .r-auto { --c: var(--r-auto); }
.stackwrap { margin-top: 5px; margin-left: auto; }
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
.detail dd { overflow-wrap: anywhere; }
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
  .g2 { grid-template-columns: 1fr; }
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

CSS += """
/* Repository workspace: the same report, with focused views when scripts are available. */
body { font-size: 14px; }
.script-only { display: none; }
.workspace-ready .script-only { display: inline-flex; }
.skip-link { position: fixed; top: -100px; left: 16px; z-index: 40; padding: 12px; background: var(--surface); }
.skip-link:focus { top: 12px; }
.workspace-rail { position: fixed; inset: 0 auto 0 0; width: 216px; z-index: 10; display: flex; flex-direction: column; padding: 26px 16px 16px; background: var(--rail); border-right: 1px solid var(--grid); overflow-y: auto; }
.wordmark { display: flex; align-items: center; gap: 10px; padding: 0 10px; font-size: 23px; letter-spacing: -.8px; }
.wordmark strong { font-weight: 650; }
.brand-mark { width: 27px; height: 27px; color: var(--brand); }
.brand-dot { color: var(--brand); }
.brand-caption { margin: 5px 0 26px 10px; color: var(--ink2); font-size: 12px; }
.repo-context { display: grid; gap: 5px; margin: 0 0 18px; padding: 0 10px 18px; border-bottom: 1px solid var(--grid); overflow-wrap: anywhere; }
.context-label { font-size: 10px; font-weight: 650; letter-spacing: 1.2px; color: var(--ink2); }
.repo-context strong { font-weight: 600; }
.repo-context .mono { color: var(--ink2); font-size: 11px; }
.quick-trigger { justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 12px; padding: 9px 10px; border: 1px solid var(--grid); border-radius: 7px; background: transparent; color: var(--ink2); font: inherit; font-size: 12px; cursor: pointer; }
kbd { font: 11px ui-monospace, monospace; color: var(--ink2); padding: 1px 4px; border: 1px solid var(--axis); border-radius: 4px; white-space: nowrap; }
.nav-primary { margin-top: 10px; }
.workspace-rail nav a { display: flex; align-items: center; padding: 9px 10px; margin: 2px 0; border-radius: 6px; color: var(--ink2); text-decoration: none; font-size: 13px; }
.workspace-rail nav a:hover, .quick-trigger:hover { background: var(--wash); color: var(--ink); }
.workspace-rail nav a[aria-current=page] { color: var(--ink); background: var(--accent-soft); font-weight: 600; }
.nav-more { margin-top: 18px; border-top: 1px solid var(--grid); padding-top: 10px; }
.nav-more summary { margin: 0; padding: 9px 10px; font-size: 12px; }
.nav-secondary { padding-top: 4px; }
.rail-bottom { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: auto; padding: 28px 10px 0; color: var(--ink2); font-size: 11px; }
.rail-bottom a { flex-basis: 100%; margin-top: 4px; color: var(--ink2); text-decoration: none; }
.snapshot-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--axis); }
.workspace-main { margin-left: 216px; min-width: 0; }
.workspace-top { position: sticky; top: 0; z-index: 5; display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 58px; padding: 10px 32px; background: var(--page); border-bottom: 1px solid var(--grid); }
.workspace-breadcrumb { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: var(--ink2); }
.workspace-breadcrumb strong { color: var(--ink); font-weight: 500; }
.snapshot-meta { display: flex; flex-shrink: 0; align-items: center; gap: 14px; font-size: 11px; color: var(--ink2); }
.snapshot-revision { display: none; white-space: nowrap; }
.workspace-breadcrumb { min-width: 0; }
.workspace-breadcrumb > span:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: min(24ch, 100%); }
.workspace-main > .wrap { max-width: 1280px; padding-left: 36px; padding-right: 36px; }
.workspace-main main { padding-top: 34px; min-height: calc(100vh - 138px); }
.workspace-ready main > section { display: none; padding-top: 0; }
.workspace-ready main > section.is-active { display: block; animation: workspace-in .16s ease-out; }
@keyframes workspace-in { from { opacity: .5; transform: translateY(3px); } to { opacity: 1; transform: none; } }
h1 { font-size: 28px; letter-spacing: -.7px; }
h2 { font-size: 25px; letter-spacing: -.5px; }
.lede { margin-top: 9px; margin-bottom: 24px; font-size: 13px; }
.hero { font-size: 42px; letter-spacing: -1px; }
.card { border-color: var(--grid); border-radius: 10px; }
.tiles { gap: 0 24px; border-top: 1px solid var(--grid); margin-top: 24px; }
.tiles > .tile { padding: 18px 0; border: 0; border-bottom: 1px solid var(--grid); border-radius: 0; background: transparent; }
.tile .value { font-size: 24px; letter-spacing: -.5px; }
.start-points { display: flex; flex-wrap: wrap; gap: 10px 24px; margin: 0 0 24px; }
.start-points a { color: var(--ink2); font-size: 12px; text-decoration: none; }
.start-points a:hover { color: var(--brand); text-decoration: underline; }
.start-points span { color: var(--brand); margin-left: 3px; }
.explorer .tools { gap: 10px; }
.explorer input { max-width: none; flex: 1 1 300px; }
.explorer select { font-size: 12px; }
.impact-totals { display: flex; flex-wrap: wrap; gap: 32px; margin: 20px 0; padding-bottom: 20px; border-bottom: 1px solid var(--grid); }
.impact-total strong { display: block; font-size: 32px; letter-spacing: -1px; font-weight: 600; }
.impact-total span { color: var(--ink2); font-size: 12px; }
.evidence-note { padding: 12px 14px; background: var(--wash); border-radius: 8px; color: var(--ink2); font-size: 12px; }
.reference-list { padding-left: 20px; font-size: 12px; overflow-wrap: anywhere; }
.reference-list li { padding: 4px 0; }
dialog#quick-open { width: min(640px, calc(100% - 32px)); max-height: 85vh; padding: 0; border: 1px solid var(--axis); border-radius: 15px; background: var(--surface); color: var(--ink); box-shadow: 0 24px 90px rgba(0,0,0,.25); }
dialog::backdrop { background: rgba(0,0,0,.38); }
.quick-heading { display: flex; align-items: center; justify-content: space-between; padding: 18px 20px 4px; }
.quick-heading strong { font-size: 13px; font-weight: 500; }
#quick-query { display: block; width: calc(100% - 40px); max-width: none; margin: 12px 20px 16px; padding: 12px; border-radius: 8px; }
#quick-results { overflow-y: auto; max-height: min(390px, 48vh); padding: 0 10px 10px; }
.quick-result { display: flex; width: 100%; justify-content: space-between; align-items: center; gap: 15px; padding: 11px 12px; border: 0; border-radius: 7px; background: transparent; color: var(--ink); text-align: left; font: inherit; font-size: 12px; cursor: pointer; overflow-wrap: anywhere; }
.quick-result[aria-selected=true] { background: var(--accent-soft); }
.quick-result small { flex-shrink: 0; color: var(--ink2); font-size: 11px; }
.quick-empty { padding: 20px 12px; color: var(--ink2); font-size: 12px; }
.quick-footer { display: flex; justify-content: space-between; gap: 12px; padding: 12px 20px; border-top: 1px solid var(--grid); color: var(--ink2); font-size: 11px; }
footer { font-size: 11px; }
@media (max-width: 800px) {
  .workspace-rail { position: relative; width: auto; padding: 16px; border-right: 0; border-bottom: 1px solid var(--grid); }
  .wordmark { padding-left: 0; font-size: 22px; }
  .brand-caption, .repo-context, .rail-bottom { display: none; }
  .quick-trigger { position: absolute; right: 16px; top: 17px; margin: 0; }
  .workspace-rail nav { margin-top: 14px; }
  .nav-primary { display: flex; gap: 4px; overflow-x: auto; margin-top: 0; }
  .nav-more { margin-top: 4px; padding-top: 0; border: 0; }
  .nav-secondary { display: flex; flex-wrap: wrap; gap: 4px; }
  .nav-more summary { padding: 5px 9px; }
  .workspace-rail nav a { flex-shrink: 0; padding: 7px 9px; }
  .workspace-main { margin-left: 0; }
  .workspace-main > .wrap { padding-left: 20px; padding-right: 20px; }
  .workspace-top { padding-left: 20px; padding-right: 20px; }
  .snapshot-captured { display: none; }
  .snapshot-revision { display: inline; }
  .workspace-main main { padding-top: 25px; }
  .g2 { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) { .workspace-ready main > section.is-active { animation: none; } }
@media print {
  .workspace-rail, .workspace-top, .start-points, .skip-link, dialog { display: none !important; }
  .workspace-main { margin: 0; }
  .workspace-ready main > section { display: block !important; padding-top: 20px; }
}
"""

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
  const evidence = E.files.map(() => new Map());
  for (const [s, t, , kind] of E.edges) evidence[s].set(t, kind || 'unknown');
  E._ix = {byPath, rev, fwd, evidence};
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

function impactOf(E, input, hops, testLimit, policy = 'all') {
  if (!['all', 'imports'].includes(policy)) return {error: 'Unknown relationship policy.'};
  const target = resolve(E, input);
  if (target.error) return target;
  const {rev, fwd, evidence} = indexOf(E);
  const kinds = ['import', 'package', 'dynamic', 'string', 'unknown'];
  const imported = kind => kind === 'import' || kind === 'package';
  function walk(selected) {
    const dist = new Int32Array(E.files.length).fill(-1), queue = [];
    const followed = {}, excluded = {}, references = [], unknown = new Set();
    for (const kind of kinds) (selected === 'all' || imported(kind) ? followed : excluded)[kind] = 0;
    for (const s of target.seeds) { dist[s] = 0; queue.push(s); }
    for (let head = 0; head < queue.length; head++) {
      const node = queue[head];
      if (hops != null && dist[node] >= hops) continue;
      for (const d of rev[node]) {
        const kind = evidence[d].get(node) || 'unknown';
        if (!imported(kind)) references.push({from: E.files[d][0], to: E.files[node][0], kind});
        if (kind === 'unknown') unknown.add(E.files[d][5] || '?');
        if (selected === 'imports' && !imported(kind)) { excluded[kind]++; continue; }
        followed[kind]++;
        if (dist[d] < 0) { dist[d] = dist[node] + 1; queue.push(d); }
      }
    }
    return {dist, queue, followed, excluded, references, unknown};
  }
  const walked = walk(policy), {dist, queue} = walked;
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
    if (seeds.has(t) || f[3] || (policy === 'imports' && !imported(evidence[s].get(t)))) continue;
    if (!needs.has(f[1])) needs.set(f[1], new Set());
    needs.get(f[1]).add(t);
  }
  const ordered = tests.slice().sort((a, b) => dist[a] - dist[b] || (E.files[a][0] < E.files[b][0] ? -1 : 1));
  const edges = {
    policy, hops: hops == null ? null : hops,
    kinds: kinds.filter(k => policy === 'all' || imported(k)),
    followed: walked.followed, excluded: walked.excluded,
    references: {count: walked.references.length, limit: 8, listed: walked.references.slice(0, 8)},
    unclassified: {edges: (walked.followed.unknown || 0) + (walked.excluded.unknown || 0), analyzers: Array.from(walked.unknown).sort()},
  };
  if (policy === 'all') {
    const narrow = walk('imports').queue.filter(i => !seeds.has(i));
    edges.imports_only = {files: narrow.filter(i => !E.files[i][3]).length, tests: narrow.filter(i => E.files[i][3]).length};
  }
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
    edges,
    depends_on: Array.from(needs, ([m, set]) => ({module: E.modules[m], files: set.size})).sort((a, b) => b.files - a.files || (a.module < b.module ? -1 : 1)),
    owners: Array.from(people, ([p, lines]) => ({name: E.people[p].name, idle_days: E.people[p].idle_days, share: code ? Math.round(100 * lines / code) : 0}))
      .sort((a, b) => b.share - a.share || (a.name < b.name ? -1 : 1)),
  };
}

// ---- URL fragment: #view, or #impact?path=<encoded>&edges=all|imports&hops=<n> for a restorable query ------
// Pure functions: the page wires them to location, history and the explorer controls below.

function positiveSteps(value) {
  // A hop limit is a positive safe integer, written plainly; anything else is "no limit given", never a wider walk.
  const text = String(value == null ? '' : value).trim();
  return /^[1-9][0-9]*$/.test(text) && Number.isSafeInteger(Number(text)) ? Number(text) : null;
}

function parseFragment(hash) {
  const raw = String(hash == null ? '' : hash).replace(/^#/, '');
  const cut = raw.indexOf('?');
  let view;
  try { view = decodeURIComponent(cut < 0 ? raw : raw.slice(0, cut)); } catch (_) { view = ''; }
  const params = new URLSearchParams(cut < 0 ? '' : raw.slice(cut + 1));  // first value wins; malformed escapes do not throw
  const path = (params.get('path') || '').trim();
  if (view !== 'impact' || !path) return {view, query: null};
  const edges = params.get('edges') === 'imports' ? 'imports' : 'all';
  return {view, query: {path, edges, hops: positiveSteps(params.get('hops'))}};
}

function impactFragment(path, edges, hops) {
  const name = String(path == null ? '' : path).trim();
  if (!name) return '#impact';
  let fragment = '#impact?path=' + encodeURIComponent(name);
  if (edges === 'imports') fragment += '&edges=imports';
  const steps = positiveSteps(hops);
  if (steps != null) fragment += '&hops=' + steps;
  return fragment;
}

const root = typeof globalThis !== 'undefined' ? globalThis : window;
root.RepolifeCore = {resolve, impactOf, parseFragment, impactFragment};
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

// The impact explorer's controls, declared here because restoring a query from the URL happens while the first
// view is chosen, before the explorer block below runs.
const E = DATA.explorer;
const input = $('#impact-q'), out = $('#impact-out'), hopsBox = $('#impact-hops'), edgesBox = $('#impact-edges');

// Focused views retain ordinary anchors as the no-script and print fallback.
const views = $$('main > section[id]'), viewLinks = $$('nav a[data-view]');
function selectView(id, focus) {
  const view = views.find(v => v.id === id);
  if (!view) return false;
  views.forEach(v => v.classList.toggle('is-active', v === view));
  viewLinks.forEach(link => {
    if (link.dataset.view === id) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  const link = viewLinks.find(a => a.dataset.view === id);
  $('#current-view').textContent = link ? link.lastElementChild.textContent : id;
  const holder = link && link.closest('details');  // a secondary entry folded into the rail's "more" list
  if (holder && !holder.open) holder.open = true;
  if (focus) {
    const heading = $('h1, h2', view);
    if (heading) { heading.tabIndex = -1; heading.focus({preventScroll: true}); }
    window.scrollTo({top: 0});
  }
  return true;
}
function hashView() {
  // Reads the address and never writes it, so a hash change can not start a loop.
  const parsed = parseFragment(location.hash);
  const id = parsed.view;
  if (id === 'workspace-content' && views.some(view => view.classList.contains('is-active'))) return;
  const node = document.getElementById(id), view = node && node.closest('main > section');
  selectView(view ? view.id : 'overview', false);
  if (parsed.query && view && view.id === 'impact') applyImpactQuery(parsed.query);
}
function currentFragment(id) {
  return id === 'impact' && E && input ? impactFragment(input.value, edgesBox.value, hopsBox.value) : '#' + id;
}
function navigateWorkspace(id, focus = true) {
  if (!selectView(id, focus)) return;
  const target = currentFragment(id);  // the impact entry carries the query, so it is a link worth keeping
  if (location.hash !== target) location.hash = target;
}
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  if (!link) return;
  const node = document.getElementById(link.getAttribute('href').slice(1));
  const view = node && node.closest('main > section');
  if (view) { event.preventDefault(); navigateWorkspace(view.id); }
});
window.addEventListener('hashchange', hashView);
hashView();
document.body.classList.add('workspace-ready');

// Quick navigation only searches the views and analyzed paths in this snapshot.
const quickDialog = $('#quick-open'), quickTrigger = $('#quick-trigger'), quickQuery = $('#quick-query');
const quickResults = $('#quick-results'), quickCount = $('#quick-count');
let quickRows = [], quickIndex = 0, restoreQuickFocus = true;
const viewChoices = viewLinks.map(a => ({label: a.lastElementChild.textContent, kind: 'View', view: a.dataset.view}));
const indexedFiles = DATA.explorer ? DATA.explorer.files.map(f => ({label: f[0], kind: 'File'})) : [];
const indexedDirs = new Set();
indexedFiles.forEach(f => { const parts = f.label.split('/'); for (let i = 1; i < parts.length; i++) indexedDirs.add(parts.slice(0, i).join('/')); });
const quickChoices = [...viewChoices, ...Array.from(indexedDirs).sort().map(label => ({label, kind: 'Directory'})), ...indexedFiles];
function highlightQuick() {
  $$('.quick-result', quickResults).forEach((row, i) => row.setAttribute('aria-selected', String(i === quickIndex)));
  if (quickRows.length) {
    quickQuery.setAttribute('aria-activedescendant', 'quick-result-' + quickIndex);
    const row = document.getElementById('quick-result-' + quickIndex);
    row.scrollIntoView({block: 'nearest'});
  } else quickQuery.removeAttribute('aria-activedescendant');
}
function chooseQuick(index) {
  const selected = quickRows[index];
  if (!selected) return;
  restoreQuickFocus = false;
  quickDialog.close();
  if (selected.view) navigateWorkspace(selected.view);
  else { window.showImpact(selected.label); $('#impact-q').focus({preventScroll: true}); }
}
function searchQuick() {
  const query = quickQuery.value.trim().toLowerCase();
  const matches = quickChoices.filter(row => !query || row.label.toLowerCase().includes(query));
  quickRows = matches.slice(0, 60); quickIndex = 0;
  quickResults.replaceChildren(...quickRows.map((row, i) => {
    const button = el('button', {class: 'quick-result', id: 'quick-result-' + i, type: 'button', role: 'option', tabindex: '-1', 'aria-selected': String(i === 0)}, el('span', {class: row.kind === 'View' ? '' : 'mono', text: row.label}), el('small', {text: row.kind}));
    button.addEventListener('click', () => chooseQuick(i));
    return button;
  }));
  if (!quickRows.length) quickResults.append(el('p', {class: 'quick-empty', text: 'No matching file or view in this snapshot.'}));
  quickCount.textContent = (matches.length > 60 ? 'Showing 60 of ' : '') + n(matches.length) + ' matches' + (!DATA.explorer ? ' · file index unavailable' : '');
  highlightQuick();
}
function openQuick() {
  if (quickDialog.open) { quickDialog.close(); return; }
  restoreQuickFocus = true; quickQuery.value = '';
  quickDialog.showModal(); quickQuery.setAttribute('aria-expanded', 'true');
  searchQuick(); quickQuery.focus();
}
if (typeof quickDialog.showModal === 'function') {
  quickTrigger.addEventListener('click', openQuick);
  $('#quick-close').addEventListener('click', () => quickDialog.close());
  quickDialog.addEventListener('close', () => { quickQuery.setAttribute('aria-expanded', 'false'); if (restoreQuickFocus) quickTrigger.focus(); });
  quickQuery.addEventListener('input', searchQuick);
  quickQuery.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); quickDialog.close(); }
    else if (['ArrowDown', 'ArrowUp'].includes(event.key) && quickRows.length) {
      event.preventDefault(); quickIndex = (quickIndex + (event.key === 'ArrowDown' ? 1 : -1) + quickRows.length) % quickRows.length; highlightQuick();
    } else if (event.key === 'Enter') { event.preventDefault(); chooseQuick(quickIndex); }
  });
  $('#quick-shortcut').textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ K' : 'Ctrl K';
  document.addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openQuick(); } });
} else quickTrigger.hidden = true;

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

// impact explorer (its controls are declared with the views above)
function applyImpactQuery(query) {
  if (!E || !input) return;
  input.value = query.path;
  edgesBox.value = query.edges;
  if (query.hops == null) hopsBox.value = '';
  else {
    // A limit the control does not offer gets its own option, so the link's limit is applied, not widened.
    const text = String(query.hops);
    if (!Array.from(hopsBox.options).some(option => option.value === text)) hopsBox.append(el('option', {value: text, text: text + (query.hops === 1 ? ' step' : ' steps')}));
    hopsBox.value = text;
  }
  renderImpact();
}
function syncImpactUrl() {
  // While the impact view is current, the address mirrors the query through replaceState: one history entry per
  // view change, none per keystroke. Fails quietly where the history API is unavailable.
  if (!E || !input) return;
  const active = views.find(view => view.classList.contains('is-active'));
  if (!active || active.id !== 'impact') return;
  const target = impactFragment(input.value, edgesBox.value, hopsBox.value);
  if (location.hash === target) return;
  try { history.replaceState(history.state, '', target); } catch (_) { /* the address stays as it is */ }
}
function renderImpact() {
  if (!E) return;
  paintImpact();
  syncImpactUrl();
}
function paintImpact() {
  const q = input.value;
  if (!q.trim()) { out.replaceChildren(el('p', {class: 'sub', text: 'Type a file or a directory from this repository.'})); return; }
  const hops = hopsBox.value ? Number(hopsBox.value) : null;
  const r = impactOf(E, q, hops, null, edgesBox.value);
  if (r.error) { out.replaceChildren(el('p', {class: 'err', text: r.error})); return; }
  const d = r.dependents, t = r.tests, kids = [];
  kids.push(el('h3', {}, el('code', {text: r.target}), ' · ' + n(r.files) + (r.files === 1 ? ' file' : ' files')));
  kids.push(el('div', {class: 'impact-totals'},
    el('div', {class: 'impact-total'}, el('strong', {text: n(d.files)}), el('span', {text: 'code files reached'})),
    el('div', {class: 'impact-total'}, el('strong', {text: n(t.files)}), el('span', {text: 'candidate tests'}))));
  const evidence = r.edges, references = evidence.references;
  const scope = (hops ? 'Within ' + hops + (hops === 1 ? ' step' : ' steps') : 'Any number of steps') + ' · ';
  const explanation = evidence.policy === 'all'
    ? 'all relationships. Import-based links alone reach ' + n(evidence.imports_only.files) + ' code files and ' + n(evidence.imports_only.tests) + ' candidate tests.'
    : 'recognized dependency syntax and Python parent packages. ' + n(Object.values(evidence.excluded).reduce((a, b) => a + b, 0)) + ' inferred or unknown edges encountered but excluded.';
  kids.push(el('p', {class: 'evidence-note', text: scope + explanation}));
  if (!d.files && !t.files) {
    kids.push(el('p', {text: 'No dependent files reached under this relationship policy and step limit. Other runtime or external consumers may exist.'}));
  } else {
    kids.push(el('ul', {},
      el('li', {text: 'Affected modules: ' + n(d.modules.length) + ' · code files one step away: ' + n(d.direct)}),
      el('li', {text: 'Candidate tests one step away: ' + n(t.direct)}),
      d.by_distance.length > 1 ? el('li', {text: 'Code files by distance: ' + d.by_distance.map((c, k) => (k + 1) + (k ? ' steps: ' : ' step: ') + n(c)).join(', ')}) : null));
    if (d.modules.length) {
      const rows = d.modules.slice(0, 15).map(m => el('tr', {}, el('td', {class: 'path', text: m.module}), el('td', {class: 'num', text: n(m.files)}), el('td', {class: 'num', text: n(m.direct)}), el('td', {class: 'num', text: n(m.code)})));
      kids.push(el('div', {class: 'tablewrap'}, el('table', {}, el('thead', {}, el('tr', {}, el('th', {text: 'Affected module'}), el('th', {class: 'num', text: 'Files'}), el('th', {class: 'num', text: 'Direct'}), el('th', {class: 'num', text: 'Code'}))), el('tbody', {}, rows))));
      if (d.modules.length > 15) kids.push(el('p', {class: 'sub', text: (d.modules.length - 15) + ' more modules.'}));
    }
    if (r.owners.length) kids.push(el('p', {}, el('b', {text: 'Recorded file maintainers: '}), r.owners.slice(0, 5).map(o => o.name + ' ' + o.share + '%' + (o.idle_days > E.inactive_days ? ' (silent ' + o.idle_days + 'd)' : '')).join(', ')));
    if (t.paths.length) kids.push(el('details', {}, el('summary', {text: 'Candidate tests, nearest first (' + n(t.files) + ')'}), el('ul', {}, t.paths.map(p => el('li', {class: 'mono', text: p}))), t.files > t.paths.length ? el('p', {class: 'sub', text: 'and ' + n(t.files - t.paths.length) + ' more'}) : null));
  }
  if (references.count) kids.push(el('details', {}, el('summary', {text: 'Inferred and unknown evidence (' + n(references.count) + ')'}), el('ul', {class: 'reference-list'}, references.listed.map(ref => el('li', {}, el('code', {text: ref.from}), ' → ', el('code', {text: ref.to}), ' · ' + ref.kind))), references.count > references.listed.length ? el('p', {class: 'sub', text: 'Showing ' + references.listed.length + ' of ' + n(references.count) + ' edges at the visited frontier.'}) : null));
  if (r.depends_on.length) kids.push(el('p', {}, el('b', {text: 'It depends on: '}), r.depends_on.slice(0, 10).map(m => m.module + ' (' + m.files + ')').join(', ')));
  kids.push(el('p', {class: 'sub', text: 'Static evidence from this snapshot. Candidate paths do not record test execution or replace the project’s required checks.'}));
  out.replaceChildren(...kids);
}
window.showImpact = function (name) {
  if (!E) return;
  input.value = name;
  renderImpact();
  navigateWorkspace('impact', false);
  window.scrollTo({top: 0});
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
  edgesBox.addEventListener('change', renderImpact);
  renderImpact();
}
})();
"""
