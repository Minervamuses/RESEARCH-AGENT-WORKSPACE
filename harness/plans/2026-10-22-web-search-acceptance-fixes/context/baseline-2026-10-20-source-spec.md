> 凍結快照：取自 commit f5cf123 的 `harness/plans/2026-10-20-web-search-citation/context/source-spec.md`。舊計劃目錄已於 2026-10-22 依使用者指示（「舊的用不到的就可以清理了」）移除，本檔保留作為修正計劃的需求基準。內容逐字保留，只把指向舊計劃其他檔案的連結改為純文字。舊計劃的其他檔案（PLANS、PROMPTS、build/、build-log、context/acceptance.md）可用 `git show f5cf123:harness/plans/2026-10-20-web-search-citation/<路徑>` 讀取。

# GUI 分支 Web Search MCP 工程規格

本次工程將 Web Search MCP 收斂為忠實的網頁資料取得工具，修正內容被改寫、候選來源被丟棄、執行結果被誤報，以及瀏覽器與程序收尾不可靠的問題。既有主 Agent 負責理解、相關性判斷與下一步選擇；論文搜尋與引用維持 Citation skill 的 Crossref／DataCite 主線。

本規格作為後續落地 plan 的需求基線。工程目標、責任邊界與必要行為已確定；多引擎策略、參數的部分語意及有條件的效能優化，依「待決策事項」處理。需求與驗收編號用於交接追蹤，不代表實作順序或測試檔案數量。

| 項目 | 基線 |
| --- | --- |
| 版本與日期 | 1.0，2026 年 10 月 20 日 |
| Repository | Minervamuses/RESEARCH-AGENT-WORKSPACE |
| 分支 | GUI |
| 程式碼基準 | [7026a70e1d3368d3fc1617cf735c44e9ff0c1b86][BASE] |
| 適用環境 | 既有 Linux 本機研究工作流 |
| 交付用途 | 拆解工程任務、確認介面契約及撰寫落地 plan |
| 本次產出 | 工程規格；功能修正與執行驗收由後續實作完成 |

## 一 任務背景與完成目標

目前問題的共同成因，是 Web Search MCP 同時承擔資料取得與語意判斷。它會用字詞規則刪正文、判斷頁面品質，並對搜尋結果計算本地相關性分數，再以分數決定採用哪一批搜尋結果。這些中間處理會影響主 Agent 實際看見的證據。[E1][SCORE][E2][QUALITY]

另一組問題屬於執行可靠性：內容抓取狀態與搜尋命中混用、參數未完整傳遞、統計不反映實際嘗試、瀏覽器併發與清理不完整，以及 Python 啟動的 Node 程序未明確取得所需設定。[E3][E4][E5][E6]

工程完成後，應具備以下能力：

1. 主 Agent 能看見來源實際提供的搜尋資訊、可讀內容與連結，並知道此次到底取得了什麼。
2. 工具的結果選擇與正文轉換，不再由自製語意黑名單、相關性分數或模型類型猜測左右。
3. 搜尋失敗、解析出零筆、未讀正文、格式不支援與內容截斷，都能被如實辨識。
4. 有效參數、時間預算、併發限制與清理責任，從主 Agent 的真實執行入口成立。
5. 某個 MCP 無法啟用時，其他可用工具仍能載入。

這次修正的成效應由上述行為驗證。搜尋結果是否足以回答問題，仍由主 Agent 依任務與取得的證據判斷。

## 二 已確定的責任分工

| 元件 | 責任 |
| --- | --- |
| 主 Agent | 理解問題、判斷來源與內容是否相關、辨識是否仍在中介頁、選擇真實連結、決定是否搜尋或讀取下一頁，以及表達證據限制。 |
| Citation skill 與既有工作流 | 論文發現、Crossref／DataCite 等既有 provider 的書目與摘要取得、識別碼與版本處理、引用身分核實，以及已授權的儲存。 |
| Web Search MCP | 執行搜尋、取得頁面、保守轉換為可讀內容、保存來源資訊與連結、執行明確參數和資源限制，以及回報執行事實。 |
| 既有 HTTP 與瀏覽器元件 | 標準網址解析、正常重新導向、HTTP 狀態與媒體類型取得，以及真實頁面導覽。 |

