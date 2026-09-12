# Issue 08 — Build Log

本檔是唯一 runtime phase status 與 observed implementation evidence owner。
計劃描述未來工作；本檔只記錄真正發生的執行結果。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Citation turn lifecycle | Complete | 2026-09-12 | 2026-09-12 | Phase 01 evidence below | — |
| 02 — Desktop integration | Blocked | 2026-09-12 | — | Phase 02 offline evidence below | Required native Citation UI journey unavailable |

只使用 Not started、In progress、Blocked、Complete。
必要 acceptance 有 observed evidence 才可 Complete。

## 證據規則

- 記錄時間、phase、狀態變化、changed files、exact command／操作、
  cwd／runtime、pass／fail／skipped／unavailable、簡短觀察與 artifact 路徑。
- 分開實際觀察、歷史資訊與 planned checks；不複製整份輸出或 credentials。
- 以 command 輸入／正式答案／registry 狀態／provider counter／bundle 檔案
  對應 acceptance；fake model、reducer 或 helper checks 不代表原生 UI 已驗收。
- 未通過或不可執行的必要檢查保持未完成，記具體原因與下一個最小行動。
- 重大矛盾以 append-only correction 保留原紀錄；依證據更新狀態表。
- 重大發現與真實 review 依 PLANS.md 路徑寫入，沒有內容不先建立空文件。

## 活動紀錄

尚無 implementation activity。本次只 authoring，application tests、Desktop
build／UI 操作與各 phase planned verification 均未作為本計劃實作證據執行。

### 2026-09-12 — 授權與 Phase 01 preflight

- 使用者先要求執行入口且「每一步皆需 commit」，唯讀 preflight 發現待決契約
  及 issue 02 缺口後，再回答「我同意授權」。批准 GOALS 全部建議契約、
  PLANS 六個 production files 與既有 tests，並允许 issue 02 原生 GUI 驗收
  尚未完成時繼續。每個執行步驟／phase commit；未授權 push／branch 操作。
- Root `/home/minervamuses/research-agent-workspace`，branch `GUI`，HEAD `73faa76`，
  `git status --short` 空。讀根 AGENTS.md，`rg --files -g AGENTS.md issue app`
  未發現更下層指示；context／code_review 尚不存在。
- 使用 non-login Bash，`source /home/minervamuses/miniconda3/etc/profile.d/conda.sh`
  及 `conda activate app`；`command -v python poetry node npm git` 確認前四者
  均為 Conda app、Git `/usr/bin/git`。Python 3.13.14、Poetry 2.4.1；
  初次 login shell 的 pipx Poetry 未用於任何 application 操作。
- Correction：authoring 所述 issue 02 未實作已過期。Live catalog helpers／
  SlashComposer 已存在，issue 02 log 為 Complete／Blocked／Not started。
  只更新本 issue 的依賴決定，不修改 issue 02，也不宣稱 native UI 通過。
- Phase 01 範圍：command intent、turn lock 內 Citation scope、normal／cleanup、
  Skill 來源 lifetime 與既有離線 tests。保留 gate/storage/legacy API；
  Desktop 留至 Phase 02。Checks 依 phase 的三組 focused pytest，先 red 後 green；
  必要失敗、超出六檔或 required evidence 缺失依 PLANS 停止。
- 本步只修改 GOALS、PLANS、兩個 phase files、build-log；未跑 application tests。

### 2026-09-12 — Phase 01 Complete

- 授權決定已 commit `b48c267`。本 phase production 只改
  `app/agent/cli/slash_commands.py`、`app/agent/cli/chat.py`、`app/agent/session.py`、
  `app/skills/citation/SKILL.md`；tests 只改既有 citation slash／activation／e2e 三檔。
- Parser 回傳 `skill_name=citation` 和原始需求，不 activate；空 command 回用法、
  唯一 off/none/deactivate 回 migration hint。CLI 比較完整參數，`off topic` 能送入
  agent，大小寫／apostrophe／原 command display 與 reserved collision 均驗證。
- 既有 turn lock 與 one-shot runner 擴充 Citation：load/validation 在 state mutation 前，
  installer cleanup 後 snapshot 原 mode，新 scope 清掉 legacy registry、暫用 normal，
  finally 於 gate/render/metrics/durable completion 後清理並恢復 mode。
  `_begin_turn` durable mode 記 normal；completed duplicate 於 load／activation 前返回。
  Legacy activate/deactivate API 保留，沒有 policy/storage/schema/dependency 修改。
- Red（cwd app、non-login Bash、Conda app）：
  `timeout 300s poetry run pytest tests/test_citation_slash_command.py::test_followup_text_runs_as_agent_turn_via_chat_loop tests/test_citation_skill_activation.py::test_citation_turn_scope_restores_mode_and_records_actual_normal -q`
  → 2 failed：舊 handler 提早 activate；session 拒絕 Citation one-shot。
