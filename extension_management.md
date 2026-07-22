# Extension Management 可控熱插拔改造計畫（實證審查修訂版）

日期：2026-07-22

狀態：待最終核准；本文件只規劃改動，尚未修改 production code

修訂依據：

- production 探查基準：`a8209a323350ad8af6f2d40d633d9eeb9b47fd6f`
- 原計畫 commit：`8ca86e38cdb5caf7198c34c2fed503318a448ea9`
- 本次修訂起點：`repair` HEAD `0092ca2e9061ca8c74400074a96283899433c5aa`
- 原計畫與 production 基準之間只有文件新增，沒有 production code 差異
- 本修訂納入 repository 實證審查、故障推演、官方 MCP／Python／LangGraph／packaging 資料與 build-vs-buy 結論

---

## 1. 決策摘要

本計畫仍要達成「同一個 `ChatSession` 內，經使用者明確觸發後，新增／修改／刪除支援格式的 Skill 與 MCP，不需修改 host Python，也不需重啟 CLI」的核心目標。

但第一版不再採用「LLM management agent 是每次 reconcile 的必要入口」與「disk current pointer 加 memory pointer 等於單一原子交易」這兩項假設。

修訂後的核心方向如下：

1. **正常管理路徑完全 deterministic。**
   - scan、schema validation、diff、approval lookup、snapshot、MCP probe、tool inventory、collision、graph build、durable commit、runtime swap 與 status 全由 host code 執行。
   - v1 不依賴 LLM 才能安裝或更新已有嚴格 descriptor 的 Skill／MCP。

2. **狀態明分四層，不宣稱 disk 與 memory 可同時原子。**
   - `desired`：使用者 drop-in tree 想要的內容。
   - `applied`：durable registry 已批准、可重建的 generation。
   - `realized`：目前 Python process 實際綁定的 generation。
   - `turn generation`：一個 in-flight turn 所固定使用的 realized generation。

3. **durable metadata 使用 SQLite transaction。**
   - 以 workspace-scoped SQLite database 保存 current generation、extension records、approval 與 audit metadata。
   - 使用 `BEGIN IMMEDIATE`、expected-generation compare-and-swap 與短交易，處理多個 CLI process 共用同一 state root 的 lost update。
   - content-addressed immutable snapshots 仍放 filesystem。

4. **使用者 drop-in、shipped private resources 與 runtime state 物理分離。**
   - shipped resources：read-only，透過 `importlib.resources` 取得。
   - user drop-in root：writable，只放使用者 bundle。
   - state root：writable，只放 SQLite、staging、immutable snapshots 與 bounded diagnostics。
   - private management prompt 不得位於 user-writable drop-in tree。

5. **drop-in bundle 必須有明確 completeness contract。**
   - v1 user drop-in bundle 必須包含 `.extension-lock.json`，列出所有其他 regular files 的 relative path、size 與 SHA-256。
   - scanner 必須驗證「列出的檔案全部存在且相符，沒有未列出的 regular file」。
   - 缺 lock、缺檔、額外檔、hash 不符、copy 中變動一律是 `unsealed`／`unstable`，不可 apply。
   - content hash 是識別與 TOCTOU 防線，不是假裝成來源簽章或 publisher trust。

6. **完整 tool identity 必須包含 owner。**
   - 不能再只以 tool name 當 identity。
   - 所有 local、MCP、host skill、management tools 在 build graph 前做全 universe collision fail-fast。
   - 不允許 first-wins、last-wins 或 silent namespace rewrite。

7. **MCP process lifecycle 是獨立基礎設施。**
   - drop-in MCP 不可沿用資料驅動的 `/bin/sh -c` 字串 pipeline。
   - 使用 direct argv、minimal env、bounded stdout/stderr、分離 initialize／tool-call timeout、cancel、terminate、kill、wait/reap 與 process-tree cleanup。
   - v1 只支援 strict declarative `stdio` MCP；不自動 build、install 或 fetch network dependencies。

8. **第一個可交付 milestone 是 prompt-only Skill 同 session CRUD。**
   - 先證明 roots、scanner、store、runtime pointer、active Skill transition、LKG 與 wheel packaging。
   - 第二 milestone 才加入 strict declarative stdio MCP CRUD。

9. **management agent 延後為 optional descriptor inference。**
   - 只在使用者明確要求分析「沒有 descriptor 的 MCP bundle」時產生候選 descriptor。
   - 只讀、無 mutation API、無 probe、無 apply。
   - 候選仍須 deterministic validation、exact approval 與後續 host-only apply。

建議實作決策：**依本修訂版執行，不依原 10-commit 順序直接開工。**

---

## 2. v1 目標與非目標

### 2.1 v1 必做

1. 支援 sealed prompt/resource-only Skill bundle：
   - add、update、delete；
   - reconcile 後同一 session picker與activation立即使用新 catalog；
   - active Skill 更新、刪除、invalid update與 task-mode 變更有明確政策。

2. 支援 sealed declarative stdio MCP bundle：
   - add、update、delete；
   - exact execution approval；
   - probe、tool surface inventory、collision與same-session graph swap；
   - failed update保留last-known-good。

3. 保留既有語義：
   - local base tools仍為global；
   - Web Search仍為global MCP family；
   - GitHub仍為skill-scoped MCP family；
   - `--no-mcp` 不probe、不啟動、不綁定MCP；
   - citation service與SourceRefs維持session isolation；
   - 單一MCP無法realize不拖垮CLI。

4. source checkout與built wheel都可用：
   - shipped resources從package讀；
   - user drop-ins落writable root；
   - state不寫進site-packages或source bundle。

5. 多process安全：
   - 同一workspace/state root同時只有一個durable generation commit成功；
   - stale process必須abort或重新prepare；
   - committed snapshot在v1不自動GC。

### 2.2 v1 明確不做

- 不動態 import／reload任意Python Local Tool。
- 不讓下載Skill直接註冊host tool factory。
- 不做background filesystem watcher。
- 不自動執行package manager、build script或network install。
- 不保證任意GitHub MCP repository可自動適配。
- 不支援HTTP／SSE／WebSocket MCP transport。
- 不做persistent MCP session pool或跨generation handle reference counting。
- 不做自動snapshot GC。
- 不在v1搬移citation Python engine或其bundle assets。
- 不引入pluggy、stevedore、resolvelib或watchfiles。
- 不讓`--yes`建立首次executable/global-exposure approval。
- 不讓LLM參與已有strict descriptor的正常CRUD。

### 2.3 phase 2 候選

- `/Extension-Management infer <mcp-id>` read-only descriptor inference agent。
- MCPB importer。
- explicit rollback command。
- process lease與safe snapshot GC。
- persistent MCP transports。
- installed Python plugin／entry-point模式。
- citation bundle asset migration。
- watcher/debounce。

---

