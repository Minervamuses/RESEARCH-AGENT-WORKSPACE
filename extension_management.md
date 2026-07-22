# Extension Management 熱插拔改造計畫

日期：2026-07-22

狀態：待審核；本文件只規劃改動，尚未修改 production code

探查基準：commit `a8209a3` 與目前 working tree（既有 `cite/` 變更不在本計畫範圍內）

## 決策摘要

本次把「熱插拔」明確定義為：使用者可在 CLI 啟動前或啟動後，把 MCP／Skill 資料夾放進約定目錄，再執行一次 `/Extension-Management`，同一個 `ChatSession` 就完成掃描、驗證、增改刪、工具權限重算與 LangGraph runtime 切換，不需要修改 Python，也不需要重啟 CLI。

第一版採用以下架構：

```text
app/tool/                         # 使用者與維護者面對的 extension 根目錄
├── mcp/<extension-id>/           # MCP drop-in bundles
├── skill/<skill-id>/             # public Skill bundles
├── local/                        # v1 保留位置；本次不開放動態 Python import
└── _internal/
    └── extension-management/
        └── SKILL.md              # 私有、每次管理命令強制重新讀取

                scan + fingerprint
                         │
                         ▼
              Extension-Management agent
           （私有 skill + 最小權限管理工具）
                         │ structured plan
                         ▼
        deterministic validator / reconciler / registry
                         │ candidate runtime
                         ▼
      atomic ChatSession runtime + LangGraph generation swap
```

核心決策：

1. `/Extension-Management` 是 built-in slash command，大小寫不敏感；canonical 名稱可用 `extension-management`，現有 registry 的 `casefold()` 已讓使用者輸入 `/Extension-Management` 正常命中。
2. Management agent 是獨立、一次性的最小權限 agent，不是一般 `/skill`，也不使用 `SlashCommandResult.followup_input` 進入主 agent。
3. 私有 management skill 放在 public Skill 掃描路徑之外；每次命令都從固定路徑重新讀取、驗證、計算 hash，禁止 cache，缺失或損壞時 fail closed。
4. Deterministic scanner 負責產生不可變、完整的 authoritative diff。Agent 每次 fresh read私有 skill後查看該diff，只能補足「缺少descriptor的MCP」之有限候選欄位與說明；不得新增、刪除、改類型或漏報op。真正的plan coverage驗證、filesystem containment、MCP trust/probe、registry、graph rebuild與swap全由host code執行。
5. Extension 目錄代表 desired state；另保存 last-known-good applied registry。新增／更新失敗不會破壞仍可用的舊版，已存在但損壞的資料夾也不會被誤判成刪除。
6. Skill refresh 不能只更新 picker；MCP refresh 不能只更新 `extra_tools`。任何工具 universe 變更都要先建完整 candidate runtime，再一次替換 session 的 tools、family map、active Skill resolution、prompt availability 與 compiled graph。
7. 本次目標是 MCP 與 Skill。`app/tool/local/` 在v1只是保留／說明位置，不參與scan、registry或generation diff；實際Local Tool仍由`app/agent/tools/`靜態註冊。除README外若出現內容，manager明確回`unsupported`，不靜默忽略或安裝。
8. 不先做全 repo 搬家。`app/skills/citation` 同時是 Skill bundle 與 importable Python package；先用 compatibility provider 接入中央 catalog，再分階段搬 bundle assets，避免 big-bang import／packaging 重構。

## 現況探查結果

### 現行載入鏈

```text
CLI startup
  ├─ ChatSession.create()
  │    ├─ load_mcp_tools_with_families()
  │    │    └─ resolve_mcp_specs()
  │    │         ├─ _web_search_spec()   # hard-coded
  │    │         └─ _github_spec()       # hard-coded
  │    └─ ChatSession(... extra_tools, mcp_families)
  │         ├─ discover_skills()         # startup snapshot
  │         └─ build_graph()             # captures complete tool universe
  └─ build_default_registry()            # fixed slash command registry
```

| 區域 | 現況 | 熱插拔阻礙 |
|---|---|---|
| MCP discovery | `app/agent/mcp.py:56-137` 只認 Web Search 與 GitHub；前者固定找 user-data entrypoint，後者固定讀專用 env vars | 放入第三個 MCP 資料夾不會被發現 |
| MCP loader | `app/agent/mcp.py:216-257` 已能載入任意 `MCPServerSpec` 並回傳 tool→family map | loader 可沿用，但 spec discovery、schema、trust、collision 尚未泛化 |
| MCP transport | `app/agent/mcp.py:188-213` 強制 `/bin/sh -c` + `grep` 的 stdio pipeline | 綁 Linux shell；資料驅動 command 後會放大 command/path 風險 |
| MCP lifecycle | `app/agent/session.py:963-1001` 只在 `ChatSession.create()` 載入一次 | session 中途沒有 reload／unload API |
| Skill discovery | `app/agent/skills/metadata.py:16-56` 只掃單一 `app/skills/*/SKILL.md` | 沒有 public/internal、多 root、嚴格 diagnostics 或 applied state |
| Skill cache | `app/agent/session.py:124-130` 把發現結果存入 `loaded_skills`；`app/agent/cli/slash_commands.py:466-471` 優先使用該 snapshot | 當前 session 看不到新增／改名；刪除項仍留在 picker |
| Skill activation | `app/agent/skills/runtime.py:156-202` 啟用時其實會重新 discover 並重讀內容 | 同名既有 Skill 停用再啟用可吃到修改，但 active runtime 不會自行更新 |
| Tool graph | `app/agent/graph.py:200-270,448-462` 在 compile 時固定 tool objects、name map、default bindings 與 `PolicyToolNode` | 改 list 不等於改 graph；必須 rebuild + swap |
| Tool access | `app/agent/tool_access.py:25-109` 把唯一 global MCP family 寫死為 `web_search` | 新 family 的 exposure 無法由 extension metadata 決定 |
| Local tools | `app/agent/tools/inventory.py:42-150,202-226` 固定 metadata 與 factories | 下載的 Skill 若要求新 Python tool，仍必須改 host code |
| Slash commands | `app/agent/cli/slash_commands.py:140-210` 靜態註冊；`app/agent/cli/chat.py:123-147` 在本地執行 | 新 management command 要明確接入；不能把工作轉回普通 agent |
| Internal Skill | `_prompt-master` 只是命名慣例，文件甚至允許 `/skill _prompt-master` | 現在沒有「只能被特定 agent 載入」的權限語義 |
| Built-in citation | `app/skills/citation` 同時含 `SKILL.md` 與 `skills.citation.*` Python package；`session.py:13-24` 等直接 import | 直接搬到新根會破壞 imports、Poetry package 與大量測試 |

### 精確的現況判斷

