# Research Agent Desktop GUI 修復 — Build Log

## Phase Summary / 階段摘要（Mutable Status Authority）

本檔是唯一 mutable execution status。Phase files 的 `Initial status` 只描述 authoring 起點；後續 agent 必須以本表與 dependency graph 選工作。

| Phase | Status | Attempts against current cause | Last checkpoint | Evidence / 證據 | Commit |
| --- | --- | ---: | --- | --- | --- |
| 01 — MCP defaults | Complete | 1 | Focused verification and scope audit passed | CLI/backend observed `True` default and `False` opt-out; sole React caller omits `loadMcp`; Python `56 passed`, Node `7 passed` | `f625d7b0f8c43c9970898dd0d34baeacdaadd3b3` |
| 02 — Long-request liveness | Complete | 1 | Focused verification and scope audit passed | No normal absolute timeout; long result order passed; backend selector `20 passed`; terminal/startup/shutdown cases preserved | Pending phase commit |
| 03 — One-shot Skill runtime | Not started | 0 | None | None | None |
| 04 — Desktop Skill command | Not started | 0 | None | None | None |
| 05 — Normal live streaming | Not started | 0 | None | None | None |
| 06 — Tool-aware conversation restore | Not started | 0 | None | None | None |
| 07 — Integration acceptance | Not started | 0 | None | None | None |

## Current Checkpoint

- Phase 01 focused implementation、scope audit與local implementation commit `f625d7b0f8c43c9970898dd0d34baeacdaadd3b3` 完成；hash-record commit是`21bcadfac3277c6f7a9a5926ac7944e82bdad8fa`。
- Phases 01–02 focused implementation與scope audit完成；Phase 02 local commit/hash recording pending。
- Next eligible phase是Phase 03（dependencies none）。
- Blockers: none recorded。
- Implementation authorization: active under the 2026-09-01 Start/Resume message and [`PLANS.md`](PLANS.md) envelope。
- Local phase-scoped commits: authorized；remote push remains unauthorized。
- Broader-suite counters remain `0`；Phase 01只執行focused selectors。

## Authoring Baseline — 2026-08-31 Asia/Taipei

- Repository: `/home/minervamuses/research-agent-workspace`
- Runtime selected: WSL/Linux；commands 必須用 Linux Git/toolchain，Python 使用 Conda environment `app`。
- Branch/upstream observed: `GUI` / `origin/GUI`。
- Initial HEAD observed: `fa24b086e8dcf5bdae1a8db228b4337e9798df65`。
- Initial user-owned untracked inputs observed: `harness/fix_plans/user-decisions.md`、`issue/07-gui-first-turn-durability-deferred.md`、`issue/08-desktop-absolute-request-timeout.md`；本 plan 又依使用者批註加入 issue 09 與 bundle files。
- No application test、build、provider、MCP、Ollama、live GUI journey 或 persistent-data mutation was run as implementation evidence during authoring。

## Shared Safety Counters

- Live/paid provider calls: `0`；budget in this plan: none authorized。
- Real MCP/Ollama calls: `0`；budget in this plan: none authorized。
- Full Python broader suite runs: `0`；planned maximum before fresh authority: one, in Phase 07。
- Full Cargo suite runs: `0`；planned maximum before fresh authority: one, in Phase 07。
- Tauri no-bundle builds: `0`；planned maximum before fresh authority: one, in Phase 07。

## 2026-08-31 — Plan-authoring Validation（非 implementation evidence）

- Long-horizon harness strict validator 以 repository shape `application`、risk `medium`、`harness-only` 與精確 13-file proposed/allowed write set執行；final observed result是 `valid: true`、`errors: 0`、`warnings: 0`。
- Main-agent structural walkthrough確認7個phase各有objective/scope/non-goals/dependencies/verification/acceptance/handoff，所有status仍為`Not started`，dependency graph從numeric-first eligible Phase 01開始。
- Independent fresh-agent walkthrough只找到一個cross-file contradiction：Phase 04曾列完整`npm test`，與Phase 07唯一broader npm pass衝突。Phase 04已改成targeted protocol/conversation/backend Node selectors，strict validator於修正後重新通過。
- No application test、build或implementation acceptance was run；本節只證明planning bundle結構與交接可讀性，不使任何phase成為Complete。

