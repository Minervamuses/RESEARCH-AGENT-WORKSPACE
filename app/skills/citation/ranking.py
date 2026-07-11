"""Deterministic cross-provider fusion, relevance scoring, and work grouping.

Identity fusion remains deliberately strict: only a canonical DOI or the same
namespaced provider ID merges records.  Distinct versions of a work retain
their own candidate IDs and are grouped non-destructively for presentation.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Literal

from skills.citation.normalize import normalize_title
from skills.citation.providers.base import ProviderRecord
from skills.citation.types import CitationCandidate, RankingEvidence
from skills.citation.venue import annotate_venue

RRF_K = 60
RankingMode = Literal["rrf", "lexical"]

PROVIDER_PRECEDENCE = ("structured", "crossref", "openalex", "web")

# The workflow exposes at most 50 canonical works while retaining bounded,
# independently selectable versions behind those works.
MAX_WORKFLOW_WORKS = 50
MAX_WORKFLOW_VERSIONS = 100
# Backward-compatible name used by callers/tests that mean visible works.
MAX_WORKFLOW_CANDIDATES = MAX_WORKFLOW_WORKS

_MERGEABLE_FIELDS = ("title", "year", "venue", "url", "work_type", "snippet")
_WORD_OR_CJK_RE = re.compile(r"[a-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]+")
_EN_STOPWORDS = frozenset({
    "a", "an", "and", "for", "in", "of", "on", "the", "to", "with",
    "paper", "papers", "study", "studies",
})


def normalize_ranking_mode(value: str | None) -> RankingMode:
    mode = (value or "rrf").strip().casefold()
    if mode not in {"rrf", "lexical"}:
        raise ValueError("citation_ranking_mode must be 'rrf' or 'lexical'")
    return mode  # type: ignore[return-value]


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


def _text_tokens(raw: str | None) -> set[str]:
    normalized = normalize_title(raw)
    tokens: set[str] = set()
    for piece in _WORD_OR_CJK_RE.findall(normalized):
        if piece.isascii():
            if piece not in _EN_STOPWORDS:
                tokens.add(piece)
            continue
        chars = [ch for ch in piece if ch.strip()]
        if len(chars) == 1:
            tokens.add(chars[0])
        else:
            tokens.update("".join(chars[i:i + 2]) for i in range(len(chars) - 1))
    return tokens


def _token_f1(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    return 2.0 * overlap / (len(left) + len(right))


def _title_relevance(
    candidate: CitationCandidate, queries: tuple[str, ...]
) -> tuple[float, str]:
    title_tokens = _text_tokens(candidate.title)
    snippet_tokens = _text_tokens(candidate.snippet)
    best_score = 0.0
    best_query = queries[0] if queries else ""
    for index, query in enumerate(queries):
        if normalize_title(query) and normalize_title(query) == normalize_title(candidate.title):
            score = 1.0
        else:
            query_tokens = _text_tokens(query)
            title_score = _token_f1(query_tokens, title_tokens)
            snippet_score = 0.25 * _token_f1(query_tokens, snippet_tokens)
            score = max(title_score, snippet_score)
        # Expansion queries are useful translations, but cannot outweigh an
        # equally strong match to the user's original wording.
        if index > 0:
            score *= 0.9
        if score > best_score:
            best_score = score
            best_query = query
    return best_score, best_query


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


def _build_candidate(bucket: _Bucket, *, workflow_id: str) -> CitationCandidate:
    ordered = bucket.ordered_records()
    candidate = CitationCandidate(candidate_id="", workflow_id=workflow_id)

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
            if existing in ("", None, []):
                setattr(candidate, field_name, value)
                candidate.field_provenance[field_name] = record.provider
            elif value != existing:
                conflicts = candidate.conflicts.setdefault(field_name, [])
                entry = {"provider": record.provider, "value": value}
                if entry not in conflicts:
                    conflicts.append(entry)
    candidate.venue_annotation = annotate_venue(candidate.venue)
    return candidate


def _candidate_number(candidate: CitationCandidate) -> int:
    try:
        return int(candidate.candidate_id.removeprefix("c"))
    except ValueError:
        return 10**9


def _author_surnames(candidate: CitationCandidate) -> set[str]:
    return {
        author.strip().split()[-1].casefold()
        for author in candidate.authors
        if author.strip()
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _years_compatible(left: CitationCandidate, right: CitationCandidate) -> bool:
    return left.year is None or right.year is None or abs(left.year - right.year) <= 2


def _should_group(left: CitationCandidate, right: CitationCandidate) -> bool:
    title_left = normalize_title(left.title)
    title_right = normalize_title(right.title)
    if not title_left or not title_right or not _years_compatible(left, right):
        return False

    authors_left = _author_surnames(left)
    authors_right = _author_surnames(right)
    author_overlap = _jaccard(authors_left, authors_right)
    if title_left == title_right:
        if authors_left and authors_right:
            return author_overlap >= 0.5
        return (
            (left.doi is None or right.doi is None)
            and left.year is not None
            and left.year == right.year
        )
    return (
        _jaccard(_text_tokens(left.title), _text_tokens(right.title)) >= 0.9
        and author_overlap >= 0.7
    )


def _is_preprint_or_repository(candidate: CitationCandidate) -> bool:
    kind = candidate.venue_annotation.kind if candidate.venue_annotation else ""
    work_type = candidate.work_type.casefold()
    venue = candidate.venue.casefold()
    return (
        kind == "repository"
        or any(token in work_type for token in ("preprint", "posted-content", "repository"))
        or venue in {"arxiv", "ssrn"}
    )


def choose_version_representative(
    candidates: list[CitationCandidate],
) -> CitationCandidate:
    """Choose a display representative without merging or invalidating IDs."""
    return min(
        candidates,
        key=lambda candidate: (
            1 if _is_preprint_or_repository(candidate) else 0,
            0 if candidate.doi else 1,
            -len(candidate.provider_ids),
            _candidate_number(candidate),
            -(candidate.year or 0),
            candidate.doi or normalize_title(candidate.title),
        ),
    )


def assign_version_groups(candidates: list[CitationCandidate]) -> int:
    """Recompute non-destructive version groups over stable candidate IDs."""
    for candidate in candidates:
        candidate.related_group = None
        candidate.related_candidate_ids = []
        candidate.is_group_representative = True
        if candidate.venue_annotation is None:
            candidate.venue_annotation = annotate_venue(candidate.venue)

    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)

    for left in range(len(candidates)):
        for right in range(left + 1, len(candidates)):
            if _should_group(candidates[left], candidates[right]):
                union(left, right)

    groups: dict[int, list[CitationCandidate]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        groups[find(index)].append(candidate)

    grouped = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        grouped += 1
        members.sort(key=_candidate_number)
        group_id = f"related-{_candidate_number(members[0])}"
        representative = choose_version_representative(members)
        member_ids = [member.candidate_id for member in members]
        for member in members:
            member.related_group = group_id
            member.related_candidate_ids = [cid for cid in member_ids if cid != member.candidate_id]
            member.is_group_representative = member is representative
    return grouped


def representative_candidates(candidates: list[CitationCandidate]) -> list[CitationCandidate]:
    """Return one representative per group, ordered by the group's first hit."""
    groups: dict[str, list[CitationCandidate]] = {}
    order: list[str] = []
    for candidate in candidates:
        key = candidate.related_group or f"candidate:{candidate.candidate_id}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(candidate)
    return [choose_version_representative(groups[key]) for key in order]


