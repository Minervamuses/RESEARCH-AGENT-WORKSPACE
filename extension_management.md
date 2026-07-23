# Extension Management Drop-in 管理改造計畫

日期：2026-07-23

目標分支：repair_temp

狀態：v1 已依本計畫完成實作與自動測試；待補使用者角度的隔離沙盒驗收紀錄。

## 1. 這個計畫究竟要做什麼

一句話版本：

> 使用者把下載好的 Skill 或 MCP 資料夾放進指定目錄，執行 /Extension-Management，系統便掃描所有增改刪、依私有管理 Skill 產生計畫並寫入已套用狀態；重新啟動程式後，新工具才正式載入。

使用者流程固定為：

1. 把 Skill 或 MCP 資料夾放到 tool/skill 或 tool/mcp。
2. 啟動程式並執行 /Extension-Management。
3. Extension-Management agent 查看完整差異，依私有 Skill 說明每一項將如何處理。
4. Host 做格式與安全檢查，向使用者顯示需要確認的刪除與 MCP 執行命令。
5. 確認後，host 把通過檢查的內容複製成受管理版本並更新 registry。
6. 指令明確回報需要重啟。
7. 下次啟動時，現有的 Skill、MCP 與 graph 建立流程一次載入新版本。

這裡要解決的是「每次新增工具都要修改 host Python」，不是「程式永遠不能重啟」。因此 v1 不做同一個 ChatSession 內的 graph 替換、MCP process 熱切換或 active Skill 搬移。

~~~text
使用者 drop-in 資料夾
        │
        ▼
掃描 desired state 與目前 registry 的差異
        │
        ▼
fresh read 私有 Extension-Management Skill
        │
        ▼
隔離的管理 agent 產生完整 typed plan
        │
        ▼
host 驗證、顯示風險、取得確認
        │
        ▼
寫入受管理副本與單一 registry
        │
        ▼
restart required
        │
        ▼
下次啟動沿用既有載入流程建立一個正常 session
~~~

## 2. v1 邊界

### 2.1 v1 支援

- Prompt／resource 型 Skill。
- 已經可以直接執行的 stdio MCP。
- 有 extension.yaml 的 MCP。
- 沒有 extension.yaml、但能從常見 metadata 唯一判定啟動方式的 MCP。
- Skill／MCP 的 add、update、delete 與 unchanged。
- /Extension-Management、--dry-run 與 status。
- Source checkout 與 installed wheel。
- 既有 Web Search、GitHub、citation、academic-paper-writing 與 _prompt-master 行為。

### 2.2 v1 不支援

- 同一個執行中 session 的 Skill 或 MCP 熱切換。
- Background filesystem watcher。
- Local Tool 的動態 Python import／reload。
- npm install、pip install、build script 或自動下載相依套件。
- 從網路下載 repository 或 package。
- HTTP、SSE 或 WebSocket MCP transport。
- 自動執行 Skill bundle 裡的 scripts。
- 自動 rollback CLI、外掛簽章、市集或 dependency solver。
- 非互動批次批准高風險 MCP。

若某個 MCP 只是 source code，必須先 build 或 install 才能執行，v1 應清楚回報 unsupported；不得由 agent 臨場猜一套安裝流程。

## 3. 直接沿用專案現有能力

這次不是重寫工具系統。實作應沿著現有啟動流程加一層「已套用外掛來源」。

| 現有能力 | v1 怎麼用 |
|---|---|
| Skill discovery、manifest validation 與 runtime loader | 保留既有格式；啟動時再合併已套用 Skill |
| MCPServerSpec 與 langchain MCP adapter | 把已套用 MCP 轉成相同 spec，再走既有 loader |
| ChatSession 啟動前載入 MCP、之後建立 graph | 正好對應「重啟後生效」；只建立一次 graph |
| 現有 tool access 與 MCP family map | 沿用既有判定，只由 startup 多傳入哪些 family 是 global |
| Slash command registry | 新增一個本地 command handler |
| 現有 model 建立方式與 structured output | 用於一次性的 Extension-Management agent 呼叫 |
| Citation storage 已使用的 staged write、hash 與 atomic replace 作法 | 只參考已驗證的寫入模式；不重構 citation |

