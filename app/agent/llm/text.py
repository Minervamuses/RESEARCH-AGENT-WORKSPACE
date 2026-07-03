"""Text helpers for LangChain chat models."""

from langchain_core.messages import HumanMessage


def normalize_content(content, *, drop_unknown_parts: bool) -> str:
    """Flatten LangChain message content (str or content-part list) to text.

    drop_unknown_parts decides what a dict part without usable text becomes:
    True renders it as "" (after also consulting a "content" key), False keeps
    its repr so the caller can still see what the part was (e.g. a tool_use
    part). Non-list content is stringified without stripping.
    """
    if isinstance(content, list):
        return "\n".join(
            _content_part_to_text(part, drop_unknown_parts=drop_unknown_parts)
            for part in content
        )
    return str(content or "")


def _content_part_to_text(part, *, drop_unknown_parts: bool) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        if drop_unknown_parts:
            return str(part.get("text") or part.get("content") or "")
        text = part.get("text")
        if text is not None:
            return str(text)
    return str(part)


def invoke_text(model, prompt: str) -> str:
    """Invoke a LangChain chat model with one user prompt and return text.

    Unknown content parts are dropped and the result is stripped.
    """
    response = model.invoke([HumanMessage(content=prompt)])
    content = getattr(response, "content", response)
    return normalize_content(content, drop_unknown_parts=True).strip()


def invoke_text_messages(model, messages: list) -> str:
    """Invoke a LangChain chat model with a full message list and return text.

    Unlike invoke_text, unknown content parts keep their repr and list-joined
    content is not stripped, so multi-part reply boundaries stay intact.
    """
    response = model.invoke(messages)
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return normalize_content(content, drop_unknown_parts=False)
    return str(content or "").strip()
