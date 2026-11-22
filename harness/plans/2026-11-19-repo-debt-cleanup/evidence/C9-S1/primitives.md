# C9-S1 Modal 與 Menu 互動原語（S081、U22）

基準：C8-S7 之後的 HEAD `1bd53a3`。只抽出「相同」的互動，語意不同的部分留在呼叫端。

## 一、盤點：4 處 focus trap（實際有 5 個 dialog）

| dialog | 位置（C9-S1 後） | Esc | Tab | 初始焦點 | 焦點還原 | 其他關閉條件 |
|---|---|---|---|---|---|---|
| 刪除對話 | `App.tsx::DeleteConversationDialog` | 不忙才 `preventDefault` 並 `onCancel`；忙碌時不攔截 | 只在 `button:not(:disabled)` 內循環；無可用控制項時吞掉 Tab | Cancel 的 `autoFocus` | 在 `onCancel`：`scheduleOwnedFrame` 後焦點回對話選單的來源列 | 無（backdrop 不關閉） |
| 改名對話 | `App.tsx`（`ModalDialog as="form"`） | 不忙才關閉並焦點回來源列；忙碌時不攔截 | `input`＋`button`；無可用控制項時**不**吞 Tab | 輸入框 `autoFocus` 並全選 | 在 dismiss／Cancel：直接 `focus()` 來源列 | 表單 `submit` |
| 選專案 | `App.tsx`（`ModalDialog`） | 不忙才關閉；**不**還原焦點 | `input`＋`button`＋`select`；無可用控制項時不吞 Tab | 「Choose project folder…」`autoFocus` | 無 | Cancel |
| 核准 | `trust.tsx::ApprovalDialog` | **一律** `preventDefault`；`!resolving` 才 `onResolve(false)` | 只在 `button:not(:disabled)` 內循環；無控制項吞 Tab；**非 modal（文件／operation 核准）不攔 Tab** | Deny 的 `autoFocus` 加 effect `focus()` | effect cleanup 呼叫 `returnFocus`（由 `App` 的 `returnApprovalFocus` 決定） | backdrop `mousedown`（僅 modal 且 `!resolving`）＝拒絕 |

## 二、共用的原語

### `src/lib/interaction.ts`（純函式，`tests/interaction.test.ts` 7 個測試）

- `dialogKeyDecision(key, shiftKey, activeIndex, controlCount, policy)` → `{ preventDefault, dismiss, focus }`。`policy` 把上表的差異變成 4 個旗標：`dismissible`、`trapTab`、`blockEmptyTab`、`preventEscapeWhenBlocked`。
- `focusLeftContainer(container, next)`：blur 後焦點是否離開選單容器。
- `menuShouldClose(key, open, tabCloses)`：Esc（context menu 另含 Tab）且選單開著時關閉。
- `menuNextIndex(key, current, count, homeEnd)`：ArrowDown／ArrowUp 循環，`homeEnd` 啟用 Home／End；非導覽鍵回 `null`；沒有項目時回 -1（維持「導覽鍵被吞掉但沒有焦點可移」的原行為）。

### `src/components/Modal.tsx::ModalDialog`

backdrop、`role="dialog"`、`aria-modal`、`aria-labelledby`／`describedby`、Esc 與 Tab 迴圈（呼叫 `dialogKeyDecision`）。面板元素可選 `section`／`div`／`form`。**不含任何 hook**，所以 `DeleteConversationDialog(props)` 仍可直接呼叫做元素樹檢查。

### `src/hooks/useDisclosureMenu.ts`

`ThinkingControl` 與 `ExportMenu` 完全相同的部分：`open` state、trigger／menu ref、停用即關閉、開啟時聚焦 `initialFocus` 選擇器、blur 到外面關閉、Esc 關閉並聚焦 trigger。回傳 `containerProps`（`onBlur`、`onKeyDown`）直接 spread 到容器上。

## 三、保留在呼叫端的語意差異

