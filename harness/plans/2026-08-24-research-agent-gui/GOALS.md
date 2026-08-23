# Goal: Research Agent Linux Desktop GUI

- **Plan ID:** `2026-08-24-research-agent-gui`
- **Plan root:** `harness/plans/2026-08-24-research-agent-gui/`
- **Status:** Draft — planning only
- **Owner / decision maker:** Repository owner
- **Last updated:** 2026-08-24T00:22:53+08:00

## Objective（目標）

在 Ubuntu 24.04 WSL/WSLg 與既有 Conda `app` runtime 中，交付一個從 source checkout 啟動的本機 desktop GUI，讓單一使用者能透過真實的 Chat、Knowledge、Extensions 與 Diagnostics 流程操作現有 research agent；GUI 必須忠實呈現目前能力與限制，沿用 Python domain APIs 和 safety policy，並在正常關閉時提供可觀察的持久化結果。

## Observable Success Criteria（可觀察成功條件）

- [ ] **SC-001 — 啟動與診斷：** 從明確的 Linux/Conda 啟動命令開啟 Tauri 視窗；畫面可區分 desktop、Python backend、ChatSession 與外部服務 readiness，且 secret 只顯示 configured/not configured。
- [ ] **SC-002 — Chat：** 一個代表性 turn 經 `ChatSession.turn_outcome()` 完成，GUI 顯示 finalized safe Markdown、經過 allowlist 的 progress/tool summary、mode/thinking/skill/citation 狀態，以及失敗或 recovery notice；不暗示 token streaming、可靠 cancel 或 session resume。
- [ ] **SC-003 — Knowledge：** 以 temporary store 完成 overview、search、chunks/context、single-file/folder ingest、sync 與 prune preview/revalidation；UI 與 persistent result 一致，並保留目前多 ingest-root 的 namespace 隔離。
- [ ] **SC-004 — Extensions：** 以 temporary drop-in/state roots 完成 status → preview → exact MCP binding approval → apply → backend restart；未核准、stale 或 host-blocked binding 不會執行或顯示為已套用。
- [ ] **SC-005 — Bash policy：** 在該 phase 的獨立批准下，GUI bash bridge 必須通過 exact-command、default-deny、timeout、late-response 與 crash checks；若未獲批准，GUI 必須明確顯示 unavailable/auto-denied，並維持既有 non-TTY deny。
- [ ] **SC-006 — Shutdown 與 recovery：** idle close 可觀察到 recent-turn flush；flush failure、active work、backend crash 與 force quit 均呈現真實風險，不把 process termination 說成成功 cancellation。
- [ ] **SC-007 — Compatibility：** 既有 CLI、agent、RAG、citation、skill/tool policy 與 extension representative checks 保持相容；任何未跑、失敗或只由 proxy 支持的檢查都清楚記錄。
- [ ] **SC-008 — Delivery：** 文件提供已實測的 Linux/WSLg source-run 與 build 命令、dependency/runtime 邊界及已知限制；不承諾 standalone Python bundle、Windows executable 或未驗證能力。

## In Scope（範圍內）

- Tauri 2、React、TypeScript 與 Vite 的單一 Linux desktop window。
- Rust supervisor 管理一個長駐 Python child；Rust/Python 之間使用有版本、可 correlation、可排序的 NDJSON stdio protocol。
- Python application adapter 對 `ChatSession`、公開 RAG read APIs、`agent.ingest` wrappers 與 `ExtensionManager` 提供安全、穩定的 desktop DTO。
- Chat、Knowledge、Extensions、Diagnostics 四個主要區域與繁體中文 user-facing copy。
- 單一 active `ChatSession`、單飛 turn、server-side busy enforcement、safe progress、structured failures、graceful shutdown 與手動 restart。
- Mode、thinking、skill/task mode 與 citation controls，保留現有互斥、teardown 與 finalization policy。
- RAG read 與 host-controlled mutations；destructive operation 使用 backend preview token、fresh revalidation 和 actual result。
- Extension preview/apply/restart 與逐一 MCP binding approval。
- 必要的 Security、Privacy、Accessibility、contract tests、representative real-case validation 和 Linux source-run handoff。

## Non-Goals（明確非目標）

