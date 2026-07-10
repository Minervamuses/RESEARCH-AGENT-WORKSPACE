"""Lazy LLM query expansion for citation discovery.

The LLM's only role in discovery: propose at most two *additional* search
queries for the structured providers. It never emits metadata, never scores
relevance, and is never required — when the model cannot be built or the
call fails/times out, discovery proceeds with the original query alone.

The chat model is built lazily on first use (no startup probe) via the
injected factory, so ``/citation`` sessions that never search pay nothing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

MAX_EXPANSIONS = 2
_EXPAND_TIMEOUT_SECONDS = 20.0

_SYSTEM_PROMPT = (
    "You expand ONE academic paper search query into alternative queries for "
    "bibliographic APIs (Crossref/OpenAlex). Reply with a JSON array of at "
    f"most {MAX_EXPANSIONS} strings — alternative phrasings or English "
    "translations a researcher would use. No explanations, no scores, no "
    "metadata, no invented paper titles."
)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def parse_expansions(raw: str, *, original_query: str) -> list[str]:
    """Accept only a JSON array of strings; anything else expands to nothing."""
    try:
        data = json.loads(_strip_code_fence(raw or ""))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    seen = {original_query.strip().casefold()}
    out: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        query = item.strip()
        key = query.casefold()
        if not query or key in seen:
            continue
        seen.add(key)
        out.append(query)
        if len(out) >= MAX_EXPANSIONS:
            break
    return out


class QueryExpander:
    """Builds the chat model on first use; every failure degrades to []."""

    def __init__(
        self,
        llm_factory: Callable[[], object],
        *,
        timeout: float = _EXPAND_TIMEOUT_SECONDS,
    ):
        self._llm_factory = llm_factory
        self._timeout = timeout
        self._llm: object | None = None
        self._unavailable = False

    def _get_llm(self):
        if self._unavailable:
            return None
        if self._llm is None:
            try:
                self._llm = self._llm_factory()
            except Exception as exc:  # noqa: BLE001 - expansion is optional
                logger.warning("query expander LLM unavailable: %s", exc)
                self._unavailable = True
                return None
        return self._llm

    async def expand(self, query: str) -> list[str]:
        """Return up to two extra queries; [] whenever the LLM cannot help."""
        llm = self._get_llm()
        if llm is None:
            return []
        try:
            response = await asyncio.wait_for(
                llm.ainvoke([("system", _SYSTEM_PROMPT), ("human", query)]),
                timeout=self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 - degrade, never block discovery
            logger.warning("query expansion failed: %s", exc)
            return []
        return parse_expansions(
            str(getattr(response, "content", "") or ""), original_query=query
        )
