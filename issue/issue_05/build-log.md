# Issue 05 — Citation 保存結果回報：執行紀錄

本檔是唯一 runtime phase status 與實際 implementation／verification evidence
來源。未來步驟在 phase 檔；本檔只記錄已發生的事。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Save result reporting | Complete | 2026-09-12 | 2026-09-12 | Tool characterization, four E2E scenarios, regressions and full suite below | None |

使用 `Not started`、`In progress`、`Blocked`、`Complete`。
必要 acceptance 與 verification 均有實際證據才可標 Complete。

## Evidence Rules

- 記錄 exact command／procedure、runtime／working directory、結果及 acceptance
  對應；分清 observed、historical、planned，不用 skipped 代替 pass。
- 記錄實際變更、重要失敗與未執行原因；新測試直接通過時如實記錄
  characterization，不虛構 red／修正。
- 模型輸入證據必須指出讀取 ToolMessage content 的位置及其先後順序；
  CLI evidence 指向本次實際擷取輸出，不只記 metrics。
- 大型輸出用連結，避免完整 payload、secrets 或 routine narration。
- 重大發現才寫 context，真實 review 才寫 review。矛盾 evidence 都保留，
  釐清前不得 Complete；錯誤紀錄以 append-only correction 修正。

## Activity Log

尚未開始實作，沒有 application tests、live provider 或保存流程的執行證據。
本次只撰寫計劃；authoring validator 結果不代表應用程式已驗收。

日後事件記錄：時間／時區、phase 狀態變化、授權 scope 連結、
實際變更、exact checks／結果、驗收對應、重大發現、未執行限制與 blocker。

### 2026-09-12（Asia/Taipei）— Preflight / baseline

- 使用者要求執行 issue_05 且每一步 commit；授權本計劃與逐步 commit。
  Not started → In progress。唯一 applicable AGENTS 在 repository root；
  已讀 GOALS、PLANS、PROMPTS、phase、log 與相關 live code/tests。
  issue 04 / 05 均無既有 context/code_review。
- Root `/home/minervamuses/research-agent-workspace`，project `app/`，Linux，
  bash `/usr/bin/bash`、Git `/usr/bin/git`，branch `GUI`，起始 HEAD `6b6d8a5`。
  `git status --short`、`git diff --stat` 均空。
- 初始 PATH 優先找到 Linux pipx Poetry 2.3.4；未用它跑 application checks。
  以下共同前置確認 Python 3.13.14、Poetry 2.4.1 與
  `poetry run python -c 'import sys; print(sys.executable)'` 均來自 Conda app：

  ```bash
  source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
  conda activate app
  export PATH="$CONDA_PREFIX/bin:$PATH"
  cd /home/minervamuses/research-agent-workspace/app
  ```

- 外部 prerequisite：issue_04/build-log 的 Complete 與 commits
  `359669b`、`6b6d8a5` 對得上 live resolution 的 earliest 年份歧義、
  service authority guard 及三個相關測試檔。其 72 focused / 1061 full-suite
  passes 是歷史證據，本次不冒充重跑；未發現矛盾。
- Live tool 使用一次 outcome.to_artifact 產生 content/artifact；PolicyToolNode
  保留 ToolMessage，graph tools → agent，session 使用 artifact 做 metrics，
  finalization 寫入答案，CLI 印出 session.turn response。既有 e2e fake 仍讀
  artifact；本次補 content 觀察。維持 schema、production 與其他 issue 範圍。
- Baseline exact command（上述 runtime/cwd）：

  ```bash
  poetry run pytest tests/test_citation_workflow_tool.py tests/test_citation_e2e.py -q
  ```

  **21 passed, 1 warning in 0.41s**。Warning 為既有 LangChain
  allowed_objects pending deprecation；無 failed/skipped/unavailable。
- 下一步僅補兩個既有測試檔：11 狀態序列化、四種真 graph 流程、mixed CLI、
  history / registry / bundle 對照。通過即記 characterization，不製造 red。
  Required checks 依 phase 包含 focused、preserved regressions、最後一次
  timeout 600s full suite 與 diff check。既有 fetcher/模型/embedding fixtures
  可離線使用，issue 04 full suite 歷史約 27 秒，未發現成本門檻變更。
  必要檢查缺證據、範圍外 production 修正或兩次 focused attempt 失敗即停止。

### 2026-09-12（Asia/Taipei）— Tool content characterization

