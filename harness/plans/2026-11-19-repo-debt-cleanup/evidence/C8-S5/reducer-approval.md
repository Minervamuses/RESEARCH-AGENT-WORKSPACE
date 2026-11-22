# C8-S5 對話 reducer 與核准擁有者（S079、S080）

## 一、S079：reducer 只算一次

**之前**：`applyConversation` 先手動跑 `conversationReducer(conversationRef.current, action)` 更新 ref，再 `conversationDispatch(action)`，`useReducer` 又跑一次同一個 reducer。另有 effect `conversationRef.current = conversation` 回補 ref。

**之後**：`conversation` 改為 `useState`；`src/lib/reducerOnce.ts` 的 `applyReducerOnce(reducer, ref, publish, action)` 只呼叫 reducer 一次，結果同時寫入 ref 與 `setConversation`；reducer 回傳同一個物件（被忽略的 action）時不 publish。ref 的回補 effect 已刪除（ref 是唯一寫入點，與 state 同步）。`applyConversation` 簽名與回傳值不變。

## 二、S080：核准擁有者模組

**之前**：approval 用 2 個 state（`pendingApproval`、`approvalResolving`）、3 個 ref（`pendingApprovalRef`、`approvalResolvingRef`、`approvalOwnerRef`）加 `citationRequestRef`，並有 10 處各自手寫的清除區塊（C8-S1 行號）：1230、1251、1363、1378、1432、1722、2051、2083、2349、2389；只有 3 處（document finally、citation finally、resolve finally）同時釋放 owner。另有 2 份各自的 `approval.required` 接受程式（citation 路徑、turn/document 路徑）。

**之後**：`src/lib/approvalOwner.ts`（純函式，不依賴 React）。React 端只有 `approval` 一個 state、`approvalRef` 一個 ref、`commitApproval`（寫 ref + setState，狀態未變則不動）與 `acceptApproval`（呼叫模組後重設 `frameOwnerRef`）。

### 模組 API（`ApprovalOwnerState<Owner>`：`pending`、`resolving`、`owner`、`documentRequestId`、`citationRequestId`）

| 函式 | 用途 |
|---|---|
| `registerApprovalRequest(state, "document"｜"citation", id)` | 登記可能提出核准的 request（發出 `bibliography.add`、開始 document 操作） |
| `finishApprovalRequest(state, kind, id)` | request 結束：忘記該 id；若 pending 由它提出就關閉並釋放 owner |
| `forgetApprovalRequest(state, kind)` | 只忘記登記（`invalidateOperations`，不動 pending） |
| `dropApprovalOwner(state)` | 只釋放 owner（`invalidateOperations`） |
| `receiveApprovalEvent(state, input)` | 決定是否接受 `approval.required`：已有 pending 則不接受；預期 request id 為 citation → document → 回合（呼叫端傳入 `turnRequestId`）；其餘判斷沿用 `acceptApprovalEvent`；接受時設定 pending 與 owner |
| `clearStaleApproval(state, turnRequestId)` | 過期清除：沒有任何存活的擁有者（回合、document、citation）才清除；沿用 `approvalHasLiveOwner` |
| `approvalToResolve(state, stopPending, expectedId?)` | Deny/Approve 能否進行：需 pending、owner、非 resolving、無 Stop、id 相符 |
| `beginApprovalResolve(state)` | 設 `resolving` |
| `clearApproval(state, dropOwner = false)` | **唯一的關閉實作**：pending 與 resolving 歸零，可選擇釋放 owner |

### 刻意保留的行為差異（非遺漏）

C8-S1 觀察到 10 處清除中只有 3 處釋放 owner。這一步**不統一**：`clearApproval` 以 `dropOwner` 參數保留原行為。原因：對話框卸載時 `returnApprovalFocus` 以 `owner !== null` 決定是否把焦點還給輸入框；其他 7 處（backend crash、`clearTransientUi`、`resetStaleHistory`、開啟專案、回合成功、回合失敗、過期效果）保留 owner，所以焦點照舊會還給輸入框。統一成都釋放會讓這 7 條路徑失去焦點歸還，屬行為改變，不在本步範圍。

其他對應：`invalidateOperations` 原本只清 `approvalOwnerRef` 與 `documentRequestRef`，現在對應 `dropApprovalOwner` + `forgetApprovalRequest("document")`（`documentRequestRef` 仍保留，因為它還裝 `turnId` 與 document context；登記的 id 與它在相同位置寫入/清除）。`citationRequestRef` 已刪除，由模組的 `citationRequestId` 取代。

## 三、清除位置對照（App.tsx 現行位置）

| 原清除點 | 現在 |
|---|---|
| backend.crashed／shutting_down 事件 | `clearApproval(…)`（保留 owner） |
| `clearTransientUi`、`resetStaleHistory`（2 處） | `clearApproval(…)` |
| 開啟專案重設 | `clearApproval(…)` |
| 回合成功、回合失敗（2 處） | `clearApproval(…)` |
| 過期清除 effect | `clearStaleApproval(…)` → 內部 `clearApproval` |
| document 操作 finally | `finishApprovalRequest(…, "document", id)` → 內部 `clearApproval(…, true)` |
| `bibliography.add` finally | `finishApprovalRequest(…, "citation", id)` → 內部 `clearApproval(…, true)` |
| `resolvePendingApproval` finally | `clearApproval(…, true)` |

