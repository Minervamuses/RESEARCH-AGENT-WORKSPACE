# Web Search 與 Citation 工程目標
日期：2026-10-20（Asia/Taipei），A1 修訂 2026-10-21。本文件擁有穩定需求與決策；執行狀態只見 [build-log.md](build-log.md)。

## 來源與優先序
- S1：[原工程規格完整快照](context/source-spec.md)，版本 1.0，原始檔 gui-web-search-engineering-spec.md，基準 GUI / 7026a70e1d3368d3fc1617cf735c44e9ff0c1b86。這是需求資料，不是執行授權。
- S2：使用者 2026-10-20 回覆本次釐清問題的 annotation 1–8，短引文與歸納見下表。annotation 4 只有選取，沒有新增決策；annotation 5 才提出 10000。
- S3：同次追加要求：「修改citation skill」「只需要小改」「加一段prompt層級的限制」「不要用web search」「當回傳有問題時誠實告知」「之後觀察違規狀況再決定是否需要更硬的限制」。
- S4：同次規劃要求：「完整模式」「一次執行到底」「有問題先紀錄，最後統一彙報」「每一步改動皆強制要求commit」「不準push」「不準創造、切換branch」。
- S5：repository AGENTS.md 與使用者 Personal Engineering Defaults：Linux、Conda app、Poetry、保留既有工作、最小修正、低成本與必要授權。
- S6：使用者 2026-10-21 對 A1 唯讀審查結果的逐項回覆：兩個搜尋工具輸出與 AC05「同意」；局部 timeout「同意」；「直接把我核准沙箱外執行寫進去，一旦我授權執行計劃，就同步授權沙箱外連網，但如果真的還是出問題，也不要停下來等我，如實紀錄就好，計劃繼續做完」；README 設定表「把更新改成新增」；content-extractor.ts 最小型別相容修改「同意」；「存在於gitignore內的東西不必commit，其餘照舊」；「計劃的精神是end2end執行完成，然後我才會回來人工check，中途停下來要求我授權或等我review什麼是錯誤的行為」。
- 最新 S2/S3/S6 覆寫 S1 的對應未決項與 Citation 輔助搜尋解讀；未修改的 R01–R12、AC01–AC14 仍適用。執行者不需要原聊天或作者電腦上的 skill。

## 目標與驗收
| 目標 | 必須可觀察的結果 | 擁有階段 | 來源 |
| --- | --- | --- | --- |
| G1 | Citation 有一段 provider-only prompt；provider 失敗／缺摘要／不確定時誠實表達，不自行轉 Web Search；既有存檔與 DOI 核實不變 | P1 | S3、R01、AC13 |
| G2 | 依策略 B 跨可用引擎補足候選；不做本地語意打分；來源、失敗與零解析在兩個搜尋工具（full-web-search、get-web-search-summaries）的 Agent 可見輸出中可區分 | P2 | S2-2、S6、R02/R04/R06、AC01/03/05 |
| G3 | 預設讀正文，保守 Markdown 保存來源文字、結構、連結；PDF/失敗候選仍保留 | P3 | S2-3、R03/R04/R05、AC02/03/04 |
| G4 | 長度參數全程有效且截斷透明；候選、正文嘗試、狀態與交付統計相符 | P2、P3 | S2-5、R06/R07、AC06/07 |
| G5 | 無 Firefox；真實資源有限；逾時／取消／成功／關閉均有界收尾；每次工具呼叫不超五分鐘 | P4、P5 | S2-6/7、R08/R09、AC08/09/10 |
| G6 | Python→Node 設定有效；單 MCP 解析、準備、啟動、載入失敗不拖垮其他工具；實際入口可驗證 | P5 | R10/R11、AC11/12 |
| G7 | 建置與真實入口驗收涵蓋所有必要行為，分段量測後記錄 session 重用決策；完整記錄未通過事項 | P6 | R12、AC14、S4 |
| G8 | 在原 GUI 分支逐改動步驟 commit（gitignore 涵蓋路徑除外），保留無關檔案；end-to-end 執行，不中途要求授權或等待人工審查；不 push／建分支／切分支 | P1–P6 | S4、S5、S6 |

