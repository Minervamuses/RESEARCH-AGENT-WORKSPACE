# C4-S2 Pandoc vs citeproc-js

- Pandoc 3.13 (citeproc Haskell library inside pandoc) vs citeproc-js 2.4.63 (npm `citeproc`), en-US locale from citation-style-language/locales `8bef426`.
- Styles: the four bundled CSL files (styles commit `205bf7b`). Corpus: `corpus.json` (16 cases). Strings compared after NFC and whitespace normalization; Pandoc output is plain text (italics dropped), citeproc-js output format `text`.
- Core categories: 作者清單/et al., 消歧, 排序/編號, locator.

| case | category | apa | modern-language-association | ieee | chicago-author-date |
|---|---|---|---|---|---|
| authors-1 | 作者清單/et al. | ✓ | ✓ | ✓ | ✓ |
| authors-2 | 作者清單/et al. | ✓ | ✓ | ✓ | ✓ |
| authors-3 | 作者清單/et al. | ✓ | ✓ | ✓ | ✓ |
| authors-8 | 作者清單/et al. | ✓ | ✓ | ✓ | ✓ |
| authors-21 | 作者清單/et al. | ✓ | ✓ | ✓ | ✓ |
| same-author-year | 消歧 | ✓ | ✓ | ✓ | ✓ |
| same-surname | 消歧 | ✓ | ✓ | ✓ | ✓ |
| institution | 作者清單/et al. | ✓ | ✓ | ✓ | ✓ |
| particle | 作者清單/et al. | ✓ | ✓ | ✓ | ✓ |
| no-year | 其他 | ✓ | ✓ | ✓ | ✓ |
| locator | locator | ✓ | ✓ | ✓ | ✓ |
| suppress-author | 其他 | ✓ | ✗ 其他 | ✓ | ✓ |
| multi-cite | 排序/編號 | ✓ | ✓ | ✓ | ✓ |
| numeric-order-range | 排序/編號 | ✓ | ✓ | ✓ | ✓ |
| title-case | 大小寫 | ✓ | ✓ | ✓ | ✓ |
| conference-doi-url | 其他 | ✓ | ✓ | ✓ | ✓ |

- 一致：63/64 組（樣式×案例）。
- **Pandoc 在核心類別的不一致數：0**。

## modern-language-association / suppress-author (citations 0, 其他)

- citeproc-js: `[NO_PRINTED_FORM]`
- Pandoc: ``

## 注意

- MLA 的 `[-@key]`（省略作者）在沒有頁碼時，Pandoc 輸出空字串，citeproc-js 輸出 `[NO_PRINTED_FORM]`；MLA 文中引用只有作者與頁碼，兩者都沒有可印的內容。不是核心類別；產品照 Pandoc。
- IEEE 的多篇引用兩個引擎都輸出 `[1], [2], [3], [4]`（此版 IEEE 樣式不合併成範圍），計劃中「[1]–[3]」的預期與官方樣式不同，以樣式為準。
- 重現：`node citeproc_js.js corpus.json <styles> locales-en-US.xml`（`NODE_PATH` 指向 `$TMPDIR` 的 `npm ci` 安裝），`python -I pandoc_run.py corpus.json <styles>`，`python -I compare.py`。
