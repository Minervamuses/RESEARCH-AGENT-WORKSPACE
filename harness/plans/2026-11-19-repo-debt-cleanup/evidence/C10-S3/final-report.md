# Repo 債務清理：最終彙報（C10-S3）

- **計劃**：`harness/plans/2026-11-19-repo-debt-cleanup/`（目標與決策見 [GOALS.md](../../GOALS.md)，路線見 [PLANS.md](../../PLANS.md)，狀態見 [build-log.md](../../build-log.md)）
- **撰寫日期**：2026-11-22；分支 `GUI`；彙報撰寫時的最後一個 commit 是 `4ca4f72`（`[C10-S2]`）。
- **證據引用方式**：每個數字與狀態後面括號內是 build-log 事件、步驟 ID 或 `evidence/<步驟>/` 路徑。少數數字是撰寫本彙報時由唯讀指令重算，已標明「撰寫時重算」。
- **重要聲明：GUI 沒有被執行者驗證。** 執行者看不到畫面，也沒有啟動桌面 app。所有「畫面行為不變」與「畫面會變成……」的敘述，只來自程式碼、`tsc`、`vite build`、`npm test` 的靜態渲染測試與 evidence 的推論，第 10 節的清單必須由你本人操作後才算驗收。

---

## 1. 總結

### 1.1 S-ID 結果（與第 2 節表格逐列相符）

| 結果 | 項數 | 說明 |
|---|---:|---|
| APPLIED | 76 | 完成。 |
| 部分 | 8 | 只做了 GOALS 納入的部分或附理由保留：S026、S029、S036、S037、S066、S096、S121、S123。 |
| Blocked | 0 | 沒有任何階段被阻塞（build-log 狀態表：C1–C9 皆 Complete）。 |
| 未納入 | 41 | GOALS「不納入」（含長尾 DECIDE、R5、使用者的資料與治理文件）。 |
| KEEP | 9 | 稽核確認有用途，不動：S034、S035、S065、S068、S069、S095、S104、S107、S124（S034、S035 在 C7-S8a 只搬家）。 |
| 未確認 | 0 | 每個 S-ID 都找得到結果依據。S001、S019、S066 的 S-ID 標籤沒有寫在 build-log／evidence，依 PLANS 的歸屬與步驟內容對應，已在表格註明。 |
| **合計** | **134** | S001–S134 |

- 稽核標為 READY 的 46 項：44 項 APPLIED、2 項部分（S026、S029，皆附保留理由），符合 GOALS G8「APPLIED 或附理由」。
- 完成 = APPLIED 76 + 部分 8 = 84 項；阻塞 0 項；未納入 41 項；KEEP 9 項。

### 1.2 階段與最終檢查

- build-log 狀態表：C1–C9 為 Complete，C10 為 In progress（C10-S0、S1、S2 已完成；C10-S3 就是本檔）。本檔不修改 build-log；依 phase-10 的驗收，build-log 的 C10 列要在本彙報提交後標為 Complete，下一步寫「使用者：GUI 清單、`$infrastructure` 重新整理、未處理的決策」。
- 最終程式狀態（`e9436fc`，其後只有 evidence 的行尾空白清理）上的四套檢查（`evidence/C10-S2/metrics-after.md`）：

| 檢查 | 結果 | 耗時 | C1-S2 基線（`evidence/C1-S2/baseline.md`） |
|---|---|---:|---|
| 完整 pytest（沙箱外） | 1827 passed（2 warnings） | 79 s | 1,808 passed、64.58 s |
| `npm test` | 253 pass、0 fail | 13 s | 329 pass、11.25 s |
| `npm run build`（`tsc`、`tsc -p tsconfig.test.json`、`vite build`） | 通過 | 8 s | 通過（739 modules）、0.87 s（只有 vite build） |
| `cargo test --locked`（沙箱外） | 35 passed | 9 s | 42 passed |
| `git diff --check 4f488eb~1..HEAD` | 無輸出（第一次抓到 14 行行尾空白，全在本計劃的兩個 evidence 檔，已清除） | — | — |

- 測試數量下降是預期的：刪掉的功能（knowledge RPC、bundle、catalog、browser preview、Rust 與 TS 的逐方法驗證）連同其測試退役，每項退役紀錄在各步驟 evidence。四套都沒有失敗、略過或既有失敗。
- 全部變更範圍（撰寫時重算：`git diff --stat 4f488eb~1..HEAD -- app`）：204 個檔案、+15,345／−19,696 行；本計劃自 `4f488eb`（`[C1-S1]`）起共 77 個 `[Cn-Sm]` commit（`git log --oneline 4f488eb~1..HEAD`）。
- 沒有建立或切換 branch、沒有 push（依 PLANS 執行契約；本彙報沒有檢查遠端狀態）。

### 1.3 需要你做的事（詳見後面各節）

1. 操作第 10 節的 GUI 清單（58 項；前 37 項為 C8／C9 標示的高風險或需人工項目）。
2. 以 `$infrastructure` 重新整理 `for_agents/`（第 8 節）。
3. 決定第 11 節的未處理事項，尤其是掃描快取（R3）、`retryable` 不一致、P8 是否維持。
4. 視需要處理第 9 節 `AGENTS.md` 的過時句子與第 12 節的殘留資料。

---

## 2. S-ID 結果表（S001–S134）

欄位：稽核標籤（READY／DECIDE／KEEP，取自 [稽核原文](../../context/repo-debt-audit-2026-11-19.md)）、稽核標題、本計劃結果、對應步驟 ID（commit 以 `git log --oneline` 的 `[Cn-Sm]` 標記對應）、說明。