- 初次相關測試：`timeout 300s poetry run pytest tests/test_citation_slash_command.py tests/test_citation_skill_activation.py -q`
  → 30 passed、1 failed：既有 tampered slash test 仍期待空 command activation；
  按批准契約改用有需求的 command，於真正 turn load 時仍拒絕 tampered runtime，
  保留 prior skill/service/mode 且 graph 無呼叫。
- 新 e2e 初次 `timeout 300s poetry run pytest tests/test_citation_slash_command.py tests/test_citation_skill_activation.py tests/test_citation_e2e.py -q`
  → 41 passed、6 failed。兩個測試假設錯誤：fake `bind_tools` 回同一 mutable model，
  不能反映 graph 的 cached bindings；既有 gate safe message 允許在錯誤說明保留 marker。
  單獨 `timeout 300s poetry run pytest tests/test_citation_e2e.py::test_later_citation_requires_new_receipt_and_reuses_saved_bundle -q --tb=short`
  → 1 failed，確認後者；只修 fake binding 與輸出斷言，不改 graph/gate。
- Green：`timeout 300s poetry run pytest tests/test_citation_slash_command.py tests/test_citation_skill_activation.py tests/test_citation_e2e.py -q --tb=short`
  → **48 passed**（1.01 s）。補足 empty-search／cancel 後 ordinary turn 斷言後：
  `timeout 300s poetry run pytest tests/test_citation_e2e.py::test_search_selection_journey_stops_when_search_is_empty tests/test_citation_e2e.py::test_cancelled_save_late_writer_cannot_populate_next_citation -q`
  → **2 passed**（0.28 s）。
- Required checks：`timeout 300s poetry run pytest tests/test_turn_finalizer.py tests/test_session_persistence.py -q`
  → **46 passed**（0.89 s）；`timeout 300s poetry run pytest tests/test_skills.py -k one_shot -q`
  → **2 passed, 7 deselected**（0.20 s）。既有 LangChain pending-deprecation warning 1 項。
  `git diff --check` passed；完整 suite 留 Phase 02。
- 代表 CLI journey：`/citation 搜尋 Paper A，選擇 2021 年正式記錄，保存並引用` →
  真 search/save tool content 決定 fixture DOI `10.1234/paper-a`，真 gate/render 輸出
  `已保存並引用來源 [1]。` 及 Sources；canonical assistant text 與 CLI 相同。
  temporary `reference.bib`／`citation.json` 存在且 receipt 對應 registry；下一個
  ordinary question 輸出 ordinary answer，共 4 次 fake model invocation，普通 binding
  無 workflow tool，prompt 無 sources hint，沒有 active runtime/service。
- 成功、save all-failure/mixed/retry、empty-search、gate rejection、provider exception、
  final durable write failure 與 async cancel 有直接狀態／輸出斷言。
  Completed／failed／interrupted 沿用既有 schema；失敗沒有偽造 assistant output。
  Extended 原 mode（含 installer temporary normal）恢復，durable Citation mode normal。
- Duplicate 計數與禁止 runtime load spy 證明不重跑；後次 Citation 的空 registry
  不接受歷史 marker，正式 save/reuse 產生本次 receipt；既有 bundle bytes／mtime 不變。
  可控 writer 在 cancel 後落盤，舊、新 registry 皆不接收晚到 receipt，磁碟 bundle 保留，
  下一工作及 ordinary turn 均可操作。Thread 在 tmp_path 生命週期內收尾。
- 限制：全部 provider/model 為離線 scripted boundary，env={}、RoutingFetcher、tmp_path；
  extended 後的 ordinary graph 以 monkeypatch 替代 Fusion orchestrator，不證明 Fusion
  或真模型品質。原生 GUI 尚未驗收，屬 Phase 02。

### 2026-09-12 — Phase 02 preflight

- Phase 01 committed `5b138ad`，worktree clean。Conda app Node v24.18.0、npm 11.16.0，
  既有 node_modules／TypeScript 可用；不安裝依賴。
- 重用 service `_session_slash_registry`／`_desktop_command_eligible`、
  snapshot `slashCommands` 與 `SlashComposer`；production 預期只改 service.py、App.tsx。
  真 ChatSession factory、既有 citation fixtures 可在 pytest temporary paths 跑完整 dispatch。
- 原生入口存在 `server._build_runtime_service` 的 `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02`，
  但其 `FixtureSession` 是 coordinator fixture，並非真 Citation graph/service journey。
  沒有直接可用的 Citation UI fixture；不改第七個 production file 或接 user store。
- `timeout 3s xdotool getdisplaygeometry` → exit **124**，無輸出；工具清單沒有原生
  computer/browser 操作工具，Xvfb/weston/orca 查無命令。只做唯讀 UI preflight，
  未啟動一般 Desktop。繼續完成已授權離線實作/checks，再如實記 required UI 缺口。

### 2026-09-12 — Phase 02 implementation verified offline; Blocked on native UI

