# C3-S2 TS 改讀 contract

- **日期**：2026-11-22
- **寫法**：C3-S1 的 (a)，`import contract from "../protocol/v1/contract.json" with { type: "json" };`。
- **規模**：`src/protocol.ts` 2,333 → 1,016 行；`src/backend.ts` 681 → 632 行；`tests/protocol.test.ts` 471 → 317 行。

## 1. `protocol.ts` 匯出的詞彙常數（定義式都引用 `contract`）

```
60:export const PROTOCOL_VERSION: number = CONTRACT.protocolVersion;
61:export const MAX_REQUEST_ID_BYTES: number = CONTRACT.requestIdMaxBytes;
62:export const MAX_ERROR_MESSAGE_BYTES: number = CONTRACT.errorMessageMaxBytes;
63:export const PROTOCOL_METHODS: readonly string[] = CONTRACT.methods.map(({ name }) => name);
64:export const REQUEST_EVENTS: readonly string[] = CONTRACT.requestEvents;
65:export const PROCESS_EVENTS: readonly string[] = CONTRACT.processEvents;
66:export const PROTOCOL_ERROR_CODES: readonly string[] = CONTRACT.errorCodes;
```

`CONTRACT` 是 `contract as unknown as ProtocolContract`（JSON module 型別把 field rule 的 `type` 放寬成 `string`，所以需要型別轉換）。`tests/protocol.test.ts` 的「protocol vocabulary constants are read from contract.json, not copied」斷言上列七個常數等於直接讀出的 `contract.json` 值。

**不再存在於 TS 的常數**（步驟規格列舉的類別中，TS 已無用途者）：

| 常數 | 處置 | 理由 |
|---|---|---|
| `MAX_PROTOCOL_LINE_BYTES` | 刪除 | 只被測試專用的 `parseProtocolLine` 使用（S072）；TS 透過 invoke 收到已解析的值，行長由 Rust 與 Python 負責。 |
| `FULL_TEXT_RESULT_METHODS` | 刪除 | 只有測試使用（S072）；大 result 豁免由 Rust 依 pending request 的 method 判斷。 |
| `FORBIDDEN_DATA_KEY_FRAGMENTS` | 刪除 | TS 不再掃描 result／event data（U1）；Rust 的 `validate_safe_data` 與 Python 的 `FORBIDDEN_DATA_KEY_FRAGMENTS` 保留。 |
| `PROCESS_EVENT_ORIGINS` | 刪除 | process event 來源檢查屬於 Rust 保留的框架檢查（C3 責任表）。TS 只檢查 origin 是 `python` 或 `rust`。 |
| 所有 `*_SCHEMA`、`RESULT_DATA_SCHEMAS`、`EVENT_DATA_SCHEMAS`、`METHOD_PARAM_SCHEMAS`、`METHOD_REQUIRED_PARAMS`、`TOOL_EVENT_DATA_KEYS`、`TOOL_STATUSES` | 刪除 | 手抄的 schema；request 參數改由 `METHOD_PARAMS`（`CONTRACT.methods[].params` 建成的 Map）驗證，必填取自 `params[].required`。 |

## 2. `src/protocol.ts` 中 `"<前綴>.<名稱>"` 形式的字串

grep：`grep -nE '"(session|document|bibliography|knowledge|extensions|runtime|project|workspace|approval)\.[a-z_]+"' src/protocol.ts`

| 行 | 用途 |
|---|---|
| 88–127 | `export type ProtocolMethod = | "…"` 型別聯集（40 個方法名，僅型別）。C3-S3 的 U16 測試會讓它與 contract 一致。 |
| 138–140 等 | `export type RequestEvent = | "…"` 型別聯集中 `knowledge.progress`、`shutdown.progress` 等以這些前綴開頭的 event 名（僅型別）。 |
| 449 | `ApprovalRequiredDto.operation` 的字面值聯集（DTO 型別，approval operation 名稱，不是方法清單）。 |
| 802 | `validateProjectPath(snapshot.path, "document.path")`：錯誤訊息中的欄位標籤，不是方法名。 |
| 854 | `validateParams` 中 `if (method === "session.turn")`：`session.turn` 專屬的 request 語意檢查（skill reference 範圍、submittedContext 合計大小）。 |
| 864 | `validateParams` 中 `if (method === "document.apply" && …)`：`callId` 與 `undoOfCallId` 二選一的 request 語意檢查。 |

沒有任何 runtime 陣列或物件字面量列出方法名稱。

## 3. production 中捕捉 result 驗證失敗的位置（盤點）