| S-ID | 稽核標籤 | 稽核標題 | 結果 | 步驟 | 說明與依據 |
|---|---|---|---|---|---|
| S001 | DECIDE/MERGE | `protocol.ts` 手抄 `contract.json` | **APPLIED** | C3-S2 | 與 U1 同一步；S-ID 標籤未寫在 build-log，內容對應見 `evidence/C3-S2/ts-contract.md`（`protocol.ts` 讀 contract，2,333→1,016 行（C3-S2）、C3-S6 記 1,094、C10-S2 量為 1,100） |
| S002 | DECIDE | Rust 逐方法驗證器 | **APPLIED** | C3-S4 | `protocol.rs` 3,638→616；`evidence/C3-S4/rust-framing.md` |
| S003 | READY | Rust 對每個 result 送兩次到 WebView | **APPLIED** | C3-S4 | result 只送一次（缺陷 #4）；新增單次送出斷言 |
| S004 | READY | TS 對同一個 result 驗兩次 | **APPLIED** | C3-S2 | 刪除 TS 的 `validateResultData` 重複呼叫 |
| S005 | READY | Python 送出時同一訊息驗 2–3 次 | **APPLIED** | C3-S5 | 每則送出訊息只驗一次；`evidence/C3-S5/python-single-validation.md` |
| S006 | DECIDE/DELETE | 12 個從未發出的 request event | **APPLIED** | C4-S3 | request event 20→8（U7） |
| S007 | DECIDE | 13 個沒有呼叫者的方法 | **APPLIED** | C4-S1、C4-S2 | 10 個 `knowledge.*`（U2）＋3 個 RPC（P1）；斜線指令共用符號保留（A3） |
| S008 | READY | contract 中沒人產生也沒人讀的欄位 | **APPLIED** | C4-S5 | `evidence/C4-S5/unused-fields.md` |
| S009 | DECIDE | streaming 殘留 `streamKind: "final_only"`／`chunkCount: 0` | **APPLIED** | C4-S3 | `streamKind`／`chunkCount` 端到端刪除 |
| S010 | DECIDE | `ollamaReachable`／`ollamaModelAvailable` 永遠是 None | **APPLIED** | C4-S3 | `ollamaReachable`／`ollamaModelAvailable` 與 GUI 兩列刪除 |
| S011 | DECIDE | 只給測試用的 trace validator | **APPLIED** | C3-S2、C3-S4、C3-S5 | TS、Rust、Python 三端的 trace validator 各自處理；Python 版移到 `app/tests/protocol_trace_oracle.py` |
| S012 | DECIDE | fixtures.json 5,194 行、三語言各跑一遍 | **APPLIED** | C3-S5 | 刪除寫死的 28 個 schema 名稱與歷史測試；補 8 個 request fixtures；`fixtures.json` 5,194→5,104 |
| S013 | DECIDE | `documentContext` schema 在 contract 中內嵌 11 次（約 90 行） | **未納入** | — | 長尾 DECIDE（GOALS 不納入）：不在稽核路線內／證據信心較低／會改變行為而無使用者決策 |
| S014 | READY | 沒用到的 Tauri capability | **APPLIED** | C2-S7 |  |
| S015 | DECIDE（低） | 行動平台 scaffolding | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S016 | DECIDE | 權限的三個名字 | **APPLIED** | C4-S4 | `session.set_permission`、`permissionMode`、`PermissionControl`（U8＋P2） |
| S017 | DECIDE | 前端複製 Python 的解析規則 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S018 | DECIDE/DELETE | 舊的全域 catalog 建構路徑 | **APPLIED** | C6-S2 | 舊 catalog 建構路徑隨 `DesktopProjectCatalog` 一併刪除（`evidence/C6-S1/surface.md`、`C6-S2/backend.md`） |
| S019 | DECIDE | catalog 其實是衍生快取 | **APPLIED** | C6-S2、C6-S3 | catalog 改由 scan 推導（U3）；S-ID 標籤未寫在 build-log，內容對應見 `evidence/C6-S2/backend.md` |
| S020 | DECIDE/MOVE | `fixture_session.py`（1,493 行）放在 production 套件 | **APPLIED** | C7-S1 | `fixture_session.py` 移到 `app/tests/support/`，server 開關移除（P5） |
| S021 | READY（隨 S020） | `documents.selected_text` | **APPLIED** | C7-S1 |  |
| S022 | READY（隨 S020/S007） | `DesktopKnowledgeOperations.workspace_root` | **APPLIED** | C7-S1 |  |
| S023 | READY | `_execute_desktop_extension_command` 回傳 tuple 但第二個值被丟掉 | **APPLIED** | C2-S10 |  |
| S024 | READY | `_apply_controls` 是只做一次呼叫的 async 包裝 | **APPLIED** | C2-S10 |  |
| S025 | DECIDE | `_validate_turn_result_shape` 每回合跑兩次 | **未納入** | — | 長尾 DECIDE（GOALS 不納入）；C3-S5 build-log 明記「pre-persist 的 S025 不納入」 |
| S026 | READY | `documents.py` 重複驗證 | **部分** | C2-S10 | 刪除 `undo` 重複的第二次 `validate_snapshot`；`prepare` 的 `candidateText` 驗證負責攔截合併後超過上限的新字串，保留（`evidence/C2-S10/notes.md`） |
| S027 | DECIDE | 每次刷新側欄都重掃歷史 | **APPLIED** | C6-S2 | 隨 S019：每次 `session.list` 由 2 次 scan 降為恰好 1 次；仍每次重掃，快取留給使用者（R3，見第 7 節） |
| S028 | DECIDE（結構） | 忙碌判斷複製 8 份 | **APPLIED** | C7-S6 | U21：4 個共用查詢；沒有新增拒絕條件、沒有搬移狀態所有權（`evidence/C7-S6/busy-matrix.md`） |
| S029 | READY | bibliography handler 的重複讀取 | **部分** | C5-S3 | inspect 共用同一份 fingerprint、`styles.json` 只解析一次；跨 handler 的三處路徑解析與 add 寫入後的 fingerprint 讀取附理由保留（`evidence/C5-S3/single-store.md` §2） |
| S030 | DECIDE | `extensions.apply` 的三重計算與自我核對 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S031 | READY | 為了不完整的假物件寫的建構期探測 | **APPLIED** | C7-S2、C7-S4 | 刪除 `inspect.signature` 探測與假物件分支 |
| S032 | DECIDE | 對同程序資料再做輸出驗證（約 350 行） | **未納入** | — | GOALS 不納入：`_knowledge_count`、`_knowledge_string_items` 仍被斜線指令使用，所以整項不納入（build-log CA1 第 2 點） |
| S033 | DECIDE | service 內複製 contract 已做的檢查 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S034 | KEEP（建議搬家） | `_map_exception`／`_exception_*` | **KEEP** | C7-S8a | GOALS KEEP（只搬家）：`_map_exception` 一族搬到 `errors.py` |
| S035 | KEEP | `DesktopServiceError(ProtocolError)` | **KEEP** | C7-S8a | GOALS KEEP：`DesktopServiceError` 隨搬到 `errors.py` |
| S036 | DECIDE | desktop 測試膨脹 | **部分** | C4-S1 | 依 GOALS 只處理因移除功能而失效的測試（4 項 RPC 測試退役或改寫到 `/ingest`，`evidence/C4-S1/knowledge-rpc.md`）；稽核所稱的超長 journey 測試與逐指令重疊測試沒有整併紀錄 |
| S037 | DECIDE（結構） | desktop 測試的假物件與私有存取 | **部分** | C7-S2（含 C7-S4、C7-S5 的測試改名） | 共用 helper 集中到 `app/tests/desktop_support.py`、13 個測試模組改 import；「同名但語意不同的 helper 不合併」，假 session／假 service 的種類未縮減（`evidence/C7-S2/fakes.md`） |
| S038 | READY | 同步版 thinking helpers 只剩測試在用 | **APPLIED** | C2-S1 | `evidence/C2-S1/retired-tests.md` |
| S039 | READY | `agent.llm.text.invoke_text`（prompt 字串版） | **APPLIED** | C2-S1 | `evidence/C2-S1/retired-tests.md` |
| S040 | READY | `ChatSession.activate_citation_skill`／`deactivate_citation_skill` | **APPLIED** | C2-S2 | 40 處測試引用改走單回合 `skill_name="citation"` |
| S041 | READY | `ChatSession.citation_service` 公開 property | **APPLIED** | C2-S1 | `evidence/C2-S1/retired-tests.md` |
| S042 | READY | `ChatSession.restore` | **APPLIED** | C2-S1 | `evidence/C2-S1/retired-tests.md` |
| S043 | READY | `_active_skill_context_block` 轉手函式 | **APPLIED** | C7-S3 | `_active_skill_context_block` inline 後刪除 |
| S044 | READY | 建構時重複檢查專案所有權 | **APPLIED** | C2-S1 | `evidence/C2-S1/retired-tests.md` |
| S045 | DECIDE | `skill_loader_node` 與 `skill_runtime_getter` | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S046 | DECIDE | 對話 schema v1/v2 讀取器 | **APPLIED** | C2-S5 | U6；`app/store` 4/4 為 v3；讀 v1/v2 成為 `unsupported_version` scan issue |
| S047 | DECIDE | `TurnJournal.turn_logs` | **APPLIED** | C2-S6 | 缺陷 #5；移除 `TurnJournal.turn_logs` |
| S048 | DECIDE | 只做 re-export 的 `__init__` | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S049 | DECIDE | `agent/skills/broker.py`（32 行）＋`test_skill_broker.py` | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S050 | DECIDE | `agent/adapters/` 三個檔案只為一個函式 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S051 | DECIDE（低） | `turns/memory.py`（15 行） | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S052 | DECIDE（結構） | 從外部改寫 `ChatSession` 私有屬性 | **APPLIED** | C7-S3、C7-S4、C7-S5 | A5 成立；orchestrator 改公開名稱＋`TurnHost`，desktop 端改公開屬性，installer／文件回合旗標隨 U17 移除（C10-S2：`agent/desktop` 直接私有存取 4→0、字串形式 6→1，唯一命中非 `ChatSession`） |
| S053 | DECIDE | 一個 desktop 回合載入 skill runtime 3–4 次 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S054 | DECIDE（結構） | Skill policy 寫死在名稱上 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S055 | DECIDE（結構） | thinking mode 字面值散在 8 處 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S056 | DECIDE（結構） | `LocalWorkScope` 住在 RAG 包裝模組裡 | **未納入** | — | R5：這次不處理 `LocalWorkScope` 的循環 import（C7-S7 只改其 `finish_stop` 行為，import 無變動，執行者以 `git diff` 核對） |
| S057 | DECIDE（結構） | 安裝器狀態機散落兩處 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S058 | DECIDE（結構） | `agent/cli/slash_commands.py` 也被 desktop 使用 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S059 | DECIDE（結構） | 回合生命週期的處理梯重複 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S060 | DECIDE | 已退役指令的墓碑 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S061 | READY | manifest 的舊欄位友善錯誤 | **APPLIED** | C2-S3 | `evidence/C2-S3/retired-tests.md` |
| S062 | READY | `tests/test_extension_baseline.py` | **APPLIED** | C2-S3 | `evidence/C2-S3/retired-tests.md` |
| S063 | READY | `tests/test_smoke.py` | **APPLIED** | C2-S3 | `evidence/C2-S3/retired-tests.md` |
| S064 | DECIDE | `tests/test_history_retirement.py` 名不副實 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S065 | KEEP（有條件） | `tests/test_extension_packaging.py` | **KEEP** | — | GOALS KEEP（稽核確認有用途，不動） |
| S066 | DECIDE（結構） | 測試對 ChatSession 私有屬性的存取 | **部分** | C7-S3、C7-S4、C7-S5 | 只處理與 S052 相關的測試改名／改走公開屬性；稽核所稱約 100 處測試私有存取的整體遷移未做（例如 `_prompt_master_skill_text_cache` 仍由測試設定，`evidence/C7-S3/private-access.md` §2）。build-log 與 evidence 沒有 S066 專屬紀錄 |
| S067 | DECIDE | Python 相依 | **未納入** | — | GOALS 不納入：相依變更需另外核准，U9 只核准 `pybtex` |
| S068 | KEEP | 其他 Python 相依 | **KEEP** | — | GOALS KEEP（稽核確認有用途，不動） |
| S069 | KEEP | 看起來可刪但有用途 | **KEEP** | — | GOALS KEEP（稽核確認有用途，不動） |
| S070 | DECIDE | 多專案側欄 scaffolding 對上單專案後端 | **APPLIED** | C6-S3 | `sessionLists` 改單一 `sessionList`；刪多專案 scaffolding |
| S071 | READY | 重複或沒用到的文件型別 | **APPLIED** | C3-S2、C3-S3、C8-S6 | 兩個 0 引用 DTO 先刪（C3-S2），隨後 `DocumentOpenDto`／`DocumentResultDto` 因 DTO 一致性檢查需要而作為真正的 result DTO 重新加入（C3-S3，`evidence/C3-S3/dto-check.md`）；`DocumentSnapshot` 併入 `DocumentContextDto`（C8-S6，`evidence/C8-S6/domains.md` §四） |
| S072 | READY | 沒用到或只給測試用的匯出與零件 | **APPLIED** | C3-S2 | `evidence/C3-S2/ts-contract.md` §5 |
| S073 | READY | `conversationInteractionState` | **APPLIED** | C2-S8 | `evidence/C2-S8/retired-tests.md` |
| S074 | READY | `sessionCreateParams` | **APPLIED** | C2-S8 | `evidence/C2-S8/retired-tests.md` |
| S075 | READY | 後端 snapshot／lifecycle 處理寫了 4 份 | **APPLIED** | C2-S8 | `evidence/C2-S8/retired-tests.md` |
| S076 | READY | 死的 CSS 規則 | **APPLIED** | C2-S8 | `evidence/C2-S8/retired-tests.md` |
| S077 | DECIDE | `BoundedRuntimeDiagnostics`／`toBoundedDiagnostics` | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S078 | DECIDE | browser-preview 模式 | **APPLIED** | C8-S4 | U5；`browserPreview` 狀態與 8 處守衛刪除 |
| S079 | DECIDE（結構） | `applyConversation` 每個 action 跑兩次 reducer | **APPLIED** | C8-S5 | `applyReducerOnce`、`approvalOwner.ts`；原 10 處核准清除改為 `clearApproval`（7 處呼叫，並以 `dropOwner` 保留 3／7 的差異） |
| S080 | DECIDE（結構） | approval 清除區塊重複 11 次 | **APPLIED** | C8-S5 | `applyReducerOnce`、`approvalOwner.ts`；原 10 處核准清除改為 `clearApproval`（7 處呼叫，並以 `dropOwner` 保留 3／7 的差異） |
| S081 | DECIDE（結構） | focus trap 與 popup menu 各自複製 | **APPLIED** | C9-S1 | 依 U22 只共用相同互動原語（4 個純函式＋`ModalDialog`＋`useDisclosureMenu`）；語意差異留在呼叫端 |
| S082 | DECIDE | 29 處 `as unknown as XDto` 與 19 處 id 回聲檢查 | **APPLIED** | C8-S3 | 新增 `src/api.ts`；`App.tsx` 的 `as unknown as` 23→0；就地 `protocolMismatch` 13→7（剩下的是與 UI 狀態比對） |
| S083 | DECIDE（結構） | 為測試而存在的匯出與測試基礎設施 | **APPLIED** | C8-S2 | 9 個 `src/lib/*.ts` 純模組；33 個純函式測試改直接 import；新增 `tsconfig.test.json`＋`tests/node-shim.d.ts` 讓 `npm run build` 檢查測試型別 |
| S084 | DECIDE | `styles.test.ts`（34 行） | **未納入** | — | GOALS 不納入：屬之後的 UI 重設計；INV-021 數值不變，`styles.test.ts` 未改且通過（C9-S4／C9-S5） |
| S085 | READY | 檢查已退役「Product Plan Mode」不存在的原始碼 grep 測試 | **APPLIED** | C3-S2 |  |
| S086 | DECIDE | 其他 grep 原始碼的測試 | **APPLIED** | C8-S5、C9-S4 | `trust.test.ts` 原始碼比對測試在 C8-S5 改為流程測試；`editorZoom.test.ts` 在 C9-S4 改測 `editorFontOptions`／`zoomKeybindings`；讀 `.tsx` 的測試為 0（唯一保留的是讀 CSS 的 `styles.test.ts`） |
| S087 | DECIDE | 在渲染結果上斷言 class name | **APPLIED** | C9-S4 | class name 斷言改 role／文字／aria（`evidence/C9-S4/tests.md` §二） |
| S088 | DECIDE | 大型合成資料測試 | **APPLIED** | C9-S4 | 5 個大型合成資料測試合併成 1 個，輸入大小不變 |
| S089 | DECIDE | `sensitiveMessagePattern` | **APPLIED** | C2-S11 | U15；`bounded_error_message` 先遮蔽再截斷，刪 `sensitiveMessagePattern` |
| S090 | DECIDE（隨 S002） | TS 對 Rust snapshot 做逐鍵驗證 | **APPLIED** | C3-S2 | `parseBackendSnapshot`／`parseShutdownReport` 只檢查是物件 |
| S091 | DECIDE | 寫死的 fallback 與重複的 enum 檢查 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S092 | READY | `generation?`／`projectEpoch?` 標為可選，但所有呼叫端都有傳 | **APPLIED** | C2-S8 | `evidence/C2-S8/retired-tests.md` |
| S093 | DECIDE（結構） | 原生 picker 繞過 backend client | **APPLIED** | C8-S3、C8-S6 | 原生 picker 與（C8-S6）`listen` 收進 `api.ts` |
| S094 | DECIDE（小） | `index.html` | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S095 | KEEP | 前端看似可刪但有用途 | **KEEP** | — | GOALS KEEP（稽核確認有用途，不動） |
| S096 | DECIDE（結構） | CSS 地基 | **部分** | C9-S3 | 依 P12／R4 只做依區塊分檔（7 個連續區段）與借用 class 改名（`dialog-error`）；色彩 token、近似色合併、media query 整併不做（C10-S2：hex 110／rgba 16 不變） |
| S097 | DECIDE（結構） | 拆解 `App()` | **APPLIED** | C8-S6、C9-S1、C9-S2 | 依 U18 調整範圍：domain hook 只有 `useExtensions`（及 C9-S1 的 `useDisclosureMenu`），15 個元件檔，`App.tsx` 3,059→1,932；不是稽核建議的七個 hooks（`evidence/C8-S6/domains.md`、`C9-S2/components.md`） |
| S098 | READY | PowerShell 腳本重複設定編碼 | **APPLIED** | C2-S7 |  |
| S099 | DECIDE（小） | `seen_request_ids` 在整個 generation 期間只增不減 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S100 | DECIDE（低） | snapshot 的 `stderrLines`／`stderrBytes` | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S101 | READY | `BackendSupervisor::new` 與 `for_test` 重複建構 | **APPLIED** | C2-S7 |  |
| S102 | READY | `main.py` 特判不存在的 `public/` 目錄 | **APPLIED** | C2-S7 |  |
| S103 | DECIDE（結構） | `backend.rs` 混了六種職責 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S104 | KEEP | Rust 端必要的部分 | **KEEP** | — | GOALS KEEP（稽核確認有用途，不動） |
| S105 | DECIDE | citation bundle（`cite/`）與專案書目庫是兩套儲存 | **APPLIED** | C5-S3（含 C5-S4、C5-S5） | U4、U13、U20、P8、P9、P13；評估分界 commit `9068f87`（第 5 節） |
| S106 | READY（若 S105 選 a；選 b 則無須處理） | v1 bundle 讀取器 | **APPLIED** | C5-S3 | 隨 S105 消失（v1 bundle 讀取器、`legacy_v1_bundle` fixture 一併刪除） |
| S107 | KEEP | 兩組看似重複、實際各有用途的設計 | **KEEP** | — | GOALS KEEP（稽核確認有用途，不動） |
| S108 | READY | 只剩測試在用的 citation 符號 | **APPLIED** | C5-S3 | `evidence/C5-S3/single-store.md` §3 |
| S109 | READY | gate 的 `user_input` 是無作用參數 | **APPLIED** | C2-S3 | `evidence/C2-S3/retired-tests.md` |
| S110 | READY（低） | `render.RenderedTurn.cited_sources`／`format_bibliography_entry` | **APPLIED** | C5-S3 | `evidence/C5-S3/single-store.md` §3 |
| S111 | DECIDE（低） | `CitationProviderHub.aclose` | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S112 | DECIDE（低） | `rag_list_chunks` 的 tool schema | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S113 | DECIDE（低） | `Hit.score` 永遠是 None | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S114 | READY | `VectorRetriever` 只是轉手 | **APPLIED** | C2-S4 |  |
| S115 | READY | `BaseStore` ABC | **APPLIED** | C2-S4 |  |
| S116 | DECIDE（低） | RAG 的單檔 package 與 lazy `__getattr__` | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S117 | READY | 註解與程式碼矛盾 | **APPLIED** | C2-S4 |  |
| S118 | READY | `csl_render` 重複載入 | **APPLIED** | C5-S3 | `evidence/C5-S3/single-store.md` §3 |
| S119 | READY | 小型重複 helper | **APPLIED** | C5-S3 | `evidence/C5-S3/single-store.md` §3 |
| S120 | READY（外觀） | 私有成員與 inline import | **APPLIED** | C5-S3 | `evidence/C5-S3/single-store.md` §3 |
| S121 | DECIDE | citation 測試重疊 | **部分** | C5-S3、C5-S6 | 只刪因 U4／U13 失效的 citation 測試；稽核列出的其他重疊（workflow tool／save isolation、三個啟用 contract 模組、e2e 與 doi-first-save）未處理（`evidence/C5-S6/wrap-up.md` §1） |
| S122 | READY | `tests/test_ingest.py` 放錯位置 | **APPLIED** | C2-S3 | `evidence/C2-S3/retired-tests.md` |
| S123 | DECIDE（結構） | citation 與 RAG 的邊界外洩 | **部分** | C7-S8b | 只做 GOALS 納入的部分：bibliography handler 抽成 `bibliography_ops.py`（301 行）；`skills/citation` 對 `agent.paths` 的反向依賴、`rag/cli/ingest.py` 的函式庫 API 位置、新增 provider 要改 4 處皆未處理（`evidence/C7-S8/modules.md`） |
| S124 | KEEP | skills 與 RAG 中必要的部分 | **KEEP** | — | GOALS KEEP（稽核確認有用途，不動） |
| S125 | DECIDE | 已完成的計畫紀錄 | **未納入** | — | GOALS 不納入：使用者的 GUI checklist 與 live grill eval 尚未完成 |
| S126 | DECIDE | 根目錄的 `NOTES-grill-skill-and-document-context.md`（未追蹤） | **未納入** | — | GOALS 不納入：使用者的研究資料（根目錄筆記，未追蹤） |
| S127 | DECIDE | `note/20261106/`（未追蹤，8.2 MB） | **未納入** | — | GOALS 不納入：使用者的研究資料（`note/20261106/`，未追蹤） |
| S128 | READY | `app/desktop/watch.out`（未追蹤，509 B） | **APPLIED** | C2-S9 | S128 為缺陷 #7（`watch.out` 刪除）；S129 刪 `__pycache__/` 與空的 `harness/plans/.claude/` |
| S129 | READY | 根目錄的 `__pycache__/`（09-23 的過期 .pyc，已被 ignore）與 `harness/plans/.claude/.cc-writes`（空目錄） | **APPLIED** | C2-S9 | S128 為缺陷 #7（`watch.out` 刪除）；S129 刪 `__pycache__/` 與空的 `harness/plans/.claude/` |
| S130 | DECIDE | RAG 文件重複 | **未納入** | — | 長尾 DECIDE（GOALS 不納入） |
| S131 | DECIDE | `AGENTS.md` 過時 | **未納入** | — | GOALS 不納入：`AGENTS.md` 是使用者的治理文件；過時句子列於第 9 節 |
| S132 | DECIDE | `tool/local/` 預留區 | **未納入** | — | GOALS 不納入：產品方向決定（`tool/local/` 預留區） |
| S133 | DECIDE | README 與 UI 細節綁在一起 | **未納入** | — | GOALS 不納入：文件風格決定；C10-S1 只修與行為不符的句子 |
| S134 | DECIDE | 分支策略 | **未納入** | — | GOALS 不納入：使用者規則禁止建立、切換、刪除 branch 與 push |

