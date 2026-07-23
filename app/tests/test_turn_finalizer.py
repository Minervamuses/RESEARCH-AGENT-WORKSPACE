"""Chat E2E contracts for response safety, marker rendering, and save telemetry."""

import asyncio
import json
import logging

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from conftest import FakeHistoryStore, make_astream_graph

from agent.config import AgentConfig
from agent.session import ChatSession
from agent.turn_outcome import TurnOutcome
from agent.turn_safety import find_content_tool_protocol_artifact
from skills.citation.hub import CitationProviderHub
from skills.citation.service import CitationService
from skills.citation.types import (
    CanonicalIdentity,
    SaveBatchOutcome,
    SaveItemOutcome,
    SaveReceipt,
    SourceRef,
)


@pytest.fixture
def make_session(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: make_astream_graph(),
    )

    def _make(answer="ok", window: int = 5):
        cfg = AgentConfig(persist_dir=str(tmp_path / "persist"))
        cfg.agent_recent_turns_window = window
        store = FakeHistoryStore()
        session = ChatSession(cfg, history_store=store)
        session.graph = make_astream_graph(answer=answer)
        return session, store

    return _make


async def _noop_fetcher(url, headers):
    raise AssertionError(f"network not expected: {url}")


def _seed_verified_source(session, tmp_path, source_id="src-known"):
    hub = CitationProviderHub(env={}, fetcher=_noop_fetcher)
    service = CitationService(hub, output_dir=tmp_path / "cite")
    ref = SourceRef(
        source_id=source_id,
        doi="10.1234/known",
        title="Known Paper",
        authors=["Ada Lovelace"],
        year=2021,
        venue="Journal",
        work_type="journal-article",
        verification_level="doi_identity_verified",
        schema_version=2,
        canonical_identity=CanonicalIdentity("doi", "10.1234/known"),
    )
    receipt = SaveReceipt(
        source_id=ref.source_id,
        canonical_identity=ref.canonical_identity,
        doi=ref.doi,
        title=ref.title,
        year=ref.year,
        work_type=ref.work_type,
        bundle_path=str(tmp_path / "cite" / source_id),
        verification_level=ref.verification_level,
        cite_marker=f"[[cite:{ref.source_id}]]",
        version_kind="published",
    )
    service.registry.register(ref, receipt=receipt)
    session._citation_service = service
    return service


def _save_tool_message(
    session,
    source_id="src-known",
    *,
    status="success",
    call_id="save-1",
):
    receipt = session.citation_service.registry.trusted_receipt(source_id)
    assert receipt is not None
    artifact = SaveBatchOutcome(
        f"batch-{call_id}",
        (
            SaveItemOutcome(1, "missing", "not_found", "no_provider_records"),
            SaveItemOutcome(0, "wanted", "saved", "saved_new", receipt),
        ),
    ).to_artifact()
    return ToolMessage(
        content="Actual citation save result:\n" + json.dumps(artifact),
        tool_call_id=call_id,
        name="citation_workflow",
        status=status,
        artifact=artifact,
    )


def _save_failure_tool_message(*failures, content="save failed", call_id="save-failed"):
    artifact = SaveBatchOutcome(
        f"batch-{call_id}",
        tuple(
            SaveItemOutcome(
                request_index=request_index,
                requested_label=requested_label,
                status=status,
                reason_code=reason_code,
            )
            for request_index, requested_label, status, reason_code in failures
        ),
    ).to_artifact()
    return ToolMessage(
        content=content,
        tool_call_id=call_id,
        name="citation_workflow",
        artifact=artifact,
    )


def _assert_save_metrics(
    session, *, batches=0, saved=0, reused=0, failed=0,
):
    metrics = session.turn_logs[-1]
    assert {
        "citation_save_batch_count": metrics["citation_save_batch_count"],
        "new_saved_count": metrics["new_saved_count"],
        "reused_count": metrics["reused_count"],
        "failed_count": metrics["failed_count"],
    } == {
        "citation_save_batch_count": batches,
        "new_saved_count": saved,
        "reused_count": reused,
        "failed_count": failed,
    }


def test_clean_turn_returns_outcome_and_records(make_session):
    session, _ = make_session(answer="plain answer")
    outcome = asyncio.run(session.turn_outcome("hello"))
    assert isinstance(outcome, TurnOutcome)
    assert outcome.text == "plain answer"
    assert outcome.validation_errors == []
    assert session.recent_turns[-1].assistant_output == "plain answer"
    assert session.turn_logs[-1]["validation_errors"] == []
    assert session.turn_logs[-1]["recovery"] is None
    _assert_save_metrics(session)


