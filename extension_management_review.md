# Extension Management 計畫實證審查報告

- 審查日期：2026-07-22
- 目標 repo：`Minervamuses/RESEARCH-AGENT-WORKSPACE`
- 審查分支：`repair`
- 受審計畫：`extension_management.md`
- 受審 commit：`8ca86e38cdb5caf7198c34c2fed503318a448ea9`
- 程式基準：`a8209a323350ad8af6f2d40d633d9eeb9b47fd6f`
- 審查方式：逐項對照現行 repo 程式、設定、CLI、Skill、MCP、graph、storage、packaging，再對照 MCP／Agent Skills 官方規格與現成實作
- 限制：本次無可用的 GitHub Actions run／commit status；本地 clone 因執行環境 DNS 失敗，未能重跑測試。因此本文不把計畫中的「63 passed」當成獨立驗證結果，也不宣稱已執行測試。

---

## 1. 結論

### 1.1 總評

這份計畫**大體建立在真實 repo 上**，對現況的掌握程度高，尤其下列判斷是正確的：

- MCP 目前是 Web Search／GitHub 兩個固定 resolver，啟動時載入，沒有資料驅動的 extension catalog。
- Skill discovery、Skill activation、tool access、graph binding、CLI slash routing 目前彼此耦合，不能只加 scanner 就得到安全熱插拔。
- graph、tools、MCP family、active Skill、prompt 必須來自同一份 runtime state，否則會出現 stale tool／stale permission。
- 壞掉的更新應保留 last-known-good，存在但 malformed 的資料夾不能被誤判為刪除。
- management mutation tool 不應暴露給主 graph，LLM 不應直接持有 apply API。
- 現有 `/bin/sh -c | grep` MCP 啟動方式不適合作為一般第三方 MCP 的安全執行路徑。
- citation 是 code-backed built-in Skill，不能在第一步就當作普通資料夾搬遷。

但這份計畫**不宜原樣進入實作**。它缺少幾個會在真實使用時造成權限擴張、跨 process 競爭、crash 後狀態分裂的關鍵設計；同時把 LLM/private Skill 放進太多 deterministic 操作的必要路徑，增加了不必要的失敗面。

### 1.2 評分

| 面向 | 評分 | 判斷 |
|---|---:|---|
| 與 repo 真實狀態吻合度 | A- | 多數檔案、呼叫鏈、耦合點描述正確 |
| 原計畫可直接落地程度 | C+ | 能做，但原樣實作會留下重大一致性與權限問題 |
| 修訂後可落地程度 | A- | 先做 deterministic substrate，再接 MCPB／Agent Skills，可控 |
| 現成工具可重用程度 | 高 | MCPB、MCP Registry、MCP Python SDK、LangChain MCP adapter、Agent Skills spec、SQLite 都可直接降低自製範圍 |
| 建議決策 | **先修訂計畫，再寫 production code** | 不建議依現有 10 commits 直接開工 |

---

## 2. 計畫是否構建於真實 repo

## 2.1 已被 repo 證實的部分

| 計畫判斷 | repo 實證 | 結論 |
|---|---|---|
| MCP 是固定配置，不是 extension catalog | `app/agent/mcp.py::_web_search_spec`、`_github_spec`、`resolve_mcp_specs` 只列兩個 resolver | 正確 |
| MCP 在 session 建立前一次性載入 | `app/agent/session.py::ChatSession.create` 呼叫 `load_mcp_tools_with_families()`，再建 `ChatSession` | 正確 |
| graph 捕獲當時的 tool universe | `app/agent/graph.py::build_graph` 建立 `tools_by_name`、binding cache、`PolicyToolNode` 後 compile | 正確 |
| Skill picker 使用 constructor 時的 cache | `ChatSession.__init__` 寫入 `loaded_skills`；`cli/slash_commands.py::_session_skills` 優先讀該欄位 | 正確 |
| Skill runtime 本身是 activation 時的 snapshot | `load_skill_runtime()` 重新讀檔，但 active runtime 不會自動重載 | 正確 |
| `/skill` 與 `/citation` 尚未走共用 runtime transaction | handler 直接呼叫同步 `activate_skill()`／`deactivate_skill()`，直接改 instance field | 正確 |
| turn 已有 session 級鎖可利用 | `turn_outcome()` 使用 `_turn_execution_lock` | 正確，這是改造基礎 |
| global MCP family 被硬編碼為 web_search | `app/agent/tool_access.py::GLOBAL_MCP_FAMILY` | 正確 |
| prompt 硬寫 Web Search／GitHub | `app/agent/session.py::SYSTEM_PROMPT` | 正確 |
| behavior evaluator 的 Web tool names 是 frozen list | `app/agent/tools/inventory.py::WEB_BEHAVIOR_TOOL_NAMES` | 正確 |
| 現行 duplicate policy 會默默吞掉部分 collision | `build_base_tools()` 跳過同名 extra tool；`tools_by_name` dict 會後寫覆蓋 | 正確，必須先改 |
| `/init` 已間接排除 `app/tool` | `app/agent/ingest.py::init_workspace` 排除整個 `app/` | 正確 |
| wheel 尚未包含新的 tool bundle resources | `app/pyproject.toml` 只 package `agent`、`skills`，額外 data 只有 citation venue catalog | 正確 |
| citation storage 已有 staging／fsync／rename／hash／lock 模式可重用 | `app/skills/citation/storage.py` | 正確，可抽成共用 storage primitive |
| repair 計畫 commit 沒偷改 production code | `8ca86e3` 相對 `a8209a3` 只新增 `extension_management.md` | 正確 |

