"""Find citation keys in Markdown (Pandoc syntax) and LaTeX (``\\cite`` family).

Positions are UTF-16 code-unit offsets, the same unit the desktop document
editor uses. Markdown follows what Pandoc itself parses (cross-checked with
``pandoc -t json`` Cite nodes):

* ``@key`` is a citation unless the ``@`` follows a letter or digit (so
  ``jane@doe.com`` and ``見@a`` are not), is escaped (``\\@``), or sits in
  code, an HTML comment or tag, an autolink ``<...>``, inline math, YAML front
  matter, a link or image destination or title, a reference definition's
  target, or a ``{...}`` attribute block after a link or span;
* ``(@label)`` with ASCII parentheses is an example-list reference;
* a key starts with a letter, digit or ``_``; it may contain the internal
  punctuation ``:.#$%&-+?<>~/`` only when a letter, digit or ``_`` follows,
  so trailing punctuation is never part of the key; ``@{...}`` keys may
  contain anything except ``}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Format = Literal["markdown", "latex"]

_INTERNAL_PUNCT = set(":.#$%&-+?<>~/")
LATEX_CITE_COMMANDS = (
    "cite", "citep", "citet", "parencite", "textcite", "autocite", "nocite",
    "Cite", "Citep", "Citet", "Parencite", "Textcite", "Autocite",
    "citealp", "citealt", "citeauthor", "citeyear", "footcite", "smartcite",
    "supercite",
)
_LATEX_CITE = re.compile(
    r"\\(" + "|".join(sorted(LATEX_CITE_COMMANDS, key=len, reverse=True)) + r")\*?"
    r"(?![A-Za-z])\s*(?:\[[^\]]*\]\s*){0,2}\{([^{}]*)\}"
)
_LATEX_VERBATIM = re.compile(
    r"\\begin\{(verbatim\*?|lstlisting|minted|comment)\}.*?\\end\{\1\}", re.S
)


@dataclass(frozen=True)
class CitationUse:
    key: str
    start: int  # UTF-16 offset of the citation token (``@`` or the LaTeX key)
    end: int  # UTF-16 offset just after it
    line: int  # 1-based
    group: int  # uses in the same bracket/``\\cite`` share a group

    def to_dict(self) -> dict:
        return {"key": self.key, "start": self.start, "end": self.end, "line": self.line, "group": self.group}


def format_for_path(path: str) -> Format | None:
    lowered = path.casefold()
    if lowered.endswith((".md", ".markdown")):
        return "markdown"
    if lowered.endswith(".tex"):
        return "latex"
    return None


def find_citations(text: str, fmt: Format) -> list[CitationUse]:
    """All citation uses in document order."""
    if fmt == "markdown":
        raw = _markdown_uses(text)
    elif fmt == "latex":
        raw = _latex_uses(text)
    else:
        raise ValueError(f"unsupported citation format: {fmt!r}")
    return _with_positions(text, raw)


def keys_in(text: str, fmt: Format) -> list[str]:
    return [use.key for use in find_citations(text, fmt)]


# --- shared -----------------------------------------------------------------


def _with_positions(text: str, raw: list[tuple[str, int, int, int]]) -> list[CitationUse]:
    """Convert (key, start, end, group) in code points to UTF-16 offsets."""
    if not raw:
        return []
    uses = []
    targets = sorted({index for _key, start, end, _group in raw for index in (start, end)})
    utf16: dict[int, int] = {}
    lines: dict[int, int] = {}
    offset = 0
    line = 1
    cursor = 0
    for target in targets:
        for ch in text[cursor:target]:
            offset += 2 if ord(ch) > 0xFFFF else 1
            if ch == "\n":
                line += 1
        cursor = target
        utf16[target] = offset
        lines[target] = line
    for key, start, end, group in raw:
        uses.append(CitationUse(key, utf16[start], utf16[end], lines[start], group))
    return uses


def _blank(chars: list[str], start: int, end: int) -> None:
    for index in range(start, min(end, len(chars))):
        if chars[index] != "\n":
            chars[index] = " "


# --- Markdown -------------------------------------------------------------------


def _mask_markdown(text: str) -> str:
    """Replace regions Pandoc never reads citations from with spaces."""
    chars = list(text)
    # YAML front matter at the very start.
    front = re.match(r"---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?:\n|$)", text, re.S)
    if front:
        _blank(chars, 0, front.end())
    # Fenced code blocks.
    fence: tuple[str, int] | None = None
    fence_start = 0
    position = 0
    for line in text.splitlines(keepends=True):
        match = re.match(r" {0,3}(`{3,}|~{3,})", line)
        if fence is None:
            if match:
                fence = (match.group(1)[0], len(match.group(1)))
                fence_start = position
        elif match and match.group(1)[0] == fence[0] and len(match.group(1)) >= fence[1] \
                and not line[match.end():].strip():
            _blank(chars, fence_start, position + len(line))
            fence = None
        position += len(line)
    if fence is not None:
        _blank(chars, fence_start, len(text))
    _mask_indented_code(text, chars)
    masked = "".join(chars)
    # HTML comments.
    for match in re.finditer(r"<!--.*?-->", masked, re.S):
        _blank(chars, match.start(), match.end())
    masked = "".join(chars)
    # Inline code spans (matching backtick runs).
    index = 0
    while index < len(masked):
        if masked[index] == "`" and (index == 0 or masked[index - 1] != "\\"):
            run = re.match(r"`+", masked[index:]).group(0)
            close = re.compile(r"(?<!`)" + run + r"(?!`)")
            found = close.search(masked, index + len(run))
            if found:
                _blank(chars, index, found.end())
                index = found.end()
                continue
            index += len(run)
            continue
        index += 1
    masked = "".join(chars)
    # Autolinks and inline math.
    for pattern in (
        r"<[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*>",
        r"<[^\s<>@]+@[^\s<>]+>",
        r"\$\$.+?\$\$",
        r"(?<![\\$])\$(?=\S)[^$\n]*?(?<=\S)\$(?!\d)",
    ):
        for match in re.finditer(pattern, masked, re.S):
            _blank(chars, match.start(), match.end())
        masked = "".join(chars)
    # Raw HTML tags: attributes are never read (element content still is). A
    # "<" glued to a word character is inside a citation key (``@a<b>c``).
    for match in re.finditer(r"(?<!\w)</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>", masked):
        _blank(chars, match.start(), match.end())
    masked = "".join(chars)
    _mask_link_targets(masked, chars)
    return "".join(chars)


# A footnote ("[^n]: ...") or a citation-shaped label ("[@k]: ...") is not a
# reference definition in Pandoc; its text is still read for citations.
_REFERENCE_DEFINITION = re.compile(
    r"^ {0,3}\[(?![\^@]|-@)[^\]\n]+\]:[ \t]*(?:<[^<>\n]*>|\S+)"
    r"(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^()\n]*\)))?[ \t]*$",
    re.M,
)


def _link_destination_end(text: str, start: int) -> int | None:
    """Index of the ``)`` closing an inline link destination opened at ``start``.

    ``start`` points just after ``(``. Accepts ``<...>`` or a destination with
    balanced parentheses, then an optional quoted or parenthesized title;
    returns None when Pandoc would not read this as a link.
    """
    index = start
    length = len(text)
    while index < length and text[index] in " \t\n":
        index += 1
    if index < length and text[index] == "<":
        close = text.find(">", index)
        if close < 0 or "\n" in text[index:close]:
            return None
        index = close + 1
    else:
        depth = 0
        while index < length and not text[index].isspace():
            char = text[index]
            if char == "\\" and index + 1 < length:
                index += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            index += 1
    while index < length and text[index] in " \t\n":
        index += 1
    if index < length and text[index] in "\"'(":
        closer = ")" if text[index] == "(" else text[index]
        close = text.find(closer, index + 1)
        if close < 0:
            return None
        index = close + 1
        while index < length and text[index] in " \t\n":
            index += 1
    if index < length and text[index] == ")":
        return index
    return None


def _mask_link_targets(masked: str, chars: list[str]) -> None:
    """Blank link/image destinations and titles, reference-definition targets,
    and attribute blocks after links or bracketed spans.

    Link text (``[see @a](url)``) stays visible: Pandoc reads citations there.
    """
    for match in _REFERENCE_DEFINITION.finditer(masked):
        colon = masked.index("]:", match.start()) + 2
        _blank(chars, colon, match.end())
    for _open, close in _bracket_groups(masked):
        after = close + 1
        if after < len(masked) and masked[after] == "(":
            end = _link_destination_end(masked, after + 1)
            if end is None:
                continue
            _blank(chars, after, end + 1)
            after = end + 1
        if after < len(masked) and masked[after] == "{":
            brace = masked.find("}", after)
            if brace > after and "\n" not in masked[after:brace]:
                _blank(chars, after, brace + 1)


_LIST_MARKER = re.compile(r" {0,3}(?:[-*+]|\d{1,9}[.)]|\(@[\w-]*\))[ \t]")


def _mask_indented_code(text: str, chars: list[str]) -> None:
    """Blank indented code blocks (4+ columns after a blank line, not in a list)."""
    position = 0
    previous_blank = True
    in_code = False
    in_list = False
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\n")
        blank = not body.strip()
        indented = body.startswith(("    ", "\t"))
        if blank:
            previous_blank = True
        else:
            if indented and (in_code or (previous_blank and not in_list)):
                in_code = True
                _blank(chars, position, position + len(line))
            else:
                in_code = False
                if _LIST_MARKER.match(body):
                    in_list = True
                elif not indented and previous_blank:
                    in_list = False
            previous_blank = False
        position += len(line)


def _is_key_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _scan_key(text: str, start: int) -> int:
    """Return the end index of a bare key starting at ``start`` (exclusive)."""
    end = start
    length = len(text)
    while end < length:
        ch = text[end]
        if _is_key_char(ch):
            end += 1
        elif ch in _INTERNAL_PUNCT and end + 1 < length and _is_key_char(text[end + 1]):
            end += 1
        else:
            break
    return end


def _bracket_groups(masked: str) -> list[tuple[int, int]]:
    """Spans of ``[...]`` (innermost brackets) that may hold citation groups."""
    spans = []
    stack: list[int] = []
    for index, ch in enumerate(masked):
        if ch == "[" and (index == 0 or masked[index - 1] != "\\"):
            stack.append(index)
        elif ch == "]" and stack and (index == 0 or masked[index - 1] != "\\"):
            spans.append((stack.pop(), index))
    return spans


def _markdown_uses(text: str) -> list[tuple[str, int, int, int]]:
    masked = _mask_markdown(text)
    found: list[tuple[str, int, int]] = []
    index = masked.find("@")
    while index >= 0:
        prev = masked[index - 1] if index > 0 else ""
        if prev.isalnum() or prev == "\\":
            index = masked.find("@", index + 1)
            continue
        nxt = masked[index + 1] if index + 1 < len(masked) else ""
        if nxt == "{":
            close = masked.find("}", index + 2)
            if close > index + 2 and not re.search(r"\s", masked[index + 2:close]):
                found.append((masked[index + 2:close], index, close + 1))
                index = masked.find("@", close + 1)
                continue
        elif nxt and _is_key_char(nxt):
            end = _scan_key(masked, index + 1)
            key = masked[index + 1:end]
            # "(@label)" opening a line is an example-list marker.
            line_start = masked.rfind("\n", 0, index) + 1
            example = (
                prev == "("
                and not masked[line_start:index - 1].strip(" ")
                and index - 1 - line_start <= 3
                and end < len(masked)
                and masked[end] == ")"
                and (end + 1 >= len(masked) or masked[end + 1] in " \t\n")
                and re.fullmatch(r"[\w-]+", key)
            )
            if not example:
                found.append((key, index, end))
            index = masked.find("@", end)
            continue
        index = masked.find("@", index + 1)
    found = _footnote_order(masked, found)
    groups = _bracket_groups(masked)
    result = []
    group_of_span: dict[tuple[int, int], int] = {}
    next_group = 0
    for key, start, end in found:
        span = next((s for s in groups if s[0] < start and end <= s[1]), None)
        if span is not None and _is_citation_bracket(masked[span[0] + 1:span[1]]):
            if span not in group_of_span:
                group_of_span[span] = next_group
                next_group += 1
            group = group_of_span[span]
        else:
            group = next_group
            next_group += 1
        result.append((key, start, end, group))
    return result


_FOOTNOTE_DEF = re.compile(r" {0,3}\[\^([^\]\s]+)\]:")


def _footnote_order(masked: str, found: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """Order uses as Pandoc does: a footnote's citations sit at its reference.

    Uses inside a footnote definition that is never referenced are dropped,
    because Pandoc drops the definition.
    """
    definitions: list[tuple[str, int, int]] = []  # (label, start, end)
    position = 0
    current: list | None = None
    pending_blank = False
    for line in masked.splitlines(keepends=True):
        body = line.rstrip("\n")
        match = _FOOTNOTE_DEF.match(body)
        if match:
            current = [match.group(1), position, position + len(line)]
            definitions.append(current)
            pending_blank = False
        elif current is not None:
            if not body.strip():
                pending_blank = True
            elif body.startswith(("    ", "\t")) or not pending_blank:
                current[2] = position + len(line)
                pending_blank = False
            else:
                current = None
        position += len(line)
    if not definitions:
        return found
    inside = [(label, start, end) for label, start, end in definitions]
    references: dict[str, int] = {}
    for match in re.finditer(r"\[\^([^\]\s]+)\](?!:)", masked):
        if any(start <= match.start() < end for _label, start, end in inside):
            continue
        references.setdefault(match.group(1), match.start())
    ordered = []
    for key, start, end in found:
        owner = next((d for d in inside if d[1] <= start < d[2]), None)
        if owner is None:
            ordered.append(((start, 0), (key, start, end)))
        elif owner[0] in references:
            ordered.append(((references[owner[0]], 1, start), (key, start, end)))
    ordered.sort(key=lambda pair: pair[0])
    return [use for _sort, use in ordered]


def _is_citation_bracket(inner: str) -> bool:
    items = inner.split(";")
    return all(len(re.findall(r"(?:^|[^\w\\])-?@", item)) == 1 for item in items)


# --- LaTeX ------------------------------------------------------------------------


def _mask_latex(text: str) -> str:
    chars = list(text)
    for match in _LATEX_VERBATIM.finditer(text):
        _blank(chars, match.start(), match.end())
    masked = "".join(chars)
    for match in re.finditer(r"(?<!\\)%[^\n]*", masked):
        _blank(chars, match.start(), match.end())
    return "".join(chars)


def _latex_uses(text: str) -> list[tuple[str, int, int, int]]:
    masked = _mask_latex(text)
    result = []
    for group, match in enumerate(_LATEX_CITE.finditer(masked)):
        body_start = match.start(2)
        for part in re.finditer(r"[^,]+", match.group(2)):
            key = part.group(0).strip()
            if not key or key == "*":
                continue
            start = body_start + part.start() + (len(part.group(0)) - len(part.group(0).lstrip()))
            result.append((key, start, start + len(key), group))
    return result
