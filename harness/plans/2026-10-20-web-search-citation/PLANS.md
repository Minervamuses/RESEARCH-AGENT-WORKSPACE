# Web Search 與 Citation 完整執行計劃
計劃位置：harness/plans/2026-10-20-web-search-citation/
準備狀態：**可啟動**。本次是規劃交付，沒有實作已完成的宣告；階段執行狀態與實際證據只由 [build-log.md](build-log.md) 擁有。

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

未觀察：目前真實搜尋可用率、瀏覽器可啟動性、五分鐘行為、修正後效能、測試是否通過。不得把 S1 引述或上述靜態檢查當作動態成功證據。

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
1. **授權邊界**：本次只寫、審查、驗證並本地 commit 計劃。未來使用者明確啟動此計劃後，持續執行已列明的必要工作、範圍內修正、測試、計劃維護與逐步 commit；不在階段結尾要求人工 review/approve/continue。啟動提示在檔案中不代表現在已啟動。
2. **第一個動作**：讀本 repository 適用指令、GOALS、本文件、build-log，再唯讀核對 pwd、branch、HEAD、status、index、Conda 工具路徑。若 conda 未在 PATH，使用現有安裝的 bin/conda 或先初始化既有 Conda；目前本機位置為 /home/minervamuses/miniconda3/bin/conda，搬移後應重新發現，不能改用 system Python。只在 GUI 進行變更；若別人已換分支，不自行切回，記錄實際阻塞。記錄原有 dirty/index 項目；不 reset/stash/clean/amend/rebase，也不更改 worktree。
3. **檔案範圍**：各階段列出的 vendor 現行 src、必要既有測試與說明、app/agent/mcp.py/startup.py，必要且具證據的 session 接點，以及 Citation SKILL.md 和本計劃。每項變更須對應 G/R/AC。優先每步最多三個 production 檔案；若一個不可分的共享生命週期修正確實需要四檔，P4-S1 已列明最小因果範圍，未來啟動該具體計劃時一併執行，不再創建泛用框架或擴到其他模組。
4. **每個改動步驟必須 commit**：P1-S1 等每個穩定步驟是一個完整可檢查的改動單位，不是一次編輯工具呼叫。完成該步的 focused 檢查、更新 build-log 後，立即在 GUI 本地 commit，成功後才開始下一個改動步驟。不得累積多步最後一起提交。測試失敗可 commit 範圍清楚的 checkpoint，但必須標示未完成、保留失敗證據，不能讓依賴該成功條件的步驟繼續。純唯讀檢查不造空 commit；若產生證據／計劃改動則納入該步 commit。
5. **commit 作法**：先看 git status --short、git diff、git diff --cached --name-only；只 git add -- 明確本步路徑，檢查 staged diff/whitespace，再 git commit -m 'type(scope): outcome [P?-S?]'。不 git add .、不把別人的 staged 變更帶入。用穩定步驟 ID 從 git log 找 commit，不為記錄自身 hash 再製造遞迴 commit。規劃 authoring 使用 A0。root .gitignore 忽略 build/；首次新增此計劃 phase Markdown 時只對逐一列名的 planning files 用 git add -f，絕不 force-add dist 或生成資料。
6. **禁止事項**：不 push、不創造或切換 branch、不 fork worktree、不改 Git identity、不繞 hooks、不刪未追蹤資料、不替使用者發佈。不得使用 paid model/provider、改依賴／lock／環境、建立新服務或通用架構。外部查詢限必要公開唯讀 smoke，不做付費 LLM 遵循測試。
7. **問題處理**：一般失敗先記錄→提出單一因果假設→最小修正→focused 重驗。遵守最多兩次 focused 修正失敗即停止該問題的規則；仍可推進互不依賴工作。外部封鎖／缺安裝／缺權限／需新依賴等記錄為未滿足前提，採現有能力替代；沒有安全替代則隔離受影響步驟。全部可做工作完成後一次彙報已完成、失敗、未驗證與恢復條件，不在中途反覆要求人工審查。
8. **不可假裝越過硬阻塞**：commit 失敗（hook、identity、index 污染等）不得宣稱已提交，也不能繼續累積下一步改動。先做不破壞他人狀態的修復；仍失敗時只完成剩餘唯讀分析與紀錄，最後報具體 blocker。host 強制權限、真實資源／權限缺失或使用者後來的停止指令優先，計劃文字不授予額外外部權限。
9. **修訂與恢復**：中斷後以 build-log 與 git log 的步驟 ID、實際 diff、目前 dist 新鮮度重新對帳，確認外部 smoke 是否已做，避免重複。必要時修訂未開始步驟的實作細節及對應驗收並 commit；不變更使用者目標或把失敗改成通過。若乾淨結果已成立，標明復用的 commit/測試環境，避免重做。
10. **自動化限制**：此契約指執行 turn 內持續完成，沒有建立背景排程或自動喚醒承諾。使用現有宿主能力續作；交接入口不依賴作者私人路徑。

## 必要檢查與成本
已從現有檔案查到、但規劃時未執行的命令：
- 工作目錄 app/vendor/web-search-mcp：conda run -n app --no-capture-output npm run build；conda run -n app --no-capture-output node tests/test-search-result-retention.mjs。
- 工作目錄 app：conda run -n app --no-capture-output poetry run pytest tests/test_citation_skill_activation.py tests/test_tool_access_matrix.py -q。
- 工作目錄 app：conda run -n app --no-capture-output poetry run pytest tests/test_mcp.py tests/test_mcp_stderr_log.py -q。
- 工作目錄 app：完整 app suite 用 conda run -n app --no-capture-output poetry run pytest -q，所有程式修正後最多一次。若前置資訊顯示會超過十分鐘或觸發外部付費行為，記錄暫不執行與原因，不能把 targeted tests 冒充完整 suite 通過。
- 新 Node 回歸檔屬 P3/P4 待實作的少量原生 assert 測試，不是已存在命令；先確定實際路徑才執行。沒有 npm test，不新增 framework。
- 每步執行 git diff --check / git diff --cached --check；不執行全庫 format。
- 網路 smoke 最多六個有明確目的的公開請求組，累計最多八分鐘；每組單獨有界，必要時用低於 300 秒的部署 timeout。deadline 邊界用縮短預算與可控本地例子驗證，不等待多輪五分鐘。限時耗盡記錄未驗證，不做 sweep。
- 量測只取三類必要路徑與同一小樣本的必要重現，不建 benchmark framework、不做大樣本或全資料集。
- 需要 Chromium 可執行但尚未確認。若缺失不自動 install；先完成離線測試，最終列 AC08/AC14 未驗證。已安裝 npm/Poetry package 不需重新 install。

## 完成判準
G1–G8 及原 AC01–AC14／新增 AC15 的必要條件均有實際證據；程式在受影響 focused checks 與可執行的完整 suite 符合預期，真實 Agent→dist 輸出、設定、候選保留與時間／收尾成立；所有改動步驟 commit，分支仍 GUI、無 push、無無關檔案。D05 必須有量測後決策，非必須實作重用。

若仍有失敗／必要檢查不可用，交付報告必須稱「部分完成／有阻塞」，不可因已走到最後一階段就宣稱工程完成。計劃的 ready 僅表示路線足以啟動。
