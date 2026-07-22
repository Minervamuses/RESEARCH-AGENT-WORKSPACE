# Extension Management 可控熱插拔實作計畫

日期：2026-07-22

實作分支：`repair_temp`

狀態：**Milestone A 可依本計畫實作；Milestone B 在 MCP dependency spike 通過前維持 blocked。**

本文件定義 implementation contract、commit 邊界與驗收 gate。production code 尚未因本文件而變更；實際 baseline、測試數與依賴 lock hash 必須由 Commit 0 在當時的 branch HEAD 重新記錄。

---

## 1. 決策摘要

1. **正常 reconcile 完全 deterministic。**
   - scan、schema validation、diff、approval lookup、snapshot、MCP probe、tool inventory、collision、graph build、durable commit、runtime swap、status 與 recovery 全由 host code 執行。
   - 已有嚴格格式的 Skill／MCP 不依賴 LLM 才能管理。

2. **狀態固定分為 `desired`、`applied`、`realized` 與 turn generation。**
   - `desired`：完整掃描後觀察到的使用者來源狀態。
   - `applied`：SQLite durable registry 已提交、可重建的 generation。
   - `realized`：目前 Python process 實際綁定的 generation。
   - turn generation：一個 in-flight turn 開始時固定取得的 realized snapshot。
   - disk commit 與 memory pointer swap 是 crash-consistent protocol，不宣稱為單一原子交易。

3. **absence 只有在 authoritative complete scan 後才能變成 delete。**
   - 每個 root 都輸出 `complete | partial | fatal`。
   - root 不存在、權限錯誤、mount／磁碟離線、traversal 中斷、root identity 改變或 scanner error 一律是 zero-delete outcome。
   - delete 還必須通過明確 deletion authorization；不能只因資料夾暫時看不到就移除 applied extension。

4. **workspace、global、shipped 與 state root 明確分離。**
   - workspace drop-in：`<workspace>/.agent/extensions/`。
   - optional global drop-in：`platformdirs.user_data_dir(...)/extensions/`。
   - state：`platformdirs.user_state_dir(...)` 下依 workspace identity 分區。
   - shipped resources 只透過 `importlib.resources` 讀取。
   - 不以 source checkout 與 wheel 啟動方式改變 extension scope。

5. **Skill 使用 sealed Agent Skills bundle；MCP 使用 MCPB safe subset。**
   - Skill 由 `.extension-lock.json` 證明完整性。
   - MCP 的 canonical external package 是 `.mcpb`；host wrapper 只提供 drop-in completeness 與 policy overlay。
   - `extension.yaml` 只能作 internal normalized descriptor，不是唯一外部格式。

6. **active Skill 的行為內容變更不會未經重新啟用直接接管 session。**
   - inactive valid update 更新 catalog，不自動 activate。
   - active Skill 的 prompt、capability、task mode 或 runtime resource closure 變更時，提交新版並明確 deactivate；使用者必須重新啟用。
   - invalid update 保留舊 applied snapshot 與舊 active runtime。

7. **tool identity 必須包含 owner，所有 collision fail-fast。**
   - local、built-in Skill、MCP、management tools 在 graph build 前共用單一 catalog。
   - raw name 與 casefold name 都不得重複。
   - 不允許 first-wins、last-wins、silent drop 或自動 namespace rewrite。

8. **durable metadata 使用明確版本的 SQLite schema 與 CAS。**
   - `BEGIN IMMEDIATE`、`busy_timeout=0`、expected generation compare-and-swap。
   - descriptor object content-addressed 去重，不在每一代重複存整份 JSON。
   - transaction 內不讀 raw source、不 copy、不 hash、不 probe、不 compile。

9. **MCP 採兩階段批准。**
   - 第一階段批准 exact execution closure，只允許 isolated probe。
   - 第二階段批准 probe 得到的 exact tool surface 與 exposure。
   - runtime realization 必須再次驗證相同 runtime fingerprint 與 surface hash，才可進 main graph。

10. **MCP process lifecycle 優先重用官方 MCP Python SDK v1。**
    - pin `mcp>=1.27,<2`。
    - SDK 負責 stdio lifecycle、safe inherited environment、terminate／kill／wait、POSIX session 與 Windows process-tree cleanup。
    - host 只補 SDK 缺少的 bounded stdout frame、bounded stderr、host timeout、sanitized diagnostics 與 policy classification。
    - 不重寫完整跨平台 process supervisor。

11. **LangChain adapter 只做 tool conversion。**
    - host 建立並持有 explicit initialized `ClientSession`。
    - production path 不把 connection dict 交給 adapter 讓它自行 spawn。
    - adapter 不擁有 approval、process、surface verification 或 generation lifecycle。

12. **交付順序固定。**
    - Milestone A：sealed prompt/resource-only Skill same-session CRUD。
    - MCP dependency spike：先驗證 SDK hard bounds、MCPB importer、explicit session ownership 與 persistent session。
    - Milestone B：只有 spike gate 全通過後才加入 MCP CRUD。
    - 最後必須有強制 cleanup commit，刪除 shell pipeline、dual state 與所有 legacy live-authority path。

---

## 2. 已確認的 repository 現況

實作必須以 Commit 0 記錄的 branch HEAD 為唯一 baseline。以下介面目前已存在，改造不得假設另一套架構：

### 2.1 Session 與 graph

- `app/agent/session.py` constructor 直接保存 `extra_tools`、`mcp_families`、`web_search_tool_names`、`loaded_skills` 與 `self.graph`。
- `loaded_skills` 由 constructor-time `discover_skills(config)` 取得。
- static system prompt 仍硬編碼 Web Search、GitHub 與 `skills/<name>` 的 catalog／路徑語意。
- `build_graph()` 在 compile 時固定 model bindings、tool node 與 tool lookup。
- `_turn_execution_lock` 已存在，但 activation、deactivation、runtime mutation 尚未全部收斂到同一 mutation contract。

### 2.2 Skill

- `AgentConfig.skills_dir` 可指向任意目錄；未設定時使用 repo skills path。
- `discover_skills()` 是單一目錄的一次性掃描。
- malformed Skill 目前以 warning 跳過，沒有 authoritative desired/applied diagnostic。
- `load_skill_file()` 與 metadata/runtime loader 必須統一改成 strict UTF-8 與 sealed snapshot source。

### 2.3 MCP

- `app/agent/mcp.py` 目前只解析 Web Search 與 GitHub host specs。
- `_spec_to_connection()` 使用 `/bin/sh -c` 與 `grep` 過濾 stdout。
- `MultiServerMCPClient` connection mode 會由 adapter／SDK 自行建立 session。
- family map 以 tool name 為 key，後寫可覆蓋先前 owner。
- MCP 只在 `ChatSession.create()` 時載入一次，沒有 close handle 或 same-session replacement。

### 2.4 Storage 與 packaging

- `app/skills/citation/storage.py` 已有 content hash、0600 staged write、file／directory fsync、atomic rename、stale staging 與 POSIX lock，可抽為共用 primitive。
- `app/pyproject.toml` 尚未直接包含 `mcp`、`platformdirs`、`jsonschema`。
- dependency change 必須同 commit 更新 `app/poetry.lock`，且不得帶 unrelated lock drift。
- `.gitignore` 尚未涵蓋 `.agent/extensions/` 與 workspace extension metadata。
- `app/agent/resources/__init__.py` 尚未建立；wheel resource test 不得假設 namespace package 自動包含新檔案。

---

## 3. v1 範圍與 milestone gate

### 3.1 Milestone A 必做

- workspace 與 optional global scoped roots。
- per-root authoritative scan 與 zero-delete gate。
- sealed Skill bundle add、update、delete。
- immutable snapshots、SQLite generations、CAS、quota 與 recovery。
- owner-aware generation-0 tool catalog。
- same-session picker refresh、explicit activation、active update deactivation。
- legacy `skills_dir` 顯式 migration。
- minimal deterministic status／apply／dry-run。
- source checkout 與 installed wheel acceptance。
- 不啟動任何第三方 MCP process。

### 3.2 MCP dependency spike gate

Milestone B production code 開始前，必須由獨立 commit 證明：

- MCPB safe-subset importer 可安全拒絕 archive 攻擊與 unsupported runtime。
- 官方 MCP SDK v1 可重用哪些 lifecycle；host 只補哪些 hard bounds。
- bounded stdout frame 與 bounded stderr 可透過 public API、upstream hook 或最小 transport adapter 實現。
- host-owned explicit `ClientSession` 可傳給 `langchain-mcp-adapters`，且 production path 不會由 adapter 另行 spawn。
- generation-scoped persistent session 的 initialize、call、cancel、swap、shutdown 與 orphan 行為可控。
- cold／warm P50、P95 latency、peak RSS 與連續 100 calls process churn 已量測。
- POSIX process tree 與 Windows Job Object／SDK equivalent 都有真實測試。

