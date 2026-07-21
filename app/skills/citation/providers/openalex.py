"""OpenAlex discovery client with provider-native work query planning.

OpenAlex is a recall source, never the final DOI authority.  A Work can carry
multiple DOI-bearing locations, and its top-level DOI is OpenAlex's canonical
external identifier for that Work rather than proof that the DOI represents
the manifestation requested by the user.  ``search_work`` therefore preserves
and expands those locations; downstream resolution still verifies every DOI.

The API key is added only after cache keys have been constructed and is
redacted from every provider error.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import replace
from typing import Awaitable, Callable, Iterable

from skills.citation.doi import canonicalize_doi
from skills.citation.providers.base import (
    MAX_RECORDS_PER_QUERY,
    BibliographicQuery,
    Manifestation,
    ProviderRecord,
    QueryPass,
    plausible_identity_hit,
)
from skills.citation.providers.net import (
    SEARCH_TTL_SECONDS,
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    TTLCache,
    fetch_with_retries,
    redact,
)
from skills.citation.types import PublishedDateFilter

PROVIDER_NAME = "openalex"
SEARCH_URL = "https://api.openalex.org/works"

Fetcher = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]

_OPENALEX_ID_PREFIX = "https://openalex.org/"
_IDENTITY_SELECT = ",".join(
    (
        "id",
        "doi",
        "display_name",
        "publication_year",
        "publication_date",
        "type",
        "relevance_score",
        "authorships",
        "primary_location",
        "locations",
        "ids",
        "biblio",
        "is_retracted",
        "is_paratext",
    )
)


def _quoted_phrase(value: str) -> str:
    """Return one literal OpenAlex/Lucene phrase.

    URL encoding is a separate step.  Backslashes and quotes must first be
    escaped for the search grammar or a bibliographic title can accidentally
    become an operator-bearing query.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _quoted_author(value: str) -> str:
    # A comma is OpenAlex's filter separator.  Published names such as
    # ``Vaswani, Ashish`` are searched as the equivalent byline phrase.
    without_commas = re.sub(r"\s*,\s*", " ", value)
    return _quoted_phrase(" ".join(without_commas.split()))


def _pass_params(
    *,
    search_field: str,
    phrase: str,
    filters: Iterable[str],
    rows: int,
) -> dict[str, str]:
    params = {
        search_field: phrase,
        "per_page": str(max(1, min(rows, MAX_RECORDS_PER_QUERY))),
        "select": _IDENTITY_SELECT,
    }
    native_filters = [value for value in filters if value]
    if native_filters:
        params["filter"] = ",".join(native_filters)
    return params


def build_work_query_plan(
    query: BibliographicQuery,
    *,
    rows: int = MAX_RECORDS_PER_QUERY,
) -> tuple[QueryPass, ...]:
    """Build bounded OpenAlex passes from structured bibliographic hints.

    ``search.exact`` is unstemmed, not an exact-title endpoint, so every pass
    still requires local title/author validation.  The deprecated
    ``title.search`` filter is deliberately never used.
    """
    if not query.title:
        raise ValueError("OpenAlex work search requires a title")
    rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
    title_phrase = _quoted_phrase(query.title)
    author_filter = (
        f"raw_author_name.search:{_quoted_author(query.first_author)}"
        if query.first_author
        else ""
    )

    passes: list[QueryPass] = []
    if query.year is not None:
        date_filters = (
            f"from_publication_date:{max(1000, query.year - 1):04d}-01-01",
            f"to_publication_date:{min(2999, query.year + 1):04d}-12-31",
        )
        passes.append(
            QueryPass.build(
                "exact_with_year",
                _pass_params(
                    search_field="search.exact",
                    phrase=title_phrase,
                    filters=(author_filter, *date_filters),
                    rows=rows,
                ),
            )
        )

    # This pass is also the strict pass when no year was supplied.  Keeping
    # the author filter sharply reduces full-text hits that only cite the title.
    passes.append(
        QueryPass.build(
            "exact_without_year",
            _pass_params(
                search_field="search.exact",
                phrase=title_phrase,
                filters=(author_filter,),
                rows=rows,
            ),
        )
    )
    # Final recall pass removes author/date filters and enables stemming, while
    # retaining phrase matching.  It runs only when earlier passes produced no
    # locally plausible identity hit.
    passes.append(
        QueryPass.build(
            "stemmed_phrase",
            _pass_params(
                search_field="search",
                phrase=title_phrase,
                filters=(),
                rows=rows,
            ),
        )
    )
    return tuple(passes)


