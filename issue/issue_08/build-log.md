# Issue 08 — Build Log

本檔是唯一 runtime phase status 與 observed implementation evidence owner。
計劃描述未來工作；本檔只記錄真正發生的執行結果。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Citation turn lifecycle | Complete | 2026-09-12 | 2026-09-12 | Phase 01 evidence below | — |
| 02 — Desktop integration | Not started | — | — | — | 依 PLANS 前置順序 |

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
