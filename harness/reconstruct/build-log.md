# Canonical Conversation JSON 與 Plan Mode 退場 — Build Log

本檔是 runtime phase status與 observed implementation/verification evidence的唯一 source of truth。Plan描述預定工作；本檔只記真正發生的結果。

## Phase summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Canonical conversation contract | Complete | 2026-09-04 18:20 CST | 2026-09-04 18:44 CST | Contract, Red/Green tests, review, and commits below | None |
| 02 — Legacy import bridge | Complete | 2026-09-04 18:48 CST | 2026-09-04 19:14 CST | Mapping, Red/Green tests, fault review, and commits below | None |
| 03 — Write-through turn lifecycle | Complete | 2026-09-04 19:23 CST | 2026-09-04 20:30 CST | Atomic lifecycle, host/protocol cutover, fault tests, and fresh review below | None |
| 04 — Host/catalog/retry cutover | Complete | 2026-09-04 20:39 CST | 2026-09-04 22:26 CST | Catalog recovery, full lifecycle paging, explicit retry, display-only commands, and fresh review below | None |
| 05 — Remove Product Plan Mode | In progress | 2026-09-04 22:31 CST | — | Preflight inventory below | None |
| 06 — Retire chat-history Chroma | Not started | — | — | — | None |
| 07 — Migration, faults, docs | Not started | — | — | — | None |

允許的狀態只有 `Not started`、`In progress`、`Blocked`、`Complete`。只有 required acceptance與verification都有 observed evidence時才能標為 `Complete`。

## Evidence rules

- 記錄 exact command/procedure、WSL/Linux + Conda `app` target、concise result與 pass/fail/skipped/unavailable。
- 對每個 acceptance criterion保留 evidence mapping；large output只連結 artifact，不貼完整 log。
- Planned command、歷史 harness result、authoring inspection、status flag或 builder narrative都不是本次 passing evidence。
- 保留 material failed attempt與後來 correction；相衝 evidence在解決前讓 phase維持 `In progress`/`Blocked`。
- 不記 credentials、secret、raw provider/tool payload、完整 diff、真實 user transcript或例行 narration。

## Authoring baseline

- **Date:** 2026-09-03 (Asia/Taipei)
- **Repository:** `/home/minervamuses/research-agent-workspace`
- **Branch/HEAD observed:** `GUI` / `b145b040f014560157ef9444544f4102b81e485e`
- **Worktree observed before authoring:** clean
- **Runtime gate observed:** WSL/Linux；Conda `app`；Python 3.13.14；Poetry 2.4.1
- **Authoring writes:** only the eleven Markdown artifacts under `harness/reconstruct/`
- **Implementation evidence:** none；pytest、npm、Cargo、Tauri、provider與 migration均未執行

## Activity log

尚無 implementation activity。Plan bundle authoring與 structural validation不代表任何 phase已開始或完成。

## 2026-09-03 — Authoring validation

- **Frozen write set:** `git status --short --untracked-files=all`只列出本bundle的11個task-owned Markdown files；沒有application、tests、manifests、legacy data或Git state mutation。
- **Strict validator:** 在WSL/Linux、Conda `app`中執行`validate_harness.py --repo /home/minervamuses/research-agent-workspace --plan-root harness/reconstruct --project-shape application --risk high --harness-only --strict --json`，結果`valid=true`、0 errors、0 warnings。
- **Content checks:** 精確檔案清單、UTF-8/LF、trailing-whitespace、錯誤live paths、tracked+untracked audit語意與command working directories已檢查；`git grep --untracked`已證明能看見本bundle的untracked files。
- **Fresh-agent walkthrough:** 逐項對照使用者architecture brief、live repository與root `AGENTS.md`後，最終結果為0 blocking defects；兩項advisory已吸收：Phase 05/06加入Skills/Citation直接checks，TS typecheck改用既有本機`node_modules/.bin/tsc`並禁止隱式下載。
- **Implementation evidence:** none；七個phase仍全部`Not started`，沒有執行pytest/npm/Cargo/Tauri、provider、Ollama或migration。

## 2026-09-04 18:20 CST — Phase 01: preflight and schema checkpoint

- **Status:** `Not started` → `In progress`。
- **Authorization:** 使用者以`PROMPTS.md`的Start/Resume入口明確啟動implementation，並另外授權本次工作每個logical change都commit；push/merge/rebase/branch/worktree/deploy仍未授權。
- **Runtime/ownership gate:** root=`/home/minervamuses/research-agent-workspace`、branch=`GUI`、execution-start HEAD=`e5fc5176984574f160866f13945bb9bba6766f05`、worktree clean；WSL/Linux、Conda`app`、Python 3.13.14、Poetry 2.4.1。相對authoring baseline `b145b04`的drift僅為已提交的11個`harness/reconstruct/`計畫檔及Phase 04 retry文字澄清，沒有application overlap。
- **Live preflight:** `TurnRecord`仍混用integer turn identity且只能表示completed pair；Desktop另產生UUIDv4 hex turn ID。Canonical contract因此固定`turnId`為stable lowercase UUIDv4 hex，`turnNumber`為conversation-local contiguous positive integer，不直接重用`TurnRecord`。Conversation root由Python-owned `ConversationRepository(persist_dir)`解析為`<persist_dir>/conversations/`；不修改`rag`或runtime callers。
- **Schema v1 exact fields:** conversation=`schemaVersion`, `conversationId`, `projectId`, `createdAt`, `updatedAt`, `turns`；turn=`turnId`, `turnNumber`, `kind`, `state`, `displayInput`, `semanticInput`, `contextEligible`, `thinkingMode`, `submittedAt`, `finishedAt`, `assistantOutput`, `toolActivities`, `failure`；tool activity summary=`callId`, `name`, `status`, `summary`；failure=`code`, `message`, `retryable`。所有objects拒絕unknown/missing keys與non-JSON/runtime objects；不提供任意metadata dict、raw tool arguments/results、provider payload、reasoning或LangGraph/React serialization欄位。
- **Enums and bounds:** schemaVersion=`1`；kind=`conversational|display-only`；state=`pending|completed|failed|interrupted`；thinkingMode=`normal|extended|null`；tool status=`ok|failed|denied|incomplete`；failure code=`execution_failed|persistence_failed|interrupted|cancelled`。Conversation/turn ID皆canonical UUIDv4 hex；projectId為nullable或既有lowercase local ID。最多4096 turns/檔、4096 conversation files/scan、8 MiB/document、1 MiB/each display or semantic input、2 MiB/assistant output、128 tool summaries/turn、256 bytes/callId or tool name、64 KiB/tool summary、4 KiB/failure message、64 bytes/timestamp、256 bytes/derived title。
- **State/shape rules:** first durable file由turn #1 `pending`原子建立，不為未送出的空session建立JSON；後續pending依序append，且每份conversation同時最多一個pending turn。`display-only`固定semanticInput=null、contextEligible=false、thinkingMode=null；`conversational`要求nonblank semanticInput與normal/extended。Pending沒有finishedAt/output/failure/activity；completed要求nonblank output且無failure；failed/interrupted沒有output且需typed failure。Context query只回最近10個completed+contextEligible conversational semantic-input/final-output pairs，依turnNumber升冪；title取最低turnNumber的第一個有效conversational displayInput，collapse whitespace並以UTF-8安全截至256 bytes。
- **Transition/idempotency table:** new ID→pending；pending→completed/failed/interrupted；failed/interrupted→pending僅經explicit retry且保留turnId/turnNumber/input；completed為terminal。同ID同immutable input的duplicate回現有state/result且不append；同ID不同input/kind/thinking/context contract一律conflict；相同completed payload可重送，不同terminal payload或非法transition fail closed。
- **Durability/conflict contract:** strict bounded UTF-8 JSON parse、deterministic encoding、same-directory private temp、file flush+fsync、validated publish、atomic no-clobber create或`os.replace`、parent-directory fsync。Loaded snapshot攜帶bounded content SHA-256 fingerprint；replace前重讀比對，不一致即conflict，沒有merge/last-writer-wins。只清理由本次write建立的精確temp path，symlink/non-regular target拒絕。
- **Verification:** 尚未執行Phase 01 tests；下一步先加入`tests/test_conversation_repository.py`並觀察Red。
- **Blockers:** None。