def _normalized_location_version(raw: object) -> str:
    value = str(raw or "").strip().casefold()
    return {
        "publishedversion": "published",
        "acceptedversion": "accepted",
        "submittedversion": "submitted",
    }.get(value, "unknown")


def _location_doi(location: dict) -> str | None:
    return canonicalize_doi(location.get("id")) or canonicalize_doi(
        location.get("landing_page_url")
    )


def _parse_manifestations(result: dict, top_level_doi: str | None) -> tuple[Manifestation, ...]:
    primary = result.get("primary_location") or {}
    locations: list[tuple[dict, bool]] = []
    if isinstance(primary, dict) and primary:
        locations.append((primary, True))
    for location in result.get("locations") or []:
        if isinstance(location, dict):
            locations.append((location, False))

    # The primary location is commonly repeated in ``locations``.  Merge that
    # exact duplicate by OR-ing the primary flag, but preserve distinct URLs or
    # version claims for the same DOI as separate evidence.
    order: list[tuple] = []
    manifestations: dict[tuple, Manifestation] = {}
    for location, is_primary in locations:
        doi = _location_doi(location)
        if not doi:
            continue
        source = location.get("source") or {}
        venue = (
            str(source.get("display_name", "") or "").strip()
            if isinstance(source, dict)
            else ""
        ) or str(location.get("raw_source_name", "") or "").strip()
        url = str(location.get("landing_page_url", "") or "").strip()
        manifestation = Manifestation(
            identifier=doi,
            identifier_type="doi",
            url=url,
            version_kind=_normalized_location_version(location.get("version")),
            venue=venue,
            is_primary=is_primary,
            is_accepted=bool(location.get("is_accepted")),
            is_published=bool(location.get("is_published")),
        )
        key = (
            manifestation.identifier,
            manifestation.url,
            manifestation.version_kind,
            manifestation.venue,
            manifestation.is_accepted,
            manifestation.is_published,
        )
        current = manifestations.get(key)
        if current is None:
            order.append(key)
            manifestations[key] = manifestation
        elif is_primary and not current.is_primary:
            manifestations[key] = replace(current, is_primary=True)

    if top_level_doi and not any(
        item.identifier == top_level_doi for item in manifestations.values()
    ):
        raw_primary = primary if isinstance(primary, dict) else {}
        source = raw_primary.get("source") or {}
        venue = (
            str(source.get("display_name", "") or "").strip()
            if isinstance(source, dict)
            else ""
        ) or str(raw_primary.get("raw_source_name", "") or "").strip()
        synthetic = Manifestation(
            identifier=top_level_doi,
            identifier_type="doi",
            url=str(result.get("doi", "") or ""),
            version_kind=_normalized_location_version(raw_primary.get("version")),
            venue=venue,
            is_primary=not any(item.is_primary for item in manifestations.values()),
            is_accepted=bool(raw_primary.get("is_accepted")),
            is_published=bool(raw_primary.get("is_published")),
        )
        key = (
            synthetic.identifier,
            synthetic.url,
            synthetic.version_kind,
            synthetic.venue,
            synthetic.is_accepted,
            synthetic.is_published,
        )
        order.append(key)
        manifestations[key] = synthetic
    return tuple(manifestations[key] for key in order)


