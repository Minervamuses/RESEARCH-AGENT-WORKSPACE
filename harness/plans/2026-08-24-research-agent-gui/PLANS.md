# Plan: Research Agent Linux Desktop GUI

## Plan Metadata（計劃中繼資料）

- **Plan ID:** `2026-08-24-research-agent-gui`
- **Plan root:** `harness/plans/2026-08-24-research-agent-gui/`
- **Plan depth:** Rolling-wave
- **Project shape:** Application
- **Overall risk:** High — 6/8
- **Current authorized phase:** None
- **Status:** Draft — planning only
- **Last updated:** 2026-08-24T00:22:53+08:00

## Risk Profile（風險輪廓）

| Dimension | Score (0–2) | Evidence and rationale |
|---|---:|---|
| Ambiguity | 1 | `GUI/00.md`–`18.md` 已詳細描述 scope 與 architecture，但與目前 HEAD 有已知漂移，且 DTO、shutdown、preview lifecycle、root-aware read UX 尚未決定。 |
| Coupling | 2 | 工作跨 React/TypeScript、Tauri/Rust、Python process lifecycle、LangGraph session、RAG、citation、extensions、MCP、persistent state 與 multiple tool policies。 |
| Verifiability | 1 | 現有 Python tests 與 fake/temp fixtures 良好，可建立 contract tests；但 WSLg UI、a11y、process lifecycle 與 external-service behavior 仍需 manual/integration evidence。 |
| Blast radius | 2 | GUI 涵蓋 bash approval、prune、extension apply、secret redaction、shutdown flush 與 persistent data；錯誤可能造成任意 command、資料刪除或不實安全宣稱。 |

風險結果要求：Phase 00 先重新 characterization；後續採 rolling-wave；每個 phase 都有 exact approval gate、Rollback/Recovery、Compatibility/Security coverage 與獨立 evaluator；最終以 `GOALS.md` 和實際 user-visible behavior 做 integration audit。

## Confirmed Repository Facts（已確認 repository 事實）

- Repository root 是 `/home/minervamuses/research-agent-workspace`；唯一 Python/Poetry project 是 `app/`，唯一支援 runtime 是 Linux，Conda `app` 管 Python/Node/Poetry。
- `GUI/00.md`–`GUI/18.md` 共 19 份、2,358 行，是 2026-08-21 的 planning-only full draft；Git state 顯示整個 `GUI/` 未追蹤，且沒有 completion/evidence log。
- 目前沒有 `app/desktop/`、`app/agent/desktop/`、`package.json`、`Cargo.toml`、Tauri config 或 frontend source；GUI 尚未實作。
- Repository 沒有既有 `GOALS.md`、`PLANS.md`、`PROMPTS.md`、planning harness 或 CI workflow；`app/plan_logs/` 是 generated runtime transcript，不是本計劃 convention。
- `ChatSession.create()`、`turn_outcome()`、`status_snapshot()`、plan/thinking/skill methods 與 `flush_recent_turns()` 是目前最接近 GUI 的 application seams；CLI `agent.cli.chat._run()` 混合 terminal input、slash commands 和 human-readable output。
- `TurnOutcome` 目前只有 `text`、`validation_errors`、`tool_calls`；tool call trace 含 args，`status_snapshot()` 是 loose CLI dict，startup diagnostics 是 strings。它們不可直接跨 wire。
- Graph progress callback 是同步的 `(node_name, new_messages)` update callback；目前有 node/tool update，沒有 token stream；raw messages 可能含 tool args/results。
- `rag` 公開 read surface 是 `search`、`explore`、`list_chunks`、`get_context`；`list_chunks` 仍讀完整 `raw.json`，`Hit.score` 目前為 `None`。
- `agent.ingest` 已包裝 init/file/folder/diff/prune mutation；`ingest_repo` 仍會 `print()` 到 stdout，尚無 desktop-safe progress callback。
- 2026-08-23 的 current RAG code 已保存 `source_namespace` 與 `source_root`；sync/prune 依 canonical root namespace 隔離，`tests/rag/test_root_identity.py` 證明相同相對路徑的不同 roots 不互相刪除。Prior `GUI/12.md` 的「schema 無法區分 roots」已過時。
- Current plan log header 不再包含 `do_not_index: true`，single-file ingest 也不再檢查該 sentinel；`plan_logs/` 由 skip-directory policy 排除。Prior `GUI/12.md`/`17.md` 的相關 checks 已過時。
- 唯讀 current inventory 是 73 個 `test_*.py` files 與 617 個 literal test function definitions；`694 passed, 1 warning` 是 2026-08-20 的 checked-in歷史證據，之後已有多個 commits，本輪未重跑完整 suite。
- 2026-08-24 observed runtime：WSLg `DISPLAY=:0`、`WAYLAND_DISPLAY=wayland-0`；Conda `app` 可執行 Python 3.13.14、Node 24.18.0、npm 11.16.0、Poetry 2.x。一般非互動 `bash -lc` 找不到 `conda`，`rg` 解析到無法在 WSL 執行的 Windows binary；Rust/Cargo 與必要 Tauri dev packages 尚未就緒。
- Bash tool 在 non-TTY process 會 default-deny，且既有 tests 鎖定此行為；GUI approval bridge 是需要另行批准的 production behavior change。
- `ExtensionManager.status/preview/apply` 已有 authoritative recheck 與 exact binding hash；apply 後新 revision 需新 session 才載入。
- `ChatSession` 目前沒有通用 `close/aclose`；只確認 recent-turn flush。Provider/MCP resource shutdown ownership 是 open assumption。
- Root `.gitignore` 的 `build/` rule 會忽略 `harness/plans/2026-08-24-research-agent-gui/build/phase-00-refresh-gui-assumptions.md`；使用者已批准本輪不改 config/Git state。
- Worktree 在 plan authoring 前只有既有 `?? GUI/`；所有 user files 必須保留。

