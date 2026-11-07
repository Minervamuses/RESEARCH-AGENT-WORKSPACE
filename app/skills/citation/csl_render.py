"""Render and export Markdown citations with Pandoc citeproc (the only engine).

Preview and export use the same Pandoc run, so a preview matches the export.
Pandoc is always a direct subprocess (no shell), the document arrives on
stdin, every call has a timeout, and readers run with ``--sandbox`` so only
the style and bibliography named on the command line are read.

Exported ``.docx`` keeps local images: the citeproc pass runs sandboxed into a
JSON AST, remote images are replaced by links (never fetched), and only then
does the docx writer run with the document's own folder as resource path.

Nothing here ever writes the source document.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from skills.citation import library as lib
from skills.citation.citekeys import find_citations

STYLES_DIR = Path(__file__).resolve().parent / "styles"
STYLES_MANIFEST = STYLES_DIR / "styles.json"
DEFAULT_TIMEOUT_SECONDS = 60
# Plain Markdown: citations as text, no Pandoc div/span wrappers, curly quotes kept.
MARKDOWN_EXPORT_FORMAT = "markdown-citations-smart"
_REMOTE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class RenderError(RuntimeError):
    """``code``: pandoc_unavailable, pandoc_failed, pandoc_timeout,
    style_unknown, or a library_* code from the bibliography."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# --- styles -------------------------------------------------------------------


def list_styles() -> list[dict]:
    """Bundled styles: id, name, kind (author-date | author | numeric), origin."""
    manifest = json.loads(STYLES_MANIFEST.read_text(encoding="utf-8"))
    return [
        {key: style[key] for key in ("id", "name", "kind", "origin")}
        for style in manifest["styles"]
    ]


def style_path(style_id: str) -> Path:
    return STYLES_DIR / _style_entry(style_id)["file"]


# --- pandoc -------------------------------------------------------------------------


def find_pandoc() -> str | None:
    """Pandoc from the running Conda environment first, then PATH."""
    beside = Path(sys.executable).parent / "pandoc"
    if beside.is_file() and os.access(beside, os.X_OK):
        return str(beside)
    return shutil.which("pandoc")