## 3. 已確認的現行 repository 架構

下列為固定 production 基準可直接證實的現況，實作不得假設另一套架構。

```text
CLI startup
  └─ agent.cli.chat._run()
       ├─ ChatSession.create(load_mcp=not args.no_mcp)
       │    ├─ load_mcp_tools_with_families()
       │    │    └─ resolve_mcp_specs()
       │    │         ├─ _web_search_spec()
       │    │         └─ _github_spec()
       │    └─ ChatSession(...)
       │         ├─ loaded_skills = discover_skills(config)
       │         ├─ citation_workflow_tool = create_citation_workflow_tool(...)
       │         ├─ graph = build_graph(...)
       │         └─ FusionOrchestrator(...)
       └─ build_default_registry()
```

### 3.1 CLI與slash routing

- `SlashCommandRegistry`以`casefold()`做lookup。
- slash handler先在本地執行。
- 只有`SlashCommandResult.followup_input`非空時，CLI才把內容送入普通`session.turn()`。
- `/Extension-Management`不得使用`followup_input`。
- 現行`finally`只呼叫`flush_recent_turns()`；v1需新增idempotent `ChatSession.aclose()`。

### 3.2 Skill

- `discover_skills()`只掃單一`skills_dir/*/SKILL.md`。
- malformed Skill在discovery被log後跳過，沒有authoritative diagnostics。
- `ChatSession.loaded_skills`是constructor snapshot。
- picker優先讀`loaded_skills`。
- `load_skill_runtime()` activation時會重新discover並讀取Skill內容。
- active `SkillRuntime`不會自行更新。
- `_validate_task_mode()`目前在`task_modes: []`時仍可能接受任意傳入mode；必須先固定語義。

### 3.3 MCP

- discovery只認Web Search與GitHub兩個host resolver。
- `_spec_to_connection()`目前以`/bin/sh -c`與`grep`處理特定server的stdout noise。
- `load_mcp_tools_with_families()`逐server取得tools，沒有通用descriptor trust、owner identity或close handle。
- MCP只在`ChatSession.create()`載入一次。

### 3.4 Tool policy與graph

- `GLOBAL_MCP_FAMILY`目前固定為`web_search`。
- `build_graph()`在compile前固定：
  - tool objects；
  - `tools_by_name`；
  - model tool bindings；
  - binding cache；
  - `PolicyToolNode`。
- 改動`extra_tools`或family map不會改變已compile graph。
- 現行duplicate policy存在不一致：
  - MCP family map可能對同名tool後寫覆蓋；
  - base inventory又可能first-wins跳過同名extra tool；
  - 可能形成「執行A tool，按B family授權」。

### 3.5 Fusion

- proposer graph只綁固定read-only local allowlist。
- proposer建立時`extra_tools=None`，不含MCP或citation workflow。
- v1 extension generation變更不應無條件清除所有Fusion graph cache。
- 只有`GraphSignature`中的model、base local tool identity/schema或graph policy改變才invalidate。

### 3.6 Citation

- `app/skills/citation`同時是Skill bundle與`skills.citation` Python package。
- `ChatSession`直接import並建立`citation_workflow_tool`。
- citation service為session-scoped，離開citation active state時必須走完整teardown。
- failed runtime commit不得清除舊citation service或SourceRefs。

### 3.7 Packaging

- 目前Poetry package包含`agent`與`skills`。
- 新的user drop-in root、private management resource與state root尚不存在。
- `find_app_root()`依實體`pyproject.toml`定位source checkout，不可作為installed wheel resource locator。

---

## 4. 不可破壞的 invariants

### 4.1 狀態與交易

1. **一個turn只使用一個realized generation。**
2. **durable applied與process realized分開紀錄。**
3. **candidate未完整建好前不得改current applied或session runtime pointer。**
4. **durable commit失敗時memory完全不變。**
5. **durable commit成功但process在memory swap前終止時，startup可從applied重建realized。**
6. **同一state root的durable commit使用SQLite compare-and-swap。**
7. **任何process不得在持有SQLite write transaction時等待LLM、input、copy、probe、graph build或另一把session lock。**
8. **v1不刪除已committed snapshot。**

### 4.2 Source與trust

9. **raw drop-in永遠不直接成為runtime source。**
10. **unsealed／unstable／malformed bundle不得apply。**
11. **private shipped resource不在user-writable root。**
12. **content hash只代表內容identity，不代表publisher authenticity。**
13. **下載內容不得未批准執行MCP command或升為global exposure。**
14. **normal reconcile不執行LLM。**

### 4.3 Tool與權限

15. **tool identity包含owner，不能只靠name。**
16. **extension ID、Skill ID、family ID與tool name的collision在graph build前拒絕。**
17. **management mutation tools永遠不進public tool catalog或main graph。**
18. **drop-in Skill只能要求catalog明確標為`public_skill_requestable`的host tool。**
19. **`citation_workflow`只可由built-in citation Skill取得。**
20. **global exposure由host policy＋approval決定，bundle自我宣告不會直接升權。**
21. **model binding、prompt availability與`PolicyToolNode`必須來自同一realized snapshot。**

### 4.4 MCP lifecycle

22. **drop-in MCP禁止shell字串拼接。**
23. **probe與tool call都必須有timeout、bounded streams與cleanup。**
24. **timeout／cancel／delete／CLI shutdown後不得留下host已知orphan process。**
25. **`--no-mcp` session不得probe、start或bind MCP。**

### 4.5 Active Skill與citation

26. **active Skill刪除或失去required family時不得懸空。**
27. **invalid Skill update保留舊applied與舊active runtime。**
28. **valid新版移除current task mode時套用新版並明確deactivate，不自動改選其他mode。**
29. **只有committed deactivation才執行citation teardown。**

---

## 5. Physical roots與package resources

### 5.1 三個物理trust domain

```text
A. shipped resource root（read-only）
   importlib.resources.files("agent.resources.extensions")
   importlib.resources.files("skills")

B. user drop-in root（writable）
   <extension_root>/skill/<id>/
   <extension_root>/mcp/<id>/

C. state root（writable, local filesystem）
   <extension_state_dir>/registry.sqlite3
   <extension_state_dir>/staging/
   <extension_state_dir>/snapshots/<sha256>/
   <extension_state_dir>/diagnostics/
```

規則：

- source checkout預設`extension_root = <app>/tool`。
- installed wheel預設使用`platformdirs.user_data_dir(...)`下的`tool`。
- `extension_state_dir`預設使用`platformdirs.user_state_dir(...)`並按workspace identity分區。
- 明確config值永遠優先。
- state root必須是local filesystem；network filesystem在v1回`unsupported_state_filesystem`。
- shipped resource與user root不得解析成相同實體路徑。
- state root不得位於user drop-in root或shipped package tree內。

### 5.2 Source checkout目錄