## 2.2 與 repo 有偏差或需要收斂的部分

### A. 「單一 runtime generation 原子提交」用詞過度

disk 的 `current` pointer 與 Python process 內的 state pointer 不可能形成真正單一原子交易。即使先 commit durable pointer，再做保證不 raise 的 memory assignment，process 仍可能在兩者之間 crash。

應改成三層狀態：

1. **desired**：使用者 drop-in tree 想要什麼；
2. **applied**：durable registry 已批准並可重建的 generation；
3. **realized**：這個 process 現在實際綁定的 generation。

這個系統可以做到 crash-consistent、可恢復、可偵測 drift；不能誠實地宣稱 disk 與 memory 完全原子。

### B. Fusion cache 的 invalidation 範圍過大

現行 `FusionOrchestrator` 的 proposer graph：

- 以 model ID cache；
- `extra_tools=None`；
- 不載 MCP；
- 只綁固定 read-only local allowlist。

所以「任何 MCP generation 變更都清掉所有 Fusion cache」不是目前 repo 的必要條件。應用 `GraphSignature` 精準判斷：只有 model、local tool identity/schema、graph policy 或 proposer allowlist 改變才 rebuild。Skill 文字或 MCP catalog 改變通常只需重算 prompt/runtime state。

### C. MCP retired-handle lifecycle 在 v1 可能過度設計

現行 `langchain-mcp-adapters` 的 `MultiServerMCPClient.get_tools()` 預設在每次 tool invocation 建新的 `ClientSession`，不是必然持有一個長生命週期 session。除非本專案明確改成 persistent session，第一版不需要先做複雜的 per-generation handle reference counting。

仍要保留 lifecycle abstraction，但 v1 可先做到：

- candidate probe session 有明確 timeout／close；
- turn lock 保證 swap 時沒有本 process 的 in-flight turn；
- future persistent transports 再實作 retired handle draining。

### D. `status` 不應依賴 private management Skill

計畫要求 `status` 也 fresh-load private `SKILL.md`。這會造成最需要診斷時，因 private prompt 缺檔或損壞而連 status 都不能用。

較合理的邊界：

- `status`、scan、strict validation、diff、strict descriptor apply 全為 host-only deterministic path；
- private management Skill 只用在「缺 descriptor 的 MCP 推導候選」；
- private Skill 壞掉時，status 應顯示 `manager_inference_unavailable`，而不是整個管理面失效。

### E. 「63 passed」目前沒有獨立證據

repair head 沒有 commit status，也沒有 workflow run。這個數字可以保留為作者本機基準，但應在計畫中標成：

> author-reported local baseline; must be re-run in CI before implementation gate

---

## 3. 原計畫的重大阻擋點

以下項目在開始 production implementation 前應寫回計畫，否則後面會反覆重構。

## 3.1 缺少跨 process 併發控制

計畫只有：

- management single-flight；
- session runtime lock。

這只能防同一個 Python process。若兩個 CLI instance 指向同一 workspace/state root，仍可能同時：

- 讀到 generation 12；
- 都準備 generation 13；
- 同時更新 current；
- 覆蓋 approval／audit；
- 在另一個 process 還使用 snapshot 時 GC；
- 對同一 drop-in 做不同判斷。