表格的判讀規則：「部分」一律在說明欄寫明做了什麼、沒做什麼；「未納入」引用 GOALS 的理由；沒有任何一列是靠猜測填的。

---

## 3. 量測前後對照

來源：`evidence/C1-S3/metrics-before.md`（基底 `dffb14b`，與稽核基準 `3b6cfd8` 的 `app/` 相同）與 `evidence/C10-S2/metrics-after.md`（程式狀態 `e9436fc`）。指令兩邊相同。

### 3.1 熱點檔案行數

| 檔案 | C1-S3 | C10-S2 | 差 | 備註 |
|---|---:|---:|---:|---|
| `app/agent/desktop/service.py` | 4,643 | 461 | −4,182 | handler 分到 11 個模組，合計 3,962 行（C7-S8，`evidence/C7-S8/modules.md`） |
| `app/desktop/src-tauri/src/protocol.rs` | 3,638 | 616 | −3,022 | 只剩框架檢查（C3-S4） |
| `app/desktop/src/App.tsx` | 3,059 | 1,932 | −1,127 | 15 個元件檔拆出（C9-S2） |
| `app/desktop/src-tauri/src/backend.rs` | 2,497 | 2,505 | +8 | evidence 未逐項說明；C3-S4 刪除 result 的第二次送出與 `validate_result_data` |
| `app/desktop/src/protocol.ts` | 2,333 | 1,100 | −1,233 | 直接讀 contract（C3-S2） |
| `app/agent/session.py` | 1,555 | 1,519 | −36 | |
| `fixture_session.py` | 1,493（`agent/desktop/`） | 1,480（`tests/support/`） | −13 | 移到測試（C7-S1） |
| `app/desktop/src/styles.css` | 1,299 | 288 | −1,011 | 另 6 個區段檔合計 1,001 行，規則順序不變（C9-S3） |
| `app/desktop/protocol/v1/contract.json` | 1,261 | 1,020 | −241 | |
| `catalog.py` → `project.py` | 840 | 429 | −411 | |
| `app/desktop/src/conversations.ts` | 800 | 844 | +44 | 收進選取恢復純函式等 |
| `app/agent/desktop/protocol.py` | 760 | 695 | −65 | |
| `app/desktop/src/backend.ts` | 605 | 591 | −14 | 另新增 `api.ts` 178 行 |
| `app/desktop/src/trust.tsx` | 549 | （已拆為 `components/` 下的元件） | — | C9-S2a |
| `app/desktop/protocol/v1/fixtures.json` | 5,194 | 5,104 | −90 | 刪除與補充 fixtures 相抵 |

### 3.2 協定詞彙

| 指標 | C1-S3 | C10-S2 |
|---|---:|---:|
| contract 方法 | 40 | 25 |
| request event | 20 | 8 |
| process event | 4 | 4 |
| 錯誤碼 | 25 | 25（沒有新的死錯誤碼，`evidence/C10-S0/vocabulary.md`） |
| fixtures messages／traces | 127／60 | 125／60 |

C10-S0 腳本比對 contract 與 PLANS.md「目標詞彙」：25 個方法、8 個 request event 雙向差集皆空。

### 3.3 `App()` 與 `ChatSession` 私有存取

| 指標 | C1-S3 | C10-S2 |
|---|---:|---:|
| `App()` 本體 `useState`／`useRef`／`useEffect`／`useCallback` | 35／35／14／42 | 33／33／11／46 |
| 整檔 `App.tsx`（含 import 一次） | 43／39／16／43 | 34／34／12／47 |
| `agent/desktop` 對 `ChatSession` 私有成員：直接存取／`self.session._`／字串形式 | 4／0／6 | 0／0／1（唯一命中是 `server.py` 讀 `DesktopService._with_turn_lifecycle`，不是 `ChatSession`） |
| 不同 hex 色值／`rgba(...)` 字面值（所有 CSS） | 110／16 | 110／16（不變，R4） |

註：`useCallback` 增加（42→46）是 C8-S5／C8-S6 的取捨，不是退步；G6 驗收的是 domain 邏輯移到純模組並有測試，而不是 hook 數量（`evidence/C8-S6/domains.md` §六）。

### 3.4 測試數量沿革（各階段收尾 evidence）

| 時點 | pytest | `npm test` | cargo |
|---|---:|---:|---:|
| C1-S2 基線 | 1,808 | 329 | 42 |
| C2-S12 | 1,808 | 330 | 42（C2-S7） |
| C3-S6 | 1,816 | 228 | 35 |
| C4-S6 | 1,798 | 224 | 35 |
| C5-S6 | 1,762 | 224 | 35 |
| C6-S5 | 1,755 | 224 | 35 |
| C7-S8／S9 | 1,827 | — | — |
| C8-S7 | — | 247 | — |
| C9-S5 | — | 253 | — |
| C10-S2 | 1,827 | 253 | 35 |

（`—` 表示該階段收尾 evidence 沒有重跑該套。）

---

## 4. 使用者可見的行為改變

下列都是「程式與 evidence 顯示會改變」的行為；GUI 呈現本身未經執行者驗證（見開頭聲明與第 10 節）。

### 4.1 回合與錯誤

