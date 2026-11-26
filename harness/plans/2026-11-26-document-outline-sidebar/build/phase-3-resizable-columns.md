# D3 可拖曳欄寬

- **後置條件**：「側欄｜主區」與「文件｜對話」兩條直立邊界可用滑鼠拖曳與鍵盤調整，雙擊恢復預設，寬度在重新開啟後保留；窄版面時不出現對應邊界；沒有上下方向的拖曳。
- **涵蓋**：G6。
- **相依**：D1（與 D2 無關，可先做）。
- **輸入**：GOALS U3、U5、A6–A8；PLANS「架構」第 6、7 點；`src/editorZoom.ts` 的儲存模式；PLANS「基線／版面」。

## 範圍

- 新增 `src/lib/layout.ts`（讀寫、夾限、預設值）、`src/components/ColumnResizer.tsx`、`src/styles/layout.css`、`tests/layout.test.ts`；修改 `src/App.tsx`（放置兩個邊界、提供 CSS 變數）、`src/styles.css` 的 `.app-shell`、`src/styles/document.css` 的 `.writing-workspace`、`src/main.tsx`（在 `document.css` 後 import `layout.css`）、`tests/styles.test.ts`。
- **格線只用一種做法**：D3 把 `.app-shell` 改成「側欄｜邊界｜主區」三欄、`.writing-workspace` 改成「文件｜邊界｜對話」三欄；圖示列那一欄在 D4 才加入。D3 結束時版面不能有空欄或錯位。
- `grid-template-columns` 只在原檔修改（`styles.css`、`document.css`），以 `var(--…, 現在的預設值)` 帶入；`.app-shell` 的直接子元素明確指定 `grid-column`（含 `.skip-link` 之外的每一個）。`layout.css` 只放 `ColumnResizer` 的元件樣式與針對新元素的 `@media`，不得重新定義兩個容器的欄（PLANS「架構」第 7 點）。
- 不改 `responsive.css` 與 `document.css` 既有的窄版單欄規則；將側欄與主區的桌面欄位定位限定在 > 760 px，文件與對話的並排定位限定在 > 1050 px；堆疊時可見內容都排在第一欄。

## 行為規格

- **側欄邊界**：寬度夾在 160–420 px（A7）。拖曳或鍵盤調整後記住像素值。
- **文件｜對話邊界**：記住文件欄所佔比例（例如 0.2–0.8 的分數），兩欄各至少 300 px（A7）；視窗變寬變窄時按比例分配，仍受最小寬度限制。
- **依視窗夾限**（A7）：任何 ≥ 720 px 的視窗寬度、任何儲存值組合都不得出現水平捲軸或欄位重疊。> 1050 px 時側欄實際寬度不超過「視窗寬度 − 圖示列 − 兩條邊界 − 600 px」；761–1050 px 時不超過「視窗寬度 − 圖示列 − 邊界 − 300 px」。以 CSS `min()` 表達，儲存值不改寫；拖曳時的夾限函式以容器目前寬度計算，與 CSS 一致。
- **預設**：沒有儲存值時，格線與現在完全相同（側欄 `minmax(10.15rem, 11.9rem)`、文件 `1.05fr`、對話 `1fr`）。雙擊邊界：清除該邊界的儲存值，回到預設。
- **拖曳**：以 pointer events 與 `setPointerCapture`；拖曳期間直接改 CSS 變數（不經 React state），`pointerup`／`pointercancel` 才寫入狀態與儲存。拖曳時避免選取文字（例如暫時加 `user-select: none` 的 class），放開後移除。Monaco 的 `automaticLayout: true` 會自己重新排版。
- **鍵盤**：邊界可取得焦點（`tabIndex=0`、`role="separator"`、`aria-orientation="vertical"`、`aria-valuenow/min/max`、`aria-label`），左右鍵每次 16 px，Home／End 到最小／最大，Enter 不做事。
- **儲存**：鍵名用 `research-agent.` 前綴；讀到不合法或超出範圍的值時用預設；`localStorage` 不存在或丟例外時照常運作，只是不記住。
- **斷點**（A8）：> 1050 px 兩條都出現；761–1050 px 只有側欄邊界（文件與對話上下堆疊）；≤ 760 px 都隱藏。
- **對話框**：刪除對話框開啟時（`deleteDialog !== null`）邊界跟側欄一樣 `inert`。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| D3-S1 | `src/lib/layout.ts` 與 `tests/layout.test.ts`：讀寫、夾限、比例換算、依容器寬度夾限、預設、儲存失敗。 | 測試：合法值往返、超界值夾限或回預設、非數字回預設、`getItem`／`setItem` 丟例外時不拋出、清除後回預設、最小寬度與比例的換算邊界；**儲存 420 px 側欄與 0.8 比例後，以 1051 px 與 800 px 容器計算的實際寬度加總不超過容器寬度，且文件／對話欄 ≥ 300 px** |
| D3-S2 | `ColumnResizer` 與 `layout.css`；在 `App.tsx` 放置兩個邊界並套用 CSS 變數；修改兩處格線（含子元素的明確 `grid-column`）；`main.tsx` import；擴充 `tests/styles.test.ts`。 | `npm test`：SSR 渲染 `ColumnResizer` 有正確的 role／aria 屬性；`styles.test.ts` 斷言 `main.tsx` 在 `document.css` 之後 import `layout.css`、`:root` 斷言仍通過、`layout.css` 沒有 `.app-shell` 或 `.writing-workspace` 的 `grid-template-columns`、兩個單欄斷點均保有單欄規則，且桌面子元素的多欄定位只在相應寬度生效。另以讀 CSS 文字的測試確認變數的預設值與現在的欄寬相同。`npm run build` 通過 |
| D3-S3 | 鍵盤調整、雙擊重設、拖曳中 class 的移除、`pointercancel` 處理；把指標事件的計算抽成純函式（起點寬度＋位移 → 夾限後寬度）以便測試。 | 純函式測試：位移超出範圍時夾限、比例邊界；SSR 測試鍵盤屬性。GUI 實際拖曳列入 D8 手動清單 |

## 交付給後續階段

`ColumnResizer` 元件與寬度變數；`.app-shell` 新格線（D4 加圖示列時沿用）。