## 2026-09-04 18:24 CST — Phase 01: Red contract

- **Status:** `In progress`。
- **Changes:** 新增`app/tests/test_conversation_repository.py`，以11個focused tests固定pending/completed round trip、transition/retry/duplicate、single-pending、latest-10、title、UTF-8 bounds、closed metadata、per-file degradation、SHA-256 conflict與file/directory fsync ordering。
- **Verification:** 從`app/`執行`PYTHONDONTWRITEBYTECODE=1 conda run -n app poetry run pytest tests/test_conversation_repository.py -q`，exit 1；collection如預期因`ModuleNotFoundError: No module named 'agent.conversations'`失敗，證明新contract尚無implementation。唯一額外輸出是既有LangGraph deprecation warning。
- **Blockers:** None；下一步實作新`agent/conversations/`package，不切換runtime caller。

## 2026-09-04 18:44 CST — Phase 01: canonical repository complete

- **Status:** `In progress` → `Complete`。
- **Authorized scope:** `phases/phase-01-canonical-conversation-contract.md`；只新增canonical conversation package與相鄰測試，沒有切換runtime caller、修改config、讀寫legacy source或遷移真實資料。
- **Changes:** 新增`app/agent/conversations/{__init__,models,repository}.py`，實作schema v1 frozen DTO、closed parser/validation、typed errors、create/load/save、pending→terminal transition、同-ID retry/idempotency/conflict、summary/scan/latest-context，以及bounded deterministic UTF-8 JSON。Durable publish使用same-directory private temp、file flush/fsync、validated no-clobber create或atomic replace、directory fsync與SHA-256 optimistic conflict check；symlink、FIFO及其他non-regular paths fail closed。
- **Verification:** 從`app/`執行`PYTHONDONTWRITEBYTECODE=1 conda run -n app poetry run pytest tests/test_conversation_repository.py -q`，exit 0，`17 passed, 1 warning in 0.41s`；warning是既有LangGraph `allowed_objects` deprecation。`git diff --cached --check`於功能commit前exit 0。
- **Failure injection:** tests實際驗證malformed/duplicate-key/unknown-version/oversized files逐檔隔離、外部rewrite fingerprint conflict、forced `os.replace` failure保留原檔且清除本次temp、file fsync發生在replace前且directory fsync發生在replace後、FIFO讀取不阻塞、invalid/arbitrary historical save不碰磁碟。
- **Acceptance mapping:** schema/transition/identity/normal+extended+display-only/retry由round-trip與transition tests覆蓋；latest-10、display-vs-semantic、project/summary/first-valid title各有focused tests；max legal field、oversized field/document與bounded read有executable coverage；forbidden metadata/runtime objects及allowlisted bounded activity/failure DTO有negative tests；corruption/version/rewrite isolation與atomic publish如上；`git show --stat f86a25d`只含新package與單一相鄰test module，證明未切換runtime caller或修改舊資料。
- **Review:** focused code review提出三項：`save()`可改寫歷史、FIFO open可能阻塞、retry會覆寫原始`submittedAt`。三項均在Green commit前修正並新增/擴充回歸測試；review後無未解P1/P2。
- **Evidence references:** Red commit `c5fcf2b`；Green commit `f86a25d`；schema checkpoint commit `5e189d8`。
- **Limitations:** 本階段依計畫未跑live provider、Ollama、full migration或runtime integration；這些不是Phase 01 acceptance evidence。
- **Blockers:** None。
- **Next action:** 重新讀durable authority後開始Phase 02 legacy import bridge。

## 2026-09-04 18:48 CST — Phase 02: preflight and mapping checkpoint

- **Status:** `Not started` → `In progress`。
- **Runtime/ownership gate:** Phase 01 completion commit=`0d5259d`、worktree clean；仍使用root=`/home/minervamuses/research-agent-workspace`、branch=`GUI`、WSL/Linux與Conda`app`。只允許synthetic/temp fixtures，不操作`app/store/`、真實Chroma或Plan logs。
- **Legacy input facts:** Chroma strict reader以canonical session UUID查詢、要求每個positive integer `turn_id`恰有user/assistant role pair與相同aware timestamp，並以integer排序；Plan strict reader支援v1/v2、要求同session header、bounded files/turns/text、拒絕fusion、duplicate IDs、ambiguous blocks與unsupported versions。兩者都只回completed `TurnRecord`，不記錄normal/extended thinking mode。
- **Source-to-target mapping:** legacy session ID原樣成為canonical `conversationId`；caller提供並驗證nullable `projectId`。跨Chroma/Plan的integer turn IDs必須唯一且合併後從1連續；`turnNumber`保留該integer，`turnId`由固定domain separator + conversation ID + turn number經SHA-256產生，再固定RFC 4122 variant/version-4 bits，確保重跑為同一合法logical ID。Aware legacy timestamp正規化為UTC `Z`並同時作該completed turn的`submittedAt`/`finishedAt`；document時間取可恢復timestamps的最早/最晚instant。
- **Unrecoverable-field policy:** legacy沒有保存normal/extended thinking mode，因此不得把它猜成任一模式；完整user/assistant pair以completed `display-only`保存，`displayInput`保留原user文字、`semanticInput=null`、`contextEligible=false`、`thinkingMode=null`。這保留可見transcript但不捏造model-context authority。所有legacy tool activities一律丟棄，不把arguments/results、secret-like keys、reasoning或placeholder穿透至canonical JSON。
- **Transaction/idempotency policy:** reader先產生完整bounded in-memory snapshot；任一source malformed、duplicate/gap或轉換失敗即整個conversation失敗。Publish前重新讀取同一sources並比對deterministic relevant-content fingerprint；不一致不發布。只用Phase 01 repository的一次性no-clobber whole-document create；有效target已存在回`already_present`，無效/mismatched target回`failed`且不覆寫，無legacy turns回`skipped`。JSON target本身是唯一success marker，不建立migration database或寫回legacy source。
- **Blockers:** None；下一步加入focused Red migration contract。