```text
app/tool/
├── skill/
│   └── <id>/
│       ├── .extension-lock.json
│       ├── SKILL.md
│       ├── manifest.yaml          # optional
│       ├── references/            # optional
│       ├── assets/                # optional
│       └── scripts/               # optional, inert
└── mcp/
    └── <id>/
        ├── .extension-lock.json
        ├── extension.yaml
        └── runtime files
```

不再在user root建立：

- `_internal/extension-management`；
- `local/` placeholder；
- registry、audit或snapshot資料夾。

### 5.3 Shipped private／built-in resources

- v1 normal path不需要private management Skill。
- phase 2若加入inference agent，private prompt放在：

```text
app/agent/resources/extensions/private/extension-management/SKILL.md
```

並透過`importlib.resources`exact-path load。

- built-in Skill provider先指向現有`skills` package resources。
- citation與academic-paper-writing在v1不搬實體路徑。
- `_prompt-master`維持既有internal helper相容行為，與extension management private prompt分開。

---

## 6. Drop-in completeness與fingerprint contract

### 6.1 `.extension-lock.json`

user drop-in bundle必須包含：

```json
{
  "schema_version": 1,
  "kind": "skill",
  "id": "example-skill",
  "files": [
    {
      "path": "SKILL.md",
      "size": 1234,
      "sha256": "..."
    },
    {
      "path": "references/checklist.md",
      "size": 456,
      "sha256": "..."
    }
  ]
}
```

MCP bundle的`kind`為`mcp`，且inventory必須包含`extension.yaml`及實際會執行的bundle內artifact。

### 6.2 驗證規則

- lock file本身不可列入`files`。
- paths必須是canonical POSIX-style relative path。
- 拒絕absolute path、`..`、空segment、NUL、casefold duplicate。
- 只允許regular files與directories。
- 拒絕symlink、junction/reparse escape、device、FIFO、socket。
- 在可偵測平台拒絕`st_nlink > 1`的regular file。
- inventory列出的檔案必須全部存在、size與SHA-256相符。
- bundle中不得有inventory未列出的regular file。
- directory metadata、`.DS_Store`等是否允許必須由host固定規則決定，不由bundle自由排除。
- scan前後重新驗證lock hash與root inventory；不一致為`unstable_copy`。
- snapshot copy從已驗證的open file descriptor讀取，避免驗證後以path重新讀到另一個inode。
- snapshot完成後再驗證snapshot inventory與source hash。

### 6.3 支援與不支援的handoff

支援：

- 已封裝、已有lock的bundle直接放入final目錄；
- bundle producer先在root外完成，最後移入root；
- 更新時以完整新版目錄替換舊目錄。

不支援：

- 沒有lock的資料夾；
- 在final目錄中逐檔複製但尚未更新完整lock；
- scanner自行猜哪些檔案「應該已複製完」。

normal reconcile不得自動寫入或重建使用者lock file。

---

## 7. Data models

### 7.1 Extension identity

```text
ExtensionKey
  kind: skill | mcp
  id: canonical kebab-case
```

ID規則：

- regex：`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`
- 長度1–64。
- folder name、lock id與Skill frontmatter／MCP descriptor id必須完全相同。
- casefold後全workspace唯一。
- 保留：現有slash command、built-in Skill、MCP family、management tool與host保留名。

### 7.2 Tool identity

```text
ToolIdentity
  owner_kind: base | builtin_skill | mcp | management
  owner_id: str
  name: str
  family: str | None
  exposure: global | skill | private
  requestable_by_public_skill: bool
  description_hash: str
  input_schema_hash: str
  implementation_kind: local | mcp | management
```

規則：

- raw`name`與casefold name都必須唯一。
- 同family v1只能有一個MCP owner extension。
- management tools使用`private` exposure，且不進main catalog。
- `citation_workflow` owner為`builtin_skill:citation`，`requestable_by_public_skill=false`。

### 7.3 Durable與realized狀態

```text
DesiredInventory
  scan_token
  root_identity
  items[]
  diagnostics[]

AppliedGeneration
  generation
  parent_generation
  manifest_hash
  extensions[]
  created_at

ExtensionRuntimeSnapshot
  realized_generation
  applied_generation
  tool_catalog
  public_skill_catalog
  mcp_families
  global_mcp_families
  graph
  availability_block
  mcp_enabled
  realization_diagnostics
  graph_signature

SessionRuntimeState
  revision
  extensions: ExtensionRuntimeSnapshot
  active_skill_runtime
  active_skill_extension_generation
```

`AppliedGeneration`不保存secret value，只保存env var name、binding hash與sanitized metadata。

---

## 8. Durable store與immutable snapshots

### 8.1 SQLite schema方向

```text
meta
  schema_version
  workspace_id
  workspace_root_hash
  current_generation

applied_generations
  generation
  parent_generation
  manifest_hash
  status
  created_at

applied_extensions
  generation
  kind
  extension_id
  source_hash
  snapshot_hash
  normalized_descriptor_json
  tool_surface_hash
  approval_binding_hash
  status

approvals
  binding_hash
  scope
  extension_key
  approved_at
  approved_by

extension_events
  seq
  timestamp
  operation_id
  event_type
  generation
  extension_key
  sanitized_payload_json
```

SQLite database設定：

- schema migration必須explicit、transactional、可測。
- 使用foreign keys。
- 使用rollback journal或經測試確認的WAL策略；不得只依預設後假設跨平台行為。
- `busy_timeout=0`或極短；commit lock忙時fail-fast回`busy`，不得在session runtime lock內長等待。
- DB file permission盡可能為0600；Windows依ACL能力記錄diagnostic。

### 8.2 Snapshot store

- content-addressed path：`snapshots/<sha256>/`。
- 先寫`staging/<operation-id>/<sha256>.partial/`。
- fsync可fsync的files與parent directory。
- 最後寫完整`snapshot.json`，再same-filesystem publish。
- 若相同hash已存在，驗證後重用。
- committed generation只引用immutable snapshot hash，不引用raw source path作runtime輸入。
- v1不刪除任何committed snapshot。
- 只可清理未被DB引用且帶明確`.partial`標記的staging殘留。

### 8.3 Cross-process commit

所有process使用相同順序：

```text
process-local reconcile reservation
  -> session runtime lock
  -> SQLite BEGIN IMMEDIATE
```

禁止任何路徑以反方向取得鎖。

commit transaction內必須recheck：

- expected current generation；
- expected session revision；
- desired scan token／source hashes；
- approval binding hashes；
- private inference prompt hash（只有phase 2 inference結果）；
- candidate manifest hash。

stale或DB busy時：

- rollback SQLite；
- 不改memory；
- 釋放session lock；
- 回`stale`／`busy`，由caller決定重新prepare，不在鎖內自動重跑昂貴操作。

---

