# Citation／搜尋可靠性與耗時診斷：執行路線

計劃根目錄：`harness/plans/2026-10-19-citation-search-reliability/`。本文件只擁有路線與執行契約；實際狀態唯一記錄在 [build-log.md](build-log.md)。

## 可開始程度

**已具體化第一批與後續條件路線，尚未實作。** P1、P3 的最小修改可在使用者啟動後進行。P2 的 source／安裝目標已找到，但修改外部 checkout 與替換實際安裝須獲明確範圍授權；P4 優先確認三個檔案內的 callback 路線是否足以提供可靠統計，若需更多 production files 先按既有規則核准。P5 等待具體 timeout／重試政策確認。這些執行門檻不阻止本次計劃完成。

P6–P10 從第一批產生的新資料開始，僅量測已選定問題；量測後最多提出三個具體下一步並停在後續範圍決策點。沒有新資料就記「尚不可歸因」，不自動跑付費模型補證據。

## 文件分工與閱讀順序

1. 適用的 AGENTS.md → [GOALS.md](GOALS.md)：目標、來源、不可退讓條件。
2. 本文件：啟動範圍、依賴、成本與停止規則。
3. [build-log.md](build-log.md)：目前證據、阻塞與下一步。
4. 對應 [階段文件](#路線)，必要時讀 [蒐證](context/evidence.md)及[來源文件](context/SOURCE-BRIEF.md)。
5. [PROMPTS.md](PROMPTS.md)提供可直接使用的啟動／恢復／修訂入口；[plan-index.json](plan-index.json)只存靜態關係，不存進度。

## 基準與環境

- 主專案 root：`/home/minervamuses/research-agent-workspace`，Python／Poetry root 為 `app/`；目前主專案 HEAD 與來源文件一致，未實作任何修復。
- 本機 WSL Ubuntu-24.04：Bash、`/usr/bin/git`；Conda `app` 的 Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0。不是 Windows Python／Git；`rg` 未安裝，可用 `git grep`／`grep`。
- Web Search source：`/home/minervamuses/mcp-servers/web-search-mcp`，HEAD `eeb03f88525cbf74c4019e59a3fea45a537a760b`。
- 實際 Web Search 安裝：`/home/minervamuses/.local/share/mcp-servers/web-search-mcp`，不是 source checkout；執行的是其 `dist/`。P2 必須跨越此交付邊界。
- 主專案已有刪除及未追蹤輸出；外部 source 有使用者修改的 `package-lock.json`。只讀狀態與精確保留規則見蒐證；恢復時重新讀取，不能把本次快照當永久狀態。
- 原始碼確認：前端包裝可遮蔽開頭 slash；全文重複組裝；外部 fallback 可遺失結果；工具進度為批次觀測；Citation 先截斷後本地年分過濾。
- 現有 `agent.diagnostics` 已安裝本機 rotating log，通常為 `~/.local/state/research-agent/logs/desktop-backend.log`，可被 `AGENT_LOG_DIR`／`XDG_STATE_HOME` 覆寫。不硬編另一個儲存系統。
- 尚無足以分解歷史五分鐘的逐呼叫 trace。當前蒐證不等於修復後驗收；來源與限制見蒐證表。

## 首次執行的環境與工作區 gate

在 WSL Bash 中先執行以下唯讀命令；其他主機須先確認實際 Linux root 與 Conda 路徑，不能照抄成本機路徑：

```bash
cd /home/minervamuses/research-agent-workspace
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
pwd
command -v bash git python poetry node npm
python --version
poetry --version
git rev-parse HEAD
git status --short
git diff --cached --name-status
```

重新讀適用指令；確認 production diff 與計劃基準是否變動、目前授權涵蓋哪些階段、所選測試是否可能連網。環境不符先停，不安裝、不建立 venv、不使用系統 Python。第一個業務動作：P1 讀 `composeTurnText()` 與既有段落留言測試，將目前失敗案例連接到 backend 的真實技能選擇邊界。

## 路線

| 階段 | 一個主要後置條件 | 前提 | 目標／文件 |
|---|---|---|---|
| P1 | 明確 Citation 選擇通過段落留言組裝後仍有效 | 環境 gate、實作啟動 | G1：[技能啟動](build/phase-01-activation.md) |
| P2 | source 修復產物確實抵達實際 MCP 安裝，所有結束分支保留最佳結果 | 環境 gate、外部目標授權 | G2：[搜尋結果保留](build/phase-02-search-results.md) |
| P3 | 模型輸入全文去重，但 snapshot／版本與重試語義不變 | 環境 gate、實作啟動 | G3：[上下文去重](build/phase-03-context.md) |
| P4 | 真正執行邊界的最小 trace 可持久保存並串接 | 環境 gate、檔案範圍 gate | G4：[最小計時](build/phase-04-timing.md) |
| P5 | 實際 SDK 的有限 timeout／重試離線驗證成立 | 環境 gate、具體政策決策 | G5：[SDK 穩定性](build/phase-05-retry-policy.md) |
| P6 | 用真實程序成本決定 MCP session 是否需要重用，選中時完成有界修正 | P1–P4 完成；新資料與後續範圍核准 | G6：[MCP 生命週期](build/phase-06-mcp-lifecycle.md) |
| P7 | 用引擎／瀏覽器資料選定有證據的搜尋改善，選中時保留品質與結果 | P1–P4 完成；新資料與後續範圍核准 | G7：[引擎與瀏覽器](build/phase-07-engine-budget.md) |
| P8 | 用 provider 分段資料選定有限等待與不完整結果政策 | P1–P4 完成；新資料與後續範圍核准 | G8：[Citation 等待](build/phase-08-provider-budget.md) |
| P9 | 選定修正後合格候選先過濾再截斷，既得資料能補位 | P1–P4 完成；結果資料與後續範圍核准 | G9：[候選保留](build/phase-09-candidate-filter.md) |
| P10 | 選定調整後，補查有明確缺口並能在無新證據時收斂 | P1–P4 完成；action trace 與後續範圍核准 | G10：[補查與停止](build/phase-10-research-stop.md) |

P1–P4 無程式上的相互依賴，可按共享檔案衝突安排順序；推薦 P1 → P2 → P3 → P4，不以「同批」包成大範圍 patch。P5 不依賴上述計時結論，既有故障風險即可提出修正。P6–P10 互不強制依賴，編號只對應原文。後續選中一項時，執行者須把該階段的實際修改檔案、預算與驗收決策補入 log；若新增真實依賴，同步更新路線與 index。

## 執行契約與審批

本計劃描述工作，不能自行授權。此次只寫、驗證、commit 計劃；後續只有使用者明確啟動的範圍可執行。已授權的有界範圍內可自行完成一般選擇、修正與驗證，不在每個階段重複請示。新上下文從 log 恢復同一授權，不把 PROMPTS.md 的引文當已收到指令。

每個 focused fix 先確定因果與最小寫入集合。修改超過三個 production files、較小局部改動仍可行卻新增 persistent module、依賴／lock／環境變更、public API／schema／protocol 改動、新服務／cache／持久化層／並行模型、廣泛 refactor，均須依使用者規則另行取得明確核准。先把可安全完成的調查與具體方案做好，再提出需核准的範圍、較小替代方案不足之處、預期成本和維護負擔；不要用拆步驟規避同一修正的三檔限制。

計劃不要求加依賴。外部 Web Search 僅限具名 source 及已辨識安裝目錄，修改與安裝授權須明確；不把其使用者 lock diff 帶入本專案或覆蓋。source、build 產物、實際執行檔各自核驗。不直接修 dist 當永久解決方案，不任意 clone、切 branch 或開 worktree。

執行檢查以既有 offline fixtures／fake model／mock transport 優先。付費 provider、模型推論、GPU、完整資料集、全參數搜尋及預計超過約十分鐘命令皆需事前核准。免費公開搜尋也僅在選定的測量需求下跑小樣本，不開抓取／benchmark campaign。沒有可用歷史資料時先報缺證，不能把「驗收需要」當支出授權。

每個已授權修正完成後記錄觀察與代表性輸出。Git 政策沿用專案：本次已授權的是此計劃 commit；未來實作 commit、push、merge、rebase、分支或 worktree 操作須另有明確授權。若啟動指令明確授權 scoped local commits，可依完成的 coherent step 提交，subject 含穩定步驟 ID；不為補記自身 hash 產生遞迴 commit。不 push、不改身份、不繞過 hooks。

## 檢查與第一批完成 gate

各階段有最小 targeted checks。主專案 Python 命令工作目錄為 `app/`，環境為 Conda `app`；前端命令工作目錄為 `app/desktop/`。下列既有入口已由程式／package scripts 核實，尚未在本次執行：

- `poetry run pytest <階段列出的既有測試檔> -q`。
- `npm test`：既有 Node tests；可使用 `node --test --experimental-strip-types tests/conversations.test.ts` 執行指定測試。
- `npm run build`：`tsc --noEmit && vite build`，僅前端改動時。
- `poetry run pytest`：全套僅在已確認相關且合理便宜時於第一批末執行一次；預估超過十分鐘或會啟動外部成本則先問。不能因此省略未解釋的必需驗收。
- `git diff --check -- <本次路徑>`；精確檢查 dirty／staged 狀態。

第一批需一個連通的離線代表案例：主請求 `/citation`＋段落留言 → 真實前端組裝 → 後端技能啟動 → 截獲實際模型輸入（同一全文一份、引用完整）→ fake model／tool 執行 → durable trace 可回查。P2 另以真正安裝 dist 的離線四情境驗證；Citation 的成功不代表 Web Search MCP 已驗收。測試可串接現有 TS 與 Python 入口或臨時輸出，不建立新框架，不把兩端各自寫死的字串測試稱為跨層整合。

只在授權的正常 GUI 使用中補一次真實樣本；若需要付費模型，須等獲授權或等使用者下次正常使用，先交付「離線正確性已驗證、實際耗時未驗證」。完整 frozen snapshot 的儲存／重試檢查與 log 不洩漏內容是必要反例。針對未變動 subsystem 不擴大測試矩陣。

## 新資料如何決定 6–10

P4 完成後優先讀既有新 log，列出該 turn 的總經過時間、每次模型區間（包含 SDK 內部等待但不臆測其重試次數）、每個工具區間及重疊、無法分配的空隙、Citation action 和結果／摘要數。分開成功與失敗、冷／暖程序、不同 query；不以工具數推算模型輪數。

必要細分只針對資料指向的候選：P6 程序建立／初始化／關閉；P7 引擎／browser／retry／fallback；P8 limiter queue／HTTP／backoff。第一批不預建全部細分探針。記錄「哪一段實際占用使用者等待、是否丟結果／反覆無新證據、最小修法」後最多提出三個選項。數值未定就提出有依據的預算供選擇；延遲改善與結果品質分開報。

G9 的反例可先靠既得候選離線證明，不必捏造其耗時占比。已知正確性缺口不會因量測排序被寫成不存在，但依原文留到後續選定範圍。

## 失敗、恢復與完成

兩次 focused implementation 嘗試失敗後，停止該問題並報證據、最可能未解原因及最小下一步；一次 expensive attempt 失敗／無改善後不得無核准再跑。同時可完成其他已授權且獨立的項目，不以不相關失敗開新清理工作。

每次中斷在 build-log 記錄：步驟 ID、實際檔案、命令／輸入、結果、證據位置、限制、阻塞和下一個動作。恢復先比對 Git diff、實際安裝 checksum 與 log，判斷哪些作用已發生；不盲目重跑 provider 或覆蓋外部安裝。還原只針對本次 patch／先前備份，保留原本工作，不用整樹 reset。

完成區分三層：
1. **計劃交付**：文件完整、內容與結構核驗、從 WSL scoped commit；不代表修復。
2. **第一批完成**：G1–G4 代表行為通過且必要 checks 完成；缺實際自然使用 trace 就明記性能待量測。
3. **後續選定範圍完成**：G5 或被明確選中的 G6–G10 達成各自驗收。未選項保留 Not started 與理由，不假稱全部優化完成。沒有任何「必須縮短至 X 秒」的虛構總驗收。
