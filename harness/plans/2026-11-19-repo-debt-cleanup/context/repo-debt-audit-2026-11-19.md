> 本檔是 2026-11-19 唯讀稽核的完整報告，原本只存在 session 暫存區，撰寫計劃時原樣複製到這裡保存。
> 報告寫於決策之前：§4 的「需要你決定的事」已由使用者回答，結果以 [GOALS.md](../GOALS.md) 的 U1–U9 為準；§6 各項的處置以 [PLANS.md](../PLANS.md) 的 S-ID 歸屬表為準。
> 行號以 `3b6cfd8` 為準，執行時以符號重新定位。

# Research Agent Workspace — 技術債與可演進性審查

- 日期：2026-11-19；基準：branch `GUI` @ `3b6cfd8` ＋ 目前工作樹（`for_agents/` 9 檔未提交修改、3 個未追蹤項目）
- 模式：**audit（唯讀）**。全 repo 範圍；本輪未修改任何 repo 檔案、未執行 pytest／npm／cargo／tsc。
- 方法：主線程做跨切面分析（git 歷史、成長曲線、檔案體積、分支），五個唯讀 reviewer 依路徑分區深讀，最後由主線程對 15+ 個關鍵結論親自 grep／讀碼複核並修正一處錯誤（見 §8）。
- 行號來自 `3b6cfd8`；標 ✔ 者為主線程親自複核過。

---

## 0. 結論先講

**狀態統計（134 項）：READY 46／DECIDE 79（其中 19 項是「結構重整」而非刪除）／KEEP 9／BLOCKED 0／APPLIED 0。**

對「將來會大改 UI、加改功能」而言，真正的債不在零散死碼（那些加總幾千行，多半無害），而在四個**結構性的放大器**：每加一個功能，它們讓成本乘上好幾倍。

1. **協定四份手抄本＋大量死詞彙。** `contract.json` 宣稱是單一來源，但只有 Python 在 runtime 讀它；TS（`protocol.ts` 2,333 行）與 Rust（`protocol.rs` 2,822 行 prod＋816 行 test）各自手抄一份，再用 parity test 互相監督。27 個改過 contract 的 commit 中有 26 個同時改了 TS 與 Rust。一條 `session.turn` 結果從 Python 到 React 最多被驗證 **7 次**，Rust 還把每個 result **送兩次**到 WebView（✔）。40 個方法中 **13 個沒有任何 GUI/Rust 呼叫者**，20 個 request event 中 **12 個從未被發出**（✔）。新增一個方法 ≈ contract 27 行＋Rust 34 行＋TS 22 行＋fixtures 182 行（以 `dcae226` 實測）。
2. **線兩端各有一個 god object。**
   - 後端 `DesktopService`：4,643 行、148 個成員、約 60 個可變欄位，「是否忙碌」的判斷在 8 處各自複製。FAIL-022（Retry Stop 卡死）就是這個結構的直接後果。
   - 前端 `App()`：2,034 行、35 個 `useState`＋35 個 `useRef` 鏡像、14 個 effect、無 context。approval 清除區塊重複 11 次。
   - 中間的 `ChatSession`（1,555 行）被 desktop 與 orchestrator 從外部改寫私有屬性 ≥ 20 處。
3. **測試與 production 互相綁死。**
   - 1,493 行的 `fixture_session.py` 是第二套 ChatSession 實作，住在 production 套件裡，靠環境變數開啟。
   - `service.py` 為了配合「參數不全的假 session」用 `inspect.signature` 探測建構參數。
   - 測試對 `ChatSession` 私有屬性約 100 處、對 `service._x` 數十處的直接存取，任何重構都會先打壞幾十個測試。
   - 前端測試釘死 CSS 數值、class name 與原始碼文字；`App()` 本身的編排邏輯則**零測試**。
4. **UI 沒有可重設計的地基。**
   - `styles.css` 1,299 行全域樣式、0 個 CSS 變數、107 個不同 hex 色，可辨識出三代寫法、四處 media query。
   - 沒有元件或 hook 邊界；dialog／menu 程式碼複製 3–4 份。
   - 「browser preview」模式只顯示降級橫幅，任何視覺修改都必須同時跑 Tauri＋Python 後端。

另有一批**已退役功能的殘留**：streaming（`streamKind`／`chunkCount` 常數）、knowledge RPC（兩個方法恆失敗）、多專案 catalog（上限 32、實際只有 1）、v1 citation bundle 讀取器、對話 schema v1/v2 讀取器、同步版 thinking helpers、`/skill` 與 `recall_history` 的墓碑。它們每項都不大，但每一項都要被四份協定、測試與文件一起背著走。

**建議順序：先縮協定（Phase 1），再切後端接縫（Phase 2），再打前端地基（Phase 3）。** 理由：每個 UI 功能都會穿過這條線。先把「加一個方法要改五處」降成「改兩處」，後面所有 UI 工作都更便宜；反過來先拆 `App.tsx`，等於把四份協定的負擔搬進新元件裡。見 §3。

---

## 1. 跨切面事實（主線程量測）

| 指標 | 數值 |
|---|---|
| 追蹤檔案 | 531 個（不含 vendor 與 note 的程式碼約 53k 行） |
| Python prod／tests | prod 約 33k 行（agent 23.1k 含 desktop 8.9k、skills 7.8k、rag 2.1k）／tests 38.7k 行 |
| TS／CSS | TS prod 8.9k、CSS 1.3k、TS tests 3.7k |
| Rust | prod 約 4.5k、tests 約 1.6k |
| 協定 | 手寫驗證器 Py 760＋TS 2,333＋Rust 2,822 ≈ **5.9k 行**；contract 1,261；fixtures 5,194 |
| 成長曲線 | `service.py` 1,207（08-28）→ 4,643；`App.tsx` 99（08-24）→ 3,059；`contract.json` 328 → 1,261；`protocol.rs` 1,929 → 3,638 |
| 改動熱點（07-20 以來 commit 數） | `session.py` 63、`service.py` 52、`App.tsx` 46、README 43、`test_desktop_service.py` 35、`styles.css` 29、`protocol.rs`／`protocol.ts`／contract／fixtures 各 27–29、`fixture_session.py` 28 |
| commit 類型（08-20 以來共 586 個） | docs 172、feat 101、fix 99、chore 98、test 77、refactor 31 |
| 分支 | `GUI` 領先 `main` **656** commits；`main` 最後更新 2026-07-24；`clean` 是 `GUI` 的舊祖先（08-24） |
| 已完成計畫紀錄 | `harness/plans/` 124 檔、11.5k 行、約 1.2 MB |

---

## 2. 今天「做一件事」要碰哪些地方

| 變更 | 今天要碰 | 摩擦來源 |
|---|---|---|
| 新增一個協定方法 | contract（約 27 行）、`protocol.rs`（約 34 行：`PROTOCOL_METHODS`、`required_params`、`allowed_params`、`validate_params` 與 `validate_result_data` 兩個分支、manifest 測試）、`protocol.ts`（約 22 行＋DTO）、fixtures（約 182 行）、Python handler＋dispatch＋忙碌檢查＋`_map_exception`、Python 測試中寫死的 28 個名稱、React 呼叫端 | S001、S002、S012、S028 |
| 加一個 UI 面板 | `App()` 再加 state（目前已 35 個）、把 `documentBusy \|\| pendingApproval !== null \|\| workspaceBusy !== null` 再複製一次（目前已 12+ 處）、在 1,299 行全域 CSS 尾端追加規則、手動跑 Tauri＋Python 才看得到 | S096、S097、S078 |
| 重新設計 transcript | 三套 turn 渲染（`RestoredTurn`、live 分支、pending 分支）＋散落的 `.message`、`.tool-*` 規則＋釘住 class name 的測試 | S087、S097 |
| 新增一般 Skill | 放一個 `SKILL.md` 即可，**這部分很順** | — |
| 新增帶 policy 的 Skill（例如唯讀） | `READ_ONLY_DOCUMENT_SKILLS`、`"skill-installer"` 字串出現 6 次、citation 的特例散布約 10 處 | S054 |
| 新增 thinking mode | `"normal"`／`"extended"` 字面值散在 8 處＋協定＋前端 | S055 |
| 新增 CSL 樣式 | 一個 `.csl` 檔＋`styles.json` 一筆，**很順** | — |
| 新增 citation provider | `providers/` 新 client、`hub.__init__`、`service.search`、`WorkResolver.resolve`，共 4 處＋4 個測試檔 | S123 |
| 新增匯出格式 | `csl_render`＋`service._bibliography_export`＋四份協定 | S001、S002 |

---

## 3. 建議執行順序

**Phase 0 — 零風險清理（READY，可一次做完）。**
S003–S005、S008、S014、S021–S024、S026、S029、S031、S038–S044、S061–S063、S071–S076、S085、S092、S098、S101、S102、S106（若 S105 選保留 bundle）、S108–S110、S114、S115、S117–S120、S122、S128、S129。

