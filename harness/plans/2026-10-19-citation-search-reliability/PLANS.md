# Citation／搜尋可靠性與耗時診斷：執行路線

計劃根目錄：`harness/plans/2026-10-19-citation-search-reliability/`。本文件只擁有路線與執行契約；實際狀態唯一記錄在 [build-log.md](build-log.md)。

## 可開始程度

**整份 P1–P10 的自主執行路線已就緒；目前只修訂計劃，尚未開始實作。** 將新版 [PROMPTS.md](PROMPTS.md) 交給執行者後，一次涵蓋所有階段、計劃內必要局部決策、具名外部 Web Search 交付及逐步 WSL local commits。不再於第一批結束、挑選後續順序、一般 timeout 設定或每次 commit 前請示。

P1–P4 優先；P5 獨立推進。P6–P10 全部要處理，執行者依證據自行排序並完成必要修正／驗收。條件性優化可以有證據地決定保留現狀，但不能因「未選中」或資料尚缺就標為完成。受阻時記錄問題並推進其他真正獨立的項目；資料前提與推薦順序分開列於下表。

## 文件分工與閱讀順序

1. 適用的 AGENTS.md → [GOALS.md](GOALS.md)：目標、來源、不可退讓條件。
2. 本文件：啟動範圍、依賴、成本與停止規則。
3. [build-log.md](build-log.md)：目前證據、阻塞與下一步。
4. 對應 [階段文件](#路線)，必要時讀 [蒐證](context/evidence.md)及[來源文件](context/SOURCE-BRIEF.md)。
5. [PROMPTS.md](PROMPTS.md)提供可直接使用的啟動／恢復／修訂入口；[plan-index.json](plan-index.json)只存靜態關係，不存進度。

## 基準與環境

- 主專案 root：`/home/minervamuses/research-agent-workspace`，Python／Poetry root 為 `app/`；production code 蒐證基準為 450f6d3，之後 71ac369 僅新增計劃；本次修訂前尚未實作修復。執行時重新核對最新 HEAD，不能將文件 commit 當作修復證據。
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

| 階段 | 一個主要後置條件 | 真正依賴／輸入 | 目標／文件 |
|---|---|---|---|
| P1 | 明確 Citation 選擇通過段落留言組裝後仍有效 | 環境 gate | G1：[技能啟動](build/phase-01-activation.md) |
| P2 | source 修復產物抵達有效 MCP 安裝，所有結束分支保留最佳結果 | 環境 gate、核對具名 runtime 入口 | G2：[搜尋結果保留](build/phase-02-search-results.md) |
| P3 | 模型輸入全文去重，snapshot／版本與重試語義不變 | 環境 gate | G3：[上下文去重](build/phase-03-context.md) |
| P4 | 真正執行邊界的最小 trace 可持久保存並串接 | 環境 gate、驗證最小 callback 接點 | G4：[最小計時](build/phase-04-timing.md) |
| P5 | 實際 SDK 的有限 timeout／重試離線驗證成立 | 環境 gate；執行者選設定並記錄依據 | G5：[SDK 穩定性](build/phase-05-retry-policy.md) |
| P6 | 依真實程序成本決定並完成有必要的 MCP session 改善 | P2、P4；真正搜尋器程序資料 | G6：[MCP 生命週期](build/phase-06-mcp-lifecycle.md) |
| P7 | 依引擎／瀏覽器資料完成必要改善且保留品質與結果 | P2、P4；engine/browser 分段資料 | G7：[引擎與瀏覽器](build/phase-07-engine-budget.md) |
| P8 | 依 provider 資料完成有限等待與不完整結果處理 | P1、P4；Citation/provider 分段資料 | G8：[Citation 等待](build/phase-08-provider-budget.md) |
| P9 | 合格候選先過濾再截斷，既得資料能補位 | 既有 service/tool 與 offline fixtures；無其他階段硬依賴 | G9：[候選保留](build/phase-09-candidate-filter.md) |
| P10 | 補查有明確缺口，無新證據時能誠實收斂 | P1、P3、P4；新 action trace／合法研究輸出 | G10：[補查與停止](build/phase-10-research-stop.md) |

正常順序以 P1 → P2 → P3 → P4 為第一批，接續 P5 與依證據排序的 P6–P10，並保持小 patch。第一批是優先順序，不是所有後續共同的硬阻塞：例如 P2 安裝暫時受阻，仍可做 P3、P4、P5、P9；資料尚不足以評估 P6，仍可處理已有離線反例的 P9。執行者在 log 寫入實際修改檔案、設定、排序依據及驗收結果後直接繼續，不要求使用者再次選階段。只有新增真實依賴時才同步更新路線與 index。

## 執行契約與審批

### 全計劃授權與自主決策

使用者最新指示是「自動完成所有任務，並逐步 commit，遇到問題記錄下來，而不是一直停下來找我」。它取代舊版只做 P1–P4、量測後只提三個選項就停、外部交付和每次 commit 另請示的安排。此次操作仍是修訂文件；收到完整啟動 prompt 的執行者須連續完成 P1–P10，跨上下文保留同一授權。文件中的啟動引文不是要求修訂者當下執行。

在具體十項問題內，執行者自行決定最小實作、保守有限的 timeout／retry 預算及後續順序，先把證據、取捨與驗收寫入 log，再實作／驗證。不要把尚未由使用者指定的參數偽稱使用者決策。P4 必要的額外統計插點、P6 session 生命週期、P7/P8 搜尋等待與取消安排、P10 有證據必要的向後相容 tool action，均按此明列範圍處理，不因跨三個 production files 或局部介面接點而反覆請示。仍須先證明較小做法不足，逐檔通過因果範圍檢查；此例外不授權泛用 framework、計劃外重構、破壞性 public API 或持久化格式改動。

### 具名外部交付

完整啟動範圍包含主專案，以及 `/home/minervamuses/mcp-servers/web-search-mcp` 內與 P2/P7 直接相關的 source 修正、現有依賴 build、備份及更新 `/home/minervamuses/.local/share/mcp-servers/web-search-mcp` 必要產物。先核對有效 launch 入口，若實際指向別處，先辨明差異與安全替代，不盲目覆蓋未知安裝。保留既有 lock diff；source、build 產物、實際執行檔各自核驗。不直接修 dist 作永久方案，不中斷使用者正在執行的回合。

### 成本與真正邊界

優先既有 fixtures／fake model／mock transport／可重播結果，必要免費公開搜尋只跑小代表樣本。最新自主要求不等於無限支出或任意擴張：未另獲授權的付費 provider／模型呼叫、GPU、完整資料集、參數 sweep、預計超過約十分鐘的昂貴命令、依賴／lock／環境變更、新服務／額外持久化層、計劃外架構、刪除使用者資料及破壞性 API／schema 變更，不能自行執行。先找安全低成本替代；仍缺必要條件就記錄受影響驗收與 blocker，繼續其他項目，而不是立刻結束整個任務來問。

### 逐步 Git checkpoint

每個完成且有意義的 coherent step，在通過其最小必要驗收後，直接從 WSL 使用 Linux Git 在**所屬 repo** 做 scoped local commit，不需另問。主專案步驟提交主專案；外部搜尋 source 步驟提交外部 repo；安裝目錄非 Git repo，只記錄 checksum／備份與交付結果。主專案 log 可記外部步驟的 commit hash。

每次提交前核對 staged／unstaged，僅 stage 此步驟檔案／hunks，保留使用者原有修改；已有他人 staged 內容時不得混入本次提交或擅自 reset。subject 使用 Conventional Commit 並含步驟 ID，記錄檢查與限制。不為瑣碎文字、未驗證破損程式或每筆 log 產生大量 commit；也不等全計劃做完才一次大提交。若程式路線受阻，可提交有價值的獨立診斷／計劃 checkpoint，但不得標成修復完成。無法提交時記錄精確原因、保留可恢復工作，繼續安全的獨立工作。

不 push、merge、rebase、切 branch／改 worktree，不改 Git 身分、不繞過 hooks、不為滿足 commit 要求初始化未知 repo。新上下文先對照 step ID／Git log，避免重做已提交的步驟或遞迴提交自身 hash。

## 檢查與第一批完成 gate

各階段有最小 targeted checks。主專案 Python 命令工作目錄為 `app/`，環境為 Conda `app`；前端命令工作目錄為 `app/desktop/`。下列既有入口已由程式／package scripts 核實，尚未在本次執行：

- `poetry run pytest <階段列出的既有測試檔> -q`。
- `npm test`：既有 Node tests；可使用 `node --test --experimental-strip-types tests/conversations.test.ts` 執行指定測試。
- `npm run build`：`tsc --noEmit && vite build`，僅前端改動時。
- `poetry run pytest`：全套僅在已確認相關且合理便宜時於第一批末執行一次；預估超過十分鐘或會啟動未授權外部成本時，先採 targeted 替代並記錄完整 suite 待驗，不讓該項阻止其他工作。未執行的必需驗收不能當作通過。
- `git diff --check -- <本次路徑>`；精確檢查 dirty／staged 狀態。

第一批需一個連通的離線代表案例：主請求 `/citation`＋段落留言 → 真實前端組裝 → 後端技能啟動 → 截獲實際模型輸入（同一全文一份、引用完整）→ fake model／tool 執行 → durable trace 可回查。P2 另以真正安裝 dist 的離線四情境驗證；Citation 的成功不代表 Web Search MCP 已驗收。測試可串接現有 TS 與 Python 入口或臨時輸出，不建立新框架，不把兩端各自寫死的字串測試稱為跨層整合。

優先用真實程式路徑＋離線 fixture／既有錄製輸入產生可回查 trace，接續處理其他階段；另讀已有正常 GUI 使用樣本。若特定行為／性能驗收確實需要未授權付費模型，記錄該項「離線正確性已驗證、真實模型行為／實際耗時待驗」，不要等待使用者下次正常使用而停掉所有工作。離線 trace 可驗機制與串接，不能冒充真實 provider 延遲。完整 frozen snapshot 的儲存／重試檢查與 log 不洩漏內容是必要反例。針對未變動 subsystem 不擴大測試矩陣。

## 新資料如何決定 6–10

P4 完成後讀已有新 log，必要時用最小離線重播補足事件串接。列出 turn 經過時間、每次模型區間（包含 SDK 內部等待但不臆測其重試次數）、各工具區間及重疊、無法分配的空隙、Citation action 與結果／摘要數。標記資料來自正常使用、錄製重播還是假元件；分開成功／失敗、冷／暖、不同 query，不以工具數推算模型輪數。

對 P6 程序建立／初始化／關閉、P7 引擎／browser／retry／fallback、P8 limiter queue／HTTP／backoff，按證據逐項完成最小量測與判定。執行者自主決定哪個具體改動值得做、先做什麼，依同案例驗收結果繼續下一項；不只列選項等待使用者挑選。設定值由執行者提出有據的保守值並離線確認，延遲改善與結果品質分開報。

P9 是已知正確性缺口，可用既得候選離線反例實作並驗收，不需要真實延遲排名才能開始。P10 需處理實際補查缺口與停止行為，區分技能／工具契約已驗證和真模型行為待驗。沒有瓶頸的充分證據可以支持不採某個優化方案；沒有資料只代表未判定，不能被當作不需修改或整階段完成。

## 失敗、恢復與完成

### 遇到問題的動作

先在目前有界範圍內診斷、做最小修正並驗證。兩次 focused implementation 嘗試失敗後停止該路線，記錄失敗假說、實際結果、最可能未解原因與恢復所需資料，繼續其他 dependency-ready 項目；一次 expensive attempt 失敗／無改善後不自行重跑昂貴工作。不能將此規則解讀成整份計劃一遇錯就結束，也不能藉自主要求無界重試或改成重寫。

每個問題在同一 build-log 下有穩定 ID，記錄受影響階段、原因／假說、已做嘗試與命令、結果／證據、採用的安全替代、剩餘限制及下一個恢復動作。需要使用者介入的事先累積在 log，不逐項打斷；沒有真正 blocker 時直接繼續。只有剩餘工作全被無法自行解決的條件阻擋，或需要作未授權且沒有安全替代的不可逆／支出操作，才集中回報所需的最小介入。

### 恢復

中斷時記錄當前步驟、實際檔案、已完成 checks、Git checkpoint、外部安裝 checksum、未完成作用及下一步。恢復先比對 Git diff／log、安裝與證據，判斷哪些作用已發生；不重問已存在的全計劃／逐步 commit 授權，不盲目重跑 provider 或覆蓋安裝。還原只針對本次 patch／備份，保留使用者工作，不用整樹 reset。

### 完成與最終報告

1. **計劃修訂交付**：文件一致、驗證通過、從 WSL scoped commit；不代表程式修復。
2. **階段完成**：必要行為及代表案例通過、所屬 repo 的步驟 commit 已完成，log 有證據。對 G6–G8 這類條件優化，若足夠真實資料支持保留現狀，可標 Complete 並在結果欄明列「有證據不需修改」與比較／判定；不宣稱已實作或加速。
3. **尚未完成**：缺證據、必需驗收未跑、修復失敗或必要 checkpoint 尚無法提交，就保持 In progress／Blocked 並列清恢復條件。記錄問題本身不是完成。P9 的已知正確性缺口不能用「沒有速度證據」跳過。
4. **全計劃完成**：P1–P10 各自有合乎上述定義的完成證據，所有必要交付與 commits 已完成；不捏造秒數目標。若只剩真正 blocker，停止時明確報「仍有未完成」，而非全部完成。

最後一次整理所有階段結果、主專案／外部 repo commit、檢查、未解問題及唯一需要使用者處理的阻塞。過程可簡短更新進度，不把進度回報變成一般許可問題。
