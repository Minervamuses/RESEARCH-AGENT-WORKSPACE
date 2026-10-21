# P1 — Citation prompt 小改
依據：[目標](../GOALS.md)、[執行契約](../PLANS.md)。相依：無。涵蓋 G1/G8、R01、AC13、AC15。

## 後置條件
Citation 的搜尋與引用沿既定 provider workflow；缺資料或失敗時誠實回答，不能轉 Web Search 補救。只增加 prompt 指令，不新增硬封鎖，不聲稱模型違規已被技術上消除。

## P1-S1：加一段明確限制並 commit
輸入 app/skills/citation/SKILL.md，預計在 introduction 的 workflow 責任描述後、/citation 使用說明前加以下一段（可調措辭但保留全部語意）：

> For paper discovery and citation work, use only citation_workflow and its existing Crossref, DataCite, and optional OpenAlex providers, preserving the workflow's existing authoritative identifier resolution and save behavior. Do not use Web Search or browse other websites to find papers, fill missing metadata or abstracts, or repair failed, incomplete, or ambiguous provider results. When the workflow cannot provide a reliable result, honestly report the returned failure, uncertainty, or missing information and present any usable results with their limitations; follow the existing bounded retry rules instead of searching the web. This instruction applies even when Web Search tools remain available.

唯一 production 寫入範圍是 app/skills/citation/SKILL.md。保留使用者已提供／既有可見結果的 DOI/arXiv 交回 save、doi.org 身分/BibTeX、摘要與論點支持界線、有限 provider 重試、使用者儲存授權。一般技術與新聞仍可用 Web Search。OpenAlex 無 key 時仍依現有行為略過，不為此新增 key 或改 provider。

檢查：
1. 執行者自行逐句核對（不請使用者確認）：找論文、補 metadata／摘要、provider 失敗／不完整／歧義均不得轉 Web Search；部分結果及未知誠實揭露；沒有刪除或硬封鎖工具。
2. 從 app 套用 PLANS 的暫存與日誌隔離，執行既有 conda run -n app --no-capture-output poetry run pytest tests/test_citation_skill_activation.py tests/test_tool_access_matrix.py -q -p no:cacheprovider。
3. diff 只有新增小段與必要空白。既有 tool_access_matrix 仍期待 Citation 可見 web_search，不可修改斷言假裝 prompt-only 變成 runtime enforcement。

記錄實際命令、結果與限制，commit 建議：docs(citation): require provider workflow for paper citations [P1-S1]。不用新測試框架或付費 LLM；測試只能證明載入與未改硬權限，模型是否遵守留待使用者日後觀察。
