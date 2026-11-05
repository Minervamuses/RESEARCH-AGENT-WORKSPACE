# C5 附件十七樣式

- **後置條件**：`app/skills/citation/styles/` 有自訂的附件十七 `.csl`，列在樣式清單中；它在論文語料上的輸出已與 bime_word 產生的 `proposal.docx` 逐條比對；CSL 能表達的差異都已修正，不能表達的逐項列出。
- **目標**：CG6、CG4。決策 D3（不改走 `cite.py`）。規則見 [context/appendix17-references.md](../context/appendix17-references.md)。
- **相依**：C4（樣式清單與渲染模組）。

## 輸入（唯讀）

全部從使用者論文 repo 的 HEAD 取得，放在 `$TMPDIR`，不寫回、不提交正文：
- `git -C /home/minervamuses/論文 show HEAD:proposal.md`、`HEAD:references.json`、`HEAD:proposal.docx`、`HEAD:regulations.docx`。
- 工作區有使用者未提交的修改（例如 `proposal.docx`）；一律以 HEAD 為準，並記錄所用的 HEAD SHA。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C5-S1 | **建立基準**。用標準函式庫（`zipfile` + XML）從 `proposal.docx` 取出參考文獻段落（「參考文獻」標題之後的段落）與正文中的引用字串。正文引用的對齊方式：把 `proposal.md` 每個含引用的段落以 Pandoc 轉成純文字，與 docx 對應段落比較，取出引用位置的文字。記錄條目數與引用數 | `evidence/C5-S1/oracle.json`：參考文獻條目字串（依 docx 順序）與每個引用 key 群組對應的 docx 字串；條目數等於 proposal 實際引用的不同作品數；無法對齊的引用列出 key，不猜測 |
| C5-S2 | **撰寫 `.csl` 並比對**。以 `chicago-author-date.csl` 或其他最接近的作者年制樣式為起點，依附件十七 二.8 與使用者的格式決定修改：作者全列、名字縮寫、「年。」位置、期刊名用 `container-title-short`（ISO 4 縮寫）、卷期頁 `23(2): 34-42`、會議錄的編者與地點、網頁的「Available at」「Accessed」等。正文引用：(Smith, 1985)、(Smith and Kline, 1968)、三人以上 et al.、同作者同年 a/b。逐條比對 C5-S1 基準，修正後重跑，直到剩下的差異都屬於 CSL 或 Pandoc 表達不了的類別 | `evidence/C5-S2/compare.md`：每條參考文獻與每個引用「一致/不一致」，不一致者附兩邊字串與類別；最後一輪的一致率；列出無法表達的規則與理由 |
| C5-S3 | **中日文規則的合成測試**。論文語料沒有任何中日文條目，所以另建合成條目（依 二.8 的例子：田秉才等、張福祥與盧福明、邱奕志的碩士論文等），以附件十七原文為預期：中文三人以上（陳等人，1989）、二人（林與張，1960）、全形標點、中文在前（筆畫）、日文其次、英文最後。若需要條目帶 `language` 欄位才能切換，只在合成條目上加，並記錄「使用者既有條目沒有此欄位」這個限制 | `evidence/C5-S3/`：每個中日文規則「達成/無法以 CSL 表達/部分達成」，附輸出字串；結論寫入最終彙報 |

## 失敗與恢復

- docx 基準對齊不到某些引用：只比對對得到的，列出對不到的 key，不放寬比對規則。
- 某規則確定無法以 CSL 表達：依 D3 不改走 `cite.py`，只記錄；不更改使用者的 `references.json`。

## 交付給後續階段

附件十七樣式的 ID（建議 `bime-appendix17`）與已知限制清單。
