# 執行紀錄

本檔是本計劃唯一的狀態來源。目前只完成了撰寫與 2026-11-20 的修訂（CA5）；**C1–C10 都還沒有開始，也沒有執行過任何實作或產品測試。**

「撰寫紀錄」中 CA0–CA4 提到的步驟編號是當時的編號；CA5 重新整理了 C2、C3、C7、C8 的步驟，現行編號以 `build/phase-*.md` 為準。

## 目前狀態

狀態只用四種：

- `Not started`：尚未開始。
- `In progress`：已有步驟 commit，但階段驗收未完成。
- `Blocked`：在「阻塞」欄寫明缺少的前提與受影響的步驟。
- `Complete`：階段驗收已觀察到並記錄。

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| C1 | In progress | `evidence/C1-S1/relocation.md` | — | C1-S2 建立基線 |
| C2 | Not started | — | — | 等 C1 |
| C3 | Not started | — | — | 等 C1 |
| C4 | Not started | — | — | 等 C3 |
| C5 | Not started | — | — | 等 C3 |
| C6 | Not started | — | — | 等 C3 |
| C7 | Not started | — | — | 等 C2、C4、C5、C6 |
| C8 | Not started | — | — | 等 C3–C6 |
| C9 | Not started | — | — | 等 C8 |
| C10 | Not started | — | — | 等 C2–C9 |

## 撰寫紀錄

### CA0 撰寫計劃（2026-11-19）

**依據**

- 2026-11-19 的唯讀 repo 債務稽核。全文複製在 `context/repo-debt-audit-2026-11-19.md`。
- 使用者當日的決策 U1–U10（見 GOALS）：
  - U1–U4：回覆稽核提出的四個問題；
  - U5–U9：撰寫時以選項確認；
  - U10：要求撰寫計劃。
- U4 的決策紀錄依使用者要求寫成 `note/20261119/citation_storage_unification_decision.md`。

**撰寫時的讀碼範圍**

撰寫時只讀碼，沒有執行任何產品程式或測試。基準是 HEAD `3b6cfd8`，branch `GUI`。讀過：

- citation 的 `storage.py`、`service.py`、`types.py`、`registry.py`、`tool.py`、`session_policy.py`、`providers/doi_org.py`，以及 `resolution.py` 的 DOI 路徑；
- `agent/desktop/catalog.py` 的 catalog 類別與專案載入；
- `service.py` 的 registration、citation 輸出目錄與 runtime diagnostics 相關段落；
- contract 的頂層鍵、方法與 event 清單；
- `app/desktop/package.json`、`tsconfig.json`、`tests/protocol.test.ts` 開頭與 `tests/styles.test.ts`；
- Rust 的 `protocol.rs` 函式清單與 `backend.rs` 的協定呼叫點；
- `pyproject.toml` 與 `poetry.lock` 中的 `pybtex`；
- `for_agents/` 的 INV-010、INV-011、INV-015、INV-016、INV-021、INV-023、INV-027、INV-032，以及 FAIL-022 與 BACKLOG-022。

PLANS「基線」中的行號與行為，都要由 C1 重新核對。

**commit**：`64225d1`（決策紀錄）、`8f4ca06`（計劃）。

### CA1 依獨立審查修訂計劃（2026-11-19）

**審查方式**

- 另一個 agent 在新的 context 中做唯讀走查，只拿到計劃、決策紀錄、稽核原文與使用者原話。
- 結果：0 個 critical、5 個 major、9 個次要問題，共 14 項。
- 撰寫者以 grep 與讀碼逐項複核後才修正。其中一項審查結論是錯的，見第 2 點。

**修正內容**

1. **S023、S024、S026 沒有歸屬。** 這三個 READY 項目已加入 C2-S10，原本的收尾步驟改為 C2-S11。
2. **C4-S1 會刪掉斜線指令仍在用的程式。** 撰寫者讀碼確認：`/init /ingest /sync /prune` 仍使用 `knowledge.*` 名稱做核准 operation、`_map_exception` 的 method key 與 `_KNOWLEDGE_MUTATIONS`（`service.py` 約 1759–1779、1793 行）。
   - 審查認為 `_map_exception` 的 knowledge 分支與 `OLLAMA_*` 錯誤碼只屬於 RPC，這是錯的，沒有照它刪。
   - C4-S1 改為逐一列出要刪與要留的符號。
   - GOALS 的 A3 改寫為已確認的事實。
   - S032 改為整項不納入。
   - C7-S5 的 flag 清單加入 knowledge 操作。
