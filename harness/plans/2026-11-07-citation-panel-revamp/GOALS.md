# 引用面板改版：目標與決策

## 目的

桌面 GUI 編輯器下方的 Citations 面板目前有四個問題：

- 多餘的按鈕（Insert）容易誤用。
- Remove 緊貼在 Insert 旁邊，2026-11-07 使用者想撤銷 Insert 時按了 Remove，結果把 `yao2023react` 從 `references.json` 刪除。
- 面板佔用太多空間，字也太小。
- 匯出按鈕過多：三個，其中 BibTeX 用不到。

本計劃依使用者在 2026-11-07 對話中做出的決定改版面板，加入「系上格式 Word」匯出（由 bime_word 產生），最後更新 README。

## 目標

| ID | 必須達成的結果 | 成功的觀察方式 |
|---|---|---|
| G1 | 面板上不再有任何「插入引用」按鈕 | 本文引用列與「Verify and add」成功訊息中都沒有 Insert／Insert at cursor；`citationInsertion`、`insertIntoSnapshot` 與只供它們使用的游標管線已刪除；編輯器輸入 `[@` 仍會出現 key 補全 |
| G2 | Remove 只出現在「Not cited in this document」區，按下後先確認 | 本文引用列沒有 Remove；未引用區每筆都有 Remove，確認文字說明會從書目檔刪除、且不檢查其他文件；取消後書目不變 |
| G3 | BibTeX 匯出從前端到後端全部移除 | GUI 沒有 BibTeX 選項；`bibliography.export` 傳入 `format: "bib"` 會被協定驗證拒絕；`export_bib` 與 `.bib` 匯出目標不存在；`.tex` 文件不顯示 Export，但檢查、跳行與補全照常 |
| G4 | 匯出合併為一個 `Export ▾`，展開後可選 Word（一般）、Word（系上格式）、Markdown | Markdown 文件只有一個 Export 按鈕，選單有三個選項；Word（一般）寫出 `<檔名>.<樣式>.docx`，Markdown 寫出 `<檔名>.<樣式>.md`，行為與現在相同；原稿不變 |
| G5 | 「Word（系上格式）」以專案內附的 bime_word 1.1.5 產生 `<檔名>.bime.docx` | 對 `proposal.md` 的副本匯出後得到 `proposal.bime.docx` 與 bime_word 的三份報告；GUI 顯示輸出路徑與稽核摘要；bime_word 回報稽核錯誤時仍顯示檔案路徑與錯誤數；設定或轉檔失敗時顯示 bime_word 的錯誤訊息 |
| G6 | 面板預設收合成一條摘要列 | 開啟文件時只看到一列：引用數、問題數、Style、Preview、Export、Refresh 與展開鈕；有 Problems 時摘要列標紅並自動展開；按 Preview 時自動展開以顯示結果 |
| G7 | 編輯器字體預設 16px，可用 Ctrl+= / Ctrl+− 縮放並記住設定；面板文字至少 0.9rem | 新開的編輯器字體為 16px；縮放後重開 GUI 仍是縮放後的大小；Ctrl+0 恢復 16px；行高隨字級調整，28px 的多行文字不重疊；面板內沒有小於 0.9rem 的文字 |
| G8 | 決定保留的行為不受影響 | Preview、Style 選單、Problems、Verify and add、Line 跳轉、key 補全，以及 Python、npm、cargo 全部測試都和改版前一樣通過 |
| G9 | README 反映改版後的面板 | `README.md` 的引用面板、格式與匯出、輸出位置表，以及 `app/skills/citation/README.md` 的匯出說明，都與實際行為一致；列出 bime_word 的來源與版本 |
| G10 | 面板與 Agent 都不再看到 verified／unverified（D17） | 面板條目沒有標籤；`bibliography.inspect` 的 entries 與 `bibliography_lookup` 的回傳都沒有 `verification` 欄位，三方協定拒絕帶此欄位的回應；`bundle_checker` 已刪除；Agent 存檔前的權威來源查證與 `cite/` 的查證紀錄照舊 |

**驗收分工（D14）**：上表保留完整的預期行為。代理負責實作、必要的自動檢查與程式碼核對，並交付 GUI 手動檢查清單；實際 GUI 操作由使用者本人於交付後驗收。代理不等待手動驗收，也不以 GUI 尚未操作阻塞交付；紀錄須區分自動證據與尚未回報的手動結果，不得宣稱 GUI 已實測。

## 決策紀錄

