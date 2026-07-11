"""Tests for active skill runtime loading."""

import pytest
from langchain_core.tools import tool

from agent.config import AgentConfig
from agent.skills.runtime import load_skill_runtime, render_tool_availability_block
from agent.tool_access import ToolAccessResolution, resolve_tool_access


@tool("read_file")
def _read_file(path: str) -> str:
    """Read a file."""
    return path


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search RAG."""
    return query


@tool("bash")
def _bash(command: str) -> str:
    """Run shell."""
    return command


@tool("paper_helper")
def _paper_helper(action: str) -> str:
    """Skill-scoped helper tool."""
    return action


def _write_skill(tmp_path):
    skills_dir = tmp_path / "skills"
    root = skills_dir / "paper"
    refs = root / "references"
    refs.mkdir(parents=True)
    (root / "SKILL.md").write_text(
        """---
name: paper
description: Use when writing a paper.
---

# Paper
""",
        encoding="utf-8",
    )
    (refs / "guide.md").write_text("guide text", encoding="utf-8")
    (root / "manifest.yaml").write_text(
        """
tools:
  required:
    local:
      - paper_helper
resources:
  - path: references/guide.md
    pinned: true
task_modes:
  - revision
""",
        encoding="utf-8",
    )
    return skills_dir, root


def test_load_skill_runtime_reads_skill_and_pinned_references(tmp_path):
    skills_dir, root = _write_skill(tmp_path)
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    runtime = load_skill_runtime(
        "paper",
        config=cfg,
        all_tools=[_read_file, _rag_search, _bash, _paper_helper],
        task_mode="revision",
    )

    assert runtime.name == "paper"
    assert runtime.root == root.resolve()
    assert "# Paper" in runtime.instructions
    assert runtime.pinned_references == {"references/guide.md": "guide text"}
    assert runtime.tool_access.skill_tools == ("paper_helper",)
    assert runtime.tool_access.effective_tools == (
        "read_file",
        "rag_search",
        "bash",
        "paper_helper",
    )
    assert runtime.task_mode == "revision"


def test_load_skill_runtime_blocks_on_missing_required_tool(tmp_path):
    skills_dir, _root = _write_skill(tmp_path)
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    with pytest.raises(
        ValueError,
        match="required skill tools are unavailable: paper_helper",
    ):
        load_skill_runtime(
            "paper",
            config=cfg,
            all_tools=[_read_file, _rag_search, _bash],
        )


def test_load_skill_runtime_rejects_legacy_capabilities_field(tmp_path):
    skills_dir, root = _write_skill(tmp_path)
    (root / "manifest.yaml").write_text(
        """
capabilities:
  required:
    - file.read
""",
        encoding="utf-8",
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    with pytest.raises(ValueError, match="no longer supported"):
        load_skill_runtime("paper", config=cfg, all_tools=[_read_file])


def test_load_skill_runtime_rejects_legacy_tool_policy_field(tmp_path):
    skills_dir, root = _write_skill(tmp_path)
    (root / "manifest.yaml").write_text(
        """
tool_policy:
  disallow:
    - bash
""",
        encoding="utf-8",
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    with pytest.raises(ValueError, match="no longer supported"):
        load_skill_runtime("paper", config=cfg, all_tools=[_read_file, _bash])


def test_load_skill_runtime_rejects_manifest_typo_key(tmp_path):
    skills_dir, root = _write_skill(tmp_path)
    (root / "manifest.yaml").write_text(
        """
toolz:
  required:
    local:
      - paper_helper
""",
        encoding="utf-8",
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    with pytest.raises(ValueError, match="toolz"):
        load_skill_runtime("paper", config=cfg, all_tools=[_read_file])


def test_load_skill_runtime_rejects_empty_tools_section(tmp_path):
    skills_dir, root = _write_skill(tmp_path)
    (root / "manifest.yaml").write_text(
        """
tools: {}
""",
        encoding="utf-8",
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    with pytest.raises(ValueError, match="tools section must request"):
        load_skill_runtime("paper", config=cfg, all_tools=[_read_file])


def test_load_skill_runtime_rejects_non_bool_pinned(tmp_path):
    skills_dir, root = _write_skill(tmp_path)
    (root / "manifest.yaml").write_text(
        """
resources:
  - path: references/guide.md
    pinned: "yes"
""",
        encoding="utf-8",
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    with pytest.raises(ValueError, match="pinned"):
        load_skill_runtime("paper", config=cfg, all_tools=[_read_file])


def test_load_skill_runtime_allows_missing_optional_tool(tmp_path):
    skills_dir, root = _write_skill(tmp_path)
    (root / "manifest.yaml").write_text(
        """
tools:
  optional:
    mcp_families:
      - github