任何一項沒有可重現證據，Milestone B 保持 blocked。

### 3.3 Milestone B 必做

- MCPB safe-subset add、update、delete。
- exact probe approval 與 exact surface approval。
- runtime fingerprint 與 tool surface revalidation。
- same-session MCP realization、LKG、dependency closure 與 graph swap。
- generation-scoped session ownership、list-changed fail-closed、`aclose()`。
- `--no-mcp` no-probe／no-start／no-bind。
- approval list／approve／revoke／headless policy import／rollback UX。

### 3.4 v1 明確不做

- 任意 Python module 動態 import／reload。
- downloaded Skill 註冊 host Python tool factory。
- background filesystem watcher。
- package manager、build script、UV、npx、uvx 或 network install。
- HTTP／SSE／WebSocket MCP transport。
- external mutable entrypoint。
- 自動 committed snapshot GC。
- 通用 dependency solver。
- normal reconcile 內的 LLM inference。
- 把 MCP Inspector 或 `skills-ref` 當 production dependency。

### 3.5 v1 後候選

- descriptor inference agent。
- signed publisher／artifact provenance。
- process lease 與 safe automatic GC。
- remote MCP transport。
- trusted installed Python entry-point plugins。
- watcher／debounce。

---

## 4. 不可破壞的 invariants

### 4.1 State 與 transaction

1. 一個 turn 只使用一個 realized generation。
2. candidate 未完整建好前不得改 current applied 或 session runtime pointer。
3. durable commit 失敗時 memory、active Skill、citation service 與 SourceRefs 全部不變。
4. durable commit 成功但 process 在 pointer swap 前終止時，startup 可從 applied 重建 realized。
5. 同一 state root 的 durable commit 使用 SQLite compare-and-swap。
6. SQLite transaction 與 session runtime lock 內不得 copy、hash raw source、probe、compile、等待 input、跑 LLM 或做 network I/O。
7. transaction 只比較 prepare 階段已產生的 immutable candidate hashes、scan token、approval binding 與 expected generation。
8. raw source 在 snapshot 最後驗證後再變動，只形成下一次 desired drift；不破壞已完成 snapshot。

### 4.2 Scan 與 delete

9. 每個 configured root 都有 expected root identity。
10. 只有 `status == complete`、observed identity 等於 expected identity、沒有 fatal traversal error 且 deletion policy 授權時，absence 才能產生 delete。
11. `partial` 或 `fatal` root 對該 root 的 applied members 一律 zero-delete。
12. root missing、permission denied、I/O interruption、mount offline、identity changed、scanner exception 都不得刪除任何既有 member。
13. root identity mismatch 未經 explicit `adopt-root` 前，不得套用該 root 的 add、update 或 delete。
14. workspace/global 同 ID 或 casefold ID collision 不使用 precedence；candidate 必須 fail closed。

### 4.3 Source 與 capability

15. raw user-writable drop-in 永遠不直接成為 runtime source。
16. unsealed、unstable、malformed、oversize 或 quota-exceeding bundle 不得 apply。
17. content hash 只代表 identity 與 integrity，不代表 publisher authenticity。
18. Skill `allowed-tools`、host manifest、MCPB manifest 與 policy overlay 都是不受信任的 capability request，不是批准。
19. Skill scripts 不會因 discovery 或 activation 被 host 自動執行；其內容仍可能影響模型，因此不能描述成 capability-free。
20. drop-in Skill 不得要求 management tool、citation private tool 或未標記為 public requestable 的 host tool。
21. normal reconcile 不執行 LLM。

### 4.4 Active Skill

22. inactive Skill valid update 只更新 catalog，不自動 activate。
23. active Skill 的 prompt body、capability set、task modes 或 runtime resource closure 變更時，提交新版並 deactivate；必須 explicit reactivation。
24. 只有 catalog-only metadata 變更且 runtime hash 完全相同時，active runtime 才可維持。
25. invalid update 保留舊 applied snapshot 與舊 active runtime。
26. intentional delete 可提交，但 active Skill 必須在同一 runtime transition 明確 deactivate。
27. `--yes` 不會自動重新啟用被更新而 deactivated 的 Skill。
28. citation teardown 只在 durable commit 與 runtime pointer swap 都成功後執行。

### 4.5 Tool 與 graph

29. tool identity 包含 owner；name 不是唯一 authority。
30. raw name 與 casefold name 在完整 universe 中唯一。
31. model binding、dynamic availability、prompt access 與 `PolicyToolNode` 來自同一 realized snapshot。
32. management mutation tools 永遠不進 public catalog 或 main graph。
33. graph signature 在 bind／compile 前計算；相同 signature 必須重用現有 graph。

### 4.6 MCP

34. drop-in MCP 禁止 shell 字串拼接。
35. probe 與 runtime realization 都必須綁 exact executable/runtime closure。
36. probe approval 與 surface approval 分開；surface 未批准前不得進 main graph。
37. realization session 必須重新 initialize、list tools 並比對 exact surface hash。
38. host 持有 explicit `ClientSession`；adapter 不得自行 spawn production process。
39. timeout、cancel、delete、generation swap 與 CLI shutdown 後不得留下 host 已知 orphan process。
40. stdout frame、stderr、tool count、schema、result 與 diagnostics 都有 hard bound。
41. `tools/list_changed` 或 surface drift 立即使該 MCP fail closed；未重新批准前不得繼續 call 或 exposure。
42. `--no-mcp` session 不 probe、不 start、不 bind MCP。

### 4.7 Capacity 與 cleanup

43. committed snapshots v1 不自動 GC，但 state、staging、snapshot、generation、event 與 diagnostics 都有 hard quota。
44. copy／extract 前先做 capacity preflight；超限時不得留下半套 committed state。
45. final cleanup commit 前不得宣告 v1 完成。
46. cleanup gate 必須由 grep／AST assertion 驗證，不接受人工宣稱 legacy path 已不再使用。

---

## 5. Roots、scope、identity 與 migration

### 5.1 Physical roots

```text
A. shipped package resources
   importlib.resources.files("agent.resources.extensions")
   importlib.resources.files("skills")

B. workspace drop-in root
   <workspace>/.agent/extensions/

C. optional global drop-in root
   platformdirs.user_data_dir("research-agent", ...)/extensions/

D. workspace-scoped state root
   platformdirs.user_state_dir("research-agent", ...)/extensions/<workspace-id>/
```

state root 內容：

```text
registry.sqlite3
staging/
snapshots/<sha256>/
diagnostics/
backups/
```

規則：

- source checkout 與 installed wheel 使用相同 workspace/global scope。
- 明確 config override 優先於 default，但不能讓 shipped、drop-in、state roots alias。
- state root 必須是 local filesystem；不支援的 network filesystem fail closed。
- `.gitignore` 預設加入：

```gitignore
.agent/extensions/
.agent/workspace-id
```

- 使用者要 version-control extension 時，必須明確移除 ignore；runtime 不依 git tracking 判斷 trust。
- shipped root 的 `read-only` 是 host trust label，不是同一 OS user 下的 security boundary。

### 5.2 Root identity

```text
RootIdentity
  scope
  canonical_realpath
  filesystem_id
  file_id_or_inode
  workspace_id
```

- `extension_roots` table 保存 expected identity。
- 第一次啟用 root 時由 interactive `adopt-root` 或 headless policy document 建立 expected identity。
- canonical path 相同但 filesystem/file identity 改變時視為 identity mismatch。
- workspace 搬移不自動猜測 state ownership；使用 `migrate-state` 顯式把舊 workspace state 綁到新 workspace identity。
- optional global root 未設定時不列入 authoritative root set；已設定卻暫時不存在時為 `fatal`，不是 empty complete scan。

### 5.3 Scope collision

- built-in IDs 為保留名，drop-in 不得覆蓋。
- workspace 與 global root 可同時提供不同 IDs。
- workspace/global 同 ID 或 casefold ID 是 configuration error；不使用 shadowing 或 precedence。
- status 顯示每個 extension 的 `source_scope`、root identity 與 snapshot hash。

### 5.4 Legacy `skills_dir` migration

`AgentConfig.skills_dir` v1 改為 deprecated read-only import source：

- 不再直接成為 runtime authority。
- startup 偵測到 non-package legacy directory 時，status 顯示 `legacy_skills_pending_import`，不讓既有 Skills 無聲消失。
- `/Extension-Management import-legacy-skills [<path>]`：
  - dry-run 列出可匯入、collision、invalid UTF-8、unsupported metadata 與 capability request；
  - explicit confirmation 後把內容複製到 workspace Skill root；
  - 由 migration command 生成 `.extension-lock.json`；normal reconcile 永遠不替使用者重建 lock；
  - 不修改原 legacy directory；
  - 不自動 activate；
  - import event 與 source hash 寫入 audit。