def _run(args: list[str], stdin: bytes, *, timeout: float) -> bytes:
    pandoc = find_pandoc()
    if pandoc is None:
        raise RenderError("pandoc_unavailable", "Pandoc is not installed in this environment.")
    try:
        completed = subprocess.run(
            [pandoc, *args], input=stdin, capture_output=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError("pandoc_timeout", f"Pandoc did not finish within {timeout:g} s.") from exc
    except OSError as exc:
        raise RenderError("pandoc_unavailable", f"Pandoc could not start: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()[-500:]
        raise RenderError("pandoc_failed", f"Pandoc failed: {detail}")
    return completed.stdout


_CJK_LANGUAGE = re.compile(r"(?:zh|chi|zho|ja|jpn)(?:$|[-_])", re.I)
_KANA = re.compile(r"[\u3040-\u30ff]")
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _style_entry(style_id: str) -> dict:
    manifest = json.loads(STYLES_MANIFEST.read_text(encoding="utf-8"))
    for style in manifest["styles"]:
        if style["id"] == style_id:
            return style
    raise RenderError("style_unknown", f"unknown citation style: {style_id!r}")


def cjk_language(item: dict) -> str | None:
    """"zh"/"ja" when an entry is Chinese or Japanese, else None.

    An explicit ``language`` decides (``en``, ``de`` … are not CJK); without
    one, kana means Japanese and Han characters mean Chinese, looking at the
    title and the names (the rule bime_word uses).
    """
    language = item.get("language")
    if isinstance(language, str) and language.strip():
        if not _CJK_LANGUAGE.match(language.strip()):
            return None
        return "ja" if language.strip().casefold().startswith(("ja", "jpn")) else "zh"
    sample = str(item.get("title", ""))
    for role in ("author", "editor"):
        for name in item.get(role) or []:
            if isinstance(name, dict):
                sample += "".join(str(name.get(part, "")) for part in ("family", "given", "literal"))
    if _KANA.search(sample):
        return "ja"
    return "zh" if _HAN.search(sample) else None


def language_branch_items(items: list[dict]) -> list[dict]:
    """Copy of ``items`` for a style that switches to its CJK branch on ``language``.

    Standard CSL can only test whether ``language`` is present, not its
    value, so the copy keeps ``language`` exactly on Chinese/Japanese entries
    (inferred when missing) and drops it everywhere else. The value is the
    canonical ``zh`` or ``ja``: the style sorts on it (descending: Chinese,
    then Japanese), so ``chi``/``jpn`` or ``zh-TW`` next to ``zh`` must not
    reorder or split the groups. The user's file is never changed.
    """
    out = []
    for item in items:
        copy = {key: value for key, value in item.items() if key != "language"}
        language = cjk_language(item)
        if language is not None:
            copy["language"] = language
        out.append(copy)
    return out


# Characters Pandoc leaves alone and collates like ignorable punctuation (so
# "D'Arcy" sorts as "DArcy", as bime_word does); the first one absent from the
# bibliography and the document stands in for a straight apostrophe.
_APOSTROPHE_PLACEHOLDERS = ("\u2035", "\u055a", "\u05f3", "\u02b9")
_VERBATIM_FIELDS = frozenset({"id", "type", "language", "URL", "DOI", "ISBN", "ISSN", "PMID", "PMCID"})


def _map_strings(value, convert):
    if isinstance(value, str):
        return convert(value)
    if isinstance(value, list):
        return [_map_strings(item, convert) for item in value]
    if isinstance(value, dict):
        return {key: _map_strings(item, convert) for key, item in value.items()}
    return value


def protect_apostrophes(items: list[dict], document_text: str) -> tuple[list[dict], str | None]:
    """Hide straight apostrophes from Pandoc, which always prints them as ’.

    Returns the copy and the placeholder to turn back into ``'`` after
    rendering (None when no free placeholder exists; then nothing changes).
    Identifier fields are left verbatim; typographic ’ in the data stays ’.
    """
    used = json.dumps(items, ensure_ascii=False) + document_text
    placeholder = next((char for char in _APOSTROPHE_PLACEHOLDERS if char not in used), None)
    if placeholder is None:
        return items, None
    out = [
        {key: value if key in _VERBATIM_FIELDS else _map_strings(value, lambda text: text.replace("'", placeholder))
         for key, value in item.items()}
        for item in items
    ]
    return out, placeholder


_NAME_ROLES = ("author", "editor", "translator", "collection-editor", "container-author")
_NICKNAME = re.compile(r"\s*\([^)]*\)")


def _given_for_appendix17(given: str) -> str:
    """bime_word's given-name rules: drop "(Nickname)"; initialize hyphenated
    parts when one starts lower-case ("Wen-tau" -> "W.-t."), which CSL drops."""
    tokens = []
    for token in _NICKNAME.sub(" ", given).split():
        parts = [part for part in token.split("-") if part]
        if len(parts) > 1 and any(part[0].islower() for part in parts[1:]):
            token = "-".join(part[0] + "." for part in parts)
        tokens.append(token)
    return " ".join(tokens)


def normalize_given_names(items: list[dict]) -> list[dict]:
    """Copy with Appendix 17 given-name rules applied to non-CJK names."""
    out = []
    for item in items:
        copy = dict(item)
        if cjk_language(item) is None:
            for role in _NAME_ROLES:
                names = item.get(role)
                if not isinstance(names, list):
                    continue
                fixed = []
                for name in names:
                    if isinstance(name, dict) and isinstance(name.get("given"), str):
                        name = dict(name)
                        given = _given_for_appendix17(name["given"])
                        if given:
                            name["given"] = given
                        else:
                            name.pop("given")
                    fixed.append(name)
                copy[role] = fixed
        out.append(copy)
    return out


# A source-truncated author list ends in a literal like "et al."; the
# Appendix 17 style prints such lists without "and" and ends them with et al.
_ET_AL_LITERALS = frozenset({"et al.", "et al", "others", "等", "等人"})
TRUNCATION_FLAG = "references"  # the CSL variable bime-appendix17.csl tests


def mark_truncated_author_lists(items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        copy = {key: value for key, value in item.items() if key != TRUNCATION_FLAG}
        names = item.get("author")
        if isinstance(names, list) and len(names) > 1 and isinstance(names[-1], dict) \
                and str(names[-1].get("literal", "")).strip().casefold() in _ET_AL_LITERALS:
            copy["author"] = names[:-1]
            copy[TRUNCATION_FLAG] = "truncated-author-list"
        out.append(copy)
    return out


def prepare_render_items(items: list[dict], steps: list[str], document_text: str) -> tuple[list[dict], dict[str, str]]:
    """Apply a style's ``preprocess`` steps (styles.json) to a copy of the items.

    Returns the copy and the replacements to apply to Pandoc's output.
    """
    restore: dict[str, str] = {}
    if "cjk-language" in steps:
        items = language_branch_items(items)
    if "given-names" in steps:
        items = normalize_given_names(items)
    if "truncated-authors" in steps:
        items = mark_truncated_author_lists(items)
    if "straight-apostrophes" in steps:
        items, placeholder = protect_apostrophes(items, document_text)
        if placeholder is not None:
            restore[placeholder] = "'"
    return items, restore


def _citeproc_ast(text: str, library_path: Path, style_id: str, *, timeout: float) -> dict:
    library = lib.load(Path(library_path))  # validates; raises LibraryError
    style = _style_entry(style_id)
    args = ["--sandbox", "-f", "markdown", "-t", "json", "--citeproc", "--csl", str(STYLES_DIR / style["file"])]
    if not library.exists:
        return json.loads(_run(args, text.encode("utf-8"), timeout=timeout))
    steps = style.get("preprocess") or []
    if not steps:
        args += ["--bibliography", str(library_path)]
        return json.loads(_run(args, text.encode("utf-8"), timeout=timeout))
    items, restore = prepare_render_items(library.items, steps, text)
    with tempfile.TemporaryDirectory(prefix="citation-render-") as folder:
        copy = Path(folder) / "bibliography.json"
        copy.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        args += ["--bibliography", str(copy)]
        ast = json.loads(_run(args, text.encode("utf-8"), timeout=timeout))
    for placeholder, original in restore.items():
        ast = _map_strings(ast, lambda value: value.replace(placeholder, original))
    return ast


def _library_or_error(library_path: Path) -> lib.Library:
    try:
        return lib.load(Path(library_path))
    except lib.LibraryError as exc:
        raise RenderError(exc.code, str(exc)) from exc


# --- AST helpers ----------------------------------------------------------------


def _segments(inlines: list, style: dict | None = None) -> list[dict]:
    """Pandoc inlines -> [{text, italic?, bold?, url?}] (adjacent runs merged)."""
    style = style or {}
    out: list[dict] = []

    def add(text: str, extra: dict | None = None) -> None:
        if not text:
            return
        segment = {"text": text, **style, **(extra or {})}
        if out and {k: v for k, v in out[-1].items() if k != "text"} == {k: v for k, v in segment.items() if k != "text"}:
            out[-1]["text"] += text
        else:
            out.append(segment)

    for node in inlines:
        kind = node.get("t")
        content = node.get("c")
        if kind == "Str":
            add(content)
        elif kind in {"Space", "SoftBreak", "LineBreak"}:
            add(" ")
        elif kind == "Emph":
            for seg in _segments(content, {**style, "italic": True}):
                add(seg.pop("text"), seg)
        elif kind == "Strong":
            for seg in _segments(content, {**style, "bold": True}):
                add(seg.pop("text"), seg)
        elif kind == "Quoted":
            left, right = ("“", "”") if content[0]["t"] == "DoubleQuote" else ("‘", "’")
            add(left)
            for seg in _segments(content[1], style):
                add(seg.pop("text"), seg)
            add(right)
        elif kind == "Link":
            url = content[2][0]
            for seg in _segments(content[1], {**style, "url": url}):
                add(seg.pop("text"), seg)
        elif kind == "Code":
            add(content[1])
        elif kind in {"SmallCaps", "Superscript", "Subscript", "Underline", "Strikeout"}:
            for seg in _segments(content, style):
                add(seg.pop("text"), seg)
        elif kind in {"Span", "Cite"}:
            for seg in _segments(content[1], style):
                add(seg.pop("text"), seg)
        elif kind == "Math":
            add(content[1])
        # RawInline, Note, Image: not part of citation text
    return out


def _plain(segments: list[dict]) -> str:
    return "".join(segment["text"] for segment in segments).strip()


def _collect_cites(node, out: list) -> None:
    if isinstance(node, dict):
        if node.get("t") == "Cite":
            out.append(node["c"])
            return
        for value in node.values():
            _collect_cites(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_cites(value, out)


def _refs_entries(blocks: list) -> list[tuple[str, list]]:
    for block in blocks:
        if block.get("t") == "Div" and block["c"][0][0] == "refs":
            entries = []
            for entry in block["c"][1]:
                if entry.get("t") != "Div":
                    continue
                key = entry["c"][0][0].removeprefix("ref-")
                inlines = []
                for inner in entry["c"][1]:
                    if inner.get("t") in {"Para", "Plain"}:
                        if inlines:
                            inlines.append({"t": "Space"})
                        inlines.extend(inner["c"])
                entries.append((key, inlines))
            return entries
    return []


# --- public API ------------------------------------------------------------------


@dataclass(frozen=True)
class Rendered:
    style_id: str
    citations: list[dict]  # {index, keys, start, end, text, segments}
    bibliography: list[dict]  # {key, text, segments}
    missing: list[str]

    def to_dict(self) -> dict:
        return {
            "styleId": self.style_id,
            "citations": self.citations,
            "bibliography": self.bibliography,
            "missing": self.missing,
        }


def render(text: str, library_path: Path, style_id: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Rendered:
    """Render every citation of a Markdown document and its bibliography."""
    library = _library_or_error(library_path)
    try:
        ast = _citeproc_ast(text, Path(library_path), style_id, timeout=timeout)
    except lib.LibraryError as exc:
        raise RenderError(exc.code, str(exc)) from exc
    cites: list = []
    _collect_cites(ast["blocks"], cites)
    groups = _source_groups(text)
    known = set(library.keys())
    citations = []
    cursor = 0
    for index, (items, inlines) in enumerate(cites):
        keys = [item["citationId"] for item in items]
        position = None
        for probe in range(cursor, len(groups)):
            if groups[probe][0] == keys:
                position = groups[probe][1:]
                cursor = probe + 1
                break
        segments = _segments(inlines)
        citations.append({
            "index": index,
            "keys": keys,
            "start": position[0] if position else None,
            "end": position[1] if position else None,
            "text": _plain(segments),
            "segments": segments,
        })
    bibliography = []
    for key, inlines in _refs_entries(ast["blocks"]):
        segments = _segments(inlines)
        bibliography.append({"key": key, "text": _plain(segments), "segments": segments})
    order = list(dict.fromkeys(key for keys, *_ in groups for key in keys))
    missing = [key for key in order if key not in known]
    return Rendered(style_id, citations, bibliography, missing)


def _source_groups(text: str) -> list[tuple[list[str], int, int]]:
    """Citation groups in Pandoc order: (keys, utf16 start, utf16 end)."""
    groups: dict[int, list] = {}
    for use in find_citations(text, "markdown"):
        entry = groups.setdefault(use.group, [[], use.start, use.end])
        entry[0].append(use.key)
        entry[1] = min(entry[1], use.start)
        entry[2] = max(entry[2], use.end)
    return [tuple(value) for value in groups.values()]


def export_markdown(text: str, library_path: Path, style_id: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Markdown with citations replaced by text and the bibliography appended."""
    _library_or_error(library_path)
    ast = _unwrap(_citeproc_ast(text, Path(library_path), style_id, timeout=timeout))
    out = _run(
        ["--sandbox", "-f", "json", "-t", MARKDOWN_EXPORT_FORMAT, "--wrap=preserve"],
        json.dumps(ast).encode("utf-8"), timeout=timeout,
    )
    return out.decode("utf-8")


def _unwrap(node):
    """Drop Div/Span wrappers (keep their content) so Markdown stays plain."""
    if isinstance(node, list):
        out = []
        for item in node:
            if isinstance(item, dict) and item.get("t") in {"Div", "Span"}:
                out.extend(_unwrap(item["c"][1]))
            else:
                out.append(_unwrap(item))
        return out
    if isinstance(node, dict):
        return {key: _unwrap(value) for key, value in node.items()}
    return node


def _unlink_remote_images(node):
    """Replace remote images with links so no writer ever fetches them."""
    if isinstance(node, list):
        return [_unlink_remote_images(item) for item in node]
    if isinstance(node, dict):
        if node.get("t") == "Image":
            attr, alt, (url, title) = node["c"]
            if _REMOTE.match(url):
                return {"t": "Link", "c": [attr, alt or [{"t": "Str", "c": url}], [url, title]]}
        return {key: _unlink_remote_images(value) for key, value in node.items()}
    return node


def export_docx(
    text: str,
    library_path: Path,
    style_id: str,
    *,
    resource_dir: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """A .docx with formatted citations and bibliography.

    Remote images become links and are never fetched. Local images are
    embedded only when ``resource_dir`` (the document's folder) is given;
    otherwise the writer also runs sandboxed and leaves them out.
    """
    _library_or_error(library_path)
    ast = _unlink_remote_images(_citeproc_ast(text, Path(library_path), style_id, timeout=timeout))
    args = ["-f", "json", "-t", "docx", "-o", "-"]
    if resource_dir is None:
        args.insert(0, "--sandbox")
    else:
        args += ["--resource-path", str(Path(resource_dir).resolve())]
    return _run(args, json.dumps(ast).encode("utf-8"), timeout=timeout)


EXPORT_SUFFIXES = {"docx": ".docx", "markdown": ".md"}


def export_target(fmt: str, *, document_path: Path, style_id: str) -> Path:
    """Where an export goes (A5): ``<document stem>.<style>.docx|md`` beside the document."""
    document_path = Path(document_path)
    return document_path.parent / f"{document_path.stem}.{style_id}{EXPORT_SUFFIXES[fmt]}"
