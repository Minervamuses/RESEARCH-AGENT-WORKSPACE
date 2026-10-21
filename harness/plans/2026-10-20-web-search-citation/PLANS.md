# Web Search 與 Citation 完整執行計劃
計劃位置：harness/plans/2026-10-20-web-search-citation/
準備狀態：**可啟動**（A1 已依 2026-10-21 使用者回覆修訂）。本次是規劃交付，沒有實作已完成的宣告；階段執行狀態與實際證據只由 [build-log.md](build-log.md) 擁有。

## 閱讀與責任
[GOALS.md](GOALS.md) 擁有需求、來源與假設；本文件擁有路線與執行契約；[PROMPTS.md](PROMPTS.md) 是啟動／續作入口；build 階段檔擁有具體工作與驗收；[plan-index.json](plan-index.json) 只是靜態相依圖；[context/source-spec.md](context/source-spec.md) 保存原規格；[驗收對照](context/acceptance.md) 連接 R/AC 與階段。不得把 index 或 GOALS 變成第二份進度表。

## 觀察到的基線（2026-10-20；靜態檢查，不是執行測試）
- repository 是 research-agent-workspace，分支 GUI，產品程式基準 7026a70e1d3368d3fc1617cf735c44e9ff0c1b86。規劃前 tracked/index 乾淨，只有 app/store/ 未追蹤。harness/plans/ 已存在且沒有待續作計劃。
- 明確支援 Linux；目前 Windows-hosted agent 透過 WSL Ubuntu-24.04 使用 Linux shell/git 與 Conda app。驗得 Python 3.13.14、Poetry 2.4.1、Node v24.18.0、npm 11.16.0；app/poetry.toml 禁用 Poetry venv。Git identity 已有，不需修改。Linux rg 不在 PATH，可用 git ls-files/find/grep，不安裝替代工具。
- vendor package.json 已有 Cheerio、Axios、Playwright、p-limit、p-retry、MCP SDK；node_modules/ 與 dist/ 存在但內容新鮮度未證明；dist 不追蹤。沒有 npm test，存在 build 與 lint script。
- src/index.ts:8/24 使用 EnhancedContentExtractor；:327–361 驗證遺失 maxContentLength；:66–90 猜模型類型；:373 正文模式過量取候選。工具文案過度承諾完整內容。
- src/search-engine.ts:28–119 用分數選單一批次，初始順序 Bing/DDG/Brave；:1045–1130 詞彙評分；:1024–1028 重複 URL 解碼。Bing/Brave 獨立 browser 不由 closeAll 完整掌握。
- src/enhanced-content-extractor.ts:403–459 過濾 PDF、成功者優先、裁切；:465–561 刪 class/id 子字串與詞彙、展平正文；:310–322 短文品質判斷；:413–422 race 不取消底層工作與 timer。BrowserPool keyed by type，launch 有競態，預設包含 Firefox。
- app/agent/mcp.py:63–102 預設 vendored dist，保留停用／自訂 command/args；兩種 Web Search spec.env 都是空。:137–144 resolver 無各別隔離；:262–267 connection preparation 在 try 外。startup.py:50–66 有無 extension 的 diagnostics 不一致。
- Python 啟動器已有 stdout JSON 過濾、stderr log rotation；雖 Node 有 console.log，此次不推定整個 transport 已壞，也不額外重寫 wrapper。paths.py 不需要因 resolver 例外被全面改寫。
- installed langchain_mcp_adapters/client.py 的 get_tools 使用逐呼叫 session；tools.py:372–385 在真正 call 時建立／初始化 session。只替 Node handler 加 timeout 不能證明父層啟動有界。庫內有 connection session_kwargs，但具體外層 cancel/close 行為需 P4/P5 小型檢查，禁止修改 site-packages。
- Citation SKILL.md 第 12 行後可加單一段落；Crossref/DataCite 已有，OpenAlex 取決於現有 key；doi.org 是既有身分核實。tool_access_matrix 目前要求 citation 可見 web_search；prompt-only 變更應保留它。

