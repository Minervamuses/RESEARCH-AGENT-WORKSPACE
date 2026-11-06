# C5-S2 附件十七 CSL 與 bime_word 基準比對

- 樣式：`app/skills/citation/styles/bime-appendix17.csl`（ID `bime-appendix17`）。基準：`evidence/C5-S1/oracle.json`（論文 HEAD `59e9dc1` 的 `proposal.docx`）。渲染：`csl_render.render`（Pandoc 3.13）對 `$TMPDIR` 的 `proposal.md` + `references.json` 複本。
- 比較：NFC、空白正規化後逐字串相同才算一致。參考文獻依位置比較（同時檢查排序）；只出現在 TODO 註記中的 3 個 key 不在 docx，也不列入比較。

## 修正輪次

| 輪 | 改動 | 引用一致 | 參考文獻一致 |
|---|---|---|---|
| 1 | 初版（作者全列、名字縮寫、年。、`container-title-short`、`卷(期): 頁`、會議錄 In “…”, 頁. 編者, eds. 地: 出版者、網頁 Available at/Accessed、頁碼連字號、引號外逗號） | 46/46 | 30/42 |
| 2 | 排序鍵改為作者姓氏（不含名字） | 46/46 | 28/42（Lee/Lee 修正，但 Li/Liang 因標點被忽略而顛倒） |
| 3 | 主鍵改為第一作者姓氏、次鍵為全部作者姓氏 | 46/46 | 32/42 |
| 4 | 沒有 URL/DOI 時不印「Available at:」（以附件十七原文英文範例測試發現；論文語料不受影響） | 46/46 | 32/42 |

**最後一輪一致率**：引用 46/46（100%）；參考文獻 32/42（76%），排序 42/42 全對。

## 不一致的條目

### asai2026openscholar — 撇號 ' → ’；連字號名字 W.-t. → W.

- 基準：`Asai, A., J. He, R. Shao, W. Shi, A. Singh, J. C. Chang, K. Lo, L. Soldaini, S. Feldman, M. D'Arcy, D. Wadden, M. Latzke, J. Sparks, J. D. Hwang, V. Kishore, M. Tian, P. Ji, S. Liu, H. Tong, B. Wu, Y. Xiong, L. Zettlemoyer, G. Neubig, D. S. Weld, D. Downey, W.-t. Yih, P. W. Koh, and H. Hajishirzi. 2026. Synthesizing scientific literature with retrieval-augmented language models. Nature 650(8103): 857-863.`
- CSL：`Asai, A., J. He, R. Shao, W. Shi, A. Singh, J. C. Chang, K. Lo, L. Soldaini, S. Feldman, M. D’Arcy, D. Wadden, M. Latzke, J. Sparks, J. D. Hwang, V. Kishore, M. Tian, P. Ji, S. Liu, H. Tong, B. Wu, Y. Xiong, L. Zettlemoyer, G. Neubig, D. S. Weld, D. Downey, W. Yih, P. W. Koh, and H. Hajishirzi. 2026. Synthesizing scientific literature with retrieval-augmented language models. Nature 650(8103): 857-863.`

### gero2022sparks — 撇號 ' → ’

- 基準：`Gero, K. I., V. Liu, and L. Chilton. 2022. Sparks: Inspiration for Science Writing using Language Models. In “Designing Interactive Systems Conference (DIS '22)”, 1002-1019. New York, NY: ACM.`
- CSL：`Gero, K. I., V. Liu, and L. Chilton. 2022. Sparks: Inspiration for Science Writing using Language Models. In “Designing Interactive Systems Conference (DIS ’22)”, 1002-1019. New York, NY: ACM.`

### grattafiori2024llama3 — 截斷作者清單（literal "et al." 名字前多出 and）

- 基準：`Grattafiori, A., A. Dubey, A. Jauhri, A. Pandey, A. Kadian, A. Al-Dahle, A. Letman, A. Mathur, A. Schelten, A. Vaughan, et al. 2024. The Llama 3 Herd of Models. arXiv:2407.21783. Available at: https://doi.org/10.48550/arXiv.2407.21783.`
- CSL：`Grattafiori, A., A. Dubey, A. Jauhri, A. Pandey, A. Kadian, A. Al-Dahle, A. Letman, A. Mathur, A. Schelten, A. Vaughan, and et al. 2024. The Llama 3 Herd of Models. arXiv:2407.21783. Available at: https://doi.org/10.48550/arXiv.2407.21783.`