@pytest.mark.parametrize("draft", ["", "   \n\t"])
def test_blank_turn_uses_deterministic_fallback_and_records_it(make_session, draft):
    session, _ = make_session(answer=draft)
    outcome = asyncio.run(session.turn_outcome("請整理結果"))
    assert "未能產生可顯示" in outcome.text
    assert session.recent_turns[-1].assistant_output == outcome.text
    assert session.turn_logs[-1]["recovery"] == "finalizer:empty_final_answer"


@pytest.mark.parametrize("draft", [
    'citation_workflow(action="sources", page=5)',
    'citation_workflow({"action":"sources","page":5})',
    '<｜tool▁calls▁begin｜>citation_workflow',
    '{"name":"citation_workflow","args":{"action":"sources"}}',
    '{"type":"tool_use","name":"citation_workflow","input":{"action":"sources"}}',
])
def test_tool_protocol_artifact_never_reaches_history(make_session, draft):
    session, _ = make_session(answer=draft)
    outcome = asyncio.run(session.turn_outcome("繼續"))
    assert "citation_workflow" not in outcome.text
    assert draft not in session.recent_turns[-1].assistant_output
    assert session.turn_logs[-1]["recovery"].startswith("finalizer:")


@pytest.mark.parametrize("draft", [
    "The citation_workflow tool is available for verified citations.",
    "Tool calls begin after the model chooses a function.",
    "The tool call begins only after approval.",
])
def test_plain_tool_prose_is_not_a_protocol_artifact(make_session, draft):
    session, _ = make_session(answer=draft)
    outcome = asyncio.run(session.turn_outcome("explain"))
    assert outcome.text == draft
    assert session.turn_logs[-1]["recovery"] is None


def test_structured_tool_content_is_detected_before_flattening():
    content = [{
        "type": "tool_use",
        "name": "citation_workflow",
        "input": {"action": "sources"},
    }]
    assert find_content_tool_protocol_artifact(
        content, tool_names=["citation_workflow"],
    ) == "structured_tool_content"


def test_turn_and_trace_wrappers_return_finalized_text(make_session):
    session, _ = make_session(answer="wrapped")
    assert asyncio.run(session.turn("q")) == "wrapped"
    text, calls = asyncio.run(session.turn_with_trace("q"))
    assert text == "wrapped"
    assert calls == []


def test_cited_answer_is_rendered_with_bibliography(make_session, tmp_path):
    session, _ = make_session(
        answer="Transformers work [[cite:src-known]]. Really [[cite:src-known]]."
    )
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.turn_outcome("tell me"))
    assert "Transformers work [1]. Really [1]." in outcome.text
    assert "Sources:" in outcome.text
    assert "[doi_identity_verified]" in outcome.text
    assert session.recent_turns[-1].assistant_output == outcome.text


@pytest.mark.parametrize("active", [False, True])
def test_raw_citation_styles_are_not_blocked_or_rewritten(
    make_session, tmp_path, active,
):
    draft = (
        "As shown in [1] and (Vaswani et al., 2017), see "
        "https://doi.org/10.48550/arXiv.1706.03762.\n\n"
        "## References\n- Vaswani et al. (2017)."
    )
    session, _ = make_session(answer=draft)
    if active:
        session.activate_skill("citation")
        _seed_verified_source(session, tmp_path)

    outcome = asyncio.run(session.turn_outcome("tell me"))

    assert outcome.text == draft
    assert outcome.validation_errors == []
    assert session.recent_turns[-1].assistant_output == draft


def test_save_artifact_does_not_override_model_prose_and_records_metrics(
    make_session, tmp_path, caplog,
):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)

    with caplog.at_level(logging.INFO, logger="agent.observability"):
        outcome = asyncio.run(session.finalize_and_record(
            user_input="save",
            answer="Model-selected response.",
            new_messages=[_save_tool_message(session)],
            tool_calls=[],
            trace_events=[],
        ))

    assert outcome.text == "Model-selected response."
    assert session.recent_turns[-1].assistant_output == "Model-selected response."
    _assert_save_metrics(session, batches=1, saved=1, failed=1)
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == "agent.observability"
    ]
    assert lines == [
        "citation_save_finalized citation_save_batch_count=1 "
        "new_saved_count=1 reused_count=0 failed_count=1"
    ]
    assert "10.1234/known" not in lines[0]
    assert "Known Paper" not in lines[0]


