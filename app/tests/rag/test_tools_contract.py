"""Contract tests for rag's framework-neutral tool layer."""

import subprocess
import sys

import pytest

from rag import RAGConfig, TOOL_SCHEMAS, dispatch


def test_tool_schemas_have_stable_public_shape():
    assert {tool["name"] for tool in TOOL_SCHEMAS} == {
        "rag_search",
        "rag_explore",
        "rag_list_chunks",
        "rag_get_context",
    }

    for tool in TOOL_SCHEMAS:
        assert set(tool) == {"name", "description", "input_schema"}
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "config" not in schema.get("properties", {})


def test_dispatch_serializes_inventory_dataclass(tmp_path):
    config = RAGConfig(persist_dir=str(tmp_path))

    result = dispatch("rag_explore", {}, config=config)

    assert result == {
        "categories": {},
        "tags": [],
        "date_range": None,
        "folders": [],
    }


def test_dispatch_serializes_empty_chunk_list(tmp_path):
    config = RAGConfig(persist_dir=str(tmp_path))

    result = dispatch("rag_list_chunks", {}, config=config)

    assert result == []


def test_dispatch_rejects_unknown_tool():
    with pytest.raises(ValueError, match="Unknown rag tool"):
        dispatch("missing", {})


def test_dispatch_rejects_config_in_tool_args():
    with pytest.raises(ValueError, match="config must be passed"):
        dispatch("rag_explore", {"config": {}})


def test_public_import_defers_vector_backends():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; "
            "from rag import ChromaStore, RAGConfig, TOOL_SCHEMAS, dispatch; "
            "assert not ({\"chromadb\", \"langchain_chroma\", "
            "\"langchain_ollama\", \"numpy\"} & sys.modules.keys())",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