本計畫明確不新增：

- 新 LangGraph runtime framework。
- Session generation 或 mutable runtime pointer。
- MCP process supervisor。
- Built-in descriptor provider 抽象層。
- Package manager 或 build engine。
- SQLite、audit database 或 revision history 系統。
- 對 citation、fusion 或既有 graph transaction 的重構。

## 4. 目錄與資料所有權

Source checkout 提供以下使用者視圖：

~~~text
app/tool/
├── skill/<extension-id>/
│   ├── SKILL.md
│   ├── manifest.yaml       # optional
│   ├── references/        # optional
│   └── assets/            # optional
├── mcp/<extension-id>/
│   ├── extension.yaml     # 建議提供；部分 ready-to-run MCP 可省略
│   └── ...
├── local/
│   └── README.md          # v1 僅說明尚未支援
└── _internal/
    └── extension-management/
        └── SKILL.md
~~~

三種資料必須分開：

| 類型 | 誰可修改 | 用途 |
|---|---|---|
| shipped resource | 專案／package | 私有管理 Skill；read-only |
| user drop-in root | 使用者 | 想要的 desired state；管理器不改寫 |
| extension state root | host | registry、staging 與驗證後副本 |

路徑解析順序：

1. AgentConfig 明確指定的 drop-in root／state root。
2. Source checkout 使用 app/tool 作為 drop-in root。
3. Installed wheel 使用 platform user-data 目錄；不得寫入 site-packages。

既有 app/skills 不在 v1 搬家。啟動時把既有 built-in Skills 與已套用 drop-in Skills 合併即可。這避免為了目錄外觀去遷移 citation 等 code-backed bundle。

私有管理 Skill 由 package resource 定位，不從 user drop-in root 掃描。一般 /skill 永遠只看 public Skill catalog，因此無法列出或啟用它。

## 5. Bundle 最小契約

### 5.1 共通規則

- Folder name 就是 extension ID；只允許小寫英數與連字號。
- Skill name、MCP ID、MCP family 與 tool name 不得覆蓋 built-in 或其他已套用項。
- 禁止 path traversal、bundle 外的 resource／cwd／entrypoint、symlink escape 與特殊檔案。
- Fingerprint 以相對路徑、檔案大小、可執行位元與 SHA-256 計算，不信任 mtime；複製時保留可執行位元。
- 掃描與複製後 hash 不一致時，本項標記 source_changed，不套用。
- 設定合理的檔案數、單檔與 bundle 總大小上限。
- 管理器只改 extension state，不改寫或刪除 user drop-in folder。

### 5.2 Skill

沿用專案目前的 Skill 格式：

- SKILL.md 必須是 UTF-8，frontmatter 至少包含非空 name 與 description。
- Folder ID、frontmatter name 必須一致。
- Optional manifest.yaml 繼續使用既有 strict schema。
- Manifest 引用的 resource 必須存在且留在 bundle 內。
- scripts 只能當成普通資源；v1 不自動執行。
- Required MCP family 在 startup 實際載入的 MCP catalog 中不存在時，Skill 不得啟用。

### 5.3 MCP

建議的最小 extension.yaml：

~~~yaml
schema_version: 1
kind: mcp
id: example
family: example
scope: skill

runtime:
  transport: stdio
  command: node
  args: [server.js]
  cwd: .

environment:
  API_TOKEN:
    from_env: EXAMPLE_API_TOKEN
    required: true
~~~

規則：

- v1 只接受 stdio。
- command 必須能由 host 唯一解析；script、cwd 與相對 artifact 必須在驗證後副本內。
- args 必須是字串陣列，不接受 shell command string。
- Drop-in MCP 使用 direct command／argv；既有 Web Search 的 stdout sanitizer 保留為 legacy 特例。
- Secret 只能引用環境變數；registry 不保存 secret value。
- scope 可為 skill 或 global；global 必須在確認畫面中特別標示。
- 新增或修改 MCP 時，使用者批准的是 exact command binding：artifact hash、resolved command、argv、cwd、env 名稱、family 與 scope。
- 任一 binding 改變都必須重新批准。
- Startup 重新解析 command 後若不再符合已批准 binding，該 MCP 不執行，必須重新 apply。
- 啟動失敗只使該 MCP unavailable，不得拖垮整個 CLI。