`atomic replace` 只能防 torn write，不能防 lost update。

### 必須補的設計

- 使用 workspace-scoped cross-process transaction：
  - 建議 stdlib `sqlite3`；
  - 或至少 cross-platform file lock + compare-and-swap。
- 準備與人類 approval 期間不能持有 DB write lock。
- commit 階段才短暫：
  1. 取得本 process session runtime lock；
  2. `BEGIN IMMEDIATE`；
  3. recheck expected applied generation、scan token、source hashes、approval hashes；
  4. durable commit；
  5. memory pointer assignment；
  6. release。
- DB busy 或 precondition stale 時，釋放 session lock並回報 retry/busy，不在鎖內等待 LLM、copy、probe、input。

## 3.2 缺少 Skill capability approval

這是目前計畫最重要的權限缺口。

現行 Skill manifest 可要求：

- `bash`
- `read_file`
- `recall_history`
- RAG tools
- 任意已存在的 MCP family

原計畫只對 MCP execution、network/build、global exposure 做 approval，卻沒有對「新 Skill 取得敏感工具」做權限差異審批。

一個看似只有 `SKILL.md` 的 drop-in Skill，可以在 manifest 要求 `bash`，其 prompt 再引導模型執行命令。雖然 bash 每次還會詢問使用者，但這仍是明確的 capability escalation；`read_file`、history、RAG 也涉及資料外洩面。

### 必須補的設計

每個 Skill 要產生 `CapabilityDelta`，至少包含：

- requested local tools；
- requested MCP families；
- bundled scripts；
- resource read scope；
- network requirement；
- compatibility／runtime requirement；
- 是否嘗試使用 host-unsupported vendor fields。

建議分類：

| capability | 建議政策 |
|---|---|
| prompt-only、無 tools、無 scripts | 可 deterministic 安裝；不自動啟用 |
| RAG read-only | 可由 policy 預批准或首次顯示 |
| `read_file`／history | 顯式 capability approval |
| `bash` | 顯式高風險 approval；不得由 `--yes` 首次批准 |
| MCP family | 需同時滿足 Skill capability grant 與 MCP execution grant |
| scripts | 安裝不執行；真正執行仍走 host tool policy |

Approval 必須綁定 Skill bundle hash + normalized manifest hash；manifest 權限改變後舊批准失效。

## 3.3 Private Skill／LLM 被放進不必要的 critical path

純 Skill CRUD、已有合法 MCPB/strict descriptor 的 MCP CRUD，都可完全 deterministic。讓管理 agent 每次介入會增加：

- model unavailable；
- structured output failure；
- prompt injection surface；
- token 成本；
- 行為不穩定；
- private prompt 損壞造成整體不可用。

### 建議

第一版 `/Extension-Management` 不啟動 LLM。另設明確 assisted command，例如：

```text
/Extension-Management infer mcp:<id>
```

它只能：

- 讀 host 限定的 metadata；
- 產生 candidate normalized descriptor；
- 回傳 evidence／uncertainty；
- 儲存為待審 proposal。

它不能在同一命令自動 probe 或 apply。真正執行要再次 deterministic validate + explicit approval。

## 3.4 source checkout 把不同信任域混在 `app/tool/`

原計畫在 source checkout 想提供單一 `app/tool/` 視圖，但這會混合：

- 受版控的 built-in resources；
- private management prompt；
- 使用者下載的未信任 drop-ins；
- 可能巨大、含 node_modules／binary 的 artifacts。

現行 `.gitignore` 沒有相應規則。風險包括：

- 使用者 drop-in 出現在 git status；
- 誤 commit 第三方程式、token 或 build output；
- raw bundle 可覆寫／混淆 host-owned 資源；
- private Skill 在 source checkout 其實是 user-writable，不能當安全邊界；
- wheel 與 source mode 語義分裂。

### 建議根目錄

```text
ShippedResourceRoot (read-only package resources)
  agent/resources/extensions/...

WorkspaceDropInRoot (writable desired state)
  <workspace>/.agent/extensions/
    skill/
    mcp/

StateRoot (writable, non-source)
  <platform-state>/research-agent/<workspace-id>/
    registry.sqlite3
    objects/
    staging/
```

若產品需求堅持「拖到 repo 內」，至少改為：

```text
app/tool/dropins/{skill,mcp}/
```

並明確 gitignore；`_internal`／built-in 不應和 drop-ins 同一 physical root。

## 3.5 approval 沒有綁定完整 execution closure

