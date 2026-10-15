# 計畫狀態與實際證據

這是唯一可變執行狀態來源。2026-10-15 本次只撰寫計畫，沒有功能實作、App 啟動、應用程式測試、build、provider 呼叫、migration 或 Git mutation。

## 目前階段

| 階段 | 狀態 | 實作證據 | 阻塞／前提 | 下一步 |
|---|---|---|---|---|
| P1 | Complete | E05-E15: implementation, focused tests and native checkpoint | none | P2 dependency is ready; broader acceptance continues in P4 |
| P2 | Complete | E16-E23: canonical/protocol/reference lifecycle and native mixed-reference retry | none | P3 dependency ready; full A21 continues in P4 |
| P3 | Complete | E24-E29: compact UI, focused checks/build and native A16-A20 | none | P4 dependency ready |
| P4 | In progress | E30-E33: complete regression plus scoped repairs; native A21 underway | Native A10 exposed omitted safe-link label; correction under verification | Verify native link capture and complete journey |

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

### E17 / P2-S2: strict cross-layer submission contract

- Shared contract, Python, TypeScript and Rust accept typed document/chat submittedContext on session.turn and optional nullable submittedContext on transcript items. Unknown/mutually exclusive fields, original UTF-16 text/line ranges, root/project identity, Skill spans, duplicate IDs and serialized 1 MiB input are checked; existing 2 MiB wire limit is unchanged. Python additionally verifies rules text SHA-256; TS/Rust enforce SHA format, with actual project rules checked by the service.
- document.proposed optionally carries referenceId so conflict UI can identify the original frozen source without copying another snapshot over the wire. Context projectId and canonical Linux path validation were aligned across layers, including uppercase/newline IDs, DEL, leading double slash and legal C1 Unicode filename cases.
- Actual bounded runs: Python181 passed, Node175 passed, Rust13 passed (cached compile about4s); isolated protocol.ts TypeScript passed. Final newline-ID correction: Python118 shared cases, Node shared suite119 including parent, Rust shared-message test1, isolated TypeScript all passed. Canonical path parity cases3 passed (0.18s).
- Earlier failures were old exact transcript-field expectations, new invalid fixtures missing expected errorCode, and a Rust manifest test treating the first optional event field as required; corrected those test expectations. First standalone tsc command required --ignoreConfig and did not typecheck; corrected invocation passed. Main reviewed protocol semantics and scoped whitespace checks. No dependencies or version-ceiling changes.

### E18 / P2-S3 editor capture

- Existing Monaco editor exposes Add to chat next to the selected source plus a context-menu/keyboard action (Ctrl/Cmd+Alt+Enter). The action copies the full original-source snapshot and retained UTF-16 selection without saving or submitting. Parent callback owns cards and focus.
- Actual existing document helper module: 8/8 passed (3.855s), covering second duplicate, BOM/CRLF/emoji coordinates and detached frozen snapshot. TypeScript passed after correcting an inferred false literal to boolean in Monaco's context key. Scoped diff check passed. Native popover/focus is being checked separately and is not established by these tests.

### E19 / P2-S5/S6 backend: original retry context and writable targets

- Service checks new submissions against freshly inspected project rules and controls. Existing turns use durable context/rules/semantic input; changed same-ID context and mismatched current Permission/Thinking are rejected explicitly. Transcript returns the original packet. Stored document snapshots can be analyzed after the original file disappears; prepare/apply still require the real current file and original version checks.
- document_edit accepts optional reference_id for a frozen document target, rejects chat/unknown targets and ambiguous multiple references, and emits its source identity for conflict display. No ID retains the current background range. References are separate quoted data, never fed into the user's background line resolver.
- Actual checks: document service+documents modules44 passed (0.78s); new reopen/legacy cases3 passed after two legacy fixtures were corrected to refresh the catalog before selection. Additional background-line/reference cases4 passed (0.70s); final retry/reference subset6 passed (0.55s). These include Ask/Bypass editor conflicts, second duplicate-only writes, missing-source retry, explicit control mismatch, full service reopen, v1 read-no-write, and refusing unavailable legacy writable context even when a new editor is supplied.
- Existing service/conversation modules first run148 passed/2 failed (6.24s). Fixed a real legacy identity regression: original semantic override now requires explicit retry for context-null turns; updated the exact transcript assertion for the newly added nullable field. Relevant13 cases then passed (0.74s), unchanged148 evidence reused. Initial new retry check exposed generic INTERNAL_ERROR for a submission conflict; changed only this helper's errors to clear PROTOCOL_INVALID and the failed case passed.
- Independent review found a single-reference fallback could replace an explicit background line target. Removed that fallback and verified lines40-45 still change when an unrelated first-line reference is attached. No target is guessed from last selection/text. Main reviewed actual diff; scoped whitespace check passed.