- Windows native、macOS、跨平台 mixed-runtime、portable Python sidecar、AppImage/deb 完整獨立發行、signing 或 auto updater。
- 多使用者、登入、雲端同步、遠端存取、telemetry、crash upload、HA 或 multi-tenant design。
- 多視窗、多 active sessions、完整 transcript database、歷史 session list 或 resume。
- Token streaming、可靠 turn/ingest cancellation、背景 queue 或新的 concurrency model。
- Attachment、PDF/DOCX/image ingestion、voice 或 multimodal workflow。
- GUI secret 編輯/保存、keyring、localStorage transcript 或新的 GUI database。
- 新增 root inventory/filter schema；v1 可讓使用者針對選定 root 操作，但不得破壞現有 multi-root identity。
- 在此 GUI 計劃中順便修復 issue 02、03、04，或重構 citation、RAG、extension 的鄰近技術債。
- Extension hot reload、local-tool plugin system、跨 process extension lock 或 startup 後 applied-skill integrity redesign。
- 將 `Hit.score=None`、不存在的 recovery metadata、cancel、resume 或 provider readiness 包裝成已具備的能力。

## Preserved Behavior and Invariants（必須保留的行為）

| ID | Behavior or invariant | Why it matters | Verification surface |
|---|---|---|---|
| `INV-001` | Linux 是唯一支援 runtime；Python/Poetry/Node 必須來自 Conda `app`，不得混用 Windows executable、system Python 或 `.venv`。 | 避免 WSL/Windows path、ABI 與 runtime 漂移。 | Runtime identity diagnostics；`agent.cli.runtime.require_conda_runtime`；phase runtime gate。 |
| `INV-002` | Chroma、`raw.json`、`folder_meta.json`、chat history、plan logs、citation bundles 與 extension registry 的所有 persistent writes 仍由 Python domain code 擁有。 | 防止第二個 truth source 和跨語言資料損壞。 | DTO/command review；temp-store integration tests；WebView capability audit。 |
| `INV-003` | `rag` 保持 framework-neutral，不反向 import `agent`、Tauri 或 desktop UI。 | 保留既有 package boundary 與 direct RAG use。 | Import/static review；existing RAG tests。 |
| `INV-004` | GUI 不解析 CLI output、slash-command display text、TTY prompt 或 raw stderr 作為 protocol。 | CLI 是 terminal adapter，不是穩定 API。 | Import/search checks；protocol fixtures；subprocess contract tests。 |
| `INV-005` | Final answer、citation gate/render、skill/tool access 與 `PolicyToolNode` 仍由 Python authoritative path enforcement。 | 防止 UI 繞過安全與語意 policy。 | Existing citation/tool-policy tests；representative Chat flow。 |
| `INV-006` | Raw secret、traceback、tool args/results、provider payload 與 arbitrary MCP stderr 預設不跨 wire 或顯示。 | 保護本機隱私並縮小 WebView trust boundary。 | Redaction/XSS fixtures；DTO snapshots；manual inspection。 |
| `INV-007` | UI 只呈現已存在或已觀察的能力；目前沒有 token stream、可靠 cancel、resume 或可信 search score。 | 防止 user-visible promise 與 backend reality 不一致。 | UX contract review；real-case acceptance。 |
| `INV-008` | Extension authoritative operation、revision/hash recheck 與 exact MCP binding approval 不能由 frontend override。 | 防止未核准 extension execution。 | Existing extension journey + desktop contract tests。 |
| `INV-009` | Repo ingest 的 `source_namespace`/`source_root` isolation 與 root-scoped sync/prune 不退化。 | 目前 store 已能安全區分相同相對路徑的不同 roots。 | `tests/rag/test_root_identity.py`；temp-root GUI flow。 |
| `INV-010` | 預設驗證不讀寫使用者 `app/store/`、`cite/`、`app/plan_logs/` 或真實 extension state。 | 防止 planning/validation 損壞本機研究資料。 | Temp-path setup；written-path audit；build log。 |

## Constraints（限制）

### Technical（技術）