「讓 LLM 判斷」指既有主 Agent 使用可見證據做決定。這項分工不要求 Agent 為每筆結果打數值分數，也不新增 MCP 內部的 LLM 評審、網址修復 Agent 或另一套研究流程。

程式仍應處理確定的技術契約，例如參數型別、可導覽的網址協定、HTTP 狀態、Content-Type、解析結果數量、長度與逾時。禁止的是以持續擴張的字詞或網站規則代替語意理解，而非取消基本輸入驗證。

## 三 工程需求

### R01 維持 Citation 主線並校正工具描述

論文搜尋、文獻候選呈現與引用處理，應沿用 Citation skill 的既有 Crossref／DataCite 路徑。既有可選 provider 不因這次修正被順便移除。

Web Search MCP 保留一般網頁問題與必要輔助搜尋能力；它提供的 title、snippet、URL 與頁面文字，不會自動升格成論文摘要、已驗證書目或論點支持。網頁線索中的真實識別碼，可依 Citation 的既有契約交回工作流處理。

本次不新增 PDF 解析、PDF 轉文字或另一套全文證據驗證流程。Citation 目前止於實際取得的摘要，摘要缺失需明示；來源身分核實與論點支持是不同判斷，這些邊界須保留。[E7]

Web Search 的工具說明與輸出標籤，必須準確描述「搜尋結果」與「此次取得的頁面內容」，不得承諾最完整資訊、完整正文或已完成文獻品質驗證。現有 full-web-search 的描述有這類過度承諾，需同步修正。[E8]

### R02 移除自製語意規則與本地相關性評分

刪除目前以查詢字詞命中、片語加分及主題扣分構成的相關性評分，以及依分數執行的批次優劣選擇、品質門檻、提前結束與相關日誌宣告。現行評分是程式中的詞彙規則，沒有使用向量、embedding 或 LLM。[SCORE]

同步移除以下行為：

- 用正文出現 robot、captcha 等詞，或少於某個字數，推定內容品質不佳。
- 用正文詞彙黑名單刪除 photo、privacy、legal 等字詞或字詞的一部分。
- 用參數是字串、數字或布林值，猜測模型類型後改寫內容長度。
- 已失去功能意義的評分設定、品質文案與測試斷言。

搜尋引擎本身回傳的排序可以保留。MCP 不再額外建立同義詞辭典、Unicode 補丁評分、向量排序或內嵌 LLM 評審，以替代被刪除的評分器。

移除評分會影響搜尋控制流程。落地 plan 必須先處理 D01 的最小搜尋策略，再替換控制流程；不得只把 ENABLE_RELEVANCE_CHECKING 設為 false 就宣告完成。

### R03 保守轉換 HTML 並保存可讀結構

正文轉換應以保留來源文字、可讀結構與實際連結為原則。優先採用既有能力或成熟的小型 HTML 轉換元件；確切套件由落地 plan 評估，本規格未選定或批準新增依賴。

目前 EnhancedContentExtractor 才是實際啟用的擷取器。它使用廣泛的 class／id 子字串選擇器、移除 figure／figcaption，並以 .text() 展平內容；修正必須涵蓋實際呼叫路徑。[E2][E8]

必要行為如下：

- 文字內容不得因主題詞、CSS 類名偶然包含 ad，或通用的詞彙黑名單而被改寫或刪除。
- 保留可讀段落、標題、清單、必要的表格文字、圖說，以及可見連結的文字與目的地。無法保留的呈現資訊需有一致的轉換政策。
- 可以忽略執行程式、樣式等非正文內容，並進行基本空白整理；不得藉「清理」推定哪些主題內容沒有價值。
- 頁面標題應來自實際取得的頁面。只有網址時，可呈現網址標籤，但不能冒稱已取得 page title。
- 未取得的圖片內容、公式語意或其他非文字資訊，不得從轉換後的文字自行補造。

可接受的取捨是保留部分導覽或重複文字，讓主 Agent 判斷。這比無聲破壞來源文字更符合本次目標；本次不要求通用且完美的主文辨識器。

### R04 以真實導覽與連結處理網址

保留搜尋與頁面實際提供的 URL。相對網址以標準 URL 解析器與實際頁面基底解析；正常 HTTP 重新導向交由既有客戶端或瀏覽器處理。最終網址必須來自實際導覽結果。

