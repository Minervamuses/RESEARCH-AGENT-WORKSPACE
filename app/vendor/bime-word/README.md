# bime_word · 1.1.5

依臺大生物機電工程學系論文格式附件（附件十七）執行三種操作：Markdown 轉 Word、在 Word 局部新增內容、唯讀檢查 Word。交付物包含 agent 指示、Python 程式、依權威標記的規則目錄、系辦原始附件、範例與自動測試。

**權威順序：系辦附件十七 > 朋友手做的 Word 範本 > 作者的 CLAUDE.md > 實作預設。** 只有系辦條文是學校規定；系辦沒寫清楚的地方依序由後面的來源補上，每個值的來源見 `references/authority.md`。

**名稱說明：**產品及顯示名稱保留 `bime_word`；Agent Skills 標準的 `name` 不接受底線，因此安裝資料夾及機器識別名稱為 `bime-word`，ZIP 是 `bime_word.zip`。請保持根目錄與 SKILL.md 的 name 一致。

## 1.1.5 的變更

- 新設定 `"cover": true`：非完整論文（例如計畫書）也能以 YAML `bime:` 區塊產生系辦封面範例的封面（欄位與完整論文相同，見 workflows.md C 節）。封面自成一頁、不編頁碼，其後從 1 起編；有封面時第一個 `#` 標題不再另外印成文件標題。預設 false，行為與 1.1.4 相同。

## 1.1.4 的變更

- 目錄、圖目錄、表目錄在轉檔時就寫好項目：每個標題或圖表標題加上書籤，每個項目是連到該書籤的超連結，打開檔案就能點擊跳頁（Word 預設是 Ctrl＋點擊）。頁碼是 PAGEREF 欄位，在 Word 更新欄位後填入；更新後連結仍在。
- 稽核不再把目錄項目（例如「誌謝」「參考文獻」）當成章節標題。

## 1.1.3 的變更

- 轉檔一律略過 `[TODO: …]`（作者決定：Markdown 保留待辦，Word 是要交出去的版本）。括號成對比對，TODO 裡的引用一併略過；只剩標籤的行（例如「步驟：」）列在 `.bime.json` 的 `todo_dangling`。設定 `"drop_todo": false` 可保留。`[CITE: …]`、`[FIGURE: …]` 不受影響。

## 1.1.2 的變更

- 修正：表格在 Word 中沒有框線。Pandoc 讓表格套用名為「Table」的樣式，1.1.1 以前的範本檔沒有定義它；現在定義為全框線（單線 0.5 pt），表格置中，依朋友範本（系辦沒有規定）。

## 1.1.1 的變更

- 計畫書以 `shift_heading_level: -1` 轉檔時，第一個 `#` 標題保留為文件開頭的置中標題。
- 書目的作者清單可用 `{"literal": "et al."}` 標記來源只列前幾位；輸出「A, B, C, et al.」，不補作者。
- 論文集的叢書名（collection-title）接在書名後；沒有卷頁的期刊、沒有頁碼與出版者的會議論文以網址作為定位。
- 英文參考文獻排序忽略變音符號（Järvelin 排在 Jarvelin 的位置）；參考文獻區段的 [TODO] 段落不列入排序檢查。
- 生成的封面、標題頁、審定書之後出現其他段落時，即視為離開該頁。
- 作者的 CLAUDE.md 已改為依附件十七章名，相關紀錄更新為「已解決」。

## 1.1.0 的變更

- 依權威順序重寫規則：每條規則標明來源；系辦的歧義（頁碼起點、行距範圍、摘要字數、「十位以下」）已決定並記錄依據；被推翻的朋友範本設定與 CLAUDE.md 設定列在 `rules.json` 的 `rejected`。
- 輸出符合 OOXML 元素順序（1.0.0 把 `w:rPr` 放在 `w:t` 後面，Microsoft Word 可能判為損毀）；寫檔前自我檢查，順序錯誤就不寫入。
- 封面、標題頁、口試委員會審定書依系辦範例產生；各自一頁、不編頁碼；誌謝為 i。
- 章號、圖表標題、目錄、行距、頁尾依系辦與朋友範本；頁尾距離改為 1.0 cm，避免撐大 2 cm 的下邊界。
- 支援 pandoc 引用鍵，依二.8 的例子產生正文引用與參考文獻清單。
- 稽核能讀 Word 的清單自動編號；自動顏色視為黑色；相同發現合併；檢查頁首頁尾高度、前置頁行距、章名、後置部分章號、目錄內容、封面與審定書欄位、數字與引用標點。
- 局部新增會沿用收件文件的標題與圖表標題樣式，並核對 Word 將顯示的編號。
- 設定鍵 `first_line_indent_cm` 改為 `first_line_indent_chars`（預設 2）；舊設定檔要改名，否則會被拒絕。

## 安裝

