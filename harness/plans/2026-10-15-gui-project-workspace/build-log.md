# 計畫狀態與實際證據

這是唯一可變執行狀態來源。2026-10-15 本次只撰寫計畫，沒有功能實作、App 啟動、應用程式測試、build、provider 呼叫、migration 或 Git mutation。

## 目前階段

| 階段 | 狀態 | 實作證據 | 阻塞／前提 | 下一步 |
|---|---|---|---|---|
| P1 | Complete | E05-E15: implementation, focused tests and native checkpoint | none | P2 dependency is ready; broader acceptance continues in P4 |
| P2 | In progress | 無 | P1 | 依 D4/D5 進行 canonical 與協議調整 |
| P3 | Not started | 無 | P2 | 刪常駐區塊、重排與量測 |
| P4 | Not started | 無 | P1/P2/P3 | 執行 A21 與相關回歸 |

## 規劃證據

### E01：環境與目標核對

- 讀取使用者指定 long-horizon-plan-author 技能及其 templates/verification。
- 以 WSL Linux git 讀取 branch/status/remote/HEAD：GUI，HEAD 1cf54d7ed8a6769e8c9e155fa8bcb6243621c156，開始時工作樹乾淨，origin 指定 repository。
- 啟用 Conda app 後讀取 executable paths/version：Linux Git；Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0、cargo 1.97.1 均屬預期環境。
- 未 fetch；無遠端最新狀態保證。rg 未安裝，使用 git grep/grep，沒有安裝工具。

### E02：程式基線唯讀檢查

主作者檢查 shared contract、Python/TS/Rust 協議、DocumentWorkspace、service、canonical repository/session、launcher、現有測試與 fixture。兩個平行唯讀子代理分別核對 frontend 與 persistence，提供具體行號；已完成並停止。

確認 startup 全域 history 與文件根脫鉤、structured reference 缺失、歷史 retry context 缺失、archive read_file 根綁定、sidebar/layout 數值、可重用版本／Permission 檢查。摘要見 PLANS.md。未讀真實 history、秘密或使用者專案文件。

### E03：計畫產物與覆蓋

產出 GOALS、PLANS、contracts、四個 phase、PROMPTS、靜態索引與本 log（10 份內容檔），另有一份局部 .gitignore；範圍僅限本計畫目錄。12 個目標對應 4 個階段及 A01–A21 可觀察驗收。具體格式、chooser 與預設路徑標記為提案；未提供舊資料 mapping，接入舊資料時不得猜測。

### E04：交付前驗證

- 結構 lint：以 Conda app 的 Linux Python 執行下列唯讀命令，實際結果 ok=true、errors=[]、warnings=[]、checked_files=10。它只驗證檔案／連結／圖結構，不能證明 App 行為。
  `python /mnt/c/Users/garyc/.codex/skills/long-horizon-plan-author/scripts/validate_plan.py /home/minervamuses/research-agent-workspace/harness/plans/2026-10-15-gui-project-workspace --json`
- Fresh-context review：獨立 reviewer 只取得原需求、計畫位置與執行環境限制，讀完整計畫並查相關程式；另有唯讀專案契約交叉檢查。確認 fresh executor 第一動作與中斷恢復可行，提出一項具體 A21 順序缺口：同程序 retry 完成後已無原 failed turn 可供重開測試。
- 修正：A21 第 5／6 步已分成兩個不同 turnId；第一個驗證同程序 retry 至 completed，第二個保留 failed 供重開 retry；作者核對修正後流程。不把已 completed 的第一個回合當 failed 重跑。
- 作者交叉檢查：補上 Permission 改選後不得暗中以舊 Bypass retry、requested/effective Thinking 區別、既有 skillReferences 的保存，以及 initialized-empty 與 conversations/ 遺失的區別。12 個 G 與 A01–A21、依賴順序、非目標及三層協議工作一致；格式及 chooser 仍標為提案。
- 逐檔 UTF-8 解碼、LF、結尾換行及 replacement-character 檢查通過。首次逐檔 `git diff --no-index --check -- /dev/null <實際檔案>` 找到 Markdown 行尾空白，已移除並重跑通過；沒有隱藏該發現。
- Git 交接檢查發現根 .gitignore 的 build/ 會忽略四個 phase。已只在計畫目錄加 .gitignore 解除此影響；`git status --short --untracked-files=all` 確認 11 個檔案全數可見且均在本計畫目錄。tracked production diff 為空；`git diff --check` 通過，沒有 stage、commit、branch/worktree mutation。
- 撰寫時一次過長的 shell 輸入遭 Windows command-line 長度限制，尚未建立檔案；改成較短的 WSL/Linux 寫入後成功。沒有因此改用 Windows runtime 寫 project 檔案。
- 規劃就緒：可交付並明確啟動。實作階段仍全為 Not started，舊資料歸屬、真實 GUI 可操作性與可能昂貴的驗證依 D9/P4 條件處理；沒有將計畫驗證宣稱為功能完成。