### E20 / native-discovered P1/P2 selection race

- First P2 native selection returned SESSION_NOT_READY while the App's intentional parallel transcript preview was active; selecting again after preview completed succeeded. Code tracing confirmed the P1 broad operation count treated that read-only preview as a conflicting session mutation.
- Kept all reads in the project-root switch guard, but subtract read-only list/transcript operations for same-project session create/select admission. No concurrency pipeline was added. A deterministic delayed-transcript regression verifies selection succeeds, root switching remains blocked until the read finishes, and counters balance.
- Actual focused command: `poetry run pytest tests/test_desktop_service.py -q -k "parallel_transcript_preview or project_lifecycle or project_open" --tb=short` -> 7 passed (0.49s), first run. Scoped whitespace check passed. Native recheck pending restart.
- Native P2 observation before pause: selected second duplicate CRLF/emoji paragraph using Monaco keys, clicked Add selected document text to chat; card showed draft.md lines2-2 and same-emoji text, composer was focused, disk bytes unchanged and conversation still1turn. This is partial P2 GUI evidence, not full phase completion.

### E21 / P2-S2 fixture submission and reference tool seam

- Existing isolated fixture propagates submitted_context through conversational/display-only pending writes; fail-once marker reads original display input, so frozen semantic sources do not disable failure/retry. Two distinct logical IDs support same-process retry and a separate failed-turn reopen retry.
- Added [[fixture:reference-replace]] to the existing document seam: exactly one document reference supplies its reference_id; zero/multiple references request clarification without a tool or write. Existing document-replace remains a background edit. This is synthetic fixture behavior, not model execution.
- Actual checks: context/fail/status/round-trip subset5 passed (0.68s); new reference seam test1 passed (0.40s), checking0/2/1 references, unchanged bytes then second-duplicate-only save and proposal identity; existing real document coordinator1 passed (0.25s). Main reviewed actual diff and scoped whitespace check.

### E22 / P2-S4/S5/S7 frontend reference lifecycle

- Existing reducer owns detached draft references and original submitted context. Cards show frozen source/range/version and full selected text; draft cards can be removed, historical cards cannot. Single-message chat selections use visible rendered text with UTF-16 offsets and hash, exclude controls/cards/hidden content, and reject cross-message selection.
- New submission first inspects current project rules under the operation owner, then freezes context; retries skip inspection and reuse original context. Text/reference edits start a new logical turn; differing Permission/Thinking disable original retry with an explicit new-turn option. References-only drafts require discard confirmation on project/conversation changes. All asynchronous selection/hash/focus paths retain generation/epoch/token ownership. Named document proposal uses the original reference snapshot for conflict display, without sending that local UI field to document.apply.
- Actual checks: TypeScript passed; related conversations/documents/answer_stream67/67 passed; final ownership/reference/retry subset9 passed. Main review found line labels only counted LF; changed to canonical CRLF/CR/LF break endpoints and added CR-only case, final TypeScript and2 focused document-reference checks passed. No P3 grid/dimension changes, only14 required reference CSS rules.
- Independent read-only App/reducer review found no demonstrated blocking issue in retry, discard, late callbacks, historical cards or source identity. Main reviewed actual diff and whitespace check. Native selection/mixed-reference/retry verification remains in progress; P2 is not complete yet.

### E23 / P2 native checkpoint and phase completion

