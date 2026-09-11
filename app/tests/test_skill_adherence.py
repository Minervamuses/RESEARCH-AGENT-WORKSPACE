"""End-to-end adherence checks for slash-command skill runtime."""

import asyncio
import json
import shlex
import sys
import zipfile
from pathlib import Path

import pytest

from langchain_core.messages import AIMessage, ToolMessage

from agent.cli.slash_commands import (
    SlashCommandContext,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from agent.config import AgentConfig
from agent.session import ChatSession
from agent.tools.read_file import _read_file


def _write_academic_skill(tmp_path):
    skills_dir = tmp_path / "skills"
    root = skills_dir / "academic-paper-writing"
    refs = root / "references"
    refs.mkdir(parents=True)
    (root / "SKILL.md").write_text(
        """---
name: academic-paper-writing
description: Use when writing academic papers.
---

# Academic Paper Writing
""",
        encoding="utf-8",
    )
    (refs / "section-playbooks.md").write_text("section reference", encoding="utf-8")
    (root / "manifest.yaml").write_text(
        """
resources:
  - path: references/section-playbooks.md
    pinned: true
""",
        encoding="utf-8",
    )
    return skills_dir, root


class _CaptureGraph:
    def __init__(self, captured):
        self.captured = captured

    async def astream(self, state, config=None, stream_mode="updates"):
        self.captured["state"] = state
        yield {"agent": {"messages": [AIMessage(content="ok")]}}


def _make_session(tmp_path, monkeypatch, captured):
    skills_dir, _root = _write_academic_skill(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, **kwargs: _CaptureGraph(captured),
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))
    return ChatSession(cfg)


def test_slash_skill_command_selects_exactly_one_runtime_turn(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)
    registry = build_default_registry(session)

    result = asyncio.run(execute_slash_command(
        parse_slash_command("/academic-paper-writing revise  this abstract"),
        SlashCommandContext(session=session, registry=registry),
    ))
    assert result.skill_name == "academic-paper-writing"
    assert result.followup_input == "revise  this abstract"
    assert session.active_skill_runtime is None

    answer = asyncio.run(session.turn(
        result.followup_input,
        skill_name=result.skill_name,
    ))
    assert answer == "ok"
    assert captured["state"]["active_skill"] == "academic-paper-writing"
    assert session.active_skill_runtime is None


def test_active_skill_state_and_prompt_are_ready_before_turn(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)

    answer = asyncio.run(session.turn(
        "revise this abstract",
        skill_name="academic-paper-writing",
    ))
    state = captured["state"]
    prompt_text = "\n".join(message.content for message in state["messages"])

    assert answer == "ok"
    # The session initial state carries the same serialized active-skill slice
    # as the graph loader.
    serialized_keys = {
        "active_skill",
        "skill_root",
        "skill_instructions",
        "loaded_references",
        "effective_tools",
    }
    assert serialized_keys <= set(state)
    assert state["active_skill"] == "academic-paper-writing"
    assert state["skill_instructions"].startswith("---")
    assert state["loaded_references"] == {
        "references/section-playbooks.md": "section reference"
    }
    assert "# Academic Paper Writing" in prompt_text


def test_active_skill_relative_reference_resolves_to_skill_bundle(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)
    asyncio.run(session.turn(
        "read the reference",
        skill_name="academic-paper-writing",
    ))

    payload = json.loads(
        _read_file(
            "references/section-playbooks.md",
            skill_root=captured["state"]["skill_root"],
        )
    )

    assert payload["path"].endswith(
        "skills/academic-paper-writing/references/section-playbooks.md"
    )
    assert payload["content"] == "section reference"


def test_active_skill_keeps_global_tools(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)
    asyncio.run(session.turn(
        "draft",
        skill_name="academic-paper-writing",
    ))

    assert "read_file" in captured["state"]["effective_tools"]
    assert "bash" in captured["state"]["effective_tools"]


def test_no_skill_turn_keeps_skill_state_empty(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)

    answer = asyncio.run(session.turn("hello"))

    assert answer == "ok"
    assert session.active_skill_runtime is None
    assert "active_skill" not in captured["state"]


