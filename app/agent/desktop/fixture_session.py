"""Isolated no-provider session fixture for the Phase 02 desktop journey."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from langchain_core.messages import AIMessage, ToolMessage

from agent.config import AgentConfig
from agent.conversations import (
    ConversationConflictError,
    ConversationError,
    ConversationRepository,
    ConversationSnapshot,
    FailureInfo,
    InvalidTransitionError,
    ToolActivitySummary,
    is_canonical_uuid4_hex,
)
from agent.desktop.catalog import (
    CATALOG_FILENAME,
    CatalogMalformedError,
    CatalogUnavailableError,
    DesktopProjectCatalog,
)
from agent.desktop.service import DesktopKnowledgeOperations, DesktopService
from agent.extensions.manager import ExtensionManager
from agent.extensions.startup import load_extension_startup
from agent.tools.bash import create_bash_tool
from agent.turns.memory import TurnRecord
from agent.turns.plan_log import PlanLog
from agent.turns.results import TurnOutcome


FIXTURE_MODE_ENV = "RESEARCH_AGENT_DESKTOP_FIXTURE"
FIXTURE_ROOT_ENV = "RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT"
FIXTURE_MODE = "phase02"
FIXTURE_ROOT_PREFIX = "research-agent-desktop-phase02-"
FIXTURE_KNOWLEDGE_DIRNAME = "knowledge-source"
FIXTURE_BLOCK_INIT_MARKER = ".fixture-block-init"
FIXTURE_CHANGED_ORPHAN_MARKER = ".fixture-changed-orphans"
FIXTURE_LONG_OUTPUT_MARKER = ".fixture-long-output"
FIXTURE_RAG_QUESTION = "What does the fixture knowledge say?"
FIXTURE_DELAYED_FINAL = "[[fixture:delayed-final]]"
FIXTURE_BASH_APPROVE = "[[fixture:bash-approve]]"
FIXTURE_BASH_DENY = "[[fixture:bash-deny]]"
FIXTURE_PRIVATE_SKILL_DIRNAME = "fixture-extension-management"

SESSION_A = "28b222e0cc6543aa8d7bbdc423de99a7"
SESSION_B = "f2ddf2369f994905afa0b85d8cca79b1"
SESSION_C = "7a9708991f8f420bbdadc3e430a78c10"

_SEED_TURNS = {
    SESSION_A: ("A seed question", "A seed answer"),
    SESSION_B: ("B seed question", "B seed answer"),
    SESSION_C: ("C seed question", "C seed answer"),
}
_FIXTURE_TIMESTAMP = datetime(2026, 8, 28, 2, 30, tzinfo=timezone.utc)
_MAX_CONTEXT_CHARS = 2_048


class FixtureConfigurationError(RuntimeError):
    """The explicitly requested fixture root is missing or unsafe."""


class FixtureProviderError(RuntimeError):
    """A bounded synthetic provider failure used only by this fixture."""

    def __init__(self, status_code: int) -> None:
        super().__init__("synthetic fixture provider failure")
        self.status_code = status_code


class FixtureExtensionProvider:
    """Deterministic manager response with a visible no-network call count."""

    def __init__(self) -> None:
        self.calls = 0

    def model_factory(self, _config: AgentConfig) -> "FixtureExtensionProvider":
        self.calls += 1
        return self

    def invoke(self, messages: list[Any]) -> AIMessage:
        content = str(messages[-1].content)
        payload = json.loads(content[content.index("{") :])
        items = []
        for change in payload["authoritative_changes"]:
            operation = change["operation"]
            blocked = operation in {"blocked", "guarded"}
            items.append({
                "key": change["key"],
                "operation": operation,
                "decision": "block" if blocked else "apply",
                "summary": f"Fixture accepts validated {operation}.",
                "reason": change["reason"] if blocked else None,
                "mcp_descriptor": None,
            })
        return AIMessage(content=json.dumps({"items": items}))


class FixtureBashRunner:
    """Record approved commands and return output without starting a process."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args[0] if args else "",
            returncode=0,
            stdout="fixture bash runner output\n",
            stderr="",
        )


