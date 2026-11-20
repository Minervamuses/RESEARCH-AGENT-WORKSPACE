# Research Agent

供個人研究使用的本地桌面工作區：開啟研究文件、與 agent 討論、對文件或對話逐段留言，再由 agent 依要求修改目前文件。對話、知識庫與產出保存在本地；模型及啟用的外部工具仍可能需要網路服務。

**文件編輯器只開啟目前研究專案內的 `.md`、`.markdown`、`.tex`。研究資料放在 WSL 檔案系統。**

## 環境與首次準備

支援的執行環境是 Linux。這套桌面選檔流程使用 Windows 上的 WSL／WSLg：Python、Node、Rust、Git 與後端都在 Linux 執行，Windows 只提供原生資料夾與檔案選擇視窗。WSL 須能呼叫 `powershell.exe` 與 `wslpath`。

本機驗證環境為 Ubuntu 24.04。建置使用的系統套件包括 `build-essential`、`pkg-config`、`libgtk-3-dev`、`libwebkit2gtk-4.1-dev`、`libssl-dev`、`librsvg2-dev`；請先備妥相應的 Linux 桌面建置環境。

在 **WSL terminal、workspace 根目錄**執行首次安裝：

```bash
conda env create -f app/env/env-app.yml
conda activate app
cd app
poetry install
cd desktop
npm ci
cd ../vendor/web-search-mcp
npm ci
npx playwright install chromium
npm run build
cd ../../..
```

已存在 `app` 環境時直接啟用，不必重新建立。Conda 管理 Python、Poetry、Node、Rust 與 Pandoc；Poetry 在這個環境內管理 Python 套件，專案已停用 Poetry 自建虛擬環境。

引用格式的預覽與匯出使用 Pandoc（`app/env/env-app.yml` 已列入）。在加入 Pandoc 之前建立的 `app` 環境，補裝一次即可：

```bash
conda install -n app -c conda-forge "pandoc>=3,<4"
```

網頁搜尋工具來自專案內附的 [Web Search MCP server](app/vendor/web-search-mcp/README.md)，agent 啟動時載入它的 `dist/index.js`。尚未 build 時 agent 仍會啟動，只是沒有網頁搜尋，log 會記錄缺少的路徑。

引用面板的「系上格式 Word」匯出使用專案內附的 [bime_word](app/vendor/bime-word/README.md) 1.1.5（依臺大生機系附件十七把 Markdown 轉成 Word）。它來自作者提供的 `bime_word-1.1.5.zip`（SHA-256 `66052fb91d5f9fbccff4b7eb98c3ea56779ec55192360e1772f8179e26303ab2`），原樣放在 `app/vendor/bime-word/`，不做修改，也不會被當成 agent 技能載入。它需要的 `python-docx` 與 `lxml` 已列在 `app/pyproject.toml`，`poetry install` 會安裝；Pandoc 沿用上面的 Conda 套件。檢查環境：

```bash
python app/vendor/bime-word/scripts/bime_word.py doctor
```

更新版本時，把新的 zip 解壓到空目錄並在其中執行 `sha256sum -c manifest.sha256`，通過後整個取代 `app/vendor/bime-word/`，再到該目錄執行一次 `sha256sum -c manifest.sha256`。

模型使用啟動 shell 繼承的 `OPENROUTER_API_KEY`，例如：

```bash
export OPENROUTER_API_KEY='你的金鑰'
python main.py
```

程式不會自動讀取 `.env`。模型設定在 [AgentConfig](app/agent/config.py)。知識庫語義檢索另需可連線的 Ollama 與 `bge-m3` 模型，可用 `ollama pull bge-m3` 準備；其餘 RAG 設定見 [RAG 文件](app/rag/README.md)。

## 日常啟動

每次從 workspace 根目錄啟動：

```bash
conda activate app
python main.py
```

啟動器會使用正式版桌面程式；首次啟動，或桌面原始碼比執行檔新時，會先建置。它不會代替首次的 `poetry install`／`npm ci`。開發時可用 `python main.py --dev` 啟用即時重新載入；`--rebuild` 可強制重建正式版。

桌面開啟後自動啟動本地後端並顯示準備狀態，正常使用不需要再按 Start。Backend ready 表示本地連線就緒，尚未送出研究或模型請求。若啟動或環境檢查失敗，依畫面的錯誤與 `Retry start`、`Retry runtime check` 或 `Restart backend` 重試。

