"""Typed containers for the citation workflow.

Session-scoped workflow objects (:class:`CitationCandidate`,
:class:`CitationMatch`) are opaque-ID, in-memory records owned by the
Coordinator; they carry no schema version because they are never persisted.
Only persisted formats (:class:`SourceRef` and the bundle sidecar built from
it) carry ``schema_version`` — currently :data:`PERSIST_SCHEMA_VERSION`.

Invariants enforced here:
  * A :class:`CitationResult` whose status is not ``confirmed`` always has
    ``accepted_doi is None`` — failures never leak a DOI as "accepted".
  * ``identity_verified`` means the DOI and the bibliographic pipeline agree
    on the identity of the record; it never claims the source supports any
    particular statement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal

# Version stamped into every persisted artifact (SourceRef JSON, sidecar).
PERSIST_SCHEMA_VERSION = 1

# The only verification levels a SourceRef can carry.
VerificationLevel = Literal["identity_verified", "user_supplied_unverified"]

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
    (never destructively resolved). ``related_group`` links candidates that
    look like versions of the same work (e.g. preprint vs published) without
    merging them.
    """

    candidate_id: str
    workflow_id: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str | None = None
    url: str | None = None
    snippet: str = ""
    provider_ids: dict[str, str] = field(default_factory=dict)
    identifiers: dict[str, str] = field(default_factory=dict)
    provider_ranks: dict[str, int] = field(default_factory=dict)
    field_provenance: dict[str, str] = field(default_factory=dict)
    conflicts: dict[str, list] = field(default_factory=dict)
    related_group: str | None = None

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

    Produced by ``/citation select``; invalidated by any later select, search,
    or cancel. Bibliographic fields are nullable — a missing value means the
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
    Persisted (in bundle sidecars and turn records), so it carries
    ``schema_version``. ``verification_level`` is strictly identity-level:
    ``identity_verified`` proves the DOI and bibliographic pipeline agree,
    nothing more.
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
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SourceRef":
        """Rehydrate from persisted JSON; missing fields are treated as empty."""
        level = data.get("verification_level")
        if level not in ("identity_verified", "user_supplied_unverified"):
            level = "user_supplied_unverified"
        year = data.get("year")
        return cls(
            source_id=str(data.get("source_id", "")),
            doi=data.get("doi") or None,
            title=str(data.get("title", "")),
            authors=[str(a) for a in data.get("authors", []) or []],
            year=int(year) if isinstance(year, int) else None,
            venue=str(data.get("venue", "") or ""),
            work_type=str(data.get("work_type", "") or ""),
            url=data.get("url") or None,
            verification_level=level,
            provenance=str(data.get("provenance", "") or ""),
            bundle_path=data.get("bundle_path") or None,
            schema_version=int(data.get("schema_version", PERSIST_SCHEMA_VERSION)),
        )


@dataclass
class CitationResult:
    """Outcome of one ``/citation confirm`` (or terminal workflow event).

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
    message: str = ""

    def __post_init__(self) -> None:
        if self.status != "confirmed" and self.accepted_doi is not None:
            raise ValueError(
                f"CitationResult(status={self.status!r}) must not carry an "
                f"accepted_doi (got {self.accepted_doi!r})"
            )
        if self.status == "confirmed" and not self.accepted_doi:
            raise ValueError("confirmed CitationResult requires accepted_doi")
