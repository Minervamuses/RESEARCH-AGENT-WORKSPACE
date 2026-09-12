# Issue 07 — Phase 01 actual diff review

2026-09-12（Asia/Taipei）。由執行 agent 對實際 diff 重新逐項審查，
不是獨立 sub-agent review；本 phase 未要求另派 reviewer。
範圍為 `4d7d8a5..9f9efc6`，並重讀 live manager、registry、CLI/desktop mapping
及新增的 process tests。測試結果與完整 suite 以 [build-log](../build-log.md) 為準。

結論：在既定 Linux 本機、配合相同鎖協議的 manager 範圍內，沒有需修正的 finding。

| 審查項目 | 實際 code / observed evidence |
|---|---|
| Critical section 起點 | `manager.py:464–482` 保留外層 threading lock，flock 成功後才進 `_apply_locked`；第一個 revision read 在 :503。Busy/open failure 沒有進入 installation 的路徑；EIO test 用 fail sentinel 驗證不進 transaction |
| Critical section 終點 | `return self._apply_locked(...)` 完整執行後才進 finally close；writer 仍在方法內。`registry.py:55–68` 未修改，temporary write → file fsync → replace → directory fsync 順序保留；獨立 process probe 在 directory fsync 邊界仍 locked，writer 返回後 available |
| 固定鎖及錯誤通道 | `.apply.lock` 以 O_CREAT/O_RDWR/O_CLOEXEC 開啟、0600，不 truncate/unlink/replace。BlockingIOError 才映射 busy，其餘 OSError/RegistryError/ValueError 沿用 ManagementError；無自動 retry/fallback。fd finally close，外層 finally release thread lock |
| Lost update oracle | A/B 各自 spawn/rebuild 真 manager 與 fake planner，先取得相同 revision 0 preview。僅 A 在 writer 前暫停，B 回報後才放行；沒有鎖內雙方 barrier 或 sleep。Red 確認雙 success 1 與 beta entry 遺失；Green 同案例只有 alpha success 1，beta 沒有 installed 副本 |
| Revision/bytes 恢復 | 原 beta preview 被拒絕，明確重新 preview 後 success 2；registry 2 兩 entry/hash/SKILL bytes 皆直接比對，沒有自動換 preview |
| Cleanup 與隔離 | 兩種鎖內 exception 保留原 registry bytes，原 process 與另一 process 再次 apply 成功；crash A 在 read 前持真鎖，SIGTERM exit -15 後 B 成功，固定 inode 保持；不同 root 的 B 可在 A 暫停時完成。自身 children 有界 join/terminate/close，正常 exit 0 |
| 入口與 preserved behavior | CLI 測試使用真 flock 和 slash handler；Desktop 測试正式 dispatch 的 ManagementError → BUSY_EXTENSION_OPERATION/retryable/通用文字 mapping。既有 dry-run 無 state、selected scope、source/private validation、MCP approval、restart 與 protocol checks 通過 |
| Scope | Production 只改 manager.py 23 additions/5 deletions，無 writer/schema/API/依賴改動。新增 tests 僅 manager 與 Desktop 既有 test files；其餘為本 bundle 的執行與審查紀錄。`git diff 4d7d8a5..HEAD --check` 通過 |

驗證限制：使用 temporary local filesystem、fake model 與既有 sandbox MCP，
沒有真 GUI 雙視窗、network filesystem、live provider 或 power-loss testing。
Crash evidence 僅涵蓋第一次 revision read 前終止；不能推論部分安裝／replace 後 rollback。
Advisory lock 不約束舊版或手動 writers。O_CLOEXEC 防止 fd 跨 exec 保留；
本 apply 路徑不建立 child，測試使用 spawn，不宣稱任意 fork/dup 後都不會繼承 fd。

沒有額外修正、測試矩陣或後續 issue。Review 重用已通過 required checks，未重跑 full suite。
