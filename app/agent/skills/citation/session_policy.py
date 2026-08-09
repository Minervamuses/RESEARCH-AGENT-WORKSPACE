"""Session-scoped citation service lifecycle and finalization policy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.messages import SystemMessage, ToolMessage

from skills.citation.gate import build_safe_message, check_citations
from skills.citation.render import render_citations
from skills.citation.tool import create_citation_workflow_tool
from skills.citation.types import SaveBatchOutcome, is_citable_source

from agent.config import AgentConfig
from agent.observability import CitationSaveMetrics

if TYPE_CHECKING:
    from skills.citation.service import CitationService

logger = logging.getLogger(__name__)


class CitationSessionPolicy:
    """Own the citation service, registry lifecycle, gate, and rendering."""

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._service: CitationService | None = None
        self.workflow_tool = create_citation_workflow_tool(
            service_getter=lambda: self.service,
        )

    @property
    def service(self) -> CitationService:
        """Lazily build and return this session's citation service."""
        if self._service is None:
            from skills.citation.hub import get_provider_hub
            from skills.citation.service import CitationService

            self._service = CitationService(
                get_provider_hub(),
                config=self._config,
            )
        return self._service

    @property
    def loaded_service(self) -> CitationService | None:
        """Return the loaded service without constructing it."""
        return self._service

    def set_loaded_service(self, service: CitationService | None) -> None:
        """Replace the loaded service, primarily for controlled injection."""
        self._service = service

    @property
    def registry(self):
        """Return the live source registry without constructing a service."""
        service = self._service
        return service.registry if service is not None else None

    def reset(self) -> None:
        """Discard the in-memory service and its source registry."""
        self._service = None

    def build_sources_hint(
        self,
        *,
        citation_active: bool,
    ) -> SystemMessage | None:
        """Render verified sources for the active citation skill."""
        if not citation_active:
            return None
        registry = self.registry
        if registry is None:
            return None
        sources = [
            ref
            for ref in registry.prompt_sources()
            if is_citable_source(ref)
        ]
        if not sources:
            return None
        lines = [
            "[Citable sources] Use these markers when you want the citation "
            "renderer to number a saved source and append its bibliography "
            "entry. Use [[citation-needed]] when a claim lacks a source.",
        ]
        for ref in sources:
            label = ref.title or ref.doi or ref.url or "(unknown)"
            lines.append(f"- [[cite:{ref.source_id}]] {label}")
        return SystemMessage(content="\n".join(lines))

    def save_metrics(
        self,
        new_messages: list,
        *,
        citation_active: bool,
    ) -> CitationSaveMetrics:
        """Aggregate trustworthy counts across attempted citation saves."""
        registry = self.registry if citation_active else None
        if registry is None:
            return CitationSaveMetrics()
        batch_count = 0
        saved_count = 0
        reused_count = 0
        failed_count = 0
        for message in new_messages:
            if (
                not isinstance(message, ToolMessage)
                or getattr(message, "name", None) != "citation_workflow"
            ):
                continue
            if getattr(message, "status", "success") != "success":
                continue
            artifact = getattr(message, "artifact", None)
            if (
                not isinstance(artifact, dict)
                or artifact.get("kind") != "citation_save_batch"
            ):
                continue
            try:
                batch = SaveBatchOutcome.from_artifact(artifact)
            except (TypeError, ValueError) as exc:
                logger.warning("ignored invalid citation save batch: %s", exc)
                continue
            batch_count += 1
            for item in batch.items:
                receipt = item.receipt
                if receipt is not None:
                    ref = registry.get(receipt.source_id)
                    if (
                        ref is None
                        or not registry.receipt_is_trusted(receipt)
                        or not is_citable_source(ref)
                    ):
                        logger.warning("save receipt/registry mismatch")
                        failed_count += 1
                        continue
                if item.status == "saved":
                    saved_count += 1
                elif item.status == "reused":
                    reused_count += 1
                else:
                    failed_count += 1
        return CitationSaveMetrics(
            batch_count=batch_count,
            new_saved_count=saved_count,
            reused_count=reused_count,
            failed_count=failed_count,
        )

    def finalize_answer(
        self,
        answer: str,
        *,
        user_input: str,
        citation_active: bool,
    ) -> tuple[str, list[str]]:
        """Apply citation validation and render verified markers."""
        registry = self.registry if citation_active else None
        verified_ids = frozenset(
            ref.source_id
            for ref in (registry.list() if registry is not None else [])
            if is_citable_source(ref)
        )
        violations = check_citations(
            answer,
            verified_source_ids=verified_ids,
            citation_active=citation_active,
            user_input=user_input,
        )
        if violations:
            errors = [
                f"{violation.code}: {violation.detail}"
                for violation in violations
            ]
            logger.warning(
                "citation gate blocked a draft: %s",
                [violation.code for violation in violations],
            )
            safe = build_safe_message(
                violations,
                citation_active=citation_active,
            )
            return safe, errors
        if not citation_active:
            return answer, []
        resolve = registry.get if registry is not None else (lambda _sid: None)
        return render_citations(answer, resolve=resolve).text, []