def require_fixture_root(environ: Mapping[str, str]) -> Path:
    """Return a narrowly constrained caller-created temporary directory."""
    raw = environ.get(FIXTURE_ROOT_ENV, "")
    if not raw:
        raise FixtureConfigurationError(
            f"{FIXTURE_ROOT_ENV} is required for the Phase 02 fixture"
        )
    candidate = Path(raw)
    if not candidate.is_absolute() or candidate.is_symlink():
        raise FixtureConfigurationError("fixture root must be an absolute non-symlink")
    try:
        resolved = candidate.resolve(strict=True)
        stat = resolved.stat()
    except OSError as exc:
        raise FixtureConfigurationError("fixture root is unavailable") from exc
    temporary_root = Path("/tmp").resolve(strict=True)
    if (
        not resolved.is_dir()
        or resolved.parent != temporary_root
        or not resolved.name.startswith(FIXTURE_ROOT_PREFIX)
        or stat.st_uid != os.getuid()
    ):
        raise FixtureConfigurationError(
            "fixture root must be an owned direct child of /tmp with the fixture prefix"
        )
    return resolved


def _fixture_session_id(index: int) -> str:
    digest = bytearray(
        hashlib.sha256(f"desktop-phase02-session-{index}".encode("ascii")).digest()[:16]
    )
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return digest.hex()


def _timestamp(turn_id: int) -> str:
    return (
        _FIXTURE_TIMESTAMP + timedelta(seconds=turn_id)
    ).isoformat().replace("+00:00", "Z")


def _plan_log(config: AgentConfig, session_id: str) -> PlanLog:
    return PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: Path("/"),
    )


def _seed_plan_turn(config: AgentConfig, session_id: str, user: str, answer: str) -> None:
    log_dir = Path(config.plan_logs_dir)
    if any(log_dir.glob(f"plan-{session_id}-*.md")):
        return
    plan_log = _plan_log(config, session_id)
    path = plan_log.new_log_file()
    plan_log.append_block(
        str(path),
        plan_log.render_block(
            turn_id=1,
            timestamp=_timestamp(1),
            user_input=user,
            answer=answer,
            new_messages=[],
            tool_calls=[],
        ),
    )


def _seed_fixture_extensions(root: Path) -> Path:
    """Create deterministic desired bundles and a private manager Skill."""
    private_root = root / FIXTURE_PRIVATE_SKILL_DIRNAME
    skill_bundle = root / "extensions" / "desired" / "skill" / "fixture-writer"
    mcp_bundle = root / "extensions" / "desired" / "mcp" / "fixture-clock"
    directories = (private_root, skill_bundle, mcp_bundle)
    if any(path.is_symlink() for path in directories):
        raise FixtureConfigurationError("fixture extension roots must not be symlinks")
    for path in directories:
        path.mkdir(parents=True, exist_ok=True)

    files = {
        private_root / "SKILL.md": (
            "---\n"
            "name: extension-management\n"
            "description: Deterministic private fixture extension planner.\n"
            "---\n\n"
            "Return one JSON plan item for every authoritative host change.\n"
        ),
        skill_bundle / "SKILL.md": (
            "---\n"
            "name: fixture-writer\n"
            "description: Deterministic applied Skill for desktop fixture verification.\n"
            "---\n\n"
            "Use only for the isolated desktop fixture.\n"
        ),
        mcp_bundle / "server": (
            "#!/bin/sh\n"
            "# This fixture executable is resolved and copied but never launched.\n"
            "exit 0\n"
        ),
        mcp_bundle / "extension.yaml": (
            "schema_version: 1\n"
            "kind: mcp\n"
            "id: fixture-clock\n"
            "family: fixture-clock\n"
            "scope: global\n"
            "runtime:\n"
            "  transport: stdio\n"
            "  command: ./server\n"
            "  args:\n"
            "    - --stdio\n"
            "  cwd: .\n"
            "environment:\n"
            "  FIXTURE_MODE:\n"
            "    value: deterministic\n"
        ),
    }
    for path, content in files.items():
        if path.is_symlink():
            raise FixtureConfigurationError("fixture extension files must not be symlinks")
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    server = mcp_bundle / "server"
    server.chmod(0o755)
    return private_root / "SKILL.md"