**Phase 1 — 縮小線上介面並收斂協定副本。**
1. 先決定 S006、S007、S009、S010、S016（要刪哪些詞彙、權限要不要改名），一次改完四份。
2. 再做 S001（TS 直接 import contract）與 S002（Rust 只驗框架）。
3. 預估效果：刪約 1,080 行 TS、約 2,000 行 Rust prod＋約 500 行 test、約 220 行 Python handler，以及對應的 fixtures。之後新增一個方法只需改 contract＋Python handler＋TS DTO＋呼叫端。

**Phase 2 — 後端接縫。**
1. S052：建立 `ChatSession` 的公開 API，取代私有屬性存取；`_document_turn_active` 改成 turn 參數，從結構上不可能洩漏到下一回合。
2. S028：用一個 operation-state 物件取代 8 處忙碌判斷，**順帶修好 FAIL-022**。
3. 將 `service.py` 拆成模組：errors、bibliography、extensions、knowledge commands、document ops、approvals、transcript、turn context，約 2,400–2,800 行（55–60%）可移出。
4. S020：把 `fixture_session` 移到 `tests/`；S031、S037：統一假物件。

**Phase 3 — 前端地基。**
1. S083：把純函式抽成模組，讓測試直接 import，去掉 Vite SSR 中轉，並讓 `tsconfig` 也檢查 `tests/`。
2. S097：抽出 hooks（`useBackendEvents`、`useApproval`、`useWorkspaceOperations`、`useDocumentWorkspace`、`useTurn`、`useConversationCatalog`、`useExtensions`）與元件（Composer、Transcript、Sidebar、DocumentPane、ProjectChooser），並共用 Modal 與 Menu。目標是 `App()` 只剩 300–400 行組裝。
3. S096：建立 `tokens.css`，整併 media query。
4. S078：把 browser preview 改成**用 fixture 驅動的預覽**，GUI 迭代就不必每次都起 Tauri＋Python。

**橫跨各 Phase 的事。**
- S084、S086–S088：釘死 layout 的測試，在對應重構時一起換成行為斷言。
- S134：開始前先決定 `GUI` 與 `main` 的分支策略。

---

## 4. 需要你決定的事（依影響排序）

| # | 決定 | 我的建議 | 相關 ID |
|---|---|---|---|
| 1 | TS／Rust 還要不要各自做逐方法驗證？論文是否需要宣稱「三層驗證邊界」？ | Rust 只驗框架；TS import contract，只驗 request 與 id 回聲 | S001、S002、S011、S090 |
| 2 | 10 個 `knowledge.*` RPC：全刪，或保留 4 個唯讀方法給未來的知識庫面板？ | 近期沒有面板計畫就全刪；之後要再加，在 Phase 1 之後成本很低 | S007、S022、S036 |
| 3 | 12 個未發出的 event、streaming 欄位、ollama 欄位是否移除 | 移除 | S006、S009、S010 |
| 4 | `desktop-projects.json` catalog 要不要改成「從對話目錄掃描推導」（同時刪掉 registration retry 與多專案殘留）？ | 要，前提是你確認不需要「catalog 指向不存在的對話時拒絕開啟」這個行為 | S018、S019、S027、S070 |
| 5 | citation bundle（`cite/`）與專案書目庫要不要合併成單一儲存？ | 若 CLI 可以不再單獨存檔就合併，這是 citation 子系統最大的減量（含 `pybtex` 相依） | S105、S106 |
| 6 | 權限欄位改名：`bashPermissionMode`、`permissionMode`、`mode` 統一成一個名字 | 在 Phase 1 一次改完 | S016 |
| 7 | 對話 schema v1/v2 讀取器是否刪除 | 若你的研究專案 `historyDirectory` 都在 `app/store` 下（目前 4/4 個都是 v3）就刪 | S046 |
| 8 | `fixture_session.py` 移到 `tests/` | 要 | S020 |
| 9 | browser preview：刪掉，或改成用 fixture 驅動的預覽 | 改成 fixture 預覽 | S078 |
| 10 | `harness/plans/` 兩份已完成計畫何時刪 | 等你自己的 GUI checklist 與 live grill eval 結束後，沿用 `git show` 慣例刪除 | S125 |
| 11 | `GUI` 合回 `main`？`clean` 分支刪除？ | 大重構前先合併，讓 `main` 重新成為主線 | S134 |
| 12 | `styles.test.ts` 釘住 INV-021 的 clamp 數值 | UI 重設計時同步改 INV-021 並改成行為測試 | S084 |

---

## 5. 順帶發現的缺陷（不是 bloat，本輪不修，只回報）

1. **Retry Stop 卡死**（FAIL-022，已知）。`finish_stop` 失敗後 `_turn_active` 一直是 True，Retry 只會重播快取的錯誤（`service.py:3038`、`:3382-3391`）。S028 可以從結構上修掉。
2. **`error-text` class 沒有任何 CSS 規則**（✔）。Stop 錯誤（`trust.tsx:343`）與 source editor 問題（`DocumentEditor.tsx:425`）顯示時沒有錯誤樣式。
3. **`sensitiveMessagePattern` 會吞掉正當錯誤**（✔）。`backend.ts:131,253` 只要訊息含 `token`、`secret`、`authorization`、`bearer`、`traceback` 或 `api key` 就整句隱藏，而且也作用在業務錯誤上（`normalizeBusinessError` → `normalizeUiError`）。例如模型回「超過 context token 上限」時，你只會看到「Sensitive backend details were withheld」。
4. **Rust 對每個 result 都 emit 一次 event 再 invoke 回傳一次**（✔ `backend.rs:1545-1546`）。transcript 可能有數 MB，等於多一次 IPC 加一次完整 parse，而且 React 會把那個 event 直接丟掉。
5. **`TurnJournal.turn_logs` 每回合累加、從不清除**（`turns/journal.py`、`session.py:544`），production 沒有任何地方讀它。
6. `providers/doi_org.py:125` 的 `_encoded` 標註回傳 `str`，實際回傳 tuple。
7. 未追蹤的 `app/desktop/watch.out` 含一個 Windows 前景視窗標題（輕微隱私）。

---

## 6. 完整 ledger

格式：**ID — 狀態／動作 — 標題**，下列位置、證據、保留理由、動作、不確定、驗證。

### 6.1 協定與跨語言

**S001 — DECIDE／MERGE — `protocol.ts` 手抄 `contract.json`**
- 位置：`app/desktop/src/protocol.ts:1-1190`（常數、方法、event 與錯誤碼清單、所有 `*_SCHEMA` 字面量、`METHOD_REQUIRED_PARAMS` `:1183`）；`app/desktop/tests/protocol.test.ts:117-176`（parity test）。
- 證據：Python 在 runtime 讀 contract（`agent/desktop/protocol.py:17`）。`tsconfig.json` 已開 `resolveJsonModule`，但 `src` 沒有任何 JSON import。泛用的 field-rule 解譯器（`protocol.ts:1667-1778`）已經存在。
- 保留理由：未確立，只是讓 TS 端做 client 驗證。
- 動作：`import contract from "../protocol/v1/contract.json"`，刪約 1,080 行字面量與 parity test，保留手寫 DTO interface（`:1192-1580`）。
- 不確定：node `--experimental-strip-types` 測試需要 import attribute。與 S002、S004、S090 一起決定 TS 還要驗什麼。
- 驗證：`npm test`、`npm run build`（`tsc --noEmit`＋vite）、Python 與 Rust 的 contract 測試。

**S002 — DECIDE — Rust 逐方法驗證器**
- 位置：`app/desktop/src-tauri/src/protocol.rs:9-135`（常數）、`:280-390`（`required_params`／`allowed_params`）、`:534-790`（語意副本：document range、skill references、submitted context）、`:799-1010`（`validate_params`）、`:1242-1410`（`validate_event_data`）、`:1506-2300`（`validate_result_data`）、`:2339-2475`（bibliography）；tests `:2960`、`:3262-3527`、`:3527-3638`。
- 證據：Rust 轉送只需要 `requestId`、`sequence`、`ok`、`method`（判斷大結果豁免）與三種 process event。Python 收發兩端都會驗。manifest parity 測試只是為了守住手抄本。
- 保留理由：縱深防禦（WebView 內容含 LLM 輸出）；若論文要宣稱 Rust 是獨立驗證邊界。
- 動作（建議）：縮到只驗框架、envelope、`requestId`、`sequence`、process event 來源與禁止鍵掃描（`validate_safe_data`，約 40 行）。約減 2,000 行 prod 與 500 行 test。
- 不確定：reviewer 沒有逐行讀完每個方法分支，也沒有 `cargo build`。
- 驗證：`cargo test`、`npm test`、手動 GUI 冒煙測試。

**S003 — READY — Rust 對每個 result 送兩次到 WebView**（✔）
- 位置：`backend.rs:1545-1546`；consumer `backend.ts:312`、`App.tsx:1418`（非 event 直接 return）。
- 證據：同一個值先 `emit_protocol(value.clone())`，再 `sender.send(Ok(value))`。`session.turn` 與 `session.transcript` 不受 2 MiB 限制。
- 保留理由：無。
- 動作：result 只透過 invoke 回傳，不再 emit。
- 驗證：調整 `readiness_request_event_result_and_graceful_shutdown` 等 Rust 測試；`cargo test`、`npm test`。

