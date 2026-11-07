"""Project bibliography: one CSL-JSON array file with stable keys.

The file is the user's: existing entries, keys and layout are never changed.
``load`` accepts only an array of objects with unique string ``id`` values and
detects which ``json.dumps`` layout reproduces the file byte for byte; a file
no known layout reproduces can be read but is never rewritten. ``merge`` reuses an existing
entry with the same DOI (case-insensitive) or arXiv ID, otherwise appends one
new entry at the end. ``write_atomic`` re-reads the file before replacing it
and refuses when it changed since ``load``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from agent.paths import fsync_directory
from skills.citation.doi import canonicalize_doi

LIBRARY_MALFORMED = "library_malformed"
LIBRARY_FORMAT_UNSUPPORTED = "library_format_unsupported"
LIBRARY_CONFLICT = "library_conflict"
LIBRARY_WRITE_FAILED = "library_write_failed"

DEFAULT_LIBRARY_FILENAME = "references.json"
LAYOUTS: tuple[int | str, ...] = (1, 2, 4, "\t")
NEW_FILE_LAYOUT: int | str = 1
NEW_FILE_MODE = 0o644

TITLE_STOPWORDS = frozenset({
    "a", "an", "the", "of", "on", "in", "for", "and", "or", "to", "with",
    "from", "by", "at", "as", "is", "are", "be", "into", "onto", "via",
    "toward", "towards", "using", "its", "it", "this", "that", "do", "does",
    "what", "how", "why", "when", "can", "we", "our", "not", "vs",
})


class LibraryError(RuntimeError):
    """A bibliography operation failed; ``code`` is one of the LIBRARY_* codes."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Library:
    """A loaded bibliography plus what is needed to rewrite it safely."""

    path: Path
    items: list[dict]
    # json.dumps indent that reproduces the file; None = unknown (read-only).
    layout: int | str | None = NEW_FILE_LAYOUT
    fingerprint: str | None = None  # sha256 of the bytes read; None = no file

    @property
    def exists(self) -> bool:
        return self.fingerprint is not None

    def keys(self) -> list[str]:
        return [item["id"] for item in self.items]


@dataclass(frozen=True)
class MergeResult:
    status: str  # "added" | "existing"
    key: str
    item: dict
    library: Library = field(compare=False)


def fingerprint(path: Path) -> str | None:
    """sha256 of the file bytes, or None when the file does not exist."""
    try:
        data = Path(path).read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LibraryError(LIBRARY_MALFORMED, f"cannot read {path}: {exc}") from exc
    return hashlib.sha256(data).hexdigest()


def serialize(items: list[dict], layout: int | str) -> str:
    return json.dumps(items, ensure_ascii=False, indent=layout) + "\n"


