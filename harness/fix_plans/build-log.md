# Research Agent Desktop GUI 修復 — Build Log

## Phase Summary / 階段摘要（Mutable Status Authority）

本檔是唯一 mutable execution status。Phase files 的 `Initial status` 只描述 authoring 起點；後續 agent 必須以本表與 dependency graph 選工作。

| Phase | Status | Attempts against current cause | Last checkpoint | Evidence / 證據 | Commit |
| --- | --- | ---: | --- | --- | --- |
| 01 — MCP defaults | Not started | 0 | None | None | None |
| 02 — Long-request liveness | Not started | 0 | None | None | None |
| 03 — One-shot Skill runtime | Not started | 0 | None | None | None |
| 04 — Desktop Skill command | Not started | 0 | None | None | None |
| 05 — Normal live streaming | Not started | 0 | None | None | None |
| 06 — Tool-aware conversation restore | Not started | 0 | None | None | None |
| 07 — Integration acceptance | Not started | 0 | None | None | None |

## Current Checkpoint

- Plan bundle authoring only；application implementation 尚未開始。
- Next eligible phase 依 numeric order 是 Phase 01；Phases 02 與 03 也沒有 dependencies，但 executor 仍依 [`PLANS.md`](PLANS.md) selection algorithm 每次只選一個。
- Blockers: none recorded。
- Implementation authorization: not active。只有使用者之後實際送出 [`PROMPTS.md`](PROMPTS.md) 的 Start/Resume prompt 或等價明確訊息才啟動。
- Local implementation commits: not authorized yet。
- Remote push: not authorized for future implementation。2026-08-31 對 plan-authoring current worktree 的 commit/push 指示不延伸到本計劃執行期。

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