### jakesch2023cowriting — 撇號 ' → ’

- 基準：`Jakesch, M., A. Bhat, D. Buschek, L. Zalmanson, and M. Naaman. 2023. Co-Writing with Opinionated Language Models Affects Users' Views. In “Proceedings of the 2023 CHI Conference on Human Factors in Computing Systems”, 1-15. New York, NY: ACM.`
- CSL：`Jakesch, M., A. Bhat, D. Buschek, L. Zalmanson, and M. Naaman. 2023. Co-Writing with Opinionated Language Models Affects Users’ Views. In “Proceedings of the 2023 CHI Conference on Human Factors in Computing Systems”, 1-15. New York, NY: ACM.`

### karpukhin2020dpr — 連字號名字 W.-t. → W.

- 基準：`Karpukhin, V., B. Oguz, S. Min, P. Lewis, L. Wu, S. Edunov, D. Chen, and W.-t. Yih. 2020. Dense Passage Retrieval for Open-Domain Question Answering. In “Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)”, 6769-6781. B. Webber, T. Cohn, Y. He, and Y. Liu, eds. Stroudsburg, PA: Association for Computational Linguistics.`
- CSL：`Karpukhin, V., B. Oguz, S. Min, P. Lewis, L. Wu, S. Edunov, D. Chen, and W. Yih. 2020. Dense Passage Retrieval for Open-Domain Question Answering. In “Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)”, 6769-6781. B. Webber, T. Cohn, Y. He, and Y. Liu, eds. Stroudsburg, PA: Association for Computational Linguistics.`

### lala2023paperqa — 撇號 ' → ’

- 基準：`Lála, J., O. O'Donoghue, A. Shtedritski, S. Cox, S. G. Rodriques, and A. D. White. 2023. PaperQA: Retrieval-Augmented Generative Agent for Scientific Research. arXiv:2312.07559. Available at: https://doi.org/10.48550/arXiv.2312.07559.`
- CSL：`Lála, J., O. O’Donoghue, A. Shtedritski, S. Cox, S. G. Rodriques, and A. D. White. 2023. PaperQA: Retrieval-Augmented Generative Agent for Scientific Research. arXiv:2312.07559. Available at: https://doi.org/10.48550/arXiv.2312.07559.`

### lee2022coauthor — 撇號 ' → ’

- 基準：`Lee, M., P. Liang, and Q. Yang. 2022. CoAuthor: Designing a Human-AI Collaborative Writing Dataset for Exploring Language Model Capabilities. In “CHI Conference on Human Factors in Computing Systems (CHI '22)”, 1-19. New York, NY: ACM.`
- CSL：`Lee, M., P. Liang, and Q. Yang. 2022. CoAuthor: Designing a Human-AI Collaborative Writing Dataset for Exploring Language Model Capabilities. In “CHI Conference on Human Factors in Computing Systems (CHI ’22)”, 1-19. New York, NY: ACM.`

### lee2025critical — 名字中的括號暱稱 (Hank) 未去除

- 基準：`Lee, H.-P., A. Sarkar, L. Tankelevitch, I. Drosos, S. Rintel, R. Banks, and N. Wilson. 2025. The Impact of Generative AI on Critical Thinking: Self-Reported Reductions in Cognitive Effort and Confidence Effects From a Survey of Knowledge Workers. In “Proceedings of the 2025 CHI Conference on Human Factors in Computing Systems”, 1-22. New York, NY: ACM.`
- CSL：`Lee, H.-P. (Hank)., A. Sarkar, L. Tankelevitch, I. Drosos, S. Rintel, R. Banks, and N. Wilson. 2025. The Impact of Generative AI on Critical Thinking: Self-Reported Reductions in Cognitive Effort and Confidence Effects From a Survey of Knowledge Workers. In “Proceedings of the 2025 CHI Conference on Human Factors in Computing Systems”, 1-22. New York, NY: ACM.`

