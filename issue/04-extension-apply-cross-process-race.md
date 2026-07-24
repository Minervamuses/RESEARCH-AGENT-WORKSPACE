# Extension apply 的跨 Process Lost Update

## Issue 定位

- 類型：併發狀態一致性。
- 優先度：低至中。
- 整併判定：不阻擋將 `repair` fast-forward 至 `main`；跨 process 併發修正保留為後續技術債。
- 成立條件：兩個獨立 CLI process 對同一個 extension state root 幾乎同時 apply。

## 專案背景

Extension Management 使用 `<state_root>/registry.json` 保存 applied state。Registry 含單調遞增的 `revision` 與目前所有 installed extensions。

Apply 流程位於 `app/agent/extensions/manager.py`：

1. Preview 讀取 registry revision N、掃描 drop-in，產生 plan。
2. 使用者核准後呼叫 `ExtensionManager.apply()`。
3. Apply 再讀一次 registry；若 revision 已變更就拒絕舊 preview。
4. 安裝或移除各 extension，建立新的 registry revision N+1。
5. `app/agent/extensions/registry.py` 以 temporary file + `os.replace()` 原子替換 `registry.json`。

程式另有 module-level `threading.Lock`，避免同一個 Python process 中兩個 apply 同時進入 critical section。

## 原 annotation

> 這個我也需要你講白話一點。

## 白話問題描述

兩個獨立終端中的 CLI 不共享 Python `threading.Lock`，因此可能發生：

1. CLI A 讀到 registry revision 5，準備加入 Skill A。
2. CLI B 也讀到 revision 5，準備加入 MCP B。
3. A 與 B 都在各自 process 內通過「revision 還是 5」的檢查。
4. A 寫入 revision 6，內容包含 Skill A，並回報成功。
5. B 接著也寫入 revision 6，但 B 的資料是從舊 revision 5 建立，可能只包含 MCP B。
6. B 最後 replace registry，A 已回報成功的 Skill A 從 registry 消失。

這稱為 lost update。Atomic replace 只保證 JSON 不會寫一半，不能保證兩個完整更新不互相覆蓋。

## 目前已有的保護

- 同一 process 的 `threading.Lock`。
- Apply 前的 revision recheck。
- Registry temporary file、fsync 與 atomic replace。
- Source hash 與 preview signature recheck。

缺少的是跨 process critical section：從最後一次讀取 revision、套用變更到 replace 完成，必須對所有 CLI 互斥。

## 風險邊界

- 單一 CLI 依序操作不會遇到。
- 一個 CLI 的兩個 thread 會被現有鎖擋住。
- 只有共享同一 state root 的不同 process 才有問題。
- 因目前主要使用情境是單人操作，這不是 branch 整併阻斷項。

## 建議修法

### 方案 A：跨 process 檔案鎖

在 state root 建立固定 lock file，從 apply 最後一次 revision check 前開始持鎖，直到 registry replace 與 directory fsync 完成才釋放。

需考慮：

- Linux/WSL 的 `flock` 或跨平台 lock library。
- Native Windows 的檔案鎖語意。
- Process crash 後鎖能否自動釋放。
- Lock timeout 與使用者可理解的錯誤訊息。

### 方案 B：真正的 compare-and-swap storage

只有目前 registry 仍符合預期 revision／content hash 時才提交新 registry；否則整次 apply 失敗並要求重新 preview。

單純在 replace 前再讀一次而沒有鎖仍有 race window，因此不能視為完整 CAS。

## 重現測試建議

使用 multiprocessing 建立兩個 process，共用 temporary state root：

1. 兩者都完成 revision N preview。
2. 以 barrier 讓兩者同時進入最後 revision check。
3. A 與 B 各套用不同 extension change。
4. 驗證最多一個 process 成功；另一個必須回報 registry changed／lock conflict。
5. 驗證最終 registry 是有效 JSON，且沒有任何已回報成功的更新消失。

## 驗收條件

- 相同 state root 的 concurrent apply 最多一個成功提交。
- 失敗方不回報 applied revision 成功。
- Crash／timeout 不留下永久死鎖。
- 單 process 正常 apply、dry-run 與 restart 流程不退化。
- Registry atomic durability 保證維持不變。

## 主要參考檔案

- `app/agent/extensions/manager.py`
- `app/agent/extensions/registry.py`
- `app/agent/extensions/models.py`
- `app/agent/extensions/paths.py`
- `app/tests/test_extension_manager.py`
- `app/tests/test_extension_registry.py`
- `app/tests/test_extension_user_journey.py`
