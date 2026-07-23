"""Citation tool contracts: visible identifiers, trusted model intent, and saves."""

import asyncio
import json
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage
from pydantic import ValidationError

from skills.citation.providers.base import ProviderRecord
from skills.citation.tool import CitationWorkflowInput, TOOL_NAME, create_citation_workflow_tool
from skills.citation.types import SaveBatchOutcome, SaveItemOutcome


class FakeService:
    output_dir = Path("/tmp/cite")

    def __init__(self):
        self.save_calls = 0
        self.saved_intents = []
        self.search_calls = []

    async def search(self, query, *, date_filter=None):
        self.search_calls.append((query, date_filter))
        return [ProviderRecord(
            "x",
            "x:1",
            0,
            title="A Work",
            authors=["Ada Author"],
            year=2020,
            venue="Venue",
            work_type="article",
            version_kind="published",
            doi="10.1234/visible",
            identifiers={"doi": "10.1234/visible", "arxiv": "2001.00001"},
            url="https://doi.org/10.1234/visible",
        )], ["x:ok"]

    async def save(self, intents):
        self.save_calls += 1
        self.saved_intents.append(intents)
        return SaveBatchOutcome("batch", tuple(
            SaveItemOutcome(i, intent.requested_label, "not_found", "no_provider_records")
            for i, intent in enumerate(intents)
        ))

    def list_sources(self, page):
        return [], 1

    def activate_source(self, source_id):
        return None


def args(label="work", **work):
    return {
        "action": "save",
        "works": [{"requested_label": label, "title": "A Work", **work}],
    }


def test_tool_name_and_five_action_schema():
    tool = create_citation_workflow_tool(service_getter=FakeService)
    assert tool.name == TOOL_NAME
    assert set(tool.args_schema.model_fields) == {
        "action", "query", "works", "source_id", "page", "year_from", "year_to",
    }
    assert set(CitationWorkflowInput.model_fields["action"].annotation.__args__) == {
        "search", "save", "sources", "source", "explain",
    }


def test_json_schema_exposes_direct_model_selected_version_and_identifiers():
    definitions = CitationWorkflowInput.model_json_schema()["$defs"]
    work_fields = definitions["WorkIntentInput"]["properties"]
    identifier_fields = definitions["IdentifierInput"]["properties"]

    assert work_fields["version_kind"]["anyOf"][0]["enum"] == [
        "published", "preprint", "repository", "repost", "earliest",
    ]
    assert work_fields["work_kind"]["anyOf"][0]["const"] == "original_research"
    assert set(identifier_fields) == {"kind", "value"}
    assert "constraints" not in work_fields
    assert "version" not in work_fields


def test_unknown_candidate_provenance_and_constraint_fields_are_rejected():
    invalid_works = [
        {"requested_label": "x", "candidate_id": "c1"},
        {"requested_label": "x", "constraints": []},
        {
            "requested_label": "x",
            "identifiers": [{
                "kind": "doi",
                "value": "10.1234/work",
                "provenance": "explicit_current_user",
            }],
        },
    ]
    for work in invalid_works:
        with pytest.raises(ValidationError):
            CitationWorkflowInput.model_validate({"action": "save", "works": [work]})
    with pytest.raises(ValidationError):
        CitationWorkflowInput.model_validate({
            "action": "save", "identifier": "c1", "works": [{"requested_label": "x"}],
        })


@pytest.mark.parametrize(
    "version_kind",
    ["published", "preprint", "repository", "repost", "earliest"],
)
def test_model_selected_version_maps_directly_to_work_intent(version_kind):
    payload = CitationWorkflowInput.model_validate(args(version_kind=version_kind))

    intent = payload.works[0].to_domain()
    assert intent.version_kind == version_kind
    assert not hasattr(intent, "constraints")


def test_model_selected_work_kind_and_identifier_map_directly():
    payload = CitationWorkflowInput.model_validate(args(
        work_kind="original_research",
        identifiers=[{"kind": "doi", "value": "https://doi.org/10.1234/WORK"}],
    ))

    intent = payload.works[0].to_domain()
    assert intent.work_kind == "original_research"
    assert [(item.kind, item.value) for item in intent.identifiers] == [
        ("doi", "10.1234/work"),
    ]


