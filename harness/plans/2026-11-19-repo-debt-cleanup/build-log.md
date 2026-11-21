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
| C1 | Complete | `evidence/C1-S1/`–`C1-S4/` | — | C2-S1 |
| C2 | Complete | `evidence/C2-S1/`–`C2-S3/`, `evidence/C2-S5/`, `evidence/C2-S8/`–`C2-S11/`；C2-S12 見事件 | — | — |
| C3 | Complete | `evidence/C3-S1/`–`C3-S6/` | — | — |
| C4 | Complete | `evidence/C4-S1/`–`C4-S6/` | — | — |
| C5 | In progress | `evidence/C5-S1/`–`C5-S5/` | — | C5-S6 |
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

### C1-S2 建立基線（2026-11-21）

- **觀察結果**：四套基線檢查全部通過，無既有失敗：
  - Python `pytest`：1,808 passed, 0 failed, 0 skipped（64.58 s）
  - 前端 `npm test`：329 passed, 0 failed, 0 skipped（11.25 s）
  - 前端 `npm run build`：`tsc --noEmit && vite build` 通過，739 modules（873 ms）
  - Rust `cargo test --locked`（於啟用的 Conda `app` 環境內）：42 passed, 0 failed, 0 ignored（0.69 s 執行，49.89 s 編譯）
- **執行指令**：見 `evidence/C1-S2/baseline.md`。
- **證據**：`evidence/C1-S2/baseline.md`。
- **限制**：`cargo test` 的 supervisor 測試檢查 `CONDA_PREFIX`，後續執行皆須先 `conda activate app`。
- **下一步**：C1-S3 量測熱點檔案與協定指標。

### C1-S3 量測基線指標（2026-11-21）

- **觀察結果**：已記錄 15 個熱點檔案行數、協定詞彙（40 methods、20 requestEvents、4 processEvents、25 errorCodes；fixtures 127 messages、60 traces）、`App()` 函式本體 hook 數（`useState` 35、`useRef` 35、`useEffect` 14、`useCallback` 42）、`styles.css` 色數（110 hex、16 rgba），以及 `service.py` 私有成員存取次數（`session._` 4 次、`self.session._` 0 次、`getattr/hasattr/setattr` 反射存取 6 次）。
- **執行指令**：見 `evidence/C1-S3/metrics-before.md`。
- **證據**：`evidence/C1-S3/metrics-before.md`。
- **限制**：無。
- **下一步**：C1-S4 探測 Node JSON import 與 TypeScript compiler API。

### C1-S4 拋棄式探測與 C1 驗收完成（2026-11-21）

- **觀察結果**：
  1. **JSON import（GOALS A2）**：`import contract from ".../contract.json" with { type: "json" };` 在 `node --experimental-strip-types`（Node `v24.18.0`）直接通過，印出 `contract.methods.length = 40`，無錯誤訊息。
  2. **TypeScript compiler API（GOALS A6）**：在 `node --test --experimental-strip-types` 中 `import ts from "typescript"`（TypeScript `6.0.3`）建立 `Program` 並透過 `TypeChecker` 解析 `SessionListDto` 成功，完整列出 8 個必填屬性（`projectId`、`status`、`issue`、`items`、`total`、`offset`、`limit`、`hasMore`），耗時 `322.96 ms`，不需啟用備案。
  3. **C1 階段驗收**：`evidence/C1-S1`～`C1-S4` 均已建立且為實際執行結果，repo 產品程式碼未改動。
- **執行指令**：見 `evidence/C1-S4/probes.md`。
- **證據**：`evidence/C1-S4/probes.md`。
- **限制**：`tsc` 與 `vite build` 對 `with { type: "json" }` 的相容性依計劃在 C3-S1 實測。
- **下一步**：進入 C2（C2-S1）。

### C2-S1 移除 Agent 核心測試專用 API（2026-11-21）

- **觀察結果**：
  - **S038（APPLIED）**：刪除 `agent/thinking/review.py` 的同步 `rewrite_prompt`、`review_draft`、`aggregate_candidates` 與 `parsers.py` 的同步 `parse_reviser_output` 及 `thinking/__init__.py` re-export，`test_thinking.py` 改測 async 版。
  - **S039（APPLIED）**：刪除 `agent.llm.text.invoke_text` 與 `agent/llm/__init__.py` re-export（保留 `thinking` 的 `invoke_text_messages` 別名）；`test_openrouter_model.py` 改測 `invoke_text_messages`，`test_text_normalization.py` 改直接測 `normalize_content(..., drop_unknown_parts=True)`。
  - **S041（APPLIED）**：刪除 `ChatSession.citation_service`、`_citation_service` 屬性／setter 與 `CitationSessionPolicy.set_loaded_service`，相關測試改用 `_fixture_services` 與 `_citation_policy`。
  - **S042（APPLIED）**：刪除 `ChatSession.restore`，3 處測試改用 `ChatSession.create(..., session_id=...)`。
  - **S044（APPLIED）**：刪除 `ChatSession.__init__` 中與緊接其後 `_recover_interrupted_turn -> _validate_snapshot_project` 重複的 inline 專案歸屬檢查。
