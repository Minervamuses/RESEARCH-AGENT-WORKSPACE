# Phase 07 — 啟用一次性 migration、完成 fault journeys 與文件一致性

Status: Not started

## Objective

把已驗證的 non-destructive importer 接到明確的一次性 migration/reconciliation 入口，完成端到端故障注入與跨語言 Desktop journeys，並更新 active architecture/invariants/docs。最後證明 canonical JSON 是新對話唯一 authority，Plan Mode 與 conversation-history Chroma 不再被 active runtime 使用，而 legacy sources 仍可恢復。

## In Scope

1. 在 application startup、catalog discovery 或明確 pre-runtime hook 中，以最小同步流程掃描尚無有效 JSON 的 legacy conversations 並逐會話 import。
2. 成功狀態只由有效 canonical target 存在決定；不新增 migration database。失敗可重跑且不阻斷健康 conversations。
3. 補齊六個 durability crash/failure points、duplicate/retry、external rewrite、malformed/unknown version、catalog drift、A→B→A、normal→extended→restart 等代表性 tests。
4. 建立至少一條從 React/TS/Rust/Python 到 JSON 再重啟恢復的 full Desktop journey，依現有 harness 能力使用 fixtures/stubs，不呼叫 live provider。
5. 更新 active docs、for-agents invariants/data flow/module responsibilities/testing/failure modes，以及與已確認結果直接相關的 issue/backlog 狀態。
6. 執行一次合理的 full Python suite、Desktop tests/build、Rust tests 與近最終 Tauri no-bundle build。

## Non-goals

- 不刪除、壓縮、搬移或改寫任何 legacy Chroma/Plan user data。
- 不自動遷移本機真實 store 作為測試；真實資料執行需要另一次明確使用者授權、備份與 dry run。
- 不做 live provider、paid API、Ollama model pull、full dataset replay 或效能 sweep。
- 不建立 migration dashboard、background worker、watcher、資料庫或 multiwriter support。
- 不把歷史 `harness/`, `issue/`, `note/` 中的原始紀錄全部改寫成新架構。

## Dependencies and prerequisites

- Phase 01–06 acceptance criteria、focused tests 與 build-log evidence 均完成；沒有未解 schema/protocol blocker。
- 先確認所有 production caller 已切到 JSON，migration reader 沒有 active write responsibility。
- Docs 以目前程式與實際測試為準，不以原始計畫宣稱實作已完成。
- 只有使用者送出 `PROMPTS.md` 的完整 launch block 時，Phase 07 的第一組 broad Python/npm/Cargo/Tauri checks 才已被明確授權，即使合計可能超過約 10 分鐘；若以單-phase prompt 啟動而未另行授權，則先停下詢問。

## Expected components

Migration wiring 應落在現有 startup/catalog/service 邊界的最小位置。Docs 檢查範圍至少包括：

- `README.md`
- `app/agent/README.md`
- `app/agent/turns/README.md`
- `app/agent/tools/README.md`
- `app/agent/thinking/README.md`
- `app/SKILLS_GUIDE.md`
- `app/skills/citation/README.md`
- `app/rag/README.md`
- `app/rag/docs/API.md`
- `for_agents/invariants.md`
- `for_agents/architecture-map.md`
- `for_agents/data-flow.md`
- `for_agents/module-responsibilities.md`
- `for_agents/testing-strategy.md`
- `for_agents/dangerous-assumptions.md`
- `for_agents/known-failure-modes.md`
- `for_agents/future-work-backlog.md`
- `issue/07-gui-first-turn-durability-deferred.md`

只修改與實際新行為直接相關的段落；若某檔不存在或內容不相關，在 build log 記錄後略過，不新增替代文檔。

## Authorization and stop conditions

本階段授權測試 fixture migration，不授權對真實使用者 persist directory 執行。若 startup migration 會使正常啟動需要 Ollama、網路或完整 Chroma service，停止並把 importer 改為可選的 local-read boundary；不可犧牲新 JSON conversations 的可用性。