## 恢復規則

開始前依 PROMPTS.md 讀文件並核對實際 workspace。實作後將實際步驟／命令／結果／驗收編號／限制寫入此處；不在 GOALS 或 index 增加第二份動態狀態。已完成檢查若來源未變可明確重用；被後續變更影響的檢查才重做。

## Execution evidence

### E05 / P1-S1: authorized execution and runtime preflight (2026-10-15 Asia/Taipei)

- The user explicitly started the complete plan, accepted D1/D4/D5 and necessary cross-layer/tool parameter changes, and required a commit for each change step. Local step commits are authorized by that instruction; push/merge/rebase/branch/worktree changes and expensive checks still require separate approval. No new dependencies, paid providers, or real history migration are authorized.
- First action was read-only runtime/branch/dirty discovery: GUI, clean working tree, origin git@github.com:Minervamuses/RESEARCH-AGENT-WORKSPACE.git. Current HEAD is 2121935 (planning commit), after the documented baseline 1cf54d7. No implementation existed at this checkpoint.
- Read root AGENTS.md, then GOALS.md, PLANS.md, context/contracts.md, build-log.md, and dependency-ready phase-01-project.md. No ancestor or nested AGENTS.md was found.
- Windows PowerShell is only the host launcher; project commands use WSL Ubuntu-24.04 bash at /home/minervamuses/research-agent-workspace. /usr/bin/git 2.43.0; Conda app Python 3.13.14, Poetry 2.4.1, Node 24.18.0 and cargo 1.97.1 verified. conda is not on login-shell PATH, so use its absolute launcher or source its activation script. rg is absent; use git grep/find without installing tools.
- Existing Python, Node and Rust tests/fixtures were located. node_modules, dist and Rust debug cache/binary exist. WSLg DISPLAY=:0 and wayland-0, xdotool and gdbus are available; no app process was running. A separate read-only/isolated-fixture baseline investigation is in progress; no GUI acceptance or size measurement is claimed yet.
- No build/test/provider call or real history access has occurred in this step. Next: finish GUI baseline before CSS changes; implement and verify P1-S2 in existing desktop catalog/test modules.

### E06 / P1-S2: strict project metadata and scoped history helpers

- Added inspect_project / initialize_project / load_project_catalog in existing catalog.py. Metadata parsing excludes fenced examples, rejects duplicate keys/blocks and unsupported syntax; existing prose bytes are preserved on append. Fingerprint checks and atomic publication protect initialization, with explicit leftover history locations on write failure.
- Initialization creates only this hashed canonical-root project and an empty conversations directory. Existing history is accepted only after a complete healthy scan with the same project ownership; mixed/null ownership, malformed conversation data and missing catalog members fail closed. No real user history was read or moved.
- Added 24 cases in existing test_desktop_conversations.py for A02/A03 and scoped ownership/incomplete-scan aspects of A04/A07. Agent ran `poetry run pytest tests/test_desktop_conversations.py -k "project_settings or catalog" -q`: 39 passed, 22 deselected, 0.50s (one existing LangChain deprecation warning). Main agent reviewed actual diff; scoped git diff --check passed. These helper tests do not establish integrated GUI acceptance.
- P1-S1 baseline investigation has launched only the existing isolated no-provider fixture; measured 1080x720 Tauri window, sidebar 272px and transcript 370x197px through AT-SPI. Editor baseline remains pending because working-tree protocol updates reached Vite before backend binding was integrated.
- Next: P1-S3 service binding plus shared TS/Python/Rust protocol, followed by P1-S4 chooser. P1-S5 archive-root work is partially present but uncommitted: two attempts failed with missing Path import (second edit matched no text); requested permission for the concrete one-import correction under the two-attempt rule. Do not treat that work as verified.

