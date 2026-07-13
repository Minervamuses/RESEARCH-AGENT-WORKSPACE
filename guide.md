# Research Agent Workspace 使用指南

這份文件說明目前這個專案怎麼使用與維護。它假設你會使用終端機、conda、Poetry，也大致知道什麼是 RAG/LLM，但不假設你熟悉本專案內部架構。

專案分成兩個主要部分：

- `app/`: 聊天 agent、CLI、slash commands、skills（含內建 citation skill）、對話記憶。
- `rag/`: 獨立的 RAG library，負責 ingest、Chroma/JSON store、搜尋與 context window。

一般使用者大多只需要從 `app/` 啟動 chat CLI；需要直接管理知識庫時才會進 `rag/`。

## 1. 前置條件總表

先分清楚哪些是「跑專案必備」、哪些是「用到某功能才需要」。缺少某個前置條件時，對應功能 fail-fast 或停用是預期行為，不代表專案故障。

### 必備：Python/conda/Poetry

| 項目 | 目前專案要求 |
|---|---|
| Python | `>=3.12,<3.14`；env 檔目前 pin `python=3.13` |
| conda env | `app` 與 `rag` 兩個獨立環境 |
| Poetry | env 檔要求 `poetry>=2.3,<3` |
| Poetry venv | 兩邊都設 `virtualenvs.create = false`、`in-project = false`，不建立也不採用 `.venv` |

重點：一定要先 `conda activate app` 或 `conda activate rag`，再跑 `poetry install`。Chat CLI 會檢查 Python runtime 必須等於 `CONDA_PREFIX`，因此 system Python、Poetry `.venv`、巢狀 venv 與錯誤的 Conda env 都會被拒絕。

### 必備：依使用入口

| 使用入口 | 必要前置條件 |
|---|---|
| `python -m agent.cli.chat` | `app` conda env、`poetry install` 完成、`OPENROUTER_API_KEY` |
| `/thinking extended` | chat 前置條件 + `AgentConfig` 內 extended-thinking model slots 有值且 OpenRouter 可用 |
| `/init` 或 `/ingest <folder>` | `OPENROUTER_API_KEY`、Ollama server、`bge-m3` |
| `/ingest <file>` | Ollama server、`bge-m3` |
| `rag.search(...)` / `rag_search` | 已有資料 + Ollama server、`bge-m3` |
| `rag.explore(...)` / `list_chunks(...)` / `get_context(...)` | 已有 store；不需要 OpenRouter，通常也不需要 Ollama |
| `/citation`（citation skill） | `app` env + 網路（Crossref/doi.org）；OpenAlex 需 `OPENALEX_API_KEY`；Web Search 預設可用於 fallback / `more`，OpenRouter query expansion 為選配 |

### API keys 與環境變數

程式不讀取 `.env`。持久設定交給 Conda env，臨時測試才使用 shell `export`。例如：

```bash
conda env config vars set -n app OPENROUTER_API_KEY=...
conda env config vars set -n rag OPENROUTER_API_KEY=...

# 自訂 store 時兩邊必須一致
conda env config vars set -n app KMS_STORE_DIR=/path/to/store
conda env config vars set -n rag KMS_STORE_DIR=/path/to/store
```

設定後重新 activate 對應環境。Chat CLI、RAG CLI 與直接 import 都只讀取啟動程序收到的真實環境變數。

目前程式會用到的環境變數：

