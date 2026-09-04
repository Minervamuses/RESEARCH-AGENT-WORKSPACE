"""Phase 06 contracts for retiring active conversation-history retrieval."""

from __future__ import annotations

import json
import shlex
import subprocess
import uuid

from agent.config import AgentConfig
from agent.conversations import ConversationRepository
from agent.session import ChatSession
from agent.tools import inventory as tool_inventory
from agent.tools.bash import create_bash_tool
from agent.tools.read_file import create_read_file_tool


def _session(monkeypatch, tmp_path, *, history_factory):
    graph_kwargs: dict[str, object] = {}

    def build_graph(_config, **kwargs):
        graph_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr("agent.session.build_graph", build_graph)
    monkeypatch.setattr(
        "agent.session.get_chat_history_store",
        history_factory,
        raising=False,
    )
    repository = ConversationRepository(tmp_path)
    session = ChatSession(
        AgentConfig(persist_dir=str(tmp_path)),
        loaded_skills=[],
        conversation_repository=repository,
        session_id=uuid.uuid4().hex,
    )
    return session, repository, graph_kwargs


def test_session_creation_has_no_active_history_store_surface(monkeypatch, tmp_path):
    calls: list[tuple[tuple, dict]] = []

    def retired_history_factory(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("normal session creation must not initialize chat history")

    session, _repository, graph_kwargs = _session(
        monkeypatch,
        tmp_path,
        history_factory=retired_history_factory,
    )

    assert calls == []
    assert "history_store" not in graph_kwargs
    assert not hasattr(session, "history_store")
    assert not hasattr(session, "_turn_store")
    assert not hasattr(session, "flush_recent_turns")


def test_inventory_and_prompt_retire_recall_but_keep_document_rag_and_filesystem_tools():
    names = tool_inventory.base_tool_names()
    prompt = tool_inventory.render_base_tool_prompt()

    assert "recall_history" not in names
    assert "recall_history" not in prompt
    assert names[:3] == ["rag_explore", "rag_search", "rag_get_context"]
    assert names[-2:] == ["read_file", "bash"]


def test_session_guidance_and_status_expose_the_canonical_archive_root(
    monkeypatch,
    tmp_path,
):
    session, repository, _graph_kwargs = _session(
        monkeypatch,
        tmp_path,
        history_factory=lambda *_args, **_kwargs: object(),
    )
    expected_root = str(repository.root.resolve())

    status = session.status_snapshot()
    prompt_parts = [str(message.content) for message in session._prompt_history()]
    archive_hints = [part for part in prompt_parts if expected_root in part]

    assert status["conversation_root"] == expected_root
    assert len(archive_hints) == 1
    hint = archive_hints[0]
    assert len(hint.encode("utf-8")) <= 8_192
    assert "approval-gated" in hint
    assert "fixed-string" in hint
    assert "read_file" in hint
    assert "must not fall back to rag_search or embeddings" in hint


def test_exact_archive_grep_then_read_file_and_paraphrase_miss_use_no_rag(
    tmp_path,
):
    exact_prompt = "Exact archive phrase: cobalt heron 7419"
    paraphrase = "the blue bird phrase"
    repository = ConversationRepository(tmp_path)
    conversation_id = uuid.uuid4().hex
    turn_id = uuid.uuid4().hex
    snapshot = repository.create(
        conversation_id=conversation_id,
        project_id=None,
        turn_id=turn_id,
        kind="conversational",
        display_input=exact_prompt,
        semantic_input=exact_prompt,
        context_eligible=True,
        thinking_mode="normal",
        submitted_at="2026-09-04T15:00:00Z",
    )
    repository.complete_turn(
        snapshot,
        turn_id=turn_id,
        assistant_output="Archived answer",
        finished_at="2026-09-04T15:00:01Z",
    )
    conversation_path = repository.path_for(conversation_id).resolve()
    approvals: list[tuple[str, str, int]] = []

    def approve(command: str, description: str, timeout: int) -> bool:
        approvals.append((command, description, timeout))
        return True

    config = AgentConfig(persist_dir=str(tmp_path))
    bash = create_bash_tool(
        config,
        approval_handler=approve,
        command_runner=subprocess.run,
    )
    read_file = create_read_file_tool(config)

    exact_command = (
        f"grep -lF -- {shlex.quote(exact_prompt)} "
        f"{shlex.quote(str(conversation_path))}"
    )
    exact_result = json.loads(bash.invoke({
        "command": exact_command,
        "description": "Find the exact prompt in the canonical conversation archive.",
    }))

    assert exact_result["approved"] is True
    assert exact_result["exit_code"] == 0
    assert exact_result["stdout"].strip() == str(conversation_path)
    file_result = json.loads(read_file.invoke({"path": str(conversation_path)}))
    assert exact_prompt in file_result["content"]

    miss_command = (
        f"grep -lF -- {shlex.quote(paraphrase)} "
        f"{shlex.quote(str(conversation_path))}"
    )
    miss_result = json.loads(bash.invoke({
        "command": miss_command,
        "description": "Check the canonical archive for this exact wording.",
    }))

    assert miss_result["approved"] is True
    assert miss_result["exit_code"] == 1
    assert miss_result["stdout"] == ""
    assert len(approvals) == 2