- 純 prompt/resource Skill 本來就不必改 Python；目前缺的是同 session 的 strict rescan/reconcile。README 所說「修改後一定要重啟」是保守說法，不完全等於 runtime 行為。
- 帶新 local/stateful tool 的 Skill 不是純 Skill 熱插拔問題。現有 `citation_workflow` 由 `ChatSession` 明確 import、建立、加入 `skill_tools` universe，還有專屬 teardown；任意下載 bundle 不能只靠 `manifest.yaml` 變出 Python tool。
- MCP host loader 已有通用的一半：`load_mcp_tools_with_families(specs=...)`。缺的是資料夾契約、strict manifest、信任、diff、collision guard 與 session runtime transaction。
- 現有 graph 以 tool name 建 dict；MCP loader 的 family map 也按 tool name 後寫覆蓋。若兩個 server 或 MCP/local tool 同名，可能出現「執行的是 A tool，權限 family 卻來自 B」；動態化前必須先補 collision fail-fast。
- `read_file` 是一般全域工具，能讀絕對路徑；本計畫承諾的是 management skill 不可被 `/skill` 列出或啟用，不宣稱該檔案在作業系統層面對主 agent 完全不可讀。

## 目標與非目標

### 目標

1. 使用者新增、修改、刪除支援格式的 MCP／Skill 時，不再修改 host Python。
2. `/Extension-Management` 後，變更在同一 session 的下一個 turn 生效。
3. 新增／更新／刪除都可被辨識並有明確結果：`applied`、`unchanged`、`pending_approval`、`quarantined`、`removed`、`rolled_back`。
4. 新 runtime 未完整驗證前，舊 runtime 持續可用；失敗不得留下 tools、family map、prompt 與 graph 各自處於不同 generation 的半套狀態。
5. 私有管理規則每次都強制 fresh read；一般 `/skill` picker、`/skill extension-management` 與 public runtime loader 都不可取得它。
6. 下載內容不因「被掃到」就執行；尤其 MCP command、install/build 與 global exposure 要通過信任界線。
7. 保留現有 global local tools、Web Search 預設行為、GitHub skill-scoped 行為、citation isolation、`--no-mcp` 與單一 server 失敗不拖垮 CLI 的既有語義。
8. 所有變更有 content hash、generation、結果與 sanitized diagnostics，可重現、可稽核、可 rollback。

### 非目標

- v1 不做背景 filesystem watcher；熱插拔由 slash command 明確觸發。
- v1 不動態 import／reload 任意 Python Local Tool，也不讓下載 Skill 直接註冊 host tool factory。
- v1 不保證任意 GitHub MCP repository 都能零歧義自動安裝。無標準 manifest 的 bundle 可由 agent產生「候選 descriptor」，但只有 deterministic validation 與使用者批准後才可執行。
- 不讓 management agent 任意使用 `bash`、RAG、history、一般 MCP 或主 session 的 tools。
- 不讓 public Skill 透過 `manifest.yaml` 要求 `extension_apply` 等管理能力。
- 不在第一個 commit 直接搬移 `app/skills/citation` Python package。
- 不自動修改、格式化或刪除使用者拖入的 source bundle；管理的是 applied catalog/runtime，來源目錄仍由使用者控制。

## 不可破壞的不變條件

1. **未批准不執行**：raw drop-in MCP 不得在 startup scan 或 descriptor inference 階段啟動。
2. **私有規則不可旁路**：management command 缺少有效 private `SKILL.md` 時停止；不得 fallback 成一般模型自由決策。
3. **管理工具不進主 universe**：主 graph、public Skill 與 `PolicyToolNode` 永遠看不到 mutation tools。
4. **單一 runtime generation**：tools、MCP families、global family set、public Skill catalog、active Skill runtime、availability prompt、main graph 必須同 generation。
5. **失敗保留 last-known-good**：invalid add 不安裝；invalid update 保留舊 applied snapshot；candidate graph 失敗不替換現行 graph。
6. **資料夾存在但壞掉不等於刪除**：malformed YAML、copy 未完成、權限錯誤、symlink 越界一律是 invalid/pending，不可被 diff 當成 remove。
7. **名稱唯一**：extension ID、public Skill name、MCP family/tool name與 local tool name的 collision 在 commit 前拒絕，不能靠載入順序決定勝負。
8. **active Skill 不懸空**：刪除或變更 active Skill／required family 時，要 reload 成新 runtime或明確 deactivate；不能留下指向已刪路徑與舊權限的 runtime。
9. **host metadata不序列化秘密**：registry、normalized descriptor與audit只保存 env var 名稱，不保存token/value。第三方MCP取得獲准secret後仍可能自行外洩，不能把timeout/cwd誤稱sandbox；untrusted MCP stderr預設不持久化，只回傳經known-secret redaction的bounded diagnostics。
10. **無 shell 字串拼接**：runtime command 使用 argv + bounded cwd/env；不把未信任 manifest 丟進 `/bin/sh -c`。
11. **`--no-mcp` 優先**：該次 session 即使 catalog 有 MCP，也只能管理 metadata，不得 probe、啟動或綁定 MCP。
12. **同一時間不改兩次runtime**：turn、runtime swap、`/skill`、`/citation`與其他active Skill mutation都走同一個public session transaction API；management single-flight另防兩個reconcile同時執行，固定順序只能是management operation → session runtime lock。

## 目錄與來源模型

### Source checkout 為何選 `app/tool/`

在目前這個source-checkout專案中，中央根放在`app/tool/`，而不是workspace root的`tool/`：

- `find_app_root()` 已可靠定位 `app/`，不依賴使用者從哪個 cwd 啟動。
- `/init` 現在排除整個 `app/` 與 `rag/`；放在 `app/tool/` 不會把下載的 README、private management skill 或可能含 prompt injection 的內容 ingest 進研究 RAG。
- 可由`app/pyproject.toml`明確include host-owned bundle data。
- 避免和既有 Python package `app/agent/tools/` 混成同一 import namespace。

但installed wheel通常沒有`pyproject.toml`、site-packages也不保證可寫，不能把wheel內resource與使用者drop-in混成同一信任域。路徑resolver因此明分：

- **shipped resource root（read-only）**：以`importlib.resources`定位host-owned/private bundles；source checkout時對應`app/tool/`內受版控部分。
- **user drop-in root（writable）**：`AgentConfig.tool_root`明示值優先；source checkout預設可用`app/tool/`，installed mode預設使用platform/XDG user-data下的`tool/`。
- **state root（writable, non-source）**：`extension_state_dir`存registry、snapshots與audit，永遠不和raw drop-in或shipped resources共用。

因此source checkout維持使用者想要的單一`app/tool/`視圖；wheel模式則仍使用相同子目錄契約，但物理上把受信任shipped resources與可寫drop-ins分離。

### 目錄契約

