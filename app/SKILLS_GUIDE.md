# Skills 規範與建立指南

> 這份文件是本專案 skills 的**權威格式參考**。在新增、修改、或重構 skill 時請以此為準。
> 適用對象：人類開發者、Claude Code、Codex、其他 AI 編碼助手。

---

## 為什麼需要這份文件

Skills 有一份開放標準（Agent Skills），但各家 runtime（特別是 Claude Code）在標準之上加了許多自己的擴充欄位和語法。網路上的教學經常把兩者混在一起，導致：

- AI 助手依照 Claude Code 文件寫 skill，但本專案 agent 並非 Claude Code，那些擴充功能不會生效
- 使用了非標準欄位（如 `arguments: [...]`、`context: fork`），讓 skill 失去可攜性
- 在 SKILL.md 內文使用 `` !`command` ``、`$ARGUMENTS` 等 Claude Code 專屬語法，在其他 runtime 變成字面字串

**本專案以 Agent Skills 標準為準。** 撰寫本專案 skill 時，標準之外的欄位或語法，除非在本文件中明確列為「本專案實作的擴充」，否則不使用。安裝外部 skill 則保留原始文件，不為符合本文件而改寫；保留 metadata 不代表 runtime 實作其行為或授予額外權限。

---

## 一、什麼是 Skill

Skill 是一個資料夾，至少包含一個 `SKILL.md` 檔案。`SKILL.md` 包含：

1. **YAML frontmatter** — 給 slash-command help 與 completion 顯示、辨識的 metadata
2. **Markdown 內文** — 使用者明確選擇該次工作後，agent 該照著做的指令
3. **manifest.yaml（選用，本專案擴充）** — 宣告 resource 與 tool policy

Skill 採用**漸進式揭露（progressive disclosure）**：

- **啟動時**：agent 不把 skill 清單、frontmatter 或 description 自動塞進 system prompt
- **執行時**：一般 skill 由使用者透過 `/<skill-name> <自然語言 prompt>` 明確選擇，runtime 才為該次工作載入完整 `SKILL.md`；公開 `skill-installer` 另支援下述明確自然語言安裝入口
- **延伸時**：`SKILL.md` 可引用同目錄的其他檔案；該次 skill 工作中，`references/`、`assets/`、`scripts/` 開頭的路徑會被限制在 skill bundle 內

這個機制讓我們可以維持可預期的手動、一次性選擇路徑，避免 agent 自行掃描、判斷或自動啟用 skills。

### Internal helper skill：`_prompt-master`

`skills/_prompt-master/` 是 `/thinking extended` controller 使用的內部 helper。它一次性 vendor 自 `nidhinjs/prompt-master`，controller 只直接讀取 `SKILL.md` 作為 prompt rewrite 的 system context，不透過 skill loader 自動啟用，也不會改變使用者當前 active skill。

如果使用者手動執行 `/_prompt-master <prompt>`，它仍會走一般 one-shot skill runtime；它沒有 `tools` 區段，所以工具集合與普通模式完全相同。這個資料夾名稱前面的 `_` 是唯一 command-name 例外；一般新增給使用者選用的 skill 仍應使用 kebab-case。

### Built-in skill：`citation`

`skills/citation/` 是內建的引用 skill，同一個資料夾**既是 skill bundle 也是可 import 的 `skills.citation` package**（stateless resolver/service、providers、marker gate、renderer、tool adapter 都住在裡面）。它有兩個一般 skill 沒有的特性：

1. **skill 專屬工具**：manifest 在 `tools.required.local` 要求 session-scoped 的 `citation_workflow` 工具。這類 skill 工具不屬於全域工具，普通模式與其他 skills 綁不到也呼叫不了（執行層 PolicyToolNode 會拒絕偽造呼叫）；只有 manifest 明確要求它的 skill 才綁得到。全域工具（local base tools + Web Search MCP）在 citation skill 下照常可用。
2. **session 隔離副作用**：啟用時強制切回 normal thinking；停用或切換到另一個 one-shot skill 時清除來源 registry。搜尋本身不建立 candidate pool，會直接回傳可供後續 save 使用的 metadata 與穩定 identifier；同輪多次 save 由工具序列化，不設 one-shot turn guard。

`/citation` 是它的專屬 persistent 啟用入口；`/citation off` 才會停用。它不會投影成一般 dynamic command。新增一般 skill 不需要、也不應該仿照這種 host 深度整合；請以 `academic-paper-writing` 為範本。

