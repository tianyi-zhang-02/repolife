"""A small JavaScript/TypeScript scanner: finds module specifiers without a parser.

repolife has no dependencies, so there is no tree-sitter or TypeScript compiler to lean on.
Reading imports only needs the lexical layer: enough to tell code from strings, comments,
template literals and regex literals, so `import` inside a comment or a string is not an import.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Dynamic:
    """`import(`./pages/${name}.tsx`)`: the literal text before and after the computed part."""

    head: str
    tail: str
    deep: bool  # a "/" follows the computed part, so subdirectories are possible


@dataclass
class Scan:
    specs: list[str] = field(default_factory=list)  # module specifiers: import, export ... from, require(), import()
    strings: set[str] = field(default_factory=set)  # other string literals that look like file paths
    dynamic: list[Dynamic] = field(default_factory=list)
    globs: list[str] = field(default_factory=list)  # import.meta.glob(...) patterns
    contexts: list[tuple[str, bool, str | None]] = field(default_factory=list)  # require.context(dir, recursive, regex)
    main_guard: bool = False
    hashbang: bool = False


# Only these produce events; identifiers, numbers and punctuation are skipped by the regex engine.
_EVENT = re.compile(
    r"""(?P<line>//[^\n]*)|(?P<block>/\*.*?\*/)|(?P<str>'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*")|(?P<tpl>`)|(?P<slash>/)"""
    r"""|(?<![\w$])(?<!(?<!\.)\.)(?P<kw>import|export|require)(?![\w$])""",  # not `obj.require`, but `...require(x)` is fine
    re.S,
)
_STRING = re.compile(r"""'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*\"""", re.S)
_REGEX = re.compile(r"/(?![*/])(?:[^/\\\n\[]|\\.|\[(?:[^\]\\\n]|\\.)*\])+/[a-z]*")
_REGEX_AFTER_WORD = re.compile(r"(?:^|[^\w$.])(?:return|typeof|case|do|else|in|of|void|yield|await|delete|throw|new|instanceof)$")

_IMPORT_FROM = re.compile(r"""\s*(?:type\s+|typeof\s+)?(?:[\w$]+\s*,?\s*)?(?:\*\s*as\s+[\w$]+\s*)?(?:\{[^}]*\}\s*)?from\s*(['"])([^'"\n]+)\1""")
_EXPORT_FROM = re.compile(r"""\s*(?:type\s+)?(?:\*(?:\s*as\s+[\w$]+)?|\{[^}]*\})\s*from\s*(['"])([^'"\n]+)\1""")
_REQUIRE = re.compile(r"\s*(?:\.\s*(?P<member>resolve|context)\s*)?\(\s*")
_CONTEXT = re.compile(r"""(['"])([^'"\n]+)\1\s*(?:,\s*(true|false)\s*(?:,\s*(/(?:[^/\\\n]|\\.)+/[a-z]*))?)?""")
_META_GLOB = re.compile(r"""\s*\.\s*meta\s*\.\s*glob(?:Eager)?\s*(?:<[^>(]*>)?\s*\(\s*(?P<arg>\[[^\]]*\]|'[^'\n]*'|"[^"\n]*"|`[^`]*`)""")
_LITERAL = re.compile(r"""['"`]([^'"`]+)['"`]""")
_CONCAT = re.compile(r"""\s*\+(?:\s*[\w$.]+(?:\([^()]*\))?\s*\+\s*(['"])([^'"\n]*)\1)?""")
_TRIPLE = re.compile(r"""///\s*<reference\s+path\s*=\s*["']([^"']+)["']""")
_MAIN = re.compile(r"\brequire\.main\s*===?\s*module\b|\bimport\.meta\.main\b|\bmodule\.parent\b|\bprocess\.argv\[1\]")

_PATHLIKE = re.compile(r"[\w@~<>./\-]+")
_CODE_EXT = re.compile(r"[\w\-]\.(?:[cm]?[jt]sx?|vue|svelte|astro)$")  # a name before the dot: ".js" alone is a suffix, not a file


def _skip_ws(text: str, i: int) -> int:
    """Skip whitespace and comments: `import(/* webpackChunkName: "x" */ "./x")` still has its argument next."""
    n = len(text)
    while i < n:
        if text[i] in " \t\r\n":
            i += 1
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2)
            if close < 0:
                break
            i = close + 2
        elif text.startswith("//", i):
            newline = text.find("\n", i)
            i = n if newline < 0 else newline
        else:
            break
    return i


def _regex_allowed(text: str, i: int) -> bool:
    """Whether the `/` at `i` starts a regex literal rather than dividing, judged by the previous token."""
    j = i - 1
    while j >= 0 and text[j] in " \t\r\n":
        j -= 1
    if j < 0:
        return True
    c = text[j]
    if c in "(,=:[!&|?{};+-*%<>~^":
        return True
    return (c.isalnum() or c in "_$") and bool(_REGEX_AFTER_WORD.search(text[max(0, j - 10) : j + 1]))


