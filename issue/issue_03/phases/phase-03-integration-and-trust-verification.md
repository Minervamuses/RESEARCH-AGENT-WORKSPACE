# Phase 03 — Integration and Trust Verification

## Source Inputs

- `../GOALS.md`
- `../PLANS.md`
- `../build-log.md`
- `phase-01-backend-policy-and-contract.md`
- `phase-02-desktop-permission-control.md`
- All material `../context/` and actual `../code_review/` files, if present.
- Actual implementation diff and relevant Python/Node/Rust tests.
- `../../../README.md` desktop verification commands.

## Objective

以 deterministic fake-runner、cross-language protocol、frontend build、Linux
Rust/Tauri checks 與 independent trust-boundary review，證明完整 lifecycle 與隔離
情境；只有每個 `GOALS.md` success condition 都有 observed evidence 時才宣告
Issue 03 完成。

## In Scope

- 代表性 matrix：fresh ask、A bypass、B ask、回 A bypass、切回 ask、active/pending
  setter rejection、backend/app generation reset。
- Ask safe-display/correlation/timeout/replay regression 與 bypass zero-event/
  zero-resolve fake execution。
- Invalid mode 與 malformed/stale ACK rejection。
- Extension apply/MCP exact-binding 與 CLI/non-Desktop Bash 明確隔離。
- Relevant Python/Node/Rust checks、TypeScript/Vite build、Tauri no-bundle build 與
  一次 final broader Python suite。
- Fresh-context review actual diff、evidence mapping、scope containment 與未驗證限制。
- 修正 final verification 直接揭露的 in-scope defect；修正後只重跑能區分該 defect
  與 regression 的最小 checks。

## Non-Goals

- 新功能、polish、general refactor、benchmark 或 test framework。
- 真實 shell command、credential、live/paid provider、使用者資料或 external write。
- 第二次 expensive broad pass，除非 fresh authority。
- Dependency/toolchain/system package 安裝、commit、release 或 deployment。

## Dependencies and Prerequisites

- Phases 01 and 02 在 `../build-log.md` 都是 `Complete`，且 required focused
  evidence 可追溯。
- WSL/Linux Conda `app` Python/Poetry/Node/npm 可用。
- Linux Cargo/rustc 與 Tauri system build prerequisites 可用；若仍缺少，不得安裝。
  記錄 blocker，並取得 fresh authority 以提供或安裝必要環境。僅接受 skipped
  evidence 不符合目前成功條件；若要移除該條件，須先由使用者明確變更目標並
  repair plan。
- Actual diff 未包含不明 ownership 或 out-of-scope changes。
- **Unresolved manual evidence:** provider-free GUI 是否能到達 session controls。
  Preflight 依 live app 判定；不得以 credentialed provider 補足。

## Expected Components Affected

- Existing tests and `app/desktop/protocol/v1/fixtures.json` only when cross-layer
  acceptance coverage仍有直接缺口。
- `../build-log.md` for observed evidence。
- `../context/phase-03-integration-and-trust-verification-context.md` only for material
  discovery。
- `../code_review/phase-03-integration-and-trust-verification-review.md` only after the
  required actual review。
- Production files only for a concrete in-scope defect found by verification；先在
  `build-log.md` 記錄 causal link，不做 cleanup。

## Authorization and Stop Conditions

- Missing Linux Cargo/Tauri prerequisite、預期超過十分鐘的 command、第二次 broad
  pass 或任何 install 需要 fresh authority。
- Required Rust/Tauri evidence unavailable 時，本 high-risk plan 保持 `Blocked`；
  skipped 不等於 pass。改變此 success condition 需要明確的使用者決策與 plan
  repair，不能由執行者自行降級。
- 發現 persistence、Extension/MCP trust、CLI behavior 或 protocol compatibility
  regression 時先修復；不可把它列為 optional completion limitation。
- Scope expansion、real command/provider/data、dependency 或 Git mutation 立即停止。

## Implementation and Verification Plan

### Preflight

- Reload every acceptance criterion and map it to existing Phase 01/02 evidence；找出
  尚未由 direct observation 覆蓋的項目。
- Inspect actual diff for protocol mirror parity、default ask、active ownership、
  no-persistence、no-auto-resolve and isolated trust paths。
- Confirm current WSL/Linux tool paths and estimate broader commands before running。
- Run no live command/provider；all execution assertions must use existing fake runners。

### Characterization

本 phase 不要求 ceremonial Red。先執行 representative fake-runner journey 與
targeted isolation checks；任何 failure 都是待診斷的 observable baseline。

Required journey 必須觀察：

1. Fresh A 是 ask，safe Bash 只有 resolve 後 fake runner 執行。
2. A setter ACK 後是 bypass；兩個連續 calls 各執行一次且 event count 為零。
3. Fresh B 是 ask；回 A 恢復 bypass。
4. A 切回 ask，下一個 call 再次等待 resolve。
5. Active/pending 時 setter 失敗且 pending command 不執行。
6. New service/backend generation 與 UI generation reset 後 A/B 都回 ask。
7. Ask unsafe context 仍 zero-event/zero-run；bypass secret-like fake context只進 fake
   runner且不跨 UI event。