```text
app/tool/
├── mcp/
│   └── <kebab-case-id>/
│       ├── extension.yaml        # 建議；runtime 的唯一 canonical contract
│       └── ...                   # server source/build artifacts
├── skill/
│   └── <kebab-case-id>/
│       ├── SKILL.md              # 必要
│       ├── manifest.yaml         # 選用；沿用現有 strict schema
│       ├── references/           # 選用
│       ├── assets/               # 選用
│       └── scripts/              # 選用；不自動執行
├── local/
│   └── README.md                 # v1 說明 host-owned、非 hot-pluggable
└── _internal/
    └── extension-management/
        └── SKILL.md              # v1唯一允許檔案；每次命令 fresh read
```

Applied registry、last-known-good snapshots、build staging 與 audit 不放在使用者 drop-in tree；新增可注入的 `extension_state_dir`，預設使用 platform/XDG state-data 路徑並以 workspace identity 分區。這樣 raw source update 損壞時仍能回到已驗證 snapshot，也不會把 token 或本機絕對 build path commit 進 repo。

### 過渡期來源

第一個可用版本同時有兩種ownership provider，但只產生一個合併catalog：

1. `BuiltInSkillDescriptorProvider`：host-owned ID明確映射到bundle resource path、host skill tools與lifecycle hooks。過渡期descriptor指向現有`app/skills/`，保住citation、academic-paper-writing與`_prompt-master`目前可手動選取的行為。
2. `DropInExtensionProvider`：只掃writable public root的`skill/`與`mcp/`作為desired inventory，絕不掃`_internal`；主runtime只讀已套用的managed snapshots，不直接載入raw folders。

`discover_public_skills()`合併host-owned descriptors與applied drop-in records；規則是built-in ID保留、drop-in不可覆寫。日後搬bundle時是原本descriptor原子改指新resource path，不是把built-in降級成drop-in，並在同commit移除舊path provider與提供rollback。這不是熱插拔主路徑的前置條件。

## Extension 資料契約

### 共通識別與 fingerprint

- ID／folder name：`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`，長度 1–64。
- `kind + id` 是 registry key；大小寫折疊後也必須唯一。
- 禁止 `_internal`、`.state`、`extension-management`、現有 slash command名稱與 host 保留名稱。
- 禁止 symlink、hard-link escape、special file、路徑穿越與 bundle root 外 resource/cwd/entrypoint。
- Fingerprint 由 canonical relative path、file type、size 與 content hash 組成；不相信 mtime。
- 排除 `.git/`、platform metadata、cache、logs 與 manager state；是否排除 `node_modules/`／build output 由 MCP descriptor 明確列出，不能由 scanner 猜。
- 掃描前後 fingerprint 不一致視為 `unstable_copy`，本輪不 apply。

### Skill bundle

Skill 沿用現有 `SKILL.md` + optional `manifest.yaml`，但 management scan 比目前 `discover_skills()` 更嚴格：

- `SKILL.md` 必須有可解析 frontmatter、非空 `name`／`description`，且 frontmatter name 必須等於 folder ID。
- 檢查 ID 格式、casefold collision、檔案／總容量上限、UTF-8、resource containment、pinned limits。
- discovery 階段就驗證 `manifest.yaml`，不讓壞 manifest 先出現在 picker、啟用時才爆。
- manifest列出的每個resource（不只pinned）都必須存在、是regular file且落在staged snapshot內；pinned項再套內容大小上限。
- manifest 的 required/optional tools 必須對 candidate tool universe 解析；required 缺失則該 Skill 不進 applied catalog。
- 網路下載 Skill 的未知 vendor frontmatter／語法會回 compatibility diagnostics。可保留 inert metadata，但不得假裝本 runtime 支援 Claude Code hooks、`context: fork`、自動 script 或任意 local tool。
- `scripts/` 只是 Skill resource；仍需現有受批准的 `bash` 路徑才可能執行，Extension-Management 不會因安裝 Skill 自動執行它。

### MCP bundle 與 normalized descriptor

Runtime 只接受 schema 驗證過的 normalized `extension.yaml`。建議最小形狀：

```yaml
schema_version: 1
kind: mcp
id: github
version: 1.2.3
family: github
exposure: skill

runtime:
  transport: stdio
  command: ./bin/github-mcp-server
  args: [stdio]
  cwd: .
  stdout_policy: strict
  init_timeout_seconds: 20
  tool_call_timeout_seconds: 60

environment:
  GITHUB_PERSONAL_ACCESS_TOKEN:
    from_env: GITHUB_PERSONAL_ACCESS_TOKEN
    required: false
  GITHUB_TOOLSETS:
    value: repos,pull_requests,issues,actions,context
    secret: false

compatibility:
  platforms: [linux]
  executables: []
```

契約規則：

- `family` 是 Skill manifest 使用的 capability identity；`id` 是 bundle identity，兩者不可暗中由 tool name 推導。v1每個family只能有一個owner extension，避免同family中只有一個獲准global卻讓其他server一起升權。
- `exposure` 只有 `global|skill`。新下載 MCP 預設 `skill`；要求 global 必須在 change plan 顯示並獲信任批准，不能由 bundle 自我宣告後自動升權。
- phase 1 正式支援 stdio。HTTP/SSE/WebSocket schema 可以先保留 discriminator，但要等 header secret、TLS、origin 與 lifecycle 測試完成再開。
- command 使用 managed snapshot 內相對 executable，或經resolver找到的allowlisted interpreter；args是字串陣列，禁止shell fragment。Interpreter + script/module argv同樣是code execution surface，trust必須綁exact argv，不能只批准`node`或`python`名稱。
- `cwd` 必須落在 managed snapshot 內。
- secret 只能 `from_env`；literal value 若標 secret 或疑似 token，拒絕並要求改用 env reference。
- child env從最小allowlist建立，不繼承完整`os.environ`；`LD_PRELOAD`、`PYTHONPATH`、`NODE_OPTIONS`等runtime控制變數預設拒絕，除非host policy另有專用trusted adapter。
- init/probe與每次tool call使用不同timeout；另限制tool數量、名稱／description長度、serialized input schema、單次result大小、檔案數量、環境變數數量與argv長度。
- `stdout_policy`只能是host實作的`strict|json_lines`。現有Web Search需要過濾stdout banner，改用host-owned direct-subprocess sanitizer，不把未信任argv串成shell pipeline；fake server測試要覆蓋noise line。
- tool discovery/probe 後，把 tool names 寫進 candidate record；任何跨 MCP、MCP/local、MCP/management collision 都拒絕整個 candidate generation。

若 raw MCP folder 沒有 `extension.yaml`：

1. Management agent 可把 `package.json`、`pyproject.toml`、known MCP metadata 與 README 當作**未信任資料**分析。
2. Agent 只能輸出上述有限 schema 的 candidate descriptor與 evidence；README 內要求「忽略規則／執行某命令」不具權限。
3. Deterministic validator 檢查 entrypoint 是否存在、argv 是否可安全解析、runtime 是否存在、secret 是否只引用 env。
4. 每個新MCP的首次probe，以及descriptor/artifact/argv/cwd/env-name set/exposure任一改變，都先列為execution trust approval；install/build/network另列風險。approval綁定這些hash與exact values，未批准連probe都不得執行。
5. 批准後只在 managed staging snapshot 執行 bounded subprocess，不修改 raw bundle；成功 probe 才可成為 applied descriptor。
6. 無法唯一判定 entrypoint 時 quarantine 並回報需要的最小資訊，不猜一個命令直接啟動。

