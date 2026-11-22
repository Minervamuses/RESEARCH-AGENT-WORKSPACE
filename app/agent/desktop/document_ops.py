"""Editor document handlers: open, save, the document_edit tool, candidates and apply/undo."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Annotated, Any
from langchain_core.tools import InjectedToolCallId
from agent.desktop.project import ProjectError, project_citation_settings
from agent.desktop.documents import DocumentError
from agent.ingest import await_sync_work, current_local_work, run_local_work
from skills.citation.citekeys import format_for_path as citation_format_for_path
from skills.citation.citekeys import keys_in as citation_keys_in
from skills.citation.library import LibraryError
from skills.citation.library import load as load_bibliography
from agent.desktop.errors import EventSink


@dataclass
class _DocumentCandidate:
    value: Any
    context: dict[str, Any]
    turn_id: str
    parent_request_id: str
    permission_mode: str
    future: asyncio.Future[dict[str, Any]] | None = None
    result: dict[str, Any] | None = None
    stopped: bool = False


class _DocumentOps:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    async def _document_open(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._documents.open, params["path"])

    async def _document_save(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._documents.save, params["documentContext"])

    def _unknown_new_citation_keys(self, context: dict[str, Any], replacement_text: str) -> dict[str, Any] | None:
        """Refuse an edit whose resulting document adds uses of keys missing from the bibliography.

        The check runs on the full text the candidate would save (the
        replacement spliced into the source exactly as ``prepare`` does), so a
        partial selection such as ``known`` inside ``[@known]`` cannot turn a
        known key into an unknown one. A key counts as added when it occurs
        more often after the edit than before; existing uses, including
        unknown keys the document already had, are left alone.
        Returns the failure payload, or None when the edit may proceed.
        """
        fmt = citation_format_for_path(context["path"])
        if fmt is None:
            return None
        try:
            base, candidate = self._documents.candidate_text(context, replacement_text)
        except DocumentError:
            return None  # prepare() reports the same invalid range or text
        before = Counter(citation_keys_in(base["sourceText"], fmt))
        after = Counter(citation_keys_in(candidate, fmt))
        added = [key for key in after if after[key] > before.get(key, 0)]
        if not added:
            return None
        project = self._project
        try:
            if project is None:
                raise LibraryError("library_malformed", "No research project is open.")
            path = project_citation_settings(project["rootPath"])["bibliographyPath"]
            known = set(load_bibliography(path).keys())
        except (ProjectError, LibraryError) as exc:
            return {
                "status": "failed",
                "issue": (
                    "The edit adds citation keys to the document, but the project bibliography cannot be read "
                    f"({exc}); no candidate was prepared."
                ),
                "unknownKeys": added,
            }
        unknown = [key for key in added if key not in known]
        if not unknown:
            return None
        return {
            "status": "failed",
            "issue": (
                "After this edit the document would cite keys that are not in the project bibliography "
                f"({path}); no candidate was prepared. Use bibliography_lookup for existing keys, or "
                "save the work with /citation first. Do not invent keys."
            ),
            "unknownKeys": unknown,
        }

    async def _desktop_document_edit(
        self, replacement_text: str, tool_call_id: Annotated[str, InjectedToolCallId],
        reference_id: str | None = None,
    ) -> str:
        """Serialize version-checked writes to the current editor or a frozen reference."""
        async with self._document_tool_lock:
            return await self._run_desktop_document_edit(replacement_text, tool_call_id, reference_id)

    async def _run_desktop_document_edit(
        self, replacement_text: str, tool_call_id: str, reference_id: str | None = None,
    ) -> str:
        """Prepare one bounded candidate and wait for the actual editor save result."""
        scope = current_local_work()
        if scope is not None:
            scope.check_cancelled()
        turn = self._running_turn
        if turn is None:
            return json.dumps({"status": "failed", "issue": "No active desktop document snapshot is available."})
        context = turn.document_context
        document_references = [item for item in turn.references if item["kind"] == "document"]
        reference = None
        if reference_id is not None:
            reference = next((item for item in turn.references if item["referenceId"] == reference_id), None)
            if reference is None or reference["kind"] != "document":
                return json.dumps({"status": "failed", "issue": "reference_id must identify a document reference; chat references are read-only."})
        elif len(document_references) > 1:
            return json.dumps({"status": "failed", "issue": "Supply the reference_id identified by the user's request for this edit. Handle separately requested references in order; ask for clarification only if the target is unclear."})
        if reference is not None:
            context = reference["document"]["snapshot"]
            if context["path"] != turn.editor_path:
                return json.dumps({"status": "failed", "issue": "Open this reference's document in the editor and submit a new turn before editing it."})
        turn_id = turn.turn_id
        parent_request_id = turn.parent_request_id
        sink = turn.event_sink
        if not self._turn_active or context is None or parent_request_id is None or sink is None:
            return json.dumps({"status": "failed", "issue": "No active desktop document snapshot is available."})
        # The model call's identity is stable for an explicit retry, while two
        # distinct operations within one turn must remain separate candidates.
        call_id = hashlib.sha256(f"{turn_id}\0{tool_call_id}".encode("utf-8")).hexdigest()
        existing = self._document_candidates.get(call_id)
        if existing is not None:
            await run_local_work(
                self._documents.prepare, existing.context, replacement_text,
                turn_id=turn_id, call_id=call_id,
            )
            if existing.result is not None:
                if existing.result.get("status") == "saved":
                    checked = await run_local_work(self._documents.apply, existing.value, context)
                    existing.result = {**checked, "callId": existing.value["callId"]}
                    self._advance_document_working_context(existing, checked)
                return json.dumps(existing.result, ensure_ascii=False)
            return json.dumps({"status": "failed", "issue": "This turn already has a pending document candidate; do not replay it."})
        refused = self._unknown_new_citation_keys(context, replacement_text)
        if refused is not None:
            return json.dumps(refused, ensure_ascii=False)
        candidate_value = await run_local_work(
            self._documents.prepare, context, replacement_text, turn_id=turn_id, call_id=call_id,
        )
        future = asyncio.get_running_loop().create_future()
        candidate = _DocumentCandidate(
            value=candidate_value, context=context, turn_id=turn_id,
            parent_request_id=parent_request_id,
            permission_mode=turn.permission_mode, future=future,
        )
        self._document_candidates[call_id] = candidate
        try:
            sink("document.proposed", {"turnId": turn_id, "callId": call_id, **({"referenceId": reference["referenceId"]} if reference is not None else {})})
            result = await asyncio.wait_for(asyncio.shield(future), timeout=self._approval_timeout_seconds * 2)
        except asyncio.CancelledError:
            if not future.done():
                future.cancel()
            raise
        except TimeoutError:
            result = {
                "path": context["path"], "callId": call_id, "status": "cancelled",
                "candidateText": candidate_value["candidateText"],
                "issue": "The document operation did not finish; the candidate is retained and no save is confirmed.",
            }
            candidate.result = result
            if not future.done():
                future.set_result(result)
        return json.dumps(result, ensure_ascii=False)

    def _advance_document_working_context(
        self, candidate: _DocumentCandidate, result: dict[str, Any],
    ) -> None:
        turn = self._running_turn
        if (
            result.get("status") != "saved" or not self._turn_active
            or turn is None or candidate.turn_id != turn.turn_id
        ):
            return
        snapshot_keys = ("rootPath", "path", "editorRevision", "sourceText", "diskFingerprint")
        saved = {
            key: result[key]
            for key in (*snapshot_keys, "rangeStartUtf16", "rangeEndUtf16")
        }
        active = turn.document_context
        if active is not None and all(active[key] == candidate.context[key] for key in snapshot_keys):
            turn.document_context = saved
        start = candidate.value["rangeStartUtf16"]
        end = candidate.value["rangeEndUtf16"]
        saved_end = result["rangeEndUtf16"]
        delta = saved_end - end
        for reference in turn.references:
            if reference["kind"] != "document":
                continue
            before = reference["document"]["snapshot"]
            # Only advance this candidate's base; a repeated saved receipt must
            # not shift ranges that already include the edit.
            if any(before[key] != candidate.context[key] for key in snapshot_keys):
                continue
            left, right = before["rangeStartUtf16"], before["rangeEndUtf16"]
            if right <= start:
                pass
            elif left >= end:
                left, right = left + delta, right + delta
            else:
                left, right = min(left, start), max(saved_end, right + delta)
            reference["document"]["snapshot"] = {
                **saved, "rangeStartUtf16": left, "rangeEndUtf16": right,
            }

    async def _document_apply(
        self, params: dict[str, Any], event_sink: EventSink | None
    ) -> dict[str, Any]:
        candidate = self._document_candidates.get(params.get("callId") or params.get("undoOfCallId"))
        owner = self._turn_work
        owns_candidate = (
            owner is not None and candidate is not None
            and owner.turn_id == candidate.turn_id
            and owner.parent_request_id == candidate.parent_request_id
        )
        if candidate is not None and candidate.stopped and not params.get("undoOfCallId"):
            raise DocumentError("The owning turn was stopped; this document operation can no longer start.")
        if not owns_candidate or not self._turn_active:
            return await self._apply_document_candidate(params, event_sink)
        task = asyncio.current_task()
        owner.document_tasks.add(task)
        try:
            with owner.scope.bind():
                return await self._apply_document_candidate(params, event_sink)
        finally:
            owner.document_tasks.discard(task)

    async def _apply_document_candidate(
        self, params: dict[str, Any], event_sink: EventSink | None
    ) -> dict[str, Any]:
        async with self._document_apply_lock:
            context = self._documents.validate_snapshot(params["documentContext"])
            turn_id = params["turnId"]
            undo_of = params.get("undoOfCallId")
            call_id = params.get("callId") or undo_of
            candidate = self._document_candidates.get(call_id)
            if candidate is None or candidate.turn_id != turn_id:
                raise DocumentError("Unknown document operation; do not replay after restart.")
            if params.get("parentRequestId") is not None and params["parentRequestId"] != candidate.parent_request_id:
                raise DocumentError("Document operation belongs to another turn request.")
            running = self._running_turn
            if self._turn_active and (
                running is None or turn_id != running.turn_id
                or candidate.parent_request_id != running.parent_request_id
            ):
                raise DocumentError("Document operation does not match the active turn.")
            if context["path"] != candidate.context["path"]:
                raise DocumentError("Document operation belongs to another file.")
            scope = current_local_work()
            if scope is not None:
                scope.check_cancelled()
            resolution = params.get("resolution")
            if undo_of and resolution is not None:
                raise DocumentError("Undo does not adopt an arbitrary conflict candidate.")
            if resolution in {"keep", "cancel"}:
                result = await await_sync_work(
                    self._documents.apply, candidate.value, context,
                    resolution="current" if resolution == "keep" else "cancel",
                )
            else:
                # In a turn, approval shares session.turn's live event stream. A later
                # conflict choice or Undo uses its own document.apply request stream.
                running = self._running_turn
                approval_sink = (running.event_sink if running is not None else None) if self._turn_active else event_sink
                approval_parent = (
                    (running.parent_request_id if running is not None else None)
                    if self._turn_active else getattr(event_sink, "request_id", None)
                )
                if not isinstance(approval_parent, str):
                    raise DocumentError("Document operation requires a correlated desktop request.")
                mode = self._permission_mode if undo_of else candidate.permission_mode
                approved, context = await self._document_operation_approval(
                    event_sink=approval_sink, parent_request_id=approval_parent,
                    turn_id=turn_id, operation="document.undo" if undo_of else "document.apply",
                    context=context, permission_mode=mode,
                )
                if not approved:
                    result = {
                        "path": context["path"], "status": "cancelled",
                        "candidateText": candidate.value["candidateText"],
                        "issue": "The document operation was denied or its approval expired; no write occurred.",
                    }
                elif undo_of:
                    request_id = getattr(event_sink, "request_id", None)
                    if not isinstance(request_id, str):
                        raise DocumentError("Undo requires a new correlated requestId.")
                    result = await await_sync_work(
                        self._documents.undo, undo_of, context, request_id=request_id, turn_id=turn_id,
                    )
                else:
                    result = await await_sync_work(
                        self._documents.apply, candidate.value, context,
                        resolution="candidate" if resolution == "use" else None,
                        expected_snapshot=params.get("expectedSnapshot"),
                    )
            result = {**result, "callId": call_id}
            if not undo_of:
                self._advance_document_working_context(candidate, result)
                candidate.result = result
                if candidate.future is not None and not candidate.future.done():
                    candidate.future.set_result(result)
            return result
