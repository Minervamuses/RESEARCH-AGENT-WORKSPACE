# Canonical Conversation JSON 與 Plan Mode 退場 — Build Log

本檔是 runtime phase status與 observed implementation/verification evidence的唯一 source of truth。Plan描述預定工作；本檔只記真正發生的結果。

## Phase summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Canonical conversation contract | In progress | 2026-09-04 18:20 CST | — | Preflight and schema checkpoint below | None |
| 02 — Legacy import bridge | Not started | — | — | — | None |
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