### A1 唯讀審查觀察（2026-10-20；修正前基線，不是本計劃的實作證據）
- 產品程式與 7026a70 相同；repo 現有 dist 與重新 build 的結果經 diff 相同。vendor 的 npm run build exit 0；node tests/test-search-result-retention.mjs 19/19 passed。npm run lint 在基線就失敗（2 errors、223 warnings），本計劃不把 lint 列為檢查。
- focused pytest（暫存與日誌隔離後）：test_citation_skill_activation＋test_tool_access_matrix 21 passed；test_mcp＋test_mcp_stderr_log 20 passed。完整 suite：沙箱外加隔離設定 1495 passed、約 46 秒；沙箱內 2 failed＋25 errors，全部是 desktop 測試寫死 /tmp 造成的 EROFS。
- src/index.ts 有三個工具：full-web-search（:33）、get-web-search-summaries（:151）、get-single-web-page-content（:244）。summaries handler 只輸出 title/URL/description，沒有引擎或狀態；:230 每次 summaries 呼叫都 closeAll()。index.ts 載入即啟動 stdio server（:526–527），離線測試不能直接 import 它。
- 現有局部上限：
  - search-engine.ts:58 的 min(timeout/3, 4000) 傳給各引擎方法，作為引擎內每次導覽／HTTP 請求的 timeout（:203、:389、:410、:475、:542）。它不是整個嘗試的上限：一次 Bing／Brave 嘗試還包含 Chromium launch、0.5 秒重試等待、selector 等待與開新 browser 的重試。handler 呼叫 search() 時沒傳 timeout，預設 10000，所以目前實際約 3.3 秒。
  - Bing／Brave selector 等待 2–3 秒（:213、:403、:433、:486）。
  - enhanced-content-extractor.ts：單頁 HTTP 與瀏覽器讀取預設 DEFAULT_TIMEOUT 6000（:15）；瀏覽器導覽字面上限 min(timeout, 8000)（:172），HTTP/1 重試 min(timeout, 6000)（:208）。搜尋後正文每頁傳入 6000（:415），外加整體 race 8000（:419）；單頁工具目前沒有整體上限。
- content-extractor.ts 雖未被呼叫，仍被 tsc 編譯，並匯入 types.ts 的 ContentExtractionOptions／SearchResult 與 utils.ts 的 cleanText 等函式。
- Node 收尾：TS SDK 1.15 的 StdioServerTransport 不把 stdin EOF 轉成 onclose；Python mcp 1.27 取消時不送 cancelled 通知；Chromium 由 Playwright 以 detached 啟動在獨立 process group。審查實驗中，外層 timeout 落在 SDK 收尾期時呼叫懸住超過 40 秒並留下 sh/node/Chromium 孤兒；Node 改為在 stdin end 時關 browser 並退出後，4.85 秒乾淨返回。
- Chromium：Playwright 1.54.2 對應的 chromium-1181 與 headless shell 已安裝；TMPDIR 可寫（或在沙箱外）時 headless launch 成功（139.0.7258.5）。
- 單次網路觀測（沙箱內經 proxy 的 curl）：Bing 200、DuckDuckGo 202（anomaly 頁）、Brave 429。只作背景，不是引擎可用性的結論。

未觀察：修正後的行為與效能、五分鐘邊界、沙箱外真實搜尋可用率。不得把 S1 引述、上述靜態檢查或修正前審查觀察當作本計劃的動態成功證據。

## 依相依順序的路線
| 階段 | 單一交付後置條件 | 相依 | 目標 | 詳細 |
| --- | --- | --- | --- | --- |
| P1 | Citation prompt 已明確禁止 Web Search 找論文／補救 provider，既有 workflow 與工具可見性保留 | 無 | G1/G8 | [Citation 小改](build/phase-01-citation.md) |
| P2 | 搜尋能補足候選並如實回報；長度參數全程有明確語意 | 無 | G2/G4/G8 | [候選與參數](build/phase-02-search-contract.md) |
| P3 | 正文轉換忠實、候選不丟失、內容狀態和統計可相信 | P2 | G3/G4/G8 | [正文與交付](build/phase-03-content.md) |
| P4 | Chromium、併發、取消與 Node 清理已受控，沒有 Firefox 與無主背景工作 | P3 | G5/G8 | [生命週期](build/phase-04-lifecycle.md) |
| P5 | 真實 Python 啟動設定／整體時間預算成立；單 MCP 故障隔離到準備階段 | P4 | G5/G6/G8 | [Python 整合](build/phase-05-python.md) |
| P6 | 以實際 dist 與 Agent 路徑完成驗收、量測與一次統一報告 | P1/P3/P5 | G7/G8 | [整合驗收](build/phase-06-verification.md) |

P1 或 P2 可獨立先做；預設依表順序執行。階段中的獨立步驟可在其他步驟阻塞時推進，只有相依結果可用後才進行依賴它的行為驗收。不得把「有問題先記錄」當作忽略破壞性 regression 的理由。

