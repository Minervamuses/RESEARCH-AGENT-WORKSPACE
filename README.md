# Research Agent Workspace

可放在研究專案旁邊使用的可攜式 agent 執行環境與本地 RAG library。

```text
research-agent-workspace/
├── app/  # LangGraph chat agent、CLI、slash commands、skills(含 citation skill)、對話記憶
└── rag/  # 獨立 RAG library:ingest、Chroma/JSON store、語意搜尋、context window
```

一般使用只需從 `app/` 啟動 chat CLI;要直接管理知識庫時才會用到 `rag/`。預設把 workspace 根目錄視為 host project:`/init` 會 ingest `app/` 的上層目錄並排除 `app/` 與 `rag/`,讓知識庫只收研究材料、不收 agent 自身的程式碼。

## 1. 前置作業

缺少某個前置條件時,對應功能會 fail-fast 或停用——這是預期行為,不代表專案故障。

### 必備工具

| 項目 | 要求 |
|---|---|
| Python | `>=3.12,<3.14`(env 檔 pin `python=3.13`) |
| conda env | `app` 與 `rag` 兩個獨立環境 |
| Poetry | `>=2.3,<3`;兩邊 `poetry.toml` 都設 `virtualenvs.create = false` |

Poetry 不會另建 `.venv`,`poetry install` 直接裝進目前啟用的 conda env——務必先 `conda activate app` / `conda activate rag` 再執行,否則套件會裝錯地方。

rag 的 distribution 名稱是 **`research-agent-rag`**(PyPI 上已有不相干的 `rag==0.1.0`),Python import 仍是 `import rag`;app 在 `[project.dependencies]` 宣告 `research-agent-rag==0.1.0`,本機開發由 `[tool.poetry.dependencies]` 的 editable path(`../rag`)提供,不會進 wheel metadata。

### 外部服務

- **Ollama + `bge-m3`**:ingest 與語意搜尋必要(`ollama pull bge-m3`)。
- **OpenRouter**(`OPENROUTER_API_KEY` + 可連外網路):chat agent、extended thinking、repo/folder ingest 的 folder tagging 必要;citation skill 只在 query expansion 時 lazy 使用,缺 key 仍可運作。
- **MCP servers**(選配):Web Search 與 GitHub,由 `app/.env` 啟用。GitHub MCP 沒 token 可能仍可啟動,但實際呼叫多半會被拒。
- citation skill 的 Crossref/OpenAlex/doi.org 查詢需要網路;OpenAlex 需另設 `OPENALEX_API_KEY`(缺 key 顯示 disabled,不影響其他 provider)。

### 各功能入口需求對照

| 使用入口 | 必要前置條件 |
|---|---|
| `python -m agent.cli.chat` | `app` env、`poetry install` 完成、`OPENROUTER_API_KEY` |
| `/thinking extended` | 同上 + `AgentConfig` 的 extended-thinking model slots 有值且模型在 OpenRouter 可用 |
| `/init`、`/ingest <folder>` | `OPENROUTER_API_KEY` + Ollama + `bge-m3` |
| `/ingest <file>` | Ollama + `bge-m3` |
| `rag.search(...)` / `rag_search` | 已有資料 + Ollama + `bge-m3` |
| `rag.explore` / `list_chunks` / `get_context` | 已有 store;不需 OpenRouter,通常也不需 Ollama |
| `/citation`(citation skill) | `app` env + 網路(Crossref/doi.org);OpenAlex 需 `OPENALEX_API_KEY`;Web Search MCP 與 OpenRouter 皆為選配(fallback / query expansion) |

### 可寫入路徑

確認目前使用者對以下位置有寫入權限:

- `rag/store/`(或 `KMS_STORE_DIR` 指向的位置):Chroma、`raw.json`、`folder_meta.json`、chat history。
- `app/plan_logs/`:plan mode markdown logs。
- 平台 user-data 目錄(Linux 預設 `~/.local/share/research-agent/citation/`,或 `CITATION_OUTPUT_DIR` / `AgentConfig.citation_output_dir` 指向的位置):citation bundle 輸出(`<title>--<doi-hash>/reference.bib` + `citation.json`)。
- `~/.cache/agent-mcp/`(或 `$XDG_CACHE_HOME/agent-mcp/`):MCP stderr logs。

## 2. 安裝

第一次安裝:

```bash
conda env create -f rag/env/env-rag.yml
conda env create -f app/env/env-app.yml

conda activate rag
cd rag
poetry install

conda activate app
cd ../app
poetry install

ollama pull bge-m3
```

更新既有環境:

```bash
conda env update -n rag -f rag/env/env-rag.yml --prune
conda env update -n app -f app/env/env-app.yml --prune
```

確認版本(本機驗收時為 Python 3.13.14、Poetry 2.4.1):

```bash
conda run -n app python --version && conda run -n app poetry --version
conda run -n rag python --version && conda run -n rag poetry --version
```

## 3. 環境變數設定

從範本開始:

```bash
cp app/.env.example app/.env
```

讀取規則:

- `python -m agent.cli.chat` 會自動讀 `app/.env`,且 `override=False`——shell 已有的同名環境變數不會被 `.env` 覆蓋。
- `python -m rag.cli.ingest` 與直接 import `rag` **不會**讀 `app/.env`,只認 shell 環境變數;需要時先在 shell `export OPENROUTER_API_KEY=...`、`export KMS_STORE_DIR=...`。

| 變數 | 必要性 | 用途 |
|---|---|---|
| `OPENROUTER_API_KEY` | chat、extended thinking、repo/folder ingest 必要;citation 選配 | OpenRouter chat model、RAG folder tagging、citation query expansion(lazy) |
| `KMS_STORE_DIR` | 選用 | 改 RAG store 位置;app 與 rag 要共用資料必須設同一值 |
| `AGENT_ENABLE_MCP_WEB_SEARCH` | 選用 | 設 `1`/`true`/`yes`/`on` 啟用 Web Search MCP |
| `AGENT_MCP_WEB_SEARCH_COMMAND` | 啟用該 MCP 時必要 | Web Search MCP 啟動命令(如 `npx` 或本機 server path) |
| `AGENT_MCP_WEB_SEARCH_ARGS` | 視 server 而定 | Web Search MCP 啟動參數 |
| `AGENT_ENABLE_MCP_GITHUB` | 選用 | 設 `1`/`true`/`yes`/`on` 啟用 GitHub MCP |
| `AGENT_MCP_GITHUB_COMMAND` | 啟用該 MCP 時必要 | GitHub MCP server 啟動命令 |
| `AGENT_MCP_GITHUB_ARGS` | 視 server 而定 | GitHub MCP server 啟動參數 |
| `AGENT_MCP_GITHUB_TOOLSETS` | 選用 | GitHub MCP toolsets;預設 `repos,pull_requests,issues,actions,context` |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | 實際使用 GitHub MCP 時需要 | GitHub MCP 認證 |
| `CROSSREF_MAILTO` | 選用 | citation 呼叫 Crossref 時加進 User-Agent(polite pool) |
| `OPENALEX_API_KEY` | 選用 | 啟用 OpenAlex discovery provider;key 只作 query parameter 且 log/trace 會 redact |
| `CITATION_OUTPUT_DIR` | 選用 | 改 citation bundle 輸出位置(優先序:`AgentConfig.citation_output_dir` → 此變數 → 平台 user-data 目錄;要沿用舊位置請明確設定此變數) |
| `CITATION_RANKING_MODE` | 選用 | citation discovery 排序模式:`lexical`(預設,RRF 加 bounded title relevance)或 `rrf`(回退到原始 RRF 排序) |
| `XDG_CACHE_HOME` | 選用 | 改 MCP stderr log/cache 位置(預設 `~/.cache/agent-mcp/`) |

## 4. 啟動聊天 Agent

```bash
conda activate app
cd app
python -m agent.cli.chat
```

啟動後出現 `>>` prompt:一般問題直接輸入文字,`/` 開頭是本地 slash command。

可用參數:

- `--max-turns 32`:每回合 LangGraph 最多跑幾輪工具/模型循環。
- `--no-mcp`:即使 `.env` 有設定,也不載入 MCP 工具。

離開:輸入 `q`、`quit`、`exit`、`/quit` 或 `/exit`。

## 5. 知識庫與資料匯入

RAG store 預設在 `rag/store/`(可用 `export KMS_STORE_DIR=/path/to/store` 改位置),內含:

- **ChromaDB**:語意搜尋用。
- **`raw.json`**:chunk 的 JSON 備份,`get_context`、`list_chunks`、sync/prune 讀它。
- **`folder_meta.json`**:repo ingest 時由 LLM 產生的 folder tags 與 summaries。
- **`chat_history/`**:被移出近期 prompt window 的對話記憶(也放在同一個 store 底下)。