**S004 — READY — TS 對同一個 result 驗兩次**（✔）
- 位置：`backend.ts:574`（`traceValidator.accept`，其內 `protocol.ts:2306-2307` 已呼叫 `validateResultData`）、`backend.ts:578`（再呼叫一次）。
- 動作：刪 `backend.ts:578`。驗證：`npm test`。

**S005 — READY — Python 送出時同一訊息驗 2–3 次**
- 位置：`protocol.py:359-361`、`:509-510`、`:665-677`（`success_result` → `validate_result_data`＋`validate_message`；`_encode_message` 再 `validate_message`；`validate_message` 內再跑 `_validate_safe_data`）。
- 動作：encode 路徑只驗一次。turn 的 pre-persist hook 另計（S025）。
- 驗證：`pytest tests/test_desktop_protocol_contract.py tests/test_desktop_server.py`。

**S006 — DECIDE／DELETE — 12 個從未發出的 request event**（✔ grep agent／rag／skills 皆 0）
- 事件：`request.progress`、`knowledge.progress`、`shutdown.progress`、`collecting.started`、`collecting.completed`、`tagging.started`、`tagging.folder_completed`、`metadata.written`、`writing.started`、`writing.file_completed`、`ingest.completed`、`ingest.failed`。
- 位置：contract `requestEvents`／`eventDataSchemas`（約 51 行）、`protocol.ts:50-71,485-535`、`protocol.rs:~1300-1360`、fixtures `ingest-progress-*`；另有 3 個 trace fixture 與 1 個 message fixture 拿 `request.progress` 當泛用事件用。
- 保留理由：只有在要做「結構化 ingest 進度」時才需要。
- 動作：從 contract 與三份驗證器移除，fixture 改用真實存在的 event。
- 驗證：三語言 contract 測試。

**S007 — DECIDE — 13 個沒有呼叫者的方法**（✔ GUI 端只有 `trust.tsx:329-331` 的顯示標籤）
- 方法：10 個 `knowledge.*`（`service.py:3665-3882`、`_hit_dto` `:4257-4273`、`_KNOWLEDGE_MUTATIONS` `:144`、`_prune_previews`），其中 `knowledge.init_workspace` 與 `knowledge.ingest_folder` 永遠 raise「not enabled yet」（✔ `:3772`、`:3805`）；`session.status`（`:1690`）、`session.shutdown`（`:3417`）、`extensions.status`（`:3884`）。
- 證據：React 呼叫 26 個方法，Rust 自己呼叫 `runtime.shutdown`，共 27／40。測試面：`test_desktop_service.py` 8 個、`test_project_permissions.py` 3 個；`backend.rs:1914` 把 `knowledge.overview` 當範例 request。
- 注意：RAG 在桌面版**仍是活的**，但走的是 composer 指令 `/init /ingest /sync /prune`（`service.py:1754-2081`，`_DESKTOP_SLASH_COMMANDS` ✔）與 agent 的 `rag_*` 工具，不經這些 RPC。
- 選項：(a) 全刪，約 220 行 Python＋三份 schema＋測試；(b) 保留 `overview`、`search`、`list_chunks`、`get_context` 給未來的知識庫面板，只刪 6 個 mutator 與 stub。`session.*` 與 `extensions.status` 只刪 RPC 註冊，內部函式保留（`workspace.select`、`session.delete` 會用）。
- 建議：近期沒有面板計畫就選 (a)。

**S008 — READY — contract 中沒人產生也沒人讀的欄位**
- 項目：
  - `messageTypes`（contract:6）。
  - 頂層 `documentContextSchema`（三語言都不讀）。
  - `session.turn.documentOperations`：沒有任何 producer，卻在 `protocol.py:372`、`protocol.rs:597,1628`、TS `DocumentOperationDto` 被驗證。
  - `methods[].requiredParams`：與 `params[].required` 重複。
  - `methods[].operation`：只有測試讀。
  - approval 的 operation enum 值 `extensions.apply`：實際值是 `extension.install`。
  - `candidateId`（`protocol.py:342`）。
- 動作：移除，連同只為它們存在的測試（例如「destructive 必須帶 `previewId`」）。
- 驗證：三語言 contract 測試。

**S009 — DECIDE — streaming 殘留 `streamKind: "final_only"`／`chunkCount: 0`**
- 位置：`conversations.ts:10,40-41,50,60,446-447,452,470`；`App.tsx:2404,2585`；`protocol.ts:675-676,1232-1234`；`service.py:1724,3250,3351`；`protocol.rs:1623`；`test_desktop_answer_stream.py:105-201`；`desktop/tests/answer_stream.test.ts`（名稱）。
- 證據：合法值只剩常數，TS 遇到其他值會 reject（`conversations.ts:446`）。
- 動作：端到端移除欄位，測試改名後併入一般 turn 測試。需要跨語言同步改，與 S006–S008 同一批做。

**S010 — DECIDE — `ollamaReachable`／`ollamaModelAvailable` 永遠是 None**
- 位置：`service.py:852-853`；GUI 顯示 unknown。
- 動作：二選一：真的去探測，或移除欄位。

**S011 — DECIDE — 只給測試用的 trace validator**
- 位置：
  - Rust：`ProtocolTraceValidator`／`RequestTraceState`（`protocol.rs:2691-2822`）、`parse_protocol_line(_from_origin)`（`:2494-2510`）、`PROTOCOL_METHODS`（`:15-57`，只有測試引用）。
  - Python：`TraceValidator`（`protocol.py:695-760`，只有 `test_desktop_protocol_contract.py` 用）。
  - TS：`ProtocolTraceValidator` 在 production 有用，但每個 request 新建一個，只為檢查 `turnId`／`sessionId` 回聲。
- 動作：Rust 版隨 S002 刪除；Python 版移到 `tests/` 當 fixture oracle 或刪除；TS 版改成兩個直接的 equality 檢查。

**S012 — DECIDE — fixtures.json 5,194 行、三語言各跑一遍**
- 位置：Rust `shared_*`（`protocol.rs:3527-3638`）、TS `protocol.test.ts:376-471`、Python `test_desktop_protocol_contract.py:443-490`；Python 測試寫死 28 個 result schema 名稱（約 `:30-60`）；`:516-575` 重複 bash-permission fixtures；`:83` `test_phase04_...v1_additions` 是歷史測試。
- 證據：`dcae226`（6 個 bibliography 方法）為 fixtures 加了 1,092 行，contract 只加了 160 行。
- 動作：S002 之後 Rust 不再跑 fixtures；刪掉寫死的名稱集合；移除死 event 的 fixtures；約定「每個方法一個合法例＋一個非法例」。

**S013 — DECIDE — `documentContext` schema 在 contract 中內嵌 11 次（約 90 行）**
- 動作：與 S001 一起改成單一定義（`$ref` 或載入時展開）。

**S014 — READY — 沒用到的 Tauri capability**
- 位置：`capabilities/main.json` 的 `core:app:allow-tauri-version`；`src/` 沒有 `getTauriVersion`。
- 動作：刪一行。驗證：build＋啟動。

**S015 — DECIDE（低）— 行動平台 scaffolding**
- 位置：`Cargo.toml` 的 crate-type `["staticlib","cdylib","rlib"]`；`lib.rs` 的 `mobile_entry_point`。
- 證據：只支援 Linux。
- 不確定：需要實際 build 確認。

**S016 — DECIDE — 權限的三個名字**
- 名稱：`bashPermissionMode`（session DTO；`service.py` 21 次、`src` 43 次）、`permissionMode`（持久化，`conversations/models.py:255-263`）、`mode`（`set_bash_permission` 參數）；元件叫 `BashPermissionControl`，但 `trust.tsx:387` 的 tooltip 說它管文件、citation、索引、MCP 與擴充。
- 動作：Phase 1 一次在線上協定中統一改名。

**S017 — DECIDE — 前端複製 Python 的解析規則**
- 位置：
  - `@Skill` token regex 有 5 份：`App.tsx:266-299`、`protocol.ts:1851-1869`、`protocol.py:259`、`agent/skills/runtime.py:278`、`conversations/models.py:541`。
  - `LATEX_CITE`：`citations.ts:245` 與 `skills/citation/citekeys.py:29`。
  - `CITATION_OFF_ARGUMENT`：`conversations.ts:744`、`chat.py:35`、`slash_commands.py:466`。
- 保留：`completionPrefix`（編輯器補全一定要在 client 端）。
- 動作：若後端能自己從原文推導 `skillReferences`，client 只送原文即可。
- 不確定：未確立後端是否已經重新推導。

### 6.2 Python 桌面後端（`app/agent/desktop/*`）

**S018 — DECIDE／DELETE — 舊的全域 catalog 建構路徑**
- 位置：`catalog.py:22-23`（`DEFAULT_PROJECT_*`）、`:144-160`（`__init__`／`_load_or_bootstrap`）、`:215-260`（`rebuild_from_conversations`，0 個呼叫者 ✔）、`:287-303`（reconcile 的 unknown-project 分支，在 scoped catalog 下不可達）。
- 證據：production 一律走 `_scoped_catalog`（`__new__`，`:690`、`:723`、`:790`）。舊建構子只被約 20 個測試點與 `fixture_session.py:580` 使用。可能是 `7773558` 改成 scoped history 後的遺留。
- 動作：刪除，給測試一個 scoped helper。
- 驗證：`pytest tests/test_desktop_conversations.py tests/test_desktop_fixture.py`。