缺少 extension.yaml 時，Extension-Management agent 可以查看有上限的 package.json、pyproject.toml、常見 MCP metadata 與 README，提出 normalized descriptor。Host 只在下列條件全部成立時接受：

1. 已存在可直接執行的 entrypoint。
2. 啟動方式只有一個合理答案。
3. 不需要 build、install 或 network fetch。
4. command、argv、cwd 與 env reference 都通過相同 deterministic validation。
5. 使用者看過 exact binding 並批准。

Agent 產生的 descriptor 只存入 registry；不回寫使用者資料夾。無法唯一判定時回報 quarantined，不猜測執行。

## 6. Extension-Management agent 與私有 Skill

### 6.1 私有 Skill

固定資源：

~~~text
app/tool/_internal/extension-management/SKILL.md
~~~

它只描述：

- 如何解讀 add、update、delete。
- Skill 與 MCP 的支援範圍。
- 缺少 MCP descriptor 時可檢查哪些 metadata。
- 哪些情況必須 blocked、quarantined 或要求批准。
- 最終報告應如何呈現。

每次 apply 或 dry-run 都重新讀取全文並驗證 UTF-8、frontmatter、檔案類型、大小與 hash。缺失或損壞時停止管理操作，不使用 cache，也不退回普通 agent 自由發揮。

status 不需要 LLM；即使私有 Skill 壞掉，仍可讀 registry 並顯示 manager_unavailable。

### 6.2 管理 agent

Extension-Management agent 在 v1 是一次性的隔離 structured-output 呼叫，不另外建一套 LangGraph。

Host 傳給它：

- Fresh private Skill 全文。
- 完整 add／update／delete／blocked 差異。
- 每一項的 ID、kind、hash、validation diagnostics。
- 經過大小限制的 Skill metadata 或 MCP 常見 metadata。

Agent 必須：

- 看見每一個變更，不得漏項、改 ID 或自行新增項目。
- 對每項輸出 action、摘要、理由、normalized MCP proposal 與 approval requirement。
- 把不確定項標成 blocked，不得猜測。

Agent 不取得：

- Shell、任意 file read、MCP、RAG、chat history 或主 session tools。
- Copy、delete、registry write、process start 或 session mutation 能力。

Agent 的輸出只是計畫。Host 仍會以固定程式碼驗證 schema、路徑、hash、collision 與 command binding；只有 host 可以寫入 applied state。

## 7. Registry 與受管理副本

v1 只需要一份 registry，不建立多層 current／revision manifest 系統：

~~~text
<state-root>/
├── registry.json
├── installed/
│   ├── skill/<id>/<source-hash>/...
│   └── mcp/<id>/<source-hash>/...
└── staging/<operation-id>/...
~~~

registry.json 最少保存：

- schema_version。
- 單調增加的 revision。
- 綁定的 canonical drop-in root path。
- 最近一次成功 apply 的 private Skill hash。
- 每個 extension 的 kind、ID、source hash 與 installed relative path。
- Skill normalized manifest。
- MCP normalized descriptor、command-binding hash 與批准結果。

更新方式：

1. 新內容先複製到同一 state root 下的 staging。
2. 複製後重新計算 hash。
3. 通過後把資料夾 rename 到以 source hash 命名的 installed path。
4. 所有選定項準備好後，以 temp file、0600 權限、fsync 與 atomic replace 一次更新 registry.json。
5. Registry 寫入失敗時，舊 registry 仍是唯一有效狀態；殘留 staging／未引用副本在下次管理時清理。

不需要另建 audit log、approval database、snapshot GC service 或 rollback engine。Invalid update 只要保留 registry 中原本的 installed path，就能維持上一個已套用版本。

同一個 CLI process 內只允許一個管理操作。寫入前再比較 registry revision；若已被其他 process 改變便中止並要求重新掃描。v1 明確不支援同一 workspace 由多個 CLI 同時 apply，也不為這個非核心情境自行實作 distributed lock。

## 8. Scan、diff 與刪除