## 2026-09-04 18:53 CST — Phase 02: Red migration contract

- **Status:** `In progress`。
- **Changes:** 新增`app/tests/test_conversation_migration.py`，固定real Chroma strict-pair read、Plan v1/v2 read、deterministic UUIDv4 mapping、UTC normalization、display-only/no-context policy、tool payload drop、valid/invalid target precedence、rerun idempotency、source-change detection、gap/duplicate all-or-nothing、publish failure、per-conversation isolation與empty-source skip。
- **Verification:** 從`app/`執行`PYTHONDONTWRITEBYTECODE=1 conda run -n app poetry run pytest tests/test_conversation_migration.py -q`，exit 1；collection如預期因`ModuleNotFoundError: No module named 'agent.conversations.legacy'`失敗。這證明migration boundary與one-shot document publish尚未實作；唯一額外輸出是既有LangGraph deprecation warning。
- **Review checkpoint:** live source audit另確認Phase 01 repository只有pending-first `create()`，若逐turn匯入會留下partial target；Green必須新增窄版whole-document no-clobber API。Plan v2 reader也需在本階段以focused tests固定duplicate-key/non-finite JSON與symlink/non-regular source fail-closed。
- **Blockers:** None。

## 2026-09-04 19:14 CST — Phase 02: legacy import bridge complete

- **Status:** `In progress` → `Complete`。
- **Authorized scope:** `phases/phase-02-legacy-import-bridge.md`；只建立migration-only readers/importer、repository whole-document create與相鄰 strict-reader/tests，沒有接入startup/runtime、沒有執行真實migration，也沒有寫回或刪除legacy source。
- **Changes:** 新增`agent.conversations.legacy`的strict merge、UTC normalization、deterministic legacy turn UUID、safe source counts/fingerprint及`LegacyChromaReader`；Chroma reader用non-following file-descriptor clone把`<persist_dir>/chat_history`複製到private temporary directory，只對副本開啟Chroma client。新增`agent.conversations.migration`的structured `created|already_present|skipped|failed`結果與all-or-nothing importer；repository新增一次性validated/no-clobber whole-document create。Plan v2 JSON改為拒絕duplicate keys/non-finite constants，Plan files以`O_NOFOLLOW|O_NONBLOCK`開啟並拒絕symlink/FIFO/non-regular source。
- **Mapping result:** Chroma/Plan完整pairs保留conversation ID、caller project ID、integer order、user/assistant text與normalized event timestamp；因兩種legacy source都沒有normal/extended thinking mode，turn依checkpoint固定為completed `display-only`且不進context。所有legacy tool activities無條件drop，只留下安全count；不保存arguments/results、secret、reasoning或placeholder。
- **Verification:** 從`app/`執行`PYTHONDONTWRITEBYTECODE=1 conda run -n app poetry run pytest tests/test_conversation_migration.py tests/test_conversation_repository.py tests/test_plan_mode.py tests/test_history_rag_store.py -q`，exit 0，`82 passed, 1 warning in 0.78s`。其中migration module為20個tests（含parameterized cases）；另單跑Plan strict-reader為`32 passed, 1 warning in 0.14s`。warning均為既有LangGraph `allowed_objects` deprecation；`git diff --check`與功能commit前`git diff --cached --check`皆exit 0。
- **Fault/idempotency evidence:** executable tests證明source在staging期間或兩次read之間改變即不發布、gap/duplicate/malformed source不留target、publish前一次交付完整document、forced pre-link failure不留target、post-link directory-fsync錯誤以exact valid target作success marker、rerun不再讀legacy且bytes/turn count不變、valid target優先、invalid/identity/project mismatch target不覆寫，以及單一conversation失敗後另一個仍可成功。
- **Read-only/security evidence:** fake client刻意改寫clone後source marker不變；installed Chroma 1.5.8的real temporary collection也成功經clone讀取，來源tree逐檔bytes前後相同。Missing source不被建立，symlink/FIFO source entry在client初始化前被拒絕；Plan v1/v2 source bytes不變。Valid、malformed、unknown-field與oversized activity fixtures均證明raw payload不進canonical JSON或context。
- **Acceptance mapping:** Chroma/Plan strict malformed coverage=`test_history_rag_store.py`/`test_plan_mode.py`；conversation-atomic/source-change=`test_conversation_migration.py` staging/publish faults；rerun/target precedence=Chroma happy path與existing-target cases；不可恢復欄位=display-only mapping；欄位級identity/order/text/timestamps=real strict-reader round trips；cannot-smuggle=Plan activity cases；failure isolation=two-conversation case；真實store隔離=所有paths皆`tmp_path`且source snapshots比對不變。
- **Review:** focused review提出三項P2：confirm read早於document staging、post-link error可能留下有效target卻回failed、缺少真正不開啟source的Chroma adapter。三項均補fault/real-client tests並修正；第二次focused adapter review未發現剩餘P1/P2。
- **Evidence references:** start=`76a6bbe`；Red=`a36829e`；test tightening=`2bf5093`；Plan reader hardening=`3ddf7be`；Green=`3c58541`。
- **Limitations:** legacy display-only transcript可完整顯示，但因無法證明historical thinking mode，不產生sidebar title或model context；這是已測試的fail-closed取捨，不是遺漏。未使用Ollama/provider、credentials、`app/store/`或真實user data。
- **Blockers:** None。
- **Next action:** 重新讀durable authority後開始Phase 03 atomic write/read vertical cutover。

## 2026-09-04 19:23 CST — Phase 03: atomic lifecycle preflight