完整 launch block只授權第一組 broad checks；第二次昂貴 broad rerun、任何 dependency 安裝/升級或 lockfile 修改都仍需 fresh approval。若本階段不是由完整 launch block 啟動，任何預估超過約 10 分鐘的命令先請使用者批准。

## Implementation and verification plan

### Preflight

1. 檢查 Phase 01–06 build log，列出所有未解項；任何 correctness blocker 未解就不做 final validation。
2. 固定 migration trigger 與 result reporting；確認有效 target 是唯一 completion signal。
3. 盤點現有跨語言 test harness 與 fixtures，選最小能證明 full journey 的路徑。
4. 記錄測試開始前 `git status --short --untracked-files=all`，把既有user-owned與本計畫task-owned paths分開，避免覆蓋使用者變更或提交generated stores；後續untracked audit只對本計畫相對baseline新增的paths主張所有權。

### Red

補齊仍缺的失敗/旅程 tests，至少能區分：

1. prompt JSON temporary write 前失敗：provider/tool 未執行、draft 可重送。
2. pending publish 後、provider 前 crash：重啟顯示 interrupted，不 auto replay。
3. provider/tool 中斷：保留 accepted prompt 與非 completed state。
4. finalization/citation rejection：不得持久化不安全 completed text。
5. completed temporary write/replace 失敗：不得對 UI 回 terminal success。
6. completed commit 後、response delivery 前中斷：retry 同 ID 只回/恢復同一結果，不重複 side effect。

以上六個checkpoint都必須使用既有Desktop fixture/subprocess能力的最小延伸、fake provider/tool與deterministic test latch，真正終止process後restart並檢查JSON/UI/side-effect sentinel；不能以同process exception mock取代process-kill gate。Atomic tempfile/fsync/replace失敗另以deterministic低層fault injection補充。若任一checkpoint在live architecture中技術上無法精確停住，Phase 07必須標Blocked並記錄原因，不得用「代表性」較少案例宣告通過。另覆蓋 duplicate request、external rewrite conflict、truncated/malformed file isolation、unknown schema、catalog orphan/missing、50 turns UI transcript 與模型只取最後 10 個 eligible turns。

### Green

1. 接上同步、逐 conversation、可重跑的 migration hook；每筆 structured result 可被安全記錄/顯示。
2. 僅針對 tests 揭露的缺口修正 lifecycle/retry/catalog；不得藉最終階段展開重構。
3. 實作/完成 cross-language fixture journey：建立 turn → durable pending → completed → shutdown/restart → sidebar select → transcript 恢復 → 送出下一個 prompt；驗證下一個 context 與 turn number，並證明 no Plan/log/chat-history new writes。
4. 依實際 code 更新 active docs 與 invariants，清楚標出 legacy source retained、single writer、no automatic replay、latest-10、display-only、RAG preserved。
5. 在 `for_agents/invariants.md` 明確retire/replace舊 `INV-006`（Plan-only persistence）與 `INV-016`（switch-before-flush），並在architecture/data-flow/tools docs明確移除Chroma history lifecycle與`recall_history` workflow；不要只做泛稱更新。
6. 對 issue 07/backlog 只記錄已由測試證實的狀態，不宣稱真實資料 migration 已執行。

### Refactor

- 移除本計畫引入的 temporary diagnostics、unused fixtures 與 dead adapters。
- 不做廣泛格式化或無關 docs cleanup。
- 逐一檢查 generated `app/store/`, `app/dist/`, caches、screenshots 沒有進入 diff。

### Verification

先跑所有受影響 focused tests；通過後只在此階段跑一次 broad suites：

```bash
conda run -n app poetry run pytest
```

再從 `app/desktop/` 執行：

```bash
conda run -n app npm test
conda run -n app npm run build
conda run -n app cargo test --manifest-path src-tauri/Cargo.toml
conda run -n app npm run tauri -- build --no-bundle
```

最後執行：

```bash
git diff --check
git status --short --untracked-files=all
```