### 在 chat CLI 匯入(建議流程)

| 指令 | 行為 |
|---|---|
| `/init` | 把 `app/` 的上層(目前的 workspace 根目錄)當 host project ingest,排除頂層 `app/` 與 `rag/` |
| `/ingest <file-or-folder>` | upsert 單檔或整個資料夾;單檔不做 LLM folder tagging,資料夾/repo 會做 |
| `/sync [folder]` | 只比對磁碟與 store 差異、不刪東西;輸出分 `on disk, not in store` 與 `in store, not on disk` |
| `/prune [folder]` | dry run,列出會刪的 orphan entries;加 `--yes` 才真的刪除 |

`/prune` 只處理 repo/folder ingest 寫入、帶 `file_path` metadata 的項目;單檔 ingest 加入的項目不代表某個 tracked tree,不會被 sync/prune 當成 orphan 管理。

### 哪些檔案會被 ingest

repo/folder ingest 收集常見文字與程式檔:

- 文件/設定/資料:`.md` `.txt` `.rst` `.csv` `.json` `.yaml` `.yml` `.toml` `.ini` `.cfg` `.conf` `.sql`
- 程式:`.py` `.js` `.ts` `.tsx` `.jsx` `.html` `.css` `.vue` `.svelte` `.java` `.c` `.cpp` `.h` `.go` `.rs` `.rb`
- shell/legacy:`.sh` `.bash` `.zsh` `.pck` `.pkb` `.pks` `.plsql`
- 特定檔名:`Makefile`、`Dockerfile`、`Procfile`、`.gitignore`、`.env.example`

預設略過目錄:`.git`、`.github`、`__pycache__`、`node_modules`、`.venv`、`venv`、`env`、`.claude`、`.opencode`、`.cursor`、`plan_logs`、`volumes`、`dist`、`build`。

不想被 ingest 的檔案:在檔案前幾行加 `do_not_index: true` 即會被跳過或拒絕(repo/folder ingest 檢查 Markdown 檔前幾行;單檔 ingest 檢查該檔前幾行)。plan mode 的 `plan_logs/` 本來就會被跳過。**敏感資料不要放進可 ingest 的資料夾**——即使 `.env` 不在文字副檔名清單內,也不要依賴副檔名當唯一保護。

### 知識庫維護

- **更新已修改的檔案**:重新 `/ingest` 同一路徑即可。repo/folder ingest 是 upsert:先刪同 folder 這輪涉及的 pids,再加入新 chunks。
- **刪掉已不存在檔案的 entries**:先 `/sync` 檢查,再 `/prune <folder> --yes`。
- **完全重建**:先停止 chat CLI,再 `mv rag/store rag/store.backup`(有設 `KMS_STORE_DIR` 就操作那個目錄),然後重新 `/init` 或 `/ingest`。

## 6. Slash Commands

在 chat CLI 輸入 `/help` 查看。完整列表:

| Command | 用途 |
|---|---|
| `/help` | 顯示 slash commands |
| `/status` | 顯示 session id、turn count、mode、active skill、最近工具使用 |
| `/mode [normal\|plan]` | 切換一般模式或 plan mode;不帶參數出互動選單 |
| `/thinking [normal\|extended]` | 切換一般回答或 extended thinking |
| `/skill [name\|none] [mode]` | 啟用/停用 skill;不帶參數出互動選單 |
| `/citation [文字\|off]` | 啟用 citation skill(持續生效);帶文字時同時把該句話交給 agent;`off` 停用 |
| `/init` | ingest host workspace,排除 `app/` 與 `rag/` |
| `/ingest <file-or-folder>` | upsert 單檔或資料夾到 RAG store |
| `/sync [folder]` | dry run 檢查磁碟與 store 差異 |
| `/prune [folder] [--yes]` | dry run 或實際刪除 orphan store entries |
| `/clear` | 清空終端機畫面 |
| `/quit`、`/exit` | 離開 CLI |

### `/mode`

- **normal**:回合保存在近期 prompt window;過舊的 turn 寫入 `chat_history` Chroma store,之後可用 `recall_history` 找回。
- **plan**:回合寫進 `app/plan_logs/plan-...md`,不寫入 ChromaDB,也不會被 RAG ingest(`plan_logs/` 被排除且檔案 frontmatter 有 `do_not_index: true`)。

