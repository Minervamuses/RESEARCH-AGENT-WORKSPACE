# rag

`rag` is a framework-neutral Python library for ingesting text files into a local Chroma/JSON knowledge store and retrieving them through a small public API.

## Install

`rag` ships inside the app distribution and uses the same `app` Conda
environment, Poetry manifest, lock file, and local store as the chat agent.
From the workspace root:

```bash
conda env create -f app/env/env-app.yml
conda activate app
cd app
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
python -m rag.cli.ingest README.md
```

Search the store and print hit text:

```bash
python - <<'PY'
from rag import search

for hit in search("What is this project?", k=3):
    print(hit.text)
    print("---")
PY
```

For repo ingest instead of a single file:

```bash
python -m rag.cli.ingest -r /path/to/project
```

Each canonical repo root gets a deterministic source namespace. Repo-ingest
PIDs combine that namespace with the root-relative path, while `file_path`
stays root-relative for display. Sync, prune, and folder metadata are scoped
to that namespace, so different roots may safely contain the same paths.

Stores created before root namespaces were introduced must be rebuilt before
use. The store is generated output: rag does not migrate or automatically
delete an existing `store/`, `raw.json`, Chroma collection, or
`folder_meta.json`.

## API Reference

See [docs/API.md](docs/API.md) for the complete public API contract, dataclass fields, configuration details, error model, and tool-calling interface.
