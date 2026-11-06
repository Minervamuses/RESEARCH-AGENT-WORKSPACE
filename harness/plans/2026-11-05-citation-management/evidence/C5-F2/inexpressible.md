# C5-F2 附件十七剩餘差異：逐類論證

C5-S2 把 10 條不一致歸為四類，並寫「無法以 CSL 表達」。驗收審查指出：「有 10 條不一致」已確認，但「這 10 條全部無法以 CSL 表達」需要逐類論證。本檔以實驗回答兩個問題：

1. **改樣式**（`.csl`）能不能消除這一類差異？
2. 如果不能，**改資料**（`references.json`）或**在 CSL 之外處理**能不能消除？

## 方法

- `probe_inexpressible.py` 為每一類寫出只含相關機制的最小樣式，用 Pandoc 3.13（產品引擎）與 citeproc-js 2.4.63（參考基準）各渲染一次，輸出存在 `probe-results.json`。
- 最小樣式把無關因素排除：例如 A 類的樣式只輸出 `title` 變數本身，沒有任何格式屬性。
- 「改資料」的變體只用來說明可行的替代做法。依規定，本計劃不修改你的 `references.json`。
- 結論只限於 CSL 1.0.2 提供的機制：格式屬性（`font-*`、`text-decoration`、`vertical-align`、`text-case`、`quotes`、`strip-periods`、affixes）、名字選項（`initialize*`、`and`、`delimiter-*`、`et-al-*`、`name-part`）、條件（`cs:if` 只能測 type、變數有無、is-numeric、is-uncertain-date、locator、position、disambiguate）。CSL 沒有字串取代、子字串或依名字內容判斷的機制。

## A. 直撇號 `'` 變成 `’`（6 條：asai2026openscholar、gero2022sparks、jakesch2023cowriting、lala2023paperqa、lee2022coauthor、openai2023outage）

| 變體 | Pandoc | citeproc-js |
|---|---|---|
| 樣式只輸出 `<text variable="title"/>`（沒有任何格式屬性） | `Users’ Views` | `Users’ Views` |
| 加上 `quotes="false"` | `Users’ Views` | `Users’ Views` |
| 資料本身已是 `’` | `Users’ Views` | `Users’ Views` |

- **結論：樣式無法表達。** 樣式什麼都不做、只輸出原始變數時，撇號已經被換掉。這表示替換發生在處理器讀取或輸出文字的階段，不在樣式內。CSL 只能增加格式，沒有屬性能把 `’` 換回 `'`。
- **CSL 之外**：可以在渲染流程中處理。例如沿用 C5-F1 的暫存副本機制，先用佔位字元保護直撇號，渲染後再換回；或直接取代輸出中的 `’`，但後者也會改到資料中原本就是 `’` 的字元。這是排版選擇而不是附件十七的規則：附件十七的範例是一般文字，沒有規定撇號形狀。目前保留排版撇號，**列為使用者決定**。

## B. 小寫開頭的連字號名字 `Wen-tau` → `W.`（3 條：asai2026openscholar、karpukhin2020dpr、lewis2020rag，作者都是 Wen-tau Yih）

| 變體 | Pandoc | citeproc-js |
|---|---|---|
| `initialize-with=". "`、`initialize-with-hyphen` 預設 true | `Yih, W.`／`Godard, J.-L.` | 相同 |
| `initialize-with-hyphen="false"` | `Yih, W.` | 相同 |
| `initialize-with="."` | `Yih, W.` | 相同 |
| `initialize="false"` | `Yih, Wen-tau` | 相同 |
| **資料**：given 寫成 `W.-t.` | `Yih, W.-t.` ✓ | `Yih, W. -t.` |

- **結論：樣式無法表達。** 兩個處理器只縮寫大寫開頭的連字號部分：`Jean-Luc` 會變成 `J.-L.`，`Wen-tau` 的小寫 `tau` 則被丟掉。所有縮寫選項都得不到 `W.-t.`；不縮寫又會得到全名。
- **改資料**：把 given 寫成 `W.-t.`，產品引擎 Pandoc 就輸出正確的 `W.-t.`。citeproc-js 會多一個空白，但它不是產品引擎。

## C. 以 `{"literal": "et al."}` 表示資料中被截斷的作者清單（1 條：grattafiori2024llama3）