| 決策 | 改變 | 依據 |
|---|---|---|
| **U14** Retry Stop | 兩層快取都修了。(a) `LocalWorkScope.finish_stop` 失敗後不再重播舊例外，下次只重做尚未停下的 process group。(b) Stop 送達時若回合已結束但被卡住，才重試清理，然後從磁碟重讀回合狀態：terminal（completed／failed／interrupted）或確認未受理且未落盤才解除；仍 pending 時走 `reload_and_recover` 標成 interrupted；讀取失敗或恢復失敗則維持封鎖。第一次 Stop 不會自動重試兩次。清理失敗的訊息現在附原因（「The turn's local work could not finish stopping: <reason>」，有長度上限），錯誤碼仍是 `INTERNAL_ERROR`。FAIL-022 已修正。 | C7-S7，`evidence/C7-S7/retry-stop.md`（6 個新測試，失敗注入在 `_stop_process_group`） |
| **U15** 錯誤遮蔽 | 只在 Python 的錯誤出口做一次：`bounded_error_message` 先以值的格式遮蔽憑證（`Authorization` 標頭、URL 帳密、`sk-`／`ghp_`／`github_pat_` 獨立金鑰、已知 secret），再截斷到 4096 bytes。TS 依關鍵字（`token`、`secret`、`authorization`、`bearer`、`traceback`、`api key`）整句隱藏的邏輯刪除，所以含這些字的正常訊息現在原文顯示。 | C2-S11，`evidence/C2-S11/error-sources.md` |
| **U17** 每回合設定 | 文件回合的強制 thinking mode／`document_edit` 工具與 Bypass 的 installer 略過核准，改為隨每回合參數傳入並在同一方法還原；`DesktopService` 的 10 個回合欄位改放每回合紀錄。可見影響：文件回合中途失敗後，下一個一般回合不會殘留 normal thinking 或文件工具；Bypass 回合後改回 Ask，installer 不再略過核准。 | C7-S5，`evidence/C7-S5/turn-state.md`（測試 (a)(b)(c)） |
| 缺陷 #2 | `.error-text` 補上既有錯誤色 `#843c38`（Stop 失敗訊息、source editor 問題訊息）。 | C2-S8 |

### 4.2 協定與畫面詞彙

| 決策 | 改變 | 依據 |
|---|---|---|
| **U2** 刪 10 個 `knowledge.*` RPC | 桌面的 RAG 仍走 composer 指令 `/init /ingest /sync /prune` 與 agent 的 `rag_*` 工具（不變，A3）。副作用：composer `/ingest` 遇到錯誤時，錯誤 details 只剩 turn lifecycle，沒有 `partialWritePossible`（既有行為，因為該欄位只存在於已刪的 RPC 路徑；見第 11 節）。 | C4-S1，`evidence/C4-S1/knowledge-rpc.md` |
| **P1** | 另刪 `session.status`、`session.shutdown`、`extensions.status` 三個沒有呼叫者的 RPC 註冊（`_extensions_status` 仍供 `/extension-management status`）。無畫面影響。 | C4-S2 |
| **U7** | 刪 12 個從未發出的 request event（20→8）、`streamKind`／`chunkCount`、永遠是 null 的 Ollama 欄位。可見：Local runtime details 不再顯示「Ollama」與「Ollama model」兩列。RAG 本身仍用 Ollama，只是協定不再回報 null。 | C4-S3 |
| **U8、P2** | `session.set_bash_permission`→`session.set_permission`、`bashPermissionMode`／`mode`→`permissionMode`、`BashPermissionControl`→`PermissionControl`。畫面名稱與行為不變；對話檔不受影響（持久化的本來就是 `permissionMode`）。 | C4-S4 |
| **P3** | 沒有錯誤碼被移除：25 個都有 producer（含斜線指令使用的 `OLLAMA_*`、`BUSY_KNOWLEDGE_MUTATION`、`RAG_*`、`PRUNE_PREVIEW_STALE`）。 | C4-S5、C10-S0 |
| **U19** `project.list` | 方法刪除；前端只呼叫 `session.list`。選取恢復保留：`conversationToRestore` 純函式，3 個情況有測試（A7 結論：支援的流程中 `selectedSessionId` 一律為 null，恢復只靠 `resumeSelectionRef`）。 | C6-S1、C6-S3 |

### 4.3 對話清單與儲存

| 決策 | 改變 | 依據 |
|---|---|---|
| **U3** catalog 改由掃描推導 | 程式不再讀寫 `desktop-projects.json`（殘留檔照常容許，開啟與初始化都不改它的內容與 mtime）。`project.list`、`session.retry_registration`、`registrationStatus`／`registrationIssue`、`registered` 都從 Python、contract、TS、fixtures 移除。可見：側欄只有一個專案，依建立時間由舊到新列出；新對話第一次送出完成前顯示「Not saved yet」；沒有「Retry registration」與「CATALOG REGISTRATION PENDING」；session details 沒有 cataloged／transient。原本承擔「對話已存檔但無法重新整理」訊息的通知保留為「CONVERSATION NOT REFRESHED」，按鈕改為「Refresh without resending」（重新讀清單與 transcript，不重送 prompt）。 | C6-S2、C6-S3 |
| U3 消失的兩個 fail-closed | (1)「catalog 指向不存在的對話時拒絕開啟專案」：遺失的對話現在只是不出現在清單。(2)「空歷史目錄的專案歸屬」：見 U11。專案擁有權與歷史健康檢查（壞檔、缺目錄、混入他專案對話）仍 fail closed（INV-016）。 | C6-S2 (a)–(e) |
| **U11**（已接受） | 兩個專案指向同一個空的 `historyDirectory` 時都能開啟；有對話之後歸屬檢查照舊。 | C6-S2 |
| **U6** | 讀到 schema v1／v2 的對話檔時明確拒絕（`unsupported_version`，成為 scan issue），不靜默升版。依 INV-016，一個非 v3 檔案會讓**整個專案**無法開啟。`app/store` 下 4/4 個檔案為 v3（C2-S5 唯讀核對）；`app/store` 以外的專案歷史目錄，執行者無法檢查。 | C2-S5，`evidence/C2-S5/store-versions.md` |
| **U5** | browser-preview 降級模式刪除。不在 Tauri 內開啟時，由既有的事件訂閱失敗 `catch` 顯示一般的後端無法連線錯誤（程式推論，未見畫面）。 | C8-S4 |

### 4.4 Citation（U4、U13、U20、P8、P9、P13，決策紀錄 §6）

| 項目 | 改變 | 依據 |
|---|---|---|
| 儲存位置 | 桌面存檔只併入專案書目庫（預設 `references.json`），不再產生 `cite/`、`reference.bib`、`citation.json`。CLI 不寫任何檔案。 | C5-S3、決策紀錄 §4.1–§4.2 |
| 存檔結果誠實（U13） | 桌面：只有書目庫裡確實有這筆才回報 `saved`／`reused` 並可引用；寫入失敗為 `storage_failed`，不可引用，工具結果明說沒有存檔、可重試。同批重複作品依第一筆結果；混合批次（U20）中批次前已在書目庫的 A 仍 `reused`、保留 key，B 寫入失敗為 `storage_failed`。CLI 驗證成功一律 `verified`，只在當次 task 可引用。 | C5-S3 測試 (a)–(k) |
| P13 | 同一 source ID 屬於另一個 identity 改報 `identity_conflict`（reason `registry_conflict`），在寫入書目庫之前判定。 | C5-S3 |
| 核准對話框 | `citation.save` 與 `bibliography.add` 的核准目標改為書目庫路徑；專案 metadata 的 `bibliography` 格式錯誤而沒有書目庫時，目標是 `(not written to disk)`。 | C5-S3 §2、C5-S1 第 5 題 |
| P9 | `AgentConfig.citation_output_dir`、環境變數 `CITATION_OUTPUT_DIR`、diagnostics 的 `citationOutputPath` 與 GUI 兩處「Citation output」顯示移除；`.env` 若還設著該變數，之後不再有作用。 | C5-S3 §2 |
| P8 | 隨 BibTeX 移除的「doi.org CSL 與 BibTeX 的 DOI 交叉比對」不補回，也沒有新增「回應 DOI 必須等於要求 DOI」。C5-S1 實測確認：BibTeX 鏈本來就**不**拒絕缺標題或缺年份的記錄（缺作者是 `IndexError`），最低欄位要求實際由權威 adapter 負責，沒有「無人負責」的欄位檢查；已在決策紀錄末尾追加更正（C5-S2）。 | C5-S1、C5-S2 |
| 功能損失（決策紀錄 §6.1） | CLI 失去單獨存檔能力、跨 session 的 `reused` 在 CLI 消失；`citation.json` 保存的 agent intent、resolution 記錄來源、provider record ID 不再落地（診斷 log 仍有 batch ID、index、status、reason code）；舊 `cite/` 不遷移、不讀回。 | 決策紀錄 §6.1、§7 |
| 相依（U9） | `pybtex 0.26.1` 與 `latexcodec 3.0.1` 從 `pyproject.toml`／`poetry.lock` 移除（dry-run 確認 0 installs、0 updates；`poetry check` 通過）。 | C5-S5 |
| 模型看到的文字 | `SKILL.md`、skill README、工具描述與 `explain` 文字改變，這是**實驗條件**的改變（第 5 節）。 | C5-S3、C5-S4 |

### 4.5 其他讀得到的差異

- `main.py` 不再特判不存在的 `public/` 目錄；`WINDOWS_PICKER_SCRIPT` 的編碼設定合併；`BackendSupervisor` 建構合併（C2-S7，無使用者可見影響）。
- 核准框關閉後焦點是否回到輸入框，原本 10 處清除中只有 3 處同時釋放擁有者，C8-S5 以 `clearApproval(state, dropOwner)` 保留差異，預期行為不變（`evidence/C8-S5/reducer-approval.md`）；仍列入 GUI 清單。
- dialog／menu 的 class 改名：`approval-backdrop`／`approval-dialog`→`modal-backdrop`／`modal-dialog`（C9-S1），借用的 `extension-error`→`dialog-error`（C9-S3，只改選擇器，打包後 CSS 只差一個選擇器）。預期畫面不變，需目視確認。

---

## 5. citation 評估的分界 commit

- **分界 commit：`9068f87`**（`refactor(citation): keep verified works only in the project bibliography and report saves truthfully [C5-S3]`，`evidence/C5-S6/wrap-up.md` §3；build-log C5-S6）。C5-S2（`f5c856d`）只新增不依賴 BibTeX 的測試，沒有改變驗證結果。分界前一個 commit 是 `f5c856d`（撰寫時以 `git rev-parse 9068f87~1` 核對）。
- 模型指令的分界另有一個 commit：C5-S4（`2fd68c6`，`SKILL.md` 與 skill README）；C5-S5（`979274d`）只移除相依，不改行為。若評估要精確隔離「模型指令」與「工具結果與狀態」兩種變因，兩個 commit 要分開看。
- **以 `9068f87` 為界的評估結果不能直接合併比較**（決策紀錄 §6.2）。

### 5.1 改變的狀態值與 reason（`evidence/C5-S3/single-store.md` §1）