- Native Linux Tauri/WebKit at `/tmp/research-agent-desktop-phase02-p2gui-20261015-2c56ba5`: restarted backend to generation2, explicitly reopened A and first selection succeeded with seed transcript (p2-first-select-fixed.json), confirming E20 race correction in the App.
- Selected the second identical CRLF/emoji line; Add to chat retained UTF-16 [8,14), original revision0/source and lines2-2 after cursor movement and editor changes. No save or turn occurred on add. References-only draft with dirty editor survived inspect-B then Cancel. Native visible A seed question selection added a chat card with original message identity/hash.
- Mixed document+chat references sent with [[fixture:fail-once]] failed, then Retry saved draft completed after further editor edits. Main independently compared p2-failed-turn-evidence.json and p2-retried-turn-evidence.json: identical turnId 9cbd8ed8366742018c829ddca0257ce2, submittedContext, semanticInput and displayInput; failed -> completed, total conversation count remained2. Native snapshots p2-mixed-failed/retried retained in fixture root.
- Actual same-window baseline p2-layout-baseline.json: 1080x720, sidebar272px, Monaco code412x427px, transcript370x197px; font/zoom unchanged. Two draft references reduced transcript to35px and failure notice overflowed viewport; this observed layout defect is within the next P3 compression task, not claimed resolved. Pixel capture is unavailable; AT-SPI rendered controls/geometry and exact disk evidence are used.
- P2 implementation end condition met using E16-E23; remaining reopen, multiple failed logical turns and full reference-write native journey belong to P4. Owned Vite/native sessions stopped, fixture/evidence preserved. Runtime/GUI branch and clean HEAD6cf31fd rechecked before this entry. No provider/dependency/real-history operation.

### E24 / P3-S1/S2: compact document actions

- Removed permanent folder/path fields, toolbar and normal success notice. Existing document header now contains filename/full-path title, true dirty marker, short busy indicator and Open file/Save/Undo last Agent edit menu. Open uses a temporary relative-path dialog with Escape/Tab handling; dirty replacement requires explicit confirmation. Existing document.open/save/apply/undo and Mod+S handlers remain the only operations.
- Open/save/apply exceptions stay visible in a persistent local error area; successful open/save removes it. Failed open retains source and undo receipt. No automatic save or project binding on file open.
- Actual frontend checks: `npx tsc --noEmit` passed; four focused existing header/save/reconcile cases passed. Main reviewed complete three-file diff and whitespace. Native menu, keyboard and dirty workflow remain pending; no GUI completion claim.
- Additional pre-S3 native width baseline: same font/zoom at1440x900 gives sidebar290px (p3-old-sidebar-1440-baseline.json in E23 fixture root), versus272px at1080x720. Owned native/Vite processes stopped after measurement. P3-S3 can now compare actual widths at both sizes.

### E25 / A03 and A12 direct evidence gaps

- Independent mapping found that malformed JSON was not evidence of filesystem permission denial, and separate pending/context tests did not directly establish structured pending recovery. Added only existing-test coverage for these two required cases.
- Actual Linux uid1000 chmod(0) on owned temporary RESEARCH.md/history raises OS PermissionError; cold opening rejects without fallback and a failed switch preserves B binding. Finally restores exact mode; all fixture file bytes remain unchanged. Structured pending with both document/chat references becomes interrupted on restore, preserving original context/semantic/display with no graph invocation.
- Exact command: `poetry run pytest tests/test_desktop_conversations.py::test_project_open_permission_denied_preserves_sources_and_current_binding tests/test_session_persistence.py::test_reload_interrupts_leftover_pending_without_replay -q --tb=short` -> 4 passed,0.53s; first attempt, one existing deprecation warning. Main reviewed two-file diff; whitespace passed. No production or real-data operations.

### E26 / P3-S3: sidebar width and long titles

- Set sidebar minmax bounds14.5/17rem ->10.15/11.9rem; kept root font scale and760/1050px breakpoints. Reduced internal gaps, wrapped lifecycle actions and ellipsized project/conversation titles with full title and hover/keyboard-focus expansion.
- Actual TypeScript and existing styles module2/2 passed. Initial new floating-point exact equality assertion failed at10.15 vs10.149999999999999; corrected numeric tolerance only, no production workaround. Main reviewed three-file diff and whitespace. Actual rendered70% ratio remains pending P3 native verification against E23/E24 baselines.