## 2026-09-01 00:17 CST — Phase 01: runtime/source preflight

- Status transition: `Not started` → `In progress`。
- Durable sources reloaded: root `AGENTS.md`、`PROMPTS.md`、`GOALS.md`、`PLANS.md`、`user-decisions.md`、本檔與 `phases/phase-01-mcp-defaults.md` 已完整重讀；依 numeric-first eligible rule 選 Phase 01。
- Runtime/Git/dirty-tree gate: repository `/home/minervamuses/research-agent-workspace`；WSL2 Linux；branch `GUI` tracking `origin/GUI`；HEAD `1b4a4a9f989b6fd8aa1beb0a8015156c7ea29d26`；首次寫入前 `git status --short` 無輸出。命令固定由 WSL 執行；Conda `app` 實測 Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0；Linux rustc/Cargo 1.91.1。
- Authorization in force: 使用者本次 Start/Resume 訊息授權 phase causal scope 內 application/tests、focused checks、phase-scoped local commit 與 build-log hash；不授權 dependency/lockfile、live provider/MCP/Ollama/credential/real store、non-goals、branch/worktree、push或release。
- Current causal hypothesis and attempt number: attempt 1。唯一 production defect是 `app/desktop/src/App.tsx` 的 normal create caller明確送 `loadMcp:false`，覆蓋 `DesktopService` 缺省 `true`；CLI `load_mcp=not args.no_mcp` 與 backend explicit-false/default-true semantics 不需 production rewrite，只需 regression protection。
- Exact initial/expanded write set and ownership: `app/desktop/src/App.tsx`、`app/desktop/tests/conversations.test.ts`、`app/tests/test_chat_cli.py`、`app/tests/test_desktop_service.py`、`harness/fix_plans/build-log.md`。全部為 Phase 01 direct scope；初始 tree 無其他 owner change。
- Commands actually run and exact outcomes: read-only `git grep` 找到唯一 React `session.create` caller在 `App.tsx:669` 且 payload 是 `{ loadMcp: false, projectId: activeProjectId }`；Python service `service.py:1128` 是 `params.get("loadMcp", True)`；CLI `chat.py:111` 是 `load_mcp=not args.no_mcp`，parser `--no-mcp` 使用 `store_true`。尚未執行 application test。
- User-visible/fixture observation: none；未啟動 provider、MCP process或 GUI。
- Diff/scope/safety audit: first write只更新本 phase execution log；dependency/lockfile與 application code尚未改動。
- Commit disposition/hash: pending focused verification。
- Blockers or disproved assumptions: `rg` 不在 base shell；後續 repository search 使用 Linux `git grep`。Conda nested login shell會重設 PATH，因此實際命令使用 `/home/minervamuses/miniconda3/bin/conda run -n app <command>`，不使用會解析到 Windows npm 的 host PATH。
- Next eligible action: 先加入 CLI/backend/frontend caller regression，執行最小 red selectors；確認能拒絕現況後只移除 GUI 的 false override。

## 2026-09-01 00:20 CST — Phase 01: focused rejecting check

