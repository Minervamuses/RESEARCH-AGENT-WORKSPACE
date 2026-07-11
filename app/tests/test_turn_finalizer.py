"""Chat E2E: every turn branch funnels through finalize_and_record."""

import asyncio

import pytest
from langchain_core.messages import ToolMessage

from conftest import FakeHistoryStore, make_astream_graph

from agent.config import AgentConfig
from agent.session import ChatSession
from agent.turn_outcome import TurnOutcome
from agent.turn_safety import find_content_tool_protocol_artifact
from skills.citation.coordinator import CitationCoordinator
from skills.citation.hub import CitationProviderHub
from skills.citation.types import ConfirmReceipt, SourceRef


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
    coordinator = CitationCoordinator(hub, output_dir=tmp_path / "cite")
    coordinator.registry.register(SourceRef(
        source_id=source_id,
        doi="10.1234/known",
        title="Known Paper",
        authors=["Ada Lovelace"],
        year=2021,
        venue="Journal",
        verification_level="identity_verified",
        bundle_path=str(tmp_path / "cite" / source_id),
    ))
    session._citation_coordinator = coordinator
    return coordinator


def _confirm_tool_message(session, source_id="src-known", **overrides):
    ref = session.citation_coordinator.registry.get(source_id)
    receipt = ConfirmReceipt(
        source_id=ref.source_id,
        accepted_doi=ref.doi,
        bundle_path=ref.bundle_path,
        verification_level=ref.verification_level,
        cite_marker=f"[[cite:{ref.source_id}]]",
        warnings=("title conflict",),
    ).to_artifact()
    receipt.update(overrides)
    return ToolMessage(
        content="citation confirmed",
        tool_call_id="confirm-1",
        name="citation_workflow",
        artifact=receipt,
    )


def test_clean_turn_returns_outcome_and_records(make_session):
    session, store = make_session(answer="plain answer")
    outcome = asyncio.run(session.turn_outcome("hello"))
    assert isinstance(outcome, TurnOutcome)
    assert outcome.text == "plain answer"
    assert outcome.validation_errors == []
    assert session.recent_turns[-1].assistant_output == "plain answer"
    assert session.turn_logs[-1]["validation_errors"] == []
    assert session.turn_logs[-1]["recovery"] is None


@pytest.mark.parametrize("draft", ["", "   \n\t"])
def test_blank_turn_uses_deterministic_fallback_and_records_it(make_session, draft):
    session, _ = make_session(answer=draft)

    outcome = asyncio.run(session.turn_outcome("請整理結果"))

    assert "未能產生可顯示" in outcome.text
    assert session.recent_turns[-1].assistant_output == outcome.text
    assert session.turn_logs[-1]["recovery"] == "finalizer:empty_final_answer"


@pytest.mark.parametrize("draft", [
    'citation_workflow(action="list", page=5)',
    'citation_workflow({"action":"list","page":5})',
    '<｜tool▁calls▁begin｜>citation_workflow',
    '{"name":"citation_workflow","args":{"action":"list"}}',
    '{"arguments":{"action":"list"},"name":"citation_workflow"}',
    '{"type":"tool_use","name":"citation_workflow",'
    '"input":{"action":"list"}}',
])
def test_tool_protocol_artifact_never_reaches_history(make_session, draft):
    session, _ = make_session(answer=draft)

    outcome = asyncio.run(session.turn_outcome("繼續"))

    assert "citation_workflow" not in outcome.text
    assert draft not in session.recent_turns[-1].assistant_output
    recovery = session.turn_logs[-1]["recovery"]
    assert recovery.startswith("finalizer:")
    assert "tool" in recovery


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
        "input": {"action": "list"},
    }]

    assert find_content_tool_protocol_artifact(
        content,
        tool_names=["citation_workflow"],
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
    assert "[identity_verified]" in outcome.text
    # The rendered text (bibliography included) is what history records.
    assert session.recent_turns[-1].assistant_output == outcome.text


def test_blocked_draft_never_reaches_history_or_plan_log(make_session, tmp_path):
    draft = "As shown in [1], transformers won (Vaswani et al., 2017)."
    session, store = make_session(answer=draft)
    outcome = asyncio.run(session.turn_outcome("tell me"))

    assert outcome.validation_errors
    assert "封鎖" in outcome.text
    assert draft not in outcome.text
    # The safe message — not the draft — is what history sees.
    recorded = session.recent_turns[-1].assistant_output
    assert draft not in recorded
    assert "raw_numeric_citation" in recorded
    errors = session.turn_logs[-1]["validation_errors"]
    assert any("raw_numeric_citation" in err for err in errors)
    assert any("raw_author_year" in err for err in errors)


def test_confirm_receipt_replaces_clean_model_draft(make_session, tmp_path):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)

    outcome = asyncio.run(session.finalize_and_record(
        user_input="儲存",
        answer="已儲存。",
        new_messages=[_confirm_tool_message(session)],
        tool_calls=[],
        trace_events=[],
    ))

    assert "引用已確認並保存" in outcome.text
    assert "`src-known`" in outcome.text
    assert "`10.1234/known`" in outcome.text
    assert str(tmp_path / "cite" / "src-known") in outcome.text
    assert session.recent_turns[-1].assistant_output == outcome.text