只 hash descriptor、argv、cwd、env-name set 還不夠。以下內容變動都可能改變實際執行程式：

- system `python`／`node` realpath 或版本；
- `node_modules`／Python bundled libs；
- dynamic library；
- build output；
- interpreter-controlled env；
- mutable external path；
- `uv`／`npx` 在執行時下載的新 dependency。

### v1 approval 建議至少綁定

- staged snapshot tree hash；
- entrypoint/artifact hash；
- normalized descriptor hash；
- exact argv、cwd；
- env key set及值來源類型；
- resolved interpreter realpath、version、platform、arch；
- exposure；
- discovered tool surface hash；
- host policy version。

第一版應只接受已可執行、依賴已封裝的 artifact。`uv` 自動安裝、`npx`、任意 repo build、network install 全部放到 phase 2。

## 3.6 timeout／cwd／minimal env 不是 sandbox

第三方 MCP 仍以使用者 OS 身分執行，通常能：

- 讀取同帳號可讀檔案；
- 對外連網；
- 啟動 child process；
- 掃描 home；
- 將收到的 secret 外傳。

CLI approval 文案必須直說：

> 這會以你的作業系統帳號執行第三方本機程式；目前不是 sandbox。

不要把 bounded subprocess 寫成隔離。真正隔離需另做 platform backend，例如 container／OS sandbox，且應是後續 milestone。

## 3.7 generic stdout sanitizer 不應成為公開策略

現行 `/bin/sh -c "... | grep '^{'”` 是為特定 Web Search server 的相容 workaround，不適合泛化：

- 經 shell；
- 可能吞掉協議錯誤；
- 無法可靠處理 multiline／非 object frame；
- 會把壞 server 偽裝成正常；
- 增加 process tree／取消／stderr 管理難度。

v1 規則應是：

- 新 drop-in MCP 的 stdout 必須是嚴格 MCP transport；
- noise 直接 quarantine；
- Web Search 若仍需 sanitizer，使用 host-owned、server-specific direct subprocess adapter；
- 不提供任意 manifest 可選的 `json_lines` 清洗模式。

## 3.8 root scan health 必須阻止 mass delete

不能只針對單一 folder 判斷 malformed。若整個 desired root：

- mount 掉線；
- 權限錯誤；
- 路徑被暫時替換；
- I/O 中斷；
- scanner 未完整走完，

則所有 applied extension 看起來都「不存在」，會造成 mass delete。

只有 `ScanResult.complete == true`、root identity 相符、沒有 fatal traversal error 時，absence 才可產生 delete。

## 3.9 Registry schema migration／recovery 未定義

`schema_version: 1` 不夠。要定義：

- known version migration；
- unknown newer version fail closed；
- migration backup；
- integrity check；
- current generation foreign-key／checksum；
- approval policy version；
- audit retention；
- object GC 的引用關係。

SQLite 比手寫多個 JSON current pointer 更適合這一層；大型 snapshot／artifact 仍可放 content-addressed filesystem。

## 3.10 tool identity 不能只是一張 `tool_name -> family` map

現行 family map 對同名 tool 會後寫覆蓋。新系統應先建立不可變 `ToolDescriptor`：

```text
ToolDescriptor
  public_name
  owner_kind
  owner_id
  extension_generation
  family
  exposure
  input_schema_hash
  description_hash
  side_effect_class
  adapter/tool object
```

規則：

- 所有 public name 在 candidate catalog 建 graph 前一次性 fail-fast；
- collision 不能靠載入順序或 dict 覆蓋；
- PolicyToolNode、model binding、prompt、status 都讀相同 descriptors；
- MCP 每次 realization 重新取得 surface，若 schema／name／description hash 漂移，轉 pending approval，不可靜默綁定。

## 3.11 `--yes` 不可創造第一次 code-execution approval

建議明確限制：

- `--yes` 只能重用已存在、完全匹配 hash 的 grant；
- 不能首次批准第三方 executable；
- 不能首次批准 Skill 的 `bash`／敏感讀取 capability；
- 不能批准 global exposure；
- 不能跨越 missing secret、unsupported transport、ambiguous entrypoint；
- CI 可使用預先寫入、可審計的 policy file／approval record，而不是把 `--yes` 當總開關。

## 3.12 平台範圍需要先決定

計畫使用的 `0600`、directory fsync、POSIX symlink/hardlink、process group、signal、`fcntl` 並非完全跨平台。repo 目前 citation cross-process lock 在 non-POSIX 直接 fail closed。