- **執行指令**：13 個受影響 pytest 模組（359 passed in 13.43 s）與 `.py` 符號 grep（0 筆殘留）。
- **證據**：`evidence/C2-S1/retired-tests.md`。
- **限制**：無。
- **下一步**：C2-S2 移除 `activate_citation_skill` 與 `deactivate_citation_skill`（S040）。

### C2-S2 移除 `activate_citation_skill` 與 `deactivate_citation_skill`（2026-11-21）

- **觀察結果**：**S040（APPLIED）**。已從 `agent/session.py` 刪除只供測試跨回合常駐的 `activate_citation_skill` 與 `deactivate_citation_skill`；7 個測試檔共 40 處引用全部改走單回合 `skill_name="citation"`／`/citation` 正式路徑，未另建等價啟動 helper。
- **執行指令**：`grep -rn --exclude-dir=__pycache__ "activate_citation_skill\|deactivate_citation_skill" app/`（0 筆）及 7 個測試模組 `pytest`（126 passed in 4.10 s）。
- **證據**：`evidence/C2-S2/retired-tests.md`。
- **限制**：無。
- **下一步**：C2-S3 Skills 與測試整理（S061–S063、S109、S122）。

### C2-S3 Skills、Gate 與測試模組整理（2026-11-21）

- **觀察結果**：
  - **S061（APPLIED）**：刪除 `agent/skills/manifest_schema.py` 的 `_LEGACY_FIELDS` 友善錯誤，`extra="forbid"` 繼續拒絕舊欄位，`test_skill_runtime.py` 同步更新訊息斷言。
  - **S062（APPLIED）**：`test_skill_scan_ignores_only_regular_zip_sources` 移入 `test_extension_registry.py`，刪除 `tests/test_extension_baseline.py`。
  - **S063（APPLIED）**：`test_smoke.py` 的 3 支 `AgentConfig` 驗證測試移入 `test_graph_skill_loader.py`，移除無實質檢查的 `test_imports`，保留 `test_graph_builds_without_error`。
  - **S109（APPLIED）**：刪除 `skills/citation/gate.py` 的無作用參數 `user_input` 與呼叫端傳值。
  - **S122（APPLIED）**：`tests/test_ingest.py` 移至 `tests/rag/test_ingest.py`。
- **執行指令**：8 個受影響測試模組 `pytest`（134 passed in 9.96 s）。
- **證據**：`evidence/C2-S3/retired-tests.md`。
- **限制**：無。
- **下一步**：C2-S4 RAG 清理（S114、S115、S117）。

### C2-S4 RAG 清理（2026-11-21）

- **觀察結果**：
  - **S114（APPLIED）**：將 `VectorRetriever` inline 到 `rag/api.py::search`，更新 `rag/__init__.py` 的 lazy `__getattr__` 與 `__all__`，並刪除 `rag/retriever/`。
  - **S115（APPLIED）**：刪除無人依賴的 `rag/store/base.py::BaseStore` 與 store 子類別繼承及 `rag/store/__init__.py` re-export。
  - **S117（APPLIED）**：修正 `rag/llm/__init__.py` 與 `agent/llm/openrouter.py` 共用設定匯入現況矛盾的模組註解。
  - 未刪除任何測試。
- **執行指令**：`pytest tests/rag/`（38 passed in 4.36 s）與 `import rag` 延遲載入檢查（通過）。
- **證據**：build-log 本節與 `tests/rag/test_tools_contract.py::test_public_import_defers_vector_backends`。
- **限制**：無。
- **下一步**：C2-S5 刪除對話 schema v1/v2 讀取器（U6、S046）。

### C2-S5 刪除對話 schema v1/v2 讀取器（2026-11-21）

- **觀察結果**：**S046（APPLIED，U6）**。唯讀核對 `app/store` 下 4/4 個對話檔均為 `schemaVersion = 3`。已刪除 `agent/conversations/models.py` 與 `repository.py` 對 v1/v2 的讀取與升版分支，讀取非 v3 檔案明確拋出 `unsupported_version` 並成為 scan issue；`test_conversation_repository.py` 已改為驗證 v3 rename 隔離與 v1/v2 拒絕不升版。
- **執行指令**：`pytest tests/test_conversation_repository.py tests/test_desktop_conversations.py tests/test_session_persistence.py tests/test_conversation_archive_access.py`（90 passed in 4.69 s）。
- **證據**：`evidence/C2-S5/store-versions.md`。
- **限制**：`app/store` 以外的使用者專案 `historyDirectory` 依 GOALS 限制無法由執行者檢查。
- **下一步**：C2-S6 移除 `TurnJournal.turn_logs`（S047，缺陷 #5）。

### C2-S6 移除無限累加的 `TurnJournal.turn_logs`（2026-11-21）

- **觀察結果**：**S047／缺陷 #5（APPLIED）**。已移除 `TurnJournal.turn_logs` 與 `ChatSession.turn_logs`，`TurnJournal` 只保留覆寫更新的 `last_tool_calls`，`ChatSession._record_turn` 改為同步方法；單回合診斷結果隨當次回傳的 `TurnOutcome`（`trace_events`、`recovery_reason`、`fusion`）與 `agent.observability` 的 `citation_save_finalized` 日誌觀察。`test_turn_finalizer.py` 與 `test_thinking_session.py` 已改讀 `TurnOutcome` 與 `caplog`，並於連續兩回合測試中斷言 `set(vars(session._turn_journal)) == {"last_tool_calls"}`。未刪除任何測試。
- **執行指令**：`grep -rn --exclude-dir=__pycache__ "turn_logs" app/`（0 筆）及 `pytest tests/test_turn_finalizer.py tests/test_thinking_session.py tests/test_observability.py tests/test_session_lifecycle.py`（89 passed in 2.92 s）。
- **證據**：build-log 本節。
- **限制**：無。
- **下一步**：C2-S7 Rust 與啟動器清理（S014、S098、S101、S102）。