這個設計保留「下載後拖入」體驗，但 runtime 永遠不直接信任模型猜測。

Legacy Web Search／GitHub由host compatibility provider帶預先信任記錄：GitHub token保持現況的optional警告語義；外部user-data Web entrypoint與`/opt/...` command可使用明確的`trusted_external`例外，不開放給drop-in descriptor。Web Search同時使用上述host-owned stdout sanitizer。等它們materialize進managed snapshot後才移除例外，不能一面宣稱等價相容、一面套用只允許snapshot-relative path的新規則。

## Extension-Management agent

### 身分與入口

新增 `ExtensionManagementAgent`，由 slash handler 直接呼叫：

```text
/Extension-Management
  -> handler awaits session.extension_manager.reconcile(...)
  -> manager exact-path loads private SKILL.md
  -> dedicated management graph
  -> structured ManagementPlan
  -> deterministic apply + RuntimeSwapReport
```

不可使用 `followup_input`。現有 `app/agent/cli/chat.py:143-150` 會把 followup 送進普通 `session.turn()`，繼承使用者當前 active Skill 與主 graph tools，正好違反「private skill 強制每次讀」及最小權限要求。

### 私有 Skill loader

新增 exact-path loader，例如：

```text
load_internal_skill(
  app/tool/_internal/extension-management/SKILL.md,
  expected_name="extension-management",
)
```

硬性行為：

- `DropInExtensionProvider`只掃writable public root的`skill/*/SKILL.md`，完全不走`_internal`；`discover_public_skills()`另合併受信任built-in descriptors。
- `/skill` picker 不列出 management Skill。
- `/skill extension-management` 及大小寫／alias 變體皆回 unknown/reserved Skill。
- private loader 不以名稱搜尋，不接受使用者路徑，只接受 host 常數解析出的 exact path。
- v1 private bundle只允許單一`SKILL.md`，不允許references/scripts/assets；每次command invocation重新讀全文、驗證frontmatter/size與完整bundle hash，不放入`ChatSession._prompt_master_skill_text_cache`類cache。
- manager system context記錄本次 private bundle hash；approval前、commit前都重查同一hash，apply report與audit也記錄它。執行中被替換時abort/rescan。
- 缺檔、無效 YAML、名稱不符、超限、symlink時中止整次管理操作。

### 最小權限工具

Management graph使用全新的minimal builder、history-free state與獨立system prompt；不重用會自動注入RAG/history/read_file/bash的現有`build_graph()`，也不帶主session recent turns或active Skill。它只綁以下read-only／pure工具；名稱僅示意：

- `extension_get_diff`：回傳host已產生的immutable authoritative diff、diagnostics、content hash與opaque scan token。
- `extension_inspect`：只讀 scan token 所指 bundle內 allowlisted metadata/text，有限大小、禁止 escape。
- `extension_check_candidate`：pure schema/policy check，僅協助修正缺descriptor MCP的candidate fields，不做probe或mutation。

模型返回後，slash host才執行exact coverage validation、顯示／取得approval並直接呼叫reconciler；apply API永遠不是model tool。上述read-only工具也不得傳給主`build_graph(... skill_tools=...)`，因目前public Skill selector只按tool name授權、沒有owner/principal。Management graph不含`bash`、RAG、history、一般`read_file`、citation或任何已下載MCP。

### Agent 的責任邊界

Agent可以：

- 查看host已分類的完整authoritative add/update/delete/no-op diff。
- 對缺descriptor的MCP整理候選entrypoint與必要runtime。
- 為每一個authoritative op產生typed proposal outcome與人類可讀摘要。
- 將不確定項標成 blocked/pending，而不是硬猜。

Agent不可以：

- 直接刪、搬、覆寫 raw source folder。
- 直接執行 shell、package manager或 MCP server。
- 自行決定 secret 值或擴張 env inheritance。
- 自行把 MCP升為 global。
- 在 deterministic validator拒絕後改用另一條旁路重試 mutation。
- 把 bundle README／SKILL.md中的指令提升成 manager system instruction。

Agent輸出必須通過strict structured parsing；最多做一次只針對schema error的bounded repair，仍無效就整次fail closed。Validator必須證明scan token相同、每個authoritative op的kind/ID/hash不可變且剛好有一個結果、沒有額外op；不能把未解析prose、漏掉delete或自行新增的operation交給apply層。純Skill與已有strict MCP descriptor的CRUD不依賴模型決策，agent只能說明其deterministic outcome。

## Change detection 與 applied registry

### Registry 最小內容

```json
{
  "schema_version": 1,
  "generation": 12,
  "workspace_id": "...",
  "private_bundle_hash": "...",
  "extensions": {
    "skill:academic-paper-writing": {
      "source_path": "...",
      "source_hash": "...",
      "snapshot_path": "...",
      "normalized_manifest_hash": "...",
      "status": "applied"
    },
    "mcp:github": {
      "source_path": "...",
      "source_hash": "...",
      "snapshot_path": "...",
      "snapshot_checksum": "...",
      "artifact_hash": "...",
      "normalized_manifest_hash": "...",
      "approved_descriptor_hash": "...",
      "approval": {
        "scope": "execute+skill-exposure",
        "approved_at": "...",
        "command_binding_hash": "..."
      },
      "family": "github",
      "exposure": "skill",
      "tool_names": ["..."],
      "tool_surface_hash": "...",
      "build_provenance": null,
      "status": "applied"
    }
  }
}
```

Registry以temp file + fsync + atomic replace寫入，檔案權限0600；audit用append-only JSONL，所有host diagnostics先做known-secret redaction。若build output／`node_modules`不進source fingerprint，`artifact_hash`與snapshot checksum仍必須內容定址實際執行物，並記錄generated descriptor/build recipe provenance。每一generation保留有限數量last-known-good snapshots供rollback，GC只在新generation已durable且不再被runtime引用後執行。

### Diff 語義

| Desired tree vs applied registry | 結果 |
|---|---|
| 新 ID、strict validation成功 | `add`，進 candidate generation |
| 新 ID、validation／approval失敗 | `quarantined`／`pending_approval`，不影響現行 runtime |
| 同 ID、hash改變、驗證成功 | `update`，新 snapshot取代 applied version |
| 同 ID、hash改變、驗證失敗 | 保留舊 applied snapshot，持續回報 pending invalid update |
| applied ID在 desired tree確實不存在 | `delete`，candidate catalog移除；raw source本來已由使用者移除 |
| desired path存在但 unreadable／malformed／unstable | 不是 delete；保留舊版或不安裝 |
| folder rename | 舊 ID delete + 新 ID add；不得偷偷把 identity沿用 |
| hash與 normalized manifest皆相同 | `unchanged`，不 probe、不 rebuild graph |
| duplicate/casefold collision | 相關項全 blocked；不得靠排序挑一個 |

