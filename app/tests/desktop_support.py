"""Desktop test helpers shared by several test modules (fake session, factory, service builders)."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.config import AgentConfig
from agent.desktop.protocol import request_event, success_result
from agent.desktop.service import DesktopService
from agent.extensions.manager import ApplyItemResult, ApplyReport, ExtensionStatus
from agent.session import ChatSession
from agent.skills import SkillMetadata
from agent.turns.results import TurnOutcome


class _FakeSession:
    def __init__(self, config: AgentConfig, progress_cb=None) -> None:
        self.config = config
        self.progress_cb = progress_cb
        self.session_id = "123e4567e89b42d3a456426614174000"
        self.thinking_mode = "normal"
        self.loaded_skills = [
            SkillMetadata("research", "Research local material.", Path(__file__))
        ]
        self.mcp_families = {"web": "web_search"}
        self.running_extension_revision = 3
        self.extension_startup_diagnostics = ("MCP loader unavailable: TimeoutError",)
        self.recent_turns: list[object] = []
        self.turn_started = asyncio.Event()
        self.turn_release = asyncio.Event()
        self.block_turn = False
        self.turn_inputs: list[str] = []
        self.skill_turn_inputs: list[tuple[str, str | None]] = []
        self.turn_calls: list[dict[str, object]] = []
        self.turn_options: list[object] = []
        self._turn_number = 0
        self._prompt_persisted_callback = None

    def set_prompt_persisted_callback(self, callback) -> None:
        self._prompt_persisted_callback = callback

    def set_final_text_validator(self, validator) -> None:
        self.final_text_validator = validator

    def clear_skill_installer(self) -> dict:
        return {}

    def skill_runtime_for(self, name: str):
        # Fakes carry no skill runtimes; Citation stays out of their command list.
        raise KeyError(name)

    async def turn_outcome(
        self,
        text: str,
        *,
        display_input: str | None = None,
        turn_id: str | None = None,
        skill_name: str | None = None,
        retry: bool = False,
        options=None,
    ) -> TurnOutcome:
        assert turn_id is not None
        assert uuid.UUID(hex=turn_id).hex == turn_id
        self.turn_options.append(options)
        self.turn_inputs.append(text)
        self.skill_turn_inputs.append((text, skill_name))
        self.turn_calls.append({
            "semanticInput": text,
            "displayInput": display_input,
            "turnId": turn_id,
            "skillName": skill_name,
            "retry": retry,
        })
        if self._prompt_persisted_callback is not None:
            self._prompt_persisted_callback()
        self.turn_started.set()
        if self.block_turn:
            await self.turn_release.wait()
        if self.progress_cb is not None:
            self.progress_cb(
                "tools",
                [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "rag_search",
                                "args": {"query": "private query"},
                                "id": "call-safe-1",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    ToolMessage(
                        content="private tool result",
                        tool_call_id="call-safe-1",
                        name="rag_search",
                        status="success",
                    ),
                ],
            )
        self._turn_number += 1
        return TurnOutcome(
            text=f"完成：{text}",
            validation_errors=[],
            turn_id=turn_id,
            turn_number=self._turn_number,
            state="completed",
            accepted=True,
            persisted=True,
        )

    async def run_display_only_turn(
        self,
        _display_input,
        action,
        render_result,
        *,
        turn_id,
        retry=False,
        failure_retryable=True,
    ):
        del retry, failure_retryable
        if self._prompt_persisted_callback is not None:
            self._prompt_persisted_callback()
        result = await action()
        text = render_result(result)
        self._turn_number += 1
        return result, TurnOutcome(
            text=text,
            turn_id=turn_id,
            turn_number=self._turn_number,
            state="completed",
            accepted=True,
            persisted=True,
        )

    def set_thinking_mode(self, mode: str) -> None:
        self.thinking_mode = mode

    def status_snapshot(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "conversation_root": "/tmp/canonical-conversations",
            "turn_count": 0,
            "recent_turn_count": len(self.recent_turns),
            "graph_recursion_limit": self.config.graph_recursion_limit,
            "last_tool_counts": "none",
            "thinking_mode": self.thinking_mode,
            "mcp_families": "web_search",
        }


class _SessionFactory:
    def __init__(self) -> None:
        self.calls: list[tuple[AgentConfig, bool]] = []
        self.fail_once = False
        self.created: _FakeSession | None = None

    async def __call__(
        self,
        config: AgentConfig,
        *,
        load_mcp: bool,
        progress_cb,
        conversation_repository,
        project_id,
        **_kwargs,
    ):
        del conversation_repository, project_id
        self.calls.append((config, load_mcp))
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        self.created = _FakeSession(config, progress_cb)
        return self.created


class _FakeExtensionManager:
    def __init__(self, tmp_path: Path) -> None:
        binding_hash = "a" * 64
        candidate = SimpleNamespace(
            binding_hash=binding_hash,
            descriptor=SimpleNamespace(id="local-search", family="local_search"),
            resolved_command="/conda/envs/app/bin/python",
            args=("server.py", "--fixture"),
            cwd=str(tmp_path / "dropin" / "mcp" / "local-search"),
            env_names=("LOCAL_SEARCH_MODE",),
            env={"PRIVATE_TOKEN": "must not cross wire"},
        )
        desired_skill = SimpleNamespace(id="writer", kind="skill")
        self.preview_object = SimpleNamespace(
            private_skill_hash="private-manager-hash",
            registry=SimpleNamespace(revision=0),
            diff=SimpleNamespace(
                changes=[
                    SimpleNamespace(
                        operation="add",
                        key="skill:writer",
                        desired=desired_skill,
                    )
                ],
                diagnostics=(),
            ),
            plan=SimpleNamespace(
                items=[
                    SimpleNamespace(
                        key="skill:writer",
                        summary="secret-from-untrusted-extension-metadata",
                    )
                ]
            ),
            mcp_candidates={"mcp:local-search": candidate},
        )
        self.status_object = ExtensionStatus(
            dropin_root=tmp_path / "dropin",
            state_root=tmp_path / "state",
            desired_count=1,
            applied_count=0,
            applied_revision=0,
            running_revision=0,
            restart_required=False,
            manager_available=True,
            manager_error=None,
            diagnostics=(),
        )
        self.applied_preview = None
        self.apply_calls = 0
        self.before_apply = None
        self.status_calls = 0
        self.preview_calls = 0
        self.approved_bindings: set[str] | None = None

    def status(self, **kwargs):
        self.status_calls += 1
        return replace(
            self.status_object,
            running_revision=kwargs.get("running_revision", 0),
            running_mcp_families=tuple(kwargs.get("running_mcp_families", ())),
        )

    def preview(self):
        self.preview_calls += 1
        return self.preview_object

    def apply(self, preview, *, approved_mcp_bindings):
        self.apply_calls += 1
        if self.before_apply is not None:
            self.before_apply()
        self.applied_preview = preview
        self.approved_bindings = set(approved_mcp_bindings)
        return ApplyReport(
            previous_revision=0,
            applied_revision=1,
            restart_required=True,
            items=(
                ApplyItemResult(
                    "skill:writer",
                    "added",
                    "secret-from-untrusted-extension-metadata",
                ),
            ),
            diagnostics=("secret-from-untrusted-extension-metadata",),
        )


def _service(tmp_path: Path, **kwargs) -> DesktopService:
    config = kwargs.pop(
        "config",
        AgentConfig(
            persist_dir=str(tmp_path / "store"),
            extension_dropin_dir=str(tmp_path / "dropin"),
            extension_state_dir=str(tmp_path / "state"),
        ),
    )
    return DesktopService(
        original_cwd=tmp_path,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
        config=config,
        **kwargs,
    )


def _turn_params(
    text: str,
    *,
    turn_id: str | None = None,
    retry: bool = False,
) -> dict[str, object]:
    return {
        "text": text,
        "turnId": turn_id or uuid.uuid4().hex,
        "retry": retry,
    }


async def _dispatch_approved(service, method, params):
    """Existing lifecycle tests grant the new single-operation consent explicitly."""
    tasks = []

    class Sink:
        request_id = str(uuid.uuid4())

        def __call__(self, event, data):
            if event == "approval.required":
                tasks.append(asyncio.create_task(service.dispatch("approval.resolve", {
                    "approvalId": data["approvalId"], "parentRequestId": data["parentRequestId"],
                    "turnId": data["turnId"], "approved": True,
                })))

    try:
        return await service.dispatch(method, params, event_sink=Sink())
    finally:
        await asyncio.gather(*tasks)


async def _open_test_project(service, root: Path, *, history_directory: str | None = None):
    root.mkdir(exist_ok=True)
    params = {"rootPath": str(root), "action": "inspect"}
    if history_directory is not None:
        params["historyDirectory"] = history_directory
    preview = await service.dispatch("workspace.select", params)
    return await service.dispatch("workspace.select", {
        "rootPath": str(root), "action": "initialize",
        "historyDirectory": preview["historyDirectory"],
        "expectedFingerprint": preview["researchFingerprint"],
    })


class _DocumentModel:
    def __init__(self):
        self.calls = []
        self.bound_names = []
        self.replacement = "第二段已修改🙂"
        self.fail_after_save = False
        self.fail_before_answer = False
        self.reference_id = None

    def bind_tools(self, tools):
        self.bound_names.append(tuple(tool.name for tool in tools))
        return self

    async def ainvoke(self, messages):
        return self.invoke(messages)

    def invoke(self, messages):
        self.calls.append(messages)
        if self.fail_before_answer:
            self.fail_before_answer = False
            raise RuntimeError("fixture failed after durable pending")
        if isinstance(messages[-1], ToolMessage):
            result = json.loads(messages[-1].content)
            if self.fail_after_save:
                self.fail_after_save = False
                raise RuntimeError("fixture response interrupted after document save")
            return AIMessage(content=f"Document operation: {result['status']}.")
        prompt = next(message.content for message in reversed(messages) if isinstance(message, HumanMessage))
        if prompt.startswith("分析"):
            return AIMessage(content="分析完成，沒有修改稿件。")
        return AIMessage(content="", tool_calls=[{
            "name": "document_edit", "id": "model-document-call",
            "args": {"replacement_text": self.replacement, **({"reference_id": self.reference_id} if self.reference_id else {})}, "type": "tool_call",
        }])


class _Sink:
    def __init__(self, service, context, *, approve=True, on_approval=None, on_saved=None):
        self.request_id = str(uuid.uuid4())
        self.service = service
        self.context = context
        self.approve = approve
        self.on_approval = on_approval
        self.on_saved = on_saved
        self.events = []
        self.tasks = []
        self.results = []

    def __call__(self, event, data):
        self.events.append((event, data))
        request_event(self.request_id, len(self.events), event, data)
        if event == "document.proposed":
            async def apply():
                result = await self.service.dispatch("document.apply", {
                    "documentContext": self.context, "turnId": data["turnId"],
                    "callId": data["callId"], "parentRequestId": self.request_id,
                }, event_sink=self)
                success_result(str(uuid.uuid4()), "document.apply", result)
                self.results.append(result)
                if result["status"] == "saved" and self.on_saved is not None:
                    self.on_saved(self, result)
            self.tasks.append(asyncio.create_task(apply()))
        elif event == "approval.required":
            if self.on_approval:
                self.on_approval(self)
            self.tasks.append(asyncio.create_task(self.service.dispatch("approval.resolve", {
                "approvalId": data["approvalId"], "parentRequestId": data["parentRequestId"],
                "turnId": data["turnId"], "approved": self.approve,
                "documentContext": self.context,
            })))


async def _setup(tmp_path, monkeypatch):
    model = _DocumentModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _config: model)
    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _config: [])

    async def factory(config, *, load_mcp, **kwargs):
        assert load_mcp is False
        return ChatSession(config, loaded_skills=[], **kwargs)

    service = _service(tmp_path, session_factory=factory)
    preview = await service.dispatch("workspace.select", {"rootPath": str(tmp_path), "action": "inspect"})
    project = await service.dispatch("workspace.select", {
        "rootPath": str(tmp_path), "action": "initialize",
        "historyDirectory": preview["historyDirectory"],
        "expectedFingerprint": preview["researchFingerprint"],
    })
    await service.dispatch("session.create", {"loadMcp": False, "projectId": project["projectId"]})
    path = tmp_path / "稿件.md"
    path.write_text("相同段落🙂\n\n相同段落🙂\n尾段\n", encoding="utf-8")
    context = await service.dispatch("document.open", {"path": str(path)})
    success_result(str(uuid.uuid4()), "document.open", context)
    return service, model, path, context