### Built-in skill：`skill-installer`

`skills/skill-installer/` 是公開的本機 ZIP 安裝 skill。CLI 與 Desktop 的一般對話可輸入「請用 skill-installer 安裝 /tmp/example.zip」，或 `/skill-installer install /tmp/example.zip`。這是明確選用的入口，不是依 description 自動推薦技能。

- **來源路徑**：使用可讀的 Linux 本機 ZIP 絕對路徑；亦可放在 drop-in 的 `skill/` 下，再要求「請用 skill-installer 安裝」。Source checkout 預設為 `app/tool/skill/`；`AgentConfig.extension_dropin_dir` 可覆寫 drop-in root；沒有 checkout 的 wheel 安裝使用 `${XDG_DATA_HOME:-~/.local/share}/research-agent/tool/skill/`。以 `/Extension-Management status` 顯示的實際路徑為準。ZIP 與已展開目錄可共存，ZIP 不會自動成為 catalog 項目。
- **一次選一個**：ZIP 內有多個含 `SKILL.md` 的候選時，依清單回覆 skill 名稱或 `第二個` 等順序。另裝其他候選需提出新請求。同名但內容不同的 source 或既有安裝需要明確更新意圖；未授權時會等待實際使用者回覆「更新」。Builtin 同名衝突會拒絕。
- **有限續接**：來源、候選、更新澄清與待套用 preview 只保留於目前會話的記憶體；回覆「取消」、完成或切換對話都會清除。安裝暫用 normal 工具模式，結束後恢復原 thinking mode。`skill_install` 是此 installer 專屬的 host 工具，既有 shell permission 與選定項目的安裝授權仍各自有效。
- **原始 bundle**：保留原 `SKILL.md`、根層 reference、`scripts/` 等全部支援檔的相對結構與 bytes；不要求自訂 manifest。只安裝選定 skill，保留原 ZIP 與成功展開的 source，不套用其他 Skill/MCP 的 pending changes。下載內容只作安裝資料，不執行其腳本或安裝依賴；`allowed-tools` 等外部 metadata 不會擴張 host 權限。
- **何時可用**：成功回報包含名稱、來源、安裝位置及啟用提示。CLI 需關閉後重新啟動；Desktop 建立新對話或切換到另一份已儲存對話會建立新 startup catalog，也可重啟 backend 後建立／選取對話。繼續或再次選取目前對話不會重新載入。新 catalog 載入後，才可用 `/<skill-name> <prompt>` 選用。

此流程目前不提供遠端 URL 安裝、GUI 拖曳／上傳或 hot reload。第三方私有工具、依賴與腳本的業務能力需要另行驗證；離線 deterministic-model 整合只能證明 host 與檔案流程，不能證明真實模型必然能自主完成安裝。

---

## 二、標準格式

### 目錄結構

```
skills/
└── <skill-name>/
    ├── SKILL.md           # 必要
    ├── manifest.yaml      # 選用，本專案 runtime metadata
    ├── references/*.md    # 選用，補充文件
    ├── scripts/           # 選用，可執行腳本（需 bash 工具支援）
    └── assets/            # 選用，模板或資源檔
```

**命名規則：**

- 資料夾名稱使用 **kebab-case**（小寫字母、數字、連字號）
- 長度上限 64 字元
- 必須叫 `SKILL.md`（大小寫敏感）。`skill.md`、`Skill.md`、`README.md` 都不會被識別
- 只有 internal helper 可以使用 `_` 前綴，例如 `skills/_prompt-master/`

### SKILL.md 結構

```markdown
---
name: skill-name
description: Use when the user wants to ... [具體適用情境]
---

# Skill 標題

## 任務說明
[祈使句寫的指令]

## 步驟
1. ...
2. ...
```

### Frontmatter 欄位（標準）

只有兩個欄位你需要關心：

| 欄位 | 必要性 | 說明 |
|------|--------|------|
| `name` | 建議 | Skill 識別碼。省略時會用資料夾名稱推導。kebab-case。 |
| `description` | **強烈建議** | slash-command help 與 completion 顯示給使用者看的辨識文字。詳見下方寫作指引。 |

**標準也定義但本專案通常不用：**

| 欄位 | 說明 |
|------|------|
| `license` | Skill 的授權條款 |
| `compatibility` | 宣告此 skill 相容於哪些 runtime |
| `metadata` | 自訂 metadata（鍵值對） |
| `allowed-tools` | 標準中標記為 experimental，行為各 runtime 不一，本專案不依賴 |