## Prior Plan Disposition（舊計劃處置）

- 本 bundle 成為後續 GUI planning 的唯一 active source of truth。
- `GUI/00.md`–`GUI/18.md` 保留原樣作 provenance 與需求來源，不代表 phase authorization、observed result 或 current repository fact。
- 下表把 prior steps 完整映射到 rolling-wave roadmap；未列為 phase detail 的內容仍須在 owner phase evidence refresh 時重新檢查，不能默默丟失。

| Prior source | New owner phase |
|---|---|
| `GUI/00.md`–`01.md` | Phase 00 — current scope、UX contract、architecture assumptions |
| `GUI/02.md`–`03.md` | Phase 01 — dependency gate、Linux shell/scaffold spike |
| `GUI/04.md`–`05.md` | Phase 02 — protocol、DTO、Python desktop service |
| `GUI/06.md`–`07.md`、`14.md` lifecycle部分 | Phase 03 — Rust supervisor、readiness、diagnostics、shutdown/recovery |
| `GUI/08.md`、`10.md` | Phase 04 — Chat、modes、skills、citation |
| `GUI/09.md` | Phase 05 — safe progress、conditional bash approval |
| `GUI/11.md` | Phase 06 — read-only Knowledge browser |
| `GUI/12.md` | Phase 07 — ingest/sync/prune mutation |
| `GUI/13.md` | Phase 08 — extension/MCP management |
| `GUI/14.md`–`16.md` | Phase 09 — error/security/privacy/a11y/automated verification |
| `GUI/17.md`–`18.md` | Phase 10 — representative acceptance、Linux handoff |

## Load-Bearing Assumption Ledger（承重假設帳本）

