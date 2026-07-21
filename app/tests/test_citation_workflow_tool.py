"""Stateless citation tool schema, metadata search, and one-shot mutation."""

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from skills.citation.providers.base import ProviderRecord
from skills.citation.service import CitationTurnContext, MutationGuard
from skills.citation.tool import CitationWorkflowInput, TOOL_NAME, create_citation_workflow_tool
from skills.citation.types import SaveBatchOutcome, SaveItemOutcome


class FakeService:
    output_dir = Path("/tmp/cite")

    def __init__(self):
        self.save_calls = 0
        self.search_calls = []

    async def search(self, query, *, date_filter=None):
        self.search_calls.append((query, date_filter))
        return [ProviderRecord("x", "x:1", 0, title="A Work", authors=["Ada Author"], year=2020, venue="Venue", work_type="article", doi="10.1234/hidden")], ["x:ok"]

    async def save(self, intents):
        self.save_calls += 1
        return SaveBatchOutcome("batch", "attempted", "none", tuple(
            SaveItemOutcome(i, intent.requested_label, "not_found", "no_provider_records")
            for i, intent in enumerate(intents)
        ))

    def list_sources(self, page):
        return [], 1

    def activate_source(self, source_id):
        return None


def args(label="work"):
    return {
        "action": "save",
        "works": [{"requested_label": label, "title": "A Work"}],
    }


def test_tool_name_and_five_action_schema():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)
    assert tool.name == TOOL_NAME
    assert set(tool.args_schema.model_fields) == {"action", "query", "works", "source_id", "page", "year_from", "year_to"}
    assert set(CitationWorkflowInput.model_fields["action"].annotation.__args__) == {"search", "save", "sources", "source", "explain"}


def test_nested_unknown_and_legacy_candidate_fields_are_strictly_rejected():
    with pytest.raises(ValidationError):
        CitationWorkflowInput.model_validate({"action": "save", "works": [{"requested_label": "x", "candidate_id": "c1"}]})
    with pytest.raises(ValidationError):
        CitationWorkflowInput.model_validate({"action": "save", "identifier": "c1", "works": [{"requested_label": "x"}]})


def test_search_returns_complete_metadata_without_candidate_or_match_ids():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)
    text = asyncio.run(tool.ainvoke({"action": "search", "query": "work"}))
    assert "A Work" in text and "Ada Author" in text and "2020" in text and "Venue" in text
    assert "c1" not in text and "m1" not in text and "10.1234" not in text


def test_search_passes_year_range_to_provider_before_local_defense_filter():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)

    text = asyncio.run(tool.ainvoke({
        "action": "search",
        "query": "work",
        "year_from": 2019,
        "year_to": 2021,
    }))

    assert "A Work" in text
    query, date_filter = service.search_calls[0]
    assert query == "work"
    assert date_filter.year_from == 2019
    assert date_filter.year_to == 2021
    assert date_filter.date_from == "2019-01-01"
    assert date_filter.date_to == "2021-12-31"


def test_save_without_active_turn_context_fails_before_service():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)
    assert asyncio.run(tool.ainvoke(args())) == "turn_context_missing"
    assert service.save_calls == 0


def test_first_shape_valid_save_consumes_turn_even_when_not_found():
    service = FakeService()
    context = CitationTurnContext("turn", (), MutationGuard())
    tool = create_citation_workflow_tool(service_getter=lambda: service, context_getter=lambda: context)
    first = asyncio.run(tool.ainvoke(args("first")))
    second = asyncio.run(tool.ainvoke(args("second")))
    assert "attempted" in first
    assert "mutation_already_attempted" in second
    assert service.save_calls == 1


def test_invalid_action_parameter_combination_has_no_mutation_side_effect():
    service = FakeService()
    context = CitationTurnContext("turn", (), MutationGuard())
    tool = create_citation_workflow_tool(service_getter=lambda: service, context_getter=lambda: context)
    invalid = asyncio.run(tool.ainvoke({"action": "save", "query": "x", "works": [{"requested_label": "x"}]}))
    assert "validation error" in invalid
    assert not context.guard.claimed and service.save_calls == 0
    asyncio.run(tool.ainvoke(args()))
    assert service.save_calls == 1