### `/thinking`

- **normal**(預設):直接的 agent flow。
- **extended**:啟用較重流程——prompt rewrite、候選回答、review/revise、final validation。適合嚴謹推理、寫作、長文本修訂,但較慢,且依賴 OpenRouter key 與 config 中 reviewer/rewrite/repair/fusion 模型的可用性。模型 slug 不會預先驗證;key 缺失或模型不可用時,切換當下會直接報錯(fail-fast 設計),請先完成設定。

## 7. Agent 可用工具

一般模式下的本地工具:

| 工具 | 用途 |
|---|---|
| `rag_explore` | 看知識庫有哪些 categories、tags、folder summaries |
| `rag_search` | 對已 ingest 的資料做語意搜尋 |
| `rag_get_context` | 取某個 search hit 的前後文 |
| `recall_history` | 搜尋已持久化的舊對話 turn |
| `read_file` | 讀本機文字檔;單檔上限 1 MB;阻擋 `.env`、SSH key、secret/token/credential 類檔名 |
| `bash` | 執行 shell command;互動 TTY 中需使用者批准,非互動環境自動拒絕 |

`read_file` 可讀絕對路徑或工作目錄相對路徑;active skill 下 `references/`、`assets/`、`scripts/` 的相對路徑會被限制在 skill root。

MCP 工具(選配):Web Search MCP 做即時網路搜尋;GitHub MCP 存取遠端 repo、PR、issue、Actions。

工具選擇原則:問已匯入的研究/專案資料 → 先用 RAG;問早先對話內容 → `recall_history`;問本地具體檔案 → `read_file`;問即時外部資訊 → Web Search MCP;問遠端 GitHub 狀態 → GitHub MCP。

## 8. MCP 設定

由 `app/.env` 控制,預設不開,CLI 啟動時讀取:

```dotenv
# Web Search MCP
AGENT_ENABLE_MCP_WEB_SEARCH=1
AGENT_MCP_WEB_SEARCH_COMMAND=node
AGENT_MCP_WEB_SEARCH_ARGS=/absolute/path/to/web-search-mcp/dist/index.js

# GitHub MCP
AGENT_ENABLE_MCP_GITHUB=1
AGENT_MCP_GITHUB_COMMAND=/path/to/github-mcp-server
AGENT_MCP_GITHUB_ARGS=
GITHUB_PERSONAL_ACCESS_TOKEN=...
AGENT_MCP_GITHUB_TOOLSETS=repos,pull_requests,issues,actions,context
```