- Status transition: remains `In progress`；attempt 1 hypothesis retained。
- Durable sources reloaded: unchanged from Phase 01 preflight。
- Runtime/Git/dirty-tree gate: only declared Phase 01 tests and `build-log.md` were dirty before the rejecting check。
- Authorization in force: unchanged；fake/injected tests only。
- Current causal hypothesis and attempt number: attempt 1；Python semantics already correct, React false override is the single causal variable。
- Exact initial/expanded write set and ownership: added regression-only changes in `app/tests/test_chat_cli.py`、`app/tests/test_desktop_service.py`、`app/desktop/tests/conversations.test.ts`; planned production write remains only `app/desktop/src/App.tsx`。
- Commands actually run and exact outcomes: from `app/`, `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_chat_cli.py::test_chat_cli_defaults_mcp_on_and_preserves_explicit_opt_out tests/test_desktop_service.py::test_session_create_defaults_mcp_on_and_preserves_explicit_opt_out -q` → `4 passed, 1 warning in 0.21s`（既有 LangGraph pending-deprecation warning）。From `app/desktop/`, `/home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types --test-name-pattern="MCP" tests/conversations.test.ts` → exit 1, `1 failed`; exact rejection was `TypeError: sessionCreateParams is not a function` at the new normal-create MCP regression。
- User-visible/fixture observation: Python fake factory observed CLI booleans `True`/`False` and Desktop service booleans `True`/`False`; no real MCP loader, process, provider or credential access occurred。
- Diff/scope/safety audit: rejecting diff remains within four declared test/log files；no dependency、lockfile或 production modification yet。
- Commit disposition/hash: none；red checkpoint is not committable completion。
- Blockers or disproved assumptions: none；red failure distinguishes the planned React payload change。
- Next eligible action: add the smallest exported request-parameter helper in `App.tsx`, use it at the sole `session.create` caller, and rerun the same selectors。

## 2026-09-01 00:21 CST — Phase 01: focused verification complete

- Status transition: `In progress` → `Complete` after focused verification and diff/scope audit。
- Durable sources reloaded: Phase 01 acceptance and handoff evidence were rechecked against live source/tests。
- Runtime/Git/dirty-tree gate: WSL/Linux and Conda `app` retained；dirty paths are exactly the five declared Phase 01 files。
- Authorization in force: unchanged；local phase commit authorized, remote push unauthorized。
- Current causal hypothesis and attempt number: attempt 1 confirmed。Omitting `loadMcp` at the sole React caller restores the Python-owned default without removing explicit protocol opt-out。
- Exact initial/expanded write set and ownership: final set is `app/desktop/src/App.tsx`、`app/desktop/tests/conversations.test.ts`、`app/tests/test_chat_cli.py`、`app/tests/test_desktop_service.py`、`harness/fix_plans/build-log.md`; `app/agent/desktop/service.py` and CLI production remain read-only because focused evidence showed their behavior was already correct。
- Commands actually run and exact outcomes: same minimal Python selectors after production change → `4 passed, 1 warning in 0.11s`; same MCP-filtered Node selector → `1 passed, 0 failed`。Phase planned focused command from `app/`, `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_chat_cli.py tests/test_desktop_service.py -q` → `56 passed, 1 warning in 0.40s`。From `app/desktop/`, `/home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types tests/conversations.test.ts` → `7 passed, 0 failed` in `7525.883855ms`。The warning is the pre-existing LangGraph `allowed_objects` pending-deprecation warning。
- User-visible/fixture observation: CLI fake session observed default `load_mcp=True` and explicit opt-out `False`; Desktop injected session factory observed omitted-field `True` and direct `loadMcp:false` as `False`; frontend helper produced exactly `{ projectId: "local" }` with no `loadMcp` key。No provider、MCP process、credential、real store or external system was touched。
- Diff/scope/safety audit: `git diff --check` exit 0 with no output。`git diff --name-only` contains only the five declared paths；`git grep` finds one production React `session.create` request using `sessionCreateParams(activeProjectId)` and no production `loadMcp:false` override。No dependency、manifest、lockfile or generated file changed。
- Commit disposition/hash: authorized phase-only local commit pending；hash will be appended immediately after creation in a Phase 01 log-only follow-up commit。
- Blockers or disproved assumptions: none。
- Next eligible action: create the scoped local commit, record its hash, restore a clean tree, then continue directly to Phase 02。

## 2026-09-01 00:22 CST — Phase 01: local commit recorded

