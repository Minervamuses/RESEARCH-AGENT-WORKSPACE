"""The /citation slash command: dispatch, formatting, and no /cite alias."""

import asyncio
import json

import pytest

from agent.cli.slash_commands import (
    SlashCommandContext,
    SlashCommandError,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from skills.citation.coordinator import CitationCoordinator
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.net import FetchResponse

from tests.test_citation_coordinator import CROSSREF_ITEMS, DOI_A, RoutingFetcher


class SessionWithCoordinator:
    def __init__(self, tmp_path):
        fetcher = RoutingFetcher()
        hub = CitationProviderHub(env={}, fetcher=fetcher)
        self.citation_coordinator = CitationCoordinator(
            hub, output_dir=tmp_path / "cite"
        )


def _context(session):
    return SlashCommandContext(session=session, registry=build_default_registry())


def _run(session, raw):
    parsed = parse_slash_command(raw)
    return asyncio.run(execute_slash_command(parsed, _context(session)))


def test_registry_has_citation_but_no_cite_alias():
    registry = build_default_registry()
    assert registry.get("citation") is not None
    assert registry.get("cite") is None


def test_bare_query_is_a_search(tmp_path):
    session = SessionWithCoordinator(tmp_path)
    result = _run(session, "/citation attention papers")
    assert "found 2 candidate(s)" in result.message
    assert "[c1]" in result.message
    assert "provider crossref: ok" in result.message
    assert "provider openalex: disabled" in result.message


def test_search_list_show_flow(tmp_path):
    session = SessionWithCoordinator(tmp_path)
    _run(session, "/citation search paper")
    listed = _run(session, "/citation list")
    assert "page 1/1" in listed.message
    shown = _run(session, "/citation show c1")
    assert "Candidate c1" in shown.message
    assert "Paper A" in shown.message
    missing = _run(session, "/citation show zz")
    assert "unknown or stale" in missing.message


def test_select_and_confirm_flow_saves_bundle(tmp_path):
    session = SessionWithCoordinator(tmp_path)
    _run(session, "/citation search paper")
    selected = _run(session, "/citation select c1")
    assert "Confirmable matches" in selected.message
    assert "[m1]" in selected.message

    confirmed = _run(session, "/citation confirm m1")
    assert "citation confirmed" in confirmed.message
    assert f"DOI: {DOI_A}" in confirmed.message
    assert "[[cite:src-" in confirmed.message
    bundles = list((tmp_path / "cite").glob("*/reference.bib"))
    assert len(bundles) == 1

    sources = _run(session, "/citation sources")
    assert "identity_verified" in sources.message
    source_id = json.loads(
        next((tmp_path / "cite").glob("*/citation.json")).read_text(encoding="utf-8")
    )["source_ref"]["source_id"]
    detail = _run(session, f"/citation source {source_id}")
    assert "re-activated" in detail.message


def test_status_and_cancel(tmp_path):
    session = SessionWithCoordinator(tmp_path)
    _run(session, "/citation search paper")
    status = _run(session, "/citation status")
    assert "workflow_id: wf-" in status.message
    assert "candidates: 2" in status.message
    cancelled = _run(session, "/citation cancel")
    assert "cancelled" in cancelled.message
    stale = _run(session, "/citation select c1")
    assert "invalid_state" in stale.message


def test_usage_errors_are_slash_command_errors(tmp_path):
    session = SessionWithCoordinator(tmp_path)
    for raw in (
        "/citation",
        "/citation search",
        "/citation show",
        "/citation select a b",
        "/citation confirm",
        "/citation status extra",
        "/citation list one two",
    ):
        with pytest.raises(SlashCommandError):
            _run(session, raw)


def test_session_without_coordinator_is_rejected():
    class Bare:
        citation_coordinator = None

    with pytest.raises(SlashCommandError):
        _run(Bare(), "/citation query")


def test_pagination_of_candidates(tmp_path):
    fetcher = RoutingFetcher()
    many = [
        {
            "DOI": f"10.1234/p{i:02d}",
            "title": [f"Paper {i}"],
            "issued": {"date-parts": [[2020]]},
            "score": 20.0 - i,
        }
        for i in range(15)
    ]
    fetcher.crossref_response = FetchResponse(
        status=200, body=json.dumps({"message": {"items": many}}).encode()
    )
    session = SessionWithCoordinator(tmp_path)
    session.citation_coordinator = CitationCoordinator(
        CitationProviderHub(env={}, fetcher=fetcher), output_dir=tmp_path / "cite"
    )
    _run(session, "/citation search papers")
    page1 = _run(session, "/citation list 1")
    page2 = _run(session, "/citation list 2")
    assert "page 1/2" in page1.message
    assert "page 2/2" in page2.message
    assert "[c11]" in page2.message and "[c1]" not in page2.message


def test_real_chat_session_exposes_lazy_coordinator(monkeypatch, tmp_path):
    # The ChatSession property builds a Coordinator from the process hub and
    # the session's already-loaded web tools without touching MCP again.
    import agent.session as session_module
    from agent.config import AgentConfig
    from tests.conftest import FakeHistoryStore

    config = AgentConfig(citation_output_dir=str(tmp_path / "cite"))
    session = session_module.ChatSession(
        config, history_store=FakeHistoryStore()
    )
    coordinator = session.citation_coordinator
    assert coordinator is session.citation_coordinator  # cached
    assert str(coordinator._output_dir) == str(tmp_path / "cite")  # noqa: SLF001