def _template(text: str, i: int) -> tuple[int, list[str]] | None:
    """Read the template literal opening at `text[i]`: (end, literal pieces around each `${}`), or None if unterminated."""
    pieces: list[str] = []
    buf: list[str] = []
    n = len(text)
    i += 1
    while i < n:
        c = text[i]
        if c == "\\":
            buf.append(text[i + 1 : i + 2])
            i += 2
        elif c == "`":
            pieces.append("".join(buf))
            return i + 1, pieces
        elif c == "$" and text.startswith("${", i):
            pieces.append("".join(buf))
            buf = []
            i = _skip_expression(text, i + 2)
            if i < 0:
                return None
        else:
            buf.append(c)
            i += 1
    return None


_EXPR_EVENT = re.compile(r"""[{}'"`/]""")


def _skip_expression(text: str, i: int) -> int:
    """Index just past the `}` that closes a `${` whose body starts at `i`, or -1."""
    depth = 1
    n = len(text)
    while i < n:
        m = _EXPR_EVENT.search(text, i)
        if m is None:
            return -1
        c, i = m.group(), m.end()
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        elif c == "`":
            nested = _template(text, m.start())
            if nested is None:
                return -1
            i = nested[0]
        elif c == "/":
            if text.startswith("//", m.start()):
                newline = text.find("\n", i)
                i = n if newline < 0 else newline
            elif text.startswith("/*", m.start()):
                close = text.find("*/", i)
                if close < 0:
                    return -1
                i = close + 2
            elif _regex_allowed(text, m.start()):  # `${s.replace(/\//g, "-")}`: the escaped slashes are not a comment
                regex = _REGEX.match(text, m.start())
                if regex:
                    i = regex.end()
        else:
            s = _STRING.match(text, m.start())
            if s:
                i = s.end()
    return -1


def _note(out: Scan, value: str) -> None:
    """Remember a string literal that names a file, e.g. `new URL("./worker.ts", import.meta.url)`."""
    if 0 < len(value) <= 200 and _PATHLIKE.fullmatch(value) and (value.startswith(("./", "../", "<rootDir>/")) or _CODE_EXT.search(value)):
        out.strings.add(value)


def scan(text: str) -> Scan | None:
    """What `text` imports, or None when it cannot be read as JavaScript (unterminated comment or template)."""
    try:
        return _scan(text)
    except RecursionError:
        return None


def _scan(text: str) -> Scan | None:
    out = Scan(hashbang=text.startswith("#!"), main_guard=bool(_MAIN.search(text)))
    newline = text.find("\n")
    pos = (len(text) if newline < 0 else newline + 1) if out.hashbang else 0
    spec_at = -1  # where the string or template that is the argument of `import(` / `require(` starts
    while True:
        m = _EVENT.search(text, pos)
        if m is None:
            return out
        kind, start, pos = m.lastgroup, m.start(), m.end()
        if kind == "line":
            ref = _TRIPLE.match(m.group())
            if ref:
                out.specs.append(ref.group(1) if ref.group(1).startswith(".") else "./" + ref.group(1))
        elif kind == "str":
            value = m.group()[1:-1]
            if start != spec_at:
                _note(out, value)
                continue
            more = _CONCAT.match(text, pos)
            if more:  # "./pages/" + name [+ ".tsx"]
                tail = more.group(2) or ""
                out.dynamic.append(Dynamic(value, tail, "/" in tail))
            else:
                out.specs.append(value)
        elif kind == "tpl":
            parsed = _template(text, start)
            if parsed is None:
                return None
            pos, pieces = parsed
            if start == spec_at:
                if len(pieces) == 1:
                    out.specs.append(pieces[0])
                else:
                    out.dynamic.append(Dynamic(pieces[0], pieces[-1], "/" in "".join(pieces[1:])))
        elif kind == "slash":
            if text.startswith("/*", start):
                return None  # a terminated block comment would have matched above
            if _regex_allowed(text, start):
                regex = _REGEX.match(text, start)
                if regex:
                    pos = regex.end()
        elif kind == "kw":
            word = m.group()
            if word == "import":
                i = _skip_ws(text, pos)
                nxt = text[i : i + 1]
                if nxt == "(":
                    spec_at, pos = _skip_ws(text, i + 1), i + 1
                elif nxt in ("'", '"'):
                    spec_at = i
                elif nxt == ".":
                    glob = _META_GLOB.match(text, pos)
                    if glob:
                        out.globs.extend(_LITERAL.findall(glob.group("arg")))
                        pos = glob.end()
                else:
                    static = _IMPORT_FROM.match(text, pos)
                    if static:
                        out.specs.append(static.group(2))
                        pos = static.end()
            elif word == "export":
                static = _EXPORT_FROM.match(text, pos)
                if static:
                    out.specs.append(static.group(2))
                    pos = static.end()
            else:
                call = _REQUIRE.match(text, pos)
                if call and call.group("member") == "context":
                    ctx = _CONTEXT.match(text, call.end())
                    if ctx:
                        out.contexts.append((ctx.group(2), ctx.group(3) != "false", ctx.group(4)))
                        pos = ctx.end()
                elif call:
                    pos = call.end()
                    spec_at = _skip_ws(text, pos)