| 情境 | 之前 | 之後（狀態／reason） |
|---|---|---|
| 桌面，新作品，書目庫寫入成功 | `saved`（以 bundle 寫入為準） | `saved`／`saved_new` |
| 桌面，批次前已在書目庫 | `reused` | `reused`／`reused_existing`，用既有 key，不受同批新作品寫入失敗影響（U20） |
| 同批重複 | 同批較早一筆剛加入記憶體的作品，之後的同一作品被報成 `existing`，即使整批寫入失敗（PLANS 基線描述） | 第一筆 `saved`、其後同一作品 `reused` 並共用 key；第一筆寫入失敗時，其後同一作品同為 `storage_failed` |
| 書目庫合併被拒、寫入失敗、無法讀取 | 存檔狀態不變，失敗只反映在 `bibliography` 連結（INV-032） | **`storage_failed`**，reason 為書目庫錯誤碼（`library_conflict`、`library_write_failed`、`library_malformed`…），不登記、不可引用、沒有 receipt |
| 書目庫寫入時非預期例外 | build-log C5-S3 記「原本會讓整個存檔崩潰」，未說明是基線或中間版本 | 參與該次寫入的各筆 `internal_error`／`storage_internal_error` |
| CLI（沒有書目庫；桌面專案 metadata 格式錯誤時亦同） | `saved`（bundle 寫入） | **新狀態 `verified`**／`verified_not_persisted`，只在當次 task 可引用，不寫檔 |
| registry 衝突 | 在登記時才失敗 | `identity_conflict`／`registry_conflict`（P13），寫入前判定 |
| BibTeX 相關失敗 | `bibtex_lookup_*`、`bibtex_doi_mismatch`、`authority_bibtex_invalid` | 不再出現 |
| provenance 字串 | `fresh-resolution+doi.org-csl+bibtex` | `fresh-resolution+doi.org-csl` |

### 5.2 改變的計數與資料欄位

- `CitationSaveMetrics.to_record` 新增 **`verified_count`**；`new_saved_count` 只算 `saved`；`reused_count` 只算 `reused`；其餘狀態都算 `failed_count`。
- turn trace 的 `_tool_result_counts` 新增 `save_verified`。
- 存檔批次 artifact 的 `SAVE_BATCH_SCHEMA_VERSION` 由 2 升為 **3**；artifact 的 `bibliography` 鍵一律存在（值可為 null）。A1 已確認該 artifact 不寫進對話 JSON（`evidence/C5-S1/guarantee-map.md`），所以不影響舊回合讀取。
- `SaveReceipt.bundle_path` 刪除；`BibliographyLink` 只剩 `added`／`existing`（`failed` 與 `reason_code` 移除，失敗改由項目的 `storage_failed` 表達）；`SaveItemStatus` 新增 `verified`。
- 存檔紀錄來源：`cite/` 的 sidecar 不再存在；逐筆資訊只剩診斷 log 的 `citation save batch … item …` INFO 行（決策紀錄 §6.2 第 5 點）。

### 5.3 改變的工具結果文字（`tool.py`）

- JSON 之後附上每筆的白話說明。
- `storage_failed`：「NOT saved and not citable in this task (<reason>)… Tell the user nothing was saved; the save can be retried.」，有書目庫連結時列出路徑。
- `verified`：「verified and citable in this conversation only; nothing was written to disk (no project bibliography)」。
- `TOOL_DESCRIPTION` 與 `format_explain` 不再提 BibTeX 與 bundle，`explain` 改說明書目庫或「不寫入磁碟」。
- 執行中發現並修正的缺陷：工具結果在沒有書目庫連結時，說明文字未換行就接在 JSON 後（測試抓到）。

### 5.4 免費 provider 冒煙測試

C5-S6 以真實 `CitationProviderHub` 存 `10.1038/s41586-021-03819-2` 到暫時書目庫（只連 doi.org，沒有付費 API）：狀態 `saved`，書目庫多一筆 `jumper2021highly`（`evidence/C5-S6/wrap-up.md` §4）。

---

## 6. 產品邊界檢查

### 6.1 「機制 → 觸發情境 → 支援的正常使用」紀錄彙整

以下取自各步驟 evidence 的產品邊界段落（PLANS 執行契約要求新增機制時寫一行）。**註：** 只有標「逐行」的是 evidence 中三段式的原句；標「概括」的 evidence 只寫了該步的整體聲明，沒有逐機制拆開，本彙報不替它補寫理由。

| # | 機制 | 觸發情境 | 支援的正常使用 | 依據 |
|---|---|---|---|---|
| 1 | 錯誤出口遮蔽（`bounded_error_message`） | 支援流程中的錯誤（文件操作失敗、書目匯出失敗、框架錯誤）送往 WebView | 是：循序使用中的一般錯誤顯示；不是協調或狀態機制，不新增拒絕條件（逐行） | `evidence/C2-S11/error-sources.md` §6 |
| 2 | `planBackendSnapshotTransition`／`applyBackendSnapshot`（把 4 處重複處理收斂為純函式與單一 callback） | 後端 crash 或使用者重啟造成 lifecycle／generation 改變 | 是；沒有新增任何鎖或並行控制（逐行） | `evidence/C2-S8/retired-tests.md` §2 |
| 3 | 成功回應的 `projectId`／`sessionId` 回聲比對（由 contract 推導，TS） | 依序切換專案或對話後，已結束操作（`session.select`、`session.transcript`）的回應晚到 | 是（GOALS 不變量「已結束操作晚到的回應」）；沒有新增拒絕以外的狀態或協調機制（逐行） | `evidence/C3-S2/ts-contract.md` §4 |
| 4 | Rust 框架檢查 | 無新增 | C3-S4 沒有新增任何檢查或協調機制，只刪除重複驗證與重複送出（逐行） | `evidence/C3-S4/rust-framing.md` §6 |
| 5 | registry 衝突提前檢查（P13） | 同一 citation task 中，某個 source ID 已登記為另一個 identity | 是：單一回合內的存檔；既有 `registry.register` 拒絕條件提前到寫入前，避免書目庫出現不可引用的條目，不是協調機制（逐行） | `evidence/C5-S3/single-store.md` §5 |
| 6 | 書目庫寫入的非預期例外轉為 `internal_error` | 使用者在單一專案流程中存檔，寫入時發生權限或磁碟錯誤 | 是：循序存檔失敗必須誠實回報，不可讓整個工具呼叫崩潰（逐行） | 同上 |
| 7 | `_require_saved_conversation`（事件迴圈上只做 `is_file()` 存在檢查）與 scan 推導的 `project_conversations` 三項 fail-closed 檢查 | 開啟、列出、選取、改名、刪除一個專案的對話；後端重啟或 crash 後重新開啟 | 是（概括）：「所有新增或保留的檢查都對應支援的循序使用，沒有為同時操作新增任何協調」 | `evidence/C6-S2/backend.md` 首段 |
| 8 | `conversationToRestore` 與 `historyIssue` 通知（Refresh without resending） | 開啟專案、看清單、後端 crash／重啟後選回原對話；回合停止或失敗後已存檔對話無法重新整理 | 是（概括）：「沒有新增任何跨專案或並行協調」 | `evidence/C6-S3/frontend.md` 首段 |
| 9 | `TurnOptions` 與 `_TurnWork`（每回合選項與每回合紀錄） | 一個回合中途失敗或結束後，下一個回合在同一對話開始 | 是；不新增鎖、排程或拒絕條件（R1），也不在回合開始時檢查待核准項目（R6）（逐行） | `evidence/C7-S5/turn-state.md` 首段 |
| 10 | 4 個共用 Busy 查詢（`_turn_or_approval_active`、`_document_work_active`、`_other_operation_active`、`_raise_if_knowledge_or_extension_active`） | 回合進行或等待核准時切換／改名／刪除對話、開啟專案、關閉 | 是：保護支援的單一工作流程中的循序操作；沒有新增拒絕條件、沒有統一 `retryable`、沒有衝突表、鎖階層或全域控制器（R1）、沒有待核准檢查（R6）；沒有搬移任何 flag、計數或 lock（逐行） | `evidence/C7-S6/busy-matrix.md` 首段與 §2 |
| 11 | Retry Stop（`_retry_stop`） | 使用者按 Stop，清理失敗（或回合仍 pending），再按一次 Stop | 是；沒有新增鎖或拒絕條件，只把「重播舊錯誤」換成「真的重試」（逐行） | `evidence/C7-S7/retry-stop.md` 首段 |
| 12 | 不在 Tauri 內執行時的處理 | 非支援的執行環境 | 不另做橫幅或假資料路徑（R2）：走一般「後端無法連線」錯誤（概括） | `evidence/C8-S4/browser-preview.md` 首段 |
| 13 | 純函式 `ownsWorkspaceOperation`、`turnEventIsStale`、`lifecycleResultIsStale`、`approvalExpiry` 與其測試 | 已結束操作的晚到回應、重啟後的舊 generation 事件、核准逾時 | 是（概括）：C8-S6「範圍遵循單一工作流，不為專案 A、B 同時操作新增檢查」；這些是保留既有必要檢查並補測試，不是新增拒絕條件 | `evidence/C8-S6/domains.md` 首段與 §三 |
| 14 | 元件只收值與 callback，不呼叫 `api.`，沒有全域 store | — | R1：沒有 `WorkspaceStore`／controller（概括） | `evidence/C9-S2/components.md` 首段；C10-S2 `grep -rn "api\." desktop/src/components` 為 0 |
| 15 | `clearApproval(state, dropOwner)` | 核准關閉的 10 條路徑 | 只保留既有的「3 條釋放擁有者、7 條不釋放」差異，未統一（概括） | `evidence/C8-S5/reducer-approval.md` |

沒有三段式紀錄、也沒有新增檢查或協調機制的步驟（C2-S1–S7、S9、S10、C3-S1、S5、S6、C4-S1–S6、C5-S1–S2、S4–S6、C6-S1、S4、S5、C7-S1–S4、S8、S9、C8-S1–S3、C9-S1、S3–S5、C10）屬於刪除、改名、搬移或測試整理。

### 6.2 沒有為不支援的同時操作新增機制

- 逐項檢視上表：每個新增或保留的機制，觸發情境都屬於 GOALS U12 表中「支援的正常使用」（依序切換、同一回合的 Stop 與核准、Stop 清理失敗再 Retry Stop、核准逾時、後端意外結束與重啟、書目庫寫入失敗、已結束操作晚到的回應）。
- 沒有新增鎖、排程、全域控制器或衝突表；測試沒有以「兩個專案」或「兩個對話同時操作」為驗收目標（C7-S6 的測試是「同一個忙碌條件」下的訊息與 `retryable` 不變，加一個「另一個讀取請求」的 select／delete 對照，皆為既有行為的釘住）。
- 限制：本節是對 evidence 的彙整，不是對全部 diff 的獨立審查；表中標「概括」的列沒有逐機制的三段式原文。

### 6.3 R1–R6 沒有重新引入

| 項目 | 結果 | 依據 |
|---|---|---|
| R1 大型 store／controller、階層鎖、忙碌衝突表 | 沒有。C7-S6 只抽共用查詢、不搬所有權；C8 沒有全域 store；C9-S2 元件不呼叫 `api.` | C7-S6、C8-S6、C9-S2 |
| R2 恢復 fixture／browser preview | 沒有。C8-S4 刪除 browser preview；`fixture_session.py` 只是從 production 套件移到 `app/tests/support/`（P5），C10-S2 `grep RESEARCH_AGENT_DESKTOP_FIXTURE\|fixture_session agent` 為 0 | C7-S1、C8-S4、C10-S2 |
| R3 立即加掃描快取 | 沒有；只量測（第 7 節） | C6-S4 |
| R4 CSS 色彩 token、近似色合併 | 沒有；hex 110／rgba 16 不變，打包後 CSS 前後只差一個選擇器 | C9-S3、C10-S2 |
| R5 S056 `LocalWorkScope` 循環 import | 沒有處理。C7-S7 只改 `LocalWorkScope.finish_stop` 的行為；撰寫時以 `git diff 4f488eb~1..HEAD -- app/agent/ingest.py` 核對，import 行沒有變動 | C7-S7、撰寫時重算 |
| R6 回合開始時檢查待核准項目 | 沒有。C7-S5、C7-S6 evidence 明確聲明；撰寫時 grep `turn_ops.py`，只有 `_complete_pending_approval` 的既有呼叫，沒有回合開始時的待核准條件 | C7-S5、C7-S6、撰寫時重算 |

---

