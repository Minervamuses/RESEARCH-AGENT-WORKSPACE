"""Non-empty offline flow across the production RAG components."""

from rag import dispatch, explore, get_context, list_chunks, search
from rag.cli.ingest import ingest_repo
from rag.collect import collect_folders
from rag.config import KNOWLEDGE_COLLECTION
from rag.store.cache import get_chroma_store, get_json_store
from rag.store.document_store import DocumentStore
from rag.sync import list_diff, prune_orphans


def test_non_empty_ingest_api_dispatch_sync_and_prune_flow(
    offline_rag_config,
    tmp_path,
):
    root = tmp_path / "knowledge"
    dated_docs = root / "docs" / "20260823"
    notes = root / "notes"
    dated_docs.mkdir(parents=True)
    notes.mkdir(parents=True)
    quasar_path = dated_docs / "quasar.md"
    orchid_path = notes / "orchid.txt"
    quasar_path.write_text(
        "quasar telemetry captures stellar radio bursts. "
        "quasar telemetry supports observatory calibration. "
        "analysts compare signal anomalies across repeated observations. "
        "the archive records instruments, timestamps, and review notes.\n",
        encoding="utf-8",
    )
    orchid_path.write_text(
        "orchid botany records petals, roots, and greenhouse humidity.\n",
        encoding="utf-8",
    )

    folders = collect_folders(root)
    assert {
        folder: [path.name for path in files]
        for folder, files in folders.items()
    } == {
        "docs/20260823": ["quasar.md"],
        "notes": ["orchid.txt"],
    }

    config = offline_rag_config(
        tmp_path / "store",
        chunk_size=10,
        chunk_overlap=2,
    )
    files_ingested, chunk_count = ingest_repo(str(root), config=config)
    assert files_ingested == 2
    assert chunk_count >= 4

    chroma_store = get_chroma_store(KNOWLEDGE_COLLECTION, config)
    json_store = get_json_store(config)
    document_store = DocumentStore(chroma_store, json_store)
    assert len(document_store.get()) == chunk_count
    assert len(chroma_store.get()) == chunk_count

    search_hits = search("quasar telemetry", k=3, config=config)
    assert search_hits
    assert search_hits[0].file_path == "docs/20260823/quasar.md"
    assert "quasar" in search_hits[0].text.casefold()

    quasar_chunks = list_chunks(
        folder_prefix="docs",
        category="documentation",
        file_type=".md",
        date_from="2026-08-23",
        date_to="2026-08-23",
        config=config,
    )
    assert len(quasar_chunks) >= 2
    assert {chunk.file_path for chunk in quasar_chunks} == {
        "docs/20260823/quasar.md"
    }
    assert len({chunk.pid for chunk in quasar_chunks}) == 1

    target = quasar_chunks[1]
    context = get_context(target.pid, target.chunk_id, window=1, config=config)
    assert context is not None
    assert context.total_chunks_in_doc == len(quasar_chunks)
    assert any(chunk.is_target for chunk in context.chunks)

    inventory = explore(config=config)
    assert inventory.categories == {"documentation": 2}
    assert inventory.tags == ["documentation", "offline-fixture"]
    assert inventory.date_range == (20260823, 20260823)
    assert {folder.folder for folder in inventory.folders} == {
        "docs/20260823",
        "notes",
    }

    dispatched_search = dispatch(
        "rag_search",
        {"query": "quasar telemetry", "k": 2},
        config=config,
    )
    assert any(hit["file_path"] == "docs/20260823/quasar.md" for hit in dispatched_search)
    dispatched_inventory = dispatch("rag_explore", {}, config=config)
    assert dispatched_inventory["categories"] == {"documentation": 2}
    dispatched_chunks = dispatch(
        "rag_list_chunks",
        {"pid": target.pid},
        config=config,
    )
    assert len(dispatched_chunks) == len(quasar_chunks)
    dispatched_context = dispatch(
        "rag_get_context",
        {"pid": target.pid, "chunk_id": target.chunk_id, "window": 1},
        config=config,
    )
    assert dispatched_context["pid"] == target.pid
    assert any(chunk["is_target"] for chunk in dispatched_context["chunks"])

    orchid_pid = next(
        doc.metadata["pid"]
        for doc in json_store.get()
        if doc.metadata["file_path"] == "notes/orchid.txt"
    )
    orchid_path.unlink()
    expected_diff = {
        "missing_from_store": [],
        "missing_from_disk": ["notes/orchid.txt"],
    }
    assert list_diff(str(root), config) == expected_diff

    # The same diff powers a prune dry run and must not mutate either store.
    json_before = sorted(doc.metadata["pid"] for doc in json_store.get())
    chroma_before = sorted(doc.metadata["pid"] for doc in chroma_store.get())
    assert list_diff(str(root), config) == expected_diff
    assert sorted(doc.metadata["pid"] for doc in json_store.get()) == json_before
    assert sorted(doc.metadata["pid"] for doc in chroma_store.get()) == chroma_before

    assert prune_orphans(str(root), config) == [orchid_pid]
    assert {
        doc.metadata["file_path"] for doc in document_store.get()
    } == {"docs/20260823/quasar.md"}
    assert {
        doc.metadata["file_path"] for doc in chroma_store.get()
    } == {"docs/20260823/quasar.md"}
