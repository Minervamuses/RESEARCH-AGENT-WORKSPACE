"""Authoritative no-DOI adapters (arXiv API, NeurIPS proceedings).

Both adapters query the official source for every lookup:

* arXiv: ``export.arxiv.org/api/query`` for the exact arXiv ID.
* NeurIPS: the official proceedings site ``proceedings.neurips.cc``. The
  year's paper list (``/paper_files/paper/<year>``) must contain exactly one
  paper whose normalized title equals the requested title; that paper's page
  then supplies the title, authors, year, venue and volume from its
  ``citation_*`` meta tags, and the page's title and year must agree again.
  The identity is the proceedings' own paper hash,
  ``venue:neurips:<year>:<hash>``. Papers outside the main proceedings site
  (e.g. the separate 2021 Datasets and Benchmarks site) are not found.
"""

from __future__ import annotations

import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser

from skills.citation.normalize import normalize_title
from skills.citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    ProviderHTTPError,
    fetch_with_retries,
)
from skills.citation.resolution import WorkIntent, normalize_arxiv
from skills.citation.types import CanonicalIdentity

MAX_AUTHORITY_BYTES = 1024 * 1024
NEURIPS_BASE = "https://proceedings.neurips.cc"
# One year's list of papers: 2024 is about 3.1 MB for about 4,500 papers.
MAX_NEURIPS_INDEX_BYTES = 16 * 1024 * 1024
_NEURIPS_LINK = re.compile(
    r'<a\s+title="paper title"\s+href="(/paper_files/paper/(\d{4})/hash/([0-9a-f]{32})-Abstract[A-Za-z_-]*\.html)"\s*>'
    r"(.*?)</a>",
    re.S,
)


@dataclass(frozen=True)
class AuthorityRecord:
    identity: CanonicalIdentity
    title: str
    authors: tuple[str, ...]
    year: int
    venue: str
    work_type: str
    url: str
    provider: str
    # (family, given) when the source states the split; empty for arXiv.
    names: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class NeurIPSPaper:
    """One entry of a year's official paper list."""

    path: str
    year: int
    paper_hash: str
    title: str


def names_neurips(venue: str | None) -> bool:
    """Does a free-text venue name the NeurIPS (formerly NIPS) proceedings?"""
    text = normalize_title(venue)
    return bool(text) and (
        "neurips" in text
        or "neural information processing systems" in text
        or re.search(r"\bnips\b", text) is not None
    )


def parse_neurips_index(page: str, year: int) -> list[NeurIPSPaper]:
    """The papers listed on ``/paper_files/paper/<year>`` (titles unescaped)."""
    papers = []
    for path, listed_year, paper_hash, raw_title in _NEURIPS_LINK.findall(page):
        if int(listed_year) != year:
            continue
        title = " ".join(html.unescape(re.sub(r"<[^>]+>", "", raw_title)).split())
        if title:
            papers.append(NeurIPSPaper(path, year, paper_hash, title))
    return papers


class _CitationMeta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        values = dict(attrs)
        name = values.get("name") or ""
        if name.startswith("citation_") and values.get("content") is not None:
            self.tags.append((name, " ".join(values["content"].split())))


def parse_citation_meta(page: str) -> list[tuple[str, str]]:
    """``(name, content)`` of every ``<meta name="citation_*">`` in page order."""
    parser = _CitationMeta()
    parser.feed(page)
    parser.close()
    return parser.tags


def _split_name(name: str) -> tuple[str, str]:
    family, _, given = name.partition(",")
    return family.strip(), given.strip()


