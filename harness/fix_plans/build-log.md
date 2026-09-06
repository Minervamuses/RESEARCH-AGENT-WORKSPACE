# Research Agent Desktop GUI 修復 — Build Log

## Phase Summary / 階段摘要（Mutable Status Authority）

本檔是唯一 mutable execution status。Phase files 的 `Initial status` 只描述 authoring 起點；後續 agent 必須以本表與 dependency graph 選工作。

| Phase | Status | Attempts against current cause | Last checkpoint | Evidence / 證據 | Commit |
| --- | --- | ---: | --- | --- | --- |
| 01 — MCP defaults | Complete | 1 | Focused verification and scope audit passed | CLI/backend observed `True` default and `False` opt-out; sole React caller omits `loadMcp`; Python `56 passed`, Node `7 passed` | `f625d7b0f8c43c9970898dd0d34baeacdaadd3b3` |
| 02 — Long-request liveness | Complete | 1 | Focused verification and scope audit passed | No normal absolute timeout; long result order passed; backend selector `20 passed`; terminal/startup/shutdown cases preserved | `45d446da4aa005019c7d8c8eded5e6a91b7251dc` |
| 03 — One-shot Skill runtime | Complete | 1 | Focused verification and scope audit passed | Dynamic one-shot command/lifecycle, Citation matrix and legacy manifest diagnostic passed; Python selectors `85 + 20 + 152 passed` | `78589e95ea7ea2e4886529b568c78ecbdb24666c` |
| 04 — Desktop Skill command | Complete | 1 | Focused verification and scope audit passed | Dynamic fixture Skill is one-shot `answer`; natural prompt persisted; Python `158`, Node `95`, slash `29`, Rust `8` passed; TypeScript/diff/removal audit clean | `6fe0d165ca58cd835ed5c2e281e58c74eb4bd50d` |
| 05 — Final-only Normal answer delivery | Complete | 1 | Focused verification and scope audit passed | No answer event/preview; terminal `final_only`/0 after validation+persistence; Python `190`, Node `86`, Rust `8`, TypeScript passed | `b95ff9a0eb5e5c7871f50fbe7eb20153a99328fb` |
| 06 — Tool-aware conversation restore | Complete | 2 | Integration-discovered Citation receipt regression repaired | v2 tool lifecycle/legacy/prompt safety passed; Python `190`, Node `89`, Rust `8`; Citation follow-up `3 passed` | `3c3ae7e84f5b860a16d4ef304b0e8f026edc3256`, `63e0ed0a3abbd1a61e542eaa18c4e3ac07fe3659` |
| 07 — Integration acceptance | Blocked | 1 | All non-repeatable evidence gathered; broader rerun authority required | Integrated fixture、focused Rust/React、npm `108` and Tauri build passed; one-time Python/Cargo runs each had one isolated failure with focused repair/pass | `c1cfd8c37857676916cd05e6afe17c7a9bc673c2` |

## Current Checkpoint

- Phases 01–06 are Complete with scoped local commits and focused evidence；Phase 06 has one additional integration-discovered compatibility fix at `63e0ed0a3abbd1a61e542eaa18c4e3ac07fe3659`。
- Phase 07 integrated fixture、focused cross-language boundaries、served-route viewports、complete npm suite and Tauri no-bundle build passed。The one-time Python broader run had one Citation receipt regression subsequently repaired by focused guards；the one-time Cargo run had one incomplete-command-environment failure subsequently passing its exact selector with `CONDA_DEFAULT_ENV=app`。
- Phase 07 is Blocked only because current authority forbids rerunning those two complete suites, while final acceptance requires broad pass evidence after the corrections。Minimum fresh authority is one corrected Python broader rerun and one corrected full Cargo rerun；no further production hypothesis is pending。
- Prior blocker disposition: true provider-live tokens無法在later token/tool metadata與post-generation gates前證明accepted；這項characterisation仍有效，但USER DECISION 014已取消live-token要求並明確禁止post-finalized模擬串流，因此不再阻擋final-only path。
- Implementation authorization: active under the 2026-09-01 Start/Resume message、USER DECISION 014追加訊息與[`PLANS.md`](PLANS.md) envelope。
- Local phase-scoped commits: authorized；remote push remains unauthorized。
- Broader-suite counters: Python `1/1` consumed (nonpass, then focused repaired)、npm `1/1` passed、Cargo `1/1` consumed (environment nonpass, then focused selector passed)、Tauri build `1/1` passed。

## Authoring Baseline — 2026-08-31 Asia/Taipei

- Repository: `/home/minervamuses/research-agent-workspace`
- Runtime selected: WSL/Linux；commands 必須用 Linux Git/toolchain，Python 使用 Conda environment `app`。
- Branch/upstream observed: `GUI` / `origin/GUI`。
- Initial HEAD observed: `fa24b086e8dcf5bdae1a8db228b4337e9798df65`。
- Initial user-owned untracked inputs observed: `harness/fix_plans/user-decisions.md`、`issue/07-gui-first-turn-durability-deferred.md`、`issue/08-desktop-absolute-request-timeout.md`；本 plan 又依使用者批註加入現稱 `issue/08-citation-skill-flow-deferred.md` 的 Citation issue 與 bundle files。
- No application test、build、provider、MCP、Ollama、live GUI journey 或 persistent-data mutation was run as implementation evidence during authoring。

## Shared Safety Counters

- Live/paid provider calls: `0`；budget in this plan: none authorized。
- Real MCP/Ollama calls: `0`；budget in this plan: none authorized。
- Full Python broader suite runs: `1`；result `908 passed, 1 failed`, sole failure focused-repaired；no rerun authorized。
- Full npm suite runs: `1`；result `108 passed, 0 failed`。
- Full Cargo suite runs: `1`；result `27 passed, 1 failed` from omitted `CONDA_DEFAULT_ENV`, exact corrected selector passed；no rerun authorized。
- Tauri no-bundle builds: `1`；passed and produced the release binary without bundling。

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

## 2026-09-01 00:35 CST — Phase 02: local commit recorded

- Status transition: remains `Complete`。
- Runtime/Git/dirty-tree gate: explicit two-path staging audit passed；implementation commit後worktree clean。
- Commands actually run and exact outcomes: `git diff --check` and `git diff --cached --check` exit 0/no output；cached paths were exactly `app/desktop/src-tauri/src/backend.rs` and `harness/fix_plans/build-log.md`。
- Diff/scope/safety audit: commit contains only Phase 02 Rust production/tests and durable execution evidence；no Cargo lock、branch/worktree or remote state change。
- Commit disposition/hash: `45d446da4aa005019c7d8c8eded5e6a91b7251dc` (`fix(desktop): remove request deadline`)。This follow-up changes only the durable hash record。
- Blockers or disproved assumptions: none。
- Next eligible action: commit this hash record, verify clean tree, then load Phase 03。

## 2026-09-01 00:45 CST — Phase 03: runtime/source preflight

- Status transition: `Not started` → `In progress`。
- Durable sources reloaded: `phases/phase-03-one-shot-skill-runtime.md`已完整重讀；root `AGENTS.md`、`PROMPTS.md`、`GOALS.md`、`PLANS.md`、`user-decisions.md`與本檔沿用本次Start/Resume的完整reload。Live `session.py`、Skill schema/runtime/state、thinking orchestrator、CLI registry/chat/completion、built-in manifests/guide、extension startup以及所有直接grep命中的core tests已重新檢查。
- Runtime/Git/dirty-tree gate: repository `/home/minervamuses/research-agent-workspace`，WSL/Linux runtime，branch `GUI`；HEAD `772bffd855dd715eca47d0c2da93e057f975c517`；preflight前`git status --short`無輸出。後續Python命令固定用`/home/minervamuses/miniconda3/bin/conda run -n app poetry ...`；未切branch/worktree。
- Authorization in force: 使用者明確授權移除Task mode全鏈、完成USER DECISION 011所需的多production-file core/CLI/manifest/test修改、focused checks與phase-only local commit；Desktop React/Rust/protocol留給Phase 04。Dependency/lockfile、provider、real MCP/Ollama/store/credential、其他non-goal與push仍未授權。
- Current causal hypothesis and attempt number: attempt 1。現況把一般Skill綁在persistent `/skill` handler、`ChatSession.active_skill_runtime`與manifest/runtime/state/thinking的`task_mode`欄位；最小因果修復是從session的`loaded_skills`投影validated dynamic slash commands，保留static namespace優先與`_prompt-master`唯一例外，把raw trailing prompt交給session lock內先load後switch的one-shot `try/finally` runtime，並把Citation activation縮成citation-only seam。
- Exact initial/expanded write set and ownership: core candidate set是`app/agent/skills/manifest_schema.py`、`app/agent/skills/runtime.py`、`app/agent/state.py`、`app/agent/session.py`、`app/agent/thinking/orchestrator.py`、`app/agent/cli/slash_commands.py`、`app/agent/cli/chat.py`（`prompting.py`目前只消費同一registry，除非rejecting evidence證明需要才改）；metadata/docs是兩個built-in `manifest.yaml`與`app/SKILLS_GUIDE.md`。Direct test set是phase明列tests，加上`app/tests/conftest.py`、`test_graph_skill_loader.py`、`test_history_recall_routing.py`、`test_skill_adherence.py`、`test_thinking_session.py`、`test_tool_access.py`、`test_thinking.py`、`test_citation_e2e.py`、`test_tool_access_matrix.py`、`test_turn_finalizer.py`，它們分別直接建構已刪欄位或呼叫將縮限的Citation seam。`app/agent/desktop/**`與desktop tests不在本phase write set。
- Commands actually run and exact outcomes: Linux `git status --short`無輸出，`git rev-parse HEAD`得到上述hash；base WSL `rg`不存在（exit 127），改用`grep -R`。Production search確認core/CLI的Task-mode owners只有manifest schema、runtime、state、session、thinking orchestrator、slash handler與兩個built-in manifests/guide；`/skill` persistent owner只在session prompt、slash handler與guide。Test search辨識出上述直接field/seam consumers；尚未執行Phase 03 application tests。
- User-visible/fixture observation: current `/skill academic-paper-writing revision`會建立跨turn runtime，status/help仍宣告active Skill與Task mode；dynamic `/<skill-name> <prompt>`尚未註冊。No provider、MCP process、Ollama、credential、real store或GUI process被啟動。
- Diff/scope/safety audit: Phase 03第一個write只有本execution log；no application、dependency、lockfile或generated output changed。
- Commit disposition/hash: pending focused verification。
- Blockers or disproved assumptions: `prompting.py`已由傳入registry產生completion，預期不需production改動；Desktop generic calls確實仍存在，但依phase dependency明確延後Phase 04，不建立compatibility adapter。
- Next eligible action: 先把dynamic namespace/raw prompt、one-shot lifecycle/cleanup、Citation matrix與legacy manifest unavailable契約寫成最小tests，跑phase列出的最小selectors取得能拒絕現況的red evidence，再做attempt 1 implementation。

## 2026-09-01 00:47 CST — Phase 03: focused causal red established

