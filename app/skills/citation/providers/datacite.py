"""DataCite REST discovery client with provider-native query planning."""

from __future__ import annotations

from dataclasses import replace
import json
import re
import urllib.parse
from typing import Awaitable, Callable, Iterable

from skills.citation.doi import canonicalize_doi
from skills.citation.providers.base import (
    MAX_RECORDS_PER_QUERY,
    BibliographicQuery,
    ProviderRecord,
    QueryPass,
    RelationEdge,
    plausible_identity_hit,
)
from skills.citation.providers.net import (
    SEARCH_TTL_SECONDS,
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    TTLCache,
    fetch_with_retries,
)
from skills.citation.types import PublishedDateFilter

PROVIDER_NAME = "datacite"
SEARCH_URL = "https://api.datacite.org/dois"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

_RESULT_FIELDS = ",".join(
    (
        "doi",
        "titles",
        "creators",
        "publicationYear",
        "published",
        "publisher",
        "container",
        "types",
        "url",
        "relatedIdentifiers",
        "version",
        "identifiers",
        "alternateIdentifiers",
        "state",
    )
)

Fetcher = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]


def _user_agent(mailto: str | None) -> str:
    base = "research-agent-citation/1.0"
    return f"{base} (mailto:{mailto})" if mailto else base


def _entries(value: object) -> list[dict]:
    """Return JSON object entries while tolerating singleton legacy shapes."""
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _year(attributes: dict) -> int | None:
    """Return a bibliographic year, never a DataCite administration year."""
    for key in ("publicationYear", "published"):
        value = attributes.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and 1000 <= value <= 2999:
            return value
        if isinstance(value, str):
            text = value.strip()
            if len(text) >= 4 and text[:4].isdigit():
                year = int(text[:4])
                if 1000 <= year <= 2999:
                    return year
    return None


def _publisher(attributes: dict) -> str:
    value = attributes.get("publisher")
    if isinstance(value, dict):
        return str(value.get("name", "") or "").strip()
    return str(value or "").strip()


def _identifier_value(kind: str, raw: object) -> str:
    value = str(raw or "").strip()
    if kind.casefold() == "doi":
        return canonicalize_doi(value) or value
    return value


def _relation_detail(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (dict, list)):
        return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(raw).strip()


def _version_kind(
    *, resource_type_general: str, resource_type: str, publisher: str, url: str
) -> str:
    """Classify only explicit publication-stage evidence; otherwise abstain."""
    text = " ".join(
        (resource_type_general, resource_type, publisher, url)
    ).casefold()
    if "preprint" in text or "arxiv" in text:
        return "preprint"
    if "postprint" in text or "accepted manuscript" in text:
        return "repository"
    normalized_types = {
        resource_type_general.replace("-", "").replace(" ", "").casefold(),
        resource_type.replace("-", "").replace(" ", "").casefold(),
    }
    if normalized_types & {"journalarticle", "conferencepaper"}:
        return "published"
    return "unknown"