- Status transition: remains `Complete`。
- Runtime/Git/dirty-tree gate: explicit five-path staging audit passed；implementation commit後worktree clean。
- Commands actually run and exact outcomes: `git diff --check` and `git diff --cached --check` both exited 0 with no output；`git diff --cached --name-only` listed exactly the five declared Phase 01 paths。
- Diff/scope/safety audit: local commit contains only Phase 01 production、regressions與execution evidence；no branch/worktree operation or push occurred。
- Commit disposition/hash: `f625d7b0f8c43c9970898dd0d34baeacdaadd3b3` (`fix(desktop): enable MCP by default`)。This follow-up changes only the durable hash record。
- Blockers or disproved assumptions: the first inline `git rev-parse` print was host-expanded before the commit and displayed the pre-commit hash；a separate direct WSL `git rev-parse HEAD` established the authoritative hash above。No test/evidence claim depended on the stale print。
- Next eligible action: commit this Phase 01 hash record, verify clean tree, then load Phase 02。

## 2026-09-01 00:24 CST — Phase 02: runtime/source preflight

- Status transition: `Not started` → `In progress`。
- Durable sources reloaded: `phases/phase-02-long-request-liveness.md` 與 live `app/desktop/src-tauri/src/backend.rs` supervisor、I/O terminal paths及同檔 tests已重讀；durable global sources沿用本次 Start/Resume 的完整 reload。
- Runtime/Git/dirty-tree gate: WSL/Linux；branch `GUI` tracking `origin/GUI` and ahead 2；HEAD `21bcadfac3277c6f7a9a5926ac7944e82bdad8fa`；Phase 01 hash-record commit後worktree clean。Rust commands使用Linux rustc/Cargo 1.91.1並由Conda `app` 提供fake-child Python/`CONDA_PREFIX`。
- Authorization in force: Phase 02 direct Rust/test/log change、focused Cargo selector與phase-scoped local commit已由本次 prompt 授權；provider、real MCP/Ollama、dependency/lockfile、heartbeat framework、branch/worktree與push仍未授權。
- Current causal hypothesis and attempt number: attempt 1。`REQUEST_TIMEOUT=600s` 只透過 `SupervisorTimeouts.request` 傳入 normal `request()`，再由 `receiver.recv_timeout(timeout)` expiry移除pending並`fatal_generation(..., kill=true)`；child exit、stdout close、malformed protocol與shutdown已有獨立sender/error或bounded shutdown signals，所以normal wait可改為untimed `recv()`，shutdown仍保留自己的response timeout。
- Exact initial/expanded write set and ownership: `app/desktop/src-tauri/src/backend.rs`（production與同檔test）及`harness/fix_plans/build-log.md`。No new module、dependency或protocol change planned。
- Commands actually run and exact outcomes: `git grep` observed `REQUEST_TIMEOUT` at line 25、`SupervisorTimeouts.request` initialization at line 208、normal wait `recv_timeout` at line 472、timeout error/kill at lines 477–482；startup uses a separate condvar deadline and shutdown uses `shutdown_response`/`shutdown_exit`。No Phase 02 test run yet。
- User-visible/fixture observation: none；planned fixture is a caller-owned temporary Python child only。
- Diff/scope/safety audit: first Phase 02 write is this log entry；application Rust remains unchanged。
- Commit disposition/hash: pending focused verification。
- Blockers or disproved assumptions: none。The existing response channel already receives terminal errors from `fatal_generation`、`stdout_closed` and `child_exited`, so removing the normal absolute deadline does not erase those signals。
- Next eligible action: add one deterministic fake mode/test with a 100ms substitute old deadline, progress before and after that boundary, and a terminal result around 180ms；run only that test to establish red before changing production wait semantics。

## 2026-09-01 00:26 CST — Phase 02: rejecting-test compile correction