- Status transition: remains `In progress`；attempt 1 hypothesis retained。
- Runtime/Git/dirty-tree gate: dirty paths are the three declared rejecting-test files plus `build-log.md`；production still unchanged。
- Current causal hypothesis and attempt number: attempt 1 confirmed independently at registry、session lifecycle與legacy schema boundaries。
- Exact initial/expanded write set and ownership: rejecting additions only in `app/tests/test_slash_commands.py`、`app/tests/test_skills.py`、`app/tests/test_extension_skill_startup.py`；final direct set remains the preflight declaration。
- Commands actually run and exact outcomes: from `app/`, `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_slash_commands.py::test_session_registry_projects_one_shot_skill_and_preserves_raw_prompt tests/test_skills.py::test_chat_session_skill_runtime_is_one_shot_and_uses_trailing_prompt tests/test_extension_skill_startup.py::test_startup_reports_legacy_task_modes_manifest_as_unavailable -q` → exit 1, `3 failed, 1 warning in 0.35s`。Failures were: `build_default_registry(session)` TypeError（current registry is global/static only）；`ChatSession.turn(..., skill_name=...)` TypeError（no one-shot lifecycle seam）；legacy installed manifest diagnostic was `installed Skill hash differs from registry` and did not contain `task_modes` because current schema still accepts that field。Warning is the existing LangGraph `allowed_objects` pending-deprecation warning。
- User-visible/fixture observation: raw example is `/paper-writing draft  "quoted"   text` and expected model/history input is exactly `draft  "quoted"   text` with internal spacing/quotes preserved。Legacy extension fixture is entirely under pytest-owned `tmp_path`; no real applied state or external system touched。
- Diff/scope/safety audit: no production、dependency、lockfile or generated output changed before red；the failures directly distinguish all three intended production changes。
- Commit disposition/hash: none；red checkpoint is not committable completion。
- Blockers or disproved assumptions: none。
- Next eligible action: implement session-specific static+dynamic registry projection, one-shot runtime inside the existing turn lock, Citation-only persistent seam, and removal of Task mode schema/runtime/state propagation; rerun these same selectors before rewriting obsolete persistent-contract tests。

## 2026-09-01 01:01 CST — Phase 03: focused verification complete

- Status transition: `In progress` → `Complete` after focused verification、catalog/lifecycle audit and exact write-set review。
- Durable sources reloaded: Phase 03 objective、Citation matrix、lifecycle、catalog validation、Task-mode removal與handoff evidence逐項對照live diff/tests；global authorization/non-goals unchanged。
- Runtime/Git/dirty-tree gate: WSL/Linux and Conda `app` retained；dirty tree contains exactly 29 declared Phase 03 paths（8 core/CLI production files、2 manifests、`SKILLS_GUIDE.md`、17 directly affected test/fake files、this log）。`app/agent/cli/prompting.py` remained read-only because its existing completer already consumes the session registry；no Desktop production/protocol/UI file changed。
- Authorization in force: unchanged；Phase-only local commit authorized, push unauthorized。
- Current causal hypothesis and attempt number: attempt 1 confirmed。The static registry now projects valid dynamic commands exclusively from `session.loaded_skills`; `ChatSession.turn(..., skill_name=...)` loads inside the existing turn lock, switches only after successful load, and identity-clears the transient runtime in `finally`。
- Exact initial/expanded write set and ownership: final changed paths are the 29 paths shown by `git diff --name-only` at this checkpoint。The extra tests beyond the phase's expected list directly constructed the removed state field or called the old generic Citation seam; no unrelated implementation、new module or test framework was added。
- Commands actually run and exact outcomes: smallest post-implementation rerun of the three causal-red selectors → `3 passed, 1 warning in 0.27s`。The first planned seven-file selector after core implementation → exit 1, `20 failed, 67 passed, 1 warning in 0.70s`; every failure was an obsolete persistent-command/Task-mode fixture or expectation（including the extension journey's old mode field）, not a new production branch failure。After replacing those contracts, the same planned command → `84 passed` then final rerun after `_prompt-master` coverage → `85 passed, 1 warning in 1.50s`。Planned Citation command `pytest tests/test_citation_slash_command.py tests/test_citation_skill_activation.py -q` → `20 passed, 1 warning in 0.14s`。Direct causal-ripple selector over graph loader、history routing、skill adherence、thinking、tool access、Citation E2E/matrix and finalizer → `152 passed, 1 warning in 0.81s`。All warnings are the pre-existing LangGraph `allowed_objects` pending-deprecation warning。
- User-visible/fixture observation: static names/aliases remain `help`、`status`、`mode`、`thinking`、`extension-management`、`init`、`ingest`、`sync`、`prune`、`citation`、`clear`、`quit`/`exit`; retired `skill` is additionally reserved but unregistered。Valid dynamic entries use the loaded catalog only；invalid names、casefold duplicates and static/alias/retired collisions are omitted with at most 20 detail diagnostics plus one bounded omitted-count line。`citation` always resolves to the static handler；exact `_prompt-master` is the sole underscore exception and passed help、completion and dispatch checks。Raw `/paper-writing draft  "quoted"   text` produced Skill name `paper-writing` and model/history input exactly `draft  "quoted"   text`。
- User-visible/fixture observation (lifecycle/Citation): success made the runtime visible in prompt/agent state for exactly one graph work and the next ordinary turn observed none；RuntimeError and `CancelledError` both observed the selected runtime during work and none afterward。Unknown/empty/collision fail in registry before model；target load failure happens before state mutation。With Citation active, empty/unknown/collision/load failure preserved the same service/registry identity；a valid academic Skill switch tore Citation down, completed once, then left no runtime and did not restore Citation。Citation's own static persistent semantics、finalizer and thinking rule remain otherwise unchanged；Citation redesign was not performed。
- User-visible/fixture observation (extension): the explicit legacy installed-manifest fixture now returns one bounded `applied_but_unavailable` startup diagnostic naming the removed field。The extension user journey used only its existing pytest-owned temp roots and existing local sandbox MCP subprocess/echo fixture; it used no configured/real MCP server、network provider、credential or user store, and cleaned up through the existing test lifecycle。
- Diff/scope/safety audit: `git diff --check` exit 0/no output。Core/manifests search excluding `app/agent/desktop` found no `task_mode`/`task_modes` or generic activate/deactivate seam；`SKILLS_GUIDE.md` search found none；non-Desktop Python tests contain the removed field only in `test_startup_reports_legacy_task_modes_manifest_as_unavailable`。Persistent-command search produced only unrelated path prose containing `/skill` as a directory fragment, and the explicit retired-command regression is the sole command-form legacy input。No dependency/lockfile path changed；broader-suite counters remain `0`。
- Commit disposition/hash: authorized Phase 03 local commit pending；hash will be appended immediately after creation in a log-only follow-up commit。
- Blockers or disproved assumptions: no blocker。Disproved only the expectation that `prompting.py` needed modification；the existing registry-backed completer required none。
- Next eligible action: stage exactly these 29 paths, run cached diff/name audit, create the local Phase 03 commit, record its hash, verify clean tree, then continue directly to dependent Phase 04。

## 2026-09-01 01:02 CST — Phase 03: local commit recorded

- Status transition: remains `Complete`。
- Runtime/Git/dirty-tree gate: explicit 29-path staging audit passed；implementation commit後worktree clean。
- Commands actually run and exact outcomes: `git diff --check` and `git diff --cached --check` both exit 0/no output；cached names were exactly the final declared Phase 03 set and `git diff --name-only` showed no unstaged path before commit。
- Diff/scope/safety audit: commit contains only Phase 03 core/CLI、manifests/guide、direct regressions/fakes and durable evidence；no Desktop production、dependency/lockfile、branch/worktree or remote state change。
- Commit disposition/hash: `78589e95ea7ea2e4886529b568c78ecbdb24666c` (`fix(skills): run dynamic skills once`)。This follow-up changes only the durable hash record。
- Blockers or disproved assumptions: none。
- Next eligible action: commit this Phase 03 hash record, verify clean tree, then load dependent Phase 04。

## 2026-09-01 01:06 CST — Phase 04: runtime/source preflight

- Status transition: `Not started` → `In progress` after Phase 03 dependency becameComplete。
- Durable sources reloaded: `phases/phase-04-desktop-skill-command.md`完整重讀；global plan/decision/authorization sources沿用本次完整reload。Live Desktop service turn dispatcher、conversation control snapshots、fixture session、contract/fixtures、TypeScript validators/DTO、Rust validator、React composer/control handlers及focused tests已逐一檢查。
- Runtime/Git/dirty-tree gate: WSL/Linux；branch `GUI`；HEAD `bd9d70399cd94a1bf36e1235cda8d46ab449a2a4`；Phase 03 hash-record commit後`git status --short`無輸出。Python仍用Conda `app`/Poetry；Node/npm與Linux Cargo toolchains沿用已驗證runtime。
- Authorization in force: Phase 04 Python Desktop、React/TypeScript、Rust、internal protocol/fixtures/tests及phase-only local commit在本次prompt envelope內；protocol major、dependency/lockfile、Citation redesign、live provider/real MCP/Ollama/store/credential、branch/worktree/push仍未授權。
- Current causal hypothesis and attempt number: attempt 1。`DesktopService`目前在constructor建立global static registry，composer只允許`status`/extension/knowledge集合，未知dynamic command在model前一律拒絕；同時generic list/activate/deactivate RPC、React dropdown與control snapshot仍保存跨conversation state。最小修復是從current session建立Phase 03 registry，static dispatch優先，只有registry明確標記的dynamic Skill結果才落入既有answer-turn path，並刪除整條persistent control/DTO/RPC/snapshot鏈。
- Exact initial/expanded write set and ownership: Python `app/agent/desktop/service.py`、`fixture_session.py`；shared resolver metadata owner `app/agent/cli/slash_commands.py`（新增read-only dynamic marker，讓Desktop不必執行有副作用的unsupported static handler來判型；不改Phase 03 lifecycle）；contract `app/desktop/protocol/v1/contract.json`、`fixtures.json`、`app/desktop/src/protocol.ts`、`app/desktop/src-tauri/src/protocol.rs`；UI `app/desktop/src/App.tsx`（no stylesheet change unless live diff reveals a gap）。Tests are the four planned Python Desktop files and three planned Node files。`app/agent/desktop/protocol.py`、conversation reducer、CSS與backend Rust remain read-only unless a rejecting check proves direct need。
- Commands actually run and exact outcomes: read-only searches found generic RPCs in Python dispatch table、contract/TS/Rust inventories and validators；snapshot fields in service/contract/TS/Rust/two JSON fixtures；React owns `SkillItem`/`skills` state、three `loadSkills` calls、generic control method union、dropdown and task label。`session.turn` currently returns every accepted slash result as `responseKind=command` and calls `session.turn_outcome(original_text)` only when no slash parsed。No Phase 04 application test run yet。
- User-visible/fixture observation: current GUI sends composer text raw, but `/research draft` is rejected before its fixture session because the service registry has no session catalog；normal/status behavior already shares the desired busy/registration/answer machinery。Citation is present only as an unsupported static registry command and must remain rejected/deferred after generic controls disappear。
- Diff/scope/safety audit: Phase 04 first write is this log entry only；no application/protocol/dependency/lockfile changed yet。
- Commit disposition/hash: pending focused verification。
- Blockers or disproved assumptions: no blocker。`loadedSkills` remains useful bounded catalog evidence but React does not need to fetch a second selectable catalog once `session.list_skills` is removed。
- Next eligible action: add one fake-session regression proving exact dynamic trailing prompt、answer classification and next ordinary turn state；run only that selector for causal red, then implement the Python dispatch/snapshot removal before synchronizing protocol and UI deletion tests。

## 2026-09-01 01:09 CST — Phase 04: causal rejecting check

- Write set used: `app/tests/test_desktop_service.py` only, adding a fake-session observation seam and one dynamic composer regression。
- Hypothesis/attempt: attempt 1；the current Desktop constructor-static registry rejects a session-loaded Skill before the existing answer-turn path。
- Exact command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_service.py::test_composer_routes_dynamic_skill_once_as_answer -q`。
- Exact result: exit `1`；`1 failed, 1 warning in 0.20s`。Failure is `DesktopServiceError: Unknown slash command: /research` at `agent/desktop/service.py:1632`；the fake model/session received no Skill turn before rejection。
- Evidence classification: expected causal red, not pass evidence。It proves the missing boundary is the Desktop slash resolver rather than the React raw-text sender or model outcome classifier。
- Next eligible action: add an explicit dynamic Skill marker to the existing Phase 03 projected command and make Desktop resolve against the current session registry, then route its exact trailing input through `turn_outcome(..., skill_name=...)` while preserving unsupported static-command rejection。

## 2026-09-01 01:11 CST — Phase 04: dynamic Desktop dispatch checkpoint

- Implementation: `SlashCommand` now carries an explicit optional `skill_name` marker populated only by validated session-catalog projections。`DesktopService` builds that registry from the current session unless a test registry is injected, rejects aliases/unsupported static commands before execution, validates the dynamic typed result, and sends only its exact trailing prompt through the existing answer path with a one-turn `skill_name` argument。
- Exact command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_service.py::test_composer_routes_dynamic_skill_once_as_answer -q`。
- Exact result: exit `0`；`1 passed, 1 warning in 0.08s`。Both `/research` and the immediately following ordinary turn returned `responseKind=answer`; fake-session observations were `[('draft  "quoted"   text', 'research'), ('ordinary follow-up', None)]`。
- Pass boundary: focused resolver/lifecycle evidence only；the Phase is not complete until the persistent control/RPC/DTO/UI chain is removed and all planned Python/Node/TypeScript/Rust checks pass。
- Next eligible action: remove generic Skill/Task controls from Python session snapshots and conversation snapshots, then synchronize the v1 contract fixtures and Desktop clients without removing `loadedSkills`。

