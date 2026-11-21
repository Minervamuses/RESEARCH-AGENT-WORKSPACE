"""Current citation domain and strict trusted-artifact types."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

SAVE_BATCH_SCHEMA_VERSION = 3
SAVE_BATCH_KIND = "citation_save_batch"
SAVE_RESULT_VERSION_KINDS = frozenset({
    "published", "preprint", "repository", "repost", "unknown",
})
CANONICAL_IDENTITY_KINDS = frozenset({"doi", "arxiv", "url", "venue"})
VERIFICATION_LEVELS = frozenset({
    "doi_identity_verified",
    "authority_metadata_verified",
})

VerificationLevel = Literal["doi_identity_verified", "authority_metadata_verified"]
ProviderStatus = Literal["ok", "empty", "error", "rate_limited", "timeout", "disabled"]


@dataclass(frozen=True)
class CanonicalIdentity:
    kind: Literal["doi", "arxiv", "url", "venue"]
    value: str

    def __post_init__(self):
        from skills.citation.doi import canonicalize_doi
        if self.kind not in CANONICAL_IDENTITY_KINDS or not isinstance(self.value, str):
            raise ValueError("canonical identity requires a supported string value")
        value = self.value.strip()
        if self.kind == "doi":
            value = canonicalize_doi(value) or ""
        if not value:
            raise ValueError("canonical identity requires a valid value")
        object.__setattr__(self, "value", value)

    @property
    def key(self):
        return self.value if self.kind == "doi" else f"{self.kind}:{self.value}"

    def to_dict(self):
        return {"kind": self.kind, "value": self.value}


def source_id_for(identity: CanonicalIdentity) -> str:
    """Stable session source ID for one canonical identity."""
    return f"src-{hashlib.sha256(identity.key.encode('utf-8')).hexdigest()[:12]}"


@dataclass(frozen=True)
class ProviderState:
    provider: str
    status: ProviderStatus
    detail: str = ""

    def to_dict(self):
        return {"provider": self.provider, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class PublishedDateFilter:
    date_from: str | None = None
    date_to: str | None = None
    year_from: int | None = None
    year_to: int | None = None

    @classmethod
    def from_year_range(cls, year_from, year_to):
        if year_from is None and year_to is None:
            raise ValueError("year range requires a bound")
        if year_from is not None and year_to is not None and year_from > year_to:
            raise ValueError("year_from must not exceed year_to")
        return cls(
            f"{year_from:04d}-01-01" if year_from is not None else None,
            f"{year_to:04d}-12-31" if year_to is not None else None,
            year_from, year_to,
        )

    def admits_year(self, year):
        return year is not None and (self.year_from is None or year >= self.year_from) and (self.year_to is None or year <= self.year_to)


@dataclass
class SourceRef:
    source_id: str
    doi: str | None
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    work_type: str = ""
    url: str | None = None
    verification_level: VerificationLevel = "doi_identity_verified"
    provenance: str = ""
    canonical_identity: CanonicalIdentity | None = None


def is_citable_source(ref: SourceRef):
    """A verified source: a DOI identity with its DOI, or a non-DOI authority record."""
    from skills.citation.doi import canonicalize_doi
    identity = ref.canonical_identity
    if identity is None:
        return False
    if ref.verification_level == "doi_identity_verified":
        return identity.kind == "doi" and canonicalize_doi(ref.doi) == identity.value
    return ref.verification_level == "authority_metadata_verified" and identity.kind != "doi" and ref.doi is None


# ``saved``/``reused``: in the project bibliography (desktop). ``verified``:
# citable for this task only, nothing written (no project bibliography).
SaveItemStatus = Literal["saved", "reused", "verified", "insufficient_intent", "ambiguous", "not_found", "identity_conflict", "unsupported_identifier", "unsupported_no_doi", "provider_failed", "verification_failed", "storage_failed", "internal_error"]


def _strict_fields(value, fields, label):
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"invalid {label} fields")


@dataclass(frozen=True)
class SaveReceipt:
    source_id: str
    canonical_identity: CanonicalIdentity
    doi: str | None
    title: str
    year: int | None
    work_type: str
    verification_level: VerificationLevel
    cite_marker: str
    version_kind: str = "unknown"

    def __post_init__(self):
        from skills.citation.doi import canonicalize_doi
        text_fields = (
            self.source_id,
            self.title,
            self.work_type,
            self.verification_level,
            self.cite_marker,
            self.version_kind,
        )
        if not all(isinstance(value, str) for value in text_fields):
            raise ValueError("save receipt text fields must be strings")
        if self.year is not None and type(self.year) is not int:
            raise ValueError("invalid save receipt year")
        if self.doi is not None and not isinstance(self.doi, str):
            raise ValueError("invalid save receipt DOI")
        if not self.source_id or self.cite_marker != f"[[cite:{self.source_id}]]":
            raise ValueError("save receipt source/cite marker mismatch")
        if self.canonical_identity.kind == "doi":
            if canonicalize_doi(self.doi) != self.canonical_identity.value:
                raise ValueError("save receipt DOI identity mismatch")
        elif self.doi is not None:
            raise ValueError("non-DOI receipt carries DOI")
        if self.verification_level not in VERIFICATION_LEVELS:
            raise ValueError("invalid save receipt verification level")
        if self.version_kind not in SAVE_RESULT_VERSION_KINDS:
            raise ValueError("invalid save receipt version kind")

    def to_artifact(self):
        return {"source_id": self.source_id, "canonical_identity": self.canonical_identity.to_dict(), "doi": self.doi, "title": self.title, "year": self.year, "work_type": self.work_type, "verification_level": self.verification_level, "cite_marker": self.cite_marker, "version_kind": self.version_kind}

    @classmethod
    def from_artifact(cls, value):
        fields = {"source_id", "canonical_identity", "doi", "title", "year", "work_type", "verification_level", "cite_marker", "version_kind"}
        _strict_fields(value, fields, "save receipt")
        raw = value["canonical_identity"]
        _strict_fields(raw, {"kind", "value"}, "canonical identity")
        if not all(isinstance(raw[key], str) for key in ("kind", "value")):
            raise ValueError("invalid canonical identity")
        if not all(isinstance(value[k], str) for k in ("source_id", "title", "work_type", "verification_level", "cite_marker", "version_kind")):
            raise ValueError("invalid save receipt text")
        if value["doi"] is not None and not isinstance(value["doi"], str):
            raise ValueError("invalid DOI")
        if value["year"] is not None and (not isinstance(value["year"], int) or isinstance(value["year"], bool)):
            raise ValueError("invalid year")
        return cls(value["source_id"], CanonicalIdentity(raw["kind"], raw["value"]), value["doi"], value["title"], value["year"], value["work_type"], value["verification_level"], value["cite_marker"], value["version_kind"])


@dataclass(frozen=True)
class SaveAlternative:
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    version_kind: str = "unknown"
    doi: str | None = None
    arxiv: str | None = None

    def __post_init__(self):
        if not all(isinstance(value, str) for value in (
            self.title, self.venue, self.version_kind,
        )):
            raise ValueError("invalid alternative text")
        if not isinstance(self.authors, tuple) or not all(
            isinstance(author, str) for author in self.authors
        ):
            raise ValueError("invalid alternative authors")
        if self.year is not None and type(self.year) is not int:
            raise ValueError("invalid alternative year")
        if self.doi is not None and not isinstance(self.doi, str):
            raise ValueError("invalid alternative DOI")
        if self.arxiv is not None and not isinstance(self.arxiv, str):
            raise ValueError("invalid alternative arXiv identifier")
        if self.version_kind not in SAVE_RESULT_VERSION_KINDS:
            raise ValueError("invalid alternative version kind")

    def to_artifact(self):
        return {"title": self.title, "authors": list(self.authors), "year": self.year, "venue": self.venue, "version_kind": self.version_kind, "doi": self.doi, "arxiv": self.arxiv}

    @classmethod
    def from_artifact(cls, value):
        _strict_fields(value, {"title", "authors", "year", "venue", "version_kind", "doi", "arxiv"}, "alternative")
        if not all(isinstance(value[key], str) for key in (
            "title", "venue", "version_kind",
        )):
            raise ValueError("invalid alternative text")
        if not isinstance(value["authors"], list) or not all(isinstance(x, str) for x in value["authors"]):
            raise ValueError("invalid authors")
        if value["year"] is not None and type(value["year"]) is not int:
            raise ValueError("invalid alternative year")
        if value["doi"] is not None and not isinstance(value["doi"], str):
            raise ValueError("invalid alternative DOI")
        if value["arxiv"] is not None and not isinstance(value["arxiv"], str):
            raise ValueError("invalid alternative arXiv identifier")
        return cls(value["title"], tuple(value["authors"]), value["year"], value["venue"], value["version_kind"], value["doi"], value["arxiv"])


BIBLIOGRAPHY_LINK_STATUSES = frozenset({"added", "existing"})


@dataclass(frozen=True)
class BibliographyLink:
    """Where one saved work lives in the project bibliography."""

    status: Literal["added", "existing"]
    path: str
    key: str

    def __post_init__(self):
        if self.status not in BIBLIOGRAPHY_LINK_STATUSES or not isinstance(self.path, str) or not self.path:
            raise ValueError("invalid bibliography link")
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("invalid bibliography key")

    def to_artifact(self):
        return {"status": self.status, "path": self.path, "key": self.key}

    @classmethod
    def from_artifact(cls, value):
        _strict_fields(value, {"status", "path", "key"}, "bibliography link")
        return cls(value["status"], value["path"], value["key"])


@dataclass(frozen=True)
class SaveItemOutcome:
    request_index: int
    requested_label: str
    status: SaveItemStatus
    reason_code: str
    receipt: SaveReceipt | None = None
    alternatives: tuple[SaveAlternative, ...] = ()
    bibliography: BibliographyLink | None = None

    def __post_init__(self):
        if (
            type(self.request_index) is not int
            or self.request_index < 0
            or not isinstance(self.requested_label, str)
            or not self.requested_label
            or not isinstance(self.reason_code, str)
            or not re.fullmatch(r"[a-z0-9_]+", self.reason_code)
        ):
            raise ValueError("invalid save item")
        if self.status not in SaveItemStatus.__args__:
            raise ValueError("invalid save item status")
        if (self.status in {"saved", "reused", "verified"}) != (self.receipt is not None):
            raise ValueError("save receipt/status mismatch")
        if (self.status in {"saved", "reused"}) != (self.bibliography is not None):
            raise ValueError("bibliography link/status mismatch")

    def to_artifact(self):
        return {"request_index": self.request_index, "requested_label": self.requested_label, "status": self.status, "reason_code": self.reason_code, "receipt": self.receipt.to_artifact() if self.receipt else None, "alternatives": [x.to_artifact() for x in self.alternatives], "bibliography": self.bibliography.to_artifact() if self.bibliography else None}

    @classmethod
    def from_artifact(cls, value):
        fields = {"request_index", "requested_label", "status", "reason_code", "receipt", "alternatives", "bibliography"}
        _strict_fields(value, fields, "save item")
        if (
            type(value["request_index"]) is not int
            or not isinstance(value["requested_label"], str)
            or not isinstance(value["status"], str)
            or not isinstance(value["reason_code"], str)
            or value["status"] not in SaveItemStatus.__args__
            or not isinstance(value["alternatives"], list)
        ):
            raise ValueError("invalid save item status")
        receipt = SaveReceipt.from_artifact(value["receipt"]) if value["receipt"] is not None else None
        bibliography = BibliographyLink.from_artifact(value["bibliography"]) if value["bibliography"] is not None else None
        return cls(value["request_index"], value["requested_label"], value["status"], value["reason_code"], receipt, tuple(SaveAlternative.from_artifact(x) for x in value["alternatives"]), bibliography)


@dataclass(frozen=True)
class SaveBatchOutcome:
    batch_id: str
    items: tuple[SaveItemOutcome, ...]
    schema_version: int = field(default=SAVE_BATCH_SCHEMA_VERSION, init=False)
    kind: str = field(default=SAVE_BATCH_KIND, init=False)

    def __post_init__(self):
        if not isinstance(self.batch_id, str) or not self.batch_id or not self.items:
            raise ValueError("save batch requires a string ID and at least one item")
        if len({x.request_index for x in self.items}) != len(self.items):
            raise ValueError("duplicate request index")

    def to_artifact(self):
        return {"kind": self.kind, "schema_version": self.schema_version, "batch_id": self.batch_id, "items": [x.to_artifact() for x in self.items]}

    @classmethod
    def from_artifact(cls, value):
        _strict_fields(value, {"kind", "schema_version", "batch_id", "items"}, "save batch")
        if (
            value["kind"] != SAVE_BATCH_KIND
            or type(value["schema_version"]) is not int
            or value["schema_version"] != SAVE_BATCH_SCHEMA_VERSION
            or not isinstance(value["batch_id"], str)
            or not isinstance(value["items"], list)
        ):
            raise ValueError("unsupported save batch")
        return cls(value["batch_id"], tuple(SaveItemOutcome.from_artifact(x) for x in value["items"]))