- **Status:** `Not started` → `In progress`。
- **Runtime/ownership gate:** Phase 02 completion commit=`464b761`；使用者操作前提澄清commit=`e9eaf23`；worktree clean；root=`/home/minervamuses/research-agent-workspace`、branch=`GUI`、WSL/Linux、Conda`app`、Python 3.13.14、Poetry 2.4.1。Phase 03–05保持app-offline且不操作真實user store。
- **Observed sequence before cutover:** `turn_outcome`取得per-session async lock → caller僅傳semantic input且Desktop/Python在host內臨時產生不同用途的turn ID → `_prompt_history`從`TurnJournal.recent_turns`組裝 → graph/provider/tools → `finalize_and_record`執行SafeContent、citation render/gate與Desktop final-text validator → `TurnJournal.record_turn`才建立integer ID，Plan mode立即寫Markdown；normal mode僅在window overflow、switch或shutdown寫conversation Chroma → caller收到answer。故prompt目前不是write-through，且restore/read仍合併Chroma、Plan與current memory。
- **Target sequence and single authority:** 同一session lock內：驗證caller logical UUIDv4 → load/recover canonical snapshot → exact duplicate completed直接回durable result → new或explicit retry先atomic寫`pending`並配置/保留turnNumber → 從該snapshot取latest-10 completed/context-eligible pairs，另把current semantic input恰加入一次 → graph/provider/tools →既有SafeContent/citation/final-text chokepoint → atomic transition至`completed` → 才回terminal success。Canonical `ConversationRepository`是transcript唯一writer/read/restore authority；TurnJournal只可保留暫時control/telemetry，不再寫Chroma/Plan、evict/drop或參與restore merge。
- **Identity/input mapping:** Desktop React在`requestTracked`前產生canonical lowercase UUIDv4 hex，`requestId`只作transport correlation；TS/Rust逐字轉送`turnId`；Python驗證並持久化。CLI每次agent turn產生同型ID。普通turn的display/semantic相同；one-shot Skill保留原slash input為`displayInput`，剝除command wrapper後的follow-up為`semanticInput`；restore只恢復transcript，不恢復active Skill、approval或tool policy。
- **Failure/recovery boundaries:** pending publish失敗時provider/tool不得啟動；可捕捉execution/finalization exception把已accepted turn轉`failed`，不保存raw exception或fake assistant output；completed publish未確認時caller不得收到success。Process crash無法catch，留下的唯一pending在下次ChatSession materialization/load時一次性轉`interrupted`且不自動replay；explicit retry才把同ID/turnNumber轉回pending。若publish已成功但fsync/response delivery回報不明，下一次同ID load以durable completed result為準且不重跑graph。
- **Host/read cutover:** CLI與Desktop materialize/transcript/summary/select/switch改讀同一JSON；target JSON不存在的selected legacy session先以Phase 02 importer做單會話all-or-nothing import，失敗即unavailable且不建立空transcript。第一個pending JSON已足以供basic catalog reconcile補回索引；完整catalog corruption/paging/failure UX留Phase 04。Switch/create/shutdown不再flush legacy conversation state，Python/TS/Rust移除`flushed`與flush-only error contract；暫留Plan control只改prompt/control state，不建立Plan log。
- **Preservation/test mapping:** 新增focused session lifecycle tests固定prompt-first、final-commit-before-return、provider exception、pending recovery、duplicate completed與latest-10+current-once；既有normal/extended/citation/one-shot Skill/tool-policy tests保留作route evidence。Desktop/CLI及Python/TS/Rust protocol tests固定logical ID、JSON restart/select/continue、legacy import ordering、no-flush與shutdown truthfulness；不呼叫live provider、Ollama或真實migration。
- **Verification:** 尚未執行Phase 03 tests；下一步先提交focused Red lifecycle/host/protocol contract tests，觀察預期失敗後再實作vertical slice。
- **Blockers:** None。

## 2026-09-04 19:27 CST — Phase 03: Red session lifecycle contract

- **Status:** `In progress`。
- **Changes:** 新增`app/tests/test_session_lifecycle.py`，以real temporary `ConversationRepository`與scripted graph固定六個核心契約：graph前pending含original/semantic input、stable logical ID與turnNumber；pending write failure零graph呼叫；Desktop final validator先於completed commit且commit failure不回success；completed同-ID retry不重跑graph；12個歷史turn只注入最後10 pairs且current恰一次；restore把leftover pending轉interrupted且不執行graph。
- **Verification:** 從`app/`執行`PYTHONDONTWRITEBYTECODE=1 conda run -n app poetry run pytest tests/test_session_lifecycle.py -q`，exit 1，`6 failed, 1 warning in 0.19s`。六項都在construction boundary因`ChatSession.__init__/restore`尚不接受`conversation_repository`失敗，符合Red預期；graph/provider未被誤執行。warning是既有LangGraph `allowed_objects` deprecation。
- **Evidence reference:** Red commit=`49f706a`。
- **Blockers:** None；下一步實作最小repository/session lifecycle Green，再擴到host/protocol Red。

## 2026-09-04 19:35 CST — Phase 03: Python lifecycle Green checkpoint

- **Status:** `In progress`。
- **Changes:** `ChatSession`現在注入canonical repository/project identity，在turn lock內create/append pending後才建立latest-10 prompt；normal/extended共用final chokepoint於SafeContent、citation與Desktop validator後transition completed，terminal commit完成才回`TurnOutcome`。同-ID completed request直接回durable answer；load/materialize把leftover pending一次轉interrupted；known exception嘗試寫typed failed/interrupted，失敗則保留pending供下次load recovery。Runtime prompt不再由legacy `TurnRecord`/Plan/Chroma組裝，Plan control不再建立log，journal只接收post-commit process-local diagnostics，flush成為不具durability責任的compatibility no-op。
- **Verification (Green):** `PYTHONDONTWRITEBYTECODE=1 conda run -n app poetry run pytest tests/test_session_lifecycle.py tests/test_conversation_repository.py -q`，exit 0，`23 passed, 1 warning in 0.55s`；六項新ordering/recovery tests全綠。warning仍是既有LangGraph deprecation。
- **Characterization checkpoint:** 跑`tests/test_session_eviction.py tests/test_turn_finalizer.py tests/test_thinking_session.py tests/test_skills.py -q`得到`26 failed, 57 passed`。失敗全部落在已被Phase 03刻意撤銷的Chroma eviction/flush/legacy restored-turn/Plan-log assertions，或直接繞過pending boundary呼叫internal `finalize_and_record`的舊測試；normal、extended與one-shot核心路徑其餘57項通過。這些是待改寫的obsolete specifications，不是保留行為 regression，phase仍維持`In progress`。
- **Evidence reference:** Python lifecycle commit=`85730ee`。
- **Blockers:** None；下一步把相關tests改成canonical public-turn assertions，並完成CLI/Desktop/protocol vertical slice。

## 2026-09-04 19:39 CST — Phase 03: Desktop durable-turn protocol Red

