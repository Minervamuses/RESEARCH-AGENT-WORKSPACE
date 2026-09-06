# Issue 03 — Desktop Bash 權限模式：可重用指令

本檔提供可直接複製的 entry points，不擁有 scope、phase status 或 observed
evidence。`GOALS.md`、`PLANS.md`、selected phase 與 `build-log.md` 分別是
對應的 source of truth。以下 launch block 只有在使用者實際送出時才構成
implementation authority；計畫檔本身不授權實作。

## Start or Resume End-to-End Execution

將下列完整區塊送給 coding agent：

> 在 WSL/Linux repository `/home/minervamuses/research-agent-workspace` 執行
> `issue/issue_03` 的長期計畫。
>
> 我明確授權此計畫直接必要的 implementation：可修改 `PLANS.md` 所列的超過
> 三個 production files、application tests 與 shared fixtures，並對
> protocol-v1 加入 backward-compatible 的 Bash permission method、enum、
> session snapshot field 與 setter result schema。完成一個 phase 後，在
> authorization envelope 內繼續下一個 eligible phase，不需逐 phase 再問。
>
> 我授權使用 Conda `app` 在 WSL/Linux 執行各 phase 明列的 focused checks、
> Node/TypeScript build、Linux Rust tests、Tauri no-bundle build，以及最後一次
> 合理且預期不超過十分鐘的 broader Python/Node regression。若需要安裝或升級
> dependency、Rust/Cargo、Tauri system package，執行預期超過約十分鐘，或需要
> 第二次 expensive broader run，先停止並取得我的新授權。
>
> 這項授權不包含 persistent format、protocol version/envelope、queue 或新
> concurrency model、credential/live provider、真實 Bash 驗證、使用者資料、
> commit/push/merge/rebase、branch/worktree change、deploy、publish 或 release。
> 不得修改 `AGENTS.md`。
>
> 開始前完整讀取所有 applicable `AGENTS.md`、`issue/issue_03/GOALS.md`、
> `issue/issue_03/PLANS.md`、`issue/issue_03/build-log.md`、第一個
> dependencies 已完成但自身未完成的 phase file，以及存在時相關的
> `context/`／`code_review/`。重新核對 live repository 與 worktree，
> 以 `build-log.md` 判定 runtime status，以實際觀察優先於 stale plan。
>
> 每個 eligible phase 都先做 read-only preflight，重述 scope、non-goals、
> planned checks 與 stop conditions；只實作該 phase；使用最小 red/
> characterization、green、必要 refactor 與 verification；required check
> 失敗時先修正，不得開始 dependent phase。把 exact observed evidence 寫入
> `build-log.md`，只有 material discovery 才寫 `context/`，只有實際 review
> 才寫 `code_review/`。新證據若推翻後續計畫，先修正 `PLANS.md` 與受影響的
> 未開始 phase files。
>
> 持續到整體完成，或遇到 `PLANS.md` 定義的 fresh-authority／external-state
> stop condition。不得把 planned、historical、skipped 或 unavailable check
> 寫成通過。

## Autonomous Execution Loop

收到上方完整 launch prompt 後：

1. 重新讀取 applicable `AGENTS.md`、`GOALS.md`、`PLANS.md`、
   `build-log.md`、selected phase 與相關 live files。
2. 從 `build-log.md` 找出第一個不是 `Complete` 且 dependencies 都是
   `Complete` 的 phase；不得使用另一個 mutable current-phase pointer。
3. 先確認 WSL/Linux root、Conda `app`、Git、Python/Poetry、Node/npm，以及該
   phase 需要的 Cargo/rustc 都屬於正確 runtime。缺少必要 tool 時只做 read-only
   discovery，依 `PLANS.md` 記錄 blocker。
4. 核對並保留所有 pre-existing worktree changes，於 `build-log.md` 記錄本
   phase exact write set。
5. 實作 selected phase 的最小 causal slice，跑 phase 內每個 required check。
6. Check failure 時保持 phase `In progress`／`Blocked`，先找能區分原因的
   observation；不要讓 failure 流入下一 phase。
7. 將 exact command/procedure、environment、pass/fail/unavailable 與限制記入
   `build-log.md`。
8. 只有 material discovery 才建立
   `context/phase-<NN>-<slug>-context.md`；只有真實 review 才建立
   `code_review/phase-<NN>-<slug>-review.md`。
9. 新證據若使未開始 work 無效，保留已完成 evidence，先修正 roadmap 與受影響
   phase files，再繼續。
10. 在 autonomous mode 直接選下一個 eligible phase；只在整體完成或記錄的
    stop condition 停止。

## Execute One Phase

先讀取與 end-to-end prompt 相同的 durable sources。使用者必須明確指出 phase，
且 `build-log.md` 必須顯示其 dependencies 已 `Complete`。

只執行該 phase 的 read-only preflight、bounded implementation、required
verification 與 evidence recording。不要開始後續 phase，不要把單 phase 要求
解讀成超出 `PLANS.md` 的 authority。

## Verify a Phase

讀取 named phase、`GOALS.md`、`PLANS.md`、`build-log.md`、actual diff 與
material context。直接把每個 acceptance criterion 對應到 strongest available
observed check；挑戰 default-deny、ownership、stale ACK、restart reset、
Extension/MCP/CLI 隔離與沒有真實 command execution 的證據。

只有 review 真正發生時，才在 `code_review/` 記錄 findings、verification、
remediation status 與 limitations。Builder narrative 不是 proof。

## Repair the Plan After Contradictory Evidence

讀取全部 durable sources、affected phase files、material context/review 與 live
repository。指出哪一項 planned understanding 被什麼 evidence 推翻；除非使用者
明確改變 stable intent，否則不改 `GOALS.md`。只更新 roadmap、PROMPTS、
`build-log.md` correction 與受影響的未開始 phase files；此 planning repair
task 不實作 application code。

修正後重新執行 long-horizon plan validator 與 fresh-agent walkthrough。

## Final Integration Review

以 fresh agent context 或其他獨立 deterministic oracle，逐項比較 live diff、
`build-log.md` evidence、`GOALS.md` success conditions 與 `PLANS.md` overall
completion criteria。重跑 Phase 03 指定的 representative checks，特別檢查：

- bypass 只在 valid active Desktop Bash turn 放行，且不產生 approval event；
- ask 的 fail-closed、correlation、timeout 與 replay protection 未弱化；
- A→B→A 與 restart lifecycle；
- UI 只接受 valid、same-generation、same-session ACK；
- Extension apply、MCP binding 與 CLI Bash 完全隔離；
- protocol JSON/Python/TypeScript/Rust parity；
- 無 persistence、dependency、queue、credential、真 Bash 或 user-data scope
  expansion。

Required evidence 缺少時不得宣告完成。只有實際 review 才建立
`code_review/phase-03-integration-and-trust-verification-review.md`。

