"""Web-search MCP fallback provider.

Wraps the chat session's already-loaded Web Search MCP tool handles (the
Coordinator injects them; this module never starts an MCP server). Policy —
web runs automatically only when every enabled structured provider failed or
returned zero candidates, otherwise only via the ``more`` action — lives in
the Coordinator; this adapter just searches and parses.

URL handling (per plan): normalization lowercases scheme/host only, sorts
query parameters, and keeps every parameter — including Google Scholar
identity parameters. The query string is never discarded wholesale.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import html
import re
import urllib.parse

from skills.citation.doi import extract_doi_candidates
from skills.citation.providers.base import MAX_RECORDS_PER_QUERY, ProviderRecord
from skills.citation.providers.net import ProviderError, ProviderTimeout

PROVIDER_NAME = "web"

# Tool names exposed by mrkrsl/web-search-mcp.
SUMMARIES_TOOL = "get-web-search-summaries"
FULL_SEARCH_TOOL = "full-web-search"
PAGE_CONTENT_TOOL = "get-single-web-page-content"

_TOOL_TIMEOUT_SECONDS = 30.0

# Anchors for the mrkrsl/web-search-mcp text format (fixtures taken from
# real v0.3.2 output):
#   **1. Title**
#   URL: https://...
#   Description: ...
_RESULT_HEAD = re.compile(r"^\*\*\s*(\d+)\.\s*(.+?)\s*\*\*\s*$")
_URL_LINE = re.compile(r"^URL:\s*(.+?)\s*$")
_DESC_LINE = re.compile(r"^Description:\s*(.*?)\s*$")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def normalize_url(url: str | None) -> str | None:
    """Normalize scheme/host case and sort query parameters, keeping them all.

    Never strips the query: Scholar identity parameters (`title`, `author`,
    `doi`, ...) are what make two scholar_lookup URLs distinct.
    """
    if not url:
        return url
    unescaped = html.unescape(url.strip())
    try:
        parsed = urllib.parse.urlsplit(unescaped)
    except ValueError:
        return unescaped
    if not parsed.scheme and not parsed.netloc:
        return unescaped
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    sorted_query = urllib.parse.urlencode(sorted(query_pairs))
    return urllib.parse.urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        sorted_query,
        parsed.fragment,
    ))


def unwrap_redirect_url(url: str | None) -> str | None:
    """Resolve a Bing ``/ck/a?...u=a1<base64url>`` redirect to its target."""
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        if "bing.com" not in parsed.netloc or "/ck/a" not in parsed.path:
            return url
        wrapped = urllib.parse.parse_qs(parsed.query).get("u", [""])[0]
        if not wrapped:
            return url
        encoded = wrapped[2:] if wrapped[:2].isalnum() and len(wrapped) > 2 else wrapped
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="strict")
        if decoded.startswith("http"):
            return decoded
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return url
    return url


def clean_search_title(raw_title: str) -> str:
    """Reduce a search-engine display label to the paper-ish title part."""
    raw = (raw_title or "").strip()
    if not raw:
        return raw
    parts = [p.strip() for p in re.split(r"\s{2,}", raw) if p.strip()]
    title = parts[-1] if len(parts) > 1 else raw
    title = re.sub(r"\s+-\s+Google Scholar\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^\[(?:pdf|html|book|citation)\]\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^\[[^\]]+\]\s*", "", title)
    if " | " in title:
        left = title.split(" | ", 1)[0].strip()
        if len(left) >= 8:
            title = left
    return re.sub(r"\s+", " ", title).strip() or raw


def _scholar_lookup_metadata(url: str | None) -> dict[str, object]:
    if not url:
        return {}
    parsed = urllib.parse.urlparse(html.unescape(url))
    qs = urllib.parse.parse_qs(parsed.query)
    meta: dict[str, object] = {}
    title = (qs.get("title") or [""])[0].strip()
    if title:
        meta["title"] = re.sub(r"\s+", " ", title)
    doi = (qs.get("doi") or [""])[0].strip()
    if doi:
        meta["doi"] = doi
    year = (qs.get("publication_year") or [""])[0].strip()
    if year.isdigit():
        meta["year"] = int(year)
    authors = [a.strip() for a in qs.get("author", []) if a.strip()]
    if authors:
        meta["authors"] = authors
    return meta


def _is_author_profile(url: str | None) -> bool:
    if not url:
        return False
    parsed = urllib.parse.urlparse(html.unescape(url))
    return "scholar.google." in parsed.netloc and parsed.path.startswith("/citations")


def _is_generic_label(title: str) -> bool:
    return (title or "").strip().lower() in {"google scholar", "scholar"}


def coerce_text(result) -> str:
    """Coerce a LangChain MCP tool result into plain text."""
    if isinstance(result, str):
        return result
    if isinstance(result, (list, tuple)):
        parts: list[str] = []
        for item in result:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(result, dict) and result.get("type") == "text":
        return str(result.get("text", ""))
    return str(result)


def parse_search_text(text: str) -> list[ProviderRecord]:
    """Parse mrkrsl summaries text into ordered web ProviderRecords."""
    raw_items: list[dict] = []
    current: dict | None = None
    collecting_desc = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        head = _RESULT_HEAD.match(line)
        if head:
            if current is not None:
                raw_items.append(current)
            current = {"title": clean_search_title(head.group(2)), "snippet": ""}
            collecting_desc = False
            continue
        if current is None:
            continue
        url_match = _URL_LINE.match(line)
        if url_match:
            current["url"] = unwrap_redirect_url(url_match.group(1).strip())
            collecting_desc = False
            continue
        desc_match = _DESC_LINE.match(line)
        if desc_match:
            current["snippet"] = desc_match.group(1).strip()
            collecting_desc = True
            continue
        if line.strip() == "---" or line.lstrip().startswith("**"):
            collecting_desc = False
            continue
        if collecting_desc and line.strip():
            current["snippet"] = (current["snippet"] + " " + line.strip()).strip()
    if current is not None:
        raw_items.append(current)

    records: list[ProviderRecord] = []
    seen: set[str] = set()
    for item in raw_items:
        url = item.get("url")
        if _is_author_profile(url):
            continue
        normalized = normalize_url(url)
        meta = _scholar_lookup_metadata(url)
        title = str(meta.get("title") or "") if _is_generic_label(item["title"]) else item["title"]
        title = title or item["title"]
        doi_candidates = extract_doi_candidates(
            str(meta.get("doi") or ""), url, item.get("snippet"), title
        )
        year = meta.get("year")
        if year is None:
            years = [
                int(y)
                for y in _YEAR_RE.findall(f"{title} {item.get('snippet', '')}")
                if 1950 <= int(y) <= 2035
            ]
            year = max(years) if years else None
        key = normalized or title
        if not key or key in seen:
            continue
        seen.add(key)
        records.append(ProviderRecord(
            provider=PROVIDER_NAME,
            provider_id=f"web:{normalized or title}",
            rank=len(records),
            title=title,
            authors=[str(a) for a in meta.get("authors", [])],
            year=int(year) if isinstance(year, int) else None,
            venue="",
            doi=doi_candidates[0] if doi_candidates else None,
            url=normalized,
            snippet=str(item.get("snippet", "")),
        ))
    return records


class WebSearchProvider:
    """Search adapter over injected Web Search MCP tool handles."""

    name = PROVIDER_NAME

    def __init__(self, tools: dict[str, object], *, timeout: float = _TOOL_TIMEOUT_SECONDS):
        self._tools = dict(tools or {})
        self._timeout = timeout

    @property
    def available(self) -> bool:
        return SUMMARIES_TOOL in self._tools

    async def search(self, query: str, *, rows: int = MAX_RECORDS_PER_QUERY) -> list[ProviderRecord]:
        tool = self._tools.get(SUMMARIES_TOOL)
        if tool is None:
            raise ProviderError(
                PROVIDER_NAME, f"MCP tool {SUMMARIES_TOOL!r} is not available"
            )
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        try:
            result = await asyncio.wait_for(
                tool.ainvoke({"query": query, "limit": rows}),
                timeout=self._timeout,
            )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise ProviderTimeout(PROVIDER_NAME, "web search timed out") from exc
        except Exception as exc:  # noqa: BLE001 - one MCP failure is one provider state
            raise ProviderError(
                PROVIDER_NAME, f"web search failed: {type(exc).__name__}: {exc}"
            ) from exc
        return parse_search_text(coerce_text(result))[:rows]
