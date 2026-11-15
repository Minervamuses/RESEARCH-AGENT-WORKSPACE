# Agent application

`app` 是本 workspace 唯一的 Python/Poetry project。它在同一個 distribution 內封裝 framework-neutral `rag` package 與本機 LangGraph chat application，負責 CLI、session orchestration、tools、skills 與 application-specific persistence policy。

## What lives here

| Path | Responsibility |
|---|---|
| `agent/` | LangGraph graph、session、CLI、tool policy 與 extension runtime |
| `rag/` | Ingest、chunking、Chroma/JSON store、retrieval 與 framework-neutral public API |
| `skills/` | Repo 內建 skill bundles；`SKILL.md` 是模型執行指令 |
| `tool/` | Skill/MCP drop-in roots、內部管理資源與尚未載入的 local-tool v1 預留區 |
| `vendor/` | 內附的第三方元件；`web-search-mcp/` 是加上本專案修正的全域 Web Search MCP server（Node）；`bime-word/` 是原樣內附的 bime_word 1.1.5，桌面後端以子行程執行它做系上格式 Word 匯出，不打包進 wheel，也不是 agent 技能 |
| `scripts/` | 不打包的開發與評估腳本；`grill_eval.py` 以 `@grill` 跑評估案例，預設拒絕呼叫付費模型（見 `skills/grill/README.md`） |
| `tests/` | 單一 pytest suite；`tests/rag/` 保留 RAG subsystem tests |
| `env/` | Conda-owned runtime definition |

Built-in skill 的 domain code 與 agent runtime 是不同邊界。例如 `skills/citation/` 是 citation engine，`agent/skills/citation/` 只放 session integration policy。

## Dependency boundary

- `agent` 可以依賴 `rag` 的公開 API。
- `rag` 不可反向 import `agent` 或 app-specific skill code。
- LangGraph、chat CLI、MCP、session/skill policy 都屬於 `agent`。
- 資料擷取、切塊、向量儲存與 retrieval 邏輯屬於 `rag`。
- 這是程式碼 ownership 邊界；兩者共用同一份 manifest、lock、Conda env 與 wheel。

## Developer entry points

- 桌面介面：回到 workspace 根目錄，啟用 Conda `app` 後執行 `python main.py`。操作方式見 [workspace README](../README.md)。
- `agent.ChatSession`：stateful chat facade。
- `agent.build_graph`：單回合 LangGraph workflow builder。
- `python -m agent.cli.chat --no-mcp`：不啟動 MCP 的本機 CLI。
- `python -m rag.cli.ingest -r /path/to/project`：直接管理知識庫。

安裝、環境變數、slash commands 與使用者操作以 [workspace README](../README.md) 為準。

## Documentation map

- [Agent architecture](agent/README.md)
- [Turn lifecycle](agent/turns/README.md)
- [Extended thinking](agent/thinking/README.md)
- [Tool definitions and enforcement](agent/tools/README.md)
- [Citation subsystem](skills/citation/README.md)
- [@grill 使用與評估](skills/grill/README.md)
- [RAG package](rag/README.md) 與 [RAG API](rag/docs/API.md)

舊的 Skills 指南與 extension README 已在 2026-10-15 的整理中移除，內容可能已過時；需要時可用 `git show d497bd9^:app/SKILLS_GUIDE.md`、`git show be9c46e^:app/agent/extensions/README.md` 取回。
