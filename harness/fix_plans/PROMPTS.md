# Research Agent Desktop GUI 修復 — Copy-ready Prompts

## 使用方式

這些 prompt 只在使用者實際貼回 coding agent 時生效。本 bundle 的存在，以及 2026-08-31 對 plan-authoring 檔案的 commit/push 授權，都**不**授權後續修改 application code、建立 implementation commit 或 push。

推薦用「開始／繼續完整計劃」啟動。Agent 必須從 durable files 與 dependency graph 找下一個 eligible phase，不可依聊天記憶猜測，也不可每個 phase 都停下要求確認。

## Start/Resume — 開始／恢復完整計劃（推薦）

```text
請開始或繼續執行 /home/minervamuses/research-agent-workspace/harness/fix_plans 的長期修復計劃。

先完整重讀適用的 AGENTS.md、harness/fix_plans/PROMPTS.md、GOALS.md、PLANS.md、user-decisions.md、build-log.md，以及由 build-log status 與 PLANS dependency graph 算出的第一個 eligible phase。以 live source/tests/Git state 為最強事實來源；不要重開已完成的舊 GUI plan。

我在這次訊息中明確授權你：
- 在 PLANS.md authorization envelope 與各 phase causal scope 內修改直接相關的 Python、React/TypeScript、Rust、internal protocol、built-in Skill manifest/system prompt、Plan log versioned format、fixture 與 tests；
- 為移除既有 Task mode 全鏈與完成 USER DECISION 011，觸及超過三個明列的 production files，並做最小的 Plan log v2 / transcript DTO 相容延伸；
- 使用現有 dependency graph，以 Conda app、Poetry、npm、Cargo 執行各 phase focused checks，並在 Phase 07 只執行一次計劃列出的 broader suites/build；
- 在每個通過 focused verification、diff/scope audit 的 coherent checkpoint 建立只包含該 phase 的 local Git commit，並把 hash 記入 build-log.md。

這次授權不包括：新增或更新 dependency/lockfile、live/paid provider、真實 MCP/Ollama/user store/credential、Fusion、Extended Thinking、Citation redesign、first-turn durability、多 GUI process、branch/worktree/rebase/merge、remote push、release/deployment，或其他 GOALS non-goal。需要其中任一項時先停止該 path、記錄 evidence，再一次提出最小 fresh-authority request。

完成 runtime/dirty-tree gate 後，選第一個 Not started 或 In progress 且 dependencies 全部 Complete 的 phase。每個 phase 先記錄 write set/hypothesis/attempt，做最便宜的 focused rejecting check，再做最小實作；exact command/result、failure、checkpoint 與 status 都寫入 build-log.md。不要把 planned command、post-finalized chunk、unsafe draft stream 或 legacy tool text 當成 pass evidence。

Phase 完成後直接繼續下一 eligible phase，不要因正常 checkpoint 暫停。只有全部 required phases Complete，或所有有意義的剩餘路徑都因同一已證實 blocker 需要 fresh authority 時才停止。最後回報實際 changed files、checks、commit hashes、deferred issues 與未執行事項；不要 push。
```

## 只查看狀態（read-only）

```text
請只讀檢查 /home/minervamuses/research-agent-workspace/harness/fix_plans 的目前執行狀態。完整讀取 GOALS.md、PLANS.md、user-decisions.md、build-log.md 與目前 phase，並用 live Git state 核對。回報：最後完成 checkpoint、下一個 eligible phase、實際 pass/fail evidence、dirty-tree ownership、blockers，以及需要我的最小決策。不要編輯、測試、commit 或 push。
```

## 執行單一階段（diagnostic／受限執行）

```text
請只執行 /home/minervamuses/research-agent-workspace/harness/fix_plans 的 Phase <NN>，不要自動進入下一 phase。

先完整重讀適用 AGENTS.md、GOALS.md、PLANS.md、user-decisions.md、build-log.md 與該 phase，確認 dependencies 已在 build-log.md 有 Complete evidence；若尚未完成，只回報 dependency gap，不繞過。

我這次授權只限該 phase 在 PLANS.md authorization envelope 內的直接相關 application/test變更、focused verification與一個phase-scoped local commit；不授權dependency/lockfile、live provider/MCP/Ollama/real data、non-goals、branch/worktree、push或release。開始前記錄runtime/dirty-tree/write set/hypothesis，完成後把exact evidence、status與commit disposition寫入build-log.md並停止。
```

## Blocked 後提供新 authority 並恢復

```text
請恢復 /home/minervamuses/research-agent-workspace/harness/fix_plans。先從 build-log.md 找到已記錄的 blocker、attempt evidence 與所有仍 eligible 的 phase，不要重跑沒有新 hypothesis 的失敗命令。

我這次新增授權只有：<在此寫明精確動作、檔案/介面、成本與邊界>。

除這段新增授權外，仍遵守 GOALS.md、PLANS.md、user-decisions.md、目前 phase 與原本 non-goals。更新 build-log.md 的 authorization/blocker disposition，再從最小能區分假設的 checkpoint 繼續。若新增授權仍不足，說明哪一個 concrete action 缺 authority；不要自行擴張。
```

## 修復 durable plan（不實作）

```text
請 review 並只修復 /home/minervamuses/research-agent-workspace/harness/fix_plans 這個 planning bundle，不修改 app code/tests/manifests/lockfiles。

用 live repository evidence 核對 GOALS、phase graph、write surfaces、acceptance、verification 與 build-log status；保留 user-decisions.md 的明確使用者決策。若 live evidence 推翻計劃，做最小一致性修補，列出理由與受影響 phase，執行 long-horizon plan validator 與 git diff --check。不要把 review 當 implementation evidence，不要 commit 或 push，除非我在同一訊息另外明確授權。
```

## Final review（implementation 完成後）

```text
請對 /home/minervamuses/research-agent-workspace/harness/fix_plans 已完成的 implementation 做 read-only final review。以 GOALS success conditions、user-decisions、每個 phase acceptance、build-log actual evidence、live diff/commits/tests 為準；特別檢查：
1. Normal streaming 是否真的在 terminal result 前出現且只含 accepted final-answer text；
2. 一般 Skill 是否在 success/error/cancel/shutdown 後清除非 Citation transient state；Citation pre-state 的 failed generic command 是否保持不變、successful switch 是否 teardown/no-restore，且 deferred boundary 未被改寫；
3. Conversation restore 是否從不重跑舊工具，legacy tool data 是否只 display-only；
4. MCP default 與 long-request liveness 是否沒有引入另一個 hidden off/default 或 arbitrary timeout；
5. dependency、lockfile、provider、credential、real store 與 non-goal boundary 是否乾淨。

只回報有證據的 finding，按嚴重度排序並附精確檔案/測試；沒有 finding 就明說。不要編輯、commit 或 push。
```