## 9. Skill bundle與catalog政策

### 9.1 Skill schema

沿用Agent Skills基本格式：

- `SKILL.md`必要；
- YAML frontmatter `name`、`description`必要於drop-in；
- optional `manifest.yaml`為本host擴充；
- references、assets、scripts是inert resources。

更嚴格規則：

- frontmatter name必須等於extension ID。
- UTF-8 strict decode；不得以replacement默默接受invalid bytes。
- `manifest.yaml`在discovery階段即驗證。
- manifest所有resource都必須存在、列入lock且落在snapshot內。
- scripts不自動執行。
- unknown vendor fields只可形成compatibility diagnostic，不能被當成本runtime支援。

### 9.2 Tool request policy

- local base tools維持global，不由Skill manifest增刪。
- drop-in Skill只能要求：
  - MCP family；
  - `requestable_by_public_skill=true`的host tool。
- drop-in Skill要求`citation_workflow`、management tool或其他private host tool時直接拒絕。
- required缺失：Skill不進candidate applied catalog。
- optional缺失：Skill可進catalog，但availability記錄missing optional。

### 9.3 Skill approval

- prompt-only Skill，沒有scripts、沒有額外MCP/host tool request：
  - reconcile可把它加入inert public catalog；
  -實際啟用仍只能由使用者明確`/skill`或專屬command完成。
- 新增／更新Skill若包含以下任一項，需顯示風險與exact hash：
  - scripts；
  - required/optional MCP family；
  - requestable host skill tool；
  - resources總量或prompt長度超過warning threshold。
- capability-bearing Skill的首次apply或capability set變更需要approval。
- approval綁定Skill source hash、normalized manifest hash與requested capability set。
- `--yes`只能重用完全相同的既有approval。

### 9.4 Active Skill transition

| Candidate變更 | Commit政策 |
|---|---|
| inactive Skill add/update | 更新catalog；不自動activate |
| active Skill內容更新且valid | 在同一runtime commit重新materialize |
| active Skill invalid update | 保留舊applied snapshot與舊runtime |
| active Skill被intentional delete | generation可commit，明確deactivate |
| 新版移除current task mode | 套用新版，明確deactivate |
| required MCP intentional delete | 套用delete並deactivate Skill |
| required MCP failed update | 保留舊MCP與依賴它的舊Skill closure |
| optional MCP失效／刪除 | Skill維持active，重算access與prompt |
| global MCP set改變 | 所有active Skill重算tool access |
| citation離開active | DB與memory commit成功後才teardown |

---

## 10. MCP descriptor與process supervisor

### 10.1 v1 normalized descriptor

```yaml
schema_version: 1
kind: mcp
id: github-example
version: 1.0.0
family: github-example
requested_exposure: skill

runtime:
  transport: stdio
  command: ./bin/server
  args: [stdio]
  cwd: .
  init_timeout_seconds: 20
  tool_call_timeout_seconds: 60

compatibility:
  platforms: [linux, windows]

environment:
  TOKEN:
    from_env: EXAMPLE_TOKEN
    required: true
```

### 10.2 Descriptor規則

- v1只接受`transport: stdio`。
- drop-in command必須是snapshot內relative executable，或allowlisted interpreter加snapshot內relative script/module。
- `args`只能是string array，禁止shell fragment。
- `cwd`必須落在snapshot內。
- absolute executable只允許host-owned legacy compatibility descriptor，不開放給drop-in。
- literal secret拒絕；secret只可`from_env`。
- child env由host minimal platform baseline加explicit env references建立，不繼承完整`os.environ`。
- `PYTHONPATH`、`LD_PRELOAD`、`NODE_OPTIONS`及同類runtime-control變數預設拒絕。
- descriptor必須宣告platform；不相容時回`unsupported_platform`，不可probe。
- v1不執行install/build/network fetch。

### 10.3 Exact approval binding

首次probe前必須有approval，binding至少包含：

```text
extension key
source hash
snapshot hash
normalized descriptor hash
artifact hash
command + args
cwd
referenced env names
requested exposure
tool surface limits policy version
```

- descriptor、artifact、argv、cwd、env-name set或exposure任一變更使舊approval失效。
- global exposure需要獨立scope。
- `--yes`不能建立首次approval，只能重用exact existing approval。
- `--no-mcp`下即使已有approval也不probe、不start、不bind。

### 10.4 MCPProcessSupervisor

建立host-owned supervisor，不把process ownership散落在scanner、reconciler或graph。

責任：

- direct `create_subprocess_exec`／官方MCP SDK stdio primitive；
- platform-specific process containment；
- bounded stdout/stderr reader；
- initialize timeout；
- list-tools timeout；
- tool-call timeout；
- cancellation；
- terminate → bounded grace → kill → wait/reap；
- POSIX process group；
- Windows Job Object或等價kill-tree adapter；
- sanitized bounded diagnostics；
- idempotent close。

v1 adapter策略：

- probe建立短生命週期session，完成後一定close。
- LangChain tool adapter預設每次tool invocation建立短session。
- turn lock保證runtime swap只在沒有本process in-flight turn時發生。
- 因此v1不建立per-generation persistent MCP handle reference count。

### 10.5 Legacy Web Search／GitHub

- 以host compatibility descriptors保留現有env與exposure語義。
- Web Search：global。
- GitHub：skill-scoped，token缺失維持現有warning/degraded語義。
- 現有shell＋grep只可作為暫時、host-owned、Linux-only legacy adapter；drop-in descriptor永遠不可選用。
- 優先以host-owned direct subprocess sanitizer替換，不把generic `stdout_policy`暴露給untrusted bundle。

### 10.6 Tool surface validation

probe後檢查：

- tool數量上限；
- name格式、長度與casefold collision；
- description長度與terminal control characters；
- serialized input schema大小／深度；
- result大小限制；
- owner/family/exposure一致；
- MCP/local/builtin/management全universe collision。

任何collision或超限使該MCP candidate失敗；failed update保留LKG。

---

## 11. Runtime與LangGraph切換

### 11.1 Unified session lock

將現有`_turn_execution_lock`收斂為public行為明確、private實作的runtime execution lock。

以下都必須走同一把lock：

- `turn_outcome()`完整turn；
- `/skill` activate/deactivate；
- `/citation` activate/deactivate；
- extension runtime commit；
- 其他會改active Skill或tool universe的session操作。

準備工作全部在lock外：

- scan；
- snapshot copy；
- validation；
- input／approval；
- MCP probe；
- graph build；
- active runtime candidate materialization。

commit window內不得有LLM、network、subprocess、長copy或互動input。

### 11.2 Candidate graph

以單一`ToolCatalog`建置：

- base local tools；
- realized MCP tools；
- host-owned skill tools；
- owner/family/exposure metadata；
- public Skill catalog；
- global family set。