## 四、測試對照

新增 `tests/approvalOwner.test.ts`（10 條），`tests/trust.test.ts` 刪 1 條。

| 需求 | 測試 |
|---|---|
| (a) 發出 `bibliography.add` 後 owner 已登記 | `bibliography.add approval: owner registered, accepted, kept while running, cleared once finished` 的 (a) 段 |
| (b) requestId 相符的 `approval.required` 被接受並成為 pending | 同一條 (b) 段 |
| (c) add request 進行中，過期清除不關對話框 | 同一條 (c) 段 |
| (d) add request 結束後，同一核准被判過期清除 | 同一條 (d) 段；另 `finishing the bibliography.add request closes the approval it raised and releases the owner` |
| (e) requestId 不相符不被接受 | `(e) approval.required with a non-matching requestId is not accepted`（含 parent 不符與無擁有者） |
| document request 擁有者流程 | `document request owner: accepted, kept while running, cleared when the operation finishes` |
| turn request 擁有者流程 | `turn request owner: accepted for the active turn only, stale once the turn ends` |
| 已有 pending 不再接受第二個 | `a second approval is ignored while one is already shown` |
| 過期事件仍被拒 | `an unexpired check still applies through the owner module` |
| resolve 守衛 | `resolve target requires owner, no resolve in flight, no Stop, and the expected id` |
| 唯一關閉實作 | `clearApproval is the single close: it always resets resolving and optionally releases the owner` |
| S079 reducer 只呼叫一次 | `a reducer runs exactly once per action and its single result feeds the ref and React state`（計數 reducer；含被忽略的 action 不 publish） |

## 五、測試退役紀錄

- `trust.test.ts`「App's stale-approval cleanup counts the bibliography.add request as an owner」（讀 `App.tsx` 原始碼）→ 它保護：(1) 過期清除把 `bibliography.add` request 視為擁有者；(2) 發出 `bibliography.add` 時登記擁有者；(3) listener 接受 `requestId` 等於該 add request 的 `approval.required`；(4) 舊的兩擁有者判斷不復活 → 留下的證據：`approvalOwner.test.ts` 的 (a)–(e) 流程測試（登記、接受、進行中不清、結束後清、不符不接受）；`trust.test.ts`「a pending approval stays while its turn, document or bibliography.add request is in flight」（`approvalHasLiveOwner` 單元）；舊的兩擁有者判斷已不存在於程式碼（`citationRequestRef` 已刪除，過期判斷只經 `clearStaleApproval`）。注意：App 端「listener 把事件交給模組」的接線本身沒有自動測試，列入 GUI 清單。

## 六、grep 證明

```
$ grep -rn "approvalResolvingRef\|pendingApprovalRef\|approvalOwnerRef\|setPendingApproval\|setApprovalResolving\|citationRequestRef" app/desktop/src
（無輸出）
$ grep -n "pending: null" -r app/desktop/src
lib/approvalOwner.ts:22:  initialApprovalOwnerState（初始值）
lib/approvalOwner.ts:75:  clearApproval 內的 { ...state, pending: null, resolving: false, owner: … }   ← 唯一清除實作
```
`App.tsx` 中對 `clearApproval(` 的呼叫只是呼叫端（7 處），沒有任何一處自行改寫 pending/resolving/owner。

## 七、指令與結果（app/desktop）

- `PATH=/home/minervamuses/miniconda3/envs/app/bin:$PATH npm_config_cache=$TMPDIR/npm-cache npm test`：237 tests、237 pass、0 fail（基準 228 = −1 + 10）。
- `npm run build`（`tsc --noEmit` + `tsc -p tsconfig.test.json` + `vite build`）：通過。

## 八、GUI 清單（使用者驗收）

1. 引用 Verify-and-add：核准框出現、Approve 後加入並關閉、Deny 後關閉；核准框開著期間 add request 不被誤判為過期。
2. 文件 apply 核准（回合提出與直接 document 操作）：Approve／Deny、結束後對話框關閉、焦點回輸入框。
3. 回合中的 bash／工具核准：出現、Approve／Deny、`expiresAt` 到期自動 Deny；回合結束／失敗後對話框消失。
4. 核准待處理時按 Stop：Stop 完成前不能 Approve／Deny，Stop 後對話框關閉。
5. 核准待處理時 backend 重啟或 crash：對話框消失；重啟後可正常開新回合；舊核准的事件不再套用。
6. 核准待處理時開啟/切換專案、刪除對話：對話框消失，無殘留 resolving 狀態。
7. 關閉核准框後焦點是否回到輸入框（保留 owner 的 7 條路徑與釋放 owner 的 3 條路徑行為與之前一致）。
8. 一般回合／Stop／刪除對話／專案開啟的 conversation 狀態（S079 改為單次 reducer）：草稿、引用、Stop、Retry 行為與之前一致。
