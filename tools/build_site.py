"""Build the Tessri site: the landing page from `site/index.html` and the guide from `docs/guide/*.md`.

Zero dependencies, like the tool. The landing page's example is lifted from the README so the two cannot drift; every
guide page is Markdown rendered by the small converter below (headings, paragraphs, fenced code, tables, lists,
links, code spans, bold and italic are all the guide uses). Links between guide pages become links between the
rendered pages; links out of the guide point at the repository on GitHub.

    python tools/build_site.py --out _site
    python -m http.server --directory _site

The output directory is created, or reused when it holds the marker this script writes; anything else is refused.
"""

from __future__ import annotations

import argparse
import html
import posixpath
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
GUIDE = ROOT / "docs" / "guide"
REPO = "https://github.com/tianyi-zhang-02/tessri"
BLOB = f"{REPO}/blob/main/"
TREE = f"{REPO}/tree/main/"
MARKER = ".tessri-site"
ASSETS = ("tessri.css", "favicon.svg")

# The guide's navigation: README.md (the guide index) gives the labels and the order; this gives the groups. A page
# the index names but no group claims lands under "More", so adding a page never hides it.
GROUPS = [
    ("Start", ["getting-started"]),
    ("Questions", ["scan", "ownership", "review-load", "graph", "impact"]),
    ("Changes", ["triage", "check"]),
    ("Output", ["html-report", "json"]),
    ("Setup", ["integration", "configuration"]),
    ("Reference", ["architecture", "limits", "formerly-repolife"]),
]

MARK = (
    '<svg viewBox="0 0 32 32" aria-hidden="true" fill="currentColor"><path d="M7 6h18v3H7zM15 7h3v20h-3z"/>'
    '<rect x="3" y="2" width="11" height="10" rx="3"/><rect x="19" y="2" width="11" height="10" rx="3"/>'
    '<rect x="12" y="15" width="9" height="7" rx="2"/><rect x="12" y="25" width="9" height="7" rx="2"/></svg>'
)

THEME_BUTTON = (
    '<button class="theme" type="button" aria-label="Switch between dark and light">'
    '<svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
    '<svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">'
    '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg></button>'
)

SCRIPTS = """<script>
(function () {
  var root = document.documentElement;
  var button = document.querySelector(".theme");
  if (button) {
    button.addEventListener("click", function () {
      var chosen = root.getAttribute("data-theme");
      var dark = chosen === "dark" || (!chosen && matchMedia("(prefers-color-scheme: dark)").matches);
      var next = dark ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("tessri-theme", next); } catch (e) {}
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll(".copy"), function (b) {
    b.addEventListener("click", function () {
      if (!navigator.clipboard) { return; }
      navigator.clipboard.writeText(b.getAttribute("data-copy")).then(function () {
        var was = b.textContent;
        b.textContent = "Copied";
        setTimeout(function () { b.textContent = was; }, 1200);
      });
    });
  });
})();
</script>"""

THEME_BOOT = '<script>try{var t=localStorage.getItem("tessri-theme");if(t)document.documentElement.setAttribute("data-theme",t)}catch(e){}</script>'


class BuildError(Exception):
    pass


# --- Markdown ------------------------------------------------------------------------------------------------------