## Runtime 重建與原子切換

### 新 runtime state

Extension catalog generation與一般`/skill`切換是兩種revision：切換Skill不應假裝extension generation增加，但active runtime又必須和其解析時使用的tool universe一致。因此採兩層不可變state：

```text
ExtensionRuntimeSnapshot
  generation
  public_skills
  complete_tool_catalog         # base + MCP + host-owned skill tools及owner/scope
  extra_tools                   # MCP compatibility view
  host_skill_tools              # 例如 citation_workflow
  mcp_families                 # tool_name -> family
  global_mcp_families          # trusted catalog policy
  mcp_handles                   # 本generation擁有的可關閉runtime resources
  mcp_enabled                   # 保留 --no-mcp session policy
  web_search_tool_names        # compatibility property during migration
  graph
  capability_prompt_block
  source_registry_hash

SessionRuntimeState
  revision
  extensions: ExtensionRuntimeSnapshot
  active_skill_runtime          # name/task_mode/tool resolution/source hash
  active_skill_extension_generation
```

`/skill`／`/citation`在同一session transaction API下，以相同extension snapshot建立新的`SessionRuntimeState`；extension reconcile則同時替換extension snapshot與重新materialize／deactivate後的active runtime。`ChatSession.loaded_skills`、`extra_tools`、`mcp_families`與`active_skill_runtime`先保留read-only compatibility properties，內部都改讀單一state pointer，避免測試與其他模組一次全斷。

### Reconcile transaction

1. 取得management single-flight operation reservation，讀durable current generation與session runtime revision；第二個reconcile立即回busy，不排隊重入。
2. Strict scan desired tree，由host產生immutable authoritative diff，複製穩定內容到managed staging；保留source hash與scan token。
3. Fresh load private management Skill；manager agent查看該diff，只補缺descriptor MCP的bounded candidate fields並為每個op回proposal outcome。
4. Deterministic validator檢查typed shape、完整coverage與op identity/hash不可變；有首次／變更MCP execution trust、install/build/network或global exposure時顯示exact plan並取得approval。此時沒有session runtime lock。
5. Approval後重查scan token、source hashes、private bundle hash與durable generation；任何變動都abort/rescan，不沿用舊批准。
6. 對可套用項建立managed artifacts；只有已批准MCP才可load/probe。單一item失敗依下述item policy quarantine或保留last-known-good，其餘安全項繼續組成一個閉合candidate catalog。
7. 由candidate tools建立完整tool→family map；在build graph前拒絕final catalog的extension ID、family ownership、tool name、local/skill/management collision。
8. 以candidate universe重建main graph、dynamic availability、host skill tools與active Skill candidate；清掉／重建會捕獲舊universe的Fusion caches。
9. 把immutable generation manifest、snapshots、artifact/tool-surface checksums完整寫入+fsync，但尚不移動durable`current` pointer。
10. 透過public `session.runtime_transaction()`取得session runtime lock，重新確認extension generation、session revision、active Skill與task mode沒有在prepare期間改變；stale時釋放、重建active candidate或整次retry。
11. 在lock內先以atomic replace提交durable`current` pointer；成功後只做保證不raise的單一`SessionRuntimeState` pointer assignment與prepared lifecycle state transition。pointer commit失敗時memory完全未改。
12. Durable與memory都commit後才執行citation teardown等不可逆cleanup；釋放session lock，讓retired MCP handles等in-flight引用歸零後`aclose()`。Audit與GC是post-commit best-effort，不反向宣稱主transaction失敗。
13. 釋放management reservation，回傳每一項add/update/delete/blocked/quarantined與active Skill影響。

Management operation可以跨互動approval持有single-flight reservation，但不得持session lock；因此turn與`status`仍可執行，第二個reconcile只會收到busy。唯一鎖順序是management operation → session runtime lock，任何`/skill`、`/citation`或turn路徑都不得反向取得management lock。LLM、`input()`、copy、build與probe一律在session lock外。

舊generation在swap後進入retired狀態：等既有in-flight引用歸零，再呼叫其`aclose()`並回收process/session/build資源。即使目前使用的MCP adapter多半在每次tool call建立短session，也要由snapshot明確擁有lifecycle，避免未來換transport後delete只從graph消失、背景連線卻殘留。

### Active Skill 政策

| 變更 | 套用政策 |
|---|---|
| active Skill 未改、MCP universe未影響它 | 重用或重新 materialize等價 runtime，但 tool access來自新 generation |
| active Skill內容更新且新 bundle有效 | 在 swap時直接換成新 `SkillRuntime`，下一 turn讀到新 instructions/references |
| active Skill被刪 | transaction繼續，明確 deactivate並回報 |
| active Skill更新無效 | 保留 last-known-good applied Skill與 runtime，不套用壞更新 |
| active Skill更新有效但移除目前task mode | 套用新bundle、明確deactivate並回報；不靜默改到另一mode |
| required MCP family被刪／失效 | MCP刪除照 desired state套用；deactivate該 Skill並回報 missing required family |
| optional MCP family被刪 | Skill維持 active，以新 resolution移除 optional tools並更新 availability |
| active Skill內容不變但global MCP集合改變 | 一律依新generation重算tool access，不重用帶舊resolution的runtime |
| citation離開 active狀態 | 必須走既有 `_teardown_citation_session_state()`，不能只把欄位設 None |

### Failure 與 rollback

- **item failure**：invalid/unapproved add不進candidate；invalid/unapproved update保留該ID的last-known-good；單一MCP load/probe失敗同樣quarantine／保留舊版。其他安全變更仍可形成candidate generation。
- **generation failure**：final catalog collision、graph compile、active runtime materialization、checksum／durable pointer commit或precondition retry耗盡時，整代abort；durable current與memory pointer都不變。
- 所有會raise的建置在commit前完成；durable current pointer失敗時尚未改memory，因此不需要假裝能復原已teardown的citation state。
- 如果本次原本會停用citation但commit失敗，舊`SessionRuntimeState`、`CitationService`與SourceRefs必須保持原物件與內容；以專門測試鎖定。
- CLI crash後 startup只讀最後完整、checksum有效的 applied generation；殘留 staging不可見，後續由 GC清理。
- `/Extension-Management status` 顯示 desired/applied drift與 last error；`rollback <generation>` 可列為 phase 2 command，底層 snapshot機制從 v1就要保留。

### Startup realization

