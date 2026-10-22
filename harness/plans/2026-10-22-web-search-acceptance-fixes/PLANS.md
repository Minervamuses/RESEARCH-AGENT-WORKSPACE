# Web Search 驗收缺陷修正計劃
- **計劃位置**：harness/plans/2026-10-22-web-search-acceptance-fixes/
- **準備狀態**：可啟動。這是規劃交付，尚未有任何實作；各階段的執行狀態與實際證據只由 [build-log.md](build-log.md) 擁有。

## 閱讀與責任
| 文件 | 擁有內容 |
| --- | --- |
| [GOALS.md](GOALS.md) | 需求、來源、決策與不變條件 |
| 本文件 | 路線、執行契約與檢查 |
| [PROMPTS.md](PROMPTS.md) | 啟動、續作、修訂、審查的入口提示 |
| build/phase-*.md | 各階段的具體工作與驗收 |
| [plan-index.json](plan-index.json) | 靜態相依圖 |
| [context/acceptance-findings.md](context/acceptance-findings.md) | 待修缺陷與重現方式 |
| [context/mutation-survivors.md](context/mutation-survivors.md) | 突變複驗清單 |

不得把 index、GOALS 或 phase 檔變成第二份進度表。

## 觀察到的基線（2026-10-22，規劃時唯讀檢查）
- **Git**：
  - repository 為 research-agent-workspace，分支 GUI，HEAD f5cf123（舊計劃結案）。本計劃的撰寫 commit [FA0] 會疊在其上。
  - tracked 與 index 皆乾淨；未追蹤的只有使用者既有的 app/store/ 與 note/20261022/。
  - 在部分宿主的沙箱中，`git status` 還會列出宿主掛載用的佔位項目，例如 .bashrc、.gitconfig、.mcp.json、.claude/、.vscode、.idea。它們不是 repository 內容：忽略，絕不 stage。
  - origin/GUI 停在 49d7048，本地領先，從未 push。
- **工具鏈（WSL Linux，Conda app）**：
  - Python 3.13.14、Poetry 2.4.1、Node v24.18.0（ICU 78.3）、npm 11.16.0。
  - conda 位於 /home/minervamuses/miniconda3/bin/conda；搬移後應重新尋找，不能改用 system Python。
  - Linux 沒有 rg，改用 git ls-files、find、grep。
- **產品現況**：
  - 驗收時重新編譯，src 與 repo dist 逐位元組相同。
  - Node 測試 3 份全過；focused pytest 67 passed；沙箱外完整 suite 1512 passed。
  - 缺陷見 acceptance-findings 的 AF 清單。
- **已驗證的實作前提**：
  - Node 內建 TextDecoder 可解碼 big5、shift_jis、euc-jp、gbk、gb18030、euc-kr、windows-1252。
  - AbortSignal.any 與 AbortSignal.timeout 可用。
  - 子程序設定 process.title 後，/proc/PID/cmdline 會變成單一個空白相連的字串，comm 也會跟著改變。
  - axios 1.10 的總時間上限可用 AbortSignal.any 組合；超過 10 MiB 時，錯誤物件仍保留回應的 status、Content-Type 與 responseUrl。
  - MCP SDK 1.15 client（StdioClientTransport）可帶 `_meta`、可用 AbortSignal 取消；給了 env 就會取代整個環境。
  - 以 `--import` 載入的 preload 與 dist/index.js 共用同一份模組實例。
  - 以上都不需要新依賴。
- **測試現況**：
  - Node 回歸檔中，只有 test-search-result-retention.mjs 接受可選的 dist 目錄參數（`node tests/test-search-result-retention.mjs [dist-directory]`），而且它還會讀取 dist 旁的 src/index.ts。
  - test-content-contract.mjs 與 test-browser-lifecycle.mjs 都是靜態 import `../dist`。因此突變複驗必須在含 src、tests、dist 的暫存複本內執行（見 F5-S3）。
  - 只有 retention 會攔截網路與瀏覽器啟動；content-contract 使用本機伺服器，lifecycle 用 stub。
  - 目前沒有任何測試會啟動 dist/index.js。
