# C10-S1 文件（G9）

- **日期**：2026-11-22
- **範圍**：根目錄 `README.md`（不含「單一工作流程（產品限制）」一節）、`app/README.md`、`app/agent/**/README.md`、`app/skills/**/README.md`、`app/rag/README.md` 與 `app/rag/docs/`。不改 `for_agents/`、`AGENTS.md`、`CLAUDE.md`、`note/`。
- **grep 樣式**：`cite/|bundle|reference\.bib|CITATION_OUTPUT_DIR|citation_output_dir|Citation output|storage_failed|verified_not|knowledge\.|retry_registration|project\.list|desktop-projects|catalog|cataloged|transient|bashPermissionMode|set_bash_permission|streamKind|Ollama|browser preview|schemaVersion|fixture|Retry Stop|重試停止`

## 修改前的命中

```
app/agent/README.md:11:| `conversations/` | Canonical JSON transcript authority、catalog-independent validation 與 lifecycle transitions |
app/agent/README.md:12:| `desktop/` | Python desktop protocol/service、catalog coordination、`bibliography.*` adapters (logic in `skills/citation`) 與 isolated fixture seams |
app/agent/README.md:67:- Canonical JSON是唯一支援的transcript source。Desktop選取catalog session時若對應JSON不存在，會回報conversation unavailable，並保留目前已選取的session。
app/agent/README.md:68:- 舊Plan logs與conversation Chroma不會被讀取、匯入、改寫或刪除；catalog與isolated fixture都沒有batch migration入口。
app/skills/grill/README.md:21:案例檔是 JSON：`{"note": "…", "cases": [ … ]}`。示範檔在 `tests/fixtures/grill/cases.example.json`。
app/skills/grill/README.md:46:python scripts/grill_eval.py --cases tests/fixtures/grill/cases.example.json --out /tmp/grill-dry --dry-run
app/rag/README.md:20:- Ollama for embeddings and semantic search.
app/skills/citation/README.md:36:    → item status saved / reused (with bibliography {status, path, key}) or storage_failed (reason = library error code)
app/skills/citation/README.md:55:| Styles and export | `csl_render.py`, `styles/` | Pandoc rendering (preview = export), `.docx`/Markdown export, bundled CSL styles. The desktop's BIME Appendix 17 Word export does not us
app/skills/citation/README.md:69:- A bibliography failure is the item's `storage_failed` status: nothing was saved and the work is not citable. A work already in the bibliography before the batch stays `reused` even when
app/rag/docs/API.md:23:- Ollama must be running for ingest and semantic search.
app/rag/docs/API.md:24:- The Ollama embedding model defaults to `bge-m3`; install it before ingest/search:
app/rag/docs/API.md:84:- `query: str` is embedded with the configured Ollama embedding model and matched against the Chroma `knowledge` collection.
app/rag/docs/API.md:391:- `embed_model`: Ollama embedding model name used for ingest and semantic search.
app/rag/docs/API.md:424:- Ollama errors propagate when embeddings are requested and Ollama is offline, missing `bge-m3`, or otherwise unavailable.
app/README.md:11:| `skills/` | Repo 內建 skill bundles；`SKILL.md` 是模型執行指令 |
README.md:54:程式不會自動讀取 `.env`。模型設定在 [AgentConfig](app/agent/config.py)。知識庫語義檢索另需可連線的 Ollama 與 `bge-m3` 模型，可用 `ollama pull bge-m3` 準備；其餘 RAG 設
README.md:133:- **Agent 存檔**：在專案中用 `/citation` 儲存的文獻（驗證過的 DOI 或 arXiv ID；沒有 DOI 的 NeurIPS 論文則在官方論文集網站 proceedings.neurips.cc 依該年的論文列表與
README.md:148:已接受回合的使用者訊息會保留，中斷狀態顯示為 **interrupted／Turn stopped**。Stop 不會重啟整個後端；停止完成後可直接繼續對話。若停止失敗，畫面保留實�
README.md:170:| 已儲存的文獻 | `cite/`，或 `CITATION_OUTPUT_DIR`、`AgentConfig.citation_output_dir` 指定的位置 | 只有在 Citation 中明確儲存（或在引用面板以 DOI／arXiv ID 加入）的來源 
```

## 修改

| 檔案 | 修改 |
|---|---|
| `README.md`「引用與參考文獻」 | Agent 存檔只併入書目庫、不寫 `cite/` bundle；書目庫寫入失敗時明說沒有存檔、這次不可引用、可重試，本批之前已在書目庫的文獻照常重用；CLI 不寫入任何檔案，只在當次對話可引用（決策紀錄 §4.0、§4.1） |
| `README.md`「記錄了哪些資訊」表「已儲存的文獻」列 | 位置改為「只寫入專案書目庫；CLI 不寫入任何檔案」，移除 `cite/`、`CITATION_OUTPUT_DIR`、`AgentConfig.citation_output_dir`；註明舊版 `cite/` 不再讀寫、可自行刪除 |
| `app/agent/README.md` 模組表 | `conversations/`：去掉 catalog，註明只接受 schema v3；`desktop/`：改述 C7-S8 後的模組結構與 `project.py`，fixture 改在 `tests/support/` |
| `app/agent/README.md` 行為列表 | 對話清單由掃描歷史目錄得到，不再有 catalog；舊版 `desktop-projects.json` 不讀不寫、沒有 migration 入口 |