| ID | Claim | Type | Current evidence | Confidence | Risk if wrong | Falsification method | Owner phase | Status |
|---|---|---|---|---|---|---|---|---|
| `A-001` | Tauri/Rust supervisor + NDJSON 能在 WSLg 正確啟動並繼承 Conda `app` Python。 | Architecture / operations | WSLg 與 Conda Node 可用；Rust/Tauri 尚未安裝或 build。 | Uncertain | 必須更換 process/desktop architecture 或 delivery。 | Dependency review 後做最小 window + fake child handshake/shutdown spike。 | Phase 01 | Open |
| `A-002` | Desktop DTO 可從 current domain seams 組合，不需解析 CLI 或暴露 internal/raw objects。 | Architecture / security | `ChatSession`/RAG/Extension APIs 存在；`TurnOutcome`、status、diagnostics 不足且含敏感 raw shape。 | Likely | 需要小幅 application interface change，可能改 phase scope。 | 建立 seam map、redaction contract、shared fixtures，讓 Python/Rust/TS 各自拒絕 unsafe fields。 | Phase 00 / 02 | Open |
| `A-003` | `flush_recent_turns()` 足以作 shutdown 核心，其他 provider/MCP lifecycle 可在 adapter/supervisor 層安全處理。 | Operations / behavior | 只有 flush 是 confirmed；沒有 session close API。 | Uncertain | Child/resource 泄漏或 UI 誤報安全關閉。 | 查明 loaded resources owners，fake crash/EOF/flush failure characterization；若需要，另提最小 lifecycle interface。 | Phase 00 / 03 | Open |
| `A-004` | 不新增 root inventory/filter schema 仍可完成 V1 Knowledge UX。 | Data / behavior | Mutation 已 root-scoped；read DTO 無穩定 root filter，overview/search 可能跨 roots。 | Uncertain | 使用者無法理解 read result 對應的 root。 | 以 two-root temp store走 user journey；若無法明確呈現，replan before Phase 06。 | Phase 00 / 06 | Open |
| `A-005` | Bash bridge 延後時，visible auto-deny fallback 仍可完成必要 V1 journeys。 | Behavior / security | Existing non-TTY deny；prior plan把 bash列 conditional。 | Likely | 一些 agent tasks 在 GUI 無法完成。 | 列出 acceptance journeys 是否真正依賴 bash，讓 owner決定 Phase 05 是否必需。 | Phase 00 | Open |
| `A-006` | Ubuntu 24.04 WSL 的 Tauri/system/npm/Cargo prerequisites 可接受且可重現。 | Operations / cost | Rust/Cargo/dev packages 尚缺；依賴尚未批准。 | Uncertain | 工具鏈成本或相容性使 stack 不適合本專案。 | Current official prerequisite review、dependency ledger、minimal WSLg build。 | Phase 01 | Open |
| `A-007` | 可建立 typed、secret-free diagnostics，不解析 diagnostic strings。 | Architecture / security | Runtime facts可直接取；MCP/startup diagnostics目前部分為 strings。 | Likely | Diagnostics UI 會脆弱或洩漏未信任文字。 | 定義 field provenance/allowlist，fixtures檢查 secret和unknown diagnostic。 | Phase 00 / 02 | Open |
| `A-008` | Opaque extension/prune preview 只需 bounded in-memory cache，不需 persistent queue/database。 | Architecture / operations | Single-user、single backend、existing immutable preview objects；TTL/capacity 尚未定。 | Likely | stale/replay 或 unbounded memory。 | 明確定義 max entries、expiry/consume/restart semantics並做 replay tests。 | Phase 02 / 07 / 08 | Open |
| `A-009` | Existing CLI/public Python compatibility 可在不建立 parallel domain implementation下保留。 | Compatibility | GUI plan重用 domain APIs，existing focused tests良好。 | Likely | GUI patch破壞本機 CLI/research workflows。 | Phase-local focused baseline + final existing suite once near completion。 | Every implementation phase | Open |
| `A-010` | Source-run Linux/WSLg delivery足以完成本目標，不需 bundled Python 或 Windows executable。 | Operations / scope | Explicit user decision與 prior non-goals。 | Confirmed | Delivery scope會大幅擴張。 | 只有新的明確 user decision可推翻。 | Goal change control | Validated |
| `A-011` | Skill-required ignored phase contract可在本機長期工作流中暫時接受。 | Operations / planning | `git check-ignore` 已確認；使用者批准不改 `.gitignore`。 | Confirmed with limitation | 新 clone/一般 Git tracking不會自然帶到此檔。 | 另行 Git/config task或明確 forced tracking；本 bundle handoff需一直揭露。 | Outside current skill | Validated |

## Execution Principles（執行原則）

- 一次只執行一個已批准的 phase；後一 phase 不因前一 phase完成而自動開始。
- Current repository、`AGENTS.md`、`GOALS.md` 與 observed behavior優先於 prior `GUI/` prose。
- 每個 implementation phase先建立 red/characterization baseline，再做最小變更；failed required check先處理或停止。
- Persistent/data mutation預設使用 temporary roots；mutating transport failure不自動 replay。
- Python 保持 domain/persistence authority；Rust是 process/IPC trust boundary；React只負責 presentation和interaction state。
- Material discovery寫入 phase context，observed result寫入 `build-log.md`，independent findings寫入 `code_review/`。
- Dependency、schema/public API、超過三個 production files、external/credentialed/destructive action和Git mutation都有各自 approval gate。
- Later phase detail是 provisional；開始前必須依 fresh evidence重寫成自己的 detailed contract。

## Phase Roadmap（階段路線圖）

