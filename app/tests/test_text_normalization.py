"""Table tests pinning the two divergent content-normalization behaviors.

Written before consolidating agent/llm/text.py and agent/thinking.py's copies
(pin-then-swap): these must pass byte-for-byte against the pre-swap code and
survive the swap unchanged. The two entry points intentionally diverge:

- text.invoke_text (prompt str in): drops unknown dict parts (also consulting
  a "content" key) and strips the final result.
- thinking.invoke_text (messages in): keeps unknown dict parts as their repr
  (e.g. tool_use parts) and does NOT strip list-joined content.
"""

import pytest

from agent.llm.text import invoke_text as text_invoke_text
from agent.thinking import invoke_text as thinking_invoke_text


class _FixedResponse:
    def __init__(self, content):
        self.content = content


class _FixedModel:
    def __init__(self, content):
        self._content = content
        self.seen: list = []

    def invoke(self, messages):
        self.seen.append(messages)
        return _FixedResponse(self._content)


TOOL_USE_PART = {"type": "tool_use", "id": "call-1", "name": "rag_search"}


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # plain string is stripped
        ("  hello  ", "hello"),
        # list of strings joins with newline, final strip applies
        (["  a", "b  "], "a\nb"),
        # dict parts with a text key
        ([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}], "a\nb"),
        # dict without text falls back to the "content" key
        ([{"content": "from-content"}], "from-content"),
        # empty text falls through to content (`or` chain)
        ([{"text": "", "content": "fallback"}], "fallback"),
        # unknown part with neither key is dropped to ""
        ([TOOL_USE_PART, {"text": "kept"}], "\nkept".strip()),
        # empty / falsy content
        ("", ""),
        (None, ""),
        ([], ""),
    ],
)
def test_text_invoke_text_drops_unknown_parts_and_strips(content, expected):
    model = _FixedModel(content)

    assert text_invoke_text(model, "prompt") == expected
    # prompt-str form wraps the prompt in a single human message
    assert len(model.seen[0]) == 1
    assert model.seen[0][0].content == "prompt"


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # plain string IS stripped in the str branch
        ("  hello  ", "hello"),
        # list branch is NOT stripped: surrounding whitespace survives
        (["  a", "b  "], "  a\nb  "),
        # dict parts with a text key
        ([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}], "a\nb"),
        # empty-string text is kept as "" (checked against None, not falsiness)
        ([{"text": ""}, {"text": "x"}], "\nx"),
        # a "content" key is NOT consulted; the part keeps its repr
        (
            [{"content": "from-content"}],
            str({"content": "from-content"}),
        ),
        # unknown parts (e.g. tool_use) keep their repr instead of vanishing
        (
            [TOOL_USE_PART, {"text": "kept"}],
            f"{TOOL_USE_PART}\nkept",
        ),
        # empty / falsy content
        ("", ""),
        (None, ""),
        ([], ""),
    ],
)
def test_thinking_invoke_text_keeps_unknown_parts_and_list_whitespace(content, expected):
    model = _FixedModel(content)
    messages = [object(), object()]

    assert thinking_invoke_text(model, messages) == expected
    # messages form passes the list through unchanged
    assert model.seen[0] is messages
