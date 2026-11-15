"""Replaying saved document turns to the model without old full texts (K3-S1)."""

from __future__ import annotations

import copy
import json

from langchain_core.messages import HumanMessage

from agent.document_context import (
    FROZEN_REFERENCES_HEADER,
    HISTORY_REFERENCES_HEADER,
    HISTORY_SNAPSHOT_HEADER,
    OMITTED_SNAPSHOT_HEADER,
    SNAPSHOT_HEADER,
    has_current_snapshot,
    iter_document_blocks,
    replay_history_inputs,
)
from agent.observability import measure_document_context

EDIT_INSTRUCTIONS = (
    "\nUse this exact editor snapshot, including unsaved text. Source lines start at 1; "
    "For an explicitly requested edit, call document_edit with replacement_text for only that range."
)
GRILL_INSTRUCTIONS = (
    "\nUse this exact editor snapshot as read-only material for this grill turn. "
    "Do not edit the document; document_edit is unavailable."
)
REFERENCE_INSTRUCTIONS = (
    "\nA snapshot with sourceTextSameAs omits sourceText because that exact full text "
    "appears earlier in this message. Use reference_id in document_edit."
)

DOC_V1 = "# 稿件\n第一段 alpha 😀\n第二段 beta\n第三段 gamma\n" + "填充內容。" * 40 + "\n"
DOC_V2 = DOC_V1.replace("beta", "beta（已修訂✅）")


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _snapshot(source: str, revision: int, start: int | None = None, end: int | None = None) -> dict:
    snapshot = {
        "rootPath": "/root", "path": "/root/稿件.md", "editorRevision": revision,
        "diskFingerprint": f"{revision:064x}", "sourceText": source,
    }
    if start is not None:
        snapshot.update(rangeStartUtf16=start, rangeEndUtf16=end)
    return snapshot


def _range_of(source: str, needle: str) -> tuple[int, int]:
    index = source.index(needle)
    return _utf16(source[:index]), _utf16(source[:index + len(needle)])


def _turn(user: str, snapshot: dict | None, references: list | None = None, *, instructions=EDIT_INSTRUCTIONS) -> str:
    text = user
    if snapshot is not None:
        text += f"\n\n{SNAPSHOT_HEADER}\n" + json.dumps(snapshot, ensure_ascii=False, sort_keys=True) + instructions
    if references is not None:
        text += f"\n\n{FROZEN_REFERENCES_HEADER}\n" + json.dumps(references, ensure_ascii=False, sort_keys=True) + REFERENCE_INSTRUCTIONS
    return text


def _blocks(text: str) -> list:
    headers = (SNAPSHOT_HEADER, FROZEN_REFERENCES_HEADER, HISTORY_SNAPSHOT_HEADER,
               OMITTED_SNAPSHOT_HEADER, HISTORY_REFERENCES_HEADER)
    return list(iter_document_blocks(text, headers))


def test_current_snapshot_turns_every_history_snapshot_into_a_placeholder():
    start, end = _range_of(DOC_V1, "第二段 beta")
    turns = [(1, _turn("改寫第二段", _snapshot(DOC_V1, 1, start, end))),
             (2, _turn("再看一次", _snapshot(DOC_V2, 2)))]
    original = copy.deepcopy(turns)

    replayed = replay_history_inputs(turns, current_has_snapshot=True)

    assert turns == original
    assert json.dumps(DOC_V1, ensure_ascii=False) not in replayed[0]
    assert json.dumps(DOC_V2, ensure_ascii=False) not in replayed[1]
    assert replayed[0].startswith("改寫第二段\n\n" + OMITTED_SNAPSHOT_HEADER + "\n")
    [block] = _blocks(replayed[0])
    placeholder = block.value
    assert placeholder["turnNumber"] == 1 and placeholder["path"] == "/root/稿件.md"
    assert placeholder["editorRevision"] == 1 and placeholder["diskFingerprint"] == f"{1:064x}"
    assert (placeholder["rangeStartUtf16"], placeholder["rangeEndUtf16"]) == (start, end)
    assert (placeholder["startLine"], placeholder["endLine"]) == (3, 3)
    assert placeholder["selectedText"] == "第二段 beta"
    assert "turn 1" in placeholder["archive"] and "conversation archive" in placeholder["archive"]
    # A whole-document range is not a narrow selection: only its length is kept.
    [whole] = _blocks(replayed[1])
    assert "selectedText" not in whole.value and whole.value["selectedTextChars"] == len(DOC_V2)
    assert "call document_edit" not in "".join(replayed)
    assert "not the current document" in OMITTED_SNAPSHOT_HEADER


