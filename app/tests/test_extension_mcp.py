"""Descriptor, approval, and restart-loading tests for drop-in MCP."""

import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from agent.config import AgentConfig
from agent.cli.extension_management import render_preview
from agent.extensions.manager import ExtensionManager
from agent.extensions.mcp_manifest import (
    MCPManifestError,
    descriptor_for_bundle,
    resolve_mcp_candidate,
    validate_mcp_descriptor,
)
from agent.extensions.registry import load_registry, write_registry
from agent.extensions.startup import load_extension_startup
from agent.tool_access import resolve_tool_access


class _PlanModel:
    def __init__(self, descriptor=None, *, decision="apply"):
        self.descriptor = descriptor
        self.decision = decision

    def invoke(self, _messages):
        item = {
            "key": "mcp:clock",
            "operation": "add",
            "decision": self.decision,
            "summary": "Install clock MCP for the next restart.",
            "reason": None,
            "mcp_descriptor": self.descriptor,
        }
        return AIMessage(content=json.dumps({"items": [item]}))


class _Tool:
    def __init__(self, name):
        self.name = name


def _config(tmp_path: Path) -> AgentConfig:
    return AgentConfig(
        extension_dropin_dir=str(tmp_path / "dropins"),
        extension_state_dir=str(tmp_path / "state"),
    )


def _private_skill(tmp_path: Path) -> Path:
    bundle = tmp_path / "private"
    bundle.mkdir()
    path = bundle / "SKILL.md"
    path.write_text(
        "---\n"
        "name: extension-management\n"
        "description: Test manager\n"
        "---\n\n"
        "Plan all authoritative changes.\n",
        encoding="utf-8",
    )
    return path


def _descriptor(*, scope: str = "global") -> dict:
    return {
        "schema_version": 1,
        "kind": "mcp",
        "id": "clock",
        "family": "clock",
        "scope": scope,
        "runtime": {
            "transport": "stdio",
            "command": "python3",
            "args": ["server.py"],
            "cwd": ".",
        },
        "environment": {
            "CLOCK_TOKEN": {
                "from_env": "TEST_CLOCK_TOKEN",
                "required": True,
            }
        },
    }


def _write_mcp(config: AgentConfig, *, with_descriptor: bool = True) -> Path:
    bundle = Path(config.extension_dropin_dir) / "mcp" / "clock"
    bundle.mkdir(parents=True)
    (bundle / "server.py").write_text(
        "from pathlib import Path\n"
        "Path(__file__).with_name('started.txt').write_text('started')\n",
        encoding="utf-8",
    )
    if with_descriptor:
        import yaml

        (bundle / "extension.yaml").write_text(
            yaml.safe_dump(_descriptor(), sort_keys=False),
            encoding="utf-8",
        )
    return bundle


def _manager(config, private, model):
    return ExtensionManager(
        config,
        private_skill_path=private,
        model_factory=lambda _config: model,
    )


def test_strict_descriptor_resolves_direct_interpreter_binding(
    monkeypatch, tmp_path
):
    config = _config(tmp_path)
    bundle = _write_mcp(config)
    monkeypatch.setenv("TEST_CLOCK_TOKEN", "secret-value")

    descriptor = descriptor_for_bundle(
        bundle,
        extension_id="clock",
        proposal=None,
    )
    candidate = resolve_mcp_candidate(
        descriptor,
        bundle=bundle,
        source_hash="a" * 64,
    )

    assert Path(candidate.resolved_command).name.startswith("python")
    assert candidate.args == ("server.py",)
    assert candidate.cwd == str(bundle.resolve())
    assert candidate.env["CLOCK_TOKEN"] == "secret-value"
    assert candidate.env_names == ("CLOCK_TOKEN",)
    assert len(candidate.binding_hash) == 64

    rendered = render_preview(
        _manager(
            config,
            _private_skill(tmp_path),
            _PlanModel(),
        ).preview()
    )
    assert "CLOCK_TOKEN <- $TEST_CLOCK_TOKEN (required)" in rendered


def test_manager_requires_exact_mcp_approval_and_never_starts_process(
    monkeypatch, tmp_path
):
    config = _config(tmp_path)
    bundle = _write_mcp(config)
    private = _private_skill(tmp_path)
    monkeypatch.setenv("TEST_CLOCK_TOKEN", "secret-value")
    manager = _manager(config, private, _PlanModel())
    preview = manager.preview()

    report = manager.apply(preview)

    assert report.items[0].outcome == "pending_approval"
    assert load_registry(Path(config.extension_state_dir)).extensions == {}
    assert not (bundle / "started.txt").exists()


def test_approved_mcp_is_persisted_and_loaded_only_on_next_startup(
    monkeypatch, tmp_path
):
    config = _config(tmp_path)
    raw_bundle = _write_mcp(config)
    private = _private_skill(tmp_path)
    monkeypatch.setenv("TEST_CLOCK_TOKEN", "secret-value")
    manager = _manager(config, private, _PlanModel())
    preview = manager.preview()
    binding = preview.mcp_candidates["mcp:clock"].binding_hash

    report = manager.apply(
        preview,
        approved_mcp_bindings={binding},
    )
    registry = load_registry(Path(config.extension_state_dir))
    startup = load_extension_startup(
        config,
        env={"PATH": str(Path(preview.mcp_candidates["mcp:clock"].resolved_command).parent),
             "TEST_CLOCK_TOKEN": "secret-value"},
    )

    assert report.items[0].outcome == "added"
    assert report.restart_required is True
    assert registry.extensions["mcp:clock"].execution_approved is True
    assert len(startup.mcp_specs) == 1
    assert startup.mcp_specs[0].sanitize_stdout is False
    assert startup.mcp_specs[0].family == "clock"
    assert startup.global_mcp_families == frozenset({"clock"})
    assert not (raw_bundle / "started.txt").exists()