def test_multiple_save_artifacts_aggregate_without_invariant_failure(
    make_session, tmp_path,
):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    second = _save_tool_message(session, call_id="save-2")
    second.artifact["items"][1]["status"] = "reused"
    second.artifact["items"][1]["reason_code"] = "reused_existing"

    outcome = asyncio.run(session.finalize_and_record(
        user_input="save both",
        answer="Two save calls completed.",
        new_messages=[_save_tool_message(session), second],
        tool_calls=[],
        trace_events=[],
    ))

    assert outcome.text == "Two save calls completed."
    _assert_save_metrics(
        session, batches=2, saved=1, reused=1, failed=2,
    )


@pytest.mark.parametrize(("field", "forged_value"), [
    ("bundle_path", "/forged"),
    ("title", "Forged title"),
    ("year", 1900),
    ("work_type", "forged-type"),
])
def test_registry_mismatch_affects_telemetry_but_not_model_prose(
    make_session, tmp_path, field, forged_value,
):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    message = _save_tool_message(session)
    message.artifact["items"][1]["receipt"][field] = forged_value

    outcome = asyncio.run(session.finalize_and_record(
        user_input="save",
        answer="The model owns this prose.",
        new_messages=[message],
        tool_calls=[],
        trace_events=[],
    ))

    assert outcome.text == "The model owns this prose."
    _assert_save_metrics(session, batches=1, failed=2)


def test_forged_receipt_identifier_never_reaches_logs(
    make_session, tmp_path, caplog,
):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    message = _save_tool_message(session)
    secret = "10.9999/private-provider-text"
    receipt = message.artifact["items"][1]["receipt"]
    receipt["source_id"] = secret
    receipt["cite_marker"] = f"[[cite:{secret}]]"

    with caplog.at_level(logging.WARNING):
        outcome = asyncio.run(session.finalize_and_record(
            user_input="save",
            answer="No receipt details here.",
            new_messages=[message],
            tool_calls=[],
            trace_events=[],
        ))

    assert outcome.text == "No receipt details here."
    assert secret not in "\n".join(record.getMessage() for record in caplog.records)


def test_error_tool_message_does_not_count_artifact(make_session, tmp_path):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.finalize_and_record(
        user_input="save",
        answer="工具呼叫失敗。",
        new_messages=[_save_tool_message(session, status="error")],
        tool_calls=[],
        trace_events=[],
    ))
    assert outcome.text == "工具呼叫失敗。"
    _assert_save_metrics(session)


def test_answered_save_without_artifact_logs_none_status(make_session, caplog):
    session, _ = make_session()
    session.activate_skill("citation")
    save_call = AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "save", "works": []},
        "id": "save-without-artifact",
    }])
    result = ToolMessage(
        content="validation error",
        tool_call_id="save-without-artifact",
        name="citation_workflow",
        status="success",
    )

    with caplog.at_level(logging.WARNING, logger="agent.observability"):
        outcome = asyncio.run(session.finalize_and_record(
            user_input="save",
            answer="保存未完成。",
            new_messages=[save_call, result],
            tool_calls=[],
            trace_events=[],
        ))

    assert outcome.text == "保存未完成。"
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.name == "agent.observability"
    ]
    assert lines == [
        "citation_save_finalized citation_save_batch_count=0 "
        "new_saved_count=0 reused_count=0 failed_count=0"
    ]


def test_reused_save_is_counted_separately_without_rewriting(make_session, tmp_path):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    message = _save_tool_message(session)
    saved_item = message.artifact["items"][1]
    saved_item["status"] = "reused"
    saved_item["reason_code"] = "reused_existing"

    outcome = asyncio.run(session.finalize_and_record(
        user_input="save",
        answer="Reused the existing bundle.",
        new_messages=[message],
        tool_calls=[],
        trace_events=[],
    ))

    assert outcome.text == "Reused the existing bundle."
    _assert_save_metrics(session, batches=1, reused=1, failed=1)


def test_all_save_failures_do_not_deterministically_replace_model_draft(
    make_session, tmp_path,
):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.finalize_and_record(
        user_input="全部存下來",
        answer="This is the model's final wording.",
        new_messages=[_save_failure_tool_message(
            (0, "VAE", "verification_failed", "bibtex_lookup_failed"),
            (1, "missing", "not_found", "no_provider_records"),
        )],
        tool_calls=[],
        trace_events=[],
    ))

    assert outcome.text == "This is the model's final wording."
    _assert_save_metrics(session, batches=1, failed=2)