### C2-S7 Rust 與啟動器清理（2026-11-21）

- **觀察結果**：
  - **S014（APPLIED）**：自 `app/desktop/src-tauri/capabilities/main.json` 移除未使用的 `core:app:allow-tauri-version`。
  - **S098（APPLIED）**：`WINDOWS_PICKER_SCRIPT` 的 `InputEncoding`／`OutputEncoding` 合併為單一 `New-Object System.Text.UTF8Encoding` 指派（原檔為各建一次 `UTF8Encoding`）。
  - **S101（APPLIED）**：`BackendSupervisor::new` 與 `for_test` 改共用 `BackendSupervisor::with_options`。
  - **S102（APPLIED）**：`main.py` 移除不存在的 `public/` 目錄與對應特判。
- **執行指令**：`python -m py_compile main.py`、`pytest tests/test_desktop_launcher.py`（12 passed）、`npm run build`（通過）、`cargo test --locked --manifest-path src-tauri/Cargo.toml`（42 passed in 0.90 s）。
- **證據**：build-log 本節。
- **限制**：無。
- **下一步**：C2-S8 前端小項目與 `.error-text` 樣式（S073–S076、S092、缺陷 #2）。

### C2-S8 前端小項目與 `.error-text` 樣式修正（2026-11-21）

- **觀察結果**：
  - **S073（APPLIED）**：移除 `ConversationInteractionState` 中恆等於 `turnActive` 的 `createDisabled`、`selectDisabled`、`controlDisabled`，呼叫端直接使用 `interaction.turnActive`。
  - **S074（APPLIED）**：移除只為測試匯出的 `sessionCreateParams`。
  - **S075（APPLIED）**：將 `App.tsx` 四處後端 snapshot／lifecycle 同步邏輯抽成 `src/backend.ts::planBackendSnapshotTransition` 純函式與 `App.tsx` 單一 `applyBackendSnapshot`，並新增重啟 generation 改變與 crash 兩支測試。
  - **S076（APPLIED）**：合併重複的 `.empty-state`，刪除死規則 `.file-open-dialog .document-error` 與重複的 `.writing-workspace .transcript`。
  - **S092（APPLIED）**：`ConversationAction` 中實際必傳的 `generation` 與 `projectEpoch` 改為必填。
  - **缺陷 #2（APPLIED）**：於 `src/styles.css` 為 `.error-text` 補上既有錯誤色 `#843c38`（hex 110、rgba 16 不變）。
- **執行指令**：`grep -n "error-text" src/styles.css`、`npm test`（330 passed in 5.69 s）、`npm run build`（526 ms）。
- **證據**：`evidence/C2-S8/retired-tests.md`。
- **限制**：GUI 視覺呈現交由使用者手動檢查清單驗收。
- **下一步**：C2-S9 Repo 整潔（S128 缺陷 #7、S129）。

### C2-S9 Repo 整潔（2026-11-21）

- **觀察結果**：
  - **S128／缺陷 #7（APPLIED）**：唯讀確認 `app/desktop/watch.out`（`509 bytes`）僅為 picker 調查輸出後已刪除（不記錄內容）。
  - **S129（APPLIED）**：刪除 repo 根目錄 `__pycache__/` 與空目錄 `harness/plans/.claude/.cc-writes` 及 `harness/plans/.claude/`。
- **執行指令**：`rm -f app/desktop/watch.out`、`rm -rf __pycache__`、`rmdir harness/plans/.claude/.cc-writes harness/plans/.claude`、`git status --short`。
- **證據**：`evidence/C2-S9/cleanup.md`。
- **限制**：無。
- **下一步**：C2-S10 桌面後端小項目（S023、S024、S026）。

### C2-S10 桌面後端小項目（2026-11-21）

- **觀察結果**：
  - **S023（APPLIED）**：`_execute_desktop_extension_command` 改只回傳 `SlashCommandResult`，動作解析集中至 `_desktop_extension_action`。
  - **S024（APPLIED）**：刪除單次呼叫的 `_apply_controls`，inline 至 `_session_select`。
  - **S026（部分 APPLIED，附保留理由）**：刪除 `documents.py::undo` 重複的第二次 `validate_snapshot`；`prepare` 的 `_text(candidate["candidateText"], "candidateText")` 因負責攔截「合法 `sourceText` 加合法 `replacementText` 合併後超過 `MAX_TEXT_BYTES`」的新字串上限，非重複驗證，依規則保留並記錄。
- **執行指令**：`pytest tests/test_desktop_service.py tests/test_desktop_documents.py tests/test_desktop_document_service.py tests/test_extension_*.py`（234 passed in 11.60 s）。
- **證據**：`evidence/C2-S10/notes.md`。
- **限制**：無。
- **下一步**：C2-S11 錯誤訊息只在 Python 出口遮蔽一次（U15、S089、缺陷 #3）。

