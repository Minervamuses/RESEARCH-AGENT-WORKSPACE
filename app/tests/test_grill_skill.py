"""The @grill skill: catalog loading, read-only document turns, comment behavior (K5)."""

from __future__ import annotations

from agent.config import AgentConfig
from agent.skills import DEFAULT_SKILLS_DIR, discover_skills
from agent.skills.runtime import load_skill_runtime, resolve_skill_references


def test_grill_skill_is_in_the_catalog_and_parses_as_an_inline_reference(tmp_path):
    catalog = discover_skills(AgentConfig(persist_dir=str(tmp_path)))
    grill = next(skill for skill in catalog if skill.name == "grill")
    assert grill.path == DEFAULT_SKILLS_DIR / "grill" / "SKILL.md"
    assert "Read-only" in grill.description

    text = "請 @grill 這段，不要用 email@grill.org"
    references = resolve_skill_references(text, catalog)
    assert references == [{"name": "grill", "startUtf16": 2, "endUtf16": 8}]

    runtime = load_skill_runtime("grill", config=AgentConfig(persist_dir=str(tmp_path)), all_tools=["read_file", "bash"])
    block = runtime.context_block()
    for heading in ("## 還原", "## 發現", "## 判斷", "## 回應檢查", "｜問題", "｜資料不足", "原文：「"):
        assert heading in block


import asyncio
import json
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.desktop.protocol import success_result
from agent.desktop.service import (
    _EDITABLE_SNAPSHOT_INSTRUCTIONS,
    _READ_ONLY_REFERENCE_INSTRUCTIONS,
    _READ_ONLY_SNAPSHOT_INSTRUCTIONS,
)
from agent.document_context import SNAPSHOT_HEADER, iter_document_blocks
from agent.session import ChatSession
from test_desktop_document_service import _Sink
from test_desktop_service import _service

PASSAGE = "因為樣本平均提升 5%，所以此方法對所有學生都有效😀。"
DOCUMENT = "# 研究結果\n\n" + PASSAGE + "\n\n## 限制\n\n樣本僅來自一所學校。\n"


class _GrillModel:
    """Fake chat model: records each call and its bound tools; can try an edit."""

    def __init__(self):
        self.calls = []
        self.call_tools = []  # The tool names bound for each recorded call.
        self.try_edit = False

    def bind_tools(self, tools):
        return _Bound(self, tuple(tool.name for tool in tools))

    async def ainvoke(self, messages):
        return self.invoke(messages)

    def invoke(self, messages, names=()):
        self.calls.append(messages)
        self.call_tools.append(names)
        if isinstance(messages[-1], ToolMessage):
            return AIMessage(content="## 還原\n已檢查。\n\n## 發現\n（無）\n\n## 判斷\n判斷：通過")
        if self.try_edit:
            return AIMessage(content="", tool_calls=[{
                "name": "document_edit", "id": "forbidden-edit", "type": "tool_call",
                "args": {"replacement_text": "被改掉的段落"},
            }])
        return AIMessage(content="## 還原\n主張。\n\n## 發現\n（無）\n\n## 判斷\n判斷：通過")


class _Bound:
    def __init__(self, model, names):
        self.model, self.names = model, names

    async def ainvoke(self, messages):
        return self.model.invoke(messages, self.names)

    def invoke(self, messages):
        return self.model.invoke(messages, self.names)


async def _grill_setup(tmp_path, monkeypatch):
    model = _GrillModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _config: model)
    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _config: [])

    async def factory(config, *, load_mcp, **kwargs):
        assert load_mcp is False
        return ChatSession(config, **kwargs)  # The real skill catalog, including grill.

    service = _service(tmp_path, session_factory=factory)
    preview = await service.dispatch("workspace.select", {"rootPath": str(tmp_path), "action": "inspect"})
    project = await service.dispatch("workspace.select", {
        "rootPath": str(tmp_path), "action": "initialize",
        "historyDirectory": preview["historyDirectory"],
        "expectedFingerprint": preview["researchFingerprint"],
    })
    await service.dispatch("session.create", {"loadMcp": False, "projectId": project["projectId"]})
    path = tmp_path / "稿件.md"
    path.write_text(DOCUMENT, encoding="utf-8")
    opened = await service.dispatch("document.open", {"path": str(path)})
    success_result(str(uuid.uuid4()), "document.open", opened)
    start = len(DOCUMENT[:DOCUMENT.index(PASSAGE)].encode("utf-16-le")) // 2
    end = start + len(PASSAGE.encode("utf-16-le")) // 2
    return service, model, path, {**opened, "rangeStartUtf16": start, "rangeEndUtf16": end}


def _availability(messages) -> dict[str, list[str]]:
    block = next(message.content for message in messages
                 if isinstance(message, SystemMessage) and message.content.startswith("[Tool availability]"))
    fields = dict(line.split(": ", 1) for line in block.splitlines()[1:] if ": " in line)
    return {key: [name.strip() for name in value.split(",")] for key, value in fields.items()}


def _current_prompt(messages) -> str:
    return next(message.content for message in reversed(messages) if isinstance(message, HumanMessage))


