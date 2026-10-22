# Web Search 驗收缺陷修正目標
日期：2026-10-22（Asia/Taipei）。本文件擁有穩定需求、來源與決策；執行狀態只見 [build-log.md](build-log.md)。

## 來源與優先序
- **S1 使用者要求**：2026-10-22「撰寫修正計劃」。前一則驗收報告列出 14 類缺陷，建議優先處理正文（1–3）與 /proc 解析（8），並詢問是否另立修正計劃；這則要求即是回應。
- **S2 驗收結果**：[context/acceptance-findings.md](context/acceptance-findings.md)（AF01–AF44、X01–X14）與 [context/mutation-survivors.md](context/mutation-survivors.md)。這兩份是驗收紀錄的持久副本。
- **S3 需求基準**：舊計劃 [2026-10-20-web-search-citation](../2026-10-20-web-search-citation/GOALS.md) 的 GOALS（U01–U15、A01–A09）與 [原規格 R01–R12](../2026-10-20-web-search-citation/context/source-spec.md)。除本文件明示的衍生解讀外，全部照舊適用。若舊計劃目錄已被移除，可從 git 歷史讀取，例如 `git show f5cf123:harness/plans/2026-10-20-web-search-citation/GOALS.md`。
- **S4 使用者在舊計劃的執行政策（S4/S6 原話）**：「完整模式」「一次執行到底」「有問題先紀錄，最後統一彙報」「每一步改動皆強制要求commit」「不準push」「不準創造、切換branch」「存在於gitignore內的東西不必commit」「計劃的精神是end2end執行完成，然後我才會回來人工check」，以及啟動即同步授權沙箱外與連網。本計劃把它們沿用為執行預設；實際授權仍來自使用者送出的啟動提示（[PROMPTS.md](PROMPTS.md)）。
- **S5 規範**：repository AGENTS.md 與使用者全域規範：Linux、Conda `app`、Poetry、最小修正、新增依賴須經核准。
- **S6 背景脈絡**：`note/20261022/session-510d4b09-acceptance-analysis/`，使用者對驗收 session 的成本分析，只作背景，不是實作範圍。它記錄了三件事：用量撞限造成大量重跑、`/tmp` 證據跨夜遺失、多代理平行覆核的成本結構。本計劃因此訂下證據入庫、可隨時中斷續作、不依賴大規模平行代理的規則。

優先序：S1 > S3 的使用者決策 > S2 > S4 > S5 > S6。S2 的發現描述的是現況，不會擴大 S3 的需求。

## 目標與驗收
| 目標 | 必須可觀察的結果 | 擁有階段 | 來源 |
| --- | --- | --- | --- |
| FG1 | 正文轉換忠實：整頁轉換不再靜默丟段落；巢狀表格每段文字只出現一次；caption 保留；區塊文字不黏連；依實際編碼解碼；標題取自頁面 head；轉換與截斷為線性時間，截斷後不留殘缺連結；PDF、過大回應與轉換失敗都分類正確並保留事實 | F1 | R03/R05/R06、AC02/AC04、AF01/02/04–10 |
| FG2 | 瀏覽器 fallback 在有界的等待內，能取得 DOMContentLoaded 之後才由計時器或 fetch 渲染的文字（包括 CSP 禁止 eval 的頁面）；仍為空時，可見輸出說明已等待多久 | F1 | G3、R03、AF03 |
| FG3 | 局部上限是真正的總時間上限：HTTP 讀取不再只是閒置計時；導覽後的頁面讀取有上限；每頁 8 秒從實際開始讀取起算；逾時原因可區分；自有 Chromium 在 argv 或 comm 被改寫時仍可辨識並收尾 | F3 | U13/A03/A04、R09、AF19–22 |
| FG4 | 可見狀態與統計如實：未嘗試的原因與「已達 limit」可區分；嘗試次數只計實際事件；各次嘗試的欄位不互相混雜；統計口徑寫在輸出與 README；兩個搜尋入口的驗證一致；工具文案不承諾完整性 | F4 | R01/R06、U12、AF11–18 |
| FG5 | Python 包裝穩健：任何程序名稱都不會讓 /proc 解析出錯；觀察者的錯誤不會取代已收到的結果；取消時不留未取回的例外；診斷顯示階段、根因與 log 位置；工作期限後才到的回應如實報告為「未取得」並附有效預算 | F2 | G6/A03、R11、AF24–28 |
| FG6 | 已提交的測試真正守護驗收項：入口生命週期、handler 接線、Node 與 Python 的預算／設定契約、舊 P4-S2 聚焦案例、程序樹回收、診斷、Citation 段落與工具文案都有斷言；突變清單中的「必殺」項全部被殺死，或依 FA12 記錄等效／不再適用的理由 | F2、F3、F4、F5 | AF29–39、mutation-survivors |
| FG7 | 文件與實際行為一致；真實 Python→Node 入口逐項重現修正；公開引擎在 P2-S3 之後重新觀測；完整 suite 通過；證據保存在 repository 內；最後一次統一彙報 | F6 | R08/R12、AF40–44 |
| FG8 | GUI 分支逐步本地 commit（.gitignore 涵蓋路徑除外），每個 commit 同步更新 build-log 狀態表；end-to-end 執行，中途不停下等待授權或 review；不 push、不建立或切換 branch | F1–F6 | S4、S5 |

