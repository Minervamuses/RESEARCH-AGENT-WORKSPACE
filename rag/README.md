# rag

`rag` is a framework-neutral Python library for ingesting text files into a local Chroma/JSON knowledge store and retrieving them through a small public API.

## Install

From this repository root:

```bash
poetry install
```

External dependencies:

- Ollama for embeddings and semantic search.
- The default embedding model is `bge-m3`:

```bash
ollama pull bge-m3
```

- OpenRouter is optional for library reads, but repo ingest folder tagging needs `OPENROUTER_API_KEY`.

## Minimum Example

Ingest one file:

```bash
poetry run python -m rag.cli.ingest README.md
```

Search the store and print hit text:

```bash
poetry run python - <<'PY'
from rag import search

for hit in search("What is this project?", k=3):
    print(hit.text)
    print("---")
PY
```

For repo ingest instead of a single file:

```bash
poetry run python -m rag.cli.ingest -r /path/to/project
```

## API Reference

See [docs/API.md](docs/API.md) for the complete public API contract, dataclass fields, configuration details, error model, and tool-calling interface.

## Agent Notes

`CLAUDE.md` and `AGENTS.md` are git-ignored by design. Keep local agent instructions in those files without treating them as part of the published library contract.