- Preflight commit `60197f7`。只擴充既有 workflow tool envelope test，依
  SaveItemStatus 參數化全部 11 狀態，每批兩項，未超過 works 1–10 限制。
  真 StructuredTool 以 injected service outcome 回傳；content JSON == artifact
  == 原 outcome，strict decode 還原完整 dataclass。驗證 Unicode label、
  非排序 index [1, 0]、reason、成功 receipt、兩筆 alternatives（含缺值）。
  每個 failure 都在 transport success 下保留原 failure status。
- Exact command（共同 runtime/cwd）：

  ```bash
  poetry run pytest tests/test_citation_workflow_tool.py -q
  ```

  **26 passed in 0.16s**，無 warning/failed/skipped/unavailable。
  新測試直接 green，屬 characterization；未改 production，未虛構 red。
  此證據只涵蓋 serialization channel，不宣稱逐一觸發 provider failure。
  四種真 service/graph 流程及 required completion checks 尚待執行。

### 2026-09-12（Asia/Taipei）— E2E first attempt / plan correction

- Tool characterization commit `16fe747`。既有成功及 malformed-receipt fake
  改讀 content；新增四種代表案例，真 graph/service/CLI，模型快照與磁碟 history
  對照。第一次 exact command（共同 runtime/cwd）：

  ```bash
  poetry run pytest tests/test_citation_workflow_tool.py tests/test_citation_e2e.py -q
  ```

  **1 failed, 34 passed, 1 warning in 0.67s**（exit 1）。Retry 預期第二批 saved，
  實際仍 verification_failed；其餘三种情境通過。Warning 同 baseline。
  此為第一次 focused attempt 失敗，尚未 Complete。
- 唯讀 trace 確認 DoiOrgClient.fetch_bibtex 在 service 驗證前快取 HTTP 200
  原始文字 24 小時，推翻原 retry fixture 假設。未發現結果傳遞缺陷。
  修訂 PLANS 與 active phase 的 fixture 安排：retry 首次 HTTP 503（不快取），
  第二次正確 fixture；保留錯 DOI mixed/all-failure，不變更 GOALS/acceptance。
  重大發現見 [context](context/phase-01-save-result-reporting-context.md)。
  不授權擴張 provider/cache 修正；下一次 focused 仍失敗即依上限停止。

### 2026-09-12（Asia/Taipei）— E2E green / preserved regressions

- 第二次 focused attempt：只調整測試 fetcher，retry 首次 HTTP 503；
  production diff 仍為零。Exact commands（共同 runtime/cwd）：

  ```bash
  poetry run pytest tests/test_citation_workflow_tool.py tests/test_citation_e2e.py -q
  poetry run pytest tests/test_citation_save_outcomes.py tests/test_turn_finalizer.py tests/test_chat_cli.py tests/test_citation_skill_activation.py -q
  ```

  分別 **35 passed, 1 warning in 0.60s**、**87 passed, 1 warning in 0.88s**。
  Warning 同 baseline，無 failed/skipped/unavailable。整合測試只是補齊現有
  行為證據，未修復 production bug。
- `_SaveReportingModel.invoke` 每次保存 deep message snapshot；無結果時才
  發初次 call；回覆前 `_save_content` 解析 ToolMessage.content JSON，依
  matching tool_call_id 找先前 AI call 的作品／identifier，逐項產生答案。
  模型不讀 artifact、service、expected status 表或預寫完整答案。
  一般流程快照結果數 [0,1]，retry [0,1,2]；artifact 僅作測試 oracle 對照。
- `test_save_reporting_reaches_model_history_and_cli` 四組實際結果：

  | 情境 | decoded outcome / answer | filesystem / history |
  |---|---|---|
  | all_success | A reused/reused_existing；B saved/saved_new，分清重用／新保存 | 兩個 DOI registry/bundle；A 既有所有 bundle files bytes 與 mtime_ns 不变；receipt trusted；答案等於磁碟 history |
  | all_failure | B verification_failed/bibtex_doi_mismatch，答案無新保存／重用 | registry/bundle 均零；答案等於磁碟 history |
  | mixed | A saved/saved_new；B verification_failed/bibtex_doi_mismatch | 僅 A registry/bundle；真 CLI、session.turn、fake prose、recent_turns 與重載磁碟 history 一致 |
  | retry | B verification_failed/bibtex_lookup_failed → saved/saved_new，答案保留兩次及先失敗後成功 | 兩個 call_id/batch_id；兩個 request_index 都為 0，但 calls 明確同 DOI/intent；兩次 BibTeX fetch，僅一個 B bundle；答案等於磁碟 history |