| 位置 | 捕捉什麼 | U1 之後 |
|---|---|---|
| `backend.ts` `requestTracked` 的 `.then((raw) => …)` catch → `asClientError(error, "protocol")` | 原本包含 `traceValidator.accept` 與 `validateResultData` 拋出的 result 驗證錯誤 | 兩個呼叫已刪；同一 catch 現在只接 envelope 解析錯誤、`requestId` 不相符與回聲比對錯誤。沒有另造替代檢查。 |
| `App.tsx` 約 1549 行 `normalizeUiError(error, "protocol")` | backend event listener 的 `parseBridgeEvent` 錯誤（event 路徑，不是 result） | 保留；event data 不再逐欄位驗證，只剩 envelope 錯誤會走到這裡。 |

沒有其他 production 程式捕捉 `ProtocolContractError`。

## 4. 回聲比對（`backend.ts`）

- `requestId`：維持 `message.requestId !== request.requestId` 即拒絕。
- 成功回應：`verifyResultEcho` 逐一比對 `echoedIdFields(method)`（由 contract 推導：params 與 result schema 都有的 `projectId`／`sessionId`／`turnId`），只在 request 帶了且 result 也帶了該欄位時比對。推導結果與 phase 檔列出的組合一致（另含 C6 會刪除的 `session.retry_registration`），由 `protocol.test.ts` 的「echoed identifier fields are derived from params and result schemas」固定。
- 失敗回應：`session.turn` 與 `extensions.apply`（沿用現行的方法判斷，集中在 `carriesTurnLifecycle`）解析 `error.details` 的 turn lifecycle，`turnId` 與 request 不同即拒絕；缺少 lifecycle details 也拒絕。

**產品邊界檢查**：成功回應的 `projectId`／`sessionId` 回聲比對 → 觸發情境：使用者依序切換專案或對話後，已結束操作（例如先前的 `session.select`、`session.transcript`）的回應晚到 → 支援的正常使用（GOALS「必須保留的不變量」中「已結束操作晚到的回應」）。這是 phase 檔要求從 contract 推導的既有回聲規則；原本 `ProtocolTraceValidator` 只比對 `turnId` 與 `session.stop` 的 `sessionId`，現在依同一份推導清單一致套用，沒有新增拒絕以外的狀態或協調機制。

## 5. S072、S071、S085、S090

- **S072（APPLIED）**：刪除只給測試的 `FULL_TEXT_RESULT_METHODS`、`METHOD_REQUIRED_PARAMS`、`parseProtocolLine`；`conversations.ts` 沒有 dispatcher 的 `"failure-cleared"` action；`App.tsx` 沒有選取者的 `data-document-menu` 屬性；`trust.tsx::acceptApprovalEvent` 只有測試傳的第 6 個參數 `activeTurnId`；`reconciledTurnCount` 改為呼叫端直接 `Math.max`。
- **S071（部分，APPLIED）**：刪除 0 引用的 `DocumentOpenDto`、`DocumentResultDto`。snapshot 型別統一歸 C8。
- **S085（APPLIED）**：刪除 grep `App.tsx` 原始碼的「Product Plan Mode is retired…」測試。
- **S090（APPLIED）**：`parseBackendSnapshot` 與 `parseShutdownReport` 只檢查是物件，不再逐鍵驗證（Rust 以單一 typed struct 序列化）。刪除只服務於逐鍵驗證的 `backendLifecycles`、`requireNonNegativeInteger`。

## 6. 測試退役紀錄