## 2026-09-01 01:16 CST — Phase 04: first full Python focused run

- Changes under check: Python persistent Skill/Task RPC、session DTO、conversation snapshot and fixture fake APIs removed；contract/TS/Rust/UI deletion synchronized；dynamic fixture and busy/cancel/collision/removal regressions added。
- Exact command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py -q`。
- Exact result: exit `1`；`7 failed, 151 passed, 1 warning in 1.25s`。
- Failure audit: all seven failures share `NameError: DEFAULT_SKILLS_DIR is not defined` in `DesktopService._protected_roots`。The RPC deletion correctly removed `load_skill_manifest`, but the same import line also owned the existing knowledge protected-root fallback。Resulting mapped failures affected only knowledge path tests (`RAG_*` instead of expected path/model codes)；dynamic Skill tests and contract synchronization passed in this run。
- Attempt disposition: focused attempt 1 implementation correction, not a new causal hypothesis and not pass evidence。Smallest fix is restoring only `DEFAULT_SKILLS_DIR` import；no production dependency or write-set expansion。
- Next eligible action: restore that import and repeat the same four-module selector once。

## 2026-09-01 01:19 CST — Phase 04: focused verification, scope audit and completion

- Status transition: `In progress` → `Complete` in attempt 1 after the single import correction and complete planned focused matrix。
- Confirmed implementation/result: Desktop resolves dynamic commands from the current session catalog, validates an explicit resolver-owned dynamic marker, and sends the exact trailing prompt through the ordinary `answer` path with one-turn `skill_name`。Static `status`/extension/knowledge commands retain existing local `command` handling；aliases、unknown/empty/duplicate-collision commands and reserved `/citation` are rejected before model invocation。
- Fixture/user-visible evidence: after isolated extension restart, `loadedSkills == ["fixture-writer"]`；`/fixture-writer Draft  "quoted"   body` returned `responseKind=answer` exactly once。The next ordinary turn contained no Skill label/context, and transcript `userText` ended with `['Draft  "quoted"   body', 'ordinary follow-up']` rather than the slash command。Busy rejected both a second dynamic and ordinary turn；cancelling a blocked dynamic request cleared `_turn_active`, retained only the one transient call observation, and allowed clean session shutdown。
- Removed inventory: Python dispatch/fake APIs and control snapshots no longer expose/capture/restore `session.list_skills`、`session.activate_skill`、`session.deactivate_skill`、`active_skill` or `task_mode`；contract/JSON fixtures/TypeScript/Rust/React no longer contain those methods or `activeSkill`、`taskMode`、`taskModes`、`activeTaskMode`。`loadedSkills` remains bounded session catalog evidence only。React still submits raw composer text and contains no slash parser/allowlist。
- Citation deferred boundary: static `/citation` remains reserved and Desktop-rejected；React now states `Citation mode is currently CLI-only` and no button、alias、hidden RPC or compatibility state was added。
- Exact Python command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py -q`。
- Python result after the logged correction: exit `0`；`158 passed, 1 warning in 0.85s`。The warning is the existing LangGraph `allowed_objects` pending deprecation。
- Exact Node command: `cd app/desktop && /home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types tests/protocol.test.ts tests/conversations.test.ts tests/backend.test.ts`。
- Node result: exit `0`；`95 passed, 0 failed` in `9060.246394 ms`。
- Exact TypeScript command: `cd app/desktop && /home/minervamuses/miniconda3/bin/conda run -n app ./node_modules/.bin/tsc --noEmit`；exit `0` with no output。
- Cargo invocation failure: the first command appended host `$PATH` before WSL and exited `1` with bash syntax error at Windows `Program Files (x86)`；no Cargo test ran, so it is not pass evidence。
- Exact corrected Cargo command: `cd app/desktop && env PATH=/home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:/usr/local/bin:/usr/bin:/bin /home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/cargo test --manifest-path src-tauri/Cargo.toml protocol::tests`。
- Corrected Cargo result: exit `0` after the first local dependency compile；`8 passed, 0 failed, 20 filtered out` for the library protocol selector and `0 tests` for the main target。
- Shared resolver regression command/result: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_slash_commands.py -q` exited `0`；`29 passed, 1 warning in 0.14s`。
- Diff/scope/safety audit: tracked production removal search returned no matches；only explicit negative tests retain retired method/field strings。`git diff --check` exited `0` with no output；React slash-parser search returned no matches；no dependency manifest or lockfile changed。Changed paths are exactly the 12 Phase 04 code/contract/test paths plus this log；CSS、Python protocol owner、backend Rust process code and all non-goals remained untouched。
- Commit disposition/hash: Phase 04 implementation committed locally as `6fe0d165ca58cd835ed5c2e281e58c74eb4bd50d` (`fix(desktop): run dynamic skills once`)；the tree was clean immediately after commit。
- Blockers or deferred issues: none for Phase 04。Citation GUI access remains deliberately deferred under `issue/08-citation-skill-flow-deferred.md`／non-goal；live answer delta remains Phase 05。
- Next eligible action: create the authorized Phase 04-only local commit, record its hash, verify clean tree, then load Phase 05 as the next dependency-eligible phase without running broader suites。

## 2026-09-01 01:20 CST — Phase 04: implementation hash record

- Local implementation commit: `6fe0d165ca58cd835ed5c2e281e58c74eb4bd50d` (`fix(desktop): run dynamic skills once`)。
- Commit result: `13 files changed, 348 insertions(+), 280 deletions(-)`；the count includes this Phase 04 build-log evidence and no dependency/lockfile。
- Immediate post-commit audit: `git status --short` returned no output。
- Next eligible action: commit this hash record as a log-only follow-up, verify clean tree, then load Phase 05 because Phase 04 is Complete and all Phase 05 dependencies are satisfied。

## 2026-09-01 01:23 CST — Phase 05: runtime/source preflight and mandatory characterisation start

- Status transition: `Not started` → `In progress` after Phase 04 became Complete。Runtime remains WSL/Linux on branch `GUI`；HEAD `79c1a898a5f651384e8afb21875ba34ed0b5df41`；`git status --short` returned no output before this log write。
- Durable sources reloaded: `phases/phase-05-normal-live-streaming.md` read in full；`PLANS.md` live dependency table reconfirmed Phase 05 depends on Complete Phase 04, Phase 06 depends on Phase 05, and Phase 07 depends on Phases 01–06。
- Hypothesis/attempt: attempt 1。LangGraph `messages` mode can expose actual model chunks and per-call tags/metadata, but present `agent_node` performs initial、empty retries、tool continuation、force-final and repair invocations inside the same `agent` node。More importantly, `final_response_problem` and Citation/final-text validation decide acceptance only after each complete model message, so node name or an invocation tag may attribute a candidate stage without proving before its first token that the stage will be the accepted authoritative answer。
- Source stage map so far: `execute_graph` currently requests only `stream_mode="updates"` and reports completed node messages；`agent_node` calls a tool-bound model for initial/tool-continuation and identical empty retries, a raw model near the graph fuse, and a raw repair call after an invalid completed draft。The graph emits only the selected completed response into state；`ChatSession.finalize_and_record` then runs another safety gate plus Citation rendering/final-text validator before persistence and `TurnOutcome`。Desktop currently slices only that terminal `TurnOutcome.text` as `post_finalized`。
- Cancellation/error map so far: cancelling `session.turn` propagates through `graph.astream`/`turn_outcome`; Desktop `_session_turn` finally clears request correlation, pending approval and busy state。Provider/terminal errors currently emit no answer event；React keeps the draft via its request failure reducer。
- Initial candidate write set if a safe seam is proven: Python `app/agent/turns/execution.py`、`app/agent/graph.py`、`app/agent/session.py`、`app/agent/desktop/service.py`；contract/render `app/desktop/protocol/v1/contract.json`、fixtures only if event shape changes、`app/desktop/src/protocol.ts`、`App.tsx`；tests `app/tests/test_desktop_answer_stream.py`、minimal graph/finalizer selector and `app/desktop/tests/answer_stream.test.ts`。Rust remains read-only unless the event enum validator must change。No Fusion/Extended owner、dependency/lockfile or provider code is in the candidate set。
- First diagnostic write set: a temporary characterisation test in existing `app/tests/test_desktop_answer_stream.py` only。It will use the installed fake streaming chat model and the live compiled graph to record actual `messages` chunks/metadata for clean versus repair calls; it will be removed if characterisation proves the phase requires fresh authority rather than implementation。
- Commands/results: source-only reads completed；no Phase 05 application test or model/provider call has run。Installed LangGraph `StreamMessagesHandler` confirms `messages` mode emits `AIMessageChunk` on each model token and attaches graph metadata plus filtered invocation tags；it also emits completed node messages with dedupe。This proves transport capability, not acceptance safety。
- Authorization boundary: no live provider、second model call、unsafe draft display、broad graph rewrite、Fusion/Extended change or dependency is authorized。If the fake trace confirms attribution cannot establish pre-token acceptance, the phase must be marked Blocked per the phase file rather than implementing post-final replay or exposing drafts。
- Next eligible action: run one deterministic fake-streaming live-graph characterisation with distinct sentinels and inspect exact chunk metadata/order against the accepted graph update。

## 2026-09-01 01:26 CST — Phase 05: mandatory characterisation blocker

- Status transition: `In progress` → `Blocked` in attempt 1 before production implementation。This is the explicit Phase 05 stop condition from the phase file and `PLANS.md`: do not expose unchecked drafts and do not relabel post-final replay as live streaming。
- Temporary deterministic diagnostic: added a local test-only `BindableStreamingModel(FakeListChatModel)` to the existing stream test, with provider responses `DRAFT_SENTINEL rag_search(query="x")` then `ACCEPTED_SENTINEL`。It ran the real compiled `build_graph` with `stream_mode=["messages", "updates"]`; no provider/network/store credential was used。
- Exact command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_answer_stream.py::test_characterise_live_graph_metadata_before_repair_acceptance -q`。
- Exact result: intentional diagnostic exit `1`；`1 failed, 1 warning in 0.24s`。Assertion trace was `groups=[{'text': 'DRAFT_SENTINEL rag_search(query="x")', 'node': 'agent', 'tags': ()}, {'text': 'ACCEPTED_SENTINEL', 'node': 'agent', 'tags': ()}]` while graph `updates=[{'node': 'agent', 'messages': ['ACCEPTED_SENTINEL']}]`。The observability log independently classified the first completed response as `issue=call_like_tool_protocol` and the graph repaired it。
- Characterisation conclusion 1 — stage map: initial answers、tool-continuation answers and empty retries all use the tool-bound invocation inside `agent_node`; force-final uses the raw model inside the same node; repair uses a second raw invocation inside that same node。Current `messages` metadata therefore cannot distinguish them by `langgraph_node`。Per-invocation tags could distinguish call identity, but a tag is assigned before generation and cannot assert the later output acceptance decision。
- Characterisation conclusion 2 — future-token problem: the first provider chunks can be ordinary-looking text and only a late protocol sentinel、call-like tool serialization or structured/tool-call finish metadata makes the completed message invalid。Streaming any prefix before that completion would visibly expose a repair-discarded draft, which the non-negotiable boundary forbids。Holding it until validation is the existing complete-answer buffering behavior, not provider-live delta。
- Characterisation conclusion 3 — downstream gates: after graph selection, `ChatSession.finalize_and_record` again runs `final_response_problem`, Citation policy can replace/render text when active, and Desktop's installed `_validate_final_text_before_record` can reject the complete success envelope before persistence。Phase 05 excludes Citation streaming, but normal safety and wire-size gates still occur only after complete text。A terminal error/cancel makes React discard provisional state, yet cannot undo content already shown to the user。
- Alternatives exhausted within current authority: node split、metadata tags or a callback/context seam only improve attribution and do not solve future-token acceptance；incremental filtering still exposes a prefix from a later-discarded/tool-producing draft；waiting for the accepted graph update produces post-final replay。An extra model call、unsafe provisional display、finalizer/tool-routing semantic change or broad graph rewrite is outside authorization, and an extra model call alone still requires either unchecked output visibility or another completion gate。
- Dependency effect: Phase 06 explicitly depends on Complete Phase 05；Phase 07 depends on Phases 01–06。Neither is eligible while this blocker stands, so all meaningful remaining plan paths require the same fresh product-boundary authority。
- Cleanup/scope audit: the temporary diagnostic test and imports were removed with `apply_patch` after capturing the trace；`git diff -- app/tests/test_desktop_answer_stream.py` returned no output。No Python/React/TypeScript/Rust/contract production file changed；current dirty tree contains only this `build-log.md` evidence。No focused acceptance suite was run because no safe implementation exists；no broader suite/build or live provider was run。
- Minimal fresh-authority decision required: either (A) permit explicitly provisional, unchecked normal-model deltas to appear and later be cleared/reconciled on repair/error, accepting that discarded draft text can be briefly visible；or (B) waive true provider-live Phase 05, retain the verified `post_finalized` safety boundary, and authorize the dependency/status adjustment needed to proceed to Phase 06。Authorizing only an extra model call does not by itself prove pre-token acceptance。
- Commit disposition: no Phase 05 implementation commit。This characterisation/blocker record may be committed locally as a log-only checkpoint；remote push remains unauthorized。
- Next eligible action: make the log-only blocker checkpoint, verify clean tree, then stop once with the minimal fresh-authority request because Phases 06–07 are dependency-ineligible。

