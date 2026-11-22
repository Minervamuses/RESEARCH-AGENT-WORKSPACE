"""Fifteen document turns in one desktop session, measured per model call (K2-S2).

The scenario runs the real desktop service and session graph with a scripted
fake model; no network or paid model is involved. Every model call's messages
are measured with ``measure_document_context``. Set
``DOCUMENT_BUDGET_REPORT=<path>`` to write the measurements as JSON.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.desktop.documents import utf16_length
from agent.observability import measure_document_context
from desktop_support import _Sink, _setup

SECTION_COUNT = 12
SNAPSHOT_KEYS = ("rootPath", "path", "editorRevision", "sourceText", "diskFingerprint")

# (kind, target section index); kinds: edit, double, whole, analyze, reference.
TURN_PLAN = [
    ("edit", 0), ("analyze", None), ("edit", 1), ("edit", 2), ("double", 3),
    ("analyze", None), ("whole", 4), ("edit", 5), ("reference", None), ("edit", 6),
    ("edit", 7), ("analyze", None), ("edit", 8), ("edit", 9), ("edit", 10),
]
PROMPTS = {
    "edit": "改寫選取段落",
    "double": "連續改寫選取段落兩次",
    "whole": "改寫整份稿件中的一段",
    "analyze": "分析這份稿件",
    "reference": "分析舊版引用與目前稿件的差異",
}


def _document() -> str:
    sections = []
    for index in range(SECTION_COUNT):
        body = f"研究方法與資料分析段落 {index}：樣本、變項與限制😀。" * 26
        sections.append(f"## 第 {index + 1} 節\n\n{body}")
    return "\n\n".join(sections) + "\n"


def _section_range(text: str, index: int) -> tuple[int, int]:
    """UTF-16 range of section ``index``'s body paragraph."""
    marker = f"## 第 {index + 1} 節\n\n"
    start = text.index(marker) + len(marker)
    end = text.index("\n", start)
    return utf16_length(text[:start]), utf16_length(text[:end])


def _slice(text: str, start: int, end: int) -> str:
    encoded = text.encode("utf-16-le")
    return encoded[start * 2:end * 2].decode("utf-16-le")


def _replace(text: str, start: int, end: int, replacement: str) -> str:
    encoded = text.encode("utf-16-le")
    return (encoded[:start * 2] + replacement.encode("utf-16-le") + encoded[end * 2:]).decode("utf-16-le")