def seed_fixture_root(root: Path) -> AgentConfig:
    """Seed only the production catalog and canonical plan-log formats."""
    persist_dir = root / "store"
    plan_logs_dir = root / "plan_logs"
    guarded_paths = (
        persist_dir,
        persist_dir / "chat_history",
        plan_logs_dir,
        root / "skills",
        root / "extensions",
        root / "extensions" / "desired",
        root / "extensions" / "state",
        root / FIXTURE_PRIVATE_SKILL_DIRNAME,
        root / "citations",
        root / FIXTURE_KNOWLEDGE_DIRNAME,
    )
    if any(path.is_symlink() for path in guarded_paths):
        raise FixtureConfigurationError("fixture child roots must not be symlinks")
    persist_dir.mkdir(exist_ok=True)
    plan_logs_dir.mkdir(exist_ok=True)
    knowledge_source = root / FIXTURE_KNOWLEDGE_DIRNAME
    knowledge_source.mkdir(exist_ok=True)
    knowledge_document = knowledge_source / "fixture-notes.md"
    if knowledge_document.is_symlink():
        raise FixtureConfigurationError("fixture knowledge files must not be symlinks")
    if not knowledge_document.exists():
        knowledge_document.write_text(
            "The fixture knowledge answer is local and deterministic.\n",
            encoding="utf-8",
        )
    catalog_path = persist_dir / CATALOG_FILENAME
    if catalog_path.is_symlink() or any(
        path.is_symlink() for path in plan_logs_dir.iterdir()
    ):
        raise FixtureConfigurationError("fixture persistence files must not be symlinks")
    if not catalog_path.exists():
        catalog_path.write_text(
            json.dumps({
                "projects": [
                    {
                        "projectId": "p1",
                        "name": "Project One",
                        "sessionIds": [SESSION_A, SESSION_B],
                    },
                    {
                        "projectId": "p2",
                        "name": "Project Two",
                        "sessionIds": [SESSION_C],
                    },
                ]
            }, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    config = AgentConfig(
        persist_dir=str(persist_dir),
        plan_logs_dir=str(plan_logs_dir),
        skills_dir=str(root / "skills"),
        extension_dropin_dir=str(root / "extensions" / "desired"),
        extension_state_dir=str(root / "extensions" / "state"),
        citation_output_dir=str(root / "citations"),
    )
    _seed_fixture_extensions(root)
    for session_id, (user, answer) in _SEED_TURNS.items():
        _seed_plan_turn(config, session_id, user, answer)
    return config


def _fixture_search(query: str) -> list[dict[str, str]]:
    """Return one deterministic hit through the fake agent/search seam."""
    return [
        {
            "pid": "fixture-knowledge",
            "file_path": "fixture-notes.md",
            "text": f"Local fixture result for: {query}",
        }
    ]


class FixtureKnowledgeOperations:
    """In-memory Knowledge handlers limited to the fixture source directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.source_root = (root / FIXTURE_KNOWLEDGE_DIRNAME).resolve(strict=True)
        self.calls: list[tuple[str, str]] = []
        self._orphans = ["removed-from-disk.md"]
        self._changed_orphan_pruned = False

    def _target(self, target: Path) -> Path:
        resolved = target.resolve(strict=True)
        if resolved != self.source_root and not resolved.is_relative_to(
            self.source_root
        ):
            raise ValueError("fixture knowledge target is outside its source root")
        return resolved

    def _current_orphans(self) -> list[str]:
        orphans = list(self._orphans)
        if (
            not self._changed_orphan_pruned
            and (self.source_root / FIXTURE_CHANGED_ORPHAN_MARKER).is_file()
        ):
            orphans.append("changed-after-preview.md")
        return orphans

    async def init_workspace(
        self,
        _config: AgentConfig,
    ) -> tuple[int, int, Path, set[str]]:
        self.calls.append(("init", str(self.source_root)))
        if (self.source_root / FIXTURE_BLOCK_INIT_MARKER).is_file():
            await asyncio.sleep(1.5)
        return 1, 1, self.root, {"app"}

    async def ingest_file(
        self,
        target: Path,
        _config: AgentConfig,
    ) -> tuple[str, int]:
        resolved = self._target(target)
        if not resolved.is_file():
            raise ValueError("fixture file target is invalid")
        self.calls.append(("ingest_file", str(resolved)))
        return "fixture-file-pid", 1

    async def ingest_folder(
        self,
        target: Path,
        _config: AgentConfig,
    ) -> tuple[int, int]:
        resolved = self._target(target)
        if not resolved.is_dir():
            raise ValueError("fixture folder target is invalid")
        self.calls.append(("ingest_folder", str(resolved)))
        return 1, 1

    async def diff_folder(
        self,
        target: Path,
        _config: AgentConfig,
    ) -> dict[str, list[str]]:
        resolved = self._target(target)
        if not resolved.is_dir():
            raise ValueError("fixture sync target is invalid")
        self.calls.append(("diff", str(resolved)))
        on_disk = sorted(
            str(path.relative_to(resolved))
            for path in resolved.rglob("*.md")
            if path.is_file()
        )
        if (self.source_root / FIXTURE_LONG_OUTPUT_MARKER).is_file():
            on_disk.extend(
                f"long-output/nested-research-document-{index:03}.md"
                for index in range(80)
            )
        return {
            "missing_from_store": on_disk,
            "missing_from_disk": self._current_orphans(),
        }

    async def prune_folder(
        self,
        target: Path,
        _config: AgentConfig,
    ) -> list[str]:
        resolved = self._target(target)
        self.calls.append(("prune", str(resolved)))
        orphans = self._current_orphans()
        removed = [f"fixture:{path}" for path in orphans]
        self._orphans.clear()
        if "changed-after-preview.md" in orphans:
            self._changed_orphan_pruned = True
        return removed

    def as_operations(self) -> DesktopKnowledgeOperations:
        return DesktopKnowledgeOperations(
            init_workspace=self.init_workspace,
            ingest_file=self.ingest_file,
            ingest_folder=self.ingest_folder,
            diff_folder=self.diff_folder,
            prune_folder=self.prune_folder,
        )


class FixtureSession:
    """Deterministic ChatSession-shaped implementation with no model/provider."""

    def __init__(
        self,
        config: AgentConfig,
        *,
        session_id: str,
        conversation_repository: ConversationRepository,
        project_id: str,
        progress_cb: Callable[[str, list[Any]], None] | None,
        search_handler: Callable[[str], list[dict[str, str]]],
        bash_approval_handler: Callable[[str, str, int], bool] | None,
        bash_command_runner: Callable[..., Any] | None,
    ) -> None:
        self.config = config
        self.session_id = session_id
        self.project_id = project_id
        self.conversation_repository = conversation_repository
        self._conversation_snapshot = self._load_snapshot()
        self._recover_interrupted_turn()
        self.thinking_mode = "normal"
        startup = load_extension_startup(config, env={})
        self.loaded_skills = list(startup.skills)
        self.mcp_families = {
            spec.name: spec.family for spec in startup.mcp_specs
        }
        self.running_extension_revision = startup.revision
        self.extension_startup_diagnostics = startup.diagnostics
        self.plan_mode = False
        self.plan_log_path: Path | None = None
        self._progress_cb = progress_cb
        self._search_handler = search_handler
        self._bash_tool = (
            create_bash_tool(
                config,
                approval_handler=bash_approval_handler,
                command_runner=bash_command_runner,
            )
            if bash_approval_handler is not None and bash_command_runner is not None
            else None
        )

    @property
    def recent_turns(self) -> list[Any]:
        """Return a process-local view rebuilt only from canonical JSON."""
        snapshot = self._conversation_snapshot
        return list(snapshot.document.turns) if snapshot is not None else []

    @property
    def _turn_count(self) -> int:
        snapshot = self._conversation_snapshot
        return len(snapshot.document.turns) if snapshot is not None else 0

    def _load_snapshot(self) -> ConversationSnapshot | None:
        snapshot = self.conversation_repository.load_optional(self.session_id)
        if snapshot is not None and snapshot.document.project_id != self.project_id:
            raise ConversationConflictError(
                "fixture conversation belongs to a different project"
            )
        return snapshot

    def _recover_interrupted_turn(self) -> None:
        snapshot = self._conversation_snapshot
        if snapshot is None:
            return
        pending = next(
            (turn for turn in snapshot.document.turns if turn.state == "pending"),
            None,
        )
        if pending is None:
            return
        self._conversation_snapshot = self.conversation_repository.fail_turn(
            snapshot,
            turn_id=pending.turn_id,
            state="interrupted",
            failure=FailureInfo(
                code="interrupted",
                message="The previous fixture turn was interrupted.",
                retryable=True,
            ),
            finished_at=snapshot.document.updated_at,
        )

    def _begin_turn(
        self,
        *,
        semantic_input: str | None,
        display_input: str,
        turn_id: str,
        retry: bool,
        kind: str = "conversational",
        context_eligible: bool = True,
    ) -> tuple[ConversationSnapshot, Any, bool]:
        if not is_canonical_uuid4_hex(turn_id):
            raise ValueError("turn_id must be a canonical UUIDv4 hex value")
        self._conversation_snapshot = self._load_snapshot()
        self._recover_interrupted_turn()
        snapshot = self._conversation_snapshot
        values = {
            "turn_id": turn_id,
            "kind": kind,
            "display_input": display_input,
            "semantic_input": semantic_input,
            "context_eligible": context_eligible,
            "thinking_mode": self.thinking_mode if context_eligible else None,
        }
        submitted_at = _timestamp((self._turn_count or 0) + 1)
        if snapshot is None:
            snapshot = self.conversation_repository.create(
                conversation_id=self.session_id,
                project_id=self.project_id,
                submitted_at=submitted_at,
                **values,
            )
            self._conversation_snapshot = snapshot
            return snapshot, snapshot.document.turns[-1], False

        existing = next(
            (turn for turn in snapshot.document.turns if turn.turn_id == turn_id),
            None,
        )
        if existing is not None:
            if existing.state == "completed":
                self.conversation_repository.append_pending(
                    snapshot,
                    submitted_at=existing.submitted_at,
                    **values,
                )
                return snapshot, existing, True
            if not retry:
                raise InvalidTransitionError(
                    "failed or interrupted fixture turn requires an explicit retry"
                )
            snapshot = self.conversation_repository.retry_turn(
                snapshot,
                retry_at=submitted_at,
                **values,
            )
        else:
            snapshot = self.conversation_repository.append_pending(
                snapshot,
                submitted_at=submitted_at,
                **values,
            )
        self._conversation_snapshot = snapshot
        pending = next(
            turn for turn in snapshot.document.turns if turn.turn_id == turn_id
        )
        return snapshot, pending, False

    def _fail_turn(
        self,
        snapshot: ConversationSnapshot,
        *,
        turn_id: str,
        state: str = "failed",
        code: str = "execution_failed",
        message: str = "The fixture turn could not be completed.",
    ) -> None:
        self._conversation_snapshot = self.conversation_repository.fail_turn(
            snapshot,
            turn_id=turn_id,
            state=state,
            failure=FailureInfo(
                code=code,
                message=message,
                retryable=True,
            ),
            finished_at=snapshot.document.updated_at,
        )

    async def turn_outcome(
        self,
        text: str,
        *,
        display_input: str | None = None,
        turn_id: str | None = None,
        skill_name: str | None = None,
        retry: bool = False,
    ) -> TurnOutcome:
        if skill_name is not None and skill_name not in {
            skill.name for skill in self.loaded_skills
        }:
            raise ValueError(f"unknown skill: {skill_name}")
        if turn_id is None:
            raise ValueError("turn_id is required")
        original_input = display_input if display_input is not None else text
        snapshot, pending, duplicate = self._begin_turn(
            semantic_input=text,
            display_input=original_input,
            turn_id=turn_id,
            retry=retry,
        )
        if duplicate:
            assert pending.assistant_output is not None
            return TurnOutcome(
                text=pending.assistant_output,
                turn_id=pending.turn_id,
                turn_number=pending.turn_number,
                state="completed",
                accepted=True,
                persisted=True,
            )

        try:
            if self._progress_cb is not None:
                self._progress_cb("fixture.prepare", [])
            if text == "[[fixture:rate-limit]]":
                raise FixtureProviderError(429)
            if text == "[[fixture:provider-error]]":
                raise FixtureProviderError(503)
            if text == FIXTURE_DELAYED_FINAL:
                await asyncio.sleep(0.05)
                if self._progress_cb is not None:
                    self._progress_cb("fixture.before-old-deadline", [])
                await asyncio.sleep(0.1)
                if self._progress_cb is not None:
                    self._progress_cb("fixture.after-old-deadline", [])
                await asyncio.sleep(2.0)
            if self.thinking_mode == "extended" and self._progress_cb is not None:
                self._progress_cb("fixture.extended.aggregate", [])

            next_turn = pending.turn_number
            context = " | ".join(
                turn.user_input
                for turn in self.conversation_repository.latest_context(snapshot)
            )[:_MAX_CONTEXT_CHARS]
            new_messages: list[Any] = []
            tool_activities: tuple[ToolActivitySummary, ...] = ()
            if text == FIXTURE_RAG_QUESTION:
                hits = self._search_handler(text)
                call_id = "fixture-rag-search"
                call_message = AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "rag_search",
                        "args": {"query": text},
                        "id": call_id,
                        "type": "tool_call",
                    }],
                )
                result_message = ToolMessage(
                    content=json.dumps(hits, ensure_ascii=False),
                    tool_call_id=call_id,
                    name="rag_search",
                    status="success",
                )
                new_messages = [call_message, result_message]
                if self._progress_cb is not None:
                    self._progress_cb("tools", new_messages)
                answer = f"Fixture knowledge says: {hits[0]['text']}"
                tool_activities = (ToolActivitySummary(
                    call_id=call_id,
                    name="rag_search",
                    status="ok",
                    summary="Fixture knowledge search completed.",
                ),)
            elif text in {FIXTURE_BASH_APPROVE, FIXTURE_BASH_DENY}:
                if self._bash_tool is None:
                    raise RuntimeError("fixture Bash seam is unavailable")
                approved_marker = text == FIXTURE_BASH_APPROVE
                command = (
                    "printf fixture-approved"
                    if approved_marker
                    else "printf fixture-denied"
                )
                description = (
                    "Return deterministic fixture output through the fake runner."
                    if approved_marker
                    else "Exercise the deterministic denied Bash path."
                )
                call_id = f"fixture-bash-{next_turn}"
                call_message = AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "bash",
                        "args": {
                            "command": command,
                            "description": description,
                        },
                        "id": call_id,
                        "type": "tool_call",
                    }],
                )
                new_messages.append(call_message)
                if self._progress_cb is not None:
                    self._progress_cb("tools", [call_message])
                raw_result = await asyncio.to_thread(
                    self._bash_tool.invoke,
                    {
                        "command": command,
                        "description": description,
                        "timeout_sec": 5,
                    },
                )
                payload = json.loads(str(raw_result))
                result_message = ToolMessage(
                    content=str(raw_result),
                    tool_call_id=call_id,
                    name="bash",
                    status="success",
                )
                new_messages.append(result_message)
                if self._progress_cb is not None:
                    self._progress_cb("tools", [result_message])
                approved = payload.get("approved") is True
                answer = (
                    "Fixture Bash request was approved and completed through the fake runner."
                    if approved
                    else "Fixture Bash request was denied; the fake runner was not called."
                )
                tool_activities = (ToolActivitySummary(
                    call_id=call_id,
                    name="bash",
                    status="ok" if approved else "denied",
                    summary=(
                        "Fixture Bash request completed."
                        if approved
                        else "Fixture Bash request was denied."
                    ),
                ),)
            elif text == "[[fixture:malicious-content]]":
                answer = (
                    "Fixture content: <script>unsafe()</script> "
                    "[safe](https://example.com) [unsafe](file:///etc/passwd)"
                )
            else:
                mode = "extended" if self.thinking_mode == "extended" else "normal"
                if skill_name is None:
                    answer = (
                        f"Fixture {mode} {self.session_id[:8]} turn {next_turn}: {text}"
                        f"\nContext: {context or '(empty)'}"
                    )
                else:
                    answer = (
                        f"Fixture skill {skill_name} {self.session_id[:8]} "
                        f"turn {next_turn}: {text}"
                        f"\nContext: {context or '(empty)'}"
                    )

            completed = self.conversation_repository.complete_turn(
                snapshot,
                turn_id=turn_id,
                assistant_output=answer,
                tool_activities=tool_activities,
                finished_at=snapshot.document.updated_at,
            )
            self._conversation_snapshot = completed
            if self._progress_cb is not None:
                self._progress_cb("fixture.finalized", [])
            return TurnOutcome(
                text=answer,
                turn_id=turn_id,
                turn_number=pending.turn_number,
                state="completed",
                accepted=True,
                persisted=True,
            )
        except asyncio.CancelledError:
            self._fail_turn(
                snapshot,
                turn_id=turn_id,
                state="interrupted",
                code="cancelled",
                message="The fixture turn was cancelled.",
            )
            raise
        except ConversationError:
            try:
                self._fail_turn(
                    snapshot,
                    turn_id=turn_id,
                    code="persistence_failed",
                    message="The fixture turn could not be saved.",
                )
            except ConversationError:
                pass
            raise
        except Exception:
            self._fail_turn(snapshot, turn_id=turn_id)
            raise

    async def run_display_only_turn(
        self,
        display_input: str,
        action: Callable[[], Any],
        render_result: Callable[[object], str],
        *,
        turn_id: str,
        retry: bool = False,
    ) -> tuple[object | None, TurnOutcome]:
        """Run a deterministic local command through canonical persistence."""
        snapshot, pending, duplicate = self._begin_turn(
            semantic_input=None,
            display_input=display_input,
            turn_id=turn_id,
            retry=retry,
            kind="display-only",
            context_eligible=False,
        )
        if duplicate:
            assert pending.assistant_output is not None
            return None, TurnOutcome(
                text=pending.assistant_output,
                turn_id=pending.turn_id,
                turn_number=pending.turn_number,
                state="completed",
                accepted=True,
                persisted=True,
            )

        try:
            result = await action()
            text = render_result(result)
            if not isinstance(text, str) or not text.strip():
                raise ValueError("display-only result must be nonblank text")
            completed = self.conversation_repository.complete_turn(
                snapshot,
                turn_id=turn_id,
                assistant_output=text,
                finished_at=snapshot.document.updated_at,
            )
            self._conversation_snapshot = completed
            return result, TurnOutcome(
                text=text,
                turn_id=turn_id,
                turn_number=pending.turn_number,
                state="completed",
                accepted=True,
                persisted=True,
            )
        except asyncio.CancelledError:
            self._fail_turn(
                snapshot,
                turn_id=turn_id,
                state="interrupted",
                code="cancelled",
                message="The fixture command was cancelled.",
            )
            raise
        except ConversationError:
            try:
                self._fail_turn(
                    snapshot,
                    turn_id=turn_id,
                    code="persistence_failed",
                    message="The fixture command result could not be saved.",
                )
            except ConversationError:
                pass
            raise
        except Exception:
            self._fail_turn(
                snapshot,
                turn_id=turn_id,
                message="The fixture command could not be completed.",
            )
            raise

    async def enter_plan_mode(self) -> None:
        self.plan_mode = True
        self.plan_log_path = None

    async def resume_plan_mode(self, _log_path: str | Path) -> None:
        self.plan_mode = True
        self.plan_log_path = None

    async def exit_plan_mode(self) -> None:
        self.plan_mode = False
        self.plan_log_path = None

    def set_thinking_mode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        if normalized not in {"normal", "extended"}:
            raise ValueError(f"unknown thinking mode: {mode}")
        self.thinking_mode = normalized

    def status_snapshot(self) -> dict[str, str | int | bool]:
        return {
            "session_id": self.session_id,
            "turn_count": self._turn_count,
            "recent_turn_count": len(self.recent_turns),
            "graph_recursion_limit": self.config.graph_recursion_limit,
            "last_tool_counts": "none",
            "plan_mode": self.plan_mode,
            "plan_log_path": str(self.plan_log_path or ""),
            "thinking_mode": self.thinking_mode,
            "mcp_families": ",".join(sorted(set(self.mcp_families.values()))) or "none",
            "extension_revision": self.running_extension_revision,
            "extension_diagnostics": ";".join(self.extension_startup_diagnostics),
        }


class FixtureSessionFactory:
    """Allocate deterministic unused session IDs within one fixture process."""

    def __init__(
        self,
        catalog: DesktopProjectCatalog | None,
        search_handler: Callable[[str], list[dict[str, str]]] = _fixture_search,
    ) -> None:
        self._catalog = catalog
        self._search_handler = search_handler
        self._next_index = 0
        self._issued: set[str] = set()

    async def __call__(
        self,
        config: AgentConfig,
        *,
        load_mcp: bool,
        progress_cb: Callable[[str, list[Any]], None] | None,
        conversation_repository: ConversationRepository,
        project_id: str,
        session_id: str | None = None,
        bash_approval_handler: Callable[[str, str, int], bool] | None = None,
        bash_command_runner: Callable[..., Any] | None = None,
    ) -> FixtureSession:
        del load_mcp
        if session_id is None:
            while True:
                candidate = _fixture_session_id(self._next_index)
                self._next_index += 1
                if (
                    candidate not in self._issued
                    and (
                        self._catalog is None
                        or self._catalog.project_for_session(candidate) is None
                    )
                    and conversation_repository.load_optional(candidate) is None
                ):
                    session_id = candidate
                    self._issued.add(candidate)
                    break
        return FixtureSession(
            config,
            session_id=session_id,
            conversation_repository=conversation_repository,
            project_id=project_id,
            progress_cb=progress_cb,
            search_handler=self._search_handler,
            bash_approval_handler=bash_approval_handler,
            bash_command_runner=bash_command_runner,
        )


def build_phase02_fixture_service(
    *,
    original_cwd: Path,
    environ: Mapping[str, str],
) -> DesktopService:
    """Construct the real coordinator around the isolated fake session only."""
    root = require_fixture_root(environ)
    config = seed_fixture_root(root)
    try:
        catalog: DesktopProjectCatalog | None = DesktopProjectCatalog(
            config.persist_dir
        )
    except (CatalogMalformedError, CatalogUnavailableError):
        catalog = None
    sanitized_environ = {
        key: environ[key]
        for key in ("CONDA_DEFAULT_ENV", "CONDA_PREFIX")
        if key in environ
    }
    knowledge_operations = FixtureKnowledgeOperations(root)
    extension_provider = FixtureExtensionProvider()
    extension_manager = ExtensionManager(
        config,
        private_skill_path=root / FIXTURE_PRIVATE_SKILL_DIRNAME / "SKILL.md",
        model_factory=extension_provider.model_factory,
    )
    bash_runner = FixtureBashRunner()
    return DesktopService(
        original_cwd=original_cwd,
        environ=sanitized_environ,
        config=config,
        project_catalog=catalog,
        extension_manager=extension_manager,
        session_factory=FixtureSessionFactory(catalog),
        knowledge_operations=knowledge_operations.as_operations(),
        bash_command_runner=bash_runner,
    )