### lewis2020rag — 連字號名字 W.-t. → W.

- 基準：`Lewis, P., E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W.-t. Yih, T. Rocktäschel, S. Riedel, and D. Kiela. 2020. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. In “Advances in Neural Information Processing Systems 33 (NeurIPS 2020)”, 9459-9474. H. Larochelle, M. Ranzato, R. Hadsell, M. F. Balcan, and H. Lin, eds. Curran Associates, Inc.`
- CSL：`Lewis, P., E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela. 2020. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. In “Advances in Neural Information Processing Systems 33 (NeurIPS 2020)”, 9459-9474. H. Larochelle, M. Ranzato, R. Hadsell, M. F. Balcan, and H. Lin, eds. Curran Associates, Inc.`

### openai2023outage — 撇號 ' → ’

- 基準：`OpenAI. 2023. March 20 ChatGPT outage: Here's what happened. OpenAI. Available at: https://web.archive.org/web/20231229185333/https://openai.com/blog/march-20-chatgpt-outage. Accessed 6 October 2026.`
- CSL：`OpenAI. 2023. March 20 ChatGPT outage: Here’s what happened. OpenAI. Available at: https://web.archive.org/web/20231229185333/https://openai.com/blog/march-20-chatgpt-outage. Accessed 6 October 2026.`

## 無法以 CSL 表達的規則與理由

| 類別 | 條目數 | 理由 |
|---|---|---|
| 撇號 `'` 變成 `’` | 6 | CSL 處理器把直撇號換成排版撇號（Pandoc 與 citeproc-js 實測相同）；樣式沒有開關 |
| 連字號且小寫開頭的名字 `Wen-tau` → `W.` | 3 | 兩個處理器都只取第一段縮寫；bime_word 輸出 `W.-t.`；CSL 的 `initialize-with-hyphen` 無法改變這個行為 |
| 書目資料用 `{"literal": "et al."}` 表示截斷的作者清單 | 1 | CSL 把它當成一個名字，在前面加 `and`；樣式無法辨識特定的 literal |
| 名字含括號暱稱 `Hao-Ping (Hank)` | 1 | CSL 不能刪除名字中的部分文字；bime_word 會去掉括號內容 |

（2026-11-06 驗收後補充：各類的逐類實驗論證見 [C5-F2/inexpressible.md](../C5-F2/inexpressible.md)。結論應精確表述為「無法以**樣式**表達」：B、C、D 三類可由改資料消除，A 類需在 CSL 之外處理。）

這四類都來自處理器或資料形狀，不是附件十七的格式規則本身；依 D3 不改走 `cite.py`、不改使用者的 `references.json`。若使用者願意改資料，後三類可由資料修正（`Wen-tau` 可寫成縮寫 `W.-t.`、截斷清單可改成完整作者、暱稱移到 `note`）。

## 附件十七原文英文範例

`app/tests/test_citation_appendix17.py` 以二.8 的英文範例（期刊 (a) Anderson、會議錄 (8) Miller、網站 NSC、軟體 SAS、博士論文 Campbell）與 (4) 的文中引用形式為預期，全部一致；唯一差異是 SAS 例子的 `User's` 會輸出為 `User’s`（同上撇號類別，測試以實際輸出為準）。

## 使用者決定 D10、D11 之後（2026-11-06，C5-F3、C5-F4）

依使用者決定，四類差異都在渲染時的書目副本中，套用與 bime_word 相同的規則處理；`.csl` 只多一個判斷截斷清單的分支，書目檔不被改寫：

- 直撇號：用不會被 Pandoc 轉換、排序時視為可忽略標點的佔位字元保護，輸出後換回 `'`。
- `Wen-tau` → `W.-t.`；去掉名字中的 `(暱稱)`。
- 資料中以 `{"literal": "et al."}` 結尾的作者清單：在副本中移除該名字並標記，樣式以不加 and、結尾 `et al.` 的形式輸出。

重跑 `compare_appendix17.py`：**引用 46/46、參考文獻 42/42**（`comparison.json` 為最新結果）。
