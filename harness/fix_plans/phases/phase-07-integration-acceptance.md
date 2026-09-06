# Phase 07 — Integration Acceptance and Delivery Audit

## Initial Status

Blocked.

## Dependencies

Phases 01、02、03、04、05、06 all Complete with evidence in `build-log.md`.

## Objective

在current codebase上用一個isolated fake Desktop journey整合驗證五項修復，執行一次適當的broader suites/build，完成diff/scope/deferred-boundary audit；不新增功能或開始cleanup workstream。

## Scope

- Reuse既有exact environment-gated Desktop fixture與caller-owned temporary state root；只在缺少Phases 01–06 required observation時做最小fixture/test extension。
- Run one representative React/Rust/Python boundary journey with fake MCP loader、fake finalized-answer model、fake dynamic Skill、fake tool與Plan log。
- Run planned broader Python/npm/Cargo/Tauri checks once。
- Audit manifests/lockfiles、protocol/versioned format、Git diff、deferred issues與user-visible UI。
- 若integration發現regression，回到owning phase記錄focused attempt；Phase 07不另做unrelated redesign。

## Non-goals / 非目標

- 不呼叫live/paid provider、真實MCP server、Ollama、GPU/full dataset或real user store。
- 不重跑Fusion/Extended live trial，不改Citation flow，不修first-turn abnormal-loss durability或multi-GUI concurrency。
- 不新增dependency、release/installer/CI/docs campaign、performance benchmark或generic fixture framework。
- 不建立remote push、merge/rebase/branch/worktree；只有fresh user authority才可push。
- 不因final review順手修理與GOALS acceptance無關的finding。

## Required Preflight

1. Reload all durable sources and confirm every dependency is Complete with actual evidence, not onlycheckbox。
2. Recheck WSL/Linux、Conda `app`、Node/Cargo paths、Git branch/upstream/HEAD、dirty ownership。
3. Confirm Phase 05 final-only delivery與Phase 06 migration/safety沒有unresolved blocker；有任何一項就不能開始broader pass。舊live-token characterisation是保留的歷史evidence，不是仍待解的attribution requirement。
4. Inspect current package scripts/test topology. If planned command changed，record smallest equivalent before running；do not improvise dependency install。
5. Create one exact direct non-symlink child under `/tmp`，record owner/path，route all fixture state there；never point fixture to repository `app/store`、`app/plan_logs` or user data。

## Integrated Journey

使用production Tauri supervisor、protocol validation、Desktop service、React reducer/rendering與Plan writer/parser，只替換external/agent execution owners：

1. Start backend with fake MCP loader；normal GUI session creation observes MCP default on，without external connection。
2. Dispatch a controlled normal long request that sends bounded progress/activity events across the fixture's shortened former deadline boundary；UI remains busy/responsive，Rust does not kill child，no answer text appears early，then one complete `final_only` terminal result succeeds。
3. Enter a fixture-loaded `/<skill-name> <自然語言 prompt>`。Observe exact Python resolution、one agent invocation、zero `answer.chunk` events、one complete authoritative terminal answer、no Task mode/Active Skill control，and next ordinary turn has no Skill context。
4. Exercise a Skill error or cancel terminal branch；no transient Skill or partial assistant answer appears/persists，retry starts clean。
5. In Plan mode execute one fake generic tool once，persist v2，record invocation count，gracefully stop backend。
6. Restart on the same temporary root，select conversation from sidebar。Observe user、independent tool activity/result、final assistant in order；selection itself makes zero model/tool calls。
7. Send a new ordinary question。Captured context has only validated generic v2 roles，old call count remains unchanged，new final answer在persistence完成後以`final_only` result交付一次。
8. Load one legacy tool-bearing fixture。It is selectable/display-only，legacy sentinel is absent frommodel prompt，no tool replay occurs。
9. Verify bounded error/restart state by terminating the owned fake child only if existing fixture already supports it；do not expand phase solely for an unrelated crash campaign。

## Visual and Interaction Observation