def test_search_returns_complete_metadata_and_stable_identifiers():
    tool = create_citation_workflow_tool(service_getter=FakeService)
    result = asyncio.run(tool.ainvoke({"action": "search", "query": "work"}))

    assert all(value in result for value in (
        "A Work",
        "Ada Author",
        "2020",
        "Venue",
        "published",
        "DOI: 10.1234/visible",
        "arXiv: 2001.00001",
        "URL: https://doi.org/10.1234/visible",
    ))
    assert "c1" not in result and "m1" not in result


def test_search_passes_year_range_to_provider_before_local_filter():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)

    result = asyncio.run(tool.ainvoke({
        "action": "search", "query": "work", "year_from": 2019, "year_to": 2021,
    }))

    assert "A Work" in result
    query, date_filter = service.search_calls[0]
    assert query == "work"
    assert (date_filter.year_from, date_filter.year_to) == (2019, 2021)
    assert (date_filter.date_from, date_filter.date_to) == (
        "2019-01-01", "2021-12-31",
    )


def test_save_needs_no_current_turn_context_and_returns_actual_outcome_content():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)

    content = asyncio.run(tool.ainvoke(args("paper", version_kind="published")))

    assert service.save_calls == 1
    assert service.saved_intents[0][0].version_kind == "published"
    prefix = "Actual citation save result:\n"
    assert content.startswith(prefix)
    outcome = SaveBatchOutcome.from_artifact(json.loads(content.removeprefix(prefix)))
    assert outcome.items[0].requested_label == "paper"
    assert outcome.items[0].status == "not_found"
    assert outcome.items[0].reason_code == "no_provider_records"


def test_real_tool_call_returns_content_json_identical_to_message_artifact():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)
    call = {
        "type": "tool_call",
        "name": TOOL_NAME,
        "id": "save-call",
        "args": args("paper", version_kind="published"),
    }

    message = asyncio.run(tool.ainvoke(call))

    assert isinstance(message, ToolMessage)
    prefix = "Actual citation save result:\n"
    assert str(message.content).startswith(prefix)
    content_artifact = json.loads(str(message.content).removeprefix(prefix))
    assert content_artifact == message.artifact
    assert SaveBatchOutcome.from_artifact(content_artifact).items[0].status == "not_found"


def test_multiple_save_calls_in_one_turn_are_allowed():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)

    first = asyncio.run(tool.ainvoke(args("first")))
    second = asyncio.run(tool.ainvoke(args("second")))

    assert first.startswith("Actual citation save result:")
    assert second.startswith("Actual citation save result:")
    assert service.save_calls == 2
    assert [batch[0].requested_label for batch in service.saved_intents] == [
        "first", "second",
    ]
    assert "mutation_already_attempted" not in first + second


def test_concurrent_save_calls_are_serialized_instead_of_rejected():
    class SerialService(FakeService):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.max_active = 0

        async def save(self, intents):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            try:
                return await super().save(intents)
            finally:
                self.active -= 1

    async def run_calls(tool):
        return await asyncio.gather(
            tool.ainvoke(args("first")),
            tool.ainvoke(args("second")),
        )

    service = SerialService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)
    first_loop_results = asyncio.run(run_calls(tool))
    second_loop_results = asyncio.run(run_calls(tool))

    assert service.save_calls == 4
    assert service.max_active == 1
    results = first_loop_results + second_loop_results
    assert all(result.startswith("Actual citation save result:") for result in results)
    assert not any("workflow_busy" in result for result in results)


def test_invalid_action_parameter_combination_has_no_save_side_effect():
    service = FakeService()
    tool = create_citation_workflow_tool(service_getter=lambda: service)

    invalid = asyncio.run(tool.ainvoke({
        "action": "save", "query": "x", "works": [{"requested_label": "x"}],
    }))

    assert "validation error" in invalid
    assert service.save_calls == 0
    asyncio.run(tool.ainvoke(args()))
    assert service.save_calls == 1