## 一次執行到底的契約
1. **授權邊界**：A0／A1 只寫、審查、驗證並本地 commit 計劃。未來使用者明確啟動此計劃後，持續執行已列明的必要工作、範圍內修正、測試、計劃維護與逐步 commit。依 U11，同一個啟動同時授權在宿主沙箱外執行本計劃列明的檢查並連網（見下方「宿主沙箱與執行環境」）。依 U10，從啟動到最終彙報之間，任何時點都不停下來要求使用者授權、review、approve 或 continue；遇到問題記錄後繼續其他可做工作，最後統一彙報。啟動提示在檔案中不代表現在已啟動。
2. **第一個動作**：讀本 repository 適用指令、GOALS、本文件、build-log，再唯讀核對 pwd、branch、HEAD、status、index、Conda 工具路徑。若 conda 未在 PATH，使用現有安裝的 bin/conda 或先初始化既有 Conda；目前本機位置為 /home/minervamuses/miniconda3/bin/conda，搬移後應重新發現，不能改用 system Python。只在 GUI 進行變更；若別人已換分支，不自行切回，記錄實際阻塞。記錄原有 dirty/index 項目；不 reset/stash/clean/amend/rebase，也不更改 worktree。
3. **檔案範圍**：各階段列出的 vendor 現行 src、必要既有測試與說明、app/agent/mcp.py/startup.py，必要且具證據的 session 接點，以及 Citation SKILL.md 和本計劃。每項變更須對應 G/R/AC。優先每步最多三個 production 檔案；若一個不可分的共享生命週期修正確實需要四檔，P4-S1 已列明最小因果範圍，未來啟動該具體計劃時一併執行，不再創建泛用框架或擴到其他模組。任何步驟若因 types.ts／utils.ts 變更使未呼叫的 content-extractor.ts 無法編譯，依 U14 只做讓建置通過的最小型別相容修改，計入該步實際檔案並記錄於 build-log，不整理或重構它。
4. **每個改動步驟必須 commit**：P1-S1 等每個穩定步驟是一個完整可檢查的改動單位，不是一次編輯工具呼叫。完成該步的 focused 檢查、更新 build-log 後，立即在 GUI 本地 commit，成功後才開始下一個改動步驟。不得累積多步最後一起提交。測試失敗可 commit 範圍清楚的 checkpoint，但必須標示未完成、保留失敗證據，不能讓依賴該成功條件的步驟繼續。純唯讀檢查不造空 commit；若產生證據／計劃改動則納入該步 commit。依 U15，被 .gitignore 規則涵蓋的路徑不屬於強制 commit 範圍（見第 5 項）。
5. **commit 作法**：先看 git status --short、git diff、git diff --cached --name-only；只 git add -- 明確本步路徑，檢查 staged diff/whitespace，再 git commit -m 'type(scope): outcome [P?-S?]'（可另加 -m 說明 body）。不 git add .、不把別人的 staged 變更帶入。用穩定步驟 ID 從 git log 找 commit，不為記錄自身 hash 再製造遞迴 commit。規劃 authoring 使用 A0、A1。
   依 U15，被 .gitignore 規則涵蓋的路徑不必 commit：執行步驟中不需對它們 git add，未提交也不算 commit 失敗。用 git check-ignore --no-index -v <path> 判斷（不加 --no-index 時，已追蹤檔案不會被報告）。這包括本計劃 build/ 下已追蹤的 phase 檔（root .gitignore 忽略 build/，對它們 git add -- 會回 exit 1 並提示 Use -f），以及 dist/、node_modules/、cache。phase 檔若有修訂，同步在 build-log 記下修訂摘要與原因；build-log 不在忽略路徑，照常 commit。最終彙報列出仍未提交的 phase 檔修改。絕不 force-add dist 或生成資料。
