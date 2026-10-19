# P10 — 依新 trace 限定補查缺口與停止條件

目標 G10；前提 P1–P4 完成、有保存 action 的新 Citation trace，且使用者已選定此調整。共通 [政策](../PLANS.md)／[目標](../GOALS.md)。

## 已知與限制

`agent/tools/access.py:68–112` 允許技能工具與全域 Web Search 聯集。Citation SKILL.md:20–67 要求真摘要，tool.py 的 actions 為 search/save/sources/source/explain，沒有直接按 DOI 補摘要 action。本機舊十次 citation_workflow 沒有 action，無法認定哪些重複；也不能將十工具呼叫當十模型輪數。

## 決策路線

P10-S1：只讀修正後 trace 與必要的該次合法研究輸出，依每個 search／補查辨識「未涵蓋子主張」「指定候選缺真摘要」「新證據」「只有重複候選」。query hash 可辨識重複，不能單靠 hash 推論語義；在原對話內核對目的，不將 query／全文複製到新增 log。

P10-S2：先提出最小技能指示調整：每次補查須針對具體缺口；已有來源／query 重複且未取得新證據時轉向回答限制；資料不足可誠實完成。保持全域 Web Search 可用，不能以固定工具次數硬停、直接禁用工具或另起全文研究管線。

若證據顯示主要缺口是指定 DOI 的摘要取回，先列明既有 provider 能力與最小 action/API 方案、來源 provenance、未取得摘要行為及成本，因 public tool schema 改動先核准；不在第一批偷偷新增 action／工具。沒有此需求則只改技能文字與必要局部程式，避免並行研究 pipeline。

P10-S3：用已錄製／離線候選＋真摘要 fixtures 重演三種情境：子主張仍有實際未涵蓋缺口時能繼續；同 query／同候選無新證據時能收斂；指定候選始終缺摘要時誠實標示無法據摘要判定。來源失敗仍是 incomplete；存在可用摘要也不等同主張已被證實；save 維持原授權。

可重用 `tests/test_inline_skills.py` 的段落→topic query→摘要案例、`tests/test_citation_e2e.py` 與 `tests/test_tool_access.py`。純技能文字斷言／fake model 固定最終回答只能驗指示與工具邊界，不能證明真模型會少補查；實際停止行為需經授權的單一代表正常使用 trace，或明記待觀察。不得把改提示詞本身報成已改善。

交付為每次補查的具體缺口、新證據增量與停止理由；使用者可看到已支持／未支持的子主張與限制。只有在同案例實際輸出和時間支持時才宣稱改善。
