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
from test_desktop_document_service import _Sink, _setup

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
        calls = [measure_document_context(messages) for messages in model.calls[first_call:]]
        turns.append({
            "turn": number, "kind": kind, "state": result["state"], "saved_edits": len(saved),
            "document_utf16": utf16_length(editor["sourceText"]), "calls": calls,
        })
    return {"document_bytes": len(_document().encode("utf-8")), "turns": turns}


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

    destination = os.environ.get("DOCUMENT_BUDGET_REPORT")
    if destination:
        report["summary"] = summarize(report)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