6. **禁止事項**：不 push、不創造或切換 branch、不 fork worktree、不改 Git identity、不繞 hooks、不刪未追蹤資料、不替使用者發佈。不得使用 paid model/provider、改依賴／lock／環境、建立新服務或通用架構。外部查詢限必要公開唯讀 smoke，不做付費 LLM 遵循測試。
7. **問題處理**：一般失敗先記錄→提出單一因果假設→最小修正→focused 重驗。遵守最多兩次 focused 修正失敗即停止該問題的規則；仍可推進互不依賴工作。不論上游是否阻塞，最後都執行 P6-S3 的可做部分（完整 suite、AC 對照、build-log 結案）與最終彙報。外部封鎖／缺安裝／缺權限／需新依賴等記錄為未滿足前提，採現有能力替代；沒有安全替代則隔離受影響步驟。環境類失敗依「宿主沙箱與執行環境」歸類，不消耗兩次修正額度。全部可做工作完成後一次彙報已完成、失敗、未驗證與恢復條件；依 U10 不在中途停下來要求授權或人工審查。
8. **不可假裝越過硬阻塞**：commit 失敗（hook、identity、index 污染等；第 5 項的忽略路徑不算）不得宣稱已提交，也不能繼續累積下一步改動。先做不破壞他人狀態的修復；仍失敗時完成剩餘唯讀分析與紀錄，最後報具體 blocker，不停下來等待使用者。宿主強制控制（例如宿主拒絕沙箱外執行）與使用者後來的停止指令仍優先；被拒絕的動作記為環境阻塞後，繼續其他工作。本計劃文字本身不授予 U11 以外的權限。
9. **修訂與恢復**：中斷後以 build-log 與 git log 的步驟 ID、實際 diff、目前 dist 新鮮度重新對帳，確認外部 smoke 是否已做，避免重複。必要時修訂未開始步驟的實作細節及對應驗收，並在 build-log 記錄修訂（build/ 下 phase 檔依 U15 可不 commit）；不變更使用者目標或把失敗改成通過。若乾淨結果已成立，標明復用的 commit/測試環境，避免重做。
10. **自動化限制**：此契約指執行 turn 內持續完成，沒有建立背景排程或自動喚醒承諾。使用現有宿主能力續作；交接入口不依賴作者私人路徑。

## 宿主沙箱與執行環境（U11）
A1 審查在 Claude Code 這類逐指令沙箱中觀察到：/tmp 與 ~/.cache 唯讀；MCP stdio 子程序只繼承 HOME/LOGNAME/PATH/SHELL/TERM/USER，Node 拿不到 TMPDIR 與 HTTP(S)_PROXY；每條指令有自己的 PID namespace。後果包括：
- app/agent/mcp.py 用 2>> 把 stderr 寫到 $XDG_CACHE_HOME/agent-mcp（預設 ~/.cache），沙箱內 web_search 整個載不起來（applied_but_unavailable: ExceptionGroup）。
- Chromium 在 /tmp mkdtemp 時出現 EROFS。
- Node 對外連線出現 DNS EAI_AGAIN。
- 完整 suite 出現 /tmp 相關錯誤。

依此訂出以下規則：
- **沙箱外執行**：下列檢查一律在宿主沙箱外執行（Claude Code 為關閉 sandbox 的指令；其他宿主用其提權執行方式；宿主沒有沙箱則直接執行）。
  - 經真實 Python→Node 入口的檢查（P5-S1 的 env 驗證、P5-S3、P6-S1、P6-S2）。
  - 啟動真 Chromium 的檢查。
  - 公開網路 smoke。
  - 真程序生命週期與殘留檢查（P4-S3、P5-S3、P6-S1）。
  - 完整 suite。

  build、Node stub 測試與 focused pytest 可在沙箱內或外執行。這是 U11 已授權的範圍，執行時不再詢問。
- **暫存與日誌隔離**：每次執行先建立 repo 外、本次專用的暫存根目錄（沙箱外用 mktemp -d；沙箱內放在宿主給的 $TMPDIR 下）。所有 pytest 與真實路徑命令都要：
  - 設定 XDG_CACHE_HOME、AGENT_LOG_DIR、TMPDIR 指到其子目錄；
  - 加 PYTHONDONTWRITEBYTECODE=1；
  - pytest 加 -p no:cacheprovider。

  不得寫入使用者真實的 ~/.cache/agent-mcp 或 ~/.local/state/research-agent/logs。
  - 直接以 node 啟動 Playwright／Chromium 的命令（不經 Python MCP 預設環境，例如直接測 dist adapter 或內部 browser 入口）要另設 PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright。Playwright 在 Linux 依 $XDG_CACHE_HOME/ms-playwright 找瀏覽器，隔離後若不設會報 Executable doesn't exist。這屬於設定錯誤，修正後重跑，不算 Chromium 不可用。經 Python 入口的 Node 不繼承 XDG_CACHE_HOME，不受影響。