- **Status:** `In progress`。
- **Changes:** Python與TypeScript contract tests固定`session.turn`由caller提供canonical UUIDv4 hex `turnId`，terminal result回傳同一logical ID與`turnNumber/state/accepted/persisted`；React reducer tests固定active logical ID與mismatched result fail-closed；shutdown contract移除legacy flush-only fields/errors並只回真實status。
- **Verification (Python Red):** `PYTHONDONTWRITEBYTECODE=1 conda run -n app poetry run pytest tests/test_desktop_protocol_contract.py -q`，exit 1，`2 failed, 81 passed, 1 warning`；失敗精確位於尚未更新的`requiredParams/resultDataSchemas/errorCodes`。
- **Verification (TypeScript Red):** `conda run -n app node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts tests/answer_stream.test.ts`，exit 1，`4 failed, 93 passed`；失敗精確位於active turn未保存logical ID、未拒絕mismatched ID，以及protocol尚不接受`turnId`/lifecycle fields。
- **Evidence reference:** Red commit=`2ffebb5`。
- **Blockers:** None；下一步同步更新language-neutral contract、TypeScript與Rust validators，再接通React/Python host。

## 2026-09-04 20:12 CST — Phase 03: protocol/host/fixture Green checkpoint

- **Status:** `In progress`；尚未完成全部required verification與acceptance mapping。
- **Protocol lockstep changes:** language-neutral v1 contract與fixtures、Python、TypeScript、React及Rust同步要求caller-owned canonical UUIDv4-hex `turnId`。Answer result回同一ID、`turnNumber`、`state=completed`、`accepted=true`、`persisted=true`；display-only local command回同一ID但`state=null`、`accepted=false`、`persisted=false`。Python/TypeScript/Rust移除`flushed`與flush-only errors；Rust graceful shutdown改由有效Python ACK加child exit判定。React在dispatch前建立logical ID、保存至active turn並拒絕mismatched result；transport request ID仍只作correlation。
- **Protocol verification:** `tests/test_desktop_protocol_contract.py -q` exit 0，`85 passed, 1 warning`；從`app/desktop/`執行`node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts tests/answer_stream.test.ts` exit 0，`99 passed`；`./node_modules/.bin/tsc --noEmit` exit 0；`cargo test --manifest-path src-tauri/Cargo.toml protocol::tests` exit 0，`29 passed`。沒有install、npx、full npm/build或full Cargo。
- **CLI changes/verification:** CLI在每個agent turn前產生logical UUIDv4 hex並同時傳original display input與semantic input；one-shot Skill保留slash display文字但只把follow-up送模型；exit不再flush。`tests/test_chat_cli.py -q` exit 0，`19 passed, 1 warning`。
- **Desktop Python changes:** create/materialize/select/transcript/summary改用同一`ConversationRepository`；selected legacy-only session在materialization前經Phase 02 importer，runtime不merge Chroma/Plan/current memory。Caller `turnId`原樣送Session，completed lifecycle fields經service驗證後才回；switch/create/shutdown不呼叫legacy flush。Startup只做Phase 03最低限度的健康JSON→matching project catalog補登；pending JSON且catalog registration落後的restart test直接證明list可發現、title/turn count可讀且model/session factory零呼叫。
- **Desktop/fixture verification:** `tests/test_desktop_service.py -q` exit 0，`46 passed, 1 warning`。Fixture改為canonical pending→completed/failed/interrupted唯一active authority；延遲synthetic work期間test直接從JSON讀到pending，provider failures讀到failed；safe tool summary不保存raw arguments/results；switch/shutdown前後legacy Plan bytes不變。`tests/test_desktop_fixture.py -q` exit 0，`15 passed, 1 warning`。
- **Core lifecycle replacement:** 舊`test_session_eviction.py`已改為6個real-temp-repository tests，直接驗證graph前prompt durable、pending write failure時graph零呼叫、provider failure→failed、reload pending→interrupted且不replay、completed duplicate byte-identical/no graph、latest-10+current-once且legacy flush no-op。與`test_session_lifecycle.py`合跑exit 0，`12 passed, 1 warning`。
- **Still-failing observed check:** `tests/test_memory.py tests/test_state.py tests/test_turn_finalizer.py tests/test_thinking.py tests/test_thinking_session.py tests/test_skill_runtime.py tests/test_citation_gate.py -q --tb=short` exit 1，`16 failed, 127 passed, 1 warning`。15項是`test_turn_finalizer.py`直接繞過新pending boundary呼叫internal finalizer或要求Plan/eviction寫入；1項是`test_thinking_session.py`仍要求Plan log。這些obsolete specs正在改寫，但在實際綠燈前Phase 03維持`In progress`。
- **Manual inspection evidence:** 已逐段追蹤before/target sequence、normal/extended共用`finalize_and_record` chokepoint、citation/final-text validator排序、Session→CLI/Desktop→TS/Rust→React identity flow及Desktop read/restore boundary。沒有發現受支援的external protocol-v1 consumer；live checkout為同一source tree lockstep app。Phase 03–05仍是app-offline中間狀態，未操作真實store、credentials、provider或Ollama。
- **Evidence references:** protocol Green=`f0fd27d`；CLI=`1845510`；Desktop host=`997ee1e`；catalog Red/Green=`5f54267`/`ff9290e`；fixture=`efc0ae8`；lifecycle replacement=`02233f8`。
- **Blockers:** None。下一步完成canonical Desktop conversation journey與finalizer/thinking obsolete-spec改寫，跑完整Phase 03 required command sets後再判斷Complete。

## 2026-09-04 20:30 CST — Phase 03: write-through vertical slice complete

