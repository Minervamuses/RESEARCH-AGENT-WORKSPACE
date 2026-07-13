"""Typed containers for the citation workflow.

Session-scoped workflow objects (:class:`CitationCandidate`,
:class:`CitationMatch`) are opaque-ID, in-memory records owned by the
Coordinator; they carry no schema version because they are never persisted.
Persisted formats (:class:`SourceRef` and the bundle sidecar built from it)
carry :data:`PERSIST_SCHEMA_VERSION`; the ephemeral tool-to-finalizer
:class:`ConfirmBatchOutcome` has an independent version contract.

Invariants enforced here:
  * A :class:`CitationResult` whose status is not ``confirmed`` always has
    ``accepted_doi is None`` — failures never leak a DOI as "accepted".
  * ``identity_verified`` means the DOI and the bibliographic pipeline agree
    on the identity of the record; it never claims the source supports any
    particular statement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import re
from typing import Literal

# Version stamped into every persisted artifact (SourceRef JSON, sidecar).
PERSIST_SCHEMA_VERSION = 1
BUNDLE_SCHEMA_V2 = 2
SUPPORTED_PERSIST_SCHEMA_VERSIONS = frozenset({PERSIST_SCHEMA_VERSION, BUNDLE_SCHEMA_V2})

# Version for the ephemeral, tool-to-finalizer confirm receipt. This is not a
# persisted bundle schema and deliberately evolves independently.
CONFIRM_RECEIPT_SCHEMA_VERSION = 1
CONFIRM_RECEIPT_KIND = "citation_confirm_receipt"
# v2 adds "pending": matches resolved by this call but not saved by it, so
# the finalizer can deterministically report an interrupted save. The batch
# artifact is consumed within the session; no persisted data migrates.
CONFIRM_BATCH_SCHEMA_VERSION = 2
CONFIRM_BATCH_KIND = "citation_confirm_receipt_batch"
SAVE_BATCH_SCHEMA_VERSION = 1
SAVE_BATCH_KIND = "citation_save_batch"

# The only verification level a SourceRef can carry: the DOI and the
# bibliographic pipeline agree on the identity of the record.
VerificationLevel = Literal[
    "identity_verified", "doi_identity_verified", "authority_metadata_verified"
]


@dataclass(frozen=True)
class CanonicalIdentity:
    """Namespaced, authoritative identity for a citable manifestation."""

    kind: Literal["doi", "arxiv", "url", "venue"]
    value: str

    def __post_init__(self) -> None:
        from skills.citation.doi import canonicalize_doi

        value = self.value.strip()
        if self.kind == "doi":
            value = canonicalize_doi(value) or ""
        if not value:
            raise ValueError("canonical identity requires a valid value")
        object.__setattr__(self, "value", value)

    @property
    def key(self) -> str:
        # Preserve historical DOI hashes/source IDs.
        return self.value if self.kind == "doi" else f"{self.kind}:{self.value}"

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "value": self.value}


@dataclass(frozen=True)
class VenueAnnotation:
    """Deterministic classification from the bundled venue catalog.

    This is discovery-only evidence. It is never persisted into a verified
    source and an unclassified venue deliberately carries no inferred tier.
    """

    canonical_name: str
    kind: str = "unclassified"
    tier: str | None = None
    source: str = ""
    catalog_version: str = ""

    @property
    def classified(self) -> bool:
        return self.kind != "unclassified"


@dataclass(frozen=True)
class RankingEvidence:
    """Explainable, ephemeral evidence used to order discovery candidates."""

    rrf_score: float
    title_relevance: float
    matched_query: str
    provider_count: int
    final_score: float
    mode: str


# Terminal states of one confirm attempt (or the workflow as a whole).
CitationStatus = Literal[
    "confirmed",
    "cancelled",
    "no_doi",
    "provider_failed",
    "verification_failed",
    "storage_failed",
    "invalid_state",
]

ConfirmFailureStatus = Literal[
    "invalid_state",
    "no_doi",
    "provider_failed",
    "verification_failed",
    "storage_failed",
]

CONFIRM_FAILURE_REASON_CODES = frozenset({
    "stale_match",
    "structured_lookup_failed",
    "bibtex_lookup_failed",
    "doi_mismatch",
    "bibtex_doi_mismatch",
    "parse_failed",
    "payload_too_large",
    "not_exactly_one_entry",
    "nonempty_preamble",
    "bundle_conflict",
    "write_failed",
    # save-time selection failures (keyed by candidate id, not match id)
    "unknown_candidate",
    "no_doi",
    "doi_lookup_failed",
})

# Distinct provider outcomes; empty and failed must never be conflated.
ProviderStatus = Literal["ok", "empty", "error", "rate_limited", "timeout", "disabled"]


@dataclass(frozen=True)
class ProviderState:
    """Outcome of one provider call within a workflow step."""

    provider: str
    status: ProviderStatus
    detail: str = ""

    def to_dict(self) -> dict:
        return {"provider": self.provider, "status": self.status, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict) -> "ProviderState":
        return cls(
            provider=str(data.get("provider", "")),
            status=data.get("status", "error"),
            detail=str(data.get("detail", "")),
        )


@dataclass(frozen=True)
class PublishedDateFilter:
    """Inclusive publication-date window applied to discovery.

    ``date_from``/``date_to`` (ISO ``YYYY-MM-DD``) feed the providers' native
    date filters; ``year_from``/``year_to`` bound the fail-closed post-filter
    run over the fused candidates. Fail-closed means a candidate whose year is
    unknown, or outside the window, never pretends to satisfy the filter.
    """

    date_from: str | None = None
    date_to: str | None = None
    year_from: int | None = None
    year_to: int | None = None

    @classmethod
    def within_years(
        cls, years: int, *, today: date | None = None
    ) -> "PublishedDateFilter":
        """Window ending today (UTC) and starting ``years`` years earlier."""
        if years < 1:
            raise ValueError("published_within_years must be >= 1")
        today = today or datetime.now(timezone.utc).date()
        try:
            start = today.replace(year=today.year - years)
        except ValueError:  # Feb 29 minus N years
            start = today.replace(year=today.year - years, day=today.day - 1)
        return cls(
            date_from=start.isoformat(),
            date_to=today.isoformat(),
            year_from=start.year,
            year_to=today.year,
        )

    @classmethod
    def from_year_range(
        cls, year_from: int | None, year_to: int | None
    ) -> "PublishedDateFilter":
        """Whole-year window; either bound may be open."""
        if year_from is None and year_to is None:
            raise ValueError("year range requires year_from and/or year_to")
        if year_from is not None and year_to is not None and year_from > year_to:
            raise ValueError("year_from must not exceed year_to")
        return cls(
            date_from=f"{year_from:04d}-01-01" if year_from is not None else None,
            date_to=f"{year_to:04d}-12-31" if year_to is not None else None,
            year_from=year_from,
            year_to=year_to,
        )

    def admits_year(self, year: int | None) -> bool:
        """Fail-closed: an unknown year never satisfies an active filter."""
        if year is None:
            return False
        if self.year_from is not None and year < self.year_from:
            return False
        if self.year_to is not None and year > self.year_to:
            return False
        return True

    def describe(self) -> str:
        return f"{self.date_from or '...'} .. {self.date_to or '...'}"


@dataclass
class CitationCandidate:
    """One discovery result inside a workflow generation.

    ``candidate_id`` is opaque and only valid for the workflow generation it
    was minted in. ``provider_ids`` are namespaced (``"crossref:..."``,
    ``"openalex:W..."``) so IDs from different providers can never collide.
    ``field_provenance`` maps a metadata field name to the provider that
    supplied its current value; ``conflicts`` keeps every conflicting value
    (never destructively resolved). ``related_group`` and
    ``related_candidate_ids`` link independently selectable versions of the
    same work without merging them. Venue/ranking annotations are ephemeral.
    """

    candidate_id: str
    workflow_id: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str | None = None
    url: str | None = None
    work_type: str = ""
    snippet: str = ""
    provider_ids: dict[str, str] = field(default_factory=dict)
    identifiers: dict[str, str] = field(default_factory=dict)
    provider_ranks: dict[str, int] = field(default_factory=dict)
    field_provenance: dict[str, str] = field(default_factory=dict)
    conflicts: dict[str, list] = field(default_factory=dict)
    related_group: str | None = None
    related_candidate_ids: list[str] = field(default_factory=list)
    is_group_representative: bool = True
    venue_annotation: VenueAnnotation | None = None
    ranking_evidence: RankingEvidence | None = None

    def short_label(self) -> str:
        bits = [self.title or "(untitled)"]
        meta: list[str] = []
        if self.authors:
            head = self.authors[0]
            meta.append(head + (" et al." if len(self.authors) > 1 else ""))
        if self.year:
            meta.append(str(self.year))
        if meta:
            bits.append("(" + ", ".join(meta) + ")")
        return " ".join(bits)


@dataclass
class CitationMatch:
    """A confirmable resolution of one candidate to a canonical DOI.

    Produced by the ``select`` action; invalidated by any later select,
    search, or cancel. Bibliographic fields are nullable — a missing value means the
    lookup did not report it, never a guess.
    """

    match_id: str
    candidate_id: str
    canonical_doi: str
    registration_agency: str = ""
    title: str = ""
    authors: list[str] | None = None
    year: int | None = None
    venue: str | None = None
    work_type: str | None = None
    lookup_provenance: str = ""


@dataclass(frozen=True)
class VerificationCheck:
    """One named check inside a confirm-time verification report."""

    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict) -> "VerificationCheck":
        return cls(
            name=str(data.get("name", "")),
            passed=bool(data.get("passed", False)),
            detail=str(data.get("detail", "")),
        )


@dataclass
class VerificationReport:
    """Checks and warnings from one confirm attempt.

    ``warnings`` are non-blocking (e.g. title/author/year/venue conflicts);
    ``codes`` are machine-readable markers such as
    ``doi_injected_from_verified_lookup``.
    """

    checks: list[VerificationCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict:
        return {
            "checks": [check.to_dict() for check in self.checks],
            "warnings": list(self.warnings),
            "codes": list(self.codes),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VerificationReport":
        return cls(
            checks=[VerificationCheck.from_dict(c) for c in data.get("checks", [])],
            warnings=[str(w) for w in data.get("warnings", [])],
            codes=[str(c) for c in data.get("codes", [])],
        )


@dataclass
class SourceRef:
    """A stable, citable reference to one verified (or user-supplied) source.

    The only object the chat layer may cite via ``[[cite:<source-id>]]``.
    Persisted (in bundle sidecars), so it carries ``schema_version``.
    ``verification_level`` is strictly identity-level: ``identity_verified``
    proves the DOI and bibliographic pipeline agree, nothing more.
    """

    source_id: str
    doi: str | None
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    work_type: str = ""
    url: str | None = None
    verification_level: VerificationLevel = "identity_verified"
    provenance: str = ""
    bundle_path: str | None = None
    schema_version: int = PERSIST_SCHEMA_VERSION
    canonical_identity: CanonicalIdentity | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "doi": self.doi,
            "title": self.title,
            "authors": list(self.authors),
            "year": self.year,
            "venue": self.venue,
            "work_type": self.work_type,
            "url": self.url,
            "verification_level": self.verification_level,
            "provenance": self.provenance,
            "bundle_path": self.bundle_path,
            "canonical_identity": (
                self.canonical_identity.to_dict() if self.canonical_identity else None
            ),
        }


def source_identity(ref: SourceRef) -> CanonicalIdentity | None:
    """Return a validated live identity, deriving it only for legacy DOI refs."""
    from skills.citation.doi import canonicalize_doi

    if ref.canonical_identity is not None:
        return ref.canonical_identity
    if ref.schema_version == PERSIST_SCHEMA_VERSION:
        doi = canonicalize_doi(ref.doi)
        if doi:
            return CanonicalIdentity("doi", doi)
    return None


def is_citable_source(ref: SourceRef) -> bool:
    """Central fail-closed verification-level/identity shape policy."""
    from skills.citation.doi import canonicalize_doi

    identity = source_identity(ref)
    if identity is None:
        return False
    doi = canonicalize_doi(ref.doi)
    if ref.verification_level == "identity_verified":
        return ref.schema_version == 1 and identity.kind == "doi" and doi == identity.value
    if ref.verification_level == "doi_identity_verified":
        return ref.schema_version == 2 and identity.kind == "doi" and doi == identity.value
    if ref.verification_level == "authority_metadata_verified":
        return ref.schema_version == 2 and identity.kind != "doi" and ref.doi is None
    return False



@dataclass
class CitationResult:
    """Outcome of one ``confirm`` action (or terminal workflow event).

    ``accepted_doi`` is only ever set on ``confirmed`` — enforced at
    construction so no failure path can report a half-accepted DOI.
    """

    status: CitationStatus
    accepted_doi: str | None = None
    attempts: int = 1
    provider_states: list[ProviderState] = field(default_factory=list)
    verification: VerificationReport | None = None
    source: SourceRef | None = None
    bundle_path: str | None = None
    reason_code: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        if self.status != "confirmed" and self.accepted_doi is not None:
            raise ValueError(
                f"CitationResult(status={self.status!r}) must not carry an "
                f"accepted_doi (got {self.accepted_doi!r})"
            )
        if self.status == "confirmed" and not self.accepted_doi:
            raise ValueError("confirmed CitationResult requires accepted_doi")


@dataclass(frozen=True)
class ConfirmReceipt:
    """Trusted facts emitted by a successful ``confirm`` tool call.

    The LangChain tool places the JSON-safe representation in a ToolMessage
    artifact. Chat finalization validates it against the live SourceRegistry
    before rendering it; model-facing prose is never parsed as a receipt.
    """

    source_id: str
    accepted_doi: str
    bundle_path: str
    verification_level: VerificationLevel
    cite_marker: str
    warnings: tuple[str, ...] = ()
    schema_version: int = field(default=CONFIRM_RECEIPT_SCHEMA_VERSION, init=False)
    kind: str = field(default=CONFIRM_RECEIPT_KIND, init=False)

    def to_artifact(self) -> dict:
        return {
            "kind": self.kind,
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "accepted_doi": self.accepted_doi,
            "bundle_path": self.bundle_path,
            "verification_level": self.verification_level,
            "cite_marker": self.cite_marker,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_artifact(cls, artifact: object) -> "ConfirmReceipt":
        """Strictly decode one supported receipt artifact."""
        if not isinstance(artifact, Mapping):
            raise ValueError("confirm receipt artifact must be a mapping")
        if artifact.get("kind") != CONFIRM_RECEIPT_KIND:
            raise ValueError("unknown confirm receipt kind")
        if artifact.get("schema_version") != CONFIRM_RECEIPT_SCHEMA_VERSION:
            raise ValueError("unsupported confirm receipt schema version")
        expected_fields = {
            "kind",
            "schema_version",
            "source_id",
            "accepted_doi",
            "bundle_path",
            "verification_level",
            "cite_marker",
            "warnings",
        }
        if set(artifact) != expected_fields:
            raise ValueError("confirm receipt artifact has unsupported fields")

        def required_text(key: str) -> str:
            value = artifact.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"confirm receipt requires non-empty {key}")
            return value

        source_id = required_text("source_id")
        verification_level = required_text("verification_level")
        if verification_level != "identity_verified":
            raise ValueError("unsupported confirm receipt verification level")
        cite_marker = required_text("cite_marker")
        if cite_marker != f"[[cite:{source_id}]]":
            raise ValueError("confirm receipt cite marker does not match source id")
        raw_warnings = artifact.get("warnings", [])
        if not isinstance(raw_warnings, (list, tuple)) or not all(
            isinstance(warning, str) for warning in raw_warnings
        ):
            raise ValueError("confirm receipt warnings must be strings")
        return cls(
            source_id=source_id,
            accepted_doi=required_text("accepted_doi"),
            bundle_path=required_text("bundle_path"),
            verification_level="identity_verified",
            cite_marker=cite_marker,
            warnings=tuple(raw_warnings),
        )


@dataclass(frozen=True)
class ConfirmFailure:
    """Fail-closed facts for one unsuccessful confirm or save attempt.

    ``match_id`` is the failing identifier: a match id for confirm failures,
    or a candidate id for save-time selection failures. Only stable system
    codes cross the trusted artifact boundary. Provider messages and other
    arbitrary prose deliberately have no field here.
    """

    match_id: str
    status: ConfirmFailureStatus
    reason_code: str

    def __post_init__(self) -> None:
        if not self.match_id.strip():
            raise ValueError("confirm failure requires non-empty match_id")
        if self.status not in {
            "invalid_state",
            "no_doi",
            "provider_failed",
            "verification_failed",
            "storage_failed",
        }:
            raise ValueError("unsupported confirm failure status")
        if self.reason_code not in CONFIRM_FAILURE_REASON_CODES:
            raise ValueError("unsupported confirm failure reason code")

    def to_artifact(self) -> dict:
        return {
            "match_id": self.match_id,
            "status": self.status,
            "reason_code": self.reason_code,
        }

    @classmethod
    def from_artifact(cls, artifact: object) -> "ConfirmFailure":
        if not isinstance(artifact, Mapping):
            raise ValueError("confirm failure must be a mapping")
        if set(artifact) != {"match_id", "status", "reason_code"}:
            raise ValueError("confirm failure has unsupported fields")

        def required_text(key: str) -> str:
            value = artifact.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"confirm failure requires non-empty {key}")
            return value

        status = required_text("status")
        reason_code = required_text("reason_code")
        return cls(
            match_id=required_text("match_id"),
            status=status,
            reason_code=reason_code,
        )


@dataclass(frozen=True)
class PendingMatchNote:
    """One match resolved by this tool call but not saved by it.

    Carries opaque workflow ids only — never a DOI or provider text. The
    finalizer validates each note against the live workflow state before
    rendering, so a stale note can never be shown as continuable.
    """

    candidate_id: str
    match_id: str
    needs_disambiguation: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("pending match note requires non-empty candidate_id")
        if not self.match_id.strip():
            raise ValueError("pending match note requires non-empty match_id")

    def to_artifact(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "match_id": self.match_id,
            "needs_disambiguation": self.needs_disambiguation,
        }

    @classmethod
    def from_artifact(cls, artifact: object) -> "PendingMatchNote":
        if not isinstance(artifact, Mapping):
            raise ValueError("pending match note must be a mapping")
        if set(artifact) != {"candidate_id", "match_id", "needs_disambiguation"}:
            raise ValueError("pending match note has unsupported fields")

        def required_text(key: str) -> str:
            value = artifact.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"pending match note requires non-empty {key}")
            return value

        needs_disambiguation = artifact.get("needs_disambiguation")
        if not isinstance(needs_disambiguation, bool):
            raise ValueError(
                "pending match note needs_disambiguation must be a bool"
            )
        return cls(
            candidate_id=required_text("candidate_id"),
            match_id=required_text("match_id"),
            needs_disambiguation=needs_disambiguation,
        )


@dataclass(frozen=True)
class ConfirmBatchOutcome:
    """One tool call's trusted receipts, sanitized failures, and pending notes."""

    receipts: tuple[ConfirmReceipt, ...] = ()
    failures: tuple[ConfirmFailure, ...] = ()
    pending: tuple[PendingMatchNote, ...] = ()
    schema_version: int = field(default=CONFIRM_BATCH_SCHEMA_VERSION, init=False)
    kind: str = field(default=CONFIRM_BATCH_KIND, init=False)

    def to_artifact(self) -> dict:
        return {
            "kind": self.kind,
            "schema_version": self.schema_version,
            "receipts": [receipt.to_artifact() for receipt in self.receipts],
            "failures": [failure.to_artifact() for failure in self.failures],
            "pending": [note.to_artifact() for note in self.pending],
        }

    @classmethod
    def from_artifact(cls, artifact: object) -> "ConfirmBatchOutcome":
        """Strictly decode a complete batch; one invalid item rejects all."""
        if not isinstance(artifact, Mapping):
            raise ValueError("confirm batch artifact must be a mapping")
        if artifact.get("kind") != CONFIRM_BATCH_KIND:
            raise ValueError("unknown confirm batch kind")
        if artifact.get("schema_version") != CONFIRM_BATCH_SCHEMA_VERSION:
            raise ValueError("unsupported confirm batch schema version")
        if set(artifact) != {
            "kind", "schema_version", "receipts", "failures", "pending"
        }:
            raise ValueError("confirm batch artifact has unsupported fields")
        raw_receipts = artifact.get("receipts")
        raw_failures = artifact.get("failures")
        raw_pending = artifact.get("pending")
        if (
            not isinstance(raw_receipts, list)
            or not isinstance(raw_failures, list)
            or not isinstance(raw_pending, list)
        ):
            raise ValueError(
                "confirm batch receipts, failures, and pending must be lists"
            )
        return cls(
            receipts=tuple(
                ConfirmReceipt.from_artifact(item) for item in raw_receipts
            ),
            failures=tuple(
                ConfirmFailure.from_artifact(item) for item in raw_failures
            ),
            pending=tuple(
                PendingMatchNote.from_artifact(item) for item in raw_pending
            ),
        )


