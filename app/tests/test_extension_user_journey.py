"""User-perspective sandbox acceptance journey for drop-in extensions."""

import asyncio
import hashlib
import json
import os
import shutil
import sys
import argparse
import shlex
import uuid
import zipfile

import pytest
from pathlib import Path
from unittest.mock import patch

import yaml
from langchain_core.messages import AIMessage

from agent.cli.slash_commands import (
    SlashCommandContext,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from agent.config import AgentConfig
from agent.extensions.manager import ExtensionManager
from agent.extensions.registry import load_registry
from agent.extensions.startup import load_extension_startup
from agent.mcp import load_mcp_tools_with_families
from agent.skills.runtime import load_skill_runtime


class _DeterministicManagementModel:
    """Stand in only for the external LLM; host validation remains real."""

    def invoke(self, messages):
        content = messages[-1].content
        payload = json.loads(content[content.index("{") :])
        items = []
        for change in payload["authoritative_changes"]:
            operation = change["operation"]
            blocked = operation in {"blocked", "guarded"}
            items.append(
                {
                    "key": change["key"],
                    "operation": operation,
                    "decision": "block" if blocked else "apply",
                    "summary": f"Accept validated {operation} for next restart.",
                    "reason": change["reason"] if blocked else None,
                    "mcp_descriptor": None,
                }
            )
        return AIMessage(content=json.dumps({"items": items}))


class _TrialSession:
    def __init__(
        self,
        config,
        manager,
        *,
        running_revision=0,
        mcp_families=None,
        diagnostics=(),
        loaded_skills=(),
    ):
        self.config = config
        self.extension_manager = manager
        self.running_extension_revision = running_revision
        self.mcp_families = dict(mcp_families or {})
        self.extension_startup_diagnostics = tuple(diagnostics)
        self.loaded_skills = tuple(loaded_skills)


def _slash(session, command: str):
    parsed = parse_slash_command(command)
    assert parsed is not None
    return asyncio.run(
        execute_slash_command(
            parsed,
            SlashCommandContext(
                session=session,
                registry=build_default_registry(),
            ),
        )
    )


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_skill(bundle: Path, *, version: str) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "references").mkdir(exist_ok=True)
    (bundle / "SKILL.md").write_text(
        "---\n"
        "name: sandbox-writer\n"
        "description: Use for the extension sandbox acceptance journey.\n"
        "---\n\n"
        f"# Sandbox Writer\n\nFollow {version} instructions.\n",
        encoding="utf-8",
    )
    (bundle / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "resources": [
                    {
                        "path": "references/checklist.md",
                        "use_when": "Always in this acceptance journey.",
                        "pinned": True,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (bundle / "references" / "checklist.md").write_text(
        "Sandbox checklist loaded.\n",
        encoding="utf-8",
    )


def _write_mcp(bundle: Path) -> None:
    bundle.mkdir(parents=True)
    interpreter = Path(sys.prefix) / "bin" / "python"
    server_path = bundle / "server"
    server_path.write_text(
        f"#!{interpreter}\n"
        "import os\n"
        "from pathlib import Path\n"
        "from mcp.server.fastmcp import FastMCP\n\n"
        "Path(os.environ['SANDBOX_MARKER']).write_text(\n"
        "    'started', encoding='utf-8'\n"
        ")\n"
        "server = FastMCP('sandbox-extension')\n\n"
        "@server.tool()\n"
        "def sandbox_echo(text: str) -> str:\n"
        "    \"\"\"Echo text with the injected sandbox prefix.\"\"\"\n"
        "    return f\"{os.environ['SANDBOX_PREFIX']}:{text}\"\n\n"
        "if __name__ == '__main__':\n"
        "    server.run(transport='stdio')\n",
        encoding="utf-8",
    )
    server_path.chmod(0o755)
    (bundle / "extension.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "kind": "mcp",
                "id": "sandbox",
                "family": "sandbox",
                "scope": "global",
                "runtime": {
                    "transport": "stdio",
                    "command": "./server",
                    "args": [],
                    "cwd": ".",
                },
                "environment": {
                    "SANDBOX_PREFIX": {
                        "from_env": "EXTENSION_SANDBOX_PREFIX",
                        "required": True,
                    },
                    "SANDBOX_MARKER": {
                        "from_env": "EXTENSION_SANDBOX_MARKER",
                        "required": True,
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_user_dropin_apply_restart_use_update_delete(monkeypatch, tmp_path):
    dropin_root = tmp_path / "dropins"
    state_root = tmp_path / "state"
    skill_bundle = dropin_root / "skill" / "sandbox-writer"
    mcp_bundle = dropin_root / "mcp" / "sandbox"
    _write_skill(skill_bundle, version="version-one")
    _write_mcp(mcp_bundle)
    marker = tmp_path / "mcp-started.txt"
    monkeypatch.setenv("EXTENSION_SANDBOX_PREFIX", "sandbox")
    monkeypatch.setenv("EXTENSION_SANDBOX_MARKER", str(marker))
    monkeypatch.setenv(
        "PATH",
        str(Path(sys.executable).parent)
        + os.pathsep
        + os.environ.get("PATH", ""),
    )
    config = AgentConfig(
        extension_dropin_dir=str(dropin_root),
        extension_state_dir=str(state_root),
    )
    manager = ExtensionManager(
        config,
        model_factory=lambda _config: _DeterministicManagementModel(),
    )
    running = _TrialSession(config, manager)
    source_hashes = {
        "skill": _tree_hash(skill_bundle),
        "mcp": _tree_hash(mcp_bundle),
    }

    before = _slash(running, "/Extension-Management status")
    dry_run = _slash(running, "/Extension-Management --dry-run")
    print("\n=== status before apply ===\n" + before.message)
    print("\n=== dry-run ===\n" + dry_run.message)
    assert str(dropin_root.resolve()) in before.message
    assert "restart_required: false" in before.message
    assert "skill:sandbox-writer: add -> apply" in dry_run.message
    assert "mcp:sandbox: add -> apply" in dry_run.message
    assert "SANDBOX_PREFIX <- $EXTENSION_SANDBOX_PREFIX (required)" in (
        dry_run.message
    )
    assert not state_root.exists()

    with patch("builtins.input", return_value="yes"):
        applied = _slash(running, "/Extension-Management")
    print("\n=== apply ===\n" + applied.message)
    assert "revision 0 -> 1" in applied.message
    assert "restart_required: true" in applied.message
    assert running.running_extension_revision == 0
    assert running.loaded_skills == ()
    assert _tree_hash(skill_bundle) == source_hashes["skill"]
    assert _tree_hash(mcp_bundle) == source_hashes["mcp"]
    assert not marker.exists()

    registry = load_registry(state_root)
    installed_mcp = state_root / registry.extensions[
        "mcp:sandbox"
    ].installed_relpath
    assert (installed_mcp / "server").is_file()
    restarted = load_extension_startup(config)
    assert restarted.revision == 1
    assert [skill.name for skill in restarted.skills] == ["sandbox-writer"]
    assert restarted.global_mcp_families == frozenset({"sandbox"})
    assert not marker.exists()

    tools, families = asyncio.run(
        load_mcp_tools_with_families(specs=list(restarted.mcp_specs))
    )
    assert [tool.name for tool in tools] == ["sandbox_echo"]
    assert families == {"sandbox_echo": "sandbox"}
    echo_result = asyncio.run(tools[0].ainvoke({"text": "hello"}))
    print("\n=== MCP call after restart ===\n" + str(echo_result))
    assert echo_result[0]["type"] == "text"
    assert echo_result[0]["text"] == "sandbox:hello"
    assert marker.read_text(encoding="utf-8") == "started"
    assert _tree_hash(mcp_bundle) == source_hashes["mcp"]

    runtime_v1 = load_skill_runtime(
        "sandbox-writer",
        config=config,
        all_tools=tools,
        mcp_families=families,
        global_mcp_families=restarted.global_mcp_families,
        catalog=restarted.skills,
    )
    assert "version-one" in runtime_v1.instructions
    assert runtime_v1.pinned_references == {
        "references/checklist.md": "Sandbox checklist loaded.\n"
    }
    assert runtime_v1.tool_access.effective_tools == ("sandbox_echo",)

    after_restart_session = _TrialSession(
        config,
        manager,
        running_revision=restarted.revision,
        mcp_families=families,
        diagnostics=restarted.diagnostics,
        loaded_skills=restarted.skills,
    )
    after_restart = _slash(
        after_restart_session,
        "/Extension-Management status",
    )
    print("\n=== status after restart ===\n" + after_restart.message)
    assert "running revision: 1" in after_restart.message
    assert "restart_required: false" in after_restart.message
    assert "running MCP: sandbox" in after_restart.message

    _write_skill(skill_bundle, version="version-two")
    with patch("builtins.input", return_value="yes"):
        updated = _slash(
            after_restart_session,
            "/Extension-Management",
        )
    print("\n=== Skill update apply ===\n" + updated.message)
    assert "skill:sandbox-writer: updated" in updated.message
    assert "revision 1 -> 2" in updated.message
    assert "version-one" in runtime_v1.instructions

    restarted_v2 = load_extension_startup(config)
    runtime_v2 = load_skill_runtime(
        "sandbox-writer",
        config=config,
        all_tools=tools,
        mcp_families=families,
        global_mcp_families=restarted_v2.global_mcp_families,
        catalog=restarted_v2.skills,
    )
    assert restarted_v2.revision == 2
    assert "version-two" in runtime_v2.instructions

    assert skill_bundle.is_relative_to(dropin_root / "skill")
    shutil.rmtree(skill_bundle)
    delete_session = _TrialSession(
        config,
        manager,
        running_revision=restarted_v2.revision,
        mcp_families=families,
        loaded_skills=restarted_v2.skills,
    )
    with patch("builtins.input", return_value="yes"):
        deleted = _slash(delete_session, "/Extension-Management")
    print("\n=== Skill delete apply ===\n" + deleted.message)
    assert "skill:sandbox-writer: removed" in deleted.message
    assert "revision 2 -> 3" in deleted.message
    assert [skill.name for skill in delete_session.loaded_skills] == [
        "sandbox-writer"
    ]

    restarted_v3 = load_extension_startup(config)
    assert restarted_v3.revision == 3
    assert restarted_v3.skills == ()
    assert len(restarted_v3.mcp_specs) == 1
    assert set(load_registry(state_root).extensions) == {"mcp:sandbox"}


@pytest.mark.parametrize("entry", ["cli", "desktop"])
def test_conversational_zip_acceptance(entry, tmp_path, monkeypatch, capsys):
    """Optional local upstream archive; never fetch from the network in pytest."""
    from agent.cli import chat
    from agent.desktop.service import DesktopService, DesktopServiceError
    from agent.session import ChatSession
    from test_skill_adherence import _InstallerScriptModel, _installer_apply_step

    config = AgentConfig(
        persist_dir=str(tmp_path / "store"),
        extension_dropin_dir=str(tmp_path / "dropins"),
        extension_state_dir=str(tmp_path / "state"),
        plan_logs_dir=str(tmp_path / "plans"),
    )
    root = Path(config.extension_dropin_dir)
    (root / "skill").mkdir(parents=True)
    archive = root / "skill" / "original.zip"
    provided = os.environ.get("ISSUE10_ACCEPTANCE_ZIP")
    if provided:
        shutil.copyfile(provided, archive)
    else:
        with zipfile.ZipFile(archive, "w") as handle:
            for name in ("alpha", "pdf"):
                handle.writestr(f"fixture/skills/{name}/SKILL.md", f"---\nname: {name}\ndescription: Local fixture\n---\nRead forms.md.\n")
                handle.writestr(f"fixture/skills/{name}/forms.md", b"Original root forms\r\n")
                handle.writestr(f"fixture/skills/{name}/scripts/never.py", b"raise RuntimeError('never execute')\n")
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as handle:
        selected_root = next(name.rsplit("/", 1)[0] for name in handle.namelist()
                             if name.endswith("/skills/pdf/SKILL.md"))
        prefix = selected_root + "/"
        expected = {info.filename[len(prefix):]: handle.read(info) for info in handle.infolist()
                    if info.filename.startswith(prefix) and not info.is_dir()}
    other = root / "skill" / "untouched"
    other.mkdir()
    (other / "SKILL.md").write_text("---\nname: untouched\ndescription: Pending\n---\n", encoding="utf-8")
    pending_mcp = root / "mcp" / "untouched-mcp"
    pending_mcp.mkdir(parents=True)
    (pending_mcp / "server.py").write_bytes(b"# unselected, never execute\n")
    untouched = {path: path.read_bytes() for folder in (other, pending_mcp) for path in folder.rglob("*") if path.is_file()}
    prepared = tmp_path / "prepared-pdf"
    helper = Path(__file__).resolve().parents[1] / "skills/skill-installer/zip_bundle.py"
    command = shlex.join([sys.executable, str(helper), "extract", str(archive),
                          "--root", selected_root, "--destination", str(prepared)])

    def read_root(messages):
        root_line = next(line for message in messages if message.type == "system"
                         for line in str(message.content).splitlines() if line.startswith("skill_root: "))
        return "read_file", {"path": str(Path(root_line.removeprefix("skill_root: ")) / "forms.md")}

    def confirm_root_read(messages):
        result = next(json.loads(message.content) for message in reversed(messages)
                      if message.type == "tool" and message.name == "read_file")
        assert result.get("content")
        assert expected["forms.md"].decode("utf-8").replace("\r\n", "\n").startswith(result["content"])
        assert result["path"].endswith("/forms.md")
        return "Read the original root resource"

    steps = [("skill_install", {"action": "status"})]
    if entry == "desktop":
        steps += ["Choose a candidate", ("skill_install", {"action": "status"})]
    steps += [
        ("bash", {"command": command, "description": "Extract the authorized skill into isolated test temp"}),
        ("skill_install", {"action": "preview", "prepared_path": str(prepared)}),
        _installer_apply_step,
        "MODEL CLAIM MUST NOT BE TRUSTED",
        read_root, confirm_root_read,
    ]
    model = _InstallerScriptModel(steps)
    manager = ExtensionManager(config, model_factory=lambda _cfg: _DeterministicManagementModel())
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _cfg: [])
    monkeypatch.setattr("agent.session.ExtensionManager", lambda _cfg: manager)
    real_create = ChatSession.create
    sessions = []

    async def create(cls, cfg, **kwargs):
        kwargs.setdefault("bash_approval_handler", lambda *_args: True)
        session = await real_create(cfg, **kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr(ChatSession, "create", classmethod(create))
    answers = []
    events = []
    approval_tasks = []

    async def scenario():
        if entry == "cli":
            monkeypatch.setattr(chat, "AgentConfig", lambda **_kwargs: config)
            inputs = iter([f'請用 skill-installer 安裝 "{archive}" 中的 pdf', "exit"])
            async def reader(_prompt):
                return next(inputs)
            await chat._run(argparse.Namespace(max_graph_steps=80, no_mcp=True), read_line=reader)
            answers.append(capsys.readouterr().out)
            fresh = await ChatSession.create(config, load_mcp=False)
            assert "pdf" in {skill.name for skill in fresh.loaded_skills}
            await fresh.turn("Read forms.md only, do not execute scripts", skill_name="pdf")
        else:
            service = DesktopService(config=config, original_cwd=tmp_path, environ={}, approval_timeout_seconds=3.0)
            await service.dispatch("session.create", {"loadMcp": False})
            class Sink:
                request_id = uuid.uuid4().hex
                def __call__(self, method, payload):
                    events.append((method, payload))
                    if method == "approval.required":
                        async def approve():
                            with pytest.raises(DesktopServiceError) as busy:
                                await service.dispatch("extensions.preview", {})
                            assert busy.value.code == "BUSY_EXTENSION_OPERATION"
                            await service.dispatch("approval.resolve", {
                                "approvalId": payload["approvalId"], "parentRequestId": payload["parentRequestId"],
                                "turnId": payload["turnId"], "approved": True,
                            })
                        approval_tasks.append(asyncio.create_task(approve()))
            async def turn(text):
                return await service.dispatch("session.turn", {
                    "text": text, "turnId": uuid.uuid4().hex, "retry": False,
                }, event_sink=Sink())
            first = await turn(f'請用 skill-installer 安裝 "{archive}"')
            assert "pdf" in first["text"] and service.session._skill_installer.pending
            result = await turn("pdf")
            if approval_tasks:
                await asyncio.gather(*approval_tasks)
            answers.append(result["text"])
            assert result["responseKind"] == "answer"
            snapshot = service.session._conversation_snapshot
            assert len(snapshot.document.turns) == 2
            assert all(item.kind == "conversational" for item in snapshot.document.turns)
            await service.dispatch("session.create", {"loadMcp": False})
            assert "pdf" in {skill.name for skill in service.session.loaded_skills}
            await turn("/pdf Read forms.md only, do not execute scripts")
            await service.dispatch("session.shutdown", {})

    asyncio.run(scenario())
    registry = load_registry(Path(config.extension_state_dir))
    assert set(registry.extensions) == {"skill:pdf"}
    installed = Path(config.extension_state_dir) / registry.extensions["skill:pdf"].installed_relpath
    for folder in (root / "skill/pdf", installed):
        actual = {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()}
        assert actual == expected
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_hash
    assert all(path.read_bytes() == raw for path, raw in untouched.items())
    assert "pdf" not in {skill.name for skill in sessions[0].loaded_skills}
    assert str(installed) in answers[0] and "added" in answers[0]
    assert "MODEL CLAIM" not in answers[0]
    assert model.calls[-1] == ("read_file", {"path": str(installed / "forms.md")})
    if entry == "desktop":
        assert len([event for event in events if event[0] == "approval.required"]) == 1
    print(json.dumps({"entry": entry, "upstream": bool(provided), "archive_sha256": archive_hash,
                      "selected_root": selected_root, "files_verified": len(expected),
                      "bundle_bytes": sum(map(len, expected.values())),
                      "installed": str(installed), "calls": [name for name, _args in model.calls]}, sort_keys=True))
