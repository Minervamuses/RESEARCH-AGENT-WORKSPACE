# Phase06 — actual diff review（2026-09-13 Asia/Taipei）

本次由執行代理重新從 live code 與完整 diff 做 bounded review，沒有另派 reviewer 或宣稱獨立代理驗證。Review baseline 40b843c → cf3183b；production 只有 session.py 與 desktop/service.py，Rust backend.rs 只改 cfg(test) setup，另有兩個 Python regression test files。沒有全 repo audit。

## 已檢查的邊界與結果

- Installer：逐行核對 load/validation → clear → cleanup_conflict → host public text → finalize/durable write；衝突分支在設定新 runtime／進 graph 前返回，既有 clear 保留 changed source／backup 並恢復 mode。公開內容來自 _installer_result_text 的 cleanup_detail／backup_path，非 raw dict 或模型猜測。兩種 Skill 的 regression 直接核對 public response、canonical answer、graph/Fusion/model 零呼叫與全部 source/backup bytes。
- Mode：_begin_turn 前只計算 effective_mode，沒有先 mutation／cleanup。Citation／installer 保持 normal；installer pending 切一般 Skill 用原模式。實際 Fusion proposer/aggregator/reviewer、Normal graph、durable JSON thinkingMode 與結束後 session mode 都有断言。Load failure 及 completed installer retry 保留 transaction/runtime/source bytes。
- Replay：Desktop 的 completed 候選僅延後 runtime eligibility；不直接讀回答案。仍執行 shared slash parser 與 turn_outcome 的 lock、_reload_and_recover 的 project validation、append_pending 的 kind/display/semantic/context/mode 比對及 snapshot fingerprint。Completed return 在新 runtime/scope/cleanup 前；retry=true 也不重跑。八種身分／fingerprint 反例以及 failed/interrupted 的 runtime gate 都由真 repository + service tests 拒絕。
- Effects：loader failure 與真 applied bundle tamper 的重送均核對同 answer/turnNumber/final_only、loader/model/fetch/scope/save counters 不增加、canonical/bundle bytes 與 mtime 不變；不是只檢查 status。
- Rust fixture red：kill-only 允許 stdout_closed 在 process exit 前回報 Degraded；修改後在既有 child mutex 下 kill/wait，兩個 observer 只能讀到已退出程序。沒有持有 supervisor state lock 等待 child、沒有用 sleep 猜退出、沒有放寬 Crashed 或 NotRunning assertions，也不修改 production lifecycle。唯一 affected target 真程序檢查 green。
- Native evidence：Phase03 的 Windows Computer Use 操作對照 Linux AT-SPI、實際 backend request/model/save audit、canonical output 和 bundle hash。普通下一回合與 A/B/restart 不重播，失敗／原生中斷恢復已觀察。IME skipped、task cancel 原生沒有入口及離線 provider 限制均有明列。

## Review 結論與限制

無尚待處理的 required code findings。Python1138／Node165 全套通過；Rust 唯一完整 run 為35passed／1failed，測試同步修正後該1項 focused passed，未重跑整套；Tauri offline source build 通過。這些涵蓋最終 production diff，Rust後續只改測試，無需重新取得 native production evidence。

額外的 Citation candidate 讀取仍受既有 repository 解析與後續鎖內驗證約束；不宣稱跨程序 conversation CAS 或連續惡意 writer 防護。Issue06 activation precheck TOCTOU、Issue04 只有年份、Issue05 真模型敘述品質及 live provider 都維持既有範圍，不順便擴張。此 review 是同一代理 source review，不是另一次完整測試或獨立團隊 sign-off。

清理前發現 README 與 for_agents 的舊 issue 引用；僅在 cleanup step 改為固定 Git 歷史連結，保留 for_agents 原2026-09-06 audit 的歷史性，不把舊 probe 更新成今天 passed。