Startup沒有舊in-memory graph可rollback，但仍要保留目前「單一MCP失敗不拖垮CLI」的可用性。載入最後applied generation時，逐項realize：成功MCP進tool map；因secret缺失、runtime消失或timeout而失敗的項標為transient `applied_but_unavailable`，不進本次realized universe。其餘MCP與local tools仍建圖，active Skill重新resolve；required family不在realized universe時不自動啟用。`/status`同時顯示applied generation與realized差異，但startup不得偷偷改durable catalog或approval record。

## Tool access 與 prompt 動態化

### MCP exposure

把 `GLOBAL_MCP_FAMILY = "web_search"` 改成 catalog輸入：

```text
resolve_tool_access(
  manifest,
  all_tools,
  mcp_families=...,
  global_mcp_families=runtime_snapshot.global_mcp_families,
)
```

- local base tools仍為 global。
- Web Search compatibility descriptor宣告 global，保留既有行為。
- GitHub descriptor宣告 skill，保留既有行為。
- 新 MCP預設 skill-scoped；只有 trusted approval可進 global set。
- Skill manifest現有 `tools.required/optional.mcp_families` 可直接沿用，無需為每個新 family改 Python enum。

### Prompt 與 evaluator

`app/agent/session.py:73-95` 不應繼續硬寫只有 Web Search、GitHub。改成穩定的 generic policy + 每 turn從 runtime snapshot產生 capability/availability block，正常模式也能看到實際綁定工具，不宣稱尚未載入的 MCP。

`app/agent/tools/inventory.py:142-159` 的 frozen Web tool names要和 runtime discovery拆開：

- base local inventory繼續是單一事實來源。
- behavior evaluator接收當次 catalog/tool universe，或用 family metadata分類 dynamic MCP tools。
- 不用新增 MCP的實際 tool names去改 `WEB_BEHAVIOR_TOOL_NAMES` 才能通過評估。

`PolicyToolNode` 繼續作第二層執行防線，但 resolution、model binding、prompt rendering與 node enforcement都必須吃同一 generation snapshot。

## Slash command UX

建議第一版介面：

```text
/Extension-Management                 # scan → plan → 套用安全項；風險項互動確認
/Extension-Management --dry-run       # 只顯示 diff、diagnostics與需要的 approval
/Extension-Management status          # desired/applied generation、pending/quarantine
/Extension-Management --yes           # 非互動環境套用已可驗證且預先允許的計畫
```

`status`是host-only read path：仍先fresh-load／驗證private bundle以遵守入口完整性，但不啟動LLM、management graph或MCP probe，也不等待mutation reservation。stdin不是TTY且未給`--yes`時不得呼叫`input()`；完成scan後，把所有需要approval的項目保留pending並正常回報。Approval cancel也是正常、零mutation結果，不轉成CLI error。`--yes`只能批准plan中已標為batch-approvable、且descriptor/artifact/scan hashes仍完全相同的項目，hard block永遠不能跳過。

輸出至少包含：

```text
Extension reconcile generation 11 -> 12
  added:       skill:foo
  updated:     mcp:web-search
  removed:     skill:bar
  unchanged:   4
  quarantined: mcp:unknown-server (entrypoint ambiguous)
  active skill: bar -> none (bundle removed)
  runtime swap: committed
```

注意：`--yes` 不能越過缺 secret、unsupported transport或無法唯一辨識 entrypoint等 hard block；它只批准已完整呈現exact execution binding與global exposure、且被policy定義為可批次批准的項目。

## 具體檔案改動面

### 新增模組／檔案

| 檔案 | 責任 |
|---|---|
| `app/agent/extensions/models.py` | `ExtensionId`、bundle record、diff、typed `ManagementPlan`、runtime/report schema |
| `app/agent/extensions/paths.py` | canonical tool root、state root、containment與workspace identity |
| `app/agent/extensions/discovery.py` | strict scan、stable fingerprint、diagnostics；不直接執行任何 extension |
| `app/agent/extensions/registry.py` | applied generations、atomic persistence、last-known-good snapshots、audit redaction |
| `app/agent/extensions/builtins.py` | host-owned Skill/MCP descriptors、bundle resource path、tool ownership與lifecycle hooks |
| `app/agent/extensions/mcp_manifest.py` | strict MCP schema、env reference、transport與argv resolver |
| `app/agent/extensions/validation.py` | duplicate、collision、reserved name、size、symlink、secret與exposure policy |
| `app/agent/extensions/reconciler.py` | diff → staging → validate → candidate → commit/rollback transaction |
| `app/agent/extensions/runtime.py` | `ExtensionRuntimeSnapshot`／`SessionRuntimeState`建置、public transaction與retired lifecycle |
| `app/agent/extensions/manager_agent.py` | fresh private Skill loader、全新minimal graph、structured proposal；不接主 tools也不暴露apply |
| `app/agent/cli/extension_management.py` | slash args、approval UI、report rendering與 error translation |
| `app/tool/_internal/extension-management/SKILL.md` | add/update/delete決策、相容性與blocked條件；每次命令強制讀 |
| `app/tool/local/README.md` | 明示 v1 local tools仍是host-owned，不宣稱drop-in |
| `app/tests/fake_mcp_server.py` | 真實 stdio MCP integration fixture，不只 monkeypatch adapter |
| `app/tests/test_extension_*.py` | discovery、registry、manager、transaction、security、CLI/E2E |

### 修改既有檔案

| 檔案 | 變更 |
|---|---|
| `app/agent/config.py` | 新增injectable writable `tool_root`、`extension_state_dir`、scan/size/probe timeout限制；shipped resources另由`importlib.resources`定位 |
| `app/agent/mcp.py` | 固定 resolver拆成 legacy compatibility provider + declarative spec loader；structured transport、safe log name、collision guard |
| `app/agent/skills/metadata.py` | 支援 catalog provider/public visibility；保留簡單 reader但不再把 catch-all skip當管理 diff |
| `app/agent/skills/runtime.py` | 從 catalog record載入 applied snapshot；internal loader與public loader完全分離；修正 task mode空集合仍接受任意值的邊角 |
| `app/agent/tool_access.py` | global MCP families由 runtime snapshot傳入，不再只有常數 `web_search` |
| `app/agent/tools/inventory.py` | base tools維持靜態；behavior分類改接 dynamic MCP metadata |
| `app/agent/graph.py` | build前完整duplicate fail-fast；明確接收單一 runtime tool catalog |
| `app/agent/session.py` | 持有單一runtime state、public async transaction API、active Skill transition、dynamic prompt、startup applied/realized狀態 |
| `app/agent/fusion.py` | runtime generation變更時 invalidation；不得繼續使用捕獲舊 universe的cache |
| `app/agent/cli/slash_commands.py` | 註冊 Extension-Management並把handler委派到獨立模組 |
| `app/agent/cli/chat.py` | 建manager依賴；維持command本地執行，不走`followup_input`；non-TTY approval policy |
| `app/pyproject.toml` | include host-owned `tool/**/*.md|yaml|json` resources；wheel smoke驗證read-only private/built-in資源與writable user root分離 |
| `README.md`、`guide.md`、`app/SKILLS_GUIDE.md` | 新目錄、drag-and-reconcile、manifest、approval、刪除/rollback與local限制 |