| Desired tree 與 registry | 結果 |
|---|---|
| 新 ID 且有效 | add |
| 新 ID 但無效／未批准 | blocked、quarantined 或 pending approval |
| 同 ID hash 改變且有效 | update |
| 同 ID hash 改變但無效 | 保留舊 registry entry |
| Applied ID 確定已不存在 | delete |
| Folder 還在但 malformed／unreadable／複製中改變 | 不判 delete，保留舊 entry |
| Folder rename | 舊 ID delete + 新 ID add |
| Hash 相同 | unchanged；不複製、不重新批准 |
| Duplicate／casefold collision | 相關項全部 blocked |

刪除保護：

- Drop-in root 不存在、無法列舉或發生 root-level I/O error 時，本輪不產生任何 delete。
- Registry 保存 canonical drop-in root path；設定改到另一個 root 時，第一次 apply 必須明確確認重新綁定。
- 第一次成功 apply 才把 root path 寫入 registry；dry-run 不寫。
- 完整掃描到真正的空目錄可以產生全刪除計畫，但必須把所有刪除明確列出並再次確認。
- Delete 只從 registry 移除，不刪使用者 raw folder；未引用的 installed copy 可在成功 commit 後 best-effort 清理。

## 9. Slash command 行為

~~~text
/Extension-Management
/Extension-Management --dry-run
/Extension-Management status
~~~

Command lookup 沿用現有大小寫不敏感規則。

### 9.1 Apply

1. 讀取 registry 並掃描完整 drop-in root。
2. 建立 authoritative diff；任何 root-level 掃描錯誤先關閉 delete。
3. Fresh-load 私有 Skill。
4. 呼叫隔離管理 agent，要求對所有變更輸出 typed plan。
5. Host 驗證 coverage、bundle contract、collision 與 MCP command binding。
6. 顯示 exact plan；刪除、global MCP 與新增／變更 MCP execution 必須明確確認。
7. 把通過且獲准的 add／update 複製到 staging。
8. 再次核對 source hash、private Skill hash 與 registry revision。
9. Atomic 更新 registry；invalid update 仍引用舊副本，互不相關的有效項可以一起提交。
10. 回報 added／updated／removed／unchanged／blocked 與 restart_required=true。

Apply 階段不啟動 MCP、不重建 graph、不更換 active Skill，也不修改目前 session。MCP 第一次真正執行是在下次 startup。

### 9.2 Dry-run

- 執行 scan、private Skill fresh load、agent planning 與 host validation。
- 顯示相同 diff、blocked reason 與 approval requirements。
- 不建立 installed copy、不寫 registry、不刪資料、不啟動 MCP。

### 9.3 Status

- Host-only，不呼叫 LLM、不啟動 MCP。
- 顯示 desired、applied、running 三個狀態。
- Applied revision 與目前 session 的 running revision 不同時顯示 restart required。
- 顯示 startup 時各 MCP 的 loaded／applied_but_unavailable 狀態。
- 私有 Skill 無效時顯示 manager_unavailable，但仍顯示其他診斷。

## 10. 重新啟動時如何生效

ChatSession 建立前增加一個小型 startup loader：

1. 讀 registry.json，驗證 schema、installed path containment 與 content hash。
2. Registry 無效時 fail closed：只啟動既有 built-ins，並顯示 extension registry error。
3. 把既有 app/skills 與 registry 中的 applied Skills 合併成 public catalog。
4. 把 applied MCP descriptor 轉為現有 MCPServerSpec，與既有 Web Search／GitHub spec 合併，同時產生 global family set。
5. --no-mcp 時完全不啟動 applied MCP，但 Skills 與 status 仍可載入。
6. 逐一啟動 MCP；單一 MCP 缺 secret、command 不存在、timeout 或載入失敗時只跳過該 MCP。
7. 載入後檢查 tool-name collision；衝突的 drop-in MCP 整個排除，不讓現有 inventory 靜默選 winner。
8. 使用現有 extra tools、family map 與 Skill loader 建立一次 graph。
9. Session 記住 running revision 與 startup diagnostics，供 status 顯示。

Startup 不修改 registry，也不嘗試在失敗後自動發明修復方式。使用者修正 drop-in folder、再次執行管理命令並重啟即可。