build順序：

1. final tool identity/collision validation；
2. resolve normal-mode access；
3. resolve active Skill access；
4. build model bindings；
5. build `PolicyToolNode`；
6. compile graph；
7. renderdynamic availability block；
8. compute graph signature。

任何步驟失敗時不進commit。

### 11.3 Fusion cache

- extension generation不是Fusion proposer graph cache key。
- `GraphSignature`只包含真正被proposer graph捕獲的依賴：
  - model ID/config；
  - read-only base tool identity/schema；
  - proposer allowlist；
  - graph policy version。
- Skill文字、MCP catalog與active Skill改變通常只改prompt/state，不重建proposer graph。

### 11.4 Commit protocol

```text
1. 取得process-local reconcile reservation。
2. 讀desired inventory、applied generation、session revision。
3. 建stable snapshots與authoritative diff。
4. deterministic validate與dependency closure。
5. 取得／重用exact approvals。
6. probe MCP並建立candidate tool catalog。
7. build candidate graph與active Skill candidate。
8. 再驗證source lock/hash與candidate manifest。
9. 取得session runtime lock；等待既有turn完成。
10. 確認session revision／active Skill／task mode未變。
11. SQLite BEGIN IMMEDIATE，fail-fast。
12. recheck current applied generation與all hashes。
13. insert complete generation、extension rows、audit event並更新current。
14. COMMIT SQLite。
15. 在無await、cancellation-shielded區段做單一SessionRuntimeState pointer assignment。
16. commit成功後執行必要citation teardown。
17. 釋放session lock與operation reservation。
18. 回傳applied generation與realized generation。
```

如果process在步驟14與15之間終止：

- durable applied已成功；
-該process尚未realize；
-下次startup從applied重建；
-其他process不假裝該process已切換。

這是crash-consistent protocol，不稱為disk＋memory單一原子交易。

---

## 12. Dependency closure與partial apply

不能只按單一extension item決定partial apply。

建立candidate dependency graph：

```text
Skill -> required MCP families
Skill -> optional MCP families
Built-in Skill -> private host tools
MCP family -> one owner MCP extension
```

規則：

- 對每個connected required-dependency closure決定：
  - all-new；
  - all-old LKG；
  - intentional delete＋dependent deactivate；
  - blocked/quarantined。
- failed MCP update不能讓依賴它的Skill切到只相容新版的bundle。
- intentional MCP delete與failed update不同：
  - delete可套用並deactivate dependent Skill；
  - failed update保留舊MCP與舊dependent Skill closure。
- optional edge不阻止Skill applied，但必須重算realized access與prompt。

---

## 13. Startup realization與recovery

### 13.1 Startup流程

```text
1. 開啟／migrate registry.sqlite3。
2. 讀current applied generation。
3. 驗證generation manifest與snapshot checksums。
4. 若current artifact損壞，尋找最近可完整驗證的前代作realized fallback；不偷偷改current。
5. 依session --no-mcp policy逐項realize MCP。
6. 單一MCP因secret、runtime、platform或timeout失敗：
   - 標applied_but_unavailable；
   - 不進realized tool catalog；
   - 其他MCP與local tools繼續。
7. build realized graph。
8. session從inactive Skill開始；不自動恢復active Skill。
```

status必須同時顯示：

- desired scan token／drift；
- current applied generation；
- process realized generation；
- applied但unavailable項目；
- fallback reason；
- pending approval／invalid update。

### 13.2 Crash residue

- `.partial` staging不進runtime。
- SQLite transaction rollback處理未完成metadata commit。
- startup可清理明確未被DB引用的staging partial。
- 不自動刪除committed snapshots。

---

## 14. `/Extension-Management` CLI UX

### 14.1 v1 commands

```text
/Extension-Management
/Extension-Management --dry-run
/Extension-Management status
/Extension-Management apply
/Extension-Management apply --yes
```

語義：

- 無參數：scan、顯示diff；TTY下可互動取得新approval並apply；non-TTY不讀input。
- `--dry-run`：scan、validate、dependency analysis，不建新approval、不probe、不commit。
- `status`：host-only read path；不需private Skill、不跑LLM、不probe。
- `apply`：套用可完整驗證的candidate；風險項無approval則pending。
- `apply --yes`：只重用existing exact approvals；不能建立首次MCP execution、global exposure或capability-bearing Skill approval。

### 14.2 Non-TTY

- stdin非TTY時不得呼叫`input()`。
- 未有exact approval的項目保留`pending_approval`。
- approval cancel是正常零mutation outcome，不轉成CLI fatal error。
- `--no-mcp`下：
  - status/scan可見MCP desired/applied；
  - 不probe、不start、不bind；
  - 新／更新MCP不能進applied generation，維持pending；
  - Skill-only安全變更仍可commit。

### 14.3 Result model

預期失敗使用typed report，不以exception控制正常流程：

```text
ExtensionReconcileReport
  operation_id
  desired_scan_token
  applied_before
  applied_after
  realized_before
  realized_after
  items[]
  active_skill_transition
  runtime_swap_status
  diagnostics[]
```

item outcome至少包含：

- `applied`
- `unchanged`
- `pending_approval`
- `unsealed`
- `invalid`
- `quarantined`
- `kept_last_known_good`
- `removed`
- `deactivated_dependency`
- `unsupported`
- `busy`
- `stale`

只有parser bug、DB corruption無可fallback、programming invariant breach等非預期錯誤才轉`SlashCommandError`或internal error。

### 14.4 Help與completion

- canonical command為`extension-management`。
- registry既有casefold行為使`/Extension-Management`可命中。
- help/completion由同一registry產生。
- command不寫入普通chat history、不呼叫`session.turn()`。

---

## 15. Optional management inference agent（phase 2，非v1 gate）

### 15.1 唯一用途

處理沒有`extension.yaml`的MCP bundle，提出候選descriptor。

不處理：

- 已有strict descriptor的CRUD；
- Skill CRUD；
- status；
- approval；
- probe；
- apply；
- rollback。

### 15.2 Isolation

- private prompt從read-onlypackage resource exact-path讀取。
- dedicated history-free graph。
- 不帶main session history、active Skill、RAG、bash、read_file、citation或任何MCP。
- 只綁bounded read-only tools：
  - 取得authoritative untrusted metadata摘要；
  - 讀取allowlisted小型text metadata；
  - pure schema check。
- apply API永遠不作model tool。

### 15.3 Trust語義

- private prompt hash只記錄「使用了哪份提示」，不是security authority。
- security invariants全部在host validator。
- hostile README、SKILL.md、package metadata一律標為untrusted data。
- agent只可輸出有限typed candidate；不得新增authoritative operation。
- candidate無法唯一決定entrypoint時回blocked，不猜command。

---

## 16. 模組邊界與檔案改動面

