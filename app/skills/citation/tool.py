"""Model-facing citation workflow with stateless search and verified saving."""

from __future__ import annotations

import asyncio
import json
import weakref
from typing import Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from skills.citation.resolution import (
    WorkIdentifier,
    WorkIntent,
)
from skills.citation.types import PublishedDateFilter, SourceRef

TOOL_NAME = "citation_workflow"
TOOL_DESCRIPTION = (
    "Academic citation workflow. search(query, optional year range) is "
    "stateless discovery that returns numbered records, each carrying its own "
    "DOI/arXiv identifier. save(works=[WorkIntent...]) verifies and stores each "
    "selected work. When the selected record shows a DOI or arXiv identifier, "
    "pass requested_label plus that identifier; the workflow fetches "
    "authoritative doi.org metadata and BibTeX itself, so do not re-type title, "
    "authors, year, venue, or work_type. Only when no identifier exists, give "
    "the known title, authors, year, venue, work_type, work_kind, and "
    "version_kind as separate fields for a descriptive best match. Never invent "
    "bibliographic facts, pass provider syntax, or pass a result number. save "
    "returns the actual per-item persistence result."
)

CitationAction = Literal["search", "save", "sources", "source", "explain"]


class IdentifierInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["doi", "arxiv"] = Field(
        description="The identifier namespace; use only DOI or arXiv."
    )
    value: str = Field(
        min_length=1,
        max_length=2048,
        description=(
            "The DOI or arXiv identifier for the selected manifestation, copied "
            "exactly from the selected search record or the conversation."
        ),
    )


class WorkIntentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    requested_label: str = Field(
        min_length=1,
        max_length=160,
        description=(
            "A short user-facing label for this requested work. Keep an unresolved "
            "acronym here; never expand it into a guessed title."
        ),
    )
    title: str = Field(
        default="",
        max_length=512,
        description=(
            "The work title only. Needed only when no DOI/arXiv identifier is "
            "available."
        ),
    )
    authors: list[str] = Field(
        default_factory=list,
        max_length=32,
        description="Separate human author names; do not append them to title.",
    )
    year: int | None = Field(
        default=None,
        ge=1000,
        le=2999,
        description="A bibliographic year hint, not a provider query fragment.",
    )
    venue: str = Field(
        default="",
        max_length=256,
        description="A human-readable venue, not an API filter expression.",
    )
    work_type: str = Field(
        default="",
        max_length=256,
        description=(
            "The bibliographic work type, such as journal article or conference "
            "paper; this is not the publication manifestation."
        ),
    )
    work_kind: Literal["original_research"] | None = Field(
        default=None,
        description=(
            "A requested semantic work class. Use original_research only when "
            "the user explicitly distinguishes the original research work from "
            "a review, tutorial, or derivative work."
        ),
    )
    version_kind: Literal[
        "published", "preprint", "repository", "repost", "earliest"
    ] | None = Field(
        default=None,
        description=(
            "The requested publication manifestation. Use only a user-stated or "
            "visibly reported value; omit it when unknown. 'earliest' is a "
            "selection request, not observed provider metadata."
        ),
    )
    identifiers: list[IdentifierInput] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "The selected record's DOI or arXiv identifier. This is the "
            "preferred, sufficient save target: the workflow fetches the "
            "authoritative metadata for it. Do not combine identifiers "
            "belonging to different versions."
        ),
    )

    def to_domain(self) -> WorkIntent:
        return WorkIntent(
            requested_label=self.requested_label,
            title=self.title,
            authors=tuple(self.authors),
            year=self.year,
            venue=self.venue,
            work_type=self.work_type,
            work_kind=self.work_kind,
            version_kind=self.version_kind,
            identifiers=tuple(
                WorkIdentifier(identifier.kind, identifier.value)
                for identifier in self.identifiers
            ),
        )


class CitationWorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: CitationAction = Field(description="The citation workflow operation.")
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="A natural-language topic/title query, never provider syntax.",
    )
    works: list[WorkIntentInput] | None = Field(
        default=None,
        min_length=1,
        max_length=10,
        description="Self-contained work intents; accepted only by save.",
    )
    source_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="A stable saved source ID; accepted only by source.",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="One-based page number; accepted only by sources.",
    )
    year_from: int | None = Field(
        default=None,
        ge=1000,
        le=2999,
        description="Inclusive publication-year lower bound for search.",
    )
    year_to: int | None = Field(
        default=None,
        ge=1000,
        le=2999,
        description="Inclusive publication-year upper bound for search.",
    )


def _error(message: str) -> str:
    return f"validation error: {message}"


def _format_records(records, states) -> str:
    if not records:
        if states and not any(state.endswith(":ok") for state in states):
            return (
                "Search failed: no provider answered successfully ("
                + "; ".join(states)
                + "). This is not evidence that the work does not exist; "
                "retry the search later."
            )
        return "No bibliographic records found. " + "; ".join(states)
    lines = [
        f"Found {len(records)} bibliographic record(s). Each numbered block is "
        "one record; its metadata and identifiers belong together:"
    ]
    for number, record in enumerate(records, start=1):
        arxiv = record.identifiers.get("arxiv")
        lines.append(f"{number}. {record.title or 'untitled'}")
        lines.append(f"   authors: {', '.join(record.authors) or 'unknown'}")
        lines.append(
            f"   year: {record.year or 'unknown'}; "
            f"venue: {record.venue or 'unknown'}; "
            f"type: {record.work_type or 'unknown'}; "
            f"version: {record.version_kind or 'unknown'}"
        )
        if record.doi:
            lines.append(f"   DOI: {record.doi}")
        if arxiv:
            lines.append(f"   arXiv: {arxiv}")
        if record.url:
            lines.append(f"   URL: {record.url}")
        if not record.doi and not arxiv:
            lines.append(
                "   no DOI/arXiv identifier: saving needs descriptive fields"
            )
    lines.append("Provider states: " + "; ".join(states))
    lines.append(
        "To save a record, pass requested_label plus that block's DOI (or "
        "arXiv identifier) in identifiers; the workflow fetches authoritative "
        "metadata itself, so descriptive fields are unnecessary. Block numbers "
        "are display labels, never save identifiers."
    )
    return "\n".join(lines)