**S019 — DECIDE — catalog 其實是衍生快取**
- 位置：`catalog.py`（840 行）；`service.py:1130-1180`（`session.retry_registration`）、`:2118-2165`、`_session_registered`／`_pending_registration`、`registrationStatus`／`registrationIssue`；`App.tsx:2419-2431`。
- 證據：`load_project_catalog` 每次呼叫都重掃整個歷史目錄再改寫；`CATALOG_MAX_PROJECTS=32`，實際只會有 1 個專案。
- 唯一獨有的行為：「catalog 指向不存在的對話時 fail-closed」。
- 選項：(A) 保留；(B) 直接從 `ConversationRepository.scan()` 推導，刪掉 catalog 檔、retry RPC、registration 狀態、UI 分支與相關測試。
- 建議：你確認不需要那個 fail-closed 行為後選 B。相關：S027、S070。

**S020 — DECIDE／MOVE — `fixture_session.py`（1,493 行）放在 production 套件**
- 位置：`agent/desktop/fixture_session.py`；`server.py:419-430`（✔ `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02`）。
- 證據：它重新實作了 ChatSession 的回合持久化（`_begin_turn`、`_recover_interrupted_turn`、`turn_outcome`、`run_display_only_turn`）；用 `getattr` 讀私有的 `_document_turn_active`（`:1063`、`:1084`）；import 私有的 `tool._format_records`（`:773`）。只有 5 個 Python 測試模組在用。
- 動作：移到 `tests/support/`；`test_desktop_crash_recovery` 改用測試自有的入口啟動子程序；刪掉 `server.py` 的開關。
- 驗證：那 5 個模組（需要可寫的 `/tmp`）。

**S021 — READY（隨 S020）— `documents.selected_text`**
- 位置：`documents.py:63`；只有 `fixture_session.py:782` 與 `test_desktop_documents.py:84` 使用。

**S022 — READY（隨 S020／S007）— `DesktopKnowledgeOperations.workspace_root`**
- 位置：`service.py:290`（`:1793` 讀取）；只有 fixture 會設定。

**S023 — READY — `_execute_desktop_extension_command` 回傳 tuple 但第二個值被丟掉**
- 位置：`service.py:2083-2116`；呼叫端 `:3168-3171` 丟棄 `_action`，並在 `:3150-3159` 重算同一個值。
- 動作：只回傳結果。

**S024 — READY — `_apply_controls` 是只做一次呼叫的 async 包裝**
- 位置：`service.py:1595-1602`。動作：inline。

**S025 — DECIDE — `_validate_turn_result_shape` 每回合跑兩次**
- 位置：`service.py:1704`（定義）、`:1747`（pre-persist hook，`:1513` 安裝）、`:3331`。
- 保留：第一次必須在持久化前 reject。
- 不確定：hook 只檢查文字，第二次檢查完整 result；需確認差異後再刪第二次，或註明為何兩次都需要。

**S026 — READY — `documents.py` 重複驗證**
- 位置：`undo` 對 `validate_snapshot` 呼叫兩次（`:382`、`:392`）；`prepare` 建好 candidate 後再檢查一次（`:256`）。

**S027 — DECIDE — 每次刷新側欄都重掃歷史**
- 位置：`service.py:859-920`、`:1293-1305`；測試 `test_desktop_service.py:1200-1239` 斷言 3 個 session 時是 2 次掃描＋6 次 load。`_reconcile_lagged_catalog_entries` 直接寫 `catalog._snapshot`（`:1303`、`:2213`）。
- 動作：隨 S019 解決，或快取 summary。

**S028 — DECIDE（結構）— 忙碌判斷複製 8 份**
- 位置：`_session_select` `:925-946`、`_session_rename` `:1031-1044`、`_session_delete` `:1082-1095`、`_session_create` `:1617-1634`、`_workspace_select` `:2170-2180`、`_runtime_shutdown` `:3427-3448`、`_shutdown_session` `:3461-3495`、`_require_idle_session` `:3541-3556`。
- 證據：每份都是對約 25 個 bool、計數器與 lock 的 if 串，訊息與錯誤碼略有差異。
- 動作：一個 operation-state 物件（`enter()`／`require_idle()`），保留現有細節差異（例如 `-self._project_read_count`）。FAIL-022 會變成一處可修。
- 驗證：desktop 全部測試＋Stop 失敗注入測試。

**S029 — READY — bibliography handler 的重複讀取**
- 位置：書目路徑解析 3 份（`service.py:1307-1320`、`:2476-2496`、`:2521-2535`）；每次 `bibliography.inspect` 重新解析 `list_styles()` 3 次（`:2251`、`:2295`、`:2328`）；inspect 之後 fingerprint 再讀一次書目（`:2284-2285`）；add 之後為了 fingerprint 再讀一次（`:2417`）。
- 動作：同一個 handler 內共用第一次讀到的結果。驗證：`pytest tests/test_desktop_bibliography.py`。

**S030 — DECIDE — `extensions.apply` 的三重計算與自我核對**
- 位置：display input 算了 3 次（`:600-604`、`:3954`、`:3957`）；DTO → 序列化 → 解析 → 重建 DTO 再比對相等（`:3994-4001`）；預先模擬容量的 `_validate_extension_apply_preview_capacity`（`:4390-4434`）。
- 保留：解析路徑本身用於從持久化文字重播。
- 動作：刪掉自我核對與預先模擬（防禦性，非必要）。

**S031 — READY — 為了不完整的假物件寫的建構期探測**
- 位置：`_materialize_session` 的 5 處 `inspect.signature` 探測（`service.py:1473-1511`）、`_session_factory_accepts_bash`（`:366`）；假 session 用的 `getattr`／`hasattr`／`isinstance` 分支（`:616`、`:1512`、`:1520-1528`、`:1573`、`:1577-1579`、`:2761`、`:2947`、`:3072`、`:3564`）。
- 證據：production 永遠用完整參數呼叫 `ChatSession.create`。
- 動作：一律傳完整 kwargs，測試 factory 改成接收 `**_kwargs`。
- 驗證：desktop 測試。

**S032 — DECIDE — 對同程序資料再做輸出驗證（約 350 行）**
- 位置：transcript bounds（`:1383-1414`）、`_knowledge_count`／`_knowledge_string_items`（約 70 行）、`_extension_binding_dto` 的大小與 secret 掃描（`:4298-4344`）、`_extension_apply_dto`（`:4436-4478`）。
- 保留：`_approval_context_is_safe` 與 secret regex（`:172-178`），因為與安全相關。
- 不確定：現行行為會把超大資料轉成 degraded 狀態，刪除後會改成在 encode 時失敗。

**S033 — DECIDE — service 內複製 contract 已做的檢查**
- 位置：rename 標題長度（`:1052` 對 contract 的 `maxBytes: 256`）、`set_bash_permission` enum（`:3406`）、`extension_apply_values`（`:3913-3930`）、graph 遞迴上限。
- 證據：contract 在 dispatch 前就會 reject。
- 差異：錯誤碼與訊息不同（`PROTOCOL_INVALID` 對專用錯誤碼）。

**S034 — KEEP（建議搬家）— `_map_exception`／`_exception_*`**
- 位置：`service.py:645-806`。這是錯誤對照表，建議移到 `errors.py`。

**S035 — KEEP — `DesktopServiceError(ProtocolError)`**
- 位置：`service.py:268`。空子類別，但承擔型別身分。

**S036 — DECIDE — desktop 測試膨脹**
- 超長 fixture journey 測試：`test_desktop_fixture.py:969`（280 行）、`:444`（147 行）、`:828`（141 行），與 `test_desktop_service.py` 的 composer 測試（`:1433`、`:1579`、`:846`、`:758`）重疊。
- 釘住過時行為的測試：`test_desktop_service.py:2171`、`:1342`、`:2041`；`test_project_permissions.py:168`（隨 S007）；`test_desktop_answer_stream.py`（隨 S009）。
- 建議：保留一條端到端 journey，刪重疊的逐指令複本。
- 不確定：重疊判斷主要依名稱與長度，測試本體未全讀。

**S037 — DECIDE（結構）— desktop 測試的假物件與私有存取**
- 證據：5 種假 session＋9 種假 service；5 個測試模組互相 import helper；`test_desktop_document_service.py` 有 34 處 `service._x`；`test_project_permissions.py:281-297` 手動設定私有的 turn 欄位。
- 動作：集中到 `tests/desktop_support.py`，並配合 S028 與 S052 改走公開介面。

### 6.3 Agent 核心（`app/agent` 除了 desktop）

