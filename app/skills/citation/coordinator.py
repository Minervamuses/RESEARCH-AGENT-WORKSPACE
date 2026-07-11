"""Session-scoped citation workflow coordinator.

The only object allowed to search for papers, mint verified SourceRefs, and
write citation bundles. Chat reaches it exclusively through the skill-only
``citation_workflow`` tool, bound while the citation skill is active.

Workflow generations: every ``search`` or ``cancel`` starts a new generation
and invalidates all previous candidate/match IDs. ``more`` keeps candidate
IDs but clears the selection and matches. Every ``select`` invalidates prior
match IDs. A failed ``confirm`` keeps the resolved state so another match
can be confirmed; a successful one completes the workflow but the SourceRef
registry survives for citing and re-activation.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from skills.citation.doi import canonicalize_doi, doi_equal, extract_doi_candidates
from skills.citation.expansion import QueryExpander
from skills.citation.hub import CitationProviderHub
from skills.citation.normalize import titles_match
from skills.citation.providers.base import ProviderRecord
from skills.citation.providers.doi_org import DoiNotFound, StructuredRecord
from skills.citation.providers.net import (
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
)
from skills.citation.providers.web import WebSearchProvider
from skills.citation.ranking import MAX_WORKFLOW_CANDIDATES, fuse_ranked_lists
from skills.citation.bibtex_canonical import (
    BibtexValidationError,
    inject_doi,
    parse_canonical_bibtex,
)
from skills.citation.storage import (
    StorageError,
    doi_hash,
    resolve_output_dir,
    write_bundle,
)
from skills.citation.types import (
    CitationCandidate,
    CitationMatch,
    CitationResult,
    ProviderState,
    PublishedDateFilter,
    SourceRef,
    VerificationCheck,
    VerificationReport,
)

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
PROMPT_REGISTRY_LIMIT = 20


@dataclass
class SearchOutcome:
    """What one search/more call produced.

    ``date_filtered_out`` counts fused candidates dropped by the fail-closed
    published-date filter (unknown year, or year outside the window).
    """

    candidates: list[CitationCandidate] = field(default_factory=list)
    provider_states: list[ProviderState] = field(default_factory=list)
    used_web_fallback: bool = False
    queries: list[str] = field(default_factory=list)
    error: str = ""
    date_filtered_out: int = 0


@dataclass
class SelectOutcome:
    """Matches produced by the select action (or the failure that stopped it)."""

    matches: list[CitationMatch] = field(default_factory=list)
    result: CitationResult | None = None
    provider_states: list[ProviderState] = field(default_factory=list)


class SourceRegistry:
    """Session registry of citable SourceRefs, most recently active first."""

    def __init__(self):
        self._sources: dict[str, SourceRef] = {}
        self._recency: list[str] = []

    def register(self, ref: SourceRef) -> SourceRef:
        existing = self._sources.get(ref.source_id)
        self._sources[ref.source_id] = ref
        self._touch(ref.source_id)
        return existing or ref

    def _touch(self, source_id: str) -> None:
        if source_id in self._recency:
            self._recency.remove(source_id)
        self._recency.insert(0, source_id)

    def get(self, source_id: str) -> SourceRef | None:
        return self._sources.get(source_id)

    def activate(self, source_id: str) -> SourceRef | None:
        ref = self._sources.get(source_id)
        if ref is not None:
            self._touch(source_id)
        return ref

    def list(self) -> list[SourceRef]:
        return [self._sources[sid] for sid in self._recency]

    def prompt_sources(self, limit: int = PROMPT_REGISTRY_LIMIT) -> list[SourceRef]:
        return self.list()[: max(0, limit)]


def _candidate_from_structured(
    record: StructuredRecord, *, workflow_id: str
) -> CitationCandidate:
    return CitationCandidate(
        candidate_id="c1",
        workflow_id=workflow_id,
        title=record.title,
        authors=list(record.authors),
        year=record.year,
        venue=record.venue,
        doi=record.doi,
        url=record.url,
        work_type=record.work_type,
        provider_ids={"structured": f"structured:{record.doi}"},
        provider_ranks={"structured": 0},
        field_provenance={
            name: "structured"
            for name in ("title", "authors", "year", "venue", "doi")
        },
    )


class CitationCoordinator:
    """Drives one session's citation workflows against the shared hub."""

    def __init__(
        self,
        hub: CitationProviderHub,
        *,
        web_tools: dict[str, object] | None = None,
        llm_factory=None,
        config: object | None = None,
        output_dir=None,
    ):
        self._hub = hub
        self._web = WebSearchProvider(web_tools or {})
        self._expander = (
            QueryExpander(llm_factory) if llm_factory is not None else None
        )
        self._output_dir = (
            output_dir if output_dir is not None else resolve_output_dir(config)
        )
        self.registry = SourceRegistry()

        self._generation = 0
        self._workflow_id = ""
        self._candidates: list[CitationCandidate] = []
        self._selected_id: str | None = None
        self._matches: dict[str, CitationMatch] = {}
        self._match_counter = 0
        self._last_query = ""
        self._last_states: list[ProviderState] = []
        self._attempts = 0
        self._previous_failure_codes: list[str] = []
        self._date_filter: PublishedDateFilter | None = None

    # --- workflow generation management ----------------------------------

    def _new_generation(self) -> None:
        self._generation += 1
        self._workflow_id = f"wf-{self._generation}"
        self._candidates = []
        self._selected_id = None
        self._matches = {}
        self._match_counter = 0
        self._attempts = 0
        self._previous_failure_codes = []
        self._date_filter = None

    def _clear_resolution(self) -> None:
        self._selected_id = None
        self._matches = {}

    @property
    def workflow_id(self) -> str:
        return self._workflow_id

    # --- discovery ---------------------------------------------------------

    async def search(
        self, query: str, *, date_filter: PublishedDateFilter | None = None
    ) -> SearchOutcome:
        """Start a new workflow generation for ``query``.

        A DOI-shaped query resolves directly through the doi.org singleton —
        no LLM, no web search. Otherwise all enabled structured providers run
        in parallel over the query plus at most two lazy LLM expansions; the
        web MCP runs automatically only when every enabled structured
        provider failed or produced zero candidates.

        ``date_filter`` (optional) is pushed down to the structured providers'
        native date filters and then re-applied fail-closed over the fused
        candidates: unknown or out-of-window years never qualify. The filter
        sticks to the workflow generation, so ``more`` respects it too.
        """
        self._new_generation()
        self._last_query = query.strip()
        self._date_filter = date_filter

        canonical = canonicalize_doi(query)
        if canonical is not None:
            return await self._search_by_doi(canonical)

        queries = [self._last_query]
        if self._expander is not None:
            queries += await self._expander.expand(self._last_query)

        ranked_lists, states = await self._run_structured_search(queries)
        if not self._hub.openalex_enabled:
            states.append(ProviderState(
                provider="openalex", status="disabled",
                detail="OPENALEX_API_KEY not configured",
            ))

        used_web = False
        structured_empty = not any(ranked_lists)
        if structured_empty:
            web_list, web_state = await self._run_web_search(self._last_query)
            states.append(web_state)
            if web_list:
                ranked_lists.append(web_list)
                used_web = True

        fused = fuse_ranked_lists(
            [lst for lst in ranked_lists if lst],
            query=self._last_query,
            workflow_id=self._workflow_id,
        ) if any(ranked_lists) else []
        self._candidates, filtered_out = self._apply_date_filter(fused)
        self._last_states = states
        return SearchOutcome(
            candidates=list(self._candidates),
            provider_states=states,
            used_web_fallback=used_web,
            queries=queries,
            date_filtered_out=filtered_out,
        )

    def _apply_date_filter(
        self, candidates: list[CitationCandidate]
    ) -> tuple[list[CitationCandidate], int]:
        """Fail-closed post-filter; survivors are renumbered c1..cN."""
        if self._date_filter is None:
            return candidates, 0
        kept = [c for c in candidates if self._date_filter.admits_year(c.year)]
        for index, candidate in enumerate(kept):
            candidate.candidate_id = f"c{index + 1}"
        return kept, len(candidates) - len(kept)

    async def _search_by_doi(self, canonical: str) -> SearchOutcome:
        try:
            record = await self._hub.doi_org.fetch_structured(canonical)
        except DoiNotFound:
            states = [ProviderState("doi.org", "empty", "DOI does not resolve")]
            self._last_states = states
            return SearchOutcome(provider_states=states, queries=[canonical])
        except ProviderRateLimited as exc:
            states = [ProviderState("doi.org", "rate_limited", exc.detail)]
            self._last_states = states
            return SearchOutcome(provider_states=states, queries=[canonical])
        except ProviderTimeout as exc:
            states = [ProviderState("doi.org", "timeout", exc.detail)]
            self._last_states = states
            return SearchOutcome(provider_states=states, queries=[canonical])
        except ProviderError as exc:
            states = [ProviderState("doi.org", "error", exc.detail)]
            self._last_states = states
            return SearchOutcome(provider_states=states, queries=[canonical])
        candidate = _candidate_from_structured(record, workflow_id=self._workflow_id)
        self._candidates, filtered_out = self._apply_date_filter([candidate])
        states = [ProviderState("doi.org", "ok")]
        self._last_states = states
        return SearchOutcome(
            candidates=list(self._candidates),
            provider_states=states,
            queries=[canonical],
            date_filtered_out=filtered_out,
        )

    async def _run_structured_search(
        self, queries: list[str]
    ) -> tuple[list[list[ProviderRecord]], list[ProviderState]]:
        providers = [("crossref", self._hub.crossref)]
        if self._hub.openalex is not None:
            providers.append(("openalex", self._hub.openalex))

        async def _one(name: str, client, query: str):
            try:
                records = await client.search(query, date_filter=self._date_filter)
            except ProviderRateLimited as exc:
                return [], ProviderState(name, "rate_limited", exc.detail)
            except ProviderTimeout as exc:
                return [], ProviderState(name, "timeout", exc.detail)
            except ProviderError as exc:
                return [], ProviderState(name, "error", exc.detail)
            status = "ok" if records else "empty"
            return records, ProviderState(name, status, f"query={query!r}")

        tasks = [
            _one(name, client, query)
            for name, client in providers
            for query in queries
        ]
        results = await asyncio.gather(*tasks)
        ranked_lists = [records for records, _state in results]
        states = [state for _records, state in results]
        return ranked_lists, states

    async def _run_web_search(
        self, query: str
    ) -> tuple[list[ProviderRecord], ProviderState]:
        if not self._web.available:
            return [], ProviderState("web", "disabled", "web MCP not loaded")
        try:
            records = await self._web.search(query)
        except ProviderRateLimited as exc:
            return [], ProviderState("web", "rate_limited", exc.detail)
        except ProviderTimeout as exc:
            return [], ProviderState("web", "timeout", exc.detail)
        except ProviderError as exc:
            return [], ProviderState("web", "error", exc.detail)
        status = "ok" if records else "empty"
        return records, ProviderState("web", status, f"query={query!r}")

    async def more(self, query: str | None = None) -> SearchOutcome:
        """Explicitly pull web results into the current workflow.

        Keeps existing candidate IDs, clears selection/matches, appends only
        identity-new candidates, and respects the 50-candidate cap.
        """
        if not self._workflow_id:
            return SearchOutcome(error="no active workflow; run a search first")
        self._clear_resolution()
        effective_query = (query or self._last_query).strip()
        if not effective_query:
            return SearchOutcome(error="no query available for more")

        web_list, web_state = await self._run_web_search(effective_query)
        states = [web_state]
        known_dois = {c.doi for c in self._candidates if c.doi}
        known_pids = {
            pid for c in self._candidates for pid in c.provider_ids.values()
        }
        fresh = [
            record
            for record in web_list
            if not (record.doi and record.doi in known_dois)
            and record.provider_id not in known_pids
        ]
        appended: list[CitationCandidate] = []
        filtered_out = 0
        if fresh:
            room = MAX_WORKFLOW_CANDIDATES - len(self._candidates)
            fused = fuse_ranked_lists(
                [fresh], query=effective_query, workflow_id=self._workflow_id,
                limit=max(room, 1),
            )
            if self._date_filter is not None:
                admitted = [
                    c for c in fused if self._date_filter.admits_year(c.year)
                ]
                filtered_out = len(fused) - len(admitted)
                fused = admitted
            offset = len(self._candidates)
            for i, candidate in enumerate(fused[:room] if room > 0 else []):
                candidate.candidate_id = f"c{offset + i + 1}"
                appended.append(candidate)
            self._candidates.extend(appended)
        self._last_states = states
        return SearchOutcome(
            candidates=appended,
            provider_states=states,
            used_web_fallback=True,
            queries=[effective_query],
            date_filtered_out=filtered_out,
        )

    # --- inspection ---------------------------------------------------------

    def list_candidates(self, page: int = 1) -> tuple[list[CitationCandidate], int]:
        """Return (page of 10 candidates, total page count)."""
        total_pages = max(1, -(-len(self._candidates) // PAGE_SIZE))
        page = max(1, min(page, total_pages))
        start = (page - 1) * PAGE_SIZE
        return self._candidates[start:start + PAGE_SIZE], total_pages

    def get_candidate(self, candidate_id: str) -> CitationCandidate | None:
        for candidate in self._candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        return None

    def status(self) -> dict:
        return {
            "workflow_id": self._workflow_id or "none",
            "query": self._last_query,
            "date_filter": (
                self._date_filter.describe() if self._date_filter else "none"
            ),
            "candidates": len(self._candidates),
            "selected": self._selected_id or "none",
            "matches": len(self._matches),
            "attempts": self._attempts,
            "sources": len(self.registry.list()),
            "provider_states": [state.to_dict() for state in self._last_states],
        }

    def cancel(self) -> CitationResult:
        """Abort the current workflow; candidate/match IDs become stale."""
        had_workflow = bool(self._workflow_id)
        self._new_generation()
        self._workflow_id = ""
        return CitationResult(
            status="cancelled",
            message="workflow cancelled" if had_workflow else "no active workflow",
        )

    # --- resolution ----------------------------------------------------------

    async def select(self, candidate_id: str) -> SelectOutcome:
        """Resolve every confirmable match for one candidate. Never writes."""
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            return SelectOutcome(result=CitationResult(
                status="invalid_state",
                message=f"unknown or stale candidate id: {candidate_id}",
            ))
        self._clear_resolution()
        self._selected_id = candidate_id

        doi_candidates = extract_doi_candidates(
            candidate.doi, candidate.url, candidate.snippet, candidate.title
        )
        if not doi_candidates:
            return SelectOutcome(result=CitationResult(
                status="no_doi",
                message=(
                    "candidate has no DOI; it can be viewed but not saved as a "
                    "verified citation"
                ),
            ))

        matches: list[CitationMatch] = []
        states: list[ProviderState] = []
        seen_dois: set[str] = set()
        hard_failure: ProviderState | None = None
        for doi in doi_candidates:
            try:
                record = await self._hub.doi_org.fetch_structured(doi)
            except DoiNotFound:
                states.append(ProviderState("doi.org", "empty", f"{doi} does not resolve"))
                continue
            except ProviderRateLimited as exc:
                hard_failure = ProviderState("doi.org", "rate_limited", exc.detail)
                states.append(hard_failure)
                continue
            except ProviderTimeout as exc:
                hard_failure = ProviderState("doi.org", "timeout", exc.detail)
                states.append(hard_failure)
                continue
            except ProviderError as exc:
                hard_failure = ProviderState("doi.org", "error", exc.detail)
                states.append(hard_failure)
                continue
            if record.doi in seen_dois:
                continue
            seen_dois.add(record.doi)
            agency = ""
            try:
                agency = await self._hub.doi_org.fetch_registration_agency(record.doi)
            except ProviderError:
                agency = ""
            self._match_counter += 1
            matches.append(CitationMatch(
                match_id=f"m{self._match_counter}",
                candidate_id=candidate_id,
                canonical_doi=record.doi,
                registration_agency=agency,
                title=record.title,
                authors=list(record.authors) or None,
                year=record.year,
                venue=record.venue or None,
                work_type=record.work_type or None,
                lookup_provenance="doi.org-csl",
            ))
            states.append(ProviderState("doi.org", "ok", f"resolved {record.doi}"))

        if not matches:
            if hard_failure is not None:
                return SelectOutcome(
                    result=CitationResult(
                        status="provider_failed",
                        provider_states=states,
                        message="DOI lookup failed; try again later",
                    ),
                    provider_states=states,
                )
            return SelectOutcome(
                result=CitationResult(
                    status="no_doi",
                    provider_states=states,
                    message="no extracted DOI candidate resolves at doi.org",
                ),
                provider_states=states,
            )
        self._matches = {match.match_id: match for match in matches}
        return SelectOutcome(matches=matches, provider_states=states)

    # --- confirm: the only writer ---------------------------------------------

    async def confirm(self, match_id: str) -> CitationResult:
        """Verify, register, and persist one selected match."""
        match = self._matches.get(match_id)
        if match is None:
            return CitationResult(
                status="invalid_state",
                message=f"unknown or stale match id: {match_id}",
            )
        self._attempts += 1
        candidate = self.get_candidate(match.candidate_id)
        states: list[ProviderState] = []
        report = VerificationReport()

        # 1. Re-fetch the structured record; never trust the discovery copy.
        try:
            record = await self._hub.doi_org.fetch_structured(match.canonical_doi)
        except ProviderError as exc:
            states.append(ProviderState("doi.org", "error", exc.detail))
            return self._fail("provider_failed", states, report,
                              f"structured lookup failed: {exc.detail}")
        states.append(ProviderState("doi.org", "ok", "structured record fetched"))

        doi_ok = doi_equal(match.canonical_doi, record.doi)
        report.checks.append(VerificationCheck(
            name="match_doi_equals_structured_doi",
            passed=doi_ok,
            detail=f"match={match.canonical_doi} structured={record.doi}",
        ))
        if not doi_ok:
            return self._fail("verification_failed", states, report,
                              "structured record DOI differs from selected match")

        # 2. BibTeX for the same canonical DOI.
        try:
            raw_bibtex = await self._hub.doi_org.fetch_bibtex(record.doi)
        except ProviderError as exc:
            states.append(ProviderState("doi.org", "error", exc.detail))
            return self._fail("provider_failed", states, report,
                              f"BibTeX retrieval failed: {exc.detail}")
        try:
            canonical_bib = parse_canonical_bibtex(raw_bibtex)
        except BibtexValidationError as exc:
            report.checks.append(VerificationCheck(
                name="bibtex_canonical", passed=False, detail=f"{exc.code}: {exc}",
            ))
            return self._fail("verification_failed", states, report,
                              f"BibTeX validation failed ({exc.code})")
        report.checks.append(VerificationCheck(name="bibtex_canonical", passed=True))

        if canonical_bib.doi is not None:
            bib_doi_ok = doi_equal(canonical_bib.doi, record.doi)
            report.checks.append(VerificationCheck(
                name="bibtex_doi_equals_structured_doi",
                passed=bib_doi_ok,
                detail=f"bibtex={canonical_bib.doi} structured={record.doi}",
            ))
            if not bib_doi_ok:
                return self._fail("verification_failed", states, report,
                                  "BibTeX DOI differs from verified structured DOI")
        else:
            canonical_bib = inject_doi(canonical_bib, record.doi)
            report.codes.append("doi_injected_from_verified_lookup")
            report.checks.append(VerificationCheck(
                name="bibtex_doi_injected", passed=True,
                detail="BibTeX lacked a DOI; injected from verified lookup",
            ))

        # 3. Bibliographic conflicts warn but never block.
        self._collect_warnings(report, record, canonical_bib, candidate)

        # 4. Persist and register.
        source_ref = SourceRef(
            source_id=f"src-{doi_hash(record.doi)}",
            doi=record.doi,
            title=record.title or canonical_bib.title,
            authors=list(record.authors) or list(canonical_bib.authors),
            year=record.year if record.year is not None else canonical_bib.year,
            venue=record.venue or canonical_bib.venue,
            work_type=record.work_type,
            url=record.url or f"https://doi.org/{record.doi}",
            verification_level="identity_verified",
            provenance="doi.org-csl+bibtex",
        )
        sidecar = {
            "run_id": uuid.uuid4().hex,
            "source_ref": source_ref.to_dict(),
            "provider_states": [state.to_dict() for state in states],
            "candidate_snapshot": self._candidate_snapshot(candidate),
            "match_snapshot": {
                "match_id": match.match_id,
                "candidate_id": match.candidate_id,
                "canonical_doi": match.canonical_doi,
                "registration_agency": match.registration_agency,
                "lookup_provenance": match.lookup_provenance,
            },
            "verification": report.to_dict(),
            "previous_attempt_failure_codes": list(self._previous_failure_codes),
        }
        try:
            bundle = write_bundle(
                self._output_dir,
                canonical_doi=record.doi,
                title=source_ref.title,
                bibtex_text=canonical_bib.text,
                sidecar=sidecar,
            )
        except StorageError as exc:
            report.checks.append(VerificationCheck(
                name="bundle_write", passed=False, detail=f"{exc.code}: {exc}",
            ))
            return self._fail("storage_failed", states, report,
                              f"bundle write failed ({exc.code})")

        source_ref.bundle_path = str(bundle.bundle_dir)
        self.registry.register(source_ref)
        # Success completes the workflow; the registry survives.
        self._candidates = []
        self._clear_resolution()
        return CitationResult(
            status="confirmed",
            accepted_doi=record.doi,
            attempts=self._attempts,
            provider_states=states,
            verification=report,
            source=source_ref,
            bundle_path=str(bundle.bundle_dir),
            message=("bundle reused (same DOI already confirmed)"
                     if bundle.reused else "bundle written"),
        )

    def _fail(
        self,
        status: str,
        states: list[ProviderState],
        report: VerificationReport,
        message: str,
    ) -> CitationResult:
        # Failed confirms keep the resolved state so the user can pick a
        # different match; codes accumulate for the eventual sidecar.
        self._previous_failure_codes.append(status)
        return CitationResult(
            status=status,
            attempts=self._attempts,
            provider_states=states,
            verification=report,
            message=message,
        )

    @staticmethod
    def _candidate_snapshot(candidate: CitationCandidate | None) -> dict:
        if candidate is None:
            return {}
        return {
            "candidate_id": candidate.candidate_id,
            "workflow_id": candidate.workflow_id,
            "title": candidate.title,
            "authors": list(candidate.authors),
            "year": candidate.year,
            "venue": candidate.venue,
            "doi": candidate.doi,
            "url": candidate.url,
            "provider_ids": dict(candidate.provider_ids),
            "field_provenance": dict(candidate.field_provenance),
            "conflicts": dict(candidate.conflicts),
        }

    @staticmethod
    def _collect_warnings(
        report: VerificationReport,
        record: StructuredRecord,
        canonical_bib,
        candidate: CitationCandidate | None,
    ) -> None:
        def warn(text: str) -> None:
            if text not in report.warnings:
                report.warnings.append(text)

        if canonical_bib.title and record.title and not titles_match(
            canonical_bib.title, record.title
        ):
            warn(f"title conflict: structured={record.title!r} bibtex={canonical_bib.title!r}")
        if (
            canonical_bib.year is not None
            and record.year is not None
            and canonical_bib.year != record.year
        ):
            warn(f"year conflict: structured={record.year} bibtex={canonical_bib.year}")
        if candidate is not None:
            if candidate.title and record.title and not titles_match(
                candidate.title, record.title
            ):
                warn(f"title conflict: candidate={candidate.title!r} structured={record.title!r}")
            if (
                candidate.year is not None
                and record.year is not None
                and candidate.year != record.year
            ):
                warn(f"year conflict: candidate={candidate.year} structured={record.year}")

    # --- saved sources ---------------------------------------------------------

    def list_sources(self, page: int = 1) -> tuple[list[SourceRef], int]:
        sources = self.registry.list()
        total_pages = max(1, -(-len(sources) // PAGE_SIZE))
        page = max(1, min(page, total_pages))
        start = (page - 1) * PAGE_SIZE
        return sources[start:start + PAGE_SIZE], total_pages

    def activate_source(self, source_id: str) -> SourceRef | None:
        return self.registry.activate(source_id)