8. Extension/MCP/CLI 結果不因 Bash mode 改變。

### Green/Repair

- 只修正上述 journey、build 或 review 揭露的 causal defect。
- 一次變更一個主要 hypothesis，先跑最小 focused check再回到 failed integration
  check。
- 相同原因兩次 focused attempt 失敗後，記錄 blocker並停止猜測性修補。

### Verification

From `/home/minervamuses/research-agent-workspace/app`:

- **Relevant Python regression:**
  `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_bash_tool.py tests/test_tool_inventory.py tests/test_tool_access_matrix.py tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_fixture.py tests/test_desktop_server.py tests/test_extension_mcp.py -q`
- **One final repository suite:**
  `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest`

From `/home/minervamuses/research-agent-workspace/app/desktop`:

- **All Node tests:** `/home/minervamuses/miniconda3/bin/conda run -n app npm test`
- **Frontend build:** `/home/minervamuses/miniconda3/bin/conda run -n app npm run build`
- **All Rust tests:**
  `/home/minervamuses/miniconda3/bin/conda run -n app cargo test --manifest-path src-tauri/Cargo.toml`
- **Linux Tauri source build:**
  `/home/minervamuses/miniconda3/bin/conda run -n app npm run tauri -- build --no-bundle`

From repository root:

- **Whitespace/path sanity:** `git diff --check`
- **Scope review:** `git status --short` and `git diff --stat`, followed by direct review
  of every changed production/test/plan file。

- **Manual UI:** Only if controls are reachable without credentials/provider/real Bash,
  inspect default and narrow layout, current-mode visibility, labels, keyboard operation
  and disabled state。Otherwise record unavailable and use deterministic render/build
  evidence。
- **Failure behavior:** Required failure keeps Phase 03 `In progress` or `Blocked`；
  overall plan cannot complete。Do not repeat a broad command without a new hypothesis。

### Independent Review

Use a fresh agent context or equivalent independent reviewer。Compare actual diff and
observed evidence directly with `GOALS.md`，focusing on：

- bypass branch after active ownership but before display/pending staging；
- ask fail-closed path unchanged；
- atomic A/B snapshot commit and restart clearing；
- strict setter result validation and stale ACK rejection；
- absence of persistence, auto-resolve, new concurrency, dependency and unrelated trust
  changes；
- fake-runner-only execution evidence and honest unavailable checks。

Record actual findings in
`../code_review/phase-03-integration-and-trust-verification-review.md`。Resolve findings
or obtain explicit user acceptance before completion。

## Reliability, Security, and Recovery

- Trust risk is bounded by explicit per-conversation selection, backend ownership,
  generation reset and default ask。
- Deterministic fake runner proves routing without creating shell side effects。
- Cross-language validation and build catch partial protocol rollout。
- Extension/MCP/CLI isolation prevents privilege widening。
- Recovery is local：keep phase incomplete, repair/revert the scoped diff, rerun only
  affected focused checks, then the previously failed acceptance check。No migration or
  operational rollback applies。

## Acceptance Criteria

- [ ] The complete eight-step representative journey above has exact observed fake-runner
      and event-count evidence。
- [ ] A→B→A、ask↔bypass、active/pending、backend/app reset and stale ACK match
      `GOALS.md`。
- [ ] Ask safety/correlation/timeout/replay、Extension/MCP trust and CLI Bash behavior
      pass direct regressions。
- [ ] Python、JSON fixtures、TypeScript and Rust agree on the additive protocol。
- [ ] Relevant Python regression、one final Python suite、all Node tests、frontend build、
      all Rust tests and Tauri no-bundle build pass，或任何 unavailable required check
      remains explicitly Blocked rather than misreported。
- [ ] No dependency、persistent format、queue/concurrency system、credential、real
      command、user-data or out-of-scope change exists。
- [ ] Independent review findings are resolved or explicitly accepted。
- [ ] `git diff --check` passes and worktree ownership remains clear。

## Evidence to Record

- Acceptance criterion → exact test/procedure mapping in `../build-log.md`。
- Exact command、tool/runtime、duration when relevant、concise result and limitation。
- Material discovery only in `../context/phase-03-integration-and-trust-verification-context.md`。
- Full actual review in
  `../code_review/phase-03-integration-and-trust-verification-review.md`。
- Do not record planned checks as passed or copy secrets/full logs。

## Handoff

- Mark Phase 03 `Complete` only when every overall completion criterion in `../PLANS.md`
  has observed support and no required blocker remains。
- Final report leads with the user-visible outcome，then exact changed files、checks/results、
  preserved boundaries and honest limitations。
- Do not continue polishing、commit、push、deploy、publish or release after completion。