**S038 — READY — 同步版 thinking helpers 只剩測試在用**（✔）
- 位置：`thinking/review.py:157`（`rewrite_prompt`）、`:187`（`review_draft`）、`:214`（`aggregate_candidates`）、`thinking/parsers.py:110`（`parse_reviser_output`）；re-export 在 `thinking/__init__.py:7-25,75-88`；`test_thinking.py` 約 13 個測試；`test_text_normalization.py:16,98` 用到 `invoke_text` 別名。
- 證據：production 走 async 版（`orchestrator.py:446,529,645,680`）。
- 動作：刪同步版，測試改測 async 版。
- 驗證：`test_thinking.py`、`test_thinking_session.py`。

**S039 — READY — `agent.llm.text.invoke_text`（prompt 字串版）**
- 位置：`llm/text.py`、`llm/__init__.py:8,13`；只有 `test_openrouter_model.py:14,136` 使用。
- 注意：不要和 `thinking` 裡的 `invoke_text_messages` 別名搞混。

**S040 — READY — `ChatSession.activate_citation_skill`／`deactivate_citation_skill`**（✔ production 0 個呼叫者）
- 位置：`session.py:925-945`（docstring 自己寫了 production 不會呼叫）。
- 成本：7 個測試檔約 40 處引用，要改成走 `/citation` 回合路徑。

**S041 — READY — `ChatSession.citation_service` 公開 property**
- 位置：`session.py:567`；setter（`:558-565`）只為測試存在。

**S042 — READY — `ChatSession.restore`**
- 位置：`session.py:1532-1555`；只有 3 個測試使用，desktop 走 `create(session_id=...)`。

**S043 — READY — `_active_skill_context_block` 轉手函式**
- 位置：`session.py:670`；唯一呼叫者 `orchestrator.py:525`。併入 S052。

**S044 — READY — 建構時重複檢查專案所有權**
- 位置：`session.py:189-195` 與 `_validate_snapshot_project`（`:267-275`，下一行就會被呼叫）。動作：刪 inline 那段。

**S045 — DECIDE — `skill_loader_node` 與 `skill_runtime_getter`**
- 位置：`graph.py:100`、`:358-363`、`:373`、`:382-383`；`session.py:240`。
- 證據：session 已在 `session.py:1188` 把 skill runtime 注入 graph 輸入；fusion 傳 None；`skill_instructions` 有值時 node 直接回傳 `{}`。`test_graph_skill_loader.py:62-84` 釘住它。
- 不確定：需確認 `SkillRuntime.instructions` 不可能為空。

**S046 — DECIDE — 對話 schema v1/v2 讀取器**
- 位置：`conversations/models.py:436-439`、`:641`；`repository.py:148-149`、`:195`、`:253-255`、`:276`；寫入時升版（`:428`、`:490`）；`test_conversation_repository.py:452-496`。
- 證據：`app/store/projects/*/conversations` 下 4/4 個檔案都是 v3（✔）。未檢查：其他研究專案設定在 `app/store` 以外的 `historyDirectory`。
- 選項：刪除（舊檔將無法讀取）／保留。

**S047 — DECIDE — `TurnJournal.turn_logs`**
- 位置：`turns/journal.py:13,29-38`；`session.py:544`、`:1200-1223`（`_record_turn` 是 async 但沒有 await 任何東西）。
- 證據：每回合累加、從不清除；production 只讀 `last_tool_calls`。`test_turn_finalizer` 與 `test_observability` 有讀 `turn_logs`。

**S048 — DECIDE — 只做 re-export 的 `__init__`**
- 位置：`agent/extensions/__init__.py`（14 個名稱，沒有任何地方從 package 層 import）、`agent/thinking/__init__.py`（40 個名稱，註解寫著「讓舊 importer 不變」）、`agent/tools/__init__.py`、`agent/adapters/**/__init__.py`。
- 另外：`agent/__init__.py` 會 eager import session 與 graph，與 `agent/README.md:49` 的規範矛盾。

**S049 — DECIDE — `agent/skills/broker.py`（32 行）＋`test_skill_broker.py`**
- 證據：只在 `resolve_tool_access` 之上多一個 ValueError。動作：inline 到 `runtime.py`。

**S050 — DECIDE — `agent/adapters/` 三個檔案只為一個函式**
- 證據：`create_rag_tools` 唯一呼叫者 `tools/inventory.py:22`。
- 動作：移到 `agent/tools/rag_tools.py`，同步更新 `test_adapter_formatting.py` 與 `agent/README.md`。

**S051 — DECIDE（低）— `turns/memory.py`（15 行）**
- 動作：`CanonicalTurnView` 併入 `turns/results.py`。

**S052 — DECIDE（結構）— 從外部改寫 `ChatSession` 私有屬性**
- desktop（`service.py`）：`_set_final_text_validator`（`:1513`）、`_set_prompt_persisted_callback`（`:1520-1526`）、`_document_turn_active = True/False`（`:3026`、`:3277`）、`_citation_policy`（`:2770`）、`_installer_context`（`:2788`）、`_skill_installer.bypass_approval`（`:2980-3024`）、`_load_skill_runtime`（`:3075`、`:3568`）、`_conversation_snapshot`（`:616`）、直接指派 `system_prompt_message`（`:1574`、`:2948`）。
- orchestrator：`_run_graph_turn`（`:407`、`:671`）、`_execute_graph`（`:244`）、`_base_prompt_history`（`:188`）、`_tool_availability_block`（`:165`）、`_visible_context_text`（`:534`）、`_active_skill_context_block`（`:525`）、`_prompt_master_skill_text`（`:513`）、`_operation_approval_handler`（`:209`、`:211`）。
- 動作：
  - 給 desktop 的 `SessionControls` 介面。
  - 給 fusion 的 `TurnHost` Protocol。
  - `_document_turn_active` 改成 `turn_outcome(document_turn=True)` 參數，從結構上就無法洩漏到下一回合。
- 建議先做 orchestrator：同套件，最好切。

**S053 — DECIDE — 一個 desktop 回合載入 skill runtime 3–4 次**
- 位置：`service.py:3071-3076`（預檢）、`session.py:1351-1356`、`:1090-1091`、`:1394-1396`、`service.py:3563-3571`（只為回答一個 bool）。
- 動作：公開的 `preflight_skills()` 回傳已載入的 runtime，讓 `turn_outcome` 直接接收。

**S054 — DECIDE（結構）— Skill policy 寫死在名稱上**
- 位置：`READ_ONLY_DOCUMENT_SKILLS`（`session.py:76`；`service.py:93`、`:3260` import）；`"skill-installer"` 字串在 `session.py` 出現 6 次（`:664`、`:806`、`:966`、`:979`、`:1040`、`:1355`）；citation 特例散在 `session.py:903-1115,1358`、`slash_commands.py:194,251,465`、`chat.py:111`、`service.py:3099,3118,3563`。
- 動作：在 manifest 加 policy 欄位（`read_only_document` 等），`grill` 是最簡單的第一個。

**S055 — DECIDE（結構）— thinking mode 字面值散在 8 處**
- 位置：`conversations/models.py:30,46,264`、`slash_commands.py:352`、`session.py:607,888-892,1032,1238`。
- 動作：一個 enum，加一張 mode → runner 對照表。

**S056 — DECIDE（結構）— `LocalWorkScope` 住在 RAG 包裝模組裡**
- 位置：`agent/ingest.py`；被 `tools/bash.py:27`、`read_file.py:20`、`rag_tools.py:12`、`session.py:26` import；ingest 又 lazy import `tools.bash._stop_process_group`（循環相依）。
- 動作：移到 `agent/local_work.py`。

**S057 — DECIDE（結構）— 安裝器狀態機散落兩處**
- 位置：`extensions/manager.py` 放了兩個無關的類別：`ExtensionManager`（`:374-706`）與 `SkillInstaller`（`:709-1127`）。ChatSession 身上有 5 個安裝器欄位與分支（`session.py:944-1115`、`:804-835`）。
- 動作：拆成兩個檔案，另抽出 `SkillInstallerHost`。

**S058 — DECIDE（結構）— `agent/cli/slash_commands.py` 也被 desktop 使用**
- 動作：移到 `agent/commands/`。

**S059 — DECIDE（結構）— 回合生命週期的處理梯重複**
- 位置：`run_display_only_turn`（`session.py:1242-1334`）與 `turn_outcome`（`:1336-1445`）的 persist、dedup、`except` 梯幾乎相同。
- 動作：一個 `_persisted_turn` context manager。兩者的錯誤訊息與 incident 記錄有差異，需保留。

**S060 — DECIDE — 已退役指令的墓碑**
- 位置：`slash_commands.py:224`（`_RETIRED_SKILL_COMMANDS`，`/skill`）、`:465-488`（`_CITATION_OFF_TOKENS` 說明訊息）、`chat.py:~110`（`_CITATION_STOP_ARGUMENTS`）；README 敘述：`agent/README.md:44-46`、`turns/README.md`、`tools/README.md:44`（`recall_history` 已移除）。
- 動作：刪除。這些是遷移記號，不是行為。

**S061 — READY — manifest 的舊欄位友善錯誤**
- 位置：`skills/manifest_schema.py:11-14,72-75`；`extra="forbid"` 已經會拒絕。
- 動作：刪除，同步更新 `test_skill_runtime.py:104,120`。