def limit_to_canonical_works(
    candidates: list[CitationCandidate],
    *,
    work_limit: int = MAX_WORKFLOW_WORKS,
    version_limit: int = MAX_WORKFLOW_VERSIONS,
) -> list[CitationCandidate]:
    """Keep representatives for the first works, then bounded extra versions.

    Reserving one slot per work before retaining alternatives prevents a dense
    version group near the top of the ranking from consuming the entire
    version budget and hiding otherwise eligible works.
    """
    ranked = list(candidates)
    assign_version_groups(ranked)
    work_cap = max(1, work_limit)
    version_cap = max(1, version_limit)
    visible_cap = min(work_cap, version_cap)
    allowed: list[str] = []
    groups: dict[str, list[CitationCandidate]] = defaultdict(list)
    for candidate in ranked:
        key = candidate.related_group or f"candidate:{candidate.candidate_id}"
        groups[key].append(candidate)
        if key not in allowed and len(allowed) < visible_cap:
            allowed.append(key)

    allowed_set = set(allowed)
    required = {id(choose_version_representative(groups[key])) for key in allowed}
    selected = set(required)
    for candidate in ranked:
        if len(selected) >= version_cap:
            break
        key = candidate.related_group or f"candidate:{candidate.candidate_id}"
        if key in allowed_set:
            selected.add(id(candidate))

    kept = [candidate for candidate in ranked if id(candidate) in selected]
    assign_version_groups(kept)
    return kept


