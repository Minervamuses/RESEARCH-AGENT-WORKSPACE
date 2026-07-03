"""JSON file-based document store."""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from langchain_core.documents import Document

from rag.store.base import BaseStore


class JSONStore(BaseStore):
    """File-based store for BM25 and backup.

    Every read/write entry point revalidates the in-memory copy against an
    (st_mtime_ns, st_size) fingerprint of raw.json, so a process-cached
    instance notices external rewrites; ns-level mtime plus size double-keys
    the check so same-second writes are never mistaken for "unchanged".
    Saves go through a temp file + os.replace, so a crash mid-write can never
    leave a truncated raw.json. ``deferred_save()`` batches many add/delete
    calls into one atomic write.
    """

    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        self._docs: list[dict] = []
        self._fingerprint: tuple[int, int] | None = None
        self._defer_depth = 0
        self._load()

    # --- File syncing -------------------------------------------------------

    def _read_fingerprint(self) -> tuple[int, int] | None:
        try:
            stat = self.json_path.stat()
        except FileNotFoundError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    def _load(self) -> None:
        if self.json_path.exists():
            with self.json_path.open("r", encoding="utf-8") as f:
                self._docs = json.load(f)
        else:
            self._docs = []
        self._fingerprint = self._read_fingerprint()

    def _maybe_reload(self) -> None:
        """Reload when the on-disk file changed under us (one stat call).

        Skipped inside a deferred_save batch: the batch's pending in-memory
        changes must not be clobbered; the batch exit re-verifies the
        fingerprint and fails loudly instead.
        """
        if self._defer_depth:
            return
        if self._read_fingerprint() != self._fingerprint:
            self._load()

    def _save(self) -> None:
        if self._defer_depth:
            return
        self._write_out()

    def _write_out(self) -> None:
        """Atomically replace raw.json (temp file + os.replace)."""
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=self.json_path.parent,
            prefix=f"{self.json_path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._docs, f, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.json_path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise
        self._fingerprint = self._read_fingerprint()

    @contextmanager
    def deferred_save(self):
        """Batch add/delete calls into one atomic write on exit.

        On entry the on-disk state is synced and its fingerprint recorded;
        per-call saves are suppressed. On successful exit the fingerprint is
        re-verified: if another process rewrote the file during the batch,
        RuntimeError is raised and nothing is written — re-run the ingest
        (upserts are idempotent). Crash semantics: an exception inside the
        batch means this batch's JSON updates never hit disk while Chroma may
        hold partial writes; recovery is to re-run the ingest.
        """
        self._maybe_reload()
        entry_fingerprint = self._fingerprint
        self._defer_depth += 1
        try:
            yield self
        finally:
            self._defer_depth -= 1
        if self._defer_depth:
            return
        if self._read_fingerprint() != entry_fingerprint:
            raise RuntimeError(
                f"{self.json_path} was modified by another process during a "
                "deferred_save batch; this batch's JSON updates were discarded. "
                "Re-run the ingest (upserts are idempotent)."
            )
        self._write_out()

    # --- Store API ------------------------------------------------------------

    def add(self, documents: list[Document]) -> None:
        """Add documents to JSON file."""
        self._maybe_reload()
        for doc in documents:
            self._docs.append({
                "page_content": doc.page_content,
                "metadata": doc.metadata,
            })
        self._save()

    def get(self, pid: str | None = None) -> list[Document]:
        """Retrieve documents, optionally filtered by pid."""
        self._maybe_reload()
        docs = []
        for entry in self._docs:
            if pid and entry.get("metadata", {}).get("pid") != pid:
                continue
            docs.append(Document(
                page_content=entry["page_content"],
                metadata=entry.get("metadata", {}),
            ))
        return docs

    def delete(self, pid: str) -> None:
        """Delete all documents matching a pid."""
        self._maybe_reload()
        self._docs = [
            d for d in self._docs
            if d.get("metadata", {}).get("pid") != pid
        ]
        self._save()
