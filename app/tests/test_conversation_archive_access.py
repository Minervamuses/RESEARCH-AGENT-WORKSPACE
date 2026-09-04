"""Offline graph journeys for exact-text canonical conversation lookup."""

from __future__ import annotations

import asyncio
import json
import shlex
import subprocess
import uuid

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from agent.config import AgentConfig
from agent.conversations import ConversationRepository
from agent.session import ChatSession
from agent.tools.bash import create_bash_tool
from agent.tools.read_file import MAX_BYTES, create_read_file_tool

MAX_ARCHIVE_MATCHES = 20


class _ArchiveLookupModel:
    def __init__(self, command: str, query: str) -> None:
        self.command = command
        self.query = query
        self.bound_tool_names: list[list[str]] = []
        self.requested_tools: list[str] = []
        self.read_documents: list[dict] = []

    def bind_tools(self, tools):
        self.bound_tool_names.append([item.name for item in tools])
        return self

    def invoke(self, messages):
        bash_results = [
            message for message in messages
            if isinstance(message, ToolMessage) and message.name == "bash"
        ]
        read_results = [
            message for message in messages
            if isinstance(message, ToolMessage) and message.name == "read_file"
        ]
        if not bash_results:
            self.requested_tools.append("bash")
            return AIMessage(content="", tool_calls=[{
                "name": "bash",
                "args": {
                    "command": self.command,
                    "description": (
                        "Find this exact wording in the canonical conversation archive."
                    ),
                },
                "id": "archive-grep",
            }])

        grep_payload = json.loads(bash_results[-1].content)
        if grep_payload["exit_code"] == 1:
            return AIMessage(content=(
                "That exact wording was not found in an earlier completed turn."
            ))
        if grep_payload["exit_code"] != 0:
            raise AssertionError("the exact-text archive grep failed unexpectedly")
        if not read_results:
            matched_paths = grep_payload["stdout"].splitlines()
            if len(matched_paths) > MAX_ARCHIVE_MATCHES:
                return AIMessage(content=(
                    "The exact wording matched too many archive files; please "
                    "provide a more specific phrase."
                ))
            self.requested_tools.extend("read_file" for _path in matched_paths)
            return AIMessage(content="", tool_calls=[
                {
                    "name": "read_file",
                    "args": {"path": matched_path},
                    "id": f"archive-read-{index}",
                }
                for index, matched_path in enumerate(matched_paths)
            ])

        completed_answers: list[str] = []
        for result in read_results:
            file_payload = json.loads(result.content)
            document = json.loads(file_payload["content"])
            self.read_documents.append(document)
            for turn in document["turns"]:
                searchable = (
                    turn.get("displayInput"),
                    turn.get("semanticInput"),
                    turn.get("assistantOutput"),
                )
                if (
                    turn["state"] == "completed"
                    and any(
                        isinstance(value, str) and self.query in value
                        for value in searchable
                    )
                ):
                    completed_answers.append(turn["assistantOutput"])
        if completed_answers:
            return AIMessage(content=f"Recovered: {completed_answers[0]}")
        return AIMessage(content=(
            "That exact wording was not found in an earlier completed turn."
        ))