- built-in `skills` package 直接由 package resource provider 載入，不走 legacy migration。

---

## 6. Bundle contract、scan 與 immutable snapshot

### 6.1 Workspace layout

Skill：

```text
.agent/extensions/skill/<id>/
├── .extension-lock.json
├── SKILL.md
├── manifest.yaml          # optional host extension
├── references/            # optional
├── assets/                # optional
└── scripts/               # optional; host不因發現而自動執行
```

MCP：

```text
.agent/extensions/mcp/<id>/
├── .extension-lock.json
├── <id>.mcpb
└── policy.yaml
```

`policy.yaml` 是 host policy request overlay，包含 family、requested exposure、timeouts、result limits 與 secret binding names；它不是 execution approval。

### 6.2 `.extension-lock.json`

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
    }
  ]
}
```

MCP wrapper 的 inventory 必須包含 `.mcpb` 與 `policy.yaml`。lock file 本身不列入 `files`。

### 6.3 Per-root scan model

```text
RootScanResult
  scope
  configured_path
  expected_root_identity
  observed_root_identity
  scan_token
  status: complete | partial | fatal
  items[]
  diagnostics[]

DesiredInventory
  roots[]
  items[]
  aggregate_token
  diagnostics[]
```

`scan_token` 由 root identity、canonical sorted item paths、file sizes、content hashes 與 scanner policy version產生。

### 6.4 Delete gate

```text
absence -> delete
only if:
  originating_root.status == complete
  AND observed_root_identity == expected_root_identity
  AND no fatal traversal error
  AND exact deletion set is authorized
  AND dependency closure permits the delete
```

以下一律 zero-delete：

- configured root 不存在；
- permission denied；
- mount、disk 或 removable media 暫時離線；
- traversal 中途失敗；
- scanner internal error；
- root identity 改變；
- lock/inventory 尚未完整讀完；
- delete set 未被 interactive confirmation 或 policy document exact 授權。

complete root 的 add/update 可與其他 partial root 的 zero-delete 結果共同形成 candidate，但仍須通過 dependency closure；不得因 partial root 而推導依賴項不存在。

### 6.5 Safe traversal

- paths 必須是 canonical POSIX-style relative paths。
- 拒絕 absolute path、`..`、空 segment、NUL、path length 超限、raw/casefold duplicate。
- 只接受 regular files 與 directories。
- 拒絕 symlink、junction/reparse escape、device、FIFO、socket。
- 在可偵測平台拒絕 `st_nlink > 1` 的 regular file。
- strict UTF-8 metadata；binary runtime artifacts 依 manifest 處理。
- inventory 列出的 file 必須存在且 size/hash 完全相符。
- bundle 不得有 lock 未列出的 regular file。
- scan 前後重新驗證 lock hash、root identity 與 inventory。

### 6.6 One-pass snapshot

```text
open no-follow FD
  -> fstat
  -> stream to staging
  -> 同時計算 SHA-256 與 byte count
  -> compare expected hash/size
  -> fsync file
  -> fsync staging directory
  -> write snapshot.json last
  -> fsync
  -> same-filesystem atomic publish
```

- 不先 hash source、再 copy、再讀 snapshot 做第三次完整掃描。
- source copy/hash 使用同一 pass。
- startup 對 committed snapshot 做後續 corruption verification。
- 相同 snapshot hash 已存在時先完整驗證再重用。
- `.partial` staging 不得被 runtime 讀取。

### 6.7 MCPB extraction safety

- archive hash 納入 snapshot identity。
- 使用 `jsonschema` 驗證 MCPB manifest safe subset。
- 拒絕 zip-slip、absolute path、`..`、duplicate entry、casefold duplicate、encrypted entry、symlink entry、special file、path length 超限。
- 限制 archive bytes、總解壓 bytes、單檔 bytes、檔案數與 compression ratio。
- extraction 只進 operation staging；驗證完成前不 publish。
- manifest entrypoint 必須落在 extracted snapshot。
- executable mode 依 host 固定規則設定；不盲信 archive permission bits。

---

## 7. Schema 與 validation policy

### 7.1 Extension ID

```regex
^[a-z0-9]+(?:-[a-z0-9]+)*$
```

- ASCII 長度 1–64。
- 不接受 leading/trailing hyphen 或連續 hyphen。
- folder name、lock id、Skill frontmatter name、MCPB/package id 與 policy id 必須完全相同。
- casefold 後跨 workspace/global scope 唯一。
- built-in Skill、slash command、MCP family、management tool 與 host reserved names 不得使用。

### 7.2 Agent Skills

必要：

- `SKILL.md`。
- strict UTF-8。
- YAML frontmatter `name`、`description`。
- `name` 等於 parent directory／extension ID。

`allowed-tools`：

- 依 Agent Skills 欄位語法解析。
- 只轉成 untrusted capability request。
- v1 只接受能映射到已知 MCP family 或 `public_skill_requestable=true` host tool 的條目。
- unknown syntax、private tool、management tool、`citation_workflow` 或無法唯一解析的項目直接 invalid。
- bundle 宣告不會自行產生 exposure 或 approval。

`manifest.yaml` host extension 可描述：

- task modes；
- required／optional MCP families；
- requested host tools；
- runtime references；
- warning thresholds。

`allowed-tools` 與 `manifest.yaml` capability request 取 canonical union；互相矛盾時 invalid。

scripts policy：

- discovery、apply、activation 都不自動執行 scripts。
- scripts 仍是 untrusted prompt-visible resources，可能誘導模型使用 global base tools或要求 bash approval。
- activation UI 必須顯示 scripts count、hash、requested capabilities 與 global base tool policy，不得標示為 capability-free。

production validator 使用本 repo 的 strict typed model；`skills-ref` 只在 dev/CI 作 differential oracle，不作 runtime dependency。

### 7.3 MCPB safe subset

允許：

- `stdio` transport。
- bundled native binary。
- bundled Node entrypoint與dependencies，使用 allowlisted host Node runtime。
- bundled Python entrypoint與dependencies／bundled venv。
- platform/runtime compatibility metadata。
- sensitive user configuration 的 env-name binding。

拒絕或保持 unsupported：

- UV-managed dependencies。
- npx、uvx 或任何 runtime fetch。
- package manager install。
- build scripts。
- HTTP／SSE／WebSocket。
- external mutable entrypoint。
- literal secrets。
- shell command string。
- manifest 要求的 runtime 不在 allowlist或無法 fingerprint。

MCPB manifest 中的 tools／prompts 只作 declared metadata；actual `tools/list` 才形成 surface candidate。

### 7.4 Internal normalized descriptor

```text
InternalNormalizedMCPDescriptor
  extension_key
  archive_hash
  snapshot_hash
  package_runtime
  entrypoint
  argv
  cwd
  env_bindings
  compatibility
  declared_surface

HostPolicyOverlay
  family
  requested_exposure
  init_timeout
  tool_call_timeout
  result_limit
  secret_binding_names
  approval_policy_version
```

internal descriptor 由 MCPB manifest 與 policy overlay deterministic 產生，不由 LLM 產生 authoritative command。

---

## 8. Durable store

### 8.1 SQLite settings

v1 固定：

```text
PRAGMA foreign_keys = ON
PRAGMA journal_mode = DELETE
PRAGMA synchronous = FULL
PRAGMA busy_timeout = 0
PRAGMA locking_mode = NORMAL
PRAGMA trusted_schema = OFF
PRAGMA application_id = 1163416653  -- 0x4558544D, "EXTM"
PRAGMA user_version = 1
```

- v1 不使用 WAL；更換 journal mode 必須另有跨 OS／filesystem benchmark與 recovery ADR。
- unknown newer `user_version` fail closed。
- startup 執行 `PRAGMA quick_check`。
- migration、explicit verify 或 quick-check failure 執行完整 `integrity_check`。
- migration 前使用 SQLite backup API 建立 fsynced backup；migration 失敗時保留原 DB 與 backup，不部分升版。
- DB permission 盡可能為 0600；Windows 記錄 ACL diagnostic。

### 8.2 Schema v1

```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE applied_generations (
    generation INTEGER PRIMARY KEY,
    parent_generation INTEGER NULL,
    manifest_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (parent_generation)
        REFERENCES applied_generations(generation)
);

CREATE TABLE registry_meta (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    workspace_id TEXT NOT NULL,
    workspace_root_hash TEXT NOT NULL,
    current_generation INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (current_generation)
        REFERENCES applied_generations(generation)
);

CREATE TABLE extension_roots (
    scope TEXT PRIMARY KEY
        CHECK (scope IN ('workspace', 'global')),
    configured_path_hash TEXT NOT NULL,
    expected_root_identity TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    adopted_at TEXT NOT NULL,
    last_complete_scan_token TEXT NULL
);