### C2-S11 錯誤訊息只在 Python 出口遮蔽一次（2026-11-21）

- **觀察結果**：
  - **S089／U15／缺陷 #3（APPLIED）**：`bounded_error_message` 先呼叫 `agent/diagnostics.py::redact_text` 再依 4096 bytes 截斷；`redact_text` 擴充 `Authorization` 標頭、URL 帳密、`sk-`／`ghp_`／`github_pat_` 獨立金鑰樣式，並與診斷 log 共用同一份已知 secret 清單（`configured_secrets()`）。未建立第二組樣式。
  - Rust 盤點：bridge／process 錯誤全為固定字串，child stderr 不轉送，未改 Rust。
  - TS：刪除 `sensitiveMessagePattern` 與整句隱藏分支；原測試改為驗證含 `token`、`secret` 的正當訊息原文顯示。
  - **續作事件**：前一個 session 卡在 `test_server_framework_errors_redact_credentials_at_protocol_exit` 40 分鐘以上。根因是測試在 `run()` 啟動 writer 之前直接送框架錯誤（測試缺陷）；第 1 次聚焦修正（先 `writer.start()`）成功。截斷邊界測試的輸入改為以空白分隔的獨立金鑰（`\b` 是刻意保護正常字詞），斷言未放寬。細節見 evidence 第 5 節。
- **執行指令**：`pytest tests/test_desktop_*.py tests/test_diagnostics.py`（沙箱外，509 passed in 21.62 s）、`npm test`（330 passed）、`npm run build`（通過）、`grep -rn "sensitiveMessagePattern" app/desktop`（0 筆）。
- **證據**：`evidence/C2-S11/error-sources.md`。
- **限制**：GUI 錯誤顯示由使用者手動檢查（已列入清單項目）。
- **下一步**：C2-S12 階段收尾（完整 pytest、`npm test`、`npm run build`；未改 Rust，不重跑 cargo）。

### C2-S12 階段收尾與 C2 驗收（2026-11-21）

- **觀察結果**：
  - 完整 pytest（沙箱外，`app/`）：**1808 passed, 2 warnings in 56.91 s**，0 失敗。兩則 warning 與 C1-S2 基線相同。測試總數與基線相同屬巧合：C2 刪除與新增的測試相抵（退役紀錄見各步 evidence）。
  - `npm test`：330 passed，0 failed；`npm run build`：通過。兩者在 C2-S11 最終程式狀態上執行（之後只改 build-log 與 evidence）。
  - cargo：C2-S7 之後未改 Rust（C2-S11 盤點確認不需修改），依步驟規格不重跑；C2-S7 的結果為 42 passed。
  - **C2 驗收**：C2 歸屬的每個 S-ID 都有結果（S038、S039、S040、S041、S042、S044、S046、S047、S061、S062、S063、S109、S122、S114、S115、S117、S014、S098、S101、S102、S073–S076、S092、`.error-text`、S089、S128、S129、S023、S024 APPLIED；S026 部分 APPLIED 附保留理由）。`evidence/C2-S5/store-versions.md` 與 `evidence/C2-S11/error-sources.md` 存在。
- **執行指令**：`timeout 900 python -m pytest -q -p no:cacheprovider`（沙箱外）。
- **證據**：build-log 本節。
- **限制**：無。
- **下一步**：C3-S1。

### C3-S1 決定 TS 讀取 contract 的寫法（2026-11-21）

- **觀察結果**：寫法 (a) `import contract from "../protocol/v1/contract.json" with { type: "json" };` 同時通過 `tsc --noEmit`、`vite build` 與 `node --test --experimental-strip-types`（完整 `npm test` 330 pass）；寫法 (b)（無 import attribute）在 Node 失敗（`ERR_IMPORT_ATTRIBUTE_MISSING`）。**採用 (a)**，不產生 TS 副本。暫時改動已還原、未提交。
- **執行指令**：見 `evidence/C3-S1/decision.md`。
- **證據**：`evidence/C3-S1/decision.md`。
- **限制**：無。
- **下一步**：C3-S2 TS 改讀 contract。

### C3-S2 TS 改讀 contract（2026-11-22）

- **觀察結果**：
  - `protocol.ts` 以 C3-S1 的 JSON import 讀 contract：七個詞彙常數引用 `contract`；request 參數由解譯器讀 `methods[].params` 驗證，必填取自 `params[].required`。刪除所有手抄字面量與 `*_SCHEMA`、result／event data 驗證（含 `validateResultData` 與其重複呼叫，S004）、`ProtocolTraceValidator`、TS 端的禁止鍵掃描與 process event 來源表。2,333 → 1,016 行。
  - `backend.ts` 只保留 envelope 解析與回聲比對：成功回應比對由 contract 推導的 `echoedIdFields`（request 與 result 都帶時才比），失敗回應對 `session.turn`／`extensions.apply` 比對 `error.details.turnId`。產品邊界紀錄見 evidence §4。
  - **S072（APPLIED）**、**S071 兩個死 DTO（APPLIED）**、**S085（APPLIED）**、**S090（APPLIED）**，細節見 evidence §5。
  - result 驗證失敗的 catch 盤點：只剩 `requestTracked` 的單一 catch（改為只接 envelope／回聲錯誤），未另造替代檢查。
