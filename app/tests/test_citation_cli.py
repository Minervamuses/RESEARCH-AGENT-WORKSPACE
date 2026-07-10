"""Standalone citation CLI: interactive-only contract, shared Coordinator."""

import asyncio

from citation.cli import build_parser, run_repl
from citation.coordinator import CitationCoordinator
from citation.hub import CitationProviderHub

from tests.test_citation_coordinator import DOI_A, RoutingFetcher


def _coordinator(tmp_path):
    hub = CitationProviderHub(env={}, fetcher=RoutingFetcher())
    return CitationCoordinator(hub, output_dir=tmp_path / "cite")


def _scripted_repl(coordinator, lines, *, initial_query=""):
    queue = list(lines)
    outputs = []

    async def read_line(_prompt):
        if not queue:
            raise EOFError
        return queue.pop(0)

    rc = asyncio.run(run_repl(
        coordinator,
        initial_query=initial_query,
        read_line=read_line,
        write=outputs.append,
    ))
    return rc, "\n".join(str(o) for o in outputs)


def test_parser_has_no_auto_mode():
    parser = build_parser()
    options = {
        opt for action in parser._actions for opt in action.option_strings
    }
    assert "--auto" not in options
    assert "--auto-attempts" not in options
    help_text = parser.format_help()
    assert "auto" not in help_text.lower().replace("automatic", "")
    assert "--no-mcp" in help_text


def test_scripted_search_select_confirm_flow_saves_bundle(tmp_path):
    coordinator = _coordinator(tmp_path)
    rc, output = _scripted_repl(
        coordinator,
        ["select c1", "confirm m1", "sources", "quit"],
        initial_query="paper",
    )
    assert rc == 0
    assert "found 2 candidate(s)" in output
    assert "Confirmable matches" in output
    assert "citation confirmed" in output
    assert f"DOI: {DOI_A}" in output
    assert "identity_verified" in output
    assert len(list((tmp_path / "cite").glob("*/reference.bib"))) == 1


def test_confirm_requires_prior_interactive_select(tmp_path):
    # No hidden auto-selection: confirming without select is invalid_state.
    coordinator = _coordinator(tmp_path)
    rc, output = _scripted_repl(
        coordinator, ["search paper", "confirm m1", "quit"]
    )
    assert rc == 0
    assert "invalid_state" in output
    assert list((tmp_path / "cite").glob("*/reference.bib")) == []


def test_slash_prefix_and_help_and_errors(tmp_path):
    coordinator = _coordinator(tmp_path)
    rc, output = _scripted_repl(
        coordinator,
        ["help", "/citation status", "/unknown thing", "show", "quit"],
    )
    assert rc == 0
    assert "usage: /citation" in output
    assert "workflow_id: none" in output
    assert "(unknown command" in output
    assert "(error: usage: /citation show <candidate-id>)" in output


def test_eof_exits_cleanly(tmp_path):
    coordinator = _coordinator(tmp_path)
    rc, _ = _scripted_repl(coordinator, [])
    assert rc == 0