### E07 / P1-S3 and P1-S7 protocol slice: explicit project binding

- Service construction no longer instantiates or scans conversation storage. Cold project.list returns no projects; documents and sessions require an explicitly opened project. workspace.select inspects without binding; initialized/validated candidates bind document root, repository and catalog together only after old-session cleanup succeeds. Busy document/session operations block switching.
- Updated shared contract/fixtures and TS/Rust validation for workspace.select inspection, initialization fingerprint and scoped result fields. Python consumes the shared schema. Unknown fields/enums and malformed fingerprints remain rejected. New rejected session.turn guards preserve the existing accepted/persisted lifecycle DTO.
- Actual targeted checks: Python protocol 155 passed (0.37s); Node protocol 149 passed (188ms); cached/offline Rust protocol 12 passed (0.08s test runtime). Rust first run exposed a manifest test that rejected all null params; corrected its expectation specifically from nullableString schema, then reran successfully.
- Service integration tests (`poetry run pytest tests/test_desktop_service.py -q -k project_open`) 4 passed, 81 deselected (latest 0.41s). They check no cold storage access, no pre-open session/document, read-only preview, isolated same-filename A/B roots, failed cleanup preserving A, foreign ownership/incomplete scan rejection and busy switching. Initial new-test failures were invalid UUID literals; corrected those fixtures, with no production relaxation.
- Main reviewed actual service/protocol diff; no runtime/Git environment switch, dependency addition, paid call or true history access. Existing implicit-local test fixtures still need adaptation in P1-S7; this is not P1 completion.
- User explicitly approved the P1-S5 one-import correction. It was applied and archive tests passed (6/6), then a new Normal/Extended graph routing case passed (7/7, 0.48s); those separate pending files are not included in this S3 commit.

### E08 / P1-S4: cold project chooser and scoped history UI

- App now starts without loading any catalog/session history and presents the existing Linux-folder chooser after local backend diagnostics. Inspect shows canonical root/history and metadata status; initialization is explicit. Editing a proposed history path requires re-inspection before Initialize can be enabled. Only an opened result commits and clears the prior project state.
- History refresh accepts exactly the selected project; document.open no longer changes workspace. The chooser requires Save/Discard/Cancel for dirty content and explicit draft discard; failed open keeps current data. Backend restart reopens the already selected canonical root and retains editor/draft before restoring selection.
- Changes limited to App.tsx, conversations.ts and existing conversations.test.ts. Actual checks: `npx tsc --noEmit` passed; Node conversations+documents 36/36 passed (~5.2s); after canonical-history-preview correction, tsc and 4 focused project tests passed. Main reviewed diff; scoped whitespace check passed.
- Full epoch/late-result protection remains P1-S6. Native GUI integrated project-open acceptance remains pending fixture adaptation; no visual completeness claim is made.

### E09 / P1-S5: scoped rules and archive tooling

- Preserve the existing SYSTEM_PROMPT and append canonical project root plus RESEARCH rules with explicit Permission/version boundaries. Recheck settings at each new turn boundary; changes to history identity reject that turn and require reopening. In-flight rules and Permission stay fixed.
- Propagate selected ConversationRepository root through the existing session -> graph -> inventory -> read_file chain, including Extended proposer graphs. CLI/default root retains the prior defaults; config.persist_dir and other stores are unchanged. No new module/dependency or alternate tool pipeline.
- Actual tests: `poetry run pytest tests/test_desktop_service.py -q -k project_rules` -> 2 passed (0.39s), verifying system prompt preservation, midturn rule edits, Ask despite bypass text and pointer-change rejection before execution. `poetry run pytest tests/test_conversation_archive_access.py -q --tb=short` -> 7 passed (0.48s), including >1MiB scoped chunk access, unchanged global store, and Normal/Extended root propagation.
- Earlier missing-Path-import failure and no-op repair are retained in E06/E07. User explicitly authorized the one-import correction and continuing P1-P4; corrected file was re-read before the successful rerun. Main reviewed diff and scoped whitespace check passed.
- Next P1-S6: late-operation guards; inspection found existing session lifecycle calls can cancel pending approval before rejecting BUSY_TURN, so this directly relevant guard must be corrected and tested.