def _format_sources(sources: list[SourceRef], page: int, total_pages: int) -> str:
    if not sources:
        return "No saved sources in this session."
    lines = [f"Saved sources (page {page}/{total_pages}):"]
    for ref in sources:
        lines.append(f"- {ref.source_id}: {ref.title} ({ref.year or 'year unknown'})")
    return "\n".join(lines)


def _format_source(ref: SourceRef) -> str:
    return "\n".join([
        f"Source {ref.source_id}", f"title: {ref.title}",
        f"authors: {', '.join(ref.authors) or 'unknown'}",
        f"year: {ref.year or 'unknown'}", f"venue: {ref.venue or 'unknown'}",
        f"type: {ref.work_type or 'unknown'}", f"marker: [[cite:{ref.source_id}]]",
    ])


def format_explain(output_dir) -> str:
    return (
        "search is stateless and returns numbered record blocks with full "
        "metadata plus stable DOI/arXiv identifiers, without cX/mX IDs. "
        "save accepts 1–10 WorkIntent objects. A DOI goes straight to doi.org "
        "verification (CSL JSON and BibTeX) without another search; only a "
        "work without any identifier is resolved through provider-specific "
        "Crossref, DataCite, and optional OpenAlex queries. Authoritative "
        "metadata and BibTeX are verified before persistence, and save returns "
        "the actual result for every requested item. The agent owns "
        "conversational target and authorization decisions; bundles are "
        "written atomically under "
        + str(output_dir)
    )


def create_citation_workflow_tool(
    *,
    service_getter: Callable | None = None,
) -> StructuredTool:
    if service_getter is None:
        raise ValueError("service_getter is required")
    # asyncio primitives are loop-bound once contended. Keep one serializer
    # per loop so a tool reused by tests or library callers across
    # ``asyncio.run`` invocations remains valid; storage has its own
    # cross-process identity lock for the actual filesystem mutation.
    save_locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    def _save_lock() -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        lock = save_locks.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            save_locks[loop] = lock
        return lock

    async def _run(
        action: CitationAction,
        query: str | None = None,
        works: list[WorkIntentInput] | None = None,
        source_id: str | None = None,
        page: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> tuple[str, dict | None]:
        payload_size = len(json.dumps({
            "action": action, "query": query,
            "works": [w.model_dump() for w in works] if works else None,
            "source_id": source_id, "page": page,
            "year_from": year_from, "year_to": year_to,
        }, ensure_ascii=False, sort_keys=True).encode())
        if payload_size > 64 * 1024:
            return _error("canonical request exceeds 64 KiB"), None
        service = service_getter()
        if action == "search":
            if not query or works is not None or source_id is not None or page is not None:
                return _error("search requires only query and optional year filters"), None
            if year_from is not None and year_to is not None and year_from > year_to:
                return _error("year_from must not exceed year_to"), None
            date_filter = (
                PublishedDateFilter.from_year_range(year_from, year_to)
                if year_from is not None or year_to is not None
                else None
            )
            records, states = await service.search(query, date_filter=date_filter)
            records = [r for r in records if (year_from is None or (r.year is not None and r.year >= year_from)) and (year_to is None or (r.year is not None and r.year <= year_to))]
            return _format_records(records, states), None
        if action == "save":
            if not works or any(value is not None for value in (query, source_id, page, year_from, year_to)):
                return _error("save requires only works (1..10)"), None
            intents = tuple(work.to_domain() for work in works)
            # Queue concurrent calls instead of rejecting a legitimate retry or
            # a second user-authorized save in the same conversation turn.
            async with _save_lock():
                outcome = await service.save(intents)
            artifact = outcome.to_artifact()
            return (
                "Actual citation save result:\n"
                + json.dumps(artifact, ensure_ascii=False, sort_keys=True),
                artifact,
            )
        if action == "sources":
            if any(value is not None for value in (query, works, source_id, year_from, year_to)):
                return _error("sources accepts only page"), None
            sources, total = service.list_sources(page or 1)
            return _format_sources(sources, min(page or 1, total), total), None
        if action == "source":
            if not source_id or any(value is not None for value in (query, works, page, year_from, year_to)):
                return _error("source requires only source_id"), None
            ref = service.activate_source(source_id)
            return (_format_source(ref) if ref else f"unknown source id: {source_id}"), None
        if action == "explain":
            if any(value is not None for value in (query, works, source_id, page, year_from, year_to)):
                return _error("explain accepts no additional fields"), None
            return format_explain(service.output_dir), None
        return _error("unknown action"), None

    _run.__name__ = TOOL_NAME
    return StructuredTool.from_function(
        coroutine=_run, name=TOOL_NAME, description=TOOL_DESCRIPTION,
        args_schema=CitationWorkflowInput, infer_schema=False,
        response_format="content_and_artifact",
    )
