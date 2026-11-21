"""Stateless citation discovery and WorkIntent save orchestration."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from skills.citation.authority import AuthorityRecord, AuthorityRegistry
from skills.citation.csl import csl_from_authority, minimal_csl
from skills.citation.library import LibraryError
from skills.citation.library import load as load_library
from skills.citation.library import merge as merge_library
from skills.citation.library import write_atomic as write_library_atomic
from skills.citation.registry import PROMPT_REGISTRY_LIMIT, SourceRegistry
from skills.citation.doi import canonicalize_doi
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
from skills.citation.types import (
    BibliographyLink,
    CanonicalIdentity,
    PublishedDateFilter,
    SaveAlternative,
    SaveBatchOutcome,
    SaveItemOutcome,
    SaveReceipt,
    SourceRef,
    source_id_for,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _VerifiedWork:
    """A verified work that is not yet registered or written anywhere."""

    label: str
    ref: SourceRef
    receipt: SaveReceipt
    csl: dict


class CitationService:
    def __init__(self, hub, *, library_path=None):
        self.hub = hub
        self.registry = SourceRegistry()
        # The project CSL-JSON bibliography is the only citation store
        # (desktop projects). Without one (the CLI) a save verifies works for
        # the current task only and writes nothing.
        self.library_path = Path(library_path) if library_path is not None else None
        self.resolver = WorkResolver(
            crossref=hub.crossref,
            datacite=hub.datacite,
            openalex=hub.openalex,
            doi_org=hub.doi_org,
        )
        self.authorities = AuthorityRegistry(fetcher=hub.fetch)
        # Search providers that already exhausted their retries on a transient
        # failure. A service lives for one Citation task (the session rebuilds
        # it per turn), so later queries in that task skip them instead of
        # waiting on the same outage again; the next task tries them again.
        self._failed_search_providers: dict[str, str] = {}

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
            earlier = self._failed_search_providers.get(name)
            if earlier is not None:
                return [], f"{name}:skipped({earlier} earlier in this task)"
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
                kind = failure_kind(exc)
                if kind in TRANSIENT_FAILURE_KINDS:
                    self._failed_search_providers.setdefault(name, kind)
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
        if date_filter is not None and (date_filter.year_from is not None or date_filter.year_to is not None):
            # Apply year eligibility before truncating so lower-ranked eligible
            # candidates already retrieved can fill the result.
            ordered = [record for record in ordered if date_filter.admits_year(record.year)]
        return ordered[:rows], states

    async def save(self, intents: tuple[WorkIntent, ...]) -> SaveBatchOutcome:
        """Resolve, verify, and record each intent with per-item isolation.

        Desktop (a project bibliography): a work is citable only once it is in
        the bibliography. ``saved`` was added by this batch's write,
        ``reused`` was there before the batch (or shares the key of an
        earlier item that was written), and ``storage_failed`` was not
        written and is not citable. CLI (no bibliography): every verified
        work is ``verified``, citable in this task only, and nothing is
        written. An unexpected exception in one item becomes that item's
        ``internal_error`` outcome instead of discarding the other items.
        """
        batch_id = uuid.uuid4().hex
        resolutions = await asyncio.gather(
            *(self.resolver.resolve(intent) for intent in intents),
            return_exceptions=True,
        )
        outcomes: list[SaveItemOutcome | None] = []
        verified: dict[int, _VerifiedWork] = {}
        for index, (intent, resolution) in enumerate(zip(intents, resolutions, strict=True)):
            try:
                if isinstance(resolution, BaseException):
                    raise resolution
                planned = await self._plan_item(index, intent, resolution)
            except Exception as exc:
                planned = self._internal_failure(batch_id, index, intent.requested_label, "resolution", exc)
            if isinstance(planned, SaveItemOutcome):
                outcomes.append(planned)
                continue
            record, _resolution_reason = planned
            try:
                work = self._verified_work(intent, record)
            except Exception as exc:
                outcomes.append(self._internal_failure(batch_id, index, intent.requested_label, "verification", exc))
                continue
            if self.registry.conflicts(work.ref):
                # Checked before the bibliography write so a rejected work is
                # never written without being citable.
                logger.warning(
                    "citation save batch %s item %d: source ID %s belongs to another identity",
                    batch_id, index, work.ref.source_id,
                )
                outcomes.append(SaveItemOutcome(index, work.label, "identity_conflict", "registry_conflict"))
                continue
            verified[index] = work
            outcomes.append(None)

        # All resolution and verification completes before the one write.
        if self.library_path is None:
            for index, work in verified.items():
                outcomes[index] = self._registered(batch_id, index, work, "verified", "verified_not_persisted")
        elif verified:
            try:
                links = await asyncio.to_thread(
                    self._link_library, {index: work.csl for index, work in verified.items()}
                )
            except Exception as exc:
                # One write serves every verified item, so an unexpected
                # failure leaves all of them unsaved; earlier items keep theirs.
                links = {}
                for index, work in verified.items():
                    outcomes[index] = self._internal_failure(batch_id, index, work.label, "storage", exc)
            for index, link in links.items():
                work = verified[index]
                if isinstance(link, BibliographyLink):
                    saved = link.status == "added"
                    outcomes[index] = self._registered(
                        batch_id, index, work,
                        "saved" if saved else "reused",
                        "saved_new" if saved else "reused_existing",
                        link,
                    )
                else:
                    outcomes[index] = SaveItemOutcome(index, work.label, "storage_failed", link)
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
                # The NeurIPS adapter runs only for a venue naming NeurIPS and
                # searches only the official proceedings, so the venue is already
                # established; comparing "NeurIPS 2017" with "Advances in Neural
                # Information Processing Systems 30" as text would reject it.
                venue="" if authority.provider == "neurips" else authority.venue,
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

    def _verified_work(self, intent: WorkIntent, record) -> _VerifiedWork:
        """Build the source, receipt, and CSL item for one eligible record."""
        if isinstance(record, AuthorityRecord):
            identity = record.identity
            sid = source_id_for(identity)
            ref = SourceRef(
                sid, None, record.title, authors=list(record.authors), year=record.year,
                venue=record.venue, work_type=record.work_type, url=record.url,
                verification_level="authority_metadata_verified",
                provenance=f"authoritative:{record.provider}",
                canonical_identity=identity,
            )
            version_kind = "preprint" if record.provider == "arxiv" else "published"
        else:
            identity = CanonicalIdentity("doi", record.doi)
            sid = source_id_for(identity)
            ref = SourceRef(
                sid, identity.value, record.title,
                authors=list(record.authors),
                year=record.year,
                venue=record.venue,
                work_type=record.work_type,
                url=record.url or f"https://doi.org/{identity.value}",
                verification_level="doi_identity_verified",
                provenance="fresh-resolution+doi.org-csl",
                canonical_identity=identity,
            )
            version_kind = infer_version_kind(record)
        receipt = SaveReceipt(
            sid, identity, ref.doi, ref.title, ref.year,
            ref.work_type, ref.verification_level, f"[[cite:{sid}]]", version_kind,
        )
        return _VerifiedWork(intent.requested_label, ref, receipt, self._csl_item(record, receipt))

    def _registered(
        self,
        batch_id: str,
        index: int,
        work: _VerifiedWork,
        status: str,
        reason_code: str,
        link: BibliographyLink | None = None,
    ) -> SaveItemOutcome:
        """Register a verified work as citable and report it."""
        try:
            self.registry.register(work.ref, receipt=work.receipt)
        except ValueError as exc:
            logger.warning(
                "citation save batch %s item %d: registry rejected the source: %s",
                batch_id, index, exc,
            )
            return SaveItemOutcome(index, work.label, "identity_conflict", "registry_conflict")
        return SaveItemOutcome(index, work.label, status, reason_code, work.receipt, bibliography=link)

    @staticmethod
    def _csl_item(record, receipt: SaveReceipt) -> dict:
        """CSL-JSON for a verified work, from verified metadata only."""
        if isinstance(record, AuthorityRecord):
            return csl_from_authority(record)
        item = dict(record.csl) if getattr(record, "csl", None) else minimal_csl(
            title=record.title,
            authors=list(record.authors),
            year=record.year,
            venue=record.venue,
            work_type=record.work_type,
            doi=record.doi,
            url=record.url,
        )
        if receipt.doi:
            item["DOI"] = receipt.doi
        item.pop("abstract", None)
        return item

    def _link_library(self, csl_items: dict[int, dict]) -> dict[int, BibliographyLink | str]:
        """Merge verified works into the project bibliography in one write.

        Returns each item's link, or the library error code when the item is
        not in the bibliography after this call. A work that was on disk
        before the batch keeps its link even when the write of other, new
        works fails; a work added by this batch (and any duplicate of it in
        the same batch) is linked only if the write succeeded.
        """
        path = str(self.library_path)
        try:
            library = load_library(self.library_path)
        except LibraryError as exc:
            logger.warning("citation bibliography load failed: %s (%s)", exc.code, exc)
            return {index: exc.code for index in csl_items}
        merges = {}
        added_keys: set[str] = set()
        for index, item in csl_items.items():
            try:
                merged = merge_library(library, item)
            except LibraryError as exc:
                merges[index] = exc.code
                continue
            library = merged.library
            if merged.status == "added":
                added_keys.add(merged.key)
            merges[index] = merged
        write_error = None
        if added_keys:
            try:
                write_library_atomic(library)
            except LibraryError as exc:
                logger.warning("citation bibliography write failed: %s (%s)", exc.code, exc)
                write_error = exc.code
        links: dict[int, BibliographyLink | str] = {}
        for index, merged in merges.items():
            if isinstance(merged, str):
                links[index] = merged
            elif merged.key not in added_keys:
                links[index] = BibliographyLink("existing", path, merged.key)
            elif write_error is not None:
                links[index] = write_error
            else:
                links[index] = BibliographyLink(merged.status, path, merged.key)
        return links

    @staticmethod
    def _internal_failure(
        batch_id: str,
        index: int,
        label: str,
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
        return SaveItemOutcome(index, label, "internal_error", f"{stage}_internal_error")

    def list_sources(self, page: int = 1):
        sources = self.registry.list()
        start = max(0, page - 1) * PROMPT_REGISTRY_LIMIT
        return sources[start:start + PROMPT_REGISTRY_LIMIT], max(1, (len(sources) + PROMPT_REGISTRY_LIMIT - 1) // PROMPT_REGISTRY_LIMIT)

    def activate_source(self, source_id: str):
        return self.registry.activate(source_id)