3. **決策紀錄把計劃設計寫得像使用者決策。** 決策紀錄的開頭改為分開寫「使用者決定的內容」與「計劃提出的內容」。新增 P8（不補回 CSL 與 BibTeX 的 DOI 交叉比對）、P9（移除輸出目錄設定與顯示）、P10（近似色合併）。
4. **決策紀錄 §5.2 的 DOI 檢查有誤。** 讀碼確認，`parse_csl` 本來就以回應中的 DOI 為 identity；舊的 BibTeX 檢查比的是 CSL 與 BibTeX 兩種格式是否一致，不是回應與要求是否一致。
   - 原本計劃新增「回應 DOI 必須等於要求 DOI」，這會拒絕 alias DOI，已撤回。
   - 稽核 S105 漏掉這個交叉比對，已在決策紀錄 §2.3 更正。
5. **「書目庫失敗即不可引用」是撰寫時自己加的行為改變，而且需要調整登記順序。** 已撤回，改為維持現行 INV-032：書目庫失敗不改變存檔狀態（P7、決策紀錄 §4.0）。這也解決了審查指出的登記順序問題。
6. **U6 的後果寫得不足。** 已補上：一個 v1/v2 檔案會讓整個專案無法開啟。
7. **幾項驗收檢查改成能觀察到、會失敗的形式：**
   - C3-S2：詞彙常數必須引用 contract。
   - C3-S3：新增測試，確認 result 只送一次。
   - C6-S2：新增壞檔與缺目錄這兩個 fail-closed 測試。
   - C7-S4：grep 也涵蓋 `getattr` 字串形式的私有存取。
   - C7-S6：逐一分類 `service.py` 剩下的方法。
   - C8-S3：遞迴 grep，並包含 `backendClient.`。
   - C8-S6：逐一標明 `App()` 剩下的 hook。
   - C9-S3：hex 之外也檢查 `rgba`。
   - C8-S1：effect 數量改以 C1-S3 的量測為準。
8. **決策紀錄與程式不符時沒有處理規則。** GOALS 的限制改為：允許在本計劃決策紀錄末尾追加更正。
9. **build-log 的狀態值沒有定義。** 已定義四種狀態。

審查提出的「計劃目錄未提交」，是因為審查在 `8f4ca06` 之前讀取，不需要修正。

### CA2 依 Codex 審核修訂計劃（2026-11-19）

使用者轉來 Codex 的唯讀審核，共 5 點。撰寫者逐點對照程式碼確認都成立後修正。

1. **C3 回聲比對會把成功報成失敗。**
   - 讀碼確認：`document.apply` 與 `approval.resolve` 的 request 參數有 `turnId`，result schema 沒有。
   - C3 改為「只比對 request 參數與 result schema 都有的 ID 欄位，清單從 contract 推導」，並列出撰寫時推導出的組合，加上正反兩面的測試。
   - C8-S3 的 `api.ts` 改為引用同一規則。
2. **C5 的刪除順序與文字。**
   - 讀碼確認：`agent/desktop/service.py` 第 107 行 import `skills.citation.storage`。`tests/test_inline_skills.py` 經由 `agent.desktop.service` 間接 import 它，原本的順序會讓測試在收集階段就失敗。
   - 調整順序：C5-S3 先在桌面端移除 import 與 4 處 `resolve_output_dir`，C5-S4 才刪模組，並以 `pytest --collect-only` 檢查。
   - fixture 的 `citation_output_dir` 留到 C5-S4 才刪，避免測試寫進 repo 的 `cite/`。
   - C5-S5 殘留的舊說法「書目庫失敗等於存檔失敗」改成與 P7 一致。
   - 評估分界 commit 改指 C5-S4。
3. **C6 空歷史目錄失去歸屬保護。**
   - 讀碼確認：`_check_catalog_owner` 在沒有對話時也會拒絕他專案。
   - GOALS 的 U3 後果加入這一點，並新增 P11：預設接受這個改變，否決時改寫擁有者標記檔。C6 也寫入兩種做法。
4. **C7 的 Retry Stop 只改桌面端不夠。**
   - 讀碼確認：`agent/ingest.py::LocalWorkScope.finish_stop` 把失敗的清理 task 存在 `_bash_cleanup`，之後每次呼叫都重拋同一個例外。
   - 既有的 `test_failed_stop_cleanup_keeps_new_turn_blocked` 整個替換了 `finish_stop`，測不到這個問題。
   - C7-S5 改為兩層都修，驗收要在底層清理動作注入失敗，並加上 `LocalWorkScope` 的單元測試。