**就這樣。其他你在網路上看到的欄位都不是標準的一部分**（詳見第五節）。

---

### manifest.yaml 欄位（本專案擴充）

`manifest.yaml` 是本專案 runtime 使用的嚴格 schema。未知 top-level key、型別錯誤、空的 `tools: {}` 都會在 skill 載入時 raise `ValueError`，讓問題早點暴露。舊欄位 `capabilities` / `tool_policy` 與舊版 per-task mode 欄位已移除，出現時會被直接拒絕；applied extension 會在下次 startup 顯示 unavailable diagnostic。

工具模型是兩級的，manifest 只宣告「額外」需要什麼：

- **全域工具**：local base tools（`rag_explore`、`rag_search`、`rag_get_context`、`read_file`、`bash`）加上已載入的 Web Search MCP family。所有模式、每次 skill 工作都有，manifest 不需要（也無法）宣告或移除它們。
- **skill 工具**：其他所有工具（GitHub MCP family、`citation_workflow`、未來的 stateful tools）。只有該次所選 skill 的 manifest `tools` 區段明確要求時才存在。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `tools.required.local` | string list | 必要的本地工具名（如 `citation_workflow`）。解析不到時載入失敗。 |
| `tools.required.mcp_families` | string list | 必要的 MCP family 名（如 `github`）。該 family 沒有任何已載入工具時載入失敗。 |
| `tools.optional.local` / `tools.optional.mcp_families` | string list | 選用工具；不存在時不阻止啟用。 |
| `resources` | list | 每項需有 `path: string`，可選 `use_when: string`、`pinned: bool`。`pinned: "yes"` 這類字串不是 bool，會被拒絕。 |

範例（大多數 skill 不需要 `tools`，省略即可——工具集合與普通模式相同）：

```yaml
tools:
  required:
    local:
      - citation_workflow
  optional:
    mcp_families:
      - github

resources:
  - path: references/checklist.md
    use_when: checklist-heavy tasks
    pinned: false
```

Pinned resources 會在執行該次 one-shot skill 工作時直接放進 context，受 `skill_max_pinned_reference_chars` 與 `skill_max_total_skill_context_chars` 限制。只 pin 每次都必要、且很小的檔案；其他 reference 讓 agent 在該次工作中按需讀取。

工具語義要精確：

- `rag_explore` / `rag_search` / `rag_get_context` 只查 indexed KB（知識庫文件、研究筆記、已 ingest 的資料），不查 conversation JSON。Normal thinking下的較早對話查找，須在已知canonical root下把文字先依JSON規則escape，再以每次需批准的`bash`做exact `grep -F`；listing第21個命中代表文字太寬，必須零讀檔並請使用者縮小，否則最多用`read_file`檢查20檔、排除本輪pending prompt。Canonical JSON大檔可依`next_offset`分段讀至完整檔案，不另設總檔案bytes上限；exact miss不轉用document RAG/embeddings。Extended thinking沒有`bash`，不得宣稱能執行此流程。
- `citation_workflow` 與 `skill_install` 是 skill 專屬工具，分別保留給內建 citation 與 skill-installer，一般 skill 不應宣告。

## 三、Description 寫作指引

`description` 不會讓 agent 自動選擇 skill。一般 skill 使用 `/<skill-name> <prompt>` 明確選擇；skill-installer 的明確自然語言入口由 host 識別安裝意圖，不依賴 description 路由。Description 的作用是讓 help/completion 中的 command 容易辨認，也讓人類維護者快速理解用途。

### 公式

```
What it does + When to use it + （選用）Specific signals / Negative cases
```

### 不好的寫法

```yaml
description: Translates text to formal Chinese.
```

問題：只說功能，使用者在 help/completion 裡不容易判斷該不該選它。

### 好的寫法

```yaml
description: Use when the user wants to translate text into formal written
  Traditional Chinese suitable for business letters, official emails, or
  professional documents. Do NOT use for casual translation or spoken Chinese.
```

差別：明確列出適用情境（商務書信、正式 email、專業文件）和不適用情境（口語、休閒翻譯）。使用者選 skill 時比較不容易選錯。

### Description 寫作清單

- [ ] 寫出**做什麼**（What）
- [ ] 寫出**何時用**（When）— 列出具體的使用者請求型態
- [ ] 必要時寫出**何時不用**（When NOT）— 用 "Do NOT use for..." 或 "Not for..."
- [ ] 用英文寫（方便維護與跨 runtime 閱讀，內文可用中文）
- [ ] 不超過 3-4 句

