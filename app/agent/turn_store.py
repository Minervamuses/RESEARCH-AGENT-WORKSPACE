"""Persistence half of the recent-turns window.

Owns spilling prompt-visible turns into the long-term chat-history store;
the session facade keeps the recent_turns list itself (shared by reference)
because prompt assembly reads it every turn.
"""

from __future__ import annotations

import asyncio
import logging

from agent.config import AgentConfig
from agent.memory import TurnRecord

logger = logging.getLogger(__name__)


class TurnStore:
    """Spills turns past the window into the history store; flushes on exit."""

    def __init__(
        self,
        history_store,
        *,
        config: AgentConfig,
        session_id: str,
        recent_turns: list[TurnRecord],
    ):
        self._history_store = history_store
        self._config = config
        self._session_id = session_id
        self._recent_turns = recent_turns

    async def store_turn(self, turn: TurnRecord) -> None:
        if turn.persist_target == "plan_log":
            return
        if turn.persist_target == "none":
            return
        if turn.persist_target != "chroma":
            raise ValueError(
                f"unknown persist_target={turn.persist_target!r} on turn {turn.turn_id}"
            )
        await asyncio.to_thread(
            self._history_store.add_turn,
            turn,
            session_id=self._session_id,
            turn_id=turn.turn_id,
            timestamp=turn.timestamp,
        )

    async def evict_overflow(self) -> None:
        """Spill turns past the window into the long-term store. Log + keep on failure."""
        window = self._config.agent_recent_turns_window
        hard_cap = window * 3
        while len(self._recent_turns) > window:
            oldest = self._recent_turns[0]
            try:
                await self.store_turn(oldest)
            except Exception as exc:
                logger.warning(
                    "history_rag: eviction failed for turn %s (kept in recent_turns): %s",
                    oldest.turn_id, exc,
                )
                if len(self._recent_turns) > hard_cap:
                    logger.error(
                        "history_rag: hard cap %d reached; dropping oldest turn %s unrecorded",
                        hard_cap, oldest.turn_id,
                    )
                    self._recent_turns.pop(0)
                break  # don't retry within the same turn
            self._recent_turns.pop(0)

    async def flush(self) -> None:
        """Persist all prompt-visible turns before the session is discarded."""
        while self._recent_turns:
            oldest = self._recent_turns[0]
            try:
                await self.store_turn(oldest)
            except Exception as exc:
                logger.warning(
                    "history_rag: shutdown flush failed for turn %s (left in recent_turns): %s",
                    oldest.turn_id, exc,
                )
                break
            self._recent_turns.pop(0)