**S062 — READY — `tests/test_extension_baseline.py`**
- 證據：`registry.get("SKILL") is registry.get("skill")` 實際是 None is None，沒有檢查到東西；其餘測試與 `test_extension_manager`、`test_skills` 重複。
- 動作：只把 `test_skill_scan_ignores_only_regular_zip_sources` 移到 `test_extension_registry.py`，其餘刪除。

**S063 — READY — `tests/test_smoke.py`**
- 證據：docstring 還寫著「decoupling refactor 前後」；`test_imports` 沒有實際檢查。
- 動作：config 驗證測試移出，保留 `test_graph_builds_without_error`。

**S064 — DECIDE — `tests/test_history_retirement.py` 名不副實**
- 證據：名稱與 docstring 寫 Phase 06，實際上釘的是 archive hint 的字句（`session.py:605-643`）。
- 動作：改名，並決定要不要繼續逐字釘住 prompt。

**S065 — KEEP（有條件）— `tests/test_extension_packaging.py`**
- 釘住 `tool/` 目錄結構。目錄還在就保留（見 S132）。

**S066 — DECIDE（結構）— 測試對 ChatSession 私有屬性的存取**
- 證據：約 100 處（`_citation_service` 約 41、`_skill_installer` 27、`_fusion` 9 等）；最多的是 `test_skill_adherence` 26、`test_turn_finalizer` 15、`test_inline_skills` 10。
- 動作：隨 S052 逐步遷移，不一次重寫。

**S067 — DECIDE — Python 相依**
- `chromadb`：沒有直接 import，經由 `langchain-chroma` 帶入，而 `rag/store/cache.py` 依賴它的內部。目前等於拿來釘版本。
- `openrouter`：被直接 import（`agent/llm/openrouter.py:16`、測試），卻沒有宣告，是經 `langchain-openrouter==0.2.6` 帶入的遞移相依。
- 改相依需要你核准（AGENTS.md）。

**S068 — KEEP — 其他 Python 相依**
- `python-docx`：vendored bime_word 子程序需要。
- `lxml`、`pybtex`（除非 S105 選合併）、`typing-extensions`、`openai`、`tiktoken` 等：皆有 import。

**S069 — KEEP — 看起來可刪但有用途**
- AgentConfig 28 個欄位都有 production 讀取。
- `tool_access_resolution` 每回合重算：成本低，且結果會隨狀態變。
- `uninstall_diagnostic_log`：與 install 成對，測試清理需要。

### 6.4 前端（`app/desktop/src`、`tests`）

**S070 — DECIDE — 多專案側欄 scaffolding 對上單專案後端**
- 位置：`App.tsx:1049`、`:1625`、`:1784-1813`、`:2790-2808`；`:207-222` 在回傳的專案數不是 1 時直接 throw。
- 動作：隨 S019，改成單一專案清單。

**S071 — READY — 重複或沒用到的文件型別**（✔ 兩個 DTO 0 引用）
- 位置：`DocumentOpenDto`、`DocumentResultDto`（`protocol.ts:1476-1499`）；`DocumentSnapshot`（`DocumentEditor.tsx:55`）等同 `DocumentContextDto`（`protocol.ts:1421`）；`App.tsx:943-952` 的 `DocumentResult`。
- 動作：刪兩個 DTO，統一用一個 snapshot 型別。

**S072 — READY — 沒用到或只給測試用的匯出與零件**
- 位置與證據：
  - 只有測試使用：`FULL_TEXT_RESULT_METHODS`（`protocol.ts:5`）、`METHOD_REQUIRED_PARAMS`（`:1183`）、`parseProtocolLine`（`:2239`）。
  - `"failure-cleared"` action（`conversations.ts:202,481,716`）沒有任何 dispatcher（✔ 測試也 0）。
  - `data-document-menu` 屬性（`App.tsx:924`）沒有任何 JS 或 CSS 選取。
  - `acceptApprovalEvent` 第 6 個參數 `activeTurnId`（`trust.tsx:223-231`）只有測試傳。
  - `reconciledTurnCount`（`conversations.ts:351`）就是 `Math.max`。
- 驗證：`npm run build`、`npm test`。

**S073 — READY — `conversationInteractionState`**（✔）
- 位置：`conversations.ts:222-228`、`:789-800`；14 處測試引用。
- 證據：`createDisabled`、`selectDisabled`、`controlDisabled` 全都等於 `turnActive`。

**S074 — READY — `sessionCreateParams`**
- 位置：`App.tsx:171`，只回傳 `{projectId}`，匯出只為了測它。

**S075 — READY — 後端 snapshot／lifecycle 處理寫了 4 份**
- 位置：`App.tsx:1370-1403`、`:1515-1547`（幾乎逐字相同）、`:1589-1591`、`:1815-1838`。
- 動作：一個 `applyBackendSnapshot()`。
- 驗證：`App()` 沒有整合測試，需要 `tsc` 加手動重啟與 crash 測試。

**S076 — READY — 死的 CSS 規則**
- 位置：`.file-open-dialog .document-error`（約 `:1213`，沒有對應 markup）、重複的 `.empty-state`（約 `:220-243`）、`.writing-workspace .transcript{min-height:0}`（約 `:1237`，與 `.transcript` 重複）。
- 另見 §5 #2（`error-text` 沒有樣式）。

**S077 — DECIDE — `BoundedRuntimeDiagnostics`／`toBoundedDiagnostics`**
- 位置：`backend.ts:19-21`、`:58-75`、`:438-464`。
- 證據：對協定驗證過的 DTO 再設一次上限。

**S078 — DECIDE — browser-preview 模式**
- 位置：`backend.ts:97,107,111,282-293`；`App.tsx:1359`、`:2736-2748`、`:2880`。
- 證據：目前只顯示降級橫幅並停用控制項。
- 選項：(1) 刪除，約 6 個守衛＋1 個測試；(2) **改成用 fixture 驅動的預覽**，建議選這個，重設計 UI 時最省力。

**S079 — DECIDE（結構）— `applyConversation` 每個 action 跑兩次 reducer**
- 位置：`App.tsx:1109-1117`（先手動跑一次更新 ref，再 dispatch 一次）。
- 動作：改成 store 式 reducer 或 `useSyncExternalStore`。

**S080 — DECIDE（結構）— approval 清除區塊重複 11 次**
- 位置：`App.tsx:1252,1273,1385,1415,1528,1744,1834,2107,2140,2410,2455`；同一概念用了 3 個 ref＋2 個 state。
- 動作：一個 `useApproval`。

**S081 — DECIDE（結構）— focus trap 與 popup menu 各自複製**
- 位置：focus trap 在 `App.tsx:185-193`、`:2969-2978`、`:3003-3010` 與 `trust.tsx:286-303`；四個選單各自處理 Esc 與 blur（`DocumentHeader` `App.tsx:924-939`、對話選單 `:2940-2964`、`ThinkingControl`、`ExportMenu`）。
- 動作：共用 Modal 與 Menu。

**S082 — DECIDE — 29 處 `as unknown as XDto` 與 19 處 id 回聲檢查**
- 動作：一個型別化的 `api.ts`，逐方法包裝並集中處理回聲檢查。回聲檢查要不要留，與 S001／S002 同一個問題。

**S083 — DECIDE（結構）— 為測試而存在的匯出與測試基礎設施**
- 證據：`App.tsx` 有 31 個只為測試存在的匯出；5 個測試檔各自啟 Vite SSR 載入模組，並手寫該模組的型別（例如 `conversations.test.ts:1-140`）；`tsconfig` 只 include `src`，測試沒有型別檢查。
- 動作：抽出純函式模組，測試直接 import，`tests` 加入 type check。

**S084 — DECIDE — `styles.test.ts`（34 行）**
- 證據：它對 `:root` 的 font-size clamp 數值做 regex 比對，等於在執行 INV-021。
- 動作：UI 重設計時同步修改 INV-021，並改成行為層的可讀性測試。

**S085 — READY — 檢查已退役「Product Plan Mode」不存在的原始碼 grep 測試**
- 位置：`protocol.test.ts:178-198`。

**S086 — DECIDE — 其他 grep 原始碼的測試**
- 位置：`editorZoom.test.ts:64-71`（grep `DocumentEditor.tsx` 的按鍵綁定）、`trust.test.ts:400-409`（對 `App.tsx` 原始碼做 regex）。
- 動作：抽出元件後改成行為測試。

**S087 — DECIDE — 在渲染結果上斷言 class name**
- 位置：`citation_preview.test.ts:124,127,139,140,157`；`conversations.test.ts:360,546`。
- 動作：改斷言 role、文字與 aria，讓樣式 hook 可以自由改。

**S088 — DECIDE — 大型合成資料測試**
- 位置：`conversations.test.ts:308-352`（14 萬個子元素 ×3）、`:551`；`protocol.test.ts:217`。
- 動作：三個合併成一個。

**S089 — DECIDE — `sensitiveMessagePattern`**（✔，見 §5 #3）
- 位置：`backend.ts:131`、`:253`。
- 證據：Python 已有 `FORBIDDEN_DATA_KEY_FRAGMENTS` 與診斷 log 的遮蔽。
- 建議：刪除或大幅縮小 pattern。

