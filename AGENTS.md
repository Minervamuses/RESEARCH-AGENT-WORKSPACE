# Repository Guidelines

## Project Scope & Operating Assumptions

This is a student-owned, local-use research project, not a commercial or customer-facing production service. Prioritize correct research workflows, simplicity, reproducibility, short feedback loops, and debuggability. Do not add enterprise hardening, high-availability or multi-tenant design, broad compatibility layers, or generic abstractions unless the user explicitly requests them or a demonstrated problem requires them. Treat records in `issue/` and `note/` as context, not automatic implementation scope.

Linux is the supported runtime. The working tree may be edited from Windows through WSL tooling, but commands and runtime behavior must target Linux. Preserve the repository's LF line-ending policy, and do not add native Windows runtime support unless explicitly requested.

## Project Structure & Module Organization

This workspace contains one Python 3.12-3.13 Poetry project rooted at `app/`. Its single distribution contains the `agent`, `skills`, and `rag` import namespaces. `app/agent/` implements the LangGraph agent, CLI, tools, memory, and extension runtime; built-in skills live in `app/skills/`; the framework-neutral ingestion and retrieval subsystem lives in `app/rag/`; all tests live in `app/tests/`, with RAG-specific tests under `app/tests/rag/`. Use `issue/` and `note/` for project records. Treat `cite/`, `app/plan_logs/`, `app/store/`, `app/dist/`, and caches as generated output.

## Build, Test, and Development Commands

Conda owns the Python/runtime environment and Poetry owns Python package resolution inside that active environment. The workspace uses the single Conda environment `app`. Do not use system Python, direct `pip install`, `python -m venv`, or a project `.venv`; `app/poetry.toml` intentionally disables Poetry-created virtual environments. Activate `app` first, or use `conda run -n app ...` for non-interactive commands.

```bash
conda env create -f app/env/env-app.yml
conda activate app && cd app && poetry install
```

Adding or changing dependencies requires explicit user approval. When approved, update `app/pyproject.toml` and `app/poetry.lock` with Poetry in the `app` Conda environment; change `app/env/env-app.yml` only for Conda-managed runtime requirements.

From the `app/` project directory:

- `poetry run pytest` runs the complete Agent and RAG test suite.
- `poetry run pytest tests/test_state.py -q` runs one focused Agent test module.
- `poetry run pytest tests/rag/test_config.py -q` runs one focused RAG test module.
- `poetry build` creates the single wheel and source distribution in `app/dist/`.
- `python -m agent.cli.chat --no-mcp` starts the local agent CLI without MCP servers.
- `python -m rag.cli.ingest README.md` ingests one file into the local store.

Semantic search requires Ollama and `ollama pull bge-m3`.

## Coding Style & Naming Conventions

Follow existing Python conventions: four-space indentation, type hints on public interfaces, concise docstrings, and explicit control flow. Use `snake_case` for modules, functions, variables, and tests; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants. Keep agent-specific behavior out of `app/rag/`. No formatter or linter is configured, so preserve nearby style. Text files use LF endings per `.gitattributes`.

## Testing Guidelines

Tests use pytest 9 and follow `test_*.py` / `test_*` naming. Add the smallest regression test beside the affected subsystem, reusing `app/tests/fixtures/` where possible. Run focused tests, then the complete `app` suite. No coverage threshold is enforced.

## Commit & Pull Request Guidelines

Recent history favors concise Conventional Commit subjects such as `test(extensions): record sandbox user journey` and `docs(citations): rerun single-request user trial`. Use an imperative `type(scope): summary` form when practical. Pull requests should explain the user-visible change, identify the affected subsystem, link any relevant issue, and list exact verification commands. Include screenshots or terminal excerpts only when output or CLI behavior changed. Keep generated stores, citation bundles, secrets, and `.env` files out of commits.
