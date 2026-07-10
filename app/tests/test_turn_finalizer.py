"""Chat E2E: every turn branch funnels through finalize_and_record."""

import asyncio

import pytest

from conftest import FakeHistoryStore, make_astream_graph

from agent.config import AgentConfig
from agent.session import ChatSession
from agent.turn_outcome import TurnOutcome
from skills.citation.coordinator import CitationCoordinator
from skills.citation.hub import CitationProviderHub
from skills.citation.types import SourceRef


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
    ))
    session._citation_coordinator = coordinator
    return coordinator


def test_clean_turn_returns_outcome_and_records(make_session):
    session, store = make_session(answer="plain answer")
    outcome = asyncio.run(session.turn_outcome("hello"))
    assert isinstance(outcome, TurnOutcome)
    assert outcome.text == "plain answer"
    assert outcome.sources == []
    assert outcome.validation_errors == []
    assert session.recent_turns[-1].assistant_output == "plain answer"
    assert session.turn_logs[-1]["validation_errors"] == []


def test_turn_and_trace_wrappers_return_finalized_text(make_session):
    session, _ = make_session(answer="wrapped")
    assert asyncio.run(session.turn("q")) == "wrapped"
    text, calls = asyncio.run(session.turn_with_trace("q"))
    assert text == "wrapped"
    assert calls == []


def test_cited_answer_is_rendered_and_sources_snapshotted(make_session, tmp_path):
    session, _ = make_session(
        answer="Transformers work [[cite:src-known]]. Really [[cite:src-known]]."
    )
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.turn_outcome("tell me"))

    assert "Transformers work [1]. Really [1]." in outcome.text
    assert "Sources:" in outcome.text
    assert "[identity_verified]" in outcome.text
    assert [s.source_id for s in outcome.sources] == ["src-known"]
    # TurnRecord carries the snapshot.
    assert session.recent_turns[-1].sources[0].source_id == "src-known"


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
    assert any("unknown_marker" in err for err in blocked.validation_errors)


def test_dangling_cite_marker_blocks(make_session, tmp_path):
    session, _ = make_session(answer="Bogus [[cite:src-ghost]].")
    _seed_verified_source(session, tmp_path)
    outcome = asyncio.run(session.turn_outcome("q"))
    assert any("dangling_cite" in err for err in outcome.validation_errors)


def test_sources_hint_appears_in_prompt_after_registration(make_session, tmp_path):
    session, _ = make_session()
    assert session._build_sources_hint() is None
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