- **規劃後的清理（2026-10-22，使用者指示，見 build-log）**：FA0 之後另有清理 commit，移除舊計劃目錄與 web search MCP 的死碼：
  - 舊 content-extractor.ts、Google parser、未使用的工具函式與型別、只寫不讀的結果欄位，都已刪除；
  - acceptance-findings 的行號仍以 f5cf123 為準，可用 `git show f5cf123:<路徑>` 對照；utils.ts、types.ts、search-engine.ts 後段、enhanced-content-extractor.ts 後段的現行行號已移動；
  - 清理後 build、三份 Node 測試、focused pytest 與真實入口 smoke 都通過。
- **環境事件**：驗收期間主機重開機，`/tmp` 全部清空，舊計劃的 `/tmp/web-search-p*` 證據已不存在。驗收 session 曾三次撞到用量上限，背景工作的輸出檔也遺失（S6）。
- **未觀察**：修正後的行為；公開引擎在 P2-S3 之後的解析；Bing ck/a 以外的中介頁型態。

## 依相依順序的路線
| 階段 | 單一交付後置條件 | 相依 | 目標 | 詳細 |
| --- | --- | --- | --- | --- |
| F1 | 正文轉換忠實、晚渲染可讀、線性，分類正確 | 無 | FG1/FG2/FG8 | [正文讀取](build/phase-1-content.md) |
| F2 | Python 包裝穩健，診斷可讀，測試順序無關 | 無 | FG5/FG6/FG8 | [Python 包裝](build/phase-2-python.md) |
| F3 | 局部上限真正有界，自有 Chromium 可辨識 | F1 | FG3/FG6/FG8 | [時間上限與 Chromium](build/phase-3-timeouts.md) |
| F4 | 引擎與頁面讀取的可見事實與統計如實 | F3 | FG4/FG6/FG8 | [可見狀態](build/phase-4-status.md) |
| F5 | 入口、生命週期與契約都有會失敗的回歸測試，突變清單全部殺死 | F2、F4 | FG6/FG8 | [回歸守護](build/phase-5-regression.md) |
| F6 | 文件一致，真實入口與公開觀測完成，最後交付 | F5 | FG7/FG8 | [驗收交付](build/phase-6-delivery.md) |

- **建議的步驟順序**：F1-S1 → F1-S2 → F2-S1 → F1-S3 → F1-S4 → F2-S2 → F3 → F4 → F5 → F6。
  - 先完成使用者優先項（GOALS S1）：正文 1–2 在 F1-S1，晚渲染 3 在 F1-S2，/proc 解析 8 在 F2-S1。執行若被用量上限中斷，最有價值的修正已先提交。
  - F1 與 F2 互不相依，可以交錯進行；任一個阻塞時，先做另一個。
- F1、F3、F4 會修改同一組 Node 檔案，必須依序進行，不可平行修改。

## 一次執行到底的契約
1. **授權邊界**：
   - FA0 只撰寫、驗證並本地 commit 本計劃。
   - 使用者送出 PROMPTS 的啟動提示後，執行者持續完成計劃列明的必要工作：範圍內修正、測試、計劃維護與逐步 commit。
   - 同一個啟動同時授權依下方「宿主沙箱與執行環境」在沙箱外執行列明的檢查並連網。
   - 從啟動到最終彙報之間，任何時點都不停下來要求授權、review 或確認。遇到問題就記錄、隔離受影響的步驟，繼續其他可做的工作，最後統一彙報。
   - 本文件的文字本身不授予任何權限。