def _canonical_fixture(tmp_path, marker: str) -> ConversationRepository:
    repository = ConversationRepository(tmp_path)
    conversation_id = uuid.uuid4().hex
    turn_id = uuid.uuid4().hex
    snapshot = repository.create(
        conversation_id=conversation_id,
        project_id=None,
        turn_id=turn_id,
        kind="conversational",
        display_input=marker,
        semantic_input=marker,
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
    return repository


@pytest.mark.parametrize(
    (
        "marker",
        "query",
        "archive_copies",
        "metachar_root",
        "expected_tools",
        "expected_text",
        "expected_pending_reads",
    ),
    [
        (
            "orchid-amber-731 research checkpoint",
            "orchid-amber-731 research checkpoint",
            1,
            False,
            ["bash", "read_file", "read_file"],
            "Recovered: Archived answer",
            1,
        ),
        (
            'literal $HOME $(printf query) `printf backtick` \'single\' "double"\\\nnext',
            'literal $HOME $(printf query) `printf backtick` \'single\' "double"\\\nnext',
            1,
            True,
            ["bash", "read_file", "read_file"],
            "Recovered: Archived answer",
            1,
        ),
        (
            "orchid-amber-731 research checkpoint",
            "a paraphrase that is absent",
            1,
            False,
            ["bash", "read_file"],
            "That exact wording was not found in an earlier completed turn.",
            1,
        ),
        (
            "common archive wording",
            "common archive wording",
            20,
            False,
            ["bash"],
            (
                "The exact wording matched too many archive files; please "
                "provide a more specific phrase."
            ),
            0,
        ),
    ],
)
def test_archive_lookup_uses_exact_approved_grep_without_rag_fallback(
    monkeypatch,
    tmp_path,
    marker,
    query,
    archive_copies,
    metachar_root,
    expected_tools,
    expected_text,
    expected_pending_reads,
):
    persist_dir = (
        tmp_path / "archive $HOME $(printf root) 'quoted'"
        if metachar_root
        else tmp_path
    )
    repository = None
    for _index in range(archive_copies):
        repository = _canonical_fixture(persist_dir, marker)
    assert repository is not None
    quoted_root = shlex.quote(str(repository.root.resolve()))
    encoded_query = json.dumps(query, ensure_ascii=False)[1:-1]
    command = (
        f"grep -lF -- {shlex.quote(encoded_query)} {quoted_root}/*.json "
        f"| head -n {MAX_ARCHIVE_MATCHES + 1}"
    )
    model = _ArchiveLookupModel(command, query)
    rag_calls: list[str] = []
    approvals: list[tuple[str, str, int]] = []

    @tool("rag_explore")
    def rag_explore() -> str:
        """Fail-fast document RAG sentinel."""
        rag_calls.append("rag_explore")
        raise AssertionError("conversation lookup must not use document RAG")

    @tool("rag_search")
    def rag_search(search_query: str) -> str:
        """Fail-fast document RAG sentinel."""
        rag_calls.append(f"rag_search:{search_query}")
        raise AssertionError("conversation lookup must not use document RAG")

    @tool("rag_get_context")
    def rag_get_context(pid: str, chunk_id: int) -> str:
        """Fail-fast document RAG sentinel."""
        rag_calls.append(f"rag_get_context:{pid}:{chunk_id}")
        raise AssertionError("conversation lookup must not use document RAG")

    def approve(command_text: str, description: str, timeout: int) -> bool:
        approvals.append((command_text, description, timeout))
        return True

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _config: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _config: [rag_explore, rag_search, rag_get_context],
    )
    config = AgentConfig(
        persist_dir=str(persist_dir),
        graph_recursion_limit=12,
    )
    session = ChatSession(
        config,
        loaded_skills=[],
        conversation_repository=repository,
        session_id=uuid.uuid4().hex,
        bash_approval_handler=approve,
        bash_command_runner=subprocess.run,
    )

    outcome = asyncio.run(session.turn_outcome(
        f"Look up this older exact phrase: {query}",
        turn_id=uuid.uuid4().hex,
    ))

    assert [call["name"] for call in session.last_tool_calls] == expected_tools
    assert model.requested_tools == expected_tools
    assert rag_calls == []
    assert len(approvals) == 1
    assert approvals[0][0] == command
    assert "recall_history" not in model.bound_tool_names[0]
    pending_self_matches = [
        turn
        for document in model.read_documents
        for turn in document["turns"]
        if turn["state"] == "pending" and query in turn["displayInput"]
    ]
    assert len(pending_self_matches) == expected_pending_reads
    assert outcome.text == expected_text


def test_large_canonical_archive_is_read_in_bounded_chunks_after_exact_grep(
    tmp_path,
):
    marker = "cobalt-heron-924 archive marker"
    large_prompt = marker + " " + ("x" * (MAX_BYTES // 2 + 16_384))
    repository = _canonical_fixture(tmp_path, large_prompt)
    conversation_path = next(repository.root.glob("*.json")).resolve()
    approvals: list[str] = []

    def approve(command: str, _description: str, _timeout: int) -> bool:
        approvals.append(command)
        return True

    config = AgentConfig(persist_dir=str(tmp_path))
    bash = create_bash_tool(
        config,
        approval_handler=approve,
        command_runner=subprocess.run,
    )
    read_file = create_read_file_tool(config)
    command = (
        f"grep -lF -- "
        f"{shlex.quote(json.dumps(marker, ensure_ascii=False)[1:-1])} "
        f"{shlex.quote(str(conversation_path))}"
    )

    grep_payload = json.loads(bash.invoke({
        "command": command,
        "description": "Find the exact wording in the canonical archive.",
    }))
    chunks: list[str] = []
    offset = 0
    while True:
        payload = json.loads(read_file.invoke({
            "path": grep_payload["stdout"].strip(),
            "offset_bytes": offset,
        }))
        chunks.append(payload["content"])
        if payload["next_offset"] is None:
            break
        offset = payload["next_offset"]

    document = json.loads("".join(chunks))
    assert approvals == [command]
    assert len(chunks) == 2
    assert document["turns"][0]["state"] == "completed"
    assert marker in document["turns"][0]["semanticInput"]