SaveItemStatus = Literal[
    "saved", "reused", "insufficient_intent", "ambiguous", "not_found",
    "identity_conflict", "unsupported_identifier", "unsupported_no_doi",
    "provider_failed", "verification_failed", "storage_failed",
]


@dataclass(frozen=True)
class SaveReceipt:
    source_id: str
    canonical_identity: CanonicalIdentity
    doi: str | None
    title: str
    year: int | None
    work_type: str
    bundle_path: str
    verification_level: VerificationLevel
    cite_marker: str

    def __post_init__(self) -> None:
        if not self.source_id or self.cite_marker != f"[[cite:{self.source_id}]]":
            raise ValueError("save receipt source/cite marker mismatch")
        if self.canonical_identity.kind == "doi":
            from skills.citation.doi import canonicalize_doi
            if canonicalize_doi(self.doi) != self.canonical_identity.value:
                raise ValueError("save receipt DOI identity mismatch")
        elif self.doi is not None:
            raise ValueError("non-DOI save receipt must not carry DOI")

    def to_artifact(self) -> dict:
        return {
            "source_id": self.source_id,
            "canonical_identity": self.canonical_identity.to_dict(),
            "doi": self.doi,
            "title": self.title,
            "year": self.year,
            "work_type": self.work_type,
            "bundle_path": self.bundle_path,
            "verification_level": self.verification_level,
            "cite_marker": self.cite_marker,
        }

    @classmethod
    def from_artifact(cls, artifact: object) -> "SaveReceipt":
        fields = {"source_id", "canonical_identity", "doi", "title", "year", "work_type", "bundle_path", "verification_level", "cite_marker"}
        if not isinstance(artifact, Mapping) or set(artifact) != fields:
            raise ValueError("invalid save receipt fields")
        raw_identity = artifact.get("canonical_identity")
        if not isinstance(raw_identity, Mapping) or set(raw_identity) != {"kind", "value"}:
            raise ValueError("invalid save receipt identity")
        text_fields = ("source_id", "title", "work_type", "bundle_path", "verification_level", "cite_marker")
        if not all(isinstance(artifact.get(key), str) for key in text_fields):
            raise ValueError("invalid save receipt text")
        doi, year = artifact.get("doi"), artifact.get("year")
        if doi is not None and not isinstance(doi, str):
            raise ValueError("invalid save receipt DOI")
        if year is not None and (not isinstance(year, int) or isinstance(year, bool)):
            raise ValueError("invalid save receipt year")
        return cls(
            artifact["source_id"], CanonicalIdentity(raw_identity["kind"], raw_identity["value"]),
            doi, artifact["title"], year, artifact["work_type"], artifact["bundle_path"],
            artifact["verification_level"], artifact["cite_marker"],
        )