D1–D13 沿用原計劃記錄的 2026-11-07 對話來源；D14 來自使用者的 GUI 驗收分工修訂；D15 是代理在核對中提出、使用者採用的局部阻塞規則；D16 是使用者對「昂貴嘗試」的定義；D17 是使用者驗收後同意代理的提議，取代 D9。本計劃保留必要引文，執行時不需要讀原對話。

| ID | 決策 | 狀態 | 來源 | 後果 |
|---|---|---|---|---|
| D1 | 拆掉 Insert。agent 寫入的引用用不到它，使用者自己寫時有 `[@` 補全可用 | 已確認 | 「那就直接拆掉」 | G1 |
| D2 | 方案 1A：刪除 Insert；Remove 只保留在「Not cited」區 | 已確認 | 「1A」 | G1、G2 |
| D3 | 刪除 BibTeX 匯出，包括後端；接受 `.tex` 文件沒有任何匯出 | 已確認 | 「至於輸出bibtex，我傾向直接刪掉」、「那就拿掉」 | G3 |
| D4 | Word 匯出保留兩種：一般格式與系上格式 | 已確認 | 「先保留，就讓word有是不是系上格式兩種選擇」 | G4、G5 |
| D5 | 方案 3A：一個 `Export ▾` 選單，檔案自動命名並存在原稿旁 | 已確認 | 「3A」 | G4 |
| D6 | 方案 2A：預設收合成摘要列，有 Problems 時自動展開 | 已確認 | 「2A」 | G6 |
| D7 | 編輯器 16px，加上 Ctrl+= / Ctrl+− 縮放並記住設定；面板文字至少 0.9rem | 已確認 | 「我同意這個」 | G7 |
| D8 | 保留 Preview | 已確認 | 「preview我覺得很好，應該保留」 | G8 |
| D9 | 不隱藏 unverified 標籤 | 被 D17 取代 | 「不需要」 | G8 |
| D10 | 以 Poetry 把 `python-docx` 與 `lxml` 加入 `app`（依 AGENTS.md，新增依賴必須經過使用者同意，此處已取得） | 已確認 | 選擇「加進 app 環境（推薦）」 | G5、R3 |
| D11 | 把 bime_word 1.1.5 vendor 到 `app/vendor/bime-word/`，作法比照 web-search-mcp | 已確認 | 選擇「vendor 1.1.5 進 repo（推薦）」 | G5、R3 |
| D12 | 系上格式輸出檔名為 `<檔名>.bime.docx`，不覆蓋使用者追蹤的 `proposal.docx` | 已確認 | 選擇「proposal.bime.docx（推薦）」 | G5 |
| D13 | 最後一步更新 README | 已確認 | 「最後要追加一個更新README」 | G9、R6 |
| D14 | GUI 驗收由使用者本人操作；代理完成實作、自動檢查並交付手動清單，不等待 GUI 驗收 | 已確認 | 本次審核回覆：「這個我不同意，GUI驗收留給我本人操作就好」 | G1–G8、R6、代理交付完成條件 |
| D15 | 同一問題兩次聚焦修正失敗只封鎖該問題及相依步驟；獨立工作繼續。昂貴嘗試失敗／無改善，或已無可執行的獨立工作時，停止整次執行 | 本次修訂採用 | 使用者後續核對 B：「只停下那個問題和依賴它的步驟，標為 Blocked；不相依的階段繼續做」 | PLANS、PROMPTS、步驟相依與續作；取代本計劃先前兩次局部失敗即停止整次的規則 |
| D16 | 「昂貴嘗試」只指付費 API 呼叫，本專案基本上只有 OpenRouter。完整測試、`poetry add`、編譯等本機或免費的操作都不算 | 已確認 | 使用者：「昂貴嘗試的定義就是付費API(基本上這邊應該只有openrouter的付費)」 | D15 的整次停止條件；本計劃本來就不授權付費 API，所以這個條件只在意外發生付費呼叫時才會觸發 |
| D17 | 拿掉 verified／unverified：面板標籤、協定的 `verification` 欄位、`bibliography_lookup` 回傳的狀態與 `bundle_checker` 都刪除。Agent 存檔前向權威來源查證、`cite/` 的查證紀錄、NeurIPS 官方網址的去重保留 | 已確認（2026-11-07 驗收後） | 使用者問「真的需要保留那個verify機制嗎?」；代理說明標籤只表示「`cite/` 有 Agent 存檔的紀錄」，使用者的 70 筆書目 0 筆 verified（52 筆有 DOI），建議只拿掉標籤；使用者：「我同意你的判斷，去改」 | G8、G10、R8；取代 D9 |