Web Search MCP 使用 [mrkrsl/web-search-mcp](https://github.com/mrkrsl/web-search-mcp) v0.3.2(commit `e694d8d5da11d1509b9bf0976d380035f648d6f9`,已驗證版本;上游沒有可用的 npm pin):在外部 clone 該 commit、`npm install && npm run build` 之後,以 `node /absolute/path/dist/index.js` 啟動(如上例)。

MCP server 啟動失敗時 agent 仍會啟動,只是少那組外部工具;stderr log 在 `~/.cache/agent-mcp/`(啟動前以 0600 建立,每次 run 寫入 timestamp/run-ID header,達 5 MiB 輪替並保留 3 份)。

## 9. Skills

Skill 是手動啟用的工作模式,agent 不會自行決定啟用哪個 skill:

```text
/skill                                    # 互動選單
/skill academic-paper-writing             # 直接啟用
/skill academic-paper-writing revision    # 啟用特定 task mode
/skill none                               # 停用(也可用 off / deactivate)
```

內建 skills:

- `citation`:驗證式引用工作流(見第 11 節);只授權 skill 專屬的 `citation_workflow` 工具,啟用時自動切回 normal thinking。也可用 `/citation` 啟用。
- `academic-paper-writing`:學術寫作、文獻回顧、段落/章節修訂、投稿支援。task modes:`revision`、`literature-review`、`drafting`、`submission-support`。允許檔案讀取、RAG、history search,選配 web search,禁止 `bash`。
- `_prompt-master`:extended thinking 內部 helper,一般使用者通常不需手動啟用。

Skill 啟用後會影響:agent 看到的指令、可用工具 policy、task mode、pinned references 是否自動進 context。

### 新增/修改/刪除 skill

Skills 放在 `app/skills/<skill-name>/`,至少要有 `SKILL.md`:

```text
app/skills/my-skill/
├── SKILL.md          # 必要;開頭要有 YAML frontmatter(name、description)
├── manifest.yaml     # 選用
└── references/       # 選用;另可有 assets/、scripts/
```

`SKILL.md` 開頭範例:

```markdown
---
name: literature-screening
description: Use when the user wants to screen papers for a literature review based on inclusion and exclusion criteria.
---

# Literature Screening

Follow the user's inclusion and exclusion criteria...
```

- **新增**:建小寫 kebab-case 資料夾 → 寫 `SKILL.md` → 視需要加 `manifest.yaml` → 重啟 chat CLI(skills 只在 CLI 啟動時掃描,已啟動的 session 不會重新掃)。
- **修改**:改完 `SKILL.md` / `manifest.yaml` 後重啟 CLI(active skill runtime 是啟用當下載入的,重啟最不易遇到舊狀態)。
- **刪除**:`rm -rf app/skills/my-skill`;若 CLI 執行中,先 `/skill none` 再重啟,避免 session 拿著舊的 runtime。

### `manifest.yaml`

工具模型是兩級的:**全域工具**(local base tools:`rag_explore`、`rag_search`、`rag_get_context`、`recall_history`、`read_file`、`bash`,加上已載入的 Web Search MCP family)在普通模式與所有 skill 下永遠可用;其他工具(如 GitHub MCP family、`citation_workflow`)只有在 active skill 的 manifest `tools` 區段明確要求時才存在。

最小範例(沒有專屬工具的 skill 可完全省略 `tools`):

```yaml
tools:
  required:
    local:
      - citation_workflow
  optional:
    mcp_families:
      - github
resources: []
task_modes:
  - screening
```

- `tools.required`:必要的 skill 工具(`local` 為工具名、`mcp_families` 為 MCP family 名);解析不到時 skill 啟用失敗。
- `tools.optional`:解析不到不阻止啟用。
- `resources`:skill 內補充檔案,可標 `pinned: true`。
- `task_modes`:`/skill <name> <mode>` 可用的模式。
- schema 是嚴格的:未知欄位、錯誤型別、空的 `tools: {}` 都會在啟用時報錯;舊欄位 `capabilities` / `tool_policy` 會被直接拒絕。

`citation_workflow` 是 skill 專屬工具:只有 manifest 明確要求的 skill 綁得到;普通模式與其他 skill 的偽造呼叫會被執行層(PolicyToolNode)拒絕。它保留給內建 citation skill,一般 skill 不應宣告。

Skill 的 `references/`、`assets/`、`scripts/` 用 `read_file` 讀相對路徑時,路徑被限制在 skill root、不 fallback 到工作目錄(防路徑穿越與同名檔混淆)。只有非常小且每次必要的 reference 才建議 `pinned: true`——pinned content 每回合都進 context,過大會浪費 token,也可能超過 `skill_max_pinned_reference_chars` 或 `skill_max_total_skill_context_chars` 上限。

## 10. 直接使用 RAG(不經過 chat CLI)

### CLI

```bash
conda activate rag
cd rag

python -m rag.cli.ingest                                  # 匯入目前目錄
python -m rag.cli.ingest -r /path/to/project              # 匯入指定 repo/folder
python -m rag.cli.ingest /path/to/file.md                 # 匯入單檔,pid 預設檔名 slug
python -m rag.cli.ingest /path/to/file.md --pid my-note   # 單檔自訂 pid
python -m rag.cli.ingest -r /path/to/project --skip node_modules --skip external  # 額外略過目錄
```

RAG CLI 與 chat CLI 用同一套 store 設定,但**不會**自動讀 `app/.env`。先在 shell export,否則會看起來像資料不見了:

```bash
export OPENROUTER_API_KEY=...        # repo/folder ingest 的 folder tagging 需要
export KMS_STORE_DIR=/path/to/store  # 若不用預設 rag/store;app 與 rag 兩邊要設同一值
```

### Python API

```python
from rag import explore, get_context, list_chunks, search

inventory = explore()          # 看 categories、tags、folder summaries
print(inventory.categories)

hits = search("retrieval evaluation latency", k=5, file_type=".md")  # 語意搜尋,需 Ollama embedding
for hit in hits:
    print(hit.pid, hit.chunk_id, hit.file_path)
    print(hit.text[:300])

window = get_context(hits[0].pid, hits[0].chunk_id, window=2)  # 擴展某個 hit 的前後文
chunks = list_chunks()         # 從 raw.json 列 chunks,不跑 embedding
```

完整參數與 dataclass 欄位見 `rag/docs/API.md`。

## 11. Citation Skill

citation 是內建 skill(engine 就住在 `app/skills/citation/`,同一目錄既是 skill bundle 也是 `skills.citation` package)。`/citation` 啟用後持續生效,之後全部用自然語言操作;agent 透過 skill 專屬的 `citation_workflow` 工具驅動「搜尋 → 呈現候選 → 使用者選擇 → 解析 match → 使用者跨 turn 確認 → 驗證+保存」的流程。

```text
/citation                      # 啟用 citation skill(不觸發網路);同時自動切回 normal thinking
/citation 幫我尋找近5年內關於HPC的論文   # 啟用後立即把這句話交給 agent(進 history/trace)
/citation off                  # 停用(也可用 none / deactivate);/skill none 或切換其他 skill 亦會停用
```

模式與隔離:

- 啟用會取代目前 active skill(無 restoration stack);啟用失敗保留原 skill。citation active 期間 `/thinking extended` 會被拒絕。
- 停用/切換 skill 立即清除 in-memory workflow 與 session 來源 registry(已寫入磁碟的 bundle 保留);citation hint、renderer 與工具同時消失。
- `citation_workflow` 是 skill 專屬工具:普通模式與其他 skills 完全綁不到,偽造的 tool call 也會被執行層(PolicyToolNode)拒絕。
- 同 session 同時只能有一個 workflow call(並行呼叫回 busy);`confirm` 必須發生在 `select` 之後的較晚使用者 turn——同 turn confirm 一律拒絕。
- 自然語言確認完全由模型依目前對話與 citation skill 指引判斷；host/tool 不維護確認詞白名單，也不重新分類原始使用者文字。確定性執行層只保留 workflow 狀態限制：`confirm` 必須跨 turn、identifier 必須是仍有效的 `mX`，同 turn confirm 與 stale match 一律拒絕。此設計刻意信任模型的語意判斷，因此模型若誤判使用者意圖，host 不會以第二套文字規則攔截，但成功後的 DOI/BibTeX 驗證、atomic storage 與 receipt 驗證仍照常執行。

工具 actions(由 agent 依使用者的自然語言呼叫):`search`(可帶 `published_within_years` 或 `year_from`/`year_to`,兩者互斥;`published_within_years` 依當日 UTC 計算日期範圍,Crossref/OpenAlex 用原生日期 filter,回傳後再做 fail-closed 年份篩選——年份未知或超出範圍的候選一律剔除,並回傳實際日期窗)、`more`、`refine`(只篩選既有 candidate pool,不呼叫 provider;可帶 keyword/year/venue/work type,只有使用者明確要求 venue 等級時才使用 fail-closed `venue_tiers`)、`list`、`show`、`select`、`confirm`、`status`、`explain`(唯讀;回傳 workflow 驗證/儲存流程的公開契約與 citation 輸出目錄)、`cancel`、`sources`、`source`。

引用政策(單一 finalization chokepoint、兩種明確政策):

- **citation inactive**:禁止一切 citation markers(含 `[[citation-needed]]`)、raw DOI、`[1]` 數字引用、作者年份引用與手寫 References;一般非 DOI 網址連結不受影響;renderer 不執行。
- **citation active**:只接受目前 registry 中 `identity_verified` 的 `[[cite:<source-id>]]` 與 `[[citation-needed]]`;通過 gate 後 renderer 依首次出現順序編號 `[1]`、`[2]`... 並產生固定格式 bibliography。
- 任一 gate 失敗都不保存原草稿；一般回合以安全訊息取代。若同輪 `confirm` 已成功，finalizer 會改以經 live registry 驗證的結構化 artifact 產生 deterministic receipt，明示草稿被攔截但寫入已完成，避免成功副作用被誤述為失敗。

流程與保證:

- **Discovery**:Crossref 與(有 `OPENALEX_API_KEY` 時)OpenAlex 並行查詢,LLM 最多 lazy 產生 2 個 query expansion(LLM 不可用時照常運作);先以固定 `k=60` 做 reciprocal-rank fusion,再以 bounded deterministic title relevance rerank(可用 `CITATION_RANKING_MODE=rrf` 回退),只在 canonical DOI 或同 provider ID 相同時合併。不同 DOI 的 preprint/正式版/reprint 只會非破壞式分組,每個版本保留自己的 `cX` 與選擇權;shortlist 每組顯示一個代表版本。venue catalog 是有版本、有限的 project-curated allowlist,平時只標示,不參與一般排序。web MCP 只在 structured providers 全失敗/零候選時自動 fallback,否則由 agent 依使用者要求以 `more` 引入。
- **驗證**:confirm 會重新以 doi.org 取 CSL JSON structured record,再以同一 canonical DOI 取 BibTeX(pybtex 驗證、恰一 entry、canonical 重序列化);match/structured/BibTeX 三方 DOI 必須相等(BibTeX 缺 DOI 時由已驗證 record 注入並記 `doi_injected_from_verified_lookup`);title/year 等衝突只警告。驗證等級只有 `identity_verified`——證明 DOI 與書目管線一致,不代表來源支持特定主張。
- **保存**:atomic bundle 寫入 citation 輸出目錄(見第 1 節「可寫入路徑」)之 `<utf8-byte-capped-title>--<doi-hash>/`(`reference.bib` + `citation.json` sidecar,schema v1);staging + rename,成功 bundle 不會半套;同 DOI 重複 confirm 驗證後重用;schema/DOI/hash 不符 fail closed 不覆寫。無 DOI 候選可展示但不可保存。
- **Confirm 收據**:成功 confirm 的最終文字固定包含 source ID、以 code literal 呈現的 DOI、bundle 絕對路徑、驗證等級與 cite marker；這段文字會像一般 assistant output 一樣進 recent history/plan log，淘汰後可由 history recall 找回。模型草稿文字不會被解析成收據，artifact 版本或內容與 live registry 不符時亦不採信。
- **範圍**:來源 registry 是 session 內、citation 模式內的狀態;turn record 與 Chroma history 不再夾帶 SourceRef snapshot或額外 receipt metadata(收據只存在於 finalized assistant text;舊資料中的 `sources_json` metadata 會被忽略,不影響一般 history 查詢)。停用 citation 仍會清除 registry,不會從磁碟 bundle 自動 rehydrate。

## 12. 疑難排解

| 狀況 | 處理 |
|---|---|
| `ModuleNotFoundError`(如 pytest)或套件找不到 | 多半是沒啟用對的 conda env,或在錯的 env 跑 `poetry install`;`conda activate app && cd app && poetry install`(rag 同理) |
| 功能報錯提到 OpenRouter key | `OPENROUTER_API_KEY` 未設定;export 或寫進 `app/.env`。直接報錯是預期的 fail-fast |
| ingest/search 失敗提到 Ollama/embeddings | 確認 Ollama 正在跑,且 `ollama pull bge-m3` 已完成 |
| `/thinking extended` 切換即報錯 | 需要 OpenRouter key,且 config 設定的 reviewer/rewrite/repair/fusion 模型都要在 OpenRouter 可用;先完成設定再啟用 |
| `/sync` 顯示大量磁碟上不存在的檔案 | 確認 sync 的 root 與當初 ingest 的 root 相同;`file_path` 是以 ingest root 為基準的相對路徑,root 不同會誤判 |
| 找不到 plan mode 的內容 | plan mode 只寫 `app/plan_logs/`,不進 Chroma、`recall_history` 搜不到;直接讀該 markdown 檔 |
| Web search / GitHub 工具沒出現 | 確認 `.env` 已啟用對應 MCP 且 command 可執行;可先用 `--no-mcp` 排除本地啟動問題,再查 `~/.cache/agent-mcp/` log |

## 13. 開發者驗證

```bash
# 測試
conda activate app && cd app && poetry run pytest
conda activate rag && cd ../rag && poetry run pytest

# import smoke
conda run -n app python -c "import agent, skills.citation, rag; print('app ok')"
conda run -n rag python -c "import rag; print('rag ok')"

# Poetry manifest/lock 檢查
conda run -n app poetry check --lock
conda run -n rag poetry check --lock
```

## Repository Notes

Python package 名稱維持 `agent` 與 `rag` 以保持 import 穩定。本 review copy 刻意省略歷史 log、本地筆記、run ledgers 與專案特定 fixtures。