- Status transition: remains `In progress`；attempt 1 causal hypothesis not yet exercised。
- Runtime/Git/dirty-tree gate: only declared `backend.rs` test additions and `build-log.md` are dirty。
- Current causal hypothesis and attempt number: unchanged；the observed failure was test-code compilation, not request-timeout behavior。
- Exact initial/expanded write set and ownership: unchanged two-file Phase 02 set。
- Commands actually run and exact outcomes: from `app/desktop/`, `/home/minervamuses/miniconda3/bin/conda run -n app /home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/cargo test --manifest-path src-tauri/Cargo.toml backend::tests::progressing_request_can_outlive_the_prior_absolute_deadline -- --exact` → exit 1 after the first local Rust dependency compile；`rustc E0716` at `backend.rs:1528` because collected `&str` values outlived a temporary `MutexGuard` in the new test。The test binary did not run, so this is not pass/red evidence for the product cause。
- User-visible/fixture observation: none；fake child did not execute。
- Diff/scope/safety audit: no production line changed；Cargo used existing lock/dependency graph and did not modify a lockfile。
- Commit disposition/hash: none。
- Blockers or disproved assumptions: none；compiler suggestion confirms a local guard binding is sufficient。
- Next eligible action: bind the captured-events guard for the assertion lifetime (and remove one trailing-space line), then rerun the exact same selector to obtain functional red evidence。

## 2026-09-01 00:28 CST — Phase 02: rejecting-fixture indentation correction

- Status transition: remains `In progress`；attempt 1 production hypothesis still unexercised。
- Runtime/Git/dirty-tree gate: unchanged two declared files。
- Current causal hypothesis and attempt number: unchanged。This result exposed only malformed test-fixture source。
- Commands actually run and exact outcomes: reran the exact single Cargo selector；Rust compiled successfully in 2.98s, then the one test failed in 0.04s at `backend.rs:1518`: expected startup lifecycle `Ready`, observed `Crashed`。Readback of the raw Python fixture showed the newly added `slow_graceful`/`long_request` branches and generic response line had lost the four-space `for raw in sys.stdin` indentation, making the child script invalid before request handling。
- User-visible/fixture observation: no valid progress/result event was produced；this failure is not deadline evidence。
- Diff/scope/safety audit: production supervisor remains unchanged；fix is indentation-only inside the existing test fixture。
- Commit disposition/hash: none。
- Blockers or disproved assumptions: none；live fixture text identifies the exact local cause。
- Next eligible action: restore all affected lines under the existing stdin loop and rerun the exact selector。If it does not then fail specifically with `BACKEND_REQUEST_TIMEOUT`, stop this red-harness path and reassess rather than stacking more changes。

## 2026-09-01 00:30 CST — Phase 02: focused causal red established

- Status transition: remains `In progress`；attempt 1 hypothesis confirmed by rejecting evidence。
- Runtime/Git/dirty-tree gate: same declared Rust test/log paths；production timeout code still unchanged at this checkpoint。
- Current causal hypothesis and attempt number: attempt 1 confirmed。A valid, ready fake child cannot complete a progressing request after the shortened absolute boundary because normal `request()` still calls `recv_timeout` and kills the generation。
- Commands actually run and exact outcomes: exact single Cargo selector compiled in 2.86s and ran one test；exit 1, `0 passed, 1 failed, 25 filtered out` in 0.12s。The panic at `backend.rs:1522` was `progressing request result: BridgeError { code: "BACKEND_REQUEST_TIMEOUT", message: "The desktop backend request did not finish in time.", retryable: true }`。This occurred after the valid child emitted its pre-boundary sequence but before it could emit the planned post-boundary progress and terminal result。
- User-visible/fixture observation: fixture boundary is caller-owned temp script directory removed by `TempScript::drop`; no provider/MCP/Ollama/credential/real store。Old deadline substitute: 100ms；planned events at approximately 0ms/50ms/130ms and result around 180ms。
- Diff/scope/safety audit: no production change yet；no lockfile/dependency modification。
- Commit disposition/hash: none；red is not a completion checkpoint。
- Blockers or disproved assumptions: none。
- Next eligible action: remove `REQUEST_TIMEOUT` and `SupervisorTimeouts.request`; make normal `request()` use untimed channel receive, pass `Some(shutdown_response)` only for internal graceful shutdown, preserve explicit closed-channel/child/pipe/protocol terminal errors, then rerun the same test。