## 7. 掃描量測（R3：只量測，不加快取）

來源：`evidence/C6-S4/scan-cost.md`、腳本 `scan_cost.py`（commit `87c8844`，`[C6-S4]`）。

- **條件**：Intel Core Ultra 9 285H（16 執行緒）、31 GiB RAM、WSL2、Python 3.13.14；資料在 `$TMPDIR`（ext4）。每個對話約 0.96 MiB（4 個文件回合，每回合凍結的 `sourceText` 約 250 KB）。每次量測新建 `DesktopService`，量「開啟專案」（`workspace.select` open，含 inspect 與 scan）與緊接的一次 `session.list`；各跑 3 次取中位數；scan 次數以包裝 `ConversationRepository.scan` 計算。

| 對話數 | 歷史總大小 | 開啟專案（中位數） | 開啟時 scan 次數 | 一次 `session.list`（中位數） | `session.list` scan 次數 |
|---|---|---|---|---|---|
| 10 | 10.1 MB | 0.122 s | 1 | 0.123 s | 1 |
| 50 | 50.6 MB | 0.565 s | 1 | 0.557 s | 1 |

- 耗時約與歷史總位元組數成正比，約每 MB 11 ms（scan 會完整讀取並驗證每個對話檔，包含凍結的文件內容）。
- 前端在支援的流程中觸發 scan 的時機：開啟專案（`workspace.select` 一次加 `session.list` 一次）、每個回合完成後重新載入清單一次、刪除與 turn 停止／失敗後的重新整理各一次、Load more 一次。以 50 個約 1 MiB 的對話估算：每回合完成後多約 0.56 s 的背景清單載入（此時回答已顯示、回合已結束），開啟專案約 1.1 s。
- 限制：只量熱檔案快取（檔案剛寫完），沒有量冷快取；只有一種對話大小（約 1 MiB）。
- **「是否加快取」是使用者的決定（R3）**：本計劃不訂門檻、不加快取。證據只顯示成本與歷史大小成正比；沒有資料顯示你實際專案的歷史大小。

---

## 8. 過時的 `for_agents/` 條目（建議以 `$infrastructure` 重新整理）

`for_agents/` 依限制沒有修改（9 個檔案有你未提交的修改，`git status` 仍為 ` M`）。下列條目的描述與現況不符。「`for_agents/` 現狀」引用的是撰寫時工作樹（含你的未提交修改）的行號與文字，行號可能隨你的修改位移。

| 條目 | `for_agents/` 現狀 | 現況（依據） |
|---|---|---|
| INV-006 | 「Schema v3 writes (reads v1–v3)」；提到 `_reload_and_recover` | 只讀 v3，v1／v2 明確拒絕（C2-S5）；`reload_and_recover` 已公開（C7-S4） |
| INV-010 | 驗證包含「authoritative metadata/BibTeX」、「bundle written」；`_persist_item` 是唯一 `registry.register` 呼叫 | 無 BibTeX、無 bundle；桌面「可引用 ⇔ 已在書目庫」，登記移到書目庫寫入成功之後；CLI 是 `verified`（C5-S3） |
| INV-011 | 「40 methods, 20 request events … validated in Python, TS, and Rust」「127 shared message … fixtures」、`ProtocolTraceValidator`、BACKLOG-011、`final_only` | 25／8／4／25；只有 Python 驗 schema，TS 讀 contract 只驗 request 與回聲，Rust 只驗框架（U1）；125 messages／60 traces；`ProtocolTraceValidator` 已刪（Python 版在 `app/tests/protocol_trace_oracle.py`）；`streamKind` 已刪（C3、C4、C6-S2、C10-S2） |
| INV-016 | `catalog.py`、`load_project_catalog` fail-closed | 改為 `project.py` 的 `open_project_history`／`project_conversations`；catalog 指向遺失對話與空歷史目錄歸屬兩項 fail-closed 消失（U3、U11）；壞檔、缺目錄、混入他專案對話仍拒絕（C6-S2） |
| INV-023 | `bashPermissionMode`、`_session_set_bash_permission`，「Wire field name remains `bashPermissionMode`」 | `permissionMode`、`session.set_permission`（C4-S4） |
| INV-027 | Retry Stop 重播快取錯誤（FAIL-022）、`service.py::_session_stop`／`_finish_turn_work` | 已修（C7-S7）；這兩個函式現在在 `turn_ops.py`（C7-S8e） |
| INV-029 | `cite/` 是產生輸出；列出 `app/desktop/watch.out` 在工作樹 | `cite/` 不再產生新內容（殘留 bundle 見第 12 節）；`watch.out` 已刪（C2-S9） |
| INV-032 | 「never alter bundle save outcomes」；`catalog.py::update_project_metadata`；`service.py::_unknown_new_citation_keys` | 桌面書目庫失敗即 `storage_failed`、不可引用（U13）；合併規則本身不變；catalog 模組改名 `project.py`；`service.py` 已拆成 11 個模組，`_unknown_new_citation_keys` 等位置須重查（C7-S8） |
| FAIL-022 | 失敗的 Stop 清理讓後端忙碌到重啟 | **已修正**（U14，C7-S7；`known-failure-modes.md` 第 67 行起與第 425 行的症狀表要更新） |
| BACKLOG-011 | 對齊宣告與產生的協定詞彙（40 個方法、12 個未發出 event、disabled folder-ingest RPC） | 已完成（C4、C6；C10-S0 比對 25／8） |
| BACKLOG-022 | 讓失敗的 Stop 可恢復 | 已完成（C7-S7） |
| ASM-014 | 「12 `SaveItemStatus` values plus `BibliographyLink` status/key」模型是否誇大存檔結果 | 存檔狀態本身已誠實回報；新增 `verified`、`BibliographyLink` 只剩 `added`／`existing`，風險描述與值數要更新（C5-S3） |
| ASM-016 | 依賴 `catalog.py`、`desktop-projects.json`、`DesktopProjectCatalog` 無 fingerprint 寫入 | catalog 已不存在，該失敗模式消失；剩 `RESEARCH.md` 與 `references.json` 的 fingerprint 預檢（C6-S2） |
| `data-flow.md` | 第 32、35、37 行（`load_project_catalog`、`CatalogError`、`catalog.py`）；第 85–94 行（`cite/`、`write_identity_bundle`、bundle-only、`bibliography.status="failed"`＋`reason_code`）；第 119、160 行（FAIL-022）；第 149、154 行（catalog、`cite/*`） | C5-S3、C6-S2、C7-S7 |
| `module-responsibilities.md` | 第 22 行（bundles/receipts）、25 行（`catalog.py`）、28 行（`{protocol,server,service,fixture_session}.py`、40 個方法）、41 行（`service.py` 4,643 行、40 個方法）、46 行（`bashPermissionMode`、`DesktopProjectCatalog.rebuild_from_conversations`、`activate_citation_skill`、Retry Stop） | C4-S4、C5-S3、C6-S2、C7-S1、C7-S7、C7-S8、C2-S2 |
| `testing-strategy.md` | 第 14 行（`npm run build` 只有 `tsc --noEmit && vite build`）、43／60 行（`answer_stream.test.ts`，「Repeated Stop after failed cleanup untested」）、66 行（`fixture_session.py` 在 `agent/desktop`）、68 行（127／60 fixtures） | `npm run build` 現在加跑 `tsc -p tsconfig.test.json`（C8-S2）；`answer_stream.test.ts` 改名為 `conversation_turns.test.ts`（C4-S3）；Retry Stop 已有測試（C7-S7）；fixture 在 `app/tests/support/`（C7-S1）；125／60（C10-S2） |
| `architecture-map.md` | 第 22、28、55、84 行（bundle-only／saved citation bundles）、44 行（fixture gate）、46 行（Project catalog）、74 行（catalog fingerprint）、115 行（`cite/`、`CITATION_OUTPUT_DIR`、`AgentConfig.citation_output_dir`） | C5-S3、C6-S2、C7-S1 |
| 其他 | `for_agents/README.md`、`dangerous-assumptions.md` 仍描述 `catalog.py`、`DesktopProjectCatalog`、`load_project_catalog`、`CatalogConflictError`（C6-S2 evidence 已記） | C6-S2 |

另：C4-S3 evidence 指出 `invariants.md`、`testing-strategy.md`、`known-failure-modes.md` 仍提到被改名的舊測試檔名。`for_agents` 的測試數字（1,808／329／42 等）也已過時（第 3.4 節）。

---

## 9. `AGENTS.md` 過時的句子（只列出，沒有修改）

撰寫時以 `grep -n "issue/\|cite/" AGENTS.md` 核對；`ls issue` 回報目錄不存在。

1. **`issue/` 不存在**（`AGENTS.md` 第 5 行）：「Treat records in `issue/` and `note/` as context, not automatic implementation scope.」
2. **`issue/` 不存在**（第 19 行）：「Use `issue/` and `note/` for project records.」
3. **`cite/` 已不會產生新內容**（第 19 行同段）：「Treat `cite/`, `app/store/`, `app/dist/`, and caches as generated output.」——桌面存檔只寫專案書目庫，CLI 不寫檔（C5-S3）；現存 `cite/` 只是殘留（決策紀錄 §7 也註明：這句話對殘留檔案仍然成立，是否修改由你決定）。
4. **「citation bundles」不再產生**（第 53 行）：「Keep generated stores, citation bundles, secrets, and `.env` files out of commits.」——bundle 已不再產生；`.gitignore` 的 `/cite/` 規則仍保留（撰寫時 `git check-ignore -v cite` 命中 `.gitignore:11`）。

撰寫時另 grep `AGENTS.md` 的 `pybtex|bibtex|knowledge|browser|preview|CITATION_OUTPUT|service.py|App.tsx|protocol.rs|protocol.ts|parity`，沒有命中。

---

## 10. GUI 手動檢查清單（共 58 項）

**GUI 沒有被執行者驗證。** 下表每一項都是需要你本人在桌面 app 中操作並目視確認的項目；「預期」欄是 evidence 依程式碼與測試推論的結果，不是觀察結果。

- 順序：第 1–37 項是 C8 與 C9 標為高風險或明列「需人工」的項目（焦點與 Tab 行為、effect 時序、核准框接線、擴充重啟順序、重啟後的過期事件）；第 38 項起是各階段新增的其餘項目與基礎回歸流程。
- 「流程編號 F」取自 `evidence/C8-S1/app-behaviors.md` §1（拆解前盤點的 28 個使用者流程）；C8-S1 當時的行號已失效，只取流程描述。
- 風險欄：「高（C8）」＝C8 evidence 標註高風險；「高（C9）」＝C9 evidence 註明只能在 WebView 驗證；「一般」＝其餘。

### 10.1 C8 高風險項目（1–19）