_CODE = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*([^*\s](?:[^*]*?[^*\s])?)\*(?![\w*])")
_HEADING = re.compile(r"(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"[-*]\s+(.*)")
_NUMBERED = re.compile(r"\d+\.\s+(.*)")


def rewrite_link(url: str) -> str:
    """A link as the guide writes it (relative to docs/guide) -> a link as the site needs it."""
    if re.match(r"[a-z][a-z0-9+.-]*:", url) or url.startswith("#"):
        return url
    path, _, fragment = url.partition("#")
    tail = f"#{fragment}" if fragment else ""
    if "/" not in path and path.endswith(".md"):
        name = "index.html" if path == "README.md" else path[:-3] + ".html"
        return name + tail
    inside = posixpath.normpath(posixpath.join("docs/guide", path))
    if inside.startswith("../"):
        raise BuildError(f"link leaves the repository: {url}")
    return (TREE if path.endswith("/") or "." not in posixpath.basename(inside) else BLOB) + inside + tail


def inline(text: str) -> str:
    """Code spans, links, bold and italic; everything else escaped."""
    spans: list[str] = []

    def keep(m: re.Match) -> str:
        spans.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = _CODE.sub(keep, text)
    text = html.escape(text, quote=False)
    text = _LINK.sub(lambda m: f'<a href="{html.escape(rewrite_link(m.group(2)), quote=True)}">{m.group(1)}</a>', text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    return re.sub("\x00(\\d+)\x00", lambda m: spans[int(m.group(1))], text)


def plain(text: str) -> str:
    """Heading text without its markup, for titles and labels."""
    text = _CODE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    return _BOLD.sub(r"\1", text).replace("*", "").strip()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", plain(text).lower()).strip("-")


def _table(rows: list[str]) -> str:
    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    head = cells(rows[0])
    align = [c.endswith(":") for c in cells(rows[1])] if len(rows) > 1 and set(rows[1]) <= set("|-: ") else [False] * len(head)
    body = rows[2:] if len(rows) > 1 and set(rows[1]) <= set("|-: ") else rows[1:]
    def attr(i: int) -> str:
        return ' class="num"' if i < len(align) and align[i] else ""

    out = ['<div class="table"><table>', "<thead><tr>" + "".join(f"<th{attr(i)}>{inline(c)}</th>" for i, c in enumerate(head)) + "</tr></thead>"]
    if body:
        out.append("<tbody>")
        for row in body:
            out.append("<tr>" + "".join(f"<td{attr(i)}>{inline(c)}</td>" for i, c in enumerate(cells(row))) + "</tr>")
        out.append("</tbody>")
    out.append("</table></div>")
    return "\n".join(out)


def render_markdown(text: str) -> tuple[str, str]:
    """(title, body HTML) for one guide page. The title is the first level-one heading."""
    lines = text.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    title = ""
    i = 0

    def flush() -> None:
        if paragraph:
            out.append(f"<p>{inline(' '.join(s.strip() for s in paragraph))}</p>")
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush()
            lang = line[3:].strip()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            attr = f' class="language-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre><code{attr}>{html.escape(chr(10).join(code))}</code></pre>")
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        if re.fullmatch(r"-{3,}|\*{3,}", line.strip()):
            flush()
            out.append("<hr>")
            i += 1
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            level, body = len(heading.group(1)), heading.group(2)
            if level == 1 and not title:
                title = plain(body)
            out.append(f'<h{level} id="{slug(body)}">{inline(body)}</h{level}>')
            i += 1
            continue
        if line.startswith("|"):
            flush()
            rows: list[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_table(rows))
            continue
        bullet, numbered = _BULLET.match(line), _NUMBERED.match(line)
        if bullet or numbered:
            flush()
            tag, pattern = ("ul", _BULLET) if bullet else ("ol", _NUMBERED)
            items: list[str] = []
            while i < len(lines):
                m = pattern.match(lines[i])
                if m:
                    items.append(m.group(1))
                elif lines[i].startswith("  ") and items and lines[i].strip():
                    items[-1] += " " + lines[i].strip()  # a wrapped item
                else:
                    break
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(item)}</li>" for item in items) + f"</{tag}>")
            continue
        paragraph.append(line)
        i += 1
    flush()
    return title, "\n".join(out)


# --- Pages -----------------------------------------------------------------------------------------------------------


def guide_index() -> list[tuple[str, str]]:
    """(slug, label) for every page the guide index links, in its order."""
    text = (GUIDE / "README.md").read_text(encoding="utf-8")
    found = []
    for m in _LINK.finditer(text):
        label, url = m.group(1), m.group(2)
        if "/" not in url and url.endswith(".md") and url != "README.md":
            found.append((url[:-3], plain(label)))
    return found


def head(title: str, description: str, depth: int) -> str:
    up = "../" * depth
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f'<meta name="description" content="{html.escape(description, quote=True)}">\n'
        f'<link rel="icon" href="{up}favicon.svg" type="image/svg+xml">\n<link rel="stylesheet" href="{up}tessri.css">\n'
        f"{THEME_BOOT}\n</head>\n"
    )


def top(depth: int, current: str | None) -> str:
    up = "../" * depth
    guide = ' aria-current="page"' if current == "guide" else ""
    return (
        f'<div class="sky">\n<header class="wrap top">\n  <a class="wordmark" href="{up or "./"}" aria-label="Tessri home">{MARK}<span>tessri<span class="dot">.</span></span></a>\n'
        f'  <nav aria-label="Site"><a href="{up}guide/"{guide}>Guide</a><a href="{REPO}">GitHub</a>{THEME_BUTTON}</nav>\n</header>\n</div>\n'
    )


def foot(depth: int) -> str:
    up = "../" * depth
    return (
        '<footer class="wrap foot">\n  <nav aria-label="Footer">'
        f'<a href="{up}guide/">Guide</a><a href="{up}guide/integration.html">Integration</a><a href="{up}guide/json.html">JSON</a>'
        f'<a href="{up}guide/limits.html">Limits</a><a href="{BLOB}CHANGELOG.md">Changelog</a><a href="{REPO}">GitHub</a></nav>\n'
        f'  <span>MIT. Formerly repolife; the <a href="{up}guide/formerly-repolife.html">old name works through 0.2.x</a>.</span>\n</footer>\n'
    )


