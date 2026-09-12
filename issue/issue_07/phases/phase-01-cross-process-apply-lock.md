# Phase 01 — 跨程序 apply 互斥與可恢復性

## 目標

兩個獨立 process 使用同一 revision 的有效 preview 競爭同一 state root 時，
一方成功的變更不會被另一方覆蓋；lock conflict／error／process crash
不留下永久鎖，既有 apply／dry-run／restart 與錯誤契約維持。

## 來源與範圍

- [GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)。
- 原始 `issue/07-extension-apply-cross-process-race.md`。
- `app/agent/extensions/manager.py`：apply／_apply_locked。
- `app/agent/extensions/registry.py`：安裝／atomic writer。
- `app/tests/test_extension_manager.py`：fake model、selected scope、stale preview。
- `app/tests/test_extension_registry.py`、`test_extension_user_journey.py`、
  `test_desktop_service.py`、`test_desktop_protocol_contract.py`：回歸來源。

範圍只含一個 critical section、其生命週期與直接驗證。預期只改 manager.py
一個 production file；其餘是 PLANS 授權範圍內既有 test files。

## 非目標

GOALS 擁有完整 non-goals。本 phase 不改 registry writer 的持久化算法、
paths／models／入口 production code，不新增共用測試框架、production module、
延遲重試、timeout configuration 或 crash transaction rollback。

## 依賴與前置條件

- 無前置 phase；issue 06 不構成依賴。
- 使用者已明確核准 PLANS 指定的跨程序鎖方案並啟動計劃。
- Linux／Conda app runtime gate 通過，既有測試依賴可用，不安裝新 dependency。
- 確認 temp state root 在 Linux 本機 filesystem，測試不接觸真實 state／provider。
- **尚待確認：** 子程序測試啟動方式與 cleanup 能否在 pytest 下穩定工作。
  使用 stdlib multiprocessing 的明確 `spawn` context、module-level child target，
  child 內重建 config／manager／fake model／patch，不 pickle 既有 lambda。
  所有 child 在取得 apply lock 前啟動，避免 fork 繼承鎖造成錯誤 oracle。
- **尚待觀察：** 競爭失敗／commit 邊界／crash 的真實結果。
  按下列最小案例取得 evidence，不展開壓力測試或參數 sweep。

## 授權與停止條件

沿用 PLANS 的精確 envelope；新增不同同步方案、其他 production 修正、
public contract 變更或超額成本，先停止並提供直接證據。
本 phase 的測試 helper 只服務本檔案例，不升格為 persistent framework。
必要 check 失敗保持 In progress；缺決策／runtime／證據則 Blocked。

## 實作與驗證計劃

### Read-only preflight

1. 重新讀 applicable AGENTS、GOALS／PLANS／log、current diff，
   保留先前使用者對 issue 目錄的變動。
2. 核對 `apply` 至 `write_registry` 的 live 路徑、busy exception mapping、
   現存 regression tests；若原假設已改變，先修計劃。
3. 在 Linux shell：
   ```bash
   source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
   conda activate app
   cd /home/minervamuses/research-agent-workspace/app
   command -v python
   command -v poetry
   timeout 120s poetry run pytest tests/test_extension_manager.py tests/test_extension_registry.py -q
   ```
   這是日後 planned baseline，authoring 未執行。既有失敗先分類，不追修無關問題。

### Red：最小且可重現的 lost update

在既有 `test_extension_manager.py` 重用 fake model／Skill helper。
父程序準備兩個不同 Skill，兩個 child 共享 dropins／state／private Skill，
各以 `selected_skill_keys` 只 preview 自己的一個新增項目，確認都讀 revision N。
每個 child 回報具名 outcome／revision／例外，而非只傳 boolean。

- 父程序先啟動兩個 child，等待兩者 preview ready。
- 允許 A apply；在 A 的 `manager_module.write_registry` test-only wrapper
  中、呼叫真正 writer **之前**通知父程序並等待 release。
  此時 A 已完成 revision recheck 與自身 installation。
- 父程序收到 A ready 後才允許 B apply，保持 A 暫停直至 B 回報。
  舊實作會讓 B 成功寫入 N+1；再放行 A，A 用舊 snapshot 覆寫 B，
  兩者成功但 B entry 消失。新實作應令 B 立即回報 busy。