| Phase | Outcome | Depends on | Status | Approval gate | Verification surface |
|---|---|---|---|---|---|
| Phase 00 — Refresh GUI assumptions | Prior plan與current HEAD的差異被裁決；UX/architecture/DTO/lifecycle/root/bash decisions與Phase 01入口被凍結。 | None | Not started | User approves read-only characterization write set與focused baseline budget。 | Repository/runtime evidence、targeted existing tests、fresh adversarial review。 |
| Phase 01 — Prove Linux desktop shell | 經批准的工具鏈可在WSLg開窗，並完成fake child runtime identity/handshake/shutdown spike。 | Phase 00 | Not started | Separate apt/Rust/npm/Cargo/lockfile與exact scaffold write-set approval。 | Vite build、Rust tests、manual WSLg window、process cleanup。 |
| Phase 02 — Freeze protocol and Python service | Versioned safe DTO/NDJSON contract與Python desktop application service在fake dependencies下可驗證。 | Phase 01 | Not started | Exact `agent.desktop` files、shared fixtures及任何 public-interface change approval。 | Python unit/subprocess contract、stdout purity、redaction、busy/replay tests。 |
| Phase 03 — Own backend lifecycle | Rust supervisor可管理single backend、ordered channel、diagnostics、graceful shutdown、crash/restart。 | Phase 02 | Not started | Exact Rust/TS write set與任何 lifecycle interface change approval。 | Fake child Rust tests、pending cleanup、flush/crash manual integration。 |
| Phase 04 — Complete core Chat UX | Single live transcript、safe Markdown、modes/thinking/skills/citation與truthful busy/error states可用。 | Phase 03 | Not started | Exact frontend/component write set與Markdown/test dependencies approval。 | Reducer/component tests、existing session/citation checks、representative fake/live turn。 |
| Phase 05 — Add progress and decide bash bridge | Safe progress events可觀察；bash要嘛通過exact default-deny bridge，要嘛明確保持 unavailable。 | Phase 04 | Not started | Separate cross-layer production write set及bash behavior approval。 | Policy/non-TTY regressions、approve/deny/timeout/late/crash tests。 |
| Phase 06 — Add read-only Knowledge | Overview/search/chunks/context在current root semantics與service degradation下正確呈現。 | Phase 03 | Not started | Exact adapter/UI files；若需 root-aware API，另行 schema/interface approval。 | Existing RAG read tests、two-root temp read UX、Ollama degradation。 |
| Phase 07 — Add Knowledge mutations | Ingest/sync/prune具structured progress、single mutation lock、preview freshness與temp-store recovery。 | Phase 06 | Not started | RAG callback signature、production files、dialog capability與destructive flow approval。 | Temp component/root-identity/partial-write tests、stale prune、manual dialog flow。 |
| Phase 08 — Add Extensions management | Status/preview/binding approval/apply/restart完整重用host validation。 | Phase 03 | Not started | Exact files、model-call budget和temp/live extension boundary approval。 | Existing extension journey、safe DTO、replay/revision/restart integration。 |
| Phase 09 — Harden and verify integration | Error taxonomy、Security/Privacy、Accessibility、contract matrix與cross-feature busy policy通過。 | Phases 04–08 | Not started | Exact hardening/test write set；任何新增 test dependency approval。 | Python/Rust/TS focused suites、CSP/capability/XSS/redaction、keyboard/a11y spot checks。 |
| Phase 10 — Accept and hand off Linux V1 | 所有 `GOALS.md` criteria有representative observed evidence，source-run/build instructions可重現。 | Phase 09 | Not started | Live provider/bash/full-suite/real-data items逐項批准。 | Final integration audit、WSLg real-case matrix、shutdown/process audit、delivery commands。 |

## Phase Outlines（階段摘要）

### Phase 00 — Refresh GUI Assumptions and Freeze the Executable Contract

- **Purpose:** 將2026-08-21 full draft轉成與current HEAD一致的可執行決策與baseline，先解決最可能造成 cascade rework 的 assumptions。
- **Key assumptions/risks:** `A-002`、`A-003`、`A-004`、`A-005`、`A-007`；同時記錄 `A-001`/`A-006` 必須由 Phase 01 spike驗證。
- **Exit condition:** 所有已知 stale claims有source-backed disposition；UX/architecture/interface decision表獲使用者接受；focused baseline與independent review被記錄；Phase 01 exact contract尚未開始，等待新批准。
- **Detailed contract:** `build/phase-00-refresh-gui-assumptions.md`

