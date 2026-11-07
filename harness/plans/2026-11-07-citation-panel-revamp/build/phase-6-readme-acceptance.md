# R6 更新 README 與最終驗收

- **後置條件**：
  - README 與實際行為一致。
  - 三套完整測試與建置都通過。
  - build-log 記錄了每個目標的觀察證據。
  - 最終彙報已交付。
- **涵蓋**：G9、G8。決策 D13。
- **相依**：R5。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| R6-S1 | **更新 README**。<br>1. `/README.md`：<br>&nbsp;&nbsp;• 「引用面板」一段：刪除 Insert；說明 Remove 只在未引用區、會先確認，以及「其他文件不檢查」；說明預設收合的摘要列與自動展開；保留 `[@` 補全的說明。<br>&nbsp;&nbsp;• 「格式與匯出」一段：說明 `Export ▾` 的三個選項與輸出檔名，包括 `<檔名>.bime.docx` 和 bime_word 的三份報告；說明系上格式要先存檔，並且不使用 Style；說明 `.tex` 文件不提供匯出。<br>&nbsp;&nbsp;• 輸出位置表（約第 132 行）：刪除 `.bib`，加入 `.bime.docx` 與報告。<br>&nbsp;&nbsp;• 加上編輯器字體縮放的快捷鍵。<br>&nbsp;&nbsp;• 在說明 vendor 工具的地方（目前約第 37 行提到 web-search-mcp），加入 bime_word：來源 zip、版本 1.1.5、SHA-256、依賴 python-docx 與 lxml、更新方式（重新 vendor 並以 manifest 檢查）。<br>2. `app/skills/citation/README.md` 第 41、55 行：刪除 `export_bib` 與 BibTeX 匯出。<br>3. 以 `grep -rn -i "insert\|bibtex\|\.bib\b\|export" README.md app/README.md app/skills/citation/README.md` 檢查其餘描述，只修改與這次改版有關、已經過時的句子。 | 逐條對照 GOALS 的 G1–G7，確認 README 的描述與實際程式行為一致，記錄在 build-log；README 中的相對連結都指向存在的檔案；`git diff --check` 通過 |
| R6-S2 | **最終驗收**。<br>1. 執行完整 pytest（沙箱外）、`npm test`、`npm run build`、`cargo test --locked`（沙箱外），與 R1-S2 的基線比較。<br>2. 重跑 G1、G3 的負面 `grep`。<br>3. 用 R4-S3 的方式，以 proposal 副本重跑一次系上格式匯出，確認最終程式碼仍能轉出。<br>4. 在 build-log 中逐一記錄 G1–G9 的觀察證據，把所有階段標為 Complete。如果有任何一項沒有證據，該階段保持 In progress 或 Blocked，並寫明原因。 | 全部通過，或者每個失敗都有記錄與原因；與基線相比，沒有未解釋的新失敗；`/home/minervamuses/論文/` 的 `git status` 和 R1 時相同 |

每個步驟各自 commit，例如 `docs(readme): describe the revised citation panel [R6-S1]`。

## 最終彙報（給使用者）

依序寫明以下內容：

1. 實際完成的改變與 commit 範圍；三套測試的數字，以及和基線的差異。
2. **手動 GUI 檢查清單**，請使用者在 GUI 中自己確認：
   - 開啟 `proposal.md` 時面板是收合的。
   - 展開後本文引用沒有 Insert，也沒有 Remove。
   - 未引用區的 Remove 會先確認，取消後沒有任何變化。
   - `Export ▾` 有三個選項。
   - 開啟 `.tex` 文件時沒有 Export。
   - 有未存檔的修改時，系上格式匯出會被拒絕。
   - 匯出後 `proposal.bime.docx` 與報告出現在原稿旁。
   - 輸入 `[@notakey` 並存檔後，摘要列變紅並自動展開。
   - Ctrl+= / Ctrl+− / Ctrl+0 能縮放編輯器字體；重開 GUI 後保留縮放的大小。
   - 面板文字的大小可以接受。
   - 保留的功能都還正常：Style 選單、Preview、verified／unverified 標籤、Line 跳轉、Verify and add、`[@` 補全。
3. 需要使用者決定或注意的事：
   - `/home/minervamuses/論文/references.json` 中被誤刪的 `yao2023react` 仍未還原（本計劃不寫入論文資料夾）。還原指令是 `git -C /home/minervamuses/論文 checkout -- references.json`。在還原之前，系上格式匯出會因為這個未知的 key 而停止。
   - 本計劃中可逆的假設 A1–A11，有任何一項需要改的話請告知。
   - `for_agents/` 可能已經過時，需要用 infrastructure skill 更新。
   - 已知的既有失敗，或無法驗證的項目。
