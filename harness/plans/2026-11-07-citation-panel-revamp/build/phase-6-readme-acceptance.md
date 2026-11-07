# R6 更新 README 與最終驗收

- **後置條件**：
  - README 與實際行為一致。
  - 三套完整測試與建置都通過。
  - build-log 記錄每個目標的自動檢查／程式碼證據，另列交由使用者操作的 GUI 項目；不以尚未回報的 GUI 結果阻塞代理交付。
  - 最終彙報已交付。
- **涵蓋**：G9、G8，以及 G1–G8 的 GUI 清單交接。決策 D13、D14。
- **相依**：R4、R5 全部完成。R5 的獨立步驟先完成，不會解除 R4-S3 真實案例對最終驗收的阻塞。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| R6-S1 | **更新 README**。<br>1. `/README.md`：<br>&nbsp;&nbsp;• 「引用面板」一段：刪除 Insert；說明 Remove 只在未引用區、會先確認，以及「其他文件不檢查」；說明預設收合的摘要列與自動展開；保留 `[@` 補全的說明。<br>&nbsp;&nbsp;• 「格式與匯出」一段：說明 `Export ▾` 的三個選項與輸出檔名，包括 `<檔名>.bime.docx` 和 bime_word 的三份報告；說明系上格式要先存檔，並且不使用 Style；說明 `.tex` 文件不提供匯出。<br>&nbsp;&nbsp;• 輸出位置表（約第 132 行）：刪除 `.bib`，加入 `.bime.docx` 與報告。<br>&nbsp;&nbsp;• 加上編輯器字體縮放的快捷鍵。<br>&nbsp;&nbsp;• 在說明 vendor 工具的地方（目前約第 37 行提到 web-search-mcp），加入 bime_word：來源 zip、版本 1.1.5、SHA-256、依賴 python-docx 與 lxml、更新方式（重新 vendor 並以 manifest 檢查）。<br>2. `app/skills/citation/README.md` 第 41、55 行：刪除 `export_bib` 與 BibTeX 匯出。<br>3. 以 `grep -rn -i "insert\|bibtex\|\.bib\b\|export" README.md app/README.md app/skills/citation/README.md` 檢查其餘描述，只修改與這次改版有關、已經過時的句子。 | 逐條對照 GOALS 的 G1–G7，確認 README 的描述與實際程式行為一致，記錄在 build-log；README 中的相對連結都指向存在的檔案；`git diff --check` 通過 |
| R6-S2 | **代理最終驗收與交接**。<br>1. 各執行一次完整 pytest、`npm test`、`npm run build`、完整 `cargo test --locked`（遵守 PLANS 的環境與成本限制），與 R1-S2 可用的歷史／局部證據比較，不把未知基線寫成已通過。<br>2. 核對 G1 的移除結果與 R2-S3 限定範圍的 G3 檢查，包含必須保留的 BibTeX 功能；不要恢復全域「bib 零命中」搜尋。<br>3. R4-S3 的程式、vendor、輸入與環境未改變時沿用其真實案例證據；有相關變更才以同一正向副本重跑必要案例，不重做無關驗證。<br>4. 在 build-log 記錄 G1–G9 的代理證據與手動 GUI 清單。必要自動檢查、真實案例及其餘代理工作全部通過後標記階段 Complete，GUI 操作另記「由使用者驗收，尚無結果」，不等待結果。 | 必要自動檢查全部通過、G5 的真實 proposal 證據有效；既有失敗也不能只靠解釋就算通過，未解決時 G8／R6 保持未完成並彙報，不順便修復無關問題。`/home/minervamuses/論文/` 的 `git status` 和 R1 相同。GUI 尚未回報不阻塞代理交付，也不冒充 GUI 驗收成功 |

每個步驟各自 commit，例如 `docs(readme): describe the revised citation panel [R6-S1]`。

## 最終彙報（給使用者）

依序寫明以下內容：

1. 實際完成的改變與 commit 範圍；三套測試的數字，以及和基線的差異。
2. **手動 GUI 檢查清單**，依 D14 交由使用者本人於交付後操作；代理不等待此驗收，也不把下列項目寫成已實測：
   - 開啟沒有 Problems 的 `proposal.md` 副本時面板收合；若開啟時已有 Problems，應自動展開。
   - 展開後本文引用沒有 Insert，也沒有 Remove。
   - 未引用區的 Remove 會先確認，取消後沒有任何變化。
   - `Export ▾` 有三個選項。
   - 開啟 `.tex` 文件時沒有 Export。
   - 有未存檔的修改時，系上格式匯出會被拒絕。
   - 匯出後 `proposal.bime.docx` 與報告出現在原稿旁。
   - 輸入 `[@notakey` 並存檔後，摘要列變紅並自動展開。
   - Ctrl+= / Ctrl+− / Ctrl+0 能縮放編輯器字體；重開 GUI 後保留縮放的大小；放大至 28px 時，多行中英文不重疊。
   - 面板文字的大小可以接受。
   - 保留的功能都還正常：Style 選單、Preview、verified／unverified 標籤、Line 跳轉、Verify and add、`[@` 補全。
3. 需要使用者決定或注意的事：
   - `/home/minervamuses/論文/references.json` 中被誤刪的 `yao2023react` 仍未還原（本計劃不寫入論文資料夾）。還原指令是 `git -C /home/minervamuses/論文 checkout -- references.json`。在還原之前，系上格式匯出會因為這個未知的 key 而停止。
   - 本計劃中可逆的假設 A1–A11，有任何一項需要改的話請告知。
   - `for_agents/` 可能已經過時，需要用 infrastructure skill 更新。
   - 已知的既有失敗，或無法驗證的項目。
