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

## Local Store Lifecycle

The default `app/store/` is generated local state. The `store/` rule in
`app/.gitignore` excludes the whole directory, so a normal fresh clone has no
Chroma database, `raw.json`, `folder_meta.json`, canonical conversations, or
legacy `chat_history/`. The RAG package never creates or reads conversation
history; the legacy directory is preserved only for the agent migration reader.
Branches and commits do not carry different copies of this state. A new user can run
`/init`, `/ingest`, or the ingest CLI directly; there is no old database to
migrate or rebuild first.

Compatibility matters only when a machine or working copy has run an older
version and keeps its gitignored `app/store/` while the code is updated, or
when `KMS_STORE_DIR` points to a persistent store created earlier. If an
on-disk schema is incompatible, this local project does not migrate it in
place: stop the application, back up or move that generated store, then run
`/init` or `/ingest` again. A full rebuild is a local maintenance/recovery
operation, not a fresh-install step.

## API Reference

See [docs/API.md](docs/API.md) for the retrieval API contract, dataclass fields, configuration details, error model, and tool-calling interface.
