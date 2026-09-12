# Phase 01 — Citation turn-owned lifecycle

## 目標

依 [GOALS.md](../GOALS.md) 正式核准的契約，從 CLI 執行一次 Citation：
來源在 gate/render／答案保存期間有效，成功、錯誤與取消後釋放本次 scope；
下一個普通輸入沒有隱藏 Citation 狀態，thinking 恢復正確。

## 來源

- ../GOALS.md、../PLANS.md、../build-log.md。
- app/agent/cli/slash_commands.py、app/agent/cli/chat.py、app/agent/session.py。
- app/agent/skills/citation/session_policy.py、app/skills/citation/service.py、
  app/skills/citation/SKILL.md。
- 下面列出的現有 tests。

## 範圍與預期元件

Production 預期修改 slash_commands.py、chat.py、session.py、Citation SKILL.md：
共同 parser 回傳工作意圖；Session 在既有 turn lock 內管理 activation／cleanup；
Skill 文字對齊本次 registry lifetime。chat.py 保留既有 forwarding，只校正
_command_feeds_agent 的控制命令判斷：off／none／deactivate 必須是完整唯一
參數，/citation off topic 仍為自然語言工作。policy reset／gate、
CitationService save／reuse 可直接重用。

測試延伸既有 test_citation_slash_command.py、test_citation_skill_activation.py、
test_citation_e2e.py；只有需要直接斷言 durable 整合時才局部補
test_session_persistence.py 或 test_turn_finalizer.py。不新建 framework。

## 非目標

Desktop dispatch／menu 由 Phase 02 負責；不改 citation resolver、gate、bundle
schema、持久 registry、取消交易機制或內部 legacy API。沒有獨立 refactor 階段。

## 依賴與前置

- 使用者已確認 GOALS 待決產品契約並核准 PLANS 的實作範圍。
- issue 02 依原 issue 指定順序完成，有 live catalog／menu 和可核對 evidence；
  不由本 phase 代做。
- Linux／Conda app 工具吻合，initial worktree snapshot 已記錄。
- **待解技術點：** snapshot thinking 的時機須在既有 installer cleanup 恢復後、
  Citation 暫用 normal 前；_begin_turn 也需記 normal。Preflight 直接核對
  turn_outcome／clear_skill_installer／_run_turn 呼叫順序，不另造全局模式管理器。
- **待解技術點：** 舊 persistent Citation service 如已存在，新的 command 必須
  以新 scope 進入，不恢復舊 registry；不得使內部 legacy callers 無關行為改變。

## 實作與驗證計劃

### Preflight／最小因果檢查

依 PLANS 共用環境進入 app/。閱讀上述 code 與目前 tests，先觀察哪些測試
鎖定舊 persistent slash 語意、哪些保護直接 activation API，避免整批刪除。
核對 completed duplicate 在 activation 前返回，以及現有真 CLI 測試接縫；
後续實作的 scope 必須涵蓋真正的 turn，不是在 parser 提早改 state。

### 最小測試與修改

1. 在 slash tests 描述有需求、空需求、舊 off tokens、原文字串、保留命令 collision。
   斷言 parser handler 不直接 activate；CLI 仍送 prompt 與 display_input、
   skill_name。加入 /citation off topic 與 /citation off 的最小對照，
   讓 CLI classifier 與共同 handler 使用相同的完整控制指令語意。
   重用現有 CLI monkeypatch 測試，不啟動 live model。
2. 在 session/e2e test 用現有 RoutingFetcher、env={}、tmp_path，
   指定 DOI fixture 的搜尋→save→引用流程。比較 fake model 真正收到的
   tool result、正式渲染答案、saved receipt／bundle 和 canonical assistant text；
   不把一段固定假答案當成 gate／save 整合成功。
3. Session 沿用 turn_outcome、_run_one_shot_skill_turn 的局部 scope 或同檔小 helper；
   Citation 有自己的啟用、normal、teardown 邏輯，不新增平行 pipeline。
   Load/validation 應在更動 active state 前完成，duplicate 不啟動新 service。