## 11. 實際程式改動面

### 11.1 新增

| 路徑 | 責任 |
|---|---|
| app/agent/extensions/models.py | Scan、diff、plan、registry 與 report schema |
| app/agent/extensions/discovery.py | Strict scan、fingerprint、bundle validation |
| app/agent/extensions/registry.py | 單一 registry、staging copy 與 atomic write |
| app/agent/extensions/manager.py | Private Skill loader、隔離 agent 呼叫、host plan validation |
| app/agent/extensions/startup.py | 讀 applied state，產生 Skill catalog 與 MCP specs |
| app/agent/cli/extension_management.py | Command parsing、confirmation 與 report rendering |
| app/tool/_internal/extension-management/SKILL.md | 每次管理操作強制讀取的規則 |
| app/tool/local/README.md | 說明 Local Tool 延後 |

### 11.2 修改

| 路徑 | 最小改動 |
|---|---|
| app/agent/config.py | 增加可注入的 drop-in root、state root 與基本 size limits |
| app/agent/skills/metadata.py | 允許合併既有 root 與 startup 提供的 applied Skill metadata |
| app/agent/skills/runtime.py | 依 session catalog 載入選定 Skill，不再假設只有單一 skills_dir |
| app/agent/mcp.py | 接受 applied specs；drop-in 走 direct argv，legacy sanitizer 維持原狀 |
| app/agent/tool_access.py | 接受 startup 傳入的 global family set；未傳時維持只有 Web Search global |
| app/agent/graph.py | 把同一份 startup catalog／global family set 傳給既有權限判定；不加入 swap |
| app/agent/session.py | create 時先讀 startup catalog；保存 running revision／diagnostics |
| app/agent/cli/slash_commands.py | 註冊 Extension-Management 並委派獨立 handler |
| app/agent/cli/chat.py | 顯示 startup extension diagnostics |
| app/pyproject.toml | 將私有 Skill 與 README 包進 wheel |
| .gitignore | 忽略 source checkout 的使用者 drop-ins，但保留範例／README |
| README.md、guide.md、app/SKILLS_GUIDE.md | 說明目錄、支援格式、批准與重啟語義 |

不需要修改 fusion.py 或 citation runtime，也不建立新的 graph abstraction；現有 graph 只增加 startup 參數。

## 12. 落地順序

每個 commit 都只做一件可驗證的事。

### Commit 0 — 鎖定既有啟動行為

- 補 Skill discovery／activation、MCP loading、--no-mcp、Web Search global、GitHub skill-scoped、citation isolation 與 slash local routing 的 characterization tests。
- 不加入 Extension Management 行為。

### Commit 1 — Drop-in scan 與單一 registry

- 加入 paths、models、strict discovery、fingerprint、diff、staging 與 atomic registry。
- 完成 add／update／delete／unchanged、invalid update 保留舊 entry 與 zero-delete guard。
- 此階段不接 LLM、不接 session、不啟動 MCP。

### Commit 2 — 私有管理 Skill 與 slash command

- 加入 private Skill fresh loader。
- 以現有 model client 做一次性 structured management call。
- 加入 complete-plan coverage validation、互動確認、apply、dry-run 與 status。
- Apply 只寫 disk state，回報 restart required。

### Commit 3 — Skill 在下次啟動生效

- Startup 讀 registry，合併 built-in 與 applied Skill catalog。
- /skill picker、activation、task mode 與 resource loading 使用同一 catalog。
- 驗證目前 session 在 apply 後不變，重啟後才看到增改刪。

### Commit 4 — MCP 在下次啟動生效

- Applied descriptor 轉成既有 MCP specs。
- 加入 exact execution approval、direct argv/env/cwd、scope 對應、逐項 failure isolation 與 collision guard。
- 保留既有 Web Search／GitHub 相容行為。
- 不新增 probe process 或 process supervisor。

### Commit 5 — Packaging 與文件

- 打包 private Skill／README。
- 完成 source checkout 與 wheel 的 root resolution smoke test。
- 更新使用說明、範例 descriptor、限制與 migration 說明。

## 13. 測試矩陣

### 13.1 Discovery／registry