解壓後將整個 `bime-word` 資料夾放入其中一個位置，不要只複製 SKILL.md：

| 使用環境 | 專案內 | 個人全域 |
|---|---|---|
| Claude Code | `.claude/skills/bime-word/` | `~/.claude/skills/bime-word/` |
| Codex | `.agents/skills/bime-word/` | `~/.agents/skills/bime-word/` |

Claude Code 可用 `/bime-word`；Codex 可明確引用 `$bime-word`。也可以直接說「用 bime_word 檢查這份 Word」。安裝路徑與命名的官方技術來源見 `references/technical-sources.md`。

## 依賴與啟動

需要 Python 3.10+、python-docx、lxml；轉檔及新增還需要 **Pandoc**。僅執行 audit/inspect 不呼叫 Pandoc。執行過程不需要網路、付費 API 或 LLM API key。

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell：.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/bime_word.py doctor
```

使用 Conda 時，可在獨立環境安裝 `python lxml python-docx pandoc`（conda-forge 都有）。本版以 Pandoc 3.1.11.1 測試；其他版本先跑附帶測試。

可選視覺預覽需要 LibreOffice 與 Poppler 的 `pdftoppm`。**字型不包含在 ZIP**：目標 Word 應安裝標楷體（DFKai-SB）、細明體（MingLiU）及 Times New Roman。Linux fontconfig 找到替代字型不是字型合規證明。

## 三個功能

### 1. Markdown 轉 Word

```bash
python scripts/bime_word.py convert examples/chapter.md -o chapter.docx
python scripts/bime_word.py convert my-thesis.md -o thesis.docx --scope thesis --bibliography refs.json
```

`fragment` 適用於單章，不產生前置頁。`thesis` 產生封面、標題頁、審定書，分節編頁碼，並補上缺的目錄、圖目錄、表目錄。

- 章節：`# 前言` → 「第一章　前言」，`## 研究目的` → 「1.1 研究目的」；英文論文為「Chapter 1 Introduction」。兩個以上的「# 附錄」會改成附錄一、附錄二。
- 封面資料：Markdown 開頭的 YAML `bime:` 區塊（見 `examples/thesis-outline.md` 與 `references/workflows.md` C 節）。
- 圖表：寫「圖 1-1　標題」「表 1-1　標題」，表題在表前、圖題在圖後；輸出為「圖1-1」加定位字元，置中、不加粗。
- 引用：`[@key]`、`@key`、`[-@key]`、`[@a; @b]`、`[@key, commit abc1234]`。書目用 CSL-JSON 或 .bib（.bib 的標題以大括號保護大小寫）。清單放在 `{{REFERENCES}}`。正文要出現 @ 字元本身時寫成 `\@`，否則會被當成引用鍵。
- 行距：依全篇撰寫語言，中文 1.5 倍、英文 2 倍；自動判斷，或在設定檔寫 `language`。

生成四個檔：`chapter.docx`、`chapter.audit.json`、`chapter.audit.md`、`chapter.bime.json`。最後一個記錄語言、生成決策、書目缺欄與未引用條目。

目錄是 Word 欄位，而非計算完成的目錄；必須在 Word 更新並檢查。以純文字輸入的交互引用不會隨編號改變。

### 2. 局部新增

```bash
python scripts/bime_word.py inspect chapter.docx --output inspection.json
python scripts/bime_word.py insert chapter.docx --md examples/insert.md --under '第一章 前言' -o revised.docx --dry-run
python scripts/bime_word.py insert chapter.docx --md examples/insert.md --under '第一章 前言' -o revised.docx
```

`--before TEXT` / `--after TEXT` / `--under TEXT` / `--at-end` 四選一。匹配的是原檔最外層段落的完整文字（空白、定位字元、全形空格視為相同）；`--under` 是整段章節末端。`--occurrence 2` 指同文案第二次出現。表格儲存格不能當 anchor。

新增標題必須打出插入位置應有的章節編號。收件文件用清單自動編號時（例如朋友範本），新增標題與圖表標題沿用收件文件的樣式，打的編號交給 Word 自動產生；寫入前核對，不一致就拒絕。`--keep-bime-styles` 停用這項對應。原本的 Word 不經 Pandoc 重建，原 body 子樹逐一驗證未改動。

### 3. 唯讀檢查

```bash
python scripts/bime_word.py audit revised.docx --scope fragment --report check
python scripts/bime_word.py audit thesis.docx --scope thesis --report thesis-check --fail-on unresolved
```

輸出 `check.json` 與 `check.md`。逐項附規則 ID、實際／預期值、XML 位置、依據（系辦、朋友範本或 CLAUDE.md）、原文段落與採用的解讀。相同的發現合併並附次數與位置樣本。檢查檔案不修改原 DOCX。

