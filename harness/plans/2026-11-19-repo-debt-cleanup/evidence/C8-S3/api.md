# C8-S3 api.ts 證據

## 1. api.ts 的形狀（`app/desktop/src/api.ts`）

- `createApi(backend, nativeInvoke)` 回傳一個物件，每個 UI 用到的 protocol 方法一個型別化函式；模組底部 `export const api` 是接上真的 `createBackendClient` 與 Tauri `invoke` 的實例。測試用 `createApi` 注入假的 backend 與假的 native invoke。
- 參數型別取自 `MethodParams[M]`，回傳型別取自 `MethodResults[M]`。內部只有一個泛型 `tracked`／`call`，每個方法函式一行。
- 追蹤型（要先拿 `requestId`）：`documentApplyTracked`、`sessionTurnTracked`、`bibliographyAddTracked`，回傳 `{ requestId, result }`。
- 生命週期：`initialize`、`start`、`restart`、`shutdown`（轉接 backend client）。
- 原生 picker：`pickProject(initialPath)`、`pickDocument(rootPath)`，這是 `invoke<` 唯一的呼叫點（另有 backend.ts 的 transport）。
- `eventData(event, data)`：把 request event 的 `data` 轉成 `EventData[E]`（取代 App.tsx 的 `as unknown as ApprovalRequiredDto`）。
- `session.set_thinking` 在 contract 沒有 result schema（`MethodWithoutResultDto`）；`sessionSetThinking` 回傳 `SessionCreatedDto`，這個轉型寫在 api.ts 內並加註解。
- 回聲檢查：`verifyResultEcho` 從 backend.ts 搬進 api.ts（backend.ts 不再比對成功結果），仍用 protocol.ts 的 `echoedIdFields`（由 contract 推導），規則不變：欄位在 request 與 result schema 都有、這次 request 有帶、回應也有時才比對。錯誤型別與訊息不變（`BackendClientError`，`source: "protocol"`，訊息 `data.<field> must match params.<field>`）。失敗回應的 `error.details.turnId` 比對仍在 backend.ts 的 `normalizeBusinessError`（它屬於 transport 的錯誤解析，不是結果回聲）。
- `App.tsx` 不再 import `invoke`、`createBackendClient`；`CitationPanel` 的 `request` prop 改為 `api`（`Pick<Api, bibliography*>`）；`loadSelectedProjectHistory`、`fetchTranscriptPage`、`selectConversationWithPreview` 改為接收 api 函式（`Api["sessionList"]`、`Api["sessionTranscript"]`、`Pick<Api, "sessionSelect"|"sessionTranscript">`）。`documentContextPayload` 回傳 `DocumentContextDto`。

## 2. MethodParams 與 DTO 一致性測試

- `protocol.ts` 新增 `MethodParams`（25 個 contract 方法全部；無參數者為 `Record<string, never>`）。
- `tests/protocol_types.test.ts` 擴充：`MethodParams` 的鍵必須等於 contract 全部方法，每個 params DTO 以同一個 `compareObject` 與該方法的 `params` schema 比對。輸出：`protocol DTO check: 24 results, 25 params, 3 events`。
- 負向演練：在 `contract.json` 的 `session.rename.params` 暫時加入必填 `driftProbe`。
  - `npm test`：`pass 224 / fail 4`，其中 `TS protocol DTOs, method names, and event names follow contract.json` 失敗，訊息 `MethodParams["session.rename"].driftProbe: missing from the DTO`；另 3 個既有測試（shared request fixtures、缺必填參數、`session-rename-request`）也因 `params.driftProbe is required` 失敗。
  - 還原：`cp` 回備份，`git diff -- app/desktop/protocol/v1/contract.json` 為空；還原後 `npm test` 228 pass。

## 3. 移除的轉型與回聲檢查

| 項目 | 前 | 後 |
|---|---|---|
| `as unknown as` 在 App.tsx | 23 | 0 |
| 在 CitationPanel.tsx | 4 | 0 |
| 在 lib/sidebar.ts、lib/transcript.ts | 1、2 | 0 |
| 在 protocol.ts | 2 | 1（`CONTRACT`，JSON 模組型別被放寬，已加註解；`validateDocumentRange` 改為接受結構型別而移除） |
| `protocolMismatch(` 就地比對：App.tsx | 13 | 7 |
| lib/sidebar.ts、lib/transcript.ts | 1、2 | 0 |
| App.tsx 直接 `invoke<`（pick_*） | 2（另有 transport 包裝 1） | 0 |
| App.tsx 直接 `backendClient.*` | 約 30 行 | 0 |

