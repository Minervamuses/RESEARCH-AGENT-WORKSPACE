"""End-to-end adherence checks for slash-command skill runtime."""

import asyncio
import json
import shlex
import sys
import threading
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
    session = ChatSession(config, bash_approval_handler=approve if callable(approve) else lambda *_args: approve)
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



@pytest.mark.parametrize("cleanup", [False, True])
def test_installer_shell_denial_before_final_clears_pending_and_reports_denial(tmp_path, monkeypatch, cleanup):
    archive = _installer_test_archive(tmp_path)
    prepared = tmp_path / "prepared"
    session, model = _real_installer_session(tmp_path, monkeypatch, [
        ("skill_install", {"action": "status"}),
        _installer_extract_step(archive, prepared),
        *([("bash", {"command": "true", "description": "Represent successful cleanup of owned temp"})] if cleanup else []),
        "The user denied the shell operation, so I stopped.",
    ], approve=lambda command, *_args: command == "true")
    session.set_thinking_mode("extended")

    answer = asyncio.run(session.turn(f'請用 skill-installer 安裝 "{archive}"'))

    assert "denied" in answer.lower() or "拒絕" in answer
    assert not session._skill_installer.pending
    assert session.thinking_mode == "extended"
    assert session.active_skill_runtime is None
    assert [name for name, _args in model.calls] == ["skill_install", "bash"] + (["bash"] if cleanup else [])
    assert not prepared.exists()
    assert not (Path(session.config.extension_dropin_dir) / "skill/writer").exists()
    assert not Path(session.config.extension_state_dir).exists()


def test_installer_slow_preview_keeps_loop_responsive_and_cancellation_waits_for_cleanup(tmp_path, monkeypatch):
    archive = _installer_test_archive(tmp_path)
    prepared = tmp_path / "prepared"
    session, _model = _real_installer_session(tmp_path, monkeypatch, [
        ("skill_install", {"action": "status"}),
        _installer_extract_step(archive, prepared),
        ("skill_install", {"action": "preview", "prepared_path": str(prepared)}),
        "Preview complete",
    ])
    session.set_thinking_mode("extended")
    preview_entered = threading.Event()
    preview_finished = threading.Event()
    release_preview = threading.Event()
    original_preview = session.extension_manager.preview

    def held_preview(*args, **kwargs):
        preview_entered.set()
        try:
            release_preview.wait(timeout=1.0)
            return original_preview(*args, **kwargs)
        finally:
            preview_finished.set()

    monkeypatch.setattr(session.extension_manager, "preview", held_preview)

    async def cancel_during_preview():
        task = asyncio.create_task(session.turn(f'請用 skill-installer 安裝 "{archive}"'))
        responsive = False
        waited_for_worker = False
        try:
            async with asyncio.timeout(3):
                while not preview_entered.is_set():
                    await asyncio.sleep(0.001)
                responsive = not preview_finished.is_set() and not release_preview.is_set()
                task.cancel()
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                waited_for_worker = not task.done()
        finally:
            release_preview.set()
            if not task.done() and not task.cancelling():
                task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=3)
        assert responsive, "slow host preview blocked the event-loop heartbeat"
        assert waited_for_worker, "cancellation returned while host work was still running"

    asyncio.run(cancel_during_preview())

    assert preview_finished.is_set()
    assert not session._skill_installer.pending
    assert session.thinking_mode == "extended"
    assert session.active_skill_runtime is None
    skill_root = Path(session.config.extension_dropin_dir) / "skill"
    assert not (skill_root / "writer").exists()
    assert not list(skill_root.glob(".skill-installer-*"))
    assert not Path(session.config.extension_state_dir).exists()