- **dialog**：關閉條件（`!busy`、`workspaceBusy === null`、`!resolving`）、Esc 是否在忙碌時被吞（核准會，其餘不會）、空控制項是否吞 Tab（核准與刪除會，改名與選專案不會）、Tab 迴圈的選擇器（button／input／select）、焦點還原的位置與時機（刪除：`scheduleOwnedFrame`；改名：同步；核准：effect cleanup；選專案：無）、初始焦點（`autoFocus` 與 effect）、backdrop 是否關閉（只有核准）、非 modal 核准。這些都是 `ModalDialog` 的 props 或留在 dialog 元件內。
- **選單**：
  - `DocumentHeader`（原生 `<details>`）：Esc 一律攔截並聚焦 `summary`（不看是否開著）；選項被點擊時關閉並聚焦 `summary`；只共用 `focusLeftContainer`。沒有方向鍵。
  - 對話選單（右鍵、fixed 定位）：Esc **與 Tab** 關閉並還原焦點；backdrop click 關閉並還原焦點，backdrop 右鍵關閉但**不**還原；ArrowDown／Up 只走啟用的按鈕，**沒有** Home／End；用 `menuShouldClose(…, tabCloses=true)` 與 `menuNextIndex(…, homeEnd=false)`。
  - `ThinkingControl`：用 `useDisclosureMenu`；另有 trigger 上的 ArrowDown 開啟、選單內 Home／End（`menuNextIndex(…, true)`）、開啟時聚焦已選項。
  - `ExportMenu`：用 `useDisclosureMenu`；開啟時聚焦第一個按鈕；沒有方向鍵。

## 四、class 改名

- `approval-backdrop` → `modal-backdrop`、`approval-dialog` → `modal-dialog`（`styles.css` 3 條選擇器加 `.document-approval-backdrop .modal-dialog` 1 條；宣告與值不變）。核准的非 modal 變體仍加 `document-approval-backdrop`。
- 未改（不在本列範圍）：`approval-context` 仍被選專案對話借用、`file-open-dialog` 其實只用於改名、`extension-error` 用於非擴充錯誤（C9-S3）。

## 五、測試

- 新增 `tests/interaction.test.ts`（+7）：Tab 往返與 Shift+Tab、空控制項、非 modal、Esc 的三種政策、選單關閉鍵、方向鍵循環與 Home／End、blur 判斷。
- 改寫 1 個：`conversations.test.ts`「conversation deletion confirms its scope…」。刪除對話的面板現在由 `ModalDialog` 包裝，元素樹少一層 `<section>`，所以 `elementChildren(dialog)[0]` 再取子節點改為直接 `elementChildren(dialog).at(-1)`。被改的測試 → 它保護的行為（刪除對話的範圍文字、Cancel 不確認、忙碌時兩顆按鈕 disabled、錯誤時的 Retry 文字）→ 同一測試的其餘斷言不變，行為斷言一條未刪。
- 核准對話的 `trust.test.ts` 靜態渲染測試（`role="dialog"`、`aria-modal`、按鈕數與 disabled 數）未改，通過。

## 六、檢查

- `npm test`：254 pass（247＋7）、0 fail。`npm run build`：通過。

## 七、GUI 清單（需人工；jsdom 沒有，焦點與 Tab 行為只能在 WebView 看）

dialog（逐一：Tab 循環、Shift+Tab 反向、Esc、焦點還原）：
1. 刪除對話：右鍵對話 → Delete；Tab／Shift+Tab 只在兩顆按鈕間循環；Cancel 已有焦點；Esc 關閉且焦點回該列；刪除進行中 Esc 無效。
2. 改名對話：輸入框已全選；Tab 在輸入框、Save、Cancel 間循環；Esc 關閉、焦點回該列；儲存中 Esc 無效；IME 組字時 Enter 不送出。
3. 選專案：Tab 在按鈕／輸入／radio 之外的 select／checkbox 間循環（含展開候選後）；Esc 關閉（焦點不特別還原）；忙碌時 Esc 無效。
4. Bash 核准（modal）：Deny 先有焦點；Tab 只在 Deny／Approve／Stop 間循環；Esc 與點 backdrop 都等於拒絕；處理中 Esc 不關閉也不洩漏到後面。
5. 文件／operation 核准（非 modal）：Tab 可離開對話回到編輯器；Esc 等於拒絕；backdrop 點擊不拒絕。

選單（逐一：Esc、點外部、鍵盤）：
6. 文件 `•••`：Esc 關閉並聚焦 summary；點外部關閉；Tab 離開關閉；點項目後關閉並回到 summary。
7. 對話選單（右鍵）：Esc 與 Tab 關閉並焦點回該列；方向鍵循環；點 backdrop 關閉並還原焦點；右鍵 backdrop 關閉。
8. Thinking：ArrowDown 開啟並聚焦已選項；方向鍵／Home／End；Esc 關閉並聚焦 trigger；點外部關閉；選項後焦點回 trigger；turn 進行中停用時自動關閉。
9. Export：開啟後聚焦第一項；Esc 關閉並聚焦 trigger；點外部關閉；選項後焦點回 trigger。