### E27 / P3-S4/S5/S6: footer controls and usable height

- Moved Thinking icon/current-mode menu and Permission Ask/Bypass to composer footer left, Send right. Reused ACK handlers and turn/document/approval/workspace disabled guards. Thinking menu supports Escape/arrows/Home/End and returns focus; actual document Extended preference gets a short effective-Normal hint only while active.
- Removed old session-controls and both obsolete four-row conversation tracks. Conversation now allocates remaining height to transcript; draft references, retry/error notices and session details have bounded scroll areas. Normal document/composer controls remain compact, with existing narrow breakpoints and unchanged font scale.
- Main review caught task-introduced duplicate media CSS (removed) and full-path ellipsis hiding reference filename/lines. Compact card now displays basename and original lines, with full source path in title and expanded version detail. No frozen-packet changes. Independent read-only review found no demonstrated handler/ACK/retry/focus blocker.
- Actual `npx tsc --noEmit`, documents/trust/styles/conversations66/66 and `npm run build` passed (735modules; existing Monaco >500kB chunk warning). Final card correction additionally passed one targeted card test, TypeScript and justified rebuild; whitespace check passed. Two preliminary tool-input quoting errors executed no shell or file changes. Native dimensions, keyboard, save/Undo and multiple-card failure usability still pending; P3 remains in progress.

### E28 / P3 native dimensions with identical content

- To compare the same long-title list rather than infer from CSS, materialized read-only `git archive d01d4c0` frontend source in `/tmp/research-agent-p3-baseline-ui-1urhhxou/app/desktop`, linked already-installed dependencies and served it through existing Vite/native binary. No checkout/branch/worktree mutation or install. Both old and current UI used the same isolated fixture `/tmp/research-agent-desktop-phase02-p3gui-20261015-57fc0f8`, same seeded A transcript, CRLF duplicate source and additional long-title conversation; selected A for every measure. Font/zoom unchanged.
- Actual AT-SPI sidebar at1080x720:272 ->190px (69.8529%; agreed272*0.7=190.4, integer bounds differ by-0.4px). At1440x900:290 ->203px (70.0%). Editor heights427 ->584px (+157) and608 ->754px (+146); transcript heights197 ->423px (+226) and387 ->585px (+198). Main read p3-old-new-layout-comparison.json, checked all longTitlePresent flags and both ratios/height increases. Four underlying snapshots preserved there; no pixel screenshot claim.
- Current native Document actions -> Open file dialog actually opened draft.md; old permanent path inputs and top controls are absent. Native save/Undo, keyboard/disabled controls, multi-reference failure and minimum-window usability are still in progress; P3 not yet marked complete.

### E29 / P3 native operations and phase completion

- Same isolated E28 native App: .md -> dirty Open .tex showed confirmation; Escape/Cancel retained editor and disk. Ctrl+S and menu Save each wrote actual bytes and cleared dirty. Clean open .tex succeeded. Thinking Space/Down/Enter selected Extended, Space/Escape closed menu; Permission keyboard selected Bypass then Ask with visible acknowledged states.
- During fake document edit Ask approval, Thinking/Permission were disabled and effective-Normal document hint appeared. Approve wrote the candidate; menu Undo required its own Ask approval and restored original TeX bytes. External disk change + Ctrl+S retained external bytes and showed conflict/dirty. Separate owned locked/note.md directory chmod500 produced actual Errno13/Save failed/dirty, unchanged disk; directory restored700 in finally, Cancel preserved editor.
- Two references show basename/lines and expanded complete source/version. Mixed-reference failure at1080x720 kept actual root height720, Message387x78 and Send74x40 inside viewport; transcript82px, resolving E23 overflow. At720x560 the existing stacked layout scrolls; keyboard focus brought Message and Send fully inside actual viewport. Long-title focus wrapped complete text within sidebar. Evidence: p3-savefailure-visible, p3-checkpoint-final, p3-minimum-*-focused, p3-longtitle-focus, p3-failed-turn-for-p4.json plus interaction snapshots in E28 fixture root.
- P3 A16-A20 native checkpoint passed with no additional production change. Cached native/Vite retained for P4; only synthetic project data changed. P4 is now dependency-ready; full regression and complete two-failure/reopen journey have not yet been claimed.