class AuthorityRegistry:
    def __init__(self, *, fetcher, limiter: AsyncRateLimiter | None = None):
        self._fetcher = fetcher
        self._limiter = limiter or AsyncRateLimiter(max_concurrency=1)
        # Per session: a year's paper list does not change while it runs.
        self._neurips_years: dict[int, list[NeurIPSPaper]] = {}

    async def resolve(self, intent: WorkIntent) -> AuthorityRecord | None:
        arxiv = next((item.value for item in intent.identifiers if item.kind == "arxiv"), None)
        if arxiv:
            return await self._arxiv(arxiv)
        if intent.year and intent.title and names_neurips(intent.venue):
            return await self._neurips(intent.title, intent.year)
        return None

    async def _get(self, provider: str, url: str, accept: str, max_bytes: int) -> bytes | None:
        """Body of an official page; ``None`` for 404. Other failures raise ProviderError."""

        async def _fetch() -> FetchResponse:
            return await self._fetcher(url, {"Accept": accept})

        try:
            response = await fetch_with_retries(_fetch, provider=provider, limiter=self._limiter)
        except ProviderHTTPError as exc:
            if exc.status == 404:
                return None
            raise
        if len(response.body) > max_bytes:
            raise ProviderError(provider, "response payload exceeds limit")
        return response.body

    async def _neurips_year(self, year: int) -> list[NeurIPSPaper]:
        if year not in self._neurips_years:
            body = await self._get(
                "neurips", f"{NEURIPS_BASE}/paper_files/paper/{year}", "text/html", MAX_NEURIPS_INDEX_BYTES,
            )
            page = body.decode("utf-8", errors="replace") if body else ""
            self._neurips_years[year] = parse_neurips_index(page, year)
        return self._neurips_years[year]

    async def _neurips(self, title: str, year: int) -> AuthorityRecord | None:
        wanted = normalize_title(title)
        matches = [paper for paper in await self._neurips_year(year) if normalize_title(paper.title) == wanted]
        if len(matches) != 1:
            return None
        paper = matches[0]
        url = NEURIPS_BASE + paper.path
        body = await self._get("neurips", url, "text/html", MAX_AUTHORITY_BYTES)
        if not body:
            return None
        meta = parse_citation_meta(body.decode("utf-8", errors="replace"))

        def first(name: str) -> str:
            return next((value for key, value in meta if key == name and value), "")

        page_title = first("citation_title")
        names = tuple(_split_name(value) for key, value in meta if key == "citation_author" and value)
        date = first("citation_publication_date")
        venue = first("citation_journal_title") or first("citation_conference_title")
        if (
            normalize_title(page_title) != wanted
            or not re.match(r"\d{4}", date) or int(date[:4]) != year
            or not names or not all(family for family, _given in names)
            or not venue
        ):
            return None
        volume = first("citation_volume")
        if volume and not venue.endswith(f" {volume}"):
            # Same form as the author's NeurIPS entries ("... Systems 30"); bime_word
            # prints the proceedings title but not a separate volume.
            venue = f"{venue} {volume}"
        return AuthorityRecord(
            CanonicalIdentity("venue", f"neurips:{year}:{paper.paper_hash}"),
            page_title,
            tuple(f"{given} {family}".strip() for family, given in names),
            year,
            venue,
            "inproceedings",
            url,
            "neurips",
            names=names,
        )

    async def _arxiv(self, arxiv_id: str) -> AuthorityRecord | None:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": arxiv_id})
        body = await self._get("arxiv", url, "application/atom+xml", MAX_AUTHORITY_BYTES)
        if not body:
            return None
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return None
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", ns)
        if entry is None:
            return None
        entry_id = entry.findtext("a:id", "", ns).strip()
        parsed_path = urllib.parse.urlparse(entry_id).path
        if "/abs/" not in parsed_path:
            return None
        try:
            returned_arxiv = normalize_arxiv(parsed_path.split("/abs/", 1)[1])
        except ValueError:
            return None
        if returned_arxiv != arxiv_id:
            return None
        title = " ".join((entry.findtext("a:title", "", ns)).split())
        authors = tuple(
            name.text.strip() for name in entry.findall("a:author/a:name", ns)
            if name.text and name.text.strip()
        )
        published = entry.findtext("a:published", "", ns)
        year = int(published[:4]) if re.match(r"\d{4}", published) else 0
        if not title or not authors or not year:
            return None
        return AuthorityRecord(
            CanonicalIdentity("arxiv", arxiv_id), title, authors, year,
            "arXiv", "preprint", f"https://arxiv.org/abs/{arxiv_id}", "arxiv",
        )
