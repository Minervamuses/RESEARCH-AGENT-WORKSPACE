"""Tests for ingest-time path guards."""

import sys

import pytest

from rag import collect as collect_mod
from rag.cli import ingest as ingest_mod


def test_collect_folders_skips_node_modules(tmp_path):
    dependency = tmp_path / "node_modules" / "foo.md"
    note = tmp_path / "notes" / "bar.md"
    dependency.parent.mkdir()
    note.parent.mkdir()
    dependency.write_text("vendored dependency notes", encoding="utf-8")
    note.write_text("regular note", encoding="utf-8")

    folders = collect_mod.collect_folders(tmp_path)
    files = {path.relative_to(tmp_path).as_posix() for paths in folders.values() for path in paths}

    assert files == {"notes/bar.md"}


def test_ingest_single_refuses_skip_dir_lineage(tmp_path):
    dependency = tmp_path / "node_modules" / "foo.md"
    dependency.parent.mkdir()
    dependency.write_text("vendored dependency notes", encoding="utf-8")

    with pytest.raises(ValueError, match="lies under skip dir"):
        ingest_mod.ingest_single(str(dependency))


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
