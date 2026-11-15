"""The @grill skill: catalog loading, read-only document turns, comment behavior (K5)."""

from __future__ import annotations

from agent.config import AgentConfig
from agent.skills import DEFAULT_SKILLS_DIR, discover_skills
from agent.skills.runtime import load_skill_runtime, resolve_skill_references


def test_grill_skill_is_in_the_catalog_and_parses_as_an_inline_reference(tmp_path):
    catalog = discover_skills(AgentConfig(persist_dir=str(tmp_path)))
    grill = next(skill for skill in catalog if skill.name == "grill")
    assert grill.path == DEFAULT_SKILLS_DIR / "grill" / "SKILL.md"
    assert "Read-only" in grill.description

    text = "請 @grill 這段，不要用 email@grill.org"
    references = resolve_skill_references(text, catalog)
    assert references == [{"name": "grill", "startUtf16": 2, "endUtf16": 8}]

    runtime = load_skill_runtime("grill", config=AgentConfig(persist_dir=str(tmp_path)), all_tools=["read_file", "bash"])
    block = runtime.context_block()
    for heading in ("## 還原", "## 發現", "## 判斷", "## 回應檢查", "｜問題", "｜資料不足", "原文：「"):
        assert heading in block
