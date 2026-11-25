"""Session turns: the turn handler, Stop and Retry Stop, progress events and result checks."""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import dataclass, field
from typing import Any
from langchain_core.messages import AIMessage, ToolMessage
from agent.conversations import MAX_INPUT_BYTES, ConversationError, truncate_utf8
from agent.cli.slash_commands import (
    SlashCommandContext,
    SlashCommandError,
    SlashCommandResult,
    execute_slash_command,
    parse_slash_command,
)
from agent.desktop.protocol import ProtocolError, success_result
from agent.desktop.documents import DocumentError
from agent.document_context import FROZEN_REFERENCES_HEADER, SNAPSHOT_HEADER
from agent.ingest import LocalWorkScope, run_local_work
from agent.session import ChatSession, READ_ONLY_DOCUMENT_SKILLS, TurnOptions
from agent.skills.runtime import resolve_skill_references
from agent.turns.safety import content_text
from agent.desktop.errors import DesktopServiceError, EventSink
from agent.desktop.extension_ops import _MAX_LOCAL_COMMAND_BYTES
from agent.desktop.turn_context import _EDITABLE_REFERENCE_INSTRUCTIONS, _EDITABLE_SNAPSHOT_INSTRUCTIONS, _READ_ONLY_REFERENCE_INSTRUCTIONS, _READ_ONLY_SNAPSHOT_INSTRUCTIONS, _model_reference_projection


_DESKTOP_KNOWLEDGE_COMMANDS = frozenset({"init", "ingest", "sync", "prune"})


_DESKTOP_EXTENSION_COMMAND = "extension-management"


_WIRE_BUDGET_REQUEST_ID = "00000000-0000-4000-8000-000000000000"


_WIRE_BUDGET_TURN_ID = "00000000000040008000000000000000"


@dataclass
class _TurnWork:
    """One session turn: its identity, Stop bookkeeping and every per-turn value.

    The service reads the per-turn values only through ``_running_turn``, which
    is None once the turn finishes, so nothing carries into the next turn.
    """

    session_id: str
    turn_id: str
    parent_request_id: str | None
    task: asyncio.Task
    scope: LocalWorkScope
    done: asyncio.Future[None]
    event_sink: EventSink | None = None
    loop: asyncio.AbstractEventLoop | None = None
    permission_mode: str = "ask"
    document_context: dict[str, Any] | None = None
    references: list[dict[str, Any]] = field(default_factory=list)
    editor_path: str | None = None
    tool_names: dict[str, str] = field(default_factory=dict)
    tool_summaries: dict[str, dict[str, str]] = field(default_factory=dict)
    display_input: object = None
    finished: bool = False
    document_tasks: set[asyncio.Task] = field(default_factory=set)
    stopping: bool = False
    result: dict[str, Any] | None = None
    error: DesktopServiceError | None = None