已移除（由 api.ts 的通用回聲比對涵蓋；通用比對本來就在 backend client 內先於這些檢查執行，所以這些就地檢查在正式環境是死碼）：`session.rename`（projectId、sessionId）、`session.stop`（sessionId、turnId）、`session.create`（有帶才比 projectId）、`extensions.apply` 的 `turnId` 部分、`session.select`、`session.transcript`（兩處呼叫與 `fetchTranscriptPage` 的 `mismatchMessage` 參數）、`session.list` 的 projectId（sidebar 與載入更多）、`session.delete` 的 projectId／sessionId。

## 4. 保留的專屬檢查

移進 api.ts（比對對象是 request 自己的參數，行為相同）：
1. `sessionList`：request 有帶 `offset` 時，`data.offset` 必須相同，訊息 `The backend returned a mismatched conversation page.`（原本只有載入更多檢查；首頁載入送 `offset: 0`，後端原樣回傳，所以不改變行為）。
2. `sessionDelete`：`data.status === "deleted"`，訊息 `The backend deleted a different conversation.`
3. `approvalResolve`：`data.approvalId === params.approvalId`，訊息 `The backend resolved a different approval request.`

順序差異：這三項原本在 `isCurrent()` 守衛之後才比較，現在在守衛之前就丟出。呼叫端的 `catch`／`finally` 都以 `isCurrent()` 或 `ownsOperation` 守衛，晚到的過期回應仍被靜默忽略。

留在 App.tsx（比對對象是目前畫面狀態或擁有者，不是 request 參數，所以不屬於回聲比對）：
- `receiveDocumentResult` 的 `path`／`rootPath`（對 captured 文件，且在過期檢查之後）。
- `document.open` 的 `rootPath` 對目前專案；`rootPath` 為 optional 的 DTO，因此改成先取出再比較，`undefined` 仍視為不符。baseline 的 `editorRevision` 由 `undefined` 變成 0，baseline 只讀 `sourceText`，沒有可見差異。
- 重新開啟專案的 `status／projectId／rootPath`（對 `project` 狀態）。
- `extensions.apply` 的 `sessionId` 對 `state.session`。
- `session.set_thinking`、`session.set_permission` 的 `sessionId` 與 generation（`reconcilePermissionAck`）。
- `session.turn` 結果與 reducer 的對應（`mismatched conversation result`）。

## 5. 測試退役與新增

- `tests/backend.test.ts`：5 個 `echo:` 成功結果測試（document.apply／approval.resolve、session.stop、session.select、session.create、session.turn）移到 `tests/api.test.ts`，同樣情境加上錯誤訊息比對；失敗回應回聲（`error.details.turnId`）測試留在 backend.test.ts。
- `tests/conversations.test.ts`：`loadSelectedProjectHistory` 測試中 `/different project/` 的斷言退役（改由 api.test.ts 的 `session.list` projectId 比對涵蓋）；其餘 fake request 以 `fakeApi` 包成 api 函式。
- `tests/citation_preview.test.ts`：元件渲染測試的 `request` prop 改為 `api` 假物件。
- 新增 `tests/api.test.ts`（9 個）：符合的結果被接受並以正確方法與參數送出；他人的 session／project 被拒（相同錯誤型別與訊息）；stop／turn／create／extensions.apply 的比對；document.apply 與 approval.resolve 成功結果沒有 turnId 仍接受；offset、deleted、approvalId 專屬檢查；set_thinking；兩個原生 picker。
- `npm test`：228 通過（基準 224：+9 api、−5 backend echo）。`npm run build`（含 `tsc` 與 `tsc -p tsconfig.test.json`）通過。

## 6. grep

`grep -rn "invoke(\|invoke<\|backendClient\.\|\.request(\|as unknown as" app/desktop/src` 的命中：
- `api.ts`、`backend.ts`：預期。
- `protocol.ts:64`：`const CONTRACT = contract as unknown as ProtocolContract;`，JSON 模組型別放寬，唯一例外，已在原始碼註解。
- `App.tsx` 等其他檔案：0。

`listen<`（事件訂閱）仍在 App.tsx，依任務說明保留，不在 grep 範圍。

## 7. 要加入 GUI 清單的流程（呼叫已移到 api.ts）

啟動與重啟後的 backend 連線、診斷；專案選擇（Browse 的原生 picker、inspect、open、initialize）與重新開啟專案；對話建立／選擇（含預覽）／改名／刪除／載入更多／載入較舊訊息；送出、Stop、Retry Stop；核准的允許與拒絕（含文件核准、`bibliography.add` 的核准）；文件開啟（原生 picker）、存檔、套用、undo；引用面板的 inspect、render、export、set_style、remove、add；thinking 與 permission 控制；擴充預覽與套用。
