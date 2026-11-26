# D1 前置核對與基線

- **後置條件**：分支、HEAD、工作樹、工具與 PLANS「基線」列出的程式位置已核對；修改前的 `npm test` 與 `npm run build` 結果已記錄；本計劃檔已提交。
- **涵蓋**：G9（後續回歸以這裡的基線比較）。
- **相依**：無。
- **標準與政策**：[GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| D1-S1 | **唯讀核對**：<br>1. 分支是 `GUI`，記錄 HEAD；不是 `78cd9ac` 時列出中間的 commit，判斷是否影響基線。<br>2. 本計劃檔都已提交；沒有的話補一個 `docs(plan): …` commit（`build/` 用 `git add -f`）。<br>3. `git status` 中與本計劃無關的檔案只記錄、不動。<br>4. 用 `grep -n` 確認 PLANS「基線」每一項仍成立（行號可位移，程式碼必須還在），特別是：`.app-shell` 與 `.writing-workspace` 的 `grid-template-columns`、`main.tsx` 的 CSS import 順序、`updateDocument` 的四個呼叫處、`openDocument`、`publishSelection`、`scrollBeyondLastLine: false`、`.tex` 用 `plaintext`、補全的 `triggerCharacters`、`documentPositionAt` 的 BOM 處理、`editorZoom.ts` 的儲存模式。<br>5. `export PATH=/home/minervamuses/miniconda3/envs/app/bin:$PATH` 後 `node --version`、`npm --version` 可用。 | 每項指令與結果寫進 build-log。有不符時判斷影響哪些階段，修改那些階段檔並 commit 後再繼續 |
| D1-S2 | **修改前基線**：在 `app/desktop/` 跑 `npm test` 與 `npm run build`。記錄通過數、耗時與 `dist/assets/` 中 `index-*.js`、`editor.api-*.js` 的大小（撰寫時參考值：393 kB、2.70 MB）。不跑完整 pytest（D8 才跑）。 | 結果寫進 build-log。已存在的失敗列出測試名稱，不修無關問題；D8 仍要求全部通過 |

D1-S1、D1-S2 各自 commit（只提交 build-log 與必要時修改的計劃檔）。

## 交付給後續階段

已核對的程式位置、修改前的測試數與 bundle 大小、已知的既有失敗。
