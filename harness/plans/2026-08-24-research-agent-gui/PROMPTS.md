# Plan Prompts: Research Agent Linux Desktop GUI

- **Plan ID:** `2026-08-24-research-agent-gui`
- **Plan root:** `harness/plans/2026-08-24-research-agent-gui/`

一次只使用一個 prompt。所有 prompt 都必須先讀 repository root 的 `AGENTS.md` 與本 bundle；它們不會隱含批准下一個 phase、依賴安裝、external call、destructive action 或 Git mutation。

目前唯一已存在的 detailed contract 是：

`harness/plans/2026-08-24-research-agent-gui/build/phase-00-refresh-gui-assumptions.md`

未來 phase 必須先取得自己的 exact path/write-set approval；在使用通用 prompt 時，將 `PHASE_CONTRACT_PATH`、`PHASE_CONTEXT_PATH` 和 `PHASE_REVIEW_PATH` 替換成該次已批准的實際路徑。

## 1. Refresh Repository Evidence — Read Only（重新蒐集 repository 證據）

~~~text
讀取 repository root 的 AGENTS.md，以及：
- harness/plans/2026-08-24-research-agent-gui/GOALS.md
- harness/plans/2026-08-24-research-agent-gui/PLANS.md
- harness/plans/2026-08-24-research-agent-gui/build-log.md
- 當前 detailed phase contract
- GUI/00.md 到 GUI/18.md（只作 provenance）

只做唯讀 inspection，並先驗證工作根目錄、Ubuntu/WSL/Linux shell、Conda app、Git 與語言/package tools屬於預期runtime。Windows executable、system Python或一般bash找不到conda時，不得自行混用環境。

把結果分成：
1. confirmed facts；
2. strong inferences；
3. load-bearing assumptions；
4. unresolved unknowns。

特別核對 ChatSession/TurnOutcome/progress、RAG root identity/read filters/ingest stdout、extension preview/apply、bash non-TTY policy、shutdown resource ownership、persistent paths、existing tests、worktree changes與目前phase的exact write set。

不要修改任何檔案，不要安裝依賴，不要跑live provider，不要把GUI舊稿或歷史test紀錄當成current evidence。回報哪些assumptions應validated、rejected、superseded或留待owner phase。
~~~

## 2. Red-Team the Plan and Assumptions（對計劃與假設做對抗審查）

~~~text
你是fresh adversarial planning reviewer。先讀：
1. harness/plans/2026-08-24-research-agent-gui/GOALS.md
2. repository root AGENTS.md
3. live repository與當前runtime evidence
4. current phase contract

先形成獨立判斷，再讀PLANS.md、build-log.md和builder narrative。

不要潤飾文字；嘗試推翻計劃。尋找：
- Tauri/Rust/Conda/NDJSON architecture錯誤；
- CLI/internal object被誤當desktop contract；
- secret、tool args/results、stderr或raw HTML跨trust boundary；
- shutdown/approval/prune/extension replay與recovery漏洞；
- current multi-root identity被prior GUI舊敘述覆蓋；
- acceptance criteria可在實際UI、persistent result或process lifecycle錯誤時仍通過；
- unnecessary scope、premature dependency/schema/API change；
- tests、manual WSLg或external checks的不可用缺口。

每個finding提供severity、exact evidence、downstream impact、cheapest decisive check與required remediation。不要實作，也不要自行批准下一phase。
~~~

## 3. Author or Refresh the Next Phase Contract（撰寫或刷新下一階段契約）

~~~text
讀取：
- harness/plans/2026-08-24-research-agent-gui/GOALS.md
- harness/plans/2026-08-24-research-agent-gui/PLANS.md
- harness/plans/2026-08-24-research-agent-gui/build-log.md
- relevant phase context/review files
- repository root AGENTS.md
- current live repository

重新評估所有仍承重的assumptions，先提出下一phase的exact contract path和frozen write set，等待明確批准後才建立或修改PHASE_CONTRACT_PATH。

Contract必須定義一個bounded state transition、goal traceability、exact scope/non-goals、dependencies與human decisions、confirmed facts、assumptions to falsify、interfaces/invariants、red或characterization baseline、planned sequence、observable acceptance、exact verification matrix、independent review、Security/Compatibility、Rollback/Recovery/cleanup、stop conditions和approval gate。

若是dependency、public API/protocol/schema、超過三個production files、bash/RAG callback、live/external/destructive或Git action，必須分開列批准。不要實作，不要啟動該phase，也不要默認後續phase。
~~~

## 4. Execute One Approved Phase — Builder（只執行一個已批准階段）

~~~text
只執行已由使用者批准的PHASE_CONTRACT_PATH。開始前讀：
- harness/plans/2026-08-24-research-agent-gui/GOALS.md
- harness/plans/2026-08-24-research-agent-gui/PLANS.md
- repository root AGENTS.md
- relevant context/review/build-log evidence
- current live repository與worktree status

