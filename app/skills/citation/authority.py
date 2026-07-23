"""Allowlisted authoritative no-DOI adapters and deterministic BibTeX export."""

from __future__ import annotations

import asyncio
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from pybtex.database import BibliographyData, Entry, Person

from skills.citation.bibtex_canonical import parse_canonical_bibtex
from skills.citation.normalize import normalize_title
from skills.citation.providers.net import (
    ProviderError,
    ProviderHTTPError,
    ProviderTimeout,
)
from skills.citation.resolution import WorkIntent, normalize_arxiv
from skills.citation.types import CanonicalIdentity

MAX_AUTHORITY_BYTES = 1024 * 1024


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


_NEURIPS = {
    (2017, normalize_title("Attention Is All You Need")): AuthorityRecord(
        CanonicalIdentity("venue", "neurips:2017:7181"),
        "Attention Is All You Need",
        ("Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit", "Llion Jones", "Aidan N. Gomez", "Lukasz Kaiser", "Illia Polosukhin"),
        2017, "Advances in Neural Information Processing Systems 30",
        "inproceedings",
        "https://papers.nips.cc/paper_files/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html",
        "neurips",
    ),
}


class AuthorityRegistry:
    def __init__(self, *, fetcher):
        self._fetcher = fetcher

    async def resolve(self, intent: WorkIntent) -> AuthorityRecord | None:
        arxiv = next((item.value for item in intent.identifiers if item.kind == "arxiv"), None)
        if arxiv:
            return await self._arxiv(arxiv)
        venue = normalize_title(intent.venue)
        if intent.year and (
            "neurips" in venue
            or "neural information processing systems" in venue
        ):
            return _NEURIPS.get((intent.year, normalize_title(intent.title)))
        return None

    async def _arxiv(self, arxiv_id: str) -> AuthorityRecord | None:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": arxiv_id})
        try:
            response = await self._fetcher(
                url, {"Accept": "application/atom+xml"}
            )
        except ProviderError:
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise ProviderTimeout("arxiv", "request timed out") from exc
        if response.status >= 400:
            if response.status == 404:
                return None
            raise ProviderHTTPError("arxiv", response.status)
        if len(response.body) > MAX_AUTHORITY_BYTES:
            raise ProviderError("arxiv", "response payload exceeds limit")
        if not response.body:
            return None
        try:
            root = ET.fromstring(response.body)
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


def export_bibtex(record: AuthorityRecord):
    fields = {
        "title": record.title, "year": str(record.year), "url": record.url,
    }
    if record.provider == "neurips":
        fields["booktitle"] = record.venue
    else:
        fields["eprint"] = record.identity.value
        fields["archiveprefix"] = "arXiv"
    key = re.sub(r"[^a-z0-9]+", "", record.authors[0].split()[-1].casefold()) + str(record.year)
    entry = Entry(
        "inproceedings" if record.provider == "neurips" else "misc",
        fields=fields,
        persons={"author": [Person(author) for author in record.authors]},
    )
    text = BibliographyData({key: entry}).to_string("bibtex")
    return parse_canonical_bibtex(text)