### Phase 01 — Prove Linux Desktop Shell

- **Purpose:** 先證明 WSLg、Tauri、Rust、Conda child process與最小權限組合可行，再投入domain integration。
- **Dependencies:** Phase 00 decisions和separate dependency approval。
- **Exit condition:** Minimal shell/fake child spike的build、window、runtime identity、graceful cleanup有observed evidence。
- **Contract status:** Create after Phase 00 closeout; not authorized.

### Phase 02 — Freeze Protocol and Python Service

- **Purpose:** 建立唯一的safe desktop contract和Python application adapter。
- **Dependencies:** Phase 01 stack/runtime evidence。
- **Exit condition:** Shared fixtures、Python service和subprocess contract可辨別version、ordering、busy、redaction、shutdown failures。
- **Contract status:** Create later after fresh evidence; not authorized.

### Phase 03 — Own Backend Lifecycle

- **Purpose:** 讓Rust正確擁有child、pending requests、ordered events、crash/restart與close flow。
- **Dependencies:** Phase 02 protocol。
- **Exit condition:** Fake child及representative Python bridge證明沒有orphan process、永久pending或假的resume/cancel。
- **Contract status:** Create later after fresh evidence; not authorized.

### Phase 04 — Complete Core Chat UX

- **Purpose:** 忠實呈現single live session與existing mode/skill/citation semantics。
- **Dependencies:** Phase 03 lifecycle；Phase 02 DTO。
- **Exit condition:** Representative Chat journey與server-enforced state通過，unsafe Markdown/raw tool data不進UI。
- **Contract status:** Create later after fresh evidence; not authorized.

### Phase 05 — Add Progress and Decide Bash Bridge

- **Purpose:** 提供safe progress，並以明確decision落實conditional bash scope。
- **Dependencies:** Phase 04 Chat flow。
- **Exit condition:** Progress truthfully correlated；bash bridge若存在則逐call default-deny，否則UI明確unavailable。
- **Contract status:** Create later after fresh evidence; not authorized.

### Phase 06 — Add Read-Only Knowledge

- **Purpose:** 先以non-mutating flow驗證RAG DTO、two-root semantics和service degradation。
- **Dependencies:** Phase 03 lifecycle；Phase 02 service。
- **Exit condition:** Overview/search/documents/context representative cases與root wording正確。
- **Contract status:** Create later after fresh evidence; not authorized.

### Phase 07 — Add Knowledge Mutations

- **Purpose:** 加入安全path validation、progress、serialization、sync/prune preview/revalidation與recovery。
- **Dependencies:** Phase 06 read flow。
- **Exit condition:** Temporary-store ingest/sync/prune有actual persistent evidence，failure不污染NDJSON或真實store。
- **Contract status:** Create later after fresh evidence; not authorized.

### Phase 08 — Add Extensions Management

- **Purpose:** 將現有host-authoritative extension journey暴露為safe GUI。
- **Dependencies:** Phase 03 lifecycle；Phase 02 DTO。
- **Exit condition:** Temp roots完成status/preview/approval/apply/restart，且blocked/stale/replayed input fail closed。
- **Contract status:** Create later after fresh evidence; not authorized.

### Phase 09 — Harden and Verify Integration

- **Purpose:** 統一cross-feature error/recovery、安全、隱私、accessibility和automated contract coverage。
- **Dependencies:** Phases 04–08 feature evidence。
- **Exit condition:** 必要targeted suites/build、安全與keyboard/manual checks通過或限制被接受。
- **Contract status:** Create later after fresh evidence; not authorized.

### Phase 10 — Accept and Hand Off Linux V1

- **Purpose:** 對live system而非builder narrative驗收 `GOALS.md`，再交付實測source-run流程。
- **Dependencies:** Phase 09 integration-ready state。
- **Exit condition:** Final independent audit支持complete/accepted limitations，所有written paths、live calls、skipped checks和known limitations已記錄。
- **Contract status:** Create later after fresh evidence; not authorized.

## Parallelism and Ownership Boundaries（平行與 ownership）