### 選項辨識度

如果發現使用者常選錯或不知道該選哪個 skill，可以把 description 寫得更具體一點：

```yaml
description: Use when the user wants to translate ... Especially relevant for
  formal letters, official documents, business communication, or 公文-style
  translation, even if the user does not explicitly say "formal".
```

---

## 四、SKILL.md 內文寫作指引

### 基本原則

- 用**祈使句**：「Read the file」「Use this template」，不要「The skill will read...」
- 控制在 500 行內。超過就拆成 reference 檔案
- 解釋**為什麼**這麼做，不要堆疊 MUST、ALWAYS、NEVER
- Skill 是寫給 agent 看的，不是寫給人看的文件——別寫「本 skill 旨在...」這種廢話

### 結構建議

```markdown
---
name: ...
description: ...
---

# Skill 名稱

## When to use
（補充 frontmatter 的 description，講細節）

## Process / Steps
1. 第一步
2. 第二步
   - 子步驟
3. 第三步

## Output format
（明確規定輸出格式，可以給範本）

## Examples
**Input:** ...
**Output:** ...

## Edge cases
- 情況 A：怎麼處理
- 情況 B：怎麼處理
```

### Extended Thinking 與 Skills

`/thinking extended` 不會自動啟用任何使用者 skill。它保留目前 active skill 的 context 與工具集合，另外用 `_prompt-master` helper 把使用者輸入重寫成較清楚的 agent prompt。

Extended mode 的 rewriter、writer、reviewer 都會收到同一份 runtime `[Tool availability]` block（來自共用的 tool access resolution）。fusion proposer 是 read-only 的：只綁固定 read-only allowlist 與當前 effective tools 的交集，`bash`、extra tools 與 MCP tools 一律排除。skill 內文或測試不要自行假設工具集合，一律以 `available_tools` / `unavailable_tools` 為準。

啟用 `/thinking extended` 前，必須直接在 `agent/config.py` 的 `AgentConfig` 填入三個角色 model 欄位：

```python
thinking_reviewer_model: str = "anthropic/claude-haiku-4.5"
thinking_reviewer_max_tokens: int = 1024
thinking_rewrite_model: str = "openai/gpt-5-mini"
thinking_repair_model: str = "openai/gpt-5-mini"
```

這些欄位直接由 `AgentConfig` 決定；任一被設為空字串時，`/thinking extended` 會拒絕切換，避免 Extended mode 靜默退回 `llm_model` 造成同 model 自審。它們不從環境變數或 CLI 參數讀取；`OPENROUTER_API_KEY` 等 secret 則由啟動程序的 Conda／shell 環境提供。

### 漸進式揭露（檔案拆分）

當 SKILL.md 接近 500 行，開始拆檔。在 SKILL.md 裡明確指引何時讀子檔案：

```markdown
## Routing

- 處理表單填寫 → 讀 `forms.md`
- 抽取表格 → 讀 `tables.md`
- 一般文字抽取 → 繼續看下面
```

子檔案路徑是相對於 SKILL.md 所在目錄。Runtime context 會提供真實絕對 `skill_root`；例如用 `read_file` 讀取 `<skill_root>/forms.md`。`read_file` 對一般相對路徑仍以 cwd 解讀，`bash` 的 cwd 仍是 app root；不要因 skill 已啟用就直接假定 `forms.md` 或 `python scripts/example.py` 會指向 bundle。Shell 命令應使用經 POSIX quoting 的絕對資源路徑。

### 多領域組織

當一個 skill 涵蓋多個變體（例如多雲端）時，按變體組織：