- 空 root、首次 apply、no-op、混合 add/update/delete、folder rename。
- Root missing、permission error、設定路徑改變與空 root 全刪除確認。
- Invalid add；invalid update 保留舊 registry entry。
- Duplicate、reserved ID、casefold collision、symlink、path escape、特殊檔案與容量上限。
- Scan 後 source 改變、copy 後 hash 不符、registry write failure 與 staging 殘留。
- Dry-run 對 registry 與 installed tree 都是零寫入。

### 13.2 Private manager

- Private Skill 不出現在 /skill，也不能按名稱啟用。
- 每次 apply／dry-run fresh read。
- 缺失、invalid UTF-8、frontmatter 錯誤或中途換檔時停止 mutation。
- Agent 漏項、改 ID／kind／hash、新增虛構項目或輸出 schema 錯誤時拒絕。
- Bundle 文字中的 prompt injection 不能取得 mutation 權限。
- Status 在 manager unavailable 時仍可讀。

### 13.3 Skill restart activation

- Apply add／update／delete 後，目前 session catalog 不變並顯示 restart required。
- 重啟後 picker、activation、task mode、manifest 與 resources 使用新 applied copy。
- Invalid update 重啟後仍使用舊 applied copy。
- Built-in Skills 不被 drop-in 覆蓋。

### 13.4 MCP restart activation

- Strict descriptor 與可唯一推導的 ready-to-run MCP。
- Ambiguous entrypoint、需要 build／install、non-stdio、literal secret 均 blocked。
- Approval 精確綁定 artifact、command、argv、cwd、env names、family 與 scope。
- Apply／dry-run 都不啟動 MCP；重啟後才啟動。
- Missing secret、command missing、timeout 與單一 server failure 不拖垮 CLI。
- MCP／MCP、MCP／built-in 與 family collision fail closed。
- --no-mcp 不啟動任何 drop-in process。
- Web Search、GitHub 的既有 scope 與 sanitizer 行為不變。

### 13.5 CLI／packaging

- Command 名稱大小寫不敏感；help 列出正確用法。
- Apply confirmation、cancel、dry-run、status 與 restart report。
- Command 不進普通 session.turn，也不寫入一般 chat history。
- Source checkout 與 installed wheel 都能定位 private Skill、drop-in root 與 state root。
- /init 不 ingest extension roots。

## 14. v1 完成驗收

以下全部成立才算落地：

1. 使用者放入合法 Skill，執行 /Extension-Management、確認並重啟後，可以由 /skill 找到並使用；不修改 host Python。
2. Skill 的 update 與 delete 走相同流程，apply 後目前 session 不變，重啟後正確生效。
3. 使用者放入 ready-to-run stdio MCP，管理畫面顯示 exact command，批准並重啟後工具可用；不修改 host Python。
4. 缺 descriptor 但可唯一判定的 MCP 能由 agent 產生 normalized proposal；無法唯一判定時保持 blocked。
5. Extension-Management agent 每次看見全部變更並強制讀取 private Skill，但沒有 filesystem mutation 或 process execution 權限。
6. Private Skill 永遠不出現在一般 /skill。
7. Raw drop-in folder 永遠不被管理器改寫或刪除。
8. Root scan 不完整時不會誤刪 applied extensions。
9. Apply 與 dry-run 不啟動任何 drop-in MCP；未批准的 MCP 在 startup 也不執行。
10. Invalid update 保留舊 applied copy；registry commit 失敗不破壞舊狀態。
11. 單一 MCP 啟動失敗不拖垮其他工具或 CLI。
12. Citation、Web Search、GitHub、既有 built-in Skills 與 --no-mcp regression tests 全部通過。
13. Source checkout 與 wheel install 都能完成 drop-in → apply → restart → use。

## 15. 明確延後

- 同一 session 的 Skill refresh。
- 同一 session 的 MCP swap 與舊 process draining。
- Background watcher。
- Local Tool plugin API。
- Build、install、dependency download 與 remote fetch。
- Remote MCP transport。
- Batch approval、rollback CLI、簽章與 extension marketplace。

將來若實作證明某種同 session refresh 可以用很小的改動完成，可以另開 v2；v1 不為尚未需要的熱切換預先建立複雜 runtime 架構。