## 2026-09-01 00:34 CST — Phase 02: production green and pipe-fixture hang

- Status transition: remains `In progress`；attempt 1 production change retained, terminal-case fixture correction pending。
- Runtime/Git/dirty-tree gate: exact two-file write set retained；Cargo created only ignored `src-tauri/target` outputs and did not modify lockfiles。
- Current causal hypothesis and attempt number: normal request deadline hypothesis passed its smallest check。The later hang was isolated to a newly added output-close fixture that did not actually close the inherited OS pipe。
- Exact initial/expanded write set and ownership: unchanged `backend.rs` plus this log；same-file tests added for progress order, wrong-id, pipe close and pending shutdown because they are explicit Phase 02 terminal conditions。
- Commands actually run and exact outcomes: after removing the normal timeout, the exact liveness selector → `1 passed, 0 failed, 25 filtered out` in 0.20s；observed total duration exceeded the 100ms substitute and child remained running through terminal result。Then the planned `cargo test --manifest-path src-tauri/Cargo.toml backend::tests` produced no completion output for over 90s。Read-only `pgrep` showed test binary PID 28688 and temp child `/tmp/research-agent-supervisor-28688-12/fake_backend.py`; reading that caller-owned script identified `MODE = "output_close"`。The run was interrupted with Ctrl-C (exit 1), and a subsequent `pgrep` confirmed no matching Cargo/test/fake child remained。
- User-visible/fixture observation: the hanging fake used `sys.stdout.close()` but retained the inherited OS write fd, then waited for more stdin; therefore no EOF/exit/error signal existed and untimed normal receive correctly remained pending。No external system was touched。
- Diff/scope/safety audit: production currently has no `REQUEST_TIMEOUT`、`timeouts.request` or `BACKEND_REQUEST_TIMEOUT`; only the shutdown path calls `recv_timeout`。No dependency/lockfile change。
- Commit disposition/hash: none；focused suite did not pass。
- Blockers or disproved assumptions: disproved fixture assumption that `sys.stdout.close()` closes the inherited protocol fd in this Python runtime。Use `os.close(sys.stdout.fileno())` for a real pipe EOF。
- Next eligible action: make that one fixture correction, run only `stdout_pipe_close_fails_the_pending_request_without_a_deadline`, then rerun the Phase 02 backend selector once it passes。

## 2026-09-01 00:34 CST — Phase 02: focused verification complete