移除會改變目標語意的重複解碼與任意字串改寫，不擴建 Bing、DuckDuckGo 或網站專用網址清洗辭典。目前 DuckDuckGo 路徑在 URLSearchParams 取值後再次解碼，正是需要消除的行為。[E9]

若請求停在 HTTP 200 的中介頁，應回傳該頁實際取得的標題、內容與可用 href。主 Agent 據此決定是否開啟下一個連結。這要求 R03 保留連結目的地；只有純文字而沒有 href，無法支持可靠的後續導覽。

主 Agent 必要時可使用標準編解碼能力處理有證據支持的網址操作。模型的職責是選擇與理解，不是憑空拼出未觀測到的目的地。MCP 不因任務未完成就自動啟動無界的追連結流程。

### R05 將候選來源與正文取得結果分開

搜尋選定的候選集合，應依明確的搜尋策略、來源排序與結果數量限制形成。取得正文是附加在候選上的執行結果；同一候選不得只因 PDF、抓取失敗、正文較短或格式不支援而無聲消失。

在相同搜尋策略及 limit 下，是否讀正文不應自行改變已選定的候選集合。若此次拿到更多候選，限制筆數的方式必須明確，不得改成以「能成功讀到正文」替代來源選擇。

對每個已納入回傳範圍的候選，保留實際取得的搜尋標題、URL、snippet 及來源引擎。未取得的欄位如實留空或標示未知。

遇到 PDF 或其他不支援的媒體類型時，保留候選資訊並表示此次未取得可讀正文。媒體處理應依實際取得的 Content-Type 等技術資訊，不得把 PDF bytes 當成 HTML 正文，也不得因 URL 沒有 .pdf 副檔名就宣告它是 HTML。URL 外觀可作線索，不能偽裝成已觀測到的媒體類型。[E10]

本需求不要求無限回傳所有搜尋結果，也不要求為確認每個來源而額外下載全文。它要求在明確的候選範圍內保留身分與失敗事實。

### R06 如實呈現搜尋狀態與執行統計

搜尋命中、HTTP 請求、頁面文字轉換與研究上的可用性，應分別表達。傳輸完成或取得非空文字，不代表已讀到目標文章，也不代表內容與問題相關。

必須可區分：

- 引擎／網路／瀏覽器執行失敗。
- 已取得回應，但解析出零筆搜尋結果。
- 已取得候選，正文未嘗試讀取。
- 已嘗試讀取，但為 HTTP 錯誤、逾時、取消、轉換失敗或不支援格式。
- 已取得可讀文字，以及是否發生截斷。

HTTP 200 加上 parser 回傳零筆，只能證明這次解析出零筆；不能據此宣告不存在相關網頁或文獻。若資料不足以區分真正無結果與頁面結構問題，回報已知事實與必要診斷，讓主 Agent 判斷；不要補一套挑戰頁字詞辭典。[E11]

後續引擎失敗時，先前取得的候選與其正確來源必須保留。若此次搜尋只完成部分範圍，需讓主 Agent 知道不完整之處；清理錯誤也不得覆蓋原本的成功或失敗。

統計只計入實際執行的事件。至少能回答「取得多少候選、嘗試讀取多少來源、各取得狀態多少、最後交付多少」。includeContent=false 時，正文讀取嘗試數必須為零。實際發生的失敗不得因最後裁切回傳筆數而消失。按來源計數與按 HTTP／瀏覽器重試次數計數，應明確區分口徑。[E3]

## 四 回傳資料的最小語意契約

下表固定 Agent 必須能辨識的資訊，不要求立即建立特定 JSON schema、欄位名稱或大型狀態框架。沿用現有 MCP 文字回傳也可以，但資訊要一致、可理解。

| 資訊 | 語意要求 |
| --- | --- |
| 搜尋候選 | 搜尋端實際取得的 title、URL、snippet、來源引擎；未知資訊不補造。 |
| 導覽資訊 | 請求 URL 與實際最終 URL 可區分；有實際頁面標題時，與搜尋標題分清來源。 |
| 執行事實 | 是否嘗試、取得的 HTTP 狀態／媒體類型，以及失敗所處階段；未知狀態不能猜。 |
| 內容可用性 | 未讀、格式不支援、轉換後無文字、已有可讀文字等事實可辨識；不要用一個 success 同時表示 HTTP 成功與取得有效文章。 |
| 證據種類 | 搜尋 snippet、頁面正文與 Citation 提供的實際摘要不混稱。 |
| 連結 | 轉換內容中保留可見連結文字及其真實目的地，供後續選擇。 |
| 截斷 | 明示是否截斷及有效上限；不知道原始完整長度時，不編造總長度或完整率。 |
| 整體狀態 | 已嘗試的引擎及失敗／未完成範圍、實際執行統計與回傳筆數相互一致。 |