CREATE TABLE extension_objects (
    object_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('skill', 'mcp')),
    extension_id TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    normalized_descriptor_json TEXT NOT NULL,
    prompt_hash TEXT NULL,
    runtime_closure_hash TEXT NULL,
    tool_surface_hash TEXT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE approvals (
    binding_hash TEXT PRIMARY KEY,
    approval_type TEXT NOT NULL CHECK (
        approval_type IN (
            'skill_capability',
            'delete_set',
            'mcp_probe',
            'mcp_surface',
            'global_exposure',
            'root_adoption',
            'state_migration'
        )
    ),
    extension_kind TEXT NULL,
    extension_id TEXT NULL,
    scope TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    binding_json TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    source_document_hash TEXT NULL,
    revoked_at TEXT NULL
);

CREATE TABLE generation_members (
    generation INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('skill', 'mcp')),
    extension_id TEXT NOT NULL,
    object_hash TEXT NOT NULL,
    source_scope TEXT NOT NULL CHECK (source_scope IN ('built-in', 'workspace', 'global')),
    source_root_identity TEXT NOT NULL,
    skill_capability_approval_hash TEXT NULL,
    mcp_probe_approval_hash TEXT NULL,
    mcp_surface_approval_hash TEXT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (generation, kind, extension_id),
    FOREIGN KEY (generation)
        REFERENCES applied_generations(generation) ON DELETE RESTRICT,
    FOREIGN KEY (object_hash)
        REFERENCES extension_objects(object_hash) ON DELETE RESTRICT,
    FOREIGN KEY (skill_capability_approval_hash)
        REFERENCES approvals(binding_hash),
    FOREIGN KEY (mcp_probe_approval_hash)
        REFERENCES approvals(binding_hash),
    FOREIGN KEY (mcp_surface_approval_hash)
        REFERENCES approvals(binding_hash)
);

CREATE TABLE extension_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    generation INTEGER NULL,
    extension_kind TEXT NULL,
    extension_id TEXT NULL,
    sanitized_payload_json TEXT NOT NULL,
    FOREIGN KEY (generation)
        REFERENCES applied_generations(generation)
);

CREATE INDEX idx_generation_members_object
    ON generation_members(object_hash);
CREATE INDEX idx_generation_members_extension
    ON generation_members(kind, extension_id, generation);
CREATE INDEX idx_approvals_extension
    ON approvals(extension_kind, extension_id, approval_type, revoked_at);
CREATE INDEX idx_events_operation
    ON extension_events(operation_id, seq);
CREATE INDEX idx_events_extension
    ON extension_events(extension_kind, extension_id, seq);
```

規則：

- `extension_objects` content-addressed；大型 normalized descriptor 只存一次。
- generation 只保存 membership 與 approval references。
- revoked approval 保留 audit row，但不得再被新 generation 重用。
- generation 0 由 migration 建立，承接當時可重現的 built-in／legacy compatibility catalog。

### 8.3 Cross-process CAS

所有 process 使用相同鎖順序：

```text
process-local reconcile reservation
  -> session runtime lock
  -> SQLite BEGIN IMMEDIATE
```

transaction 內只檢查：

- expected current generation；
- expected session revision；
- prepared candidate aggregate scan token；
- prepared object/snapshot/manifest hashes；
- exact unrevoked approval hashes；
- candidate generation manifest hash。

stale 或 busy：

- rollback；
- memory 不變；
- 釋放 session lock；
- 回 typed `stale`／`busy`；
- 不在鎖內重跑昂貴 prepare。

---

## 9. Hard limits 與 capacity policy

v1 initial defaults 必須進 `AgentConfig`、status 與 tests；調整預設值需獨立 benchmark／compatibility說明。

| Limit | Default |
|---|---:|
| `max_bundle_archive_bytes` | 256 MiB |
| `max_bundle_unpacked_bytes` | 1 GiB |
| `max_single_file_bytes` | 128 MiB |
| `max_files_per_bundle` | 20,000 |
| `max_path_bytes` | 1,024 |
| `max_archive_compression_ratio` | 100 |
| `max_state_bytes` | 8 GiB |
| `max_staging_bytes` | 2 GiB |
| `max_snapshots` | 2,048 |
| `max_generations` | 512 |
| `max_events` | 100,000 |
| `max_diagnostics_bytes` | 64 MiB |
| `max_startup_fallback_generations` | 16 |
| `max_mcp_stdout_frame_bytes` | 8 MiB |
| `max_mcp_stderr_bytes_per_session` | 1 MiB |
| `max_mcp_result_bytes` | 8 MiB |
| `max_mcp_tools` | 256 |
| `max_tool_description_bytes` | 16 KiB |
| `max_tool_schema_bytes` | 1 MiB |
| `max_tool_schema_depth` | 64 |

capacity preflight：

- 在 copy／extract 前計算 candidate worst-case bytes、file count、snapshot count、generation row 與 event row。
- content-addressed snapshot 已存在時可扣除可驗證的重用 bytes。
- 超限回 `state_quota_exceeded`／`staging_quota_exceeded`，不寫一半再失敗。
- v1 不自動刪 committed snapshots、generations 或核心 audit events。
- quota 滿時 fail closed；status 必須顯示可釋放空間所需的 explicit maintenance／rollback資訊。

status 至少顯示：

```text
state bytes used / limit
staging bytes used / limit
snapshot count / limit
generation count / limit
event count / limit
largest snapshots
oldest retained generations
```

---

## 10. Approval model

### 10.1 Skill capability approval

binding 包含：

```text
extension key
source hash
snapshot hash
prompt hash
normalized manifest hash
allowed-tools/requested capability set
scripts/resources closure hash
host skill policy version
```

- prompt/resource-only且無 capability request 的 inactive Skill 可進 catalog，不自動 activate。
- capability-bearing Skill 首次 apply 或 capability set 變更需要 exact approval。
- `--yes` 只能重用完全相同且未 revoked 的 approval。

### 10.2 Delete authorization

binding 包含：

```text
expected applied generation
root scope + expected root identity
complete scan token
sorted exact deletion set
dependency transition summary
delete policy version
```

- TTY apply 顯示 exact delete set 後取得一次性 authorization。
- non-TTY 必須由 exact policy document 授權。
- `--yes` 不建立首次 delete authorization。

### 10.3 MCP probe execution approval

probe 前 binding 至少包含：

```text
extension key
MCPB archive hash
snapshot hash
normalized descriptor hash
entrypoint/artifact hash
resolved executable realpath
resolved executable content hash or stable file identity
runtime name + exact version
OS + architecture
argv + cwd
env source names and source types
non-secret runtime configuration value hashes
host execution policy version
transport limit policy version
requested exposure
```

- secret values永不寫入 DB 或 approval hash；只保存 env name、required flag與 source type。
- executable path、runtime version、platform、artifact、argv、cwd、env source set或非 secret config改變，舊 probe approval失效。
- probe approval只允許 isolated initialize／list-tools probe，不批准 main graph exposure。

### 10.4 MCP surface approval

probe 後 binding 包含：

```text
probe binding hash
tool names
description hashes
input schema hashes
output schema hashes
annotations hashes
side-effect classifications
family
requested + approved exposure
tool-surface policy version
```

- global exposure 使用獨立 approval scope。
- actual surface 與 MCPB declared surface 不一致時，以 actual surface作 candidate並顯示 drift。
- tool name、description、schema、annotation、classification、family 或 exposure任一改變，舊 surface approval失效。
- surface approval存在但 realization fingerprint不同時仍不得 exposure。

### 10.5 `approved_by` 與 headless provisioning

interactive actor：

```text
interactive:<os-user>@<hostname>
```

headless actor：

```text
policy:<document-sha256>:<os-user>@<hostname>
```

`import-policy`：

- 文件使用 strict schema，列出 exact binding hashes、scope、expiry/revocation policy與變更 ticket metadata。
- import 前檢查 regular file、no symlink、ownership／permission policy、strict UTF-8 與 content hash。
- import event 保存 document hash與 actor，不保存 secret。
- policy 不得用 wildcard 批准未來任意 executable、surface 或 delete set。

---

## 11. Skill catalog 與 active transition

### 11.1 Tool request policy

- local base tools 維持 global；Skill bundle不能自行增刪。
- drop-in Skill 只能 request：
  - 已存在的 MCP family；
  - `public_skill_requestable=true` 的 host tool。
- `citation_workflow` 只屬於 built-in citation Skill。
- management tools 永遠 private。
- required capability 缺失：candidate Skill blocked。
- optional capability 缺失：Skill 可進 catalog，但 availability 明確標示 unavailable。

### 11.2 Active transition table

| Candidate change | Commit policy |
|---|---|
| inactive Skill add | 更新 catalog；不自動 activate |
| inactive Skill valid update | 更新 catalog；不自動 activate |
| active Skill catalog-only metadata update，runtime hash不變 | 維持 active |
| active Skill prompt/capability/task-mode/resource closure更新 | 提交新版並 deactivate；要求 explicit reactivation |
| active Skill invalid update | 保留舊 applied snapshot與舊 active runtime |
| active Skill intentional delete | 提交 delete並 deactivate |
| 新版移除 current task mode | 提交新版並 deactivate；不自動選其他 mode |
| required MCP intentional delete | delete dependency並 deactivate dependent Skill |
| required MCP failed update | 保留舊 MCP與舊 dependent Skill closure |
| optional MCP失效／刪除 | Skill可維持 active，但重算access與availability |
| global MCP set改變 | 所有active access由同一candidate snapshot重算 |

### 11.3 Prompt 與 availability

- static system prompt 移除硬編碼 MCP catalog、`skills/<name>` path與「用 bash 列 skills」說明。
- dynamic availability block 由 current `SessionRuntimeState` render。
- picker、activation loader、model binding、tool policy與status都讀同一 public Skill catalog。
- active Skill content 只從 committed snapshot讀取。

---

## 12. MCP runtime architecture

### 12.1 SDK 與 host responsibility

採官方 MCP Python SDK v1：

- `StdioServerParameters`／`stdio_client`／`ClientSession`。
- SDK safe inherited environment subset。
- SDK stdin close、grace period、terminate、kill、wait/reap。
- SDK POSIX `start_new_session=True` 與 Windows process-tree cleanup。

host 只新增：

```text
bounded stdout JSON-RPC frame reader
bounded stderr ring/quota
host timeout and error classification
sanitized diagnostics
approval/runtime fingerprint verification
surface hash verification
session generation ownership
```

如果 SDK public API 無法加入 hard frame bound：

1. 先提出 upstream hook或patch；
2. 仍不可行時，實作最小 transport adapter；
3. 不複製 SDK 已有的跨平台 lifecycle。

### 12.2 Explicit session ownership

production path：

```text
Host MCP runtime
  -> resolve exact runtime fingerprint
  -> create SDK stdio transport
  -> create initialized ClientSession
  -> list tools and verify exact surface
  -> pass explicit ClientSession to langchain_mcp_adapters
  -> retain session under realized generation