側欄的 Restart 仍用於重新載入已設定的 MCP servers，也供需要重啟的擴充管理流程使用。停止目前回合請使用 Stop。

## 開啟專案、文件與對話

1. 按 **Choose project folder…**，在 Windows 原生視窗選取 WSL 資料夾，例如 `\\wsl.localhost\Ubuntu-24.04\home\你的帳號\research`。
2. 檢查畫面顯示的 Linux 專案路徑與 history directory。已有設定時按 **Open project**；首次設定時確認歷史位置，再按 **Initialize and open project**。專案的 `RESEARCH.md` 保存研究規則及對話歷史位置。
3. 在文件區右上方選單選 **Open file**，選取目前專案內的 `.md`、`.markdown` 或 `.tex`。編輯後以 **Ctrl+S** 保存。Windows 選取路徑會對應到原本的 Linux 文件，開啟與保存使用同一份實體檔案。編輯器字體預設 16px；游標在編輯器中時，**Ctrl+=** 放大、**Ctrl+-**（減號）縮小（每次 1px，範圍 10–28px），**Ctrl+0** 恢復 16px。縮放後的大小會記住，重開程式仍沿用。
4. 從側欄手動選取既有對話，或按 **New conversation** 建立新對話。

每次重新開啟程式都要手動選專案、文件與對話；既有歷史仍保留，但不自動回到上次位置。取消原生選檔視窗會保留目前文件與未送出的草稿。選檔視窗會開在程式前面並取得焦點；萬一 Windows 不讓它到前面，工作列會有「Research Agent: choose project folder」或「Research Agent: open document」按鈕，點它即可回到選檔視窗。

### 單一工作流程（產品限制）

這是**單人本地學術寫作工具**。一次只操作**一個已開啟的研究專案、一個選取中的對話，以及一個進行中的研究工作回合**。可以保存許多專案和對話並依序切換，但**不支援同時開啟兩個專案、在不同對話中平行執行 agent，或用多個桌面實例同時操作同一份工作區資料**。這不是通用多使用者或多工作流程 Agent。

請先讓目前回合完成，或使用 **Stop** 確認停止後，再切換專案、切換對話或送出下一項工作。核准視窗正在等待時，先批准或拒絕，不要另起回合。同一回合內的 Ask 核准、Stop、以及由該回合要求的文件套用，屬於**同一工作的正常步驟**，不是兩個平行研究任務。

這項限制不要求軟體提供跨專案並行管理、通用讀寫鎖或多實例協調；但遵守上述順序時，存檔結果、停止與重試、核准、後端中斷恢復仍應正確，不得把正常使用中的失敗當成使用者責任。

## 逐段留言與整批送出

在目前文件或一則對話訊息內選取文字，按 **Add comment** 或 **Comment on selection**。agent 回覆也可以作為引文來源。每段都有對應留言框與數字入口。

- 在段落留言框按 **Enter** 只會確認並收合這則留言；**Shift+Enter** 換行，輸入法組字中的 Enter 不會送出。
- 可以繼續標註其他段落，或點數字入口重開修改、移除留言。
- 最後按主輸入區的 **Send**，將主訊息、本批全部留言及引文一起送成一個回合。主訊息可以空白；在主輸入框按 Enter 也會送出，Shift+Enter 換行。

引文是來源資料，留言與主訊息才是使用者要求。批次留言不等於批次授權；Ask／Bypass 仍由使用者決定。對話引文可以用來討論，但不會回寫原對話訊息。

後端確認本回合已保存並接受後，清除本批草稿與數字標記；尚未接受的送出失敗會保留草稿。已接受後若回合失敗，依畫面的保存狀態與重試入口處理。不要用反覆 Send 判斷是否送達。

未送出的草稿與標註只存在本次程式記憶體中，不跨程式重啟恢復，也沒有獨立標註歷史。已送出的合成訊息與必要 context 仍按一般對話保存，並依正常 context window 規則使用或移出；載入舊訊息不會重新建立留言標記或額外注入標註歷史。

## 修改文件與權限

agent 可在同一回合依留言依序修改目前文件的多個段落，後續修改保留本回合先前已保存的成果。

**Ask** 會在需要核准的文件寫入或工具操作前顯示確認；核對目標與內容後才批准。**Bypass** 依目前權限策略略過這些確認，檔案範圍與版本檢查仍適用。多段留言不會自動把 Ask 改成 Bypass。

