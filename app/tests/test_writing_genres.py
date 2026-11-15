"""The writing-genres skill and the per-turn reply rules in SYSTEM_PROMPT (K7)."""

from __future__ import annotations

from agent.config import AgentConfig
from agent.skills import DEFAULT_SKILLS_DIR, discover_skills
from agent.skills.runtime import load_skill_runtime, resolve_skill_references

GENRES = ("論文", "教材", "筆記", "計劃書", "Abstract", "Poster", "投影片")


def test_writing_genres_is_in_the_catalog_and_covers_seven_genres(tmp_path):
    config = AgentConfig(persist_dir=str(tmp_path))
    catalog = discover_skills(config)
    skill = next(item for item in catalog if item.name == "writing-genres")
    assert skill.path == DEFAULT_SKILLS_DIR / "writing-genres" / "SKILL.md"
    assert resolve_skill_references("用 @writing-genres 寫投影片", catalog) == [
        {"name": "writing-genres", "startUtf16": 2, "endUtf16": 17},
    ]
    block = load_skill_runtime("writing-genres", config=config, all_tools=["bash"]).context_block()
    sections = block.split("\n### ")[1:]
    assert [section.split("\n", 1)[0].split(" ", 1)[0] for section in sections] == list(GENRES)
    for section in sections:
        assert "Default file:" in section and "`.md`" in section  # Every genre names its format.
    for rule in ("`.md`,\n   `.markdown` and `.tex`", "set -o noclobber", "[@key]", "\\cite{key}",
                 "[TODO: …]", "[CITE: …]", "[FIGURE: …]", "@academic-paper-writing", "@grill"):
        assert rule in block
