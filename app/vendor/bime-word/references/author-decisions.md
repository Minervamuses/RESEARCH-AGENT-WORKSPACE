# CLAUDE.md 的作者決定（逐字摘錄）

來源：作者論文 repository 的 `CLAUDE.md`，git commit `38f76bf`，2026-09-30 讀取；章名一條於同日改寫（commit `7317bbf`），見下方。以下是與論文格式有關的段落原文。權威低於系辦附件十七與朋友範本；三者衝突時的處理見 [authority.md](authority.md)。

> - **Cover** (proposal and thesis): 國立臺灣大學生物資源暨農學院生物機電工程學系; Department of Biomechatronics Engineering / College of Bioresources and Agriculture / National Taiwan University; author name in Chinese and English; advisor as 指導教授／Advisor; date as 中華民國○年○月 Month Year.
> - **Numbering**: sections 1.1 or 1-1; figures and tables numbered by chapter (圖1-1, 表1-1). Table caption goes above the table, figure caption below; each must be self-contained.
> - **Numerals and units**: numbers above ten in Arabic numerals (Chinese numerals below ten are allowed, mixing is left as is); SI units; terms without a fitting translation stay in the original language.
> - **In-text citation**: (Smith, 1985), Smith (1985), (Smith and Kline, 1968), (Smith, 1985; Wang and Lin, 1992); three or more authors: (Smith et al., 1990) for English, (陳等人，1989) for Chinese. Write English names in narrative citations as `Name et al. [-@key]`, not with Chinese connectives.
> - **Reference list**: only works cited in the text; Chinese by stroke count, then Japanese, then English alphabetical by surname; same author by year; journal names ISO 4 abbreviated; journal, book, chapter, proceedings, thesis, software, website and patent formats are given in the appendix. Author decisions: arXiv preprints are left as they are (no appendix category); web pages get the company as publisher and no place of publication; proceedings entries carry editors and place where a source states them (ACL Anthology, Crossref, NeurIPS pages); the author's own repositories are cited as software entries with commit hashes as pinpoints in the text.
> - **Typesetting** (decided at conversion): Chinese 12 pt 標楷體 at 1.5 line spacing, English 12 pt Times New Roman at double spacing, black text, front matter in lowercase Roman numerals, body in Arabic; single-sided printing is allowed at 80 pages or fewer.
> - **Thesis-only parts**: signature page, acknowledgements, Chinese then English abstract (500–1000 words each, no lists, 3–5 keywords), lists of figures and tables, symbol list.
> - **Chapter names do not follow Appendix 17.** The appendix lists 前言／文獻探討／材料與方法／結果與討論／結論; the author decided the DSR spine above takes precedence, so keep 緒論 and the separate results and discussion chapters.

2026-09-30 改寫後（commit `7317bbf`）：

> - **Chapter names follow Appendix 17**: 前言／文獻探討／材料與方法／結果與討論／結論 (decided 2026-09-30; this replaces the earlier decision to keep the DSR chapter names). *Thesis structure* above shows where each part of the DSR spine goes.

## 在本 skill 的去向

| 決定 | 狀態 | 用在哪裡 |
|---|---|---|
| 封面欄位 | 與系辦範例相同 | 封面產生器 |
| 大於十用阿拉伯數字 | 採用（系辦「十位以下」語意不明） | 稽核 NUMERAL |
| 引用格式與 `Name et al. [-@key]` | 採用 | `cite.py` 的正文引用 |
| arXiv、網頁、會議論文集、自己的 repository | 採用（系辦沒有這些類別或細節） | `cite.py` 的參考文獻條目 |
| 期刊名 ISO 4 縮寫 | 採用，只用使用者提供的縮寫 | `container-title-short` |
| 摘要各 500–1000 | 採用（系辦沒說明計算方式） | 稽核 ABSTRACT_LENGTH |
| 圖目錄、表目錄、符號說明 | 採用（與系辦目錄範例、朋友範本一致） | 轉檔補頁、稽核 AUTHOR_THESIS_PARTS |
| 行距、字型、頁碼格式 | 與系辦相同 | 轉檔與稽核 |
| 80 頁以下可單面印刷 | 記錄，不在 Word 格式範圍 | — |
| 章名 | 原本的 DSR 章名不採用（系辦與朋友範本權威較高）；CLAUDE.md 已改為依附件十七，與系辦一致 | 稽核 CHAPTER_NAMES |