2. **第一個動作**：
   - 讀適用的 AGENTS.md、GOALS、本文件、build-log。
   - 唯讀核對 pwd、branch（必須是 GUI）、HEAD、`git status --short`、`git diff --cached --name-only`，以及 Conda 工具路徑。
   - 記錄原有的 dirty／index 項目。不得 reset、stash、clean、amend、rebase，也不更動 worktree。若分支已不是 GUI，不自行切回，記錄為硬阻塞。
   - 確認本計劃已在 HEAD 中被追蹤：`git ls-files harness/plans/2026-10-22-web-search-acceptance-fixes` 應列出 GOALS、PLANS、PROMPTS、build-log、plan-index、兩份 context，以及六份 build/phase-*.md。若沒有，代表 [FA0] 尚未提交，記錄為硬阻塞，不開始實作。
   - 在 vendor 目錄 build，並跑三份既有 Node 測試，確認基線仍綠，結果記入 build-log。
3. **檔案範圍**：
   - 各步驟列出的 production 檔，每步最多 3 個：app/vendor/web-search-mcp/src/*.ts、app/agent/mcp.py、app/agent/startup.py。
   - 既有與新增的測試、README、本計劃目錄都不計入這個數量。
   - 不修改 AGENTS.md、依賴、lock、環境定義或 site-packages。
4. **每步 commit，狀態同步**：
   - 每個 F?-S? 是一個完整、可檢查的改動單位。完成 focused 檢查並更新 build-log（事件紀錄與頂端狀態表都要更新）後，立即在 GUI 本地 commit，成功後才開始下一個改動步驟。
   - 不累積多步再一起提交。
   - 測試失敗時，可以 commit 一個標示未完成、保留失敗證據的 checkpoint，subject 寫成 `[F?-S? checkpoint]`；依賴該成功條件的步驟不得繼續。
   - 純唯讀的檢查不製造空 commit。
   - 狀態表只用四種狀態：Not started、In progress、Blocked、Complete。
5. **commit 作法**：
   - 先看 `git status --short`、`git diff`、`git diff --cached --name-only`。
   - 只 `git add --` 本步明確的路徑，用 `git diff --cached --check` 檢查空白，再 `git commit -m 'type(scope): outcome [F?-S?]'`，body 說明改動、檢查與限制。
   - 不使用 `git add .`，不帶入別人已 staged 的變更。
   - root .gitignore 忽略 build/。本計劃的六份 build/phase-*.md 已在 [FA0] 以 `git add -f` 逐檔追蹤：
     - 對它們執行一般的 `git add --` 時，雖然已 stage，仍會回 exit 1 並提示 Use -f。因此修訂 phase 檔時，改用 `git add -f -- <確切的 phase 檔路徑>` 一併提交。它們是已追蹤的計劃文件，不是生成資料。
     - 依 S4，也可以不提交 phase 檔的修訂，但必須在 build-log 記錄摘要與原因，最終彙報列出未提交的修訂。
   - 其他被 .gitignore 涵蓋的路徑（dist/、node_modules/、cache）不必 commit。用 `git check-ignore --no-index -v <path>` 判斷。
   - 絕不 force-add dist 或生成資料。
   - 需要 hash 時，從 git log 以步驟 ID 反查，不為記錄自己的 hash 再 commit 一次。
6. **禁止事項**：
   - 不 push，不建立或切換 branch，不 fork worktree，不改 Git identity，不繞過 hooks，不刪除未追蹤資料，不代使用者發佈。
   - 不使用付費模型或服務，不新增依賴或服務，不建立通用框架。
   - 外部請求只限下方預算內的公開唯讀 smoke。
7. **問題處理**：
   - 一般失敗先記錄，提出單一因果假設，做最小修正，再 focused 重驗。
   - 同一問題最多兩次 focused 修正；仍失敗就隔離該問題，繼續互不相依的工作。
   - 環境類失敗依下方歸類處理，不消耗修正額度。
   - 不論上游是否阻塞，最後都執行 F6-S4 能做的部分與最終彙報。
8. **硬阻塞**：
   - commit 失敗（hook、identity、index 被污染等；第 5 項的忽略路徑不算）時，不得宣稱已提交，也不得累積下一步改動。先做不破壞他人狀態的修復；仍失敗就完成剩餘的唯讀分析與紀錄，最後報告具體 blocker，不停下來等待。
   - 宿主的強制控制（例如拒絕沙箱外執行）與使用者後來的停止指令優先。被拒絕的動作記為環境阻塞，然後繼續其他工作。
9. **中斷與續作**：
   - 執行可能因宿主用量上限、程序結束或主機重開機而中斷。續作只依 build-log 與 git 實際狀態：
     - 以步驟 ID 對帳 git log；
     - 檢查未提交的 diff 屬於哪個步驟，從該步的檢查開始繼續，不重做已提交的步驟；
     - 確認 dist 是否與 src 一致，必要時重新 build；
     - 公開 smoke 已做到哪一組，以 evidence/F6-S3/groups.jsonl 為準，不重複發出已記錄的組；
     - 突變複驗已做到哪一項，以 evidence/F5-S3/results.jsonl 為準，略過已記錄的項目；
     - 以 `pgrep -af` 檢查命令列含本計劃暫存根目錄的殘留程序（舊的本機伺服器、測試子程序、Chromium），記錄後只終止這些程序。命令列只含 `--web-search-owner` 的 Chromium 可能屬於使用者自己的 Agent 工作，只記錄、不終止。
   - 不得假設 `/tmp` 或宿主的背景輸出檔仍然存在。
10. **證據**：
    - 依 GOALS FA11，一次性的驅動腳本、量測與公開請求，都把腳本與結果存到 evidence/步驟ID/，與該步一起 commit。build-log 引用這些路徑。
    - 已提交測試的執行結果（命令、退出碼、通過數），只在 build-log 摘要即可。
    - 單一檔案應小於 200 KB。外部頁面只保存必要摘錄，以 JSON 字串保存，避免尾端空白讓 `git diff --cached --check` 失敗；不保存 cookie、nonce、憑證或個人資料。
11. **輔助代理**：
    - 本計劃不要求平行代理或多代理覆核，執行者以 focused 檢查自行驗證。
    - 宿主若提供輔助代理，其結果須先寫入 evidence/ 或 build-log 才可依賴，也不得重複發出已在 evidence 記錄過的公開請求。

## 宿主沙箱與執行環境
舊計劃在逐指令沙箱中觀察到以下限制：
- `/tmp` 與 `~/.cache` 是唯讀的。
- MCP stdio 子程序只繼承 HOME、LOGNAME、PATH、SHELL、TERM、USER，Node 拿不到 TMPDIR 與 HTTP(S)_PROXY，Chromium 因此出現 EROFS，DNS 出現 EAI_AGAIN。
- 每條指令有自己的 PID namespace。

規則如下：
- **沙箱外執行**：以下檢查在宿主沙箱外執行（宿主沒有沙箱就直接執行），這是啟動提示授權的範圍：
  - 經真實 Python→Node 入口的檢查；
  - 經產品路徑啟動 Chromium 的檢查；
  - 公開網路 smoke；
  - 真實程序生命週期與殘留檢查；
  - 完整 suite。

  build、Node 回歸檔與 focused pytest 可在沙箱內外執行。在沙箱內直接啟動 Node，並且 TMPDIR 指向可寫目錄時，Chromium 可以啟動。
- **暫存與日誌隔離**：
  - 每次執行先建立 repository 外、本次專用的暫存根目錄：沙箱外用 `mktemp -d`，沙箱內放在宿主給的 $TMPDIR 下。
  - 所有 pytest 與真實路徑命令都要把 XDG_CACHE_HOME、AGENT_LOG_DIR、TMPDIR 指到該目錄的子目錄，加上 PYTHONDONTWRITEBYTECODE=1，pytest 再加 `-p no:cacheprovider`。
  - 不得寫入使用者真實的 ~/.cache/agent-mcp 或 ~/.local/state/research-agent/logs。
  - 直接以 node 啟動 Playwright 的命令要另設 `PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright`。若出現「Executable doesn't exist」，那是設定錯誤，不代表 Chromium 不可用。
- **產品不遷就沙箱**：不把 TMPDIR 或 proxy 加入 web_search 的環境 allowlist。
- **環境失敗歸類**：EROFS、proxy／DNS 錯誤（EAI_AGAIN、407）與宿主拒絕屬於環境阻塞：
  - 在沙箱內遇到時，改到沙箱外重跑。
  - 沙箱外仍失敗時，如實記錄並隔離受影響的驗收，其他工作繼續。這類阻塞只讓該項記為未驗證，不能據此判定 Chromium 或引擎不可用。
- **殘留程序證據**：
  - 在同一個腳本內取證：呼叫期間記錄 wrapper、Node、Chromium 的 PID、process group 與 starttime，返回後檢查是否仍存活。
  - 另開一條 ps 指令得到的結果不算證據。
  - 取證後只終止本腳本記錄的 PID 或群組，並記錄有無殘留與清理結果。

## 必要檢查與成本
pytest 與真實路徑命令都套用上一節的隔離。以下命令都已存在；新測試檔建立後才加入。
- **vendor 目錄（app/vendor/web-search-mcp）**：
  - `conda run -n app --no-capture-output npm run build`
  - `conda run -n app --no-capture-output node tests/test-search-result-retention.mjs`
  - `conda run -n app --no-capture-output node tests/test-content-contract.mjs`
  - `conda run -n app --no-capture-output node tests/test-browser-lifecycle.mjs`
  - F5-S1 建立的 `node tests/test-server-entry.mjs`
- **app 目錄**：
  - `conda run -n app --no-capture-output poetry run pytest tests/test_mcp.py tests/test_mcp_stderr_log.py tests/test_extension_mcp.py -q -p no:cacheprovider`
  - `conda run -n app --no-capture-output poetry run pytest tests/test_citation_skill_activation.py tests/test_tool_access_matrix.py -q -p no:cacheprovider`
- **完整 suite**：在 app 目錄、沙箱外，以 `timeout 600 conda run -n app --no-capture-output poetry run pytest -q -p no:cacheprovider` 執行，時機是最終程式改動之後。若因此發現 regression 或環境設定錯誤並修正，可再跑一次，全計劃最多兩次。逾時代表未完成，不是通過。
- **每步**：`git diff --check` 與 `git diff --cached --check`。不做全庫 format，不做 lint（npm run lint 在基線就失敗）。
- **公開網路**：只限 F6-S3，最多六組有明確目的的公開請求、累計最多八分鐘。每組各自設上限，必要時用低於 300 秒的部署 timeout。預算用完就記為未驗證，不做 sweep，不為湊出成功而更換案例。
- **時間邊界**：用縮短的預算與可控的本機例子驗證，不等待多輪五分鐘。
- **量測**：只量 F1-S2、F1-S4 與 F6-S2 列出的線性與延遲項目，每項一次，必要時重測同一小例一次，不建 benchmark framework。
- **突變複驗**：只做 context/mutation-survivors.md 列出的項目，在 repository 外的暫存複本進行，不修改 repo 的 dist。
- **前提**：需要可執行的 Chromium（已安裝 Playwright 1.54.2 對應的 chromium-1181）。若在沙箱外仍無法啟動，不自動安裝；先完成離線測試，再把相關真實驗收列為未驗證。

## 完成判準
- FG1–FG8 的必要條件都有實際證據。
- acceptance-findings 中處置指向 F1–F6 的每個 AF，都有「已修正並附證據」或「依規則隔離並說明」的紀錄。
- mutation-survivors 的必殺項全部被殺死，或依 GOALS FA12 記錄等效／不再適用的理由。
- 受影響的 focused 檢查與完整 suite 都通過。
- 真實 Python→Node 入口重現各項修正。
- 所有改動步驟都已 commit（.gitignore 涵蓋的路徑除外）；分支仍是 GUI，沒有 push；執行中沒有停下要求授權或 review。

若仍有失敗或無法執行的必要檢查，交付時必須寫「部分完成／有阻塞」，不得因為已走到 F6 就宣稱完成。計劃的「可啟動」只代表路線足以開始執行。