診斷只需足以理解問題與除錯。這個契約不要求保留所有原始頁面、引入資料庫、建置追蹤平台，或輸出大量重複日誌。

## 五 執行可靠性需求

### R07 讓參數從入口到輸出保持一致

maxContentLength 是明確的呼叫參數。有效的正整數上限，必須由入口傳到內容取得、轉換與輸出；搜尋後讀取與單頁讀取應有相同語意。不能在中間驗證函式遺失，也不能被模型猜測邏輯解除或縮小。[E4]

截斷應有可辨識的標記。短輸出可能只是呼叫者設定較小上限，不能觸發「低品質」推定與額外 fallback。內容長度計算的單位、metadata 是否計入，以及正文內連結文字的處理，需在落地 plan 明訂並使工具描述一致。

省略參數、值為 0，以及部署端預設上限的關係依 D02 決定。若實作存在硬性上限，必須公開其有效行為，不能以「無上限」文案遮蔽實際截斷。

limit 與 includeContent 也應只執行已定義的行為。此次輔助性定位不自動決定 includeContent 的新預設值。

### R08 從所有 Web Search 路徑移除 Firefox

Web Search 的搜尋、內容取得與 fallback 路徑均不得再啟動 Firefox。移除範圍涵蓋：

- BrowserPool 的預設型別、啟動與相關設定。
- Brave 搜尋中獨立呼叫 firefox.launch 的路徑。
- Firefox 專用分支、說明與不再適用的設定或驗收假設。

Brave 是搜尋引擎，Firefox 是瀏覽器；移除 Firefox 不等於決定移除 Brave。Brave 若改用保留的瀏覽器路徑，必須在支援環境驗證該路徑可執行。[E5]

工程上優先收斂到既有可用瀏覽器與有限的頁面／context 併發。單一 Chromium 是優先評估方向；本規格不要求為不同搜尋引擎維護不同瀏覽器，也不新增替代瀏覽器輪替框架。

### R09 修正併發限制與完整生命週期

browser、context、page、網路請求與 timer 都必須有清楚的建立、使用與回收責任。

併發限制需約束真實資源或工作數量。同時抵達的請求不得重複建立之後無人追蹤的 browser；以 Map 內的瀏覽器類型數當作實例或併發數量，不能滿足要求。每次呼叫所需的瀏覽器資訊應跟隨自身資源，不可依賴其他呼叫能改寫的「最後使用類型」。[E5]

搜尋、搜尋後讀取與單頁讀取都應有明確的時間預算。預算需涵蓋排隊、啟動、導覽、等待、重試與 fallback，並規定清理的有界收尾方式。具體秒數由 D04 決定，不沿用目前局部的 6、8、10 秒作為已同意的 SLA。

逾時或取消後，必須取消可取消的請求、停止後續導覽與重試，並回收持有的資源。無法直接取消的操作也須有界收尾，不得讓它持續擴張或啟動新工作。單純讓 Promise.race 回傳，不等於工作已停止。

成功、失敗與取消都必須進入清理；成功後清除逾時計時器。MCP 連線結束或程序收到可處理的終止訊號時，也須回收由該程序持有的瀏覽器與未完成工作，並完成有界收尾。close() 失敗可以回報清理診斷，但不能把已取得的成功改成搜尋失敗，也不能蓋掉原始錯誤。[E12][RACE][E14]

完成判準是實際並行資源受到限制、呼叫能在定義的預算內結束，且不遺留無人管理的工作。實作優先選擇本機專案所需的最簡形式。

### R10 明確傳遞仍支援的執行設定

Python Agent 會啟動獨立的 Node MCP 程序；父程序裡有設定，不代表 Node 一定收到。現行 web_search 的啟動規格使用空 env，連線建構也只在 spec.env 非空時明確傳入設定。因此，驗收需確認 Node 的有效值，不能只確認父程序中存在環境變數。[E6][CONNECTION]