- 父程序放行 A、join children，檢查恰好一個成功、最終 N+1 有效 JSON、
  所有成功 entry／hash／installed bytes 保留，失敗方 entry 與 installed 副本不存在。
  最後一項可抓出「只在 write_registry 附近加鎖」導致先安裝敗方 bundle 的錯誤。

只用 Events／Pipe／Queue 傳遞進度，不以 sleep 製造勝負。
每個 wait／poll／get／join 有明確上限（例如 10 秒，可依實測 startup 合理微調），
finally 必須 release、terminate 尚存的測試 children 並 join／關閉 handles。
超時是測試失敗，不是業務 lock conflict。
**不可**讓兩個程序在鎖內共同等待 barrier：修正後第二個程序進不去會 deadlock。

先只新增此回歸並執行：
```bash
timeout 120s poetry run pytest tests/test_extension_manager.py -q -k cross_process
```
新增案例名稱統一包含 `cross_process`，這是預定命名而非聲稱檔內已有測試。
確認有實際 collected tests，失敗原因是兩次成功／lost update，不是 child import、
fixture、通信或清理錯誤；若未出現預期 red，不堆疊 speculative patch。

### Green：最小鎖修正

1. 保留 `_APPLY_LOCK` 非阻塞取得及既有 finally release。
2. 在 `manager.py` 同檔私有局部邏輯開啟固定 `.apply.lock`，
   state root 允許首次建立；以非截斷方式、適當私有權限如 0600 開啟 fd。
   fd 僅屬該次 apply，確保不傳給其他 process。
3. 用 `fcntl.flock(fd, LOCK_EX | LOCK_NB)`；在取得成功後才進入
   `_apply_locked` 的第一個 `load_registry`。
   持有至整個方法返回，包含 install、revision recheck、writer replace／directory fsync。
4. 鎖被占用時回傳既有 `ManagementError("another extension apply is already running")`。
   不把 open、權限、filesystem 不支援等其他錯誤都誤報為 busy；
   非衝突錯誤使用既有 ManagementError failure path，不能失敗後無鎖執行。
5. 正常、stale preview、其他 exception 都確保 fd 關閉與 thread lock release。
   固定 lock file 留存，不 unlink／replace、不寫 PID、不做 stale-file cleanup。
6. 不改 writer、registry schema 或 ApplyReport；preview／dry-run 不取得鎖或建 state。

重跑上述 focused regression。只有核心案例通過後，補足下列同一生命週期的必要案例；
不另設驗證 phase。無獨立 refactor 工作，只有為正確 cleanup 所需的局部整理。

### 必要補充案例

| 案例 | 最小觀察與通過條件 |
|---|---|
| 敗方恢復 | A 完成後，B 用原 preview 被 registry-changed 拒絕；重新 preview／核准後成功至 N+2，兩個 entry 與 bytes 都保留。不得自動重試舊 preview。 |
| 持鎖直到 directory fsync | 在 A 的 test-only `registry.fsync_directory(state_root)` 邊界暫停 writer；父程序令另一個獨立 process 對相同 lock file 嘗試非阻塞 flock，必須尚不可取得。放行 writer 後可取得。必要時補記 file fsync→replace→directory fsync 順序；不能僅憑 registry 已 N+1 推論鎖還在。 |
| 正常 exception 釋鎖 | 在鎖內第一個 revision read 或 writer-before-replace 注入一次 OSError／RegistryError，確認 ManagementError、無成功回報，registry 保留原值；移除 patch 後同 process 與另一個 process 都可再次 apply。重用局部 parametrization，不新增測試矩陣。 |
| 開鎖失敗 | 局部注入 lock-file open 或非 busy flock error，不能進入 `_apply_locked`；錯誤後原 thread lock 可再次使用。至少一個能區分「錯誤被吞掉後無鎖提交」的案例。 |
| Process crash 釋鎖 | A 取得真 apply lock 後在第一次 revision read 前用 child-local wrapper 回報 ready 並暫停；父程序終止 A，確認 exit／join 後，B 能使用尚未過期的 preview 正常 apply。測試只終止自身建立的 child；不刪 lock file。 |
| State root 隔離 | A process 持 root X，獨立 B process 對 root Y 的正常 apply 可完成；不要求改善同 process 的全域 thread lock。 |
| 入口與 read-only 保留 | CLI busy 仍是 SlashCommandError；Desktop busy 仍對應既有 BUSY_EXTENSION_OPERATION；既有 dry-run 不建立 state，成功 apply／restart 顯示與 schema 不變。缺 error assertion 時只在既有 test file 補一個局部 regression。 |

