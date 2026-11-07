# 規則索引

權威順序：**系辦附件十七 > 朋友範本 > CLAUDE.md > 實作預設**（見 [authority.md](authority.md)）。只有「系辦」列是學校規定；「決定」欄表示系辦原文模糊或衝突時，採用的解讀來自哪一層。P# 是原始 DOCX 主文段落的 1-based 索引，不是頁碼；逐字摘錄和原檔供回查。

系辦來源 SHA-256：`89721138dda00df0c4d07ee826f128ad83fc5f2771d887a84cdbdf8777abfdc6`
朋友範本 SHA-256：`6ab7ee5aa6198e4698708904001db68ad9575124392c3a8606eac31540f0e880`（未打包，證據見 [friend-template.md](friend-template.md)）
CLAUDE.md：commit `38f76bf`（摘錄見 [author-decisions.md](author-decisions.md)）

| ID | 權威 | 來源／原段落 | 性質 | 檢查方式 | 決定 | 內容 |
|---|---|---|---|---|---|---|
| STRUCTURE | 系辦 | 一 / P6 | explicit | mixed | 朋友範本 | 論文組成、順序；中文摘要在英文摘要之前 |
| SPECIAL_PAGES | 系辦 | 二.1 / P9 | example | manual | 系辦 | 封面、標題頁、簽名頁與目錄參考範例 |
| ABSTRACT_LENGTH | 系辦 | 二.2 / P10 | ambiguous | manual | CLAUDE.md | 約500–1000字、不超過三頁：計算方式未說明（見 decision） |
| ABSTRACT_CONTENT | 系辦 | 二.2 / P10 | explicit | manual |  | 目的、方法、結果、結論；中英內容一致 |
| ABSTRACT_LIST | 系辦 | 二.2 / P10 | explicit | heuristic |  | 摘要不採條列 |
| KEYWORDS | 系辦 | 二.2 / P10 | explicit | deterministic |  | 中英文各3–5個關鍵詞 |
| HEADING_NUMBER | 系辦 | 二.3 / P11 | explicit | mixed |  | 章節編號可用1.1或1-1 |
| CAPTION_NUMBER | 系辦 | 二.3 / P11 | explicit | mixed |  | 圖表按章分別編號 |
| CAPTION_POSITION | 系辦 | 二.3 / P11 | explicit | deterministic |  | 表標題在上，圖標題在下 |
| CAPTION_COMPLETE | 系辦 | 二.3 / P11 | explicit | manual |  | 每個表格、圖片有獨立完整內容 |
| PAGE_FORMAT | 系辦 | 二.4 / P12 | explicit | mixed |  | 正文前小寫羅馬字，正文阿拉伯字 |
| PAGE_ORIGIN | 系辦 | 二.4 vs 目錄範例 / P12 | conflict | manual | 朋友範本 | 條文誌謝 i 與範例審定書 i、誌謝 ii 衝突（見 decision） |
| PAGE_POSITION | 系辦 | 二.4 / 二.5 / P12 | explicit | mixed |  | 頁碼在每頁底部中央 |
| MARGINS | 系辦 | 二.5 / P13 | explicit | deterministic | 朋友範本 | 上3cm、下2cm、左右各3cm；頁首頁尾不可撐大邊界 |
| NUMERAL | 系辦 | 二.6(1) / P15 | ambiguous | manual | CLAUDE.md | 「十位以下」語意不明；採用大於十用阿拉伯數字（見 decision） |
| SI_UNITS | 系辦 | 二.6(2) / P16 | explicit | manual |  | SI主要；其他單位於括號；ASAE未附完整內容 |
| TERMINOLOGY | 系辦 | 二.6(3) / P17 | explicit | manual |  | 習見符號無須譯名；無適當譯名用原文 |
| PHOTO_ORIGIN | 系辦 | 二.7 / P18 | explicit | manual |  | 原始攝影、學術或說明價值 |
| IMAGE_SCALE | 系辦 | 二.7 / P18 | explicit | manual |  | 涉及大小時嵌入大小單位標示 |
| REF_CITED | 系辦 | 二.8(1) / P20 | explicit | mixed |  | 列表僅收錄正文實際引用的文獻 |
| REF_ORDER | 系辦 | 二.8(2) / P21 | explicit | mixed |  | 中、日、英歐；筆畫或字母；同作者按年 |
| JOURNAL_ABBREVIATION | 系辦 | 二.8(3) / P22 | explicit | manual | CLAUDE.md | 可縮寫者採學術通用縮寫；不可猜ISO4縮寫 |
| CITATION_FORM | 系辦 | 二.8(4) / P24 | explicit | mixed |  | 作者年份；兩人and/與；三人含以上et al./等人 |
| REF_TYPES | 系辦 | 二.8(5)–(13) / P25 | example | manual | CLAUDE.md | 九種文獻類型分別核對；範例不等於所有欄位硬性必填 |
| FONT_ZH | 系辦 | 三.2 / P64 | principle | deterministic | 系辦 | 中文以12號楷書；細明體及標楷體為主 |
| FONT_EN | 系辦 | 三.2 / P64 | principle | deterministic |  | 英文12號Times New Roman |
| FONT_SIZE | 系辦 | 三.2 / P64 | principle | deterministic |  | 正文12pt；不套用所有標題、封面 |
| LINE_SPACING | 系辦 | 三.2 / P64 | ambiguous | mixed | 朋友範本 | 中文 1.5、英文雙行；中英混排與適用範圍未說明（見 decision） |
| TEXT_COLOR | 系辦 | 三.2 / P64 | explicit | deterministic |  | 正文字色黑色 |
| PUNCTUATION | 系辦 | 三.2 / P64 | explicit | manual |  | 文內要加標點 |
| PAGE_SIZE | 系辦 | 四.1 / P67 | principle | deterministic |  | A4原則 |
| CHAPTER_NAMES | 系辦 | 一 / 目錄範例 / P6 | explicit | heuristic | 系辦 | 正文各章對應前言、文獻探討、材料與方法、結果與討論、結論；系辦範例本身用過其他章名，故不符只給 warning。 |
| BACKMATTER_UNNUMBERED | 系辦 | 二.1 目錄範例 / P152 | example | deterministic |  | 參考文獻與附錄不編章號；多個附錄依範例寫附錄一、附錄二。 |
| TOC_CONTENT | 系辦 | 二.1 目錄範例 / P152 | example | mixed |  | 目錄收錄前置頁、各章、節、參考文獻與附錄，不收錄「目錄」本身；右上標「頁數」。 |
| COVER_CONTENT | 系辦 | 二.1 / 四.4 封面範例 / P111 | example | mixed |  | 封面依範例行序；系名與學位 18 pt、英文系院 14 pt、National Taiwan University 與 Master Thesis 16 pt、題目、姓名、指導教授與日期 18 pt，置中、1.5 倍行距。 |
| SIGNATURE_CONTENT | 系辦 | 二.1 / 四.4 第一頁範例 / P132 | example | mixed |  | 審定書依範例：24 pt 校名學位、26 pt 標題、20 pt 題目、16 pt 內文與簽名欄；不填造簽名或口試結果。 |
| WRITING_LANGUAGE | 系辦 | 三.1 / P63 | principle | mixed |  | 撰寫語言決定三.2 的行距（中文 1.5、英文雙行）。 |
| HOUSE_TYPOGRAPHY | 朋友範本 | friend_template styles.xml / — | house | manual |  | 系辦未規定的標題字級、首行縮排與頁碼字級，依朋友範本：章標題 18 pt 粗體置中、節標題 14 pt 粗體、前置頁標題 18 pt 粗體置中、正文首行縮排兩字、頁碼 10 pt。只用於產生，稽核不當成系辦規定。 |
| HOUSE_CAPTION | 朋友範本 | friend_template numbering.xml / styles.xml / — | house | manual |  | 圖表標題寫成「圖1-1」（無空格）＋定位字元＋標題，置中、不加粗；圖片段落置中並與標題同頁。 |
| HOUSE_FOOTER | 朋友範本 | friend_template footer2.xml / sectPr / — | house | deterministic |  | 頁碼 10 pt 置中；頁首距離 1.5 cm 沿用朋友範本；頁尾距離改為 1.0 cm，且頁碼下不留空段落，避免撐大 2 cm 的下邊界（二.5 優先於朋友範本）。 |
| AUTHOR_THESIS_PARTS | CLAUDE.md | CLAUDE.md Page format / — | author | mixed |  | 完整論文應有圖目錄、表目錄與符號說明（系辦目錄範例與朋友範本也有）。 |
| CITATION_KEYS | CLAUDE.md | CLAUDE.md In-text citation / — | author | deterministic |  | Markdown 以 pandoc 引用鍵撰寫；轉檔時依書目資料產生二.8(4) 的作者年份格式；英文作者一律用 and／et al.，中文作者用與／等人。 |

## 性質欄

explicit：明文；principle：原則；ambiguous：含義未定；conflict：來源互相衝突；example：示例；house：朋友範本的做法；author：CLAUDE.md 的決定。這是來源強度，不等於工具已完整驗證。即使檢查方式寫 deterministic，特殊物件或讀取不到的有效值也須回報 unknown／manual。

## 嚴重度

- error：系辦明文、確定適用的機器檢查發現不符。
- warning：原則或範例的偏離、依朋友範本或 CLAUDE.md 採用的解讀不符，或啟發式疑似問題。
- unknown：無法可靠解析有效格式。
- manual：必須閱讀語意、補證據或看實際版面。
- conflict：保留給系辦來源之間尚未決定的衝突；目前的衝突都已依權威順序決定，所以正常情況不會出現。

朋友範本的字級、縮排等「house」規則只用來產生文件，稽核不把它們當成規定，也不會因為文件的標題字級不同就回報。需要精確原句，直接查看 rules.json 的 quote；不要從上表簡述擴張成來源沒有的規定。
