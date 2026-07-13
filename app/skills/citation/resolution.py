"""Pure work-identity resolution contracts and blocking policy.

This module is deliberately independent of tools, sessions, providers and
storage.  It answers one narrow question: does a bibliographic record identify
the work *and manifestation* the user asked for?  Ranking may order records,
but it can never undo a blocking contradiction recorded here.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from typing import Callable, Literal, Sequence

from skills.citation.doi import canonicalize_doi
from skills.citation.normalize import normalize_title
from skills.citation.providers.base import ProviderRecord
from skills.citation.providers.net import (
    ProviderDisabled,
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
)
from skills.citation.types import ProviderState

IdentifierKind = Literal["doi", "arxiv"]
ClaimProvenance = Literal[
    "explicit_current_user", "visible_context", "provider_discovered"
]
ClaimStrength = Literal["hard", "preference"]
ConstraintField = Literal["year", "venue", "work_kind", "version_kind"]
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
MAX_CONSTRAINTS = 8
MAX_CONSTRAINT_VALUE = 256


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
    provenance: ClaimProvenance = "visible_context"

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
class WorkConstraint:
    field: ConstraintField
    value: str
    provenance: ClaimProvenance = "visible_context"
    requested_strength: ClaimStrength = "preference"
    effective_provenance: ClaimProvenance = "visible_context"
    effective_strength: ClaimStrength = "preference"
    host_verified: bool = False
    polarity: Literal["positive", "negative"] = "positive"

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _clean(
            self.value, limit=MAX_CONSTRAINT_VALUE, field_name="constraint value"
        ))

    @property
    def is_hard(self) -> bool:
        return (
            self.host_verified
            and self.effective_provenance == "explicit_current_user"
            and self.effective_strength == "hard"
            and self.polarity == "positive"
        )


@dataclass(frozen=True)
class WorkIntent:
    requested_label: str
    title: str = ""
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    work_type: str = ""
    identifiers: tuple[WorkIdentifier, ...] = ()
    constraints: tuple[WorkConstraint, ...] = ()
    binding_reason: str = ""
    negative_target: bool = False

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
            _clean(a, limit=MAX_AUTHOR, field_name="author") for a in self.authors
        ))
        if self.year is not None and not 1000 <= self.year <= 2999:
            raise ValueError("year is out of range")
        if len(self.identifiers) > MAX_IDENTIFIERS:
            raise ValueError("too many identifiers")
        if len(self.constraints) > MAX_CONSTRAINTS:
            raise ValueError("too many constraints")


@dataclass(frozen=True)
class HostIntentClaim:
    field: Literal["doi", "arxiv", "year", "venue", "work_kind", "version_kind", "original"]
    value: str
    polarity: Literal["positive", "negative"] = "positive"
    strength: ClaimStrength = "hard"
    span: tuple[int, int] | None = None
    target_hint: str = ""


@dataclass(frozen=True)
class BindingResult:
    intents: tuple[WorkIntent, ...]
    ambiguous: bool = False
    reason_code: str = "none"


class HostIntentBinder:
    """Bind independently extracted current-user claims to frozen intents.

    Exact identifiers are authoritative anchors.  A claim without an anchor
    may be injected into a single-item request, but is rejected for a
    multi-item batch unless its target hint uniquely matches one item.
    """

    def bind(
        self, intents: Sequence[WorkIntent], claims: Sequence[HostIntentClaim]
    ) -> BindingResult:
        bound = list(intents)
        ambiguous = False
        for claim in claims:
            targets = self._targets(bound, claim)
            if len(targets) != 1:
                ambiguous = True
                continue
            index = targets[0]
            intent = bound[index]
            if claim.polarity == "negative":
                bound[index] = replace(
                    intent, negative_target=True, binding_reason="negative_target"
                )
                continue
            if claim.field in {"doi", "arxiv"}:
                identifier = WorkIdentifier(
                    kind=claim.field,
                    value=claim.value,
                    provenance="explicit_current_user",
                )
                identifiers = tuple(
                    i for i in intent.identifiers
                    if not (i.kind == identifier.kind and i.value == identifier.value)
                ) + (identifier,)
                bound[index] = replace(intent, identifiers=identifiers)
                continue
            if claim.field == "original":
                # "original" has two materially different meanings.  The
                # extractor must turn it into work_kind or version_kind first.
                ambiguous = True
                continue
            constraint = WorkConstraint(
                field=claim.field,
                value=claim.value,
                provenance="explicit_current_user",
                requested_strength=claim.strength,
                effective_provenance="explicit_current_user",
                effective_strength=claim.strength,
                host_verified=True,
            )
            remaining = tuple(c for c in intent.constraints if c.field != claim.field)
            bound[index] = replace(intent, constraints=remaining + (constraint,))
        if ambiguous:
            bound = [replace(i, binding_reason="intent_binding_ambiguous") for i in bound]
            return BindingResult(tuple(bound), True, "intent_binding_ambiguous")
        return BindingResult(tuple(bound))

    @staticmethod
    def _targets(intents: Sequence[WorkIntent], claim: HostIntentClaim) -> list[int]:
        if len(intents) == 1:
            return [0]
        value = claim.value.casefold().strip()
        exact: list[int] = []
        if claim.field in {"doi", "arxiv"}:
            try:
                wanted = WorkIdentifier(claim.field, claim.value).value
            except ValueError:
                return []
            exact = [
                n for n, intent in enumerate(intents)
                if any(i.kind == claim.field and i.value == wanted for i in intent.identifiers)
            ]
        if len(exact) == 1:
            return exact
        hint = claim.target_hint.casefold().strip()
        if hint:
            matches = [
                n for n, intent in enumerate(intents)
                if hint in f"{intent.requested_label} {intent.title}".casefold()
            ]
            if len(matches) == 1:
                return matches
        # A year/venue shared by more than one item is not a target anchor.
        return []


@dataclass(frozen=True)
class ResolutionEvidence:
    provider_record_ids: tuple[str, ...] = ()
    field_comparisons: tuple[str, ...] = ()
    blocking_reason_codes: tuple[str, ...] = ()
    score: float = 0.0
    version_reason_codes: tuple[str, ...] = ()


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
    queries: tuple[str, ...]


class ResolutionPolicy:
    """Versioned, conservative identity policy.

    Generic references such as "this paper" do *not* select published/VoR.
    Likewise, an unqualified "original" never selects original-work or
    earliest-manifestation semantics.  Both cases require clarification.
    """

    version = "2026-07-13.1"
    minimum_title_similarity = 0.88
    winning_margin = 0.08
    online_print_year_tolerance = 1


def _tokens(value: str) -> set[str]:
    return set(normalize_title(value).split())


def _title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return max(seq, jac)


def _author_overlap(expected: Sequence[str], actual: Sequence[str]) -> bool:
    if not expected:
        return True
    actual_tokens = set().union(*(_tokens(a) for a in actual)) if actual else set()
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


def evaluate_record(
    intent: WorkIntent, record: ProviderRecord, *, policy: ResolutionPolicy | None = None
) -> ResolutionDecision:
    policy = policy or ResolutionPolicy()
    reasons: list[str] = []
    comparisons: list[str] = []
    if intent.binding_reason:
        return ResolutionDecision("insufficient_intent", intent.binding_reason)
    if intent.negative_target:
        return ResolutionDecision("insufficient_intent", "negative_target")
    if not intent.title and not intent.identifiers:
        return ResolutionDecision("insufficient_intent", "insufficient_identity_anchor")

    exact_identifier = False
    for identifier in intent.identifiers:
        if identifier.kind == "doi" and record.doi:
            exact_identifier = canonicalize_doi(record.doi) == identifier.value
            if not exact_identifier:
                reasons.append("identifier_mismatch")
    similarity = _title_similarity(intent.title, record.title) if intent.title else 1.0
    comparisons.append(f"title_similarity:{similarity:.3f}")
    if intent.title and similarity < policy.minimum_title_similarity:
        reasons.append("title_mismatch")
    if intent.authors and not _author_overlap(intent.authors, record.authors):
        reasons.append("author_mismatch")
    if intent.year is not None and record.year is not None:
        delta = abs(intent.year - record.year)
        comparisons.append(f"year_delta:{delta}")

    version = infer_version_kind(record)
    for constraint in intent.constraints:
        if not constraint.is_hard:
            continue
        if constraint.field == "year" and record.year is not None:
            try:
                wanted = int(constraint.value)
            except ValueError:
                reasons.append("invalid_year_constraint")
            else:
                delta = abs(wanted - record.year)
                if delta > policy.online_print_year_tolerance:
                    reasons.append("hard_year_mismatch")
                elif delta == 1:
                    comparisons.append("online_print_year_tolerance")
        elif constraint.field == "venue":
            if normalize_title(constraint.value) not in normalize_title(record.venue):
                reasons.append("hard_venue_mismatch")
        elif constraint.field == "version_kind" and constraint.value == "earliest":
            pass  # compared across surviving manifestations in decide_resolution
        elif constraint.field == "version_kind" and constraint.value != version:
            reasons.append("hard_version_mismatch")
        elif constraint.field == "work_kind" and constraint.value == "original_research":
            type_text = f"{record.work_type} {record.title}".casefold()
            if any(x in type_text for x in ("review", "introduction", "monograph", "tutorial", "repost", "posted-content")):
                reasons.append("not_original_research")

    if reasons:
        status: DecisionStatus = "identity_conflict" if exact_identifier or any(
            r.startswith("hard_") or r in {"identifier_mismatch", "not_original_research"}
            for r in reasons
        ) else "not_found"
        priority = next(
            (code for code in ("not_original_research", "hard_version_mismatch", "hard_venue_mismatch", "hard_year_mismatch", "identifier_mismatch", "title_mismatch", "author_mismatch") if code in reasons),
            reasons[0],
        )
        return ResolutionDecision(
            status, priority, record=record,
            evidence=ResolutionEvidence(
                provider_record_ids=(record.provider_id,),
                field_comparisons=tuple(comparisons),
                blocking_reason_codes=tuple(reasons),
                score=similarity,
            ),
        )
    return ResolutionDecision(
        "eligible", "unique_strong_match", record=record,
        evidence=ResolutionEvidence(
            provider_record_ids=(record.provider_id,),
            field_comparisons=tuple(comparisons), score=similarity,
            version_reason_codes=(f"version:{version}",),
        ),
    )


def decide_resolution(
    intent: WorkIntent,
    records: Sequence[ProviderRecord],
    *,
    policy: ResolutionPolicy | None = None,
) -> ResolutionDecision:
    """Evaluate all records and require one work and one version."""
    policy = policy or ResolutionPolicy()
    if intent.binding_reason or intent.negative_target:
        return evaluate_record(intent, ProviderRecord("none", "none", 0), policy=policy)
    if not records:
        return ResolutionDecision("not_found", "no_provider_records")
    decisions = [evaluate_record(intent, record, policy=policy) for record in records]
    eligible = [d for d in decisions if d.status == "eligible" and d.record is not None]
    if not eligible:
        conflicts = [d for d in decisions if d.status == "identity_conflict"]
        return conflicts[0] if conflicts else decisions[0]

    # Deduplicate the same canonical identity seen at multiple providers.
    unique: dict[tuple[str, str], ResolutionDecision] = {}
    for decision in eligible:
        record = decision.record
        assert record is not None
        key = ("doi", canonicalize_doi(record.doi) or "") if record.doi else (
            "provider", record.provider_id
        )
        current = unique.get(key)
        if current is None or decision.evidence.score > current.evidence.score:
            unique[key] = decision
    eligible = sorted(unique.values(), key=lambda d: d.evidence.score, reverse=True)
    if len(eligible) == 1:
        return eligible[0]

    versions = {infer_version_kind(d.record) for d in eligible if d.record is not None}
    earliest = next((
        c for c in intent.constraints
        if c.field == "version_kind" and c.value == "earliest" and c.is_hard
    ), None)
    if earliest is not None:
        dated = [d for d in eligible if d.record is not None and d.record.year is not None]
        if not dated:
            return ResolutionDecision("ambiguous", "earliest_manifestation_unknown", alternatives=tuple(d.record for d in eligible if d.record is not None))
        first_year = min(d.record.year for d in dated)
        first = [d for d in dated if d.record.year == first_year]
        if len(first) == 1:
            return first[0]
        return ResolutionDecision("ambiguous", "multiple_earliest_manifestations", alternatives=tuple(d.record for d in first if d.record is not None))
    has_explicit_version = any(
        c.field == "version_kind" and c.host_verified for c in intent.constraints
    )
    if len(versions) > 1 and not has_explicit_version:
        return ResolutionDecision(
            "ambiguous", "version_clarification_required",
            alternatives=tuple(d.record for d in eligible if d.record is not None),
        )
    if eligible[0].evidence.score - eligible[1].evidence.score < policy.winning_margin:
        return ResolutionDecision(
            "ambiguous", "multiple_plausible_records",
            alternatives=tuple(d.record for d in eligible if d.record is not None),
        )
    return eligible[0]


class WorkResolver:
    """Bounded, deterministic multi-provider resolver.

    Discovery providers run concurrently and are treated symmetrically.  A
    DOI winner is always re-fetched through doi.org and evaluated again; a
    discovery ranking score can therefore never authorize persistence.
    """

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
        self._providers = [
            ("crossref", crossref),
            ("datacite", datacite),
        ]
        if openalex is not None:
            self._providers.append(("openalex", openalex))
        self._doi_org = doi_org
        self._rows = max(1, min(rows_per_query, 20))
        self._metrics = metrics or (lambda _event, _values: None)

    @staticmethod
    def queries_for(intent: WorkIntent) -> tuple[str, ...]:
        exact = [i.value for i in intent.identifiers]
        title = intent.title.strip()
        author = intent.authors[0].strip() if intent.authors else ""
        qualifiers = " ".join(
            value for value in (title, author, str(intent.year or ""), intent.venue) if value
        ).strip()
        queries: list[str] = []
        if exact:
            queries.append(exact[0])
        if qualifiers and qualifiers not in queries:
            queries.append(qualifiers)
        if title and author and len(queries) < 2:
            fallback = f"{title} {author}".strip()
            if fallback not in queries:
                queries.append(fallback)
        return tuple(queries[:2])

    async def resolve(self, intent: WorkIntent) -> WorkResolution:
        if intent.binding_reason or intent.negative_target:
            decision = ResolutionDecision(
                "insufficient_intent",
                intent.binding_reason or "negative_target",
            )
            return WorkResolution(decision, (), ())
        queries = self.queries_for(intent)
        if not queries:
            return WorkResolution(
                ResolutionDecision("insufficient_intent", "insufficient_identity_anchor"),
                (),
                (),
            )

        async def call(name: str, provider, query: str):
            try:
                records = await provider.search(query, rows=self._rows)
                return records, ProviderState(name, "ok" if records else "empty")
            except ProviderDisabled:
                return [], ProviderState(name, "disabled")
            except ProviderRateLimited:
                return [], ProviderState(name, "rate_limited")
            except ProviderTimeout:
                return [], ProviderState(name, "timeout")
            except ProviderError:
                return [], ProviderState(name, "error")

        tasks = [call(name, provider, query) for query in queries for name, provider in self._providers]
        results = await asyncio.gather(*tasks)
        states = tuple(state for _records, state in results)
        records = [record for provider_records, _state in results for record in provider_records]
        self._metrics("resolver_provider_phase", {
            "queries": len(queries), "records": len(records), "states": [s.status for s in states]
        })
        if not records and states and all(s.status in {"error", "timeout", "rate_limited"} for s in states):
            return WorkResolution(
                ResolutionDecision("provider_failed", "all_providers_failed"), states, queries
            )

        decision = decide_resolution(intent, records)
        if decision.status != "eligible" or decision.record is None:
            return WorkResolution(decision, states, queries)
        winner = decision.record
        if not winner.doi:
            return WorkResolution(
                ResolutionDecision(
                    "unsupported", "unsupported_no_doi", record=winner,
                    evidence=decision.evidence,
                ),
                states,
                queries,
            )
        try:
            csl = await self._doi_org.fetch_structured(winner.doi)
        except ProviderRateLimited:
            return WorkResolution(
                ResolutionDecision("provider_failed", "doi_refetch_rate_limited"),
                states + (ProviderState("doi.org", "rate_limited"),), queries,
            )
        except ProviderTimeout:
            return WorkResolution(
                ResolutionDecision("provider_failed", "doi_refetch_timeout"),
                states + (ProviderState("doi.org", "timeout"),), queries,
            )
        except ProviderError:
            return WorkResolution(
                ResolutionDecision("verification_failed", "doi_refetch_failed"),
                states + (ProviderState("doi.org", "error"),), queries,
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
            relations=dict(winner.relations),
            field_provenance={
                "doi": "doi.org", "title": "doi.org", "authors": "doi.org",
                "year": "doi.org", "venue": "doi.org", "work_type": "doi.org",
            },
        )
        verified_decision = evaluate_record(intent, verified)
        if verified_decision.status != "eligible":
            verified_decision = ResolutionDecision(
                "verification_failed",
                "refetch_identity_conflict",
                record=verified,
                evidence=verified_decision.evidence,
            )
        return WorkResolution(
            verified_decision,
            states + (ProviderState("doi.org", "ok"),),
            queries,
        )