## 範圍
- **納入**：acceptance-findings 中處置欄指向 F1–F6 的所有 AF，以及 mutation-survivors 中的「必殺」突變。
- **排除**：X01–X14 與標為「等效」的突變。執行中如有新發現，只在不違反下列不變條件、且屬於同一行為缺陷時才修正；否則記入最終彙報的後續選項。

## 衍生決策與可逆假設
這些是本計劃的明示預設，執行時直接採用，不需中途再確認。若新證據推翻某項假設，執行者可在 S3 決策與下列不變條件之內自行修訂，並在 build-log 記錄證據與理由；超出本計劃範圍的變更只列入最終彙報。
| ID | 預設 | 依據與界線 |
| --- | --- | --- |
| FA01 | 正文以整個 `<body>`（沒有 body 時用整份文件）依原順序轉換，只移除 script、style、noscript、template。導覽、頁尾、側欄文字保留，由 10000 上限與透明的截斷標記處理長度 | 衍生自 R03：「不得藉『清理』推定哪些主題內容沒有價值」「可接受的取捨是保留部分導覽或重複文字……這比無聲破壞來源文字更符合本次目標」。不做主文偵測，不加品質分數（舊 P3-S1） |
| FA02 | 表格只輸出屬於自己的列；儲存格內的巢狀表格只在該儲存格內輸出一次；caption 在列前輸出一次；儲存格內容收成單行。沿用既有的「span structure simplified」說明 | A07「表格可用逐列文字退化」。驗收重點：每段可見文字只出現一次，外層每列一行 |
| FA03 | 字元編碼的判定順序：BOM → Content-Type 的 charset → 文件前 4096 bytes 內的 meta charset／http-equiv → UTF-8。以 Node 內建 TextDecoder 解碼，判定結果與來源在輸出中可見。遇到不支援的 label 時以 UTF-8 解碼並明示 | 順序依 HTML 標準的編碼判定（BOM 優先於傳輸層宣告）。不新增依賴。已驗證 conda app 的 Node v24.18.0（ICU 78.3）支援 big5、shift_jis、euc-jp、gbk、gb18030、euc-kr、windows-1252 |
| FA04 | 瀏覽器讀取在 DOMContentLoaded 之後，等到「網路靜止，且頁面已有可見文字」，或等滿上限。上限為新的具名常數 renderSettle，初始值 3000 ms，取 min(上限, 剩餘預算)。判斷由 Node 端輪詢，不依賴需要頁內 eval 的 waitForFunction。只用在瀏覽器讀取；HTTP 讀取不受影響 | U13：局部上限是可調整的初始值，3000 ms 與既有 selector 等待同級。基線的等待約為 0.5–1.5 s 加上最多 2 s 的 selector。「且」才能處理導覽列先出現、主要內容後到的頁面 |
| FA05 | 每個操作上限都是該操作的總時間上限，不只是閒置計時。搜尋後每頁 8 秒的整體視窗，從該頁實際取得第一個讀取 slot 起算；排隊時間只受整次呼叫預算限制。逾時原因要區分是操作上限、每頁視窗還是整次期限 | U13「依現行語意」：基線各頁同時開始讀取，沒有排隊。舊計劃執行時把它解讀為「含排隊」，本計劃更正 |
| FA06 | 導覽之後的 page.title、page.content、innerText 共用一個具名上限，初始值與 pageRequest 相同（6000 ms），並取 min(上限, 剩餘預算) | U13：新增的具名常數同樣集中管理，不新增環境設定 |
| FA07 | 引擎狀態保留 completed、zero_parsed、error、strategy_stopped（僅代表已達 limit），新增 not_attempted，並附原因：deadline、cancelled、rate_limited、queue_expired。attempts 只計實際開始的傳輸。已知的 HTTP status 列在引擎行。「開始」的定義在引擎與頁面讀取上一致：已發出 HTTP 請求，或已開始為這次讀取啟動瀏覽器、建立 context；只在佇列中等待、從未取得 slot 的不算 | U12 規定「策略停止」須可見；R06 規定只計實際事件，並回報已知事實 |
| FA08 | 統計口徑：source_read_attempts 是依 FA07「開始」定義計算的 HTTP 與瀏覽器讀取次數；candidates_attempted 是至少開始過一次讀取的候選數；同一次 HTTP 讀取內跟隨的 redirect 不另計。移除恆為 0 的 transport_retries。輸出附一行口徑說明，README 同步 | R06：區分按來源計數與按重試計數 |
| FA09 | Python 診斷顯示階段、根因（逐層展開 ExceptionGroup，最多 3 個葉例外）與 stderr log 路徑。逾時訊息附有效的 DEFAULT_TIMEOUT 毫秒數 | R11 |
| FA10 | 自有 Chromium 的辨識：/proc/PID/cmdline 以 NUL 或空白切分後，只要含 owner flag token 就成立；仍要求 pgid 等於 pid，且 starttime 一致。stat 一律從最後一個「)」之後解析 | 已驗證：以 process.title 改寫後，cmdline 變成單一字串，NUL 切分無法找到 flag，空白切分可以；comm 也會改成例如 `a) b c d --web-`，舊的 `split(') ')` 會讀錯欄位 |
| FA11 | 證據存於本計劃的 evidence/步驟ID/（JSON、文字與驅動腳本），與該步驟一起 commit。外部頁面只保存必要摘錄（每頁 ≤2000 code points），不保存 cookie、nonce 或憑證。`/tmp` 只作執行時暫存 | 舊證據在 `/tmp`，重開機後已遺失（AF42、S6） |
| FA12 | 突變複驗只針對 mutation-survivors 的清單。每個必殺突變必須被殺死；若證明它是等效突變，或對應程式已因修正而不存在，記錄理由即可 | 有界，不做全面突變測試 |

