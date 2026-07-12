"""Final-response safety helpers shared by the graph, session, and CLI."""

from __future__ import annotations

import re
from collections.abc import Iterable

from langchain_core.messages import HumanMessage, ToolMessage

from agent.llm.text import normalize_content


_PROTOCOL_SENTINEL_RE = re.compile(
    r"<\s*[|｜]?\s*tool[\s_▁-]*calls?[\s_▁-]*(?:begin|end)"
    r"\s*[|｜]?\s*>"
    r"|<\s*/?\s*tool_call\s*>"
    r"|\[\s*/?\s*tool_calls?\s*\]"
    r"|\btool[_▁-]+calls?[_▁-]+(?:begin|end)\b",
    re.IGNORECASE,
)


def content_text(content) -> str:
    """Flatten model content without discarding unknown content parts."""
    return normalize_content(content, drop_unknown_parts=False)


def find_content_tool_protocol_artifact(
    content,
    *,
    tool_names: Iterable[str] = (),
) -> str | None:
    """Detect structured tool-use blocks before content is flattened to text."""
    if not isinstance(content, list):
        return None

    names = {name.casefold() for name in tool_names if name}
    if not names:
        return None

    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = str(part.get("type", "")).casefold()
        name = str(part.get("name", "")).casefold()
        if (
            part_type in {"tool_use", "tool_call", "function_call"}
            and name in names
            and any(key in part for key in ("input", "args", "arguments"))
        ):
            return "structured_tool_content"

        function = part.get("function")
        if not isinstance(function, dict):
            continue
        function_name = str(function.get("name", "")).casefold()
        if (
            part_type in {"tool_use", "tool_call", "function_call"}
            and function_name in names
            and any(key in function for key in ("input", "args", "arguments"))
        ):
            return "structured_tool_content"
    return None


def find_tool_protocol_artifact(
    text: str,
    *,
    tool_names: Iterable[str] = (),
) -> str | None:
    """Return the protocol artifact kind, or ``None`` for normal prose.

    A bare mention of a tool name is intentionally harmless. Tool-name matches
    require either a serialized name/payload envelope or call-like syntax with
    an argument assignment or JSON object, matching observed provider formats.
    """
    if not text:
        return None
    if _PROTOCOL_SENTINEL_RE.search(text):
        return "tool_protocol_sentinel"

    names = sorted({name for name in tool_names if name}, key=len, reverse=True)
    if not names:
        return None
    alternation = "|".join(re.escape(name) for name in names)
    serialized = re.compile(
        rf"[\"']name[\"']\s*:\s*[\"'](?:{alternation})[\"']"
        rf"[\s\S]{{0,240}}?[\"'](?:args|arguments|input)[\"']\s*:",
        re.IGNORECASE,
    )
    if serialized.search(text):
        return "serialized_tool_call"
    serialized_reverse = re.compile(
        rf"[\"'](?:args|arguments|input)[\"']\s*:[\s\S]{{0,240}}?"
        rf"[\"']name[\"']\s*:\s*[\"'](?:{alternation})[\"']",
        re.IGNORECASE,
    )
    if serialized_reverse.search(text):
        return "serialized_tool_call"
    call_like = re.compile(
        rf"(?<![\w.-])(?:{alternation})\s*\(\s*"
        rf"(?:\{{[\s\S]{{0,300}}\}}|[^\n)]{{0,300}}\b\w+\s*=)",
        re.IGNORECASE,
    )
    if call_like.search(text):
        return "call_like_tool_protocol"
    return None


def final_response_problem(
    text: str,
    *,
    tool_names: Iterable[str] = (),
    dropped_tool_calls: bool = False,
) -> str | None:
    """Classify an invalid user-visible response."""
    if not text.strip():
        return "empty_final_answer"
    artifact = find_tool_protocol_artifact(text, tool_names=tool_names)
    if artifact is not None:
        return artifact
    if dropped_tool_calls:
        return "dropped_tool_calls"
    return None


def last_user_text(messages: Iterable[object]) -> str:
    for message in reversed(list(messages)):
        if isinstance(message, HumanMessage):
            return content_text(message.content)
    return ""


def has_tool_results(messages: Iterable[object]) -> bool:
    return any(isinstance(message, ToolMessage) for message in messages)


def build_recovery_message(*, user_input: str, had_tool_results: bool) -> str:
    """Return a deterministic Traditional-Chinese or English fallback."""
    is_chinese = bool(re.search(r"[\u3400-\u9fff]", user_input))
    if is_chinese:
        if had_tool_results:
            return (
                "工具結果已取得，但本回合未能完成總結；已停止後續工具操作。"
                "請重試，或縮小問題範圍。"
            )
        return (
            "本回合未能產生可顯示的最終回答；已停止未完成的工具操作。"
            "請重試，或縮小問題範圍。"
        )
    if had_tool_results:
        return (
            "Tool results were received, but this turn could not produce a final "
            "summary. Further tool operations were stopped. Please retry or "
            "narrow the request."
        )
    return (
        "This turn could not produce a displayable final answer. Incomplete "
        "tool operations were stopped. Please retry or narrow the request."
    )


def build_empty_upstream_message(*, user_input: str, had_tool_results: bool) -> str:
    """Honest notice that the upstream model kept returning empty responses.

    Shown only after the in-turn retries are exhausted. It must state what
    actually happened — empty upstream replies, nothing new executed — and
    must never be produced by another model call, which could invent results.
    """
    is_chinese = bool(re.search(r"[\u3400-\u9fff]", user_input))
    if is_chinese:
        if had_tool_results:
            return (
                "上游模型連續回傳空回應（重試後仍為空），本回合無法產生總結。"
                "先前已完成的工具結果不受影響，但沒有執行任何新的操作。"
                "這通常是模型服務暫時不穩定，請稍後重試。"
            )
        return (
            "上游模型連續回傳空回應（重試後仍為空），本回合沒有產生任何回答，"
            "也沒有執行任何工具操作。這通常是模型服務暫時不穩定，請稍後重試。"
        )
    if had_tool_results:
        return (
            "The upstream model returned empty responses repeatedly (still empty "
            "after retries), so this turn has no summary. Tool results already "
            "completed are unaffected, but no new operation was performed. This "
            "is usually transient provider instability; please retry."
        )
    return (
        "The upstream model returned empty responses repeatedly (still empty "
        "after retries), so this turn produced no answer and performed no tool "
        "operation. This is usually transient provider instability; please retry."
    )