```
cloud-deploy/
├── SKILL.md           # 共通流程 + 路由
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

SKILL.md 裡寫清楚「使用者提到 AWS → 讀 references/aws.md」。

---

## 五、⚠️ 不在標準裡的東西

下列項目經常出現在 Claude Code 文件或網路教學中，但**不是 Agent Skills 標準的一部分**。撰寫本專案 skill 時不使用；安裝外部 bundle 時保留原文並如實說明 runtime 不支援的行為。

### Claude Code 專屬 Frontmatter 欄位（不要用）

```yaml
disable-model-invocation: true   # ❌ Claude Code 擴充
user-invocable: false            # ❌ Claude Code 擴充
context: fork                    # ❌ Claude Code 擴充（子 agent 隔離）
agent: Explore                   # ❌ Claude Code 擴充
effort: high                     # ❌ Claude Code 擴充
paths: "src/**,*.md"             # ❌ Claude Code 擴充
argument-hint: [issue-number]    # ❌ Claude Code 擴充
model: claude-sonnet-4-...       # ❌ Claude Code 擴充
hooks: ...                       # ❌ Claude Code 擴充
mode: true                       # ❌ Claude Code 擴充
```

這些欄位寫了不會出錯，但本專案 agent 不會解讀，等於沒效果，反而誤導後續維護者以為 skill 有那些行為。

### Claude Code 專屬內文語法（不要用）

```markdown
!`git diff HEAD`              # ❌ Claude Code 的 bash 預執行注入
$ARGUMENTS                     # ❌ Claude Code 的參數替換
$0  $1  $2                     # ❌ Claude Code 的位置參數
${CLAUDE_SKILL_DIR}            # ❌ Claude Code 的環境變數
${CLAUDE_SESSION_ID}           # ❌ Claude Code 的環境變數
```

在本專案 agent 眼中，這些都是普通字串，會原封不動傳給 model，不會有任何替換或執行行為。

### 不存在的欄位（網路上的訛傳）

```yaml
arguments: [arg1, arg2]        # ❌ 這個欄位根本不存在；正確的是 argument-hint（仍是 Claude Code 擴充）
$name                          # ❌ 沒有具名參數這種東西
```

### 簡單判別法

如果某個欄位或語法**不在本文件列出的標準 frontmatter、SKILL.md 內文寫法，或本專案 `manifest.yaml` 擴充**中，就不要用。

---

## 六、完整範例

### 範例 1：純文字指令型 skill

`skills/formal-chinese-translation/SKILL.md`

```markdown
---
name: formal-chinese-translation
description: Use when the user wants to translate text into formal written
  Traditional Chinese suitable for business letters, official emails, or
  professional documents. Do NOT use for casual translation or spoken Chinese.
---

# Formal Chinese Translation

## Process

When translating into formal Traditional Chinese:

1. Use 您 instead of 你 when addressing the reader
2. Replace colloquial vocabulary with formal equivalents:
   - 給 → 致 / 予
   - 因為 → 由於 / 緣於
   - 但是 → 然而 / 惟
   - 現在 → 現今 / 目前
3. Use complete sentence structures; avoid 啊、啦、欸、耶
4. End requests with formal closings: 敬請查照、煩請惠覆、謹此致謝
5. Preserve original meaning precisely — do not embellish

## Output format

Provide the translation directly without explanation, unless the user
specifically asks for notes on word choices.

## Examples

**Input:** 跟你說一下，那個案子我們可能要延後
**Output:** 茲告知，該案恐須延後辦理。
```

### 範例 2：多檔案 skill

```
skills/code-review/
├── SKILL.md
├── security.md
├── performance.md
└── style.md
```

`skills/code-review/SKILL.md`

```markdown
---
name: code-review
description: Use when the user asks for code review, requests feedback on
  a pull request, asks about code quality, or wants to identify issues in
  existing code.
---

# Code Review

## Process

1. Read the code the user provided
2. Determine which review dimensions apply (often multiple)
3. For each dimension, read the corresponding reference and apply its checklist
4. Aggregate findings into the output format below

## Routing

- Security concerns (auth, input validation, secrets) → read `security.md`
- Performance concerns (algorithms, queries, memory) → read `performance.md`
- Code style / readability → read `style.md`

If unsure, default to applying all three.

## Output format

Group findings by severity:

### 🔴 Critical
- [檔案:行號] 問題描述 + 建議修法

### 🟡 Should fix
- ...