async def run_budget_scenario(tmp_path: Path, monkeypatch) -> dict:
    """Run the fifteen turns and return per-call measurements plus scenario facts."""
    service, model, path, _opened = await _setup(tmp_path, monkeypatch)
    path.write_text(_document(), encoding="utf-8")
    opened = await service.dispatch("document.open", {"path": str(path)})
    first_version = {key: opened[key] for key in SNAPSHOT_KEYS}
    editor = dict(first_version)
    expected_disk = editor["sourceText"]
    replacements: list[str] = []

    async def scripted(messages):
        model.calls.append(messages)
        last_human = max(index for index, message in enumerate(messages) if isinstance(message, HumanMessage))
        prompt = messages[last_human].content
        done = sum(isinstance(message, ToolMessage) for message in messages[last_human + 1:])
        for message in messages[last_human + 1:]:
            if isinstance(message, ToolMessage):
                assert json.loads(message.content)["status"] == "saved"
        if prompt.startswith("分析") or done >= len(replacements):
            return AIMessage(content="完成。" if done else "分析完成，沒有修改稿件。")
        return AIMessage(content="", tool_calls=[{
            "name": "document_edit", "id": f"edit-{done}", "type": "tool_call",
            "args": {"replacement_text": replacements[done]},
        }])

    model.ainvoke = scripted
    turns = []
    prompts = []
    for number, (kind, section) in enumerate(TURN_PLAN, start=1):
        source = editor["sourceText"]
        if kind == "whole":
            start, end = 0, utf16_length(source)
            left, right = _section_range(source, section)
            replacements = [_replace(source, left, right, _slice(source, left, right) + f"（第 {number} 回合整份修訂✅）")]
        elif kind in {"edit", "double"}:
            start, end = _section_range(source, section)
            original = _slice(source, start, end)
            replacements = [original + f"（第 {number} 回合修訂✅）"]
            if kind == "double":
                replacements.append(replacements[0] + "（同回合第二次修訂🔁）")
        else:
            start, end = _section_range(source, 0)
            replacements = []
        context = {**editor, "rangeStartUtf16": start, "rangeEndUtf16": end}
        params = {"text": PROMPTS[kind], "turnId": uuid.uuid4().hex, "retry": False}
        if kind == "reference":
            left, right = _section_range(first_version["sourceText"], 0)
            reference = {
                "referenceId": "first-version", "kind": "document",
                "text": _slice(first_version["sourceText"], left, right),
                "document": {
                    "snapshot": {**first_version, "rangeStartUtf16": left, "rangeEndUtf16": right},
                    "startLine": 3, "endLine": 3,
                },
            }
            project = service._project
            params["submittedContext"] = {
                "projectId": project["projectId"], "rootPath": project["rootPath"],
                "permissionMode": "ask", "requestedThinkingMode": "normal", "skillReferences": [],
                "projectRules": {"text": project["rulesText"], "fingerprint": project["rulesFingerprint"]},
                "documentContext": context, "references": [reference],
            }
        else:
            params["documentContext"] = context

        def follow_save(sink, receipt):
            sink.context = {key: receipt[key] for key in (*SNAPSHOT_KEYS, "rangeStartUtf16", "rangeEndUtf16")}

        sink = _Sink(service, context, on_saved=follow_save)
        first_call = len(model.calls)
        result = await service.dispatch("session.turn", params, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        saved = [receipt for receipt in sink.results if receipt["status"] == "saved"]
        assert len(saved) == len(replacements), (number, sink.results)
        if saved:
            editor = {key: saved[-1][key] for key in SNAPSHOT_KEYS}
            text = source
            for replacement in replacements:
                text = _replace(text, start, end, replacement)
                end = start + utf16_length(replacement)
            expected_disk = text
        assert path.read_text(encoding="utf-8") == expected_disk == editor["sourceText"]
        turn_calls = model.calls[first_call:]
        calls = [measure_document_context(messages) for messages in turn_calls]
        user_calls = [
            measure_document_context([message for message in messages if isinstance(message, HumanMessage)])
            for messages in turn_calls
        ]
        prompts.append(next(
            message.content for message in reversed(turn_calls[0]) if isinstance(message, HumanMessage)
        ))
        turns.append({
            "turn": number, "kind": kind, "state": result["state"], "saved_edits": len(saved),
            "document_utf16": utf16_length(editor["sourceText"]), "calls": calls,
            "user_message_calls": user_calls,
        })
    saved = service._conversation_repository.load(service.session.session_id).document.turns
    return {
        "document_bytes": len(_document().encode("utf-8")), "turns": turns,
        "_saved_inputs_match_prompts": [turn.semantic_input for turn in saved] == prompts,
    }


def summarize(report: dict) -> list[dict]:
    """Per-turn first and last call figures for a human-readable comparison."""
    rows = []
    for turn in report["turns"]:
        for label, call in (("first", turn["calls"][0]), ("last", turn["calls"][-1])):
            document = sum(call[key] for key in (
                "document_chars_current", "document_chars_history", "document_chars_tool_results",
            ))
            rows.append({
                "turn": turn["turn"], "kind": turn["kind"], "call": label,
                "model_calls": len(turn["calls"]),
                "full_copies": call["document_full_copies"],
                "current": call["document_chars_current"], "history": call["document_chars_history"],
                "tool_results": call["document_chars_tool_results"],
                "document_chars": document, "prompt_chars": call["prompt_chars"],
                "document_share": round(document / call["prompt_chars"], 4),
            })
    return rows


def test_fifteen_document_turns_are_measured(tmp_path, monkeypatch):
    report = asyncio.run(run_budget_scenario(tmp_path, monkeypatch))
    turns = report["turns"]

    assert 18_000 <= report["document_bytes"] <= 24_000
    assert len(turns) == 15 and all(turn["state"] == "completed" for turn in turns)
    assert sum(turn["saved_edits"] > 0 for turn in turns) >= 10
    assert any(turn["saved_edits"] == 2 for turn in turns)
    assert sum(turn["kind"] in {"analyze", "reference"} for turn in turns) >= 4
    for turn in turns:
        assert len(turn["calls"]) == 1 + turn["saved_edits"]
        for call in turn["calls"]:
            assert call["document_parse_issue"] is None
            assert call["document_full_copies"] >= 1
            assert call["document_chars_current"] > 0
    reference_turn = next(turn for turn in turns if turn["kind"] == "reference")
    # The old frozen version is a second full text beside the current snapshot.
    assert reference_turn["calls"][0]["document_chars_current"] > reference_turn["document_utf16"]

    # K3: every turn carries a current snapshot, so replayed history user
    # messages hold no snapshot or frozen-reference full text; only the
    # current turn's own texts remain. Tool results are K4's concern.
    for turn in turns:
        for call in turn["user_message_calls"]:
            assert call["document_chars_history"] == 0
            assert call["document_full_copies"] == (2 if turn["kind"] == "reference" else 1)
    # Saved history is unchanged: each turn's semantic_input is exactly the full prompt it sent.
    assert report.pop("_saved_inputs_match_prompts") is True

    destination = os.environ.get("DOCUMENT_BUDGET_REPORT")
    if destination:
        report["summary"] = summarize(report)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_closed_document_keeps_only_the_last_submitted_snapshot(tmp_path, monkeypatch):
    """A is submitted and saved as B, then the document closes: history keeps A, labelled."""
    from agent.desktop.service import DesktopServiceError
    from agent.document_context import (
        HISTORY_SNAPSHOT_HEADER, OMITTED_SNAPSHOT_HEADER, SNAPSHOT_HEADER, iter_document_blocks,
    )
    import pytest

    def blocks(text):
        return list(iter_document_blocks(text, (SNAPSHOT_HEADER, HISTORY_SNAPSHOT_HEADER, OMITTED_SNAPSHOT_HEADER)))

    async def run():
        service, model, path, opened = await _setup(tmp_path, monkeypatch)
        version_a = opened["sourceText"]
        project = service._project

        def submitted(context):
            return {
                "projectId": project["projectId"], "rootPath": project["rootPath"],
                "permissionMode": "ask", "requestedThinkingMode": "normal", "skillReferences": [],
                "projectRules": {"text": project["rulesText"], "fingerprint": project["rulesFingerprint"]},
                "documentContext": context, "references": [],
            }

        # Turn 1: analysis of A.
        await service.dispatch("session.turn", {
            "text": "分析 A 版", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": opened,
        }, event_sink=_Sink(service, opened))
        # Turn 2: a failed analysis, then its retry with the saved input.
        retry_turn = uuid.uuid4().hex
        model.fail_before_answer = True
        with pytest.raises(DesktopServiceError):
            await service.dispatch("session.turn", {
                "text": "分析重試", "turnId": retry_turn, "retry": False, "submittedContext": submitted(opened),
            })
        failed_prompt = model.calls[-1][-1].content
        await service.dispatch("session.turn", {
            "text": "分析重試", "turnId": retry_turn, "retry": True, "submittedContext": submitted(opened),
        })
        retried = model.calls[-1]
        assert retried[-1].content == failed_prompt  # The retry resends the saved input verbatim.
        history = [message.content for message in retried[:-1] if isinstance(message, HumanMessage)]
        assert len(history) == 1 and [block.header for block in blocks(history[0])] == [OMITTED_SNAPSHOT_HEADER]
        assert measure_document_context(retried)["document_chars_history"] == 0
        # Turn 3: edit A into B and save.
        model.replacement = "B 版全文已存檔✅\n"
        sink = _Sink(service, opened)
        await service.dispatch("session.turn", {
            "text": "改寫全文", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": opened,
        }, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert sink.results[-1]["status"] == "saved"
        version_b = path.read_text(encoding="utf-8")
        assert version_b == "B 版全文已存檔✅\n" != version_a
        # Turn 4: the document is closed; a plain question follows.
        await service.dispatch("session.turn", {"text": "分析先前的討論", "turnId": uuid.uuid4().hex, "retry": False})
        closed = model.calls[-1]
        history = [message.content for message in closed[:-1] if isinstance(message, HumanMessage)]
        assert len(history) == 3
        assert [block.header for block in blocks(history[0])] == [OMITTED_SNAPSHOT_HEADER]
        assert [block.header for block in blocks(history[1])] == [OMITTED_SNAPSHOT_HEADER]
        [kept] = blocks(history[2])
        assert kept.header == HISTORY_SNAPSHOT_HEADER and kept.value["sourceText"] == version_a
        assert json.dumps(version_b, ensure_ascii=False) not in "".join(history)
        assert "Use this exact editor snapshot" not in history[2]
        measure = measure_document_context(closed)
        assert measure["document_parse_issue"] is None
        assert measure["document_chars_history"] == len(version_a) and measure["document_full_copies"] == 1
        # Extended thinking's plain-text context follows the same replay.
        visible = service.session.visible_context_text()
        assert [block.header for block in blocks(visible)] == [
            OMITTED_SNAPSHOT_HEADER, OMITTED_SNAPSHOT_HEADER, HISTORY_SNAPSHOT_HEADER,
        ]
        service.session._active_turn_input = history[2].replace(HISTORY_SNAPSHOT_HEADER, SNAPSHOT_HEADER)
        try:
            assert HISTORY_SNAPSHOT_HEADER not in service.session.visible_context_text()
        finally:
            service.session._active_turn_input = None
        # The saved history still holds every full submitted snapshot.
        saved = service._conversation_repository.load(service.session.session_id).document.turns
        assert [turn.state for turn in saved] == ["completed"] * 4
        for turn in saved[:3]:
            [block] = blocks(turn.semantic_input)
            assert block.header == SNAPSHOT_HEADER and block.value["sourceText"] == version_a
        assert saved[3].semantic_input == "分析先前的討論"

    asyncio.run(run())
