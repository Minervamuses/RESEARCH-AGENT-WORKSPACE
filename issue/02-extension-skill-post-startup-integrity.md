# Applied Extension Skill 在 Session 啟動後的完整性

## Issue 定位

- 類型：完整性邊界缺口。
- 優先度：中。
- 整併判定：不阻擋將 `repair` fast-forward 至 `main`；此完整性缺口保留為後續技術債。
- 主要適用情境：同一個 session 存活期間，installed bundle 被其他程序或手動操作修改。

## 專案背景

Extension Management 允許使用者把 Skill bundle 放到 drop-in 目錄，再經過 preview、確認與 apply，於下一次 CLI 啟動時載入。

主要資料位置：

- Drop-in desired state：`<dropin_root>/skill/<id>/`
- Private managed state：`<state_root>/`
- Applied registry：`<state_root>/registry.json`
- Content-addressed installed copy：`<state_root>/installed/skill/<id>/<source_hash>/`

主要元件：

- `app/agent/extensions/discovery.py`：掃描 bundle、拒絕 symlink／特殊檔案並計算 source hash。
- `app/agent/extensions/registry.py`：把核准 bundle 複製到 installed state，並原子寫入 registry。
- `app/agent/extensions/startup.py`：CLI 啟動時重新檢查 installed copy 的 hash，再建立 `SkillMetadata` catalog。
- `app/agent/session.py`：把 startup catalog 保存在 session，處理 `/skill` 啟用。
- `app/agent/skills/runtime.py`：啟用 Skill 時讀取 `SKILL.md`、`manifest.yaml` 與 pinned resources，產生 `SkillRuntime`。

設計承諾是：drop-in 的增改刪經過 apply 後，只在下一次 restart 生效；當前 session 不熱切換 extension。

## 原 annotation

> 這個我看不懂你在說什麼，講白話一點。

## 白話問題描述

目前流程像是「進門時檢查過包裹封條，但真正使用時只按照地址重新拿包裹，沒有再確認封條」：

1. Apply 把 Skill 安裝到 content-addressed installed path。
2. CLI 啟動時，`startup.py` 計算 hash 並確認 installed copy 等於 registry 記錄。
3. 驗證通過後，session catalog 主要保留 Skill 名稱、描述與 `SKILL.md` 路徑。
4. 使用者稍後輸入 `/skill <name>`。
5. `runtime.py` 依該路徑重新讀取目前磁碟上的 Skill、manifest 和 references。
6. 啟用階段沒有再次比較 registry `source_hash`。

因此，若 CLI 已啟動後 installed copy 被修改，下一次 `/skill` 可能直接讀到新內容。這個內容沒有重新 apply，也沒有 restart。

注意：修改原始 drop-in bundle 不會直接觸發此問題；問題目標是 private `state_root/installed/...` copy。

## 風險邊界

這不是遠端攻擊者可無條件利用的漏洞。能修改 installed state 的程序通常已經擁有同一個 OS 使用者的檔案權限。在單人、本機、沒有其他程序碰觸 state root 的情況下，發生機率低。

仍值得處理的原因：

- 行為違反「apply + restart 才生效」的完整性模型。
- 使用者或維護工具誤改 managed state 時不會 fail closed。
- 已核准的 MCP process 也以使用者權限執行；若 threat model 要求 extension 彼此隔離，不能假設 installed state 永遠不被碰觸。

## 重現方式

1. 使用測試用 Skill 執行 apply，讓 registry 指向 installed copy A。
2. 建立新 session，確認 startup 載入 A 並記錄 revision。
3. Session 保持存活，直接修改 installed A 的 `SKILL.md` 指令文字。
4. 呼叫 `session.activate_skill(<id>)` 或透過 CLI 執行 `/skill <id>`。
5. 檢查 active `SkillRuntime.instructions`。

現況預期：會看到修改後文字，而非啟動時驗證的文字。

也應分別測試修改：

- `manifest.yaml` 的工具權限或 task mode。
- pinned reference 的內容。

## 可選修法

### 方案 A：啟用時重新驗證 hash

`SkillMetadata` 或另一個 startup record 保留 registry `source_hash`；每次 activate 前重新執行 bundle fingerprint，比對失敗就拒絕啟用並要求 restart/re-apply。

優點：改動直接、仍可延後載入大型 instructions。缺點：每次啟用都需重新掃描檔案。

### 方案 B：啟動時建立不可變快照

Startup 驗證後立即讀入 instructions、validated manifest 與 pinned resources，session 後續只使用記憶體快照。

優點：最符合「此 session 固定在啟動 revision」。缺點：startup 成本與記憶體使用增加，需避免提前載入過大資源。

接手 Agent 應先確認既有 Skill 大小限制與 lazy-loading 需求，再選方案；不要同時維護兩個真相來源。

## 驗收條件

- Session 建立後修改 installed `SKILL.md`，下一次啟用不得採用修改內容。
- 修改 `manifest.yaml` 或 pinned reference 也得到同樣保護。
- 正常 apply → restart → activate 仍成功。
- 原始 drop-in 更新但尚未 apply 時，當前與新 session 都不應誤載入 desired state。
- 錯誤訊息應指出 applied bundle changed／restart or re-apply required，不輸出敏感檔案內容。

## 主要參考檔案

- `app/agent/extensions/discovery.py`
- `app/agent/extensions/registry.py`
- `app/agent/extensions/startup.py`
- `app/agent/extensions/models.py`
- `app/agent/skills/metadata.py`
- `app/agent/skills/runtime.py`
- `app/agent/session.py`
- `app/tests/test_extension_skill_startup.py`
- `app/tests/test_extension_user_journey.py`