def test_without_current_snapshot_only_the_last_submitted_snapshot_keeps_text():
    turns = [(3, _turn("第一次", _snapshot(DOC_V1, 1))),
             (4, "沒有文件的閒聊"),
             (5, _turn("第二次", _snapshot(DOC_V2, 2))),
             (6, "文件關閉後的問題")]

    replayed = replay_history_inputs(turns, current_has_snapshot=False)

    assert json.dumps(DOC_V1, ensure_ascii=False) not in replayed[0]
    assert replayed[1] == "沒有文件的閒聊" and replayed[3] == "文件關閉後的問題"
    assert replayed[2].startswith("第二次\n\n" + HISTORY_SNAPSHOT_HEADER + "\n")
    [kept] = _blocks(replayed[2])
    assert kept.value == _snapshot(DOC_V2, 2)
    assert replayed[2][kept.end:] == ""  # The old editor instructions are gone.
    assert "not necessarily the latest saved file" in HISTORY_SNAPSHOT_HEADER
    assert "not the current editor" in HISTORY_SNAPSHOT_HEADER
    messages = [HumanMessage(content=text) for text in replayed] + [HumanMessage(content="now")]
    measure = measure_document_context(messages)
    assert measure["document_chars_history"] == len(DOC_V2) and measure["document_full_copies"] == 1


def test_current_turn_with_only_frozen_references_counts_as_no_snapshot():
    current = _turn("比較引用", None, [{"referenceId": "r", "kind": "document", "text": "第二段 beta",
                                       "document": {"snapshot": _snapshot(DOC_V1, 1, 0, 3), "startLine": 1, "endLine": 1}}])
    assert not has_current_snapshot(current)
    assert has_current_snapshot(_turn("x", _snapshot(DOC_V1, 1)))
    assert not has_current_snapshot(None) and not has_current_snapshot("plain")
    replayed = replay_history_inputs([(1, _turn("舊", _snapshot(DOC_V1, 1)))], current_has_snapshot=has_current_snapshot(current))
    [kept] = _blocks(replayed[0])
    assert kept.header == HISTORY_SNAPSHOT_HEADER and kept.value["sourceText"] == DOC_V1


def test_history_frozen_references_keep_quotes_and_lines_but_no_full_text():
    start, end = _range_of(DOC_V1, "第三段 gamma")
    same = {key: value for key, value in _snapshot(DOC_V1, 1, start, end).items() if key != "sourceText"}
    references = [
        {"referenceId": "old", "kind": "document", "text": "第三段 gamma",
         "document": {"snapshot": _snapshot(DOC_V2, 0, start, end), "startLine": 4, "endLine": 4}},
        {"referenceId": "same", "kind": "document", "text": "第三段 gamma",
         "document": {"snapshot": {**same, "sourceTextSameAs": "current editor document snapshot"}, "startLine": 4, "endLine": 4}},
        {"referenceId": "chat", "kind": "chat", "text": "assistant words", "chat": {"turnId": "t"}},
    ]
    text = _turn("分析三個引用", _snapshot(DOC_V1, 1), references)

    [replayed] = replay_history_inputs([(7, text)], current_has_snapshot=True)

    assert json.dumps(DOC_V1, ensure_ascii=False) not in replayed
    assert json.dumps(DOC_V2, ensure_ascii=False) not in replayed
    assert "sourceTextSameAs" not in replayed and "Use reference_id in document_edit" not in replayed
    placeholder, history_refs = _blocks(replayed)
    assert placeholder.header == OMITTED_SNAPSHOT_HEADER and history_refs.header == HISTORY_REFERENCES_HEADER
    by_id = {item["referenceId"]: item for item in history_refs.value}
    assert by_id["old"]["text"] == "第三段 gamma"
    assert by_id["old"]["document"]["startLine"] == 4
    assert by_id["old"]["document"]["snapshot"]["rangeStartUtf16"] == start
    assert "sourceText" not in by_id["old"]["document"]["snapshot"]
    assert by_id["chat"] == references[2]
    assert measure_document_context([HumanMessage(content=replayed), HumanMessage(content="now")])["document_full_copies"] == 0


def test_grill_read_only_instructions_are_recognized_like_the_edit_variant():
    edit = _turn("檢查", _snapshot(DOC_V1, 1), instructions=EDIT_INSTRUCTIONS)
    grill = _turn("檢查", _snapshot(DOC_V1, 1), instructions=GRILL_INSTRUCTIONS)
    for keep in (True, False):
        [a] = replay_history_inputs([(1, edit)], current_has_snapshot=not keep)
        [b] = replay_history_inputs([(1, grill)], current_has_snapshot=not keep)
        assert a == b
        assert "document_edit" not in a


def test_unrecognized_or_broken_inputs_are_replayed_unchanged():
    broken = f"使用者文字\n\n{SNAPSHOT_HEADER}\n{{\"sourceText\": \"unterminated"
    wrong_shape = f"文字\n\n{SNAPSHOT_HEADER}\n[1, 2, 3]\nUse this exact editor snapshot."
    plain = "沒有任何文件"
    turns = [(1, broken), (2, wrong_shape), (3, plain)]
    assert replay_history_inputs(turns, current_has_snapshot=False) == [broken, wrong_shape, plain]


def test_user_text_is_preserved_verbatim():
    user = "請依[Frozen references]以外的內容\n改寫，第 2 段保留 😀"
    [replayed] = replay_history_inputs([(1, _turn(user, _snapshot(DOC_V1, 1)))], current_has_snapshot=True)
    assert replayed.startswith(user + "\n\n" + OMITTED_SNAPSHOT_HEADER)