""",
        encoding="utf-8",
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    runtime = load_skill_runtime("paper", config=cfg, all_tools=[_read_file])

    assert runtime.tool_access.missing_optional == ("github",)
    assert runtime.tool_access.effective_tools == ("read_file",)


def test_load_skill_runtime_rejects_oversized_pinned_reference(tmp_path):
    skills_dir, root = _write_skill(tmp_path)
    (root / "references" / "guide.md").write_text("x" * 20, encoding="utf-8")
    cfg = AgentConfig(
        persist_dir=str(tmp_path),
        skills_dir=str(skills_dir),
        skill_max_pinned_reference_chars=10,
    )

    with pytest.raises(ValueError, match="pinned skill reference too large"):
        load_skill_runtime(
            "paper",
            config=cfg,
            all_tools=[_read_file, _paper_helper],
        )


def test_load_skill_runtime_rejects_oversized_total_skill_context(tmp_path):
    skills_dir, _root = _write_skill(tmp_path)
    cfg = AgentConfig(
        persist_dir=str(tmp_path),
        skills_dir=str(skills_dir),
        skill_max_pinned_reference_chars=1000,
        skill_max_total_skill_context_chars=20,
    )

    with pytest.raises(ValueError, match="total skill context too large"):
        load_skill_runtime(
            "paper",
            config=cfg,
            all_tools=[_read_file, _paper_helper],
        )


def test_read_skill_resource_resolves_relative_to_skill_root(tmp_path):
    skills_dir, _root = _write_skill(tmp_path)
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))
    runtime = load_skill_runtime(
        "paper",
        config=cfg,
        all_tools=[_read_file, _paper_helper],
    )

    assert runtime.read_skill_resource("references/guide.md") == "guide text"


def test_read_skill_resource_blocks_path_escape(tmp_path):
    skills_dir, _root = _write_skill(tmp_path)
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))
    runtime = load_skill_runtime(
        "paper",
        config=cfg,
        all_tools=[_read_file, _paper_helper],
    )

    with pytest.raises(PermissionError, match="escapes skill root"):
        runtime.read_skill_resource("../../etc/passwd")


def test_read_skill_resource_missing_file_has_clear_error(tmp_path):
    skills_dir, _root = _write_skill(tmp_path)
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))
    runtime = load_skill_runtime(
        "paper",
        config=cfg,
        all_tools=[_read_file, _paper_helper],
    )

    with pytest.raises(FileNotFoundError, match="does not exist"):
        runtime.read_skill_resource("references/missing.md")


def test_load_skill_runtime_rejects_unknown_task_mode(tmp_path):
    skills_dir, _root = _write_skill(tmp_path)
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    with pytest.raises(ValueError, match="unknown task mode"):
        load_skill_runtime(
            "paper",
            config=cfg,
            all_tools=[_read_file, _paper_helper],
            task_mode="drafting",
        )


def test_render_tool_availability_block_for_active_skill():
    resolution = ToolAccessResolution(
        global_tools=("rag_search", "read_file", "bash"),
        skill_tools=("paper_helper",),
        effective_tools=("rag_search", "read_file", "bash", "paper_helper"),
        missing_required=(),
        missing_optional=(),
    )

    block = render_tool_availability_block(
        resolution=resolution,
        active_skill="paper",
        task_mode="revision",
        all_tool_names=["rag_search", "read_file", "bash", "github_search", "paper_helper"],
        mcp_families={"github_search": "github"},
    )

    assert "active_skill: paper" in block
    assert "task_mode: revision" in block
    assert "available_tools: rag_search, read_file, bash, paper_helper" in block
    assert "skill_tools: paper_helper" in block
    assert "unavailable_tools: MCP family: github" in block
    assert "skill_tools are added by the active skill" in block


def test_render_tool_availability_block_without_active_skill_collapses_mcp_families():
    resolution = resolve_tool_access(
        None,
        ["rag_search", "web_search_one", "web_search_two", "github_issue"],
        mcp_families={
            "web_search_one": "web_search",
            "web_search_two": "web_search",
            "github_issue": "github",
        },
    )

    block = render_tool_availability_block(
        resolution=resolution,
        all_tool_names=[
            "rag_search",
            "web_search_one",
            "web_search_two",
            "github_issue",
        ],
        mcp_families={
            "web_search_one": "web_search",
            "web_search_two": "web_search",
            "github_issue": "github",
        },
    )

    assert "active_skill: (none)" in block
    assert "available_tools: rag_search, MCP family: web_search" in block
    assert "web_search_two" not in block
    assert "unavailable_tools: MCP family: github" in block
    assert "No active skill; only global tools are bound" in block


def test_render_tool_availability_block_defaults_to_base_inventory():
    from agent.tools.inventory import base_tool_names

    block = render_tool_availability_block()

    assert "active_skill: (none)" in block
    for name in base_tool_names():
        assert name in block


def test_render_tool_availability_block_keeps_empty_resolution_semantics():
    empty = ToolAccessResolution(
        global_tools=(),
        skill_tools=(),
        effective_tools=(),
        missing_required=(),
        missing_optional=(),
    )

    block = render_tool_availability_block(resolution=empty)

    assert "available_tools: (none)" in block
    assert "unavailable_tools: (none)" in block