- **產品不遷就沙箱**：不把 TMPDIR 或 proxy 變數加入 web_search 的環境 allowlist；沙箱外的 Node 直接使用系統 /tmp 與網路。
- **環境失敗歸類**：以下屬環境阻塞，不算實作錯誤，不消耗執行契約第 7 項的兩次修正額度，也不能據此停用搜尋引擎或判定 Chromium 不可用：EROFS／Read-only file system、proxy 或 DNS 錯誤（EAI_AGAIN、407）、宿主沙箱拒絕。
  - 在沙箱內誤跑出這類失敗時，改到沙箱外重跑。
  - 沙箱外仍失敗（含宿主拒絕沙箱外執行）時，如實記錄，隔離受影響驗收，繼續其他工作，不停下等待使用者。
  - 環境阻塞只把該項真實驗收記為未驗證，不算執行契約第 4 項的「成功條件未成立」。該步驟在其離線／stub 檢查通過後照常 commit，build-log 註明未驗證項；依賴它的後續步驟繼續實作與檢查，受影響的真實驗收在 P6 統一列為未驗證。
- **殘留程序證據**：在同一個測試腳本或同一條指令內取證。呼叫期間記錄 wrapper／Node／Chromium 的 PID 與 process group，返回後在同一腳本內檢查是否仍存活。另開一條 ps／pgrep 指令得到的「沒有殘留」不算證據，因為沙箱會在每條指令結束時回收其程序。取證後，由同一腳本只終止本次記錄的 PID／process group（沙箱外不會自動回收），並在 build-log 記錄是否有殘留與清理結果；不終止其他程序。

## 必要檢查與成本
已從現有檔案查到的命令（A1 審查已在修正前基線上跑過前三項，結果見基線）。pytest 與真實路徑命令都套用上一節的暫存與日誌隔離：
- 工作目錄 app/vendor/web-search-mcp：conda run -n app --no-capture-output npm run build；conda run -n app --no-capture-output node tests/test-search-result-retention.mjs。
- 工作目錄 app：conda run -n app --no-capture-output poetry run pytest tests/test_citation_skill_activation.py tests/test_tool_access_matrix.py -q -p no:cacheprovider。
- 工作目錄 app：conda run -n app --no-capture-output poetry run pytest tests/test_mcp.py tests/test_mcp_stderr_log.py -q -p no:cacheprovider。
- 工作目錄 app：完整 app suite 在沙箱外以 timeout 600 conda run -n app --no-capture-output poetry run pytest -q -p no:cacheprovider 執行，時機是最終程式改動之後。若因此發現 regression 或環境設定錯誤並修正，修正後可再跑一次（全計劃最多兩次）。逾時是未完成，不是通過。若前置資訊顯示會觸發外部付費行為，記錄暫不執行與原因。不能把 targeted tests 冒充完整 suite 通過。
- 新 Node 回歸檔屬 P3/P4 待實作的少量原生 assert 測試，不是已存在命令；先確定實際路徑才執行。沒有 npm test，不新增 framework。
- 每步執行 git diff --check / git diff --cached --check；不執行全庫 format。
- 網路 smoke 最多六個有明確目的的公開請求組，累計最多八分鐘；每組單獨有界，必要時用低於 300 秒的部署 timeout。deadline 邊界用縮短預算與可控本地例子驗證，不等待多輪五分鐘。限時耗盡記錄未驗證，不做 sweep。
- 量測只取三類必要路徑與同一小樣本的必要重現，不建 benchmark framework、不做大樣本或全資料集。
- 需要 Chromium 可執行。A1 審查已觀察到它在 TMPDIR 可寫或沙箱外時可啟動；執行時若在沙箱外仍無法啟動，不自動 install，先完成離線測試，最終列 AC08/AC14 未驗證。已安裝 npm/Poetry package 不需重新 install。

## 完成判準
G1–G8 及原 AC01–AC14／新增 AC15 的必要條件均有實際證據；程式在受影響 focused checks 與可執行的完整 suite 符合預期，真實 Agent→dist 輸出、設定、候選保留與時間／收尾成立；所有改動步驟 commit（gitignore 涵蓋路徑依 U15 除外），分支仍 GUI、無 push、無無關檔案；執行中沒有停下來要求授權或 review。D05 必須有量測後決策，非必須實作重用。

若仍有失敗／必要檢查不可用，交付報告必須稱「部分完成／有阻塞」，不可因已走到最後一階段就宣稱工程完成。計劃的 ready 僅表示路線足以啟動。