5. **C8 不能全面移除 Vite SSR。**
   - 讀碼確認：`citation_preview`、`documents`、`conversations`、`trust` 這 4 個測試檔以 `renderToStaticMarkup` 渲染元件，例如 `trust.test.ts` 約 250 行的 `ApprovalDialog`。
   - C8-S2 改為：只有純函式測試改成直接 import，元件渲染測試保留 SSR 載入。
   - PLANS 原本寫「前端沒有 DOM 測試工具」，不夠精確，已改為「沒有互動式 DOM 測試，但有靜態渲染測試」。
   - C9 的新元件沿用同一方式做靜態渲染測試。

### CA3 依 Codex 第二輪審核修訂計劃（2026-11-19）

使用者轉來 Codex 對 `052649a` 的第二輪唯讀審核，共 5 點。撰寫者逐點讀碼確認都成立後修正。

1. **C5 的中間狀態不一致。**
   - 問題：原本 C5-S3 先把核准畫面改成書目庫並解除舊目錄保護，C5-S4 才停止寫入 bundle（`skills/citation/service.py` 約 390 行）。若停在中間，核准畫面會漏報實際寫入位置。
   - 修正：兩步合併成單一 commit 的 C5-S3；中間狀態不提交。原本的 S5–S7 依序改為 S4–S6，PLANS、PROMPTS 與 C10 的引用同步更新。
   - CA2 紀錄中提到的 C5-S3／C5-S4 是當時的編號。
2. **C7 的 Retry Stop 可能放行仍是 pending 的回合。**
   - 讀碼確認：`service.py` 約 3017–3021 行在回合持久化狀態仍是 `pending` 時，也會設定 `owner.error`。
   - 修正：C7-S5 規定重試時要重新讀取回合狀態，只有清理成功**而且**回合已是 terminal 才解除。仍 pending 時，只能沿用現有的恢復路徑（`session.py` 的 `_recover_interrupted_turn`）標成 interrupted，否則維持封鎖。另加「清理成功、回合仍 pending」的測試。
3. **C3 回聲比對漏了選填的 ID。**
   - 讀碼確認：`session.create` 的 `projectId` 是選填，`service.py` 約 1635 行會補上目前的專案。
   - 修正：比對規則加上「request 實際帶了這個欄位」的條件，並加測試。
4. **C8 的測試順序。**
   - 問題：`trust.test.ts` 約 400–409 行直接比對 `App.tsx` 的原始碼。C8 搬移 approval 邏輯時這個測試就會失敗，但原本排在 C9 才改寫。
   - 修正：C8 加上規則「原始碼比對測試要跟著被搬移的程式在同一步改寫」，`useApproval` 那一步明列要改寫它；C9-S4 只處理剩下的部分。
5. **C6 驗收依賴 C4。**
   - 問題：C6 收尾要求剛好 26 個方法，也要更新 C4 的錯誤碼清單，C4 被阻塞時 C6 就無法驗收。
   - 修正：C4 與 C6 都只驗收自己負責移除的項目。完整清單比對與 P3 錯誤碼複查移到新的 C10-S0；C10 的涵蓋目標加上 G2，plan-index 同步更新。

### CA4 使用者接受 P11，並依 Codex 第三輪審核修訂（2026-11-19）

**使用者決定**：回覆「P11接受」，記為 GOALS U11。C6 不實作擁有者標記檔，原本的否決分支已刪除。

**Codex 第三輪審核**（對 `fbf1e5f`）共 4 點，撰寫者讀碼確認都成立：

1. **C7 可能永久卡在忙碌。**
   - 讀碼確認：`fixtures.json` 的 `session-stop-before-prompt-acceptance` 中，受理前就 Stop 的合法結果是 `state=null`、`accepted=false`、`persisted=false`，沒有終止紀錄可等。
   - 修正：C7-S5 的解鎖條件改為「清理成功」加上以下其一：已持久化為 terminal，或已確認未受理且未落盤。讀取失敗或仍是 pending 時維持封鎖。補上這兩種情況的測試。
2. **C3 漏了失敗回應的 ID 比對。**
   - 讀碼確認：`protocol.ts` 約 2314–2318 行對 `session.turn`、`extensions.apply` 的失敗回應比對 `error.details.turnId`。
   - 修正：回聲比對規則保留這一項，並沿用現有的錯誤 ID 案例驗收。