def test_installer_new_request_reports_cleanup_conflict_without_replacing_transaction(tmp_path, monkeypatch):
    archive = _installer_test_archive(tmp_path)
    prepared = tmp_path / "prepared"
    next_source = tmp_path / "next-request"
    next_source.mkdir()
    next_archive = _installer_test_archive(next_source, names=("alpha",))
    session, _model = _real_installer_session(tmp_path, monkeypatch, [
        ("skill_install", {"action": "status"}),
        _installer_extract_step(archive, prepared),
        ("skill_install", {"action": "preview", "prepared_path": str(prepared)}),
        "Preview complete",
        ("skill_install", {"action": "status"}),
        "Next request",
    ])
    session.set_thinking_mode("extended")
    source = Path(session.config.extension_dropin_dir) / "skill/writer"
    source.mkdir(parents=True)
    original_skill = b"---\nname: writer\ndescription: Existing skill\n---\nOriginal instructions\n"
    (source / "SKILL.md").write_bytes(original_skill)
    (source / "forms.md").write_bytes(b"Existing source reference")
    first_request = f'請用 skill-installer 更新 "{archive}"'
    asyncio.run(session.turn(first_request))
    assert session._skill_installer.pending
    backup = session._skill_installer._temporary
    assert backup is not None
    assert (backup / "previous/SKILL.md").read_bytes() == original_skill
    (source / "forms.md").write_bytes(b"User modification after preview")

    answer = asyncio.run(session.turn(f'請用 skill-installer 安裝 "{next_archive}"'))

    result = session._skill_installer.last_result
    assert result["status"] == "blocked"
    assert result["cleanup_conflict"] is True
    assert str(backup) in answer
    assert "cleanup" in answer.lower() or "保留" in answer
    assert session._skill_installer._request == first_request
    assert not session._skill_installer.pending
    assert session.thinking_mode == "extended"
    assert session.active_skill_runtime is None
    assert (source / "forms.md").read_bytes() == b"User modification after preview"
    assert (backup / "previous/SKILL.md").read_bytes() == original_skill
    assert (backup / "previous/forms.md").read_bytes() == b"Existing source reference"
    assert not (source.parent / "alpha").exists()
    assert not Path(session.config.extension_state_dir).exists()


def _previewed_installer(tmp_path, monkeypatch):
    archive = _installer_test_archive(tmp_path)
    prepared = tmp_path / "prepared"
    session, model = _real_installer_session(tmp_path, monkeypatch, [
        ("skill_install", {"action": "status"}),
        _installer_extract_step(archive, prepared),
        ("skill_install", {"action": "preview", "prepared_path": str(prepared)}),
        "Preview complete",
    ])
    source = Path(session.config.extension_dropin_dir) / "skill/writer"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_bytes(b"---\nname: writer\ndescription: Existing\n---\nOriginal\n")
    (source / "forms.md").write_bytes(b"Existing reference")
    session.set_thinking_mode("extended")
    asyncio.run(session.turn(f'請用 skill-installer 更新 "{archive}"'))
    assert session._skill_installer.pending
    backup = session._skill_installer._temporary
    assert backup is not None
    return session, model, source, backup


@pytest.mark.parametrize("skill_name", ["citation", "academic-paper-writing"])
def test_installer_skill_switch_exposes_cleanup_conflict_without_execution(
    tmp_path, monkeypatch, skill_name,
):
    from conftest import make_astream_graph
    from test_desktop_service import _service, _turn_params
    from test_thinking_session import _Factory, _default_models

    models = _default_models()
    monkeypatch.setattr("agent.session.get_chat_model_for_role", lambda _cfg, *, role: models[role])
    monkeypatch.setattr("agent.session.get_fusion_aggregator_model", lambda _cfg: models["aggregator"])
    session, model, source, backup = _previewed_installer(tmp_path, monkeypatch)
    factory = _Factory()
    session._fusion._graph_builder = factory
    session._prompt_master_skill_text_cache = "prompt-master skill"
    (source / "forms.md").write_bytes(b"User modification after preview")
    before = {
        path: path.read_bytes()
        for root in (source, backup) for path in root.rglob("*") if path.is_file()
    }
    graph = make_astream_graph(answer="New skill ran despite cleanup conflict")
    session.graph = graph
    runs = []
    original_run = session._run_turn

    async def observe_run(text):
        runs.append(text)
        return await original_run(text)

    monkeypatch.setattr(session, "_run_turn", observe_run)
    calls_before = list(model.calls)
    service = _service(tmp_path, config=session.config)
    service.session = session
    response = asyncio.run(service.dispatch(
        "session.turn", _turn_params(f"/{skill_name} draft"),
    ))
    assert "source cleanup conflict" in response["text"]
    assert "staged source changed; preserving user changes and backup" in response["text"]
    assert f"backup_path: {backup}" in response["text"]
    assert response["state"] == "completed"
    assert response["streamKind"] == "final_only" and response["chunkCount"] == 0
    assert runs == [] and graph.states == [] and model.calls == calls_before
    assert factory.calls == [] and all(not model.calls for model in models.values())
    assert before == {
        path: path.read_bytes()
        for root in (source, backup) for path in root.rglob("*") if path.is_file()
    }
    assert session.thinking_mode == "extended"
    assert session.active_skill_runtime is None
    turn = session.conversation_repository.load(session.session_id).document.turns[-1]
    assert turn.assistant_output == response["text"]