建議第一版明確標示 **Linux-first**。若第一版就承諾 Windows/macOS，必須提前加入：

- cross-platform lock；
- Windows executable/path semantics；
- process tree termination；
- directory durability差異；
- ACL 而非只寫 `0600`；
- platform-specific MCPB resolution。

## 3.13 build/network scope 與 milestone 互相矛盾

計畫一方面說第一個 milestone 不做任意 repository autobuild，一方面又把 build staging、install/build/network approval、provenance 混進核心 transaction。

應拆開：

- **v1**：prebuilt binary、bundled Node/Python dependencies、strict stdio；
- **v2**：MCPB `uv`、package manager、network install、reproducible build、SBOM/provenance；
- **v3**：sandboxed build/install。

## 3.14 quotas／GC 尚不夠具體

至少要設定並測試：

- root 總 bytes；
- bundle bytes、file count、單檔大小；
- path depth／path length；
- manifest／description／input schema size；
- tool count；
- probe output／tool result／stderr diagnostics；
- staging age；
- retained generation count；
- global state disk quota；
- GC 只刪零引用 object。

---

## 4. 可直接重用的現成工具、API 與 repo

## 4.1 MCPB：不要自創唯一外部套件格式

官方 `modelcontextprotocol/mcpb` 已定義：

- `.mcpb` zip bundle；
- `manifest.json`；
- Node／Python／binary／UV server type；
- entrypoint；
- runtime compatibility；
- `mcp_config`；
- user configuration／sensitive fields；
- pack／validate tooling與 loader code。

建議架構：

```text
MCPB manifest.json
        │
        ├─ importer
        ▼
InternalNormalizedMCPDescriptor
        ▲
        ├─ Registry server metadata importer
        ├─ legacy Web/GitHub adapter
        └─ optional repo-specific descriptor importer

HostPolicyOverlay
  family / exposure / timeout / secret binding / approval
```

`extension.yaml` 可以保留，但應定位為：

- host-owned internal normalized form；或
- `agent-policy.yaml` sidecar，只保存本 host 的 family/exposure/policy。

不應宣稱它是唯一 canonical external contract。

官方來源：
- https://github.com/modelcontextprotocol/mcpb
- https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md

## 4.2 MCP Registry：用於 discovery／metadata，不等於信任

官方 Registry 已有 `server.json` model、API、publisher 與 namespace ownership validation。

可重用：

- server metadata；
- package/install hints；
- version discovery；
- namespace provenance；
- known transport metadata。

不可直接推論：

- registry 出現 = 程式安全；
- publisher namespace ownership = artifact 不惡意；
- 最新版 = 已批准執行。

Registry importer 後仍需 artifact hash、host policy、execution approval。

官方來源：
- https://github.com/modelcontextprotocol/registry
- https://registry.modelcontextprotocol.io/docs

## 4.3 MCP Python SDK：用於 deterministic probe

建議以官方 Python SDK直接做：

- stdio launch；
- initialize；
- tools/list；
- schema capture；
- timeout／close；
- probe error classification。

再用 `langchain-mcp-adapters` 把已批准的 MCP tools 轉成 LangChain tools。

截至 2026-07-22，官方 README 明確指出：

- v1.x 是 production stable；
- v2 尚為 prerelease；
- stable v2 目標為 2026-07-27；
- 建議依賴加 `<2` 上限避免意外 major upgrade。

因此 v1 implementation 應先：

```text
mcp>=1.x,<2
```

並把 SDK 隔離在 internal adapter interface，日後再做 v2 migration。

官方來源：
- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/langchain-ai/langchain-mcp-adapters

## 4.4 LangChain MCP adapters：保留 wrapper，別重寫

repo 已依賴 `langchain-mcp-adapters`。它可繼續負責：

- MCP tool → LangChain tool；
- ToolMessage error semantics；
- Multi-server compatibility。

但 current dependency `<0.3.0` 已落後官方 2026-06 release `0.3.0`。不要在 extension 主改造中順手升級；先寫 adapter characterization tests，再另開 dependency upgrade commit。

另外，官方文件說 `MultiServerMCPClient.get_tools()` 預設每次 tool invocation 建新 `ClientSession`。這支持前述結論：v1 不必先把所有 MCP 視為 permanent process handle。

## 4.5 MCP Inspector：CI／開發 oracle，不是 runtime dependency

