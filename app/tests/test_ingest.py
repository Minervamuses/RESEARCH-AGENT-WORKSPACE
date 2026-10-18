"""Agent-side RAG ingest boundary tests."""

import asyncio
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import ingest as ingest_module
from agent.config import AgentConfig


def test_init_workspace_uses_app_parent_as_host_root(monkeypatch, tmp_path):
    app_root = tmp_path / "app"
    app_root.mkdir()
    calls: dict[str, object] = {}

    def fake_ingest_repo(
        repo_root: str,
        *,
        config: AgentConfig,
        skip_rel_paths: set[str],
    ) -> tuple[int, int]:
        calls.update(
            repo_root=Path(repo_root),
            config=config,
            skip_rel_paths=skip_rel_paths,
        )
        return 3, 7

    monkeypatch.setattr(ingest_module, "find_app_root", lambda: app_root)
    monkeypatch.setattr(ingest_module, "ingest_repo", fake_ingest_repo)
    config = AgentConfig(persist_dir=str(tmp_path / "store"))

    result = asyncio.run(ingest_module.init_workspace(config))

    assert result == (3, 7, tmp_path, {"app"})
    assert calls == {
        "repo_root": tmp_path,
        "config": config,
        "skip_rel_paths": {"app"},
    }


def test_stopped_ingest_waits_for_started_write_and_does_not_start_next_file(monkeypatch, tmp_path):
    import rag.cli.ingest as rag_ingest
    from langchain_core.documents import Document

    root = tmp_path / "source"
    for name in ("first", "second"):
        folder = root / name
        folder.mkdir(parents=True)
        (folder / "note.md").write_text(name)
    entered = threading.Event()
    release = threading.Event()
    reads = []
    writes = []

    class Chunker:
        def __init__(self, _config):
            pass

        def chunk(self, text, pid):
            reads.append(text)
            return [Document(page_content=text, metadata={"pid": pid})]

    class JsonStore:
        @contextmanager
        def deferred_save(self):
            yield

    class Store:
        def __init__(self, *_stores):
            pass

        def delete_many(self, _pids):
            pass

        def add(self, docs):
            entered.set()
            assert release.wait(2), "test must release the started write"
            writes.extend(doc.page_content for doc in docs)

    monkeypatch.setattr(rag_ingest, "TokenChunker", Chunker)
    monkeypatch.setattr(rag_ingest, "DocumentStore", Store)
    monkeypatch.setattr(rag_ingest, "get_json_store", lambda _config: JsonStore())
    monkeypatch.setattr(rag_ingest, "get_chroma_store", lambda *_args: object())
    monkeypatch.setattr(rag_ingest, "_tag_folders", lambda folders, _config: {
        name: {"tags": ["test"], "summary": ""} for name in folders
    })

    async def run():
        scope = ingest_module.LocalWorkScope()
        with scope.bind():
            task = asyncio.create_task(ingest_module.ingest_folder(
                root, AgentConfig(persist_dir=str(tmp_path / "store")),
            ))
            try:
                async with asyncio.timeout(2):
                    while not entered.is_set():
                        await asyncio.sleep(0.001)
                task.cancel()
                await asyncio.sleep(0)
                assert not task.done()
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert reads == ["first"]
                assert writes == ["first"]
                await asyncio.sleep(0)
                assert writes == ["first"]
            finally:
                release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


@pytest.mark.parametrize("provider", ["ollama", "tagger", "installer"])
def test_sync_provider_scope_awaits_native_async_cancellation_cleanup(monkeypatch, provider):
    from agent.llm.text import invoke_text_messages
    from langchain_core.messages import AIMessage
    from rag.embedder.ollama import OllamaEmbedder
    from rag.llm import openrouter

    async def run():
        entered = asyncio.Event()
        cleaned = asyncio.Event()
        transport_closed = asyncio.Event()

        async def request(*_args, **_kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0)
                cleaned.set()

        if provider == "ollama":
            wrapper = OllamaEmbedder.__new__(OllamaEmbedder)
            wrapper._embeddings = SimpleNamespace(
                embed_query=lambda _query: [[1.0]], aembed_query=request,
            )
            call = lambda: wrapper.embed_query("test")
        elif provider == "tagger":
            class Client:
                def __init__(self, **kwargs):
                    assert kwargs["max_retries"] == 10
                    assert kwargs["timeout"] == "original timeout"
                    self.chat = SimpleNamespace(completions=SimpleNamespace(create=request))

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *_exc):
                    await asyncio.sleep(0)
                    transport_closed.set()

            monkeypatch.setattr(openrouter, "AsyncOpenAI", Client)
            wrapper = openrouter.OpenRouterLLM.__new__(openrouter.OpenRouterLLM)
            wrapper.model = "fixture"
            wrapper.client = SimpleNamespace(
                api_key="fixture", max_retries=10, timeout="original timeout",
                chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="sync result"))],
                ))),
            )
            call = lambda: wrapper.invoke("test")
        else:
            model = SimpleNamespace(
                invoke=lambda _messages: AIMessage(content="sync result"),
                ainvoke=request,
            )
            call = lambda: invoke_text_messages(model, [])

        scope = ingest_module.LocalWorkScope()
        with scope.bind():
            task = asyncio.create_task(ingest_module.run_local_work(call))
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert cleaned.is_set()
            if provider == "tagger":
                assert transport_closed.is_set()
        # The cached wrapper uses the normal sync path after the call scope ends.
        assert call() == ([[1.0]] if provider == "ollama" else "sync result")

    asyncio.run(run())


def test_folder_tagger_propagates_scope_and_cancels_queued_requests(monkeypatch, tmp_path):
    import rag.cli.ingest as rag_ingest
    from rag.types import invoke_provider

    async def run():
        entered = asyncio.Event()
        started = []
        cleaned = []

        class Tagger:
            def __init__(self, _config):
                pass

            def tag(self, name, *_args):
                async def request():
                    started.append(name)
                    entered.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        await asyncio.sleep(0)
                        cleaned.append(name)

                def forbidden_sync():
                    raise AssertionError("nested worker lost its operation scope")

                return invoke_provider(forbidden_sync, request)

        monkeypatch.setattr(rag_ingest, "LLMTagger", Tagger)
        scope = ingest_module.LocalWorkScope()
        with scope.bind():
            task = asyncio.create_task(ingest_module.run_local_work(
                rag_ingest._tag_folders,
                {str(index): [] for index in range(6)},
                AgentConfig(persist_dir=str(tmp_path)),
            ))
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert 1 <= len(started) <= 4
            assert sorted(cleaned) == sorted(started)

    asyncio.run(run())


def test_persistence_helper_finishes_even_when_scope_is_stopping():
    async def run():
        saved = []
        scope = ingest_module.LocalWorkScope()
        with scope.bind():
            scope.request_stop()
            await ingest_module.await_sync_work(saved.append, "persisted")
            with pytest.raises(asyncio.CancelledError):
                await ingest_module.run_local_work(saved.append, "must not start")
        assert saved == ["persisted"]

    asyncio.run(run())