def parse_doi_item(item: dict, rank: int) -> ProviderRecord | None:
    attributes = item.get("attributes") or {}
    if not isinstance(attributes, dict):
        return None
    doi = canonicalize_doi(attributes.get("doi") or item.get("id"))
    if not doi:
        return None

    title = ""
    for entry in _entries(attributes.get("titles")):
        value = str(entry.get("title", "") or "").strip()
        if value:
            title = value
            break

    authors: list[str] = []
    for creator in _entries(attributes.get("creators")):
        name = str(creator.get("name", "") or "").strip()
        if not name:
            name = " ".join(
                str(creator.get(key, "") or "").strip()
                for key in ("givenName", "familyName")
            ).strip()
        if name:
            authors.append(name)

    types = attributes.get("types") or {}
    if not isinstance(types, dict):
        types = {}
    resource_type_general = str(types.get("resourceTypeGeneral", "") or "").strip()
    resource_type = str(types.get("resourceType", "") or "").strip()

    container = attributes.get("container") or {}
    venue = (
        str(container.get("title", "") or "").strip()
        if isinstance(container, dict)
        else ""
    )
    publisher = _publisher(attributes)
    url = str(attributes.get("url", "") or "").strip()

    relations: dict[str, list[str]] = {}
    relation_edges: list[RelationEdge] = []
    for relation in _entries(attributes.get("relatedIdentifiers")):
        relation_type = str(relation.get("relationType", "") or "").strip()
        identifier_type = str(
            relation.get("relatedIdentifierType", "") or ""
        ).strip()
        identifier = _identifier_value(
            identifier_type, relation.get("relatedIdentifier")
        )
        if not relation_type or not identifier:
            continue
        resource = str(relation.get("resourceTypeGeneral", "") or "").strip()
        detail = _relation_detail(relation.get("relationTypeInformation"))
        relations.setdefault(relation_type, []).append(identifier)
        relation_edges.append(
            RelationEdge(
                relation_type=relation_type,
                identifier=identifier,
                identifier_type=identifier_type,
                resource_type=resource,
                detail=detail,
            )
        )

    identifiers = {"doi": doi}
    aliases: list[str] = []
    identifier_sources: Iterable[tuple[object, str, str]] = (
        (attributes.get("identifiers"), "identifierType", "identifier"),
        (
            attributes.get("alternateIdentifiers"),
            "alternateIdentifierType",
            "alternateIdentifier",
        ),
    )
    for raw_entries, kind_key, value_key in identifier_sources:
        for entry in _entries(raw_entries):
            kind = str(entry.get(kind_key, "") or "").strip().casefold()
            value = _identifier_value(kind, entry.get(value_key))
            if not kind or not value:
                continue
            if kind == "doi":
                if value != doi and value not in aliases:
                    aliases.append(value)
                continue
            identifiers.setdefault(kind, value)

    version_kind = _version_kind(
        resource_type_general=resource_type_general,
        resource_type=resource_type,
        publisher=publisher,
        url=url,
    )
    provenance = {
        field: PROVIDER_NAME
        for field in (
            "title",
            "authors",
            "year",
            "venue",
            "doi",
            "work_type",
            "publisher",
            "url",
        )
    }
    return ProviderRecord(
        provider=PROVIDER_NAME,
        provider_id=f"datacite:{doi}",
        rank=rank,
        title=title,
        authors=authors,
        year=_year(attributes),
        venue=venue,
        doi=doi,
        url=url or None,
        landing_url=url or None,
        work_type=resource_type_general or resource_type,
        resource_type=resource_type or resource_type_general,
        publisher=publisher,
        identifiers=identifiers,
        relations=relations,
        relation_edges=tuple(relation_edges),
        aliases=tuple(aliases),
        version_kind=version_kind,
        version=str(attributes.get("version", "") or "").strip(),
        record_state=str(attributes.get("state", "") or "").strip().casefold(),
        field_provenance=provenance,
    )


def _phrase(value: str) -> str:
    """Escape one trusted literal for an OpenSearch quoted phrase."""
    escaped = re.sub(r'([+\-=&|><!(){}\[\]^"~*?:\\/])', r"\\\1", value)
    return f'"{escaped}"'


def _author_clause(author: str) -> str:
    full_name = author.strip()
    if not full_name:
        return ""
    if "," in full_name:
        family_name = full_name.split(",", 1)[0].strip()
    else:
        family_name = full_name.rsplit(maxsplit=1)[-1]
    name_clause = f"creators.name:{_phrase(full_name)}"
    if not family_name:
        return name_clause
    return (
        f"(creators.familyName:{_phrase(family_name)} OR {name_clause})"
    )


def _work_params(query_text: str, rows: int) -> dict[str, str]:
    return {
        "query": query_text,
        "sort": "relevance",
        "page[size]": str(max(1, min(rows, MAX_RECORDS_PER_QUERY))),
        "disable-facets": "true",
        "fields[dois]": _RESULT_FIELDS,
    }


def build_work_query_plan(
    query: BibliographicQuery,
    *,
    rows: int = MAX_RECORDS_PER_QUERY,
) -> tuple[QueryPass, ...]:
    """Build strict-to-recall DataCite passes from bibliographic fields."""
    identity_clauses: list[str] = []
    if query.title:
        identity_clauses.append(f"titles.title:{_phrase(query.title)}")
    author_clause = _author_clause(query.first_author)
    if author_clause:
        identity_clauses.append(author_clause)
    if not identity_clauses:
        return ()

    base = " AND ".join(identity_clauses)
    candidates: list[tuple[str, str]] = []
    if query.year is not None:
        candidates.append(("strict", f"{base} AND publicationYear:{query.year}"))
        years = range(max(1000, query.year - 1), min(2999, query.year + 1) + 1)
        widened = " OR ".join(str(year) for year in years)
        candidates.append(
            ("year_widened", f"{base} AND publicationYear:({widened})")
        )
        candidates.append(("no_year", base))
    else:
        candidates.append(("strict", base))

    passes: list[QueryPass] = []
    seen: set[str] = set()
    for name, query_text in candidates:
        if query_text in seen:
            continue
        seen.add(query_text)
        passes.append(QueryPass.build(name, _work_params(query_text, rows)))
    return tuple(passes)