因中央根位於 `app/` 下，`app/agent/ingest.py` 現有 host-project exclusion已涵蓋，不需再為 root `tool/` 增加RAG排除；仍應新增測試鎖定這個假設。

## 分階段落地順序

每一階段獨立 commit、相關測試全綠；先建立 deterministic substrate，最後才讓 agent有 mutation入口。

### Commit 1 — `test(extensions): lock current tool, skill, MCP and slash invariants`

- 補 tool-name collision、public/internal保留名、`--no-mcp`、active Skill transition與 slash local-routing characterization tests。
- 保留目前 MCP/Skill行為，尚不新增入口。
- 記錄目前相關測試基準；已探查的 MCP/tool-access/graph/CLI組合現為 `63 passed`。

### Commit 2 — `feat(extensions): add strict bundle discovery and immutable catalog models`

- 新增 `models.py`、`paths.py`、`discovery.py`、strict diagnostics與fingerprint。
- 新增 `AgentConfig.tool_root`；建立 `app/tool/{mcp,skill,local,_internal}`。
- 掃描完全 side-effect free；malformed/unstable/duplicate與delete有不同結果。
- 測試 symlink、casefold、folder/frontmatter mismatch、oversize、copy中變更與 reserved names。

### Commit 3 — `feat(extensions): persist applied generations and last-known-good snapshots`

- 新增 atomic registry、managed staging/snapshot、audit redaction與crash recovery。
- 實作 add/update/delete diff與 no-op fast path。
- invalid update保留舊 snapshot；存在但壞掉不判 delete。
- 此階段仍不接主 session。

### Commit 4 — `refactor(session): add immutable runtime state and one commit primitive`

- 引入`ExtensionRuntimeSnapshot`與`SessionRuntimeState`，先包住現有static Skill/MCP/tools行為。
- 新增public `session.runtime_transaction()`；turn、`/skill`、`/citation`與未來reconcile共用，禁止外部直接碰private lock。
- durable generation先prepare+fsync，lock內current-pointer commit後只做no-fail state assignment；citation teardown延到commit確定後。
- 完整tool catalog納入base、MCP、`citation_workflow`等host-owned skill tools與owner/scope；Fusion cache可按generation invalidation。

### Commit 5 — `feat(skills): reconcile public drop-in skills without restarting the session`

- 建`BuiltInSkillDescriptorProvider` + `DropInExtensionProvider`合併catalog，drop-in不得覆寫built-in。
- `/skill`改讀current runtime catalog，不再讀constructor cache；所有activation/deactivation走Commit 4 transaction API。
- active prompt-only Skill可fresh reload；delete、invalid update、task mode消失與global tool重新resolution政策落地。
- private root不進public discovery；direct `/skill extension-management`拒絕。
- 保留`app/skills/citation` imports、專用`/citation`與bundle行為。

### Commit 6 — `feat(mcp): reconcile declarative MCP bundles into runtime generations`

- MCP schema、env refs、minimal child env、safe argv/cwd、分離timeouts、execution trust與bounded diagnostics。
- 將Web Search/GitHub固定resolver包成pre-trusted host descriptors；GitHub token保持optional，legacy external path與Web stdout sanitizer明確隔離。
- item quarantine/LKG與generation abort分層；tool/family collision在final candidate graph之前fail。
- phase 1只啟用stdio；用含stdout noise、timeout與cancellation的真實fake MCP subprocess測protocol與no-orphan cleanup。
- startup實作applied-vs-realized degraded policy，`--no-mcp`不probe。

### Commit 7 — `feat(extension-management): add private-skill management agent and reconciler`

- 建exact-path fresh private loader與全新history-free minimal graph，不重用main `build_graph()`。
- Host先產authoritative diff；agent只對raw MCP無descriptor補typed candidate fields與逐op摘要，bundle內容明確標為untrusted input。
- Agent輸出通過Pydantic、exact coverage與policy validator後，由host取得approval再直接呼叫reconciler；mutation API不綁給模型。
- management read-only tools從主graph完全不可見；測惡意public Skill偽造要求。

### Commit 8 — `feat(cli): add /Extension-Management dry-run, apply and status flows`

- 在default registry註冊命令；利用既有casefold支援指定大小寫。
- handler直接await manager，不用followup；所有預期錯誤轉`SlashCommandError`，CLI loop不中止。
- 實作approval、`--dry-run`、`status`、`--yes`與逐項報告。
- completion/help/status同步。

### Commit 9 — `refactor(tools): move public bundle assets under app/tool with compatibility shims`

- 先建立host-owned ID→resource path descriptors，再在同一commit把`academic-paper-writing` descriptor與bundle切到shipped `app/tool/skill/`；不能讓它短暫變成可覆寫drop-in。
- 把citation的`SKILL.md`/`manifest.yaml`與Python engine分離；host descriptor原子改指新bundle resource，engine import暫留`skills.citation`、tool owner/lifecycle hook不變。
- `_prompt-master`是否搬到 `app/tool/_internal/prompt-master` 另做明確相容決策，不和management private semantics混在一起。
- 切換同時移除舊resource provider，保留可回退descriptor；更新Poetry includes、wheel contents與路徑測試，舊`skills_dir`保留一個deprecation週期。

### Commit 10 — `docs(extensions): document controlled hot-plug, trust and recovery`

- README/guide改掉「新增/修改/刪除 Skill只能重啟」的舊說明。
- `SKILLS_GUIDE.md`分清Agent Skills標準、host manifest與code-backed built-in Skill。
- MCP文件從Web/GitHub專用env表改為descriptor + env reference，另列legacy相容期。
- 寫清楚Local Tool不在v1 hot plug範圍、MCP等同第三方code execution、approval與rollback方式。

## 測試矩陣

### Discovery／registry

- 空目錄、首次建立、no-op重掃。
- add/update/delete/rename與多項混合diff。
- invalid add、invalid update保留last-known-good。
- malformed path存在時不判delete；兩次hash不穩定時不apply。
- duplicate ID、casefold collision、reserved name、symlink/path escape、special file、容量上限。
- authoritative diff coverage：模型漏掉／新增／改kind或hash的op必須整包拒絕。
- registry atomic write失敗、staging殘留、checksum壞、前一generation recovery與GC；trust/artifact/tool-surface hashes round-trip。
- `local/`除README外內容回`unsupported`，不進diff或runtime。

### Skill