def test_grill_document_turn_reads_the_snapshot_but_cannot_edit(tmp_path, monkeypatch):
    async def run():
        service, model, path, context = await _grill_setup(tmp_path, monkeypatch)
        session = service.session
        original = path.read_bytes()
        text = "@grill 檢查這段推論"
        references = resolve_skill_references(text, session.loaded_skills)
        model.try_edit = True  # Even a model that insists on editing cannot.
        sink = _Sink(service, context)
        result = await service.dispatch("session.turn", {
            "text": text, "turnId": uuid.uuid4().hex, "retry": False,
            "documentContext": context, "skillReferences": references,
        }, event_sink=sink)
        await asyncio.gather(*sink.tasks)

        first = model.calls[0]
        prompt = _current_prompt(first)
        [snapshot] = list(iter_document_blocks(prompt, (SNAPSHOT_HEADER,)))
        assert snapshot.value["sourceText"] == DOCUMENT  # The model reads the document.
        assert prompt.endswith(_READ_ONLY_SNAPSHOT_INSTRUCTIONS)
        assert "call document_edit with replacement_text" not in prompt
        assert any(isinstance(message, SystemMessage) and "# Grill" in message.content for message in first)
        assert "document_edit" not in model.call_tools[0]
        availability = _availability(first)
        assert "document_edit" not in availability["available_tools"]
        assert "bibliography_lookup" in availability["available_tools"]
        assert "document_edit" in availability["unavailable_tools"]
        assert "MCP family: desktop_document" not in availability["available_tools"] + availability["unavailable_tools"]
        # The insisted edit was refused by policy: no candidate, no proposal, no write.
        refusal = next(message for message in model.calls[1] if isinstance(message, ToolMessage))
        assert refusal.tool_call_id == "forbidden-edit" and "sourceText" not in refusal.content
        assert not [event for event, _ in sink.events if event in {"document.proposed", "approval.required"}]
        assert service._document_candidates == {} and path.read_bytes() == original
        assert result["state"] == "completed"
        # The turn ended: skill, document flag and thinking mode are back.
        assert session.active_skill_runtime is None and not session._document_turn_active
        assert session.thinking_mode == "normal"

        # The next document turn without @grill can edit again: grill lived one turn.
        model.try_edit = True
        sink = _Sink(service, context)
        await service.dispatch("session.turn", {
            "text": "改寫這段", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context,
        }, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        later = model.calls[2]
        assert "document_edit" in model.call_tools[2]
        # Apart from document_edit, the grill turn kept the document turn's tools.
        assert set(model.call_tools[0]) == set(model.call_tools[2]) - {"document_edit"}
        assert "bibliography_lookup" in model.call_tools[0]
        restored = _availability(later)
        assert "MCP family: desktop_document" in restored["available_tools"]  # Both document tools.
        assert not {"document_edit", "MCP family: desktop_document"} & set(restored["unavailable_tools"])
        assert _current_prompt(later).endswith(_EDITABLE_SNAPSHOT_INSTRUCTIONS)
        assert not any(isinstance(message, SystemMessage) and "# Grill" in message.content for message in later)
        assert [receipt["status"] for receipt in sink.results] == ["saved"]
        assert path.read_text(encoding="utf-8") == DOCUMENT.replace(PASSAGE, "被改掉的段落")

    asyncio.run(run())


def test_grill_with_another_skill_and_frozen_references_stays_read_only(tmp_path, monkeypatch):
    async def run():
        service, model, path, context = await _grill_setup(tmp_path, monkeypatch)
        session = service.session
        original = path.read_bytes()
        text = "先用 @academic-paper-writing 看結構，再 @grill 這段。\n\nReference passage:\n請檢查。"
        references = resolve_skill_references(text, session.loaded_skills)
        assert [reference["name"] for reference in references] == ["academic-paper-writing", "grill"]
        project = service._project
        submitted = {
            "projectId": project["projectId"], "rootPath": project["rootPath"],
            "permissionMode": "ask", "requestedThinkingMode": "normal", "skillReferences": references,
            "projectRules": {"text": project["rulesText"], "fingerprint": project["rulesFingerprint"]},
            "documentContext": context,
            "references": [{"referenceId": "passage", "kind": "document", "text": PASSAGE,
                            "document": {"snapshot": context, "startLine": 3, "endLine": 3}}],
        }
        model.try_edit = True
        sink = _Sink(service, context)
        await service.dispatch("session.turn", {
            "text": text, "turnId": uuid.uuid4().hex, "retry": False, "submittedContext": submitted,
        }, event_sink=sink)
        await asyncio.gather(*sink.tasks)

        prompt = _current_prompt(model.calls[0])
        assert prompt.endswith(_READ_ONLY_REFERENCE_INSTRUCTIONS)
        assert _READ_ONLY_SNAPSHOT_INSTRUCTIONS in prompt
        assert "Use reference_id in document_edit" not in prompt
        assert "document_edit" not in model.call_tools[0] and model.call_tools[0]
        assert "document_edit" in _availability(model.calls[0])["unavailable_tools"]
        assert service._document_candidates == {} and path.read_bytes() == original
        assert session.active_skill_runtime is None

    asyncio.run(run())