## 2026-09-01 01:48 CST — Phase 05: USER DECISION 014解除blocker並開始durable plan repair

- Status transition: `Blocked` → `In progress`。USER DECISION 014明確supersede USER DECISION 006：Normal answer不做live token streaming，也不做`post_finalized`模擬串流；Python完成generation、repair、finalization、validation與persistence後，Desktop只以完整`final_only` terminal result顯示答案。
- Durable sources reloaded: personal/repository `AGENTS.md`、`PROMPTS.md`、`GOALS.md`、`PLANS.md`、`user-decisions.md`、本檔、Phase 05/06/07與long-horizon-plan-author `SKILL.md`及其四份required references已完整重讀。Phase 01–04仍有Complete evidence，Phase 05是新決策下第一個dependency-eligible phase。
- Runtime/Git/dirty-tree gate: repository`/home/minervamuses/research-agent-workspace`、WSL/Linux、branch`GUI`tracking`origin/GUI`；HEAD`63cd3d0c24c037a7f9794d521a439298d693230c`，首次寫入前`git status --short`無輸出。Conda`app`提供Python 3.13.14/Poetry 2.4.1/Node 24.18.0；未切branch/worktree。
- Authorization in force: 使用者明確授權本次durable plan repair、直接相關Python/React/TypeScript/Rust/internal protocol/fixtures/tests、Phase 05–07 focused/one-time broader checks與phase-scoped local commits；dependency/lockfile、live provider、real MCP/Ollama/store/credential、Fusion/Extended/Citation redesign、first-turn durability、多GUI、branch/worktree/push/release仍未授權。
- Current causal hypothesis and attempt number: new final-only cause attempt`0`（plan repair；尚未做implementation attempt）。`ChatSession.finalize_and_record()`在回傳前執行safety/finalization、Desktop final-text/wire validator與`_record_turn()`；唯一直接違反新契約的current chain是`DesktopService._emit_answer_chunks()`在outcome後送`post_finalized answer.chunk`，shared protocol/Rust/TypeScript/React再接受並reconcile它。最小實作是移除該producer/contract/consumer chain並固定terminal`final_only`/0，不改graph/model stream。
- Exact plan-only write set and ownership: `harness/fix_plans/user-decisions.md`、`GOALS.md`、`PLANS.md`、`PROMPTS.md`、`phases/phase-05-normal-live-streaming.md`、`phases/phase-07-integration-acceptance.md`、`build-log.md`。Phase 06內容與新契約無衝突，保持read-only；application/tests尚未修改。
- Commands actually run and exact outcomes: live `git grep -n -E "answer\\.chunk|post_finalized|streamKind|chunkCount|final_only" -- app/agent app/desktop app/tests`確認sole Python producer在`service.py`、shared contract/fixtures/Rust/TypeScript/React consumer與direct tests；`session.py` source確認final-text validator在`_record_turn()`前、`TurnOutcome`在record完成後回傳。這些是source evidence，不是implementation pass。
- Prior evidence disposition: 01:26 characterisation trace與所有blocked conclusions完整保留。它們證明unsafe live preview不可接受；新決策改變產品目標，因此解除blocker而不是推翻觀察。
- Verification so far: no application test、provider、MCP、Ollama、real store、broader suite或build已執行。Durable plan strict validator與`git diff --check`尚待執行，不能列為pass。
- Diff/scope/safety audit: first writes限定上述7個plan paths；no application、dependency、lockfile、generated output或non-goal change。
- Commit disposition/hash: pending plan validator與scope audit；remote push unauthorized。
- Next eligible action:完成7-file cross-reference/residue review，跑long-horizon strict validator與`git diff --check`；plan-only checkpoint通過後再開始Phase 05 first rejecting test。

## 2026-09-01 01:51 CST — Phase 05: durable plan repair validation

- Status transition: remains `In progress`；這是planning evidence，不是Phase 05 implementation pass。
- Plan repair result: USER DECISION 014已append且保留006；GOALS/PLANS/PROMPTS、Phase 05、Phase 07與mutable status已一致改為authoritative final-only。Phase 06不依賴answer streaming細節，無需改動。
- Exact validator command: `/home/minervamuses/miniconda3/bin/conda run -n app python /mnt/c/Users/garyc/.codex/skills/long-horizon-plan-author/scripts/validate_harness.py --repo /home/minervamuses/research-agent-workspace --plan-root harness/fix_plans --project-shape application --risk medium --harness-only --strict --json`，並對上述7個write paths各重複傳入`--proposed-path <path> --allowed-path <path>`。
- Validator result: exit`0`；`valid: true`、`errors: 0`、`warnings: 0`、`findings: []`。這只驗證durable plan結構與write boundary。
- Exact whitespace/scope checks: repository root `git diff --check` exit`0`/no output；`git diff --name-only`列出exactly上述7個plan paths，沒有application、test、dependency、lockfile或`AGENTS.md`。
- Skill disposition: long-horizon-plan-author planning-only checkpoint到此完成；其規則未允許在該invocation中修改application或Git state，因此尚未commit。後續動作屬使用者同一訊息另行明確授權的implementation run。
- Commit disposition/hash: plan-only coherent checkpoint可在離開skill invocation後依使用者local-commit authority建立；remote push仍未授權。
- Next eligible action:結束planning-only invocation，建立scoped local plan-repair checkpoint，然後以更新後Phase 05的單一Python selector取得final-only causal red。

## 2026-09-01 01:53 CST — Phase 05: durable plan repair commit recorded

- Status transition: remains `In progress`；application implementation尚未開始。
- Exact commit: `2c6d946c5b8f540fe7995ea55592a3aef66afc13` (`docs(plan): adopt final-only answers`)。
- Commit scope: exact 7-fileplan repair set；`170 insertions(+), 109 deletions(-)`。Pre-commit `git diff --cached --check` exit`0`，cached name audit只列上述7個paths。
- Immediate post-commit audit: `git status --short`無輸出；no application、dependency、lockfile、branch/worktree或remote change。
- Next eligible action: record the Phase 05 implementation preflight/write set，add the single final-only rejecting regression，and run only that selector。

## 2026-09-01 01:55 CST — Phase 05: final-only implementation preflight

- Status transition: remains `In progress`；current final-only cause attempt`1`開始。Prior live-stream characterisation仍是歷史attempt 1，但不計入已改變產品目標後的cause counter。
- Durable sources reloaded: repaired Phase 05、USER DECISION 014、live `DesktopService` result/event path、`ChatSession.finalize_and_record()` ordering、shared contract/fixtures、Rust/TypeScript validators、React reducer/render與direct Python/Node tests已對照。
- Runtime/Git/dirty-tree gate: WSL/Linux；branch`GUI`tracking`origin/GUI`and ahead11；HEAD`31774bc3feeb499a1f39cba8d3aafcdcc65a5c2f`；first implementation write前`git status --short`無輸出。Python/Node/Cargo仍使用Conda`app`與Linux toolchains。
- Authorization in force: USER DECISION 014與Start/Resume envelope允許direct Python/React/TypeScript/Rust/internal protocol/fixtures/tests和local phase commit；dependency/lockfile、live provider、real MCP/Ollama/store/credential、Fusion/Extended/Citation redesign、branch/worktree/push仍禁止。
- Current causal hypothesis: `turn_outcome()`已在validator與`_record_turn()`完成後回傳，normal service卻再呼叫`_emit_answer_chunks()`；移除sole producer並同步刪除contract/consumer即可達成final-only，不需改session、graph或model stream。
- Exact initial production/contract write set: `app/agent/desktop/service.py`、`app/desktop/protocol/v1/contract.json`、`fixtures.json`、`app/desktop/src/protocol.ts`、`app/desktop/src-tauri/src/protocol.rs`、`app/desktop/src/conversations.ts`、`app/desktop/src/App.tsx`。
- Exact initial test/log write set: `app/tests/test_desktop_answer_stream.py`、`app/tests/test_desktop_fixture.py`、`app/tests/test_desktop_protocol_contract.py`、`app/desktop/tests/answer_stream.test.ts`、`app/desktop/tests/protocol.test.ts`、本檔。`app/tests/test_desktop_service.py`與`test_turn_finalizer.py`先作required read-only verification；只有red/ripple證明缺口才編輯。
- Cheapest rejecting check: modify only`test_answer_chunks_are_emitted_only_after_turn_finalizes`into a final-only barrier assertion，then run that exact selector。Current service should fail only because it emitsone`answer.chunk`and returns`post_finalized`。
- Commands/results so far: source reads only；no Phase 05 implementation test、broader suite、build或external call已執行。
- Diff/scope/safety audit: this log is the first dirty path；no dependency/lockfile/generated/non-goal change。
- Commit disposition/hash: pending focused verification and phase-only scope audit。
- Next eligible action: apply the one-test red and run exactly that selector before production change。

## 2026-09-01 01:57 CST — Phase 05: final-only causal red established