已否決、不得重新引入：方案 1B（Insert 與 Remove 全部刪除）、1C（只改名）、2B（拖曳分隔線）、2C（移到右側分頁）、3B（系統存檔視窗），以及讓 bime_word 改用額外指定的 Python 或使用者 skill 目錄中的版本。

## 可逆的規劃假設

以下是撰寫計劃時採用的預設，不是使用者的決定。執行者可以在證據顯示有更好的作法時修改，但必須記錄在 build-log。

| ID | 假設 | 理由 |
|---|---|---|
| A1 | 系上格式匯出使用 bime_word 的預設 `--scope fragment` | 與 `論文/CLAUDE.md` 記錄的 proposal 轉檔指令相同；完整論文的 `--scope thesis` 不在本計劃範圍 |
| A2 | 原稿旁有 `bime-<檔名>-profile.json` 時傳 `--config`，例如 `proposal.md` 對應 `bime-proposal-profile.json`；沒有則不傳。一律傳 `--bibliography <專案書目檔>` | 符合使用者現有的命名；書目與面板一致 |
| A3 | bime_word 結束碼 0 代表成功；1 代表已寫出檔案但稽核有錯誤，顯示路徑與錯誤數，不算失敗；2 或其他結束碼代表失敗，顯示 stderr | 依 bime_word 1.1.5 `scripts/bime/cli.py` 的行為 |
| A4 | 重新匯出時以 `--overwrite` 覆蓋同名的 `<檔名>.bime.docx`；輸出路徑等於原稿時一律拒絕 | 與其他匯出的覆蓋行為一致 |
| A5 | 系上格式不使用 Style 選單的樣式，選單文字註明引用格式固定為附件十七 | bime_word 自己排版引用 |
| A6 | 縮放設定存在 webview 的 `localStorage`，所有讀寫都包在 try/catch 中，失敗時用 16px；範圍 10–28px，每次 ±1px；Monaco 使用自動行高（lineHeight: 0）；只在編輯器取得焦點時生效 | 專案只供本機使用，不需要後端設定檔 |
| A7 | 收合狀態不保存。開啟文件時收合；Refresh 後若問題數從 0 變成大於 0，或開啟時就有問題，就自動展開；其他情況尊重使用者的切換 | 最簡單且符合 D6 |
| A8 | 未引用區的 Remove 仍跳出確認視窗 | 代理人的提議，不是使用者的決定。起因是 2026-11-07 的誤刪；書目檔由多份文件共用，「本文未引用」不代表其他文件也沒引用 |
| A9 | GUI 標籤維持現有的英文 | 與前一個計劃的「介面文字沿用 GUI 現有語言」一致 |
| A10 | 專案只在本機使用，`app/vendor/` 不放進 wheel；vendor 目錄內的測試不納入 app 的 pytest（`testpaths = ["tests"]`） | 比照 web-search-mcp |
| A11 | 系上格式匯出讀的是磁碟上的原稿。編輯器文字和磁碟內容不同時，拒絕匯出並提示先按 Ctrl+S，不寫暫存檔 | bime_word 從檔案讀取，並以原稿所在目錄解析相對圖片路徑；拒絕是最簡單且不會產生錯誤輸出的作法 |

## 範圍外

- 存檔前的驗證邏輯、Style 清單與 Preview 的內容。面板的 verified 判斷依 D17 在 R8 刪除。
- citation skill、agent 的 `/citation` 流程，以及 `Verify and add` 的驗證與合併語意（只移除成功後的 Insert at cursor）。
- LaTeX 的引用檢查與補全（保留）。
- 寫入 `/home/minervamuses/論文/` 的任何檔案，包括還原被誤刪的 `yao2023react`，那是使用者自己的資料。zip 只讀不寫。
- 升級或修改 `~/.claude/skills/bime-word`。
- 編輯 `for_agents/`，它由外部的 infrastructure skill 管理；只在最終彙報提醒可能已過時。
- push、建立或切換 branch。

## 不可破壞的條件

- 匯出永遠不覆寫原稿。
- `references.json` 的寫入規則不變：保留既有條目、key 與排版，寫入前檢查指紋。
- 回合或文件操作進行中，Style、Remove、Export 都停用，和現在一樣。
- 書目與 bime_word 輸出的字串都是不可信文字，經既有的安全顯示路徑呈現。