3. **C8 的替代測試少驗一層。**
   - 讀碼確認：`approvalHasLiveOwner` 已有單元測試（`trust.test.ts` 約 387 行）。原本的原始碼測試還守著「發出 `bibliography.add` 時登記擁有者」與「listener 接受相符的 `approval.required`」。
   - 修正：approval 擁有者追蹤抽成純狀態模組，測完整流程：發出 add、接受相符事件、進行中不清除、結束後清除、不相符不接受。
4. **C5-S3 的搜尋會提早失敗。**
   - 讀碼確認：`skills/citation/README.md` 第 50 行列出 `bibtex_canonical.py`。
   - 修正：C5-S3 只搜 `.py` 程式碼，文件留給 C5-S4 檢查。
   - 撰寫者另外補查發現兩件事，一併修正：
     - `agent/extensions/startup.py` 的 `_installed_bundle_path` 會被子字串搜尋誤中，所以改用 `grep -w` 整字比對；
     - `skills/citation/__init__.py` 的 docstring 提到 pybtex，所以改到 C5-S3 一起修改。

### CA5 依產品邊界與人工審查重寫計劃（2026-11-20）

**依據**

- 使用者轉來的人工審查討論結論。結論是：計劃不需要重選架構，但先前的審查與分析沒有先確認產品要支援什麼，就設計如何處理所有情況；應以產品邊界為第一個判斷條件，修正幾個錯誤設計與驗收標準。
- 使用者提交的三份文件 commit：`19a661d`（README）、`90d8d58`（AGENTS.md）、`3f87f09`（CLAUDE.md），寫下單人、本地、一次一個專案、一個對話、一個回合的產品邊界。
- 撰寫者以選項詢問的一題：書目庫寫入失敗的文獻是否仍可在當次對話引用。使用者選「A：不可引用」。
- 使用者授權大幅改寫：「不要追求最小改動，因為會導致不乾淨，需要的地方就大改」。

**讀碼確認**（HEAD `3f87f09`；`git diff --stat 3b6cfd8..3f87f09 -- app` 為空，所以基線行號不變）

- `skills/citation/service.py::_link_library`：同一批次較早一筆剛加入記憶體的作品，之後的同一作品被報成 `existing`；若整批寫入失敗，它仍是 `existing`。這是討論所說的「同批重複 DOI 誤報」。
- `SourceRegistry.register` 對同一 identity 重複登記不拒絕；`session_policy.py` 依 `saved`／`reused`／其他計算存檔計數，新增狀態值必須同步改計數。
- `project.list` 唯一的呼叫者是 `App.tsx::loadSelectedProjectHistory`；選取恢復的 effect 讀 `catalog.selectedSessionId` 與 `resumeSelectionRef`。
- `_session_turn` 在回合開始時設定 `installer.bypass_approval`，文件回合設定 `session._document_turn_active` 與 thinking mode，`finally` 再逐一還原，連同 `DesktopService` 的 10 個回合欄位。`finally` 中較早的呼叫若拋錯，之後的還原不會執行。
- 送往 WebView 的錯誤訊息都經過 `protocol.py::bounded_error_message`（含 `server.py` 兩處），它只截斷不遮蔽；`diagnostics.redact_text` 已用於 log。
- contract 的 schema 只有 13 種欄位型別，`typescript` devDependency 是 6.0.3，所以可以用 compiler API 比對 DTO 與 contract。

**修訂內容**