- Production 只改 `app/agent/desktop/service.py`、`app/desktop/src/App.tsx`。
  既有 eligibility helper 以無 mutation 的 runtime load／workflow tool availability
  決定 Citation catalog 和 dispatch；缺失／無法 load 的 Citation 不列出也不啟動 model。
  Citation 和 dynamic Skill 共用 followup→`session.turn_outcome`，空 command／off tokens
  使用共同 Python handler 的原文，封裝既有 PROTOCOL_INVALID；不新增 DTO/RPC。
  App 以單次工作／normal／恢復原 mode 說明取代 CLI-only。
- Tests 只延伸 `test_desktop_service.py`、`test_desktop_conversations.py` 與
  `desktop/tests/conversations.test.ts`；沿用 real ChatSession、既有 model/fetcher
  與 temporary service/repository 接縫，不建立新 fixture framework/module。
- Red check 命令（cwd app、Conda app）：
  `timeout 300s poetry run pytest tests/test_desktop_service.py::test_composer_citation_uses_shared_command_and_available_catalog -q --tb=short`。
  前兩次於 collection 發現新測試的 `]` 遺漏，exit 4，未執行 application。
  修正測試後，以 `git show HEAD:app/agent/desktop/service.py` 暫時重現 Phase 01 的
  service（使用 mktemp 保存自己的 patch，EXIT trap 恢復並清理；未切 branch/worktree），
  同命令 → **1 failed**：catalog 中 Citation 數量 0，期望 1。
  恢復實作後同命令 → **1 passed**（0.23 s）。
- Required Python focused check：
  `timeout 300s poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py -q --tb=short`
  → **219 passed**（2.17 s）。隨後整理新測試插入位置，將其移至既有 test function
  結束之後，保留原檢查的歸屬；最終完整 suite 覆蓋該位置。
- Desktop cwd：`timeout 300s npm test` → **165 passed**（4.29 s）；
  `timeout 300s npm run build` → **passed**（TypeScript、Vite）。
  Node 新檢查觀察 `/cit` filter/insert 及 restored Citation answer／tool activity 的
  SSR markup；只證明 helper/rendering，不冒充原生鍵鼠、focus、caret 或 IME 操作。
- 全計劃唯一完整 Python suite（cwd app）：`timeout 540s poetry run pytest`
  → **1122 passed**（31.29 s），2 warnings：既有 LangChain pending-deprecation 與
  unsafe ZIP test 的 duplicate member warning。沒有重跑完整 suite。
  `git diff --check` passed，無 dependency/lockfile/schema/generated-output 變更。
- Observable command：`/CiTaTiOn off topic: 搜尋並保存 Paper A` 保留 display 原文、
  semantic input 為原自然語言；執行時 normal、結束 backend snapshot 仍為 extended。
  空參數／三種 off tokens 與 CLI Python result 的文字逐項相同且 model/service count 0。
  成功結果為 `responseKind=answer`、`streamKind=final_only`、`chunkCount=0`，
  真 gate/render 產生 `[1]`、Sources、DOI；canonical assistant text 等於 Desktop text。
- Journey 觀察 2 個 `tool.started`、2 個 `tool.finished`、2 個 citation_workflow summaries；
  transcript 保存原 command、同一份 answer 和 2 個 bounded tool activities。
  A→B→A rematerialization、backend recreation、completed duplicate 之後，
  model/provider/service counters 均不增加；session runtime/registry 空，temp bundle 保留。
  普通下一回合沒有 Citation tool，沒有新增 Citation service。
- Provider failure 與取消已完成 save／尚未 final 的 task 分別留下 failed／interrupted，
  不偽造答案。Active switch／session shutdown／runtime shutdown 回 BUSY_TURN，
  原 service 不被提早丟掉；cancel 後 busy flag 釋放、mode 恢復。
  Restart restore 不重播，未明確 retry 的重送被拒絕；`retry=true` 以新 service
  完成原 turnNumber，save outcome 為 reused，原 bundle 保留。
- Unclean-restart Citation 專屬檢查以真 repository 的 canonical pending record 模擬
  未完成工作，再重建 backend；恢復為 interrupted、assistantText=None、counter 不變。
  這是離線狀態邊界驗證，非原生 GUI kill/relaunch 操作。
- **Remaining blocker：** Phase 02 要求原生 `/` menu 選 Citation、補 prompt、送出、
  工具活動／正式答案、下一普通回合、mode selector、切換／restart／failure 操作證據。
  本次 `xdotool` read-only query 仍 timeout，且既有 native fixture 不跑真 Citation。
  使用者先前授權豁免的是 issue 02 完成門檻，未豁免 issue 08 自身 native UI acceptance。
  Phase 02 保持 **Blocked**；需可操作 Linux Desktop 的安全 Citation journey 證據，
  或使用者明確接受本次 backend + Node + build 作替代，才可標 Complete。
- 所有已授權離線工作完成，依逐步 commit 要求將本 phase code/tests/log 一起提交。
  未操作 credentials／live provider／真實 user store，未新增原生 UI fixture、
  第七個 production file 或其他 issue 工作。