正常操作順序是：選取原文 → 留言並確認收合 → 整批送出 → 等待回合完成或確實停止 → 再手動編輯原文。標註後又手動改原文、或 agent 執行中同時手動改原文，屬於目前不支援的操作；介面不另提供鎖定、標記重定位或合併機制。

## 詰問與文體 skill

**@grill：檢查一段論證。** 圈選一段後輸入 `@grill`（可加一句說明），agent 會先寫出 **還原**：這段要讀者相信什麼、各句的角色與支持關係。接著在你實際主張的範圍內試著推翻，只在找到具體問題或影響判斷的資料缺口時提出 **發現**，每條附逐字引用、理由和要你回應的事；最後給出 **判斷**。回應質疑時再打一次 `@grill`，skill 只在打了 `@grill` 的那一回合生效。

- 詰問回合只讀不改：模型看得到整份文件，但 `document_edit` 不可用，不會出現編輯核准，缺的內容只在回覆中以 `[TODO: …]`、`[CITE: …]`、`[FIGURE: …]` 建議。改寫是通過後另外一步。
- 段落留言裡的 `@grill` 作用於整個回合：主請求與所有引用都變唯讀。要改寫的請求請另外送出。
- 「通過」只表示在目前材料與檢查範圍內沒找到具體問題，不保證正確。這套方法是第一版，**還沒有用真實模型和真實段落驗證效果**。評估方法與 `scripts/grill_eval.py` 的用法見 [app/skills/grill/README.md](app/skills/grill/README.md)；`--live` 會呼叫 OpenRouter 並產生費用。

**@writing-genres：文體格式。** 輸入 `@writing-genres` 並說明要寫的文體（論文、教材、筆記、計劃書、Abstract、Poster、投影片），agent 會依該文體的結構寫成原稿，並用 bash 寫檔（Ask 下要核准）。預設寫成編輯器能開的 `.md`；Word 由 Citations 面板的 **Export** 轉出，投影片可用 Pandoc 轉成 `.pptx`。轉出的檔案不能在編輯器圈選修改。不加 `@writing-genres` 時，每回合仍有簡短的寫作規則：先辨識文體、缺內容用上述佔位符、產出非 `.md`／`.markdown`／`.tex` 的檔案前先告知、詰問與改寫分開。

## 文件在對話 context 中怎麼帶

模型自動看到最近 10 個已完成回合。帶文件的回合在對話檔中照樣保存完整快照，但重播給模型時會縮減：

- 本回合帶文件時，較早回合的文件快照與段落引用全文都換成佔位。佔位保留路徑、版本（`editorRevision`）、指紋、選取範圍與行號，以及較短的選取文字。
- 本回合沒帶文件時（例如關閉文件後），只保留最近一次**提交時**的文件快照全文，並標明它是提交時的內容。若那一回合之後 agent 又存檔改了文件，模型看到的仍是改之前的版本，不會自動讀取最新存檔。
- 同一回合連續編輯時，只有最新一次存檔結果帶全文，較早的結果只留改動的範圍。
- 舊版本仍在對話封存中。要比較或還原時可以請 agent 從封存取回；Normal 模式下它會用 bash 搜尋（需要核准），Extended 模式做不到。沒有進入任何回合快照的中間存檔版本不在封存中。

## 引用與參考文獻

每個研究專案有一份 CSL-JSON 書目庫，預設是專案根目錄的 `references.json`；可在 `RESEARCH.md` 的 metadata 加上 `"bibliography": "相對路徑.json"` 改到專案內其他位置。正文只寫引用 key，格式在預覽或匯出時才套用，切換格式不會改動正文任何文字。

