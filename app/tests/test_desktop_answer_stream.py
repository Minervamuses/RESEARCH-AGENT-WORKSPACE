"""Focused tests for authoritative final-only desktop answers."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agent.config import AgentConfig
from agent.desktop.service import DesktopService, DesktopServiceError
from agent.turns.results import TurnOutcome


class _AnswerSession:
    def __init__(self, text: str) -> None:
        self.session_id = "00000000000040008000000000000021"
        self.text = text
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.blocked = False
        self.error: Exception | None = None
        self.validation_errors: list[str] = []

    async def turn_outcome(self, _text: str) -> TurnOutcome:
        self.started.set()
        if self.blocked:
            await self.release.wait()
        if self.error is not None:
            raise self.error
        return TurnOutcome(
            text=self.text,
            validation_errors=self.validation_errors,
        )


def _service(tmp_path: Path, session: _AnswerSession) -> DesktopService:
    service = DesktopService(
        original_cwd=tmp_path,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
        config=AgentConfig(
            persist_dir=str(tmp_path / "store"),
            citation_output_dir=str(tmp_path / "cite"),
            extension_dropin_dir=str(tmp_path / "dropin"),
            extension_state_dir=str(tmp_path / "extensions"),
            plan_logs_dir=str(tmp_path / "plans"),
        ),
    )
    service.session = session  # type: ignore[assignment]
    return service


def test_answer_is_delivered_only_by_the_final_terminal_result(tmp_path: Path) -> None:
    async def run() -> None:
        session = _AnswerSession("final answer")
        session.blocked = True
        service = _service(tmp_path, session)
        events: list[tuple[str, dict]] = []

        task = asyncio.create_task(
            service.dispatch(
                "session.turn",
                {"text": "question"},
                event_sink=lambda name, data: events.append((name, data)),
            )
        )
        await session.started.wait()
        assert events == []

        session.release.set()
        result = await task

        assert events == []
        assert result["text"] == "final answer"
        assert result["streamKind"] == "final_only"
        assert result["chunkCount"] == 0

    asyncio.run(run())


def test_unicode_answer_is_returned_whole_without_answer_events(tmp_path: Path) -> None:
    text = "a" * 16_383 + "🙂" + "b" * 16_383 + "終"
    session = _AnswerSession(text)
    service = _service(tmp_path, session)
    events: list[tuple[str, dict]] = []

    result = asyncio.run(
        service.dispatch(
            "session.turn",
            {"text": "question"},
            event_sink=lambda name, data: events.append((name, data)),
        )
    )

    assert events == []
    assert result["text"] == text
    assert result["streamKind"] == "final_only"
    assert result["chunkCount"] == 0


def test_failed_or_oversized_answer_emits_no_answer_events(tmp_path: Path) -> None:
    failing = _AnswerSession("unused")
    failing.error = RuntimeError("provider payload must stay private")
    failing_service = _service(tmp_path, failing)
    failed_events: list[tuple[str, dict]] = []

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(
            failing_service.dispatch(
                "session.turn",
                {"text": "question"},
                event_sink=lambda name, data: failed_events.append((name, data)),
            )
        )
    assert raised.value.code == "INTERNAL_ERROR"
    assert failed_events == []
    assert "provider payload" not in str(raised.value)

    oversized = _AnswerSession("x" * (2_097_152 + 1))
    oversized_service = _service(tmp_path, oversized)
    oversized_events: list[tuple[str, dict]] = []
    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(
            oversized_service.dispatch(
                "session.turn",
                {"text": "question"},
                event_sink=lambda name, data: oversized_events.append((name, data)),
            )
        )
    assert raised.value.code == "INTERNAL_ERROR"
    assert oversized_events == []


@pytest.mark.parametrize(
    ("text", "validation_errors"),
    [
        ("x" * 2_097_152, []),
        ("\u0000" * 350_000, []),
        ("x" * 1_600_000, ["e" * 4_096] * 128),
    ],
)
def test_complete_success_envelope_is_budgeted_before_delivery(
    tmp_path: Path,
    text: str,
    validation_errors: list[str],
) -> None:
    session = _AnswerSession(text)
    session.validation_errors = validation_errors
    service = _service(tmp_path, session)
    events: list[tuple[str, dict]] = []

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(
            service.dispatch(
                "session.turn",
                {"text": "question"},
                event_sink=lambda name, data: events.append((name, data)),
            )
        )

    assert raised.value.code == "INTERNAL_ERROR"
    assert "response limit" in str(raised.value)
    assert events == []


def test_final_only_answer_does_not_call_the_event_sink(
    tmp_path: Path,
) -> None:
    session = _AnswerSession("authoritative")
    service = _service(tmp_path, session)
    calls = 0

    def broken_sink(_name: str, _data: dict) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("closed event channel")

    result = asyncio.run(
        service.dispatch(
            "session.turn",
            {"text": "question"},
            event_sink=broken_sink,
        )
    )

    assert result["text"] == "authoritative"
    assert result["streamKind"] == "final_only"
    assert result["chunkCount"] == 0
    assert calls == 0


def test_cancelled_turn_emits_no_answer_events(tmp_path: Path) -> None:
    async def run() -> None:
        session = _AnswerSession("must stay hidden")
        session.blocked = True
        service = _service(tmp_path, session)
        events: list[tuple[str, dict]] = []

        task = asyncio.create_task(
            service.dispatch(
                "session.turn",
                {"text": "question"},
                event_sink=lambda name, data: events.append((name, data)),
            )
        )
        await session.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert events == []
        assert service._turn_active is False

    asyncio.run(run())


@pytest.mark.parametrize(
    ("status_code", "expected_code", "retryable"),
    [
        (429, "PROVIDER_RATE_LIMITED", True),
        (503, "PROVIDER_REQUEST_FAILED", True),
        (400, "PROVIDER_REQUEST_FAILED", False),
    ],
)
def test_provider_http_failures_are_safe_and_bounded(
    tmp_path: Path,
    status_code: int,
    expected_code: str,
    retryable: bool,
) -> None:
    class ProviderFailure(RuntimeError):
        def __init__(self) -> None:
            super().__init__("raw provider payload with private headers")
            self.status_code = status_code

    session = _AnswerSession("unused")
    session.error = ProviderFailure()
    service = _service(tmp_path, session)
    events: list[tuple[str, dict]] = []

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(
            service.dispatch(
                "session.turn",
                {"text": "preserve this draft"},
                event_sink=lambda name, data: events.append((name, data)),
            )
        )

    assert raised.value.code == expected_code
    assert raised.value.retryable is retryable
    assert "raw provider" not in str(raised.value)
    assert events == []