def nav(pages: list[tuple[str, str]], current: str) -> str:
    labels = dict(pages)
    placed: set[str] = set()
    groups: list[tuple[str, list[str]]] = []
    for name, slugs in GROUPS:
        members = [s for s in slugs if s in labels]
        placed.update(members)
        if members:
            groups.append((name, members))
    rest = [s for s, _ in pages if s not in placed]
    if rest:
        groups.append(("More", rest))

    def link(s: str, label: str) -> str:
        mark = ' aria-current="page"' if s == current else ""
        return f'<li><a href="{s}.html"{mark}>{html.escape(label)}</a></li>'

    out = ['<aside class="guide-nav"><details open><summary>Guide pages</summary>']
    out.append('<p class="group">Guide</p><ul>' + ('<li><a href="./" aria-current="page">Overview</a></li>' if current == "index" else '<li><a href="./">Overview</a></li>') + "</ul>")
    for name, members in groups:
        out.append(f'<p class="group">{html.escape(name)}</p><ul>' + "".join(link(s, labels[s]) for s in members) + "</ul>")
    out.append('</details><script>if(matchMedia("(max-width: 880px)").matches){document.currentScript.previousElementSibling.removeAttribute("open")}</script></aside>')
    return "\n".join(out)


def guide_page(name: str, title: str, body: str, pages: list[tuple[str, str]]) -> str:
    description = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", body.split("<p>", 1)[1].split("</p>", 1)[0])) if "<p>" in body else title
    source = f"docs/guide/{name}.md"
    article = (
        f'<article class="prose">\n{body}\n<p class="source">Source: <a href="{BLOB}{source}">{source}</a>. The guide is Markdown in the repository; this page is built from it.</p>\n</article>'
    )
    return (
        head(f"{title} · Tessri guide", description[:300], 1)
        + "<body>\n"
        + top(1, "guide")
        + f'<div class="wrap guide">\n{nav(pages, name if name != "README" else "index")}\n{article}\n</div>\n'
        + foot(1)
        + SCRIPTS
        + "\n</body>\n</html>\n"
    )


def readme_example() -> str:
    """The fenced block under "A complete example" in the README, as it is."""
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "## A complete example")
        fence = next(i for i in range(start, len(lines)) if lines[i].startswith("```"))
    except StopIteration as exc:
        raise BuildError("README.md has no fenced example under '## A complete example'") from exc
    end = next(i for i in range(fence + 1, len(lines)) if lines[i].startswith("```"))
    return "\n".join(lines[fence + 1 : end])


def example_panel() -> str:
    """The README's example as a reader sees it: the command line, then the Markdown output rendered."""
    first, _, rest = readme_example().partition("\n")
    if not first.startswith("$ "):
        raise BuildError("the README example should start with the command that produced it")
    _, body = render_markdown(rest)
    return f'<div class="cmdline">$ <b>{html.escape(first[2:])}</b></div>\n<div class="output prose">\n{body}\n</div>'


def landing() -> str:
    template = (SITE / "index.html").read_text(encoding="utf-8")
    example = example_panel()
    filled = (
        template.replace("{{mark}}", MARK)
        .replace("{{repo}}", REPO)
        .replace("{{theme_button}}", THEME_BUTTON)
        .replace("{{example}}", example)
        .replace("{{scripts}}", SCRIPTS)
    )
    left = re.findall(r"{{\w+}}", filled)
    if left:
        raise BuildError(f"unfilled placeholders in site/index.html: {', '.join(sorted(set(left)))}")
    return filled


def build(out: Path) -> list[Path]:
    """Write the site into `out` and return the files written."""
    out = out.resolve()
    if out.exists():
        if out.is_file() or (any(out.iterdir()) and not (out / MARKER).exists()):
            raise BuildError(f"{out} is not empty and was not built by this script; choose another directory")
        shutil.rmtree(out)
    (out / "guide").mkdir(parents=True)
    written: list[Path] = []

    def write(rel: str, text: str) -> None:
        target = out / rel
        target.write_text(text, encoding="utf-8")
        written.append(target)

    for asset in ASSETS:
        shutil.copyfile(SITE / asset, out / asset)
        written.append(out / asset)
    write("index.html", landing())
    pages = guide_index()
    known = {s for s, _ in pages}
    for md in sorted(GUIDE.glob("*.md")):
        name = md.stem
        if name != "README" and name not in known:
            raise BuildError(f"docs/guide/{md.name} is not linked from docs/guide/README.md, so the guide index would not show it")
        title, body = render_markdown(md.read_text(encoding="utf-8"))
        if not title:
            raise BuildError(f"docs/guide/{md.name} has no level-one heading")
        write(f"guide/{'index' if name == 'README' else name}.html", guide_page(name, title, body, pages))
    write(".nojekyll", "")
    write(MARKER, "built by tools/build_site.py\n")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Tessri site from site/ and docs/guide/.")
    parser.add_argument("--out", default="_site", help="output directory (default: _site)")
    args = parser.parse_args(argv)
    try:
        written = build(Path(args.out))
    except BuildError as exc:
        print(f"build_site: {exc}", file=sys.stderr)
        return 2
    print(f"{len(written)} files written to {Path(args.out).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