`git diff README.md` 不含「單一工作流程（產品限制）」一節（該節標題與內容都沒有出現在 diff 中）。

## 修改後的命中（皆為現行行為或刻意的歷史說明）

```
app/rag/README.md:20:- Ollama for embeddings and semantic search.
app/README.md:11:| `skills/` | Repo 內建 skill bundles；`SKILL.md` 是模型執行指令 |
app/skills/citation/README.md:36:    → item status saved / reused (with bibliography {status, path, key}) or storage_failed (reason = library error code)
app/skills/citation/README.md:55:| Styles and export | `csl_render.py`, `styles/` | Pandoc rendering (preview = export), `.docx`/Markdown export, bundled CSL styles. The desktop's BIME Appendix 17 Wor
app/skills/citation/README.md:69:- A bibliography failure is the item's `storage_failed` status: nothing was saved and the work is not citable. A work already in the bibliography before the batch stay
app/rag/docs/API.md:23:- Ollama must be running for ingest and semantic search.
app/rag/docs/API.md:24:- The Ollama embedding model defaults to `bge-m3`; install it before ingest/search:
app/rag/docs/API.md:84:- `query: str` is embedded with the configured Ollama embedding model and matched against the Chroma `knowledge` collection.
app/rag/docs/API.md:391:- `embed_model`: Ollama embedding model name used for ingest and semantic search.
app/rag/docs/API.md:424:- Ollama errors propagate when embeddings are requested and Ollama is offline, missing `bge-m3`, or otherwise unavailable.
README.md:54:程式不會自動讀取 `.env`。模型設定在 [AgentConfig](app/agent/config.py)。知識庫語義檢索另需可連線的 Ollama 與 `bge-m3` 模型，可用 `ollama pull bge-m3` 準
README.md:133:- **Agent 存檔**：在專案中用 `/citation` 儲存的文獻（驗證過的 DOI 或 arXiv ID；沒有 DOI 的 NeurIPS 論文則在官方論文集網站 proceedings.neurips.cc 依該�
README.md:148:已接受回合的使用者訊息會保留，中斷狀態顯示為 **interrupted／Turn stopped**。Stop 不會重啟整個後端；停止完成後可直接繼續對話。若停止失敗
README.md:170:| 已儲存的文獻 | 只寫入專案書目庫（下一列）；CLI 沒有專案，不寫入任何檔案 | 只有在 Citation 中明確儲存（或在引用面板以 DOI／arXiv ID 加�
app/agent/README.md:12:| `desktop/` | Python desktop protocol/server、`DesktopService`（dispatch 與生命週期，handler 依職責分在 `*_ops.py`、`approvals.py`、`transcript.py`、`turn_*.py`
app/agent/README.md:67:- Canonical JSON是唯一支援的transcript source。Desktop的對話清單直接由掃描專案歷史目錄得到（不再有catalog）；選取的對話若沒有對應的JSON
app/agent/README.md:68:- 舊Plan logs、conversation Chroma與舊版的 `desktop-projects.json` 不會被讀取、匯入、改寫或刪除；沒有batch migration入口。
app/skills/grill/README.md:21:案例檔是 JSON：`{"note": "…", "cases": [ … ]}`。示範檔在 `tests/fixtures/grill/cases.example.json`。
app/skills/grill/README.md:46:python scripts/grill_eval.py --cases tests/fixtures/grill/cases.example.json --out /tmp/grill-dry --dry-run
```

| 命中 | 為何保留 |
|---|---|
| `app/rag/README.md:20`、`app/rag/docs/API.md` 的 Ollama、`README.md:54` | RAG 仍以 Ollama 產生嵌入；U7 只移除協定中永遠為 null 的 Ollama 診斷欄位 |
| `app/README.md:11` 的 skill bundles | 指 skill 目錄，不是引用 bundle |
| `app/skills/citation/README.md` 36、69 的 `storage_failed`、55 的 bundled CSL styles | 現行存檔語意（C5-S4 已更新）；「bundled」指內附的 CSL 樣式 |
| `README.md:133`、`README.md:170` | 本步改寫後的句子，說明不再寫 `cite/` |
| `README.md:148` 的 Retry Stop | 「停止失敗時保留錯誤與 Retry Stop，尚未收束時不能再送新回合」與 C7-S7（U14）的行為一致：Retry Stop 重新執行清理，只有回合確實結束後才放行 |
| `app/agent/README.md` 12、67、68 | 本步改寫後的句子 |
| `app/skills/grill/README.md` 的 `tests/fixtures/` | grill 評估案例的測試資料路徑，與桌面 fixture 無關 |

未命中而確認過的：`retry_registration`、`project.list`、`bashPermissionMode`、`set_bash_permission`、`streamKind`、`browser preview`、`schemaVersion`、`knowledge.` 在範圍內的文件中都沒有出現。

## 連結檢查

範圍內 10 個 Markdown 檔的相對連結全部指向存在的檔案（腳本輸出 `broken: []`）。