```

禁止：

```text
connection dict
  -> adapter自行create_session/spawn
```

adapter 只負責 MCP tool 到 LangChain tool 的 conversion；host 不重寫 conversion。

### 12.3 Probe、approval 與 realization

```text
1. validate MCPB + policy overlay
2. create immutable snapshot
3. compute exact probe binding
4. require probe approval
5. open isolated probe session
6. initialize + tools/list
7. validate limits/collision and compute surface binding
8. close probe session
9. require surface approval
10. open generation-scoped runtime session
11. initialize + tools/list again
12. compare exact runtime fingerprint + surface hash
13. only then expose tools and build graph
```

runtime session 與 probe session不是同一 process，因此步驟 10–12不可省略。

### 12.4 Generation-scoped persistent session

v1 target：

- 每個 realized MCP owner最多一個 lazy generation-scoped persistent `ClientSession`。
- graph exposure前已完成 exact surface revalidation。
- turn lock保證 generation swap時本 process沒有 in-flight turn。
- swap後新 turn只取得新 generation session。
- 舊 generation sessions在 pointer swap後關閉；close failure記錄bounded diagnostic，不回滾已commit generation。
- CLI `aclose()` idempotent關閉所有sessions。

Commit 8 benchmark若證明 persistent session無法符合 hard bounds或cleanup contract，唯一允許的替代是 per-call session，且每次 invocation 都必須 initialize、`tools/list`、比對 exact surface hash後才call；不得直接沿用 probe結果。

### 12.5 Surface change

- 支援並監聽 `tools/list_changed` notification。
- 收到 notification 立即把 owner標為 surface-drifted，拒絕後續call。
- 下一個安全 mutation window移除其 realized exposure或保持舊 graph但由PolicyToolNode fail closed。
- 重新probe與surface approval前不得曝光新／改變的tools。

### 12.6 Legacy Web Search／GitHub

- 兩者改為 host-owned normalized descriptors，與 drop-in 共用 tool catalog、session ownership、limits與close path。
- Web Search維持 global exposure。
- GitHub維持 skill-scoped exposure。
- legacy env/config resolver可保留，但只輸出 normalized host descriptor。
- `/bin/sh -c`、`grep` stdout pipeline與 one-shot live loader 必須在 cleanup commit刪除。

### 12.7 Tool surface validation

probe與realization都檢查：

- tool count；
- name格式、長度、raw/casefold collision；
- description bytes、control characters；
- input/output schema bytes與depth；
- annotations；
- side-effect classification；
- result bytes；
- owner/family/exposure一致；
- local／MCP／built-in／management全universe collision。

任一超限、collision或drift使 candidate fail closed；failed update保留LKG closure。

---

## 13. Runtime、graph 與 commit protocol

### 13.1 Runtime models

```text
ToolIdentity
  owner_kind: base | builtin_skill | mcp | management
  owner_id
  name
  family
  exposure: global | skill | private
  requestable_by_public_skill
  description_hash
  input_schema_hash
  output_schema_hash
  annotations_hash
  implementation_kind

ExtensionRuntimeSnapshot
  realized_generation
  applied_generation
  tool_catalog
  public_skill_catalog
  mcp_families
  global_mcp_families
  graph
  dynamic_availability
  mcp_sessions
  realization_diagnostics
  graph_signature

SessionRuntimeState
  revision
  extensions
  active_skill_runtime
  active_skill_extension_generation
```

`AppliedGeneration`與runtime snapshot都不保存secret value。

### 13.2 Unified mutation lock

以下都必須取得同一 session runtime lock：

- `turn_outcome()`完整turn；
- `/skill` activate/deactivate；
- `/citation` activate/deactivate；
- extension runtime commit；
- rollback realization；
- 其他會改 active Skill 或 tool universe 的操作。

prepare 全在 lock 外：

- scan；
- snapshot copy／MCPB extract；
- validation；
- approval interaction；
- MCP probe；
- runtime fingerprint；
- tool surface；
- candidate session；
- dependency closure；
- graph signature／graph build；
- active transition candidate。

### 13.3 Graph signature before compile

```text
normalize final ToolCatalog
compute precompile GraphSignature
if signature == current.graph_signature:
    reuse graph and model bindings
else:
    bind tools
    build PolicyToolNode
    compile graph
