"""Atomic bundle storage: precedence, atomicity, idempotency, fail-closed."""

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from skills.citation import storage
from skills.citation.storage import (
    BIB_FILENAME,
    MAX_BUNDLE_DIR_BYTES,
    SIDECAR_FILENAME,
    StorageError,
    cleanup_stale_staging,
    identity_bundle_dir_name,
    resolve_output_dir,
    write_identity_bundle,
    validate_identity_bundle,
)
from skills.citation.types import CanonicalIdentity, SourceRef, is_citable_source

DOI = "10.1234/example"
BIB = "@article{k,\n  title = {T},\n  year = {2020},\n}\n"
def make_sidecar(doi=DOI):
    return {
        "run_id": "r1",
        "source_ref": {
            "source_id": f"src-{storage.doi_hash(doi)}",
            "doi": doi,
            "verification_level": "doi_identity_verified",
        },
    }


def _write_doi_bundle(
    output_dir,
    *,
    canonical_doi,
    title,
    bibtex_text,
    sidecar,
):
    return write_identity_bundle(
        output_dir,
        identity=CanonicalIdentity("doi", canonical_doi),
        title=title,
        bibtex_text=bibtex_text,
        sidecar=sidecar,
    )


def test_output_dir_precedence_config_env_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "_workspace_root", lambda: tmp_path)
    config = SimpleNamespace(citation_output_dir="/custom/place")
    assert resolve_output_dir(config, env={}) == Path("/custom/place")
    assert resolve_output_dir(None, env={"CITATION_OUTPUT_DIR": "/from/env"}) == Path(
        "/from/env"
    )
    # Default: workspace-local ignored cite/ directory.
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
    identity = CanonicalIdentity("doi", DOI)
    name = identity_bundle_dir_name(long_chinese, identity)
    assert len(name.encode("utf-8")) <= MAX_BUNDLE_DIR_BYTES
    stem, _, digest = name.rpartition("--")
    assert len(digest) == 12
    assert stem  # never empty
    # Deterministic for the same inputs.
    assert name == identity_bundle_dir_name(long_chinese, identity)


def test_write_identity_bundle_creates_both_files_atomically(tmp_path):
    result = _write_doi_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    assert result.reused is False
    assert result.bib_path.read_text(encoding="utf-8") == BIB
    sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["schema_version"] == 2
    assert sidecar["doi"] == DOI
    assert sidecar["identity"] == {"kind": "doi", "value": DOI}
    assert sidecar["artifact_hashes"][BIB_FILENAME] == result.bib_sha256
    assert sidecar["run_id"] == "r1"
    # No staging leftovers.
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".staging-")]
    # 0600 files.
    assert oct(result.bib_path.stat().st_mode & 0o777) == "0o600"


def test_same_doi_save_reuses_validated_bundle(tmp_path):
    first = _write_doi_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    second = _write_doi_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    assert second.reused is True
    assert second.bundle_dir == first.bundle_dir


def test_corrupt_existing_bundle_fails_closed_never_overwrites(tmp_path):
    first = _write_doi_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    # Tamper with the artifact: hash no longer matches the sidecar.
    first.bib_path.write_text("@tampered{}", encoding="utf-8")
    with pytest.raises(StorageError) as exc:
        _write_doi_bundle(
            tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
            sidecar=make_sidecar(),
        )
    assert exc.value.code == "bundle_conflict"
    assert first.bib_path.read_text(encoding="utf-8") == "@tampered{}"


def test_unreadable_sidecar_fails_closed(tmp_path):
    first = _write_doi_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    first.sidecar_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(StorageError):
        _write_doi_bundle(
            tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
            sidecar=make_sidecar(),
        )


def test_schema_mismatch_fails_closed(tmp_path):
    first = _write_doi_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    sidecar = json.loads(first.sidecar_path.read_text(encoding="utf-8"))
    sidecar["schema_version"] = 99
    first.sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    with pytest.raises(StorageError) as exc:
        _write_doi_bundle(
            tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
            sidecar=make_sidecar(),
        )
    assert exc.value.code == "bundle_conflict"