官方 Inspector 有 CLI mode，可做：

- tools/list；
- tools/call；
- resources／prompts；
- JSON output；
- CI smoke。

適合拿來對 fake MCP 與 host probe 結果做交叉驗證；不建議讓 production reconcile 在 runtime 呼叫 `npx inspector`，避免多一套 Node／下載／process 信任面。

官方來源：
- https://github.com/modelcontextprotocol/inspector

## 4.6 Agent Skills spec：對齊格式，但不要直接依賴 demo validator

官方 Agent Skills 已明定：

- `SKILL.md`；
- `name`／`description`；
- name 1–64、小寫字母數字與 hyphen、不得連續 hyphen、需等於 folder；
- optional scripts/references/assets；
- experimental `allowed-tools`；
- progressive disclosure。

現有 built-in `_prompt-master` 不符合 public name 規則，因此需要：

- built-in/private compatibility provider；
- public drop-in 嚴格按標準；
- 不要為了舊 built-in 放鬆 public validator。

官方 `skills-ref` 可以當 conformance oracle／測試資料來源，但其 README 明說是 demonstration only、not production。建議把必要規則實作進本 repo 的 Pydantic validator，不把 demo library當 production dependency。

官方來源：
- https://agentskills.io/specification
- https://github.com/agentskills/agentskills

## 4.7 stdlib SQLite：取代脆弱的多檔 current pointer 協調

Python 3.12 內建 `sqlite3`，支援 transaction、`IMMEDIATE`／`EXCLUSIVE`、lock timeout、commit／rollback。

建議 DB 保存：

- schema migrations；
- applied generation；
- extension records；
- approvals；
- tool surface hashes；
- audit events；
- object references；
- pending/quarantine diagnostics。

filesystem 保存：

- immutable content-addressed snapshots；
- executable artifacts；
- bounded diagnostic files。

這比 registry JSON + current file + JSONL audit 三套並行一致性容易證明。

官方來源：
- https://docs.python.org/3.12/library/sqlite3.html

## 4.8 repo 內可直接抽出的 primitives

`app/skills/citation/storage.py` 已有：

- workspace root fallback；
- platform user-data path；
- staged write；
- file fsync；
- directory fsync；
- atomic rename；
- content hash；
- stale staging cleanup；
- POSIX lock。

不要複製貼上。先抽到例如：

```text
app/agent/storage/
  atomic.py
  paths.py
  locks.py
  content_store.py
```

再讓 citation 與 extension registry 共用。注意現行 lock 是 POSIX-only，不能直接宣稱跨平台。

---

## 5. 建議的 Revision B 架構

## 5.1 主要原則

1. **Deterministic first**：合法格式的 scan、validate、diff、apply、rollback 不依賴 LLM。
2. **Portable package + host overlay**：Agent Skills／MCPB 負責可攜格式，host policy 負責權限與批准。
3. **Desired／Applied／Realized 分離**：誠實處理 crash 與 transient unavailable。
4. **Immutable content store**：raw source 只作 desired input；runtime 只執行已 hash 的 applied object。
5. **Capability approval**：Skill 與 MCP 都要做 permission delta。
6. **No shell**：argv、direct subprocess、strict stdio。
7. **Short commit lock**：LLM、input、copy、hash、build、probe 都在 session/DB commit lock 外。
8. **Complete-scan delete gate**：root traversal 不完整時零 delete。
9. **No build/network in v1**：只接受 already-runnable artifacts。
10. **Status always available**：即使 manager inference prompt 壞掉也能診斷。

## 5.2 建議資料模型

```text
ExtensionKey(kind, id)

SourceRecord
  root_id
  relative_path
  source_tree_hash
  format_kind
  format_version
  scan_token

NormalizedSkillDescriptor
  id
  metadata
  resources
  requested_capabilities
  source_hash

NormalizedMCPDescriptor
  id
  package_format
  entrypoint
  argv
  cwd
  env_bindings
  runtime_requirements
  source_hash
  artifact_hash

HostPolicyOverlay
  family
  exposure
  timeouts
  result_limits
  secret bindings
  side_effect class

ApprovalGrant
  principal/user
  policy_version
  exact binding hash
  approved capability delta
  created_at
  revoked_at

AppliedGeneration
  generation
  parent_generation
  registry_hash
  object refs
  created_at

RealizedRuntime
  applied_generation
  realized tool descriptors
  unavailable records
  graph signature
  active skill runtime
```