- **Status:** `In progress` → `Complete`。
- **Final changes:** canonical Desktop journeys現在直接驗證JSON-only create/send/restart/select/continue、legacy一次性import、A→B→A context隔離、catalog落後補登、safe tool summary、caller logical-ID duplicate不重跑model，以及switch/shutdown零legacy flush。Plan-control tests保留strict legacy PlanLog reader coverage，但active normal/extended/Plan turns全走相同pending→completed repository lifecycle，不建立或修改Markdown，也不寫Chroma。Finalizer/thinking tests改由真實pending boundary進入，保留citation/trace/fusion assertions。
- **Material failure and correction:** 額外執行`tests/test_desktop_server.py -q --tb=short`最初exit 1，`4 failed, 8 passed`；三項因fixture仍漏傳required `turnId`或期待removed `flushed`欄位而走錯protocol branch，另一項揭露`agent/desktop/server.py` EOF cleanup仍發出`flush_failed`與「could not flush」文案。Production residue與fixtures於`a184bfc`改成一般`shutdown_failed`/`SHUTDOWN_FAILED`語意；重跑server module exit 0，`12 passed, 1 warning`，再與protocol contract合跑為`97 passed, 1 warning`。全樹residue search只剩兩個「SHUTDOWN_FLUSH_FAILED不得存在」的negative assertions。
- **Required Python verification:** 從`app/`執行phase列出的core command，exit 0，`149 passed, 1 warning in 2.08s`；host/protocol command exit 0，`247 passed, 1 warning in 4.54s`；policy/tool/extension/Bash preservation command exit 0，`31 passed, 1 warning in 1.06s`。warning皆為既有LangGraph `allowed_objects` deprecation，沒有live provider、Ollama或真實store操作。
- **Required Desktop verification:** 從`app/desktop/`執行`conda run -n app node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts tests/conversations.test.ts`，exit 0，`100 passed`；`conda run -n app ./node_modules/.bin/tsc --noEmit`，exit 0；`conda run -n app cargo test --manifest-path src-tauri/Cargo.toml protocol::tests`，exit 0，`9 passed, 20 filtered out`。未install、未跑npx、production build或完整Cargo suite。
- **Acceptance mapping:** (1) prompt-first與pending-write zero-provider由兩組lifecycle fault tests證明；(2) SafeContent→citation→Desktop validator→completed commit→return由finalizer ordering與commit-failure test證明；(3–4) normal/extended共用final chokepoint且latest-10/current-once綠燈；(5–6) failed/interrupted/completed restart、no replay、stable numbering與拒絕legacy restored turns綠燈；(7) citation/SafeContent/thinking/tool policy/Bash checks綠燈；(8–9) CLI/Desktop JSON authority、legacy import與React→TS→Rust→Python logical ID/duplicate journeys綠燈；(10) Plan control只改hint且不寫legacy source；(11) CLI/Desktop original/semantic input、one-shot Skill cleanup與forged unavailable tool拒絕皆有focused coverage；(12) pending與completed JSON的catalog-lag restart都不重跑model；(13) switch/shutdown、三語protocol與EOF path皆無active flush或flush-only success/error語意。
- **Fresh review:** 獨立read-only reviewer從clean `88daa78`執行required checks，並在`a184bfc`後重查live code；逐條13項結果皆PASS，沒有P1/P2或completion blocker。人工inspection確認`turn_outcome`在graph前完成pending publish，`finalize_and_record`在既有安全/引用/Desktop validator後publish completed且之後才return；active host read/restore只使用canonical repository，legacy source僅存在於explicit importer boundary。`recall_history` query仍存在但沒有新conversation write caller，依Phase 06既定scope退場。
- **Evidence references:** finalizer/thinking tests=`314a30c`；Desktop journeys=`47d81e0`；Plan-control cutover tests=`88daa78`；server flush-residue fix=`a184bfc`；Phase 03 implementation commits自`85730ee`至`a184bfc`；completion HEAD before documentation=`a184bfc50a7f`。
- **Blockers:** None。
- **Next action:** 重新閱讀durable authority並開始Phase 04 host/catalog/retry hardening；不得把本phase的basic catalog fallback誤當Phase 04完整corruption/retry UX。

## 2026-09-04 20:39 CST — Phase 04: host/catalog/retry preflight

- **Status:** `Not started` → `In progress`。
- **Runtime/ownership gate:** Phase 03 completion commit=`955b8dd`、worktree clean；仍使用root=`/home/minervamuses/research-agent-workspace`、branch=`GUI`、WSL/Linux與Conda`app`。Phase 04保持app offline，只使用temporary fixtures，不讀寫真實user store、provider、Ollama或credentials。
- **Identity and retry mapping:** wire `requestId`只作transport correlation；caller建立的canonical UUIDv4 `turnId`是durable idempotency identity；`turnNumber`只作conversation ordering。Completed同ID可直接回既有結果；failed/interrupted只有帶明確`retry=true`的使用者動作才可用同ID重跑；restart不得auto replay。現有request尚缺explicit retry欄位，Python也把每次送出當retry，列為Red gap。
- **UI state table:** not accepted=`state:null, accepted:false, persisted:false`且不建立record；accepted pending/failed/interrupted須回或由transcript恢復同一turn ID；completed須可在result delivery遺失後用同ID取回；display-only須先pending、後執行command、再terminal commit，且永不進model context。現有failure envelope、TS error mapping與completed-only transcript不足以表達此表，列為Red gap。
- **Catalog reconciliation matrix:** 有效catalog+健康JSON orphan可補登；catalog-only missing JSON保留unavailable且不得造空transcript；單一malformed/oversized/version-mismatch JSON局部隔離；catalog整檔missing或malformed則只由健康JSON summary重建，且不得修改conversation files。有效catalog保留project display/order；重建時local使用既有default project name，其餘project display以stable project ID作deterministic fallback，sessions依`createdAt`再conversation ID排序。
- **Transcript/command gaps:** 現有summary wire shape缺`createdAt`，transcript只輸出completed pair，因此無法正確支援50-turn paging與pending/failed/interrupted/display-only restore。CLI/Desktop local slash handlers目前在canonical pending write前執行；Green需共享display-only lifecycle並保留extension/prune既有one-shot approval、active-turn switch guard與approval不持久化規則。
- **Protocol consumers:** 此checkout的language-neutral fixture、Python、TypeScript、Rust與React是同一lockstep app；未發現受支援的external v1 consumer。Phase 05才移除Plan fields，本階段只補turn lifecycle/retry，不越界清除Plan UI/protocol。
- **Verification:** 尚未執行Phase 04 tests；下一步先提交focused Red tests，固定catalog rebuild、完整transcript/error lifecycle、explicit retry與display-only prompt-first contract。
- **Blockers:** None。

## 2026-09-04 22:26 CST — Phase 04: host/catalog/retry cutover complete