- **執行指令**：`npx tsc --noEmit`、`npm test`（216 pass, 0 fail）、`npm run build`（通過）。
- **證據**：`evidence/C3-S2/ts-contract.md`（常數定義行、方法名字串 grep 用途、catch 盤點、測試退役紀錄）。
- **限制**：`tests/` 尚未受 `tsc` 檢查（C8 處理）。Rust 端尚未縮減（C3-S4），兩端各自的測試皆通過。
- **下一步**：C3-S3 DTO 一致性檢查（U16）。

### C3-S3 DTO 一致性檢查（U16）（2026-11-22）

- **觀察結果**：
  - 新增 `tests/protocol_types.test.ts`：以 `typescript` compiler API 比對 `MethodResults`（26 列）與 `EventData`（3 列）的 DTO 和 contract schema，並檢查 `ProtocolMethod`、`RequestEvent`、`ProcessEvent` 聯集等於 contract。比對函式有 3 個 in-memory 單元測試，涵蓋步驟規格要求的六種偏差與 union 合併。
  - 首次比對未發現 DTO 與 contract 不一致；依 contract 補上 `MethodResults` 需要的 7 個 DTO。`App.tsx` 重複的 `DocumentResult` 改用 `DocumentResultDto`（S071 剩餘的 `App.tsx` 部分）。C3-S2 依 S071 刪除的 `DocumentOpenDto`／`DocumentResultDto` 在本步作為 result DTO 重新加入，理由見 evidence §2。
  - 例外清單 11 項，全是 C4 會移除的詞彙（P1 兩個 RPC、U7 九個 event），每項附理由；**C4 必須把清單清空**。
  - 負向演練：contract 欄位改名、DTO 必填改選填，`npm test` 都失敗並指出 `MethodResults["session.rename"]` 與欄位；兩者已還原。
- **執行指令**：`node --test --experimental-strip-types tests/protocol_types.test.ts`、`npm test`（220 pass, 0 fail）、`npm run build`（通過）。
- **證據**：`evidence/C3-S3/dto-check.md`（含演練輸出與耗時：真實比對 166–246 ms）。
- **限制**：`MethodParams` 依計劃在 C8-S3 加入。
- **下一步**：C3-S4 Rust 只驗框架、result 只送一次。

### C3-S4 Rust 只驗框架，result 只送一次（2026-11-22）

- **觀察結果**：
  - **S002（APPLIED）**：`protocol.rs` 只剩框架檢查（3,638 → 616 行）；**框架常數取法：優先方案 `include_str!` contract，以 serde 解析進 `OnceLock<Framework>`**，`main.py` 的 release 重建輸入加入 `app/desktop/protocol/`（含 launcher 測試）。
  - **S003／缺陷 #4（APPLIED）**：`backend.rs` 刪除 result 的 `emit_protocol` 第二次送出與 `validate_result_data`；result 只經 invoke 回傳。
  - **S011 Rust 部分（APPLIED）**：刪除 `ProtocolTraceValidator`、`RequestTraceState`、`PROTOCOL_METHODS`、`parse_protocol_line(_from_origin)`。
  - 範例 request 改為 `runtime.diagnostics`。新增 `oversized_success`、`forbidden_event` 模式與單次送出斷言。
- **執行指令**：`cargo test --locked`（沙箱外，35 passed）、`npm test`（220 pass）、`pytest tests/test_desktop_launcher.py`（13 passed）、grep 四個符號（0 筆）。
- **證據**：`evidence/C3-S4/rust-framing.md`（保留／移除對照、檢查對應測試、退役紀錄）。
- **限制**：無。
- **下一步**：C3-S5 Python 與 fixtures。

### C2-S11a 修正 C2-S11 遮蔽測試的執行順序依賴（2026-11-22，C3-S5 執行中發現）

- **觀察結果**：C3-S5 跑 `pytest tests/test_desktop_protocol_contract.py tests/test_desktop_server.py` 時，`test_dynamic_service_error_redacts_credentials_and_truncates_safely` 5 次中失敗 1 次。根因：兩個 `document.open` request 是並行的 task，`service.py` 以 `asyncio.to_thread(self._documents.open, ...)` 執行，替身 `fail_open` 卻依呼叫次數決定錯誤訊息，第二個 request 先到時兩則訊息對調。這是測試缺陷，不是產品缺陷。
- **修正**（此問題第 1 次聚焦修正）：替身改依路徑決定訊息（`draft.md` 為一般訊息、`boundary.md` 為跨截斷邊界的訊息），斷言不變。
- **執行指令**：同一組兩個模組連跑 15 次：0 次失敗。
- **證據**：build-log 本節。
- **限制**：無。
- **下一步**：繼續 C3-S5。

### C3-S5 Python 與 fixtures（2026-11-22）

- **觀察結果**：
  - **S005（APPLIED）**：`_encode_message` 不再重驗；`success_result` 只做 `validate_request_id` 與 `validate_result_data` 一次。每則送出的訊息只驗一次（pre-persist 的 S025 不納入）。
  - **S011 Python 部分（APPLIED）**：`TraceValidator` 仍是 trace fixtures 的 oracle，移到 `app/tests/protocol_trace_oracle.py`，production 0 引用。
  - **S012（APPLIED）**：刪除寫死的 28 個 result schema 名稱、歷史測試 `test_phase04_…v1_additions`、與 fixtures 重複的 bash-permission request 驗證；約定寫入測試模組 docstring。為 5 個保留的方法補 8 個 request fixtures，使所有保留的方法都有合法與非法例；仍缺項的 12 個方法都會在 C4／C6 移除。