def parse_work(result: dict, rank: int) -> ProviderRecord:
    """Normalize one OpenAlex Work without discarding DOI locations."""
    raw_id = str(result.get("id", "") or "")
    short_id = raw_id.removeprefix(_OPENALEX_ID_PREFIX) or raw_id
    doi = canonicalize_doi(result.get("doi"))
    authors: list[str] = []
    for authorship in result.get("authorships") or []:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author") or {}
        name = (
            str(author.get("display_name", "") or "").strip()
            if isinstance(author, dict)
            else ""
        ) or str(authorship.get("raw_author_name", "") or "").strip()
        if name:
            authors.append(name)
    year = result.get("publication_year")
    primary = result.get("primary_location") or {}
    source = primary.get("source") or {} if isinstance(primary, dict) else {}
    venue = (
        str(source.get("display_name", "") or "").strip()
        if isinstance(source, dict)
        else ""
    ) or (
        str(primary.get("raw_source_name", "") or "").strip()
        if isinstance(primary, dict)
        else ""
    )
    score = result.get("relevance_score")
    identifiers = {
        key: str(value)
        for key, value in (result.get("ids") or {}).items()
        if isinstance(value, (str, int))
    }
    manifestations = _parse_manifestations(result, doi)
    primary_manifestation = next(
        (item for item in manifestations if item.is_primary), None
    )
    return ProviderRecord(
        provider=PROVIDER_NAME,
        provider_id=f"openalex:{short_id}" if short_id else f"openalex:rank-{rank}",
        rank=rank,
        title=str(result.get("display_name") or result.get("title") or ""),
        authors=authors,
        year=int(year) if isinstance(year, int) else None,
        venue=venue,
        doi=doi,
        url=result.get("doi") or raw_id or None,
        landing_url=(
            str(primary.get("landing_page_url", "") or "") or None
            if isinstance(primary, dict)
            else None
        ),
        work_type=str(result.get("type", "") or ""),
        raw_score=float(score) if isinstance(score, (int, float)) else None,
        identifiers=identifiers,
        version_kind=(
            primary_manifestation.version_kind if primary_manifestation else "unknown"
        ),
        version=str(primary.get("version", "") or "") if isinstance(primary, dict) else "",
        record_state="retracted" if result.get("is_retracted") else "",
        manifestations=manifestations,
        field_provenance={
            field: PROVIDER_NAME
            for field in (
                "title",
                "authors",
                "year",
                "venue",
                "doi",
                "work_type",
                "url",
                "manifestations",
            )
        },
    )


def _manifestation_key(item: Manifestation) -> tuple:
    return (
        item.identifier,
        item.identifier_type,
        item.url,
        item.version_kind,
        item.venue,
        item.is_primary,
        item.is_accepted,
        item.is_published,
    )


def _merge_manifestations(*groups: tuple[Manifestation, ...]) -> tuple[Manifestation, ...]:
    out: list[Manifestation] = []
    seen: set[tuple] = set()
    for group in groups:
        for item in group:
            key = _manifestation_key(item)
            if key not in seen:
                seen.add(key)
                out.append(item)
    return tuple(out)


def _merge_records(
    records: Iterable[ProviderRecord],
    *,
    by_doi: bool,
) -> list[ProviderRecord]:
    merged: dict[tuple[str, str], ProviderRecord] = {}
    order: list[tuple[str, str]] = []
    for record in records:
        key = (
            ("doi", record.doi)
            if by_doi and record.doi
            else ("provider", record.provider_id)
        )
        current = merged.get(key)
        if current is None:
            order.append(key)
            merged[key] = record
            continue
        preferred, other = (
            (record, current) if record.rank < current.rank else (current, record)
        )
        merged[key] = replace(
            preferred,
            manifestations=_merge_manifestations(
                preferred.manifestations, other.manifestations
            ),
            identifiers={**other.identifiers, **preferred.identifiers},
            field_provenance={
                **other.field_provenance,
                **preferred.field_provenance,
            },
        )
    return [merged[key] for key in order]


def _expanded_version_kind(
    manifestations: list[Manifestation],
    *,
    work_type: str,
) -> str:
    versions = {item.version_kind for item in manifestations}
    if len(versions) == 1:
        version = next(iter(versions))
        if version == "published":
            return "published"
        if version == "accepted":
            return "repository"
        text = f"{work_type} {' '.join(item.venue for item in manifestations)}".casefold()
        if version == "submitted" and ("arxiv" in text or "preprint" in text):
            return "preprint"
        if version == "submitted":
            return "repository"
        return version
    return "unknown"


def _expand_manifestations(record: ProviderRecord) -> list[ProviderRecord]:
    by_doi: dict[str, list[Manifestation]] = {}
    doi_order: list[str] = []
    for manifestation in record.manifestations:
        if manifestation.identifier_type != "doi":
            continue
        doi = canonicalize_doi(manifestation.identifier)
        if not doi:
            continue
        if doi not in by_doi:
            by_doi[doi] = []
            doi_order.append(doi)
        by_doi[doi].append(manifestation)
    if record.doi and record.doi not in by_doi:
        by_doi[record.doi] = []
        doi_order.append(record.doi)
    if not doi_order:
        return [record]

    expanded: list[ProviderRecord] = []
    for doi in doi_order:
        evidence = by_doi[doi]
        primary = next((item for item in evidence if item.is_primary), None)
        chosen = primary or (evidence[0] if evidence else None)
        expanded.append(
            replace(
                record,
                provider_id=f"{record.provider_id}:doi:{doi}",
                doi=doi,
                url=(chosen.url if chosen and chosen.url else f"https://doi.org/{doi}"),
                landing_url=(chosen.url if chosen and chosen.url else None),
                venue=(chosen.venue if chosen and chosen.venue else record.venue),
                version_kind=_expanded_version_kind(
                    evidence, work_type=record.work_type
                ),
                version=(chosen.version_kind if chosen else "unknown"),
                # Preserve every location on every manifestation record so the
                # downstream resolver can see that the DOI choices share one
                # OpenAlex Work instead of treating them as unrelated hits.
                manifestations=record.manifestations,
            )
        )
    return expanded