def test_agent_descriptor_proposal_is_used_only_when_file_is_missing(
    monkeypatch, tmp_path
):
    config = _config(tmp_path)
    _write_mcp(config, with_descriptor=False)
    private = _private_skill(tmp_path)
    monkeypatch.setenv("TEST_CLOCK_TOKEN", "secret-value")
    manager = _manager(config, private, _PlanModel(_descriptor()))

    preview = manager.preview()

    assert preview.host_blocks == {}
    assert preview.mcp_candidates["mcp:clock"].descriptor.id == "clock"


def test_host_blocks_unsupported_command_even_when_agent_says_apply(
    monkeypatch, tmp_path
):
    config = _config(tmp_path)
    _write_mcp(config, with_descriptor=False)
    private = _private_skill(tmp_path)
    descriptor = _descriptor()
    descriptor["runtime"]["command"] = "npm"
    descriptor["runtime"]["args"] = ["start"]
    monkeypatch.setenv("TEST_CLOCK_TOKEN", "secret-value")
    manager = _manager(config, private, _PlanModel(descriptor))

    preview = manager.preview()

    assert "mcp:clock" not in preview.mcp_candidates
    assert "not an allowlisted interpreter" in preview.host_blocks["mcp:clock"]


def test_new_mcp_cannot_reuse_unchanged_applied_family(monkeypatch, tmp_path):
    config = _config(tmp_path)
    _write_mcp(config)
    private = _private_skill(tmp_path)
    monkeypatch.setenv("TEST_CLOCK_TOKEN", "secret-value")
    manager = _manager(config, private, _PlanModel())
    first = manager.preview()
    manager.apply(
        first,
        approved_mcp_bindings={
            first.mcp_candidates["mcp:clock"].binding_hash
        },
    )

    timer = Path(config.extension_dropin_dir) / "mcp" / "timer"
    timer.mkdir(parents=True)
    (timer / "server.py").write_text("pass\n", encoding="utf-8")
    descriptor = _descriptor()
    descriptor.update({"id": "timer", "family": "clock", "environment": {}})
    import yaml

    (timer / "extension.yaml").write_text(
        yaml.safe_dump(descriptor, sort_keys=False),
        encoding="utf-8",
    )

    class TimerPlanModel:
        def invoke(self, _messages):
            return AIMessage(
                content=json.dumps(
                    {
                        "items": [
                            {
                                "key": "mcp:timer",
                                "operation": "add",
                                "decision": "apply",
                                "summary": "Add timer.",
                                "reason": None,
                                "mcp_descriptor": None,
                            }
                        ]
                    }
                )
            )

    preview = _manager(config, private, TimerPlanModel()).preview()

    assert "mcp:timer" not in preview.mcp_candidates
    assert preview.host_blocks["mcp:timer"] == (
        "MCP family collides with mcp:clock"
    )


def test_literal_secret_and_missing_required_env_are_rejected(tmp_path):
    literal = _descriptor()
    literal["environment"] = {
        "API_TOKEN": {"value": "plaintext", "required": True}
    }
    with pytest.raises(MCPManifestError, match="secret-like"):
        validate_mcp_descriptor(literal, extension_id="clock")

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "server.py").write_text("pass\n", encoding="utf-8")
    descriptor = validate_mcp_descriptor(_descriptor(), extension_id="clock")
    with pytest.raises(MCPManifestError, match="required environment"):
        resolve_mcp_candidate(
            descriptor,
            bundle=bundle,
            source_hash="a" * 64,
            env={"PATH": "/usr/bin"},
        )


def test_builtin_mcp_identifiers_are_reserved():
    descriptor = _descriptor()
    descriptor["family"] = "github"

    with pytest.raises(MCPManifestError, match="reserved by a built-in"):
        validate_mcp_descriptor(descriptor, extension_id="clock")


def test_startup_rejects_tampered_approval_binding(monkeypatch, tmp_path):
    config = _config(tmp_path)
    _write_mcp(config)
    private = _private_skill(tmp_path)
    monkeypatch.setenv("TEST_CLOCK_TOKEN", "secret-value")
    manager = _manager(config, private, _PlanModel())
    preview = manager.preview()
    binding = preview.mcp_candidates["mcp:clock"].binding_hash
    manager.apply(preview, approved_mcp_bindings={binding})
    state_root = Path(config.extension_state_dir)
    registry = load_registry(state_root)
    entry = registry.extensions["mcp:clock"].model_copy(
        update={"command_binding_hash": "0" * 64}
    )
    write_registry(
        state_root,
        registry.model_copy(
            update={"extensions": {"mcp:clock": entry}}
        ),
    )

    startup = load_extension_startup(
        config,
        env={"PATH": "/usr/bin", "TEST_CLOCK_TOKEN": "secret-value"},
    )

    assert startup.mcp_specs == ()
    assert "binding differs from approval" in startup.diagnostics[0]


def test_dynamic_global_family_uses_existing_tool_access_resolver():
    tools = [_Tool("rag_search"), _Tool("clock_now")]
    families = {"clock_now": "clock"}

    scoped = resolve_tool_access(None, tools, mcp_families=families)
    globalized = resolve_tool_access(
        None,
        tools,
        mcp_families=families,
        global_mcp_families={"web_search", "clock"},
    )

    assert scoped.effective_tools == ("rag_search",)
    assert globalized.effective_tools == ("rag_search", "clock_now")
