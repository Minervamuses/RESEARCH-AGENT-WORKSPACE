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
    ``year_from``/``year_to`` — never both — and applies only to ``search``
    and the provider-free ``refine`` view.
"""

from __future__ import annotations

import asyncio
import re
from typing import Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from skills.citation.coordinator import (
    PAGE_SIZE,
    CitationCoordinator,
    RefineOutcome,
    SearchOutcome,
    SelectOutcome,
)
from skills.citation.confirmation import classify_confirmation
from skills.citation.doi import extract_doi_candidates
from skills.citation.types import (
    CitationCandidate,
    CitationMatch,
    CitationResult,
    ConfirmReceipt,
    PublishedDateFilter,
    SourceRef,
)

TOOL_NAME = "citation_workflow"

TOOL_DESCRIPTION = (
    "Drive the interactive citation workflow: search for academic papers, "
    "inspect candidates, resolve DOI matches, and save verified citation "
    "bundles. Actions: 'search' (requires query; optionally EITHER "
    "published_within_years OR year_from/year_to), 'more' (append web "
    "results to the current search), 'refine' (filter the current candidate "
    "pool without new provider calls), 'list' (page through the active view), "
    "'show' (identifier = candidate id), 'select' (identifier = candidate "
    "id; resolves confirmable matches), 'confirm' (identifier = match id; "
    "call ONLY after the user explicitly approved in a later message using "
    "a clear phrase such as 儲存/確認/OK/就這篇 — never in the same turn as "
    "select; ambiguous multiple matches require an explicit mX), 'status', "
    "'explain' (read-only: how the workflow verifies citations and where "
    "bundles are stored), 'cancel', "
    "'sources' (list saved sources), 'source' (identifier = source id; "
    "re-activate a saved source for citing). Present candidates and matches "
    "to the user and wait for their choice; the tool refuses same-turn "
    "confirms and concurrent calls."
)

CitationAction = Literal[
    "search",
    "more",
    "refine",
    "list",
    "show",
    "select",
    "confirm",
    "status",
    "explain",
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
    keywords: list[str] | None = Field(
        None,
        description=(
            "refine only: every normalized keyword must occur in candidate "
            "metadata; omit all refine fields to reset the active view."
        ),
    )
    venues: list[str] | None = Field(
        None,
        description="refine only: match any normalized venue substring.",
    )
    work_types: list[str] | None = Field(
        None,
        description="refine only: match any normalized work type exactly.",
    )
    published_within_years: int | None = Field(
        None,
        description=(
            "search/refine only: keep works published within the last N years "
            "(window computed from today, UTC). Mutually exclusive with "
            "year_from/year_to."
        ),
    )
    year_from: int | None = Field(
        None,
        description=(
            "search/refine only: earliest publication year (inclusive). Mutually "
            "exclusive with published_within_years."
        ),
    )
    year_to: int | None = Field(
        None,
        description=(
            "search/refine only: latest publication year (inclusive). Mutually "
            "exclusive with published_within_years."
        ),
    )


# --- formatting -------------------------------------------------------------


def _candidate_lines(candidate: CitationCandidate) -> list[str]:
    lines = [f"[{candidate.candidate_id}] {_redact_dois(candidate.short_label())}"]
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
    if total_pages > 1:
        lines.append(
            "Prefer action=refine when conditions change; use action=list with "
            "a page number only when the user explicitly asks to browse more."
        )
    lines.append(
        "Present these to the user and wait for their choice; then use "
        "action=show for details or action=select with the chosen candidate id."
    )
    return _redact_dois("\n".join(lines))


def format_shortlist(
    candidates: list[CitationCandidate],
    *,
    total_matches: int,
    label: str = "Shortlist",
) -> str:
    visible = candidates[:PAGE_SIZE]
    if not visible:
        return f"{label}: 0 of {total_matches} candidate(s)"
    lines = [f"{label}: {len(visible)} of {total_matches} candidate(s)"]
    for candidate in visible:
        lines.extend(_candidate_lines(candidate))
    lines.append(
        "Present this shortlist to the user. If their conditions change, use "
        "action=refine instead of scanning every candidate page."
    )
    return _redact_dois("\n".join(lines))


def format_candidate_detail(candidate: CitationCandidate) -> str:
    lines = [f"Candidate {candidate.candidate_id} (workflow {candidate.workflow_id}):"]
    lines.append(f"  title: {candidate.title or '(unknown)'}")
    if candidate.authors:
        lines.append(f"  authors: {', '.join(candidate.authors)}")
    for label, value in (
        ("year", candidate.year),
        ("venue", candidate.venue),
        ("related-version group", candidate.related_group),
    ):
        if value:
            lines.append(f"  {label}: {value}")
    if candidate.snippet:
        lines.append(f"  snippet: {candidate.snippet[:200]}")
    for provider in sorted(candidate.provider_ids):
        rank = candidate.provider_ranks.get(provider)
        lines.append(f"  provider {provider}: available (rank {rank})")
    for field_name, provider in sorted(candidate.field_provenance.items()):
        lines.append(f"  provenance {field_name}: {provider}")
    for field_name, values in sorted(candidate.conflicts.items()):
        if field_name.casefold() in {"doi", "url"}:
            continue
        rendered = "; ".join(f"{v['provider']}={v['value']!r}" for v in values)
        lines.append(f"  conflict {field_name}: {rendered}")
    lines.append("  DOI is withheld until a match is explicitly confirmed.")
    return _redact_dois("\n".join(lines))


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
        if appended:
            lines.append(format_shortlist(
                outcome.candidates,
                total_matches=len(outcome.candidates),
                label="Appended candidates",
            ))
        else:
            lines.append(format_shortlist(
                outcome.candidates,
                total_matches=len(outcome.candidates),
            ))
    return "\n".join(lines)


def format_refine_outcome(outcome: RefineOutcome) -> str:
    if outcome.error:
        return f"error: {outcome.error}"
    verb = "refinement reset" if outcome.reset else "refined candidate view"
    lines = [
        f"{verb}: {len(outcome.candidates)} match(es) from pool of "
        f"{outcome.pool_size}"
    ]
    lines.append(format_shortlist(
        outcome.candidates,
        total_matches=len(outcome.candidates),
    ))
    return "\n".join(lines)


def format_matches(matches: list[CitationMatch]) -> str:
    lines = ["Confirmable matches:"]
    for match in matches:
        lines.append(f"[{match.match_id}] confirmable match")
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
    lines.append("Do not expose a DOI literal before confirm succeeds; use mX ids.")
    return _redact_dois("\n".join(lines))


def format_result(result: CitationResult) -> str:
    lines = [f"citation {result.status}: {result.message}".rstrip(": ")]
    if result.source is not None:
        lines.append(
            f"  source: {result.source.source_id} "
            f"({result.source.verification_level})"
        )
        lines.append(f"  cite with [[cite:{result.source.source_id}]]")
    if result.accepted_doi:
        lines.append(f"  DOI: {_code_span(result.accepted_doi)}")
    if result.bundle_path:
        lines.append(f"  bundle: {_code_span(result.bundle_path)}")
    if result.verification is not None:
        for warning in result.verification.warnings:
            lines.append(f"  warning: {warning}")
        for code in result.verification.codes:
            lines.append(f"  code: {code}")
        for check in result.verification.checks:
            if not check.passed:
                lines.append(f"  failed check: {check.name} ({check.detail})")
    text = "\n".join(lines)
    return text if result.status == "confirmed" else _redact_dois(text)


def format_sources(sources: list[SourceRef], *, page: int, total_pages: int) -> str:
    if not sources:
        return "no saved sources in this session"
    lines = [f"Sources (page {page}/{total_pages}):"]
    for ref in sources:
        label = ref.title or "(untitled verified source)"
        lines.append(f"[{ref.source_id}] {_redact_dois(label)}")
        meta = [ref.verification_level]
        if ref.doi:
            meta.append(f"DOI {_code_span(ref.doi)}")
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
    for label, value in (("year", ref.year), ("venue", ref.venue)):
        if value:
            lines.append(f"  {label}: {value}")
    if ref.doi:
        lines.append(f"  DOI: {_code_span(ref.doi)}")
    if ref.url:
        rendered_url = _code_span(ref.url) if extract_doi_candidates(ref.url) else ref.url
        lines.append(f"  URL: {rendered_url}")
    if ref.bundle_path:
        lines.append(f"  bundle: {_code_span(ref.bundle_path)}")
    lines.append(f"  verification: {ref.verification_level}")
    lines.append(f"  cite with [[cite:{ref.source_id}]]")
    return "\n".join(lines)


def format_status(status: dict) -> str:
    lines = ["Citation workflow status:"]
    for key in (
        "workflow_id", "query", "date_filter", "candidates",
        "view_candidates", "refinement", "selected", "matches", "attempts",
        "sources",
    ):
        lines.append(f"  {key}: {status.get(key)}")
    for state in status.get("provider_states", []):
        detail = f" — {state.get('detail')}" if state.get("detail") else ""
        lines.append(
            f"  provider {state.get('provider')}: {state.get('status')}{detail}"
        )
    return "\n".join(lines)


def format_explain(output_dir: object) -> str:
    """Deterministic public contract of the workflow; the model must not
    invent internals beyond this text."""
    lines = [
        "Citation workflow — public contract:",
        "  1. search: discovery providers (Crossref, plus OpenAlex when",
        "     enabled) build the candidate pool; candidates usually already",
        "     carry a DOI. Web results are a fallback, never a verifier.",
        "  2. select: DOI candidates are extracted from the chosen",
        "     candidate's stored DOI/URL/snippet/title fields.",
        "  3. Each extracted DOI is resolved at doi.org into a structured",
        "     CSL record, and its registration agency is looked up.",
        "  4. confirm runs only after the user explicitly approves in a",
        "     later message. It re-fetches the CSL record from doi.org and",
        "     never trusts the discovery copy.",
        "  5. BibTeX is retrieved from doi.org via content negotiation for",
        "     the same DOI; it is never written by the model.",
        "  6. The system parses that BibTeX and verifies the selected match,",
        "     the CSL record, and the BibTeX agree on one canonical DOI.",
        "  7. On success the bundle — reference.bib plus a citation.json",
        "     sidecar — is written atomically under the citation output",
        "     directory: user data, never inside the project source tree.",
        f"  Current citation output directory: {_code_span(output_dir)}",
        "  Each bundle is one <title>--<doi-hash> directory; re-confirming",
        "  the same DOI validates and reuses the existing bundle.",
        "For saved sources and their exact bundle paths, use action=sources",
        "or action=source with a source id; never guess or scan directories.",
    ]
    return "\n".join(lines)


# --- parameter validation ----------------------------------------------------


def _validation_error(detail: str) -> str:
    return f"error: {detail}"


def _code_span(value: object) -> str:
    """Render arbitrary one-line data as a valid Markdown code span."""
    text = str(value).replace("\n", " ")
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    if text.startswith(("`", " ")) or text.endswith(("`", " ")):
        text = f" {text} "
    return f"{fence}{text}{fence}"


def _redact_dois(text: str) -> str:
    """Remove DOI literals from pre-confirm model-facing content."""
    out = text
    for doi in extract_doi_candidates(text):
        out = re.sub(re.escape(doi), "[DOI withheld until confirm]", out, flags=re.I)
    return out


def _confirm_receipt(result: CitationResult) -> ConfirmReceipt:
    if (
        result.status != "confirmed"
        or result.source is None
        or not result.accepted_doi
        or not result.bundle_path
    ):
        raise ValueError("a complete confirmed result is required for a receipt")
    return ConfirmReceipt(
        source_id=result.source.source_id,
        accepted_doi=result.accepted_doi,
        bundle_path=result.bundle_path,
        verification_level=result.source.verification_level,
        cite_marker=f"[[cite:{result.source.source_id}]]",
        warnings=tuple(
            result.verification.warnings if result.verification is not None else ()
        ),
    )


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
    user_input_getter: Callable[[], str],
) -> StructuredTool:
    """Build the session-scoped citation_workflow StructuredTool.

    ``coordinator_getter`` returns the session Coordinator lazily (so merely
    creating the tool never touches providers); ``turn_getter`` returns the
    session's completed-turn counter, used to enforce that confirm happens in
    a later user turn than select. ``user_input_getter`` supplies the current
    raw user message for a conservative, deterministic approval check.
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
        keywords: list[str] | None,
        venues: list[str] | None,
        work_types: list[str] | None,
        published_within_years: int | None,
        year_from: int | None,
        year_to: int | None,
    ) -> str | tuple[str, dict]:
        nonlocal select_turn
        coordinator = coordinator_getter()

        has_date_args = (
            published_within_years is not None
            or year_from is not None
            or year_to is not None
        )
        if has_date_args and action not in {"search", "refine"}:
            return _validation_error(
                "date filters only apply to action='search' or action='refine'"
            )
        has_refine_args = any(value is not None for value in (
            keywords, venues, work_types,
        ))
        if has_refine_args and action != "refine":
            return _validation_error(
                "keywords/venues/work_types only apply to action='refine'"
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
            select_turn = None
            outcome = await coordinator.more(query)
            return format_search_outcome(outcome, appended=True)

        if action == "refine":
            try:
                date_filter = _build_date_filter(
                    published_within_years=published_within_years,
                    year_from=year_from,
                    year_to=year_to,
                )
            except ValueError as exc:
                return _validation_error(str(exc))
            select_turn = None
            outcome = coordinator.refine(
                keywords=keywords,
                venues=venues,
                work_types=work_types,
                date_filter=date_filter,
            )
            return format_refine_outcome(outcome)

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
            decision = classify_confirmation(
                user_input_getter(),
                coordinator.pending_matches(),
                requested_match_id=identifier,
            )
            if not decision.approved:
                return _validation_error(
                    "confirm refused: the current user message is not an "
                    f"unambiguous explicit approval ({decision.reason})."
                )
            result = await coordinator.confirm(decision.match_id)
            if result.status == "confirmed":
                select_turn = None
                receipt = _confirm_receipt(result)
                return format_result(result), receipt.to_artifact()
            return format_result(result)

        if action == "status":
            return format_status(coordinator.status())

        if action == "explain":
            return format_explain(coordinator.output_dir)

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
        keywords: list[str] | None = None,
        venues: list[str] | None = None,
        work_types: list[str] | None = None,
        published_within_years: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> tuple[str, dict | None]:
        if busy_lock.locked():
            return _validation_error(
                "citation workflow busy: another workflow call is still "
                "running in this session; wait for it to finish"
            ), None
        async with busy_lock:
            result = await _dispatch(
                action, query, identifier, page,
                keywords, venues, work_types,
                published_within_years, year_from, year_to,
            )
            if isinstance(result, tuple):
                return result
            return result, None

    _run.__name__ = TOOL_NAME

    return StructuredTool.from_function(
        coroutine=_run,
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        args_schema=CitationWorkflowInput,
        infer_schema=False,
        response_format="content_and_artifact",
    )