- Status transition: remains `In progress`；final-only cause attempt`1`confirmed。
- Exact write before check: only`app/tests/test_desktop_answer_stream.py`regression plus this log；production unchanged。
- Exact command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_answer_stream.py::test_answer_is_delivered_only_by_the_final_terminal_result -q`。
- Exact result: exit`1`；`1 failed, 1 warning in 0.15s`。Failure is the post-release assertion`events == []`because current service emitted exactly one`answer.chunk`with`streamKind=post_finalized`andtext`final answer`。Before releasingthefake session barrier，events were empty。
- Evidence classification: expected causal red，not pass evidence。It directly proves the obsolete Desktop emitter is the first missing final-only boundary；no provider/network/store/credential was used，andpytest`tmp_path`owned the service paths。
- Diff/scope/safety audit: no production、protocol、dependency或lockfile change at red checkpoint。
- Next eligible action: remove the Python emitter/constants and fix terminal/wire fields to`final_only`/0，rerun this selector，then synchronize shared contract/React consumers and their direct tests。

## 2026-09-01 01:59 CST — Phase 05: smallest Python green and ordering-oracle correction

- Status transition: remains `In progress`；attempt`1`production hypothesis held at the first boundary。
- Minimal production change: removed the answer chunk byte/count constants、`_emit_answer_chunks()`、its UTF-8 slicing helper and normal success call from`app/agent/desktop/service.py`；wire-budget candidate andterminal result now use`streamKind=final_only`/`chunkCount=0`。
- Exact command: reran `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_answer_stream.py::test_answer_is_delivered_only_by_the_final_terminal_result -q`。
- Exact result: exit`0`；`1 passed, 1 warning in 0.10s`。Barrier observation remains events`[]`before release and after completion；terminal text is the full`final answer`。Warning is the existingLangGraph`allowed_objects`pending deprecation。
- Live plan correction: direct validation-before-record regression is`tests/test_session_eviction.py::test_final_text_validator_runs_before_the_turn_is_recorded`；`test_turn_finalizer.py`owns successful finalization/record outcomes。Active Phase 05 focused command now includes the former exact selector；both files remainread-only unless they fail。
- Expanded write set: only the active phase file and thislog were added for the evidence-backed selector correction；application candidate set otherwise unchanged。
- Pass boundary: Python sole-producer green only。Shared contract/fixtures/Rust/TypeScript/React still expose`answer.chunk`/`post_finalized`and must be synchronized before Phase completion。
- Next eligible action: update the remaining direct Python tests and remove the shared protocol/React chain，then run the planned focused matrix。

## 2026-09-01 02:04 CST — Phase 05: first synchronized focused matrix and fixture correction

- Status transition: remains `In progress`；attempt`1`implementation retained，one test-only assertion correction pending。
- Synchronized changes under check: Python emitter removal；contract/fixtures/Rust/TypeScript event inventory and terminal enum；React chunk/provisional/reconciliation removal；direct final-only/error/cancel/protocol tests。
- Exact Python command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_answer_stream.py tests/test_desktop_service.py tests/test_desktop_fixture.py tests/test_desktop_protocol_contract.py tests/test_turn_finalizer.py tests/test_session_eviction.py::test_final_text_validator_runs_before_the_turn_is_recorded -q`。
- Python result: exit`1`；`1 failed, 189 passed, 1 warning in 1.34s`。Only failure was`test_real_service_round_trip_registration_restore_and_final_only_answer`: assertion incorrectly requiredall events`[]`，but the production fixture emitted two allowed`stage.changed`events (`fixture.prepare`/`fixture.finalized`) and noanswer event。This does not contradict USER DECISION 014，which permits bounded progress/activity without answer text。
- Exact TypeScript command/result: `cd app/desktop && /home/minervamuses/miniconda3/bin/conda run -n app ./node_modules/.bin/tsc --noEmit`→exit`0`/no output。
- Exact Rust command/result: `cd app/desktop && env PATH=/home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:/usr/local/bin:/usr/bin:/bin /home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin/cargo test --manifest-path src-tauri/Cargo.toml protocol::tests`→exit`0`；library`8 passed, 0 failed, 20 filtered out`，main`0 tests`。
- Earlier exact narrow checks after synchronization: Python`tests/test_desktop_answer_stream.py -q`→`11 passed, 1 warning in 0.25s`；Node`node --test --experimental-strip-types tests/answer_stream.test.ts tests/protocol.test.ts`→`86 passed, 0 failed`in`185.122772ms`。
- Failure disposition: not pass evidence for the Python matrix；smallest correction is assert zero`answer.chunk`and absence ofterminal answer text in event payload while retaining stage events。No production change or new causal hypothesis needed。
- Next eligible action: correct that fixture assertion，run only its selector，then repeat the exact Python focused matrix once。

## 2026-09-01 02:06 CST — Phase 05: focused verification, scope audit and completion

- Status transition: `In progress` → `Complete`in final-only cause attempt`1`。USER DECISION 014 acceptance is satisfied without revisitingthepreserved attempt-1 live-stream blocker evidence。
- Confirmed implementation: `DesktopService`no longer has answer-chunk constants、UTF-8 slicer、emitter orsuccess call；worst-case wire budgeting and every normal/command success now use`streamKind=final_only`/`chunkCount=0`。Shared v1 contract、JSON fixtures、Rust/TypeScript validators and DTOs no longer advertise`answer.chunk`or`post_finalized`。React no longer stores chunk indexes/bytes/provisional text、reconciles prefixes or labels streamingfallback；pendingUI shows onlyworking spinner plus bounded stage/tool activity，and terminal success appends one complete answer。
- Ordering/persistence evidence: the barrier regression observed noanswer event before or after fake turn release and one full terminal text。The final Python matrix includedall`test_turn_finalizer.py`cases plus`test_session_eviction.py::test_final_text_validator_runs_before_the_turn_is_recorded`，proving successful finalized records precede returned outcomes and validator rejection leaves no recent/history record。This evidence usesfake graph/history/temp paths，not a real store/provider。
- Error/cancel/validation evidence: direct tests observed provider failures、oversize/wire-envelope rejection、cancelled blocked turn and a deliberately throwing event sink without any answer event/preview；cancel cleared`_turn_active`。Unicode final text returned intact in theterminal result。React failure retained onlytherecoverableuser draft and no assistant preview。
- Fixture observation: isolated Desktop fixture retained two allowed`stage.changed`events (`fixture.prepare`/`fixture.finalized`) whilezero answer events crossed the sink and terminal text was absent from event payloads；the registered conversation still restored/continued normally。
- Exact corrected selector: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_fixture.py::test_real_service_round_trip_registration_restore_and_final_only_answer -q`→exit`0`；`1 passed, 1 warning in 0.25s`。
- Exact final Python command/result: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_answer_stream.py tests/test_desktop_service.py tests/test_desktop_fixture.py tests/test_desktop_protocol_contract.py tests/test_turn_finalizer.py tests/test_session_eviction.py::test_final_text_validator_runs_before_the_turn_is_recorded -q`→exit`0`；`190 passed, 1 warning in 1.12s`。Warning is the existingLangGraph`allowed_objects`pending deprecation。
- Exact Node command/result: `cd app/desktop && /home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types tests/answer_stream.test.ts tests/protocol.test.ts`→exit`0`；`86 passed, 0 failed`in`185.122772ms`。
- Exact TypeScript/Rust results: `./node_modules/.bin/tsc --noEmit`underConda`app`→exit`0`/no output；the exact Rust protocol selector recorded at02:04→exit`0`，library`8 passed, 0 failed, 20 filtered out`andmain`0 tests`。
- Diff/scope/safety audit: repository-root`git diff --check`exit`0`/no output。Production-only search across`app/agent`、`app/desktop/src`、`src-tauri`and`contract.json`found no`answer.chunk`、`post_finalized`、`provisionalText`、retiredchunk action or streamingfallback labels。Remaining literals are explicit negative fixture/tests only。Changed paths are exactly7production/contract files、5direct test/fixture files、theactive Phase 05 file and this log；`session.py`、graph/execution、Fusion/Extended/Citation、dependencies/locks remain unchanged。
- External/safety counters: live/paid provider`0`、real MCP/Ollama`0`、real user store/credential`0`、broader suites/builds`0`。Cargo used existing dependency graph and ignored target output only。
- Commit disposition/hash: authorized Phase 05 local implementation commit pending；hash will be appended in a log-only follow-up。Remote push unauthorized。
- Next eligible action: run final uncached/cached name checks，commit exactlythe14 Phase 05 paths，record hash/clean tree，then immediately loadPhase 06。

## 2026-09-01 02:08 CST — Phase 05: implementation hash recorded

- Local implementation commit: `b95ff9a0eb5e5c7871f50fbe7eb20153a99328fb` (`fix(desktop): deliver final answers once`)。
- Commit result: `14 files changed, 239 insertions(+), 457 deletions(-)`；cached name audit listed exactlythe14 declared Phase 05 paths，and both uncached/cached`git diff --check`exited`0`。
- Immediate post-commit audit: `git status --short`returned no output。No branch/worktree、dependency/lockfile orremote operation occurred。
- Next eligible action: commit this hash record as a log-only follow-up，verifyclean tree，then read Phase 06/live persistence/restore sources beforeitsfirst write。

## 2026-09-01 02:13 CST — Phase 06: runtime/source preflight

- Status transition: `Not started` → `In progress` after Phase 05 became Complete and its implementation hash record was committed。
- Durable sources reloaded: Phase 06 objective、format/version contract、prompt-eligibility rules、Fusion/Citation boundaries、transcript contract、lifecycle tests and focused verification were read in full；global plan/decision/authorization sources were already reloaded for this continuous run。Live Plan log writer/parser、`TurnRecord` prompt assembly、journal/session persistence seam、Desktop transcript merge/page result、shared JSON/TypeScript/Rust protocol and directly related Python/Node tests were inspected before the first application write。
- Runtime/Git/dirty-tree gate: WSL/Linux；branch `GUI` tracking `origin/GUI` and ahead 13；HEAD `b468204d52a8cf79ba684e5c4bfcaf3607d42f37`；`git status --short` returned no output before this entry。Python uses Conda `app` with Poetry；Node/npm and Cargo remain Linux toolchains。
- Authorization in force: Plan log v2/transcript DTO compatibility extension、direct Python/React/TypeScript/Rust/internal protocol/fixtures/tests and a phase-only local commit are explicitly authorized。Dependency/lockfile、live provider、real MCP/Ollama/store/credential、Fusion/Extended/Citation redesign、first-turn durability、branch/worktree/push remain excluded。
- Current causal hypothesis and attempt number: attempt 1。The current unversioned Markdown writer drops tool identity from `TurnRecord`, while the restore parser rejects every Tool/Result marker and Desktop DTO has no activity field。The smallest safe repair is one versioned v2 structured JSON turn payload in the existing Plan log, parser-derived prompt eligibility, legacy v1 display-only parsing, and one bounded `toolActivities` transcript extension；restore reconstructs messages only for complete unique normal-scope pairs and never executes them。
- Exact initial/expanded write set and ownership: persistence/core `app/agent/turns/memory.py`、`plan_log.py`、`journal.py`、`app/agent/session.py`、`app/agent/desktop/service.py`；contract/UI `app/desktop/protocol/v1/contract.json`、`fixtures.json`、`app/desktop/src/protocol.ts`、`App.tsx`、`app/desktop/src-tauri/src/protocol.rs`（`styles.css` only if a direct render gap is proven）；direct tests `app/tests/test_plan_mode.py`、`test_desktop_conversations.py`、`test_desktop_service.py`、`test_desktop_protocol_contract.py`、`test_desktop_fixture.py` and `app/desktop/tests/conversations.test.ts`、`protocol.test.ts`；active phase file and this log。Fixture/session helpers remain read-only unless the lifecycle rejecting check proves they are the narrowest seam。
- Commands actually run and exact outcomes: source/schema reads only。Current contract confirmed transcript items contain only `turnNumber/timestamp/userText/assistantText`；`AgentConfig.plan_log_max_tool_chars` is 65,536；Rust/TypeScript exact-key validators match the same four-field DTO。No Phase 06 test、broader suite、build or external call has run yet。
- User-visible/fixture observation: current v1 Plan parser rejects a file containing `### Tool:` or `**Result:**` wholesale；current `TurnRecord.to_messages()` emits only Human/final AI, and transcript renders no independent tool role。These are source findings, not pass evidence。
- Diff/scope/safety audit: first dirty paths are only this active phase status and build-log entry；no application、dependency、lockfile、generated or real-data path changed。
- Commit disposition/hash: pending focused verification and exact phase scope audit；remote push unauthorized。
- Blockers or disproved assumptions: none。A v2 JSON payload in the existing Markdown file avoids a sidecar or migration and keeps adversarial Markdown out of parser control syntax。
- Next eligible action: add the smallest Plan log v2/tool-pair round-trip and prompt-role regression, run only that selector for causal red, then implement the persistence core before extending Desktop protocol/UI。

## 2026-09-01 02:14 CST — Phase 06: v2 causal rejecting check