落地 plan 必須列出仍支援的 Web Search 設定、預設值及優先序，並由 Python 啟動器明確傳入必要值。驗收必須從 Python／Agent 路徑確認有效設定確實改變 Node 的行為。

已移除的評分功能與 Firefox 相關設定，應移除或明確宣告不再支援，避免留下看似有效的開關。無需複製整份父程序環境或設計通用設定同步框架。

既有停用 web_search、自訂 command／args，以及缺少建置產物時的診斷能力須保留。自訂命令與預設命令的設定優先序，須一併記載。

### R11 將 MCP 失敗隔離延伸到啟動準備階段

任一 MCP 的失敗應限制在該 MCP。隔離必須涵蓋啟動規格解析、連線準備、程序啟動及工具載入。

現行一般 get_tools() 失敗已有個別處理，但 resolver 與部分連線準備在隔離之外；web_search 路徑解析失敗可能使啟動層將全部 MCP 工具清空。修正應針對這些缺口，不重寫已有作用的隔離流程。[E13]

有無 extension MCP 的啟動路徑，都應能提供不可用原因；其他可用 MCP 與本機工具繼續工作。工具缺失不能只留在不易察覺的內部例外裡。

本需求不包含完整 wheel 打包、repo 外安裝或新作業系統支援。那些是獨立產品範圍決策。

### R12 先修正收尾並量測 再決定 session 重用

先完成 R09 的生命週期修正，再從主 Agent 實際使用的 Python → vendored dist/index.js 路徑量測。分開觀察 discovery／程序啟動、搜尋、正文取得及關閉時間。

量測至少涵蓋只取搜尋資訊、純 HTTP 讀取與瀏覽器讀取。不得預設只有瀏覽器路徑會拖慢程序關閉；現行內容取得路徑即使成功，也可能留下未清除的逾時計時器。[RACE][E14]

持續 MCP session 的實作屬於 D05 的有條件優化。只有在修正後仍有實測顯著成本，且收益足以支持增加狀態管理時，才將重用納入落地範圍。若採用，需明確由 ChatSession 擁有，並在該 session 結束時釋放。

本規格不要求全域常駐 daemon、跨對話共用 browser，或分散式 rate limiter。現有逐程序的 rate limit 也不得被描述為跨 session 的全域保證。

## 六 範圍與變更落點

下列路徑均以 repository 根目錄為基準，供落地 plan 定位；不是要求逐一改動所有檔案。

| 區域 | 主要責任與可能落點 |
| --- | --- |
| Web Search 工具入口 | app/vendor/web-search-mcp/src/index.ts：工具說明、參數傳遞、輸出與統計。 |
| 搜尋取得 | app/vendor/web-search-mcp/src/search-engine.ts：移除評分、搜尋狀態、網址取得、Brave 的 Firefox 路徑與清理。 |
| 實際內容擷取器 | app/vendor/web-search-mcp/src/enhanced-content-extractor.ts：忠實轉換、連結、媒體處理、候選保留、逾時及清理。 |
| 資源與資料語意 | browser-pool.ts、types.ts、utils.ts：必要的資源限制與資料契約；不為分類整齊新增通用框架。 |
| Python 整合 | app/agent/mcp.py、startup.py，以及必要的 paths.py／session.py 接點：設定傳遞、失敗隔離與生命週期量測。 |
| Citation 與 Agent 說明 | app/skills/citation/SKILL.md、相關 README 及 Agent 工具說明：維持既有文獻工作流，僅在描述與新責任不一致時調整。 |
| 驗證與建置 | 受影響的既有 MCP 測試、vendor 測試及建置流程；確認主 Agent 實際載入新的 dist 產物。 |

舊 content-extractor.ts 不是目前主要路徑。落地 plan 可以評估是否移除已無用途的重複程式，但不得只修改它而漏掉 EnhancedContentExtractor，也不因發現旁支就自動擴成全面整理。[E8]

既有已修正的行為須保留：預設使用 repo 內 vendored build、後續搜尋失敗不丟先前非空結果與其來源引擎、Brave 對 403／429 的快速失敗，以及停用與自訂啟動能力。[E6][E1][BRAVE]

## 七 行為驗收

