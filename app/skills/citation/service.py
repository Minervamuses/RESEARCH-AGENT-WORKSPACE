"""Stateless citation discovery and WorkIntent save orchestration."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import replace
from pathlib import Path

from skills.citation.bibtex_canonical import BibtexValidationError, inject_doi, parse_canonical_bibtex
from skills.citation.authority import AuthorityRecord, AuthorityRegistry, export_bibtex
from skills.citation.registry import PROMPT_REGISTRY_LIMIT, SourceRegistry
from skills.citation.doi import canonicalize_doi, doi_equal
from skills.citation.providers.base import ProviderRecord
from skills.citation.providers.net import (
    TRANSIENT_FAILURE_KINDS,
    ProviderError,
    describe_failure,
    failure_kind,
)
from skills.citation.resolution import (
    WorkIntent,
    WorkResolver,
    evaluate_record,
    infer_version_kind,
)
from skills.citation.storage import StorageError, resolve_output_dir, source_id_for, write_identity_bundle
from skills.citation.types import (
    CanonicalIdentity,
    PublishedDateFilter,
    SaveAlternative,
    SaveBatchOutcome,
    SaveItemOutcome,
    SaveReceipt,
    SourceRef,
)

logger = logging.getLogger(__name__)


class CitationService:
    def __init__(self, hub, *, config=None, output_dir=None):
        self.hub = hub
        self.registry = SourceRegistry()
        self.output_dir = Path(output_dir) if output_dir is not None else resolve_output_dir(config)
        self.resolver = WorkResolver(
            crossref=hub.crossref,
            datacite=hub.datacite,
            openalex=hub.openalex,
            doi_org=hub.doi_org,
        )
        self.authorities = AuthorityRegistry(fetcher=hub._fetch)

    async def search(
        self,
        query: str,
        *,
        rows: int = 10,
        date_filter: PublishedDateFilter | None = None,
    ) -> tuple[list[ProviderRecord], list[str]]:
        providers = [("crossref", self.hub.crossref), ("datacite", self.hub.datacite)]
        if self.hub.openalex is not None:
            providers.append(("openalex", self.hub.openalex))

        async def call(name, provider):
            try:
                return await provider.search_text(
                    query,
                    rows=min(rows, 20),
                    date_filter=date_filter,
                ), f"{name}:ok"
            except ProviderError as exc:
                logger.warning(
                    "citation search provider %s failed: %s",
                    name,
                    describe_failure(exc),
                )
                return [], f"{name}:{describe_failure(exc)}"
            except Exception as exc:
                logger.error(
                    "citation search provider %s failed unexpectedly: %s",
                    name,
                    type(exc).__name__,
                    exc_info=exc,
                )
                return [], f"{name}:internal_error({type(exc).__name__})"

        results = await asyncio.gather(*(call(name, provider) for name, provider in providers))
        states = [state for _records, state in results]
        records = [record for found, _state in results for record in found]
        unique: dict[tuple[str, str], ProviderRecord] = {}
        for record in records:
            key = ("doi", record.doi) if record.doi else (record.provider, record.provider_id)
            current = unique.get(key)
            if current is None:
                unique[key] = record
                continue
            winner, other = (
                (record, current) if record.rank < current.rank else (current, record)
            )
            # Keep the existing metadata/rank winner while preserving a real
            # abstract supplied by another provider for the same DOI.
            if not winner.abstract and other.abstract:
                winner = replace(
                    winner,
                    abstract=other.abstract,
                    abstract_source=other.abstract_source,
                    abstract_url=other.abstract_url,
                )
            unique[key] = winner
        ordered = sorted(unique.values(), key=lambda r: (r.rank, r.title.casefold(), r.provider))
        return ordered[:rows], states

    async def save(self, intents: tuple[WorkIntent, ...]) -> SaveBatchOutcome:
        """Resolve, verify, and persist each intent with per-item isolation.

        An unexpected exception in one item becomes that item's
        ``internal_error`` outcome (logged with batch ID, index, stage, and
        traceback) instead of discarding every other item's result.
        """
        batch_id = uuid.uuid4().hex
        resolutions = await asyncio.gather(
            *(self.resolver.resolve(intent) for intent in intents),
            return_exceptions=True,
        )
        outcomes: list[SaveItemOutcome | None] = []
        eligible: list[tuple[int, WorkIntent, object, str]] = []
        for index, (intent, resolution) in enumerate(zip(intents, resolutions, strict=True)):
            try:
                if isinstance(resolution, BaseException):
                    raise resolution
                planned = await self._plan_item(index, intent, resolution)
            except Exception as exc:
                planned = self._internal_failure(batch_id, index, intent, "resolution", exc)
            if isinstance(planned, SaveItemOutcome):
                outcomes.append(planned)
                continue
            record, resolution_reason = planned
            eligible.append((index, intent, record, resolution_reason))
            outcomes.append(None)

        # All resolution/provider verification completes before the first write.
        for index, intent, record, resolution_reason in eligible:
            outcomes[index] = await self._persist_item(
                batch_id, index, intent, record, resolution_reason
            )
        for item in outcomes:
            logger.info(
                "citation save batch %s item %d: %s/%s",
                batch_id,
                item.request_index,
                item.status,
                item.reason_code,
            )
        return SaveBatchOutcome(batch_id, tuple(outcomes))

    async def _plan_item(
        self, index: int, intent: WorkIntent, resolution
    ) -> SaveItemOutcome | tuple[object, str]:
        """Return an eligible ``(record, reason)`` pair or a failure outcome."""
        decision = resolution.decision
        if decision.status == "eligible" and decision.record is not None:
            return decision.record, decision.reason_code
        if resolution.provider_states:
            logger.info(
                "citation resolution item %d: %s/%s providers=%s",
                index,
                decision.status,
                decision.reason_code,
                ", ".join(
                    f"{state.provider}:{state.status}"
                    + (f"({state.detail})" if state.detail else "")
                    for state in resolution.provider_states
                ),
            )
        # An exact DOI is the selected target. Never replace a failed DOI
        # lookup (or conflicting identifier set) with a different
        # authority identity merely because descriptive fields resemble it.
        has_exact_doi = any(
            identifier.kind == "doi" for identifier in intent.identifiers
        )
        # An authority match cannot settle missing or tied year evidence.
        earliest_ambiguity = decision.status == "ambiguous" and decision.reason_code in {
            "earliest_year_missing", "earliest_year_tie",
        }
        authority = None
        if (
            not has_exact_doi
            and decision.reason_code != "multiple_exact_identifiers"
            and not earliest_ambiguity
        ):
            try:
                authority = await self.authorities.resolve(intent)
            except ProviderError as exc:
                kind = failure_kind(exc)
                logger.warning(
                    "citation authority lookup via %s failed: %s",
                    exc.provider,
                    describe_failure(exc),
                )
                return SaveItemOutcome(
                    index,
                    intent.requested_label,
                    "provider_failed",
                    f"authority_lookup_{kind}"
                    if kind in TRANSIENT_FAILURE_KINDS
                    else "authority_lookup_failed",
                )
        if authority is not None:
            authority_record = ProviderRecord(
                provider=authority.provider,
                provider_id=f"{authority.provider}:{authority.identity.key}",
                rank=0,
                title=authority.title,
                authors=list(authority.authors),
                year=authority.year,
                venue=authority.venue,
                work_type=authority.work_type,
                url=authority.url,
                identifiers={authority.identity.kind: authority.identity.value},
                version_kind=(
                    "preprint" if authority.provider == "arxiv" else "published"
                ),
                field_provenance={
                    field: f"authoritative:{authority.provider}"
                    for field in (
                        "title",
                        "authors",
                        "year",
                        "venue",
                        "work_type",
                        "url",
                    )
                },
            )
            authority_decision = evaluate_record(intent, authority_record)
            if authority_decision.status == "eligible":
                return authority, "authoritative_exact_record"
            decision = authority_decision
        elif decision.reason_code == "exact_arxiv_requires_authority":
            return SaveItemOutcome(
                index,
                intent.requested_label,
                "not_found",
                "exact_arxiv_not_found",
            )
        status_map = {"unsupported": "unsupported_no_doi"}
        status = status_map.get(decision.status, decision.status)
        alternatives = tuple(
            SaveAlternative(
                record.title, tuple(record.authors), record.year, record.venue,
                infer_version_kind(record), canonicalize_doi(record.doi),
                record.identifiers.get("arxiv") or None,
            )
            for record in decision.alternatives[:5]
        )
        return SaveItemOutcome(
            index, intent.requested_label, status, decision.reason_code,
            alternatives=alternatives,
        )

    async def _persist_item(
        self,
        batch_id: str,
        index: int,
        intent: WorkIntent,
        record,
        resolution_reason: str,
    ) -> SaveItemOutcome:
        """Fetch/validate BibTeX, then write the bundle and register it."""
        stage = "verification"
        try:
            if isinstance(record, AuthorityRecord):
                try:
                    canonical = export_bibtex(record)
                except BibtexValidationError as exc:
                    return SaveItemOutcome(
                        index,
                        intent.requested_label,
                        "verification_failed",
                        getattr(exc, "code", "authority_bibtex_invalid"),
                    )
                identity = record.identity
                sid = source_id_for(identity)
                ref = SourceRef(
                    sid, None, record.title, authors=list(record.authors), year=record.year,
                    venue=record.venue, work_type=record.work_type, url=record.url,
                    verification_level="authority_metadata_verified",
                    provenance=f"authoritative:{record.provider}", schema_version=2,
                    canonical_identity=identity,
                )
                provider_record_ids = [identity.key]
                version_kind = "preprint" if record.provider == "arxiv" else "published"
            else:
                try:
                    raw = await self.hub.doi_org.fetch_bibtex(record.doi)
                    canonical = parse_canonical_bibtex(raw)
                    if canonical.doi is None:
                        canonical = inject_doi(canonical, record.doi)
                    elif not doi_equal(canonical.doi, record.doi):
                        raise BibtexValidationError("bibtex_doi_mismatch", "DOI mismatch")
                except ProviderError as exc:
                    kind = failure_kind(exc)
                    logger.warning(
                        "citation BibTeX lookup via doi.org failed: %s",
                        describe_failure(exc),
                    )
                    if kind in TRANSIENT_FAILURE_KINDS:
                        return SaveItemOutcome(
                            index, intent.requested_label,
                            "provider_failed", f"bibtex_lookup_{kind}",
                        )
                    return SaveItemOutcome(
                        index, intent.requested_label,
                        "verification_failed", "bibtex_lookup_failed",
                    )
                except BibtexValidationError as exc:
                    logger.warning("citation BibTeX validation failed: %s", exc.code)
                    return SaveItemOutcome(
                        index, intent.requested_label, "verification_failed", exc.code,
                    )
                identity = CanonicalIdentity("doi", record.doi)
                sid = source_id_for(identity)
                ref = SourceRef(
                    sid, identity.value, record.title or canonical.title,
                    authors=list(record.authors) or list(canonical.authors),
                    year=record.year if record.year is not None else canonical.year,
                    venue=record.venue or canonical.venue,
                    work_type=record.work_type,
                    url=record.url or f"https://doi.org/{identity.value}",
                    verification_level="doi_identity_verified",
                    provenance="fresh-resolution+doi.org-csl+bibtex",
                    schema_version=2,
                    canonical_identity=identity,
                )
                provider_record_ids = [record.provider_id]
                version_kind = infer_version_kind(record)
            sidecar = {
                "source_ref": ref.to_persisted_dict(),
                "creation_evidence": {
                    "batch_id": batch_id,
                    "request_index": index,
                    "agent_intent": self._intent_evidence(intent),
                },
                "resolution": {
                    "record_source": record.provider,
                    "provider_record_ids": provider_record_ids,
                    "version_kind": version_kind,
                    "decision_reason_codes": [resolution_reason],
                },
            }
            stage = "storage"
            try:
                bundle = await asyncio.to_thread(
                    write_identity_bundle,
                    self.output_dir,
                    identity=identity,
                    title=ref.title,
                    bibtex_text=canonical.text,
                    sidecar=sidecar,
                )
                receipt = SaveReceipt(
                    sid, identity, ref.doi, ref.title, ref.year,
                    ref.work_type, str(bundle.bundle_dir), ref.verification_level,
                    f"[[cite:{sid}]]", version_kind,
                )
                self.registry.register(ref, receipt=receipt)
            except (StorageError, ValueError) as exc:
                code = getattr(exc, "code", "registry_conflict")
                logger.warning(
                    "citation bundle storage failed for batch %s item %d: %s (%s)",
                    batch_id,
                    index,
                    code,
                    exc,
                )
                return SaveItemOutcome(index, intent.requested_label, "storage_failed", code)
            return SaveItemOutcome(
                index, intent.requested_label, "reused" if bundle.reused else "saved",
                "reused_existing" if bundle.reused else "saved_new", receipt,
            )
        except Exception as exc:
            return self._internal_failure(batch_id, index, intent, stage, exc)

    @staticmethod
    def _internal_failure(
        batch_id: str,
        index: int,
        intent: WorkIntent,
        stage: str,
        exc: Exception,
    ) -> SaveItemOutcome:
        """Log an unexpected per-item exception and report it for that item."""
        logger.error(
            "citation save batch %s item %d failed unexpectedly during %s: %s",
            batch_id,
            index,
            stage,
            type(exc).__name__,
            exc_info=exc,
        )
        return SaveItemOutcome(
            index, intent.requested_label, "internal_error", f"{stage}_internal_error",
        )

    @staticmethod
    def _intent_evidence(intent: WorkIntent) -> dict:
        """Record the agent selection used for this save without claiming proof."""
        return {
            "title": intent.title,
            "authors": list(intent.authors),
            "year": intent.year,
            "venue": intent.venue,
            "work_type": intent.work_type,
            "work_kind": intent.work_kind,
            "version_kind": intent.version_kind,
            "identifiers": [
                {"kind": identifier.kind, "value": identifier.value}
                for identifier in intent.identifiers
            ],
        }

    def list_sources(self, page: int = 1):
        sources = self.registry.list()
        start = max(0, page - 1) * PROMPT_REGISTRY_LIMIT
        return sources[start:start + PROMPT_REGISTRY_LIMIT], max(1, (len(sources) + PROMPT_REGISTRY_LIMIT - 1) // PROMPT_REGISTRY_LIMIT)

    def activate_source(self, source_id: str):
        return self.registry.activate(source_id)