- Status transition: remains `In progress`；attempt 1 causal red established。
- Exact write before check: only `app/tests/test_plan_mode.py` gained one v2 tool-pair/adversarial-marker round-trip regression；production remained unchanged。Active phase status and this log are the only other dirty paths。
- Exact command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_plan_mode.py::test_v2_plan_log_round_trips_tool_pair_and_prompt_roles -q`。
- Exact result: exit `1`；`1 failed, 1 warning in 0.09s`。The first assertion expected `format_version: 2`, but the current header had no version and the rendered body showed raw nested `### Tool:`、``````, `**Result:**`、`---` and `## Turn 99` payload markers。
- Evidence classification: expected rejecting check, not pass evidence。The test used only `tmp_path`; no real `app/plan_logs/`、provider、MCP、Ollama、store or credential was accessed。The warning is the existing LangGraph `allowed_objects` pending deprecation。
- Hypothesis disposition: confirmed at the writer boundary。A structured v2 encoding must prevent payload text from becoming turn/parser controls, retain call identity/status, and allow safe message reconstruction after restore。
- Next eligible action: implement v2 header/render/parser plus `ToolActivityRecord` prompt reconstruction, rerun the exact selector, then add legacy/incomplete/Citation/Fusion/bounds regressions before Desktop DTO work。

## 2026-09-01 02:46 CST — Phase 06: focused verification, scope audit and completion

- Status transition: `In progress` → `Complete` in attempt 1 after the complete focused matrix、lifecycle oracle and scope audit passed。
- Confirmed implementation/schema: new files use the existing Plan log path with header `format_version: 2` and one compact single-line JSON payload per turn。Root fields are `format_version/turn_id/timestamp/user/assistant/scope/tool_activities`; each on-disk activity contains only `call_id/name/arguments/result/status`。`promptEligible` is never serialized and is derived after parse。No sidecar、migration、database or dependency was added。
- Version/bounds disposition: missing header version is legacy v1；v1 resume keeps the legacy writer；v2 resume keeps v2；unknown versions fail closed and are not overwritten。Existing file/file-count/total/turn limits remain 1 MiB、4,096 files、8 MiB、4,096 turns and 131,072 chars per user/final side；v2 adds at most 128 activities, 256-byte call id/name, 32,768-byte canonical JSON arguments and 65,536-byte result。Desktop enforces the same activity bounds plus the existing 1 MiB page budget, now counting every activity field。
- Prompt/special-scope disposition: only a unique structurally valid normal-scope pair with a bounded nonempty id/name、JSON-object args、matched full result and non-`incomplete` status becomes prompt eligible。Duplicate/missing ids、orphan/extra results、malformed fields and truncation remain per-activity display-only。Legacy v1 always has `callId:null` and display-only semantics。Citation scope is display-only, and `citation_workflow` is additionally excluded even if an on-disk record claims normal scope；no registry/active Citation state is reconstructed。Fusion scope/candidate Markdown still fails closed as before；Extended/Fusion semantics were not added。
- Lifecycle observation: fake tool count was `0` initially、`1` after the first Plan turn/persist、`1` after shutdown plus fresh Desktop transcript/select、and `1` after the new ordinary turn。The restored transcript was user → independent `rag_search` activity/result → final assistant；the new graph input roles after excluding System messages were exactly `HumanMessage → AIMessage(tool_calls) → ToolMessage → AIMessage(final) → HumanMessage(new)`。The restored call id/result were `call-persisted`/`persisted tool result`; no model/tool ran during transcript or select and the continued answer came from a separate no-tool fake graph。
- Legacy/safety observations: adversarial Unicode/newline/quote/fence/`### Tool:`/`**Result:**`/`---`/fake turn-heading payload round-tripped through escaped JSON without changing turn boundaries。Legacy well-formed and malformed tool blocks retained reliable user/final sides and produced display-only activities; their sentinel text was absent from prompt messages。Duplicate、orphan、oversize、on-disk `promptEligible` injection、unknown version、wrong session header、bad UTF-8、file/file-count/total limits and Fusion exclusion all had focused regressions。Citation generic-call injection stayed excluded。
- Transcript/UI observation: shared JSON、TypeScript and Rust contracts require `toolActivities[]` with nullable call id、bounded name/arguments/result、`ok|failed|denied|incomplete` status and boolean parser-derived diagnostic。A cross-language negative trace rejects arbitrary `running` status。React SSR placed labels in strict `You → Tool activity → Tool result → Assistant` order；both arguments and result use `SafeContent`, and an embedded `<script>` rendered inert/escaped。No tool button、raw HTML or Desktop capability was introduced。
- Exact rejecting/repair evidence: initial selector `pytest tests/test_plan_mode.py::test_v2_plan_log_round_trips_tool_pair_and_prompt_roles -q` exited `1` with `1 failed, 1 warning in 0.09s` because the header lacked v2 and raw payload markers appeared in Markdown；after the core patch the same selector exited `0` with `1 passed, 1 warning in 0.06s`。The first full Python matrix exited `1` with `184 passed, 1 failed, 1 warning in 1.27s`; the sole failure was a test-only variable-placement mistake that looked for `chunkCount` in the transcript item schema。Its exact corrected selector passed `1 passed, 1 warning in 0.07s` without a production change。
- Exact lifecycle/edge commands: the lifecycle selector `pytest tests/test_desktop_conversations.py::test_v2_plan_tool_restore_and_continue_never_replays_old_tool -q` → `1 passed, 1 warning in 0.12s`；Citation/legacy/page/fixture selector → `4 passed, 1 warning in 0.24s`；wrong-session/bad-UTF-8/total-limit selector → `2 passed, 1 warning in 0.13s`。All used pytest-owned temporary roots and in-memory/fake graph/history/search boundaries；temporary data was caller-owned and no real `app/plan_logs/` or store was used。
- Exact final Python command/result: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_plan_mode.py tests/test_desktop_conversations.py tests/test_desktop_service.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py -q` → exit `0`；`190 passed, 1 warning in 1.43s`。Warning is the existing LangGraph `allowed_objects` pending deprecation。
- Exact Node command/result: `cd app/desktop && /home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types tests/conversations.test.ts tests/protocol.test.ts` → final exit `0`；`89 passed, 0 failed` in `12229.609503 ms`。An earlier identical invocation completed after the wrapper discarded its session id/tail output and therefore was explicitly not pass evidence；the immediate evidence rerun produced `88 passed`, and the final rerun after adding the shared negative fixture produced the recorded 89-pass result。
- Exact TypeScript/Rust results: `./node_modules/.bin/tsc --noEmit` under Conda `app` → exit `0`/no output。`env PATH=/home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:/usr/local/bin:/usr/bin:/bin .../cargo test --manifest-path src-tauri/Cargo.toml protocol::tests` → exit `0`; library `8 passed, 0 failed, 20 filtered out`, main `0 tests`。
- Diff/scope/safety audit: repository-root `git diff --check` exited `0`/no output。Changed paths are exactly 12 persistence/Desktop/contract/UI/fixture production paths、5 direct Python/Node test paths、the active phase file and this log（19 total）。`test_desktop_service.py` remained read-only but passed in the required matrix。Production Plan writer search contains no `promptEligible`; dependency/lockfile search returned no changed path。Live/paid provider `0`、real MCP/Ollama `0`、real store/credential `0`、broader suites/builds `0`。
- Staging-audit note: the first composite staging command returned exit `1` only at its final shell `test -z "$(git diff --name-only)"` guard even though the preceding cached check/name list were correct。The immediate direct audit showed `git diff --name-only` with no output、`git diff --cached --name-only | wc -l` = `19`, and `git diff --cached --check` exit `0`; no file changed between those observations。The composite exit is not pass evidence and is retained as an orchestration/guard anomaly。
- Commit disposition/hash: authorized Phase 06 local implementation commit pending；hash will be appended in a log-only follow-up。Remote push remains unauthorized。
- Blockers or disproved assumptions: no blocker。The only disproved write-set assumption was that `test_desktop_service.py` needed edits；existing coverage accepted the DTO extension unchanged。CSS became directly necessary to keep restored Tool/Result visually independent from user/assistant roles。
- Next eligible action: stage exactly these 19 paths, audit the cached set/check, create the Phase 06 local commit, append its hash in a log-only commit, verify clean tree, then load Phase 07 and execute its one authorized broader acceptance sequence exactly once。

## 2026-09-01 02:48 CST — Phase 06: implementation hash recorded

- Local implementation commit: `3c3ae7e84f5b860a16d4ef304b0e8f026edc3256` (`fix(plan): restore tool-aware conversations`)。
- Commit result: `19 files changed, 1932 insertions(+), 151 deletions(-)`；the count includes the phase status/evidence and no dependency/lockfile、generated user data or out-of-scope subsystem。
- Immediate post-commit audit: `git status --short` returned no output。
- Next eligible action: commit this hash record as a log-only follow-up, verify clean tree, then enter Phase 07 because all Phase 01–06 dependencies are Complete。

## 2026-09-01 02:58 CST — Phase 07: integration acceptance preflight

- Status transition: `Not started` → `In progress` after Phases 01–06 were re-read as `Complete` with focused evidence and scoped local commits.
- Durable sources reloaded: applicable repository instructions、`PROMPTS.md`、`GOALS.md`、`PLANS.md`、`user-decisions.md`、this log、Phase 07、current package scripts/test topology、Desktop fixture/service/React preview path、Rust supervisor tests and both construction-bearing RAG exclusions were read against live source and Git state. The completed historical GUI bundle was not reopened or modified.
- Runtime/Git/dirty-tree gate: WSL/Linux project `/home/minervamuses/research-agent-workspace`; branch `GUI` tracking `origin/GUI` and ahead 15; HEAD `0911d8799ff3be8717ccaf019321d73dc18ad0b5`; first Phase 07 write began from a clean tree. Tool evidence is Conda `app` Python 3.13.14、Poetry 2.4.1、Node v24.18.0 and Cargo 1.91.1, all Linux-owned.
- Authorization in force: one existing-graph Phase 07 acceptance run、minimal fixture/test extension if an observation is missing、the listed broader suites/build once each、durable status/evidence updates and one phase-scoped local commit. Dependency/lockfile、live provider、real MCP/Ollama/store/credential、Fusion、Extended、Citation redesign、first-turn durability、multi-GUI、branch/worktree/push remain excluded.
- Current causal hypothesis and attempt number: acceptance attempt 1. Existing focused tests cover each owning phase but no single existing selector carries MCP default、dynamic Skill final-only/error cleanup、Plan v2 tool persistence、restart/select/continue and legacy display-only observations through one caller-owned fixture root. The smallest extension is one high-level test in the existing `test_desktop_fixture.py`; production remains unchanged unless that gate exposes a regression. Rust long-request survival and React reducer/rendering remain their existing focused production-boundary selectors.
- Exact initial write set and ownership: `app/tests/test_desktop_fixture.py`、`harness/fix_plans/phases/phase-07-integration-acceptance.md` and this log only. The integration test will optionally consume the explicitly supplied safe fixture root and leave its cleanup to the caller; ordinary suite runs retain pytest-owned temporary cleanup.
- Expanded write set before fixture edit: live `FixtureSession.turn_outcome()` has no bounded delayed normal-answer marker, so it cannot expose the required pre-terminal observation window through the real service/native supervisor. Add only one environment-gated deterministic marker and bounded stage timing in `app/agent/desktop/fixture_session.py`; this is the existing fake owner, makes no provider/network call and does not alter normal runtime behavior.
- Temporary boundary: the accepted root is `/tmp/research-agent-desktop-phase02-phase07-yppmVG`, resolved to itself、direct child of `/tmp`、non-symlink、owner `minervamuses:minervamuses`/uid 1000、mode 700. A first shell attempt was invalid because host-shell command substitution emptied its variable after `mktemp`; it created unused empty `/tmp/research-agent-desktop-phase02-phase07-59yTTZ`, and exact non-recursive `rmdir` removed it. That failed attempt is not pass evidence.
- Verification-tool evidence: the repository `webapp-testing` helper exists, but importing Python `playwright` in Conda `app` exited 1 with `ModuleNotFoundError`; no dependency was installed. The bundled in-app browser documentation and local-web/viewport guidance were therefore read completely for the served-route fallback. WSLg is available (`DISPLAY=:0`、`WAYLAND_DISPLAY=wayland-0` and live socket), so after the single planned no-bundle build the produced native binary may be launched once for stronger visual/keyboard observation without another build.
- Broader topology decision: `tests/rag/test_component_flow.py` and `tests/rag/test_root_identity.py` remain offline but construction-bearing local Chroma/ingest/sync/prune workflows unrelated to the five GUI repairs, so the planned Python broader command will retain both exclusions. `npm run tauri -- build --no-bundle` already invokes `tsc --noEmit` plus Vite; no duplicate frontend build will be added.
- Commands actually run and outcomes: preflight/source/runtime reads only plus the root operations above. No Phase 07 fixture selector、browser interaction、broader suite、Cargo full suite or Tauri build has run yet.
- Diff/scope/safety audit: before this entry only the Phase 07 status file was dirty; no application production、manifest、dependency/lockfile、generated output or real-data path changed.
- Commit disposition/hash: pending integrated evidence、one-time broader pass、cleanup and exact scope audit; remote push unauthorized.
- Next eligible action: add the single existing-fixture integration gate, run it with the exact owned root, then run the existing focused Rust/React boundary selectors and visual checks before the one-time broader sequence.

## 2026-09-01 03:02 CST — Phase 07: isolated fixture journey green

- Status transition: remains `In progress`; acceptance attempt 1 passed its first integrated gate without an owning-phase production regression.
- Minimal fixture/test extension: `FIXTURE_DELAYED_FINAL` exists only in the environment-gated Desktop fixture. It sends bounded `fixture.prepare → before-old-deadline → after-old-deadline` stages, holds the fake turn for a two-second pre-terminal observation window, then uses the unchanged persistence/final result path. The high-level test optionally consumes the exact caller-owned root and otherwise creates/removes its own direct `/tmp` fixture root.
- Exact command: `cd /home/minervamuses/research-agent-workspace/app && RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT=/tmp/research-agent-desktop-phase02-phase07-yppmVG /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_fixture.py::test_phase07_integrated_final_only_skill_tool_restore_journey -q`.
- Exact result: exit `0`; `1 passed, 1 warning in 2.54s` (`7.65s` wrapper wall time). The warning is the existing LangGraph `allowed_objects` pending deprecation.
- Integrated event/order observation: the delayed request crossed the fixture's shortened old-deadline stage while its task was still pending; no `answer.chunk` or answer text was present. Only after the fake answer was persisted did one terminal result return with `streamKind=final_only`/`chunkCount=0`. Stage order ended with `fixture.finalized`.
- MCP/Skill observation: `session.create` omitted `loadMcp`, and `runtime.diagnostics.mcpEnabled` was `true`. After the fake extension apply plus graceful stop/restart, the same default was still true、`mcpFamilies=[fixture-clock]` and the loaded Skill catalog was `[fixture-writer]`; no external MCP executable ran. One `/fixture-writer` command incremented the fixture session by exactly one turn、returned one final-only answer with zero answer events, and the next ordinary turn contained no Skill response context. A provider-error Skill branch emitted no answer event/persisted turn; the following ordinary retry was clean. DTOs had no `activeSkill` or `taskMode`.
- Plan/tool/restart observation: in Plan mode `rag_search` ran exactly once and persisted a prompt-eligible v2 activity. After graceful stop and a fresh service on the same root, transcript and select left count at one; reconstructed role order for that turn was `Human → AI(tool call) → Tool → AI(final)`. A new ordinary turn returned one final-only answer and still left count at one. A separately seeded legacy tool-bearing v1 conversation selected successfully with `callId=null`/`promptEligible=false`; its sentinel was absent from prompt messages and tool count remained one.
- Error/partial observation: all success/error/continued event sinks contained zero `answer.chunk`; complete terminal text was absent from event payloads. The failed Skill marker was absent from transcript persistence. Every process-level service shutdown returned `{status: stopped, flushed: true}`.
- Temporary-root audit: the exact root remains owned and isolated for the later native GUI observation; current size is 332 KiB. Its only Chroma file is the fixture's locally constructed empty/history boundary under this root, not repository `app/store` or user data. No provider、real MCP、Ollama、credential or external endpoint was accessed.
- Scope/diff disposition: current changed application path is fixture-only `app/agent/desktop/fixture_session.py`; direct test、Phase 07 file and this log are the other paths. No dependency/lockfile or normal production path changed.
- Broader/visual disposition: not yet run. Next run the existing focused Rust long-request and Node final-only/tool-render selectors, then the served-route viewport/keyboard check and the one-time broader sequence.

## 2026-09-01 03:04 CST — Phase 07: focused React pass and Rust command-environment nonpass

- Status transition: remains `In progress`; acceptance attempt 1 code is unchanged.
- Exact Node command/result: `cd app/desktop && /home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types tests/answer_stream.test.ts tests/conversations.test.ts` → exit `0`; `14 passed, 0 failed` in `12453.160036ms` (`14.996s` wrapper). It covered the final-only reducer、no-preview failure、bounded activity、MCP-default create payload and SSR tool-between-user/assistant rendering with inert raw HTML.
- Exact Rust command/nonpass: `cd app/desktop && env PATH=/home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:/usr/local/bin:/usr/bin:/bin cargo test --manifest-path src-tauri/Cargo.toml progressing_request_can_outlive_the_prior_absolute_deadline` → exit `1`; one selected test failed before launching its fake child because `backend.rs` test setup required `CONDA_PREFIX` and the direct Cargo environment omitted it (`panicked ... CONDA_PREFIX`). This is not supervisor pass/fail evidence.
- New focused hypothesis: the selected Rust test intentionally resolves its fake Python from `CONDA_PREFIX/bin/python`; setting the already verified `/home/minervamuses/miniconda3/envs/app` prefix is the only command correction needed. No source/test edit is indicated. Rerun only this selector once with that variable, not a full Cargo suite.
- Broader counters remain zero; the later full npm/Cargo commands have not run.

## 2026-09-01 03:07 CST — Phase 07: focused boundary and served-route observation

- Status transition: remains `In progress`; all focused code boundaries are green, while native conversation-surface observation remains pending the single planned build.
- Corrected Rust selector: `cd app/desktop && env CONDA_PREFIX=/home/minervamuses/miniconda3/envs/app PATH=/home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:/usr/local/bin:/usr/bin:/bin cargo test --manifest-path src-tauri/Cargo.toml progressing_request_can_outlive_the_prior_absolute_deadline` → exit `0`; library `1 passed, 0 failed, 27 filtered out` in `0.25s`, main `0 tests`. The fake request emitted start/progress on both sides of the shortened old deadline、returned a terminal result and left the child alive through graceful shutdown.
- Served-route setup: one Vite dev server was started at `http://127.0.0.1:4173/`; `curl --fail` returned the expected HTML. The initial browser wait using unsupported `networkidle` was a nonpass API choice; the same already-open tab succeeded with `domcontentloaded` and was not reloaded.
- Desktop visual observation: explicit 1440×900 viewport reported body 1440×900、no horizontal overflow、no `Active Skill` or `Task mode` text, and the bounded `BROWSER_PREVIEW` recovery card remained inside the workspace. Screenshot inspection showed no disabled-control gap or clipped layout.
- Mobile visual observation: explicit 390×844 viewport reported body width 390、no horizontal overflow、main visible and the skip-link present. Screenshot inspection showed the sidebar stacked above the main recovery card with readable wrapping and no clipping.
- Keyboard/route limitation: semantic keyboard focus reached the `Skip to main workspace` anchor, but both supported press paths left the hash/target unchanged in the in-app browser automation backend. Browser preview also intentionally cannot connect to the Tauri backend, so this fallback did not observe composer、pending answer、tool-history or sidebar-select behavior. Those surfaces remain covered by the 14-pass production React reducer/SSR selector and are not yet claimed as native visual evidence.
- Browser console/cleanup: the only captured errors were Vite HMR WebSocket connection failures from the in-app browser; no application exception was observed. The explicit viewport override was reset、test tab closed、Vite was interrupted, and a final curl failed to connect as expected. The server's Ctrl-C/Conda `KeyboardInterrupt` exit 1 is shutdown evidence, not a test failure.
- Broader counters: still zero. Next execute the planned Python and npm broader suites once each, then Cargo full once and Tauri no-bundle build once; no duplicate frontend build.

