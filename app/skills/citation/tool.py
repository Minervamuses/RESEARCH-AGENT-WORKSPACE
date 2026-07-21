"""Model-facing citation workflow with stateless search and one-shot saving."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Callable, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from skills.citation.resolution import (
    HostIntentBinder,
    WorkConstraint,
    WorkIdentifier,
    WorkIntent,
)
from skills.citation.service import CitationTurnContext
from skills.citation.types import PublishedDateFilter, SaveBatchOutcome, SourceRef

TOOL_NAME = "citation_workflow"
TOOL_DESCRIPTION = (
    "Academic citation workflow. search(query, optional year range) is "
    "stateless exploratory discovery. save(works=[self-contained WorkIntent...]) "
    "resolves each work through provider-specific bibliographic queries and "
    "authoritative DOI verification. Pass title, authors, year, venue, type, "
    "identifiers, and version as separate fields; never pass provider syntax "
    "or a result position. Each user turn permits at most one valid save batch."
)

CitationAction = Literal["search", "save", "sources", "source", "explain"]


class IdentifierInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["doi", "arxiv"]
    value: str = Field(
        min_length=1,
        max_length=2048,
        description="An explicit identifier from the user or visible metadata.",
    )
    provenance: Literal["explicit_current_user", "visible_context"]


class ConstraintInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    field: Literal["year", "venue", "work_kind", "version_kind"]
    value: str = Field(min_length=1, max_length=256)
    provenance: Literal["explicit_current_user", "visible_context"]
    requested_strength: Literal["hard", "preference"]


class WorkIntentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    requested_label: str = Field(min_length=1, max_length=160)
    title: str = Field(
        default="", max_length=512, description="The work title only."
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
        default="", max_length=256, description="A human-readable work type."
    )
    identifiers: list[IdentifierInput] = Field(default_factory=list, max_length=8)
    constraints: list[ConstraintInput] = Field(default_factory=list, max_length=8)

    def to_domain(self) -> WorkIntent:
        return WorkIntent(
            self.requested_label,
            title=self.title,
            authors=tuple(self.authors),
            year=self.year,
            venue=self.venue,
            work_type=self.work_type,
            identifiers=tuple(WorkIdentifier(i.kind, i.value, i.provenance) for i in self.identifiers),
            # Tool claims are untrusted hints until HostIntentBinder upgrades them.
            constraints=tuple(WorkConstraint(
                c.field, c.value, c.provenance, c.requested_strength,
                "visible_context", "preference", False,
            ) for c in self.constraints),
        )


class CitationWorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: CitationAction
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="A natural-language topic/title query, never provider syntax.",
    )
    works: list[WorkIntentInput] | None = Field(default=None, min_length=1, max_length=10)
    source_id: str | None = Field(default=None, min_length=1, max_length=128)
    page: int | None = Field(default=None, ge=1)
    year_from: int | None = Field(default=None, ge=1000, le=2999)
    year_to: int | None = Field(default=None, ge=1000, le=2999)


def _error(message: str) -> str:
    return f"validation error: {message}"


def _redact_dois(text: str) -> str:
    return re.sub(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", "[DOI withheld]", text, flags=re.I)


def _format_records(records, states) -> str:
    if not records:
        return "No bibliographic records found. " + "; ".join(states)
    lines = [f"Found {len(records)} bibliographic record(s):"]
    for record in records:
        authors = ", ".join(record.authors) or "authors unknown"
        metadata = " | ".join(str(value) for value in (
            record.title or "untitled", authors, record.year or "year unknown",
            record.venue or "venue unknown", record.work_type or "type unknown",
            record.version_kind or "version unknown",
        ))
        lines.append(f"- {metadata}")
    lines.append("Provider states: " + "; ".join(states))
    lines.append("No result number is a save identifier; build a complete WorkIntent from the metadata.")
    lines.append("Provider order and scores are discovery evidence only; they do not choose a canonical version.")
    return _redact_dois("\n".join(lines))


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
        "search is stateless and returns full metadata without cX/mX IDs. "
        "save accepts 1–10 self-contained WorkIntent objects, resolves each "
        "through provider-specific Crossref, DataCite, and optional OpenAlex "
        "queries, retains multiple candidate manifestations, verifies a "
        "shortlisted DOI before persistence, applies blocking work/version "
        "checks, and permits one attempted mutation batch per user turn. "
        "Provider ranking alone never authorizes a save. Generic "
        "'this paper' with an unknown version and unqualified 'original' require "
        "clarification. Bundles are written atomically under " + str(output_dir)
    )


def create_citation_workflow_tool(
    *,
    service_getter: Callable | None = None,
    coordinator_getter: Callable | None = None,
    context_getter: Callable[[], CitationTurnContext | None] | None = None,
) -> StructuredTool:
    getter = service_getter or coordinator_getter
    if getter is None:
        raise ValueError("service_getter is required")
    context_getter = context_getter or (lambda: None)
    busy_lock = asyncio.Lock()

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
        service = getter()
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
            context = context_getter()
            if context is None:
                return "turn_context_missing", None
            intents = tuple(work.to_domain() for work in works)
            binding = HostIntentBinder().bind(intents, context.claims)
            if busy_lock.locked():
                rejected = SaveBatchOutcome(context.token, "rejected", "workflow_busy")
                return "save rejected: workflow_busy", rejected.to_artifact()
            async with busy_lock:
                if not await context.guard.claim():
                    rejected = SaveBatchOutcome(context.token, "rejected", "mutation_already_attempted")
                    return "save rejected: mutation_already_attempted", rejected.to_artifact()
                outcome = await service.save(binding.intents)
                return "save batch attempted; trusted artifact contains per-item results", outcome.to_artifact()
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