@pytest.mark.parametrize("slash", [False, True])
def test_installer_explicit_request_uses_normal_skill_turn(tmp_path, monkeypatch, slash):
    captured = {}
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, **kwargs: _CaptureGraph(captured),
    )
    session = ChatSession(AgentConfig(
        persist_dir=str(tmp_path / "history"),
        extension_dropin_dir=str(tmp_path / "dropins"),
        extension_state_dir=str(tmp_path / "state"),
    ))
    session.set_thinking_mode("extended")
    async def unexpected_extended(_text):
        raise AssertionError("installer must use normal tools")
    monkeypatch.setattr(session._fusion, "run_extended_turn", unexpected_extended)
    text = "install /tmp/example.zip" if slash else "請用 skill-installer 安裝 /tmp/example.zip"
    asyncio.run(session.turn(text, skill_name="skill-installer" if slash else None))

    assert captured["state"]["active_skill"] == "skill-installer"
    assert "skill_install" in captured["state"]["effective_tools"]
    assert session.active_skill_runtime is None
    assert session.thinking_mode == "extended"


@pytest.mark.parametrize("text", [
    "skill-installer 是什麼", '文件範例是「請用 skill-installer 安裝 /tmp/example.zip」',
])
def test_installer_mention_does_not_select_skill(tmp_path, monkeypatch, text):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)
    asyncio.run(session.turn(text))
    assert "active_skill" not in captured["state"]


def test_active_skill_context_exposes_absolute_root_for_root_document(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)
    root = tmp_path / "skills" / "academic-paper-writing"
    (root / "forms.md").write_text("Root-level original forms", encoding="utf-8")
    asyncio.run(session.turn("read forms.md", skill_name="academic-paper-writing"))
    prompt = "\n".join(message.content for message in captured["state"]["messages"])

    assert f"skill_root: {root.resolve()}" in prompt
    assert "relative" in prompt.lower()
    result = json.loads(_read_file(str(root / "forms.md")))
    assert result["content"] == "Root-level original forms"


class _InstallerScriptModel:
    """Deterministic tool calls; all shell/host filesystem behavior remains real."""

    def __init__(self, steps):
        self.steps = iter(steps)
        self.bindings = []
        self.calls = []

    def bind_tools(self, tools):
        self.bindings.append([tool.name for tool in tools])
        return self

    def invoke(self, messages):
        step = next(self.steps)
        if callable(step):
            step = step(messages)
        if isinstance(step, str):
            return AIMessage(content=step)
        name, args = step
        self.calls.append((name, args))
        return AIMessage(content="", tool_calls=[
            {"name": name, "args": args, "id": f"install-{len(self.calls)}"}
        ])


class _InstallerPlanModel:
    def invoke(self, messages):
        text = messages[-1].content
        payload = json.loads(text[text.index("{"):])
        return AIMessage(content=json.dumps({"items": [
            {"key": change["key"], "operation": change["operation"],
             "decision": "block" if change["operation"] in {"blocked", "guarded"} else "apply",
             "summary": "Validated selected skill", "reason": change["reason"]}
            for change in payload["authoritative_changes"]
        ]}))


def _installer_apply_step(messages):
    receipt = next(json.loads(message.content) for message in reversed(messages)
                   if isinstance(message, ToolMessage) and message.name == "skill_install")
    return "skill_install", {"action": "apply", "preview_id": receipt.get("preview_id", "missing")}


def _real_installer_session(tmp_path, monkeypatch, steps, *, approve=True):
    from agent.extensions.manager import ExtensionManager
    model = _InstallerScriptModel(steps)
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _cfg: [])
    config = AgentConfig(
        persist_dir=str(tmp_path / "history"),
        extension_dropin_dir=str(tmp_path / "dropins"),
        extension_state_dir=str(tmp_path / "state"),
    )
    session = ChatSession(config, bash_approval_handler=lambda *_args: approve)
    session.extension_manager = ExtensionManager(config, model_factory=lambda _cfg: _InstallerPlanModel())
    return session, model


def _installer_test_archive(tmp_path, names=("writer",)):
    archive = tmp_path / "original bundle.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for name in names:
            handle.writestr(f"repo/{name}/SKILL.md", f"---\nname: {name}\ndescription: Original\n---\nRead forms.md.\n")
            handle.writestr(f"repo/{name}/forms.md", b"Root original\r\n")
            handle.writestr(f"repo/{name}/scripts/never.py", b"raise RuntimeError('must not run')\n")
    return archive


def _installer_extract_step(archive, prepared, *, name="writer"):
    helper = Path(__file__).resolve().parents[1] / "skills/skill-installer/zip_bundle.py"
    command = shlex.join([sys.executable, str(helper), "extract", str(archive),
                          "--root", f"repo/{name}", "--destination", str(prepared)])
    return "bash", {"command": command, "description": "Prepare the selected original ZIP bundle in test temp"}