@dataclass(frozen=True)
class SaveAlternative:
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    version_kind: str = "unknown"

    def to_artifact(self) -> dict:
        return {"title": self.title, "authors": list(self.authors), "year": self.year, "venue": self.venue, "version_kind": self.version_kind}

    @classmethod
    def from_artifact(cls, value: object) -> "SaveAlternative":
        if not isinstance(value, Mapping) or set(value) != {"title", "authors", "year", "venue", "version_kind"}:
            raise ValueError("invalid save alternative fields")
        if not isinstance(value["authors"], list) or not all(isinstance(a, str) for a in value["authors"]):
            raise ValueError("invalid save alternative authors")
        if not all(isinstance(value[k], str) for k in ("title", "venue", "version_kind")):
            raise ValueError("invalid save alternative text")
        if value["year"] is not None and (not isinstance(value["year"], int) or isinstance(value["year"], bool)):
            raise ValueError("invalid save alternative year")
        return cls(value["title"], tuple(value["authors"]), value["year"], value["venue"], value["version_kind"])


@dataclass(frozen=True)
class SaveItemOutcome:
    request_index: int
    requested_label: str
    status: SaveItemStatus
    reason_code: str
    receipt: SaveReceipt | None = None
    alternatives: tuple[SaveAlternative, ...] = ()

    def __post_init__(self) -> None:
        if self.request_index < 0 or not self.requested_label:
            raise ValueError("invalid save item identity")
        if not re.fullmatch(r"[a-z0-9_]+", self.reason_code):
            raise ValueError("invalid save reason code")
        if (self.status in {"saved", "reused"}) != (self.receipt is not None):
            raise ValueError("save receipt/status mismatch")

    def to_artifact(self) -> dict:
        return {
            "request_index": self.request_index, "requested_label": self.requested_label,
            "status": self.status, "reason_code": self.reason_code,
            "receipt": self.receipt.to_artifact() if self.receipt else None,
            "alternatives": [item.to_artifact() for item in self.alternatives],
        }

    @classmethod
    def from_artifact(cls, value: object) -> "SaveItemOutcome":
        fields = {"request_index", "requested_label", "status", "reason_code", "receipt", "alternatives"}
        if not isinstance(value, Mapping) or set(value) != fields:
            raise ValueError("invalid save item fields")
        if not isinstance(value["request_index"], int) or isinstance(value["request_index"], bool):
            raise ValueError("invalid request index")
        if not all(isinstance(value[k], str) for k in ("requested_label", "status", "reason_code")):
            raise ValueError("invalid save item text")
        if value["status"] not in SaveItemStatus.__args__:
            raise ValueError("invalid save item status")
        if not isinstance(value["alternatives"], list):
            raise ValueError("invalid save alternatives")
        receipt = None if value["receipt"] is None else SaveReceipt.from_artifact(value["receipt"])
        return cls(
            value["request_index"], value["requested_label"], value["status"], value["reason_code"],
            receipt, tuple(SaveAlternative.from_artifact(item) for item in value["alternatives"]),
        )