@pytest.mark.parametrize("draft", ["", 'citation_workflow(action="sources")'])
def test_generic_final_response_recovery_is_not_replaced_by_save_receipt(
    make_session, tmp_path, draft,
):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.finalize_and_record(
        user_input="確認",
        answer=draft,
        new_messages=[_save_tool_message(session)],
        tool_calls=[],
        trace_events=[],
    ))
    assert "工具結果已取得" in outcome.text
    assert "src-known" not in outcome.text
    assert session.turn_logs[-1]["recovery"].startswith("finalizer:")


def test_plan_log_records_model_answer_without_injecting_receipt(make_session, tmp_path):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    asyncio.run(session.enter_plan_mode())
    draft = "Saved according to the tool."

    outcome = asyncio.run(session.finalize_and_record(
        user_input="儲存",
        answer=draft,
        new_messages=[_save_tool_message(session)],
        tool_calls=[],
        trace_events=[],
    ))
    content = session.plan_log_path.read_text(encoding="utf-8")

    assert outcome.text == draft
    assert draft in content
    assert "src-known" not in content


def test_eviction_persists_model_answer_as_plain_assistant_text(make_session, tmp_path):
    session, store = make_session(window=1)
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.finalize_and_record(
        user_input="儲存",
        answer="Saved according to the tool.",
        new_messages=[_save_tool_message(session)],
        tool_calls=[],
        trace_events=[],
    ))
    asyncio.run(session.turn("下一步"))

    assert len(store.adds) == 1
    assert store.adds[0]["assistant_output"] == outcome.text
    assert store.adds[0]["assistant_output"] == "Saved according to the tool."
    assert not hasattr(store.adds[0]["turn"], "sources")


def test_user_doi_in_input_is_never_auto_registered(make_session):
    session, _ = make_session(answer="plain answer")
    outcome = asyncio.run(
        session.turn_outcome("請看 https://doi.org/10.1234/user-paper")
    )
    assert outcome.text == "plain answer"
    assert session._citation_service is None  # noqa: SLF001

    session.graph = make_astream_graph(
        answer="Your paper [[user-cite:usr-anything]] is interesting."
    )
    blocked = asyncio.run(session.turn_outcome("continue"))
    assert any(
        "citation_inactive_marker" in error for error in blocked.validation_errors
    )


def test_dangling_cite_marker_blocks_in_citation_mode(make_session, tmp_path):
    session, _ = make_session(answer="Bogus [[cite:src-ghost]].")
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.turn_outcome("q"))
    assert any("dangling_cite" in error for error in outcome.validation_errors)


def test_verified_marker_blocks_outside_citation_mode(make_session, tmp_path):
    session, _ = make_session(answer="Known [[cite:src-known]].")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.turn_outcome("q"))
    assert any(
        "citation_inactive_marker" in error for error in outcome.validation_errors
    )


def test_plain_web_link_passes_and_renderer_skips_outside_citation_mode(
    make_session, tmp_path,
):
    draft = "See [docs](https://example.org/guide) and https://example.org/x"
    session, _ = make_session(answer=draft)
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.turn_outcome("q"))
    assert outcome.validation_errors == []
    assert outcome.text == draft
    assert "Sources:" not in outcome.text


def test_deactivating_citation_removes_hint_and_rendering(make_session, tmp_path):
    session, _ = make_session(answer="plain")
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    assert session._build_sources_hint() is not None
    session.deactivate_skill()
    assert session._build_sources_hint() is None
    assert session._citation_service is None


def test_sources_hint_appears_in_prompt_after_registration(make_session, tmp_path):
    session, _ = make_session()
    assert session._build_sources_hint() is None
    session.activate_skill("citation")
    assert session._build_sources_hint() is None
    _seed_verified_source(session, tmp_path)
    hint = session._build_sources_hint()
    assert hint is not None
    assert "[[cite:src-known]]" in hint.content
    assert "never write raw" not in hint.content
    history = session._prompt_history()
    assert any("[[cite:src-known]]" in str(message.content) for message in history)


def test_extended_mode_early_error_goes_through_finalizer(make_session):
    session, _ = make_session()
    session.thinking_mode = "extended"
    outcome = asyncio.run(session.turn_outcome("question"))
    assert isinstance(outcome, TurnOutcome)
    assert session.turn_logs[-1]["validation_errors"] == []
    assert session.recent_turns[-1].assistant_output == outcome.text