| 變數 | 必要性 | 用途 |
|---|---|---|
| `OPENROUTER_API_KEY` | chat agent、extended thinking、repo/folder ingest 必要；citation 選配 | OpenRouter chat model、RAG folder tagging、citation query expansion（lazy） |
| `KMS_STORE_DIR` | 選用 | 改 RAG store 位置；app 與 rag 若要共用資料必須設成同一個值 |
| `AGENT_ENABLE_MCP_WEB_SEARCH` | 選用 | 未設定時預設啟用；只在要持久關閉時設 `0`/`false`/`no`/`off` |
| `AGENT_MCP_WEB_SEARCH_COMMAND` | 選用 | 覆蓋預設的 Conda `node` 啟動命令 |
| `AGENT_MCP_WEB_SEARCH_ARGS` | 選用 | 與自訂 command 搭配的啟動參數 |
| `AGENT_ENABLE_MCP_GITHUB` | 選用 | 設 `1`/`true`/`yes`/`on` 啟用 GitHub MCP |
| `AGENT_MCP_GITHUB_COMMAND` | 啟用 GitHub MCP 時必要 | GitHub MCP server 啟動命令 |
| `AGENT_MCP_GITHUB_ARGS` | 啟用 GitHub MCP 時視 server 而定 | GitHub MCP server 啟動參數 |
| `AGENT_MCP_GITHUB_TOOLSETS` | 選用 | GitHub MCP toolsets；預設 `repos,pull_requests,issues,actions,context` |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | 實際使用 GitHub MCP 時需要 | GitHub MCP 認證 |
| `CROSSREF_MAILTO` | 選用 | citation skill 呼叫 Crossref 時加到 User-Agent（polite pool） |
| `XDG_CACHE_HOME` | 選用 | 改 MCP stderr log/cache base；預設 `~/.cache/agent-mcp/` |

所有入口都遵守同一規則：只讀 Conda／程序環境，不搜尋或載入專案內的 `.env` 檔。

### 外部服務與網路

- Ollama 必須在本機可連線，且有 `bge-m3`。ingest 與 semantic search 都會用它。
- OpenRouter 需要可連外網路與有效 API key。
- Web Search MCP、GitHub MCP、citation Crossref/DOI 查詢都需要網路。
- GitHub MCP 沒 token 可能仍能啟動，但實際 GitHub call 多半會被拒絕。

### 可寫入路徑

確認目前使用者對這些位置有寫入權限：

- `rag/store/` 或 `KMS_STORE_DIR` 指向的位置：RAG Chroma、`raw.json`、`folder_meta.json`、chat history。
- `app/plan_logs/`: plan mode markdown logs。
- workspace 根目錄的 `cite/`（預設，bundle 納入 git），或 `CITATION_OUTPUT_DIR` / `AgentConfig.citation_output_dir` 指向的位置：citation bundle 輸出。只有不在 git workspace 內執行的安裝套件才 fallback 到平台 user-data 目錄。
- `~/.cache/agent-mcp/` 或 `$XDG_CACHE_HOME/agent-mcp/`: MCP stderr logs。

### 工作目錄注意事項

- 啟動 chat CLI：從 `app/` 跑最直覺。
- 直接用 RAG CLI：從 `rag/` 跑最直覺。
- `read_file` 可讀絕對路徑或工作目錄相對路徑；active skill 下的 `references/`、`assets/`、`scripts/` 相對路徑會被限制在 skill root。
- `bash` tool 只在互動 TTY 中可由使用者批准執行；非互動環境會自動拒絕。

## 2. 安裝與環境

本專案刻意使用 Conda 管 Python 環境、Poetry 管 Python 套件，而且 Poetry 同時設定 `virtualenvs.create = false` 與 `in-project = false`。`poetry install` 只會裝進目前啟用的 Conda env，既不建立也不採用 `.venv`。

第一次安裝：

```bash
conda env create -f rag/env/env-rag.yml
conda env create -f app/env/env-app.yml

conda activate rag
cd rag
poetry install

conda activate app
cd ../app
poetry install
```

更新既有環境：

```bash
conda env update -n rag -f rag/env/env-rag.yml --prune
conda env update -n app -f app/env/env-app.yml --prune
```

安裝後建議確認版本：

```bash
conda run -n app python --version
conda run -n app poetry --version
conda run -n app node --version
conda run -n rag python --version
conda run -n rag poetry --version
```

目前本機驗收時看到的是 Python 3.13.14、Poetry 2.4.1、Node 24。

常用外部服務：

- Ollama + `bge-m3`: ingest 與語意搜尋需要。
- `OPENROUTER_API_KEY`: chat agent、extended thinking、repo ingest 的 folder tagging 需要。
- MCP servers:Web Search 預設啟用；GitHub 透過 `app` Conda env vars 選擇性開啟。

建議先安裝 embedding model：

```bash
ollama pull bge-m3
```

## 3. 啟動聊天 Agent

從 `app/` 啟動：

