"""Session-scoped registry of live citable SourceRefs."""

from __future__ import annotations

from skills.citation.types import SaveReceipt, SourceRef, source_identity

PROMPT_REGISTRY_LIMIT = 20


class SourceRegistry:
    def __init__(self):
        self._sources: dict[str, SourceRef] = {}
        self._save_receipts: dict[str, SaveReceipt] = {}
        self._recency: list[str] = []

    @staticmethod
    def _validate_receipt(ref: SourceRef, receipt: SaveReceipt) -> None:
        if (
            receipt.source_id != ref.source_id
            or receipt.canonical_identity != source_identity(ref)
            or receipt.doi != ref.doi
            or receipt.title != ref.title
            or receipt.year != ref.year
            or receipt.work_type != ref.work_type
            or receipt.verification_level != ref.verification_level
        ):
            raise ValueError("save receipt does not match source")

    def register(
        self, ref: SourceRef, *, receipt: SaveReceipt | None = None
    ) -> SourceRef:
        if receipt is not None:
            self._validate_receipt(ref, receipt)
        existing = self._sources.get(ref.source_id)
        if existing is not None and source_identity(existing) != source_identity(ref):
            raise ValueError(f"source_id {ref.source_id!r} belongs to another identity")
        self._sources[ref.source_id] = ref
        if receipt is None:
            self._save_receipts.pop(ref.source_id, None)
        else:
            self._save_receipts[ref.source_id] = receipt
        self._touch(ref.source_id)
        return existing or ref

    def _touch(self, source_id: str) -> None:
        if source_id in self._recency:
            self._recency.remove(source_id)
        self._recency.insert(0, source_id)

    def get(self, source_id: str) -> SourceRef | None:
        return self._sources.get(source_id)

    def trusted_receipt(self, source_id: str) -> SaveReceipt | None:
        return self._save_receipts.get(source_id)

    def receipt_is_trusted(self, receipt: SaveReceipt) -> bool:
        ref = self._sources.get(receipt.source_id)
        if ref is None or self._save_receipts.get(receipt.source_id) != receipt:
            return False
        try:
            self._validate_receipt(ref, receipt)
        except ValueError:
            return False
        return True

    def activate(self, source_id: str) -> SourceRef | None:
        ref = self._sources.get(source_id)
        if ref is not None:
            self._touch(source_id)
        return ref

    def list(self) -> list[SourceRef]:
        return [self._sources[sid] for sid in self._recency]

    def prompt_sources(self, limit: int = PROMPT_REGISTRY_LIMIT) -> list[SourceRef]:
        return self.list()[:max(0, limit)]