def test_different_doi_source_id_collision_fails_closed(tmp_path, monkeypatch):
    # Force every DOI to the same 12-hex prefix so the names collide.
    real_doi_hash = storage.doi_hash

    def fake_hash(doi, *, length=12):
        if length == 12:
            return "deadbeef0000"
        return real_doi_hash(doi, length=length)

    monkeypatch.setattr(storage, "doi_hash", fake_hash)
    first = _write_doi_bundle(
        tmp_path, canonical_doi="10.1111/one", title="Same Title",
        bibtex_text=BIB, sidecar=make_sidecar("10.1111/one"),
    )
    with pytest.raises(StorageError) as exc:
        _write_doi_bundle(
            tmp_path, canonical_doi="10.2222/two", title="Same Title",
            bibtex_text=BIB, sidecar=make_sidecar("10.2222/two"),
        )
    assert exc.value.code == "source_id_collision"
    assert [p for p in tmp_path.iterdir() if p.is_dir() and not p.name.startswith(".")] == [first.bundle_dir]


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
            _write_doi_bundle(
                blocked, canonical_doi=DOI, title="T", bibtex_text=BIB,
                sidecar=make_sidecar(),
            )
        assert exc.value.code == "write_failed"
    finally:
        blocked.chmod(0o700)


def test_visible_bundle_always_has_both_artifacts(tmp_path):
    result = _write_doi_bundle(
        tmp_path, canonical_doi=DOI, title="A Paper", bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    entries = sorted(p.name for p in result.bundle_dir.iterdir())
    assert entries == [SIDECAR_FILENAME, BIB_FILENAME] or entries == sorted(
        [BIB_FILENAME, SIDECAR_FILENAME]
    )


def test_frozen_v1_fixture_validates_and_is_reused_without_rewrite(tmp_path):
    fixture = Path(__file__).parent / "fixtures/legacy_v1_bundle/Legacy_Work--127cdd1bdbc8"
    target = tmp_path / fixture.name
    shutil.copytree(fixture, target)
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in target.iterdir()}
    result = _write_doi_bundle(
        tmp_path,
        canonical_doi="10.1234/legacy",
        title="A changed provider title",
        bibtex_text="ignored on reuse",
        sidecar=make_sidecar("10.1234/legacy"),
    )
    assert result.reused and result.bundle_dir == target
    after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in target.iterdir()}
    assert after == before


def test_v2_doi_keeps_legacy_source_id_and_reuses_across_title_drift(tmp_path):
    identity = CanonicalIdentity("doi", DOI)
    payload = {"source_ref": {"source_id": f"src-{storage.doi_hash(DOI)}"}, "creation_evidence": {"batch_id": "b1"}}
    first = write_identity_bundle(tmp_path, identity=identity, title="First title", bibtex_text=BIB, sidecar=payload)
    before = first.sidecar_path.read_bytes(), first.sidecar_path.stat().st_mtime_ns
    second = write_identity_bundle(tmp_path, identity=identity, title="Changed title", bibtex_text="different", sidecar={"creation_evidence": {"batch_id": "b2"}})
    assert second.reused and second.bundle_dir == first.bundle_dir
    assert (second.sidecar_path.read_bytes(), second.sidecar_path.stat().st_mtime_ns) == before
    data = json.loads(first.sidecar_path.read_text())
    assert data["schema_version"] == 2
    assert data["identity"] == {"kind": "doi", "value": DOI}


