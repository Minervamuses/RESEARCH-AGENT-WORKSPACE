# 人工與 agent 覆核流程

所有判斷依權威順序：系辦附件十七 > 朋友範本 > CLAUDE.md > 實作預設（[authority.md](authority.md)）。報告每條發現都標明依據；把朋友範本或 CLAUDE.md 的解讀轉述給使用者時，要說清楚那不是學校規定。

## A. 摘要

讀完整中文與英文，不只擷取首段。逐項定位研究目的、方法、結果、結論；比對對象、條件、數字、方向、限制與結論強度。指出哪一段缺項或兩語言不一致，而不是用「有這四個詞」代替內容檢查。

關鍵詞數量由程式初查，再看分隔方式是否真的代表獨立關鍵詞。列點檢測是疑似問題；確認是摘要中的條列而非文內編號提及。

長度採 CLAUDE.md 的解讀：中英文各自約 500–1000，中文算漢字、英文算單詞，超出只給 warning。三頁限制只有完成排版後才能判斷。

## B. 引用與參考文獻

### 轉檔時產生

Markdown 用 pandoc 引用鍵：`[@key]` 產生 (Smith, 1985)，`@key` 產生 Smith (1985)，`[-@key]` 只產生年份，所以 CLAUDE.md 的 `Walters and Wilder [-@key]` 會成為 Walters and Wilder (2023)。`[@a; @b]` 合併為一組括號，`[@key, commit abc1234]` 保留定位文字。

書目資料用 CSL-JSON（Zotero、Better BibTeX 可匯出）或 .bib（轉檔時以 pandoc 讀取；標題要用大括號保護大小寫，例如 `title={{Experimental Methods for Engineers}}`，否則 pandoc 會改成句首大寫）。以 `--bibliography refs.json` 或 Markdown 的 YAML `bibliography:` 指定。參考文獻清單放在 `{{REFERENCES}}` 段落；完整論文如果沒有這一段，會加在附錄之前。

格式依二.8(5)–(13) 的例子。需要的欄位：

| 類型（CSL type） | 欄位 |
|---|---|
| 期刊 `article-journal` | author、issued、title、container-title-short（查證過的 ISO 4 縮寫）、volume、issue、page |
| 圖書 `book` | author、issued、title、edition、page（引用頁數時）、publisher-place、publisher |
| 書之一部分 `chapter` | author、issued、title、container-title、editor、page、publisher-place、publisher |
| 論文集 `paper-conference` | 同上；editor 與 publisher-place 只在來源載明時填（CLAUDE.md） |
| 會議論文（無論文集） | genre（例如 ASAE Paper）、number、publisher-place、publisher |
| 學位論文 `thesis` | genre（碩士論文、PhD dissertation）、publisher-place、publisher（學校與系所） |
| 軟體 `software` | author（或機構）、version、publisher-place、publisher、URL |
| 網頁 `webpage` | author（或機構）、container-title、publisher（公司，不寫出版地）、URL、accessed |
| 專利 `patent` | number（例如 U.S. Patent No. 32455986） |
| 預印本 | DOI 或 number 含 arXiv 編號（CLAUDE.md：保持原樣） |
| 中文、日文條目 | `language: zh-TW`／`ja`；排序需要 `bime-strokes`（姓氏筆畫數，使用者查證） |

程式不填造欄位：未知的引用鍵、沒有年份的條目會讓轉檔停止；缺少的欄位列在 `.bime.json` 的 `references.missing_fields`。沒被引用的條目不列出（二.8(1)），並記在 `uncited`。

### 稽核既有文件

全文讀取正文引用及完整書目，建立對應，不把附件示例直接當使用者引用。兩作者用 and／與，三位以上（含三位）用 et al.／等人；作者數不能只看縮寫倒推，須有書目證據。程式會找出 “et al” 缺句點、英文引用用全形逗號、中文引用用半形逗號、「等」少了「人」、以 & 連接兩位作者等寫法。

清單只列正文確實引用者；中文、日文、英文依序，英文依姓氏字母，同一作者依年份。程式能檢查語言分組與英文姓氏順序；中文筆畫順序需要查證過的筆畫表，不得用 Unicode 排序冒充。

不要把 APA、IEEE、GB/T 或任意 CSL 當成替代。缺卷期、出版社、存取日期等實際資訊不可填造；先列缺資料，只有使用者授權外查才查證，並分開說明外查來源。`reference_manifest` 仍可用來做逐字的雙向比對（見 examples/reference-manifest.json）。

