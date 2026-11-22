"""Same-turn document_edit results keep only the latest full text in model input (K4-S2)."""

from __future__ import annotations

import asyncio
import copy
import json
import uuid

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.desktop.documents import utf16_length
from agent.document_context import compact_edit_result, compact_edit_results
from agent.observability import measure_document_context
from desktop_support import _Sink, _setup

SNAPSHOT_KEYS = ("rootPath", "path", "editorRevision", "sourceText", "diskFingerprint")


def _replace(text: str, start: int, end: int, replacement: str) -> str:
    encoded = text.encode("utf-16-le")
    return (encoded[:start * 2] + replacement.encode("utf-16-le") + encoded[end * 2:]).decode("utf-16-le")


def _tool(call_id: str, result: dict) -> ToolMessage:
    return ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=call_id, name="document_edit")


def test_only_the_latest_saved_result_keeps_full_text_and_inputs_stay_untouched():
    text_1, text_2, text_3 = "前文😀\n第一版\n後文\n", "前文😀\n第二版\n後文\n", "前文😀\n第三版\n後文\n"
    start = utf16_length("前文😀\n")
    saved = [
        {"status": "saved", "path": "/r/a.md", "callId": f"c{index}", "editorRevision": index,
         "diskFingerprint": f"fp{index}", "rangeStartUtf16": start, "rangeEndUtf16": start + 3, "sourceText": text}
        for index, text in enumerate((text_1, text_2, text_3), start=1)
    ]
    conflict = {"status": "conflict", "candidateText": "x", "currentDiskText": "y", "issue": "changed"}
    messages = [
        HumanMessage(content="edit"), _tool("a", saved[0]), _tool("b", conflict),
        _tool("c", saved[1]), ToolMessage(content="plain", tool_call_id="d", name="rag_search"),
        _tool("e", saved[2]),
    ]
    before = copy.deepcopy(messages)

    compacted = compact_edit_results(messages)

    assert messages == before  # The graph's own messages are never modified.
    assert compacted is not messages
    assert compacted[2] is messages[2] and compacted[4] is messages[4] and compacted[5] is messages[5]
    first, second = json.loads(compacted[1].content), json.loads(compacted[3].content)
    assert "sourceText" not in first and first["rangeText"] == "第一版" and second["rangeText"] == "第二版"
    assert first["editorRevision"] == 1 and first["documentLengthUtf16"] == utf16_length(text_1)
    assert first["path"] == "/r/a.md" and first["callId"] == "c1" and first["status"] == "saved"
    assert json.loads(compacted[2].content) == conflict  # Diagnostics stay.
    measure = measure_document_context(compacted)
    assert measure["document_full_copies"] == 1 + 2  # Latest saved text plus the conflict's two texts.


def test_whole_document_earlier_results_keep_no_text_and_odd_results_pass_through():
    whole = {"status": "saved", "sourceText": "全文😀\n", "rangeStartUtf16": 0, "rangeEndUtf16": utf16_length("全文😀\n")}
    compact = compact_edit_result(whole)
    assert "rangeText" not in compact and "sourceText" not in compact
    assert compact["documentLengthUtf16"] == utf16_length("全文😀\n")
    assert compact_edit_result({"status": "failed", "candidateText": "x"}) is None
    assert compact_edit_result({"status": "saved", "sourceText": "abc", "rangeStartUtf16": 2, "rangeEndUtf16": 9}) is None
    single = [HumanMessage(content="x"), _tool("a", whole)]
    assert compact_edit_results(single) == single


