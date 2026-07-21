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
| Poetry | `>=2.3,<3`;兩邊 `poetry.toml` 都設 `virtualenvs.create = false`、`in-project = false` |

Poetry 不會建立或採用 `.venv`,`poetry install` 直接裝進目前啟用的 conda env。務必先 `conda activate app` / `conda activate rag` 再執行；chat CLI 也會驗證 Python runtime 與 `CONDA_PREFIX` 相同,不符合就直接拒絕啟動。

rag 的 distribution 名稱是 **`research-agent-rag`**(PyPI 上已有不相干的 `rag==0.1.0`),Python import 仍是 `import rag`;app 在 `[project.dependencies]` 宣告 `research-agent-rag==0.1.0`,本機開發由 `[tool.poetry.dependencies]` 的 editable path(`../rag`)提供,不會進 wheel metadata。

### 外部服務

- **Ollama + `bge-m3`**:ingest 與語意搜尋必要(`ollama pull bge-m3`)。
- **OpenRouter**(`OPENROUTER_API_KEY` + 可連外網路):chat agent、extended thinking、repo/folder ingest 的 folder tagging 必要。
- **MCP servers**:Web Search 預設啟用,從標準 user-data 路徑載入；GitHub 仍是選配。GitHub MCP 沒 token 可能仍可啟動,但實際呼叫多半會被拒。
- citation skill 的 Crossref/DataCite/OpenAlex/doi.org 查詢需要網路;保存帶 arXiv ID 的 trusted non-DOI 記錄時另會呼叫 export.arxiv.org。OpenAlex 需另設 `OPENALEX_API_KEY`(缺 key 顯示 disabled,不影響其他 provider)。

### 各功能入口需求對照

| 使用入口 | 必要前置條件 |
|---|---|
| `python -m agent.cli.chat` | `app` env、`poetry install` 完成、`OPENROUTER_API_KEY` |
| `/thinking extended` | 同上 + `AgentConfig` 的 extended-thinking model slots 有值且模型在 OpenRouter 可用 |
| `/init`、`/ingest <folder>` | `OPENROUTER_API_KEY` + Ollama + `bge-m3` |
| `/ingest <file>` | Ollama + `bge-m3` |
| `rag.search(...)` / `rag_search` | 已有資料 + Ollama + `bge-m3` |
| `rag.explore` / `list_chunks` / `get_context` | 已有 store;不需 OpenRouter,通常也不需 Ollama |
| `/citation`(citation skill) | `app` env + 網路(Crossref/DataCite/doi.org);OpenAlex 需 `OPENALEX_API_KEY`;Web Search 可讀內容，但不參與 verified citation identity 選擇 |

### 可寫入路徑

確認目前使用者對以下位置有寫入權限:

- `rag/store/`(或 `KMS_STORE_DIR` 指向的位置):Chroma、`raw.json`、`folder_meta.json`、chat history。
- `app/plan_logs/`:plan mode markdown logs。
- workspace 根目錄的 `cite/`(預設;bundle 納入 git),或 `CITATION_OUTPUT_DIR` / `AgentConfig.citation_output_dir` 指向的位置:citation bundle 輸出(`<title>--<identity-hash>/reference.bib` + `citation.json`;DOI 記錄的 hash 取自 canonical DOI,trusted non-DOI 記錄取自 canonical identity)。只有 wheel 安裝且 cwd/package 都不在 git workspace 時才 fallback 到平台 user-data 目錄。
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

確認版本(本機驗收時為 Python 3.13.14、Poetry 2.4.1、Node 24):

```bash
conda run -n app python --version && conda run -n app poetry --version && conda run -n app node --version
conda run -n rag python --version && conda run -n rag poetry --version
```

## 3. Conda 環境變數設定

程式不讀取 `.env`。長期設定由 Conda env 管理；臨時測試才使用目前 shell 的 `export`。例如:

```bash
conda env config vars set -n app OPENROUTER_API_KEY=...
conda env config vars set -n rag OPENROUTER_API_KEY=...

# 自訂共用 store 時,兩個 env 必須設成相同路徑
conda env config vars set -n app KMS_STORE_DIR=/path/to/store
conda env config vars set -n rag KMS_STORE_DIR=/path/to/store
```

設定後重新 `conda activate` 才會更新目前 shell。CLI、RAG 與直接 import 都只讀取啟動程序收到的真實環境變數。

