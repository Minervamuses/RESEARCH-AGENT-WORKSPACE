"""Atomic citation bundle storage.

Every saved citation persists as one bundle directory::

    <output>/<utf8-byte-capped-title>--<identity-hash>/reference.bib
    <output>/<utf8-byte-capped-title>--<identity-hash>/citation.json

Atomicity: both files are written into a hidden staging directory on the
same filesystem (0600, flushed and fsynced), then a single ``rename`` makes
the bundle visible — a visible bundle is never half-written. Stale staging
directories are only reclaimed after 24 hours.

Idempotency and fail-closed rules:
  * saving the same canonical identity validates the existing sidecar and
    artifact hash, then reuses the bundle without rewriting it;
  * an existing bundle whose schema, identity, or hash does not validate fails
    closed and is never overwritten;
  * a different identity colliding on the 12-hex source slot fails closed.
    Historical 20/64-hex directories remain discoverable and reusable.

The sidecar is built by CitationService and must never contain raw pages,
LLM responses, API keys, or URLs embedding keys; storage only adds the
artifact hash and schema/identity stamps it needs for validation.

Output directory precedence: ``AgentConfig.citation_output_dir`` ->
``CITATION_OUTPUT_DIR`` env -> ``<workspace>/cite`` -> the platform user-data
directory. A workspace is the nearest ancestor containing a ``.git``
directory or worktree file. The platform path remains a fail-safe for an
installed package launched outside any repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from skills.citation.types import (
    BUNDLE_SCHEMA_V2,
    PERSIST_SCHEMA_VERSION,
    SUPPORTED_PERSIST_SCHEMA_VERSIONS,
    CanonicalIdentity,
)

BIB_FILENAME = "reference.bib"
SIDECAR_FILENAME = "citation.json"
MAX_BUNDLE_DIR_BYTES = 180
HASH_LENGTHS = (12, 20, 64)
STAGING_PREFIX = ".staging-"
STALE_STAGING_SECONDS = 24 * 60 * 60
LOCKS_DIRNAME = ".locks"
DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0

_UNSAFE_CHARS = set('<>:"/\\|?*') | {chr(i) for i in range(0x20)}


class StorageError(RuntimeError):
    """Raised when a bundle cannot be written or validated.

    ``code`` is ``bundle_conflict`` (existing bundle fails validation),
    ``source_id_collision`` (the stable slot belongs to another identity), or
    ``write_failed`` (I/O failure, staging left for later inspection/cleanup).
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BundleResult:
    """A visible, validated bundle on disk."""

    bundle_dir: Path
    bib_path: Path
    sidecar_path: Path
    bib_sha256: str
    reused: bool


def resolve_output_dir(
    config: object | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """Resolve the citation output directory by fixed precedence."""
    env = env if env is not None else dict(os.environ)
    configured = getattr(config, "citation_output_dir", None) if config else None
    if configured:
        return Path(configured).expanduser()
    from_env = env.get("CITATION_OUTPUT_DIR", "").strip()
    if from_env:
        return Path(from_env).expanduser()
    workspace = _workspace_root()
    if workspace is not None:
        return workspace / "cite"
    return _platform_user_data_dir(env) / "research-agent" / "citation"


def _workspace_root(
    cwd: Path | None = None,
    package_start: Path | None = None,
) -> Path | None:
    """Find the nearest git workspace, preferring the caller's cwd.

    ``.git`` may be a directory or a file (linked worktrees). The package
    walk is only a source-tree fallback; wheel installs outside a repository
    deliberately return ``None`` so platform user data remains available.
    """

    def nearest(start: Path) -> Path | None:
        resolved = start.expanduser().resolve()
        if resolved.is_file():
            resolved = resolved.parent
        for candidate in (resolved, *resolved.parents):
            if (candidate / ".git").exists():
                return candidate
        return None

    cwd_root = nearest(Path.cwd() if cwd is None else Path(cwd))
    if cwd_root is not None:
        return cwd_root
    package_origin = (
        Path(__file__).resolve().parent
        if package_start is None
        else Path(package_start)
    )
    return nearest(package_origin)


def _platform_user_data_dir(env: dict[str, str]) -> Path:
    if sys.platform == "win32":
        base = env.get("APPDATA", "")
        return Path(base) if base else Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = env.get("XDG_DATA_HOME", "").strip()
    return Path(xdg) if xdg else Path.home() / ".local" / "share"


def doi_hash(canonical_doi: str, *, length: int = HASH_LENGTHS[0]) -> str:
    return hashlib.sha256(canonical_doi.encode("utf-8")).hexdigest()[:length]


def identity_hash(identity: CanonicalIdentity, *, length: int = HASH_LENGTHS[0]) -> str:
    if identity.kind == "doi":
        return doi_hash(identity.value, length=length)
    return hashlib.sha256(identity.key.encode("utf-8")).hexdigest()[:length]


def source_id_for(identity: CanonicalIdentity) -> str:
    return f"src-{identity_hash(identity)}"


def _sanitize_title(title: str) -> str:
    cleaned = []
    for ch in (title or "").strip():
        if ch in _UNSAFE_CHARS or ch.isspace():
            cleaned.append("_")
        else:
            cleaned.append(ch)
    text = "".join(cleaned)
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_.") or "untitled"


def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes]
    # Never split a multi-byte character.
    return truncated.decode("utf-8", errors="ignore").rstrip("_.") or "untitled"


