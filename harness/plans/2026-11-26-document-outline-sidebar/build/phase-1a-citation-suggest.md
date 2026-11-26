# D1A 修復既有缺陷：文件編輯器的引用補全清單

- **後置條件**：文件編輯器載入 Monaco 的補全清單控制器，Markdown 與 LaTeX 的引用補全清單會顯示；打一般文字不跳出字詞建議；建置通過。
- **涵蓋**：G11。
- **相依**：D1。與 D2、D3 互不相依，建議緊接 D1 做，讓 Markdown 補全不必等到 P1。
- **輸入**：PLANS「基線／編輯器」的既有缺陷說明；GOALS G11。

## 背景（撰寫時讀碼並經使用者實機確認）

`src/DocumentEditor.tsx` 只載入 `monaco-editor/editor/editor.api`、worker 與 markdown 語言定義。從這兩個入口追 import 圖（約 704 個檔案），完全沒有 `editor/contrib/` 底下的編輯器功能，包括補全清單 `suggestController`；`dist/assets/` 也找不到 `editor.contrib.suggestController`。程式第 190 行起註冊的引用候選提供者因此永遠沒有清單可以顯示。使用者 2026-11-26 在 GUI 確認：在文件編輯器打 `@`、`/` 都沒有任何清單，Ctrl+F 也沒反應。對話輸入框的 `@`／`/` 選單是 `Composer.tsx` 自己的 React 元件，不受影響。

本階段**只**補上補全清單。右鍵選單、剪貼簿、Ctrl+F 搜尋、懸停、摺疊等其他功能已在計劃外以 `src/monacoFeatures.ts` 載入（2026-11-27，見 GOALS「範圍外」）。`suggestController` 的 import **不要**放進該檔：該檔只收 Monaco 附 `.d.ts` 的 `monaco-editor/features/<名稱>/register` 入口，`tests/monacoFeatures.test.ts` 會逐一檢查清單與 `.d.ts`。Monaco 的 `features/suggest/register` 只載入 inline completions，不含 `suggestController`，不能拿來取代下面的深層 import。bundle 大小比較以含 `monacoFeatures.ts` 的建置為基準。

## 範圍

- 修改 `src/DocumentEditor.tsx`：在 `monaco.editor.create` 之前，與既有的動態 import 一起等待 `monaco-editor/editor/contrib/suggest/browser/suggestController`（只為了副作用註冊；套件 `exports` 的 `./*` 對應到 `./esm/vs/*.js`，不需新增依賴）。Markdown 與 LaTeX 共用。
- **型別宣告**：這個深層模組沒有 `.d.ts`，專案開了 `strict`，直接 import 會讓 `tsc` 報 TS7016、`npm run build` 失敗。新增一個本地宣告檔（例如 `src/monaco-contrib.d.ts`，內容 `declare module "monaco-editor/editor/contrib/suggest/browser/suggestController";`），確認 `tsconfig.json` 與 `tsconfig.test.json` 都涵蓋它。
- **編輯器選項**：`wordBasedSuggestions: "off"`（否則載入清單後，Monaco 既有的字詞建議會在打論文內文時不斷跳出）；`quickSuggestions: { other: "on", comments: "off", strings: "on" }`（Markdown 的 `[` 會自動補 `]`，`[@key]` 整段是 `string.link` token，預設 `strings: "off"` 會讓 Esc 後繼續打字不再跳出清單；唯一的建議來源是引用提供者，它在非引用位置回傳空清單，所以開啟是安全的）。把這組選項放在可單獨測試的函式或常數（例如與 `editorFontOptions` 同一處）。
- 不改 `src/citations.ts` 的 `completionPrefix` 與候選邏輯。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| D1A-S1 | 載入 `suggestController`、新增型別宣告、補全相關編輯器選項。 | `npm test`（含 `tests/citations.test.ts`）通過；新增測試斷言補全選項為 `wordBasedSuggestions: "off"`、`quickSuggestions.strings: "on"`、`comments: "off"`；`npm run build` 通過（沒有 TS7016）；`grep -c "editor.contrib.suggestController"` 在本次 `dist/assets/*.js` 至少一個檔案 > 0，記錄檔名與 bundle 大小變化 |
| D1A-S2 | 程式審查並記錄：動態 import 在 `create` 前完成；`disposed` 檢查仍在 `Promise.all` 之後；沒有新增 listener 需要釋放。 | build-log 記錄審查結果。實機行為列入 D8 手動清單（`.md` 的 `[@`、一般文字不跳建議、Esc 後重現、Ctrl+Space 手動叫出） |

每個步驟 commit。

## 交付給後續階段

可顯示的補全清單。D6 只需加 `latex` 語言，不再處理清單控制器。