```bash
conda activate app
cd app
python -m agent.cli.chat
```

啟動後會看到 `>>` prompt。一般問題直接輸入文字；以 `/` 開頭的是本地 slash command。

可用參數：

```bash
python -m agent.cli.chat --max-turns 32
python -m agent.cli.chat --no-mcp
```

- `--max-turns`: 每回合 LangGraph 最多跑幾輪工具/模型循環。
- `--no-mcp`: 只對這次執行停用所有 MCP 工具。

離開 CLI：

```text
q
quit
exit
/quit
/exit
```

## 4. 知識庫是什麼

RAG store 預設在：

```text
rag/store/
```

裡面主要有：

- ChromaDB: 語意搜尋用。
- `raw.json`: chunk 的 JSON 備份，`get_context`、`list_chunks`、sync/prune 會讀它。
- `folder_meta.json`: repo ingest 時由 LLM 產生的 folder tags 與 summaries。
- `chat_history/`: 被移出近期 prompt window 的對話記憶。

你可以用環境變數改 store 位置：

```bash
export KMS_STORE_DIR=/path/to/store
```

注意：chat history 也會放在這個 store 底下的 `chat_history/` 子目錄。

## 5. 匯入資料：建議流程

最常用的是在 chat CLI 裡用 slash commands：

```text
/init
/ingest /path/to/file-or-folder
/sync /path/to/folder
/prune /path/to/folder
/prune /path/to/folder --yes
```

### `/init`

`/init` 會把 `app/` 的上一層，也就是目前的 `research-agent-workspace/`，當成 host project 來 ingest，並排除頂層 `app/` 與 `rag/`。

在目前 repo layout 下，它的用途是：把研究材料匯入知識庫，但不要把 agent 自己的程式碼也當研究材料匯入。

```text
/init
```

需要：

- Ollama 正在跑。
- `bge-m3` 已安裝。
- `OPENROUTER_API_KEY` 已設定，因為 repo ingest 會做 folder tagging。

### `/ingest <file-or-folder>`

匯入單一檔案：

```text
/ingest /home/me/project/notes/paper.md
```

匯入整個資料夾：

```text
/ingest /home/me/project/notes
```

單檔 ingest 不做 LLM folder tagging；資料夾/repo ingest 會做 folder tagging。

### `/sync [folder]`

只檢查磁碟與 store 的差異，不會刪任何東西：

```text
/sync /home/me/project/notes
```

輸出會分成：

- `on disk, not in store`: 磁碟上有、store 裡還沒有。
- `in store, not on disk`: store 裡有、磁碟上已不存在。

### `/prune [folder]`

預設是 dry run，只列出會刪的 orphan entries：

```text
/prune /home/me/project/notes
```

真的刪除要加 `--yes`：

```text
/prune /home/me/project/notes --yes
```

`/prune` 只處理 repo/folder ingest 寫入且帶 `file_path` metadata 的項目。用單檔 ingest 加進去的項目不代表某個 tracked tree，所以不會被 sync/prune 當成 orphan 管理。

## 6. 直接使用 RAG CLI

如果你只想操作 RAG library，可以從 `rag/` 直接跑：

```bash
conda activate rag
cd rag

# 匯入目前目錄
python -m rag.cli.ingest

# 匯入指定 repo/folder
python -m rag.cli.ingest -r /path/to/project

# 匯入單檔，pid 預設是檔名 slug
python -m rag.cli.ingest /path/to/file.md

# 單檔自訂 pid
python -m rag.cli.ingest /path/to/file.md --pid my-note

# repo ingest 時額外略過某些目錄名稱
python -m rag.cli.ingest -r /path/to/project --skip node_modules --skip external
```

直接 RAG CLI 與 chat CLI 用的是同一套 store 設定，且都只讀 Conda／程序環境。若你設定了 `KMS_STORE_DIR`，兩個 Conda env 必須使用同一個值，否則會看起來像資料不見了。

repo/folder ingest 需要 `OPENROUTER_API_KEY` 做 folder tagging。直接跑 RAG CLI 時請先在 shell export：

```bash
export OPENROUTER_API_KEY=...
export KMS_STORE_DIR=/path/to/store  # 如果你不用預設 rag/store
```