- **Status:** `In progress` → `Complete`。
- **Catalog and transcript changes:** Desktop startup/list now reconciles the catalog from bounded canonical conversation JSON scans. Healthy orphans are registered; a missing or malformed whole catalog is rebuilt without rewriting conversation files; malformed conversation files are isolated; catalog-only missing entries remain visible as unavailable. Registration happens immediately after the first durable pending prompt, before provider/tool execution. Summary and bounded transcript DTOs now preserve `createdAt`, JSON-derived title/turn count/timestamps, turn order, and pending/completed/failed/interrupted/display-only states; 50-turn paging and A→B→A/restart journeys are covered directly.
- **Identity, retry, and UX changes:** wire `requestId` remains correlation-only, caller-owned canonical `turnId` remains the durable identity, and `turnNumber` remains ordering-only. Python/TypeScript/Rust now require strict explicit `retry`; completed same-ID delivery returns the durable result without rerunning work, while failed/interrupted conversational retries require the same ID and an explicit user action. React distinguishes not-accepted draft failures from accepted lifecycle records, restores terminal/nonterminal states from JSON, retains an uncertain in-flight delivery for explicit recovery, and does not duplicate or recount a result already restored in the transcript.
- **Display-only and local actions:** CLI/Desktop local commands write the original display prompt as pending before their handler runs, commit only bounded visible output, never enter model context, and recover a crash as interrupted without automatic replay. Desktop `extensions.apply` is now the same prompt-first one-shot lifecycle: exact approved binding hashes and a frozen logical turn request are validated, the durable prompt precedes preview consumption/mutation, completed delivery is replayable without reapplying, and failed/interrupted operations require a fresh preview and approval. Approval tokens, preview payloads, raw metadata, provider payloads, and tool arguments/results are not persisted.
- **Material failures and corrections:** focused extension Green tests initially had `3 failed` because the fake preview omitted the production `registry` contract; the fixture was corrected instead of weakening validation. A fresh reviewer later found that delivery recovery after backend restart could append and count an extension result already present in the restored transcript; `App.tsx` now deduplicates against both restored transcript items and live turns before append/count, and the reviewer rechecked the fix with no remaining P1/P2/P3 finding.
- **Required Python verification:** from `app/`, `pytest tests/test_desktop_conversations.py tests/test_desktop_service.py tests/test_desktop_server.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py -q` exited 0 with `218 passed, 1 warning`; the policy/local-command preservation command plus `tests/test_chat_cli.py` exited 0 with `84 passed, 1 warning`; `tests/test_session_lifecycle.py tests/test_session_eviction.py -q` exited 0 with `12 passed, 1 warning`. Warnings are the existing LangGraph `allowed_objects` deprecation.
- **Required Desktop verification:** from `app/desktop/`, the final `node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts tests/conversations.test.ts tests/trust.test.ts` exited 0 with `122 passed`; `./node_modules/.bin/tsc --noEmit` exited 0. Rust protocol tests exited 0 with `11 passed`; `backend::tests::child_crash_fails_pending_and_restart_is_user_driven` exited 0 with `1 passed`. `git diff --check` was clean before the implementation commit.
- **Acceptance mapping:** catalog orphan/missing/malformed/full-corruption cases and JSON-derived summary/paging are fixed by conversation/service tests; prompt-first registration, completed-before-ack, explicit retry, stable IDs, switch guards, and restart/no-auto-replay are fixed by lifecycle/service/protocol tests across all three languages; React reducer/trust tests fix draft versus accepted failures and uncertain delivery recovery; CLI/display-only and extension journey tests fix original-versus-semantic input, no-context behavior, and one-shot approval/replay boundaries. Existing normal→extended→restart, A→B→A, Bash policy, approval clearing, and safe-content assertions remain green.
- **Fresh review:** an independent read-only reviewer reran extension-focused Python (`6 passed`), React trust-state (`6 passed`), and `git diff --check`, then inspected the corrected restored-transcript dedupe. Final result: no evidence-backed P1/P2/P3 blocker.
- **Limitations:** no live provider, Ollama, credentials, real user store, full npm/build, full Cargo suite, or Tauri bundle was used; the larger release matrix remains Phase 07 scope.
- **Evidence references:** Phase start=`deb6ae2`; catalog Red/Green=`15ed991`/`d0911a9`; display-only Red/Green=`a1d81db`/`1fe8b3c`; retry/protocol/React Red=`fbec211`/`0bfd47d`; protocol/catalog/UX/Rust/CLI Green=`b8a999f`, `d255c28`, `adfb72d`, `526425b`, `5bdc913`; extension apply Red/Green=`2483e77`/`68e413a`.
- **Blockers:** None。
- **Next action:** reread durable authority and begin Phase 05 removal of Product Plan Mode. Plan fields may now be removed because active durability, restore, retry, and display-only lifecycle no longer depend on them.

## 2026-09-04 22:31 CST — Phase 05: Product Plan Mode removal preflight

- **Status:** `Not started` → `In progress`。
- **Runtime/ownership gate:** Phase 04 completion commit=`b546731`、worktree clean；root=`/home/minervamuses/research-agent-workspace`、branch=`GUI`、WSL/Linux、Conda `app`，Python 3.13.14、Poetry 2.4.1、Node 24.18.0、Cargo 1.97.1。仍只使用temporary fixtures，不操作真實store、legacy files、provider、Ollama或credentials。
- **Active Product Plan surfaces:** exact residue inventory found CLI `/mode`, banner/status fields, session/journal plan state and hint, extended-thinking hint injection, Desktop `session.set_mode`, control snapshots, session DTO fields, fixture controls, protocol-v1 contract/fixtures plus Python/TS/Rust validators, and React Plan buttons. The journal still contains unreachable Plan writer branches even though canonical completion no longer calls them; they remain removal scope rather than a supported compatibility path.
- **Migration/historical allowlist:** `AgentConfig.plan_logs_dir`, protected-root handling, strict v1/v2 Plan log parsing, legacy fixture bytes, and `agent.conversations` importer calls remain solely for non-destructive legacy migration. Historical `harness/`, `note/`, and unrelated `issue/` records are not rewritten. Ordinary extension planning models, test plans, URLs containing `model`, and natural-language planning are not Product Plan Mode residues.
- **Preserved controls:** `/thinking`, `session.set_thinking`, `thinkingMode`, normal/extended orchestration, proposer/reviewer/reviser/fusion, Skills, Citation, SafeContent, approvals, and canonical pending/completed ordering remain unchanged except for direct type/caller cleanup caused by removing Plan fields.
- **Protocol boundary:** repository search still finds only the lockstep Python/TypeScript/Rust/React source checkout and no supported external protocol-v1 consumer. Old `session.set_mode` input must become an unknown method; no deprecated alias or compatibility adapter will be retained.
- **Verification:** Phase 05 characterization/Red checks have not yet run. Next step is to record the current focused baseline, then commit tests that require the removed CLI/protocol/UI surface while retaining legacy parser and extended-thinking coverage.
- **Blockers:** None。

## 2026-09-04 22:37 CST — Phase 05: removal contract Red

- **Status:** `In progress`。
- **Characterization baseline:** before test changes, the required Python command exited 0 with `350 passed, 1 warning`; Desktop protocol/conversation tests exited 0 with `106 passed`, TypeScript `tsc --noEmit` exited 0, and Rust protocol tests exited 0 with `11 passed`. This proves the starting Plan-enabled interface was internally consistent; it is not evidence of the removal target.
- **Red changes:** added focused Python contracts requiring the CLI registry to omit `/mode` while retaining `/thinking`, `ChatSession` to expose no Plan control/hint API, the strict legacy Plan reader to expose no writer methods, and create/select protocol DTOs plus methods to omit Plan fields/method while retaining normal/extended thinking. TypeScript now independently checks the language-neutral contract and React source for the same removal/preservation boundary.
- **Red verification:** `pytest tests/test_plan_mode_removal.py -q` exited 1 with `4 failed, 1 warning`; failures are exactly the still-present CLI command, Session API, Plan writer methods, and protocol surface. `node --test --experimental-strip-types tests/protocol.test.ts` exited 1 with `97 passed, 1 failed`; the single failure is the still-present `session.set_mode`. An initial uncommitted test draft referenced a module-local fixture and produced one setup error; that test was corrected to use class-level API assertions before the Red commit and the recorded rerun contains no setup/collection error.
- **Evidence reference:** Red commit=`d7bb592`。
- **Blockers:** None；next implement consumer-to-producer removal while preserving raw legacy v1/v2 parser coverage.