class _TurnOps:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    @property
    def _running_turn(self) -> _TurnWork | None:
        """The turn now running, or None (also after it finished while a failed Stop keeps the service busy)."""
        owner = self._turn_work
        return owner if owner is not None and not owner.finished else None

    def _on_prompt_persisted(self, session: ChatSession) -> None:
        owner = self._running_turn
        sink = owner.event_sink if owner is not None else None
        if (
            owner is not None and not owner.done.done()
            and owner.session_id == session.session_id and sink is not None
        ):
            try:
                sink("turn.accepted", {
                    "sessionId": owner.session_id, "turnId": owner.turn_id,
                })
            except Exception:
                # A disconnected event stream cannot undo a saved prompt.
                pass
        self._session_saved = True

    def _validation_error_dtos(self, errors: list[Any]) -> list[str]:
        return [
            truncate_utf8(str(item), 4_096)
            for item in errors[:128]
            if str(item)
        ]

    def _validate_turn_result_shape(
        self,
        *,
        session_id: str,
        text: str,
        validation_errors: list[str],
        tool_summaries: list[dict[str, str]],
    ) -> None:
        """Validate the complete terminal result shape before persistence."""
        candidate = {
            "sessionId": session_id,
            "turnId": _WIRE_BUDGET_TURN_ID,
            "turnNumber": 4_096,
            "state": "completed",
            "accepted": True,
            "persisted": True,
            "text": text,
            "validationErrors": validation_errors,
            "toolSummaries": tool_summaries,
            "responseKind": "answer",
        }
        try:
            success_result(
                _WIRE_BUDGET_REQUEST_ID,
                "session.turn",
                candidate,
            )
        except ProtocolError as exc:
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The finalized answer did not match the desktop response schema.",
            ) from exc

    def _validate_final_text_before_record(
        self,
        session_id: str,
        text: str,
        errors: list[str],
    ) -> None:
        self._validate_turn_result_shape(
            session_id=session_id,
            text=text,
            validation_errors=self._validation_error_dtos(errors),
            tool_summaries=self._running_turn_summaries(),
        )

    async def _session_turn(
        self, params: dict[str, Any], event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_session()
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN", "Another session turn is already active.", retryable=True
            )
        if self._knowledge_active:
            raise DesktopServiceError(
                "BUSY_KNOWLEDGE_MUTATION",
                "A knowledge operation is already active.",
                retryable=True,
            )
        if self._extension_active:
            raise DesktopServiceError(
                "BUSY_EXTENSION_OPERATION",
                "An extension operation is already active.",
                retryable=True,
            )
        self._turn_active = True
        task = asyncio.current_task()
        parent_request_id = getattr(event_sink, "request_id", None)
        owner = _TurnWork(
            session.session_id, params["turnId"],
            parent_request_id if isinstance(parent_request_id, str) else None, task,
            LocalWorkScope(), asyncio.get_running_loop().create_future(),
            event_sink=event_sink, loop=asyncio.get_running_loop(),
            permission_mode=self._permission_mode, display_input=params.get("text"),
        )
        self._turn_work = owner
        response = None
        failure = None
        try:
            response = await self._run_session_turn(params, event_sink, session, owner)
        except asyncio.CancelledError:
            self._request_turn_stop(owner)
            failure = DesktopServiceError("TURN_CANCELLED", "The current turn was stopped.")
        except Exception as exc:
            failure = exc
        finally:
            cleanup = asyncio.create_task(self._finish_turn_work(owner))
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    self._request_turn_stop(owner)
                    if response is None and failure is None:
                        failure = DesktopServiceError("TURN_CANCELLED", "The current turn was stopped.")
                except Exception:
                    break
            try:
                cleanup.result()
            except Exception as exc:
                owner.error = self._stop_cleanup_error(exc)
                failure = exc
            lifecycle = self._with_turn_lifecycle(
                DesktopServiceError("TURN_CANCELLED", "The current turn was stopped."),
                "session.turn", params,
            ).details
            owner.result = {
                "sessionId": session.session_id, "turnId": owner.turn_id,
                **({key: response[key] for key in ("state", "accepted", "persisted")}
                   if response is not None else lifecycle),
            }
            if owner.result["state"] == "pending":
                owner.error = DesktopServiceError(
                    "INTERNAL_ERROR", "The turn has not reached a saved terminal state.",
                    details=lifecycle,
                )
            self._complete_pending_approval(False)
            # Discard the whole per-turn record; the next turn starts a new one.
            owner.finished = True
            self._turn_active = owner.error is not None

            if not owner.done.done():
                owner.done.set_result(None)
        if failure is not None:
            raise failure
        return response

    async def _run_session_turn(
        self, params: dict[str, Any], event_sink: EventSink | None, session: ChatSession,
        owner: _TurnWork,
    ) -> dict[str, Any]:
        turn_id = owner.turn_id
        with owner.scope.bind():
            submitted_context, original_turn = await self._submitted_turn_context(session, params)
            if submitted_context is not None:
                params = {**params, "skillReferences": submitted_context["skillReferences"]}
                if "documentContext" in submitted_context:
                    params["documentContext"] = submitted_context["documentContext"]
                owner.references = copy.deepcopy(submitted_context["references"])
            context_options = {"submitted_context": submitted_context} if submitted_context is not None else {}
            original_text = params["text"]
            try:
                references = resolve_skill_references(original_text, session.loaded_skills, params.get("skillReferences"))
                for name in dict.fromkeys(reference["name"] for reference in references):
                    try:
                        session.skill_runtime_for(name)
                    except (KeyError, ValueError, OSError) as exc:
                        raise ValueError(f"Cannot load selected skill {name}: {exc}") from exc
            except ValueError as exc:
                raise DesktopServiceError("PROTOCOL_INVALID", str(exc)) from exc
            turn_text = original_text
            turn_skill_name: str | None = None
            try:
                parsed = parse_slash_command(original_text)
            except SlashCommandError as exc:
                raise DesktopServiceError(
                    "PROTOCOL_INVALID",
                    truncate_utf8(str(exc), 4_096),
                ) from exc

            if parsed is not None:
                registry = self._session_slash_registry(session)
                command = registry.get(parsed.name)
                if command is None:
                    raise DesktopServiceError(
                        "PROTOCOL_INVALID",
                        f"Unknown slash command: /{truncate_utf8(parsed.name, 256)}",
                    )
                completed_citation = False
                if command.name == "citation":
                    snapshot = await run_local_work(
                        self._conversation_repository.load_optional, session.session_id,
                    )
                    completed_citation = snapshot is not None and any(
                        turn.turn_id == turn_id and turn.state == "completed"
                        for turn in snapshot.document.turns
                    )
                # A candidate only defers runtime eligibility. turn_outcome still
                # checks the full canonical identity and fingerprint under its lock.
                if (
                    parsed.name.casefold() != command.name.casefold()
                    or (not completed_citation
                        and not self._desktop_command_eligible(command, session))
                ):
                    raise DesktopServiceError(
                        "PROTOCOL_INVALID",
                        "That slash command is not available in the desktop composer.",
                    )
                if command.skill_name is not None or command.name == "citation":
                    try:
                        result = await execute_slash_command(
                            parsed,
                            SlashCommandContext(
                                session=session,
                                registry=registry,
                            ),
                        )
                    except SlashCommandError as exc:
                        raise DesktopServiceError(
                            "PROTOCOL_INVALID",
                            truncate_utf8(str(exc), 4_096),
                        ) from exc
                    if command.name == "citation" and result.followup_input is None:
                        raise DesktopServiceError(
                            "PROTOCOL_INVALID", truncate_utf8(result.message, 4_096),
                        )
                    if (
                        result.should_exit
                        or result.clear_screen
                        or not isinstance(result.followup_input, str)
                        or not result.followup_input.strip()
                        or result.skill_name != (command.skill_name or "citation")
                    ):
                        raise DesktopServiceError(
                            "PROTOCOL_INVALID",
                            "That Skill command returned an unsupported result.",
                        )
                    turn_text = result.followup_input
                    turn_skill_name = result.skill_name
                else:
                    async def execute_local_command() -> object:
                        if command.name in _DESKTOP_KNOWLEDGE_COMMANDS:
                            return await self._execute_desktop_knowledge_command(
                                session,
                                parsed,
                            )
                        if command.name == _DESKTOP_EXTENSION_COMMAND:
                            return await self._execute_desktop_extension_command(parsed)
                        return await execute_slash_command(
                            parsed,
                            SlashCommandContext(
                                session=session,
                                registry=registry,
                            ),
                        )

                    def render_local_command(value: object) -> str:
                        if not isinstance(value, SlashCommandResult):
                            raise DesktopServiceError(
                                "INTERNAL_ERROR",
                                "The slash command returned an invalid result.",
                            )
                        result = value
                        if (
                            result.should_exit
                            or result.clear_screen
                            or result.followup_input is not None
                        ):
                            raise DesktopServiceError(
                                "PROTOCOL_INVALID",
                                "That slash-command result is not supported by the desktop composer.",
                            )
                        message = truncate_utf8(
                            str(result.message),
                            _MAX_LOCAL_COMMAND_BYTES,
                        )
                        if not message.strip():
                            raise DesktopServiceError(
                                "PROTOCOL_INVALID",
                                "The slash command returned no displayable result.",
                            )
                        return message

                    try:
                        _result, outcome = await session.run_display_only_turn(
                            original_text,
                            execute_local_command,
                            render_local_command,
                            turn_id=turn_id,
                            retry=params["retry"],
                            **context_options,
                        )
                    except SlashCommandError as exc:
                        raise DesktopServiceError(
                            "PROTOCOL_INVALID",
                            truncate_utf8(str(exc), 4_096),
                        ) from exc
                    if (
                        outcome.turn_id != turn_id
                        or not 1 <= outcome.turn_number <= 4_096
                        or outcome.state != "completed"
                        or outcome.accepted is not True
                        or outcome.persisted is not True
                        or not isinstance(outcome.text, str)
                        or not outcome.text.strip()
                        or len(outcome.text.encode("utf-8"))
                        > _MAX_LOCAL_COMMAND_BYTES
                    ):
                        raise DesktopServiceError(
                            "INTERNAL_ERROR",
                            "The session returned an invalid durable command result.",
                        )
                    response = {
                        "sessionId": session.session_id,
                        "turnId": outcome.turn_id,
                        "turnNumber": outcome.turn_number,
                        "state": outcome.state,
                        "accepted": outcome.accepted,
                        "persisted": outcome.persisted,
                        "text": outcome.text,
                        "validationErrors": [],
                        "toolSummaries": [],
                        "responseKind": "command",
                    }
                    if command.name == _DESKTOP_EXTENSION_COMMAND:
                        response["extensionAction"] = self._desktop_extension_action(parsed)
                    return response

            read_only_turn = any(
                name in READ_ONLY_DOCUMENT_SKILLS
                for name in (*(reference["name"] for reference in references), turn_skill_name)
            )
            if "documentContext" in params:
                document_context = self._documents.resolve_range(
                    params["documentContext"], original_text, require_available=submitted_context is None,
                )
                owner.document_context = document_context
                owner.editor_path = document_context["path"]
                turn_text += (
                    f"\n\n{SNAPSHOT_HEADER}\n"
                    + json.dumps(document_context, ensure_ascii=False, sort_keys=True)
                    + (_READ_ONLY_SNAPSHOT_INSTRUCTIONS if read_only_turn else _EDITABLE_SNAPSHOT_INSTRUCTIONS)
                )
                if len(turn_text.encode("utf-8")) > MAX_INPUT_BYTES:
                    raise DocumentError("The prompt plus document snapshot exceeds the existing 1 MiB turn limit; select a smaller document.")
            if owner.references:
                turn_text += (
                    f"\n\n{FROZEN_REFERENCES_HEADER}\n"
                    + json.dumps(
                        _model_reference_projection(owner.references, owner.document_context),
                        ensure_ascii=False, sort_keys=True,
                    )
                    + (_READ_ONLY_REFERENCE_INSTRUCTIONS if read_only_turn else _EDITABLE_REFERENCE_INSTRUCTIONS)
                )
            if original_turn is not None and original_turn.semantic_input is not None and (
                submitted_context is not None or (params["retry"] and "documentContext" not in params)
            ):
                turn_text = original_turn.semantic_input
            if len(turn_text.encode("utf-8")) > MAX_INPUT_BYTES:
                raise DocumentError("The prompt and frozen sources exceed the existing 1 MiB turn limit; remove references or use a smaller source. Your draft is retained.")
            skill_options = {"skill_references": params["skillReferences"]} if "skillReferences" in params else {}
            skill_options.update(context_options)
            document_turn = owner.document_context is not None
            # A document turn runs in normal thinking without changing the user's selection.
            skill_options["options"] = TurnOptions(
                document_turn=document_turn,
                thinking_mode="normal" if document_turn else None,
                permission_mode=owner.permission_mode,
            )
            if turn_skill_name is None:
                outcome = await session.turn_outcome(
                    turn_text,
                    display_input=original_text,
                    turn_id=turn_id,
                    retry=params["retry"],
                    **skill_options,
                )
            else:
                outcome = await session.turn_outcome(
                    turn_text,
                    display_input=original_text,
                    turn_id=turn_id,
                    skill_name=turn_skill_name,
                    retry=params["retry"],
                    **skill_options,
                )
            if (
                outcome.turn_id != turn_id
                or not 1 <= outcome.turn_number <= 4_096
                or outcome.state != "completed"
                or outcome.accepted is not True
                or outcome.persisted is not True
            ):
                raise DesktopServiceError(
                    "INTERNAL_ERROR",
                    "The session returned an invalid durable turn result.",
                )
            if not isinstance(outcome.text, str) or not outcome.text.strip():
                raise DesktopServiceError(
                    "INTERNAL_ERROR", "The session returned no displayable answer."
                )
            validation_errors = self._validation_error_dtos(
                outcome.validation_errors
            )
            tool_summaries = self._running_turn_summaries()
            self._validate_turn_result_shape(
                session_id=session.session_id,
                text=outcome.text,
                validation_errors=validation_errors,
                tool_summaries=tool_summaries,
            )
            return {
                "sessionId": session.session_id,
                "turnId": outcome.turn_id,
                "turnNumber": outcome.turn_number,
                "state": outcome.state,
                "accepted": outcome.accepted,
                "persisted": outcome.persisted,
                "text": outcome.text,
                "validationErrors": validation_errors,
                "toolSummaries": tool_summaries,
                "responseKind": "answer",
            }

    def _request_turn_stop(self, owner: _TurnWork) -> None:
        owner.stopping = True
        owner.scope.request_stop()
        for candidate in self._document_candidates.values():
            if candidate.turn_id == owner.turn_id and candidate.parent_request_id == owner.parent_request_id:
                candidate.stopped = True
        if self._turn_work is owner:
            self._complete_pending_approval(False)

    async def _finish_turn_work(self, owner: _TurnWork) -> None:
        self._complete_pending_approval(False)
        if owner.document_tasks:
            await asyncio.gather(*tuple(owner.document_tasks), return_exceptions=True)
        await owner.scope.finish_stop()

    async def _session_stop(
        self, params: dict[str, Any], _event_sink: EventSink | None,
    ) -> dict[str, Any]:
        def matches(owner: _TurnWork | None) -> bool:
            return owner is not None and (
                owner.session_id == params["sessionId"]
                and owner.turn_id == params["turnId"]
                and owner.parent_request_id == params["parentRequestId"]
            )

        owner = self._turn_work if matches(self._turn_work) else self._last_stopped_turn
        if not matches(owner):
            raise DesktopServiceError("PROTOCOL_INVALID", "Stop does not match the owning turn request.")
        self._last_stopped_turn = owner
        # A turn already over when this Stop arrives can only be held by an
        # earlier failed cleanup or an unsettled state: this Stop retries it.
        retrying = owner.done.done()
        if not owner.done.done() and not owner.stopping:
            self._request_turn_stop(owner)
            owner.task.cancel()
        await asyncio.shield(owner.done)
        if owner.error is not None:
            if not retrying:
                raise owner.error
            # Retry Stop (FAIL-022, U14): retry the cleanup instead of replaying its error.
            await self._retry_stop(owner)
        return dict(owner.result)

    def _stop_cleanup_error(self, exc: BaseException) -> DesktopServiceError:
        return DesktopServiceError(
            "INTERNAL_ERROR",
            truncate_utf8(f"The turn's local work could not finish stopping: {exc}", 1_024),
        )

    async def _retry_stop(self, owner: _TurnWork) -> None:
        """Release a turn held by a failed Stop only once it is really over.

        Supported use: Stop's cleanup failed (or the turn was left pending) and
        the user presses Stop again. The service stays busy unless the cleanup
        now succeeds and the turn is saved in a terminal state, or it was never
        accepted. A pending turn is finished through ``reload_and_recover``.
        """
        try:
            await self._finish_turn_work(owner)
        except Exception as exc:
            owner.error = self._stop_cleanup_error(exc)
            raise owner.error from exc
        state, accepted, persisted = await self._read_stopped_turn_state(owner)
        if state == "pending":
            session = self.session
            if session is None or session.session_id != owner.session_id:
                raise owner.error
            try:
                await asyncio.to_thread(session.reload_and_recover)
            except ConversationError as exc:
                raise owner.error from exc
            state, accepted, persisted = await self._read_stopped_turn_state(owner)
        settled = state in {"completed", "failed", "interrupted"}
        never_accepted = (
            state is None and not accepted and not persisted
            and owner.result is not None and owner.result.get("accepted") is False
            and owner.result.get("persisted") is False
        )
        if not (settled or never_accepted):
            raise owner.error
        owner.error = None
        owner.result = {
            "sessionId": owner.session_id, "turnId": owner.turn_id,
            "state": state, "accepted": accepted, "persisted": persisted,
        }
        if self._turn_work is owner:
            self._turn_active = False

    async def _read_stopped_turn_state(self, owner: _TurnWork) -> tuple[str | None, bool, bool]:
        try:
            return await asyncio.to_thread(self._saved_turn_state, owner)
        except (ConversationError, DesktopServiceError) as exc:
            # The turn stays blocked: its saved state cannot be determined.
            raise DesktopServiceError(
                "INTERNAL_ERROR", "The stopped turn's saved state could not be read; the conversation stays blocked.",
            ) from exc

    def _saved_turn_state(self, owner: _TurnWork) -> tuple[str | None, bool, bool]:
        """The turn's state read from disk; a read failure propagates (and keeps Stop blocked)."""
        repository = self._conversation_repository
        if repository is None:
            raise DesktopServiceError("SESSION_NOT_READY", "The conversation history is not open.")
        snapshot = repository.load_optional(owner.session_id)
        turn = None if snapshot is None else next(
            (
                item for item in snapshot.document.turns
                if item.turn_id == owner.turn_id and item.display_input == owner.display_input
            ),
            None,
        )
        if turn is None:
            return None, False, False
        return turn.state, True, True

    def _running_turn_summaries(self) -> list[dict[str, str]]:
        turn = self._running_turn
        return list(turn.tool_summaries.values())[:512] if turn is not None else []

    def _on_session_progress(self, node_name: str, new_messages: list[Any]) -> None:
        turn = self._running_turn
        sink = turn.event_sink if turn is not None else None
        if turn is None or sink is None:
            return
        sink("stage.changed", {"stage": str(node_name)})
        for message in new_messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    name = str(call.get("name", "")).strip()
                    call_id = str(call.get("id", "")).strip()
                    if not name:
                        continue
                    name = truncate_utf8(name, 256)
                    call_id = truncate_utf8(call_id, 256) if call_id else ""
                    if call_id:
                        turn.tool_names[call_id] = name
                    data: dict[str, Any] = {"name": name, "status": "started"}
                    if call_id:
                        data["callId"] = call_id
                    sink("tool.started", data)
                continue
            if not isinstance(message, ToolMessage):
                continue
            call_id = str(message.tool_call_id or "").strip()
            name = str(message.name or turn.tool_names.get(call_id, "")).strip()
            if not name:
                continue
            name = truncate_utf8(name, 256)
            call_id = truncate_utf8(call_id, 256) if call_id else ""
            status = self._tool_message_status(message)
            summary: dict[str, str] = {"name": name, "status": status}
            if call_id:
                summary["callId"] = call_id
            turn.tool_summaries[call_id or f"{name}:{len(turn.tool_summaries)}"] = summary
            sink(
                "tool.failed" if status in {"failed", "denied"} else "tool.finished",
                dict(summary),
            )

    @staticmethod
    def _tool_message_status(message: ToolMessage) -> str:
        text = content_text(message.content)
        if getattr(message, "status", None) == "error":
            if "tool not available in the current mode" in text.casefold():
                return "denied"
            return "failed"
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict) and payload.get("approved") is False:
            return "denied"
        return "ok"