## 7. 直接查詢 RAG API

如果你想在 Python 裡直接查知識庫，可以從 `rag` 匯入 public API：

```python
from rag import explore, get_context, list_chunks, search
```

常見用法：

```python
from rag import explore, get_context, search

inventory = explore()
print(inventory.categories)

hits = search("retrieval evaluation latency", k=5, file_type=".md")
for hit in hits:
    print(hit.pid, hit.chunk_id, hit.file_path)
    print(hit.text[:300])

window = get_context(hits[0].pid, hits[0].chunk_id, window=2)
```

四個主要函式：

- `explore(...)`: 看有哪些 categories、tags、folder summaries。
- `search(query, ...)`: 語意搜尋，需要 Ollama embedding。
- `get_context(pid, chunk_id, window=...)`: 擴展某個 hit 的前後文。
- `list_chunks(...)`: 從 `raw.json` 列出 chunks，不跑 embedding。

完整參數與 dataclass 欄位請看 `rag/docs/API.md`。

## 8. 哪些檔案會被 ingest

repo/folder ingest 會收集常見文字與程式檔，例如：

- Markdown/text/config/data: `.md`, `.txt`, `.rst`, `.csv`, `.json`, `.yaml`, `.yml`, `.toml`, `.ini`, `.cfg`, `.conf`, `.sql`
- Python/web/code: `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.html`, `.css`, `.vue`, `.svelte`, `.java`, `.c`, `.cpp`, `.h`, `.go`, `.rs`, `.rb`
- shell/legacy: `.sh`, `.bash`, `.zsh`, `.pck`, `.pkb`, `.pks`, `.plsql`
- 特定檔名：`Makefile`, `Dockerfile`, `Procfile`, `.gitignore`, `.env.example`

預設會略過：

```text
.git, .github, __pycache__, node_modules, .venv, venv, env,
.claude, .opencode, .cursor, plan_logs, volumes, dist, build
```

### 不想被 ingest 的檔案

Repo/folder ingest 會檢查 Markdown 檔案前幾行；單檔 ingest 則會檢查該檔案前幾行。如果看到：

```yaml
do_not_index: true
```

就會跳過或拒絕 ingest。Plan mode 產生的 `plan_logs/` 本來也會被跳過。

敏感資料不要放進可 ingest 的資料夾。即使 `.env` 不在文字副檔名清單內，也不要依賴副檔名當唯一保護。

## 9. Slash Commands 完整列表

在 chat CLI 裡可以輸入：

```text
/help
```

目前支援：

| Command | 用途 |
|---|---|
| `/help` | 顯示 slash commands |
| `/status` | 顯示 session id、turn count、mode、active skill、最近工具使用 |
| `/mode [normal|plan]` | 切換一般模式或 plan mode；不帶參數會出互動選單 |
| `/thinking [normal|extended]` | 切換一般回答或 extended thinking |
| `/skill [name|none] [mode]` | 啟用/停用 skill；不帶參數會出互動選單 |
| `/init` | ingest host workspace，排除 `app/` 與 `rag/` |
| `/ingest <file-or-folder>` | upsert 單檔或資料夾到 RAG store |
| `/sync [folder]` | dry run 檢查磁碟與 store 差異 |
| `/prune [folder] [--yes]` | dry run 或實際刪除 orphan store entries |
| `/clear` | 清空終端機畫面 |
| `/quit`, `/exit` | 離開 CLI |

### `/mode normal|plan`

一般模式：

- 回合會保存在近期 prompt window。
- 過舊的 turn 會被寫入 `chat_history` Chroma store，之後可用 `recall_history` 找回。

Plan mode：

- 回合寫進 `app/plan_logs/plan-...md`。
- 不寫入 ChromaDB。
- 不會被 RAG ingest，因為 `plan_logs/` 被排除且檔案 frontmatter 有 `do_not_index: true`。

使用方式：

```text
/mode plan
請幫我拆解這個重構計劃
/mode normal
```

### `/thinking normal|extended`

`normal` 是預設的直接 agent flow。

`extended` 會啟用較重的流程：prompt rewrite、候選回答、review/revise、final validation。適合需要嚴謹推理、寫作、長文本修訂的任務，但會比較慢，也更依賴 OpenRouter key 與設定的模型可用性。

