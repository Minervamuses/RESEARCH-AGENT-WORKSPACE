# upgrade｜執行紀錄

## 當前實作狀態

本檔為進度、批准、實際結果、阻擋與下一步的唯一維護位置。[PLANS.md](PLANS.md) 與 [階段檔](PLANS.md#4-執行路線與驗收入口) 只維護靜態路線與驗收定義。

| 階段 | 狀態 | 實作證據 | 阻擋／下一步 |
| --- | --- | --- | --- |
| P0 | Blocked | P0.S1、P0.S2 唯讀核對與批准提案已完成；出口未驗收 | 等待 PLANS.md §3.3 的 Q1～Q3 明確批准；之後完成 P0 出口再開始 P1 |
| P1 | Not started | 無 | P0、編輯器與契約批准 |
| P2 | Not started | 無 | P1、引用契約批准 |
| P3 | Not started | 無 | P2、權限契約批准 |
| P4 | Not started | 無 | P3、摘要傳遞及必要格式批准 |
| P5 | Not started | 無 | P1～P4、原生 GUI 驗收能力 |

## 原單檔計劃的撰寫歷史

以下為搬移前的實際紀錄，原樣保留其檢查範圍。「本次／本文件」均指原單檔撰寫回合；舊 lint 結果不是本計畫包或產品功能的驗收證據。

- 2026-10-15：讀取 S1、完整原對話的使用者決策與審查結論；確認原計劃尚未寫出，新增本文件。
- 2026-10-15：核對 Linux／Conda 工具鏈、GUI HEAD／dirty state、既有 npm scripts、編輯器／傳輸／專案 catalog 整合點；以獨立唯讀子代理補查後端整合。
- 2026-10-15：獨立審閱完整 PRD 與本計劃，確認 D1～D8、G1～G7、階段依賴、首次啟動與中斷續作沒有阻擋交付的重大缺口。補入多 Skill root／工具准入檢查，並依現有 search_text 證據移除預設重做搜尋的工作。
- 2026-10-15：以 Conda app 執行 `python /mnt/c/Users/garyc/.codex/skills/long-horizon-plan-author/scripts/validate_plan.py /home/minervamuses/research-agent-workspace/upgrade.md --json`，檢查 1 檔、0 errors、0 warnings。單檔 lint 檢查文字結構／連結；需求覆蓋與依賴圖另由人工及獨立審閱確認。
- 2026-10-15：首次空白檢查發現兩處 Markdown 尾端空白，已修正。`git diff --no-index --check /dev/null upgrade.md` 沒有空白錯誤輸出（新檔差異使 no-index 回傳 1）；另核對 UTF-8／LF 與既有 tracked diff 雜湊未變。本次只新增 upgrade.md，未實作、安裝、建置、執行應用測試或提交 Git。

## 多檔遷移紀錄

- **M1｜2026-10-15：** 使用者要求改用多檔計畫包。將原 upgrade.md 的目標／決策、基準／設計／政策、P0～P5、進度／歷史分別轉入本包；保留 G1～G7、D1～D8、A1～A6 及階段 ID。產品實作尚未啟動，現況見上表。
- **M1 來源指紋：** 原單檔 UTF-8 內容 SHA-256：`a44f79fd8ae10cbfc70dbdb533d914b728aa64efa7753afdbd24d282c276e3c7`。根目錄 upgrade.md 已改為導覽入口，不另留第二份可變更的全文計劃。
- **M1 環境核對：** GUI 分支、HEAD fb055707ba6db6fb48c832887ec164f765ab47ac；WSL Ubuntu-24.04／Conda app、Linux Git。既有 tracked diff SHA-256 為 `b9490df75eae2817b211d64657be4a3e87a2ada5c212bb4b8a8f19c642fe1b06`，staged diff 為空。本次沒有執行應用測試、建置、依賴安裝或 Git mutation。
- **M2｜結構檢查：** Conda app 執行 `python /mnt/c/Users/garyc/.codex/skills/long-horizon-plan-author/scripts/validate_plan.py /home/minervamuses/research-agent-workspace/harness/plans/2026-10-15-upgrade --json`；11 檔、0 errors、14 個 BOUNDARY_LINK warnings。這 14 個提示均為連結指向包外、repository 內的 AGENTS.md 或來源檔，不是缺檔；另以唯讀路徑檢查逐一確認目標存在且未離開 repository。沒有停用或隱藏檢查。
- **M2｜內容與連結：** 比對原單檔的目標／決策、基準、共同設計、驗證命令、執行契約與六階段全文；僅改標題、檔案責任與跨檔引用。計畫包 75 個本地連結、14 個 repository 目標、11 個標題片段均有效；UTF-8／LF、尾端空白檢查通過。原有 tracked／staged diff 保持不變。
- **M3｜獨立審閱：** 子代理唯讀比較原單檔與 11 個包內檔案，確認 D1～D8、G1～G7、A1～A6、階段依賴與驗收均保留，沒有必修缺口。只由本檔維護執行狀態；新接手者可依 PROMPTS.md 從 P0 或最後未驗收步驟續作。
- **M3｜交付：** 完成根目錄導覽及本次驗證紀錄，更新後再次檢查本包與根目錄入口。此次僅轉換計劃格式；沒有新增產品需求、開始實作、執行應用測試或提交 Git。

## P0｜首次執行紀錄（2026-10-15，Asia/Taipei）

### P0.S1｜唯讀起點核對

- **授權來源：** 本回合使用者明確要求「執行 harness/plans/2026-10-15-upgrade/ 的 upgrade 計劃」及「每一步皆需 commit」。此授權限於既定範圍的執行與逐步本機 commit；沒有批准 push、切分支、worktree、依賴、schema 或付費操作。D1～D8 未重開。
- **適用規範與讀取順序：** 使用者提供的 Personal Engineering Defaults → repository AGENTS.md（沒有其他上層／harness／app 的 AGENTS.md）→ GOALS.md → PLANS.md → 本檔 → P0。P1 僅讀取前提與驗收以整理批准項，尚未開始。
- **Runtime gate：** Windows 桌面 host 經 wsl.exe -d Ubuntu-24.04 執行 Linux bash；專案 /home/minervamuses/research-agent-workspace，Python project 為 app/。source /home/minervamuses/miniconda3/etc/profile.d/conda.sh 後 conda activate app；bash=/usr/bin/bash、git=/usr/bin/git，python／poetry／node／npm／cargo／rustc 均位於 /home/minervamuses/miniconda3/envs/app/bin。Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0、Cargo／Rust 1.97.1；poetry env info 指向同一 Conda app，未建立 .venv。
- **Git 實況：** GUI，起始 HEAD fb055707ba6db6fb48c832887ec164f765ab47ac；staged 為空（SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855），既有 tracked diff SHA-256 b9490df75eae2817b211d64657be4a3e87a2ada5c212bb4b8a8f19c642fe1b06，與 M1 一致。使用 git branch --show-current、git rev-parse HEAD、git status、git diff --stat／--binary 與 sha256sum 核對。
- **既有變更保護：** 七個既有 tracked 修改（App.tsx、styles.css、conversations.test.ts、rag/embedder/ollama.py、rag/store/chroma_store.py、tests/rag/test_tools_contract.py、main.py）及 .project-audit/、tests/test_desktop_launcher.py、hallucination.md 不收編、不還原。既有未追蹤計畫包作本次執行基線納入版本；六個 build/phase-*.md 受 .gitignore 的 build/ 規則忽略，僅對這六個已指定階段文件使用精確路徑強制加入，不修改 ignore 規則。根目錄 upgrade.md 保持原樣。
- **恢復與副作用核對：** 本檔仍記錄 P0～P5 未開始，Git 沒有本次執行 commit，實際 dependency 清單沒有 Monaco；未發現可當成已驗收升級的既有產物。未執行安裝、應用測試、build、launcher、provider／模型呼叫或服務操作；原生 binary 與 fixture 邊界待 P0.S2 核對。首次唯讀命令因 Linux 沒有 rg 中止，已改用 find／grep 繼續；沒有因此安裝工具。
- **結果／下一步：** runtime 與起始狀態核對通過；產品功能未實作或驗收，A1～A6 與必要依賴／協定尚未批准。繼續 P0.S2 的唯讀核對與具體批准提案；完成後只等待真正缺少的批准。

### P0.S2｜契約、驗收入口與具體批准提案

- **起點／持久化：** P0.S1 已提交 874fb8e（docs(upgrade): record P0 runtime checkpoint）；11 個既有計畫包檔納入版本，既有產品 diff SHA-256 仍為 b9490df75eae2817b211d64657be4a3e87a2ada5c212bb4b8a8f19c642fe1b06，staged 在 commit 後為空。該 commit 不代表任何產品驗收。
- **本步改動：** 僅在 PLANS.md §3.3 補入 P1 的最小 schema 表、字元／傳輸界線、重試限制及 Q1～Q3 具體批准包；本檔記錄結果。A1～A6 仍是提案、未寫成使用者接受；D1～D8 不變。P2／P3 只列後續欄位候選，不提前取得契約或持久格式批准。
- **協定實況：** contract.json:2–5、407–414 的 text=1,048,576 bytes、NDJSON=2,097,152 bytes；Python protocol.py:186–197／345–356、TS protocol.ts:935–938、Rust protocol.rs:473–490 拒絕未知 params。Python protocol.py:57–60 的 string 非空限制須對新文件文字明確容許空值。現有純聊天／CLI 沒有文件上下文，不需改為新 wire 呼叫。未修改任何上述產品檔。
- **重試核對：** session.py:309–341／1231–1248 可對 completed turnId 回傳既有結果；repository.py:510–529 拒絕同 turnId 不同 input，668–674 的重試清除 tool_activities。現有 models.py:247–259 無文件寫入 receipt 欄位；因此不能把 completed-turn 去重當成寫檔後、終局回合保存前崩潰的保證。首版提案保持未知狀態不自動重放，新增持久 receipt 若確定需要須另批。
- **離線隔離入口：** server.py:405–416 選 phase02；fixture_session.py:1306–1352 使用假 session／model／knowledge／Bash，349–362 的假 runner 不啟動 subprocess，1265–1277 不載入真 MCP。仍會寫 caller 預建的 /tmp/research-agent-desktop-phase02-*；server.py:440 先安裝 logger，走查必須另設 AGENT_LOG_DIR=<fixture root>/logs，才不寫入預設 ~/.local/state/research-agent/logs。現有 fixture 尚無新文件／多 Skill；只能在批准後擴充既有 fixture，不能當成新功能已驗收。
- **可用檢查（只核對存在，未執行）：** PLANS.md §5 的 Python contract／service／Skill／permission／citation 測試均存在；另有 test_desktop_server.py、test_desktop_fixture.py。前端現有六個 tests/*.test.ts，可用 node --test --experimental-strip-types tests/<指定檔>.test.ts；npm run build 為 tsc --noEmit && vite build。Rust cargo test 僅在受影響時評估編譯成本；完整 Python suite 留到收尾至多一次。
- **原生入口／成本：** release binary app/desktop/src-tauri/target/release/research-agent-desktop 存在（7,247,032 bytes），debug binary 也存在；依 main.py:7–33 所列 inputs 唯讀核對沒有較新的 build input，允許缺少 public。修改前端後 main.py:73–79 會自動 release build，時間未知；不得把 python main.py 當廉價狀態檢查，也未啟動。WSLg DISPLAY=:0、WAYLAND_DISPLAY=wayland-0 與 socket 存在，但本回合 native computer-use API disabled，P5 原生互動須安排使用者實際走查，不能以純函式測試代替。
- **副作用證據範圍：** 本次未執行 fixture／launcher／安裝／build／應用測試／provider 或付費模型。核對時 /tmp 無 phase02 fixture root，預設 diagnostics 最後修改為 10 月 12 日；程序僅見既有 Ollama，無 GUI/backend/Vite/Cargo/pytest。這是局部觀察，不宣稱證明所有外部副作用不存在。官方 Monaco release／Vite 文件只作唯讀查閱，npm registry 經瀏覽工具不可用，未為此安裝或下載套件。
- **獨立複核與修正：** 唯讀子代理確認 schema／成本／批准界線，指出 Undo 若沿原 callId 會被去重、任意反向文字又破壞候選綁定。已在 §3.3 加入 undoOfCallId、以新 requestId 獨立辨識，反向候選從同編輯階段已成功操作的原快照推導；仍須版本檢查，不覆蓋後來修改。這只是 Q2 的明確提案，未改產品協定或新增持久記錄。
- **本步檢查：** Conda app 執行 validate_plan.py <計畫包> --json：11 檔、0 errors、14 個既有 BOUNDARY_LINK warnings；另逐一確認 14 個包外連結目標皆存在且在 repository 內，UTF-8／LF／尾端空白通過。git diff --check 通過；排除本計畫包後的既有產品 diff 雜湊與 P0.S1 相同。未執行產品測試或以 lint 代替產品驗收。
- **批准狀態／停止點：** 使用者本回合的執行與逐步本機 commit 授權有效；尚無 Q1（Monaco 套件／worker）、Q2（P1 範圍與 wire）、Q3（跨三個 production 檔／至多兩個局部模組）的明確批准。較小方案與成本／維護影響已列 PLANS.md §3.3。依 Personal Engineering Defaults Approval Gates 及 PLANS.md §6.3，P0 出口與 P1 產品修改等待這三項；其餘獨立唯讀 P0 核對已完成，P2～P5 依賴未滿足。下一步收到具體批准後記錄來源、完成 P0 出口，再依 P1 最小閉環實作並逐步 commit。

## 後續紀錄方式

每次有意義的執行步驟以階段／步驟 ID 記錄：實際改動、批准的範圍及來源、輸入／命令、觀察結果、證據位置、限制、下一步。僅依觀察把上表改為 Not started／In progress／Blocked／Complete；不得把撰寫計劃或結構 lint 當作實作完成。

中斷後先核對實際檔案與副作用，再更新上表；保留失敗及舊證據的適用範圍。啟動／續作方式只在 [PROMPTS.md](PROMPTS.md) 維護，執行政策只在 [PLANS.md](PLANS.md) 維護。
