"""C6-S4 (R3): measure conversation-list scan cost; measurement only, no cache.

Run from app/: python <this file> <scratch dir>
Builds a project whose history holds N valid v3 conversations of about 1 MiB
each (written with ConversationRepository.create/complete_turn; four document
turns whose frozen documentContext.sourceText carries the size), then times
`workspace.select` (open) and one `session.list` through DesktopService.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import statistics
import sys
import time
import uuid
from pathlib import Path

from agent.config import AgentConfig
from agent.conversations import ConversationRepository
from agent.desktop.project import inspect_project, initialize_project
from agent.desktop.service import DesktopService

TURNS_PER_CONVERSATION = 4
SOURCE_BYTES_PER_TURN = 250_000  # 4 x ~250 KB of frozen context ~= 1 MiB per file
RUNS = 3


def _context(project_id: str, root: str, turn: int) -> dict:
    rules = "Cite every claim."
    source = (f"turn {turn} paragraph. " * (SOURCE_BYTES_PER_TURN // 16))[:SOURCE_BYTES_PER_TURN]
    return {
        "projectId": project_id,
        "rootPath": root,
        "permissionMode": "ask",
        "requestedThinkingMode": "normal",
        "skillReferences": [],
        "projectRules": {"text": rules, "fingerprint": hashlib.sha256(rules.encode()).hexdigest()},
        "documentContext": {
            "rootPath": root,
            "path": f"{root}/chapter.md",
            "editorRevision": turn,
            "sourceText": source,
            "diskFingerprint": hashlib.sha256(source.encode()).hexdigest(),
        },
        "references": [],
    }


def build(base: Path, count: int) -> tuple[Path, Path]:
    root = base / f"project-{count}"
    store = base / f"store-{count}"
    history = base / f"history-{count}"
    root.mkdir(parents=True)
    preview = inspect_project(str(root), store, history_directory=str(history))
    project = initialize_project(
        str(root), store, history_directory=str(history),
        expected_fingerprint=preview["researchFingerprint"],
    )
    repository = ConversationRepository(history)
    posix_root = Path(project["rootPath"]).as_posix()
    for index in range(count):
        conversation_id = uuid.uuid4().hex
        snapshot = None
        for turn in range(1, TURNS_PER_CONVERSATION + 1):
            turn_id = uuid.uuid4().hex
            values = dict(
                turn_id=turn_id, kind="conversational",
                display_input=f"Revise section {turn}", semantic_input=f"Revise section {turn}",
                context_eligible=True, thinking_mode="normal",
                submitted_at=f"2026-11-22T00:{index % 60:02d}:{turn:02d}Z",
                submitted_context=_context(project["projectId"], posix_root, turn),
            )
            if snapshot is None:
                snapshot = repository.create(conversation_id=conversation_id, project_id=project["projectId"], **values)
            else:
                snapshot = repository.append_pending(snapshot, **values)
            snapshot = repository.complete_turn(
                snapshot, turn_id=turn_id, assistant_output="Revised. " * 200,
                finished_at=f"2026-11-22T00:{index % 60:02d}:{turn:02d}Z",
            )
    return root, history


def measure(root: Path, history: Path, store: Path) -> dict:
    scans = {"count": 0}
    original = ConversationRepository.scan

    def counted(self):
        scans["count"] += 1
        return original(self)

    ConversationRepository.scan = counted
    try:
        opens, lists, open_scans, list_scans = [], [], [], []
        for _ in range(RUNS):
            service = DesktopService(
                original_cwd=root, config=AgentConfig(persist_dir=str(store)),
                session_factory=lambda *_a, **_k: None, environ={},
            )
            scans["count"] = 0
            start = time.perf_counter()
            opened = asyncio.run(service.dispatch("workspace.select", {"rootPath": str(root), "action": "open"}))
            opens.append(time.perf_counter() - start)
            open_scans.append(scans["count"])
            assert opened["status"] == "opened"
            scans["count"] = 0
            start = time.perf_counter()
            listed = asyncio.run(service.dispatch(
                "session.list", {"projectId": opened["projectId"], "offset": 0, "limit": 50},
            ))
            lists.append(time.perf_counter() - start)
            list_scans.append(scans["count"])
        sizes = [path.stat().st_size for path in (history / "conversations").glob("*.json")]
        return {
            "conversations": len(sizes),
            "listed": listed["total"],
            "mean_file_bytes": round(statistics.mean(sizes)),
            "total_bytes": sum(sizes),
            "open_seconds": [round(value, 4) for value in opens],
            "open_median": round(statistics.median(opens), 4),
            "open_scans": open_scans,
            "list_seconds": [round(value, 4) for value in lists],
            "list_median": round(statistics.median(lists), 4),
            "list_scans": list_scans,
        }
    finally:
        ConversationRepository.scan = original


def main() -> None:
    base = Path(sys.argv[1])
    results = []
    for count in (10, 50):
        root, history = build(base, count)
        results.append(measure(root, history, base / f"store-{count}"))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