## 待使用者決策（非阻塞，不在本次範圍）
| ID | 事項 | 現況與後果 |
| --- | --- | --- |
| OD1 | Bing `ck/a` 中介頁：Bing 候選的正文讀取實際上只拿到中介頁，而中介頁裡的 href 又是 ck/a | R04 明文禁止擴建 Bing 專用的網址清洗。若要解開 Bing 自家的包裝，或改用真實瀏覽器導覽中介頁，須先修訂 R04。本計劃只在 F6-S3 觀測並記錄 |
| OD2 | web_search 在啟動時卡住，session 要等整個 DEFAULT_TIMEOUT（預設最長 5 分鐘） | 目前 discovery 與呼叫共用同一個預算上限。是否另設較短的啟動預算屬於產品取捨 |
| OD3 | 舊計劃目錄、未被呼叫的 Google parser 與舊 content-extractor.ts 的去留 | 本計劃不修改舊計劃目錄（它的 build-log 宣稱由本計劃的 acceptance-findings 更正），也不清理死碼。使用者慣例是完成後另行要求移除 |

## 不變條件
- 舊計劃 S3 的使用者決策照舊：
  - U02 策略 B 與引擎順序 Bing→DDG→Brave（A05）；
  - U03 includeContent 預設 true；
  - U04／A01／A02 長度語意與 10000 上限；
  - U05／A03 每次呼叫五分鐘總上限與 285/15 切分；
  - A04 每程序 1 個 Chromium、2 個 page/context、2 個 HTTP；
  - U08 Citation 只做 prompt 層級的限制；
  - U11 不把 TMPDIR 或 proxy 加入 web_search 的環境 allowlist；
  - D05 維持逐次 session。
- 不新增或升級依賴，不改 lock 與環境定義。只使用既有套件與 Node／Python 內建能力（TextDecoder、AbortSignal.any、AbortSignal.timeout）。
- 不加入語意評分、詞彙黑名單、class/id 子字串刪除、主文品質分數或站點／引擎專用的網址辭典（R02/R03/R04）。不新增搜尋引擎，不加跨引擎融合。
- 不修改 AGENTS.md。舊 content-extractor.ts 不整理，只在 tsc 需要時做最小的型別相容修改（沿用 U14）。不修改 site-packages。
- 不 push，不建立或切換 branch，不改 Git identity，不繞過 hooks，不使用付費模型或服務。
- app/store/ 與 note/20261022/ 是規劃前就已存在的未追蹤使用者資料，不修改、不提交。app/store/ 不讀取內容；note/20261022/ 只作背景閱讀（S6）。