- Phase 00 的repository seam inspection、runtime evidence和fresh adversarial review可由不同read-only evaluator平行進行；decision consolidation與canonical artifact update必須序列化。
- Phase 01–03是architecture critical path，必須依序完成；protocol未凍結前不可平行建立三套不同DTO。
- Phase 04完成shared lifecycle/state contract後，Phase 06 read-only Knowledge與Phase 08 Extensions可在不同exact write sets內提議平行，但integration、busy policy與shared frontend state仍需single owner merge gate。
- Phase 05 bash approval與Phase 07 mutations涉及security/data risk，不能因其他UI work完成而跳過自己的approval/independent review。
- Python domain/persistence files、Rust supervisor、TypeScript protocol types各自只由當前approved phase owner修改；shared fixture變更需三層consumer一起review。
- Builder與independent evaluator必須分開；evaluator先讀 `GOALS.md`、live repo/system和contract，再讀builder narrative。

## Approval Gates（批准閘門）

1. 本 planning bundle通過validator，不代表 Phase 00 或任何implementation已獲授權。
2. 每個 detailed phase contract都要先重新對照current repository、列出exact write set、planned checks、Rollback/Recovery和unavailable evidence，再取得使用者批准。
3. apt、Rust、npm、Cargo、Python dependency或lockfile變更必須先列purpose、alternatives、disk/time/runtime/maintenance cost。
4. Public API、DTO schema、protocol、persistent format、migration或root-aware read surface變更需要單獨批准。
5. 超過三個 production files、Bash approval provider、RAG progress callback和任何新的persistent module都要說明較小方案不足處並取得批准。
6. Live OpenRouter/citation/Ollama/MCP calls、真實bash、真實store/citation/extension mutation、full suite超過十分鐘、full replay/sweep都逐項批准。
7. Destructive、credentialed、external、deployment、branch、worktree、commit、push或release行為不得由phase approval默認包含。
8. Scope超過contract時立即停止；不可用「順便整理」擴張phase。

## Rollback and Recovery Policy（回滾與復原）

- 每個phase以開始前的observed repository state作last known-good；不建立未批准branch/commit作隱性rollback機制。
- Application phase失敗時只回退該phase新增/修改的exact files；保留failed evidence，append correction，不刪舊contract/log。
- Data-affecting checks預設使用temporary roots；若mutating check意外觸及真實state，立即停止、記錄exact path和observed effect，不自動wipe或重建。
- Ingest partial write以修正根因後重跑同root recovery；prune、extension apply和mutating protocol failure不自動retry/replay。
- Rust/backend crash recovery必須fail all pending requests、default-deny approvals、保留truthful UI state並由使用者觸發新session；不可宣稱resume。
- Load-bearing assumption被推翻、rollback不安全或required verifier不可用時，將phase設為Blocked或保持In progress，replan後再請批准。

## Replanning Policy（重新規劃政策）

以下任一情況發生時，先停止並更新remaining roadmap：

- `A-001`–`A-009` 任一被拒絕、contradicted或需要不同 owner phase。
- Tauri/Conda child spike失敗，或dependency/WSLg成本超過使用者接受範圍。
- Current domain interface無法產生safe DTO，必須改public API/persistent schema。
- Two-root Knowledge UX無法在不新增root-aware read surface下正確呈現。
- Shutdown、approval、prune、extension或mutation recovery被證明不安全。
- Required test/manual oracle unavailable、不可靠或可在實際UI錯誤時仍通過。
- Phase write set超過批准、兩份durable artifacts互相矛盾，或prior `GUI/` prose被誤當current evidence。
- Success criteria、non-goals、platform、Bash requirement或delivery target有新的user decision。

Superseded decision必須保留舊值、理由和replacement reference；不得為了讓roadmap看起來順利而重寫observed evidence。

## Overall Completion Criteria（整體完成條件）

- [ ] `GOALS.md` 每個 SC 和 INV 都有observed evidence或明確accepted limitation。
- [ ] 所有phases是 Complete 或有documented Superseded disposition；沒有因檔案存在就推定完成。
- [ ] Required focused、contract、build、manual WSLg、Compatibility、Security、Recovery與cleanup checks均有actual results。
- [ ] Independent Review findings已解決或由authorized owner明確接受。
- [ ] Final evaluator從live repository/system對照 `GOALS.md`，而非只讀builder report。
- [ ] Linux source-run可重現，backend/session readiness、normal turn、Knowledge、Extensions和shutdown representative cases通過。
- [ ] No secret/raw payload leak、orphan backend、policy bypass、unapproved destructive action或不實capability claim。
- [ ] Files changed、commands run、live calls、written paths、failed/skipped checks、known limitations與future non-goals完成handoff。
- [ ] 完成後停止；bundle/Windows/resume/cancel/multimodal等後續項目不自動開始。