| 變數 | 必要性 | 用途 |
|---|---|---|
| `OPENROUTER_API_KEY` | chat、extended thinking、repo/folder ingest 必要 | OpenRouter chat model、RAG folder tagging |
| `KMS_STORE_DIR` | 選用 | 改 RAG store 位置;app 與 rag 要共用資料必須設同一值 |
| `AGENT_ENABLE_MCP_WEB_SEARCH` | 選用 | 未設定時預設啟用；只在要持久關閉時設 `0`/`false`/`no`/`off` |
| `AGENT_MCP_WEB_SEARCH_COMMAND` | 選用 | 覆蓋預設的 Conda `node` 啟動命令 |
| `AGENT_MCP_WEB_SEARCH_ARGS` | 選用 | 與自訂 command 搭配的啟動參數 |
| `AGENT_ENABLE_MCP_GITHUB` | 選用 | 設 `1`/`true`/`yes`/`on` 啟用 GitHub MCP |
| `AGENT_MCP_GITHUB_COMMAND` | 啟用該 MCP 時必要 | GitHub MCP server 啟動命令 |
| `AGENT_MCP_GITHUB_ARGS` | 視 server 而定 | GitHub MCP server 啟動參數 |
| `AGENT_MCP_GITHUB_TOOLSETS` | 選用 | GitHub MCP toolsets;預設 `repos,pull_requests,issues,actions,context` |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | 實際使用 GitHub MCP 時需要 | GitHub MCP 認證 |
| `CROSSREF_MAILTO` | 選用 | citation 呼叫 Crossref 時加進 User-Agent(polite pool) |
| `DATACITE_MAILTO` | 選用 | citation 呼叫 DataCite 時加進 User-Agent，提高可用配額並保留聯絡方式 |
| `OPENALEX_API_KEY` | 選用 | 啟用 OpenAlex discovery provider;key 只作 query parameter 且 log/trace 會 redact |
| `CITATION_OUTPUT_DIR` | 選用 | 改 citation bundle 輸出位置(優先序:`AgentConfig.citation_output_dir` → 此變數 → workspace `cite/` → 平台 user-data fail-safe;要沿用舊位置請明確設定此變數) |
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
- `--no-mcp`:只對這次執行停用所有 MCP 工具。

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

MCP 工具:Web Search MCP 預設載入,用於即時網路搜尋；GitHub MCP 是選配,用於遠端 repo、PR、issue、Actions。

工具選擇原則:問已匯入的研究/專案資料 → 先用 RAG;問早先對話內容 → `recall_history`;問本地具體檔案 → `read_file`;問即時外部資訊 → Web Search MCP;問遠端 GitHub 狀態 → GitHub MCP。

## 8. MCP 設定

Web Search MCP 預設啟用,不需要 activation 變數。程式使用 Conda env 內的 `node`,並依序從 `$XDG_DATA_HOME` 或 `~/.local/share` 找:

```text
mcp-servers/web-search-mcp/dist/index.js
```

