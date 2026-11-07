# bime_word 檢查報告

檔案：`/tmp/claude-1000/bime-e2e.xvcL/project/proposal.bime.docx`
SHA-256：`2b9406a73cb95fa42880bf4851e9c54608cf4192e682306d6f080659bf95ae70`
範圍：`fragment`；結果：`machine_checks_passed_review_required`

權威順序：系辦附件十七 > 朋友範本 > CLAUDE.md > 實作預設。只有系辦條文是學校規定；其餘來源用來補系辦沒寫清楚的地方，每條發現都標明依據。

這是 OOXML 與文字檢查，不是已完成 Word 視覺驗收。位置是 XML/段落定位，不冒充頁碼。

## 統計

error: 0 | warning: 0 | conflict: 0 | unknown: 0 | manual: 11

## 發現

### [manual] LINE_SPACING — document
Whole-document writing language is zh (profile); every prose paragraph, including acknowledgements and abstracts, is checked against 1.5 spacing (decision taken from the friend template).
依據：系辦附件十七；三.2；原始 DOCX 段落 P64；ambiguous。
採用的解讀（朋友範本）：依全篇撰寫語言（三.1「論文以中文或英文撰寫」）統一行距：中文論文全篇 1.5 倍，英文論文全篇 2 倍；前置頁的散文（誌謝、摘要）同樣適用。1.5 倍採 Word「多行 1.5」並保留文件格線（每行 18 pt）。

### [manual] PAGE_FORMAT — word/document.xml / section[2]
Front matter and body share a section; inspect field switches and the exact numbering boundary.
依據：系辦附件十七；二.4；原始 DOCX 段落 P12；explicit。

### [manual] CAPTION_COMPLETE — document
Judge whether each figure/table is independently understandable, including axes, units, and necessary explanation.
依據：系辦附件十七；二.3；原始 DOCX 段落 P11；explicit。

### [manual] NUMERAL — document
Heuristic only: numerals inside quotations, names, idioms and dates need reading in context.
依據：系辦附件十七；二.6(1)；原始 DOCX 段落 P15；ambiguous。
採用的解讀（CLAUDE.md）：大於十的數字用阿拉伯數字；十以下可用中文數字；同文混用不強制統一。稽核以啟發式找出大於十的中文數字，只給 warning。

### [manual] CITATION_FORM — document
Review author-year syntax, and two versus three-or-more authors. Citation keys and author counts cannot be proven from typography alone.
依據：系辦附件十七；二.8(4)；原始 DOCX 段落 P24；explicit。

### [manual] REF_CITED — document
No verified reference manifest supplied. Exact two-way citation matching is not claimed.
依據：系辦附件十七；二.8(1)；原始 DOCX 段落 P20；explicit。

### [manual] REF_TYPES — document
Apply the nine source-specific reference examples; do not substitute APA/IEEE or infer missing bibliographic facts.
依據：系辦附件十七；二.8(5)–(13)；原始 DOCX 段落 P25；example。
採用的解讀（CLAUDE.md）：依二.8(5)–(13) 範例為格式樣板；arXiv 預印本保持原樣（標 arXiv 編號）；網頁以公司為出版者、不寫出版地；會議論文集有來源載明時才列編者與地點；作者自己的 repository 以軟體條目列出，正文以 commit 作為定位。期刊名不用斜體（三個期刊範例中兩個未用斜體）。

### [manual] JOURNAL_ABBREVIATION — document
Check recognized journal abbreviations against supplied verified information; full ISO4/ASAE tables are not in this attachment.
依據：系辦附件十七；二.8(3)；原始 DOCX 段落 P22；explicit。
採用的解讀（CLAUDE.md）：只採用使用者在書目資料中提供並查證過的縮寫（container-title-short）；沒有就用全名並列入人工項。

### [manual] SI_UNITS — document
Check SI primacy, optional parenthetical non-SI units, and dimensions semantically.
依據：系辦附件十七；二.6(2)；原始 DOCX 段落 P16；explicit。

### [manual] TERMINOLOGY — document
Common symbols need no translation; judge terminology in context.
依據：系辦附件十七；二.6(3)；原始 DOCX 段落 P17；explicit。

### [manual] PUNCTUATION — document
Review punctuation in prose; tables, equations, and headings have different roles.
依據：系辦附件十七；三.2；原始 DOCX 段落 P64；explicit。

## 檢查覆蓋

| 規則 | 權威 | 狀態 | 機器檢查次數 |
|---|---|---|---|
| STRUCTURE | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| SPECIAL_PAGES | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| ABSTRACT_LENGTH | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| ABSTRACT_CONTENT | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| ABSTRACT_LIST | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| KEYWORDS | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| HEADING_NUMBER | 系辦附件十七 | machine_checked_with_manual_review | 19 |
| CAPTION_NUMBER | 系辦附件十七 | machine_checked_with_manual_review | 4 |
| CAPTION_POSITION | 系辦附件十七 | machine_pass | 4 |
| CAPTION_COMPLETE | 系辦附件十七 | manual | 0 |
| PAGE_FORMAT | 系辦附件十七 | machine_checked_with_manual_review | 2 |
| PAGE_ORIGIN | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| PAGE_POSITION | 系辦附件十七 | machine_checked_with_manual_review | 1 |
| MARGINS | 系辦附件十七 | machine_pass | 9 |
| NUMERAL | 系辦附件十七 | machine_checked_with_manual_review | 59 |
| SI_UNITS | 系辦附件十七 | manual | 0 |
| TERMINOLOGY | 系辦附件十七 | manual | 0 |
| PHOTO_ORIGIN | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| IMAGE_SCALE | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| REF_CITED | 系辦附件十七 | manual | 0 |
| REF_ORDER | 系辦附件十七 | machine_checked_with_manual_review | 42 |
| JOURNAL_ABBREVIATION | 系辦附件十七 | manual | 0 |
| CITATION_FORM | 系辦附件十七 | machine_checked_with_manual_review | 295 |
| REF_TYPES | 系辦附件十七 | manual | 0 |
| FONT_ZH | 系辦附件十七 | machine_pass | 233 |
| FONT_EN | 系辦附件十七 | machine_pass | 112 |
| FONT_SIZE | 系辦附件十七 | machine_pass | 385 |
| LINE_SPACING | 系辦附件十七 | machine_checked_with_manual_review | 59 |
| TEXT_COLOR | 系辦附件十七 | machine_pass | 385 |
| PUNCTUATION | 系辦附件十七 | manual | 0 |
| PAGE_SIZE | 系辦附件十七 | machine_pass | 2 |
| CHAPTER_NAMES | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| BACKMATTER_UNNUMBERED | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| TOC_CONTENT | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| COVER_CONTENT | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| SIGNATURE_CONTENT | 系辦附件十七 | not_applicable_to_selected_scope | 0 |
| WRITING_LANGUAGE | 系辦附件十七 | manual | 0 |
| HOUSE_TYPOGRAPHY | 朋友範本 | not_applicable_to_selected_scope | 0 |
| HOUSE_CAPTION | 朋友範本 | not_applicable_to_selected_scope | 0 |
| HOUSE_FOOTER | 朋友範本 | not_checked | 0 |
| AUTHOR_THESIS_PARTS | CLAUDE.md | not_applicable_to_selected_scope | 0 |
| CITATION_KEYS | CLAUDE.md | not_applicable_to_selected_scope | 0 |