@pytest.mark.parametrize("scenario", ["partial", "whole", "replay"])
def test_three_same_turn_edits_send_one_full_edit_result(tmp_path, monkeypatch, scenario):
    async def run():
        service, model, path, _opened = await _setup(tmp_path, monkeypatch)
        source = "# 稿件\n\n第一段😀中文。\n\n第二段🎉要改寫。\n\n尾段。\n"
        path.write_text(source, encoding="utf-8")
        opened = await service.dispatch("document.open", {"path": str(path)})
        if scenario == "whole":
            start, end = 0, utf16_length(source)
            replacements = [
                source.replace("第二段🎉要改寫。", f"第二段🎉第{index}次全文修訂✅。") for index in (1, 2, 3)
            ]
            call_ids = ["w1", "w2", "w3"]
        else:
            start = utf16_length(source[:source.index("第二段")])
            end = start + utf16_length("第二段🎉要改寫。")
            replacements = ["第二段🎉第一次修訂😀", "第二段🎉第二次修訂😀較長", "第三次🙂"]
            call_ids = ["e1", "e1", "e2"] if scenario == "replay" else ["e1", "e2", "e3"]
            if scenario == "replay":
                replacements = [replacements[0], replacements[0], replacements[1]]
        context = {**opened, "rangeStartUtf16": start, "rangeEndUtf16": end}

        async def scripted(messages):
            index = len(model.calls)
            model.calls.append(messages)
            if index == len(call_ids):
                return AIMessage(content="三次修改都已處理。")
            return AIMessage(content="", tool_calls=[{
                "name": "document_edit", "id": call_ids[index], "type": "tool_call",
                "args": {"replacement_text": replacements[index]},
            }])

        model.ainvoke = scripted

        def follow_save(sink, receipt):
            sink.context = {key: receipt[key] for key in (*SNAPSHOT_KEYS, "rangeStartUtf16", "rangeEndUtf16")}

        sink = _Sink(service, context, on_saved=follow_save)
        result = await service.dispatch("session.turn", {
            "text": "連續修改三次", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context,
        }, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert result["state"] == "completed"

        # Disk bytes and UTF-16 ranges follow every saved edit exactly.
        expected, edit_end = source, end
        distinct = list(dict.fromkeys(zip(call_ids, replacements)))
        for _call_id, replacement in distinct:
            expected = _replace(expected, start, edit_end, replacement)
            edit_end = start + utf16_length(replacement)
        assert path.read_bytes() == expected.encode("utf-8")
        assert [receipt["status"] for receipt in sink.results] == ["saved"] * len(distinct)
        assert [(receipt["rangeStartUtf16"], receipt["rangeEndUtf16"]) for receipt in sink.results] == [
            (start, start + utf16_length(replacement)) for _call_id, replacement in distinct
        ]
        # The editor and stored candidates still see complete results.
        assert all(isinstance(receipt["sourceText"], str) for receipt in sink.results)
        assert all(isinstance(candidate.result["sourceText"], str) for candidate in service._document_candidates.values())

        # Model input: after each edit only the newest edit result carries a full text.
        assert len(model.calls) == 4
        for call in model.calls[1:]:
            tools = [message for message in call if isinstance(message, ToolMessage)]
            assert measure_document_context(tools)["document_full_copies"] == 1
            latest = json.loads(tools[-1].content)
            assert latest["sourceText"] == path.read_text(encoding="utf-8") or len(tools) < 3
            for earlier in tools[:-1]:
                compact = json.loads(earlier.content)
                assert "sourceText" not in compact and compact["status"] == "saved"
                assert ("rangeText" in compact) is (scenario != "whole")
            # The user message's submitted snapshot is counted separately (K3).
            users = [message for message in call if isinstance(message, HumanMessage)]
            assert measure_document_context(users)["document_full_copies"] == 1
        if scenario != "whole":
            third = [json.loads(message.content) for message in model.calls[3] if isinstance(message, ToolMessage)]
            assert [item.get("rangeText") for item in third[:-1]] == [replacements[0], replacements[1]]
        # Earlier model inputs kept the original full result objects: nothing was compacted in place.
        second_call_tool = next(message for message in model.calls[1] if isinstance(message, ToolMessage))
        assert "sourceText" in json.loads(second_call_tool.content)

    asyncio.run(run())