## 5.3 建議 reconcile 流程

1. 取得本 process management reservation。
2. 完整 scan desired root；若 traversal fatal，停止，不產生 delete。
3. 將 Agent Skill／MCPB／legacy source 轉成 normalized descriptors。
4. deterministic schema、path、size、collision、capability validation。
5. 產生 authoritative diff + permission delta。
6. 對需批准項顯示 exact execution/capability binding。
7. approval 後 recheck source hash／scan token。
8. copy 到 immutable staging/CAS；再次 hash。
9. 只對已批准 MCP 做 direct SDK probe，取得 tool surface。
10. 建立完整 candidate ToolDescriptor catalog；全 universe collision fail-fast。
11. materialize active Skill candidate；build candidate graph；計算 GraphSignature。
12. 取得 session runtime lock。
13. 短暫開 SQLite write transaction，recheck expected applied generation與 session revision。
14. commit applied generation；memory pointer no-fail swap。
15. 寫 realized status；post-commit cleanup／GC。
16. 回報 desired/applied/realized、partial quarantine、active Skill 影響。
17. 若 process 在 disk commit後、memory swap前 crash，下一次 startup／turn 以 `realize_current()` 自動修復並在 status 留 recovery event。

---

## 6. 建議重排實作階段

原計畫的 10 commits 方向大致合理，但應改成下列順序。

### Phase 0 — characterization 與共同 primitives

- 鎖定現行 MCP、Skill、tool policy、citation、slash、fusion 行為。
- 補全 duplicate/collision characterization。
- 抽出 atomic storage/path/hash primitives。
- 建立 `ToolDescriptor`／`GraphSignature`，先包住現行靜態 runtime。
- CI 必須重跑並記錄基準，不沿用未驗證的「63 passed」。

### Phase 1 — deterministic Skill hot reload

- physically separate shipped/user/state roots。
- Agent Skills public validator + built-in compatibility provider。
- SQLite registry schema/migration。
- complete scan + desired/applied diff + last-known-good。
- Skill capability delta/approval。
- public async runtime transaction。
- 同 session add/update/delete/activate/deactivate。
- **不接 LLM、不接新 MCP。**

這一階段先證明最核心的 hot reload transaction。

### Phase 2 — strict prebuilt MCP

- MCPB importer。
- internal normalized descriptor + host overlay。
- stdio only。
- no shell。
- already-runnable binary／bundled Node／bundled Python only。
- MCP Python SDK probe。
- execution closure approval。
- tool surface drift／collision。
- LangChain adapter wrapper。
- `--no-mcp` 不 probe、不 realize。

### Phase 3 — crash recovery 與 cross-process

- SQLite `BEGIN IMMEDIATE` CAS。
- 兩個 CLI process 的 race tests。
- desired/applied/realized status。
- crash injection at every commit boundary。
- object reference GC／quota。
- startup transient unavailable。

### Phase 4 — optional manager inference

- private exact-path Skill。
- minimal history-free graph。
- 只處理 descriptor-less MCP。
- proposal-only，不在同一次 inference 自動執行。
- private prompt 缺失不影響 status／strict apply。
- prompt injection／coverage／typed output tests。

### Phase 5 — packaging、migration、docs

- `importlib.resources` shipped bundles。
- wheel smoke。
- built-in citation resource descriptor。
- 舊 `skills_dir` deprecation。
- 最後才考慮實體搬移 citation／academic bundle。
- 更新 README／guide／SKILLS_GUIDE。

### Phase 6 — 明確延後

- UV／npm/pip network install；
- arbitrary repo build；
- HTTP/SSE/WebSocket；
- dynamic Python local tools；
- sandbox backend；
- Registry auto-update；
- signed publisher/update channels。

---

## 7. 原測試矩陣還應增加的項目