def identity_bundle_dir_name(
    title: str, identity: CanonicalIdentity, *, hash_length: int = HASH_LENGTHS[0]
) -> str:
    suffix = f"--{identity_hash(identity, length=hash_length)}"
    budget = MAX_BUNDLE_DIR_BYTES - len(suffix.encode("utf-8"))
    return f"{_truncate_utf8(_sanitize_title(title), budget)}{suffix}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_file_0600(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return  # not supported on this platform/filesystem
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sidecar_identity(sidecar: dict) -> CanonicalIdentity:
    schema = sidecar.get("schema_version")
    if schema == PERSIST_SCHEMA_VERSION:
        return CanonicalIdentity("doi", str(sidecar.get("doi", "") or ""))
    if schema == BUNDLE_SCHEMA_V2:
        raw = sidecar.get("identity")
        if not isinstance(raw, dict) or set(raw) != {"kind", "value"}:
            raise StorageError("bundle_conflict", "v2 bundle has invalid identity")
        try:
            return CanonicalIdentity(str(raw["kind"]), str(raw["value"]))
        except (TypeError, ValueError) as exc:
            raise StorageError("bundle_conflict", "v2 bundle has invalid identity") from exc
    raise StorageError("bundle_conflict", f"unsupported bundle schema_version={schema!r}")


