"""Atomic citation bundle storage.

Every confirmed citation persists as one bundle directory::

    <output>/<utf8-byte-capped-title>--<doi-hash>/reference.bib
    <output>/<utf8-byte-capped-title>--<doi-hash>/citation.json

Atomicity: both files are written into a hidden staging directory on the
same filesystem (0600, flushed and fsynced), then a single ``rename`` makes
the bundle visible — a visible bundle is never half-written. Stale staging
directories are only reclaimed after 24 hours.

Idempotency and fail-closed rules:
  * re-confirming the same DOI validates the existing sidecar (schema, DOI,
    artifact hash) and reuses the bundle;
  * an existing bundle whose schema/DOI/hash does not validate fails closed —
    it is never overwritten;
  * a *different* DOI colliding on the same directory name lengthens the DOI
    hash from 12 to 20 to 64 hex chars.

The sidecar is built by the Coordinator and must never contain raw pages,
LLM responses, API keys, or URLs embedding keys; storage only adds the
artifact hash and schema/DOI stamps it needs for validation.

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
from dataclasses import dataclass
from pathlib import Path

from skills.citation.types import PERSIST_SCHEMA_VERSION

BIB_FILENAME = "reference.bib"
SIDECAR_FILENAME = "citation.json"
MAX_BUNDLE_DIR_BYTES = 180
HASH_LENGTHS = (12, 20, 64)
STAGING_PREFIX = ".staging-"
STALE_STAGING_SECONDS = 24 * 60 * 60

_UNSAFE_CHARS = set('<>:"/\\|?*') | {chr(i) for i in range(0x20)}


class StorageError(RuntimeError):
    """Raised when a bundle cannot be written or validated.

    ``code``: ``bundle_conflict`` (existing bundle fails validation; never
    overwritten) or ``write_failed`` (I/O failure, staging left for later
    inspection/cleanup).
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


def bundle_dir_name(
    title: str, canonical_doi: str, *, hash_length: int = HASH_LENGTHS[0]
) -> str:
    """``<utf8-byte-capped-title>--<doi-hash>``, at most 180 UTF-8 bytes."""
    suffix = f"--{doi_hash(canonical_doi, length=hash_length)}"
    budget = MAX_BUNDLE_DIR_BYTES - len(suffix.encode("utf-8"))
    stem = _truncate_utf8(_sanitize_title(title), budget)
    return f"{stem}{suffix}"


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


def validate_bundle(bundle_dir: Path, canonical_doi: str) -> BundleResult:
    """Validate an existing bundle for reuse; raise fail-closed on mismatch.

    Raises StorageError('bundle_conflict') for schema/hash mismatches or a
    corrupt sidecar, and ValueError when the bundle belongs to a *different*
    DOI (a directory-name collision the caller resolves with a longer hash).
    """
    bib_path = bundle_dir / BIB_FILENAME
    sidecar_path = bundle_dir / SIDECAR_FILENAME
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(
            "bundle_conflict",
            f"existing bundle {bundle_dir.name!r} has an unreadable sidecar; "
            f"refusing to overwrite ({exc})",
        ) from exc

    existing_doi = str(sidecar.get("doi", "") or "")
    if existing_doi != canonical_doi:
        raise ValueError("bundle belongs to a different DOI")

    if int(sidecar.get("schema_version", -1)) != PERSIST_SCHEMA_VERSION:
        raise StorageError(
            "bundle_conflict",
            f"existing bundle {bundle_dir.name!r} has schema_version="
            f"{sidecar.get('schema_version')!r}; refusing to overwrite",
        )
    expected_hash = str(
        (sidecar.get("artifact_hashes") or {}).get(BIB_FILENAME, "")
    )
    try:
        actual_hash = _sha256_bytes(bib_path.read_bytes())
    except OSError as exc:
        raise StorageError(
            "bundle_conflict",
            f"existing bundle {bundle_dir.name!r} is missing {BIB_FILENAME}; "
            "refusing to overwrite",
        ) from exc
    if not expected_hash or actual_hash != expected_hash:
        raise StorageError(
            "bundle_conflict",
            f"existing bundle {bundle_dir.name!r} artifact hash mismatch; "
            "refusing to overwrite",
        )
    return BundleResult(
        bundle_dir=bundle_dir,
        bib_path=bib_path,
        sidecar_path=sidecar_path,
        bib_sha256=actual_hash,
        reused=True,
    )


def write_bundle(
    output_dir: Path,
    *,
    canonical_doi: str,
    title: str,
    bibtex_text: str,
    sidecar: dict,
) -> BundleResult:
    """Atomically persist one bundle; idempotent for the same DOI.

    ``sidecar`` is the Coordinator-built payload; storage stamps
    ``schema_version``, ``doi``, and ``artifact_hashes`` into it.
    """
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError(
            "write_failed", f"cannot create output dir {output_dir}: {exc}"
        ) from exc

    bib_bytes = bibtex_text.encode("utf-8")
    bib_sha = _sha256_bytes(bib_bytes)
    payload = dict(sidecar)
    payload["schema_version"] = PERSIST_SCHEMA_VERSION
    payload["doi"] = canonical_doi
    payload["artifact_hashes"] = {BIB_FILENAME: bib_sha}
    sidecar_bytes = json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8")

    for hash_length in HASH_LENGTHS:
        final_dir = output_dir / bundle_dir_name(
            title, canonical_doi, hash_length=hash_length
        )
        if final_dir.exists():
            try:
                return validate_bundle(final_dir, canonical_doi)
            except ValueError:
                continue  # true collision: different DOI, lengthen the hash

        staging = output_dir / f"{STAGING_PREFIX}{uuid.uuid4().hex}"
        try:
            staging.mkdir(mode=0o700)
            _write_file_0600(staging / BIB_FILENAME, bib_bytes)
            _write_file_0600(staging / SIDECAR_FILENAME, sidecar_bytes)
            _fsync_dir(staging)
        except OSError as exc:
            raise StorageError(
                "write_failed", f"staging write failed under {output_dir}: {exc}"
            ) from exc

        try:
            os.rename(staging, final_dir)
        except OSError:
            # Lost a race: someone made final_dir first. Validate theirs.
            _remove_tree(staging)
            try:
                return validate_bundle(final_dir, canonical_doi)
            except ValueError:
                continue
        _fsync_dir(output_dir)
        return BundleResult(
            bundle_dir=final_dir,
            bib_path=final_dir / BIB_FILENAME,
            sidecar_path=final_dir / SIDECAR_FILENAME,
            bib_sha256=bib_sha,
            reused=False,
        )

    raise StorageError(
        "bundle_conflict",
        f"could not place bundle for {canonical_doi!r}: name collisions "
        "persist even at full hash length",
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
