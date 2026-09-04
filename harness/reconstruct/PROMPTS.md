# Canonical Conversation JSON 與 Plan Mode 退場 — Reusable Prompts

## Start or Resume End-to-End Execution

`PROMPTS.md` 不會像 `AGENTS.md` 自動載入。要正式啟動實作，請把以下完整 block 當成一則新訊息送給 coding agent；只說「開始下一階段」不等同於這份明確授權。

```text
執行 long-horizon plan `harness/reconstruct`，並把這次訊息視為明確的 implementation launch authorization。

在任何修改前，完整閱讀：
1. 所有適用的 AGENTS.md；
2. harness/reconstruct/GOALS.md；
3. harness/reconstruct/PLANS.md；
4. harness/reconstruct/PROMPTS.md；
5. harness/reconstruct/build-log.md；
6. 第一個尚未 Complete 且 dependencies 已 Complete 的 phase file；
7. 已存在且與該 phase 相關的 context/ 與 code_review/；
8. 該 phase 直接相關的 live source、tests、manifests 與 current diff。

先執行 read-only project/runtime/ownership gate：root 必須是 `/home/minervamuses/research-agent-workspace`，runtime 必須是 WSL/Linux，所有 Python/Poetry/Node/npm/Rust/Cargo commands 使用 Conda `app`。檢查 branch、HEAD 與 `git status --short`；所有 pre-existing changes 都視為 user-owned，不得 reset、restore、stash 或覆寫。

我明確授權在 GOALS 與每個 phase 的 causal scope 內，修改超過三個直接相關 production files；建立最小 `app/agent/conversations/` package 與 tests；加入一-conversation-一-JSON persistent schema；實作 prompt-first 與 finalized-response durability；建立 non-destructive legacy importer；原地同步更新 desktop protocol v1 contract/fixtures/Python/TypeScript/Rust implementations；移除 `session.set_mode`、Plan fields、Plan writer、conversation Chroma runtime 與 `recall_history`。這份授權只涵蓋 GOALS 已固定的 schema/API 變更，不涵蓋其他 public API、資料格式或架構擴張。

我授權使用 isolated temporary roots、fake providers/runners、現有 repository tools與 phase-specific tests。Phase 07 可執行一次完整 Python suite、一次 npm test、一次 Cargo test與一次 Tauri no-bundle build，即使第一次 final command set 約超過十分鐘；Tauri設定的`beforeBuildCommand`提供唯一一次npm production build，不另跑`npm run build`。第二次昂貴 broad pass需重新取得我的同意。不得呼叫 live/paid provider、讀 credentials、操作真實 user store、執行真實資料 migration，或刪除/移動 legacy data。

每個logical change完成focused verification後都要使用簡短Conventional Commit提交；這項授權不包含push、merge、rebase、branch/worktree切換、deploy、release或publish。Dependency/environment/manifest/lockfile 變更、service/database/queue/background worker/new concurrency model、compatibility framework、conversation semantic index、多 writer與AGENTS.md 修改都沒有授權。如確實不可避免，先把 affected phase 標為 Blocked，說明最小必要變更、較小方案為何不足，以及時間/usage/maintenance cost。

依 PLANS.md 的 autonomous execution mode逐 phase 執行：每次只實作一個 eligible phase，先 preflight，做最小 Red/characterization、Green、必要的局部 refactor與 required verification。任何 required check失敗都不得前進。每次 phase開始、material failure/checkpoint與完成時，將 exact observed evidence寫進 build-log.md；只有 material discovery才建立 context file；只有真 review才建立 code_review file。Evidence推翻未開始的計畫時，先修訂 PLANS.md與 affected unstarted phase files，再繼續。

完成一個 phase後重新讀 durable sources並自動選下一個 eligible phase。只在全部完成，或所有 meaningful remaining work都被 fresh-authority/external-state/safety blocker 阻擋時停止。不要實作額外 cleanup或鄰近 backlog。
```

### Selection and failure rules

Start/Resume agent 必須從 `build-log.md` 與 `PLANS.md` dependency order推導下一 phase，不得依賴 conversation memory或 mutable pointer。若 interrupted phase標為 `In progress`，先 reconcile live diff與 evidence，再跑最小 safe baseline；不得盲目重播 external/destructive operation。

一個 required check失敗時，phase保持 `In progress` 或 `Blocked`。同一 causal hypothesis兩次 focused implementation attempt失敗後，記錄證據並停止該路徑。由於目前 roadmap是 sequential chain，通常沒有可獨立跳過的 later phase。

## Execute One Phase

只有當使用者明確指定單一 phase時才使用：

```text
只執行 `harness/reconstruct` 中使用者指定的單一 phase。先完整閱讀 applicable AGENTS.md、GOALS.md、PLANS.md、PROMPTS.md、build-log.md、該 phase file、相關 context/review 與 live source/tests。完成 WSL/Linux + Conda app runtime/ownership gate，確認 dependencies 已在 build-log.md 有 evidence支持為 Complete。

只做該 phase 的 causal scope，執行它的 required checks，將 observed results寫回 build-log.md，必要時記 material context，然後停止。不要開始 later phase；不要把 planned command寫成 passing evidence；不要擴張授權。
```

## Verify a Phase

```text
審查 `harness/reconstruct` 中使用者指定的 phase。閱讀 applicable AGENTS.md、GOALS.md、PLANS.md、build-log.md、phase file、相關 context，以及 actual diff/live behavior。逐項把 acceptance criterion映射到真正執行的 command、fixture journey或 inspection evidence，特別挑戰 prompt/response write ordering、retry exactly-once、data loss、legacy non-destruction、SafeContent/approval與 RAG preservation。

只在實際 review發生後建立 `harness/reconstruct/code_review/phase-NN-slug-review.md`。有 missing evidence或 finding時不得把 phase標 Complete；不要在這個 review prompt下修改 application code，除非使用者另行要求修復。
```

## Repair the Plan After Contradictory Evidence

```text
修復 `harness/reconstruct` plan，不實作 application code。完整閱讀 applicable AGENTS.md、GOALS.md、PLANS.md、PROMPTS.md、build-log.md、affected phase files、material context/review與 live repository evidence。

指出哪個 planned understanding被什麼 observation推翻；保留 stable GOALS，除非使用者明確改變 outcome/scope/invariant。只更新必要的 roadmap與尚未 Complete的 phase files，在 build-log.md append material correction，不抹除先前失敗證據。重新執行 harness validator、git diff --check與 fresh-agent walkthrough後停止。
```

## Final Integration Review

```text
對 `harness/reconstruct` 做 fresh-context final integration review。從 GOALS.md success conditions與 PLANS.md completion criteria出發，直接檢查 live diff、build-log evidence、protocol fixtures、migration/failure artifacts與 representative user journeys。

確認：prompt durable前沒有 provider/tool；finalized response durable前沒有 terminal success；retry/restart不重複；50-turn UI與latest-10 context；A→B→A；catalog reconcile與per-file degradation；Plan Mode/recall/history runtime residues消失；Extended Thinking、Citation、Skills、SafeContent、Bash approval與document RAG保留；legacy sources未被刪除；真實 user data/credentials未被操作。把真正 findings寫入 code_review/，missing required evidence時不得宣告 overall complete。
```
