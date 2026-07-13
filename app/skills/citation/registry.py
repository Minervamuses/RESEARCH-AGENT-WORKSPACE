"""Session-scoped registry of live citable SourceRefs."""

from __future__ import annotations

from skills.citation.types import SourceRef, source_identity

PROMPT_REGISTRY_LIMIT = 20


class SourceRegistry:
    def __init__(self):
        self._sources: dict[str, SourceRef] = {}
        self._recency: list[str] = []

    def register(self, ref: SourceRef) -> SourceRef:
        existing = self._sources.get(ref.source_id)
        if existing is not None and source_identity(existing) != source_identity(ref):
            raise ValueError(f"source_id {ref.source_id!r} belongs to another identity")
        self._sources[ref.source_id] = ref
        self._touch(ref.source_id)
        return existing or ref

    def _touch(self, source_id: str) -> None:
        if source_id in self._recency:
            self._recency.remove(source_id)
        self._recency.insert(0, source_id)

    def get(self, source_id: str) -> SourceRef | None:
        return self._sources.get(source_id)

    def activate(self, source_id: str) -> SourceRef | None:
        ref = self._sources.get(source_id)
        if ref is not None:
            self._touch(source_id)
        return ref

    def list(self) -> list[SourceRef]:
        return [self._sources[sid] for sid in self._recency]

    def prompt_sources(self, limit: int = PROMPT_REGISTRY_LIMIT) -> list[SourceRef]:
        return self.list()[:max(0, limit)]