```text
/thinking extended
幫我審查這段論文 introduction 是否論證不足
/thinking normal
```

如果 key 未設定或模型 slug 在 OpenRouter 不可用，切換時會直接報錯。這是預期的 fail-fast 設計；請先完成 API key 與模型設定。

## 10. Agent 可用工具

Agent 在一般模式下可用的本地工具：

- `rag_explore`: 看目前知識庫有哪些 categories、tags、folder summaries。
- `rag_search`: 對已 ingest 的資料做語意搜尋。
- `rag_get_context`: 對某個 search hit 取前後文。
- `recall_history`: 搜尋已持久化的舊對話 turn。
- `read_file`: 讀本機文字檔，單檔上限 1 MB，會阻擋 `.env`、SSH key、secret/token/credential 類檔名。
- `bash`: 執行 shell command。互動環境會要求使用者批准；非互動環境自動拒絕。

MCP 工具：

- Web Search MCP:預設載入，用於即時網路搜尋。
- GitHub MCP: 用於遠端 GitHub repo、PR、issue、Actions 等。

工具選擇原則：

- 問已匯入的研究資料或專案資料：先用 RAG。
- 問早先對話內容：用 `recall_history`。
- 問本地某個具體檔案：用 `read_file`。
- 問即時外部資訊：需要 Web Search MCP。
- 問遠端 GitHub 狀態：需要 GitHub MCP。

## 11. MCP 設定

Web Search MCP 預設啟用，不需要 activation 變數。程式使用 `app` Conda env 內的 `node`，並從 `$XDG_DATA_HOME/mcp-servers/web-search-mcp/dist/index.js` 或 `~/.local/share/mcp-servers/web-search-mcp/dist/index.js` 啟動已 build 的 server。`--no-mcp` 只對單次 CLI 執行停用；持久關閉可執行：

```bash
conda env config vars set -n app AGENT_ENABLE_MCP_WEB_SEARCH=0
```

GitHub MCP 仍需在 Conda env 明確設定：

```bash
conda env config vars set -n app \
  AGENT_ENABLE_MCP_GITHUB=1 \
  AGENT_MCP_GITHUB_COMMAND=/path/to/github-mcp-server \
  AGENT_MCP_GITHUB_ARGS=stdio \
  GITHUB_PERSONAL_ACCESS_TOKEN=... \
  AGENT_MCP_GITHUB_TOOLSETS=repos,pull_requests,issues,actions,context
```

MCP server 如果啟動失敗，agent 仍會啟動，只是少掉那組外部工具。stderr log 會放在：

```text
~/.cache/agent-mcp/
```

## 12. Skills 使用

Skills 是手動啟用的工作模式。Agent 不會自己決定啟用哪個 skill；你要用 `/skill` 明確切換。

查看與選擇：

```text
/skill
```

直接啟用：

```text
/skill academic-paper-writing
```

啟用特定 task mode：

```text
/skill academic-paper-writing revision
/skill academic-paper-writing literature-review
/skill academic-paper-writing drafting
/skill academic-paper-writing submission-support
```

停用：

```text
/skill none
/skill off
/skill deactivate
```

目前 repo 內的 skills：

- `academic-paper-writing`: 學術寫作、文獻回顧、段落/章節修訂、投稿支援。
- `_prompt-master`: extended thinking 內部 helper。一般使用者通常不需要手動啟用。

Skill 啟用後會影響：

- agent 看到的指令。
- 可用工具 policy。
- task mode。
- pinned references 是否自動放進 context。

例如 `academic-paper-writing` 會允許檔案讀取、RAG、history search，選配 web search，並禁止 `bash`。

## 13. Skills 管理

Skills 預設放在：

```text
app/skills/
```

每個 skill 是一個資料夾，至少要有：

```text
app/skills/<skill-name>/SKILL.md
```

基本結構：

```text
app/skills/my-skill/
├── SKILL.md
├── manifest.yaml
└── references/
    └── checklist.md
```

### 新增 skill

1. 建資料夾，名稱用小寫 kebab-case，例如 `literature-screening`。
2. 新增 `SKILL.md`，開頭要有 YAML frontmatter：