## C. 封面、審定書與目錄

完整論文（`--scope thesis`）的封面、標題頁與口試委員會審定書，由 Markdown 開頭的 YAML `bime:` 區塊產生：

```yaml
---
bime:
  degree: master            # master 或 doctoral
  title_zh: 論文中文題目
  title_en: English Title
  author_zh: 中文姓名
  author_en: English Name
  student_id: 學號
  advisor_zh: 指導教授姓名 博士
  advisor_en: Advisor Name, Ph.D.
  year_roc: 115             # 或 date: 2026-09
  month: 9
  defense_date: 2026-07-15  # 口試日期（西元），填入審定書
---
```

非完整論文（例如計畫書）在設定檔加 `"cover": true`，也用同一個 `bime:` 區塊產生封面（只產生封面，不產生標題頁與審定書）；封面不編頁碼，其後從 1 起編。

行序與字級依系辦範例（source-excerpts.md 末節）；缺的欄位寫成 `[TODO: …]` 並列在報告裡，不猜。審定書的簽名欄留白，程式不填造簽名或口試結果。標題頁沒有範例，預設與封面相同，須與使用者確認。

封面對照附件雙語欄位、作者、指導教授、學位及年月；簽名頁對照題目、姓名、學號、系所、口試日期及簽名位置。樣本的 109 年 7 月不是使用者日期，特殊頁不可用正文字級規則全頁覆蓋。

目錄、圖目錄、表目錄是 Word 欄位，必須在 Word 中更新（全選後 F9）並核對頁碼。目錄不收「目錄」本身，右上角有「頁數」。

## D. 圖表、數字與 SI

看每一圖／表，而非只數關聯檔。確認表題在上、圖題在下，跨頁仍清楚、內容自足、按章編號（程式會比對圖表的章號與所在章）、在文中提及的號碼真的存在。涉及大小的圖要看圖內是否有單位／尺度；照片原始來源需使用者證明或可核實來源，不能從清晰度判斷。

數字採 CLAUDE.md 的解讀：大於十用阿拉伯數字，十以下可用中文，混用不強制統一。程式以啟發式找出「十二位」「二十次」之類的寫法；引文、人名、成語、日期要人工判斷。

數值與單位看語意及量綱，非 SI 只作括號補充。原文列習見 m/kg/ppm/pH 不必另用中文；不要直接把 ppm 或 pH 當成未用中文的違規。

## E. 局部新增的限制

此版不提供刪除、取代、全篇修復或全域重新編號。原檔主文、既有樣式定義、節設定，以及未變動的圖片、頁首頁尾等部件受保留檢查；新增文字不保證物理頁面不變。

收件文件有標題樣式，或有以清單層級編號的圖表標題樣式（例如朋友範本的「圖內容」「表內容」）時，新增的標題與圖表標題改用收件文件的樣式，並移除 Markdown 裡打的編號，讓 Word 自己編；寫入前會計算 Word 將顯示的編號，與打的編號不同就拒絕寫入。因此插入新節前要先 inspect，打出插入位置應有的編號。後面的既有編號由 Word 自動更新；純文字的「見圖 2-3」不會跟著改。

沒有對應樣式時，新增內容使用隔離的 BIME 樣式。一般以大綱層級收錄的目錄會收進新標題；以樣式收錄的目錄或圖表目錄可能不含隔離樣式，須確認欄位收集規則。`--keep-bime-styles` 可強制使用隔離樣式。

Word 欄位的快取結果可能仍舊，updateFields 只是請求更新。文本框、浮動圖、合併儲存格、複雜表格條件樣式、特殊字體腳本、嵌入物件、外掛內容、特殊欄位都需要額外檢查。不支援 Strict namespace、舊式 .doc 或 .docm 巨集寫入。拒絕受保護／帶簽章／未接受修訂的寫入比破壞性繞過安全。

## F. 結果格式

先給操作完成與否，接著分明確問題、疑似偏離、已採用的解讀與人工項。每條帶文件位置、最小相關引用／數值、規則 ID、依據來源（系辦、朋友範本或 CLAUDE.md）、原因及可行處理。頁尾高度是由字級與行距推算的估計值，要說明是估計。未渲染不要編造頁碼；有渲染仍需核對實際頁面。

「無 error」只代表已執行檢查未發現硬錯，不能把 manual 或 unknown 算成通過。僅審查的任務不修原檔；需要新增的任務把新檔和報告交付，並說明既有問題是否仍存在。