class OpenAlexClient:
    """Bounded OpenAlex Works search (API key required)."""

    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        fetcher: Fetcher,
        cache: TTLCache,
        limiter: AsyncRateLimiter,
        api_key: str,
    ):
        if not api_key:
            raise ValueError("OpenAlexClient requires a non-empty api_key")
        self._fetcher = fetcher
        self._cache = cache
        self._limiter = limiter
        self._api_key = api_key

    def _redact(self, text: str) -> str:
        return redact(text, self._api_key)

    async def _search_pass(
        self,
        query_pass: QueryPass,
        *,
        cache_identity: tuple,
    ) -> list[ProviderRecord]:
        cache_key = (
            PROVIDER_NAME,
            "query_pass",
            cache_identity,
            query_pass.name,
            query_pass.params,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)

        # Add the secret only after the key has been built.
        query_params = query_pass.as_params()
        query_params["api_key"] = self._api_key
        url = f"{SEARCH_URL}?{urllib.parse.urlencode(query_params)}"
        headers = {"Accept": "application/json"}

        async def _fetch() -> FetchResponse:
            return await self._fetcher(url, headers)

        try:
            response = await fetch_with_retries(
                _fetch, provider=PROVIDER_NAME, limiter=self._limiter
            )
        except ProviderError as exc:
            exc.detail = self._redact(exc.detail)
            exc.args = (self._redact(str(exc.args[0])),) if exc.args else exc.args
            raise
        except Exception as exc:  # noqa: BLE001 - normalize injected transports
            raise ProviderError(
                PROVIDER_NAME,
                self._redact(f"request failed: {type(exc).__name__}: {exc}"),
            ) from exc

        try:
            data = json.loads(response.text)
            results = data.get("results", [])
            if not isinstance(results, list):
                raise TypeError("results is not a list")
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise ProviderError(
                PROVIDER_NAME,
                self._redact(f"unparseable search response: {exc}"),
            ) from exc

        try:
            rows = int(query_pass.as_params().get("per_page", MAX_RECORDS_PER_QUERY))
        except ValueError:
            rows = MAX_RECORDS_PER_QUERY
        records = [
            parse_work(result, rank=index)
            for index, result in enumerate(results[:rows])
            if isinstance(result, dict)
        ]
        self._cache.put(cache_key, list(records), SEARCH_TTL_SECONDS)
        return records

    async def search_text(
        self,
        query: str,
        *,
        rows: int = MAX_RECORDS_PER_QUERY,
        date_filter: PublishedDateFilter | None = None,
    ) -> list[ProviderRecord]:
        """Generic exploratory full-text search."""
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        filters: list[str] = []
        if date_filter is not None and date_filter.date_from:
            filters.append(f"from_publication_date:{date_filter.date_from}")
        if date_filter is not None and date_filter.date_to:
            filters.append(f"to_publication_date:{date_filter.date_to}")
        query_pass = QueryPass.build(
            "text",
            _pass_params(
                search_field="search",
                phrase=query,
                filters=filters,
                rows=rows,
            ),
        )
        date_key = (
            (date_filter.date_from, date_filter.date_to) if date_filter else None
        )
        return await self._search_pass(
            query_pass,
            cache_identity=("text", query, rows, date_key),
        )

    async def search_work(
        self,
        query: BibliographicQuery,
        *,
        rows: int = MAX_RECORDS_PER_QUERY,
    ) -> list[ProviderRecord]:
        """Run provider-native passes until a plausible identity hit appears."""
        plan = build_work_query_plan(query, rows=rows)
        accumulated: list[ProviderRecord] = []
        for query_pass in plan:
            records = await self._search_pass(
                query_pass,
                cache_identity=("work", query.fingerprint),
            )
            accumulated.extend(records)
            if any(plausible_identity_hit(query, record) for record in records):
                break

        works = _merge_records(accumulated, by_doi=False)
        expanded = [item for work in works for item in _expand_manifestations(work)]
        return _merge_records(expanded, by_doi=True)