4. Cleanup 使用 finally／既有 failure 路徑，成功時不可早於 registry-dependent
   gate/render、metrics 與 durable completion。取消／provider／保存失敗也必須
   釋放 scope；cleanup 不遮蔽原 exception，不妨礙 failed/interrupted 記錄。
5. 以代表案例分別驗證 tool all-failure、invalid marker／receipt gate rejection、
   provider exception、durable write failure、async task cancel；
   每種 terminal 都驗證下一個普通輸入無 Citation tools／sources hint，
   並恢復原 thinking。正常設定與原先 extended 至少各一個代表案例。
6. 取消的 to_thread save 用現有 monkeypatch／threading.Event 類局部接縫
   可控地阻擋既有 writer，再取消與釋放；必要時等該測試 writer 收尾，
   不讓背景寫入越過 tmp_path 壽命。斷言晚到寫入不成為新工作 registry，
   已保存 bundle 不被刪除；不要求磁碟回滾、不引入 concurrency model。
7. 舊歷史 metadata 可用於新 /citation，只有新 save/reuse receipt 能供新 gate；
   duplicate turnId 不再呼叫 model／tool。Skill.md 只改相關流程說明。

### Planned verification

以下均為尚未執行的計劃。每命令預計低於十分鐘；逾限依 PLANS 停止。

```bash
timeout 300s poetry run pytest tests/test_citation_slash_command.py tests/test_citation_skill_activation.py tests/test_citation_e2e.py -q
timeout 300s poetry run pytest tests/test_turn_finalizer.py tests/test_session_persistence.py -q
timeout 300s poetry run pytest tests/test_skills.py -k one_shot -q
```

新增失敗測試先以最小 nodeid 跑 red；修正後跑相關上列 checks，
不機械重跑所有命令。通用 turn tests 全檔用於 finalizer／persistence 直接回歸風險。
完整 Python suite 留至 Phase 02 最後一次。

**CLI acceptance：** 重用 test_citation_slash_command.py 的
 test_followup_text_runs_as_agent_turn_via_chat_loop 與 chat._run(read_line=...)，
在 fake session/model 接縫輸入
/citation <fixture 文獻保存需求>，再輸入一般問題；檢查可見 normal 提示、
正式答案、原 command history、兩次不同工具可用範圍。只有直接调用
turn_outcome 不足以證明 CLI forwarding。於既有 test 中局部 monkeypatch
ChatSession.create／read_line，不為此新建測試框架或接付費 provider。

## 驗收條件

- [ ] 四種 command／參數分支符合 GOALS；parser 不留下 active state。
- [ ] 真 citation tool/service／gate/render 產生代表正式答案、保存檔案與 durable text。
- [ ] GOALS terminal 表中本 phase 的成功／工具失敗／validation／provider／
      persistence failure／cancel 均 cleanup；不依賴某一條成功路徑。
- [ ] Thinking 在 runtime 與 durable 記錄為預期模式，cleanup 後恢復原設定；
      completed duplicate 無 activation／model／save。
- [ ] 下一個普通 turn 無 Citation 權限／提示，新 Citation 不信任舊 source id；
      已寫 bundle 保留且可由正式 save/reuse 重新取得 receipt。
- [ ] CLI 代表輸入／輸出與所有 required checks 有直接 evidence，
      一般 one-shot／trust／durable 行為保留。

## 復原、停止與證據交接

遵守 PLANS 授權 envelope。若需要 policy、storage 或新 API shape
變更，先以具體失敗證據要求最小增補授權，不猜測加修。
失敗保持 In progress 或 Blocked；dependent phase 不可開始。
修正只限自己的局部 diff，不 git reset、checkout 或還原既有使用者變更。

在 ../build-log.md 記錄 actual commands、失敗原因與修正結果，
逐條 acceptance 對應觀察；重大時序／取消發現才寫
../context/phase-01-citation-turn-lifecycle-context.md。
本 phase 必要 checks 完成且 log 為 Complete 才交接 Phase 02。