@pytest.mark.parametrize("skill_name", ["academic-paper-writing", "citation"])
def test_installer_skill_switch_persists_effective_mode(tmp_path, monkeypatch, skill_name):
    from conftest import make_astream_graph
    from test_thinking_session import _Factory, _default_models

    factory = _Factory()
    models = _default_models()
    # Keep real Fusion orchestration; only its graph/model boundaries are scripted.
    monkeypatch.setattr("agent.session.get_chat_model_for_role", lambda _cfg, *, role: models[role])
    monkeypatch.setattr("agent.session.get_fusion_aggregator_model", lambda _cfg: models["aggregator"])
    archive = _installer_test_archive(tmp_path, names=("alpha", "writer"))
    session, _model = _real_installer_session(tmp_path, monkeypatch, [
        ("skill_install", {"action": "status"}), "Choose one",
    ])
    session.config.thinking_fusion_proposer_models = ("p1", "p2", "p3")
    session.config.thinking_rewrite_model = "rewrite"
    session.config.thinking_reviewer_model = "reviewer"
    session.config.thinking_repair_model = "repair"
    session.config.thinking_fusion_aggregator_model = "aggregator"
    session._fusion._graph_builder = factory
    session._prompt_master_skill_text_cache = "prompt-master skill"
    session.set_thinking_mode("extended")
    asyncio.run(session.turn(f'請用 skill-installer 安裝 "{archive}"'))
    assert session._skill_installer.pending and session.thinking_mode == "normal"
    pending_modes = []
    graph = make_astream_graph(on_state=lambda _state: pending_modes.append(
        session.conversation_repository.load(session.session_id).document.turns[-1].thinking_mode
    ))
    session.graph = graph
    parsed = parse_slash_command(f"/{skill_name} draft")
    selected = asyncio.run(execute_slash_command(
        parsed, SlashCommandContext(session=session, registry=build_default_registry(session)),
    ))
    answer = asyncio.run(session.turn(
        selected.followup_input, display_input=parsed.raw_text, skill_name=selected.skill_name,
    ))
    if skill_name == "academic-paper-writing":
        assert answer == "fused"
        assert {call["model_id"] for call in factory.calls} == {"p1", "p2", "p3"}
        assert len(models["aggregator"].calls) == len(models["reviewer"].calls) == 1
        assert graph.states == []
    else:
        assert answer == "ok" and pending_modes == ["normal"]
        assert factory.calls == [] and models["aggregator"].calls == models["reviewer"].calls == []
    expected = "normal" if skill_name == "citation" else "extended"
    snapshot = session.conversation_repository.load(session.session_id)
    saved = json.loads(session.conversation_repository.path_for(session.session_id).read_text())
    assert snapshot.document.turns[-1].thinking_mode == expected
    assert saved["turns"][-1]["thinkingMode"] == expected
    assert session.thinking_mode == "extended"
    assert session.active_skill_runtime is None and not session._skill_installer.pending


def test_installer_skill_switch_load_failure_and_duplicate_preserve_pending(tmp_path, monkeypatch):
    session, model, source, backup = _previewed_installer(tmp_path, monkeypatch)
    snapshot = session.conversation_repository.load(session.session_id)
    original_turn = snapshot.document.turns[-1]
    before = {path: path.read_bytes()
              for root in (source, backup) for path in root.rglob("*") if path.is_file()}
    runtime = session.active_skill_runtime
    mode = session.thinking_mode
    transaction = session._skill_installer._preview_id
    calls = list(model.calls)
    loads = []

    def unavailable(name):
        loads.append(name)
        raise ValueError("fixture runtime unavailable")

    monkeypatch.setattr(session, "_load_skill_runtime", unavailable)
    # A completed installer duplicate must return before loading or cleanup.
    duplicate = asyncio.run(session.turn(
        original_turn.semantic_input, display_input=original_turn.display_input,
        turn_id=original_turn.turn_id, skill_name="skill-installer", retry=True,
    ))
    assert duplicate == original_turn.assistant_output and loads == []
    with pytest.raises(ValueError, match="fixture runtime unavailable"):
        asyncio.run(session.turn("draft", skill_name="academic-paper-writing"))
    assert loads == ["academic-paper-writing"]
    assert session.active_skill_runtime is runtime and session.thinking_mode == mode
    assert session._skill_installer.pending
    assert session._skill_installer._preview_id == transaction
    assert session._skill_installer._temporary == backup
    assert model.calls == calls
    assert before == {path: path.read_bytes()
                      for root in (source, backup) for path in root.rglob("*") if path.is_file()}
