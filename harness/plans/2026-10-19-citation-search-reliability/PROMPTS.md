# 執行入口

下列文字是未來可交給執行者的指令，不代表本次已啟動實作。狀態只看 [build-log.md](build-log.md)，規則只看 [PLANS.md](PLANS.md)。

## 啟動第一批

> 請執行 `harness/plans/2026-10-19-citation-search-reliability/` 的第一批 P1–P4。依序閱讀適用 AGENTS.md、GOALS.md、PLANS.md、build-log.md 與下一個 dependency-ready phase，先完成 Linux／Conda app runtime gate 與 Git 狀態核對。P1 第一個動作是核對 composeTurnText 與段落留言測試，接到後端真實技能啟動邊界。遵守原有審批與成本限制，外部目標、超過三個 production files 等仍依 PLANS.md 處理；已授權範圍內持續完成，不只交付分析。先完成離線代表案例，再明確列出實際正常使用 trace 是否待補。P5 與 P6–P10 不在這次啟動範圍，不自行做後續優化或付費呼叫。若需要 Git commit 授權，先完成可審閱的改動與檢查後再請示。

如要一併授權 P2 的既定外部交付，可明確附加：

> 我授權修改 `/home/minervamuses/mcp-servers/web-search-mcp` 的結果保留控制流程，使用現有依賴 build，驗證後備份並更新 `/home/minervamuses/.local/share/mcp-servers/web-search-mcp` 對應 build 產物。保留既有 package-lock.json 修改，不安裝依賴、不改環境。外部 source 的 scoped commit 如需執行請另依我的明確授權。

若希望每個 coherent step 後在 WSL 提交，可附加「授權對本次已驗收的主專案改動做 scoped local commits，不 push」；這不授權把外部 source 複製進主專案。

## 恢復已啟動範圍

> 恢復 `harness/plans/2026-10-19-citation-search-reliability/`。先讀適用指令、GOALS、PLANS、build-log，重核目前 Git／外部安裝與已存在證據，再從日誌的下一步繼續此前已獲授權範圍。不要重複做已完成的遠端操作或重問已有授權；未解 blocker 只阻擋受影響工作。不要從這段恢復文字推定新增實作、付費或 Git 授權。

## 啟動後續決策與選定項目

> 請讀第一批修正後的既有 trace，依 PLANS.md 的決策方法評估 P6–P10，最多提出三個有證據的下一步，不先實作或跑付費呼叫。分清缺測量與已知正確性問題，為建議項目列出寫入檔案、成本、驗收與需要的政策選擇。

選定具體項目與預算後，再明確要求執行該階段。P5 的啟動須指定或確認 timeout／重試政策；不能只要求把 max_retries 設為 0。

## 修訂或稽核

> 只修訂這份計劃以反映以下新決策。保留已完成證據、未受影響目標與原有範圍，更新相關階段、依賴、驗收、index 與 log；不要實作程式。

> 只稽核這份計劃與來源 brief／目前原始碼的符合程度。指出會造成誤作、無法驗收或越權的具體缺口；不要修改或執行，除非另獲修訂授權。