@pytest.mark.parametrize("slash,approve", [(False, True), (True, True), (False, False)])
def test_installer_real_tool_loop_preserves_bundle_and_reports_actual_result(tmp_path, monkeypatch, slash, approve):
    from agent.extensions.registry import load_registry
    archive = _installer_test_archive(tmp_path)
    archive_before = archive.read_bytes()
    prepared = tmp_path / "prepared"
    steps = [
        ("skill_install", {"action": "status"}),
        _installer_extract_step(archive, prepared),
        ("skill_install", {"action": "preview", "prepared_path": str(prepared)}),
        _installer_apply_step,
        "MODEL CLAIM: installed everything successfully",
    ]
    session, model = _real_installer_session(tmp_path, monkeypatch, steps, approve=approve)
    session.set_thinking_mode("extended")
    if slash:
        result = asyncio.run(execute_slash_command(
            parse_slash_command(f'/skill-installer install "{archive}"'),
            SlashCommandContext(session=session, registry=build_default_registry(session)),
        ))
        answer = asyncio.run(session.turn(result.followup_input, skill_name=result.skill_name))
    else:
        answer = asyncio.run(session.turn(f'請用 skill-installer 安裝 "{archive}"'))
    registry = load_registry(Path(session.config.extension_state_dir))

    assert archive.read_bytes() == archive_before
    assert "MODEL CLAIM" not in answer
    assert session.thinking_mode == "extended"
    assert session.active_skill_runtime is None
    assert session._skill_installer.pending is False
    assert "skill_install" not in model.bindings[0]
    assert any("skill_install" in tools for tools in model.bindings[1:])
    if approve:
        installed = Path(session.config.extension_state_dir) / registry.extensions["skill:writer"].installed_relpath
        assert (installed / "forms.md").read_bytes() == b"Root original\r\n"
        assert (installed / "scripts/never.py").read_bytes() == b"raise RuntimeError('must not run')\n"
        assert (Path(session.config.extension_dropin_dir) / "skill/writer/forms.md").read_bytes() == b"Root original\r\n"
        assert "added" in answer and str(installed) in answer
    else:
        assert not registry.extensions
        assert not prepared.exists()
        assert "added" not in answer
    denied = json.loads(asyncio.run(session.skill_install_tool.ainvoke({"action": "apply", "preview_id": "stolen"})))
    assert denied["status"] == "error"


@pytest.mark.parametrize("reply", ["第二個", "取消"])
def test_installer_real_graph_continues_selection_or_cancels(tmp_path, monkeypatch, reply):
    from agent.extensions.registry import load_registry
    archive = _installer_test_archive(tmp_path, names=("alpha", "writer"))
    prepared = tmp_path / "prepared"
    steps = [("skill_install", {"action": "status"}), "Choose one"]
    if reply == "第二個":
        steps += [("skill_install", {"action": "status"}), _installer_extract_step(archive, prepared),
                  ("skill_install", {"action": "preview", "prepared_path": str(prepared)}),
                  _installer_apply_step, "MODEL CLAIM"]
    else:
        steps += [("skill_install", {"action": "status"}), "MODEL CLAIM"]
    session, _model = _real_installer_session(tmp_path, monkeypatch, steps)
    session.set_thinking_mode("extended")
    question = asyncio.run(session.turn(f'請用 skill-installer 安裝 "{archive}"'))
    assert "1. alpha" in question and "2. writer" in question
    assert session._skill_installer.pending
    assert session.thinking_mode == "normal"
    answer = asyncio.run(session.turn(reply))
    assert "MODEL CLAIM" not in answer
    assert session.thinking_mode == "extended"
    assert not session._skill_installer.pending
    registry = load_registry(Path(session.config.extension_state_dir))
    assert set(registry.extensions) == ({"skill:writer"} if reply == "第二個" else set())



def test_installer_cancellation_clears_pending_authority_and_restores_mode(tmp_path, monkeypatch):
    archive = _installer_test_archive(tmp_path, names=("alpha", "writer"))
    session, _model = _real_installer_session(tmp_path, monkeypatch, [
        ("skill_install", {"action": "status"}), "Choose one",
    ])
    session.set_thinking_mode("extended")
    asyncio.run(session.turn(f'請用 skill-installer 安裝 "{archive}"'))

    class CancelGraph:
        async def astream(self, *_args, **_kwargs):
            raise asyncio.CancelledError()
            yield

    session.graph = CancelGraph()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(session.turn("第二個"))
    assert not session._skill_installer.pending
    assert session.active_skill_runtime is None
    assert session.thinking_mode == "extended"
    assert not Path(session.config.extension_state_dir).exists()