## 2026-09-04 23:04 CST — Phase 05: Product Plan Mode removal complete

- **Status:** `In progress` → `Complete`。
- **Changes:** React controls、CLI `/mode`、Python/TypeScript/Rust protocol fields與`session.set_mode`、session/journal Plan state/hints、writer branches、`TurnRecord.log_path`及Plan-only tests均已移除。原`turns/plan_log.py`收斂為`conversations/legacy_plan.py`，只保留bounded strict v1/v2 reader；normal execution不import它，Desktop只在explicit legacy migration boundary使用。`/thinking`、`thinkingMode`與normal/extended orchestration保留。
- **Legacy/non-destruction:** migration tests全部使用`tmp_path` synthetic files，逐檔bytes-before/after assertion仍通過；沒有讀寫、移動或刪除真實`app/plan_logs/`或user store。`.gitignore`繼續保護legacy目錄，current runtime不再建立或append Plan log。
- **Verification (Python):** 從`app/`執行Phase-required selector加`test_plan_mode_removal.py`、`test_conversation_migration.py`、`test_memory.py`、`test_history_recall_routing.py`、`test_turn_finalizer.py`與Desktop conversation coverage，exit 0，`438 passed, 1 warning in 4.85s`。先前純required+direct affected集合亦為`430 passed, 1 warning in 5.61s`；warning均是既有LangGraph `allowed_objects` pending-deprecation。
- **Verification (Desktop):** 從`app/desktop/`執行`node --test --experimental-strip-types tests/protocol.test.ts tests/conversations.test.ts`，exit 0，`108 passed`；`./node_modules/.bin/tsc --noEmit` exit 0；`cargo test --manifest-path src-tauri/Cargo.toml protocol::tests` exit 0，`11 passed`。舊`session.set_mode` fixture現在明確得到`PROTOCOL_INVALID`，不是映射成thinking mode。
- **Residue audit:** tracked與`--untracked` exact search覆蓋`plan mode|plan_mode|session.set_mode|/mode|planLog|plan_log_path|enter/resume/exit_plan_mode`。剩餘app source只在`conversations/legacy_plan.py`、synthetic migration fixtures及negative removal tests；active docs只把`plan_logs`標成唯讀migration input。`harness/`、歷史`issue/`/`note/`與extension manager的普通planning model名稱依allowlist保留。
- **Documentation:** root operation guide、Skills guide、agent/turn lifecycle docs、`.gitignore`與`for_agents`已移除產品模式說明並改述canonical pending/completed JSON順序。`manage_for_agents.py check` exit 0（僅提示九個已tracked files受ignore規則影響）；`git diff --check` exit 0。
- **Review:** independent read-only review先找到obsolete `TurnRecord.log_path`與現行history-routing test中的Plan-only說法，兩項均修正並重跑focused checks；最終確認active runtime無Plan surface、legacy reader無writer API、thinking route保留，沒有未解blocking finding。詳見`code_review/phase-05-remove-plan-mode-review.md`。
- **Acceptance mapping:** public surface removal由Python/TS/Rust protocol negative tests、CLI registry與React source assertions覆蓋；no-new-log與migration-only import由API/residue inspection及v1/v2 parser tests覆蓋；normal/extended、Skills、Citation與canonical lifecycle由438-test集合覆蓋；legacy preservation由temporary source byte assertions覆蓋。
- **Evidence references:** start=`090472e`；Red=`d7bb592`；Red log=`0c04dd6`；Green=`e4f4107`；active docs=`e37bce5`。
- **Limitations:** 未使用live provider、Ollama、credentials、真實legacy資料、full npm/Cargo suite或Tauri build；final broad matrix仍是Phase 07 scope。
- **Blockers:** None。
- **Next action:** reread durable authority and begin Phase 06 retirement of conversation-history Chroma and `recall_history`, while preserving document RAG Chroma/Ollama.

<!--
Material implementation events append with this shape:

## YYYY-MM-DD HH:MM TZ — Phase NN: event

- Status: previous → new
- Authorized scope: link to phase file
- Initial worktree/overlap: exact user-owned changes relevant to this phase
- Changes: concise observed change
- Verification: exact commands/procedures and results
- Acceptance mapping: criterion → evidence reference
- Review: findings/sign-off when actually performed
- Limitations: skipped/unavailable evidence and residual risk
- Blockers: current blockers or None
- Next action: next eligible action from PLANS.md
- Evidence references: context/review/log/artifact/commit if one exists
-->

## 2026-09-04 23:12 CST — Phase 06: conversation-history Chroma retirement preflight

- **Status:** `Not started` → `In progress`。
- **Runtime/ownership gate:** Phase 05 completion commit=`a08faae`、worktree clean；root=`/home/minervamuses/research-agent-workspace`、branch=`GUI`、WSL/Linux、Conda `app`。仍只使用temporary fixtures，不操作真實conversation store、legacy Chroma、provider、Ollama或credentials。
- **Boundary map:** normal session目前由`ChatSession`建立`ChatHistoryStore`，再注入graph、tool inventory與extended-thinking proposer；`TurnStore` construction仍存在，但write/eviction/flush已無production caller。Desktop的`LegacyChromaReader`只在canonical JSON缺失時進入migration boundary，但暫時借用active store parser。
- **Separation decision:** 將bounded strict legacy role-pair parser與常數移入`agent.conversations.legacy`後，可刪除active `agent.history_rag`與dead `TurnStore`，不需修改`app/rag/`或dependency manifests。保留`agent_recent_turns_window`作canonical JSON最近context視窗，保留document RAG所需`chromadb`、`langchain-chroma`與`langchain-ollama`。
- **Canonical root:** `ConversationRepository.root`是authority；Phase Green會從同一repository boundary輸出resolved、bounded、escaped path到dynamic system guidance與`/status`，但不新增filesystem權限或繞過Bash approval。
- **Baseline verification:** 從`app/`執行Phase 06指定Python command，exit 0，`177 passed, 1 warning in 4.60s`；warning是既有LangGraph `allowed_objects` pending-deprecation。此基線未啟動Ollama。
- **Blockers:** None；下一步提交focused Red tests，固定active history removal、migration-only reader、canonical root與approval-gated exact-text journey。