避免把v1拆成過多相互循環的小模組。建議dependency方向：

```text
models
  ├─ paths
  ├─ discovery
  ├─ store
  ├─ tool_catalog
  └─ mcp_runtime
          
models + discovery + store + tool_catalog + mcp_runtime
  └─ runtime_builder
       └─ reconciler
            └─ CLI
```

任何底層模組不得import CLI或`ChatSession`。

### 16.1 新增

| 檔案 | 責任 |
|---|---|
| `app/agent/extensions/models.py` | IDs、inventory、diff、generation、report、typed outcomes |
| `app/agent/extensions/paths.py` | shipped/user/state roots、workspace identity、platform paths |
| `app/agent/extensions/discovery.py` | lock validation、safe scan、snapshot copy、diagnostics |
| `app/agent/extensions/store.py` | SQLite schema/migration/CAS、snapshot references、audit metadata |
| `app/agent/extensions/tool_catalog.py` | owner-aware tool identity、collision、family/exposure policy |
| `app/agent/extensions/runtime.py` | immutable realized snapshot、candidate graph builder、session state transition helpers |
| `app/agent/extensions/reconciler.py` | deterministic prepare、dependency closure、approval、commit protocol |
| `app/agent/extensions/mcp_runtime.py` | descriptor schema、approval binding、process supervisor、probe/tool adapter |
| `app/agent/cli/extension_management.py` | slash args、TTY policy、approval UI、report rendering |
| `app/agent/resources/extensions/__init__.py` | package resource root |
| `app/tests/fake_mcp_server.py` | 真實stdio fixture：normal/hang/noise/flood/child/cancel |
| `app/tests/test_extension_*.py` | discovery/store/runtime/MCP/security/CLI/E2E |

phase 2才新增：

- `app/agent/extensions/manager_agent.py`
- `app/agent/resources/extensions/private/extension-management/SKILL.md`

### 16.2 修改

| 檔案 | 變更 |
|---|---|
| `app/agent/config.py` | `extension_root`、`extension_state_dir`、limits、timeouts、platformdirs defaults |
| `app/agent/mcp.py` | 收斂為legacy compatibility provider；新drop-in走`extensions.mcp_runtime` |
| `app/agent/skills/metadata.py` | public catalog provider；保留簡單built-in reader，不再作authoritative manager scan |
| `app/agent/skills/runtime.py` | 從applied snapshot載入；固定empty task-mode語義；public/private loader分離 |
| `app/agent/tool_access.py` | 接受catalog global families與owner/requestable policy |
| `app/agent/tools/inventory.py` | base tools不變；移除silent duplicate；behavior metadata接dynamic catalog |
| `app/agent/graph.py` | 接收完整ToolCatalog；build前全collision fail-fast |
| `app/agent/policy_tool_node.py` | 以同snapshot effective identities執行防線，保留name protocol compatibility |
| `app/agent/session.py` | 單一runtime state pointer、unified async mutation API、`aclose()`、startup realization |
| `app/agent/fusion.py` | `GraphSignature`精準cache invalidation，不以extension generation清全cache |
| `app/agent/cli/slash_commands.py` | 註冊command、handler delegation、async Skill/citation mutation |
| `app/agent/cli/chat.py` | 建manager依賴、finally呼叫`session.aclose()`、維持local routing |
| `app/pyproject.toml` | 直接pin `mcp>=1.27,<2`；加入platformdirs；include package resources |
| `README.md`、`guide.md`、`app/SKILLS_GUIDE.md` | sealed bundle、desired/applied/realized、approval、限制與recovery |

### 16.3 v1不修改實體位置

- `app/skills/citation` Python engine與bundle。
- `app/skills/academic-paper-writing`。
- `app/skills/_prompt-master`。

由built-in provider使用`importlib.resources.files("skills")`取得。

---

## 17. 修訂後實作順序

每個commit都必須保持完整現有suite全綠，不能只跑新增tests。

### Commit 1 — `test/security: pin current runtime invariants and reject tool collisions`

內容：

- 記錄可重現baseline：Python版本、Poetry lock hash、完整pytest command、collected count與結果。
- 新增MCP/MCP、MCP/local、MCP/builtin skill同名collision tests。
- 移除現行silent first-wins／family last-wins行為，先fail-fast。
- characterization：Web Search global、GitHub skill-scoped、citation isolation、`--no-mcp`、slash local routing。
- 修正／固定`task_modes: []`語義。
- `pyproject.toml`直接pin `mcp>=1.27,<2`。

Gate：

- duplicate不可能進graph；
-所有現有行為測試全綠；
- CI產出完整baseline artifact。

### Commit 2 — `feat/extensions: add trust-separated roots and versioned models`

內容：

- 新增`models.py`、`paths.py`。
- shipped/user/state roots分離。
- `importlib.resources` provider。
- platformdirs defaults與config overrides。
- ID、lock file、Skill/MCP descriptor Pydantic models。
- package resource與wheel最小smoke。

Gate：

- source checkout與built wheel可讀shipped resources；
- user/state root可寫且不落site-packages；
- roots不能alias。

### Commit 3 — `feat/extensions: add sealed deterministic discovery and immutable snapshots`

內容：

- `.extension-lock.json` verification。
- safe file traversal／no-follow／reparse/special-file checks。
- sealed/unstable/unsealed/invalid diagnostics。
- content-addressed staging與snapshot publish。
- scanner完全不執行extension code。

Gate：

- 語法有效的半完成copy仍因lock不完整被拒絕；
- extra/missing/hash mismatch、symlink、hardlink、casefold與oversize測試全綠。

### Commit 4 — `feat/extensions: add SQLite applied generations and cross-process CAS`

內容：

- SQLite schema、migration、approval與event metadata。
- expected-generation `BEGIN IMMEDIATE` commit。
- snapshot references與startup current read。
- crash residue recovery。
- 不做committed snapshot GC。

Gate：

- 兩個subprocess同時commit只有一個成功；
- stale process不覆蓋current；
- transaction fault injection不留半套metadata。

### Commit 5 — `refactor/session: introduce immutable realized runtime and unified mutation lock`

內容：

- `ExtensionRuntimeSnapshot`／`SessionRuntimeState`。
- 將現有static tools/skills/MCP包入generation 0 compatibility snapshot。
- turn、`/skill`、`/citation`走同一async mutation lock。
- candidate graph build與no-await pointer assignment。
- `ChatSession.aclose()`。
- Fusion改用`GraphSignature`。

Gate：

- 一個turn只見一個generation；
- reconcile commit等待turn結束；
- failed candidate build不改任何session field；
- failed durable commit不teardown citation。

### Commit 6 — `feat(skills: reconcile sealed prompt-only skills in the same session`

內容：