以下是交付時必須能證明的行為。落地 plan 應以少量有意義的回歸案例與必要實機檢查覆蓋，不必將每列拆成獨立測試框架。

| 驗收 | 情境與通過條件 | 對應需求 |
| --- | --- | --- |
| AC01 | 中文、AI 等短查詢，以及天氣或運動主題，不再經 MCP 的詞彙分數、主題扣分或語意品質門檻選擇批次。引擎原有排序仍可保留。 | R02 |
| AC02 | 含 robotics、captcha、photographs、privacy、legal 等正常文字，以及 class 名偶然含 ad 的正文，轉換後不因這些規則遭改寫或刪除；可讀結構與 href 可供使用。 | R02、R03 |
| AC03 | 正常重新導向回報實際最終 URL；含百分比編碼的參數不被重複解碼改義。HTTP 200 中介頁交付實際頁面與連結，不宣稱已取得目標文章。 | R03、R04 |
| AC04 | 既定候選包含 PDF、不可讀或抓取失敗項目時，仍保留其 title／URL／snippet 及未讀正文的事實；不啟用 PDF 解析，不將 snippet 冒稱摘要。 | R01、R05 |
| AC05 | 全部引擎執行失敗與收到頁面後解析出零筆可區分；取得部分結果後再遇失敗，候選、來源引擎與不完整範圍均如實保留。 | R06 |
| AC06 | includeContent=false 時正文讀取嘗試數為零；實際嘗試與失敗統計不因最後回傳裁切而消失；各統計口徑一致。 | R05、R06 |
| AC07 | 同一有效正整數 maxContentLength，在完整搜尋及單頁入口均生效；接受數字／字串兩種輸入的契約若保留，兩者語意一致。截斷可辨識，小上限不觸發品質 fallback。D02 決定後，同時驗證省略值與 0。 | R07 |
| AC08 | 從主 Agent 執行搜尋、單頁讀取與各保留引擎路徑，不啟動 Firefox；保留的 Brave 路徑有支援環境中的實際驗證。 | R08 |
| AC09 | 並行請求不產生失去追蹤的重複 browser；實際工作與資源不超過所定限制，每次呼叫的資源資訊不受其他呼叫污染。 | R09 |
| AC10 | 成功、失敗、逾時、取消與 MCP 連線結束均完成有界收尾；成功後無殘留 timer，逾時後不再補抓或重試。清理失敗不覆寫已取得結果或原始錯誤。 | R09 |
| AC11 | 經 Python／Agent 啟動設定一個保留的選項，Node 的有效值與行為確實改變；停用及自訂 command／args 仍依契約作用。 | R10 |
| AC12 | 某 MCP 在規格解析、連線準備或工具載入階段失敗，其他可用 MCP 與本機工具仍存在；兩種 extension 啟動情境都提供診斷。 | R11 |
| AC13 | Citation 繼續將實際摘要、metadata 與論點支持分清；Web Search 說明如實表示輔助／一般網頁能力。文獻身分與引用處理由既有 Citation 流程承接。 | R01 |
| AC14 | 實際建置後，主 Agent 載入的 dist 行為符合本規格；完成三類讀取路徑的生命週期與分段耗時量測，據此記載是否需要 session 重用。 | R12、整體 |

既有測試若將「中文查詢固定得 0.5」或「全部搜尋失敗等於零結果」當成正確契約，應隨新需求移除或改寫；保留後續失敗不丟結果等有效保護。[E16]

實作驗證須遵守 repository 的 Linux、Conda app 與 Poetry 約定。AGENTS.md 要求先跑受影響的 focused tests，再執行完整 app suite；新增或變更依賴需遵守其明確授權要求。本規格不構成某個新套件的選型或安裝決定。[E17]

## 八 待決策事項

這些事項需在落地 plan 中明確處理。它們不阻止需求整理，但不可在實作時以舊預設或隱性 fallback 代替決策。

