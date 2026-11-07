# 技術來源（不是論文規範）

核對日期：2026-09-30（1.1.0 新增 ECMA-376、CSL-JSON 兩項）。以下只支持安裝與程式處理的技術選擇，不能取代使用者附件的任何排版規範。

- Agent Skills specification：`https://agentskills.io/specification`。SKILL.md前置欄位、目錄結構、名稱使用小寫字母／數字／連字號並與父目錄同名。
- Claude Code skills：`https://code.claude.com/docs/en/skills`。專案與個人skill路徑、明確呼叫方式。
- OpenAI skills：`https://developers.openai.com/codex/skills`（目前導向 `https://learn.chatgpt.com/docs/build-skills`）。Codex .agents/skills 路徑與可選agents/openai.yaml介面資料。
- Pandoc manual：`https://pandoc.org/MANUAL.html`。Markdown AST、DOCX輸出、數學、表格、註腳；通用格式轉換不是無損Word編輯的保證。
- python-docx paragraphs and text：`https://python-docx.readthedocs.io/en/latest/user/text.html`。段落／run格式、行距、樣式繼承的基本語意。
- ECMA-376 Part 1（Office Open XML, transitional）：`https://ecma-international.org/publications-and-standards/standards/ecma-376/`。`scripts/bime/ooxml_order.py` 的子元素順序（CT_P、CT_R、CT_PPr、CT_RPr、CT_SectPr、CT_Settings、CT_Style）。
- CSL-JSON schema：`https://github.com/citation-style-language/schema`。`cite.py` 讀取的書目欄位名稱（author、issued、container-title-short、publisher-place 等）。
- Pandoc citations 與 `--shift-heading-level-by`：同上 Pandoc manual。引用鍵語法（`[@key]`、`@key`、`[-@key]`）與把第一個 `#` 當文件標題。
- Microsoft font information：`https://learn.microsoft.com/en-us/typography/font-list/dfkai-sb`、`https://learn.microsoft.com/en-us/typography/font-list/mingliu`。字型名稱與家族資訊；本包不提供任何字型檔。

本版主要以直接OOXML讀取／合併實作原檔保留；這些技術文件不構成「已在所有Word版本測試」的證據。測試範圍看tests/ACCEPTANCE.md。