def _read_sidecar(bundle_dir: Path) -> dict:
    try:
        return json.loads((bundle_dir / SIDECAR_FILENAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(
            "bundle_conflict",
            f"existing bundle {bundle_dir.name!r} has an unreadable sidecar; refusing to overwrite",
        ) from exc


def validate_identity_bundle(bundle_dir: Path, identity: CanonicalIdentity) -> BundleResult:
    """Validate schema, canonical identity, directory hash and artifact hash."""
    bundle_dir = Path(bundle_dir)
    sidecar = _read_sidecar(bundle_dir)
    schema = sidecar.get("schema_version")
    if schema not in SUPPORTED_PERSIST_SCHEMA_VERSIONS:
        raise StorageError("bundle_conflict", "unsupported bundle schema")
    existing = _sidecar_identity(sidecar)
    if existing != identity:
        raise StorageError("source_id_collision", "source slot belongs to another identity")
    suffix = bundle_dir.name.rpartition("--")[2]
    if len(suffix) not in HASH_LENGTHS or suffix != identity_hash(identity, length=len(suffix)):
        raise StorageError("bundle_conflict", "bundle path hash does not match sidecar identity")
    if schema == BUNDLE_SCHEMA_V2:
        top_doi = sidecar.get("doi")
        if identity.kind == "doi" and top_doi != identity.value:
            raise StorageError("bundle_conflict", "v2 DOI and identity disagree")
        if identity.kind != "doi" and top_doi is not None:
            raise StorageError("bundle_conflict", "non-DOI v2 bundle carries a DOI")
    elif sidecar.get("doi") != identity.value:
        raise StorageError("bundle_conflict", "legacy DOI mismatch")
    source_ref = sidecar.get("source_ref")
    if isinstance(source_ref, dict):
        # Historical v1 and early v2 writers emitted a runtime-only key with
        # a null value. Accept that shape read-only, but never accept a path.
        if source_ref.get("bundle_path") is not None:
            raise StorageError(
                "bundle_conflict",
                "source_ref must not persist a bundle path",
            )
        source_id = source_ref.get("source_id")
        if source_id:
            if source_id != source_id_for(identity):
                raise StorageError("bundle_conflict", "source_ref source_id mismatch")
            if schema != BUNDLE_SCHEMA_V2:
                if source_ref.get("doi") not in {None, identity.value}:
                    raise StorageError("bundle_conflict", "legacy source_ref DOI mismatch")
                if source_ref.get("verification_level") not in {None, "identity_verified"}:
                    raise StorageError("bundle_conflict", "legacy verification level mismatch")
    bib_path = bundle_dir / BIB_FILENAME
    expected_hash = str((sidecar.get("artifact_hashes") or {}).get(BIB_FILENAME, ""))
    try:
        actual_hash = _sha256_bytes(bib_path.read_bytes())
    except OSError as exc:
        raise StorageError("bundle_conflict", f"bundle is missing {BIB_FILENAME}") from exc
    if not expected_hash or actual_hash != expected_hash:
        raise StorageError("bundle_conflict", "bundle artifact hash mismatch")
    return BundleResult(
        bundle_dir=bundle_dir,
        bib_path=bib_path,
        sidecar_path=bundle_dir / SIDECAR_FILENAME,
        bib_sha256=actual_hash,
        reused=True,
    )


@contextmanager
def _source_slot_lock(
    output_dir: Path, source_id: str, *, timeout_seconds: float
):
    if os.name != "posix":
        raise StorageError("write_failed", "cross-process storage lock unsupported")
    import fcntl

    locks = output_dir / LOCKS_DIRNAME
    try:
        locks.mkdir(mode=0o700, exist_ok=True)
    except OSError as exc:
        raise StorageError("write_failed", f"cannot create lock directory: {exc}") from exc
    lock_name = hashlib.sha256(
        f"citation-source-slot:{source_id}".encode("utf-8")
    ).hexdigest()
    path = locks / lock_name
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise StorageError("write_failed", "source-slot lock timeout")
                time.sleep(0.01)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _find_existing(output_dir: Path, identity: CanonicalIdentity) -> BundleResult | None:
    target_short = identity_hash(identity)
    for entry in output_dir.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        suffix = entry.name.rpartition("--")[2]
        if suffix not in {
            identity_hash(identity, length=length) for length in HASH_LENGTHS
        } and suffix != target_short:
            continue
        sidecar = _read_sidecar(entry)
        existing = _sidecar_identity(sidecar)
        if existing != identity:
            if len(suffix) == HASH_LENGTHS[0] and suffix == target_short:
                raise StorageError("source_id_collision", "source ID collision")
            continue
        return validate_identity_bundle(entry, identity)
    return None


def _portable_sidecar_payload(sidecar: dict) -> dict:
    """Copy caller metadata while removing the retired runtime path field."""
    payload = dict(sidecar)
    source_ref = payload.get("source_ref")
    if not isinstance(source_ref, dict):
        return payload
    source_ref = dict(source_ref)
    if source_ref.pop("bundle_path", None) is not None:
        raise StorageError(
            "bundle_conflict",
            "source_ref must not persist a bundle path",
        )
    payload["source_ref"] = source_ref
    return payload


def write_identity_bundle(
    output_dir: Path,
    *,
    identity: CanonicalIdentity,
    title: str,
    bibtex_text: str,
    sidecar: dict,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> BundleResult:
    """Write or reuse a schema-v2 canonical-identity bundle atomically."""
    payload = _portable_sidecar_payload(sidecar)
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError("write_failed", f"cannot create output dir {output_dir}: {exc}") from exc
    source_id = source_id_for(identity)
    with _source_slot_lock(output_dir, source_id, timeout_seconds=lock_timeout_seconds):
        existing = _find_existing(output_dir, identity)
        if existing is not None:
            return existing
        final_dir = output_dir / identity_bundle_dir_name(title, identity)
        if final_dir.exists():
            # Same 12-hex slot is never lengthened for a new write.
            raise StorageError("source_id_collision", "source ID collision")
        bib_bytes = bibtex_text.encode("utf-8")
        bib_sha = _sha256_bytes(bib_bytes)
        payload["schema_version"] = BUNDLE_SCHEMA_V2
        payload["doi"] = identity.value if identity.kind == "doi" else None
        payload["identity"] = identity.to_dict()
        payload["artifact_hashes"] = {BIB_FILENAME: bib_sha}
        sidecar_bytes = json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8")
        staging = output_dir / f"{STAGING_PREFIX}{uuid.uuid4().hex}"
        try:
            staging.mkdir(mode=0o700)
            _write_file_0600(staging / BIB_FILENAME, bib_bytes)
            _write_file_0600(staging / SIDECAR_FILENAME, sidecar_bytes)
            _fsync_dir(staging)
            os.rename(staging, final_dir)
            _fsync_dir(output_dir)
        except OSError as exc:
            _remove_tree(staging)
            raise StorageError("write_failed", f"bundle write failed: {exc}") from exc
        return BundleResult(
            bundle_dir=final_dir,
            bib_path=final_dir / BIB_FILENAME,
            sidecar_path=final_dir / SIDECAR_FILENAME,
            bib_sha256=bib_sha,
            reused=False,
        )
def _remove_tree(path: Path) -> None:
    try:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()
    except OSError:
        pass  # best-effort; stale-staging cleanup will reclaim it


def cleanup_stale_staging(
    output_dir: Path,
    *,
    max_age_seconds: float = STALE_STAGING_SECONDS,
    now: float | None = None,
) -> list[Path]:
    """Remove staging dirs older than 24 h; younger ones are left alone."""
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        return []
    current = time.time() if now is None else now
    removed: list[Path] = []
    for entry in output_dir.iterdir():
        if not entry.name.startswith(STAGING_PREFIX) or not entry.is_dir():
            continue
        try:
            age = current - entry.stat().st_mtime
        except OSError:
            continue
        if age >= max_age_seconds:
            _remove_tree(entry)
            if not entry.exists():
                removed.append(entry)
    return removed