- No Active Skill dropdown/button、Task mode label或hidden disabled gap。
- Dynamic Skill command can be typed/sent fromcomposer；unknown/empty command error is legible and draft recoverable。
- Pending answer只顯示working spinner與bounded stage/tool activity；完整assistant answer在terminal success後一次出現，沒有provisional growth、reconciled prefix或`final-only fallback`誤導標籤。
- Tool activity/result is visually distinct fromYou/Assistant，long bounded content scrolls/wraps，untrusted marker/HTML remains inert。
- Sidebar select/restart/continue works bykeyboard for the representative conversation。

Use the existing real Tauri fixture boundary when available. If native WSLg geometry/control is unavailable，record the exact limitation and use the identical served React route at existing required viewport checks only；do not claim unobserved native behavior。

## Broader Verification

Run each broad command at most once unless a new, recorded hypothesis requires fresh authority：

```bash
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest --ignore=tests/rag/test_component_flow.py --ignore=tests/rag/test_root_identity.py

cd /home/minervamuses/research-agent-workspace/app/desktop
npm test
cargo test --manifest-path src-tauri/Cargo.toml
npm run tauri -- build --no-bundle

cd /home/minervamuses/research-agent-workspace
git diff --check
```

Before execution，reconfirm the two RAG exclusions are still construction-bearing and unrelated; if they became cheap/non-mutating，use the repository's current appropriate suite，record why。`tauri build --no-bundle` already invokes frontend typecheck/build through package scripts，so do not add a duplicate `npm run build`。

On broad failure，do not immediately rerun。Isolate with the smallest owning-phase selector，form one new causal hypothesis，record attempt，repair only if directly withinGOALS。Unrelated failure is reported separately。

## Delivery Audit

- Map every GOALS success checkbox to build-log evidence/command/journey step。
- Search for forbidden residue：normal `loadMcp:false` caller、normal request absolute deadline、Task mode/general persistent `/skill` controls、current `answer.chunk`/`post_finalized` contract或producer/consumer、Tool/Result concatenation into user role。
- Confirm Citation `/citation` remains reserved/static，`issue/08-citation-skill-flow-deferred.md` remains open/deferred，and no GUI replacement is claimed。
- Confirm Fusion/Extended code/acceptance and the then-existing `issue/07-gui-first-turn-durability-deferred.md` deferral were not expanded。
- Inspect `git diff --stat`、`git diff --name-status`、`git diff` and manifests/lockfiles；every changed file maps to an owning phase，no dependency/real data/generated output。
- Confirm temporary root processes stopped，then validate exact owned path and remove only that root；record cleanup/absence。
- If local commits were authorized，verify each phase commit scope/hash。Do not push。

## Acceptance Criteria

- Integrated journey demonstrates all five required outcomes on current code，including no-answer-before-final result、`final_only`/zero-chunk delivery and no-old-tool-replay counts。
- Visual/keyboard observations cover changed Skill/final-only/tool-history surfaces，with limitations honestly recorded。
- One broader Python suite、npm suite、Cargo suite、Tauri no-bundle build and `git diff --check` pass，or any nonpass remainsexplicit and prevents incorrect Complete status。
- No dependency/lockfile、provider/MCP/Ollama/credential/real store、Fusion/Extended/Citation redesign、first-turn durability或multi-GUI change。
- Every changed file/evidence maps to a phase，temporary resources are cleaned，remote remains untouched。
- All phase rows and overall plan are markedComplete only after evidence exists。

## Handoff Evidence

Append a final `build-log.md` entry containing：

- Runtime/Git/authorization and temporary root boundary。
- Exact integrated event timeline，MCP boolean，Skill invocation/cleanup state，absence of answer events before the complete `final_only` result，tool invocation counts before/after restart/new turn。
- Transcript role/prompt capture and visual/keyboard observations。
- Exact broader command results/durations，failed/skipped/unavailable items。
- Final changed-file/manifest/lockfile/deferred-scope audit，temporary cleanup。
- Local commit hashes or explicit no-commit disposition；remote push not performed。
- Overall Complete or remaining Blocked reasons。