| 被刪或改寫的測試 | 它保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `protocol.test.ts`「language-neutral manifest matches TypeScript constants」 | TS 手抄常數與 schema 等於 contract（parity；手抄本已刪除） | 「protocol vocabulary constants are read from contract.json, not copied」；方法名唯一、無通用逃生口與 destructive 帶 `previewId` 的斷言移到「contract method names are unique and expose no generic escape hatches」。 |
| `protocol.test.ts`「Product Plan Mode is retired while extended thinking remains」 | 已退役功能不存在（grep `App.tsx` 原始碼，S085） | contract 不含 `session.set_mode`：`ProtocolMethod` 型別聯集與 C3-S3 的 U16 涵蓋檢查；Python contract 測試。 |
| `protocol.test.ts`「normal answers…」、「session turn carries…」、「extension apply carries…」、「session summaries and transcripts…」 | contract 內容（原本透過 TS 手抄本讀） | 同名測試保留，改為直接讀 `contract.json`，斷言不變。 |
| `protocol.test.ts`「complete answer and transcript text have no protocol capacity rejection」 | TS 不因大文字拒絕 result（原本經 `validateResultData`） | 改寫為「complete answer and transcript results have no client capacity rejection」：`parseProtocolMessage` 接受 750,000 字的 `session.turn` result。transcript 的 result data 在 TS 已不驗證，同一 envelope 路徑即涵蓋。 |
| `protocol.test.ts`「shared process-event origin fixtures」（6 例） | TS 端的 process event 來源檢查（已刪除，屬於 Rust 的框架檢查） | Python `test_desktop_protocol_contract.py` 的 `originCases` 參數化測試；Rust `shared_process_event_origin_fixtures`（C3-S4 保留或改寫為 Rust 自己的來源測試）；`backend.test.ts` 的未知 origin 拒絕。 |
| `protocol.test.ts`「shared message fixtures」中 49 個非 request 例 | TS 端的 result／event data 逐欄位驗證（U1 刪除） | 改為「shared request fixtures are validated against the contract params」，只跑 78 個 request 例；所有 message fixtures 仍由 Python 執行。envelope 層的拒絕另由「envelopes are parsed without validating result or event data」逐項覆蓋。 |
| `protocol.test.ts`「shared raw-line fixtures and line limit」（5 例＋行長） | `parseProtocolLine`（只給測試，S072） | Python `rawLines` 參數化測試；Rust 行長測試（C3-S4 保留）。 |
| `protocol.test.ts`「shared ordering and correlation traces」（60 例） | `ProtocolTraceValidator`（已改成直接的回聲比對） | 回聲相關案例移到 `backend.test.ts`：`turn-completed-rejects-mismatched-logical-id` → 「echo: session.turn success must carry the requested turnId」；`turn-failure-rejects-mismatched-logical-id`、`turn-failure-requires-lifecycle-details`、`turn-failure-safe-lifecycle-trace` → 「echo: turn failures compare error.details.turnId and require lifecycle details」（含 `extensions.apply`）；`session-stop-rejects-other-session`、`session-stop-rejects-other-turn`、`session-stop-*` 合法例 → 「echo: session.stop rejects another turn or session and accepts its own」。排序、post-terminal、event 關聯與 result data 的案例在 TS production 本來就不經過 trace validator（events 不進 `requestTracked`），由 Python 的 `traces` 參數化測試保留。 |
| `backend.test.ts`「backend client correlates results and applies method-specific success validation」的 `data: {}` 拒絕 | TS 對 `runtime.diagnostics` result data 的逐欄位驗證（U1 刪除） | 改名為「backend client correlates results by request ID」，改以不相符的 `requestId` 驗證拒絕。 |
| `backend.test.ts`「lifecycle commands validate start/restart snapshots…」中多一個鍵的 shutdown report 被拒絕 | Rust shutdown report 的逐鍵驗證（S090 刪除） | 同測試改名為「…return start/restart snapshots…」，改以非物件的 shutdown report 驗證拒絕仍有效。 |
| `backend.test.ts`「bridge events validate lifecycle payloads and process-event origins」中 `backend.ready` 來自 rust、`backend.crashed` 來自 python 被拒絕 | TS 端的 process event 來源檢查（已刪除） | 改寫為「bridge events parse lifecycle payloads and protocol envelopes from a known origin」：未知 origin、未知 process event 與非物件 snapshot 仍被拒絕；來源規則由 Python 與 Rust 測試保留。 |
| `trust.test.ts` 中 `acceptApprovalEvent(..., now, "other-turn")` 的斷言 | 只有測試傳的 `activeTurnId` 參數（S072 刪除） | 同測試其餘的 request 關聯與逾時斷言保留。 |
| `answer_stream.test.ts` 中 3 處 `reconciledTurnCount(...)` 斷言 | `Math.max` 包裝（S072 刪除） | 呼叫端直接 `Math.max`；三個測試的合併與 turn number 斷言保留。 |

## 7. 新增的回聲測試（`backend.test.ts`）

- (a)「echo: document.apply and approval.resolve accept success results without turnId」
- (b)「echo: session.stop rejects another turn or session and accepts its own」
- (c)「echo: session.select rejects a result for another session」（另含 `projectId` 不同）
- (d)「echo: session.create compares projectId only when the request carried it」
- (e)「echo: turn failures compare error.details.turnId and require lifecycle details」（`session.turn` 與 `extensions.apply`）
- 另有「echo: session.turn success must carry the requested turnId」。
- 缺少必填參數：`protocol.test.ts`「a request missing a required param is rejected before it is sent」與既有的 `backend.test.ts`「request builder…validates params」。

## 8. 檢查結果

- `npm test`：216 tests, 216 pass, 0 fail（數量下降來自上表退役的 fixture 子測試）。
- `npm run build`：通過（built in 670 ms）。