**S090 — DECIDE（隨 S002）— TS 對 Rust snapshot 做逐鍵驗證**
- 位置：`backend.ts:138-226`。

**S091 — DECIDE — 寫死的 fallback 與重複的 enum 檢查**
- 位置：fallback `SessionCreatedDto` 寫死 `graphRecursionLimit: 64`（`App.tsx:2693-2705`）；`reconcileBashPermissionAck` 重複檢查 enum（`trust.tsx:443-453`）。

**S092 — READY — `generation?`／`projectEpoch?` 標為可選，但所有呼叫端都有傳**
- 位置：`conversations.ts:156-160`、`:203`、`:480-482`。動作：改成必填。

**S093 — DECIDE（結構）— 原生 picker 繞過 backend client**
- 位置：`App.tsx:1287`、`:1682` 直接 `invoke("pick_*")`。
- 動作：收進 `api.ts` 或 hook。

**S094 — DECIDE（小）— `index.html`**
- 證據：`lang="zh-Hant"`，但 UI 是英文；`color-scheme` 鎖定 light。

**S095 — KEEP — 前端看似可刪但有用途**
- `editorZoom.ts`：記住縮放大小是使用者可見的功能。
- approval owner 追蹤：P1 修正需要它，S080 時併入 hook。
- 測試注入縫（`SafeContent` 的 `openExternal`、`fetchTranscriptPage` 的 `request`、`isCurrent`）：拆模組後自然消失。
- `completionPrefix`：編輯器補全需要。

**S096 — DECIDE（結構）— CSS 地基**
- 證據：
  - 0 個 CSS 變數；107 個不同 hex 色（189 次使用）＋17 個 rgba；近似灰階 `#66716d`、`#68716e`、`#626a68`、`#626b67`。
  - 三代寫法：`:1-1084` 多行規則、`:1085-1221` 混入的 media query、`:1222-1299` 後追加的單行規則，media query 分散在 4 處。
  - class 命名綁在角色上：`approval-dialog` 被 rename、delete、chooser 借用；`extension-error` 被非擴充的錯誤借用。
- 動作：`tokens.css`（約 15 個變數）、按元件拆檔、整併 media query、不再寫死 light。

**S097 — DECIDE（結構）— 拆解 `App()`**
- 證據：2,034 行（`:1026-3059`）、35 個 `useState`、35 個 `useRef`、14 個 effect、42 個 `useCallback`、`.current` 讀取 299 次；`SlashComposer` 接 22 個 props；JSX 內有超過 1,000 字元的單行（`:2870`、`:2884`）。
- 動作：
  - hooks：`useBackendEvents`（約 200 行）、`useDocumentWorkspace`（約 190）、`useApproval`（約 70）、`useWorkspaceOperations`（約 60）、`useTurn`（約 335）、`useConversationCatalog`（約 400）、`useExtensions`（約 95）。
  - 元件：`Composer`、`Transcript`、`Sidebar`、`DocumentPane`、`ProjectChooser`、`RuntimeDetails`。
  - `trust.tsx` 拆開：它混了 ApprovalDialog、composer 控制項與擴充流程。
  - annotation UI 移出 `DocumentEditor`（chat 也在用）。
- 目標：`App()` 只剩 300–400 行組裝。

### 6.5 Rust 宿主與啟動器

**S098 — READY — PowerShell 腳本重複設定編碼**
- 位置：`WINDOWS_PICKER_SCRIPT` 對 `[Console]::InputEncoding` 設了兩次（`backend.rs:~764`）。

**S099 — DECIDE（小）— `seen_request_ids` 在整個 generation 期間只增不減**
- 位置：`backend.rs:161`。Python 與 TS 也都會擋重複 id。

**S100 — DECIDE（低）— snapshot 的 `stderrLines`／`stderrBytes`**
- 位置：TS 會解析（`backend.ts:200`、`:221`），但沒有任何地方顯示。

**S101 — READY — `BackendSupervisor::new` 與 `for_test` 重複建構**
- 位置：`backend.rs:226`、`:240`。

**S102 — READY — `main.py` 特判不存在的 `public/` 目錄**
- 位置：`main.py:20`、`:24`。
- 另外：`main.py` 沒有監看 `app/desktop/protocol/`，目前無害，因為 Rust 只在測試裡 `include_str!`。

**S103 — DECIDE（結構）— `backend.rs` 混了六種職責**
- 職責：supervisor（`:225-690`）、Tauri 命令（`:689-755`）、picker（`:757-897`）、啟動設定與 stderr log（`:941-1090`）、IO 執行緒（`:1093-1330`）、協定處理與轉送（`:1332-1706`）。
- 動作：picker 移到 `picker.rs`；`handle_python_line`（約 165 行）在 S002、S003 之後拆開。

**S104 — KEEP — Rust 端必要的部分**
- picker：WSLg 沒有 Linux 檔案對話框，`AttachThreadInput` 是必要手段。
- `diagnostic_log_dir`：刻意與 Python 版對齊，有測試綁住。
- `allows_oversized_success_prefix`：大 transcript 需要豁免，但與 Python 的序列化前綴耦合，值得記下。
- exit 輪詢、所有 Cargo 相依。

### 6.6 Skills、citation 與 RAG

**S105 — DECIDE — citation bundle（`cite/`）與專案書目庫是兩套儲存**
- 位置：`skills/citation/storage.py`（399 行）、`bibtex_canonical.py`（169 行）、`authority.export_bibtex`、`providers/doi_org.py:167-179`（`fetch_bibtex`）、`service.py:30-33,55-58,167-170,372-399`、`types.SaveReceipt.bundle_path`、`pybtex` 相依、`legacy_v1_bundle` fixtures 與 bundle 測試。
- 證據：production 只在 `storage._find_existing` 讀回 bundle（判斷能不能重用）；`references.json` 由 CSL 產生，不靠 BibTeX；整條 BibTeX 鏈只為產出 `reference.bib`。每次 DOI 存檔打兩次 doi.org（CSL 一次、BibTeX 一次）。
- 保留理由：CLI 沒有專案書目庫；receipt 的信任錨定在 bundle 寫入；可作為 provenance 紀錄（未確立你是否需要）。
- 選項：(a) 維持；(b) 書目庫成為唯一儲存，receipt 改為記憶體內的信任 token。
- 建議：若 CLI 可以寫入預設書目庫或不再存檔，選 (b)。
- 不確定：牽動 `tool.py` 輸出與 receipt 型別。

**S106 — READY（若 S105 選 a；選 b 則無須處理）— v1 bundle 讀取器**
- 位置：`storage.py:19`、`:190-203`、`:233-253`、`:326-339`；`types.py:11-13`、`:129-147`；`HASH_LENGTHS` 中的 20 與 64；`tests/fixtures/legacy_v1_bundle`＋`test_citation_storage.py:253,357`。
- 證據：沒有任何 writer 會產生 v1 或 `identity_verified`；磁碟上唯一的 bundle 是 v2（reviewer 檢查）。

**S107 — KEEP — 兩組看似重複、實際各有用途的設計**
- chat 的 `[[cite:id]]` 與文件的 `[@key]`：介面不同。
- 手寫的 `citekeys.py`（447 行）與 Pandoc：編輯器需要 UTF-16 位置，面板也要在沒有 Pandoc 時運作；differential test 是對外部工具比對，不是退役實作。

**S108 — READY — 只剩測試在用的 citation 符號**（✔ 皆為 production 0 引用）
- 位置：
  - `csl_render.style_path`（`:59`）
  - `library.DEFAULT_LIBRARY_FILENAME`（`:32`，名稱由 `catalog.py` 自己持有）
  - `library.add_item`（`:414-420`，15 處測試；`service._link_library` 自己做 load、merge、write）
  - `SourceRegistry.trusted_receipt`（`registry.py:53`，8 處測試）
  - `ProviderState.from_dict`（`types.py:64`）
  - `PublishedDateFilter.within_years`（`types.py:76`）
  - `DoiOrgClient.fetch_registration_agency`（`doi_org.py:181`）
- 動作：刪除，測試改用正式路徑。驗證：`pytest tests/test_citation_*.py`。

**S109 — READY — gate 的 `user_input` 是無作用參數**（✔ `gate.py:49` 直接 `del user_input`）
- 位置：`gate.py:42-69`；`session_policy.py:191`。

**S110 — READY（低）— `render.RenderedTurn.cited_sources`／`format_bibliography_entry`**
- 位置：`render.py:32-52`；production 只用 `.text`。

**S111 — DECIDE（低）— `CitationProviderHub.aclose`**
- 位置：`hub.py:180`；只有測試呼叫，production 從不關閉 client。

**S112 — DECIDE（低）— `rag_list_chunks` 的 tool schema**
- 位置：`rag/tools.py`；沒有綁給 agent。保留它是框架中立的 contract 設計，也可刪 schema。

**S113 — DECIDE（低）— `Hit.score` 永遠是 None**
- 位置：`rag/types.py`。動作：刪欄位或真的填值。

**S114 — READY — `VectorRetriever` 只是轉手**
- 位置：`rag/retriever/vector.py`（22 行）；唯一呼叫者 `rag/api.py:93`。
- 動作：inline，刪掉 `retriever/` package。