def test_confirm_receipt_survives_raw_doi_gate_block(make_session, tmp_path):
    draft = "已儲存 DOI 10.1234/known。"
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)

    outcome = asyncio.run(session.finalize_and_record(
        user_input="儲存",
        answer=draft,
        new_messages=[_confirm_tool_message(session)],
        tool_calls=[],
        trace_events=[],
    ))

    assert any("raw_doi" in error for error in outcome.validation_errors)
    assert "草稿未通過 citation 檢查，但 confirm 已成功" in outcome.text
    assert "`10.1234/known`" in outcome.text
    assert draft not in outcome.text
    assert "請先在 citation workflow 中完成驗證" not in outcome.text
    assert session.recent_turns[-1].assistant_output == outcome.text


@pytest.mark.parametrize("draft", ["", 'citation_workflow(action="status")'])
def test_confirm_receipt_survives_final_response_recovery(
    make_session, tmp_path, draft
):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)

    outcome = asyncio.run(session.finalize_and_record(
        user_input="確認",
        answer=draft,
        new_messages=[_confirm_tool_message(session)],
        tool_calls=[],
        trace_events=[],
    ))

    assert "引用已確認並保存" in outcome.text
    assert "`src-known`" in outcome.text
    assert session.turn_logs[-1]["recovery"].startswith("finalizer:")


def test_receipt_requires_artifact_and_live_registry_match(make_session, tmp_path):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)

    text_only = ToolMessage(
        content="citation confirmed: source src-known",
        tool_call_id="confirm-text",
        name="citation_workflow",
    )
    forged = _confirm_tool_message(session, bundle_path="/tmp/not-the-live-bundle")
    for message in (text_only, forged):
        outcome = asyncio.run(session.finalize_and_record(
            user_input="儲存",
            answer="bad DOI 10.1234/known",
            new_messages=[message],
            tool_calls=[],
            trace_events=[],
        ))
        assert "confirm 已成功" not in outcome.text
        assert "回應未通過 citation 檢查" in outcome.text


def test_plan_log_persists_receipt_but_not_blocked_draft(make_session, tmp_path):
    session, _ = make_session()
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    asyncio.run(session.enter_plan_mode())
    draft = "bad DOI 10.1234/known"

    outcome = asyncio.run(session.finalize_and_record(
        user_input="儲存",
        answer=draft,
        new_messages=[_confirm_tool_message(session)],
        tool_calls=[],
        trace_events=[],
    ))
    content = session.plan_log_path.read_text(encoding="utf-8")

    assert outcome.text in content
    assert "`src-known`" in content
    assert draft not in content