```markdown
---
name: literature-screening
description: Use when the user wants to screen papers for a literature review based on inclusion and exclusion criteria.
---

# Literature Screening

Follow the user's inclusion and exclusion criteria...
```

3. 視需要新增 `manifest.yaml`。

最小 manifest 範例：

```yaml
capabilities:
  required:
    - file.read
    - rag.search

resources: []
task_modes:
  - screening

tool_policy:
  disallow:
    - bash
```

4. 重啟 chat CLI，或建立新的 `ChatSession`。目前 CLI 啟動時會掃描 skills；已啟動的 session 不會自動重新掃 skill list。

### 修改 skill

修改 `SKILL.md` 或 `manifest.yaml` 後，建議重啟 CLI。active skill 的 runtime 是啟用當下載入的；重啟最不容易遇到 cache 或舊 runtime 狀態。

### 刪除 skill

刪掉整個資料夾即可：

```bash
rm -rf app/skills/my-skill
```

如果 CLI 已經啟動，先 `/skill none`，再重啟 CLI，避免 session 還拿著舊的 active skill runtime。

### `manifest.yaml` 規則

支援欄位：

- `capabilities.required`: 必要 capability。解析不到可用工具會讓 skill 啟用失敗。
- `capabilities.optional`: 選配 capability。解析不到不阻止啟用。
- `resources`: skill 內的補充檔案，可標記 `pinned: true`。
- `task_modes`: `/skill <name> <mode>` 可用的模式。
- `tool_policy.disallow`: 禁用工具或 MCP family pattern。

目前 capability map：

| Capability | 對應工具 |
|---|---|
| `file.read` | `read_file` |
| `rag.search` | `rag_explore`, `rag_search`, `rag_get_context` |
| `history.search` | `recall_history` |
| `shell.execute` | `bash` |
| `web.search` | Web Search MCP family |
| `github.repo.read` | GitHub MCP family |

`manifest.yaml` 是嚴格 schema；未知欄位、錯誤型別、空的 `capabilities: {}` 都會在啟用 skill 時報錯。

### Skill references

Skill 裡可以放：

```text
references/
assets/
scripts/
```

當 active skill 使用 `read_file` 讀這些相對路徑時，路徑會被限制在 skill root 裡，不會 fallback 到工作目錄。這是為了避免 skill reference 被路徑穿越或同名檔案混淆。

只有非常小且每次都必要的 reference 才建議 `pinned: true`。Pinned content 每回合都會進 context，太大會浪費 token，也可能超過 `skill_max_pinned_reference_chars` 或 `skill_max_total_skill_context_chars`。

## 14. 知識庫刪減與重建

### 刪掉已不存在檔案的 store entries

使用 `/sync` 檢查，再 `/prune --yes`：

```text
/sync /path/to/project
/prune /path/to/project
/prune /path/to/project --yes
```

### 更新已修改的檔案

重新 ingest 同一個檔案或資料夾即可。repo/folder ingest 是 upsert：會先刪同 folder 這輪涉及的 pids，再加入新 chunks。

```text
/ingest /path/to/project
```

或：

```bash
conda activate rag
cd rag
python -m rag.cli.ingest -r /path/to/project
```

### 完全重建知識庫

如果你想重新開始，先停止 chat CLI，再移除或改名 store：

```bash
mv rag/store rag/store.backup
```

然後重新 `/init` 或 `/ingest`。如果有設定 `KMS_STORE_DIR`，請操作那個目錄，不一定是 `rag/store`。

## 15. Citation Skill

citation 是內建 skill。`citation_workflow` 的 stateless `search` 回傳完整 metadata；`save` 接受 1–10 個自足 WorkIntent，fresh resolve 後才保存，不使用 candidate/match ID。

```text
/citation                                # 啟用（不觸發網路），自動切回 normal thinking
/citation 幫我尋找近5年內關於HPC的論文       # 啟用並立即把這句話交給 agent
/citation off                            # 停用（也可用 none / deactivate）
```

重點：