- 成功 receipt 逐項對照 registry、reference.bib DOI、citation.json source_ref；
  新 bundle creation_evidence 的 batch_id/request_index 與當次 outcome 相等。
  未改 telemetry attempt 計數，不把兩次 retry 說成保存兩個作品。
- Mixed 經 `chat._run` 真 print，capsys 驗證末段只印一次完整 session.turn
  回覆。實際文字（亦從該次 pytest-9 的 fixture conversation JSON 核對）：

  ```text
  第 1 次保存：
  Paper A (10.1234/paper-a)：新保存（saved_new）。
  Paper B (10.1234/paper-b)：失敗（bibtex_doi_mismatch）。
  ```

  輸入 `/citation 保存 A 與 B 並逐項回報`；只替換 create、reader，turn wrapper
  委派真 turn 並記錄回傳，未模擬 graph/service/finalization/print。
- Preserved tests 涵蓋 save artifact 不覆寫 prose、marker gate/render、
  inactive skill、metrics 與 history。`git diff --check` 通過，已讀新增 e2e diff。
  Phase 維持 In progress，尚待最後一次完整 suite 與最終驗收。

### 2026-09-12（Asia/Taipei）— Final integration / Complete

- E2E / plan correction commit `4da6e10`。共同 runtime/cwd 下，最後且唯一一次
 完整 suite exact command：

  ```bash
  timeout 600s poetry run pytest -q
  ```

  **1075 passed, 2 warnings in 23.80s**（exit 0）。無 failed/skipped/unavailable。
  Warnings 為既有 LangChain allowed_objects pending deprecation，及
  test_installer_zip_rejects_unsafe_members_without_extracting 刻意產生的
  duplicate ZIP member warning。未重跑完整 suite。
- Repository root 實際執行：

  ```bash
  git diff 6b6d8a5 --check
  git diff 6b6d8a5 --stat
  git diff 6b6d8a5 -- app/tests/test_citation_workflow_tool.py
  git status --short
  git log -4 --oneline
  ```

  Whitespace check 通過；兩個測試 diff 已逐一檢視，未發現需追加修改。
  最終 log 更新前工作樹乾淨。最終 log 亦經 diff check 後 commit。

#### GOALS / phase acceptance 對應

| 成功條件 | 實際 evidence |
|---|---|
| 11 狀態 content/artifact/outcome 完整且有序 | 參數化 real tool-call test：11 組，每批兩項，index/label/status/reason/receipt/alternatives strict round trip |
| 四類真 graph，model 從 content 收結果後才回答 | 新 e2e 四組、invoke deep snapshots、matching call 在 result 之前、[0,1] / [0,1,2] 時序；既有成功 journey 亦改讀 content |
| 保存、重用、失敗與實際作品相符 | 前節四組結果、trusted receipt、BibTeX/sidecar/registry、重用 bytes/mtime 不變、0/1/2 唯一 bundle；retry 同 DOI/intent 不依跨批 index 合併 |
| CLI/session/history 一致 | Mixed 真 chat._run print 擷取，委派真 session.turn，對照模型答案、recent_turns、磁碟重載 assistant_output；文字見前節 |
| finalization/citation gate/render/telemetry/history preserved | 指定 87 項回歸及完整 1075 tests 通過；未新增保存全文覆寫層或第二資料通道 |
| 所有 required checks 與外部 prerequisite | issue 04 live 核對、focused 35、regression 87、唯一 full suite 1075、整體 diff check 均通過 |

- 實際修改僅：`app/tests/test_citation_workflow_tool.py`、
  `app/tests/test_citation_e2e.py`、`issue/issue_05/build-log.md`、
  `issue/issue_05/PLANS.md`、`issue/issue_05/phases/phase-01-save-result-reporting.md`、
  `issue/issue_05/context/phase-01-save-result-reporting-context.md`。
  Production、Skill、schema、dependencies、AGENTS 與其他 issue 均未修改。
- 保留第一次 retry fixture 失敗證據；最後 green 是既有行為 characterization。
  未呼叫 live/paid provider、真 LLM/GPU；所有 bundle/history 均限 tmp_path。
  Fake model 證明可見性、時序及整合，不保證真實 LLM 永不誤報；HTTP 200
  錯 DOI 的立即 retry 仍受既有 cache 影響，本次不擴張處理。
- Required acceptance 完整取得證據，In progress → Complete，無 blocker。
  最終驗證紀錄 commit 後停止，不啟動其他 issue。