| 決策 | 已確定的邊界 | 落地 plan 需要敲定的事項 |
| --- | --- | --- |
| D01 多引擎策略 B | 移除本地評分；不宣稱多引擎天然較好；不默認新增融合、去重辭典或另一輪 LLM 排序。 | 本次採用的最小搜尋行為，包括啟用引擎、嘗試順序、停止條件、結果呈現及 FORCE_MULTI_ENGINE_SEARCH 的去留。 |
| D02 長度語意 | 有效顯式上限必須生效，不得猜模型改寫；截斷透明。 | 省略參數、0、部署預設與硬性上限的優先序，以及長度單位和 metadata 的計數方式。現有工具文案宣稱 0 為無上限；若保留，需真正符合其定義。 |
| D03 內容預設與轉換形式 | Web Search 為輔助／一般網頁能力，正文保守轉換並保留連結。 | includeContent 的預設是否維持、Markdown／可讀文字的形式、最小轉換元件與必要的資訊保留政策。 |
| D04 執行預算與資源限制 | Firefox 移除；真實併發受限；逾時可停止並收尾。 | 具體併發數、各入口總時間預算與清理餘額、最簡 browser／context 管理形式，以及 Brave 的保留路徑。 |
| D05 session 重用 | 先修正生命週期，再量測；有明確擁有者與回收界線。 | 依修正後的量測結果，決定是否值得在本次實作重用。沒有足夠收益即可維持每次呼叫的 session 形式。 |

D01 是移除評分控制流程前的必要小決策。現況關閉評分後，預設會回傳第一個非空批次；強制多引擎則仍因同分保留第一批，並未合併結果。這只能作為理解現況的基準，不能視為使用者已選定的產品行為。[E1]

為控制落地範圍，可優先評估「沿用現有引擎順序、採明確停止條件的最小 fallback」。這是待評估方向。若未來要做跨引擎合併或提供 Agent 選擇引擎的能力，應明列所解決的需求及額外成本，再納入 plan。

## 九 工程依賴與交接原則

落地 plan 宜先固定資料語意與 D01 的最小搜尋策略，再修改評分、候選保留、狀態與輸出。R03 的連結保存是 R04 讓主 Agent 決定下一步的前提；R05 的候選與內容分離，是 R06 正確統計的前提。

Firefox 移除與 R09 資源管理可在同一個工作範圍內收斂。R10 設定傳遞與 R11 MCP 隔離可各自處理，但最終都要經主 Agent 實際啟動路徑驗證。R12 的效能量測與重用決策，必須排在生命週期修正之後。

交接時，plan 應讓每個工程項目對應本規格的需求與驗收編號，標明必要的介面變化、建置方式及未決事項的選擇。無需在本 spec 預先指定函式簽名、類別結構、完整 schema、每一個測試或 commit 切法。

本次範圍不包含 PDF／OCR／全文研究流程、網站規則辭典、MCP 內語意評審、完整多引擎融合平台、全域常駐服務、全面依賴升級、完整 wheel 發布或原生 Windows 支援。若實作遇到確切新問題，應依證據提出範圍變更，而非為假設性風險擴建系統。

## 十 原問題與本規格對照

| 原討論項目 | 本規格處理 |
| --- | --- |
| 1 正文被清理破壞 | R02 移除詞彙規則，R03 保守轉換。 |
| 2 頁面品質誤判 | R02 移除品質黑名單，R06 如實呈現執行事實。 |
| 3 失敗被當成空結果 | R06 狀態與部分結果契約。 |
| 4 相關性評分誤判 | R02 刪除評分職責。 |
| 5 PDF 與不可讀候選流失 | R01 維持 Citation 主線，R05 保留候選，不新增 PDF 解析。 |
| 6 網址清洗與中介頁 | R03 保留 href，R04 標準導覽與主 Agent 決策。 |
| 7 統計不準 | R06 以真實事件計數。 |
| 8 maxContentLength | R07 參數傳遞與一致語意，D02 敲定特殊值。 |
| 9 Firefox | R08 全路徑移除，包含 Brave 獨立啟動。 |
| 10 併發與清理 | R09 真實限制、取消與收尾。 |
| 11 Python 到 Node 設定 | R10 明確傳遞仍支援的設定。 |
| 12 session 成本 | R12 先量測，D05 有條件優化。 |
| 13 MCP resolver 隔離 | R11 延伸失敗隔離範圍。 |
| A 評分責任 | R02 已確定移除；判斷交由既有主 Agent。 |
| B 多引擎行為 | D01 待落地 plan 明確決策，不與 A 混為同一項已完成設計。 |

## 十一 程式碼依據

