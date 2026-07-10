"""Deterministic cross-provider fusion of discovery results.

Ranking is reciprocal-rank fusion with fixed ``k=60`` over each provider's
own result order. Raw provider scores are carried on the records as evidence
but never compared across providers. Ties break deterministically by: DOI
presence, exact-title match against the query, provider name, then merge key
(which fixes the eventual candidate ID order).

Merging is identity-based only: records fuse when they share a canonical DOI
or the same namespaced provider ID. A DOI-less record whose title/author/year
looks like an existing candidate joins a *related-version group* (preprint vs
published stay listed separately, never destructively merged).

Metadata precedence on merge: identifier-derived structured record ->
Crossref -> OpenAlex -> web. Lower-precedence sources only fill empty
fields; every conflicting value is preserved in ``conflicts``.
"""

from __future__ import annotations

from collections import defaultdict

from skills.citation.normalize import normalize_title
from skills.citation.providers.base import ProviderRecord
from skills.citation.types import CitationCandidate

RRF_K = 60

# Metadata precedence, best first. "structured" is an identifier-derived
# record (e.g. a doi.org CSL lookup shown as a candidate).
PROVIDER_PRECEDENCE = ("structured", "crossref", "openalex", "web")

# Hard cap on merged candidates one workflow may hold.
MAX_WORKFLOW_CANDIDATES = 50

_MERGEABLE_FIELDS = ("title", "year", "venue", "url", "work_type", "snippet")


def _precedence(provider: str) -> int:
    try:
        return PROVIDER_PRECEDENCE.index(provider)
    except ValueError:
        return len(PROVIDER_PRECEDENCE)


def _merge_key(record: ProviderRecord) -> str:
    return f"doi:{record.doi}" if record.doi else f"pid:{record.provider_id}"


def _record_value(record: ProviderRecord, field_name: str):
    value = getattr(record, field_name)
    if field_name == "authors":
        return list(value) if value else None
    if isinstance(value, str):
        return value.strip() or None
    return value


class _Bucket:
    def __init__(self, key: str):
        self.key = key
        self.records: list[ProviderRecord] = []
        self.rrf = 0.0

    def add(self, record: ProviderRecord, *, rrf_contribution: float) -> None:
        self.records.append(record)
        self.rrf += rrf_contribution

    def ordered_records(self) -> list[ProviderRecord]:
        return sorted(
            self.records,
            key=lambda r: (_precedence(r.provider), r.rank, r.provider_id),
        )

    def best_provider(self) -> str:
        return min((r.provider for r in self.records), key=_precedence)


def _build_candidate(
    bucket: _Bucket, *, candidate_id: str, workflow_id: str
) -> CitationCandidate:
    ordered = bucket.ordered_records()
    candidate = CitationCandidate(candidate_id=candidate_id, workflow_id=workflow_id)

    for record in ordered:
        if record.provider not in candidate.provider_ids:
            candidate.provider_ids[record.provider] = record.provider_id
        current_rank = candidate.provider_ranks.get(record.provider)
        if current_rank is None or record.rank < current_rank:
            candidate.provider_ranks[record.provider] = record.rank
        for key, value in record.identifiers.items():
            candidate.identifiers.setdefault(key, value)

    doi_values = {r.doi for r in ordered if r.doi}
    if doi_values:
        candidate.doi = ordered[0].doi or next(iter(sorted(doi_values)))

    for field_name in (*_MERGEABLE_FIELDS, "authors"):
        for record in ordered:
            value = _record_value(record, field_name)
            if value is None:
                continue
            existing = getattr(candidate, field_name)
            is_empty = existing in ("", None, [])
            if is_empty:
                setattr(candidate, field_name, value)
                candidate.field_provenance[field_name] = record.provider
            elif value != existing:
                conflicts = candidate.conflicts.setdefault(field_name, [])
                entry = {"provider": record.provider, "value": value}
                if entry not in conflicts:
                    conflicts.append(entry)
    return candidate


def _assign_related_groups(candidates: list[CitationCandidate]) -> None:
    """Group DOI-less candidates with look-alike candidates, non-destructively.

    Same normalized (non-empty) title plus a matching year or an author
    surname overlap forms one related-version group.
    """
    by_title: dict[str, list[CitationCandidate]] = defaultdict(list)
    for candidate in candidates:
        title_key = normalize_title(candidate.title)
        if title_key:
            by_title[title_key].append(candidate)

    group_counter = 0
    for title_key, members in by_title.items():
        if len(members) < 2:
            continue
        if all(m.doi for m in members):
            continue  # distinct DOIs are distinct works; nothing to relate
        for base in members:
            related = [base]
            for other in members:
                if other is base:
                    continue
                year_match = (
                    base.year is not None
                    and other.year is not None
                    and base.year == other.year
                )
                surnames_a = {a.split()[-1].casefold() for a in base.authors if a.strip()}
                surnames_b = {a.split()[-1].casefold() for a in other.authors if a.strip()}
                author_match = bool(surnames_a & surnames_b)
                no_signal = (
                    base.year is None or other.year is None
                ) and not (surnames_a and surnames_b)
                if year_match or author_match or no_signal:
                    related.append(other)
            if len(related) > 1:
                existing = next(
                    (m.related_group for m in related if m.related_group), None
                )
                if existing is None:
                    group_counter += 1
                    existing = f"related-{group_counter}"
                for member in related:
                    member.related_group = existing


def fuse_ranked_lists(
    ranked_lists: list[list[ProviderRecord]],
    *,
    query: str,
    workflow_id: str,
    limit: int = MAX_WORKFLOW_CANDIDATES,
) -> list[CitationCandidate]:
    """Fuse per-provider ranked lists into ordered workflow candidates.

    ``ranked_lists`` holds one list per (provider, query) call in that
    provider's own order. Deterministic: same input, same output.
    """
    buckets: dict[str, _Bucket] = {}
    for ranked in ranked_lists:
        seen_in_list: set[str] = set()
        for position, record in enumerate(ranked):
            key = _merge_key(record)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = buckets[key] = _Bucket(key)
            # A duplicate of the same work inside one ranked list contributes
            # only its best position to that list's RRF share.
            contribution = 0.0 if key in seen_in_list else 1.0 / (RRF_K + position + 1)
            seen_in_list.add(key)
            bucket.add(record, rrf_contribution=contribution)

    query_title = normalize_title(query)

    def sort_key(bucket: _Bucket):
        has_doi = any(r.doi for r in bucket.records)
        exact_title = query_title != "" and any(
            normalize_title(r.title) == query_title for r in bucket.records
        )
        return (
            -bucket.rrf,
            0 if has_doi else 1,
            0 if exact_title else 1,
            bucket.best_provider(),
            bucket.key,
        )

    ordered_buckets = sorted(buckets.values(), key=sort_key)[: max(1, limit)]
    candidates = [
        _build_candidate(
            bucket,
            candidate_id=f"c{i + 1}",
            workflow_id=workflow_id,
        )
        for i, bucket in enumerate(ordered_buckets)
    ]
    _assign_related_groups(candidates)
    return candidates