```

signature 包含真正影響 compile/binding 的內容：

- model ID/config；
- tool owner/name/description/schema/annotation hashes；
- model binding policy；
- `PolicyToolNode` policy version；
- graph policy version。

通常不需重建 graph：

- inactive prompt-only Skill add/update；
- Skill catalog description change；
- diagnostics、approval metadata、quota status變更；
- active Skill被deactivate且tool universe不變。

### 13.4 Commit protocol

```text
1. 取得process-local reconcile reservation。
2. 讀expected applied generation、session revision、root identities。
3. 執行per-root scan並產生complete/partial/fatal結果。
4. 以one-pass copy/hash建立immutable snapshots。
5. validate Skill／MCPB／policy與dependency closure。
6. 取得或重用exact approvals。
7. MCP項目完成probe、surface candidate與candidate runtime session。
8. 建立final ToolCatalog、precompile signature、必要時compile graph。
9. 建立active Skill transition candidate。
10. 產生candidate aggregate scan token、object hashes與manifest hash。
11. 取得session runtime lock；等待既有turn完成。
12. 確認session revision、active Skill、task mode與expected root adoption未變。
13. SQLite BEGIN IMMEDIATE；busy fail-fast。
14. 只比較prepared hashes/token、current generation與unrevoked approvals；不重讀raw filesystem。
15. insert extension_objects、generation、members、audit並更新current。
16. COMMIT SQLite。
17. 在無await且cancellation-shielded區段單一assign SessionRuntimeState pointer。
18. 記錄process realized generation。
19. 釋放session lock。
20. 關閉舊generation sessions並執行必要citation teardown。
21. 回傳applied/realized generation與typed report。
```

失敗處理：

- 步驟 1–10 失敗：current DB與memory不變；關閉candidate sessions；staging按規則保留或清理。
- 步驟 13–16 失敗：rollback；memory不變；candidate sessions關閉。
- 步驟 16後、17前process crash：durable applied已更新；該process尚未realize；startup重建。
- 步驟 17後舊session close失敗：新runtime維持；記錄diagnostic並在`aclose()`重試，不回滾generation。

---

## 14. Dependency closure、startup 與 LKG

### 14.1 Dependency graph

```text
Skill -> required MCP families
Skill -> optional MCP families
Built-in Skill -> private host tools
MCP family -> exactly one owner
```

每個 connected required closure只能採其中一種結果：

- all-new；
- all-old LKG；
- intentional delete + dependent deactivate；
- blocked/quarantined。

- failed MCP update不能讓dependent Skill切到只相容新版的bundle。
- intentional delete與failed update不同：delete可提交並deactivate；failed update保留舊closure。
- optional edge不阻止Skill applied，但必須重算realized access與availability。

### 14.2 Startup realization

```text
1. open registry and apply exact PRAGMAs
2. quick_check; migrate with backup if needed
3. read current applied generation
4. verify manifest and referenced snapshots
5. if current corrupt, search at most max_startup_fallback_generations valid ancestors
6. do not silently change durable current when using realized fallback
7. realize approved MCP items unless --no-mcp
8. each runtime session revalidates fingerprint + exact surface
9. unavailable MCP becomes applied_but_unavailable
10. build/reuse graph
11. start with inactive Skill
```

- 單一MCP unavailable不拖垮CLI。
- required dependent Skill不自動activate。
- fallback chain有hard bound，避免 startup讀取無限歷史bytes。
- explicit rollback建立一個新的 committed generation，membership指向選定舊objects；不改寫歷史generation。

---

## 15. `/Extension-Management` UX

### 15.1 Commands

```text
/Extension-Management
/Extension-Management --dry-run
/Extension-Management status [--verify]
/Extension-Management apply
/Extension-Management apply --yes
/Extension-Management approvals
/Extension-Management approve <binding-hash>
/Extension-Management revoke <binding-hash>
/Extension-Management import-policy <path>
/Extension-Management import-legacy-skills [<path>]
/Extension-Management adopt-root <workspace|global>
/Extension-Management migrate-state <old-workspace-id>
/Extension-Management rollback <generation>
```

語義：

- 無參數：scan、顯示diff；TTY可逐項批准並apply；non-TTY不讀input。
- `--dry-run`：scan、validate、dependency analysis、quota preflight；不probe、不新增approval、不commit。
- `status`：host-only read path；不跑LLM、不probe。
- `status --verify`：執行DB full integrity check與committed snapshot verification；仍不啟動MCP。
- `apply`：只提交可完整驗證且已取得必要approval的closure。
- `apply --yes`：只重用existing exact approvals；不建立首次Skill capability、delete、MCP probe、surface或global exposure approval。
- `approve`：只批准status/apply已產生且可完整顯示的exact binding。
- `revoke`：保留audit，後續generation不得重用；若目前realized依賴該approval，下一安全mutation window fail closed並顯示需reconcile。
- `import-policy`：headless exact provisioning，不接受wildcard future approval。
- `rollback`：建立新generation，不直接移動historical pointer。

### 15.2 Non-TTY

- stdin非TTY時不得呼叫`input()`。
- pending binding保持`pending_approval`。
- approval cancel是零mutation outcome。
- `--no-mcp`下：
  - status/scan仍顯示desired/applied MCP；
  - 不probe、不start、不bind；
  - 新／更新MCP維持pending；
  - independent Skill-only安全closure仍可commit。

### 15.3 Result model

```text
ExtensionReconcileReport
  operation_id
  root_scan_results[]
  desired_scan_token
  applied_before
  applied_after
  realized_before
  realized_after
  items[]
  approval_bindings[]
  active_skill_transition
  runtime_swap_status
  capacity_status
  diagnostics[]