- 專案仍是單一 `app/` Python/Poetry distribution；desktop adapter 屬於 `agent` application layer。
- V1 stack 以 Tauri 2 + React + TypeScript + Vite、Rust supervisor、versioned NDJSON 與 long-lived Python process 為目前批准的 planning baseline；實作依賴仍需各自批准與 lockfile review。
- 不增加 FastAPI/WebSocket、port、GUI database、shell plugin 或廣泛 filesystem/HTTP capability。
- Phase contracts 必須凍結 exact write set；新增 production dependency、超過三個 production files、schema/public API、persistent format、branch/commit/push 仍各自需要明確批准。
- Repository 目前的 `.gitignore` 會忽略 bundle 的 `build/phase-*.md`。本輪按使用者決定保留 `.gitignore` 不變；若要追蹤該檔，需另行處理 Git/configuration。

### Compatibility and Data（相容性與資料）

- 不移除 CLI 或既有 public Python entry points；不得為 GUI 讓既有 non-TTY bash deny、citation finalization 或 tool policy 變寬。
- 不改現有 store、citation 或 extension persistent schema，除非後續證據顯示 GUI 目標無法在不改 schema 下完成，且使用者另行批准 migration/rollback contract。
- Mutating transport failure 不自動 replay；partial ingest 的預設 recovery 是修正原因後重跑相同 root，不自動 wipe store。
- Fresh repository evidence 優先於 2026-08-21 的 `GUI/` 敘述；過時內容必須顯式 supersede。

### Security, Privacy, and Operations（安全、隱私與操作）

- WebView 只載 local assets；raw HTML 關閉，URL scheme allowlist，無任意 shell/fs/API。
- Bash、prune、extension apply、force quit、live paid-provider call 和 real-store mutation 必須有相應 approval gate。
- 所有預設測試使用 fake providers、temporary stores、temporary citation/extension roots，且不含 real keys/user data。
- App 不新增 remote telemetry、analytics 或 crash upload。

### Validation Budget（驗證預算）

- **Allowed:** 唯讀 repository inspection、現有小型 focused tests、fake providers、temporary directories、protocol fixtures、targeted Python/Rust/TypeScript tests、一次必要的 local build，以及經批准後的 WSLg manual smoke。
- **Ask before:** apt/Rust/npm/Cargo dependency mutation、lockfile變更、完整 suite 預估超過十分鐘、live OpenRouter/citation/Ollama/MCP call、真實 bash、真實 store/citation/extension mutation、full-dataset replay、deployment、branch/commit/push。
- **Unavailable at plan authoring:** Rust/Cargo 與 Tauri Linux dev packages、implemented desktop shell、CI、live external/provider acceptance。2026-08-20 的 `694 passed` 是歷史紀錄，不是目前 HEAD 的驗證結果。

## Authoritative Inputs（權威輸入）

- `AGENTS.md` 與本 repository 的 Linux/Conda、scope、approval、testing 和 completion 規則。
- `GUI/00.md`–`GUI/18.md` 作為 2026-08-21 的完整 prior-plan provenance；它們不是 observed progress 或可直接執行的 contract。
- 目前 HEAD 的 `README.md`、`app/README.md`、`app/pyproject.toml`、`app/env/env-app.yml`、`app/agent/`、`app/rag/`、`app/tests/` 與 `issue/`。
- 2026-08-24 唯讀 discovery：WSL/Conda toolchain、current test inventory、GUI absence、Git status/ignore behavior 及 RAG root-identity changes。
- 使用者於 2026-08-24 回覆「依建議建立」所批准的 plan ID、destination、rolling-wave depth、scope defaults 與 frozen five-file write set。

## User Decisions（使用者決策）

