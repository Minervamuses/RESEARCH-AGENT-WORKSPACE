# P3 — 保守 Markdown 與候選完整交付
依據：[目標](../GOALS.md)、[執行契約](../PLANS.md)。相依 P2。涵蓋 G3/G4/G8、R03/R04/R05/R06/R07。

## 後置條件
主 Agent 收到固定候選集合、搜尋資料及每個候選此次真正取得的內容／失敗事實；正常文字不被黑名單破壞，連結可供選擇下一步。

## P3-S1：實際 extractor 的保守轉換
主要 production 範圍 enhanced-content-extractor.ts、utils.ts（必要時 types.ts）。不整理未使用的 content-extractor.ts；但它仍被 tsc 編譯，並匯入 types.ts／utils.ts，所以本步變更若使它無法編譯，依 U14 只做讓建置通過的最小型別相容修改。
- 使用既有 Cheerio，在現有 extractor 內做有限 DOM 走訪，保留段落、標題、清單、code、表格可讀列、figure/figcaption、文字與真正 href。可移除 script/style 等非正文、做基本空白整理；不可用廣泛 class/id 子字串或 topic words 刪內容，不自創主文品質分數。
- 移除 robotics/captcha/privacy/legal/photo 等字詞及短文品質判定。移除任何因短正文而觸發的 fallback；HTTP 成功但正文無文字可走明確、有限且仍有預算的瀏覽器讀取，不能宣稱判定為低品質。
- 圖片保留來源存在的 alt/caption（標明只是文字）；公式只保留實際文字／標記，不能補造視覺語意。表格若無法呈現 colspan/rowspan，逐列保留文字並一致註明結構簡化。
- href 用實際頁面最終 URL 與有效 base href 解析；不把javascript/mailto當可導覽HTTP。保留來源文字，可將不支援協定標示為不可導覽，不用未觀測地址補造。
- 截斷用 A02，避免斷開 URL 產生錯誤目的地；已保留的連結必須完整；被截掉的區域明示未交付，不列為取得完全文。頁面 title 與搜尋 title 各有來源。
- 不要求去掉所有導覽或重複文字，忠實優先。

待新增的最小測試建議檔 tests/test-content-contract.mjs（Node 內建 assert，非 framework），直接用 inline HTML：中文＋emoji、robotics/captcha/photographs/privacy/legal、class='shadow'、figure caption、段落/list/table、相對連結及百分比參數；檢查可讀結構、文字不被刪改、href正確。URL200中介頁交付自己的 title/content/href，不冒稱目標文章。測小上限與0採部署預設，並確認不超10000，不需網路。build＋該測試通過後 commit：fix(web-search): preserve readable page text and links [P3-S1]。

## P3-S2：媒體、候選留存與真實統計
相依 P3-S1。主要 production 範圍 enhanced-content-extractor.ts、index.ts、types.ts。
- 候選在搜尋階段就定案並按原順序回傳；刪 PDF預過濾、成功者優先排序與為成功正文而補抓替換的 overfetch。
- HTTP/瀏覽器實際 Content-Type、status、requested URL、final URL、page title 若取得就回報；未取得就是unknown。PDF bytes不交HTMLparser；URL後綴只能是線索。缺失或錯誤 Content-Type 不猜HTML成功，記錄可觀察事實並採保守的有限處理。
- 每候選可辨識 not_attempted、http_error、timeout、cancelled、unsupported_media、conversion_error、empty_text、text 等技術事實；HTTP200及非空文字都不等於目標文章或研究相關性。正文取消前未開始者維持not_attempted並注明取消／預算原因。
- includeContent=false 完全不發正文請求。統計計 unique candidates selected、來源讀取 attempts、各狀態、returned，另計HTTP/browser重試；來自已實際執行且最後未交付的嘗試也不得消失。
- 狀態及輸出簡明一致，不建立新持久schema。Web Search 文案不得宣稱完整全文、已驗證摘要、來源品質或研究支持，對 Citation 路由與 P1 一致。

最少回歸：同一stub搜尋、相同limit，includeContent true/false候選URL與順序相同；混合PDF（無.pdf後綴且實際Content-Type PDF）、HTTP錯誤、正常短文、空轉換、取消；每筆仍在，snippet不當正文／摘要；false嘗試數0；總計與實際spy事件相同。重用P3-S1測試／既有retention檔，不建 fixtures框架。build與受影響測試後 commit：fix(web-search): retain unread candidates and report actual fetch outcomes [P3-S2]。

## 交付界線
外部網頁只支持取得事實；是否相關與是否為中介頁交主 Agent 判斷。頁面錯誤／unsupported不算整體資料被丟棄；清理錯誤不能覆蓋已取得資料，收尾實作由P4完成。
