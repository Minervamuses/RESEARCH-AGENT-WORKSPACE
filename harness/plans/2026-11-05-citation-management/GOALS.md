# 引用管理：目標、決策與不變條件

本文件只擁有穩定的需求、決策來源與不變條件。路線與執行契約見 [PLANS.md](PLANS.md)，執行狀態只見 [build-log.md](build-log.md)。

## 問題

桌面 GUI 已能讓使用者開啟專案文件（`.md`、`.markdown`、`.tex`）、框選段落、讓 Agent 以 `document_edit` 修改；`/citation` 能搜尋並驗證文獻，存成每篇一個 bundle（`reference.bib` + `citation.json`）。但引用與正文是斷開的：

- bundle 存在 Agent repo 的 `cite/`（或 `CITATION_OUTPUT_DIR`），不在使用者的專案裡，也沒有合併成一份書目；BibTeX key 是 doi.org 給的，沒有管理。
- `[[cite:…]]` 的檢查與編號只作用在聊天回覆（`app/agent/skills/citation/session_policy.py:167`、`:190`），寫進正文的引用完全沒有檢查。
- 只有一種固定的中性數字格式，沒有 APA、MLA 等格式。
- GUI 沒有引用管理介面。

使用者要的體驗以 Overleaf 為參考：管理引用、看見排序、增刪，並在要求時把整篇文章換成指定格式（APA、MLA…）。

## 目標

| ID | 必須達成的結果 | 觀察方式（摘要；完整驗收在各階段檔） | 來源 |
|---|---|---|---|
| CG1 | 桌面專案有一份 CSL-JSON 書目庫。`/citation` 在該專案中存檔成功（saved 或 reused）的作品會併入書目庫並取得穩定 key；既有條目、既有 key 與檔案排版不被改動；摘要不被寫入 | 以使用者格式的書目副本存一個 DOI：檔案 diff 只有新增一筆，工具結果回報 key；重存同一 DOI 不改檔、回報同一 key；書目裡已有的手寫條目被重用、內容不變；CLI 行為不變 | D2、D7 |
| CG2 | 正文的引用是可檢查的 key：解析 Markdown 的 Pandoc 引用語法與 LaTeX 的 `\cite` 家族；對目前編輯器文字產生報告（每個 key 的位置、首次出現順序、找不到的 key、未被引用的條目、重複 DOI、驗證狀態）；Agent 能唯讀查詢書目；`document_edit` 拒絕新引入的未知 key | 解析結果與 Pandoc 自己解析出的 key 集合一致；未知 key 的修改不產生候選、回報原因 | D1、D7 |
| CG3 | GUI 引用面板：列出條目、引用次數與順序、點擊跳到正文位置、顯示缺漏與未引用警告；可刪除（仍被引用時先確認）、以 DOI/arXiv 經驗證新增、輸入時自動補全 key | 後端 RPC 測試與前端測試；使用者手動 GUI 檢查清單 | 使用者：「管理引用，看見引用的排序，並做到刪減增等操作」 |
| CG4 | 指定格式：專案層級的格式設定（至少 APA 7、MLA 9、IEEE、Chicago author-date、附件十七），持久保存；預覽目前文件的引用與參考文獻；切換格式只改渲染結果，不改正文任何位元組 | 同一份正文先後以 APA 與 IEEE 渲染，輸出不同，正文雜湊不變 | D1、D3 |
| CG5 | 匯出：`.md`/`.markdown` 文件可匯出成套用所選格式的 `.docx` 與已排版 Markdown；任何文件都可把書目匯出成 `.bib`；原始檔不變 | 匯出檔存在且引用已排版；原始檔雜湊不變 | D1、D2 |
| CG6 | 附件十七以自訂 `.csl` 實作，在論文語料上與 bime_word 產出的 `proposal.docx` 比對；CSL 能表達的差異全部修正，不能表達的逐項列出 | 比對報告：逐條結果、剩餘差異的類別與例子 | D3 |
| CG7 | 依賴：Pandoc 安裝在 Conda `app` 並寫入 `app/env/env-app.yml`；用到 Poetry 套件時 `pyproject.toml` 與 `poetry.lock` 同步；產品只依賴實際使用的引擎 | `conda list`、manifest diff 與實際 import/呼叫一致 | D4 |
| CG8 | 不退化：聊天回覆的 `[[cite:…]]` 渲染、CLI 存檔、`document_edit` 既有行為、extended thinking 都不變；全部測試套件通過；文件更新；最終彙報列出待使用者決定的事 | 全套 pytest、npm、cargo；文件 diff；最終彙報 | D5、D6、AGENTS.md |

## 範圍外