def test_eviction_persists_receipt_as_plain_assistant_text(make_session, tmp_path):
    session, store = make_session(window=1)
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    receipt = asyncio.run(session.finalize_and_record(
        user_input="儲存",
        answer="saved",
        new_messages=[_confirm_tool_message(session)],
        tool_calls=[],
        trace_events=[],
    ))

    asyncio.run(session.turn("下一步"))

    assert len(store.adds) == 1
    assert store.adds[0]["assistant_output"] == receipt.text
    assert "`src-known`" in store.adds[0]["assistant_output"]
    assert not hasattr(store.adds[0]["turn"], "sources")


def test_blocked_draft_in_plan_mode_writes_safe_message_only(make_session):
    session, _ = make_session(answer="bad citation [1]")
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn("plan question"))
    content = session.plan_log_path.read_text(encoding="utf-8")
    assert "bad citation [1]" not in content
    assert "raw_numeric_citation" in content


def test_user_doi_in_input_is_never_auto_registered(make_session, tmp_path):
    """A DOI/URL in ordinary user input creates no Coordinator and no source."""
    session, _ = make_session(answer="plain answer")
    outcome = asyncio.run(
        session.turn_outcome("請看 https://doi.org/10.1234/user-paper")
    )
    assert outcome.text == "plain answer"
    assert session._citation_coordinator is None  # noqa: SLF001

    # user-cite markers are no longer a citable form at all.
    session.graph = make_astream_graph(
        answer="Your paper [[user-cite:usr-anything]] is interesting."
    )
    blocked = asyncio.run(session.turn_outcome("continue"))
    assert any(
        "citation_inactive_marker" in err for err in blocked.validation_errors
    )


def test_dangling_cite_marker_blocks_in_citation_mode(make_session, tmp_path):
    session, _ = make_session(answer="Bogus [[cite:src-ghost]].")
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.turn_outcome("q"))
    assert any("dangling_cite" in err for err in outcome.validation_errors)


def test_verified_marker_blocks_outside_citation_mode(make_session, tmp_path):
    """Even a resolvable [[cite:...]] is formal citation — skill-only."""
    session, _ = make_session(answer="Known [[cite:src-known]].")
    _seed_verified_source(session, tmp_path)  # registry exists, skill inactive
    outcome = asyncio.run(session.turn_outcome("q"))
    assert any(
        "citation_inactive_marker" in err for err in outcome.validation_errors
    )


def test_plain_web_link_passes_and_renderer_skipped_outside_citation_mode(
    make_session, tmp_path
):
    session, _ = make_session(
        answer="See [docs](https://example.org/guide) and https://example.org/x"
    )
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.turn_outcome("q"))
    assert outcome.validation_errors == []
    # Renderer untouched: no numbering, no bibliography appended.
    assert outcome.text == (
        "See [docs](https://example.org/guide) and https://example.org/x"
    )
    assert "Sources:" not in outcome.text


def test_deactivating_citation_removes_hint_and_rendering(make_session, tmp_path):
    session, _ = make_session(answer="plain")
    session.activate_skill("citation")
    _seed_verified_source(session, tmp_path)
    assert session._build_sources_hint() is not None
    session.deactivate_skill()
    assert session._build_sources_hint() is None
    assert session._citation_coordinator is None


def test_sources_hint_appears_in_prompt_after_registration(make_session, tmp_path):
    session, _ = make_session()
    assert session._build_sources_hint() is None
    session.activate_skill("citation")
    assert session._build_sources_hint() is None  # active but empty registry
    _seed_verified_source(session, tmp_path)
    hint = session._build_sources_hint()
    assert hint is not None
    assert "[[cite:src-known]]" in hint.content
    history = session._prompt_history()
    assert any("[[cite:src-known]]" in str(m.content) for m in history)


def test_extended_mode_early_error_goes_through_finalizer(make_session, monkeypatch):
    session, _ = make_session()
    session.thinking_mode = "extended"
    # No thinking models configured -> early error branch.
    outcome = asyncio.run(session.turn_outcome("question"))
    assert isinstance(outcome, TurnOutcome)
    assert session.turn_logs[-1]["validation_errors"] == []
    assert session.recent_turns[-1].assistant_output == outcome.text