### E10 / P1-S6 backend: preserve pending consent on rejected switching

- Session create/select/shutdown and runtime shutdown now reject an active turn or pending approval before any cancellation. Document apply/tool locks and outstanding project operations block lifecycle replacement. Existing explicit approval.resolve remains the decision boundary.
- Extended delayed-document test and two pending-consent cases prove rejected lifecycle requests leave the future unresolved until explicit resolution. Actual command: `poetry run pytest tests/test_desktop_service.py -q -k "project_open or project_rules or project_lifecycle"` -> 8 passed, 81 deselected, 0.47s. Main reviewed resulting control flow; scoped whitespace check passed.
- Frontend epoch/operation/focus protection is still being completed separately. Cached native build `timeout 180s cargo build --offline` succeeded in 6.01s, with no dependency or lock change, for the upcoming integrated Linux GUI check.

### E11 / P1-S7 fixture and preserved execution paths

- Existing phase02 fixture now seeds two isolated roots at <fixture-root>/projects/project-one and project-two, each with RESEARCH metadata and store/projects/<hash>/conversations. The constructed service stays unbound; tests/UI explicitly open the selected project. Only synthetic /tmp fixtures are initialized. Crash checkpoint injection remains scoped to project-one's repository.
- Adapted existing fixture, document-service, final-answer, extension-entry and crash-recovery tests to explicit project opening and scoped history, retaining their permission/save/conflict/undo/replay assertions. No production gate bypass or new test framework.
- Actual checks: fixture module first run 20 passed/1 failed because its old no-RAG-write assertion excluded only store/conversations; changed that exclusion to the selected history/conversations and reran the single case successfully. All 21 fixture cases therefore have passing evidence (unchanged 20 reused). Document-service cases: 6 non-fixture passed (0.51s), then 1 fixture passed (0.24s). Answer-stream + affected extension-entry cases: 17 passed, 1 unrelated user_dropin case deselected (0.96s). Crash-recovery module under 120s cap: 6 passed (8.72s); no actual provider calls.
- Main reviewed fixture production diff and test scope, git diff --check passed. Conversation/service legacy fixture adaptation and native project GUI flow are still pending, so P1 remains in progress.

### E12 / P1-S7 conversation regression fixtures

- Adapted existing conversation coordinator fixtures to explicitly open two separately owned project/history roots. Updated old orphan/malformed/partial-scan fallback expectations to the authorized fail-closed behavior, asserting unchanged bytes. Turn lifecycle, ordered registration, controls, retry/no-replay and citation-entry coverage remain.
- Only test_desktop_conversations.py changed; all 44 test functions retained and S2 metadata tests preserved. Actual complete-file run once: `poetry run pytest tests/test_desktop_conversations.py -q --tb=short` -> 61 passed, 2.42s. Earlier focused run: 11 passed/2 failures (fake factory missing system_prompt argument and obsolete local-project expectation); corrected those test assumptions, focused 15/15 passed before the complete-file run.
- Main reviewed actual setup/expectation diff and scoped whitespace check passed. No production bypass, true history migration or provider request.

### E13 / P1-S6 frontend: ownership of delayed results