| 類別 | 意義 |
|---|---|
| error | 系辦明文、確定適用的機器檢查發現不符 |
| warning | 原則或範例的偏離、不符採用的解讀，或啟發式疑似問題 |
| conflict | 保留給尚未決定的來源衝突（目前沒有） |
| unknown | 無法可靠解析有效格式或資訊 |
| manual | 必須閱讀語意、補證據或看實際版面 |

程式退出碼：`2` 是輸入、依賴或安全檢查失敗；audit 預設 `1` 表示有 error，`0` 只代表未命中該失敗門檻。`--fail-on warning` 加上 warning，`unresolved` 包含五類，`none` 不因發現退出 1。convert 即使退出 1 也可能已產出帶錯誤草稿；必須看報告。**退出 0 不等於全部條款合格。**

## 設定

從 `assets/defaults.json` 取需要的欄位另存成專案 profile；不用改 skill 本身。`--config profile.json` 覆蓋選定項，未知鍵拒絕。相對路徑以 profile 所在目錄為基準。

| 設定 | 預設 | 來源 |
|---|---|---|
| language | auto（依正文判斷全篇語言）；可設 zh／en | 系辦三.1；全篇一致依朋友範本 |
| font_zh / font_en | 標楷體 / Times New Roman | 系辦三.2 |
| heading_sizes_pt | 18, 14, 14, 12, 12, 12 | 朋友範本（第四層起為實作預設） |
| front_title_size_pt | 18 | 朋友範本 Title 樣式 |
| heading_separator | `.`（可改 `-`） | 系辦二.3 兩者皆可；朋友範本用 `.` |
| auto_number_headings | true | 實作選擇；insert 仍要求明確編號 |
| chapter_page_break | true | 朋友範本（每章換頁） |
| first_line_indent_chars | 2 | 朋友範本 |
| paragraph_after_pt | 0 | 朋友範本 |
| document_grid | true（每行 18 pt） | 朋友範本 |
| header_distance_cm | 1.5 | 朋友範本 |
| footer_distance_cm | 1.0（必須小於 2） | 系辦二.5 優先於朋友範本的 1.75 |
| page_number_size_pt | 10 | 朋友範本 |
| pagination_origin | acknowledgements（誌謝為 i）；可改 signature | 系辦條文與朋友範本；範例不同處見 ambiguities.md |
| title_page | same_as_cover；可改 omit | 實作預設（無來源給版面） |
| cover | false；true 時 fragment 也依系辦封面範例產生封面（讀 YAML `bime:`） | 系辦封面範例；用於計畫書是作者決定 |
| drop_todo | true：轉檔時略過 `[TODO: …]` | 作者決定 |
| shift_heading_level | 0；計畫書把 `#` 當文件標題時設 -1，`##` 成為章 | 實作選擇（proposal.md 的寫法） |
| bibliography | null（或 CSL-JSON／.bib 路徑） | CLAUDE.md 的引用鍵寫法 |
| pagination_confirmed | false | 只作紀錄：系辦或指導教授確認頁碼起點後設 true |
| role_overrides / section_roles | {} | 稽核的段落與分節分類覆寫；key 為 inspect 的 index |
| reference_manifest | null | 經核實的引用清單（逐字比對） |

`role_overrides` 和 `section_roles` 是針對原檔定位的稽核設定；插入後 indices 可能移位，必須重新 inspect 後更新。`examples/confirmed-profile.json` 只是「已獲確認時」如何填寫的示範，**不是你已經做出同意的證據**。

## 視覺覆核

```bash
python scripts/preview.py revised.docx --output-dir preview
```

輸出 PDF、每頁 PNG 和 `preview.json`；不得用非空的 preview 目錄混入舊頁。產生圖片後須真的逐頁看。preview.json 預設不標記已看過。Microsoft Word 中仍應更新全部必要欄位，核對目錄、頁碼、圖表與跨頁；替代字型的 LibreOffice 渲染不能證明目標字型及 Word 分頁一致。

## 測試與包裝驗證

```bash
python -m pip install -r requirements-test.txt
python -m pytest -q
python scripts/validate_skill.py
```

測試包括正常轉換、故意破壞格式、唯讀不變性、局部插入部件保留、註腳／圖片／編號合併、安全拒絕、OOXML 元素順序，以及 1.1.0 的權威順序行為（`tests/test_authority.py`）。`tests/ACCEPTANCE.md` 列出實際測試環境和未驗證項。

## 來源與權限

系辦附件原檔完整保存在 `references/source/` 並以 SHA-256 固定。朋友範本與 CLAUDE.md 沒有打包：前者只記錄採用的參數與 XML 證據（`references/friend-template.md`），後者逐字摘錄相關段落（`references/author-decisions.md`）。附件範例日期不是規範生效或更新日期；本包不宣稱已查證最新校系政策，也不把外部技術文件當成學校規定。原始附件與其中內容保留原權利狀態；本包沒有替附件宣告新的授權。沒有字型、API key 或你的實際論文內容。
