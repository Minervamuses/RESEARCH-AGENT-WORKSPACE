# Research Agent Workspace

Research Agent Workspace packages a portable agent runtime and a local RAG
library that can be placed beside a research project.

```text
research-agent-workspace/
├── app/  # LangGraph agent, CLI, tools, skills, history, citation workflow
└── rag/  # Framework-neutral indexing and retrieval library
```

The default workflow treats the workspace root as the host project boundary.
From `app/`, the `/init` chat command indexes the parent workspace while
excluding `app/` and `rag/`, so the knowledge base is built from the research
project material rather than the agent implementation itself. For explicit
control, use `/ingest <path>`, `/sync <path>`, and `/prune <path>`.

## Setup

Install the RAG package first, then the agent package:

```bash
cd rag
poetry install

cd ../app
poetry install
```

External services are optional for some flows and required for others:

- Ollama with `bge-m3` is needed for ingest and semantic search.
- `OPENROUTER_API_KEY` is needed for the default chat model and LLM-assisted
  folder tagging.
- MCP servers are opt-in through `app/.env`.

## Run

```bash
cd app
python -m agent.cli.chat
```

Inside the chat CLI:

```text
/init
/ingest /path/to/research-project
/skill academic-paper-writing revision
```

## Repository Notes

The Python package names remain `agent` and `rag` to keep imports stable. This
review copy intentionally omits historical logs, local notes, run ledgers, and
project-specific fixtures.
