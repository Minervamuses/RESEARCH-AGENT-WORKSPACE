# Canonical Conversation JSON 與 Plan Mode 退場 — Build Log

本檔是 runtime phase status與 observed implementation/verification evidence的唯一 source of truth。Plan描述預定工作；本檔只記真正發生的結果。

## Phase summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Canonical conversation contract | Complete | 2026-09-04 18:20 CST | 2026-09-04 18:44 CST | Contract, Red/Green tests, review, and commits below | None |
| 02 — Legacy import bridge | In progress | 2026-09-04 18:48 CST | — | Preflight and mapping checkpoint below | None |
| 03 — Write-through turn lifecycle | Not started | — | — | — | None |
| 04 — Host/catalog/retry cutover | Not started | — | — | — | None |
| 05 — Remove Product Plan Mode | Not started | — | — | — | None |
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