```

item outcome 至少包含：

- `applied`
- `unchanged`
- `pending_approval`
- `incomplete_scan`
- `zero_delete_guarded`
- `unsealed`
- `invalid`
- `unsupported`
- `quota_exceeded`
- `quarantined`
- `kept_last_known_good`
- `removed`
- `deactivated_for_update`
- `deactivated_dependency`
- `applied_but_unavailable`
- `surface_drift`
- `busy`
- `stale`

只有 parser bug、unrecoverable DB corruption或programming invariant breach轉internal error；預期policy／validation結果使用typed report。

### 15.4 Routing

- canonical command為`extension-management`；既有casefold lookup使大小寫版本可命中。
- command local執行，不使用`followup_input`。
- 不寫入ordinary chat history，不呼叫`session.turn()`。
- help/completion由同一registry產生。

---

## 16. 模組與檔案邊界

### 16.1 先抽共用 storage

新增：

```text
app/agent/storage/__init__.py
app/agent/storage/atomic.py
app/agent/storage/paths.py
app/agent/storage/content_store.py
app/agent/storage/permissions.py
```

從 citation storage 抽出：

- SHA-256 streaming；
- 0600 staged write；
- file／directory fsync；
- same-filesystem atomic publish；
- stale `.partial` handling；
- safe path／permission helpers。

citation 與 extensions 都依賴共用層；不得複製貼上近似實作。

### 16.2 Extension modules

```text
app/agent/extensions/__init__.py
app/agent/extensions/models.py
app/agent/extensions/paths.py
app/agent/extensions/discovery.py
app/agent/extensions/mcpb.py
app/agent/extensions/store.py
app/agent/extensions/approvals.py
app/agent/extensions/tool_catalog.py
app/agent/extensions/runtime.py
app/agent/extensions/mcp_runtime.py
app/agent/extensions/reconciler.py
app/agent/cli/extension_management.py
app/agent/resources/__init__.py
app/agent/resources/extensions/__init__.py
```

責任：

- `models.py`：IDs、scan、diff、generation、report、typed outcomes。
- `paths.py`：workspace/global/shipped/state roots、identity、migration。
- `discovery.py`：complete/partial/fatal scan、lock validation、one-pass snapshot。
- `mcpb.py`：MCPB safe subset、archive extraction、manifest validation。
- `store.py`：exact SQLite schema、migration、CAS、quota references、audit。
- `approvals.py`：binding canonicalization、approve/revoke/policy import。
- `tool_catalog.py`：owner-aware identity、collision、family/exposure policy。
- `runtime.py`：immutable state、graph signature、candidate transition。
- `mcp_runtime.py`：SDK transport limits、probe、explicit session、surface verification。
- `reconciler.py`：deterministic prepare、closure、commit、LKG。
- CLI module：args、TTY policy、rendering；不放business logic。

底層模組不得import CLI或`ChatSession`。

### 16.3 修改

| File | Change |
|---|---|
| `app/agent/config.py` | roots、limits、timeouts、legacy `skills_dir` deprecation |
| `app/agent/mcp.py` | host descriptor provider；移除live loader authority |
| `app/agent/skills/metadata.py` | built-in/applied catalog provider、strict schema |
| `app/agent/skills/runtime.py` | committed snapshot loader、task-mode semantics |
| `app/agent/tool_access.py` | owner/family/exposure/requestable policy |
| `app/agent/tools/inventory.py` | generation-0 catalog、移除silent duplicate |
| `app/agent/graph.py` | 接受single ToolCatalog、precompile signature |
| `app/agent/policy_tool_node.py` | same-generation identity enforcement |
| `app/agent/session.py` | single runtime pointer、unified lock、`aclose()`、dynamic prompt |
| `app/agent/fusion.py` | precise `GraphSignature` cache invalidation |
| `app/agent/cli/slash_commands.py` | register/delegate async management commands |
| `app/agent/cli/chat.py` | startup realization、finally `aclose()` |
| `app/skills/citation/storage.py` | 改用shared storage primitives |
| `app/pyproject.toml` | `mcp>=1.27,<2`、`platformdirs`、`jsonschema`、resources |
| `app/poetry.lock` | 同dependency commit更新，no unrelated drift |
| `.gitignore` | workspace extension root與workspace id |

### 16.4 Tests／fixtures

```text
app/tests/fake_mcp_server.py
app/tests/fixtures/mcpb/
app/tests/fixtures/skills/
app/tests/test_storage_atomic.py
app/tests/test_extension_models.py
app/tests/test_extension_discovery.py
app/tests/test_extension_mcpb.py
app/tests/test_extension_store.py
app/tests/test_extension_approvals.py
app/tests/test_extension_tool_catalog.py
app/tests/test_extension_runtime.py
app/tests/test_extension_mcp_runtime.py
app/tests/test_extension_reconciler.py
app/tests/test_extension_cli.py
app/tests/test_extension_e2e.py
```

MCP Inspector CLI與`skills-ref`只放dev/CI differential jobs，不在runtime執行臨時`npx`或network fetch。

---

## 17. 時間、空間與 performance gates

設：

- `F`：root files；
- `B`：root bytes；
- `E`：extensions；
- `T`：tools；
- `A`：dependency edges；
- `S`：serialized tool surface bytes；
- `G`：retained generations。

| Operation | Target | Requirement |
|---|---:|---|
| authoritative full scan | `Θ(F+B)` time, `Θ(F)` metadata | correctness不只信mtime |
| snapshot changed bytes | `Θ(B_changed)` time/staging | copy與hash同一pass |
| canonical manifest | `Θ(F log F)` worst case | producer/host canonical sort |
| extension diff | `Θ(E)` | hash map，禁止pairwise |
| tool collision | `Θ(T)` time/space | raw與casefold maps |
| dependency closure | `Θ(E+A)` | adjacency list，不需resolvelib |
| surface validation | `Θ(T+S)` | hard byte/depth limits |
| graph bind/compile | 約`Θ(T+S)` | signature相同直接reuse |
| generation commit | `Θ(E)` rows | descriptor objects去重 |
| metadata space | `Θ(unique objects + G×membership)` | hard quota |
| snapshot space | `Θ(retained bundle bytes)` | hard quota；v1不auto-GC |
| startup fallback | bounded | 最多檢查16代 |

performance-sensitive commit 必須記錄：

- full/no-op scan bytes、files、elapsed time；
- one-pass snapshot throughput與peak RSS；
- graph signature hit/miss與compile time；
- SQLite generation commit time；
- MCP cold/warm P50、P95；
- MCP peak RSS；
- 連續100 calls process/session churn；
- cancellation、orphan cleanup latency。

---

## 18. Failure-mode tests

每項都要有可重現測試、typed outcome與zero unintended mutation assertion。

### 18.1 Incomplete root

- missing root、permission denied、I/O interruption、mount identity change、scanner exception。
- outcome `partial|fatal`。
- applied members zero delete。
- complete independent root只可套用不依賴missing root的closure。

### 18.2 Copy in progress

- missing/extra/hash mismatch、lock前後變更。
- outcome `unsealed|unstable_copy`。
- 不publish snapshot，不改applied。

### 18.3 Active Skill update

- prompt body、allowed-tools、task mode、resource closure任一變更。
- 新版可applied，但active明確deactivate。
- 下一turn不使用新版prompt，直到使用者重新activate。
- invalid update維持舊runtime。

### 18.4 MCPB archive attack

- zip-slip、duplicate/casefold duplicate、symlink、encrypted entry、zip bomb、oversize、unsupported runtime。
- extraction不越界、不超quota、不publish。

### 18.5 MCP approval drift

- interpreter realpath/version、OS/arch、artifact、argv、cwd、env source、non-secret config變更。
- probe approval失效。
- tool description/schema/annotation/classification/exposure變更。
- surface approval失效。

### 18.6 Probe/runtime mismatch

- probe surface A、runtime session surface B。
- runtime session立即close，MCP不進graph，outcome `surface_drift`。

### 18.7 MCP hang/noise/flood/cancel/orphan

- no-newline stdout flood必須在frame limit終止。
- stderr ring bounded。
- initialize/list/call各自timeout。
- ignore cancel/terminate、spawn child/grandchild。
- terminate/kill/wait後PID消失。

### 18.8 Tool collision

- MCP/MCP、MCP/local、MCP/built-in、MCP/management、raw/casefold。
- 整個candidate graph fail closed。
- 不依load order選winner。

### 18.9 CAS/crash

- two-process concurrent apply只一方成功。
- crash before/after SQLite commit、before/after pointer swap。
- current/audit/member一致。
- memory不出現半套state。

### 18.10 Quota

- state/staging/snapshot/generation/event/diagnostic每一limit邊界。
- preflight超限不留下partial committed state。
- status正確顯示used/limit。

### 18.11 Legacy migration

- configured legacy `skills_dir`不直接進runtime。
- dry-run、collision、invalid、explicit import、source unchanged。
- migrated Skill同session可見但不自動activate。

### 18.12 Wheel

- build wheel、temp venv install、移除source path。
- `import agent`、`import skills.citation`。
- package resources可讀。
- workspace/global/state roots可用。
- `/Extension-Management status --no-mcp`可用。

---

## 19. Test matrix

### 19.1 Baseline/regression

- exact Python／Poetry versions。
- exact full pytest command與collected count。
- no unexplained skip/xfail。
- Web Search global、GitHub skill-scoped。
- citation activation/off/teardown/SourceRefs isolation。
- slash local routing。
- `--no-mcp`。
- normal/extended Fusion。

### 19.2 Discovery/filesystem

- empty configured root complete scan。
- configured root missing fatal scan。
- sealed add/update/delete/rename。
- delete authorization。
- symlink/junction/reparse/hardlink/special file。
- path/raw/casefold collision。
- Linux/Windows path behavior。
- one-pass copy/hash failure injection。

### 19.3 SQLite

- schema create、migration backup、unknown newer version。
- exact PRAGMAs。
- quick_check/integrity_check。
- `BEGIN IMMEDIATE` busy。
- stale generation。
- disk-full/permission failure。
- concurrent apply。
- descriptor object dedupe。
- approval revoke。

### 19.4 Skill

- official valid/invalid name vectors，包括連續hyphen拒絕。
- strict UTF-8。
- `allowed-tools` mapping與private rejection。
- same-session picker refresh。
- active deactivation on behavior update。
- invalid update LKG。
- task mode removed。
- required/optional dependency transitions。
- scripts不自動執行且UI顯示risk。
- `skills-ref` differential CI。

### 19.5 Tool/graph

- owner-aware uniqueness。
- model binding／availability／PolicyToolNode一致。
- forged old-generation call拒絕。
- precompile signature reuse。
- unrelated inactive Skill update不compile graph。

### 19.6 MCPB/MCP

- MCPB safe subset manifest vectors。
- archive security矩陣。
- exact runtime fingerprint。
- two-stage approval。
- explicit `ClientSession` adapter path。
- production path assertion：adapter不得收到connection dict。
- actual surface vs declared surface。
- list-changed fail closed。
- persistent session lifecycle。
- MCP Inspector只在pinned dev environment作oracle comparison。

### 19.7 CLI/recovery

- TTY/non-TTY × yes/cancel/no-mcp。
- approvals list/approve/revoke。
- exact policy import。
- root adopt/state migrate。
- rollback建立新generation。
- status不probe、不LLM。
- command不進history。
- applied/realized/fallback/capacity輸出。

---

## 20. Commit plan

每個 commit 都必須完整現有suite全綠，並符合第21節共同要求。

### Commit 0 — `test(runtime): record reproducible extension-management baseline`

內容：

- 記錄branch HEAD、Python／Poetry版本、OS matrix、lockfile hash。
- 記錄exact full-test command、collected count、pass/fail/skip/xfail。
- characterization：Skill、MCP、tool collision、citation、slash、`--no-mcp`、wheel。

Gate：

- baseline artifact可在CI重現。
- 不修改production behavior。

### Commit 1 — `refactor(storage): extract shared atomic content-store primitives`

內容：

- 新增`app/agent/storage/`。
- 從citation抽hash、fsync、staging、atomic publish、permissions、path helpers。
- citation改用共用層。

必須刪除：

- citation內已被shared layer取代的duplicate helper。

Gate：

- citation regression全綠。
- failure injection涵蓋write/fsync/rename。
- 尚不加入extension behavior。

### Commit 2 — `refactor(tools): introduce owner-aware catalog for generation zero`

內容：

- 建立generation-0 compatibility `ToolCatalog`。
- local、現有MCP、citation tool全部有owner identity。
- prompt、model binding、PolicyToolNode讀同一catalog。
- duplicate raw/casefold fail-fast。

必須刪除：

- silent first-wins／last-wins分支。

Gate：

- collision不可能進graph。
- existing exposure semantics全綠。

### Commit 3 — `feat(extensions): add scoped roots, strict schemas and hard limits`

內容：

- workspace/global/state/shipped roots。
- root identity models。
- Agent Skills strict ID/frontmatter/allowed-tools。
- MCPB safe-subset models與HostPolicyOverlay。
- numeric limits。
- `app/agent/resources/__init__.py`與resource package。
- `.gitignore`。
- `app/pyproject.toml`加入`mcp>=1.27,<2`、`platformdirs`、`jsonschema`。
- 同commit更新`app/poetry.lock`，no unrelated drift。

Gate：

- source/wheel resource lookup。
- workspace/global collision fail closed。
- official schema vectors/differential tests。

### Commit 4 — `feat(extensions): add authoritative scans and immutable snapshots`

內容：

- `complete|partial|fatal` per-root scan。
- zero-delete gate。
- lock validation、safe traversal、one-pass copy/hash。
- MCPB archive extraction safety。
- capacity preflight與snapshot store。

Gate：

- root missing/permission/mount/traversal error全部zero-delete。
- zip-slip/zip-bomb/symlink/oversize測試。
- no-op/full scan與snapshot benchmark。
- 不執行extension code。

### Commit 5 — `feat(extensions): add versioned SQLite registry and CAS commits`

內容：

- exact schema v1、PRAGMAs、migration backup。
- object dedupe、generations、members、roots、approvals、events。
- quotas與minimal read-only status。
- two-process CAS。

Gate：

- migration-from-previous-version test。
- unknown newer schema fail closed。
- concurrent commit只一方成功。
- transaction failure不留半套metadata。

### Commit 6 — `refactor(session): add immutable runtime state and unified mutation lock`

內容：

- `ExtensionRuntimeSnapshot`／`SessionRuntimeState`。
- single pointer、unified lock、async mutation API。
- dynamic prompt/availability。
- precompile `GraphSignature` reuse。
- `ChatSession.aclose()`。

必須刪除或停止作authority：

- `loaded_skills` picker authority。
- parallel live `extra_tools`／`mcp_families`／`web_search_tool_names` state。
- static skills/MCP catalog prompt。

Gate：

- turn generation isolation。
- failed candidate/durable commit不改session。
- citation teardown只在commit後。
- signature hit不compile。

### Commit 7 — `feat(skills): reconcile sealed skills in the same session`

內容：

- built-in＋applied public Skill catalog。
- same-session add/update/delete。
- active behavior update提交新版並deactivate。
- invalid update LKG。
- `allowed-tools` capability approval。
- legacy `skills_dir` import command。
- minimal apply/dry-run/status。

Gate：Milestone A acceptance。

- complete scan delete gate實際生效。
- picker同session refresh。
- active prompt update不直接接管下一turn。
- explicit reactivation後使用新snapshot。
- built wheel全綠。
- 不啟動第三方process。

### Commit 8 — `test(mcp): validate SDK transport limits and adapter ownership`

本commit不加入production hot-plug。

內容：

- MCPB fixtures與safe-subset importer spike。
- SDK lifecycle reuse matrix。
- bounded no-newline stdout frame feasibility。
- bounded stderr feasibility。
- explicit `ClientSession`傳入adapter。
- persistent vs per-call benchmark。
- POSIX/Windows cleanup tests。
- MCP Inspector pinned CI oracle。
- architecture decision record。

Gate：

- 第3.2節全部有可重現證據。
- 無production connection-dict ownership設計。
- hard frame bound不可行時，Milestone B維持blocked。

### Commit 9 — `feat(mcp): add exact-approved MCPB probing and surface validation`

內容：

- MCPB normalization。
- probe execution binding。
- isolated probe。
- surface binding與approval。
- runtime fingerprint。
- SDK-based bounded transport adapter。
- explicit session conversion path。

Gate：

- approval drift矩陣。
- probe/runtime surface mismatch fail closed。
- flood/hang/cancel/orphan測試。
- surface未批准不進main graph。

### Commit 10 — `feat(mcp): reconcile approved MCP runtimes with LKG recovery`

內容：

- generation-scoped persistent sessions。
- same-session add/update/delete。
- required dependency closure。
- list-changed fail closed。
- startup degraded realization。
- `--no-mcp`。
- legacy Web/GitHub normalized host descriptors。

Gate：Milestone B runtime acceptance。

- exact-approved MCPB同session CRUD。
- failed update保留LKG closure。
- global exposure無獨立approval時拒絕。
- shutdown/delete/swap無known orphan。
- cold/warm/100-call benchmark達到Commit 8定義門檻。

### Commit 11 — `feat(cli): add approvals, rollback and recovery operations`

內容：

- complete status/capacity。
- approvals list/approve/revoke。
- headless exact policy import。
- root adopt/state migration。
- rollback new-generation semantics。
- TTY/non-TTY UX。

Gate：

- `--yes`不建立任何首次高風險approval。
- wildcard policy拒絕。
- rollback不改寫歷史。
- command不進ordinary turn/history。

### Commit 12 — `refactor(extensions): remove legacy runtime paths and dual state`

必須刪除：

- `/bin/sh -c` MCP pipeline。
- `grep` stdout sanitizer。
- one-shot MCP loader作live runtime authority。
- adapter connection-dict production path。
- silent duplicate drop。
- `ChatSession.loaded_skills`作picker authority。
- parallel `mcp_families`／`web_search_tool_names`／`extra_tools` live truth。
- static `skills/<name>` catalog說明。
- 不走unified mutation lock的activate/deactivate API。

Legacy Web/GitHub只可保留normalized descriptor provider。

Gate：

- grep/AST assertions對上述symbol/path全部通過。
- source＋wheel＋OS matrix全綠。
- no compatibility field仍可改變live runtime。

### Commit 13 — `docs(extensions): document sealed hot-plug and recovery`

內容：

- README、guide、SKILLS_GUIDE。
- Skill/MCPB/policy/approval examples作parse tests。
- desired/applied/realized、root scan、quota、two-stage approval、rollback、recovery。
- MCP等同第三方code execution。
- 將`extension_management_review.md`移除或明確標為historical，不讓兩份計畫並列成authority。

Gate：

- docs examples與runtime schema一致。
- clean source checkout與clean wheel acceptance全綠。

---

## 21. 每個 commit 的共同硬性要求

1. title符合Conventional Commits。
2. 列出預期新增、修改、刪除的file與symbol。
3. 記錄exact test command與collected count。
4. collected count不得下降，除非commit明列刪除哪些tests及原因。
5. 不得新增未說明skip/xfail。
6. dependency commit必須同時更新`pyproject.toml`與`poetry.lock`，且無unrelated drift。
7. DB commit必須含migration與backup/recovery test。
8. filesystem commit必須含failure injection與zero-delete assertion。
9. MCP commit必須含memory/output limit、orphan PID、cancel與shutdown test。
10. performance-sensitive commit必須附scan、compile、cold/warm MCP benchmark。
11. 每個commit都要有backout／compatibility說明。
12. cleanup commit使用自動grep/AST assertion，不靠人工review。
13. full suite失敗時不得以只跑新增tests取代。
14. branch上的unrelated production變更不得被本計畫commit順手改寫。

---

## 22. 完成驗收標準

以下全部成立才算v1完成：

1. baseline可重現，Python／Poetry／OS／lock hash／collected count完整。
2. source checkout與wheel使用相同workspace/global scope。
3. package resources可讀，user/state roots可寫且不alias。
4. incomplete root永遠zero-delete。
5. delete只有complete scan＋exact authorization才發生。
6. sealed Skill same-session add/update/delete可用。
7. active behavior update提交新版後deactivate，不未批准接管下一turn。
8. invalid Skill update保留舊applied與舊runtime。
9. legacy `skills_dir`有清楚migration，不直接繞過sealed registry。
10. Skill ID拒絕連續hyphen；strict UTF-8與`allowed-tools` policy全綠。
11. scripts不被host自動執行，activation風險資訊完整。
12. state/staging/snapshot/generation/event/diagnostic都有hard quota與preflight。
13. SQLite exact schema/PRAGMA/migration/CAS全綠。
14. descriptor object content-addressed去重。
15. all-universe raw/casefold collision fail-fast。
16. graph signature在compile前計算，相同signature重用graph。
17. MCP canonical external format為MCPB safe subset。
18. MCP SDK lifecycle被重用，host沒有重寫完整process supervisor。
19. host持有explicit `ClientSession`，adapter production path不自行spawn。
20. MCP probe與surface分兩階段approval。
21. runtime session重新驗證runtime fingerprint與surface hash後才expose。
22. list-changed／surface drift fail closed。
23. MCP hang、flood、cancel、delete、swap、shutdown無host已知orphan。
24. `--yes`不建立首次Skill capability、delete、MCP probe、surface或global exposure approval。
25. headless policy import只接受exact binding。
26. `--no-mcp`不probe、不start、不bind；status與Skill-only reconcile仍可用。
27. desired、applied、realized、fallback與capacity status清楚。
28. durable commit失敗時memory與citation state不變。
29. commit後pointer swap前crash可在startup重建。
30. Web Search global、GitHub skill-scoped、citation isolation regression全綠。
31. shell MCP pipeline、silent duplicate、dual state與static catalog prompt已由cleanup gate刪除。
32. docs examples由tests解析，review文件不再與正式計畫競爭authority。

---

## 23. Milestones 與停止點

### Milestone A — Skill hot refresh

完成 Commit 0–7：

- authoritative roots與zero-delete gate；
- sealed Skill same-session CRUD；
- active update deactivation與explicit reactivation；
- SQLite applied state、LKG、quota；
- owner-aware catalog與graph reuse；
- legacy migration；
- source/wheel support；
- 不包含第三方process執行。

Milestone A 完成後先做獨立驗收。

### MCP dependency spike

完成 Commit 8 並通過全部gate後，才解除Milestone B阻擋。scanner能看見`.mcpb`或能啟動fake server都不等於hot-plug完成。

### Milestone B — Exact-approved MCPB hot refresh

完成 Commit 9–11：

- two-stage exact approval；
- SDK-based bounded transport；
- explicit session ownership；
- runtime surface revalidation；
- same-session CRUD與LKG closure；
- approvals/revoke/policy/rollback UX。

### v1 completion

完成 Commit 12 cleanup與Commit 13 docs後，才可宣告v1完成。任何legacy live-authority path、unbounded state或未驗證surface仍存在時，停止release。
