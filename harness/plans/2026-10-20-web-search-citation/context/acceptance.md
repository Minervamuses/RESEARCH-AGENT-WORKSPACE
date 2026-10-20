# 必要驗收追蹤
本表只擁有靜態追蹤；實際結果記 [build-log.md](../build-log.md)。原始定義見 [source-spec.md](source-spec.md)；最新使用者限制見 [GOALS.md](../GOALS.md)。

| 驗收／需求 | 擁有步驟 | 觀察程序與預期 | 類型 |
| --- | --- | --- | --- |
| AC01 / R02 | P2-S1 | 中文/短詞/運動/天氣stub，不計相關分數，依序補足且不以分數換批 | 必須離線 |
| AC02 / R02/R03 | P3-S1 | 正常詞、class含ad、圖說、list/table與href，轉換後文字不被黑名單刪改 | 必須離線 |
| AC03 / R03/R04 | P2-S1/P3-S1/P6-S1 | 編碼URL不二次解碼；相對link用actual base；redirect finalURL正確；200中介頁只交付自己和href | 離線＋受控真讀取 |
| AC04 / R01/R05 | P3-S2 | PDF/失敗/unsupported仍保留title/URL/snippet，含無.pdf但實際PDF type；不解析PDF，不稱摘要 | 必須 |
| AC05 / R06 | P2-S1 | 全失敗≠解析零筆，後續失敗不丟前面候選與來源；partial可辨識 | 必須離線 |
| AC06 / R05/R06 | P3-S2 | 相同策略limit、includeContent切換不換候選；false讀取0次，失敗與重試數等於實際事件 | 必須離線 |
| AC07 / R07 | P2-S2/P3-S1/P5-S1/P6-S1 | 省略/0=env或10000；硬上限10000，超過明確拒絕；數字/合法字串一致；Unicode計數；metadata分開；小limit不觸發quality fallback | 離線＋真env |
| AC08 / R08 | P4-S1/P6-S1 | 各保留路徑無firefox；search/single從Agent驗，保留Brave有Chromium實機；無法啟動不能標pass | 必須本地瀏覽器與有限公開smoke |
| AC09 / R09 | P4-S1 | 同時launch只有一個browser，page/context與HTTP峰值≤設定值；call資訊不互相污染 | 必須受控並行 |
| AC10 / R09 | P4-S2/P4-S3/P5-S3/P6-S1 | 成功/失敗/排隊逾時/取消/斷線均清理；無timer，取消後無新工作；close失敗不蓋結果；父子端到端有界 | 必須短deadline與真程序 |
| AC11 / R10 | P5-S1/P6-S1 | Python傳MAX_CONTENT_LENGTH=37改Node實際輸出；顯式71優先、0採部署預設；停用、自訂command/args、missing dist診斷保留 | 必須真Python→Node |
| AC12 / R11 | P5-S2 | resolver/preparation/get_tools各失敗，另一MCP和local tools存活；有無extension都有不可用診斷 | 必須既有pytest最小回歸 |
| AC13 / R01 | P1-S1/P3-S2 | prompt保留摘要/metadata/論點支持界線；WebSearch工具描述不過度承諾，Citation責任清楚 | 必須靜態＋載入測試 |
| AC14 / R12 | P6-S1/P6-S2 | 新build、真Agent入口三類路徑，startup/search/body/close分段數據，量測後D05記錄 | 必須整合與有限量測 |
| AC15 / 新增U08 | P1-S1 | 單段prompt禁止找論文及補救provider的WebSearch，誠實報錯；doi.org及可見identifier處理保留；tool可見性仍存在 | 必須；不等於LLM零違規保證 |
| AC16 / U09 | 全部改動步驟 | 穩定step ID對得上本地commit；提交後才下一改動；GUI未換；無push；問題最後統一報告 | 必須Git/紀錄核對 |

P2補足額外代表例：第一引擎2筆、第二批1重複+3新筆、limit5→5個unique候選；limit已達後不嘗試第三引擎。未補足不隱藏實際引擎失敗。來源選擇以搜尋資料為準，不按正文讀取成功換人。

不新增驗收平台或固定查詢資料集。合成inline例子只驗語意契約；真實場景執行時選取，不要求使用者預先提供來源、不做網站白名單。完整suite只在最後一次，前面用focused驗證。
