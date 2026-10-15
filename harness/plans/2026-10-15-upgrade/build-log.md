# upgrade｜執行紀錄

## 當前實作狀態

本檔為進度、批准、實際結果、阻擋與下一步的唯一維護位置。[PLANS.md](PLANS.md) 與 [階段檔](PLANS.md#4-執行路線與驗收入口) 只維護靜態路線與驗收定義。

| 階段 | 狀態 | 實作證據 | 阻擋／下一步 |
| --- | --- | --- | --- |
| P0 | Complete | P0.S1～S3：runtime、邊界、批准與驗收入口可追溯 | 依 P1 開始文件閉環 |
| P1 | Complete | P1.S1～S2：文件閉環、離線與原生代表案例 | P2；最終整合仍由 P5 驗收 |
| P2 | Complete | P2.S1～S2：行內多引用、真實 catalog／graph、順序操作與清理 | P3；真模型合作品質留 P5 明示 |
| P3 | In progress | P2 已滿足、P0.S3 批准計劃各環節 | P3.S1 共用單項批准與各副作用入口 |
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

## P0.S3｜批准後恢復（2026-10-15，Asia/Taipei）

- **批准來源：** 使用者本回合明確說「我批准計劃裡所有環節，完成計劃」。接受 A1～A6、§3.3 Q1～Q3，以及 P1～P5 既定範圍的必要契約、局部模組、依賴與驗收環節；不再於階段邊界重複詢問。仍遵守計劃非目標與失敗處理；未具體定義的付費用量沒有自行編造額度，不推送、不改分支、不重寫歷史。
- **重新 gate：** Ubuntu-24.04／Linux bash 與 /usr/bin/git；Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0 皆 Conda app。GUI，起始 HEAD 46fa7b6f3bc7f707e1bbaa7aaf223d74c0b426d4；index 空，七個既有 tracked 修改與 P0.S1 的 SHA-256 b9490df75eae2817b211d64657be4a3e87a2ada5c212bb4b8a8f19c642fe1b06 一致，未見中斷後新增產品副作用。
- **恢復點：** 已讀適用規範、GOALS→PLANS→build-log→P0→P1；最後未驗收項為批准出口，現已具備。P0 完成，P1 開始；P2～P5 仍須前階段實際驗收。
- **變更保護：** 七個既有工作樹檔案與原 diff 已複製到 repository 外的 Linux 暫存快照；之後重疊檔案只提交本次改動，保留原有未提交差異。未建立 worktree 或改變 Git 分支。

## P1.S1｜編輯器依賴（2026-10-15）

- 依 P0.S3 的批准，在 Linux／Conda app 的 app/desktop 執行 npm install --save-exact monaco-editor@0.57.0 --ignore-scripts --no-audit --no-fund；2 秒完成，新增 4 packages，npm ls monaco-editor --depth=0 確認 0.57.0。
- 僅 package.json／package-lock.json 為本步產品變更；沒有增加 wrapper、CDN、服務或執行安裝腳本。編輯器／文件／協定同一階段的實作在進行中，尚不將其離線結果當成 P1 完成。
- 下一步 P1.S2 整合文件閉環並跑定向驗收。原有七檔變更保留在暫存基線；本 commit 不收編它們。

## P1.S2｜文件閉環與代表性原生流程（2026-10-15）

- **實作：** 新增局部 DocumentWorkspace 與 Monaco DocumentEditor；既有 NDJSON 的 workspace.select、document.open/save/apply、documentContext、document.proposed 與非 Bash 單項批准同步 Python／TS／Rust。服務將當前未儲存文字、UTF-16 選取／來源行範圍交給真 ChatSession；document_edit 等待前端送回最新編輯器快照，實際 CAS 存檔／衝突結果回到模型後才完成回答。純分析不呼叫寫入工具。文件回合臨時 Normal 並還原；未開文件保留原聊天入口。
- **版本與失敗：** 同程式讀寫序列化、磁碟 SHA-256 比對、同回合候選綁定、防重送、明示衝突選擇與再次版本檢查、寫入失敗保留候選、有限 Undo。Ask 批准時另傳最新 documentContext，等待期間仍可編輯；Bypass 仍檢查版本。去重僅同 process，外部編輯器比對與 replace 間仍有縮小但未消除的競態窗口；沒有新增持久 receipt 或跨程式交易保證。
- **發現與修正：** 實際 open 回傳 rootPath/editorRevision 原先未列 schema，補共同 fixture；獨立複核找出 saved range 過期、手動 Save 無故增加 revision、手動 Save 意外全選三項，已局部修正並加回歸案例。未修改目標或降低驗收。
- **離線檢查：** poetry run pytest tests/test_desktop_documents.py tests/test_desktop_document_service.py -q 最後 40 passed（0.64s）；包含第 40–45 來源行、重複第二段、中文／emoji／tab／BOM／CRLF、未儲存文字、分析／越界、編輯器／磁碟衝突與再變、寫入失敗、拒絕、回覆中斷重試及 Undo。服務代理另跑既有 service/session/fixture/Skill/thinking 相關子集 169 passed。Python 契約 135、TS 契約 129、Rust protocol 12 passed；cargo 首次增量編譯 66 秒，最後 2.84 秒。npm test 在初整合 194 passed；最後 documents 5、trust+documents 11（修正前兩案例）及 npx tsc --noEmit 通過。npm run build 最後成功（Vite 約 0.6s），保留 Monaco chunk size 的工具提示，未為消除提示擴大優化。
- **原生實際走查：** npm run tauri dev -- --no-watch 啟動 WSLg（已有 debug cache，編譯 0.99s）；使用 computer-use 技能的 sky API 直接操作 msrdc Research Agent 視窗。phase02 fixture root=/tmp/research-agent-desktop-phase02-upgrade-2uofbvmf，AGENT_LOG_DIR 指向其 logs。啟動後端→建立隔離對話→開 draft.md→Monaco 顯示來源行號→拖曳選取第 54 行的第二個重複段落→轉到右側保有選取→Enter 送出 fake-model 指令→顯示單項文件批准→Approve→實際磁碟只改第二段為「修正版 😀」，第一段、前 50 行與末尾換行不變。再次手動 Save 後 Undo→獨立單次批准→磁碟逐字回到原稿；未因手動 Save 產生偽衝突。
- **原生證據界線：** 上述是實際桌面／檔案流程與假模型，不是真模型品質證明。最後 saved range 修正在 native Python process 啟動後發生；其邏輯已有離線回歸，P5 必須重啟 backend 載入最終程式後再走最終代表情境。原生控制已證明可用，撤回 P0 僅因 cua API disabled 而預估須使用者操作的限制；Windows 外掛的 sky 能操作 WSLg 視窗。只在 /tmp fixture 改檔，未呼叫 provider。
- **持久化／保護：** 本次僅提交 P1 產品／測試改動及本紀錄；App.tsx/css 與既有使用者修改重疊，以 repository 外基線產生 task-only index 內容，兩處文字重疊已明確保留 HEAD 的原行為並加 P1 內容；task-only App 另以 TypeScript virtual CompilerHost 型別檢查通過。工作樹仍保有全部原修改；未收編 conversations.test.ts、RAG、main.py 或其他既有未追蹤檔。
- **下一步：** P2 行內引用與多 Skill。P1 故意僅一個文件候選／回合，P2 的先後操作必須使用真正 tool call identity 並更新已存檔上下文，不能把整回合去重誤用成忽略第二次不同操作。P3 未完成前不宣稱全專案權限已統一；P5 最終 GUI／真模型狀態仍分開記錄。

## P2.S1｜行內選單與引用契約（2026-10-15）

- P1.S2 已提交 6ac9264。此步把既有 slash composer 擴為游標所在的 @ token；滑鼠／方向鍵／Enter 插入只替換當前 token，保留前後文與插入後游標；Esc、Shift+Enter、IME composing 保留原行為。無匹配的普通 @ 文字明示作原文傳送，選單選過但已移除的 Skill 則報 unavailable；沒有新持久 registry。
- 原始 prompt 不改，送出時重新掃描當前 catalog 的精確引用及 UTF-16 位置；保留重複位置，emoji／中文相鄰可用，排除 email／網域；明確 retry 保持原提交引用與文件快照。Python／TS／Rust 共同 strict schema 新增 skillReferences，最多 128 個，未知欄位／過期位置／分裂 surrogate 拒絕。
- 檢查：Python 契約 143、TS 137、Rust protocol 12 passed；node --test --experimental-strip-types tests/inline_skills.test.ts 4 passed；與既有 conversations.test.ts 同跑 30 passed（4.76s），npx tsc --noEmit 通過。此步只證明輸入與通訊契約，多 Skill 模型實際載入／清理由 P2.S2 驗收。
- 本步只提交 App 的 task-only 變更、協定／共同 fixtures、新增定向 node 測試與本紀錄；既有 App／其他七檔使用者修改仍留在工作樹。P2 後端在相同既定階段持續實作中，尚未宣告 P2 完成。

## P2.S2｜同回合多 Skill 與文件順序操作（2026-10-15）

- P2.S1 已提交 21e476d。SkillRuntime 的局部組合保存各 Skill 真實 root／完整指引與已解析工具聯集，AgentState 同步 active_skills／skill_roots；仍沿既有 graph／policy 准入，不另建 scheduler。原始 prompt／UTF-16 引用與文件快照各自核對；引用失效與工具缺失明示，普通 email／@ 原文不誤載入。
- 真 ChatSession／graph 的假模型用實際 academic-paper-writing 與 citation catalog；驗證兩份指引、原始自然語言、有效工具集合及獨立同名 references root。明確依序的兩次 document_edit 使用真模型工具 callId，各自版本檢查／存檔，第二步讀到第一步新稿。Extended 臨時 Normal、citation registry／單次狀態與 installer authority 在成功／失敗／取消後清理，原模式還原；文件內容不成為 installer 授權。
- **複核修正：** A 已保存但 B 尚未完成的重試，先核對舊 receipt 的磁碟／編輯器版本再更新活動快照，不重寫 A；混合 installer 的 authoritative 狀態與其他 Skill 產物並存，單 installer 的防偽狀態行為保留；既有 ToolNode 同批兩個文件呼叫以局部 async lock 序列化整個候選至回寫，避免前端 busy 丟事件／等待逾時，沒有新增並行流程。
- **檢查：** 新 test_inline_skills.py 與既有 document/installer adherence 相關子集最後 42 passed（1.72s）；先前更廣 Skill/citation/policy/document/fixture 定向子集 134 passed（4.71s）。root 曾跑 poetry run pytest tests/test_inline_skills.py tests/test_desktop_document_service.py -q，15 passed（0.69s），其後代理加入上述三項最小回歸並通過。不存在真 provider／模型呼叫；不把離線合作當真模型品質。git diff --check 通過。
- **界線／下一步：** P2 行為與必要離線檢查完成；P5 將重啟最終 binary/backend 後確認原生 @ 選單與代表整合。開始 P3 所有已列副作用入口的 Ask／Bypass；唯讀準備已確認 tool admission 必須先於操作批准，既有 Bash 同步橋不可從 async 工具呼叫。

## 後續紀錄方式

每次有意義的執行步驟以階段／步驟 ID 記錄：實際改動、批准的範圍及來源、輸入／命令、觀察結果、證據位置、限制、下一步。僅依觀察把上表改為 Not started／In progress／Blocked／Complete；不得把撰寫計劃或結構 lint 當作實作完成。

中斷後先核對實際檔案與副作用，再更新上表；保留失敗及舊證據的適用範圍。啟動／續作方式只在 [PROMPTS.md](PROMPTS.md) 維護，執行政策只在 [PLANS.md](PLANS.md) 維護。