1. 兩個獨立 process 同時 reconcile，同一 expected generation 只有一方 commit。
2. DB commit 後、memory swap 前 crash；重啟能辨識 applied != realized 並修復。
3. root unreadable／mount missing／fatal scandir 時零 delete。
4. Skill 從 prompt-only 更新為要求 `bash`，必須重新 approval。
5. `--yes` 無法建立第一次 executable／bash／global grant。
6. MCP runtime/interpreter realpath或版本改變使 approval 失效。
7. MCP tools/list surface 與上次 hash 不同時 quarantine/pending approval。
8. MCPB manifest version unknown 時 fail closed，且保留 last-known-good。
9. Registry schema migration失敗時 rollback DB，applied runtime不變。
10. duplicate public name 在 base/MCP/host Skill/management 的所有組合都 fail-fast。
11. root total size、file count、path depth、tool count、schema size、result size與 disk quota。
12. hardlink、symlink swap、rename race、partial copy、special file。
13. process cancellation後無 orphan；legacy Web sanitizer只對 host-owned server生效。
14. Fusion GraphSignature：MCP-only變更不做無謂 proposer rebuild；local schema變更必須 rebuild。
15. private manager prompt壞掉時 status與 strict Skill/MCP apply仍可用。
16. non-POSIX 行為：若 v1 Linux-only，Windows/macOS 明確回 unsupported，而非假裝成功。
17. audit不保存 secret value；known-secret redaction不是唯一防線，raw stderr預設不持久化。
18. approval revoke 後下一次 realization 不再載入 extension。

---

## 8. 需要由產品／維護者決定的 gate

| 決策 | 選項 | 建議 |
|---|---|---|
| G1：v1 是否需要 management LLM | 每次都跑／只做 inference／完全不做 | **只做 inference，且放 Phase 4** |
| G2：drop-in physical root | `app/tool` 混合／repo `.agent`／platform user-data | **repo `.agent` 或 platform user-data；built-in 分離** |
| G3：MCP 外部格式 | custom `extension.yaml` only／MCPB + overlay | **MCPB + host overlay** |
| G4：state persistence | JSON current + JSONL／SQLite + CAS objects | **SQLite + content-addressed objects** |
| G5：v1 platform | 跨平台／Linux-first | **Linux-first，文件誠實標示** |
| G6：v1 build/network | 支援／不支援 | **不支援** |
| G7：Skill sensitive capability | 自動允許／分級批准 | **分級批准；bash、file/history、MCP 必須顯示 delta** |
| G8：`--yes` | 可第一次批准／只重用既有 grant | **只重用既有 exact grant** |
| G9：citation bundle 搬移 | 早期／最後 | **最後，先保留 compatibility provider** |
| G10：persistent MCP sessions | v1 即做／按需後加 | **按需後加，先保留 lifecycle interface** |

---

## 9. 建議對原計畫的具體修改

在進入程式 commit 前，建議先把 `extension_management.md` 改成 Revision B，至少完成：

1. 將「atomic disk + memory」改寫為 desired/applied/realized crash-consistent model。
2. 加入跨 process transaction／SQLite schema。
3. 加入 Skill capability delta與approval。
4. 把 status／strict CRUD 從 private Skill／LLM 路徑拆出。
5. 把 `app/tool` 單一 physical root 改成信任域分離，或明確記錄這是待決產品選擇。
6. 把 MCPB／Registry／Agent Skills 納入 importer architecture。
7. 將 custom `extension.yaml` 改為 internal normalized descriptor或host overlay。
8. v1 明確禁止 build／network install／UV dynamic resolution。
9. 刪除 generic `json_lines` stdout policy；legacy sanitizer host-only。
10. 收斂 Fusion invalidation與MCP lifecycle，避免先做不必要複雜度。
11. 加入 complete-scan delete gate、schema migration、quota、tool surface drift。
12. 把 `--yes` 定義為只重用既有 exact approval。
13. 把「63 passed」改為待 CI 重跑的作者基準。
14. 明確寫出 v1 platform support。

---

## 10. 最終建議

核心目標「在同一 session 內新增／修改／刪除 Skill 與 MCP，不需改 host Python、不需重啟」是可實作的，而且目前 repo 已有足夠基礎：

- turn execution lock；
- strict Pydantic Skill manifest；
- centralized tool access resolution；
- graph policy enforcement；
- citation atomic storage primitives；
- local slash command architecture；
- LangChain MCP adapter。

真正應避免的不是 hot-plug 本身，而是一次把以下五件事綁成同一個第一版：

1. 自創套件格式；
2. LLM 自動推導；
3. 第三方 code execution；
4. 跨 process durable transaction；
5. built-in bundle 大搬遷。

最穩妥的落地路徑是：

> 先以 deterministic Skill CRUD 驗證 runtime transaction；再接 MCPB prebuilt stdio；再補 crash/cross-process；最後才加入 descriptor inference agent與 build/network。

因此本審查的建議狀態為：

**REQUEST CHANGES — 接受方向，不接受原樣實作。先由維護者決定 Gate G1–G10，修訂計畫後再進 production code。**
