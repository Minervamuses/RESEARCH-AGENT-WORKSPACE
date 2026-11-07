# bime_word 1.1.5 驗收紀錄

驗收日期：2026-09-30。這是本包的執行結果，不是對所有 Word 檔的格式認證。

## 實際執行

`python -m pytest -q`：**88 passed**（`tests/test_bime_word.py` 57 項、`tests/test_authority.py` 31 項）。1.1.5（2026-10-13）新增 `test_fragment_cover_opt_in`，同一環境重跑全數通過。Pandoc 3.12.1 下有 3 項既有測試失敗（1.1.4 原包同樣失敗），驗收以 3.1.11.1 為準。

環境：Linux（WSL2）；Python 3.12.14；python-docx 1.2.0；lxml 6.1.3；Pandoc 3.1.11.1；pytest 9.1.1；Pillow 12.3.0（conda-forge 隔離環境）。Python 3.10、3.11、3.13、Windows、macOS 與宿主 agent 的實際安裝／自動觸發沒有在這次環境逐一測試。

另外執行 `doctor`、`validate_skill.py`，以及下列 CLI 操作。

## OOXML 結構驗證

以外部的 OOXML XSD 驗證器（Claude 的 docx skill 內附 `scripts/office/validate.py`，不隨本包發佈）檢查輸出，全部通過：

| 輸出 | 操作 |
|---|---|
| examples/chapter.md | convert（fragment） |
| examples/thesis-outline.md | convert（thesis，封面資料缺，寫入 [TODO]） |
| examples/citations.md + examples/refs.json | convert（引用與參考文獻清單） |
| 含封面資料、十種書目類型、圖、表、兩個附錄的測試論文 | convert（thesis） |
| 作者 proposal.md 與 references.json（71 筆書目，`bime-proposal-profile.json`） | convert（fragment）：0 error，唯一 warning 為 26 處 [TODO] |
| chapter.docx + examples/insert.md | insert（`--under`） |
| 朋友範本 論文格式.docx + 新增 4.1 節與圖 4-2 | insert（沿用收件文件的清單編號） |

1.0.0 的輸出在同一個驗證器下失敗（`w:rPr` 在 `w:t` 之後、`w:snapToGrid` 在 `w:spacing` 之後、`w:updateFields` 位置錯）。1.1.0 另在每次寫檔前以 `ooxml_order.py` 自我檢查，並有 `test_outputs_keep_schema_child_order` 迴歸測試。

## 與來源的對照

- 參考文獻：以系辦二.8 的例子為輸入資料，輸出的 Anderson、Miller、Holman、田秉才、張福祥、USDA、SAS、Campbell、Moulton 條目與系辦原文逐字相同；差別只有期刊名不用斜體、書名號改為 “ ”（見 authority.md）。
- 朋友範本：稽核結果為 1 個 error（頁尾撐大下邊界，推算約 2.97 cm）與 9 個 warning（誌謝 1.16 倍行距、頁碼偏右約 0.35 cm、缺封面／標題頁／審定書、參考文獻與附錄被編成第六、七章、目錄收錄自己、孤立的 3.1.3），不再有 1.0.0 的 3 個「缺圖表標題」誤判。原檔 SHA-256 前後不變。
- 局部新增到朋友範本：新增標題與圖題改用範本自己的 heading 2 與「圖內容」樣式，Word 會顯示 4.1 與 圖4-2；打錯的編號（4.2、3.5）被拒絕，未寫出任何檔案。

## 明確未驗證／不能推論的事項

- **沒有視覺驗收**：本機沒有 LibreOffice，也沒有 Microsoft Word，沒有任何頁面被渲染或看過。封面、審定書的實際外觀、分頁、文件格線下的行高、目錄欄位更新後的結果都未確認。
- 頁首頁尾高度是依字級、行距與文件格線推算，不是 Word 的量測值。
- 標楷體、細明體與 Times New Roman 未安裝於測試機；字型只檢查 XML 名稱。
- XSD 通過代表結構合乎 schema，不代表 Microsoft Word 開啟時一定沒有其他警告；請在 Word 開啟一次並更新全部欄位。
- 作者 proposal.md 的 71 筆書目與 141 處引用鍵已完整轉出；書目內容本身的正確性以作者先前的查證為準，本次沒有重新查證。
- 摘要中英一致性、照片原始來源、SI 語意、文獻真實性、中文筆畫與期刊縮寫沒有被虛構為通過。任何自動測試通過只支持測試中的行為，不是完整可靠性保證。