- 啟用取代目前 active skill；停用/切換 skill 會清除 in-memory workflow 與來源 registry（磁碟上的 bundle 保留）。citation active 期間 `/thinking extended` 被拒絕。
- Actions 只有 `search`、`save`、`sources`、`source`、`explain`；普通模式與其他 skill 的偽造呼叫仍會被拒絕。
- 每輪最多一個合法 save mutation；第一次 attempted batch 即消耗機會，後續不得靜默重搜再寫。
- generic「這篇」版本不明一律詢問；`original` 一律先分辨 original work 或 earliest manifestation。
- DOI 經 doi.org CSL/BibTeX 重驗；v2 canonical identity bundle 原子保存，v1 bundle 只驗證重用。
- 搜尋支援 `year_from`/`year_to`，結果順位不具保存語意。
- citation active 時只接受通過集中式 identity/verification shape 檢查的 source marker；renderer 編號並產生 bibliography。

save 回傳 strict batch artifact；finalizer 逐項驗證 receipt 與 live registry，success、partial、ambiguity、all-failure 都 deterministic render。

輸出寫到 citation 輸出目錄（`AgentConfig.citation_output_dir` → `CITATION_OUTPUT_DIR` → workspace `cite/` → 平台 user-data fail-safe）：

```text
<輸出目錄>/<utf8-byte-capped-title>--<doi-hash>/reference.bib
<輸出目錄>/<utf8-byte-capped-title>--<doi-hash>/citation.json
```

source-slot lock + atomic staging/fsync/rename；同 identity 重用且不改 bytes/mtime；schema/identity/hash 不符 fail closed。

模型可用唯讀 `explain` action 取得上述流程與輸出目錄的確定性說明；使用者問「存在哪裡」時應走 `sources`/`source`/`explain`，不以 bash 掃目錄猜測。

## 16. 前置條件與常見狀況

### `ModuleNotFoundError: No module named pytest` 或套件找不到

通常是沒有啟用對的 conda env，或在錯的 env 裡跑 `poetry install`。確認：

```bash
conda activate app
cd app
poetry install
python -m agent.cli.chat
```

RAG library 則用：

```bash
conda activate rag
cd rag
poetry install
```

### OpenRouter API key 未設定

Chat agent、extended thinking、repo ingest 的 folder tagging 都需要 `OPENROUTER_API_KEY`。如果未設定，相關功能會直接報錯；這是預期行為，不代表 CLI 故障。

設定方式：

```bash
export OPENROUTER_API_KEY=...
```

若要持久保存，使用 `conda env config vars set -n app OPENROUTER_API_KEY=...`，再重新 activate `app`。

### Ingest 或 search 失敗，提到 Ollama / embeddings

確認 Ollama 正在跑，且模型已下載：

```bash
ollama pull bge-m3
```

### 啟用 `/thinking extended` 前要先設定模型與 key

Extended thinking 需要 OpenRouter API key，而且 config 裡設定的 reviewer/rewrite/repair/fusion model 都要能在 OpenRouter 使用。模型 slug 不會預先驗證；如果 key 缺失或模型不可用，切換 `/thinking extended` 時會 fail-fast。先完成設定再啟用即可。

### `/sync` 說 store 裡有很多磁碟上不存在的檔案

先確認你 sync 的 root 是否和當初 ingest 的 root 一樣。`file_path` 是以 ingest root 為基準的相對路徑；root 不同會造成誤判。

### Plan mode 的內容找不到

Plan mode 內容寫在 `app/plan_logs/`，不寫入 Chroma，也不會被 `recall_history` 搜到。需要時直接讀該 markdown 檔。

### Web Search 或 GitHub tools 沒出現

Web Search 請先確認標準路徑內有 built `dist/index.js`，且 `conda run -n app node --version` 成功。GitHub 則檢查 `app` Conda env vars、command 與 token。再查看 MCP log：

```text
~/.cache/agent-mcp/
```

## 17. 開發者驗證指令

修改程式後建議跑：

```bash
conda activate app
cd app
poetry run pytest

conda activate rag
cd ../rag
poetry run pytest
```

基本 import smoke：

```bash
conda run -n app python -c "import agent, skills.citation, rag; print('app ok')"
conda run -n rag python -c "import rag; print('rag ok')"
```

Poetry manifest/lock 檢查：

```bash
conda run -n app poetry check --lock
conda run -n rag poetry check --lock
```