## 2026-09-01 03:10 CST — Phase 07: one-time Python broader failure and npm broader pass

- Status transition: remains `In progress`; the one-time Python broader result prevents completion until the single owning regression is isolated and repaired. The broad command will not be rerun.
- Exact Python broader command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest --ignore=tests/rag/test_component_flow.py --ignore=tests/rag/test_root_identity.py`.
- Python broader result: exit `1`; `908 passed, 1 failed, 1 warning in 7.58s` (`13.62s` wrapper). Sole failure: `tests/test_turn_finalizer.py::test_plan_log_records_model_answer_without_injecting_receipt` found `src-known` inside a v2 `citation_workflow` activity result in the Plan log. The existing warning is LangGraph `allowed_objects` pending deprecation. This command has now consumed the single authorized Python broader run and is not pass evidence.
- Failure ownership/hypothesis: Phase 06 generalized tool-activity persistence now serializes Citation save receipts even though prompt eligibility is false. The existing finalizer regression requires that receipt not be injected into Plan content, and current goals permit Citation activity at most display-only rather than requiring persistence. The smallest likely repair is to omit `citation_workflow` from Plan-log activities while preserving the finalized model answer and all generic v2 behavior; changing Citation handler/gate/renderer/state is forbidden and unnecessary. This hypothesis must first be checked with the one failed selector and direct writer trace.
- Exact npm broader command: `cd app/desktop && /home/minervamuses/miniconda3/bin/conda run -n app npm test`.
- npm broader result: exit `0`; `108 passed, 0 failed` in `14363.889195ms` (`16.79s` wrapper). It included full answer/backend/conversation/protocol/trust coverage. Repeated Vite WebSocket warnings reported port 24678 already in use, but no test failed or skipped; the suite will not be rerun.
- Broader counters: Python 1/1 consumed (failed)、npm 1/1 consumed (passed)、Cargo full 0/1、Tauri no-bundle build 0/1. Next action is one focused failed Python selector plus live source trace; no broad retry.

## 2026-09-01 03:12 CST — Phase 06: integration-discovered Citation receipt regression

- Status transition: Phase 06 `Complete` → `In progress` for one integration-discovered compatibility regression; Phase 07 remains `In progress`. This is Phase 06 follow-up attempt 2, not a Citation redesign.
- Focused red command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_turn_finalizer.py::test_plan_log_records_model_answer_without_injecting_receipt -q`.
- Focused red result: exit `1`; `1 failed, 1 warning in 0.12s`. It reproduced the broader failure exactly: finalized model text was correct, but an orphan `citation_workflow` ToolMessage with no corresponding `tool_calls` entry became an `incomplete` display-only v2 activity whose JSON result contained `src-known`.
- Direct source distinction: `test_v2_citation_activity_is_display_only` deliberately preserves a complete paired Citation activity as display-only. The finalizer receipt is structurally different—an unmatched Citation result emitted after save finalization—and the pre-Phase-06 invariant forbids injecting that receipt into Plan content. Therefore filtering all Citation history would be too broad.
- Causal hypothesis: in `PlanLog.build_tool_activities()` omit only unmatched `citation_workflow` result entries when `scope == citation`; retain paired Citation activities display-only、retain generic Citation-scope activities display-only and retain the authoritative assistant answer. This restores the old receipt boundary without changing Citation handler、registry、gate、renderer、thinking or prompt eligibility.
- Exact expanded write set before production edit: `app/agent/turns/plan_log.py`、the Phase 06 status file and this log. Existing `test_turn_finalizer.py::test_plan_log_records_model_answer_without_injecting_receipt` is the rejecting regression; `test_plan_mode.py::test_v2_citation_activity_is_display_only` is the paired-activity preservation guard. No test edit is initially necessary.
- Broader disposition: the Python broader run will not be repeated. After the minimal edit, run only those two selectors plus the Phase 06 v2 generic round-trip selector; if green, return Phase 06 to Complete and continue the remaining first-run Cargo/build gates.

