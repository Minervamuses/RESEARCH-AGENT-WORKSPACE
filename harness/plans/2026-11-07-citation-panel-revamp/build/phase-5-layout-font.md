# R5 面板收合與字體縮放

- **後置條件**：
  - 開啟文件時，面板只顯示一列摘要。
  - 有問題時，摘要列標紅並自動展開。
  - 編輯器字體預設 16px，可以縮放，並記住設定。
  - 面板內沒有小於 0.9rem 的文字。
- **涵蓋**：G6、G7。決策 D6、D7、D14；假設 A6、A7。
- **相依**：共同前提是 R1 完成。R5-S2（字體與縮放）在 R2-S1 完成後可獨立先做，不依賴 R2-S2／S3 或 R3／R4；R5-S1（摘要列）需要 R4-S2 的 Export 選單完成，不必等 R4-S3 真實案例。
- **完成判斷**：S1、S2 及其必要自動檢查都通過，R5 才能 Complete。只有 S2 完成而 S1 被封鎖時，保留 S2 的完成證據；不得因 R4 的局部問題重做已完成的字體修改。
- **保留不變**：verified／unverified 標籤（D9）、Preview 的內容（D8）、Style 選單，以及展開後各區塊的內容。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| R5-S1 | **收合摘要列**（前提：R4-S2 完成）。<br>1. 面板分成「摘要列」和「內容區」。摘要列包含：標題 `Citations`、`N cited · M problems`（文字可依 GUI 用語調整）、Style、Preview（只限 Markdown）、`Export ▾`、Refresh，以及展開／收合切換。<br>2. 預設收合，收合時不渲染內容區。內容區包括：書目路徑、通知、預覽、本文引用、Problems、Verify and add、未引用區。<br>3. 問題數大於 0 時，摘要列使用警示樣式。<br>4. 自動展開的規則寫成純函式（A7），條件是以下任一：開啟文件時就有問題；Refresh 後問題數從 0 變成大於 0；按下 Preview。<br>5. 展開後高度上限維持 40vh。<br>6. 書目錯誤或通知出現時，即使收合也必須看得到：顯示在摘要列下方，或觸發自動展開。 | `desktop/tests`：自動展開函式的各種情況（開啟時有或沒有問題、0→N、N→N、使用者手動收合後問題數不變時不自動展開、Preview）；摘要文字的格式化；本步相關的前端測試（依 PLANS 選檔）與 `npm run build` 通過 |
| R5-S2 | **字體與縮放**（前提：R2-S1 完成；可先於 R5-S1）。<br>1. 新增一個小模組，例如 `desktop/src/editorZoom.ts`，負責：預設 16、範圍 10–28、每次 ±1；從 `localStorage` 讀取並驗證（非數字或超出範圍時用 16）；寫入。所有存取都包在 try/catch 中，例外時回到 16，不讓 UI 出錯。<br>2. `DocumentEditor.tsx` 以這個模組的值初始化 `fontSize`，把既有固定 `lineHeight: 23` 改為 `lineHeight: 0`，讓 Monaco 依字級計算行高；並註冊 Monaco 命令：`CtrlCmd+Equal`（也接受 `CtrlCmd+Shift+Equal` 與數字鍵盤的 `+`）、`CtrlCmd+Minus`、`CtrlCmd+Digit0`。觸發時以 `updateOptions({fontSize, lineHeight: 0})` 更新並儲存，重開後也採相同的自動行高設定。<br>3. 確認 Tauri 的 webview 沒有啟用自己的縮放快捷鍵，以免重複縮放，並記錄 `tauri.conf.json` 的設定。<br>4. `styles.css`：所有 `.citation-*` 規則與面板內元素的 `font-size` 都不小於 `.9rem`，包括 `.citation-badge`；必要時調整 padding，讓摘要列在窄視窗中也能換行。 | `desktop/tests`：縮放模組的預設值、上下限、遞增與遞減、無效的儲存值、`localStorage` 拋出例外時回到 16；行高只做程式碼核對：確認 `monaco.editor.create` 的初始化選項，以及縮放時的 `updateOptions` 都明確傳入 `lineHeight: 0`，並在 build-log 記錄檔案／行號；不要求 Node 測試量測實際畫面或行高；28px 多行文字是否重疊列入使用者的 GUI 清單；`grep -n "font-size" app/desktop/src/styles.css` 中屬於面板的規則全部 ≥ .9rem，結果記錄在 build-log；本步相關的前端測試（依 PLANS 選檔）與 `npm run build` 通過 |

每個步驟各自 commit。

## 失敗與恢復

- 如果 Monaco 的命令和 Tauri 或作業系統的快捷鍵衝突，改用編輯器容器的 keydown 處理器，並記錄原因；不要改用其他按鍵，因為按鍵是使用者決定的。
- 依 D14，視窗中的實際效果由使用者本人驗收；R5 完成實作與必要自動檢查，R6 交付手動清單即可，不等待 GUI 操作，也不宣稱已實測。
