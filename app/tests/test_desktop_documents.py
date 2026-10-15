"""Representative editor snapshots and safe local document operations."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from agent.desktop.documents import (
    DocumentError,
    DocumentWorkspace,
    resolve_line_range,
    selected_text,
    utf16_length,
)


def workspace(tmp_path: Path, source: str = "原稿\n"):
    path = tmp_path / "draft.md"
    path.write_bytes(source.encode("utf-8"))
    documents = DocumentWorkspace()
    documents.select_root(str(tmp_path))
    return documents, path, documents.open(str(path))


def snapshot_from_result(result):
    return {key: result[key] for key in ("rootPath", "path", "editorRevision", "sourceText", "diskFingerprint")}


def test_open_preserves_raw_bytes_and_requires_selected_root(tmp_path):
    path = tmp_path / "draft.tex"
    raw = "中文😀\t\r\n\r\nend\r\n".encode("utf-8")
    path.write_bytes(raw)
    documents = DocumentWorkspace()
    with pytest.raises(DocumentError, match="select"):
        documents.open(str(path))
    assert documents.select_root(str(tmp_path)) == {"rootPath": str(tmp_path)}
    snapshot = documents.open(str(path))
    assert snapshot["sourceText"].encode("utf-8") == raw
    assert snapshot["diskFingerprint"] == hashlib.sha256(raw).hexdigest()


def test_root_rejects_outside_symlink_and_non_sources(tmp_path):
    documents, path, snapshot = workspace(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("outside")
    try:
        (tmp_path / "escape.md").symlink_to(outside)
        (tmp_path / "binary.pdf").write_text("not a supported source")
        for value in (str(outside), str(tmp_path / "escape.md"), str(tmp_path / "binary.pdf")):
            with pytest.raises(DocumentError):
                documents.open(value)
        invalid = {**snapshot, "rootPath": str(tmp_path.parent)}
        with pytest.raises(DocumentError, match="another workspace"):
            documents.save(invalid)
    finally:
        outside.unlink()
    assert path.read_text() == "原稿\n"


def test_exact_second_paragraph_preserves_other_text_and_crlf(tmp_path):
    source = "標題😀\r\n\r\n重複\t段落\r\n\r\n重複\t段落\r\n尾聲\r\n"
    documents, path, base = workspace(tmp_path, source)
    start = source.rindex("重複")
    end = start + len("重複\t段落")
    base.update(rangeStartUtf16=utf16_length(source[:start]), rangeEndUtf16=utf16_length(source[:end]))
    candidate = documents.prepare(base, "修改😀\n第二行", turn_id="turn", call_id="call")
    assert selected_text(base) == "重複\t段落"
    result = documents.apply(candidate, base)
    expected = source[:start] + "修改😀\r\n第二行" + source[end:]
    assert result["status"] == "saved"
    assert path.read_bytes() == expected.encode("utf-8")
    assert result["sourceText"] == expected
    assert result["editorRevision"] == 1
    assert documents.open(str(path))["sourceText"] == expected


@pytest.mark.parametrize("start,end", [(2, 3), (-1, 1), (0, 99), (3, 1), (True, 1)])
def test_invalid_utf16_range_never_writes(tmp_path, start, end):
    documents, path, base = workspace(tmp_path, "中😀\t\n")
    base.update(rangeStartUtf16=start, rangeEndUtf16=end)
    with pytest.raises(DocumentError):
        documents.prepare(base, "oops", turn_id="turn", call_id="call")
    assert path.read_bytes() == "中😀\t\n".encode()


@pytest.mark.parametrize("source,replacement,expected", [("", "", ""), ("", "新😀", "新😀"), ("old\n", "", "")])
def test_empty_source_and_replacement_are_valid(tmp_path, source, replacement, expected):
    documents, path, base = workspace(tmp_path, source)
    candidate = documents.prepare(base, replacement, turn_id="turn", call_id="call")
    assert documents.apply(candidate, base)["status"] == "saved"
    assert path.read_bytes() == expected.encode()


def test_source_lines_ignore_visual_wrapping_and_preserve_unselected_lines(tmp_path):
    source = "".join(f"第{line}行😀\t" + "長" * 120 + "\r\n" for line in range(1, 51))
    documents, path, base = workspace(tmp_path, source)
    resolved = documents.resolve_range(base, "把第 40–45 行改成清單")
    assert selected_text(resolved).startswith("第40行")
    assert selected_text(resolved).endswith("\r\n")
    assert selected_text(resolved).count("\r\n") == 6
    assert resolve_line_range(source, 40, 45) == (resolved["rangeStartUtf16"], resolved["rangeEndUtf16"])
    assert documents.resolve_range(base, "change line40–45")["rangeEndUtf16"] == resolved["rangeEndUtf16"]
    assert documents.resolve_range(base, "Analyze line28, explain the claim")["rangeStartUtf16"] == resolve_line_range(source, 28, 28)[0]
    candidate = documents.prepare(resolved, "- 第一項\n- 第二項\n", turn_id="turn", call_id="call")
    result = documents.apply(candidate, base)
    assert result["status"] == "saved"
    original_lines = source.splitlines(keepends=True)
    assert path.read_bytes() == ("".join(original_lines[:39]) + "- 第一項\r\n- 第二項\r\n" + "".join(original_lines[45:])).encode()


@pytest.mark.parametrize("prompt", ["第 99 行", "第 0 行", "第 2–1 行", "line1 and line2", "第2至未知行", "line1–unknown", "line1.5", "lines1–2,3", "第1行到2行"])
def test_ambiguous_or_outside_lines_do_not_mutate(tmp_path, prompt):
    documents, path, base = workspace(tmp_path, "one\ntwo\n")
    with pytest.raises(DocumentError):
        documents.resolve_range(base, prompt)
    assert path.read_bytes() == b"one\ntwo\n"


def test_selection_survives_focus_and_unsaved_source_is_the_baseline(tmp_path):
    documents, path, base = workspace(tmp_path, "saved\n")
    current = {**base, "sourceText": "未儲存😀\n", "editorRevision": 7, "rangeStartUtf16": 0, "rangeEndUtf16": 3}
    resolved = documents.resolve_range(current, "analysis line999")
    assert resolved == current
    assert path.read_bytes() == b"saved\n"
    candidate = documents.prepare(resolved, "改寫", turn_id="turn", call_id="call")
    result = documents.apply(candidate, current)
    assert result["status"] == "saved"
    assert path.read_bytes() == "改寫😀\n".encode()
    assert result["editorRevision"] == 8


@pytest.mark.parametrize("changed", ["editor", "disk"])
def test_conflict_keeps_both_versions_and_requires_fresh_acceptance(tmp_path, changed):
    documents, path, base = workspace(tmp_path, "base\n")
    candidate = documents.prepare(base, "candidate\n", turn_id="turn", call_id="call")
    current = dict(base)
    if changed == "editor":
        current.update(sourceText="current editor\n", editorRevision=1)
    else:
        path.write_bytes(b"external disk\n")
    conflict = documents.apply(candidate, current)
    assert conflict["status"] == "conflict"
    assert conflict["candidateText"] == "candidate\n"
    assert conflict["currentDiskText"] == path.read_bytes().decode()
    with pytest.raises(DocumentError, match="requires the versions"):
        documents.apply(candidate, current, resolution="candidate")
    expected = conflict["expectedSnapshot"]
    path.write_bytes(b"changed again\n")
    repeated = documents.apply(candidate, current, resolution="candidate", expected_snapshot=expected)
    assert repeated["status"] == "conflict"
    assert path.read_bytes() == b"changed again\n"
    accepted = documents.apply(candidate, current, resolution="candidate", expected_snapshot=repeated["expectedSnapshot"])
    assert accepted["status"] == "saved"
    assert path.read_bytes() == b"candidate\n"


@pytest.mark.parametrize("resolution", ["current", "cancel"])
def test_keep_or_cancel_does_not_write(tmp_path, resolution):
    documents, path, base = workspace(tmp_path)
    candidate = documents.prepare(base, "candidate", turn_id="turn", call_id="call")
    assert documents.apply(candidate, base, resolution=resolution)["status"] == "cancelled"
    assert path.read_text() == "原稿\n"


def test_write_failure_preserves_candidate_and_editor(tmp_path, monkeypatch):
    documents, path, base = workspace(tmp_path)
    current = {**base, "sourceText": "unsaved", "editorRevision": 1}
    candidate = documents.prepare(current, "candidate", turn_id="turn", call_id="call")
    def fail(*_args):
        raise PermissionError("read only")
    monkeypatch.setattr(documents, "_write", fail)
    result = documents.apply(candidate, current)
    assert result["status"] == "failed"
    assert result["candidateText"] == "candidate"
    assert current["sourceText"] == "unsaved"
    assert path.read_text() == "原稿\n"
    assert "read only" in result["issue"]


def test_candidate_is_bound_to_operation_and_duplicate_never_reapplies(tmp_path, monkeypatch):
    documents, path, base = workspace(tmp_path)
    candidate = documents.prepare(base, "candidate", turn_id="turn", call_id="call")
    tampered = {**candidate, "candidateText": "unapproved", "replacementText": "unapproved"}
    result = documents.apply(tampered, base)
    assert result["sourceText"] == "candidate"
    with pytest.raises(DocumentError, match="another candidate"):
        documents.prepare(base, "different", turn_id="turn", call_id="call")
    def fail(*_args):
        raise AssertionError("successful operation must not be replayed")
    monkeypatch.setattr(documents, "_write", fail)
    assert documents.apply(candidate, snapshot_from_result(result)) == result
    assert documents.apply(candidate, base) == result
    newer_editor = {**snapshot_from_result(result), "editorRevision": 2, "sourceText": "later editor"}
    assert documents.apply(candidate, newer_editor)["status"] == "conflict"
    path.write_bytes(b"later change")
    assert documents.apply(candidate, snapshot_from_result(result))["status"] == "conflict"
    assert path.read_bytes() == b"later change"
    restarted = DocumentWorkspace()
    restarted.select_root(str(tmp_path))
    with pytest.raises(DocumentError, match="unknown document operation"):
        restarted.apply(candidate, base)


def test_undo_is_separate_idempotent_operation_and_checks_later_versions(tmp_path):
    documents, path, base = workspace(tmp_path, "original\n")
    candidate = documents.prepare(base, "replacement\n", turn_id="turn", call_id="call")
    saved = documents.apply(candidate, base)
    current = snapshot_from_result(saved)
    changed_editor = {**current, "editorRevision": current["editorRevision"] + 1, "sourceText": "later editor"}
    assert documents.undo("call", changed_editor, request_id="undo-1")["status"] == "conflict"
    path.write_bytes(b"later disk")
    assert documents.undo("call", current, request_id="undo-1")["status"] == "conflict"
    path.write_bytes(b"replacement\n")
    undone = documents.undo("call", current, request_id="undo-1")
    assert undone["status"] == "saved"
    assert path.read_bytes() == b"original\n"
    assert documents.undo("call", snapshot_from_result(undone), request_id="undo-1") == undone


def test_manual_save_uses_last_read_disk_and_keeps_unsaved_text_on_conflict(tmp_path):
    documents, path, base = workspace(tmp_path)
    current = {**base, "sourceText": "unsaved😀\r\n", "editorRevision": 4}
    assert documents.save(current)["status"] == "saved"
    assert path.read_bytes() == "unsaved😀\r\n".encode()
    current["sourceText"] = "more changes"
    conflict = documents.save(current)
    assert conflict["status"] == "conflict"
    assert conflict["candidateText"] == "more changes"
    assert path.read_bytes() == "unsaved😀\r\n".encode()


def test_safe_revision_limit_does_not_write_an_invalid_result(tmp_path):
    documents, path, base = workspace(tmp_path)
    base["editorRevision"] = 9_007_199_254_740_991
    candidate = documents.prepare(base, "candidate", turn_id="turn", call_id="call")
    assert documents.apply(candidate, base)["status"] == "failed"
    assert path.read_text() == "原稿\n"


@pytest.mark.parametrize("partial", [False, True])
def test_shorter_replacement_returns_valid_new_selection_for_save_and_undo(tmp_path, partial):
    source = "前文😀\nlong original paragraph😀\n尾聲\n"
    documents, path, base = workspace(tmp_path, source)
    if partial:
        start = source.index("long")
        end = source.index("尾聲")
        base.update(rangeStartUtf16=utf16_length(source[:start]), rangeEndUtf16=utf16_length(source[:end]))
    candidate = documents.prepare(base, "短😀", turn_id="turn", call_id="call")
    original_end = candidate["rangeEndUtf16"]
    saved = documents.apply(candidate, base)
    current = {**snapshot_from_result(saved), **{key: saved[key] for key in ("rangeStartUtf16", "rangeEndUtf16")}}
    assert saved["rangeEndUtf16"] == saved["rangeStartUtf16"] + utf16_length("短😀")
    assert candidate["rangeEndUtf16"] == original_end
    assert documents.validate_snapshot(current) == current
    assert selected_text(current) == "短😀"
    assert documents.save(current)["status"] == "saved"
    undone = documents.undo("call", current, request_id="undo-short")
    restored = {**snapshot_from_result(undone), **{key: undone[key] for key in ("rangeStartUtf16", "rangeEndUtf16")}}
    assert documents.validate_snapshot(restored) == restored
    assert selected_text(restored) == source
    assert path.read_bytes() == source.encode()