## 已確認的使用者決策
| ID | 決策 | 來源與後果 |
| --- | --- | --- |
| U01 | 開放式使用：類似研究、技術細節、今日新聞等；沒有預設網站或查詢對象 | S2-1「不可能預設對象」。執行時自選小型代表案例，案例不得變成白名單、詞典或產品適用範圍 |
| U02 | 策略 B：第一引擎不足 limit，繼續其他可用引擎盡量補足；不指定引擎或順序 | S2-2「B」「能運作就什麼都可以」。不保證一定湊滿，不因正文失敗重新補候選 |
| U03 | includeContent 預設 true；接受 Markdown | S2-3 |
| U04 | 內容長度上限 10000 | S2-5。依「上限」落為目前每頁硬上限；部署預設與0的細節依A01明示 |
| U05 | 等待時間五分鐘 | S2-6。以 A03 明確化適用範圍 |
| U06 | 以 32 GB CPU RAM 作資源背景 | S2-7。不是工具可獨占 32 GB，也不能推導允許無界並行 |
| U07 | 無額外腳本／MCP 客戶端等相容性需求 | S2-8。仍保留 S1 指定的停用、自訂啟動、候選與 Citation 行為 |
| U08 | Citation 僅 prompt 小改，不做 runtime 硬封鎖 | S3。「datasite」依 repository 現有名稱正規化為 DataCite；OpenAlex 保留既有 optional 條件 |
| U09 | 預設一次連續執行，問題記錄後最後統一彙報；每步 commit；禁止 push 與建立／切換分支 | S4。詳見 [執行契約](PLANS.md) |
| U10 | end-to-end 執行到完成後才由使用者人工檢查；中途停下來要求授權或等待 review 是錯誤行為 | S6。阻塞只隔離受影響步驟並記錄，其餘工作繼續；最後統一彙報 |
| U11 | 使用者授權執行本計劃時，同時授權在宿主沙箱外執行計劃列明的檢查並連網；沙箱外仍失敗時如實記錄、不停下等待，計劃繼續做完 | S6。範圍與環境設定見 [PLANS 宿主沙箱與執行環境](PLANS.md)；不擴大為新依賴、付費呼叫、push 或發佈授權；不為遷就沙箱把 TMPDIR 或 proxy 變數加入產品 web_search 環境 allowlist |
| U12 | full-web-search 與 get-web-search-summaries 的文字輸出都帶出各引擎狀態與每筆候選來源引擎，並有檢查輸出文字的斷言；AC05 驗收類型為「離線＋輸出文字」；P4-S3 點名 summaries 每次呼叫的 closeAll | S6「同意」 |
| U13 | 局部 timeout = min(該操作上限, 剩餘預算)；現有局部上限（使用者所說的 3／4／6／8 秒）依現行語意作為可調整初始值 | S6「同意」。語意對照（PLANS 基線）：引擎內單次導覽／HTTP 請求 4 秒（search-engine.ts:58 min(timeout/3, 4000)，呼叫端未傳 timeout 時實為約 3.3 秒）；selector 等待 2–3 秒；單頁 HTTP／導覽 6 秒；搜尋後正文單頁整體 8 秒。4 秒不是含 launch 與重試的整個引擎嘗試上限；整個引擎嘗試與整次呼叫只受剩餘預算限制。具名常數集中保存，不新增環境設定；DEFAULT_TIMEOUT 只表示整次呼叫總預算 |
| U14 | vendor README 新增（而非更新）直接相關設定表；content-extractor.ts 允許為建置通過的最小型別相容修改 | S6。仍不整理或重構 content-extractor.ts |
| U15 | 被 .gitignore 規則涵蓋的路徑不必 commit；其餘 commit 規則照舊 | S6。包括本計劃 build/ 下已追蹤的 phase 檔；細節見 PLANS 執行契約第 5 項 |