`git diff --check`只覆蓋tracked diff。對相對Phase 07 preflight baseline由本計畫建立的task-owned untracked files，另逐檔執行`git diff --no-index --check /dev/null <path>`並檢查文字輸出：no-index因「檔案不同」回exit 1是預期，任何whitespace診斷文字才是failure；同時人工開啟這些task-owned新檔確認內容。Baseline已存在的無關user-owned untracked files只列入overlap報告並保持不動，不得因本任務而讀寫或宣稱通過。另以`git grep --untracked -n -I -E '<精確pattern>' -- <active source/test/doc roots>`做residue searches，分別驗證 active Plan Mode、conversation `recall_history`/Chroma/flush 已消失，document RAG 與 Bash `grep`/`read_file` 仍存在。精確pattern、roots、exit code與allowlist必須寫入build log；plain `git grep`或plain `git diff`不得作為涵蓋未stage檔案的證據。

## Reliability, security, and recovery

- Migration 永不刪 legacy source；真實資料 rollout 另需備份、dry run 與授權。
- Startup 中一個 legacy conversation 失敗不可阻斷新 JSON conversation 或其他健康 migration。
- 六個 fault points 都以 observable user state 驗證，不只斷言內部 method 被呼叫。
- Duplicate/retry 測試需包含 side-effect spy，不能只檢查 JSON turn count。
- Docs 不可把 single-writer local contract 描述成 multi-process safe，也不可宣稱 production readiness。

## Acceptance Criteria

- [ ] Fixture-based one-time migration 可重跑、逐會話隔離、以有效 target 判成功，且 legacy source 完整保留。
- [ ] 六個 durability fault points 均有直接測試，UI/JSON/provider side-effect 結果符合 contract。
- [ ] 六個checkpoint逐一使用真正subprocess termination→restart驗證；fake provider/tool side-effect sentinel與各checkpoint observable結果都有evidence，任何無法注入的點會阻擋完成。
- [ ] 50-turn transcript 可恢復顯示；context 只含最新 10 個 completed eligible pairs，current prompt 一次。
- [ ] Full Desktop cross-language journey 通過，stable logical ID 跨 retry/restart 不變。
- [ ] 新執行只寫 canonical JSON/catalog，不寫 Plan logs 或 conversation-history Chroma。
- [ ] Document RAG、normal/extended thinking、Skills、Citation、SafeContent 與 Bash approval 的代表測試通過。
- [ ] 固定 conversation root 的 exact-text grep/read-file workflow 有可見、approval-gated 證據；paraphrase miss 不觸發 embedding/RAG fallback。
- [ ] Active docs/invariants 與實際實作一致，historical records 未被機械式改寫。
- [ ] `INV-006`、`INV-016`、Chroma history lifecycle與`recall_history` workflow已在active docs被逐項retire/replace，並指向新的JSON invariants。
- [ ] One-shot Skill restore、forged-tool rejection、Bash/extension/prune approval與active-turn switch guards都有可定位的focused/full-suite evidence。
- [ ] Broad suite/build 的結果、已知非本次失敗與未執行項目都如實記錄。
- [ ] Final diff 只含必要 source/tests/docs，沒有 user data、generated stores、secrets 或 caches。
- [ ] Task-owned tracked/untracked working-tree files都經residue、whitespace與content audit；既有無關user-owned files被保留並分開報告，證據未誤用只看index的plain `git grep`/`git diff`。

## Evidence to record

在 `build-log.md` Phase 07 區塊逐項填入 migration fixture counts、六個 fault結果、50/10 assertion、cross-language journey、所有命令/exit code/duration、residue allowlist、docs changed、final status。未執行的真實 migration 必須明寫「Not run; requires fresh authority」。

## Handoff

完成後由 fresh agent 依 `PROMPTS.md` 的 final review prompt 做獨立走讀：從實際 live checkout/current diff（保留所有 user-owned changes）與 isolated empty/legacy fixture roots出發，確認每個 goal有 code+test evidence，並檢查沒有 automatic replay、silent overwrite、legacy deletion或 RAG regression。Review未通過時只回到最早失敗的 phase修復，不開新架構工作流。