先重新通過Linux/WSL/Conda runtime gate。遵守contract的exact write set與validation budget；先建立planned red/characterization evidence，再做最小scoped change，run focused checks，只在checks持續成立時做必要refactor，最後執行contract列出的broader verification。

Python保持persistent/domain authority；Rust只擁有process/IPC；React不取得任意shell/fs。Default tests使用fake providers和temporary state；mutating transport failure不可auto-replay。

若assumption被推翻、required check失敗、evidence衝突、rollback不安全、scope擴張、需要未批准dependency/API/schema/files、external/destructive/credential/Git action，立即停止。不要開始另一phase。
~~~

## 5. Independently Verify a Phase — Evaluator（獨立驗證階段）

~~~text
你是fresh independent evaluator。先讀GOALS.md、repository root AGENTS.md、live repository/running system與PHASE_CONTRACT_PATH；在讀builder narrative前形成初始判斷。

驗證actual user-visible behavior與persistent/process outcome，而不只看event或unit tests。依contract檢查：
- preserved CLI/domain/RAG/citation/extension/tool-policy invariants；
- protocol ordering/correlation/redaction；
- backend/session readiness和shutdown/crash cleanup；
- busy、approval、mutation replay、prune/extension freshness；
- Security、Privacy、Compatibility、Recovery與cleanup；
- WSLg/manual UI、keyboard/a11y與truthful capability wording。

使用contract允許的strongest practical oracle；不要碰真實store/keys/providers，除非有逐項批准。結果只能是pass、pass with explicit accepted limitations或request changes。每個finding附evidence、impact和remediation；不要自行實作。

只在review實際發生後，依另行批准的write set寫入PHASE_REVIEW_PATH。不要批准或開始下一phase。
~~~

## 6. Update Phase Context（更新階段 context）

~~~text
只更新已批准的PHASE_CONTEXT_PATH。記錄會影響後續工作的material discoveries、user decisions、scope changes、validated/rejected/superseded assumptions、architecture/interface decisions與rationale、constraints、blockers、unavailable evidence和downstream implications。

不要寫routine narration、transcript、full command output、credentials、copied plans或completion status。以canonical path/reference連結證據；observed progress/result屬於build-log.md。

若需要新增未在frozen write set的檔案，停止並請求批准。不要修改AGENTS.md、implementation files或下一phase contract。
~~~

## 7. Update the Build Log from Observed Evidence（依觀察證據更新 Build Log）

~~~text
只更新 harness/plans/2026-08-24-research-agent-gui/build-log.md。

根據目前phase實際觀察，記錄exact commands/procedures、concise results、written paths、provider calls、review state、failed/skipped/unavailable checks、blockers、limitations、rollback/recovery與evidence references。

Activity log採append-only；若舊entry錯誤，新增correction並更新summary到目前受支持狀態，不刪failed history。不要把phase contract中的planned command寫成pass evidence；缺required evidence時保持In progress或Blocked。不要開始下一phase。
~~~

## 8. Close the Phase and Replan（關閉階段並重新規劃）

~~~text
讀取GOALS.md、PLANS.md、completed phase contract、phase context、build-log.md、review artifacts、repository root AGENTS.md與live repository。

判斷該phase是Complete、In progress、Blocked或Superseded。只有acceptance、required checks、independent review、Security/Compatibility/Recovery/cleanup和limitations都有observed evidence時才可Complete。

重新評估所有remaining assumptions和roadmap。先提出PLANS.md與下一phase contract的exact write set；未獲批准前不要建立下一contract。Preserve prior evidence，對outdated decisions明確標記superseded及replacement。

不要實作下一phase，不要安裝依賴，不要做Git mutation。
~~~

## 9. Final Integration Audit（最終整合稽核）

~~~text
你是fresh final reviewer。從：
1. harness/plans/2026-08-24-research-agent-gui/GOALS.md
2. repository root AGENTS.md
3. live repository與running Linux/WSLg system
開始，不要先接受implementation narrative。

逐項檢查每個SC、INV、Non-Goal、public/domain interface、persistent data ownership、multi-root identity、Security/Privacy、Compatibility、approval、shutdown/Recovery、cleanup、delivery command、skipped check與accepted limitation。

要求actual GUI/user-flow、process和persistent outcome證據；green phase-local unit tests或「event完成」不能單獨證明goal完成。確認沒有secret/raw payload leak、orphan child、fake resume/cancel/token stream/score、unapproved mutation或Windows/standalone承諾。

最後只回報overall complete、complete with accepted limitations或requires changes，並附exact evidence與remaining actions。不要自動開始bundle、Windows或其他Non-Goal工作。
~~~