下列連結固定在同一 commit，便於後續比對。若落地時 GUI 已前進，先確認變更是否已修復對應問題；以需求與行為驗收為準，不重做已成立的修正。

| 依據 | 位置與支持的事實 |
| --- | --- |
| E1 | [搜尋控制流程][E1] 與 [本地相關性評分][SCORE]：詞彙評分、主題扣分、批次勝出及提前結束。 |
| E2 | [內容轉換與清理][E2]、[短文與字詞品質判斷][QUALITY]：實際文字刪除、結構展平與品質規則。 |
| E3 | [候選數量與統計][E3]：推算 followed、最終裁切後統計及正文呼叫。 |
| E4 | [參數與模型猜測][E4]、[參數轉換與傳遞][PARAMS]、[單頁長度處理][SINGLE]。 |
| E5 | [BrowserPool][E5]、[Brave 獨立瀏覽器][BRAVE]：Firefox 與共享資源管理。 |
| E6 | [Python Web Search 啟動規格][E6] 與 [連線轉換][CONNECTION]：vendored 路徑、空 env 與覆寫能力。 |
| E7 | [Citation skill][E7]：實際摘要、provider 失敗、引用身分與全文邊界。 |
| E8 | [實際擷取器與工具描述][E8]：EnhancedContentExtractor 啟用及 full-web-search 說明。 |
| E9 | [URL 驗證與清洗][E9]：現行網址規則與 DuckDuckGo 再次解碼。 |
| E10 | [候選篩選與內容取得][E10]、[HTTP 內容轉換][HTTP]：PDF 排除、成功候選優先與未檢查媒體類型的處理。 |
| E11 | [搜尋失敗與空結果][E11]、[DuckDuckGo 取得與例外][DDG]。 |
| E12 | [瀏覽器內容取得與收尾][E12]、[外層 timeout race][RACE]、[Bing 關閉流程][BINGCLOSE]。 |
| E13 | [resolver 與載入流程][E13]、[Agent 啟動層][STARTUP]、[app root 解析][PATHS]。 |
| E14 | [stdio 結束處理][E14] 與 [MCP 工具載入][LOADTOOLS]：生命週期檢查的整合落點。 |
| E15 | [既有搜尋結果保留修正][E1]、[Brave 失敗處理][BRAVE] 與 [目前 vendored 預設入口][E6]。 |
| E16 | [現有搜尋結果保留測試][E16]：保留有效防回歸，修正不再成立的評分與空結果斷言。 |
| E17 | [Repository Guidelines][E17]：專案範圍、支援環境、測試與依賴管理約定。 |

[BASE]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/commit/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86
[E1]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/search-engine.ts#L27-L119
[SCORE]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/search-engine.ts#L1045-L1130
[E2]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/enhanced-content-extractor.ts#L465-L561
[QUALITY]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/enhanced-content-extractor.ts#L310-L322
[E3]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/index.ts#L364-L421
[E4]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/index.ts#L50-L90
[PARAMS]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/index.ts#L327-L391
[SINGLE]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/index.ts#L263-L308
[E5]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/browser-pool.ts#L1-L129
[BRAVE]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/search-engine.ts#L132-L231
[E6]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/agent/mcp.py#L63-L102
[CONNECTION]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/agent/mcp.py#L195-L232
[E7]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/skills/citation/SKILL.md
[E8]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/index.ts#L7-L56
[E9]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/search-engine.ts#L957-L1042
[E10]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/enhanced-content-extractor.ts#L400-L459
[HTTP]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/enhanced-content-extractor.ts#L63-L86
[E11]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/search-engine.ts#L100-L130
[DDG]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/search-engine.ts#L525-L554
[E12]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/enhanced-content-extractor.ts#L89-L245
[RACE]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/enhanced-content-extractor.ts#L409-L422
[BINGCLOSE]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/search-engine.ts#L339-L367
[E13]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/agent/mcp.py#L137-L274
[STARTUP]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/agent/startup.py#L49-L65
[PATHS]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/agent/paths.py#L7-L13
[E14]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/src/index.ts#L472-L518
[LOADTOOLS]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/agent/mcp.py#L234-L274
[E16]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/app/vendor/web-search-mcp/tests/test-search-result-retention.mjs
[E17]: https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/7026a70e1d3368d3fc1617cf735c44e9ff0c1b86/AGENTS.md
