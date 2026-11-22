# C9-S4 測試改為行為斷言（S086–S088）

基準：C9-S3 之後的 HEAD `793c5c5`（256 pass）。結束：253 pass、0 fail；`npm run build` 通過。

## 一、原始碼比對測試 → 純函式

`editorZoom.test.ts` 的「Monaco derives the line height…」原本 `readFile("../src/DocumentEditor.tsx")` 比對 `lineHeight: 0` 次數與按鍵綁定的字串。改為：

- `src/editorZoom.ts` 新增 `editorFontOptions(fontSize)`（回 `{ fontSize, lineHeight: 0 }`）、`ZOOM_CHORDS`／`zoomKeybindings(step, KeyMod, KeyCode)`；`DocumentEditor.tsx` 的 `create()`、`updateOptions()` 與三個 `addAction` 改呼叫它們（邏輯與值不變，只是從內嵌改為函式）。
- 測試：`editorFontOptions` 在 10、16、28 三個字級都回 `lineHeight: 0`；`zoomKeybindings` 以假的 KeyMod／KeyCode 值檢查 in＝`Ctrl/Cmd+=`、`Ctrl/Cmd+Shift+=`、`Ctrl/Cmd+NumpadAdd`，out＝`-`／`NumpadSubtract`，reset＝`0`／`Numpad0`。

退役紀錄：

- `Monaco derives the line height… (readFile DocumentEditor.tsx)` → 縮放後 line height 由 Monaco 依字級推導、不得寫死數字或 `fontSize: 14`；按鍵綁定為 Ctrl/Cmd 加 `=`／`+`／`-`／`0` → `editorZoom.test.ts` 的 `editorFontOptions` 與 `zoomKeybindings` 兩個測試（行為斷言）；「create 與 updateOptions 各出現一次」這種原始碼出現次數的斷言已刪除，因為兩處都呼叫同一個函式，沒有第二個來源可以寫死 line height。

## 二、class name 斷言 → role／文字／aria

| 檔案 | 改前（釘住的 class） | 改後 |
|---|---|---|
| `citation_preview.test.ts` | `<button … class="link-button">Remove</button>`（含 disabled 版） | `<button type="button"[^>]*>Remove</button>`、`…disabled=""…` |
| 同上 | `<header class="citation-summary"><h3>Citations</h3>`、`class="citation-toggle" aria-expanded="false"` | `<h3>Citations</h3>`、`<button[^>]*aria-expanded="false"[^>]*>Expand ▾</button>` |
| 同上 | `!html.includes("citation-body")`、`!/verified\|citation-badge/` | 只留文字斷言：沒有 `Verify and add`；沒有 `verified` 文字 |
| 同上 | `<button type="button" class="safe-link">https://doi.org/…</button>` | `<button type="button"[^>]*>https://doi.org/…</button>` |
| `conversations.test.ts` | `<button … class="safe-link" …>Docs</button>` | `<button[^>]*>Docs</button>` |
| 同上（live turn） | `<div class="message user-message"><p class="message-label">You</p>` 等 3 條、`assistant-message`、`pending-turn` | `<p[^>]*>You</p>`、`<p[^>]*>Assistant · complete</p>`、`<p[^>]*>Local command output · complete</p>`；命令結果不含 `Assistant`；不含 `restored`、`pending` |
| 同上（pending turn） | `<article class="turn-group pending-turn">`、`<p class="message-label">You · pending</p>`、`inline-spinner` | `<article` 恰好 1 個、`<p[^>]*>You · pending</p>`、`<p[^>]*>Assistant · working</p><div[^>]*aria-label="Waiting for answer"` |
| 同上（restored tool） | `<details … class="tool-activity" …><summary` | `<details[^>]*><summary` |

這些只是移除 class 依賴；斷言的行為（Remove 按鈕的有無與 disabled、摺疊狀態、標籤文字與順序、spinner 的 aria-label、連結不輸出 `href`）完全保留，所以沒有被刪的行為。

## 三、三個大型合成資料測試 → 一個

`conversations.test.ts` 的 3 個 SafeContent 大集合測試（inline 70,000 個 `` `x` ``、140,000 個 list item、140,000 個 paragraph）、restored turn 的多 MB 答案測試，以及 `protocol.test.ts` 的「complete answer and transcript results have no client capacity rejection」，合併成 `conversations.test.ts` 的一個測試「content-sized inputs reach the parser and the renderers whole, from first marker to last」。輸入大小不變（750,000 個字元的答案、140,000 個子項），所以覆蓋的行為與輸入分區不變；少了 4 個測試（5 → 1）。

退役紀錄：

- `safe content preserves a large array of inline Markdown children` → 內容大小的 inline 集合以單一陣列傳入 createElement（不被展開成引數而超出上限）→ 合併測試的 inline 段（70,000 個 `<code>x</code>`）。
- `safe content preserves a large array of Markdown list items` → 同上，list item 集合與最後一項內容 → 合併測試的 list 段（長度與最後一項）。
- `safe content preserves a large array of Markdown paragraph blocks` → 同上，paragraph 集合 → 合併測試的 paragraph 段。
- `restored turns render a complete multi-megabyte answer from first marker to last` → 多 MB 答案完整渲染（首尾標記、引號與反斜線、`<script>` 被轉義）→ 合併測試的 RestoredTurn 段（斷言原樣保留）。
- `complete answer and transcript results have no client capacity rejection`（`protocol.test.ts`）→ 750,000 字元的完成答案不被 `parseProtocolMessage` 拒絕 → 合併測試的 parse 段（`assert.doesNotThrow`，同一份 payload）。

## 四、檢查

- 讀取 `src/*.tsx` 原始碼的測試：`grep -n "readFile\|readFileSync" tests/*.ts | grep "src/"` 只剩 `styles.test.ts:10` 讀 `../src/styles.css`；`.tsx` 為 **0**。
- `styles.test.ts` 讀的是 CSS 檔（S084，不納入本計劃），未修改並保留：它仍讀 `src/styles.css`，取第一個 `:root` 的 `font-size: clamp(…)`，這是 C9-S3 保留 `styles.css` 第一區段的原因。
- `grep -n "class=\|className" tests/*.ts`（排除 `styles.test.ts`）→ 0。
- `protocol_types.test.ts` 的 `readFileSync` 讀 `protocol/v1/contract.json`，不是 `src/*.tsx`。