## 2026-09-01 03:14 CST — Phase 06: Citation receipt boundary restored

- Status transition: Phase 06 `In progress` → `Complete` again in follow-up attempt 2; Phase 07 remains `In progress`.
- Minimal production repair: `PlanLog.build_tool_activities()` now drops only unmatched `citation_workflow` result entries in Citation scope. A complete paired Citation call/result is still persisted display-only、generic Citation-scope activities remain display-only、normal generic v2 prompt roles are unchanged, and the finalized assistant answer still persists.
- Exact focused command: `cd app && /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_turn_finalizer.py::test_plan_log_records_model_answer_without_injecting_receipt tests/test_plan_mode.py::test_v2_citation_activity_is_display_only tests/test_plan_mode.py::test_v2_plan_log_round_trips_tool_pair_and_prompt_roles -q`.
- Exact result: exit `0`; `3 passed, 1 warning in 0.07s` (`3.41s` wrapper). The existing LangGraph warning is unchanged. The first selector proves `src-known` is absent from Plan content while model wording remains; the second preserves paired Citation display-only history; the third preserves generic v2 tool-role round-trip.
- Scope/non-goal audit: one conditional in the existing Plan activity builder only; no Citation handler/source registry/gate/renderer/state/thinking、dependency/lockfile or protocol change. Existing tests were sufficient and remain unedited.
- Broader disposition: the earlier Python broader result remains `908 passed, 1 failed` and is not rewritten as a pass or rerun. Its sole failure now has a focused green repair, which will be explicitly reported as the post-broad disposition.
- Commit disposition: create a separate Phase 06 follow-up commit containing only `app/agent/turns/plan_log.py`; record its hash in this still-uncommitted Phase 07 log. Remote push remains unauthorized.

## 2026-09-01 03:16 CST — Phase 06: follow-up commit recorded

- Local follow-up commit: `63e0ed0a3abbd1a61e542eaa18c4e3ac07fe3659` (`fix(plan): omit unmatched citation receipts`).
- Commit scope/result: exactly `app/agent/turns/plan_log.py`; `1 file changed, 4 insertions(+), 2 deletions(-)`. Scoped uncached and cached whitespace checks exited 0, and cached name audit listed only that path.
- Phase 07 log/fixture/test changes remain unstaged and were not mixed into this Phase 06 checkpoint. No remote operation occurred.

## 2026-09-01 03:18 CST — Phase 07: one-time Cargo broader command-environment failure

- Status transition: remains `In progress`; the single authorized full Cargo run is consumed and its nonpass remains explicit.
- Exact command: `cd app/desktop && env CONDA_PREFIX=/home/minervamuses/miniconda3/envs/app PATH=/home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:/usr/local/bin:/usr/bin:/bin cargo test --manifest-path src-tauri/Cargo.toml`.
- Exact result: exit `1`; library `27 passed, 1 failed` in `0.25s`, failing only `backend::tests::source_launch_uses_the_exact_active_conda_interpreter`; main did not run after the library failure. The test returned `RUNTIME_WRONG_CONDA_ENV` because the command set the correct prefix but omitted `CONDA_DEFAULT_ENV=app` required by the source-launch identity gate. All protocol、long-request、child-exit、shutdown and malformed-output tests passed.
- Evidence classification: this is not a Cargo broader pass and will not be rerun under the current one-run authority. It is also not yet source-code failure evidence because the test rejected the incomplete launch environment before checking the interpreter path.
- New focused hypothesis: adding only the already verified `CONDA_DEFAULT_ENV=app` to the same current Conda prefix should make the exact failed selector pass with no source change. Run only that selector once; regardless of result, preserve the full-suite nonpass in final reporting.
- Broader counters: Python 1/1 failed then focused-repaired、npm 1/1 passed、Cargo 1/1 failed at command environment、Tauri build 0/1. No broader rerun is planned.

## 2026-09-01 03:25 CST — Phase 07: build, native observation, cleanup and authority blocker

- Status transition: `In progress` → `Blocked` after every meaningful non-repeat path completed. Phases 01–06 remain Complete; Phase 07 cannot honestly become Complete without two broader pass results that current one-run authority forbids rerunning.
- Corrected Cargo isolation: `cd app/desktop && env CONDA_DEFAULT_ENV=app CONDA_PREFIX=/home/minervamuses/miniconda3/envs/app PATH=... cargo test --manifest-path src-tauri/Cargo.toml source_launch_uses_the_exact_active_conda_interpreter` → exit `0`; library `1 passed, 0 failed, 27 filtered out`, main `0 tests`. This confirms the full-run sole failure was the incomplete command environment; it does not rewrite the full Cargo result as a pass.
- Exact Tauri command: `cd app/desktop && env CONDA_DEFAULT_ENV=app CONDA_PREFIX=/home/minervamuses/miniconda3/envs/app PATH=/home/minervamuses/.rustup/toolchains/stable-x86_64-unknown-linux-gnu/bin:/home/minervamuses/miniconda3/envs/app/bin:/usr/local/bin:/usr/bin:/bin /home/minervamuses/miniconda3/envs/app/bin/npm run tauri -- build --no-bundle`.
- Tauri result: exit `0`. Its sole `beforeBuildCommand` ran `tsc --noEmit && vite build`; Vite transformed 25 modules and produced `dist/index.html` 0.45 kB、CSS 15.75 kB、JS 267.54 kB in 139ms. Rust release build finished in 2m11s and produced `app/desktop/src-tauri/target/release/research-agent-desktop`. No duplicate frontend build or bundle/release/deployment step ran.
- Native WSLg observation: one built binary was launched with fixture mode、the exact owned root and Conda `app`; no second GUI process existed. After one capture-recovery, the unique `Research Agent (Ubuntu-24.04)` window visibly showed the current native app at backend-stopped state with readable sidebar/header/primary start control、no Active Skill/Task-mode control and no clipping. EGL/Zink warnings fell back to a visible window and did not terminate it.
- Native interaction limitation: the first start-button input was interrupted with `user input was detected`; the required re-observation then captured the ChatGPT window despite the returned target still being the unique WSLg Research Agent window. Per the Computer Use skill, all further UI input stopped immediately—no stale coordinate was reused and no ChatGPT control occurred. Therefore native start/composer/sidebar keyboard behavior is unavailable, not pass evidence. Served-route desktop/mobile screenshots plus production React SSR/reducer tests are the bounded fallback; the initial native layout only is observed.
- GUI/process cleanup: Ctrl-C ended the one native binary session; `pgrep -af agent.desktop.server` and `pgrep -af research-agent-desktop` both returned no process. The earlier Vite test server and browser tab were already stopped/closed.
- Temporary-root destructive audit and cleanup: immediately before removal, `/tmp/research-agent-desktop-phase02-phase07-yppmVG` resolved to itself、was a non-symlink direct `/tmp` child owned by uid 1000/mode 700, and no fixture backend/app process remained. Exact `rm -rf -- /tmp/research-agent-desktop-phase02-phase07-yppmVG` exited 0; exact absence check passed and no `research-agent-desktop-phase02-phase07-*` child remains. This removed only disposable fixture state and is not recoverable or needed.
- GOALS mapping disposition: all Phase 01–06 conditions and the isolated integration condition are now checked from recorded focused/journey evidence. The broader-pass condition remains unchecked. The final diff/scope condition remains unchecked until its one planned repository-wide check runs.
- Fresh-authority blocker: to convert Phase 07 to Complete, authorize exactly two corrected complete-suite reruns—(1) the same Python broader command after commit `63e0ed0...`, and (2) the same full Cargo command with both `CONDA_DEFAULT_ENV=app` and the verified `CONDA_PREFIX`. No second npm suite or Tauri build is needed. No dependency、external service、non-goal or production redesign authority is requested.

## 2026-09-01 03:30 CST — Phase 07: final residue/diff audit and blocked checkpoint

- Status transition: remains `Blocked`; no unexecuted in-envelope implementation or validation path remains.
- Exact final whitespace command/result: repository root `git diff --check` → exit `0`, no output. This is the single planned repository-wide Phase 07 diff check; the later cached check is commit-scope validation only.
- Forbidden-residue audit: production search across Python、React/TypeScript、Rust and the shared contract returned no `answer.chunk`、`post_finalized`、`provisionalText`、Task-mode/active-Skill field or retired Skill RPC. Independent timeout searches returned no `request_timeout`、`normal_request_timeout` or `600` literal in `backend.rs`. `loadMcp` remains only the Python `params.get(..., True)` default and optional protocol validators; no production false default remains.
- Audit-command nonpass: one attempted combined host-shell regex search was parsed as shell pipelines and returned command-not-found for its alternatives, so it is not evidence. The independent literal searches immediately above are the corrected evidence and made no writes.
- Deferred-boundary audit: `/citation` remains the reserved persistent CLI special case; the then-named `issue/09-citation-skill-flow-deferred.md` and `issue/07-gui-first-turn-durability-deferred.md` files remained present at that checkpoint. No Fusion/Extended、Citation product redesign、first-turn durability or multi-GUI implementation changed. The Phase 06 follow-up only suppresses an unmatched Citation receipt from Plan content.
- Manifest/lock audit: diff query over `app/pyproject.toml`、`poetry.lock`、`app/env`、Desktop `package.json`/lock、Cargo manifest/lock and `AGENTS.md` returned no path. `git status --short --untracked-files=all` listed exactly the five declared Phase 07 checkpoint paths; build `dist/`/`target/` remain ignored generated outputs, not commit candidates.
- Final Phase 07 checkpoint paths: fixture-only `app/agent/desktop/fixture_session.py`、direct integration `app/tests/test_desktop_fixture.py`、`harness/fix_plans/GOALS.md`、this log and `phases/phase-07-integration-acceptance.md`. Pre-final-log stat was `468 insertions, 35 deletions`; all changes map to delayed fake observation、integrated acceptance evidence/status or success-condition mapping.
- Safety counters: live/paid provider `0`、real MCP/Ollama `0`、real store/credential `0`、dependency/lockfile `0`、remote push `0`. One exact temporary root and one native process were removed/stopped and verified absent.
- GOALS disposition: every substantive Phase 01–06 and diff/integration condition is checked from evidence. The broader-suite success condition remains the sole unchecked condition because Python and Cargo each lack a corrected complete-suite pass.
- Commit disposition: create one local Phase 07 blocked-checkpoint commit containing exactly these five paths, then append its hash in a log-only commit. This preserves completed work without claiming Phase 07/overall Complete.
- Only remaining action requiring fresh authority: rerun `cd app && poetry run pytest --ignore=tests/rag/test_component_flow.py --ignore=tests/rag/test_root_identity.py` once after the Citation fix, and rerun `cd app/desktop && CONDA_DEFAULT_ENV=app CONDA_PREFIX=/home/minervamuses/miniconda3/envs/app cargo test --manifest-path src-tauri/Cargo.toml` once. If both pass, no npm/build rerun is needed; update Phase 07/GOALS/overall status and make a log-only completion commit. Current authorization expressly forbids those second full runs.

## 2026-09-01 03:33 CST — Phase 07: blocked checkpoint commit recorded

- Local checkpoint commit: `c1cfd8c37857676916cd05e6afe17c7a9bc673c2` (`test(desktop): add integration acceptance journey`).
- Commit scope/result: exactly the five declared Phase 07 paths；`5 files changed, 483 insertions(+), 36 deletions(-)`. Cached name-status listed only those paths and cached whitespace check exited 0. Immediate post-commit `git status --short` returned no output.
- This checkpoint intentionally records Phase 07 as Blocked and leaves the broader GOALS checkbox unchecked; it does not claim overall completion. Append this hash record in one log-only commit, then stop because the only remaining commands require fresh authority.
- Remote push、branch/worktree、dependency/lockfile and release/deployment actions remain unperformed.

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
