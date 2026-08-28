"""Isolated no-provider session fixture for the Phase 02 desktop journey."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from agent.config import AgentConfig
from agent.desktop.catalog import (
    CATALOG_FILENAME,
    CatalogMalformedError,
    CatalogUnavailableError,
    DesktopProjectCatalog,
)
from agent.desktop.service import DesktopService
from agent.turns.memory import TurnRecord
from agent.turns.plan_log import PlanLog
from agent.turns.results import TurnOutcome


FIXTURE_MODE_ENV = "RESEARCH_AGENT_DESKTOP_FIXTURE"
FIXTURE_ROOT_ENV = "RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT"
FIXTURE_MODE = "phase02"
FIXTURE_ROOT_PREFIX = "research-agent-desktop-phase02-"

SESSION_A = "28b222e0cc6543aa8d7bbdc423de99a7"
SESSION_B = "f2ddf2369f994905afa0b85d8cca79b1"
SESSION_C = "7a9708991f8f420bbdadc3e430a78c10"

_SEED_TURNS = {
    SESSION_A: ("A seed question", "A seed answer"),
    SESSION_B: ("B seed question", "B seed answer"),
    SESSION_C: ("C seed question", "C seed answer"),
}
_FIXTURE_TIMESTAMP = datetime(2026, 8, 28, 2, 30, tzinfo=timezone.utc)
_MAX_CONTEXT_ITEMS = 5
_MAX_CONTEXT_CHARS = 2_048


class FixtureConfigurationError(RuntimeError):
    """The explicitly requested fixture root is missing or unsafe."""


class FixtureProviderError(RuntimeError):
    """A bounded synthetic provider failure used only by this fixture."""

    def __init__(self, status_code: int) -> None:
        super().__init__("synthetic fixture provider failure")
        self.status_code = status_code


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
    return (_FIXTURE_TIMESTAMP + timedelta(seconds=turn_id)).isoformat()


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
        root / "citations",
    )
    if any(path.is_symlink() for path in guarded_paths):
        raise FixtureConfigurationError("fixture child roots must not be symlinks")
    persist_dir.mkdir(exist_ok=True)
    plan_logs_dir.mkdir(exist_ok=True)
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
    for session_id, (user, answer) in _SEED_TURNS.items():
        _seed_plan_turn(config, session_id, user, answer)
    return config


class FixtureSession:
    """Deterministic ChatSession-shaped implementation with no model or tools."""

    def __init__(
        self,
        config: AgentConfig,
        *,
        session_id: str,
        restored_turns: list[TurnRecord],
        progress_cb: Callable[[str, list[Any]], None] | None,
    ) -> None:
        self.config = config
        self.session_id = session_id
        self.recent_turns = list(restored_turns)
        self.thinking_mode = "normal"
        self.active_skill_runtime = None
        self.loaded_skills: list[Any] = []
        self.mcp_families: dict[str, str] = {}
        self.running_extension_revision = 0
        self.extension_startup_diagnostics: tuple[str, ...] = ()
        self.plan_mode = False
        self.plan_log_path: Path | None = None
        self._progress_cb = progress_cb
        self._turn_count = max(
            (turn.turn_id for turn in self.recent_turns),
            default=0,
        )
        self._persistence_log_path = self._find_or_create_log()
        self._fail_next_flush = False

    def _find_or_create_log(self) -> Path:
        log_dir = Path(self.config.plan_logs_dir)
        paths = sorted(log_dir.glob(f"plan-{self.session_id}-*.md"))
        if paths:
            return paths[-1]
        return _plan_log(self.config, self.session_id).new_log_file()

    async def turn_outcome(self, text: str) -> TurnOutcome:
        if self._progress_cb is not None:
            self._progress_cb("fixture.prepare", [])
        if text == "[[fixture:rate-limit]]":
            raise FixtureProviderError(429)
        if text == "[[fixture:provider-error]]":
            raise FixtureProviderError(503)
        if self.thinking_mode == "extended" and self._progress_cb is not None:
            self._progress_cb("fixture.extended.aggregate", [])

        next_turn = self._turn_count + 1
        context = " | ".join(
            turn.user_input for turn in self.recent_turns[-_MAX_CONTEXT_ITEMS:]
        )[:_MAX_CONTEXT_CHARS]
        if text == "[[fixture:malicious-content]]":
            answer = (
                "Fixture content: <script>unsafe()</script> "
                "[safe](https://example.com) [unsafe](file:///etc/passwd)"
            )
        else:
            mode = "extended" if self.thinking_mode == "extended" else "normal"
            answer = (
                f"Fixture {mode} {self.session_id[:8]} turn {next_turn}: {text}"
                f"\nContext: {context or '(empty)'}"
            )
        timestamp = _timestamp(next_turn)
        turn = TurnRecord(
            user_input=text,
            assistant_output=answer,
            turn_id=next_turn,
            timestamp=timestamp,
            persist_target="plan_log",
        )
        plan_log = _plan_log(self.config, self.session_id)
        plan_log.append_block(
            str(self._persistence_log_path),
            plan_log.render_block(
                turn_id=next_turn,
                timestamp=timestamp,
                user_input=text,
                answer=answer,
                new_messages=[],
                tool_calls=[],
            ),
        )
        self.recent_turns.append(turn)
        self._turn_count = next_turn
        if text == "[[fixture:flush-failure]]":
            self._fail_next_flush = True
        if self._progress_cb is not None:
            self._progress_cb("fixture.finalized", [])
        return TurnOutcome(text=answer)

    async def flush_recent_turns(self) -> None:
        if self._fail_next_flush:
            self._fail_next_flush = False
            raise OSError("synthetic fixture flush failure")
        self.recent_turns.clear()

    async def enter_plan_mode(self) -> Path:
        self.plan_mode = True
        self.plan_log_path = self._persistence_log_path
        return self.plan_log_path

    async def resume_plan_mode(self, log_path: str | Path) -> Path:
        validated = _plan_log(self.config, self.session_id).resume_log_file(log_path)
        self.plan_mode = True
        self.plan_log_path = validated
        return validated

    async def exit_plan_mode(self) -> None:
        self.plan_mode = False
        self.plan_log_path = None

    def set_thinking_mode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        if normalized not in {"normal", "extended"}:
            raise ValueError(f"unknown thinking mode: {mode}")
        self.thinking_mode = normalized

    def activate_skill(self, _name: str, _task_mode: str | None = None) -> Any:
        raise ValueError("the Phase 02 fixture exposes no skills")

    def deactivate_skill(self) -> None:
        self.active_skill_runtime = None

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
            "mcp_families": "none",
            "extension_revision": 0,
            "extension_diagnostics": "",
            "active_skill": "",
            "task_mode": "",
        }


class FixtureSessionFactory:
    """Allocate deterministic unused session IDs within one fixture process."""

    def __init__(self, catalog: DesktopProjectCatalog | None) -> None:
        self._catalog = catalog
        self._next_index = 0
        self._issued: set[str] = set()

    async def __call__(
        self,
        config: AgentConfig,
        *,
        load_mcp: bool,
        progress_cb: Callable[[str, list[Any]], None] | None,
        session_id: str | None = None,
        restored_turns: list[TurnRecord] | None = None,
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
                ):
                    session_id = candidate
                    self._issued.add(candidate)
                    break
        return FixtureSession(
            config,
            session_id=session_id,
            restored_turns=list(restored_turns or []),
            progress_cb=progress_cb,
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
    return DesktopService(
        original_cwd=original_cwd,
        environ=sanitized_environ,
        config=config,
        project_catalog=catalog,
        session_factory=FixtureSessionFactory(catalog),
    )