Fsync lock probe 只需獨立開啟 fd 的 process，不建立第三個正式服務或框架。
Crash test 證明「在此持鎖區間終止程序後可再取得鎖」，不是所有 crash points
都能復原已部分安裝的資料。既有 Desktop unclean-crash 測試不能代替 OS lock 證據。

### 最終 verification

所有命令在上述 Conda app／app cwd 執行，使用 pytest fake model。
以下依序執行；已觀察通過且沒有新變更／問題的 checks 不反覆重跑。

**Focused／相關回歸：**
```bash
timeout 180s poetry run pytest tests/test_extension_manager.py tests/test_extension_registry.py -q
```

**代表使用者流程／Skill 與 MCP 保留：**
```bash
timeout 180s poetry run pytest tests/test_extension_user_journey.py tests/test_extension_mcp.py tests/test_extension_skill_startup.py -q
```
該 user journey 使用現有 sandbox／fake 元件；若 live code 已使其連真 provider，
停止並先修訂驗證計劃。

**Desktop backend 與 protocol 既有契約：**
```bash
timeout 180s poetry run pytest tests/test_desktop_service.py tests/test_desktop_protocol_contract.py -q -k extension
```

**Near-end 完整 suite，只跑一次：**
```bash
timeout 540s poetry run pytest -q
git -C /home/minervamuses/research-agent-workspace diff --check
```
先根據當下證據判斷 suite 仍便宜／離線；若可能超過約十分鐘須先取得新授權。
Timeout、skipped 或 unavailable 不是 pass，第二次 full suite 需授權。
Full suite 的無關失敗單獨報告，不擴張修正；必要 coverage 缺口不得標 Complete。

不需 package build、真 GUI 手動雙視窗、壓力測試、provider call 或 GPU 工作。
若 fake 入口測試不足以辨識錯誤回報，補最小既有 backend test，不能直接宣稱 UI 驗收。

## Reliability／復原

鎖檔留存是正常狀態；process lock 必須隨 fd 的確切生命週期管理。
測試所有 child 必須有界回收，正常 CLI／backend 不新增子程序。
測試使用 tmp_path，失敗不改真實 registry。修復自身局部 diff 時保留 pre-existing work，
不使用 destructive Git reset／restore 或刪除使用者資料。
若 writer 已 replace 後失敗，不能宣稱 registry 回滾；本題保持既有語意，記錄具體結果。

## 驗收條件

- [ ] 原始最小競態在 Red 因 lost update／雙成功失敗，修正後同案例恰一成功。
- [ ] Registry revision／entry／hash／installed bytes 與每個 child 的成功結果一致；
      失敗方沒有安裝副作用，舊 preview 拒絕，重新 preview 後 N+2 保留兩者。
- [ ] 真鎖覆蓋最後 read 到 directory fsync；busy 無等待、error 不退回無鎖執行。
- [ ] exception 與 process termination 後可再次取得鎖，無永久鎖或需 unlink 的操作；
      測試結束無自身殘留 child。
- [ ] 不同 state root 的獨立 processes 不共用檔案鎖。
- [ ] CLI／Desktop 的既有錯誤／成功契約、dry-run／restart／MCP approval tests 通過。
- [ ] Required focused、代表流程、Desktop checks 與一次 full suite 有 evidence；
      任何必要豁免均有使用者明確決策，不能由作者自行略過。
- [ ] Diff 符合 scope、LF，沒有依賴或 public schema 變動，git diff --check 通過。

## 記錄的證據與交接

在 [build-log.md](../build-log.md) 記錄 exact commands、collected count、
pass／fail、每個 child outcome／exit、revision 與副本驗證、
exception／crash cleanup，以及明確未涵蓋的情境。
不要把測試設計或這份計劃當作已觀察 evidence。

重大發現才寫 `../context/phase-01-cross-process-apply-lock-context.md`；
實際 review 才寫 `../code_review/phase-01-cross-process-apply-lock-review.md`。
完成前以 fresh review／deterministic assertions 核對 actual diff 的鎖範圍及 cleanup，
不得只重述 builder narrative；不要求另建審查流程。

Acceptance 全部有證據才標 Complete，依 PLANS 核對整體完成後停止。
失敗或缺授權則保留 In progress／Blocked，報告最小下一步，不開始其他 issue。