- Status transition: `In progress` → `Complete` after all Phase 02 acceptance paths received observed evidence。
- Durable sources reloaded: Phase 02 required design/acceptance rechecked against final `backend.rs` diff and test names。
- Runtime/Git/dirty-tree gate: WSL/Linux, Conda `app`, Linux Cargo retained；final dirty paths are exactly `app/desktop/src-tauri/src/backend.rs` and `harness/fix_plans/build-log.md`。
- Authorization in force: unchanged；phase-only local commit authorized, push unauthorized。
- Current causal hypothesis and attempt number: attempt 1 confirmed。Normal `request()` now passes `None` and blocks only on the response channel；private `submit_request` uses `recv_timeout` only when graceful shutdown passes `Some(shutdown_response)`。No replacement normal absolute deadline or inactivity watchdog exists。
- Exact initial/expanded write set and ownership: final two-file set unchanged。Production/test code share the existing `backend.rs` module；no new module、protocol、dependency or lockfile。
- Commands actually run and exact outcomes: post-change liveness selector → `1 passed, 0 failed, 25 filtered out` in 0.20s。After correcting the OS-pipe fixture, its selector → `1 passed, 0 failed, 27 filtered out` in 0.02s。Planned focused command from `app/desktop/`, `/home/minervamuses/miniconda3/bin/conda run -n app /home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/cargo test --manifest-path src-tauri/Cargo.toml backend::tests` → `20 passed, 0 failed, 8 filtered out` in 0.21s。`git diff --check` exit 0/no output。
- User-visible/fixture observation: long request emitted request-scoped order `request.started` → pre-boundary `request.progress` → post-boundary `request.progress` → terminal `result`; elapsed exceeded 100ms substitute, result `ok=true`, child remained running and then shut down gracefully。Focused suite also observed child crash → `BACKEND_CRASHED`; live pipe EOF → `BACKEND_OUTPUT_CLOSED`; malformed/oversized/wrong-id → `PROTOCOL_INVALID`; startup deadline → `BACKEND_START_TIMEOUT`; blocked pending request plus application shutdown → forced report and `BACKEND_SHUTDOWN_TIMEOUT` with zero pending/child stopped。All fake children used `TempScript` caller-owned temp directories；the interrupted-run processes were explicitly confirmed absent afterward。
- Diff/scope/safety audit: source grep has no `REQUEST_TIMEOUT`、`timeouts.request`、`BACKEND_REQUEST_TIMEOUT` or `Duration::from_secs(600)` in `backend.rs`; only caller sites are normal `submit_request(..., None)` and shutdown `submit_request(..., Some(self.timeouts.shutdown_response))`; only the latter branch contains `recv_timeout`。Changed paths are exactly the two declared files；broader Cargo suite counter remains `0` because only `backend::tests` ran。
- Additional formatting evidence: whole-crate `cargo fmt -- ... --check` exited 1, showing three new `backend.rs` layout suggestions plus pre-existing unmodified `protocol.rs` formatting differences。Only the three `backend.rs` suggestions were applied manually；an attempted direct toolchain `rustfmt` path exited 127 because that binary is not installed there, then `/home/minervamuses/miniconda3/bin/conda run -n app rustfmt --check --edition 2021 .../backend.rs` exited 0/no output。`protocol.rs` was not touched。
- Commit disposition/hash: authorized phase-only local commit pending；hash will be appended in a Phase 02 log-only follow-up commit。
- Blockers or disproved assumptions: no blocker。Disproved only the test-fixture assumptions already recorded above；the production cause and design held on attempt 1。
- Next eligible action: stage exactly the two Phase 02 paths, run cached diff checks, commit locally, record hash, verify clean tree, then continue to Phase 03。

## Execution Entry Template

後續每個 checkpoint append 一筆，不覆寫歷史 evidence：

```text
## YYYY-MM-DD HH:MM TZ — Phase NN: <checkpoint>

- Status transition:
- Durable sources reloaded:
- Runtime/Git/dirty-tree gate:
- Authorization in force:
- Current causal hypothesis and attempt number:
- Exact initial/expanded write set and ownership:
- Commands actually run and exact outcomes:
- User-visible/fixture observation:
- Diff/scope/safety audit:
- Commit disposition/hash:
- Blockers or disproved assumptions:
- Next eligible action:
```

## Evidence Rules

- `planned`、`expected`、checkbox、source inference 與過去舊 bundle 的 pass 不得寫成 current implementation pass。
- 每個命令記錄 working directory、selector 與 outcome；失敗、skip、timeout、unavailable 都照實寫。
- Fake fixture 必須記錄 fake boundary、temporary root ownership/cleanup 與沒有觸及的 external systems。
- Phase `Complete` 前，每個 acceptance item 必須能指向本檔的 observed evidence；沒有 evidence 就保持 `In progress` 或 `Blocked`。
- Phase 05 必須記錄第一個 live delta 相對 terminal result 的 event order，以及 excluded draft/tool/reasoning evidence。
- Phase 06 必須記錄 fake tool invocation count 在 restore 前後沒有增加，並區分 v2 prompt-eligible activity 與 legacy display-only activity。
- Commit 只能包含已宣告 scope；push、branch、worktree、dependency、provider 或 real-data action 都需各自 fresh authority。