### 🟢 Nice to have
- ...
```

---

## 七、新建 Skill 的工作流程

先分清楚用途：

- **使用者下載的外部 Skill ZIP**：依第一節的 `skill-installer` 對話流程安裝一個選定 skill，保留原始 bundle；不要修改 host Python，也不要搬進 `skills/`。
- **已展開的外部 Skill／MCP 全量管理**：仍可放到 `tool/skill/<skill-name>/` 或 `tool/mcp/<id>/`，先執行 `/Extension-Management --dry-run` 檢查全部增、改、刪，再 apply。這個管理流程會處理所有 pending changes，與對話 installer 的 selected-only 範圍不同。
- **隨專案版本控管的 built-in Skill**：才直接建立 `skills/<skill-name>/` 並提交程式庫。
- `tool/_internal/extension-management/` 是 package 內的私有管理規則；每次管理操作都會重新讀取，但不會投影成 dynamic Skill command，也不得拿使用者 drop-in 覆蓋。

當 AI 助手或開發者要新增一個 skill，依序做：

1. **確認流程已成熟**
   - 你能用口頭跟新進同事講清楚這件事怎麼做嗎？不能 → 還沒到寫成 skill 的時機
   - 流程是否會穩定重複出現？只用一次 → 不需要 skill

2. **建立目錄**
   ```
   skills/<skill-name>/SKILL.md
   ```

3. **撰寫 frontmatter**
   - `name`：與資料夾同名
   - `description`：套用第三節的公式

4. **視需要撰寫 manifest.yaml**
   - 全域工具（local base tools + Web Search MCP + scope=`global` 的 drop-in MCP）不需宣告，永遠可用
   - 需要 skill 專屬工具、GitHub 或 scope=`skill` 的 drop-in MCP family 時，才使用 `tools.required` / `tools.optional`
   - 需要 reference routing 時，使用 `resources`
   - 不要寫空的 `tools: {}`；沒有專屬工具就省略 `tools`

5. **撰寫內文**
   - 祈使句、結構化、舉例
   - 控制在 500 行以內

6. **本地驗證**
   - 外部 Skill ZIP 先完成 `skill-installer` 安裝；已展開的全量管理仍可用 `/Extension-Management --dry-run`、apply。CLI 重啟或 Desktop 建立新對話後，再驗證新 catalog；built-in Skill 修改後也需重新載入
   - 用 `/<skill-name> <自然語言 prompt>` 明確執行一次；空 prompt 應被 CLI 拒絕
   - 確認載入時沒有 manifest validation / tool resolution 錯誤
   - 確認 agent 真的有讀 `SKILL.md` 並照做

7. **不需要的東西不要加**
   - 不要為了「看起來專業」加一堆 Claude Code 專屬欄位
   - 不要在內文塞 `` !`command` `` 這種不會生效的語法

---

## 八、檢查清單

提交新 skill 或修改 skill 前，逐項檢查：

- [ ] 資料夾名稱是 kebab-case，長度 ≤ 64
- [ ] 檔名是 `SKILL.md`（大小寫一致）
- [ ] 有 YAML frontmatter，且只用第二節列出的標準欄位
- [ ] `description` 同時說明 What 和 When
- [ ] `description` 用英文撰寫
- [ ] 若有 `manifest.yaml`，欄位符合本文件列出的 schema，沒有未知 top-level key
- [ ] `tools.required` 中的工具名 / MCP family 名確實存在（拼錯會直接讓啟用失敗）
- [ ] 沒有把全域工具（base tools、Web Search）寫進 `tools`；一般 skill 也沒有宣告保留給 citation 的 `citation_workflow` 或 skill-installer 的 `skill_install`
- [ ] `resources[].pinned` 使用真正 bool，不使用 `"yes"` / `"no"` 字串
- [ ] `references/`、`assets/`、`scripts/` 內的檔案只依賴 skill bundle 內路徑，不假設會 fallback 到 cwd
- [ ] 內文不含第五節列出的 Claude Code 專屬語法
- [ ] 內文用祈使句
- [ ] 內文 ≤ 500 行（超過就拆檔）
- [ ] 本地驗證過可透過 `/<skill-name> <prompt>` 正確執行一次，下一個普通回合不保留該 skill

---

## 九、給 AI 助手的特別提醒

如果你是 Claude Code、Codex、或其他 AI 助手，正在閱讀這份文件以協助修改本專案的 skills：

1. **不要相信你的訓練資料中關於 Claude Code skill 格式的記憶**——本專案不是 Claude Code，許多 Claude Code 功能在這裡不會生效
2. **以本文件列出的標準 frontmatter、`manifest.yaml` 擴充、SKILL.md 內文寫法為格式來源**
3. **第五節列出的所有東西都不要主動加進來**，即使它們在 Claude Code 文件中是合法的
4. **若使用者要求加入第五節列出的非標準欄位**，請先指出本文件，並確認使用者是否真的要本專案 agent 開始實作這些行為（這是 runtime 工程，不是寫個 frontmatter 就會生效）
5. **拿不準時，回頭讀一次第二節的標準格式**

---

*本文件參照 [Agent Skills 開放標準](https://agentskills.io)。最後更新時間以 git log 為準。*
