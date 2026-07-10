"""The session-scoped ``citation_workflow`` tool.

The only model-facing surface of the :class:`CitationCoordinator`. The tool
validates parameters, serializes outcomes as plain text, and delegates every
state transition to the Coordinator — the search/verify state machine is
never reimplemented here. Web fallback stays an internal Coordinator concern;
the tool exposes no raw web search.

Safety rails owned by this layer:
  * one workflow call at a time per session — a concurrent call returns a
    busy error instead of interleaving with the stateful Coordinator;
  * ``confirm`` must arrive in a *later user turn* than the ``select`` that
    produced the match, so at least one explicit user confirmation separates
    resolving a match from writing the bundle;
  * date filtering is either ``published_within_years`` or
    ``year_from``/``year_to`` — never both — and only applies to ``search``.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from skills.citation.coordinator import (
    CitationCoordinator,
    SearchOutcome,
    SelectOutcome,
)
from skills.citation.types import (
    CitationCandidate,
    CitationMatch,
    CitationResult,
    PublishedDateFilter,
    SourceRef,
)

TOOL_NAME = "citation_workflow"

TOOL_DESCRIPTION = (
    "Drive the interactive citation workflow: search for academic papers, "
    "inspect candidates, resolve DOI matches, and save verified citation "
    "bundles. Actions: 'search' (requires query; optionally EITHER "
    "published_within_years OR year_from/year_to), 'more' (append web "
    "results to the current search), 'list' (page through candidates), "
    "'show' (identifier = candidate id), 'select' (identifier = candidate "
    "id; resolves confirmable matches), 'confirm' (identifier = match id; "
    "call ONLY after the user explicitly confirmed the match in a later "
    "message — never in the same turn as select), 'status', 'cancel', "
    "'sources' (list saved sources), 'source' (identifier = source id; "
    "re-activate a saved source for citing). Present candidates and matches "
    "to the user and wait for their choice; the tool refuses same-turn "
    "confirms and concurrent calls."
)

CitationAction = Literal[
    "search",
    "more",
    "list",
    "show",
    "select",
    "confirm",
    "status",
    "cancel",
    "sources",
    "source",
]

_IDENTIFIER_ACTIONS = {"show", "select", "confirm", "source"}
_PAGE_ACTIONS = {"list", "sources"}


class CitationWorkflowInput(BaseModel):
    """Input schema for the citation_workflow tool."""

    action: CitationAction = Field(description="Workflow step to perform.")
    query: str | None = Field(
        None, description="Search text (search; optional refinement for more)."
    )
    identifier: str | None = Field(
        None,
        description=(
            "Candidate id (show/select), match id (confirm), or source id "
            "(source)."
        ),
    )
    page: int | None = Field(
        None, description="1-based page for list/sources (default 1)."
    )
    published_within_years: int | None = Field(
        None,
        description=(
            "search only: keep works published within the last N years "
            "(window computed from today, UTC). Mutually exclusive with "
            "year_from/year_to."
        ),
    )
    year_from: int | None = Field(
        None,
        description=(
            "search only: earliest publication year (inclusive). Mutually "
            "exclusive with published_within_years."
        ),
    )
    year_to: int | None = Field(
        None,
        description=(
            "search only: latest publication year (inclusive). Mutually "
            "exclusive with published_within_years."
        ),
    )


# --- formatting -------------------------------------------------------------


def _candidate_lines(candidate: CitationCandidate) -> list[str]:
    lines = [f"[{candidate.candidate_id}] {candidate.short_label()}"]
    if candidate.doi:
        lines.append(f"      DOI: {candidate.doi}")
    if candidate.venue:
        lines.append(f"      venue: {candidate.venue}")
    providers = ", ".join(sorted(candidate.provider_ids))
    if providers:
        lines.append(f"      providers: {providers}")
    if candidate.related_group:
        lines.append(f"      related-version group: {candidate.related_group}")
    return lines


def format_candidates(
    candidates: list[CitationCandidate], *, page: int = 1, total_pages: int = 1
) -> str:
    if not candidates:
        return "no candidates"
    lines = [f"Candidates (page {page}/{total_pages}):"]
    for candidate in candidates:
        lines.extend(_candidate_lines(candidate))
    lines.append(
        "Present these to the user and wait for their choice; then use "
        "action=show for details or action=select with the chosen candidate id."
    )
    return "\n".join(lines)


def format_candidate_detail(candidate: CitationCandidate) -> str:
    lines = [f"Candidate {candidate.candidate_id} (workflow {candidate.workflow_id}):"]
    lines.append(f"  title: {candidate.title or '(unknown)'}")
    if candidate.authors:
        lines.append(f"  authors: {', '.join(candidate.authors)}")
    for label, value in (
        ("year", candidate.year),
        ("venue", candidate.venue),
        ("DOI", candidate.doi),
        ("URL", candidate.url),
        ("related-version group", candidate.related_group),
    ):
        if value:
            lines.append(f"  {label}: {value}")
    if candidate.snippet:
        lines.append(f"  snippet: {candidate.snippet[:200]}")
    for provider, pid in sorted(candidate.provider_ids.items()):
        rank = candidate.provider_ranks.get(provider)
        lines.append(f"  provider {provider}: {pid} (rank {rank})")
    for field_name, provider in sorted(candidate.field_provenance.items()):
        lines.append(f"  provenance {field_name}: {provider}")
    for field_name, values in sorted(candidate.conflicts.items()):
        rendered = "; ".join(f"{v['provider']}={v['value']!r}" for v in values)
        lines.append(f"  conflict {field_name}: {rendered}")
    return "\n".join(lines)


def format_search_outcome(outcome: SearchOutcome, *, appended: bool = False) -> str:
    if outcome.error:
        return f"error: {outcome.error}"
    lines = []
    verb = "appended" if appended else "found"
    lines.append(f"{verb} {len(outcome.candidates)} candidate(s)")
    if outcome.date_filtered_out:
        lines.append(
            f"({outcome.date_filtered_out} candidate(s) dropped by the date "
            "filter: unknown or out-of-window publication year)"
        )
    if outcome.used_web_fallback:
        lines.append("(web search results included)")
    for state in outcome.provider_states:
        detail = f" — {state.detail}" if state.detail else ""
        lines.append(f"  provider {state.provider}: {state.status}{detail}")
    if outcome.candidates:
        lines.append("")
        lines.append(format_candidates(outcome.candidates))
    return "\n".join(lines)


def format_matches(matches: list[CitationMatch]) -> str:
    lines = ["Confirmable matches:"]
    for match in matches:
        lines.append(f"[{match.match_id}] DOI {match.canonical_doi}")
        if match.title:
            lines.append(f"      title: {match.title}")
        meta = []
        if match.year is not None:
            meta.append(str(match.year))
        if match.venue:
            meta.append(match.venue)
        if match.registration_agency:
            meta.append(f"RA: {match.registration_agency}")
        if meta:
            lines.append(f"      {' | '.join(meta)}")
    lines.append(
        "Show these matches to the user. Only after the user explicitly "
        "confirms in a later message, call action=confirm with the match id."
    )
    return "\n".join(lines)


def format_result(result: CitationResult) -> str:
    lines = [f"citation {result.status}: {result.message}".rstrip(": ")]
    if result.source is not None:
        lines.append(
            f"  source: {result.source.source_id} "
            f"({result.source.verification_level})"
        )
        lines.append(f"  cite with [[cite:{result.source.source_id}]]")
    if result.accepted_doi:
        lines.append(f"  DOI: {result.accepted_doi}")
    if result.bundle_path:
        lines.append(f"  bundle: {result.bundle_path}")
    if result.verification is not None:
        for warning in result.verification.warnings:
            lines.append(f"  warning: {warning}")
        for code in result.verification.codes:
            lines.append(f"  code: {code}")
        for check in result.verification.checks:
            if not check.passed:
                lines.append(f"  failed check: {check.name} ({check.detail})")
    return "\n".join(lines)


def format_sources(sources: list[SourceRef], *, page: int, total_pages: int) -> str:
    if not sources:
        return "no saved sources in this session"
    lines = [f"Sources (page {page}/{total_pages}):"]
    for ref in sources:
        label = ref.title or ref.doi or ref.url or "(unknown)"
        lines.append(f"[{ref.source_id}] {label}")
        meta = [ref.verification_level]
        if ref.doi:
            meta.append(f"DOI {ref.doi}")
        if ref.year:
            meta.append(str(ref.year))
        lines.append(f"      {' | '.join(meta)}")
    lines.append(
        "Use action=source with a source id to re-activate one for citing."
    )
    return "\n".join(lines)


def format_source_detail(ref: SourceRef) -> str:
    lines = [f"Source {ref.source_id} re-activated:"]
    lines.append(f"  title: {ref.title or '(unknown)'}")
    if ref.authors:
        lines.append(f"  authors: {', '.join(ref.authors)}")
    for label, value in (
        ("year", ref.year), ("venue", ref.venue), ("DOI", ref.doi),
        ("URL", ref.url), ("bundle", ref.bundle_path),
    ):
        if value:
            lines.append(f"  {label}: {value}")
    lines.append(f"  verification: {ref.verification_level}")
    lines.append(f"  cite with [[cite:{ref.source_id}]]")
    return "\n".join(lines)


def format_status(status: dict) -> str:
    lines = ["Citation workflow status:"]
    for key in ("workflow_id", "query", "date_filter", "candidates", "selected",
                "matches", "attempts", "sources"):
        lines.append(f"  {key}: {status.get(key)}")
    for state in status.get("provider_states", []):
        detail = f" — {state.get('detail')}" if state.get("detail") else ""
        lines.append(
            f"  provider {state.get('provider')}: {state.get('status')}{detail}"
        )
    return "\n".join(lines)


# --- parameter validation ----------------------------------------------------


def _validation_error(detail: str) -> str:
    return f"error: {detail}"


def _build_date_filter(
    *,
    published_within_years: int | None,
    year_from: int | None,
    year_to: int | None,
) -> PublishedDateFilter | None:
    has_range = year_from is not None or year_to is not None
    if published_within_years is not None and has_range:
        raise ValueError(
            "published_within_years and year_from/year_to are mutually "
            "exclusive; use one date mode"
        )
    if published_within_years is not None:
        return PublishedDateFilter.within_years(published_within_years)
    if has_range:
        return PublishedDateFilter.from_year_range(year_from, year_to)
    return None


# --- the tool ----------------------------------------------------------------


def create_citation_workflow_tool(
    *,
    coordinator_getter: Callable[[], CitationCoordinator],
    turn_getter: Callable[[], int],
) -> StructuredTool:
    """Build the session-scoped citation_workflow StructuredTool.

    ``coordinator_getter`` returns the session Coordinator lazily (so merely
    creating the tool never touches providers); ``turn_getter`` returns the
    session's completed-turn counter, used to enforce that confirm happens in
    a later user turn than select.
    """
    busy_lock = asyncio.Lock()
    # Turn (as reported by turn_getter) in which the current matches were
    # resolved; None when there is no live selection.
    select_turn: int | None = None

    async def _dispatch(
        action: CitationAction,
        query: str | None,
        identifier: str | None,
        page: int | None,
        published_within_years: int | None,
        year_from: int | None,
        year_to: int | None,
    ) -> str:
        nonlocal select_turn
        coordinator = coordinator_getter()

        has_date_args = (
            published_within_years is not None
            or year_from is not None
            or year_to is not None
        )
        if has_date_args and action != "search":
            return _validation_error(
                "date filters only apply to action='search'"
            )
        if action in _IDENTIFIER_ACTIONS and not (identifier or "").strip():
            return _validation_error(f"action '{action}' requires identifier")
        if page is not None and action not in _PAGE_ACTIONS:
            return _validation_error("page only applies to list/sources")
        if page is not None and page < 1:
            return _validation_error("page must be >= 1")

        if action == "search":
            if not (query or "").strip():
                return _validation_error("action 'search' requires query")
            try:
                date_filter = _build_date_filter(
                    published_within_years=published_within_years,
                    year_from=year_from,
                    year_to=year_to,
                )
            except ValueError as exc:
                return _validation_error(str(exc))
            select_turn = None
            outcome = await coordinator.search(query, date_filter=date_filter)
            return format_search_outcome(outcome)

        if action == "more":
            outcome = await coordinator.more(query)
            return format_search_outcome(outcome, appended=True)

        if action == "list":
            candidates, total_pages = coordinator.list_candidates(page or 1)
            return format_candidates(
                candidates,
                page=min(page or 1, total_pages),
                total_pages=total_pages,
            )

        if action == "show":
            candidate = coordinator.get_candidate(identifier)
            if candidate is None:
                return f"unknown or stale candidate id: {identifier}"
            return format_candidate_detail(candidate)

        if action == "select":
            outcome: SelectOutcome = await coordinator.select(identifier)
            if outcome.result is not None:
                return format_result(outcome.result)
            select_turn = turn_getter()
            return format_matches(outcome.matches)

        if action == "confirm":
            if select_turn is not None and turn_getter() <= select_turn:
                return _validation_error(
                    "confirm refused: the user has not confirmed this match "
                    "in a later message. Present the matches and wait for an "
                    "explicit user confirmation before calling confirm."
                )
            result = await coordinator.confirm(identifier)
            if result.status == "confirmed":
                select_turn = None
            return format_result(result)

        if action == "status":
            return format_status(coordinator.status())

        if action == "cancel":
            select_turn = None
            return format_result(coordinator.cancel())

        if action == "sources":
            sources, total_pages = coordinator.list_sources(page or 1)
            return format_sources(
                sources,
                page=min(page or 1, total_pages),
                total_pages=total_pages,
            )

        if action == "source":
            ref = coordinator.activate_source(identifier)
            if ref is None:
                return f"unknown source id: {identifier}"
            return format_source_detail(ref)

        return _validation_error(f"unknown action: {action}")

    async def _run(
        action: CitationAction,
        query: str | None = None,
        identifier: str | None = None,
        page: int | None = None,
        published_within_years: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> str:
        if busy_lock.locked():
            return _validation_error(
                "citation workflow busy: another workflow call is still "
                "running in this session; wait for it to finish"
            )
        async with busy_lock:
            return await _dispatch(
                action, query, identifier, page,
                published_within_years, year_from, year_to,
            )

    _run.__name__ = TOOL_NAME

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        args_schema=CitationWorkflowInput,
        infer_schema=False,
    )
