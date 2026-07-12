"""Atomic bundle storage: precedence, atomicity, idempotency, fail-closed."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from skills.citation import storage
from skills.citation.storage import (
    BIB_FILENAME,
    MAX_BUNDLE_DIR_BYTES,
    SIDECAR_FILENAME,
    StorageError,
    bundle_dir_name,
    cleanup_stale_staging,
    resolve_output_dir,
    validate_bundle,
    write_bundle,
)

DOI = "10.1234/example"
BIB = "@article{k,\n  title = {T},\n  year = {2020},\n}\n"
SIDECAR = {"run_id": "r1", "source_ref": {"source_id": "s1"}}


def test_output_dir_precedence_config_env_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_workspace_root", lambda: tmp_path)
    config = SimpleNamespace(citation_output_dir="/custom/place")
    assert resolve_output_dir(config, env={}) == Path("/custom/place")
    assert resolve_output_dir(None, env={"CITATION_OUTPUT_DIR": "/from/env"}) == Path(
        "/from/env"
    )
    # Default: version-controlled workspace cite/ directory.
    default = resolve_output_dir(None, env={})
    assert default == tmp_path / "cite"


def test_output_dir_default_honors_xdg_data_home(monkeypatch):
    monkeypatch.setattr(storage.sys, "platform", "linux")
    monkeypatch.setattr(storage, "_workspace_root", lambda: None)
    default = resolve_output_dir(None, env={"XDG_DATA_HOME": "/xdg/data"})
    assert default == Path("/xdg/data/research-agent/citation")


def test_workspace_root_finds_nested_cwd(tmp_path):
    root = tmp_path / "workspace"
    nested = root / "app" / "skills"
    (root / ".git").mkdir(parents=True)
    nested.mkdir(parents=True)

    assert storage._workspace_root(
        cwd=nested,
        package_start=tmp_path / "elsewhere",
    ) == root


def test_workspace_root_accepts_worktree_git_file(tmp_path):
    root = tmp_path / "worktree"
    nested = root / "app"
    nested.mkdir(parents=True)
    (root / ".git").write_text("gitdir: /tmp/main/.git/worktrees/x\n")

    assert storage._workspace_root(cwd=nested) == root


def test_workspace_root_prefers_cwd_when_package_is_separate(tmp_path):
    workspace = tmp_path / "user-workspace"
    package = tmp_path / "installed-source"
    (workspace / ".git").mkdir(parents=True)
    (workspace / "nested").mkdir()
    (package / ".git").mkdir(parents=True)
    (package / "app").mkdir()

    assert storage._workspace_root(
        cwd=workspace / "nested",
        package_start=package / "app",
    ) == workspace


def test_workspace_root_returns_none_when_both_walks_lack_git(tmp_path):
    cwd = tmp_path / "cwd"
    package = tmp_path / "package"
    cwd.mkdir()
    package.mkdir()

    assert storage._workspace_root(cwd=cwd, package_start=package) is None


def test_bundle_dir_name_caps_utf8_bytes_and_keeps_hash():
    long_chinese = "極長的中文標題" * 40
    name = bundle_dir_name(long_chinese, DOI)
    assert len(name.encode("utf-8")) <= MAX_BUNDLE_DIR_BYTES
    stem, _, digest = name.rpartition("--")
    assert len(digest) == 12
    assert stem  # never empty
    # Deterministic for the same inputs.
    assert name == bundle_dir_name(long_chinese, DOI)


def test_write_bundle_creates_both_files_atomically(tmp_path):
    result = write_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=dict(SIDECAR),
    )
    assert result.reused is False
    assert result.bib_path.read_text(encoding="utf-8") == BIB
    sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == 1
    assert sidecar["doi"] == DOI
    assert sidecar["artifact_hashes"][BIB_FILENAME] == result.bib_sha256
    assert sidecar["run_id"] == "r1"
    # No staging leftovers.
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".staging-")]
    # 0600 files.
    assert oct(result.bib_path.stat().st_mode & 0o777) == "0o600"


def test_same_doi_reconfirm_reuses_validated_bundle(tmp_path):
    first = write_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=dict(SIDECAR),
    )
    second = write_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=dict(SIDECAR),
    )
    assert second.reused is True
    assert second.bundle_dir == first.bundle_dir


def test_corrupt_existing_bundle_fails_closed_never_overwrites(tmp_path):
    first = write_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=dict(SIDECAR),
    )
    # Tamper with the artifact: hash no longer matches the sidecar.
    first.bib_path.write_text("@tampered{}", encoding="utf-8")
    with pytest.raises(StorageError) as exc:
        write_bundle(
            tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
            sidecar=dict(SIDECAR),
        )
    assert exc.value.code == "bundle_conflict"
    assert first.bib_path.read_text(encoding="utf-8") == "@tampered{}"


def test_unreadable_sidecar_fails_closed(tmp_path):
    first = write_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=dict(SIDECAR),
    )
    first.sidecar_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StorageError):
        write_bundle(
            tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
            sidecar=dict(SIDECAR),
        )


def test_schema_mismatch_fails_closed(tmp_path):
    first = write_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=dict(SIDECAR),
    )
    sidecar = json.loads(first.sidecar_path.read_text(encoding="utf-8"))
    sidecar["schema_version"] = 99
    first.sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    with pytest.raises(StorageError) as exc:
        write_bundle(
            tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
            sidecar=dict(SIDECAR),
        )
    assert exc.value.code == "bundle_conflict"


def test_different_doi_name_collision_extends_hash(tmp_path, monkeypatch):
    # Force every DOI to the same 12-hex prefix so the names collide.
    real_doi_hash = storage.doi_hash

    def fake_hash(doi, *, length=12):
        if length == 12:
            return "deadbeef0000"
        return real_doi_hash(doi, length=length)

    monkeypatch.setattr(storage, "doi_hash", fake_hash)
    first = write_bundle(
        tmp_path, canonical_doi="10.1111/one", title="Same Title",
        bibtex_text=BIB, sidecar=dict(SIDECAR),
    )
    second = write_bundle(
        tmp_path, canonical_doi="10.2222/two", title="Same Title",
        bibtex_text=BIB, sidecar=dict(SIDECAR),
    )
    assert first.bundle_dir != second.bundle_dir
    stem, _, digest = second.bundle_dir.name.rpartition("--")
    assert len(digest) == 20  # extended, not overwritten
    # Both visible bundles carry both artifacts with consistent hashes.
    for result in (first, second):
        validated = validate_bundle(result.bundle_dir, json.loads(
            result.sidecar_path.read_text(encoding="utf-8")
        )["doi"])
        assert validated.reused is True


def test_stale_staging_cleanup_only_after_24h(tmp_path):
    fresh = tmp_path / ".staging-fresh"
    stale = tmp_path / ".staging-stale"
    fresh.mkdir()
    stale.mkdir()
    (stale / "reference.bib").write_text("x", encoding="utf-8")
    old = 1_000_000.0
    os.utime(stale, (old, old))
    os.utime(fresh, (old + 100_000, old + 100_000))

    removed = cleanup_stale_staging(
        tmp_path, now=old + 24 * 3600 + 1
    )
    assert stale in removed
    assert not stale.exists()
    assert fresh.exists()


def test_write_failure_surfaces_as_storage_error(tmp_path):
    blocked = tmp_path / "no-write"
    blocked.mkdir()
    blocked.chmod(0o500)
    try:
        with pytest.raises(StorageError) as exc:
            write_bundle(
                blocked, canonical_doi=DOI, title="T", bibtex_text=BIB,
                sidecar=dict(SIDECAR),
            )
        assert exc.value.code == "write_failed"
    finally:
        blocked.chmod(0o700)


def test_visible_bundle_always_has_both_artifacts(tmp_path):
    result = write_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=dict(SIDECAR),
    )
    entries = sorted(p.name for p in result.bundle_dir.iterdir())
    assert entries == [SIDECAR_FILENAME, BIB_FILENAME] or entries == sorted(
        [BIB_FILENAME, SIDECAR_FILENAME]
    )