- **舊文的純文字引用自動轉換**（討論中的 P5）。使用者決定先不做；拿著別處寫的舊文時，由使用者自己逐段框選，再用 `/citation` 處理（D5）。
- **extended thinking**：文件任務一律用 Normal 的硬限制（`app/agent/desktop/service.py:2852`，回合結束於 `:2601-2602` 還原）不動；fusion proposer 的唯讀工具清單（`app/agent/thinking/orchestrator.py:65`）不加新工具（D6）。
- **CLI 的專案書目庫**：CLI 沒有專案工作區，`/citation` 在 CLI 仍只寫 bundle（A1）。
- **`.tex` 文件的 CSL 渲染與匯出**：LaTeX 的格式由它自己的書目系統決定；本計劃只提供 `.tex` 的 key 解析、檢查、面板與 `.bib` 匯出（A6）。
- 書目條目的欄位編輯 UI、修改既有條目的內容、重新命名既有 key、跨文件的引用統計、Zotero/Mendeley 同步。
- 取代 bime_word：系所送審用的 Word（封面、目錄、`{{REFERENCES}}` 等）仍由 bime_word 產生。

## 決策紀錄

| ID | 決策 | 狀態 | 來源（本次對話，2026-11-05） | 影響 |
|---|---|---|---|---|
| D1 | 「改整篇格式」= 正文存 key，預覽或匯出時才套格式；不把正文改寫成某種格式的文字 | 使用者確認 | 使用者回覆選項 (a)：「a」 | 格式由程式渲染；LLM 不重寫全文 |
| D2 | 專案書目以 CSL-JSON 為主；bundle 的 `reference.bib` 保留；`.tex` 需要時由 CSL-JSON 產生 `.bib` | 使用者確認 | 「好，我同意」（回覆 CSL-JSON 不需重寫 skill 的說明） | citation skill 保留 doi.org 已抓到的 CSL-JSON，不重寫搜尋與驗證 |
| D3 | 附件十七走 (i)：自訂 `.csl`，不接 bime_word 的 `cite.py` | 使用者確認 | 「我選i」 | CG6；表達不了的規則只列出，不改走 (ii) |
| D4 | 依賴核准：Pandoc、citeproc-py、citeproc-js 都同意；Pandoc 裝進 Conda `app`；用 Poetry 的套件要同步更新 manifest | 使用者確認 | 「我全部都同意」；「要裝的話裝到conda app裡面，如果是potery的話也記得更新」 | 核准是允許，不是要求三個都留；見 A8 |
| D5 | 舊文純文字引用轉換不做 | 使用者確認 | 「先不要」；「如果使用者拿著別處寫的舊文，想要處理引用，就自己一段一段框起來然後用citation skill」 | 範圍外 |
| D6 | extended thinking 不動 | 使用者確認 | 「先不動extended那邊的」 | 範圍外；新工具不進 proposer 清單 |
| D7 | 第一輪/分期由計劃決定，使用者不需逐輪決定 | 使用者確認 | 「你不用管第幾輪作什麼」 | 本計劃自行排序全部範圍 |
| D8 | 執行政策：一次執行到底不停下來等驗證、有問題記錄、每一步強制 commit（含計劃檔）、只在 GUI 分支、不建立或切換 branch、不 push | 使用者的常設政策 | 2026-10-20 與 2026-10-22 兩份計劃的啟動提示：「不要停下來等我驗證，一次執行到底，有問題記錄下來就好，每一步皆強制commit，不準切換/創造branch」「不準push」 | 寫入 PLANS 契約與 PROMPTS |
| D9 | 附件十七：沒有 `language` 欄位時，依標題與姓名中的漢字、假名自動判斷中日文 | 使用者確認 | 2026-11-06 回覆「要」（問題：要不要依漢字、假名自動判斷，還是只認明確的 language） | C5-F1 的判斷規則保留 |
| D10 | 附件十七輸出直撇號 `'`，在 CSL 之外處理 | 使用者確認 | 2026-11-06 回覆「好」（問題：撇號要不要在 CSL 之外改成直撇號） | C5-F3 |
| D11 | 消除可由資料修正的 4 條附件十七差異（`Wen-tau`、截斷作者清單、名字暱稱） | 使用者確認 | 2026-11-06 回覆「好」（問題：要不要修改書目資料，消除這 4 條差異） | C5-F4：以渲染時的副本套用 bime_word 的相同規則，不改寫 `references.json`（理由見 build-log C5-F4） |

討論中被取代或否決的選項：(b) 把正文改寫成某格式的文字（D1 否決）；以 BibTeX 為書目正本（D2 否決）；附件十七接 `cite.py`（D3 否決）；citeproc-js 跑在 React 作為產品渲染器（未採用，見 A8）。

## 規劃假設（Agent 提出、使用者未逐項確認；可逆，最終彙報要列出）