### E30 / P4-S3: one complete regression run and obsolete UI assertion

- Read dependency-ready phase04 only after E29. Existing-suite cost evidence (86 modules, prior local runs and fake boundaries) supported bounded checks; no live provider/model/GPU or install. Executed once in parallel: `timeout 180s poetry run pytest -q --tb=short` (app), `timeout 120s npm test` (desktop), `timeout 180s cargo test --offline protocol` (src-tauri), all Conda app/Linux.
- Full Python actual result:1452 passed,42 failed,2 warnings,39.43s. Six inline_skills,34 project_permissions and2 skill_adherence failures use obsolete cold DesktopService fixtures before project-open (the last two directly inject a session into an unbound service). Do not claim full pass. Updating only those owned synthetic setups while preserving Skill/permission assertions; no production gate relaxation and no second full-suite run planned.
- Node actual full result:273 passed,1 failed,6.87s. The retired-Plan-mode check still required an Extended <option> in App.tsx after P3 intentionally replaced it with ThinkingControl. Updated that single source-integration assertion; existing footer SSR already verifies both options/current mode/guards. Exact focused rerun `node --test --experimental-strip-types --test-name-pattern="Product Plan Mode" tests/protocol.test.ts` ->1 passed,133.7ms. Unchanged273 results reused, no whole-suite rerun.
- Rust actual filter matched15 tests (13 protocol plus2 related backend protocol cases),15 passed; cached compilation3.92s/test0.13s. The main binary contains0 tests, which is not counted as evidence. Frontend build from E27 remains valid (only a test assertion changed). Main reviewed the one-line test diff and whitespace; native A21 is in progress.

### E31 / P4-S3: permission regression fixture binding

- Existing test_project_permissions.py now explicitly opens the owned temporary project before session.create in five setup functions. Existing Ask/Bypass, frozen consent, correlated approval, stale prune and extension assertions/fakes are unchanged. No production code changed.
- Actual `poetry run pytest tests/test_project_permissions.py -q` ->36 passed,0.69s, one existing warning; first patch/first run. This resolves the34 failures in that module from E30 and also rechecks its2 previously passing cases. Main reviewed complete diff; scoped whitespace check passed.

### E32 / P4-S3: inline Skill regression fixture binding

- Existing test_inline_skills.py opens the owned project before session.create in three setups and removes two obsolete later root-only workspace.select calls. All real catalog, multi-Skill order, save/retry, unsaved-claim and citation assertions and fake models remain unchanged.
- Actual ordered multi-Skill targeted cases3/3 passed,0.43s; complete small module `poetry run pytest tests/test_inline_skills.py -q --tb=short` ->12 passed,0.65s, one existing warning. First patch passed without repairs; all six E30 failures in this module resolved. Main reviewed complete diff; scoped whitespace check passed.

### E33 / P4-S3: Skill installer regression fixture ownership

- Existing two cleanup-conflict cases create owned project metadata before the preview turn and pass its project identity into the existing ChatSession helper. They then explicitly open that project and use session.create with a test factory returning the previewed session, checking repository root/project identity and retained pending installer state. No existing history ownership is relabeled; no production gate is bypassed. Original cleanup conflict, backup bytes, no execution and mode/answer assertions remain.
- First targeted run failed2/2 in0.31s because the new setup passed Path instead of required str to initialize_project. Corrected only that argument; second focused run2/2 passed,0.40s. Existing shared-helper load-failure/duplicate case1 passed,0.27s. One existing warning; main reviewed complete diff and scoped whitespace passed.
- All42 Python failures from E30 now have passing scoped evidence (34 E31,6 E32,2 here), with unchanged1452 initial passing results reused. This is not a second full-suite pass. No dependencies, paid providers or real data were involved.