| 變體 | 截斷清單（10 人 + literal） | 一般的 12 人清單 |
|---|---|---|
| `and="text"`、`delimiter-precedes-last="always"`（目前樣式） | `…, A. F10, and et al.` ✗ | `…, A. F11, and A. F12` ✓ |
| 不用 `and` | `…, A. F10, et al.` ✓ | `…, A. F11, A. F12` ✗（少了 `and`） |
| `et-al-min="11"`、`et-al-use-first="10"` | `…, A. F10, et al.` ✓ | `…, A. F10, et al.` ✗（截斷真實作者） |

（兩個處理器結果相同。）

- **結論：樣式無法表達。** CSL 會把 literal 名字當成一般名字。條件也沒有任何一項能檢查名字內容，所以無法只在「最後一個名字是 et al.」時拿掉 `and`。能讓這一條正確的兩種全域設定，都會弄壞其他條目：
  - 拿掉 `and` 會讓所有一般作者清單少了 `and`。
  - `et-al-min=11` 會截斷所有 11 人以上的真實清單。本論文引用的條目中有 6 筆是 11 人以上：asai2026openscholar 28、liu2024agentbench 22、liang2024mapping 14、wang2024autosurvey 13、lewis2020rag 12，以及 grattafiori2024llama3 本身（10 + literal）。這違反附件十七「作者全列」的範例。
- **改資料**：列出完整作者。你在 asai2026openscholar 的 note 中已用過這個做法（「依附件十七範例列出全部作者」）。若要保留截斷，就沒有純樣式的解法。

## D. 名字中的括號暱稱 `Hao-Ping (Hank)`（1 條：lee2025critical）

| 變體 | Pandoc | citeproc-js |
|---|---|---|
| `initialize-with=". "` | `Lee, H.-P. (Hank).` | 相同 |
| `initialize-with="."` | `Lee, H.-P.(Hank).` | 相同 |
| `name-part given text-case="lowercase"`（name-part 只能改大小寫與格式） | `Lee, h.-p. (hank).` | 相同 |
| **資料**：given 改成 `Hao-Ping`、暱稱移到 note | `Lee, H.-P.` ✓ | ✓ |

- **結論：樣式無法表達。** CSL 沒有刪除字串的機制，`(Hank)` 會被當成一個名字片段保留下來。
- **改資料**：在兩個引擎都正確。

## 總結

| 類別 | 條數 | 改樣式 | 改資料 | CSL 之外 |
|---|---|---|---|---|
| A 撇號 | 6 | 不能（樣式只輸出原始變數時已被換掉） | 不能 | 可以：渲染流程中保護或取代撇號（使用者決定） |
| B `Wen-tau` | 3 | 不能（所有縮寫選項都試過） | 可以（`W.-t.`，Pandoc 正確） | — |
| C 截斷清單 | 1 | 不能（兩種全域解法都會弄壞其他條目） | 可以（列出完整作者） | — |
| D 暱稱 | 1 | 不能（CSL 沒有字串刪除） | 可以（暱稱移到 note） | — |

所以 C5-S2 的「無法以 CSL 表達」，精確地說是**無法以樣式表達**。四類都有實驗支持。改資料可以完全消除 karpukhin2020dpr、lewis2020rag、grattafiori2024llama3、lee2025critical 這 4 條；asai2026openscholar 改資料後只剩 A 類的撇號。A 類 6 條需要在 CSL 之外處理。依計劃規定，兩種做法都沒有自動執行，列入最終彙報由你決定。

## 後續（2026-11-06，使用者決定 D10、D11）

使用者選擇消除這四類差異。依上表，它們都不能只靠樣式消除，所以在渲染時的書目副本中處理，書目檔不被改寫（C5-F3、C5-F4）：

- A 撇號：佔位字元方法。
- B：在副本中把 `Wen-tau` 預先縮寫成 `W.-t.`。
- C：在副本中移除結尾的 literal 並設定旗標，樣式只多一個依旗標輸出的分支。
- D：在副本中去掉暱稱。

B、C、D 原本建議「改資料」，實作改在副本中處理，原因：

- 不會失去完整名字。
- 以後新增的條目也適用。
- 不必寫入論文資料夾。
- C 類若列出完整作者，Llama 3 論文有數百位作者，輸出反而會與 bime_word 的截斷形式不同；本檔先前「列出完整作者即可」的建議對這一條並不正確。

論文比對因此為參考文獻 42/42。