- **Agent 存檔**：在專案中用 `/citation` 儲存的文獻（驗證過的 DOI 或 arXiv ID；沒有 DOI 的 NeurIPS 論文則在官方論文集網站 proceedings.neurips.cc 依該年的論文列表與論文頁查證），除了照舊寫入 bundle，也會併入書目庫並取得 key（例如 `jumper2021highly`）。已存在相同 DOI、arXiv ID 或 NeurIPS 論文（以官方網址中的年份與論文 hash 判斷，`papers.nips.cc` 與 `proceedings.neurips.cc` 視為同一篇）的條目會被重用，內容與 key 都不改；檔案原本的 JSON 排版保持不變。摘要不寫入。CLI 沒有專案，只寫 bundle。
- **正文寫法**：Markdown 用 Pandoc 語法 `[@key]`、`[@a; @b]`、`[see @key, p. 3]`；LaTeX 用 `\cite{key}` 一族。Agent 修改文件時不能引入書目中沒有的 key；它可用唯讀工具 `bibliography_lookup` 查詢既有 key。
- **引用面板**：開啟文件後，編輯器下方的 **Citations** 面板預設收合成一列摘要：引用數與問題數（例如 `3 cited · 1 problem`）、**Style**、**Preview**（只限 Markdown）、**Export ▾**、**Refresh** 與 **Expand／Collapse**。有問題時摘要列標紅。開啟文件時已有問題、存檔或 Refresh 後問題從無到有，或按下 **Preview** 時，面板會自動展開；其他時候維持你的選擇，收合狀態不保存。通知、書目錯誤、處理進度與匯出結果在收合時也顯示在摘要列下方。展開後列出本文引用（依首次出現順序，附引用次數；數字制樣式另顯示編號）、問題（書目中找不到的 key、重複 DOI、書目無法讀取）與未引用的條目。面板不標示條目是否查證過：查證發生在 `/citation` 存入新文獻時，手寫的條目由你自己負責。點 **Line** 會在編輯器選取那個引用。**Verify and add** 以 DOI 或 arXiv ID 驗證後加入書目（Ask 模式會先請你批准，與 `/citation` 的存檔相同）。**Remove** 只出現在 **Not cited in this document** 區，按下後一律先確認：它會從書目檔刪除那個 key，而書目檔由專案中的所有文件共用，其他文件不檢查。面板沒有插入引用的按鈕；在 `[@`、`; @` 或 `\cite{` 之後輸入會出現 key 補全。
- **格式與匯出**：**Style** 選單的選擇存在 `RESEARCH.md` 的 `citationStyle`。內建 APA 7、MLA 9、IEEE、Chicago author-date，以及依附件十七撰寫的 `bime-appendix17`。**Preview** 顯示目前文字的逐筆引用與參考文獻。Markdown 文件的 **Export ▾** 有三個選項，檔案都寫在原始文件旁（同名檔案會被覆蓋），原始文件不變：
  - **Word (.docx)**：`<檔名>.<樣式>.docx`，引用依 Style 排版。
  - **Word – BIME Appendix 17 (bime_word)**：以內附的 bime_word 寫出 `<檔名>.bime.docx`，另有三份報告 `<檔名>.bime.audit.json`、`<檔名>.bime.audit.md`、`<檔名>.bime.bime.json`。它轉換的是已存檔的檔案，所以有未存檔的修改時會拒絕，請先按 Ctrl+S；引用格式固定為附件十七，不使用 Style。原始文件旁有 `bime-<檔名>-profile.json` 時會當作 bime_word 的設定檔（例如 `proposal.md` 對應 `bime-proposal-profile.json`）；書目一律使用專案書目庫；轉換範圍是 `fragment`。文件有目錄（`{{TOC}}`）時，轉換後會把目錄獨立成一節，以小寫羅馬數字 i、ii… 編頁，本文從 1 起算（附件十七 二.4；bime_word 的 `fragment` 範圍原本把目錄也從 1 編起），再對最終檔案重跑一次 bime_word 稽核，三份報告都對應實際寫出的檔案。完成後面板顯示稽核的錯誤、警告與需人工確認的項目數，以及 `.audit.md` 的路徑；稽核有錯誤時仍會寫出檔案。bime_word 不驗證版面，請在 Word 中更新所有欄位並逐頁檢查。正文用了書目中沒有的 key、或設定檔有誤時，不會寫出檔案，面板顯示 bime_word 的錯誤訊息。
  - **Markdown (.md)**：`<檔名>.<樣式>.md`，引用已排版。

  `.tex` 文件沒有匯出，只提供檢查、面板與補全，格式由 LaTeX 自己的書目系統決定。