def _text_query(query: str, date_filter: PublishedDateFilter | None) -> str:
    text = query.strip()
    if not date_filter:
        return text
    year_from = date_filter.year_from
    year_to = date_filter.year_to
    if year_from is not None and year_to == year_from:
        year_clause = f"publicationYear:{year_from}"
    elif year_from is not None and year_to is not None:
        year_clause = f"publicationYear:[{year_from} TO {year_to}]"
    elif year_from is not None:
        year_clause = f"publicationYear:[{year_from} TO *]"
    elif year_to is not None:
        year_clause = f"publicationYear:[* TO {year_to}]"
    else:
        return text
    return f"({text}) AND {year_clause}" if text else year_clause


class DataCiteClient:
    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        fetcher: Fetcher,
        cache: TTLCache,
        limiter: AsyncRateLimiter,
        mailto: str | None = None,
    ):
        self._fetcher = fetcher
        self._cache = cache
        self._limiter = limiter
        self._mailto = mailto

    async def _fetch_records(
        self, params: dict[str, str], *, rows: int
    ) -> list[ProviderRecord]:
        url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/vnd.api+json",
            "User-Agent": _user_agent(self._mailto),
        }

        async def _fetch() -> FetchResponse:
            return await self._fetcher(url, headers)

        response = await fetch_with_retries(
            _fetch, provider=PROVIDER_NAME, limiter=self._limiter
        )
        length = response.headers.get("content-length") or response.headers.get(
            "Content-Length"
        )
        if length and length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
            raise ProviderError(PROVIDER_NAME, "response payload exceeds limit")
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise ProviderError(PROVIDER_NAME, "response payload exceeds limit")
        try:
            data = json.loads(response.text)
            items = data.get("data", []) or []
            if not isinstance(items, list):
                raise TypeError("data is not a list")
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise ProviderError(PROVIDER_NAME, "unparseable search response") from exc

        records: list[ProviderRecord] = []
        for item in items[:rows]:
            if not isinstance(item, dict):
                continue
            record = parse_doi_item(item, len(records))
            if record is not None:
                records.append(record)
        return records

    async def search_text(
        self,
        query: str,
        *,
        rows: int = MAX_RECORDS_PER_QUERY,
        date_filter: PublishedDateFilter | None = None,
    ) -> list[ProviderRecord]:
        """Generic exploratory search retained separately from work matching."""
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        date_key = (date_filter.year_from, date_filter.year_to) if date_filter else None
        cache_key = (PROVIDER_NAME, "search_text", query, rows, date_key)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)
        query_text = _text_query(query, date_filter)
        if not query_text:
            self._cache.put(cache_key, [], SEARCH_TTL_SECONDS)
            return []
        records = await self._fetch_records(
            _work_params(query_text, rows), rows=rows
        )
        self._cache.put(cache_key, list(records), SEARCH_TTL_SECONDS)
        return records

    async def search_work(
        self,
        query: BibliographicQuery,
        *,
        rows: int = MAX_RECORDS_PER_QUERY,
    ) -> list[ProviderRecord]:
        """Run bounded fielded passes until a plausible identity hit appears."""
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        cache_key = (PROVIDER_NAME, "search_work", query.fingerprint, rows)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)

        merged: dict[str, ProviderRecord] = {}
        for query_pass in build_work_query_plan(query, rows=rows):
            records = await self._fetch_records(query_pass.as_params(), rows=rows)
            for record in records:
                if record.doi and record.doi not in merged:
                    merged[record.doi] = replace(record, rank=len(merged))
            if any(plausible_identity_hit(query, record) for record in records):
                break

        result = list(merged.values())
        self._cache.put(cache_key, list(result), SEARCH_TTL_SECONDS)
        return result