- built-in＋applied drop-in public Skill catalog。
- `/skill` picker改讀current runtime catalog。
- prompt-only Skill add/update/delete。
- active Skill transition與dependency-free LKG。
- private roots不進public catalog。
- 加入最小deterministic `/Extension-Management`與`--dry-run` Skill流程。

Gate：第一個可交付milestone。

- CLI啟動後加入sealed Skill；同session reconcile後picker可見。
- active update下一turn使用新內容。
- invalid update保留舊runtime。
- delete active Skill明確deactivate。
- built wheel同樣通過。

### Commit 7 — `feat/mcp: add bounded stdio process supervisor`

內容：

- direct argv／minimal env。
- official MCP SDK client session adapter。
- bounded stdout/stderr。
- initialize/list-tools/tool-call timeout。
- cancellation、terminate/kill/wait、POSIX group／Windows job adapter。
- 真實fake server fixtures。
- legacy Web/GitHub compatibility adapter isolation。

Gate：

- hang、noise、flood、ignore-terminate、spawn-child、cancel、delete、shutdown全部無known orphan。
- untrusted descriptor永不經shell。

### Commit 8 — `feat/mcp: reconcile strict declarative MCP bundles and exact approvals`

內容：

- strict `extension.yaml` normalization。
- exact approval bindings。
- tool surface validation與owner-aware catalog。
- Skill→MCP dependency closure。
- startup applied-vs-realized degraded policy。
- `--no-mcp` no-probe/no-bind。

Gate：第二個可交付milestone。

- strict fake MCP same-session add/update/delete。
- failed update保留LKG與dependent Skill closure。
- global exposure無獨立approval時拒絕。
- collision與oversize fail-fast。

### Commit 9 — `feat/cli: complete status, non-TTY approval and recovery UX`

內容：

- `status`、`apply`、`--yes`、完整report。
- non-TTY不讀input。
- cancel零mutation。
- help/completion/casefold。
- startup fallback與applied/realized drift輸出。
- package/wheel/full CLI E2E。

Gate：

- TTY/non-TTY × yes/cancel/no-mcp矩陣全綠。
- command不進ordinary turn/history。
- status在任何private inference resource缺失時仍可用。

### Commit 10 — `docs/extensions: document sealed hot-plug, trust and crash recovery`

內容：

- README/guide/SKILLS_GUIDE。
- lock/Skill/MCP schema examples作parse tests。
- 說清楚MCP等同第三方code execution。
- 說清楚desired/applied/realized，不宣稱disk-memory原子。
- 說清楚v1不build/install、不動態Python、不watch、不auto-GC。
- 記錄phase 2 inference agent與MCPB importer為future work。

Gate：

- docs examples與runtime schema一致；
- clean source checkout與clean wheel完整acceptance全綠。

---

## 18. Failure-mode simulation要求

實作不得只測happy path。以下每項都要有可重現測試與預期outcome。

### 18.1 使用者正在複製bundle時reconcile

- 缺檔、extra檔或hash mismatch → `unsealed`／`unstable_copy`。
- 不建立snapshot，不改applied。
- 若舊版已applied，realized維持舊版。

### 18.2 新版損壞、舊版仍在使用

- desired顯示新hash與invalid diagnostic。
- applied/realized保持舊generation。
- status顯示`kept_last_known_good`。

### 18.3 turn途中reconcile

- prepare可並行。
- commit等待turn lock。
- 當前turn全程使用舊generation。
- 下一turn使用新generation。

### 18.4 active Skill required MCP被刪或更新失敗

- intentional delete：MCP刪除與Skill deactivate在同一commit。
- failed update：舊MCP與舊Skill closure一起保留。

### 18.5 MCP probe hang/noise/cancel/orphan

- timeout後terminate/kill/wait。
- bounded diagnostics。
- process與child PID消失。
- candidate不進applied。

### 18.6 兩個tool同名但family/exposure不同

- final catalog validation整代abort。
- 不依載入順序選勝者。
-舊runtime不變。

### 18.7 snapshot/metadata已prepare但candidate graph失敗

- 未published staging可清理。
- SQLite current不變。
- memory不變。

### 18.8 durable commit成功、memory swap前process crash

- 其他process可看到新applied。
- crash process重啟後從新applied realize。
- 不宣稱舊process曾完成runtime swap。

### 18.9 audit/report寫失敗

- audit metadata應與current在同SQLite transaction；不可發生current成功、核心audit row失敗。
- terminal rendering或post-commit額外log失敗不回滾已commit generation，但report必須誠實標示render/log warning。

### 18.10 non-TTY、`--yes`、cancel與`--no-mcp`

- 非TTY不input。
- `--yes`不建立首次approval。
- cancel零mutation。
- no-mcp不probe/start/bind。

### 18.11 source checkout可用、wheel找不到resource

- build wheel、安裝temp venv、移除source path後執行smoke。
- private/built-in resource仍可定位。
- user/state roots仍可寫。

### 18.12 private inference prompt或raw bundle被替換

- v1 normal path不依private prompt。
- phase 2 inference前後hash不同 → inference結果作廢。
- raw bundlelock/source hash改變 → candidate作廢並重新scan。

### 18.13 startup applied MCP無法realize

- CLI仍啟動。
- applied current不變。
- realized diagnostics標`applied_but_unavailable`。
- dependent required Skill不自動activate。

### 18.14 兩個CLI process同時apply

- 只有expected-generation相符者commit。
- 另一方回`stale`或`busy`。
- 無lost update、無重複generation ID、無交錯audit。

---

## 19. 測試矩陣

### 19.1 Baseline與regression

- full suite exact command與collected count。
- Web Search global／GitHub skill-scoped。
- citation activation、off、service teardown、SourceRefs isolation。
- `--no-mcp`。
- slash local routing與followup behavior。
- normal/extended Fusion行為。

### 19.2 Discovery與filesystem

- empty roots、no-op rescan。
- sealed add/update/delete/rename。
- missing/extra/hash mismatch lock entries。
- scan前後source變更。
- symlink、junction/reparse、hardlink、special file。
- casefold collision。
- permission error。
- file count、individual size、total size、path length限制。
- Linux與Windows path tests。

### 19.3 SQLite與cross-process

- schema create/migration。
- `BEGIN IMMEDIATE` busy。
- stale expected generation。
- crash before/aftercommit。
- database disk-full／permission failure注入。
-兩process concurrent apply。
- transaction內audit/current一致。
- network filesystem config拒絕。

### 19.4 Skill

- same-session picker refresh。
- inactive update後activation讀新snapshot。
- active valid update。
- active invalid update LKG。
- active delete。
- task mode removed。
- required/optional MCP family transitions。
- drop-in要求private host tool拒絕。
- capability approval hash change。
- scripts warning與inert behavior。
- prompt/control-character sanitization。

### 19.5 Tool catalog與graph