| ID | 假設 | 理由 | 若使用者不同意 |
|---|---|---|---|
| A1 | 書目檔預設為專案根目錄的 `references.json`；`RESEARCH.md` metadata 可選填 `bibliography`（專案內相對路徑，`.json`）覆寫。只在桌面專案中生效 | 使用者論文已用這個檔名；metadata 已由 catalog 管理 | 改預設路徑只影響 C2-S3 的一個常數與文件 |
| A2 | 格式設定存在 `RESEARCH.md` metadata 的可選 `citationStyle`（樣式 ID），由 GUI 寫入 | 與專案綁定，和 `historyDirectory` 同一處 | 改存放位置只影響 C2-S3 與 C6 |
| A3 | 新 key 規則：第一作者姓（或機構名第一個字）轉 ASCII 小寫 + 年份（缺則 `nd`）+ 標題第一個非停用字；結果只含 `[a-z0-9]`；轉換後為空就用 `ref`；撞名依序加 `a`、`b`…；既有 key 永不更改；同一 DOI（或 arXiv ID）重用既有條目 | 接近使用者既有的 `agrawal2024references` 風格，且可重現 | 規則集中在一個函式 |
| A4 | 引用統計以「目前編輯器中的這一份文件」為範圍（含未儲存文字），不掃整個專案 | 書目只列正文引用者；proposal 與 thesis 共用書目但各自統計 | 跨文件統計列為範圍外 |
| A5 | 匯出檔寫在文件旁，命名 `<主檔名>.<樣式ID>.<副檔名>`（`.bib` 為 `<書目檔名>.bib`），原子替換；由使用者在 GUI 按下觸發，和手動儲存一樣不需批准 | 不需原生存檔對話框；命名夠特殊，不易覆蓋使用者檔案 | 改路徑規則只影響 C6-S2 |
| A6 | `.tex` 不做 CSL 渲染與匯出，只提供解析、檢查、面板與 `.bib` 匯出 | 機器上沒有 LaTeX；LaTeX 自己以 `\bibliographystyle` 或 biblatex 決定格式 | 可另立後續計劃 |
| A7 | 內建樣式：APA 7（`apa.csl`）、MLA 9（`modern-language-association.csl`）、IEEE（`ieee.csl`）、Chicago author-date（`chicago-author-date.csl`），取自 CSL 官方樣式庫並保留其授權標頭；加上自訂附件十七 | 使用者舉例 APA、MLA；IEEE 代表數字制；Chicago 為常見作者年制 | 增減樣式只是加減檔案 |
| A8 | Pandoc 是唯一的產品渲染器，預覽與匯出用同一個引擎，保證預覽 = 匯出；citeproc-js 只在比較測試中當參考基準，不進 desktop 的 `package.json`；citeproc-py 只在 Pandoc 於核心行為上與基準不一致時才拿來評估，評估後移除 | 匯出 docx 必須用 Pandoc；兩個引擎會讓預覽和匯出不一致 | 若比較結果顯示 Pandoc 不夠好，最終彙報列為使用者決策 |
| A9 | 不新增正文佔位語法；`document_edit` 只拒絕新引入的未知 key，Agent 在回覆中說明哪些主張缺來源 | 使用者論文的 `[CITE: …]` 是該專案自己的規則，可寫在 `RESEARCH.md` 的規則文字 | 之後可加 |
| A10 | 面板「刪除」與「匯出」是使用者在 GUI 的直接動作，不需批准；「以 DOI 新增」會連網並寫 bundle 與書目，沿用 `citation.save` 的批准（這是產品的執行期行為：GUI 在 Ask 模式下跳出批准；與計劃執行者無關） | 與手動儲存、`knowledge.ingest_file` RPC 的既有政策一致 | 只影響 C6-S2 |

## 不變條件

- 正文永遠存 key；任何格式切換、預覽、匯出都不修改原始文件。
- 沒有通過驗證流程的作品不會由 Agent 寫進書目；使用者手寫的條目保留但標示為未驗證。
- 摘要只在當次搜尋顯示，不寫入 bundle，也不寫入書目庫（沿用既有不變條件）。
- bundle 的格式與儲存規則不變（`app/skills/citation/storage.py`）。
- `app/skills/citation` 擁有引用的正確性（解析、書目、渲染、驗證）；`app/agent/desktop` 只做轉接；`app/rag` 不碰引用。
- 書目檔寫入一律由 Python 後端執行：讀取 → 合併 → 寫入前再比對指紋 → 暫存檔、fsync、`os.replace`；指紋不符就不寫並回報衝突。
- 使用者的論文資料夾 `/home/minervamuses/論文` 是唯讀輸入：只用 `git -C … show HEAD:<檔案>` 讀取，複本放 `$TMPDIR`；不寫入、不提交它的任何檔案；本 repo 只提交彙總結果與書目字串，不提交論文正文。
- 新增協定方法維持 protocol v1 的加法式成長，四份協定定義（contract.json、Python、TypeScript、Rust）一致。
- 使用者決策 D1–D11 只能由使用者更改。