| # | 來源 | 觸發 | 預期 | 風險 |
|---|---|---|---|---|
| 1 | C8-S1 F1 | 冷啟動桌面程式 | 依序出現「Preparing your research workspace」→ 側欄「Starting backend」＋spinner 卡片 → ready 後「Checking the local runtime」→ 診斷完成後自動彈出「Open a research project」對話框；側欄「Choose a project to load its conversations.」 | 高（C8：effect 串接；`App()` effect 由 13 降為 11） |
| 2 | C8-S1 F4、C6-S3 #4 | 選取一個對話後按 Restart（或後端 crash 後按重啟） | 「Restarting backend」＋spinner → 「Reopening selected project」→ 清單重載 → 自動選回原對話並還原草稿（重啟還原時不跳 `window.confirm`）；若原對話已被刪除，不選任何對話、不顯示錯誤 | 高（C8） |
| 3 | C8-S1 F3、C2-S8 | 讓後端意外結束（回合進行中與閒置各一次） | 側欄「Backend crashed」；通知「The local backend stopped unexpectedly」＋「Restart backend」；核准框消失、進行中的回合畫面清掉；重啟後選取、草稿恢復與 C2 之前相同 | 高（C8） |
| 4 | C8-S6 §七 #8 | 回合進行中重啟後端 | 舊 generation 的事件不影響新畫面（不出現舊回合的進度、答案或核准框） | 高（C8，沿用 F3／F4） |
| 5 | C8-S6 §七 #3 | 擴充預覽 → Apply 且結果需要重啟 → Restart | 面板依序顯示 restarting → awaiting load → loaded | 高（C8：snapshot 轉移與 revision 觀察的時序） |
| 6 | C8-S6 §七 #2 | 擴充 Apply 進行中讓後端崩潰 | 面板顯示可重試；按 Retry apply 使用同一個 request；顯示「The backend stopped before the saved extension result was delivered.」 | 高（C8） |
| 7 | C8-S6 §七 #1、C8-S1 F25 | 擴充預覽 → 檢視 → Apply（Ask 與 Bypass 各一次） | Ask：每個 MCP binding 要選 Approve／Deny，全部決定前 Apply 停用；Bypass：不出現逐項核准 | 高（C8） |
| 8 | C8-S5 #1 | 引用面板 Verify-and-add | 核准框出現；Approve 後加入並關閉；Deny 後關閉；核准框開著期間 add request 不被誤判為過期 | 高（C8：核准框接線） |
| 9 | C8-S5 #2 | 文件 apply 核准（回合提出的與直接 document 操作） | Approve／Deny 皆可；結束後對話框關閉、焦點回輸入框 | 高（C8） |
| 10 | C8-S5 #3 | 回合中的 bash／工具核准 | 出現、Approve／Deny；到 `expiresAt` 自動 Deny；回合結束或失敗後對話框消失 | 高（C8） |
| 11 | C8-S5 #4 | 核准待處理時按 Stop | Stop 完成前不能 Approve／Deny；Stop 後對話框關閉 | 高（C8） |
| 12 | C8-S5 #5 | 核准待處理時後端重啟或 crash | 對話框消失；重啟後可正常開新回合；舊核准的事件不再套用 | 高（C8） |
| 13 | C8-S5 #6 | 核准待處理時開啟／切換專案、刪除對話 | 對話框消失，沒有殘留 resolving 狀態 | 高（C8） |
| 14 | C8-S5 #7 | 關閉核准框 | 焦點是否回到輸入框與之前一致（保留擁有者的 7 條路徑與釋放擁有者的 3 條路徑） | 高（C8） |
| 15 | C8-S5 #8 | 一般回合、Stop、刪除對話、專案開啟 | 草稿、引用、Stop、Retry 行為與之前一致（每個對話 action 只算一次 reducer） | 高（C8） |
| 16 | C8-S6 §七 #7 | 核准逾時；已過期的核准一出現 | 到期自動 Deny；已過期者一出現就 Deny | 高（C8） |
| 17 | C8-S6 §七 #6、C8-S1 F15–F16、C7-S7 | Stop 失敗（較難觸發，可借注入失敗的測試環境） | 出現「The turn could not finish stopping」＋「Retry Stop」；回合結束後另出現「Your message」摺疊與「Restart backend」；composer 仍鎖住；Retry Stop 後回到「Stopping…」，成功則「Refreshing saved conversation」並更新 transcript；失敗訊息以錯誤色顯示 | 高（C8） |
| 18 | C8-S6 §七 #4、C8-S1 F21 | 文件存檔衝突 | 衝突面板顯示 Original source／Current editor／Current disk／Agent candidate；Keep editor／Use candidate and save／Cancel；衝突後再編輯再按 Use 顯示「The editor changed again. Save again to review the current conflict.」；衝突存在時不能切專案 | 高（C8） |
| 19 | C8-S6 §七 #5、C8-S1 F20 | 文件 agent 操作衝突 | 選擇後同一個操作以選擇重送；失敗時顯示 issue；取消顯示「Operation cancelled」 | 高（C8） |

### 10.2 C9 高風險（只能在 WebView 驗證）項目（20–37）

| # | 來源 | 觸發 | 預期 | 風險 |
|---|---|---|---|---|
| 20 | C9-S1 #1 | 右鍵對話 → Delete | Tab／Shift+Tab 只在兩顆按鈕間循環；Cancel 已有焦點；Esc 關閉且焦點回該列；刪除進行中 Esc 無效 | 高（C9） |
| 21 | C9-S1 #2 | 右鍵對話 → Rename | 輸入框已全選；Tab 在輸入框、Save、Cancel 間循環；Esc 關閉、焦點回該列；儲存中 Esc 無效；IME 組字時 Enter 不送出 | 高（C9） |
| 22 | C9-S1 #3 | 開啟選專案對話框 | Tab 在按鈕／輸入／select／checkbox 間循環（含展開候選後）；Esc 關閉（焦點不特別還原）；忙碌時 Esc 無效 | 高（C9） |
| 23 | C9-S1 #4 | Bash 核准（modal） | Deny 先有焦點；Tab 只在 Deny／Approve／Stop 間循環；Esc 與點 backdrop 都等於拒絕；處理中 Esc 不關閉也不洩漏到後面 | 高（C9） |
| 24 | C9-S1 #5 | 文件／operation 核准（非 modal） | Tab 可離開對話回到編輯器；Esc 等於拒絕；點 backdrop 不拒絕 | 高（C9） |
| 25 | C9-S1 #6 | 文件標頭 `•••` 選單 | Esc 關閉並聚焦 summary；點外部關閉；Tab 離開關閉；點項目後關閉並回到 summary | 高（C9） |
| 26 | C9-S1 #7 | 對話右鍵選單 | Esc 與 Tab 關閉並焦點回該列；方向鍵循環；點 backdrop 關閉並還原焦點；右鍵 backdrop 關閉；靠近視窗邊緣時位置被夾住 | 高（C9） |
| 27 | C9-S1 #8 | Thinking 控制 | ArrowDown 開啟並聚焦已選項；方向鍵／Home／End；Esc 關閉並聚焦 trigger；點外部關閉；選項後焦點回 trigger；回合進行中停用時自動關閉 | 高（C9） |
| 28 | C9-S1 #9 | Export 選單 | 開啟後聚焦第一項；Esc 關閉並聚焦 trigger；點外部關閉；選項後焦點回 trigger | 高（C9） |
| 29 | C9-S2 #1 | Sidebar 操作 | 選對話、Load more、Start／Restart／Shut down、狀態點與文字、右鍵選單位置正常 | 高（C9） |
| 30 | C9-S2 #2 | DocumentPane 操作 | 開檔、儲存（Ctrl+S 與選單）、Undo、未儲存圓點、`Working…`、衝突三選項、引用面板顯示條件 | 高（C9） |
| 31 | C9-S2 #3 | Transcript | restored、live、pending 三種卡片外觀不變；工具活動展開；章節 annotation 標記與彈出視窗位置；Load older 與空對話提示；切換對話時的預覽模式 | 高（C9） |
| 32 | C9-S2 #4 | Composer | Enter／Shift+Enter／IME；`/`、`@` 清單；Stop；重試設定提示與「Send new turn with current settings」；reference issue 提示 | 高（C9） |
| 33 | C9-S2 #5 | ProjectChooser | 選資料夾、history 目錄編輯與 Inspect、未儲存文件選項、丟棄草稿勾選、按鈕狀態文字 | 高（C9） |
| 34 | C9-S2 #6 | 通知與狀態卡片 | 錯誤卡片 4 個按鈕、Stop 失敗卡片、History 未更新卡片、四種 empty state、Backend ready 卡片與 runtime details | 高（C9） |
| 35 | C9-S2 #7 | 核准框與 `ThinkingControl`、`PermissionControl` 外觀 | 外觀與 C9-S1 清單一致 | 高（C9） |
| 36 | C9-S3 | 全畫面目視比對 | 外觀與之前一致（CSS 規則順序與內容相同，但仍請目視）；刪除／改名／選專案對話的錯誤文字仍是紅色（`.dialog-error`）；擴充面板錯誤仍是紅色（`.extension-error`） | 高（C9） |
| 37 | C9-S4 | 文件編輯器 Ctrl／Cmd 加 `=`、`+`、`-`、`0` 縮放 | 縮放後 line height 不與文字重疊（`editorFontOptions`、`zoomKeybindings` 取代內嵌寫法） | 高（C9） |

### 10.3 其他項目與基礎回歸流程（38–58）

| # | 來源 | 觸發 | 預期 | 風險 |
|---|---|---|---|---|
| 38 | C8-S3 §7、C8-S1 F6–F7 | 選專案：Browse（原生 picker）→ inspect → open／initialize → 重新開啟 | 對話框顯示 Resolved project；依狀態顯示 History directory 輸入、初始化說明或驗證說明；有未存文件／草稿時出現對應選項；成功後側欄顯示專案名稱與「N saved」；存檔失敗時留在對話框 | 一般 |
| 39 | C8-S3 §7、C8-S1 F8–F12 | 對話建立、選擇（含預覽）、改名、刪除、Load more、Load older turns | 與 F8–F12 的描述一致：有草稿時 `window.confirm`；預覽為 `aria-busy`；改名超過 256 bytes 顯示「Enter a shorter name.」；刪除正在執行的對話先 stopping 再 deleting | 一般 |
| 40 | C8-S3 §7、C8-S1 F13–F14 | 送出回合、失敗與 Retry saved turn | 使用者訊息＋「Assistant · working」；Send 變 Stop；完成後捲到底、焦點回輸入框；失敗顯示對應通知、草稿保留；設定不同時顯示「Send new turn with current settings」 | 一般 |
| 41 | C8-S3 §7、C8-S1 F18–F20 | 文件開啟（原生 picker）、存檔、agent 套用、Undo | 與 F18–F20 一致：未存變更時 `window.confirm`；agent 提案自動 `document.apply`；Undo 送 `undoOfCallId` | 一般 |
| 42 | C8-S3 §7、C8-S1 F22 | 引用面板：inspect、render、export、set_style、remove、add | 展開看條目；Markdown 文件才有 Export（Word、BIME Word、Markdown）；已引用列有 Line 跳轉、未引用列有 Remove；回合進行、文件忙碌、核准中時寫入停用 | 一般 |
| 43 | C8-S3 §7、C4-S4、C8-S1 F23–F24 | 切換 Thinking（Normal／Extended）與 Permission（Ask／Bypass）後送出回合 | 控制項名稱與行為與之前相同；核准行為與切換前一致；切換對話後權限設定照常保存在記憶體；Bypass 時擴充預覽不再逐項詢問 | 一般 |
| 44 | C8-S4、C8-S1 F2、F5 | 在 Tauri app 中 Start／Restart／Shut down；啟動失敗 | 按鈕與 New conversation 的可用狀態照舊；啟動失敗顯示「Action required」與 Retry start；Shut down 顯示 shutdown 摘要 | 一般 |
| 45 | C8-S1 F26–F28 | 輸入 `/`、`@` 與選取文字加入引用 | 斜線清單與 `@` skill 清單的鍵盤行為、無符合時的提示、引用卡片與跨訊息選取提示與 F26–F28 一致 | 一般 |
| 46 | C6-S3 #1 | 開啟已有對話的專案 | 側欄只有這個專案，標題是專案資料夾名稱，「N saved」與列出的對話數一致，順序由舊到新 | 一般 |
| 47 | C6-S3 #2 | 按 New conversation 並送出第一則 | 出現「Not saved yet」列；第一次送出完成後變成一般對話列（顯示回合數），且只出現一次 | 一般 |
| 48 | C6-S3 #3 | 右鍵刪除一個對話 | 該對話從清單消失，數字減一 | 一般 |
| 49 | C6-S3 #5 | 檢視畫面與 session details | 沒有「Retry registration」按鈕與「CATALOG REGISTRATION PENDING」通知；session details 只顯示 session ID 與回合數，沒有 cataloged／transient | 一般 |
| 50 | C6-S3 #6（選擇性） | turn 停止或失敗後出現「CONVERSATION NOT REFRESHED」 | 按「Refresh without resending」後清單與對話內容更新、通知消失，且 prompt 沒有被重送 | 一般 |
| 51 | C5-S6 §6 | 在專案中以 `/citation` 存檔 | 書目庫（預設 `references.json`）新增 key；專案或 repo 中不產生 `cite/` | 一般 |
| 52 | C5-S6 §6 | 在引用面板以 DOI 加入文獻 | 核准對話框的目標顯示書目庫路徑 | 一般 |
| 53 | C5-S6 §6 | 把書目庫設為唯讀後存檔 | agent 告知沒有存檔（不可引用），而不是說已存檔 | 一般 |
| 54 | C5-S6 §6 | 展開 runtime details 與 session details | 不再顯示「Citation output」 | 一般 |
| 55 | C4-S3 §6 | 展開 Local runtime details | 不再顯示「Ollama」與「Ollama model」兩列 | 一般 |
| 56 | C2-S8 §3 | 觸發 Stop 失敗訊息與 source editor 問題訊息 | 兩處 `.error-text` 以錯誤色（`#843c38`）顯示 | 一般 |
| 57 | C2-S11 §4 | 觸發一個會失敗的文件操作（例如開啟不存在或超界範圍的文件）或書目匯出失敗 | 錯誤訊息完整顯示原文，不被整句替換為 withheld | 一般 |
| 58 | C8-S4（選擇性） | 以一般瀏覽器（非 Tauri）開啟前端 | 顯示一般的後端無法連線錯誤，沒有假資料預覽（程式推論；`listen` 失敗的 `catch` 路徑） | 一般 |

