"""Project bibliography handlers: inspect, render, style, add, remove, export and lookup."""

from __future__ import annotations

import json
from dataclasses import field
from pathlib import Path
from typing import Any
from agent.desktop import bime_export
from agent.desktop.project import (
    ProjectError,
    inspect_project,
    project_citation_settings,
    update_project_metadata,
)
from agent.desktop.documents import DocumentError
from agent.ingest import run_local_work
from skills.citation.citekeys import format_for_path as citation_format_for_path
from skills.citation import csl_render
from skills.citation import library as citation_library
from skills.citation.integrity import entry_summary
from skills.citation.integrity import inspect as inspect_citations
from skills.citation.library import LibraryError, search_bibliography
from skills.citation.library import load as load_bibliography
from agent.desktop.errors import DesktopServiceError, EventSink, logger


BIBLIOGRAPHY_LOOKUP_LIMIT = 20


DEFAULT_CITATION_STYLE = "apa"


class _BibliographyOps:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    def _project_bibliography_path(self, project_id: str) -> Path | None:
        """The opened project's CSL-JSON bibliography, or None when unusable.

        A malformed ``bibliography`` metadata value leaves citation saves
        verified for the current task only (logged, nothing written) instead
        of failing the Citation task.
        """
        project = self._project
        if project is None or project.get("projectId") != project_id:
            return None
        try:
            return project_citation_settings(project["rootPath"])["bibliographyPath"]
        except ProjectError as exc:
            logger.warning("project bibliography unavailable: %s", exc)
            return None

    def _citation_settings(self) -> tuple[Path, str, bool]:
        """(bibliography path, effective style ID, whether the project set it)."""
        settings = project_citation_settings(self._require_project()["rootPath"])
        configured = settings["citationStyle"]
        known = {style["id"] for style in csl_render.list_styles()}
        if configured in known:
            return settings["bibliographyPath"], configured, True
        return settings["bibliographyPath"], DEFAULT_CITATION_STYLE, False

    def _require_idle_for_bibliography_write(self) -> None:
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN", "Wait for the active turn to finish before changing citations.", retryable=True,
            )

    def _bibliography_snapshot(self, params: dict[str, Any], *, required: bool) -> dict[str, Any] | None:
        context = params.get("documentContext")
        if context is None:
            if required:
                raise DesktopServiceError("PROTOCOL_INVALID", "Open a document first.")
            return None
        return self._documents.validate_snapshot(context)

    @staticmethod
    def _bibliography_error(exc: Exception) -> DesktopServiceError:
        code = getattr(exc, "code", "")
        if code == "style_unknown":
            return DesktopServiceError("PROTOCOL_INVALID", str(exc))
        if code == citation_library.LIBRARY_CONFLICT:
            return DesktopServiceError("BIBLIOGRAPHY_CONFLICT", str(exc), retryable=True)
        return DesktopServiceError("BIBLIOGRAPHY_FAILED", str(exc))

    async def _bibliography_inspect(self, params: dict[str, Any], _event_sink: EventSink | None) -> dict[str, Any]:
        library_path, style_id, configured = self._citation_settings()
        snapshot = self._bibliography_snapshot(params, required=False)
        fmt = citation_format_for_path(snapshot["path"]) if snapshot is not None else None
        text = snapshot["sourceText"] if snapshot is not None else ""
        report = await run_local_work(inspect_citations, text, fmt or "markdown", library_path)
        # The fingerprint of the copy inspect just read (None when missing or unreadable).
        fingerprint = report["bibliography"]["fingerprint"]
        error = report["bibliography"]["error"] or {}
        return {
            "libraryPath": str(library_path),
            "libraryStatus": report["bibliography"]["status"],
            "libraryFingerprint": fingerprint,
            "libraryErrorCode": error.get("code"),
            "libraryError": (error.get("message") or "")[:4096] or None,
            "styleId": style_id,
            "styleConfigured": configured,
            "styles": csl_render.list_styles(),
            "documentFormat": fmt,
            "entries": [
                {
                    "key": entry["key"], "authors": [name for name in entry["authors"] if name],
                    "year": str(entry["year"]) if entry["year"] is not None else None,
                    "title": entry["title"], "doi": entry["doi"], "type": entry["type"] or "",
                    "citedCount": entry["citedCount"] if snapshot is not None else 0,
                }
                for entry in report["entries"]
            ],
            "uses": [
                {key: use[key] for key in ("key", "start", "end", "line", "group", "known")}
                for use in report["uses"]
            ],
            "order": report["order"],
            "missing": [item["key"] for item in report["missing"]],
            "uncited": report["uncited"] if snapshot is not None else [],
            "duplicateDois": report["duplicateDois"],
        }

    def _markdown_snapshot(self, params: dict[str, Any], *, required: bool) -> dict[str, Any] | None:
        snapshot = self._bibliography_snapshot(params, required=required)
        if snapshot is not None and citation_format_for_path(snapshot["path"]) != "markdown":
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "LaTeX documents keep their own bibliography style; preview and .docx/Markdown export "
                "are available for Markdown documents.",
            )
        return snapshot

    def _requested_style(self, params: dict[str, Any], default: str) -> str:
        style_id = params.get("styleId") or default
        if style_id not in {style["id"] for style in csl_render.list_styles()}:
            raise DesktopServiceError("PROTOCOL_INVALID", f"Unknown citation style: {style_id}")
        return style_id

    async def _bibliography_render(self, params: dict[str, Any], _event_sink: EventSink | None) -> dict[str, Any]:
        library_path, default_style, _configured = self._citation_settings()
        snapshot = self._markdown_snapshot(params, required=True)
        style_id = self._requested_style(params, default_style)
        try:
            rendered = await run_local_work(csl_render.render, snapshot["sourceText"], library_path, style_id)
        except csl_render.RenderError as exc:
            raise self._bibliography_error(exc) from exc
        segments = []
        for index, entry in enumerate(rendered.bibliography):
            for segment in entry["segments"]:
                segments.append({
                    "entry": index, "text": segment["text"],
                    "italic": bool(segment.get("italic")), "bold": bool(segment.get("bold")),
                    "url": segment.get("url"),
                })
        return {
            "styleId": style_id,
            "citations": [
                {
                    "index": citation["index"], "keys": citation["keys"], "text": citation["text"],
                    **({"start": citation["start"], "end": citation["end"]} if citation["start"] is not None else {}),
                }
                for citation in rendered.citations
            ],
            "entries": [{"key": entry["key"], "text": entry["text"]} for entry in rendered.bibliography],
            "segments": segments,
            "missing": rendered.missing,
        }

    async def _bibliography_set_style(self, params: dict[str, Any], _event_sink: EventSink | None) -> dict[str, Any]:
        self._require_idle_for_bibliography_write()
        style_id = self._requested_style(params, "")
        project = self._require_project()
        fingerprint = await run_local_work(update_project_metadata, project["rootPath"], {"citationStyle": style_id})
        current = await run_local_work(inspect_project, project["rootPath"], self.config.persist_dir)
        if current["status"] == "ready" and all(
            current[field] == project[field] for field in ("rootPath", "projectId", "historyDirectory")
        ):
            self._project = current
        return {"styleId": style_id, "researchFingerprint": fingerprint}

    async def _bibliography_remove(self, params: dict[str, Any], _event_sink: EventSink | None) -> dict[str, Any]:
        self._require_idle_for_bibliography_write()
        library_path, _style, _configured = self._citation_settings()

        def remove() -> str:
            library = citation_library.load(library_path)
            if library.fingerprint != params["libraryFingerprint"]:
                raise LibraryError(citation_library.LIBRARY_CONFLICT, "The bibliography changed; inspect it again before removing.")
            if params["key"] not in library.keys():
                raise DesktopServiceError("PROTOCOL_INVALID", f"{params['key']} is not in the bibliography.")
            updated = citation_library.remove_entry(library, params["key"])
            citation_library.write_atomic(updated)
            return updated.fingerprint

        try:
            fingerprint = await run_local_work(remove)
        except LibraryError as exc:
            raise self._bibliography_error(exc) from exc
        return {"key": params["key"], "libraryFingerprint": fingerprint}

    async def _bibliography_add(self, params: dict[str, Any], event_sink: EventSink | None) -> dict[str, Any]:
        self._require_idle_for_bibliography_write()
        from skills.citation.doi import canonicalize_doi
        from skills.citation.hub import get_provider_hub
        from skills.citation.resolution import WorkIdentifier, WorkIntent, normalize_arxiv
        from skills.citation.service import CitationService

        library_path, _style, _configured = self._citation_settings()
        raw = params["identifier"].strip()
        try:
            doi = canonicalize_doi(raw)
            identifier = WorkIdentifier("doi", doi) if doi else WorkIdentifier("arxiv", normalize_arxiv(raw))
        except ValueError as exc:
            raise DesktopServiceError("PROTOCOL_INVALID", "Enter a DOI or an arXiv ID.") from exc
        await self._require_operation_approval(
            "citation.save", str(library_path),
            f"Verify {identifier.kind.upper() if identifier.kind == 'doi' else 'arXiv'} {identifier.value} "
            f"and add it to the project bibliography {library_path}.",
            parameters={"identifier": identifier.value, "bibliography": str(library_path)},
            event_sink=event_sink,
        )
        service = CitationService(get_provider_hub(), library_path=library_path)
        outcome = await service.save((WorkIntent(identifier.value[:200], identifiers=(identifier,)),))
        item = outcome.items[0]
        # The save wrote (or did not write) the bibliography itself; report the result's fingerprint.
        fingerprint = await run_local_work(citation_library.fingerprint, library_path)
        if item.bibliography is None:
            # storage_failed carries the bibliography's error code; other statuses their own reason.
            return {"status": "failed", "key": None, "reasonCode": item.reason_code, "libraryFingerprint": fingerprint}
        link = item.bibliography
        return {"status": link.status, "key": link.key, "reasonCode": None, "libraryFingerprint": fingerprint}

    async def _bibliography_export(self, params: dict[str, Any], _event_sink: EventSink | None) -> dict[str, Any]:
        self._require_idle_for_bibliography_write()
        library_path, default_style, _configured = self._citation_settings()
        fmt = params.get("format")
        if fmt != "bime_docx" and fmt not in csl_render.EXPORT_SUFFIXES:
            raise DesktopServiceError("PROTOCOL_INVALID", f"Unknown export format: {fmt}")
        snapshot = self._markdown_snapshot(params, required=True)
        if fmt == "bime_docx":
            return await self._bime_export(snapshot, Path(library_path))
        style_id = self._requested_style(params, default_style)
        document_path = Path(snapshot["path"])
        target = csl_render.export_target(fmt, document_path=document_path, style_id=style_id)
        if target.resolve() == document_path.resolve():
            raise DesktopServiceError("PROTOCOL_INVALID", "An export never replaces its source document.")

        def export() -> None:
            if fmt == "markdown":
                data = csl_render.export_markdown(snapshot["sourceText"], library_path, style_id).encode("utf-8")
            else:
                data = csl_render.export_docx(snapshot["sourceText"], library_path, style_id, resource_dir=document_path.parent)
            citation_library.write_bytes_atomic(target, data)

        try:
            await run_local_work(export)
        except (csl_render.RenderError, LibraryError) as exc:
            raise self._bibliography_error(exc) from exc
        return {"format": fmt, "path": str(target)}

    async def _bime_export(self, snapshot: dict[str, Any], library_path: Path) -> dict[str, Any]:
        """BIME Appendix 17 Word via the vendored bime_word; it reads the saved file (A11)."""
        document_path = Path(snapshot["path"])
        try:
            saved = self._documents.matches_disk(snapshot)
        except DocumentError as exc:
            raise DesktopServiceError("BIBLIOGRAPHY_FAILED", str(exc)) from exc
        if not saved:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "Save the document first (Ctrl+S): the BIME Word export converts the saved file.",
            )
        if bime_export.bime_target(document_path).resolve() == document_path.resolve():
            raise DesktopServiceError("PROTOCOL_INVALID", "An export never replaces its source document.")
        try:
            result = await run_local_work(bime_export.run_bime_convert, document_path, library_path)
        except bime_export.BimeExportError as exc:
            raise DesktopServiceError("BIBLIOGRAPHY_FAILED", str(exc)) from exc
        return {"format": "bime_docx", "path": result["path"], "audit": result["audit"]}

    def _desktop_bibliography_lookup(self, query: str) -> str:
        """Search the opened project's bibliography without writing anything."""
        project = self._project
        if project is None:
            return json.dumps({"status": "failed", "issue": "No research project is open."})
        try:
            path = project_citation_settings(project["rootPath"])["bibliographyPath"]
        except ProjectError as exc:
            return json.dumps({"status": "failed", "issue": f"Project bibliography setting is invalid: {exc}"})
        try:
            library = load_bibliography(path)
        except LibraryError as exc:
            return json.dumps({"status": "failed", "code": exc.code, "issue": str(exc), "path": str(path)})
        matches = search_bibliography(library.items, query, limit=BIBLIOGRAPHY_LOOKUP_LIMIT)
        return json.dumps({
            "status": "ok",
            "path": str(path),
            "exists": library.exists,
            "total": len(library.items),
            "entries": [entry_summary(item) for item in matches],
        }, ensure_ascii=False)