- **執行指令**：`pytest tests/test_desktop_protocol_contract.py tests/test_desktop_server.py -q`（243 passed，連跑 15 次 0 失敗）、desktop 全部 pytest 模組（513 passed）、`npm test`（228 pass）、`python3 evidence/C3-S5/fixture_coverage.py app/desktop/protocol/v1`。
- **證據**：`evidence/C3-S5/python-single-validation.md`、`fixture_coverage.py`、`fixture-coverage.txt`。
- **限制**：無。
- **下一步**：C3-S6 階段收尾與「新增一個方法」走查。

### C3-S6 階段收尾、「新增一個方法」走查與 C3 驗收（2026-11-22）

- **觀察結果**：
  - 完整檢查（最後狀態）：pytest 1816 passed（沙箱外）、`npm test` 228 pass、`npm run build` 通過、`cargo test --locked` 35 passed（沙箱外）。
  - 走查 `session.rename`：第一次走查發現 `ProtocolMethod` 型別聯集是額外的手改處，改為 `keyof MethodResults | MethodWithoutResultDto`（`RequestEvent` 同理）。修正後必須手改的只剩 contract、Python handler 與 dispatch、TS DTO 與 `MethodResults` 的一列、呼叫端。
  - 行數：`protocol.ts` 2,333 → 1,094；`protocol.rs` 3,638 → 616；`protocol.py` 760 → 699；`fixtures.json` 5,194 → 5,301（補 fixtures）。
  - **C3 驗收**：責任表「移除」欄都已移除、「保留」欄有測試（C3-S2、S4、S5 evidence）；DTO 一致性檢查存在且負向演練會失敗（C3-S3）；四套檢查通過；走查符合 G1。
- **執行指令**：見 `evidence/C3-S6/add-method-walkthrough.md`。
- **證據**：`evidence/C3-S6/add-method-walkthrough.md`。
- **限制**：`tests/protocol_types.test.ts` 的 `DTO_EXCEPTIONS` 與 `MethodWithoutResultDto` 中的 `session.shutdown`、`extensions.status`，以及 9 個未發出的 event，留給 C4 清除。
- **下一步**：C4-S1。

### C4-S1 刪 10 個 `knowledge.*` RPC（2026-11-22）

- **觀察結果**：
  - **S007（U2 部分，APPLIED）**：刪除 dispatch 的 10 個項目、10 個 handler、`_hit_dto`、RPC 專用的 `_prune_previews` 與其 `clear()`，以及因此無人使用的 `rag` 查詢 import 與 `math`。A3 列出的斜線指令共用符號全部保留（evidence §2）。contract 方法 40 → 30，approval enum 保留 4 個 `knowledge.*`。
  - 測試：刪除 3 個只測 RPC 的測試與 `test_project_permissions.py` 的 RPC 核准測試（S036）；把 extension 狀態檔、0 chunk 與 Ollama 錯誤對照的兩個測試改寫到 `/ingest`，symlink 父目錄併入 composer fail-closed 測試，並在 composer 核准測試加上 `parentRequestId` 關聯斷言。fixture `unicode-path-with-spaces` 改用 `document.open`。
  - 觀察：composer `/ingest` 的錯誤 details 依 contract 只有 turn lifecycle，看不到 `partialWritePossible`（既有行為，列入最終彙報）。
- **執行指令**：相關 pytest 模組（621 passed，沙箱外）、`npm test`（224 pass）、`npm run build`（通過）。
- **證據**：`evidence/C4-S1/knowledge-rpc.md`（刪除前 grep、保留清單、退役紀錄）。
- **限制**：無。
- **下一步**：C4-S2 移除 `session.status`、`session.shutdown`、`extensions.status` 的 RPC 註冊（P1）。

### C4-S2 移除 `session.status`、`session.shutdown`、`extensions.status` 的 RPC 註冊（2026-11-22）

- **觀察結果**：**S007（P1 部分，APPLIED）**。刪除 3 個 dispatch 項目與 contract 方法（含兩個 result schema）；`_session_status` 與 `_session_shutdown` 沒有其他呼叫者而刪除，`_extensions_status` 仍供 `/extension-management status` 使用而保留（簽名簡化），`_shutdown_session` 保留。`dispatch` 中只為這兩個方法存在的例外條件同步簡化。TS 例外清單只剩 9 個 event（C4-S3 清除）。沒有刪除測試：以 `session.shutdown` 結束行程的改用 `runtime.shutdown`，需要繼續使用 service 的改呼叫 `_shutdown_session()`，server 測試的泛用方法改為 `session.set_thinking`／`runtime.diagnostics`，3 個 trace fixture 同步。
- **執行指令**：desktop 與 extension 相關 pytest（628 passed，沙箱外）、`npm test`（224 pass）、`npm run build`（通過）、grep 三個方法名（0 筆）。
- **證據**：`evidence/C4-S2/rpc-registrations.md`。
- **限制**：無。
- **下一步**：C4-S3 死 event、streaming 殘留與 Ollama 欄位（U7）。

