"""Bibliographic target resolution for model-selected citation work.

The model owns the semantic decision about which work and manifestation the
user requested.  This module only turns that selection into a provider record:
exact DOI/arXiv identifiers take precedence, while descriptive fields support
a best-match fallback for records without a stable identifier.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable, Literal, Sequence

from skills.citation.doi import canonicalize_doi
from skills.citation.normalize import normalize_title
from skills.citation.providers.base import BibliographicQuery, ProviderRecord
from skills.citation.providers.doi_org import DoiNotFound
from skills.citation.providers.net import (
    ProviderDisabled,
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
)
from skills.citation.types import ProviderState

IdentifierKind = Literal["doi", "arxiv"]
RequestedVersionKind = Literal[
    "published", "preprint", "repository", "repost", "earliest"
]
VersionKind = Literal["published", "preprint", "repository", "repost", "unknown"]
DecisionStatus = Literal[
    "eligible",
    "insufficient_intent",
    "ambiguous",
    "not_found",
    "identity_conflict",
    "unsupported",
    "provider_failed",
    "verification_failed",
]

MAX_REQUESTED_LABEL = 160
MAX_TITLE = 512
MAX_AUTHORS = 32
MAX_AUTHOR = 256
MAX_VENUE = 256
MAX_WORK_TYPE = 256
MAX_IDENTIFIERS = 8
MAX_IDENTIFIER_VALUE = 2048


def _clean(value: str, *, limit: int, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    text = unicodedata.normalize("NFKC", value).strip()
    if any(ord(ch) < 0x20 and ch not in "\t\n\r" for ch in text) or "\x00" in text:
        raise ValueError(f"{field_name} contains control characters")
    if len(text) > limit:
        raise ValueError(f"{field_name} exceeds {limit} characters")
    return text


def normalize_arxiv(value: str) -> str:
    text = value.strip().removeprefix("arXiv:").removeprefix("arxiv:")
    text = re.sub(r"v\d+$", "", text, flags=re.IGNORECASE)
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})", text, re.I):
        raise ValueError("invalid arXiv identifier")
    return text.casefold()


@dataclass(frozen=True)
class WorkIdentifier:
    kind: IdentifierKind
    value: str

    def __post_init__(self) -> None:
        value = _clean(self.value, limit=MAX_IDENTIFIER_VALUE, field_name="identifier")
        if self.kind == "doi":
            value = canonicalize_doi(value) or ""
            if not value:
                raise ValueError("invalid DOI identifier")
        elif self.kind == "arxiv":
            value = normalize_arxiv(value)
        else:
            raise ValueError("unsupported identifier kind")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class WorkIntent:
    """A target selected by the model from the visible conversation."""

    requested_label: str
    title: str = ""
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    work_type: str = ""
    work_kind: Literal["original_research"] | None = None
    version_kind: RequestedVersionKind | None = None
    identifiers: tuple[WorkIdentifier, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_label", _clean(
            self.requested_label, limit=MAX_REQUESTED_LABEL, field_name="requested_label"
        ))
        object.__setattr__(self, "title", _clean(
            self.title, limit=MAX_TITLE, field_name="title"
        ))
        object.__setattr__(self, "venue", _clean(
            self.venue, limit=MAX_VENUE, field_name="venue"
        ))
        object.__setattr__(self, "work_type", _clean(
            self.work_type, limit=MAX_WORK_TYPE, field_name="work_type"
        ))
        if len(self.authors) > MAX_AUTHORS:
            raise ValueError("too many authors")
        object.__setattr__(self, "authors", tuple(
            _clean(author, limit=MAX_AUTHOR, field_name="author")
            for author in self.authors
        ))
        if self.year is not None and not 1000 <= self.year <= 2999:
            raise ValueError("year is out of range")
        if len(self.identifiers) > MAX_IDENTIFIERS:
            raise ValueError("too many identifiers")


@dataclass(frozen=True)
class ResolutionEvidence:
    provider_record_ids: tuple[str, ...] = ()
    field_comparisons: tuple[str, ...] = ()
    score: float = 0.0


@dataclass(frozen=True)
class ResolutionDecision:
    status: DecisionStatus
    reason_code: str
    record: ProviderRecord | None = None
    alternatives: tuple[ProviderRecord, ...] = ()
    evidence: ResolutionEvidence = field(default_factory=ResolutionEvidence)


@dataclass(frozen=True)
class WorkResolution:
    decision: ResolutionDecision
    provider_states: tuple[ProviderState, ...]


class ResolutionPolicy:
    """Small set of thresholds for descriptive best-match fallback."""

    version = "2026-07-24.1"
    minimum_title_similarity = 0.88
    online_print_year_tolerance = 1


def _tokens(value: str) -> set[str]:
    return set(normalize_title(value).split())


def _title_similarity(a: str, b: str) -> float:
    normalized_a, normalized_b = normalize_title(a), normalize_title(b)
    if not normalized_a or not normalized_b:
        return 0.0
    sequence = SequenceMatcher(None, normalized_a, normalized_b).ratio()
    tokens_a, tokens_b = set(normalized_a.split()), set(normalized_b.split())
    jaccard = (
        len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
        if tokens_a | tokens_b
        else 0.0
    )
    return max(sequence, jaccard)


def _author_overlap(expected: Sequence[str], actual: Sequence[str]) -> bool:
    if not expected:
        return True
    actual_tokens = set().union(*(_tokens(author) for author in actual)) if actual else set()
    return any(_tokens(author) & actual_tokens for author in expected)


def infer_version_kind(record: ProviderRecord) -> VersionKind:
    explicit = getattr(record, "version_kind", "")
    if explicit in {"published", "preprint", "repository", "repost"}:
        return explicit
    text = f"{record.work_type} {record.venue} {record.url or ''}".casefold()
    if "posted-content" in text or "repost" in text:
        return "repost"
    if "arxiv" in text or "preprint" in text:
        return "preprint"
    if "repository" in text:
        return "repository"
    if record.venue or record.doi:
        return "published"
    return "unknown"


def _record_arxiv(record: ProviderRecord) -> str:
    raw = record.identifiers.get("arxiv", "")
    if not raw:
        return ""
    try:
        return normalize_arxiv(raw)
    except ValueError:
        return ""


def evaluate_record(
    intent: WorkIntent,
    record: ProviderRecord,
    *,
    policy: ResolutionPolicy | None = None,
) -> ResolutionDecision:
    """Score a descriptive fallback candidate against the model's selection.

    Stable identifiers are handled before fuzzy discovery.  Consequently these
    comparisons help locate a record; they are not a second authorization or
    current-turn provenance check.
    """

    policy = policy or ResolutionPolicy()
    if not intent.title and not intent.identifiers:
        return ResolutionDecision("insufficient_intent", "insufficient_identity_anchor")

    comparisons: list[str] = []
    reasons: list[str] = []
    exact_identifier = False
    for identifier in intent.identifiers:
        if identifier.kind == "doi":
            accepted = {
                normalized
                for normalized in (
                    canonicalize_doi(record.doi),
                    *(canonicalize_doi(alias) for alias in record.aliases),
                )
                if normalized
            }
            matched = identifier.value in accepted
        else:
            matched = identifier.value == _record_arxiv(record)
        exact_identifier = exact_identifier or matched
        if not matched:
            reasons.append("identifier_mismatch")

    similarity = _title_similarity(intent.title, record.title) if intent.title else 1.0
    comparisons.append(f"title_similarity:{similarity:.3f}")
    if not intent.identifiers:
        if intent.title and similarity < policy.minimum_title_similarity:
            reasons.append("title_mismatch")
        if intent.authors and not _author_overlap(intent.authors, record.authors):
            reasons.append("author_mismatch")
        if intent.year is not None and record.year is not None:
            delta = abs(intent.year - record.year)
            comparisons.append(f"year_delta:{delta}")
            if delta > policy.online_print_year_tolerance:
                reasons.append("year_mismatch")
        if intent.venue and record.venue:
            wanted_venue = normalize_title(intent.venue)
            actual_venue = normalize_title(record.venue)
            if wanted_venue not in actual_venue and actual_venue not in wanted_venue:
                reasons.append("venue_mismatch")
        if intent.version_kind not in {None, "earliest"}:
            if infer_version_kind(record) != intent.version_kind:
                reasons.append("version_mismatch")
        if intent.work_kind == "original_research":
            type_text = f"{record.work_type} {record.title}".casefold()
            if any(word in type_text for word in (
                "review", "introduction", "monograph", "tutorial", "repost",
                "posted-content",
            )):
                reasons.append("not_original_research")

    if reasons:
        status: DecisionStatus = "identity_conflict" if exact_identifier else "not_found"
        reason = next(
            (
                code
                for code in (
                    "identifier_mismatch",
                    "not_original_research",
                    "version_mismatch",
                    "title_mismatch",
                    "author_mismatch",
                    "year_mismatch",
                    "venue_mismatch",
                )
                if code in reasons
            ),
            reasons[0],
        )
        return ResolutionDecision(
            status,
            reason,
            record=record,
            evidence=ResolutionEvidence(
                provider_record_ids=(record.provider_id,),
                field_comparisons=tuple(comparisons),
                score=similarity,
            ),
        )

    bonus = 0.0
    if intent.authors and record.authors:
        bonus += 0.03
    if intent.year is not None and record.year == intent.year:
        bonus += 0.03
    if intent.venue and record.venue:
        bonus += 0.02
    if intent.version_kind not in {None, "earliest"}:
        bonus += 0.04
    return ResolutionDecision(
        "eligible",
        "exact_identifier" if exact_identifier else "best_match",
        record=record,
        evidence=ResolutionEvidence(
            provider_record_ids=(record.provider_id,),
            field_comparisons=tuple(comparisons),
            score=similarity + bonus,
        ),
    )


def decide_resolution(
    intent: WorkIntent,
    records: Sequence[ProviderRecord],
    *,
    policy: ResolutionPolicy | None = None,
) -> ResolutionDecision:
    """Return the best deterministic record for a model-selected target."""

    policy = policy or ResolutionPolicy()
    if not records:
        return ResolutionDecision("not_found", "no_provider_records")
    decisions = [evaluate_record(intent, record, policy=policy) for record in records]
    eligible = [decision for decision in decisions if decision.status == "eligible"]
    if not eligible:
        conflicts = [decision for decision in decisions if decision.status == "identity_conflict"]
        alternatives = tuple(record for record in records[:5])
        chosen = conflicts[0] if conflicts else decisions[0]
        return ResolutionDecision(
            chosen.status,
            chosen.reason_code,
            record=chosen.record,
            alternatives=alternatives,
            evidence=chosen.evidence,
        )

    unique: dict[tuple[str, str], ResolutionDecision] = {}
    for decision in eligible:
        record = decision.record
        assert record is not None
        doi = canonicalize_doi(record.doi)
        arxiv = _record_arxiv(record)
        key = ("doi", doi) if doi else (("arxiv", arxiv) if arxiv else (
            record.provider, record.provider_id
        ))
        current = unique.get(key)
        if current is None or decision.evidence.score > current.evidence.score:
            unique[key] = decision
    eligible = list(unique.values())

    if intent.version_kind == "earliest":
        eligible.sort(key=lambda decision: (
            decision.record.year is None,
            decision.record.year or 9999,
            -decision.evidence.score,
            decision.record.rank,
            decision.record.provider,
        ))
    else:
        eligible.sort(key=lambda decision: (
            -decision.evidence.score,
            decision.record.rank,
            decision.record.provider,
            decision.record.provider_id,
        ))
    return eligible[0]


class WorkResolver:
    """Resolve exact identifiers or perform bounded descriptive discovery."""

    def __init__(
        self,
        *,
        crossref,
        datacite,
        doi_org,
        openalex=None,
        rows_per_query: int = 10,
        metrics: Callable[[str, dict], None] | None = None,
    ):
        self._providers = [("crossref", crossref), ("datacite", datacite)]
        if openalex is not None:
            self._providers.append(("openalex", openalex))
        self._doi_org = doi_org
        self._rows = max(1, min(rows_per_query, 20))
        self._metrics = metrics or (lambda _event, _values: None)

    @staticmethod
    def bibliographic_query_for(intent: WorkIntent) -> BibliographicQuery:
        return BibliographicQuery(
            title=intent.title,
            authors=intent.authors,
            year=intent.year,
            venue=intent.venue,
            work_type=intent.work_type,
        )

    @staticmethod
    def _exact_identifiers(
        intent: WorkIntent,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        dois = tuple(dict.fromkeys(
            identifier.value for identifier in intent.identifiers
            if identifier.kind == "doi"
        ))
        arxiv = tuple(dict.fromkeys(
            identifier.value for identifier in intent.identifiers
            if identifier.kind == "arxiv"
        ))
        return dois, arxiv

    async def _resolve_exact_doi(self, doi: str) -> WorkResolution:
        try:
            csl = await self._doi_org.fetch_structured(doi)
        except DoiNotFound:
            return WorkResolution(
                ResolutionDecision("not_found", "exact_doi_not_found"),
                (ProviderState("doi.org", "empty"),),
            )
        except ProviderRateLimited:
            return WorkResolution(
                ResolutionDecision("provider_failed", "doi_refetch_rate_limited"),
                (ProviderState("doi.org", "rate_limited"),),
            )
        except ProviderTimeout:
            return WorkResolution(
                ResolutionDecision("provider_failed", "doi_refetch_timeout"),
                (ProviderState("doi.org", "timeout"),),
            )
        except ProviderError:
            return WorkResolution(
                ResolutionDecision("verification_failed", "doi_refetch_failed"),
                (ProviderState("doi.org", "error"),),
            )
        identifiers = {"doi": csl.doi}
        arxiv_match = re.fullmatch(r"10\.48550/arxiv\.(.+)", doi, re.IGNORECASE)
        if arxiv_match:
            try:
                identifiers["arxiv"] = normalize_arxiv(arxiv_match.group(1))
            except ValueError:
                pass
        record = ProviderRecord(
            provider="doi.org",
            provider_id=f"doi.org:{csl.doi}",
            rank=0,
            title=csl.title,
            authors=list(csl.authors),
            year=csl.year,
            venue=csl.venue,
            doi=csl.doi,
            url=csl.url,
            work_type=csl.work_type,
            version_kind=("preprint" if "arxiv" in identifiers else ""),
            identifiers=identifiers,
            aliases=(doi,) if csl.doi != doi else (),
            field_provenance={
                field: "doi.org"
                for field in ("doi", "title", "authors", "year", "venue", "work_type")
            },
        )
        return WorkResolution(
            ResolutionDecision(
                "eligible",
                "exact_identifier",
                record=record,
                evidence=ResolutionEvidence((record.provider_id,), score=1.0),
            ),
            (ProviderState("doi.org", "ok"),),
        )

    async def resolve(self, intent: WorkIntent) -> WorkResolution:
        exact_dois, exact_arxiv = self._exact_identifiers(intent)
        if len(exact_dois) > 1 or len(exact_arxiv) > 1:
            return WorkResolution(
                ResolutionDecision("identity_conflict", "multiple_exact_identifiers"),
                (),
            )
        if exact_dois and exact_arxiv:
            paired = f"10.48550/arxiv.{exact_arxiv[0]}".casefold()
            if exact_dois[0].casefold() != paired:
                return WorkResolution(
                    ResolutionDecision("ambiguous", "multiple_exact_identifiers"),
                    (),
                )
        if exact_dois:
            return await self._resolve_exact_doi(exact_dois[0])
        if exact_arxiv:
            return WorkResolution(
                ResolutionDecision("unsupported", "exact_arxiv_requires_authority"),
                (),
            )

        query = self.bibliographic_query_for(intent)
        if not query.title:
            return WorkResolution(
                ResolutionDecision("insufficient_intent", "insufficient_identity_anchor"),
                (),
            )

        async def call(name: str, provider):
            try:
                records = await provider.search_work(query, rows=self._rows)
                return records, ProviderState(name, "ok" if records else "empty")
            except ProviderDisabled:
                return [], ProviderState(name, "disabled")
            except ProviderRateLimited:
                return [], ProviderState(name, "rate_limited")
            except ProviderTimeout:
                return [], ProviderState(name, "timeout")
            except ProviderError:
                return [], ProviderState(name, "error")

        results = await asyncio.gather(*(
            call(name, provider) for name, provider in self._providers
        ))
        states = tuple(state for _records, state in results)
        records = [record for provider_records, _state in results for record in provider_records]
        self._metrics("resolver_provider_phase", {
            "providers": len(self._providers),
            "records": len(records),
            "states": [state.status for state in states],
        })
        if not records and states and all(
            state.status in {"error", "timeout", "rate_limited"} for state in states
        ):
            return WorkResolution(
                ResolutionDecision("provider_failed", "all_providers_failed"),
                states,
            )

        decision = decide_resolution(intent, records)
        if decision.status != "eligible" or decision.record is None:
            return WorkResolution(decision, states)
        winner = decision.record
        if not winner.doi:
            return WorkResolution(
                ResolutionDecision(
                    "unsupported",
                    "unsupported_no_doi",
                    record=winner,
                    alternatives=decision.alternatives,
                    evidence=decision.evidence,
                ),
                states,
            )

        try:
            csl = await self._doi_org.fetch_structured(winner.doi)
        except ProviderRateLimited:
            return WorkResolution(
                ResolutionDecision("provider_failed", "doi_refetch_rate_limited"),
                states + (ProviderState("doi.org", "rate_limited"),),
            )
        except ProviderTimeout:
            return WorkResolution(
                ResolutionDecision("provider_failed", "doi_refetch_timeout"),
                states + (ProviderState("doi.org", "timeout"),),
            )
        except ProviderError:
            return WorkResolution(
                ResolutionDecision("verification_failed", "doi_refetch_failed"),
                states + (ProviderState("doi.org", "error"),),
            )

        # Verify the discovery provider's DOI/title pair, not the model's
        # descriptive hints.  This is transport/metadata integrity, not target
        # authorization.
        if winner.title and _title_similarity(winner.title, csl.title) < ResolutionPolicy.minimum_title_similarity:
            return WorkResolution(
                ResolutionDecision("verification_failed", "refetch_identity_conflict"),
                states + (ProviderState("doi.org", "ok"),),
            )
        verified = ProviderRecord(
            provider="doi.org",
            provider_id=f"doi.org:{csl.doi}",
            rank=0,
            title=csl.title,
            authors=list(csl.authors),
            year=csl.year,
            venue=csl.venue,
            doi=csl.doi,
            url=csl.url,
            work_type=csl.work_type,
            version_kind=winner.version_kind,
            identifiers=dict(winner.identifiers),
            aliases=(winner.doi,) if csl.doi != winner.doi else (),
            relations=dict(winner.relations),
            field_provenance={
                field: "doi.org"
                for field in ("doi", "title", "authors", "year", "venue", "work_type")
            },
        )
        return WorkResolution(
            ResolutionDecision(
                "eligible",
                "best_match",
                record=verified,
                evidence=decision.evidence,
            ),
            states + (ProviderState("doi.org", "ok"),),
        )
