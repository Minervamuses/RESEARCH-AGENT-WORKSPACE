"""Tests for the single-source base tool inventory."""

from langchain_core.tools import tool

from agent.config import AgentConfig
from agent.tools import inventory as tool_inventory


@tool("web_fetch")
def _web_fetch(url: str) -> str:
    """Fake MCP tool."""
    return url


@tool("rag_search")
def _shadow_rag_search(query: str) -> str:
    """Extra tool that collides with a local base tool name."""
    return query


def test_base_tool_names_fixed_local_order():
    assert tool_inventory.base_tool_names() == [
        "rag_explore",
        "rag_search",
        "rag_get_context",
        "read_file",
        "bash",
    ]


def test_base_tool_names_appends_extra_tools_in_order():
    assert tool_inventory.base_tool_names([_web_fetch]) == [
        "rag_explore",
        "rag_search",
        "rag_get_context",
        "read_file",
        "bash",
        "web_fetch",
    ]


def test_base_tool_names_drops_extra_tool_colliding_with_local():
    # A same-named extra tool is ignored: local base tool wins.
    assert tool_inventory.base_tool_names([_shadow_rag_search]) == (
        tool_inventory.base_tool_names()
    )


def test_build_base_tools_names_match_base_tool_names(tmp_path):
    cfg = AgentConfig(persist_dir=str(tmp_path))
    tools = tool_inventory.build_base_tools(
        cfg,
        extra_tools=[_web_fetch],
    )
    built_names = [tool.name for tool in tools]

    assert built_names == tool_inventory.base_tool_names([_web_fetch])


def test_build_base_tools_does_not_double_bind_colliding_extra(tmp_path):
    cfg = AgentConfig(persist_dir=str(tmp_path))
    tools = tool_inventory.build_base_tools(
        cfg,
        extra_tools=[_shadow_rag_search],
    )
    built_names = [tool.name for tool in tools]

    assert built_names.count("rag_search") == 1
    assert built_names == tool_inventory.base_tool_names()


def test_render_base_tool_prompt_has_no_import_or_runtime_side_effects(monkeypatch):
    def _explode(*_args, **_kwargs):
        raise AssertionError("render_base_tool_prompt must not build tools")

    monkeypatch.setattr(tool_inventory, "create_rag_tools", _explode)
    monkeypatch.setattr(tool_inventory, "create_read_file_tool", _explode)
    monkeypatch.setattr(tool_inventory, "create_bash_tool", _explode)

    prompt = tool_inventory.render_base_tool_prompt()
    names = tool_inventory.base_tool_names()

    assert "**rag_explore**" in prompt
    assert "Tool selection policy:" in prompt
    assert "Workflow:" in prompt
    assert names[0] == "rag_explore"


def test_render_base_tool_prompt_covers_every_base_tool():
    prompt = tool_inventory.render_base_tool_prompt()
    for name in tool_inventory.base_tool_names():
        assert f"**{name}**" in prompt


def test_base_workflow_has_graceful_give_up_rule():
    prompt = tool_inventory.render_base_tool_prompt()

    # The give-up discipline must be evidence-based: no numeric quota, no
    # rag_get_context on irrelevant results, and an honest not-found answer.
    assert "After at most 1-3" not in prompt
    assert "available results provide enough relevant evidence" in prompt
    assert "Give up gracefully" in prompt
    assert "indexed knowledge base does not contain enough evidence" in prompt
    assert "do NOT call rag_get_context on irrelevant results" in prompt


def test_system_prompt_embeds_rendered_base_tool_prompt():
    from agent.session import SYSTEM_PROMPT

    assert tool_inventory.render_base_tool_prompt() in SYSTEM_PROMPT