- Added backend-generation, project-epoch and operation-token checks to existing workspace/document/catalog/session/control/approval callbacks, including catches, finalizers and delayed focus/scroll. Reopening A after A-to-B invalidates results from the first A. Conversation switch confirmation preserves an unsent draft on cancel/failure.
- Actual checks by frontend agent: TypeScript no-emit passed; existing conversations/documents/answer_stream tests 58/58 passed (~4.45s); final five focused epoch checks and TypeScript passed. Four new cases use deferred responses for catalog/selection/rejection and reducer epochs. An initial TypeScript check found six obsolete unused locals after replacing guards; removed before successful verification.
- Main reviewed the changed control flow and scoped whitespace check. Native project interaction remains pending and is running against synthetic data; these unit checks do not establish GUI acceptance.

### E14 / P1-S7 service regression fixtures

- Adapted existing service scenarios to explicitly open an owned project, including canonical restart/registration/citation fixtures; the base service helper remains cold. Existing read-only sidebar scan-count test now instruments all scoped repository instances and retains its fewer-scans assertion.
- Actual complete-file run: `poetry run pytest tests/test_desktop_service.py -q --tb=short` -> 89 passed, 3.71s. Earlier subsets: 20 passed, then 15 passed/3 setup failures (cold fixture and fake missing canonical records); corrected to explicit fixture opening and existing canonical factories, then all three passed. No production gate relaxation.
- Main reviewed actual fixture and assertion changes; git diff --check passed. P1 implementation and focused regression tests are complete; native chooser/switch verification remains the final P1 checkpoint.

### E15 / P1 native checkpoint and independent review

- Native Linux Tauri/WebKit with a fresh no-provider fixture at `/tmp/research-agent-desktop-phase02-p1gui-20261015-e895dc4`: cold start showed project chooser with no conversations. Opening project-one showed only its two seeded conversations, not project-two. Opened draft.md, entered unsaved editor text and an unsent composer draft. Switching/inspecting project-two showed explicit dirty Save/Discard and draft-discard choices; Cancel preserved A root, unsaved editor and `Unsent A draft`. Both project files remained unchanged on disk.
- Actual AT-SPI rendered bounds at 1080x720: sidebar 272px; Monaco code region 412x427px (not its 2px input textarea); transcript 370x197px. Evidence: project-one-document-open.json and dirty-draft-cancel-preserved.json in the fixture root. These are actual native controls and geometry; WSLg screenshot capture remains black and is not used as visual proof.
- Independent read-only integration review at 281e538 found no demonstrated P1 blocking issue after tracing cold binding, ownership, rules reload, busy guards and epoch/catch/finally/focus paths. It did not rerun tests or claim GUI evidence. Main reviewed committed scope; no dependency, lock or environment changes, and worktree was clean.
- P1 end condition is met by this checkpoint plus E05-E14 focused evidence. Remaining broader GUI permutations belong to P4; ongoing explicit discard/B-only/return-A check will be recorded when observed. Next dependency-ready phase is P2.

### E16 / P2-S1: canonical v2 and pending submission persistence

- Canonical writer now emits schemaVersion 2 with nullable submittedContext; strict v1 reads preserve bytes and schema identity until an actual fingerprint-checked write upgrades them. Existing pending-first session flow accepts optional context for conversational and display-only turns; same-ID/immutable comparisons include the detached structured packet. Nested snapshot tampering is rejected against durable data.
- Model validation covers strict document/chat unions, original UTF-16 ranges/text/lines, project/root ownership, rules hash, Skill spans and serialized 1 MiB input size. No sidecar, store migration or real history access.
- Actual checks: new canonical/session subset 21 passed (0.56s); full two affected modules `poetry run pytest tests/test_conversation_repository.py tests/test_session_persistence.py -q` -> 50 passed (1.43s). Main review found a doubled escape in Skill dot-boundary regex; corrected and added @citation.extra assertion, targeted node passed (0.30s). Scoped whitespace check passed.
- Additional P1 native evidence: explicit dirty/draft discard opened B with only C, same-named draft.md contained B text; returning A showed only A/B and original A file. Reopening the native App required chooser again; Cancel exposed no history. Native test processes were stopped. Evidence in E15 fixture root: final-baseline-a.json, reopened-cold-chooser-ready.json, reopened-chooser-canceled.json. Early snapshot while backend was still starting failed its timing assertion; the later ready snapshot passed without repeating Start. No claimed screenshot evidence.