1. **GOALS 重寫**：新增「產品邊界」一節與審查規則；新增 2026-11-20 的決策 U12–U19 與否決或延後項 R1–R6；P4、P6、P7、P10 退役（分別由 U14、U15、U13、R4 取代）；新增 P12（media query 整併延後、CSS 只依原順序分檔）與 P13（registry 衝突改報 `identity_conflict`）；G1、G3–G7、G9 的驗收改寫；新增假設 A6、A7；限制加入產品邊界，並把 `CLAUDE.md` 列為不修改。
2. **C5 存檔語意（U13）**：取代原 P7。桌面「可引用 ⇔ 已在書目庫」，寫入失敗是 `storage_failed` 且不登記；同一批次重複作品依第一筆的結果；CLI 一律 `verified`；`CitationSaveMetrics` 新增 `verified_count`；`BibliographyLink` 只剩 `added`／`existing`。驗收測試改寫為 (a)–(j)。決策紀錄 §4 依此改寫，並新增 §10 修訂紀錄。
3. **C3 加 DTO 一致性檢查（U16）**：新步驟 C3-S3，以 `typescript` compiler API 比對 `MethodResults`、`EventData` 與 contract；C8-S3 再擴充到 `MethodParams`。原 C3-S3～S5 改為 S4～S6。C1-S4 加探測 compiler API。
4. **錯誤遮蔽改到 Python 出口（U15）**：從原 C8-S5 移到新的 C2-S11，遮蔽位置從 `_map_exception` 改為 `bounded_error_message`，測試必須走真實的動態訊息路徑。原 C2-S11 收尾改為 C2-S12。
5. **C6**：加入刪除 `project.list`、保留選取恢復（U19）與掃描量測（R3，新步驟 C6-S4）；收尾改為 C6-S5。
6. **C7 重排**：新步驟 C7-S5 每回合參數（U17），涵蓋 installer bypass、文件回合旗標、thinking 覆寫與 `DesktopService` 的 10 個回合欄位；忙碌判斷（C7-S6）與 Retry Stop（C7-S7）分開，忙碌判斷明訂不改規則、不建衝突表；Retry Stop 改用公開的 `reload_and_recover`；模組化與收尾改為 C7-S8、C7-S9。
7. **C8 重寫（U18）**：取消固定的七個 hooks；新增拆解原則（可測性來自純邏輯、不引入全域 store、hook 之間不互傳 ref 或 setter、跨 domain 協調集中、必要檢查都有純函式測試）；S079、S080 合為 C8-S5；C8-S6 依 domain 拆解並逐一記錄 hook 的參數。
8. **C9**：取消色彩 token 與近似色合併（R4）與 media query 整併（P12）；CSS 只切成依原順序排列的連續區段，以打包後的 CSS 前後比對驗收。
9. **C10**：目標方法數改為 25；最終彙報加入產品邊界檢查與掃描量測；文件更新不碰 README 的產品限制一節。
10. **PLANS、PROMPTS、plan-index**：同步更新基線、目標詞彙、路線、S-ID 歸屬、執行契約（新增「產品邊界檢查」）、風險表、啟動與審查提示。

**沒有採用的建議**（理由見 GOALS R1–R6）：大型 WorkspaceStore／controller、階層式鎖與正規化的忙碌衝突表、恢復 fixture 預覽、立即加掃描快取、CSS 色彩收斂、S056、回合開始時檢查待核准項目。

### CA6 依使用者確認修訂三處（2026-11-21）

只更新計劃、citation 決策紀錄與執行提示；不修改產品程式碼，不啟動 C1–C10，也不聲稱已跑測試或 GUI 驗收。

1. **U20／C5**：本批開始前已在書目庫的 A，不受本批新增 B 寫入失敗影響；A `reused`、可引用，B `storage_failed`、不可引用。C5-S3 增加混合批次的 key、gate、計數回歸測試；citation 決策紀錄 §4.0 同步修訂。
2. **U21／C7**：C7-S6 只集中真正重複的 Busy 判斷，不再強制把全部 flag／計數／lock 搬到 `operation_state.py`。C7-S9 的驗收改為行為與共用判斷。
3. **U22／C9**：Transcript 只共用相容的呈現元件，三種生命週期的入口可以分開；Modal／Menu 也只抽同語意的原語。三種渲染測試都保留。

同步更新 GOALS、PLANS、PROMPTS、plan-index 與 C5／C7／C9；C1–C10 路線、產品邊界與其他限制均不變。

## 事件

### C1-S1 唯讀核對起點（2026-11-21）

- **觀察結果**：分支確認為 `GUI`，HEAD 為 `651cdd3`。`3b6cfd8..HEAD` 僅包含 `[CA0]`–`[CA6]` 與使用者文件 commit（`19a661d`、`90d8d58`、`3f87f09`），`git diff --stat 3b6cfd8..HEAD -- app` 為空，S-ID 無行號漂移。工作樹僅有 `for_agents/` 9 個未提交修改及 `NOTES-grill-skill-and-document-context.md`、`app/desktop/watch.out`、`note/20261106/`，均保留不動。
- **執行指令**：`git rev-parse --abbrev-ref HEAD`、`git log --oneline 3b6cfd8..HEAD`、`git diff --stat 3b6cfd8..HEAD -- app`、`git status --short`。
- **證據**：`evidence/C1-S1/relocation.md`。
- **限制**：無。
- **下一步**：C1-S2 建立四套測試與建置基線。