- CLI啟動後才drop Skill；reconcile後同session `/skill` picker與`/skill <name>`可見。
- 修改inactive Skill後啟用讀到新內容。
- 修改active Skill後reconcile，下一turn讀到新instructions/pinned refs。
- active Skill valid→invalid update保留舊runtime。
- 刪除inactive／active Skill的不同結果。
- private management Skill不在picker，名稱直載也拒絕。
- 每次management invocation確實重新讀private `SKILL.md`；連續改兩次hash與行為都更新。
- private bundle出現額外reference/script或在agent執行中被替換時fail closed/rescan。
- bundle內prompt injection不能改manager policy；vendor-only語法只產生warning。
- manifest所有resources（含non-pinned）不存在、非regular或escape snapshot時拒絕。
- active Skill新版移除current task mode時套用bundle並deactivate；global MCP變更時即使Skill內容不變也重算access。

### MCP

- descriptor schema、relative command/cwd、env reference、missing secret、literal secret拒絕。
- Web Search legacy global、GitHub legacy skill-scoped回歸。
- 新 MCP預設skill-scoped；未批准global升權拒絕。
- 新／變更MCP在首次probe前要求綁descriptor+artifact+argv+cwd+env-name+exposure hashes的approval；hash變更使舊approval失效。
- 真實fake stdio server add後可被綁定與呼叫。
- update後新tool schema生效、舊tool不再綁定。
- delete後model binding、PolicyToolNode、status/family map都不再含舊tool。
- failing server與valid server混合時的policy：invalid項quarantine，完整candidate catalog仍一致。
- 跨MCP同名、MCP/local同名、MCP/management同名全部fail-fast。
- family單一owner與exposure一致；跨extension重用family拒絕。
- command injection字元不經shell展開；minimal child env不帶runtime控制變數；log filename不能path traverse。
- fake server stdout noise由host sanitizer隔離；probe/tool-call timeout分開，取消或delete後無orphan process。
- tool數量、名稱、description、input schema與result size超限都quarantine。
- `--no-mcp` 下scan/status可用，但不probe、不啟動、不綁定。
- startup單一applied MCP無法realize時CLI仍啟動，status顯示`applied_but_unavailable`且durable generation不變。

### Session／transaction

- candidate graph build失敗保持舊graph/tools/families/prompt/generation。
- durable current-pointer commit失敗時in-memory state、citation service與SourceRefs從未改變。
- turn、`/skill`、`/citation`與reload並發不交錯；stale generation/active Skill觸發retry或abort，鎖順序無反轉。
- active Skill required family刪除會deactivate；optional family刪除會degrade並更新prompt。
- 過渡／搬移前後`/skill citation`與專用`/citation` activation/off都維持；每次graph generation重建後`citation_workflow`仍只在citation active時bound/callable。
- unrelated reconcile不清除active citation的service/SourceRefs；只有committed deactivation走完整teardown，failed commit完整保留。
- normal與extended mode都不使用舊generation；Fusion cache正確invalidated。
- forged old-generation tool call被新`PolicyToolNode`拒絕。

### CLI／agent isolation

- parser、help、completion同時接受canonical與指定大小寫。
- command不呼叫普通 `session.turn()`，也不寫入一般chat turn/history。
- private Skill缺失/損壞時fail closed。
- manager使用新minimal builder且只綁read-only/pure管理工具；沒有apply tool，主graph也列不到它們。
- dry-run零mutation；status fresh-load private bundle但不跑LLM/probe且不受busy reconcile阻塞；approval cancel零mutation。
- non-TTY未給`--yes`時不呼叫input、approval項保留pending；`--yes`只接受hash未變的batch-approvable項，不跨hard block。
- change report逐項誠實呈現partial applied/quarantined/deactivated/rollback。

### Packaging／文件

- source checkout可用`app/tool/`單一視圖；built wheel以`importlib.resources`定位read-only built-in/private bundle，writable drop-ins落user-data root。
- built wheel中`import skills.citation`成功，descriptor也能找到搬移後citation bundle。
- `python -m agent.cli.chat --no-mcp` smoke。
- `python -m agent.cli.chat` + legacy Web Search/GitHub smoke。
- `/init` ingest結果不含`app/tool/`。
- README、guide、SKILLS_GUIDE與runtime schema assertion一致，不再保留legacy `capabilities/tool_policy`範例。

## 完成驗收標準

以下全部成立才算完成，不以「scanner看得到資料夾」作為完成：

1. 啟動CLI後新增一個合法prompt-only Skill，執行 `/Extension-Management`，不重啟即可在 `/skill`看到並啟用。
2. 修改該Skill並再次執行命令，下一turn使用新內容；刪除後命令會卸載，若原本active則明確deactivate。
3. 新增一個有strict descriptor的fake MCP，命令後同session可用；更新tool surface與刪除也都不需重啟。
4. 壞掉的Skill/MCP update不會破壞last-known-good runtime，報告能指出blocked原因。
5. tools、families、active Skill、prompt、graph、status全部顯示同一generation，沒有殘留舊工具。
6. `/skill`永遠不列出或啟用Extension-Management Skill；management command每次fresh read並記錄其hash。
7. public Skill無法取得任何管理mutation tool；下載內容不能未批准執行command或升為global。
8. `--no-mcp`、citation isolation、Web Search global、GitHub skill-scoped與既有tool policy回歸測試全綠。
9. 使用者完成支援格式的新增／修改／刪除不需要改任何host Python；無法自動適配的MCP會blocked並說明缺少什麼，不會自由猜測後執行。

## 主要風險與對應

| 風險 | 對應 |
|---|---|
| 「拖入 MCP」實際上等同執行第三方程式 | raw/applied分離、strict descriptor、staging、exact approval、bounded subprocess、secret env refs |
| LLM每次管理自由發揮 | private Skill fresh read + typed plan + deterministic validator/reconciler；LLM不直接mutate |
| in-place copy半完成 | stable fingerprint、staging snapshot、scan token、TOCTOU recheck |
| graph/tools/policy部分更新 | immutable runtime generation + build-before-swap + shared lock + rollback |
| active Skill指向已刪資源 | transaction內reload/deactivate，不留懸空runtime |
| tool name覆蓋造成權限錯配 | 全universe collision fail-fast，v1不做silent namespace rewrite |
| 物理集中造成citation import大爆炸 | 先central catalog與compatibility provider，再拆bundle assets與engine |
| public Skill要求管理工具 | management tools完全不進主graph，不只靠manifest policy拒絕 |
| startup自動執行剛下載MCP | startup只載applied registry；raw desired drift等slash reconcile |
| 文件與runtime再次漂移 | schema tests + docs examples parse tests + wheel/E2E gate |

## 建議實作邊界

第一個milestone應先做到「prompt-only Skill同session CRUD + declarative MCP同session CRUD + private manager隔離 + rollback」，不要把Local Tool動態import、任意repository自動build、所有transport與全目錄搬遷一起塞入。

這個切法已達成使用者核心目標：下載／拖入後不改程式即可啟用；同時把不穩定的模型判斷限制在plan層，把真正會改runtime的行為固定在可測、可回復的程式路徑。