### C4-S3 死 event、streaming 殘留與 Ollama 欄位（2026-11-22）

- **觀察結果**：
  - **S006（U7，APPLIED）**：contract 的 request event 20 → 8；fixtures 刪 2 個 `ingest-progress-*`，另 5 個以 `request.progress` 為泛用 event 的 fixture 改用 `stage.changed`。
  - **S009（U7，APPLIED）**：`streamKind`、`chunkCount` 從 Python、contract、TS（含 `AnswerStreamKind` 與拒絕條件）與 fixtures 端到端刪除；`test_desktop_answer_stream.py` → `test_desktop_turn_results.py`、`answer_stream.test.ts` → `conversation_turns.test.ts`，保留有價值的 terminal result 斷言。
  - **S010（U7，APPLIED）**：`ollamaReachable`、`ollamaModelAvailable` 與 GUI 兩列（含 `availabilityLabel`）刪除。
  - `DTO_EXCEPTIONS` 已清空。Rust 測試的假 backend 同步改用現行詞彙。
- **執行指令**：pytest desktop／protocol 相關模組（552 passed，沙箱外）、`npm test`（224 pass）、`npm run build`（通過）、`cargo test --locked`（35 passed，沙箱外）、grep 四個欄位名（0 筆）。
- **證據**：`evidence/C4-S3/dead-vocabulary.md`。
- **限制**：`for_agents/` 仍提到舊測試檔名，列入最終彙報。
- **下一步**：C4-S4 權限命名（U8＋P2）。

### C4-S4 權限命名（2026-11-22）

- **觀察結果**：**S016（U8＋P2，APPLIED）**。方法改為 `session.set_permission`，參數 `mode` 與線上欄位 `bashPermissionMode` 改為 `permissionMode`；Python handler、`DesktopService._permission_mode`、記憶體內控制快照、TS 型別、`PermissionControl` 元件與相關函式、fixtures 與 desktop 測試名稱同步改名。持久化的 `permissionMode` 與 bash 工具內部命名不變。
- **執行指令**：相關 pytest（599 passed，沙箱外）、`npm test`（224 pass）、`npm run build`（通過）、grep（0 筆）。
- **證據**：`evidence/C4-S4/permission-naming.md`。
- **限制**：無。
- **下一步**：C4-S5 無用欄位與錯誤碼（S008＋P3）。

### C4-S5 無用欄位與錯誤碼（2026-11-22）

- **觀察結果**：
  - **S008（APPLIED）**：刪除 `messageTypes`、頂層 `documentContextSchema`、`session.turn.documentOperations`（含 Python 驗證與 TS `DocumentOperationDto`）、所有方法的 `requiredParams` 與 `operation`、approval enum 的 `extensions.apply`（含 TS 聯集與 `trust.tsx` 標籤）、`candidateId`（tool event 與 `toolSummaries`）。刪除前確認 Python 與 TS 都讀 `params[].required`。
  - **P3**：25 個錯誤碼都有 producer，本步不移除；清單與 producer 位置見 `evidence/C4-S5/error-codes.md`，C10-S0 複查。
- **執行指令**：相關 pytest（548 passed，沙箱外）、`npx tsc --noEmit`、`npm test`（224 pass）、`npm run build`（通過）。
- **證據**：`evidence/C4-S5/unused-fields.md`、`evidence/C4-S5/error-codes.md`。
- **限制**：Rust 在 C4-S6 重跑。
- **下一步**：C4-S6 階段收尾。

### C4-S6 階段收尾與 C4 驗收（2026-11-22）

- **觀察結果**：完整 pytest 1798 passed（沙箱外）、`npm test` 224 pass、`npm run build` 通過、`cargo test --locked` 35 passed（沙箱外）。contract：方法 27（25 個目標加上 C6 負責的 2 個）、request event 8、process event 4、錯誤碼 25；腳本比對 C4 移除清單全為 0。**C4 驗收**：grep 為 0、四套通過、GUI 清單已加入兩項。
- **執行指令**：見 `evidence/C4-S6/vocabulary-count.md`。
- **證據**：`evidence/C4-S6/vocabulary-count.md`。
- **限制**：無。
- **下一步**：C5-S1。

### C5-S1 保證對照與使用者盤點（2026-11-22）

- **觀察結果**：
  - **A1 成立**：存檔 artifact、receipt 與計數只存在記憶體與 log，對話 JSON 只保存固定字串的 tool activity summary；`app/store` 沒有相關資料。
  - **§5.3**：實測 `export_bibtex`／`parse_canonical_bibtex`：不拒絕缺標題或缺年份，缺作者是 `IndexError`（internal error），其餘拒絕都是 BibTeX 語法或 payload 格式的限制。權威記錄的最低欄位由 adapter 負責。**沒有「無人負責」的欄位要求**，C5-S2 只加測試 (b)、(c)。決策紀錄「例如缺標題」與程式不符，C5-S2 在決策紀錄末尾追加更正。
  - 桌面在 `library_path` 為 `None` 時仍可能觸發 `citation.save` 核准（`RESEARCH.md` 的 `bibliography` metadata 格式錯誤），C5-S3 保留分支並在 target 寫明不寫入磁碟。
  - `source_id_for` 在 `storage.py`，刪除前必須以相同公式搬家。
  - 狀態值與計數的使用者清單見 evidence §6。
