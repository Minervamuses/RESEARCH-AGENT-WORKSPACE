"""Regression coverage for independently managed repo ingest roots."""

import json

import rag.cli.ingest as ingest_module
import rag.sync as sync_module
from rag.config import KNOWLEDGE_COLLECTION
from rag.store.cache import get_chroma_store, get_json_store


def test_repo_roots_keep_independent_identity_through_sync_prune_and_reingest(
    offline_rag_config,
    tmp_path,
):
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    root_a.mkdir()
    root_b.mkdir()
    readme_a = root_a / "README.md"
    readme_b = root_b / "README.md"
    readme_a.write_text("alpha root\n", encoding="utf-8")
    readme_b.write_text("beta root\n", encoding="utf-8")

    config = offline_rag_config(tmp_path / "store")
    chroma_store = get_chroma_store(KNOWLEDGE_COLLECTION, config)
    json_store = get_json_store(config)

    assert ingest_module.ingest_repo(str(root_a), config=config) == (1, 1)
    assert ingest_module.ingest_repo(str(root_b), config=config) == (1, 1)

    docs = json_store.get()
    assert len(docs) == 2
    assert {doc.metadata["file_path"] for doc in docs} == {"README.md"}
    namespaces = {doc.metadata["source_namespace"] for doc in docs}
    assert len(namespaces) == 2
    pids_by_text = {
        doc.page_content.strip(): doc.metadata["pid"]
        for doc in docs
    }
    assert len(set(pids_by_text.values())) == 2
    assert {doc.page_content.strip() for doc in chroma_store.get()} == {
        "alpha root",
        "beta root",
    }

    with open(config.folder_meta_path(), encoding="utf-8") as file_obj:
        folder_meta = json.load(file_obj)
    assert len(folder_meta) == 2
    assert {meta["source_namespace"] for meta in folder_meta.values()} == namespaces
    assert {meta["folder"] for meta in folder_meta.values()} == {""}

    readme_a.unlink()
    expected_a_pid = pids_by_text["alpha root"]
    assert sync_module.list_diff(str(root_a), config) == {
        "missing_from_store": [],
        "missing_from_disk": ["README.md"],
    }
    assert sync_module.list_diff(str(root_b), config) == {
        "missing_from_store": [],
        "missing_from_disk": [],
    }

    # list_diff is the non-mutating data source used by `/prune` dry runs.
    before_dry_run = [doc.metadata["pid"] for doc in json_store.get()]
    assert sync_module.list_diff(str(root_a), config)["missing_from_disk"] == [
        "README.md"
    ]
    assert [doc.metadata["pid"] for doc in json_store.get()] == before_dry_run

    assert sync_module.prune_orphans(str(root_a), config) == [expected_a_pid]
    assert {doc.page_content.strip() for doc in json_store.get()} == {"beta root"}
    assert {doc.page_content.strip() for doc in chroma_store.get()} == {"beta root"}
    assert sync_module.list_diff(str(root_b), config) == {
        "missing_from_store": [],
        "missing_from_disk": [],
    }

    readme_a.write_text("alpha root\n", encoding="utf-8")
    assert ingest_module.ingest_repo(str(root_a), config=config) == (1, 1)
    assert {doc.page_content.strip() for doc in json_store.get()} == {
        "alpha root",
        "beta root",
    }
    assert {doc.page_content.strip() for doc in chroma_store.get()} == {
        "alpha root",
        "beta root",
    }
    reingested_a = next(
        doc
        for doc in json_store.get()
        if doc.page_content.strip() == "alpha root"
    )
    assert reingested_a.metadata["pid"] == expected_a_pid
    with open(config.folder_meta_path(), encoding="utf-8") as file_obj:
        reingested_meta = json.load(file_obj)
    assert len(reingested_meta) == 2
    assert {
        meta["source_namespace"] for meta in reingested_meta.values()
    } == namespaces