@dataclass(frozen=True)
class SaveBatchOutcome:
    batch_id: str
    batch_status: Literal["attempted", "rejected"]
    batch_reason_code: Literal["none", "workflow_busy", "mutation_already_attempted"]
    items: tuple[SaveItemOutcome, ...] = ()
    schema_version: int = field(default=SAVE_BATCH_SCHEMA_VERSION, init=False)
    kind: str = field(default=SAVE_BATCH_KIND, init=False)

    def __post_init__(self) -> None:
        if not self.batch_id:
            raise ValueError("save batch requires batch_id")
        if self.batch_status == "attempted":
            if self.batch_reason_code != "none" or not self.items:
                raise ValueError("invalid attempted save batch")
        elif self.batch_status == "rejected":
            if self.items or self.batch_reason_code not in {"workflow_busy", "mutation_already_attempted"}:
                raise ValueError("invalid rejected save batch")
        else:
            raise ValueError("invalid save batch status")
        indices = [item.request_index for item in self.items]
        if len(indices) != len(set(indices)):
            raise ValueError("duplicate request index")

    def to_artifact(self) -> dict:
        return {
            "kind": self.kind, "schema_version": self.schema_version,
            "batch_id": self.batch_id, "batch_status": self.batch_status,
            "batch_reason_code": self.batch_reason_code,
            "items": [item.to_artifact() for item in self.items],
        }

    @classmethod
    def from_artifact(cls, artifact: object) -> "SaveBatchOutcome":
        fields = {"kind", "schema_version", "batch_id", "batch_status", "batch_reason_code", "items"}
        if not isinstance(artifact, Mapping) or set(artifact) != fields:
            raise ValueError("invalid save batch fields")
        if artifact.get("kind") != SAVE_BATCH_KIND or artifact.get("schema_version") != SAVE_BATCH_SCHEMA_VERSION:
            raise ValueError("unsupported save batch kind/schema")
        if not all(isinstance(artifact.get(k), str) for k in ("batch_id", "batch_status", "batch_reason_code")):
            raise ValueError("invalid save batch text")
        if not isinstance(artifact["items"], list):
            raise ValueError("save batch items must be a list")
        return cls(
            artifact["batch_id"], artifact["batch_status"], artifact["batch_reason_code"],
            tuple(SaveItemOutcome.from_artifact(item) for item in artifact["items"]),
        )