- MCP/MCP、MCP/local、MCP/builtin、MCP/management collision。
- casefold collision。
- family single owner。
- requested exposure與approved exposure一致。
- model binding／availability／PolicyToolNode一致。
- forged old-generation call拒絕。
- candidate graph build exception保持舊runtime。
- Fusion graph signature不因無關MCP更新重建。

### 19.6 MCP real subprocess

- normal initialize/list-tools/call。
- stdout noise。
- stdout/stderr flood。
- initialize hang。
- tool-call hang。
- ignore cancellation。
- ignore terminate。
- spawn child/grandchild。
- oversized tool count、name、description、schema、result。
- command injection字元不展開。
- minimal env不含runtime-control vars。
- delete/shutdown無orphan。
- Windows job與POSIX process group。

### 19.7 Approval與CLI

- first MCP requiresinteractive approval。
- exact approval reuse。
- changed descriptor/artifact/argv/cwd/env/exposure使approval失效。
- `--yes`不創建首次approval。
- non-TTY不input。
- cancel零mutation。
- `status`不跑LLM/probe。
- command不進history。
- typed partial report準確。

### 19.8 Startup與recovery

- clean startup current generation。
- current snapshot壞，fallback前代作realized但不改applied。
- 單一MCP unavailable，其他仍可用。
- `--no-mcp` applied-vs-realized drift。
- SQLite transaction residue。
- staging partial cleanup。

### 19.9 Packaging

- source checkout smoke。
- Poetry wheel contents assertion。
- temp venv install後：
  - `import agent`；
  - `import skills.citation`；
  - shipped resource lookup；
  - writable user/state roots；
  - `python -m agent.cli.chat --no-mcp`；
  - legacy Web/GitHub configuration smoke。
- source tree不在`sys.path`時仍通過。

---

## 20. 現成工具與依賴決策

### 20.1 採用／沿用

| 問題 | 決策 |
|---|---|
| schema與strict typed models | 沿用Pydantic v2 |
| durable registry／CAS／audit metadata | 採stdlib `sqlite3` |
| immutable content hash | 採`hashlib.sha256` |
| package resources | 採`importlib.resources` |
| user data/state roots | 新增direct `platformdirs` dependency |
| MCP protocol | 採官方MCP Python SDK v1 |
| LangChain tool conversion | 沿用`langchain-mcp-adapters`，但不把它當process supervisor |
| subprocess | 採`asyncio.create_subprocess_exec`／SDK stdio primitive加host supervisor |
| LangGraph | 沿用現有compiled graph；host自行持有realized graph pointer |

### 20.2 版本策略

- 新增direct constraint：`mcp>=1.27,<2`。
- 維持目前`langchain-mcp-adapters>=0.2.2,<0.3`，升版另做相容性審查。
- LangGraph不因本計畫強制升major/minor；先在現有lock版本完成。

### 20.3 v1不採用

- pluggy：適合受信任Python hooks，不解決drop-in安全、MCP或transaction。
- stevedore：適合installed entry-point plugins，不適合本次user folder contract。
- watchfiles：只提供變更通知，不能證明copy complete，v1又不做watcher。
- resolvelib：v1只有exact dependency closure，不需通用version solver。
- filelock作主要registry transaction：SQLite已提供較完整的CAS與crash recovery。
- LangGraph checkpoint作extension registry：graph execution state與extension applied state責任不同。

### 20.4 只作相容／參考

- Agent Skills spec：採`SKILL.md`基本bundle格式，host lock/manifest是明確擴充。
- MCPB：phase 2可作import format；不直接採其one-click build/install語義。
- MCP Registry `server.json`：可映射publisher/package metadata；不能取代本地argv/cwd/env/approval contract。

---

## 21. 完成驗收標準

以下全部成立才算完成v1：

1. `repair` production baseline的完整測試有可重現CI紀錄，不再引用未說明的`63 passed`。
2. source checkout與built wheel都能定位shipped resources，且user/state root可寫、彼此分離。
3. user drop-in沒有valid `.extension-lock.json`時永遠不apply。
4. CLI啟動後加入sealed prompt-only Skill，reconcile後同session picker可見並可activate。
5. 修改active Skill後下一turn讀新內容；invalid update保留舊內容；delete明確deactivate。
6. 新增strict sealed stdio MCP，exact approval後同session可用；update/delete不需restart。
7. MCP hang、cancel、delete與CLI shutdown後沒有host已知orphan process。
8. tools、families、prompt、model binding與`PolicyToolNode`在每個turn內來自同一realized generation。
9. status明確區分desired、applied與realized。
10. 兩個CLI process同時apply不會lost update；一方必須stale/busy。
11. durable commit失敗時memory與citation state完全不變。
12. durable commit成功後process crash可在startup從applied重建realized。
13. all-universe同名/casefold collision一律fail-fast。
14. drop-in Skill不能取得citation或management private tools。
15. `--yes`不能建立首次MCP execution或global exposure approval。
16. `--no-mcp`不probe、不start、不bind，但status與Skill-only reconcile仍可用。
17. Web Search global、GitHub skill-scoped、citation isolation與existing tool policy regression全綠。
18. normal reconcile不呼叫LLM；private inference resource缺失不影響status或strict apply。
19. docs examples由tests解析，與runtime schema一致。
20. v1沒有自動build/install、任意Python import、watcher、HTTP transport或committed snapshot GC的隱藏路徑。

---

## 22. 最小可交付milestones

### Milestone A — Skill hot refresh

完成Commit 1–6後交付：

- sealed prompt-only Skill同session CRUD；
- active Skill安全transition；
- SQLite applied state；
- built wheel支援；
- desired/applied/realized status；
- 不含第三方process執行。

這是最早能提供實際使用價值、且風險可控的版本。

### Milestone B — Strict stdio MCP hot refresh

完成Commit 7–9後交付：

- exact-approved declarative stdio MCP同session CRUD；
- bounded supervisor；
- dependency closure；
- startup degraded realization；
- non-TTY approval policy。

### Milestone C — Optional inference

v1驗收後另行決定是否需要：

- descriptor inference agent；
- MCPB importer；
- rollback UX；
- safe GC與persistent transport。

---

## 23. 實作停止點

本文件核准後才可開始production implementation。

開始寫code前必須確認以下決策沒有被重新模糊化：

- normal reconcile是deterministic；
- desired/applied/realized分層；
- SQLite是durable metadata authority；
- user/private/state roots分離；
- sealed bundle是v1必要contract；
- v1不build/install；
- `--yes`不創建首次execution approval；
- owner-aware collision在第一個commit先修；
- MCP SDK pin `<2`；
- committed snapshot v1不auto-GC；
- citation實體搬遷與management inference都不阻擋v1。

完成Milestone A後先進行一次獨立驗收，再決定是否推進Milestone B；不得因為scanner已能看到資料夾，就宣稱熱插拔完成。