def test_v2_reader_accepts_only_null_legacy_source_ref_bundle_path(tmp_path):
    identity = CanonicalIdentity("doi", DOI)
    result = write_identity_bundle(
        tmp_path,
        identity=identity,
        title="A Paper",
        bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    sidecar = json.loads(result.sidecar_path.read_text())
    sidecar["source_ref"]["bundle_path"] = None
    result.sidecar_path.write_text(json.dumps(sidecar))

    assert validate_identity_bundle(result.bundle_dir, identity).reused

    sidecar["source_ref"]["bundle_path"] = "/machine-specific/cite/a"
    result.sidecar_path.write_text(json.dumps(sidecar))
    with pytest.raises(StorageError) as exc:
        validate_identity_bundle(result.bundle_dir, identity)
    assert exc.value.code == "bundle_conflict"


def test_writer_strips_null_legacy_bundle_path_without_mutating_caller(tmp_path):
    identity = CanonicalIdentity("doi", DOI)
    sidecar = make_sidecar()
    sidecar["source_ref"]["bundle_path"] = None

    result = write_identity_bundle(
        tmp_path,
        identity=identity,
        title="A Paper",
        bibtex_text=BIB,
        sidecar=sidecar,
    )

    persisted = json.loads(result.sidecar_path.read_text())
    assert "bundle_path" not in persisted["source_ref"]
    assert sidecar["source_ref"]["bundle_path"] is None


def test_writer_rejects_non_null_source_ref_bundle_path(tmp_path):
    sidecar = make_sidecar()
    sidecar["source_ref"]["bundle_path"] = "/machine-specific/cite/a"

    with pytest.raises(StorageError) as exc:
        write_identity_bundle(
            tmp_path,
            identity=CanonicalIdentity("doi", DOI),
            title="A Paper",
            bibtex_text=BIB,
            sidecar=sidecar,
        )
    assert exc.value.code == "bundle_conflict"


def test_v2_bundle_path_cannot_bypass_validation_without_source_id(tmp_path):
    identity = CanonicalIdentity("doi", DOI)
    result = write_identity_bundle(
        tmp_path,
        identity=identity,
        title="A Paper",
        bibtex_text=BIB,
        sidecar=make_sidecar(),
    )
    sidecar = json.loads(result.sidecar_path.read_text())
    sidecar["source_ref"].pop("source_id")
    sidecar["source_ref"]["bundle_path"] = "/machine-specific/cite/a"
    result.sidecar_path.write_text(json.dumps(sidecar))

    with pytest.raises(StorageError) as exc:
        validate_identity_bundle(result.bundle_dir, identity)
    assert exc.value.code == "bundle_conflict"


def test_v1_reader_rejects_non_null_legacy_source_ref_bundle_path(tmp_path):
    fixture = Path(__file__).parent / "fixtures/legacy_v1_bundle/Legacy_Work--127cdd1bdbc8"
    target = tmp_path / fixture.name
    shutil.copytree(fixture, target)
    sidecar_path = target / SIDECAR_FILENAME
    sidecar = json.loads(sidecar_path.read_text())
    sidecar["source_ref"]["bundle_path"] = "/machine-specific/cite/a"
    sidecar_path.write_text(json.dumps(sidecar))

    with pytest.raises(StorageError) as exc:
        validate_identity_bundle(
            target, CanonicalIdentity("doi", "10.1234/legacy")
        )
    assert exc.value.code == "bundle_conflict"


def test_v2_authoritative_non_doi_identity_is_stable(tmp_path):
    identity = CanonicalIdentity("venue", "neurips:2017:attention-is-all-you-need")
    result = write_identity_bundle(tmp_path, identity=identity, title="Attention Is All You Need", bibtex_text=BIB, sidecar={"source_ref": {"source_id": storage.source_id_for(identity)}})
    assert validate_identity_bundle(result.bundle_dir, identity).reused
    data = json.loads(result.sidecar_path.read_text())
    assert data["doi"] is None
    assert str(tmp_path) not in result.sidecar_path.read_text()


def test_verification_level_identity_shapes_fail_closed():
    legacy = SourceRef("src-x", "10.1234/x", "X")
    assert is_citable_source(legacy)
    doi_v2 = SourceRef("src-x", "10.1234/x", "X", schema_version=2, verification_level="doi_identity_verified", canonical_identity=CanonicalIdentity("doi", "10.1234/x"))
    assert is_citable_source(doi_v2)
    authority = SourceRef("src-y", None, "Y", schema_version=2, verification_level="authority_metadata_verified", canonical_identity=CanonicalIdentity("venue", "adapter:y"))
    assert is_citable_source(authority)
    contradictory = SourceRef("src-z", "10.1234/z", "Z", schema_version=2, verification_level="doi_identity_verified", canonical_identity=CanonicalIdentity("doi", "10.1234/other"))
    assert not is_citable_source(contradictory)