- **附件十七的細節**：渲染前會在書目的暫存副本套用與 bime_word 相同的規則：直撇號 `'` 不會被換成 `’`；`Wen-tau` 這類名字縮寫成 `W.-t.`；去掉名字中的 `(暱稱)`；資料中以 `{"literal": "et al."}` 結尾的作者清單輸出為 `…, A. Vaughan, et al.`。與 bime_word 產出的 `proposal.docx` 相比，引用與參考文獻全部一致。仍有的限制：標準 CSL 無法表達中日文依姓氏筆畫排序、全中文引用群組內的全形「；」，`等人` 前會多一個空白。中文或日文條目依 `language` 欄位（`zh…`、`ja…`）判斷，沒有這個欄位時依標題與作者姓名中的漢字、假名判斷；`"language": "en"` 等其他語言維持英文格式。這個判斷只用在渲染時的暫存副本，書目檔不會被改寫。比對紀錄保存在 git 歷史中：`git show 05df764:harness/plans/2026-11-05-citation-management/evidence/C5-S2/compare.md`。系所送審的 Word 檔仍由 bime_word 產生，可在 **Export ▾** 選 **Word – BIME Appendix 17 (bime_word)**。

## 停止回合

送出後 **Send** 變成 **Stop**。按下後顯示 **Stopping…**，等待模型呼叫、核准等待、工具及本回合可控制的本地工作真正收束，才恢復送出下一回合的操作。本地子程序會終止並回收；已進入的短同步操作會等返回，不會提前顯示停止完成。

已接受回合的使用者訊息會保留，中斷狀態顯示為 **interrupted／Turn stopped**。Stop 不會重啟整個後端；停止完成後可直接繼續對話。若停止失敗，畫面保留實際錯誤與 **Retry Stop**，尚未收束時不能再送新回合。

Stop 保留已完成的文件寫入及工具效果，不是復原操作，也不保證撤銷外部服務已接受的請求。若回合已經完成，就保留實際完成結果。

## 重新命名與刪除對話

在側欄對話上按右鍵，選 **Rename** 或 **Delete**。這個區域使用對話專用選單。

Rename 適用於已保存的對話；新名稱會持續保存，重新開程式後仍可見，不修改原訊息。尚未送出第一則訊息的暫時對話可以刪除，但不能重新命名。

Delete 會先確認範圍：**只刪這則對話紀錄，不刪研究專案或產出文件**。取消不改資料。刪除正在執行的對話時，會先 Stop 並等回合收束；停止失敗不會繼續刪除。成功後該對話及其清單項消失。若刪除目前選中的對話，會清除選中狀態，可手動選其他對話或新建；刪除其他對話則保留目前內容。

## 記錄了哪些資訊

所有紀錄都只存在本機。下表是目前實際寫入的位置與內容：

| 紀錄 | 位置 | 內容 | 不包含 |
| --- | --- | --- | --- |
| 診斷 log | `$AGENT_LOG_DIR`；未設定時為 `$XDG_STATE_HOME/research-agent/logs`，預設 `~/.local/state/research-agent/logs`。CLI 寫 `cli.log`，桌面後端寫 `desktop-backend.log`，各自在 5 MiB 時輪替並保留 3 份 | agent、skills、rag 的 INFO 以上訊息，以及第三方套件的 WARNING 以上訊息；錯誤的 traceback 與 incident ID（畫面上的錯誤代碼可在這裡找到）；每回合的 `turn_trace`（見下節） | 訊息內容、工具參數、原始查詢。金鑰形式的字串在寫入前會換成 `[redacted]` |
| 桌面後端 stderr | 同一目錄的 `desktop-backend.stderr.log`，5 MiB 時輪替一次 | 後端程序的 stderr，以及每次啟動的 generation 標頭 | — |
| 對話 | 桌面：專案的 `historyDirectory`（寫在專案的 `RESEARCH.md`，預設 `app/store/projects/<專案 ID>/conversations/`）。CLI：`<persist_dir>/conversations/`（預設 `app/store/conversations/`，可用 `KMS_STORE_DIR` 改） | 每回合的輸入、送出時的專案規則與引用、思考模式、回答全文、狀態與失敗原因、時間，以及工具活動（呼叫 ID、工具名稱、成功或失敗） | 工具參數與工具回傳的內容 |
| MCP server log | `$XDG_CACHE_HOME/agent-mcp/<server>.stderr.log`，預設 `~/.cache/agent-mcp/`，5 MiB 時輪替並保留 3 份 | MCP server 的 stderr：每次載入一行標頭；web_search 每次搜尋解析到的結果數、`handleWebSearch` 的 limit 與 includeContent，以及錯誤訊息（可能含網址） | 查詢文字與頁面內容。server 的 stdout 只轉送 JSON-RPC，其餘印出的文字都被丟棄 |
| 已儲存的文獻 | `cite/`，或 `CITATION_OUTPUT_DIR`、`AgentConfig.citation_output_dir` 指定的位置 | 只有在 Citation 中明確儲存（或在引用面板以 DOI／arXiv ID 加入）的來源 | 搜尋過但沒有儲存的候選 |
| 專案書目庫 | 桌面專案的 `references.json`，或 `RESEARCH.md` metadata 的 `bibliography` 指定的檔案 | 已儲存文獻的 CSL-JSON 書目欄位（作者、年份、標題、期刊、卷期頁、DOI、URL 等）與 key；使用者手寫的條目原樣保留 | 摘要、參考文獻清單、授權、ORCID、機構等欄位 |
| 引用匯出 | 文件旁的 `<檔名>.<樣式>.docx`、`<檔名>.<樣式>.md`，以及系上格式的 `<檔名>.bime.docx` 與報告 `<檔名>.bime.audit.json`、`<檔名>.bime.audit.md`、`<檔名>.bime.bime.json`；只在從 Export 選單選擇時寫出 | 套用所選格式（或附件十七）的正文與參考文獻；bime_word 的稽核結果與轉換紀錄 | — |

