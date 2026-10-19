# 執行紀錄

本檔是唯一狀態 owner。2026-10-19 起依 PROMPTS 全計劃啟動執行（見下方「執行事件」X 系列）。完整啟動後沿用 P1–P10 自主決策、問題留存與逐步 WSL commit 契約，不逐項索取授權。最新規則見 [PLANS](PLANS.md)及 A4；A1–A3 保留為原版交付歷史，不覆蓋最新指示。

## 目前階段

| ID | 狀態 | 已有證據 | 實際前提／待解事項 | 下一步 |
|---|---|---|---|---|
| P1 | Complete | X1：真實 composeTurnText→DesktopService→Citation 離線案例；反例 3 種 | 無 | P3/P4 沿用同一代表案例 |
| P2 | Not started | E2／source、dist、四情境腳本 | 核對有效入口並保留 lock diff；無逐項授權門檻 | 修復後斷言、source/build/安裝驗收與外部 commit |
| P3 | Not started | E3／重複全文已確認 | 可獨立於 P2 進行 | 模型投影去重及 snapshot／retry 驗收 |
| P4 | Not started | E4／既有 logger | 驗 callback／統計接點，記必要局部檔案集合 | 真 graph＋fake tools 驗 ID 與計時 |
| P5 | Not started | E5／SDK 實版讀碼 | 執行者選有限政策並記錄依據 | 恢復或重建最小 offline probe，直接推進 |
| P6 | Not started | E6／echo 歷史記錄 | P2、P4 與真搜尋器程序資料 | 量測並自主判定／完成必要重用 |
| P7 | Not started | E7／source 機制 | P2、P4 與 engine/browser 資料 | 逐一選有證據的主變數並驗證 |
| P8 | Not started | E8／gather/retry 機制 | P1、P4 與 Citation/provider 資料 | 分段歸因、選保守政策並驗證 |
| P9 | Not started | E9／過濾順序 | 可用既有 offline fixtures，無其他階段硬依賴 | 建立補位反例並修復驗收 |
| P10 | Not started | E10／工具與技能邊界 | P1、P3、P4 與新 action trace | 分析缺口、調整並驗證停止行為 |

問題出現時在下方追加穩定 ID、原因／假說、已嘗試命令、結果／證據、採用替代方案、剩餘限制與下一步。保留 Not started／In progress／Blocked／Complete 狀態；有證據不需修改時於結果欄明列，缺證或待驗不能算 Complete。問題不會自動停止其他工作。

## 規劃事件

### A1 — 2026-10-19：環境與基準

已用 Windows host 呼叫 WSL Ubuntu-24.04 Bash 唯讀確認 repo root、HEAD、Linux Git 與 Conda app Python／Poetry／Node。起始 staged 空，既有刪除與 app/store 未追蹤輸出保留；詳細快照在 [蒐證](context/evidence.md)。

### A2 — 2026-10-19：來源與因果核對

主代理核對計時／logger／Citation provider、候選與 SDK 接點；兩個並行唯讀子代理核對 GUI／模型上下文及外部 Web Search／SDK／MCP。結果已合入 E1–E10。沒有執行 app tests、build、live model/provider 或修改 production code。503／timeout 舊探針未找到，歷史 Bing→final zero 完整鏈未獨立核實；不可算通過。

### A3 — 2026-10-19：規劃審查與驗證

- **來源與格式**：以 Conda app Python 比對 SOURCE-BRIEF.md 與附件的 UTF-8／換行正規化內容，相等；計劃全部檔案無 CR，維持 LF。
- **結構 lint**：在 WSL 的 Conda app 執行以下唯讀命令。第一次因 plan_id 以日期數字開頭回 INVALID_IDENTIFIER；改為 citation-search-reliability-2026-10-19 後重跑，結果 ok=true、errors=[]、warnings=[]、checked_files=17。這只證明靜態結構／本機連結，不是應用行為或授權證明。
- **獨立審查**：另一位未參與撰寫、未繼承撰寫對話的子代理讀完整計劃與來源 brief，抽查 slash/backend、Web Search source/package scripts 與固定 SDK。沒有發現 material findings；確認 B1–B10 的目標／路線／驗收、首次啟動、跨 source→安裝交付、失敗／中斷恢復均可辨識。這是該次審查結果，不是品質或模型能力的普遍保證。
- **主代理語義檢查**：確認 first batch 與條件後續的範圍、所有階段依賴無循環、舊故障探針不當修復驗收、未選後續不標 Complete；由狀態表模擬新啟動與中斷恢復。
- **Git 範圍**：WSL git 僅 stage 本計劃 17 個檔案；階段文件因根 .gitignore 的 build/ 規則以精確新計劃路徑 force-add。scoped git diff --cached --check 通過，沒有納入既有刪除、app/store 或外部 lock 修改。
- **提交識別**：本次交付使用 subject `docs(plan): define citation search reliability roadmap [A3]`，提交 hash 以實際 WSL Git 結果為準；不在檔內預填 hash 或為補記自身 hash 再提交一次。
- **限制與下一步**：未跑 app tests／build／live model/provider、未做任何 production 修復。計劃已完成內容審查，執行可開始程度及未決 gate 以 PLANS.md 為準；下一個業務動作仍是取得明確啟動後執行 P1。

```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
python /mnt/c/Users/garyc/.codex/skills/long-horizon-plan-author/scripts/validate_plan.py /home/minervamuses/research-agent-workspace/harness/plans/2026-10-19-citation-search-reliability --json
git diff --cached --check -- harness/plans/2026-10-19-citation-search-reliability
```