def parse_items(text: str, *, source: str = "bibliography") -> list[dict]:
    """Validate the CSL-JSON shape this module accepts."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LibraryError(LIBRARY_MALFORMED, f"{source} is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise LibraryError(LIBRARY_MALFORMED, f"{source} must be a JSON array")
    seen: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise LibraryError(LIBRARY_MALFORMED, f"{source} entry {index} is not an object")
        key = item.get("id")
        if not isinstance(key, str) or not key:
            raise LibraryError(LIBRARY_MALFORMED, f"{source} entry {index} has no string id")
        if key in seen:
            raise LibraryError(LIBRARY_MALFORMED, f"{source} has duplicate id {key!r}")
        seen.add(key)
    return data


def load(path: Path) -> Library:
    """Load ``path``; a missing file is an empty library with the new-file layout."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return Library(path, [], NEW_FILE_LAYOUT, None)
    except OSError as exc:
        raise LibraryError(LIBRARY_MALFORMED, f"cannot read {path}: {exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LibraryError(LIBRARY_MALFORMED, f"{path} is not UTF-8") from exc
    items = parse_items(text, source=path.name)
    # An unknown layout is fine for reading; write_atomic refuses to rewrite it.
    layout = detect_layout(items, text)
    return Library(path, items, layout, hashlib.sha256(data).hexdigest())


def detect_layout(items: list[dict], text: str) -> int | str | None:
    for layout in LAYOUTS:
        if serialize(items, layout) == text:
            return layout
    return None


# --- keys ---------------------------------------------------------------


def _ascii_word(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9]", "", decomposed.encode("ascii", "ignore").decode().casefold())


def _first_author_token(item: dict) -> str:
    for role in ("author", "editor"):
        names = item.get(role)
        if not isinstance(names, list) or not names:
            continue
        first = names[0] if isinstance(names[0], dict) else {}
        family = first.get("family")
        if isinstance(family, str) and family.strip():
            return _ascii_word(family)
        literal = first.get("literal")
        if isinstance(literal, str) and literal.strip():
            return _ascii_word(literal.split()[0])
        return ""
    return ""


def _year_token(item: dict) -> str:
    issued = item.get("issued")
    if isinstance(issued, dict):
        parts = issued.get("date-parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            try:
                return str(int(parts[0][0]))
            except (TypeError, ValueError):
                pass
        literal = issued.get("literal") or issued.get("raw")
        if isinstance(literal, str):
            match = re.search(r"\d{4}", literal)
            if match:
                return match.group(0)
    return "nd"


def _title_token(item: dict) -> str:
    title = item.get("title")
    if not isinstance(title, str):
        return ""
    title = re.sub(r"<[^>]*>", " ", title)
    for raw in re.split(r"[\s\-‐‑–—/:]+", title):
        word = _ascii_word(raw)
        if word and word not in TITLE_STOPWORDS:
            return word
    return ""


def base_key(item: dict) -> str:
    """First author's surname + year + first non-stopword title word (A3)."""
    return (_first_author_token(item) or "ref") + _year_token(item) + _title_token(item)


def _suffixes():
    letters = "abcdefghijklmnopqrstuvwxyz"
    for first in letters:
        yield first
    for first in letters:
        for second in letters:
            yield first + second


def generate_key(item: dict, existing: set[str] | list[str]) -> str:
    taken = set(existing)
    key = base_key(item)
    if key not in taken:
        return key
    for suffix in _suffixes():
        if key + suffix not in taken:
            return key + suffix
    raise LibraryError(LIBRARY_CONFLICT, f"no free key for {key!r}")


# --- identity matching --------------------------------------------------

_ARXIV_ID = r"(\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?"


def item_doi(item: dict) -> str | None:
    value = item.get("DOI")
    return canonicalize_doi(value) if isinstance(value, str) else None


def item_arxiv(item: dict) -> str | None:
    doi = item_doi(item)
    if doi:
        match = re.fullmatch(r"10\.48550/arxiv\." + _ARXIV_ID, doi, re.I)
        if match:
            return match.group(1).casefold()
    url = item.get("URL")
    if isinstance(url, str):
        match = re.search(r"arxiv\.org/(?:abs|pdf)/" + _ARXIV_ID, url, re.I)
        if match:
            return match.group(1).casefold()
    number = item.get("number")
    venue = " ".join(
        str(item.get(name, "")) for name in ("publisher", "container-title", "archive")
    ).casefold()
    if isinstance(number, str):
        # "arXiv:<id>" is unambiguous; a bare id needs an arXiv venue.
        match = re.fullmatch(r"arxiv:" + _ARXIV_ID, number.strip(), re.I)
        if match is None and "arxiv" in venue:
            match = re.fullmatch(_ARXIV_ID, number.strip(), re.I)
        if match:
            return match.group(1).casefold()
    return None


# The official NeurIPS proceedings (and its former papers.nips.cc host) put the
# year and the paper hash in every paper URL, e.g.
# /paper_files/paper/2017/hash/<32 hex>-Abstract.html or …/file/<hash>-Paper.pdf.
_NEURIPS_HOSTS = frozenset({"proceedings.neurips.cc", "papers.nips.cc"})
_NEURIPS_PATH = re.compile(r"/paper(?:_files/paper)?/(\d{4})/(?:hash|file)/([0-9a-f]{32})-", re.I)


def item_neurips(item: dict) -> str | None:
    """``neurips:<year>:<hash>`` from an official NeurIPS proceedings URL.

    The same value the citation workflow's NeurIPS lookup uses as the
    ``venue`` identity, so an entry links to its saved bundle the way a DOI does.
    """
    url = item.get("URL")
    if not isinstance(url, str):
        return None
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None
    if (parsed.hostname or "").casefold() not in _NEURIPS_HOSTS:
        return None
    match = _NEURIPS_PATH.match(parsed.path)
    return f"neurips:{match.group(1)}:{match.group(2).casefold()}" if match else None


def find_existing(library: Library, item: dict) -> dict | None:
    doi = item_doi(item)
    if doi:
        for existing in library.items:
            if item_doi(existing) == doi:
                return existing
    arxiv = item_arxiv(item)
    if arxiv:
        for existing in library.items:
            if item_arxiv(existing) == arxiv:
                return existing
    neurips = item_neurips(item)
    if neurips:
        for existing in library.items:
            if item_neurips(existing) == neurips:
                return existing
    return None


def merge(library: Library, item: dict) -> MergeResult:
    """Reuse an existing entry for the same work, or append a new keyed one.

    Existing entries are never modified. The returned library is a new
    object; the input library is not mutated.
    """
    existing = find_existing(library, item)
    if existing is not None:
        return MergeResult("existing", existing["id"], existing, library)
    key = generate_key(item, library.keys())
    new_item = {"id": key, **{k: v for k, v in item.items() if k != "id"}}
    updated = Library(library.path, [*library.items, new_item], library.layout, library.fingerprint)
    return MergeResult("added", key, new_item, updated)


# --- searching ----------------------------------------------------------


def _search_text(item: dict) -> str:
    parts = [str(item.get("id", "")), str(item.get("title", "")), str(item.get("DOI", ""))]
    parts.append(_year_token(item))
    for role in ("author", "editor"):
        for name in item.get(role) or []:
            if isinstance(name, dict):
                parts.extend(str(name.get(part, "")) for part in ("family", "given", "literal"))
    return " ".join(parts).casefold()


def search_bibliography(items: list[dict], query: str, *, limit: int = 20) -> list[dict]:
    """Exact key first, then entries containing every query word."""
    query = (query or "").strip()
    exact = [item for item in items if item.get("id") == query]
    if exact:
        return exact[:limit]
    words = query.casefold().split()
    if not words:
        return items[:limit]
    return [item for item in items if all(word in _search_text(item) for word in words)][:limit]


def remove_entry(library: Library, key: str) -> Library:
    """A new library without the entry ``key`` (other entries untouched)."""
    if key not in library.keys():
        raise LibraryError(LIBRARY_MALFORMED, f"{key!r} is not in {library.path.name}")
    items = [item for item in library.items if item["id"] != key]
    return Library(library.path, items, library.layout, library.fingerprint)


# --- writing ------------------------------------------------------------


def write_atomic(library: Library) -> None:
    """Replace the file with ``library`` unless it changed since it was read."""
    path = library.path
    if library.layout is None:
        raise LibraryError(
            LIBRARY_FORMAT_UNSUPPORTED,
            f"{path.name} uses a JSON layout this tool cannot reproduce; it is left unchanged",
        )
    current = fingerprint(path)
    if current != library.fingerprint:
        raise LibraryError(
            LIBRARY_CONFLICT,
            f"{path.name} changed on disk since it was read; nothing was written",
        )
    data = serialize(library.items, library.layout).encode("utf-8")
    directory = path.parent
    try:
        mode = path.stat().st_mode & 0o7777 if current is not None else NEW_FILE_MODE
    except OSError:
        mode = NEW_FILE_MODE
    temp = directory / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(temp, mode)
        if fingerprint(path) != library.fingerprint:
            raise LibraryError(
                LIBRARY_CONFLICT,
                f"{path.name} changed on disk while writing; nothing was written",
            )
        os.replace(temp, path)
        fsync_directory(directory)
    except LibraryError:
        _unlink(temp)
        raise
    except OSError as exc:
        _unlink(temp)
        raise LibraryError(LIBRARY_WRITE_FAILED, f"cannot write {path}: {exc}") from exc
    library.fingerprint = hashlib.sha256(data).hexdigest()


def write_bytes_atomic(path: Path, data: bytes, *, mode: int = NEW_FILE_MODE) -> None:
    """Write a new or replacement file atomically (temp file, fsync, replace)."""
    path = Path(path)
    temp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(temp, mode)
        os.replace(temp, path)
        fsync_directory(path.parent)
    except OSError as exc:
        _unlink(temp)
        raise LibraryError(LIBRARY_WRITE_FAILED, f"cannot write {path}: {exc}") from exc


def add_item(path: Path, item: dict) -> MergeResult:
    """Load, merge, and (only when something was added) write ``path``."""
    library = load(path)
    result = merge(library, item)
    if result.status == "added":
        write_atomic(result.library)
    return result


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