def fuse_ranked_lists(
    ranked_lists: list[list[ProviderRecord]],
    *,
    query: str,
    workflow_id: str,
    query_variants: list[str] | tuple[str, ...] = (),
    ranking_mode: str = "rrf",
    limit: int = MAX_WORKFLOW_WORKS,
    version_limit: int = MAX_WORKFLOW_VERSIONS,
) -> list[CitationCandidate]:
    """Fuse provider lists, score them, and retain bounded canonical works."""
    mode = normalize_ranking_mode(ranking_mode)
    buckets: dict[str, _Bucket] = {}
    for ranked in ranked_lists:
        seen_in_list: set[str] = set()
        for position, record in enumerate(ranked):
            key = _merge_key(record)
            bucket = buckets.setdefault(key, _Bucket(key))
            contribution = 0.0 if key in seen_in_list else 1.0 / (RRF_K + position + 1)
            seen_in_list.add(key)
            bucket.add(record, rrf_contribution=contribution)

    queries = tuple(dict.fromkeys([query, *query_variants]))
    query_title = normalize_title(query)
    built: list[tuple[_Bucket, CitationCandidate, bool]] = []
    for bucket in buckets.values():
        candidate = _build_candidate(bucket, workflow_id=workflow_id)
        relevance, matched_query = _title_relevance(candidate, queries)
        final_score = bucket.rrf * (0.75 + 0.25 * relevance) if mode == "lexical" else bucket.rrf
        candidate.ranking_evidence = RankingEvidence(
            rrf_score=bucket.rrf,
            title_relevance=relevance,
            matched_query=matched_query,
            provider_count=len(candidate.provider_ids),
            final_score=final_score,
            mode=mode,
        )
        exact = bool(query_title) and normalize_title(candidate.title) == query_title
        built.append((bucket, candidate, exact))

    def sort_key(item: tuple[_Bucket, CitationCandidate, bool]):
        bucket, candidate, exact = item
        evidence = candidate.ranking_evidence
        assert evidence is not None
        if mode == "lexical":
            return (
                -evidence.final_score,
                0 if candidate.doi else 1,
                0 if exact else 1,
                bucket.best_provider(),
                bucket.key,
            )
        return (
            -bucket.rrf,
            0 if candidate.doi else 1,
            0 if exact else 1,
            bucket.best_provider(),
            bucket.key,
        )

    ordered = [item[1] for item in sorted(built, key=sort_key)]
    for index, candidate in enumerate(ordered):
        candidate.candidate_id = f"c{index + 1}"
    kept = limit_to_canonical_works(
        ordered, work_limit=limit, version_limit=version_limit
    )
    for index, candidate in enumerate(kept):
        candidate.candidate_id = f"c{index + 1}"
    assign_version_groups(kept)
    return kept
