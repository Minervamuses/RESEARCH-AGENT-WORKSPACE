"""Stateless citation discovery and WorkIntent save orchestration."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from skills.citation.bibtex_canonical import BibtexValidationError, inject_doi, parse_canonical_bibtex
from skills.citation.authority import AuthorityRecord, AuthorityRegistry, export_bibtex
from skills.citation.registry import PROMPT_REGISTRY_LIMIT, SourceRegistry
from skills.citation.doi import canonicalize_doi, doi_equal
from skills.citation.providers.base import ProviderRecord
from skills.citation.providers.net import ProviderError
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
            except ProviderError:
                return [], f"{name}:error"

        results = await asyncio.gather(*(call(name, provider) for name, provider in providers))
        states = [state for _records, state in results]
        records = [record for found, _state in results for record in found]
        unique: dict[tuple[str, str], ProviderRecord] = {}
        for record in records:
            key = ("doi", record.doi) if record.doi else (record.provider, record.provider_id)
            current = unique.get(key)
            if current is None or record.rank < current.rank:
                unique[key] = record
        ordered = sorted(unique.values(), key=lambda r: (r.rank, r.title.casefold(), r.provider))
        return ordered[:rows], states

    async def save(self, intents: tuple[WorkIntent, ...]) -> SaveBatchOutcome:
        batch_id = uuid.uuid4().hex
        resolutions = await asyncio.gather(*(self.resolver.resolve(intent) for intent in intents))
        outcomes: list[SaveItemOutcome] = []
        eligible: list[tuple[int, WorkIntent, object, str]] = []
        for index, (intent, resolution) in enumerate(zip(intents, resolutions, strict=True)):
            decision = resolution.decision
            if decision.status == "eligible" and decision.record is not None:
                eligible.append((index, intent, decision.record, decision.reason_code))
                outcomes.append(None)  # type: ignore[arg-type]
                continue
            # An exact DOI is the selected target. Never replace a failed DOI
            # lookup (or conflicting identifier set) with a different
            # authority identity merely because descriptive fields resemble it.
            has_exact_doi = any(
                identifier.kind == "doi" for identifier in intent.identifiers
            )
            authority = None
            if (
                not has_exact_doi
                and decision.reason_code != "multiple_exact_identifiers"
            ):
                try:
                    authority = await self.authorities.resolve(intent)
                except ProviderError:
                    outcomes.append(SaveItemOutcome(
                        index,
                        intent.requested_label,
                        "provider_failed",
                        "authority_lookup_failed",
                    ))
                    continue
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
                    eligible.append((index, intent, authority, "authoritative_exact_record"))
                    outcomes.append(None)  # type: ignore[arg-type]
                    continue
                decision = authority_decision
            elif decision.reason_code == "exact_arxiv_requires_authority":
                outcomes.append(SaveItemOutcome(
                    index,
                    intent.requested_label,
                    "not_found",
                    "exact_arxiv_not_found",
                ))
                continue
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
            outcomes.append(SaveItemOutcome(
                index, intent.requested_label, status, decision.reason_code,
                alternatives=alternatives,
            ))

        # All resolution/provider verification completes before the first write.
        for index, intent, record, resolution_reason in eligible:
            if isinstance(record, AuthorityRecord):
                try:
                    canonical = export_bibtex(record)
                except BibtexValidationError as exc:
                    outcomes[index] = SaveItemOutcome(
                        index,
                        intent.requested_label,
                        "verification_failed",
                        getattr(exc, "code", "authority_bibtex_invalid"),
                    )
                    continue
                identity = record.identity
                sid = source_id_for(identity)
                ref = SourceRef(
                    sid, None, record.title, authors=list(record.authors), year=record.year,
                    venue=record.venue, work_type=record.work_type, url=record.url,
                    verification_level="authority_metadata_verified",
                    provenance=f"authoritative:{record.provider}", schema_version=2,
                    canonical_identity=identity,
                )
                sidecar = {
                    "source_ref": ref.to_persisted_dict(),
                    "creation_evidence": {
                        "batch_id": batch_id,
                        "request_index": index,
                        "agent_intent": self._intent_evidence(intent),
                    },
                    "resolution": {"record_source": record.provider, "provider_record_ids": [identity.key], "version_kind": "preprint" if record.provider == "arxiv" else "published", "decision_reason_codes": [resolution_reason]},
                }
                try:
                    bundle = await asyncio.to_thread(write_identity_bundle, self.output_dir, identity=identity, title=ref.title, bibtex_text=canonical.text, sidecar=sidecar)
                    receipt = SaveReceipt(
                        sid, identity, None, ref.title, ref.year, ref.work_type,
                        str(bundle.bundle_dir), ref.verification_level,
                        f"[[cite:{sid}]]",
                        "preprint" if record.provider == "arxiv" else "published",
                    )
                    self.registry.register(ref, receipt=receipt)
                except (StorageError, ValueError) as exc:
                    outcomes[index] = SaveItemOutcome(index, intent.requested_label, "storage_failed", getattr(exc, "code", "registry_conflict"))
                    continue
                outcomes[index] = SaveItemOutcome(index, intent.requested_label, "reused" if bundle.reused else "saved", "reused_existing" if bundle.reused else "saved_new", receipt)
                continue
            try:
                raw = await self.hub.doi_org.fetch_bibtex(record.doi)
                canonical = parse_canonical_bibtex(raw)
                if canonical.doi is None:
                    canonical = inject_doi(canonical, record.doi)
                elif not doi_equal(canonical.doi, record.doi):
                    raise BibtexValidationError("bibtex_doi_mismatch", "DOI mismatch")
            except (ProviderError, BibtexValidationError) as exc:
                code = getattr(exc, "code", "bibtex_lookup_failed")
                outcomes[index] = SaveItemOutcome(index, intent.requested_label, "verification_failed", code)
                continue
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
            sidecar = {
                "source_ref": ref.to_persisted_dict(),
                "creation_evidence": {
                    "batch_id": batch_id,
                    "request_index": index,
                    "agent_intent": self._intent_evidence(intent),
                },
                "resolution": {
                    "record_source": record.provider,
                    "provider_record_ids": [record.provider_id],
                    "version_kind": infer_version_kind(record),
                    "decision_reason_codes": [resolution_reason],
                },
            }
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
                    sid, identity, identity.value, ref.title, ref.year,
                    ref.work_type, str(bundle.bundle_dir), ref.verification_level,
                    f"[[cite:{sid}]]", infer_version_kind(record),
                )
                self.registry.register(ref, receipt=receipt)
            except (StorageError, ValueError) as exc:
                outcomes[index] = SaveItemOutcome(index, intent.requested_label, "storage_failed", getattr(exc, "code", "registry_conflict"))
                continue
            outcomes[index] = SaveItemOutcome(
                index, intent.requested_label, "reused" if bundle.reused else "saved",
                "reused_existing" if bundle.reused else "saved_new", receipt,
            )
        return SaveBatchOutcome(batch_id, tuple(outcomes))

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
