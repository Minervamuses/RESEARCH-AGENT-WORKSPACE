"""Tests for ingest-time do-not-index protections."""

import sys

import pytest

from rag import collect as collect_mod
from rag.cli import ingest as ingest_mod


def test_collect_folders_skips_plan_logs(tmp_path):
    plan = tmp_path / "plan_logs" / "foo.md"
    note = tmp_path / "notes" / "bar.md"
    plan.parent.mkdir()
    note.parent.mkdir()
    plan.write_text("secret plan turn", encoding="utf-8")
    note.write_text("regular note", encoding="utf-8")

    folders = collect_mod.collect_folders(tmp_path)
    files = {path.relative_to(tmp_path).as_posix() for paths in folders.values() for path in paths}

    assert files == {"notes/bar.md"}


def test_collect_folders_skips_do_not_index_sentinel(tmp_path):
    leaked = tmp_path / "notes" / "leaked.md"
    regular = tmp_path / "notes" / "regular.md"
    leaked.parent.mkdir()
    leaked.write_text("---\ndo_not_index: true\n---\nprivate", encoding="utf-8")
    regular.write_text("public", encoding="utf-8")

    folders = collect_mod.collect_folders(tmp_path)
    files = {path.relative_to(tmp_path).as_posix() for paths in folders.values() for path in paths}

    assert files == {"notes/regular.md"}


def test_ingest_single_refuses_skip_dir_lineage(tmp_path):
    plan = tmp_path / "plan_logs" / "foo.md"
    plan.parent.mkdir()
    plan.write_text("secret plan turn", encoding="utf-8")

    with pytest.raises(ValueError, match="lies under skip dir"):
        ingest_mod.ingest_single(str(plan))


def test_ingest_single_refuses_do_not_index_sentinel(tmp_path):
    leaked = tmp_path / "notes" / "leaked.md"
    leaked.parent.mkdir()
    leaked.write_text("---\ndo_not_index: true\n---\nprivate", encoding="utf-8")

    with pytest.raises(ValueError, match="do_not_index sentinel"):
        ingest_mod.ingest_single(str(leaked))


def test_main_reports_value_error_without_traceback(monkeypatch, capsys):
    def fail_ingest_single(*args, **kwargs):
        raise ValueError("refusing to ingest test file")

    monkeypatch.setattr(ingest_mod, "ingest_single", fail_ingest_single)
    monkeypatch.setattr(sys, "argv", ["ingest", "blocked.md"])

    with pytest.raises(SystemExit) as exc_info:
        ingest_mod.main()

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "refusing to ingest test file" in stderr
    assert "Traceback" not in stderr
