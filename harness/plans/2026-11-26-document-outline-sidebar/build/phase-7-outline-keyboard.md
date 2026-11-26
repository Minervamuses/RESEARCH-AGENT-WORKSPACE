# D7 P1：大綱鍵盤操作

- **後置條件**：大綱可以只用鍵盤瀏覽、收合與跳轉，且按鍵只在大綱內生效。
- **涵蓋**：G8。
- **相依**：D5。
- **輸入**：GOALS G8；INV-022（輸入法 Enter 不送出、Composer 的 Enter 行為）；D4 的 `OutlineView`。

## 範圍

- 修改 `src/components/OutlineView.tsx` 與 `src/styles/outline.css`；鍵盤導覽邏輯抽成純函式（可放 `src/lib/outline/keyboard.ts`）並測試。
- 不加全域快捷鍵；不改編輯器或 Composer 的按鍵處理。

## 行為規格

- 樹狀清單採 roving tabindex：整棵樹只有一個節點 `tabIndex=0`，`role="tree"`／`treeitem`，有 `aria-expanded`、`aria-level`。
- 上／下：移到上一個／下一個可見節點；Home／End：第一個／最後一個可見節點。
- 右：收合中→展開；已展開→移到第一個子節點；沒有子節點→不動。左：已展開→收合；否則移到父節點。
- Enter：跳轉（同滑鼠點擊，A2 焦點移到編輯器）。
- 輸入法組字中（`event.nativeEvent.isComposing` 或 `keyCode === 229`）不處理任何鍵。
- 按鍵處理只綁在大綱元素上，`preventDefault` 只用於上述已處理的鍵。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| D7-S1 | 純函式：給定可見節點清單、收合狀態、目前焦點與按鍵，回傳新焦點與收合變更。 | 測試：每個按鍵在葉節點、已展開、收合、第一個、最後一個節點的結果；組字中不處理 |
| D7-S2 | 接到 `OutlineView`：roving tabindex、`aria` 屬性、焦點樣式（可見的 focus ring）。 | SSR 測試：只有一個 `tabIndex=0`、`role`／`aria-expanded`／`aria-level` 正確。`npm test`、`npm run build` 通過。實際鍵盤操作列入 D8 手動清單 |

## 交付給後續階段

鍵盤操作完成的證據。