| Decision | Choice | Rationale / provenance | Date |
|---|---|---|---|
| Operating mode | New plan；保留 `GUI/` 作 provenance，不覆寫或搬動。 | 使用者批准 proposed write set。 | 2026-08-24 |
| Plan packaging | `2026-08-24-research-agent-gui`，繁體中文 + validator 所需英文 heading，high-risk rolling-wave。 | 使用者批准建議設定。 | 2026-08-24 |
| V1 architecture baseline | Linux/WSLg；Tauri 2 + React/TypeScript + Rust supervisor + NDJSON + Python domain adapter。 | 延續 `GUI/00.md`，使用者批准作 planning baseline。 | 2026-08-24 |
| Data ownership | Python 保持所有 persistent state 的唯一 writer；v1 不新增 GUI database/schema。 | Existing architecture invariant + approved default。 | 2026-08-24 |
| Multi-root boundary | 保留 current namespace isolation；v1 不新增 root inventory/filter schema。 | Current HEAD 已推翻 prior plan 的「schema 無法分 root」理由。 | 2026-08-24 |
| Bash | Conditional phase；未另行批准 bridge 時維持 non-TTY auto-deny 並清楚標示 unavailable。 | 安全 fallback，避免 PTY parser。 | 2026-08-24 |
| Ignored phase contract | 建立 skill-required `build/phase-00-*.md`，但不在本輪改 `.gitignore` 或 Git state。 | 使用者接受建議處理。 | 2026-08-24 |

## Unknowns and Load-Bearing Assumptions（未知與承重假設）

| ID | Claim | Evidence | Risk if wrong | How to falsify | Status |
|---|---|---|---|---|---|
| `A-001` | Tauri/Rust child supervisor + NDJSON 可在 WSLg 中可靠繼承正確 Conda `app` Python。 | WSLg/Conda/Node 可用；Rust/Tauri 尚未安裝或試跑。 | 基礎架構與 delivery flow 必須重規劃。 | Phase 01 最小 shell/process spike，先驗證 runtime identity、handshake、shutdown。 | Open |
| `A-002` | Desktop DTO 可由現有 domain seams 安全組合，不需把 CLI 或 internal objects 當 wire contract。 | `ChatSession`、RAG APIs、`ExtensionManager` 存在；`TurnOutcome`/status fields 尚不足。 | 可能需要小幅 public/application interface change。 | Phase 00 seam map + Phase 02 contract test，明確決定 DTO owner。 | Open |
| `A-003` | Graceful shutdown 可在 `flush_recent_turns()` 基礎上建立，不需未存在的通用 provider/MCP close API。 | 目前只確認 flush；沒有 `ChatSession.close/aclose`。 | Child/resource lifecycle 可能洩漏或誤報 safe shutdown。 | Phase 00 查明 resource owners；Phase 03 fake/real lifecycle characterization。 | Open |
| `A-004` | 不新增 root-aware inventory/filter API 仍可完成 V1 Knowledge journey。 | Sync/prune 已 root-scoped；read DTO 不暴露穩定 root filter。 | UI 可能混合不同 roots 的 overview/search 結果。 | Phase 00 定義 representative store/UX，判斷是否需要 scope change。 | Open |
| `A-005` | Conditional bash fallback 能滿足第一版，即使 approval bridge 延後。 | Existing non-TTY auto-deny 有測試；使用者批准 conditional scope。 | 某些 agent journeys 在 GUI 可能無法完成。 | Phase 00 列出必需 bash 的 representative journeys，由使用者決定 gate。 | Open |
| `A-006` | 必要 Tauri/system/npm/Cargo dependencies 可在 Ubuntu 24.04 WSL 以可接受成本安裝與鎖定。 | Node 24 可由 Conda 使用；Rust/Cargo/dev packages 尚缺。 | GUI stack 不可重現或維護成本超出此本機專案。 | Phase 01 dependency review + minimal WSLg build。 | Open |
| `A-007` | Stable diagnostics 可由 typed adapter 產生，而不解析目前的 diagnostic strings 或洩漏 secrets。 | `status_snapshot()` 是 loose CLI dict；startup diagnostics 是 strings。 | Diagnostics UI 可能脆弱或錯誤宣稱 readiness。 | Phase 00/02 定義 typed diagnostic source與 redaction fixtures。 | Open |

## Change Control（變更控制）

更改 Objective、Success Criteria、Non-Goals、Preserved Invariants、V1 platform、persistent data ownership 或 conditional bash boundary，必須由使用者明確決定，並同步重新審查 `PLANS.md` 的 risk、phase order、verification、rollback 與 recovery。Implementation discovery 不得默默重定義 goal；prior `GUI/` 文件與本 bundle 衝突時，以目前 repository evidence、`AGENTS.md` 與已記錄使用者決策為準。