## 可逆規劃假設與技術決策
這些是本計劃的明示執行預設，不是額外使用者原話；直接採用，不需要中途再次確認。執行中出現推翻某項假設的新證據時，執行者在 U01–U15 與使用者上限內自行修訂，於 build-log 記錄證據與理由後繼續，不停下詢問；超出本計劃範圍的變更只列入最終彙報的後續選項。
| ID | 執行預設／選擇 | 驗證或修訂界線 |
| --- | --- | --- |
| A01 / D02 | 10000 是目前每頁轉換後正文的硬上限，內建預設同為10000。MAX_CONTENT_LENGTH 可設1–10000的部署預設；呼叫顯式1–10000優先；省略或0採部署預設。0不再代表不限長度 | 大於10000、負值、非整數、NaN、非純數字字串明確拒絕並說明允許範圍，不默默clamp。0採預設是本計劃的技術語意選擇；工具文案與測試同步移除舊「0無上限」，避免繞過使用者上限 |
| A02 / D02–03 | 長度用 Unicode code points 計算（不是 UTF-16 code units 或 token）；計入正文 Markdown 語法與正文中的 URL，metadata/title/snippet/狀態及截斷標記不計。可回少於上限，避免把連結目的地截成錯誤 URL | 同一內容只做一次有效截斷，兩入口相同；只在實際已知時回原始長度；不補造圖片、公式資訊 |
| A03 / D04 | 五分鐘是每次工具呼叫從 Agent dispatch 到返回的總上限，包含該次排隊、程序／session 啟動、導覽、讀取及收尾；不限制整個研究對話或整項工程。候選工作最多 285 秒，保留最多 15 秒供清理與返回；更早完成即返回 | 300 秒是使用者上限；285/15 是可逆配置。Python 外層與 Node 都要有界；新程序的啟動／初始化不能在限時之外 |
| A04 / D04 | 每個 Node MCP 程序最多 1 個 Chromium browser、2 個活躍 page/context、2 個活躍 HTTP 讀取；共用受限工作不得巢狀占住同一閘門造成死鎖 | 這是保守初始值，非 32GB 量測結論；多個程序不是全域限流，不宣稱跨 ChatSession 全域資源保證 |
| A05 / D01 | 初始沿用 Bing→DuckDuckGo→Brave，作為最少變更的有限序列。維持各引擎原始排序，逐批補到 limit（預設 5、範圍 1–10）；只對標準解析後完全相同的 URL 去重，保留最早資料及各實際來源引擎 | 不剝查詢參數、不任意改寫百分比編碼、不用標題相似度融合。重複筆不湊數。達 limit、引擎耗盡或 deadline 即停止。引擎錯誤保留此前候選 |
| A06 / D01 | 不新增搜尋引擎；現有引擎可因實機不能工作而停用並記錄原因。Brave 不必保留，但保留就必須 Chromium 實測；403/429 直接失敗 | 引擎全不可用須如實回報；不能假裝搜尋成功，不能藉機加入付費 API 或新框架 |
| A07 / D03 | 用既有 Cheerio 加現有 extractor 內少量直接轉換邏輯，產出有限且明確的保守 Markdown；不新增 dependency，不建立通用轉換框架 | 表格可用逐列文字退化；保留可見文字與 href。不是通用完美主文辨識器 |
| A08 / D05 | 先完成收尾再量測。本次必需交付是量測與重用決策；預設維持逐呼叫 session。收益不足、未知或需新增較大狀態管理時，記錄理由，將重用實作列後續選項 | 不先新增 daemon、跨聊天 browser 或 session 常駐。實測可支持後續建議，不以「可能較快」擴張本次 |
| A09 / D04 | Node 端「MCP 連線結束」以 process.stdin 的 end／close 事件判定：中止未完成工作、有界關閉自有 browser 後退出 | A1 審查證據：TS SDK 1.15 StdioServerTransport 不把 stdin EOF 轉成 onclose，Python mcp 1.27 取消時不送 cancelled 通知，所以 server.onclose／extra.signal 在真實路徑上不會觸發；Chromium 由 Playwright 放在獨立 process group。必須經真實 Python stdio 驗證，stub 通過不算 |

## 不變條件與範圍
- Web Search 保留一般網頁／技術／新聞能力。論文發現、書目、摘要、引用一律沿 Citation workflow；provider 出問題不能用網頁搜尋補救。這取代 S1 R01 可被解讀為允許 Citation fallback 的部分。
- 保留已可見的真實 DOI/arXiv 交回 workflow 的方式、doi.org 身分與 BibTeX 核實、既有儲存授權、optional provider 程式及摘要邊界。
- 不新建 PDF/OCR/全文研究流程、網站語意黑名單、MCP LLM 評審、向量排序、來源權威評分或跨引擎融合平台。
- 不增加 production dependency、改 lockfile／環境定義、安裝瀏覽器、升版套件、引入服務／資料庫／測試框架；必要工具已缺失時記錄外部前提。
- 不改 AGENTS.md、不整理未呼叫的舊 content-extractor.ts（U14 的建置所需最小型別相容修改除外）、不全面重構 RAG、GUI 或 Citation runtime。
- 無付費模型呼叫、全資料集重播、模型／GPU sweep、無界重試；具體檢查限額見 PLANS。
- app/store/ 是規劃前已存在的未追蹤資料；cite/、dist/、node_modules/、cache、憑證與其他使用者工作不納入 commit。
