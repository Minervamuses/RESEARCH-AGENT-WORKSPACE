"""Phase 06 contracts for retiring active conversation-history retrieval."""

from __future__ import annotations

import json
import shlex
import subprocess
import uuid

import pytest

from conftest import make_astream_graph

from agent.config import AgentConfig
from agent.conversations import (
    ConversationRepository,
    ConversationValidationError,
)
from agent.session import ChatSession
from agent.tools.bash import create_bash_tool
from agent.tools.read_file import create_read_file_tool


def _session(monkeypatch, tmp_path):
    graph_kwargs: dict[str, object] = {}
    graph = make_astream_graph(answer="offline answer")

    def build_graph(_config, **kwargs):
        graph_kwargs.update(kwargs)
        return graph

    monkeypatch.setattr("agent.session.build_graph", build_graph)
    repository = ConversationRepository(tmp_path)
    session = ChatSession(
        AgentConfig(persist_dir=str(tmp_path)),
        loaded_skills=[],
        conversation_repository=repository,
        session_id=uuid.uuid4().hex,
    )
    return session, repository, graph_kwargs


def test_session_guidance_and_status_expose_the_canonical_archive_root(
    monkeypatch,
    tmp_path,
):
    archive_parent = tmp_path / "含 空白 $HOME $(printf root) 'quoted'"
    session, repository, _graph_kwargs = _session(monkeypatch, archive_parent)
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
    assert "json.dumps" in hint
    assert "POSIX-shell-quote" in hint
    assert "exactly one literal argument" in hint
    assert "keep `--` before it" in hint
    assert "Never interpolate either operand unquoted" in hint
    assert (
        "grep -lF -- <shell-quoted-escaped-phrase> "
        "<shell-quoted-root>/*.json | head -n 21"
    ) in hint
    assert "read_file" in hint
    assert "current pending match" in hint
    assert "offset_bytes=0" in hint
    assert "at most 20 matched JSON files" in hint
    assert "must not fall back to rag_search or embeddings" in hint


def test_extended_archive_hint_does_not_claim_bash_is_available(
    monkeypatch,
    tmp_path,
):
    session, _repository, _graph_kwargs = _session(monkeypatch, tmp_path)
    session.set_thinking_mode("extended")

    hint = str(session.base_prompt_history()[1].content)

    assert "do not receive the approval-gated bash tool" in hint
    assert "normal thinking mode" in hint
    assert "Do not use document RAG or embeddings" in hint


def test_conversation_root_display_rejects_control_and_overlong_paths(tmp_path):
    with pytest.raises(ConversationValidationError, match="control characters"):
        ConversationRepository(tmp_path / "line\nbreak").display_root()

    overlong = tmp_path.joinpath(*(["segment"] * 600))
    with pytest.raises(ConversationValidationError, match="rendered safely|display limit"):
        ConversationRepository(overlong).display_root()


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
