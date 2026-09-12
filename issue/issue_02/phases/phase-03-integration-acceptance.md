# Phase 03 — 跨層整合與 Linux Desktop 驗收

## 來源

[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、前兩 phase 實際 evidence；
根 `README.md` 的 Linux Desktop commands、`main.py`、
既有 Desktop service/conversation/fixture tests。

## 目標

用一條代表性 journey 連接 Python catalog、wire validation、composer 選取、
最終 parser 與 session/restart lifecycle，並完成一次相關 broader verification。

## 範圍與非目標

範圍：已有實作的最小 integration assertions、Linux UI 人工操作、broader tests/build、
比對 diff 與所有 GOALS 成功條件。
非目標：新測試 framework、全資料 replay、live provider／MCP／Ollama、
issue 01/06/08 的修復、環境安裝、一般重構、發佈或提交。

## 依賴與前置條件

- Phases 01、02 在 build-log Complete；所有必要 focused evidence 已存在。
- Preflight 讀既有 `app/tests/test_desktop_fixture.py`、
  `app/tests/test_desktop_conversations.py`、
  `app/tests/test_extension_skill_startup.py` 的 isolation seams。
- 既有 `server._build_runtime_service`／`fixture_session.py` 提供明確 opt-in
  GUI fixture；確認 launch 環境與 owned tmp root 符合下列命令，並在實際 UI
  看到 deterministic fixture conversations／diagnostics，才進行驗收。
- **待解：** Linux IME、screen reader 與 GUI 操作能力。先 read-only 確認；
  不自動安裝、修改使用者輸入環境。缺少必要 evidence 就保持 Blocked，
  由使用者提供環境／手動結果，或明確修訂成功條件後再繼續。
- 命令成本參考 PLANS 的歷史數字，執行前再確認 cache/toolchain；
  預估超十分鐘或需要下載／安裝時取得新授權。

## 預期受影響元件

原則上只更新既有 integration tests（確有 coverage gap 時）及此 plan evidence。
不預先安排 production edits；若驗收揭露問題，記錄證據，回到 owning phase 修復，
必要時修訂未開始 plan，不把本階段擴張為清理。

## 驗證計劃

沒有獨立 Red/Green 功能開發；先讀前階段結果，補最小會區分錯誤整合的 assertion。

### 代表性 journey

1. 隔離 fake session A：由真實 registry projector 產生 catalog，含合法 one-shot Skill
   及應被排除的 collision；透過正常 DTO validators 接收，UI 輸入 `/` 顯示 A catalog。
2. `/sta` → 上下選取 → Enter：composer 得到 `/status `，cursor 在尾端，
   送出數仍為零。再按 Enter 恰一次 request，走既有 parser/local handler，
   得到 command response，沒有呼叫 LLM。
3. 選取 `/ingest` 後補參數，只驗證文字與游標，不執行 ingestion。
   合法 Skill 用現有 fake turn seam 驗證 `skill_name` routing，不呼叫 provider。
   手動輸入未知／CLI-only 命令確認 backend 拒絕。
4. A→B→A，確認每次以當次 session snapshot 顯示，draft／retry 和 active option
   不混用；重啟後相同 session ID 的舊 generation result 不能復活清單。
5. 在 tmp state 測 extension apply：running A catalog 不變；經既有 restart/
   rematerialization 流程載入新 catalog 後，新增 Skill 出現、移除 Skill 消失。
   GUI 的 "restart required" 不是當前 session 已更新的證據。
6. 在真正 Linux Desktop 驗證 Escape、blur、mouse selection、scroll、focus、
   Shift+Enter；使用可用 Linux IME 組字，候選字 Enter 不選取命令或送出，
   組字完成後可另按 Enter。以可用輔助工具觀察清單名稱、active option 與關閉狀態。
   原生環境不可用時分開列出 synthetic 與未驗證部分。
7. 核對既有 Bash ask/bypass、Extension/MCP approval、conversation persistence
   在既有離線 regression 中仍正確；不用真實 destructive commands 測 menu。

跨層資料使用現有 shared fixtures/test seams；若自動化只覆蓋分層而非真實 bridge，
在 evidence 明確指出範圍，GUI 部分仍保留實際操作證據。

### Planned verification commands

全部使用 Linux Conda `app`。於
`/home/minervamuses/research-agent-workspace/app`：

```bash
poetry run pytest tests/test_desktop_fixture.py tests/test_desktop_conversations.py tests/test_extension_skill_startup.py -q
poetry run pytest
```

第一個是 lifecycle／startup focused verification；依新修改先跑受影響 test node。
完整 pytest 只在局部通過後於最後執行一次；不重跑來追無關既有失敗。

於 `/home/minervamuses/research-agent-workspace/app/desktop`：

```bash
npm test
cargo test --manifest-path src-tauri/Cargo.toml
npm run tauri -- build --no-bundle
```

Tauri build 已包含 `npm run build`，此階段不另跑一次相同 frontend build。
隔離 GUI 啟動，於 repo root、Conda `app`（只在未來實作驗收時執行）：

```bash
SLASH_MENU_FIXTURE_ROOT=$(mktemp -d /tmp/research-agent-desktop-phase02-slash-menu-XXXXXX)
RESEARCH_AGENT_DESKTOP_FIXTURE=phase02 RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT="$SLASH_MENU_FIXTURE_ROOT" python main.py
```

`main.py` 呼叫既有 `npm run tauri dev`。同一 fixture root 保留於本次 A/B/restart
journey；僅清理本次建立且已確認 absolute path／ownership 的 tmp root。
不用預設 user runtime 來取代 fixture。以上只作 Linux source checkout 驗證，
不要求 installer/package/release。

最後在 repo root 執行 `git diff --check`，檢查 `git status --short` 與 diff，
對照 PLANS 的 authorized surface。不要重設、commit 或改 branch。

## 驗收

- [ ] 每個 GOALS 成功條件均可連到具體 observed check／UI evidence。
- [ ] representative command selection 不送出；後續明確 submit 一次，
      dynamic Skill 經 backend routing、禁用命令被 parser/eligibility 拒絕。
- [ ] A/B、restart、apply-before/after 與 stale response 對使用者顯示結果正確。
- [ ] keyboard/mouse/IME/accessibility 的實際覆蓋與限制分明，必要項目無缺漏。
- [ ] 一次 full pytest、Node、Rust suite 及 Linux source build 通過。
      無關既有失敗要分開報告；不得悄悄當成 pass 或自動擴大修復範圍。
- [ ] diff 限於直接必要 scope，無新依賴、資料遷移、live provider 或 Git mutations。
- [ ] required failure/missing evidence 均已解決，或使用者已明確修訂相應成功條件。

## 證據與交接

把 exact commands、環境、結果、journey 操作／request counts、未驗證限制與
criterion→evidence 對照記錄於 `../build-log.md`。
只在發生實際 review 時建立 `../code_review/phase-03-review.md`；
此 medium-risk scope 不要求額外固定 reviewer 階段。
失敗依 PLANS 止步／修復，不重跑昂貴程序或引入額外架構。
所有整體完成標準達成才標 Complete，報告 actual changed files 與 checks，然後停止。
