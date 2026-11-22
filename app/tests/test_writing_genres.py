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


import asyncio

from agent.session import SYSTEM_PROMPT, ChatSession

RULES_HEADING = "Writing rules (every turn):"


def test_system_prompt_carries_the_writing_rules_before_the_language_policy():
    section = SYSTEM_PROMPT.split(RULES_HEADING, 1)[1].split("Language policy:", 1)[0]
    for rule in ("@writing-genres", "[TODO: …]", "[CITE: …]", "[FIGURE: …]",
                 "`.md`, `.markdown` and `.tex`", "`@grill`", "separate steps"):
        assert rule in section
    assert SYSTEM_PROMPT.index(RULES_HEADING) < SYSTEM_PROMPT.index("Language policy:")
    assert "ALWAYS use Traditional Chinese" in SYSTEM_PROMPT  # The language policy is unchanged.


def test_cli_and_desktop_sessions_send_the_writing_rules_every_turn(tmp_path, monkeypatch):
    from langchain_core.messages import AIMessage, SystemMessage

    from desktop_support import _open_test_project, _service

    class Model:
        def __init__(self):
            self.calls = []

        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            self.calls.append(messages)
            return AIMessage(content="好")

    model = Model()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _config: model)
    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _config: [])
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)

    # CLI: the default ChatSession system prompt.
    cli = ChatSession(AgentConfig(persist_dir=str(tmp_path / "cli")))
    for text in ("第一回合", "第二回合"):
        asyncio.run(cli.turn(text))
    for call in model.calls:
        assert RULES_HEADING in call[0].content and isinstance(call[0], SystemMessage)

    # Desktop: the project system prompt keeps the rules ahead of RESEARCH.md rules.
    model.calls.clear()

    async def factory(config, *, load_mcp, **kwargs):
        return ChatSession(config, **kwargs)

    async def desktop():
        service = _service(tmp_path / "desk", session_factory=factory)
        project = tmp_path / "project"
        (project / "RESEARCH.md").parent.mkdir(parents=True, exist_ok=True)
        await _open_test_project(service, project)
        await service.dispatch("session.create", {"loadMcp": False})
        for text in ("第一回合", "第二回合"):
            await service.dispatch("session.turn", {"text": text, "turnId": __import__("uuid").uuid4().hex, "retry": False})

    asyncio.run(desktop())
    assert len(model.calls) == 2
    for call in model.calls:
        system = call[0].content
        assert RULES_HEADING in system
        assert system.index(RULES_HEADING) < system.index("### RESEARCH.md rules")
