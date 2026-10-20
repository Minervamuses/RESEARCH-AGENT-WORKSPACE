# P6 — 真實入口、分段量測與統一交付
依據：[目標](../GOALS.md)、[執行契約](../PLANS.md)、[AC對照](../context/acceptance.md)。相依P1/P3/P5。涵蓋G7/G8、R12、AC14與整體。

## 後置條件
每個必要結果都有足夠證據或清楚的未滿足紀錄；實際主Agent使用的新dist被驗證，分段成本已量測，所有改動步驟commit並一次統一彙報。不因走到本階段就自動宣稱完成。

## P6-S1：建置新dist並走真Python入口
1. 對帳改動、環境與分支。vendor執行conda run -n app --no-capture-output npm run build，確定測的是剛產生的dist/index.js；不commit生成dist或node_modules。
2. 重用已通過的focused evidence，僅因新改動或整合風險重跑受影響項。新測試真實存在才用實際命令，不能把草擬名稱冒充已有腳本。
3. 實作一次性或現有test內最小整合程序（目前沒有已驗證專用腳本）：由agent.mcp的既有resolver/loader取得真tool，再ainvoke，確實啟動vendored dist，經現有wrapper與env。不用LLM、不呼叫付費provider、不以mock MCP client冒充全鏈路。
4. 控制本地HTML/redirect/PDF/慢回應，保存可讀結果及設定對照；靜態HTML route驗HTTP，需瀏覽器的route以DOM動態插入可辨識文字驗browser path。後者若現有「非空HTML」先返回而未啟browser，使用同一現行內部browser入口作受控驗證並另記證據路徑，不誤標為Agent已走browser；AC14要求的Agent browser path仍需實際觸發並證明。可短暫啟動僅綁loopback、當次finally關閉的測試頁面，這不是部署服務或持久存儲。
5. 驗MAX_CONTENT_LENGTH=37、省略參數的實際Node截斷；顯式71覆寫部署值，0採37的部署預設，10001明確拒絕；觀察有效上限、body與truncated。同候選includeContent=false正文request數0。PDF/HTTP失敗候選保留，final URL和title屬實際頁面。
6. 真程序成功、timeout、cancel、connection close後確認該次子程序/contexts/timers無殘留，close錯誤不覆寫結果。不能只看狀態碼宣稱成功。
7. 普通網路實機：在執行當日選一般技術問題與新聞查詢，必要時一筆研究主題的Citation既有recorded資料檢查。使用者不需預給URL；記下當次選例供重現，不寫入產品規則。每個保留搜尋引擎至少有一次可用性觀測；可直接測同一dist adapter，但需標明不等於Python全鏈路。至少有一個完整搜尋和單頁讀取經Python入口；所有保留engine路徑無Firefox由實際可用性＋受控從入口分支驗證覆蓋。保留Brave必須有Chromium實測；無法工作就記原因、停用該engine並重驗候選策略。
8. 六組公開唯讀請求、累計八分鐘上限依PLANS。外網封鎖/結構變動區分實作錯誤與未知，不為湊成功一直換案例、引擎或大重試。各失敗如實記錄，無法完成必要實機項不得標通過。

本步若需要修正，回對應階段新增有穩定ID的最小修復步驟，單獨檢查、commit，再重驗受影響項。一次性診斷清理後不留無用production程式。驗收紀錄提交：test(web-search): record actual Agent-to-Node behavior [P6-S1]。

## P6-S2：生命週期量測與D05決策
完成P4後才量測。沿P6-S1相同實際路徑分別觀察：
- 只取搜尋資訊；
- 純HTTP讀取；
- 真實瀏覽器讀取。

每類記discovery/程序啟動、search、body、close與端到端wall time，若階段不適用寫不適用，不猜數字。可在既有入口臨時量測並於完成前移除；必要重跑同一小例最多一次區分明顯timer殘留與冷啟動，不展開benchmark campaign。若新增永久輸出僅能為本次必要診斷且不污染MCP stdout。

D05決策：記錄修正後startup/discovery/close佔比、使用頻率未知等限制；沒有明顯實測負擔就維持逐呼叫session。有負擔但重用會新增狀態/擁有者複雜度，也可維持現狀並把數據列後續選項；本次不以未設定的績效門檻或猜測聲稱優化成功。不增加ChatSession常駐client、daemon或跨對話browser。記錄屬量測後決策，不是忽略D05。

證據、限制及決策寫build-log，commit：docs(web-search): record lifecycle timings and session decision [P6-S2]。

## P6-S3：一次完整suite與最後核對
- 最終程式改動穩定後，從app執行完整現有suite一次。命令見PLANS；先檢查現有設定是否會觸發live付費資源，不讀取或輸出密鑰。若預估／已知超十分鐘，依限制記錄未跑；可用Linux timeout給現有pytest一次600秒上限，逾時就是未完成不是通過，不再跑第二輪全suite。
- 每個AC對照結果、命令、輸出摘要/證據位置、錯誤與未驗證項。純provider prompt檢查不保證模型遵守；付費或大規模遵循觀察留未來。
- git diff --check、staged範圍檢查，確保只有因果範圍；無AGENTS/lock/env變更、無生成store/dist、無無關清理；GUI分支不變，逐步commit可由ID對帳。未修改production的pure-read驗證只有證據文檔要commit。
- 更新build-log各階段：必要條件未成立留Blocked或In progress，不以總結取代事實。證據/結案commit建議docs(plan): record verification results and remaining limits [P6-S3]。
- 最終一次彙報：已完成行為與檔案、實際測試和失敗、量測結果及D05、commit對照、仍有的阻塞/恢復前提。明說沒有push、沒有建立／切換branch。可提出最多三個具體後續選項，不能自行擴張或替使用者啟動硬限制。
