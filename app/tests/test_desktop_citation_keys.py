"""Desktop document turns: bibliography_lookup and the unknown-key guard."""

import asyncio
import json
import uuid

from langchain_core.messages import AIMessage, ToolMessage

from desktop_support import _DocumentModel, _setup, _Sink

LIBRARY = [
    {"id": "ng2021journal", "type": "article-journal", "title": "A Journal Article",
     "author": [{"family": "Ng", "given": "Kim"}], "issued": {"date-parts": [[2021]]},
     "DOI": "10.1038/s41586-021-03819-2"},
    {"id": "lab2019site", "type": "webpage", "title": "Lab site",
     "author": [{"literal": "Plant Lab"}], "issued": {"date-parts": [[2019]]}},
]


def _write_library(root, items=LIBRARY):
    (root / "references.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
    )


class _LookupModel(_DocumentModel):
    def __init__(self, query):
        super().__init__()
        self.query = query
        self.tool_results = []

    def invoke(self, messages):
        self.calls.append(messages)
        if isinstance(messages[-1], ToolMessage):
            self.tool_results.append(messages[-1])
            return AIMessage(content="lookup done")
        return AIMessage(content="", tool_calls=[{
            "name": "bibliography_lookup", "id": "lookup-1",
            "args": {"query": self.query}, "type": "tool_call",
        }])