上列 validator 路徑是本次編寫主機的實際驗證位置；未來執行者無須具備此技能檔才能實作。後續若工具不可用，按 GOALS／PLANS／phase 的目標、依賴、連結與授權做等價人工核對。

### A4 — 2026-10-19：改為全計劃自主執行與逐步提交

使用者明確更正：「我要他自動完成所有任務，並逐步 commit，遇到問題記錄下來，而不是一直停下來找我。」

原版 PROMPTS 的 P1–P4 限制、後續使用者挑選、一般設定／外部交付／commit 另請示，與此指示不符。此次修訂同步 GOALS、PLANS、PROMPTS、受影響 phases、依賴 index 及目前狀態；技術驗收與原蒐證保留。全計劃啟動包含具名外部 source/build/安裝、各 repo WSL scoped commits；日常技術決策由執行者記錄後完成。未授權費用、依賴／環境、計劃外破壞性操作仍有界線，但只阻擋受影響工作。

移除 P6–P10 對整批 P1–P4 的不必要共同阻塞，保留每項真正資料前提；P9 可獨立用離線反例修正。增加問題處理、最終集中回報與完成狀態定義，避免「記錄問題＝全部完成」。

目前未實作 production code，也未跑 app tests／build／live provider。另一子代理先核對舊版矛盾，再複核修訂後完整入口、契約、各階段、狀態表與 index，未發現剩餘實質自主契約矛盾。WSL Conda app 結構 lint 通過：17 files、0 errors、0 warnings；diff check 最初找到 PLANS.md 檔尾多一空行，修正後通過。此次僅修訂 13 份既有計劃文件，原始 brief／蒐證與 A1–A3 歷史保留；未改 production code、未納入使用者既有刪除／app/store。本次修訂使用 commit subject `docs(plan): enable autonomous execution with stepwise commits [A4]`，實際 hash 以 WSL Git 為準，不為補記自身 hash 再提交一次。

## 執行事件

### X0 — 2026-10-19：啟動 gate

WSL Bash、`/usr/bin/git`、Conda app（Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0）。主專案 HEAD `df9e58b`；`450f6d3..HEAD` 只有計劃文件，無 production 變動。起始 staged 空；使用者既有刪除與 `app/store/` 保留。根目錄出現的 `.bashrc`、`.gitconfig`、`.mcp.json` 等未追蹤項是 sandbox 掛載的 `/dev/null` 字元裝置，不是檔案，絕不 stage。外部 source HEAD `eeb03f8`，dirty 仍只有 ` M package-lock.json`；source 與安裝的 `dist/search-engine.js` SHA256 仍同為 `dad8f448…a9758`。

已知環境限制（沿用）：Bash sandbox 中 `/tmp` 唯讀，`test_sidebar_refresh_skips_repeat_scans_without_changing_session_dtos` 等硬編 `/tmp` 的測試在 sandbox 內失敗，需在 sandbox 外重跑；不是本計劃引入的回歸。

### X1 — P1：主請求 `/citation` 在段落留言組裝後仍啟動 Citation

- **修改**：只改 `app/desktop/src/conversations.ts` 的 `composeTurnText()`。有留言時，若主請求（去前導空白）以 `/citation` 加空白或結尾開頭（不分大小寫，與 backend registry casefold 一致），組成 `/<原指令> Main request:\n<其餘>\n\nRequests for frozen references:…`；其餘部分只 trim，backend `_handle_citation` 依原 raw text 取自然語言 followup，不重建 shlex。單獨 `off/none/deactivate` 不提前，維持原「Main request:」包裝，因此不會因留言變成啟動。
- **決策**：bare `/citation`＋留言也提前為 `/citation Requests for frozen references:…`，因使用者已在主輸入明確選 Citation，留言即其 prompt；無留言時 bare `/citation` 的 Usage 錯誤不變。其他 slash 指令（例如 `/status`）完全不變；`/citationfoo`、文句中 `/citation`、`@citation` 與留言內 `/citation` 都不啟動。沒有新增 wire 欄位，`skillReferences` 協定未改。
- **跨層測試**：`app/tests/test_inline_skills.py` 新增 `_desktop_compose_turn_text()`，以 Conda app 的 Linux Node `--experimental-strip-types` 直接 import 真實 `desktop/src/conversations.ts` 的 `composeTurnText`，把輸出連同仿 App.tsx 的背景 documentContext＋一個 frozen document reference 送進真實 `DesktopService.session.turn`、真 graph、真 Citation tool／service 與離線 RoutingFetcher。3 個正向參數（含大寫／換行與 bare）驗證：首次模型呼叫已綁 `citation_workflow`、prompt 含 `# Citation Skill`、主請求與留言完整、引用快照完整、實際執行一次 search 工具、回合後 runtime 與 extended thinking 恢復、未寫檔。3 個反例驗證不啟動。修復前同測試以原 TS 執行失敗（綁定工具缺 `citation_workflow`），修復後通過。
- **檢查**（app/）：`python -m pytest -q -p no:cacheprovider tests/test_inline_skills.py` 18 passed；`tests/test_desktop_service.py tests/test_citation_slash_command.py tests/test_citation_skill_activation.py` 112 passed＋1 個 sandbox `/tmp` 失敗，該測試在 sandbox 外重跑 passed。app/desktop：`npm test` 260 passed；`npm run build` 成功（只有既有 chunk 大小警告）；`git diff --check` 通過。
- **限制**：GUI 的使用者訊息顯示會變成 `/citation Main request:…`（display_input 即實際提交文字）；這是保留明確指令的直接結果，不影響已存歷史回合。真模型行為未測（無付費呼叫）。