- **執行指令**：見 evidence（唯讀 grep 與 BibTeX 函式實測）。
- **證據**：`evidence/C5-S1/guarantee-map.md`。
- **限制**：無。
- **下一步**：C5-S2。

### C5-S2 先補保證，再刪 BibTeX（2026-11-22）

- **觀察結果**：C5-S1 沒有找到「無人負責」的欄位要求，本步只加測試 (b)、(c)（`test_citation_save_outcomes.py`：正常 DOI 與 arXiv 存檔成功、alias DOI 以 doi.org 回應的主要 DOI 為 identity），兩者在 BibTeX 仍存在時通過。**決策紀錄更正**：在 `note/20261119/citation_storage_unification_decision.md` 末尾追加「執行時更正（2026-11-22、C5-S2）」，說明 §5 第 3 點的「例如缺標題」與程式不符，最低欄位要求由權威 adapter 負責。
- **執行指令**：`pytest tests/test_citation_save_outcomes.py`（16 passed）、`pytest tests/test_citation_*.py`（557 passed）。
- **證據**：`evidence/C5-S2/tests.md`。
- **限制**：本步未改變驗證結果，評估分界 commit 依計劃記為 C5-S3。
- **下一步**：C5-S3。

### C5-S3 移除 bundle 與 BibTeX 鏈、改存檔語意、桌面端同步切換（2026-11-22）

- **觀察結果**：
  - **S105（U4、U13、U20、P8、P13，APPLIED）、S106（隨 S105 消失）**：書目庫成為唯一儲存；桌面只有在書目庫中時才 `saved`／`reused` 並可引用，寫入失敗為 `storage_failed`、不可引用；同批重複與 U20 混合批次依規則判讀；CLI 一律 `verified`、不寫檔；P13 衝突在寫入前判定為 `identity_conflict`。`SAVE_BATCH_SCHEMA_VERSION = 3`，計數新增 `verified_count`。
  - **P9（APPLIED）**：`citation_output_dir`、`CITATION_OUTPUT_DIR`、`citationOutputPath` 與 GUI 兩處顯示移除；核准 target 改為書目庫路徑（無書目庫時為 `(not written to disk)`）；`_protected_roots` 不含輸出目錄。
  - **S029、S108、S110、S118、S119、S120、缺陷 #6（APPLIED）**：細節見 evidence §2–§3；S029 中跨 handler 的路徑解析與 add 寫入後的 fingerprint 讀取附理由保留。
  - 刪除 `storage.py`、`bibtex_canonical.py`、BibTeX 相關函式、legacy bundle fixture 與兩個 bundle／BibTeX 測試模組；新增存檔語意測試 (a)–(k)。
  - 執行中發現並修正：工具結果在沒有書目庫連結時，說明文字未換行就接在 JSON 後（測試抓到）；書目庫寫入的非預期例外原本會讓整個存檔崩潰，改為參與寫入的各筆 `internal_error`。
  - **citation 評估分界 commit：本步（C5-S3）**。C5-S2 未改變驗證結果。
- **執行指令**：`pytest --collect-only -q`（1762，0 錯誤）、完整 pytest（沙箱外，1762 passed）、`npm test`（224 pass）、`npm run build`（通過）、整字 grep（全部 0）、`cite/` 前後清單比對（相同）。
- **證據**：`evidence/C5-S3/single-store.md`（語意表、(a)–(k) 對照、退役紀錄、產品邊界）。
- **限制**：模型指令（`SKILL.md`、README）在 C5-S4 更新；`pybtex` 相依在 C5-S5 移除；cargo 在 C5-S6 重跑。
- **下一步**：C5-S4 模型看到的文字。

### C5-S4 模型看到的文字（2026-11-22）

- **觀察結果**：**模型指令已改變（實驗條件）**。`SKILL.md` 的 description、BibTeX 的三處提及、後續 task 重新存檔的規則與「Project bibliography」一節改寫為新的存檔狀態（`saved`／`reused` 可引用、`storage_failed` 未存檔且不可引用並可重試、CLI 的 `verified` 只在本次對話可引用且不可說成已存檔）；skill `README.md` 的流程圖、模組表（刪 `bibtex_canonical.py`、`storage.py`）與狀態邊界同步。只剩「bundled CSL styles」的用語，與 citation bundle 無關。
- **執行指令**：skill 相關測試 125 passed；grep 見 evidence。
- **證據**：`evidence/C5-S4/skill-text.md`（含完整 diff）。
- **限制**：無。
- **下一步**：C5-S5 以 Poetry 移除 `pybtex`（U9）。

### C5-S5 以 Poetry 移除 `pybtex`（2026-11-22）

- **觀察結果**：**U9（APPLIED）**。dry-run 確認只移除 `pybtex 0.26.1` 與 `latexcodec 3.0.1`（0 installs、0 updates）；`poetry remove pybtex` 後 `pyproject.toml`、`poetry.lock` 不再提及兩者，`poetry check` 通過，citation 模組可匯入。lock 的 diff 只有兩個套件區塊與 `content-hash`。
- **執行指令**：見 `evidence/C5-S5/dependency.md`（沙箱外，Conda env `app`）。
- **證據**：`evidence/C5-S5/dependency.md`。
- **限制**：無。
- **下一步**：C5-S6 測試整理與收尾。