**S115 — READY — `BaseStore` ABC**
- 位置：`rag/store/base.py`；沒有任何呼叫端依賴這個抽象。

**S116 — DECIDE（低）— RAG 的單檔 package 與 lazy `__getattr__`**
- 位置：`rag/chunker`、`embedder`、`llm`、`tagger`、`retriever`、`utils`；`rag/__init__.py:9-52`。
- 注意：`tests/rag/test_tools_contract.py:64` 依賴 lazy 行為。

**S117 — READY — 註解與程式碼矛盾**
- 位置：`rag/llm/__init__.py:1-5` 說 agent 不該從這裡 import，但 `agent/llm/openrouter.py:19` 就是這樣做。
- 動作：改註解，或把常數搬到 agent。

**S118 — READY — `csl_render` 重複載入**
- 位置：render 與 export 都載入書目兩次（`:283`、`:263`）；`styles.json` 每次呼叫都重新解析（`:97`、`:50`）。

**S119 — READY — 小型重複 helper**
- 位置：`_user_agent`（`crossref.py:46`、`datacite.py:58`）、arXiv id regex（`library.py:221`、`resolution.py:71`）、`render._FENCE_OR_CODE_RE` 與 gate 的 regex。

**S120 — READY（外觀）— 私有成員與 inline import**
- 位置：`service.py:62` 使用 `hub._fetch`；`ProviderError` 在 `hub.py:119-123,156,164` inline import 三次。

**S121 — DECIDE — citation 測試重疊**
- 位置：`test_citation_workflow_tool.py:485,510` 與 `test_citation_save_isolation.py:381`；`test_citation_skill_activation.py`、`test_citation_slash_command.py`、`test_inline_skills.py`（同一組啟用 contract）；`test_citation_e2e.py`（924 行）與 `test_citation_doi_first_save.py`（同一條 search → save 流程）。
- 不確定：建議在 S105、S040 之後再整理。

**S122 — READY — `tests/test_ingest.py` 放錯位置**
- 證據：它測 `rag.cli.ingest`，依 AGENTS.md 應放在 `tests/rag/`。

**S123 — DECIDE（結構）— citation 與 RAG 的邊界外洩**
- `skills/citation/storage.py:43` 與 `library.py:24` import `agent.paths`：引擎反向依賴 app。
- bibliography handler 內嵌在 `service.py:2245-2547`：應抽成 `desktop/bibliography.py`。
- `rag/cli/ingest.py` 放著函式庫 API（`ingest_repo`、`ingest_single`），被 `agent/ingest.py` import。
- 新增 provider 要改 4 處。

**S124 — KEEP — skills 與 RAG 中必要的部分**
- `_prompt-master`：`session.py:1145` 在 extended thinking 時讀取；`references/` 是否被讀未確立。
- 5 個 CSL 樣式都有被引用。
- `types.py` 的嚴格反序列化：信任邊界，`test_turn_finalizer` 會偽造 receipt。
- `library.LAYOUTS`：保留使用者 JSON 的排版。
- vendored `bime-word` 與 `web-search-mcp`：要與 manifest 逐位元一致，`dist/` 沒有被追蹤。

### 6.7 Repo 整潔、文件與流程

**S125 — DECIDE — 已完成的計畫紀錄**
- 位置：`harness/plans/2026-11-07-citation-panel-revamp/`（89 檔）、`2026-11-14-grill-genres-document-context/`（35 檔）；`for_agents/testing-strategy.md:27-30` 有連結過去。
- 建議：等你自己的 GUI checklist 與 live grill eval 結束後，沿用 `git show <sha>:…` 慣例刪除。

**S126 — DECIDE — 根目錄的 `NOTES-grill-skill-and-document-context.md`（未追蹤）**
- 動作：移到 `note/` 或提交。

**S127 — DECIDE — `note/20261106/`（未追蹤，8.2 MB）**
- 你的研究資料，與程式碼無關，不判斷內容。決定要放在 repo 外，或在 `note/` 下追蹤。

**S128 — READY — `app/desktop/watch.out`（未追蹤，509 B）**
- 證據：picker 調查的遺留檔，含視窗標題。動作：刪除。

**S129 — READY — 根目錄的 `__pycache__/`（09-23 的過期 .pyc，已被 ignore）與 `harness/plans/.claude/.cc-writes`（空目錄）**
- 動作：刪除。

**S130 — DECIDE — RAG 文件重複**
- 位置：`rag/README.md:60-77` 與 `rag/docs/API.md:34-51` 重複同一段歷史；`API.md` 把 config、api、tools 的說明再寫一遍（同一內容共 4 份）。
- 動作：只留一處，`API.md` 縮薄。

**S131 — DECIDE — `AGENTS.md` 過時**
- 證據：它提到不存在的 `issue/`，卻沒提 `harness/` 與 `for_agents/`。這是你的治理文件，由你決定措辭。

**S132 — DECIDE — `tool/local/` 預留區**
- 位置：`tool/local/README.md`、`.gitignore` 規則、`pyproject.toml` include、`extensions/discovery.py:230`、`app/README.md:11`。
- 證據：明寫 v1 不支援。若沒有計畫就刪除。

**S133 — DECIDE — README 與 UI 細節綁在一起**
- 證據：root README 逐一描述按鈕名稱與互動（43 個 commit 改過它）；`:134` 一個 bullet 約 1.5K 字。每次 UI 重設計都得同步大改 README。
- 建議：使用說明改寫成「概念＋流程」，按鈕層級的細節留給 UI 本身。

**S134 — DECIDE — 分支策略**
- 證據：`GUI` 領先 `main` 656 commits，`main` 自 07-24 起停滯；`clean` 是 `GUI` 的舊祖先。
- 建議：在大重構前把 `GUI` 合回 `main`，讓 `main` 重新成為主線，`clean` 可以刪除。

---

## 7. 估計減量（建議全部採納時；屬估計，非保證）

| 區域 | 刪除 | 搬移／重整 |
|---|---|---|
| 協定 | TS 約 1,080、Rust 約 2,000 prod＋500 test、Python 約 220 handler＋100+ 驗證，以及死詞彙相關 fixtures（數百行） | — |
| `service.py`＋`catalog.py` | 約 700–1,100 | 約 2,400–2,800 行移出成模組 |
| `fixture_session.py` | — | 1,493 行移出 production |
| Agent 核心 | 同步 twins、死方法、墓碑、re-export 等（數百行） | ChatSession 公開 API、installer host、`local_work` |
| Citation | 選 S105(b)：`storage.py` 399＋`bibtex_canonical` 169＋鏈上程式碼＋`pybtex` 相依；否則只刪 v1 讀取器 | — |
| 前端 | 數百行（helpers、DTO、CSS 死規則、測試） | `App()` 2,034 → 300–400 行；CSS 變數化 |
| 測試 | 釘住私有實作與退役行為的測試；測試總數下降是預期的 | 假物件集中化 |

---

## 8. 覆蓋與限制

- **未執行任何工具鏈。** tsc、cargo、pytest、npm 都沒跑：一方面是唯讀，另一方面是避免把快取或 target 寫進 repo。因此 TS 與 Rust 的「未使用」結論全來自 grep，而不是編譯器警告。
- **主線程親自複核的項目：** S003、S004、S006、S007、S020 開關、S025 位置、S038、S040、S046（store 版本）、S071、S072（`failure-cleared`）、S073、S089、S108、S109，以及 `error-text` 與 `invoke_text` 的呼叫面。
- **修正一處 reviewer 錯誤：** 有 reviewer 說桌面版透過 10 個 `knowledge.*` RPC 使用 RAG，這是錯的。GUI 從不呼叫那些方法，實際路徑是 composer 指令與 agent 工具（已反映在 S007）。另外把 `sensitiveMessagePattern` 的範圍更正為 `token`、`secret`、`authorization`、`bearer`、`traceback`、`api key`（不含單獨的 `key`）。
- **只做部分閱讀的區域：**
  - Agent 核心 reviewer：`conversations/repository.py`、`observability.py`、`diagnostics.py`、`document_context.py`、`thinking/{orchestrator,prompts,schemas,trace}.py`、`tools/{access,bash,read_file,policy_node}.py`、`turns/{execution,safety,trace,results}.py`、`extensions/*` 除 manager 外、`skills/{runtime,metadata}.py`、`llm/{openrouter,thinking}.py` 只有 AST 掃描或 grep，未逐行讀。這些模組「沒列出問題」只代表**沒查**，不代表乾淨。
  - Rust：`backend.rs:260-385`、`510-560`、`590-690`、`1555-1714` 未讀；`protocol.rs` 的逐方法 body 未逐行讀。
  - Citation：`resolution.py`、`citekeys.py`、`openalex.py`、`crossref.py` 的本體未讀；`grill_eval.py` 只看函式清單。
  - 測試：多數測試檔只看名稱、大小與抽樣，所以「重疊」類判斷（S036、S088、S121）信心較低。
- **刻意排除：** vendored `bime-word` 與 `web-search-mcp` 的內部；`note/`、`cite/`、`app/store/` 的內容（只檢查了 schema 版本）。
- **不保證**已找到所有死路徑。