模型每次收到的完整 prompt、中間回覆，以及工具回傳的全文，都只存在記憶體裡，回合結束後不保存。所以事後只能從下面的長度、次數與時間判斷工具結果有沒有交給模型，不能還原內容。

### turn_trace 欄位

每個回合嘗試寫一組 `turn_trace` 行。`turn_id` 對應對話檔的 `turnId`，`attempt` 用來區分重試：

- `turn_start`；`turn_end`：`state`、`duration_ms`、`model_calls`、`tool_calls`、`unfinished`。
- `model_start`／`model_end`：`model_seq`、`at_ms`（距離嘗試開始的毫秒數）、`duration_ms`、`status`（ok、error、unfinished）、`tool_calls`、`input_tokens`、`output_tokens`（供應商回報的值）。
  - `model_end` 另記文件佔比，只有字元數：`prompt_chars`（全部訊息字元數）、`document_chars_current`（本回合快照與段落引用全文）、`document_chars_history`（歷史回合仍帶的快照全文）、`document_chars_tool_results`（`document_edit` 結果中的全文或範圍文字）、`document_full_copies`（全文份數）、`document_parse_issue`（無法辨識的文件區塊，正常為 `None`），以及 `document_tokens_estimate`：`input_tokens` 乘以文件字元占比的**估計值**，不是供應商回報的數字。
- `tool_start`／`tool_end`：
  - `tool`、`tool_call_id`、`model_seq`（由哪一次模型呼叫發出）；
  - `query_hash`（工具有 `query` 參數時）：查詢的 SHA-256 前 16 碼，只能比對兩次查詢是否相同，無法還原查詢；
  - Citation 的 `action`；`status`（ok、error、unfinished，失敗時另有 `error_type`）、`duration_ms`；
  - `output_chars`：工具成功回傳時，交給模型的文字字元數；
  - Citation 搜尋與儲存的計數，例如 `candidate_count`、`abstract_count`、`new_candidate_count`、`provider_count`、`failed_provider_count`。

模型回覆異常（空回覆、格式錯誤的工具呼叫）時，另有 `model_response` 警告行；Citation 儲存完成時另有 `citation_save_finalized` 行，只含計數。

查一個回合的所有事件：

```bash
grep -h turn_trace ~/.local/state/research-agent/logs/desktop-backend.log* | grep turn_id=<turnId>
```

## 其他入口與開發檢查

對話輸入 `/` 可查看目前後端提供的命令；可用命令與 skills 取決於該次 session。CLI 可用 `/help` 查看命令。

以下命令在 `app/`、Conda `app` 環境內執行：

```bash
python -m agent.cli.chat --no-mcp
poetry run pytest
poetry build
```

桌面前端檢查位於 `app/desktop/`：`npm test`、`npm run build`；Rust 檢查位於 `app/desktop/src-tauri/`：`cargo test --locked`。

程式結構與開發入口見 [app/README.md](app/README.md)，知識庫 API 見 [RAG API](app/rag/docs/API.md)。本次桌面改版的分段實機驗收、檢查結果與限制記在該計劃的 build log；計劃完成後已從工作樹移除，可用 `git show b4d56f1^:harness/plans/2026-10-18-desktop-interaction/build-log.md` 取回。