---

## 11. 未處理、需要使用者決定的事

### 11.1 GOALS「不納入」與「已否決或延後」

| 項目 | 狀態與需要的決定 |
|---|---|
| R3 掃描快取 | 延後；數據在第 7 節。決定是否加快取，以及門檻。 |
| R4 色彩 token、近似色合併、media query 整併（P12） | 延後到 GUI 改版；S096 因此為「部分」。 |
| R1、R2、R5、R6 | 否決或不做；本計劃沒有重新引入（第 6.3 節）。R5（S056）仍是未處理的循環 import。 |
| S125 刪除已完成的計畫紀錄 | 等你的 GUI checklist 與 live grill eval 完成。 |
| S134 把 `GUI` 合回 `main`、刪 `clean` 分支 | 使用者的規則禁止 AI 建立、切換、刪除 branch 與 push；由你決定。 |
| S084 `styles.test.ts` 與 INV-021 | 屬 UI 重設計；INV-021 數值不變，測試未改（C9-S4、C9-S5）。 |
| S067 `chromadb`、`openrouter` 相依 | 相依變更需另外核准；U9 只核准了 `pybtex`。 |
| S131 `AGENTS.md` 過時 | 第 9 節列出句子。 |
| S126、S127 根目錄筆記與 `note/20261106/` | 你的研究資料，未追蹤，未提交。 |
| S132 `tool/local/` 預留區、S133 README 改寫 | 產品方向與文件風格決定。 |
| 長尾 DECIDE（S013、S015、S017、S025、S030、S032、S033、S045、S048–S051、S053–S055、S057–S060、S064、S077、S091、S094、S099、S100、S103、S111–S113、S116、S130）；S036、S066、S121、S123 中未做的其餘部分 | 不在稽核路線內，或證據信心較低，或會改變行為而沒有決策覆蓋；逐項理由見第 2 節表格。 |
| P8 不補回 CSL 與 BibTeX 的 DOI 交叉比對 | 已執行並記在第 4.4 節。若論文要把「交叉比對兩種格式」列為驗證步驟，要否決 P8 並以 CSL 之外的來源（例如 Crossref、DataCite 記錄）比對，而不是恢復 BibTeX（決策紀錄 §6.1）。 |
| 是否另外為論文評估保存逐筆存檔紀錄 | `citation.json` 的 intent／resolution 細節已不再落地（決策紀錄 §6.1、§9）；需要時另外決定記錄位置，不恢復 bundle。 |

### 11.2 `retryable` 不一致（C7-S6 觀察，**沒有改**）

`evidence/C7-S6/busy-matrix.md` §1 的現況對照中，`BUSY_TURN` 的 `retryable`：

- **False**：`_session_create`（「A session turn is still active.」）與 `_workspace_select`（「Wait for the active turn before changing project.」）。
- **True**：`_session_select`、`_session_rename`、`_session_delete`、`_runtime_shutdown`、`_shutdown_session`、`_require_idle_session`。

C7-S6 照 U21 與 R1 不統一，只用 62 個參數化案例釘住現況。其他已觀察到但同樣保留的差異：
- knowledge 訊息用字：關閉時是「mutation」，`_require_idle_session` 是「operation」；
- `_session_delete` 與 `_workspace_select` 把另一個讀取請求也算進忙碌（`P > 1`、任何 project 請求），`_session_select`／`_session_rename`／`_session_create` 則扣除讀取（`P−R > 1`）。

決定：要不要統一，以及統一成哪一邊（統一會改變 GUI 是否顯示「可重試」）。

### 11.3 執行中新發現的項目

| 項目 | 內容 | 依據 |
|---|---|---|
| composer `/ingest` 的 `partialWritePossible` | `session.turn` 失敗的 `error.details` 依 contract 只能是 turn lifecycle 四個欄位，所以 composer `/ingest` 遇到 Ollama 或寫入錯誤時，使用者看不到「可能已部分寫入」。這是既有行為（該欄位只存在於已刪除的 RPC 路徑）。若要讓使用者知道，需要另外的設計決定。 | `evidence/C4-S1/knowledge-rpc.md` |
| `096b679` 的 docs commit 夾帶程式修改 | 標題是 `docs(plan): record App() domain split [C8-S6]`，但同時把 `listen` 移入 `api.ts`（`App.tsx` 6 行、`api.ts` 7 行）；測試與 build 通過。已在 C8-S7 evidence 註記，沒有改寫歷史。 | `evidence/C8-S7/wrap-up.md`；撰寫時 `git show --stat 096b679` 核對 |
| C9-S4 合併的合成資料測試 | 3 個 SafeContent 大集合測試、restored 多 MB 答案測試與 `protocol.test.ts` 的 750,000 字元答案測試（共 5 個）合併成 `conversations.test.ts` 的 1 個，輸入大小不變；代價是失敗時要看斷言訊息才能定位是 parser 還是 renderer。 | `evidence/C9-S4/tests.md` §三、限制欄 |
| Retry Stop 的設計選擇 | 第一次 Stop 不自動重試；只有 Stop 送達時回合已結束才重試；以磁碟狀態為準；`pending` 只走 `reload_and_recover`；讀取失敗或恢復失敗就維持封鎖（沒有重啟以外的出口）；錯誤碼仍是 `INTERNAL_ERROR`，訊息附原因。這些是依 U14 與審核修訂的實作選擇，不是你逐項確認的。 | `evidence/C7-S7/retry-stop.md` |
| `editorRevision` 由 `undefined` 變為 0 | `api.ts` 包裝 `document.open` 時，baseline 的 `editorRevision` 由 `undefined` 變成 0；baseline 只讀 `sourceText`，沒有讀取者，無可見差異。 | `evidence/C8-S3/api.md` §4 |
| `protocolMismatch` 仍有 7 處 | `App.tsx` 就地的 `protocolMismatch` 13→7，剩下的是與 UI 狀態比對，不是回聲；`as unknown as` 23→0。 | `evidence/C8-S3/api.md` |
| S029、S026、S036、S121、S123、S037、S066 的保留部分 | 附理由保留或超出 GOALS 納入範圍；見第 2 節各列。 | 第 2 節 |
| `App()` 拆解範圍 | 依 U18 只抽出一個 domain hook（`useExtensions`）；核准的兩個 effect 因順序無法從程式碼確定而留在 `App()`；對話選單收益小未抽。`App.tsx` 仍有 1,932 行。 | `evidence/C8-S6/domains.md` |
| 借用的 class 名稱 | `approval-context`、`file-open-dialog` 的借用命名未動（C9-S1 註記）；`extension-error` 的 4 處借用已改（C9-S3）。元件規則在 CSS 中仍分散在幾個區段（P12 預期）。 | `evidence/C9-S1/primitives.md`、`C9-S3/css-split.md` |
| 新增測試基礎設施 | `tsconfig.test.json` 與 `tests/node-shim.d.ts`（沒有 `@types/node`，宣告用到的 Node API），`npm run build` 因此多跑一次 `tsc -p`；沒有新增 npm 套件。 | `evidence/C8-S2/pure-modules.md` |
| `LEGACY_CATALOG_FILENAME` | `project.py` 保留這個具名常數，只用於「初始化時容許目錄內有殘留的 `desktop-projects.json`」，從不讀寫。 | `evidence/C6-S2/backend.md`、C10-S2 residual grep |
| U6 的未檢查範圍 | `app/store` 以外的 `historyDirectory` 若有 v1／v2 對話檔，會讓該專案無法開啟；執行者無法檢查。 | `evidence/C2-S5/store-versions.md` |
| 掃描量測的範圍 | 只量熱快取、單一對話大小。 | `evidence/C6-S4/scan-cost.md` |
| build-log C10 列 | 本彙報提交後，build-log 的 C10 要標為 Complete（本檔未改）。 | phase-10 驗收 |

---

## 12. 殘留資料（你可以自行處理；執行者沒有刪除任何一項）

1. **`cite/` 的舊 bundle 與 `.locks/`**（repo 根目錄，已被 `.gitignore` 的 `/cite/` 忽略）。撰寫時唯讀 `ls -la cite` 看到：`cite/Attention_Is_All_You_Need--e0b4220861eb/`（11 月 7 日建立的一個 bundle）與 `cite/.locks/`（內含一個 0 byte 的鎖檔）。程式不再讀寫它們（C5-S3：`cite/` 前後清單比對相同）。若要保留只在 CLI 存過的作品：bundle 的 `citation.json` 有 DOI，可在桌面引用面板以 DOI 加入書目庫（決策紀錄 §7）。
2. **各 `historyDirectory` 中的 `desktop-projects.json`**。程式不再讀寫（C6-S2 的測試比對殘留檔的 bytes 與 `st_mtime_ns`，開啟、列出、新增對話後都不變）。撰寫時唯讀 `find app/store -name desktop-projects.json` 在 `app/store/projects/*/` 下找到 42 個（這個數字不在 evidence 中，是撰寫時重算）。你的其他專案歷史目錄中可能還有，執行者沒有檢查。
3. **`app/store/` 的資料**（對話檔、`chroma.sqlite3`）：依限制不動；C2-S5 只唯讀核對 schema 版本。
4. **未提交且與本計劃無關的檔案**：`NOTES-grill-skill-and-document-context.md`、`note/20261106/`、`.agents/`、`.opencode/`，以及工作樹中指向沙箱裝置的點檔（`.bashrc`、`.profile`、`.claude/` 等）；`for_agents/` 9 個你未提交的修改。全部依限制保留不動、不提交。
5. **建置與暫存輸出**：`app/desktop/dist/`、`src-tauri/target/`（已被 ignore）；C6-S4 與 C5-S6 的量測資料放在執行者的 `$TMPDIR`（`c6s4`、`c5s6-smoke`，repo 外，重開機可能已清除，evidence 只保留摘要與腳本）。
6. **已由本計劃刪除、不需處理**：`app/desktop/watch.out`（509 bytes，C2-S9）、repo 根目錄 `__pycache__/` 與空的 `harness/plans/.claude/`（C2-S9）、`tests/fixtures/legacy_v1_bundle`（C5-S3）。