Web Search MCP 使用 [mrkrsl/web-search-mcp](https://github.com/mrkrsl/web-search-mcp) v0.3.2(commit `e694d8d5da11d1509b9bf0976d380035f648d6f9`,已驗證版本;上游沒有可用的 npm pin)。把該版本 clone 到上述標準路徑後,在 `app` Conda env 內執行 `npm install && npm run build`。若要暫時關閉,啟動 CLI 時加 `--no-mcp`;持久關閉則用 `conda env config vars set -n app AGENT_ENABLE_MCP_WEB_SEARCH=0`。

GitHub MCP 仍透過 Conda env vars 明確啟用:

```bash
conda env config vars set -n app \
  AGENT_ENABLE_MCP_GITHUB=1 \
  AGENT_MCP_GITHUB_COMMAND=/path/to/github-mcp-server \
  AGENT_MCP_GITHUB_ARGS=stdio \
  GITHUB_PERSONAL_ACCESS_TOKEN=... \
  AGENT_MCP_GITHUB_TOOLSETS=repos,pull_requests,issues,actions,context
```

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

RAG CLI 與 chat CLI 用同一套 store 設定,且都只讀取 Conda／程序環境。若不用 Conda 持久設定,臨時 shell 也必須 export 相同值,否則會看起來像資料不見了:

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

citation 是內建 skill(engine 位於 `app/skills/citation/`)。`/citation` 啟用後，`citation_workflow` 以 stateless 搜尋呈現完整 metadata；保存則接受自足的 WorkIntent，重新跨 provider 解析、阻擋作品／版本矛盾，再原子保存。

```text
/citation                      # 啟用 citation skill(不觸發網路);同時自動切回 normal thinking
/citation 幫我尋找近5年內關於HPC的論文   # 啟用後立即把這句話交給 agent(進 history/trace)
/citation off                  # 停用(也可用 none / deactivate);/skill none 或切換其他 skill 亦會停用
```

模式與隔離:

- 啟用會取代目前 active skill(無 restoration stack);啟用失敗保留原 skill。citation active 期間 `/thinking extended` 會被拒絕。
- 停用/切換 skill 立即清除 in-memory workflow 與 session 來源 registry(已寫入磁碟的 bundle 保留);citation hint、renderer 與工具同時消失。
- `citation_workflow` 是 skill 專屬工具:普通模式與其他 skills 完全綁不到,偽造的 tool call 也會被執行層(PolicyToolNode)拒絕。
- 每個 user turn 最多一個合法 `save(works=[...])` mutation batch；一次可帶 1–10 個 WorkIntent。第一次 attempted outcome 不論成功、資訊不足、歧義或 provider/storage failure 都會消耗本輪寫入機會。
- 搜尋結果沒有 cX/mX 或可回傳的順位 ID。下一輪保存時，模型必須由可見的完整 title/authors/year/venue/type/version metadata 建立 WorkIntent。
- generic「這篇」版本不明時一律詢問，不預設 published/VoR；`original` 一律要求分辨 original work 與 earliest manifestation。
- Actions 僅有 `search`、`save`、`sources`、`source`、`explain`。否定、條件、疑問或不明確語氣不得 save。

`search` 是探索式搜尋，可帶 `year_from`/`year_to`；年份限制會先送入 Crossref、DataCite 與可用的 OpenAlex，再做本地防禦性過濾。`save` 才進入特定作品的 identity resolution：WorkIntent 的 title/authors/year/venue/type 分欄傳入，各 provider adapter 自行產生適合的 query plan，而不是共用一串關鍵字。明確 DOI 直接走 doi.org exact lookup；明確 arXiv ID 直接走 export.arxiv.org，兩者都不先做模糊搜尋。

Crossref 先以 title/author 與寬鬆年份範圍查詢，必要時才退回 bibliographic citation lookup；DataCite 使用 title/creator/publicationYear 欄位查詢並逐步放寬年份；OpenAlex 使用 exact phrase、author/date filters，再條件式放寬，且保留同一 Work 的多個 DOI locations。provider 第一名、score、OpenAlex top-level DOI/primary location 都只是候選證據；resolver 仍須做多欄位與版本判定，再由 doi.org CSL/BibTeX 重新驗證。無 DOI 的作品若命中 trusted authority 仍可保存。`source` 只接受 stable `source_id`。

引用政策(單一 finalization chokepoint、兩種明確政策):

- **citation inactive**:禁止一切 citation markers(含 `[[citation-needed]]`)、raw DOI、`[1]` 數字引用、作者年份引用與手寫 References;一般非 DOI 網址連結不受影響;renderer 不執行。
- **citation active**:只接受 registry 中通過 `is_citable_source` 的 `[[cite:<source-id>]]` 與 `[[citation-needed]]`;renderer 負責編號與 bibliography。
- save artifact 優先於模型文字；成功收據必須符合 live registry 的 canonical identity/path/verification level，全失敗也 deterministic render。

流程與保證:

- **Discovery/Resolution**:search stateless；save 走 exact identifier 或 provider-specific strict→conditional fallback query，hard constraint 先 veto、score 只作 provider 內召回證據。
- **驗證**:DOI winner 必須由 doi.org refetch，BibTeX 經 pybtex canonical round-trip，identity-critical 衝突一律零寫入。trusted non-DOI 記錄由 authority adapter 提供 metadata，以 `authority_metadata_verified` 等級保存(BibTeX 同樣走 canonical round-trip)。
- **保存**:schema v2 canonical identity bundle 使用 source-slot 跨程序鎖、staging+fsync+rename；v1 DOI bundle只驗證／重用，不背景重寫。
- **Batch artifact**:逐項保存 success/ambiguity/not-found/failure；不攜 provider arbitrary prose。
- **範圍**:來源 registry 是 session 內、citation 模式內的狀態;turn record 與 Chroma history 不再夾帶 SourceRef snapshot或額外 receipt metadata(收據只存在於 finalized assistant text;舊資料中的 `sources_json` metadata 會被忽略,不影響一般 history 查詢)。停用 citation 仍會清除 registry,不會從磁碟 bundle 自動 rehydrate。

## 12. 疑難排解

| 狀況 | 處理 |
|---|---|
| `ModuleNotFoundError`(如 pytest)或套件找不到 | 多半是沒啟用對的 conda env,或在錯的 env 跑 `poetry install`;`conda activate app && cd app && poetry install`(rag 同理) |
| 功能報錯提到 OpenRouter key | `OPENROUTER_API_KEY` 未進入目前 Conda／程序環境；用 `conda env config vars set -n app ...` 後重新 activate。直接報錯是預期的 fail-fast |
| ingest/search 失敗提到 Ollama/embeddings | 確認 Ollama 正在跑,且 `ollama pull bge-m3` 已完成 |
| `/thinking extended` 切換即報錯 | 需要 OpenRouter key,且 config 設定的 reviewer/rewrite/repair/fusion 模型都要在 OpenRouter 可用;先完成設定再啟用 |
| `/sync` 顯示大量磁碟上不存在的檔案 | 確認 sync 的 root 與當初 ingest 的 root 相同;`file_path` 是以 ingest root 為基準的相對路徑,root 不同會誤判 |
| 找不到 plan mode 的內容 | plan mode 只寫 `app/plan_logs/`,不進 Chroma、`recall_history` 搜不到;直接讀該 markdown 檔 |
| Web Search 工具沒出現 | 確認標準路徑下有 built `dist/index.js`,且 `conda run -n app node --version` 成功；再查 `~/.cache/agent-mcp/` log |
| GitHub 工具沒出現 | 確認 `app` Conda env vars 已啟用 MCP、command 可執行且 token 有效；再查 MCP log |

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