async def _turn(service, context, text="改寫選取段落"):
    sink = _Sink(service, context)
    params = {"text": text, "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context}
    result = await service.dispatch("session.turn", params, event_sink=sink)
    await asyncio.gather(*sink.tasks)
    return result, sink


def _tool_message(model, name):
    for messages in model.calls:
        for message in messages:
            if isinstance(message, ToolMessage) and message.name == name:
                last = message
    return json.loads(last.content)


def test_lookup_runs_in_a_document_turn_without_approval(tmp_path, monkeypatch):
    async def run():
        service, model, _path, context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        # The graph already holds this model instance; switch its behavior.
        lookup = _LookupModel("Ng 2021")
        lookup.calls = model.calls
        model.invoke = lookup.invoke
        model.tool_results = lookup.tool_results
        result, sink = await _turn(service, context, "找 Ng 2021 的 key")
        assert result["text"] == "lookup done"
        assert not [e for e, _ in sink.events if e == "approval.required"]
        payload = json.loads(model.tool_results[0].content)
        assert payload["status"] == "ok"
        assert payload["total"] == 2
        assert [e["key"] for e in payload["entries"]] == ["ng2021journal"]
        assert "verification" not in payload["entries"][0]
        assert any("bibliography_lookup" in names for names in model.bound_names)
    asyncio.run(run())


def test_unknown_new_key_fails_without_a_candidate(tmp_path, monkeypatch):
    async def run():
        service, model, path, context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        before = path.read_bytes()
        model.replacement = "新段落 [@ng2021journal; @ghost2024made]。"
        result, sink = await _turn(service, context)
        assert result["text"] == "Document operation: failed."
        payload = _tool_message(model, "document_edit")
        assert payload["unknownKeys"] == ["ghost2024made"]
        assert "/citation" in payload["issue"]
        assert not [e for e, _ in sink.events if e in {"document.proposed", "approval.required"}]
        assert path.read_bytes() == before
    asyncio.run(run())


def test_known_keys_produce_a_normal_candidate(tmp_path, monkeypatch):
    async def run():
        service, model, path, context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        model.replacement = "新段落 [@ng2021journal; @lab2019site]。\n"
        result, sink = await _turn(service, context)
        assert result["text"] == "Document operation: saved."
        assert [e for e, _ in sink.events if e == "document.proposed"]
        assert path.read_text(encoding="utf-8") == "新段落 [@ng2021journal; @lab2019site]。\n"
    asyncio.run(run())


def test_unknown_key_already_in_the_range_is_kept(tmp_path, monkeypatch):
    async def run():
        service, model, path, _context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        path.write_text("舊文 [@legacy1999old]。\n", encoding="utf-8")
        context = await service.dispatch("document.open", {"path": str(path)})
        model.replacement = "改寫後的舊文 [@legacy1999old; @ng2021journal]。\n"
        result, _sink = await _turn(service, context)
        assert result["text"] == "Document operation: saved."
        assert "@legacy1999old" in path.read_text(encoding="utf-8")
    asyncio.run(run())


async def _open_with_selection(service, path, text, selected, occurrence=0):
    path.write_text(text, encoding="utf-8")
    context = await service.dispatch("document.open", {"path": str(path)})
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(selected, start + 1)
    return {**context, "rangeStartUtf16": start, "rangeEndUtf16": start + len(selected)}


def test_partial_selection_inside_a_citation_cannot_introduce_an_unknown_key(tmp_path, monkeypatch):
    """Acceptance P1: replacing only `ng2021journal` inside [@ng2021journal] with `ghost`."""
    async def run():
        service, model, path, _context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        text = "研究指出 [@ng2021journal]。🙂\n"
        context = await _open_with_selection(service, path, text, "ng2021journal")
        model.replacement = "ghost"
        result, sink = await _turn(service, context)
        assert result["text"] == "Document operation: failed."
        assert _tool_message(model, "document_edit")["unknownKeys"] == ["ghost"]
        assert not [e for e, _ in sink.events if e in {"document.proposed", "approval.required"}]
        assert path.read_text(encoding="utf-8") == text
    asyncio.run(run())


def test_selection_that_completes_a_citation_is_checked_in_the_result(tmp_path, monkeypatch):
    async def run():
        service, model, path, _context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        text = "見 [@ng2021journal] 與尾段。\n"
        # The replacement alone has no complete citation; the saved text would.
        context = await _open_with_selection(service, path, text, "[@")
        model.replacement = "[@ghost2020x; @"
        result, _sink = await _turn(service, context)
        assert result["text"] == "Document operation: failed."
        assert _tool_message(model, "document_edit")["unknownKeys"] == ["ghost2020x"]
        assert path.read_text(encoding="utf-8") == text
    asyncio.run(run())


def test_partial_edit_to_another_known_key_is_saved(tmp_path, monkeypatch):
    async def run():
        service, model, path, _context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        text = "研究指出 [@ng2021journal]。\n"
        context = await _open_with_selection(service, path, text, "ng2021journal")
        model.replacement = "lab2019site"
        result, _sink = await _turn(service, context)
        assert result["text"] == "Document operation: saved."
        assert path.read_text(encoding="utf-8") == "研究指出 [@lab2019site]。\n"
    asyncio.run(run())


def test_another_use_of_an_existing_unknown_key_is_refused(tmp_path, monkeypatch):
    async def run():
        service, model, path, _context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        text = "舊文 [@legacy1999old]。\n\n新段落。\n"
        context = await _open_with_selection(service, path, text, "新段落。")
        model.replacement = "新段落 [@legacy1999old]。"
        result, _sink = await _turn(service, context)
        assert result["text"] == "Document operation: failed."
        assert _tool_message(model, "document_edit")["unknownKeys"] == ["legacy1999old"]
        assert path.read_text(encoding="utf-8") == text
    asyncio.run(run())


def test_link_with_at_sign_is_not_treated_as_a_citation(tmp_path, monkeypatch):
    """Acceptance P2: [Profile](https://example.org/@ghost) is a link, not a citation."""
    async def run():
        service, model, path, _context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        text = "作者頁面。\n"
        context = await _open_with_selection(service, path, text, "作者頁面。")
        model.replacement = '作者頁面 [Profile](https://example.org/@ghost "about @ghost2")。'
        result, _sink = await _turn(service, context)
        assert result["text"] == "Document operation: saved."
        assert "@ghost" in path.read_text(encoding="utf-8")
    asyncio.run(run())


def test_unknown_key_inside_a_footnote_is_refused(tmp_path, monkeypatch):
    """Acceptance 2026-11-06: `[^n]: [@ghost]` is a footnote, not a link definition."""
    async def run():
        service, model, path, _context = await _setup(tmp_path, monkeypatch)
        _write_library(tmp_path)
        text = "Claim.\n"
        context = await _open_with_selection(service, path, text, "Claim.")
        model.replacement = "Claim[^n].\n\n[^n]: [@ghost]"
        result, _sink = await _turn(service, context)
        assert result["text"] == "Document operation: failed."
        assert _tool_message(model, "document_edit")["unknownKeys"] == ["ghost"]
        assert path.read_text(encoding="utf-8") == text
        report = await service.dispatch("bibliography.inspect", {"documentContext": {
            **context, "sourceText": "Claim[^n].\n\n[^n]: [@ghost]\n"}})
        assert report["missing"] == ["ghost"]
    asyncio.run(run())


def test_unreadable_bibliography_only_blocks_new_keys(tmp_path, monkeypatch):
    async def run():
        service, model, path, context = await _setup(tmp_path, monkeypatch)
        (tmp_path / "references.json").write_text("{broken", encoding="utf-8")
        model.replacement = "沒有引用的修改。\n"
        result, _sink = await _turn(service, context)
        assert result["text"] == "Document operation: saved."
        model.replacement = "加了引用 [@ng2021journal]。\n"
        context = await service.dispatch("document.open", {"path": str(path)})
        sink = _Sink(service, context)
        params = {"text": "再改", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context}
        result = await service.dispatch("session.turn", params, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert result["text"] == "Document operation: failed."
        payload = _tool_message(model, "document_edit")
        assert payload["unknownKeys"] == ["ng2021journal"]
        assert "cannot be read" in payload["issue"]
    asyncio.run(run())


def test_document_prompt_explains_keys(tmp_path, monkeypatch):
    async def run():
        service, model, _path, context = await _setup(tmp_path, monkeypatch)
        await _turn(service, context, "分析這段")
        prompt = model.calls[0][-1].content
        assert "bibliography_lookup" in prompt and "[@key]" in prompt and "\\cite{key}" in prompt
        assert "never invent a key" in prompt
    asyncio.run(run())


def test_lookup_is_not_offered_to_extended_thinking_proposers():
    from agent.thinking.orchestrator import FUSION_READ_ONLY_ALLOWLIST

    assert "bibliography_lookup" not in FUSION_READ_ONLY_ALLOWLIST


def test_lookup_is_effective_in_citation_turns_only_when_offered(monkeypatch, tmp_path):
    import asyncio
    from langchain_core.tools import StructuredTool

    from conftest import make_astream_graph
    from agent.config import AgentConfig
    from agent.session import ChatSession

    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _config: [])
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr("agent.session.build_graph", lambda _cfg, extra_tools=None, **kwargs: make_astream_graph())
    lookup = StructuredTool.from_function(func=lambda query: "[]", name="bibliography_lookup",
                                          description="lookup")
    config = AgentConfig(persist_dir=str(tmp_path / "store"))
    session = ChatSession(config, extra_tools=[lookup])
    assert session.mcp_families["bibliography_lookup"] == "desktop_document"
    assert "bibliography_lookup" not in session.tool_access_resolution().effective_tools
    desktop_effective: list[tuple[str, ...]] = []
    session.graph = make_astream_graph(
        on_state=lambda _s: desktop_effective.append(session.tool_access_resolution().effective_tools),
    )
    asyncio.run(session.turn("find papers", skill_name="citation"))
    assert "bibliography_lookup" in desktop_effective[0]
    assert "bibliography_lookup" not in session.tool_access_resolution().effective_tools

    cli = ChatSession(config)
    cli_effective: list[tuple[str, ...]] = []
    cli.graph = make_astream_graph(
        on_state=lambda _s: cli_effective.append(cli.tool_access_resolution().effective_tools),
    )
    asyncio.run(cli.turn("find papers", skill_name="citation"))
    assert "bibliography_lookup" not in cli_effective[0]
