# 執行紀錄

本檔是唯一狀態 owner。2026-10-19 起依 PROMPTS 全計劃啟動執行（見下方「執行事件」X 系列）。完整啟動後沿用 P1–P10 自主決策、問題留存與逐步 WSL commit 契約，不逐項索取授權。最新規則見 [PLANS](PLANS.md)及 A4；A1–A3 保留為原版交付歷史，不覆蓋最新指示。

## 目前階段

| ID | 狀態 | 已有證據 | 實際前提／待解事項 | 下一步 |
|---|---|---|---|---|
| P1 | Complete | X1：真實 composeTurnText→DesktopService→Citation 離線案例；反例 3 種 | 無 | P3/P4 沿用同一代表案例 |
| P2 | Complete | X2：外部 commit `ddb2dba`；source／安裝 dist 各 13/13 離線通過；安裝已備份並更新 | 無；真實搜尋品質／速度未宣稱改善 | P7 量測沿用同一回歸檔 |
| P3 | Complete | X3：同版本全文只出現一次；異版本／同 fingerprint 異內容分開；retry 重用已去重輸入 | 無；端到端速度未量 | P4 沿用同一代表案例 |
| P4 | Complete | X4：per-attempt callback → INFO `turn_trace` 持久 log；並行／例外／拒絕／取消／重試／Citation 計數均驗 | 自然使用樣本尚無（使用者下次正常使用即產生） | P6–P10 讀 trace |
| P5 | Complete | X5：顯式 SDK client；每次 HTTP 600 s、重試窗 4×5 s、Retry-After ≤8 s、0＝真停用；真 wrapper/SDK＋MockTransport＋假時鐘驗 7 情境 | 真 provider 行為未打（無付費呼叫） | — |
| P6 | Complete（有證據不需修改） | X7：真 server 每次呼叫程序開銷 0.39 s；重用會讓 server 內 10 次／分 limiter 開始拒絕 | 無 | — |
| P7 | Not started | E7／source 機制 | P2、P4 與 engine/browser 資料 | 逐一選有證據的主變數並驗證 |
| P8 | Not started | E8／gather/retry 機制 | P1、P4 與 Citation/provider 資料 | 分段歸因、選保守政策並驗證 |
| P9 | Complete | X6：service 截斷前套用年份資格；真 service＋tool 反例由 2/5 變 5/5 | 無；排序未改 | — |
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

### X2 — P2：Web Search 所有結束分支保留最佳結果

- **有效入口**：本 shell、程式碼與 shell profile 均無 `AGENT_MCP_WEB_SEARCH_COMMAND/ARGS`、`XDG_DATA_HOME` 覆寫；`agent.mcp._web_search_spec()` 實際回傳 `…/miniconda3/envs/app/bin/node ~/.local/share/mcp-servers/web-search-mcp/dist/index.js`。部署前 `ps` 無 web-search 進程，未中斷任何回合。執行中的 GUI 若另有環境覆寫無法從此讀到；如日後 log 顯示不同入口，需重核。
- **Build 可重現性**：未修改的 HEAD 以 `tsc --outDir $TMPDIR/...` 重建，`.js`／`.d.ts` 與既有 dist 位元相同（只有 sourcemap 相對路徑不同），因此新 dist 的差異只來自本修正。
- **修改（外部 repo `/home/minervamuses/mcp-servers/web-search-mcp`）**：只改 `src/search-engine.ts` 的 `search()` 控制流程。`bestQuality` 起始 -1（分數 0 的非空結果也成為 best）；所有非空後的返回用 `bestSoFar()`（best results＋其自身 engine 名）；Brave 達門檻但分數低於先前 Bing 時回 Bing；迴圈結束若有 best 則回 best；`handleBrowserError` 自身失敗時，有 best 回 best、無 best 維持原例外契約。同分保留較早引擎。未改 heuristic、重試、引擎順序、browser 生命週期。search() 沒有取消機制，故「取消不得吞成成功」在此層不適用。
- **回歸檔**：新增 `tests/test-search-result-retention.mjs`（Node assert，封鎖 net／TLS／fetch／Playwright launch，stub 三引擎；參數可指定 dist 目錄）。13 情境：計劃核心四情境（中文 query 經現有 heuristic 得 0.5 分）、分數 0 保留、較佳者取代、同分穩定、全空、全失敗、錯誤處理失敗有／無 best、forceMultiEngine、停用品質檢查。舊 dist 8/13 失敗（重現遺失），新 source dist 13/13。
- **外部 commit**：`ddb2dba fix(search): return the best result found on every exit [P2]`，只含 `src/search-engine.ts` 與新測試；使用者既有 `package-lock.json` 修改未 stage，其 diff hash 修改前後相同。ESLint 唯一 error（`debugBing` unused）為既有；新增 2 個與既有風格一致的 no-console 警告。
- **安裝交付**：只有 `search-engine.js`、`.js.map`、`.d.ts.map` 三檔不同。備份至 `~/.local/share/mcp-servers/.backups/web-search-mcp/20261019T123509Z-P2/dist/`（舊 SHA256：js `dad8f448…a9758`、js.map `9a07ce6a…c074`、d.ts.map `3cbbf514…b39a`），以同目錄暫存檔＋`mv` 原子替換。安裝後 js `54edc6ae067ec1c59a3462b06194349c93d0f76281dc4d8c9e2ab7c5d6bbe48b`，與 source dist 全目錄 `diff -rq` 相同。
- **runtime 驗收**：同一回歸檔指向安裝 dist 13/13；以 app 的實際 launch spec 經 MCP stdio initialize＋list_tools 成功，列出 `full-web-search`、`get-single-web-page-content`、`get-web-search-summaries`。（server 本身把啟動訊息印到 stdout，app 端既有 sanitize_stdout 處理；裸 client 只記 parse 警告。）
- **還原方式**：把備份三檔複製回 `~/.local/share/mcp-servers/web-search-mcp/dist/`。
- **限制**：未跑真實搜尋；不宣稱搜尋加速或品質提高。

### X3 — P3：模型輸入全文去重，保留完整 frozen snapshot

- **修改**：只改 `app/agent/desktop/service.py`。新增模組函式 `_model_reference_projection()`，只用於組 prompt 的 `[Frozen references …]` JSON：版本相同性鍵為 `(rootPath, path, editorRevision, diskFingerprint, sourceText)`（不含 range）。若 document reference 的鍵等於本回合 editor snapshot，或等於先前某個 reference，該 reference 的 snapshot 省略 `sourceText`，改為 `sourceTextSameAs: "current editor document snapshot"` 或 `"referenceId <id>"`，其 range、行號、path、revision、fingerprint、選取 text 全保留；chat reference 不變。說明文字加一句「sourceTextSameAs 省略的全文在本訊息前文、range 套用於該全文」。`self._active_references`、`submitted_context`、document_edit 工具、wire 與儲存 JSON 均未改；1 MiB 檢查仍在。
- **決策**：editor snapshot 在 prompt 中位於 references 之前，因此指標只往前指；不建立全域 cache、不正規化字串、不以 path 或 fingerprint 單獨判斷。editor 的 path 經 `validate_snapshot` resolve，與 reference 原字串不同時保守地不合併（只會少去重，不會錯合併）。
- **測試**：`test_desktop_document_service.py` 新增 `_model_references()`（把投影還原為完整 references）與 `_full_text_count()`。既有兩個測試由「frozen JSON 逐字相等」改成「投影可還原成原 references＋全文只出現一次」，保留 `submitted_context == submitted` 等儲存斷言。新增 `test_model_input_shows_each_frozen_document_version_once`：未保存 editor（revision 1）、同版本兩個 range、已保存 revision 0 兩個 range、同 path／同 fingerprint／同 revision 但內容不同的第三版；三種全文各只出現一次、指標值精確、range 欄位保留；首次模型失敗後 retry 的實際模型輸入與已存 `semantic_input` 逐字相同；未寫檔。P1 跨層測試加斷言：背景 editor 與段落 reference 共用一份全文。未修改的 service 下這三個測試失敗（格式不含指標且全文重複）。
- **檢查**（app/，sandbox 外以容許 `/tmp` fixture）：`tests/test_desktop_document_service.py tests/test_inline_skills.py tests/test_desktop_service.py` 119 passed；所有引用 submittedContext／references／fixture_session 的 13 個 test modules 487 passed；`git diff --check` 通過。
- **限制**：只縮小新回合的模型輸入；舊回合 retry 仍用其已存的未去重 semantic_input（計劃要求不遷移）。未量 token 或延遲改善。

### X4 — P4：最小可持久化執行計時

- **檔案（4 個 production）**：`agent/observability.py` 新增 `TurnTimingTrace`（LangChain `BaseCallbackHandler`，`run_inline=True`，執行緒鎖）與 `query_hash()`；`agent/turns/execution.py` 的 `execute_graph()` 多一個 `callbacks` 參數，有值時以 `config={"callbacks": …}` 傳給 `graph.astream`；`agent/session.py` 在 `turn_outcome()` 每次執行（非 duplicate）建立一個 trace、`_execute_graph()` 把它傳入，`finally` 以 completed／failed／cancelled 收尾；`skills/citation/tool.py` 的 search 回傳計數 artifact `{"kind": "citation_search_summary", candidate_count, abstract_count, provider_count, failed_provider_count}`。第 4 檔的必要性：search 原本只有給模型的格式化文字、artifact 為 None，callback 無可靠結構可讀；artifact 不送模型，save 統計只認 `citation_save_batch` kind，不受影響。
- **事件語義**（logger `agent.observability`，INFO，單行 `turn_trace key=value …`）：`turn_start`；`model_start/model_end`（`model_seq` 在同一 attempt 內遞增，含 repair 再呼叫；SDK 內部 HTTP 重試在同一區間內，不推測次數；`tool_calls`、可得時 token）；`tool_start/tool_end`（`tool`、`tool_call_id`、產生它的 `model_seq`、Citation 的 allowlist `action`、任何字串 `query` 的 `query_hash`＝sha256 前 16 hex、`status` ok／error／unfinished、`error_type`、Citation 計數；save 只記 items／saved／reused 數）；`turn_end`（state、duration、model_calls、tool_calls、unfinished）。`at_ms` 為相對 attempt 起點的 monotonic offset，`duration_ms` 為 monotonic 長度；牆鐘時間由既有 log formatter 的 asctime 提供。重試同一 logical turn 有新 `attempt`。未獲授權的工具不執行，因此沒有 tool_start（不會被記成成功）。被取消的工具 LangChain 不回呼，收尾時記 `status=unfinished`。callback 例外由 LangChain callback manager 吞下，不會讓回合失敗。不記內容、原始 query、DOI、工具參數或結果文字。
- **持久化**：沿用 `install_diagnostic_log()` 的 INFO rotating file（GUI：`desktop-backend.log`；CLI：`cli.log`；位置 `$AGENT_LOG_DIR` 或 `$XDG_STATE_HOME/research-agent/logs/`，預設 `~/.local/state/research-agent/logs/`；5 MiB×3 輪替）。檔案無法建立時沿用既有 fallback（stderr 只有 WARNING，並有 "diagnostic log file unavailable" 警告，即追蹤不可用）。
- **解析程序**（直接讀）：`grep -h 'turn_trace' ~/.local/state/research-agent/logs/desktop-backend.log* | grep 'turn_id=<對話 JSON 的 turnId>'`。同 `tool_call_id` 的 start/end 配對；並行區間用 `at_ms - duration_ms` 到 `at_ms`；turn 總時間看 `turn_end duration_ms`，不要把工具 duration 相加。
- **測試**（`tests/test_observability.py`，真 graph＋真 `BaseChatModel` 假模型）：快／慢兩工具同批並行（兩者都在任一結束前開始、快者先結束、duration 各自正確、model_seq=1）；工具例外 `status=error error_type=ConnectionResetError`；未授權工具無事件；模型例外 `model_end status=error` 與 `turn_end state=failed`；同 turn 重試產生新 attempt；取消時工具 `unfinished`、`state=cancelled`；`install_diagnostic_log` 後關閉 handler 再讀檔仍有完整事件；Citation fixture 中同 query 的 hash 相同、不同 query 不同、候選數／摘要數與 fixture 相符（2/0、年分過濾後 1/0）、model 呼叫 3 次而工具 3 次；log 文字不含 query、DOI、標題。P1 跨層案例另斷言同 turnId 的 trace 有 Citation search `candidate_count=2`、`state=completed`，且不含留言。
- **檢查**：`tests/test_observability.py` 17 passed；`tests/test_inline_skills.py` 18 passed；完整 `python -m pytest -q -p no:cacheprovider`（sandbox 外）1473 passed、44 秒。
- **離線樣本**（fixture，非真實延遲）：

```text
turn_trace event=model_end … model_seq=1 status=ok at_ms=3 duration_ms=0 tool_calls=2 input_tokens=11 output_tokens=3
turn_trace event=tool_end … tool=rag_search tool_call_id=call-fast model_seq=1 query_hash=6d96f400688b4623 status=ok at_ms=15 duration_ms=10
turn_trace event=tool_end … tool=rag_explore tool_call_id=call-slow model_seq=1 query_hash=38c0b4f8aa93bbbb status=ok at_ms=256 duration_ms=251
turn_trace event=tool_end … tool=citation_workflow tool_call_id=search-2 model_seq=2 action=search query_hash=124b71b4601630d3 status=ok at_ms=7 duration_ms=1 candidate_count=2 abstract_count=0 provider_count=2 failed_provider_count=0
turn_trace event=tool_end … tool=citation_workflow tool_call_id=search-3 model_seq=2 action=search query_hash=2415a887f1296d34 status=ok at_ms=1006 duration_ms=999 candidate_count=1 …
turn_trace event=turn_end … state=completed duration_ms=1020 model_calls=3 tool_calls=3 unfinished=0
```

  最後兩筆：同 query 的 search-2 走成功快取約 1 ms；不同 query 的 search-3 即使 fetcher 為離線也約 999 ms，指向 provider 端的固定等待（P8 跟進）。
- **限制**：目前尚無修正後的自然使用 trace；P6–P10 的真實耗時判斷需要它或有界免費量測。只觀測 LangChain 可回呼的模型（測試用 fake 若非 BaseChatModel 則無 model 事件，工具事件仍有）。

### X5 — P5：有限 timeout 與真實 SDK 重試政策

- **探針**：計劃提到的 503／timeout 舊探針在 repo 與 /tmp 均找不到，改在 `tests/test_openrouter_model.py` 重建：真 factory → 真 `ChatOpenRouter` → 真 openrouter SDK → `httpx.MockTransport`；以 monkeypatch 只替換 SDK `openrouter.utils.retries` 模組的 `time`／`asyncio.sleep`／`random`（假時鐘、無 jitter、不真的等待）。無網路、無付費呼叫。
- **修改前基準**（同一假時鐘，持續 503）：原 wrapper `max_retries=0` → 71 次 HTTP、虛擬 3609 s（落回 SDK 60 分預設窗）；`max_retries=10`（原預設）→ 36 次、1509 s；HTTP timeout 四個 phase 都是 None。
- **決策 O5（執行者選定，非使用者指定、非性能保證）**：
  - 每次 HTTP attempt `llm_request_timeout_ms = 600_000`（SDK 以 ms 傳入、httpx 換成 600 s 的 connect/read/write/pool phase timeout）。理由：非串流回應可能數分鐘才完成（65,536 token 上限、fusion judge），5 分以內的值可能切斷慢但有效的回答；10 分仍為有限值，GUI Stop 仍是使用者的總控制。它是 phase timeout，不是整次呼叫的硬 deadline。
  - SDK 重試只針對既有 5XX 與連線／timeout 錯誤（SDK 原本即不重試 429），重試窗 = `llm_max_retries × 5_000 ms`；預設 `llm_max_retries` 由 10 改為 4 → 20 s 窗；backoff 1 s 起、指數 2、單次 sleep 上限 8 s。`llm_max_retries = 0` 明確傳 `retry_config=None`，真正只打一次（修正 0 落回 60 分窗的陷阱）。
  - Server `Retry-After` 經 httpx response event hook 截到 ≤ 8 s（HTTP-date 或無法解析也截到 8 s），因 SDK 原本會無上限地 sleep 該值。
  - 可證明上界：持續 5XX ≈ 窗＋8 s（預設 23 s 內停止）；timeout 時第一個 600 s attempt 已超過窗，不再重試；短 timeout 時最多窗＋8 s＋一個 timeout。
  - 使用者可見取捨：暫時 5XX 在 20 s 內自動吸收；更長的故障會讓回合在約半分鐘內失敗（GUI 可重試），不再靜默等 25–60 分。回復方式：調整 `AgentConfig.llm_max_retries`／`llm_request_timeout_ms`，或還原本 commit。
- **修改**：`agent/llm/openrouter.py` 新增 `bounded_sdk_client()`（以 wrapper 的公開欄位複製 HTTP-Referer／X-Title／categories attribution headers、`follow_redirects=True`、base URL、API key），factory 建好 `ChatOpenRouter`（也傳 `timeout`、`max_retries` 供內省）後以公開 `client` 欄位換成此 client；transport 參數只供離線測試。`agent/config.py`：`llm_max_retries` 註解與預設（10→4）、新增 `llm_request_timeout_ms`。沒有修改 site-packages、沒有升級或替換套件。所有 agent 模型（graph 的 async `get_chat_model`、thinking 角色與 `agent/llm/text.py` 同步 helper 經 `get_openrouter_chat_model`）都經此 factory；`rag` 的獨立 OpenRouter factory 不在本計劃範圍。`graph.py` 的 empty-response 重試是另一層，未改。
- **離線驗收**（`tests/test_openrouter_model.py`）：持續 503（async 與 sync）→ sleeps `[1,2,4,8,8]`、6 次、虛擬 23 s、最終 `OpenRouterError` 503；request timeout → 實際 request 帶 ms→s 換算後的 phase timeout，600 s 時只 1 次，1.5 s 時 5 次、虛擬 22.5 s；Retry-After 3600 → sleep `[8.0]` 後成功、content 與 usage 保留、attribution header 與 host 正確；一次 503 後成功 → sleep `[1.0]`；`llm_max_retries=0` 與不可重試 400 → 恰 1 次、無 sleep；取消 → `CancelledError`、1 次、無重試。既有 factory kwargs 測試改為 stub `bounded_sdk_client` 並檢查 `timeout`。
- **檢查**：`tests/test_openrouter_model.py tests/test_thinking_models.py tests/test_thinking_session.py` 53 passed；完整 pytest（sandbox 外）1481 passed、40 秒；`git diff --check` 通過。
- **限制**：真實 OpenRouter 對非串流長回應是否送 keep-alive 位元組未驗（需付費呼叫）；若不送，600 s phase timeout 就是單次生成的實際上限。不據此宣稱解釋歷史 341 秒。

### X6 — P9：先資格過濾，再截斷候選

- **排序依據**：P9 是已知正確性缺口且可完全離線，P6–P8 需要實際量測，因此在 P5 後先做。
- **反例**（`tests/test_citation_workflow_tool.py`，真 `CitationService`＋真 tool，fake provider 只替換 `search_text`）：Crossref 10 筆、DataCite 5 筆，前段多為 2010／2005／未知年份，後段有 2021–2022 合格候選，且一筆 DOI 兩來源重複（勝者無摘要、另一來源有摘要）。修正前 `year_from=2021, year_to=2022` 只回 2 筆（前 10 名中的合格者），實際已取得 5 筆合格。
- **修改**：只在 `skills/citation/service.py` 的 `search()` 排序後、`[:rows]` 前，若 date filter 有年份上下界就以既有 `PublishedDateFilter.admits_year()` 過濾。DOI 去重與跨來源摘要合併在過濾前完成，rank 比較、provider 呼叫次數、每來源上限（`min(rows, 20)`）與傳給 provider 的 filter 均不變；tool 的本地年分過濾保留為相同語義的防線。無年份界線時行為完全不變。
- **驗收**：tool 格式化輸出回 5 筆合格（依原 rank 順序）、`Found 5`；共享 DOI 的 DataCite 真摘要與 `abstract source: datacite` 保留；各 provider 仍只被呼叫一次、rows=10、filter 年份相同。service 直接以 rows=3 回 3 筆合格；單邊界 `year_from=2022` 包含 2022、2023（inclusive）；未知年份在有界線時不通過；無 filter 時前 10 名與修改前相同且保留未知年份。
- **檢查**：`tests/test_citation*.py` 376 passed；`tests/test_citation_workflow_tool.py tests/test_citation_hub.py tests/test_citation_e2e.py tests/test_observability.py tests/test_inline_skills.py` 95 passed；`git diff --check` 通過。
- **限制**：排序沒有調整，摘要存在不升權（計劃明訂另議）；不據此報告研究時間縮短。

### X7 — P6：MCP session 重用的量測與判定（維持現狀）

- **量測方法**：以 app 實際 `_web_search_spec()`＋`_spec_to_connection()`（`/bin/sh -c "node …/dist/index.js 2>>log | grep '^{'"`）連到已安裝 server，呼叫 `get-web-search-summaries` 並給空 query，使 server 在 zod 驗證即回錯、不觸網，因此只量程序與 MCP 協定成本。`XDG_CACHE_HOME` 指向 `$TMPDIR`，不寫使用者 log。兩輪各 6 次。
- **結果**：現行 `get_tools()`（每次呼叫新建 stdio session）每次 0.374–0.429 s（中位數 0.387／0.395 s），工具清單載入 0.39–0.47 s；同一 `client.session()` 持續 session：開啟＋列工具 0.36–0.38 s 一次，之後每次 0.001–0.005 s，關閉 0.008 s。即每次 web 工具呼叫約 0.39 s 是可省的程序成本。
- **自然使用對照**：10/19 回合（`cbdca28b`，341 s）有 14 次 `get-web-search-summaries`，10/15 回合（`29f3b12a`，304 s）有 13 次 web 呼叫；程序成本合計約 5.5／5.1 s，各約 1.6–1.7%。同回合的 Bing 頁面時間（下見 X8）每次 1.5–5 s，P7 量到 fallback 每次另花 4.5–6 s，程序成本不是主要項。
- **重用的具體風險**：外部 server 的 `RateLimiter` 是程序內「每分鐘 10 次、超過直接丟錯」。現在每次呼叫是新程序，limiter 每次重置所以從未觸發；離線 stub 驗證同一 `SearchEngine` 實例第 11 次即 `Failed to perform search: Rate limit exceeded`。改為持續 session 會把 10/19 這種 14 次搜尋的回合推向 limiter 失敗，另外 session 擁有者須貫穿 ChatSession／desktop shutdown／取消／崩潰（至少 mcp.py、startup.py、session.py、desktop service 四檔）。
- **判定**：省下約 0.39 s／次，不值得改變 server 實際行為（引入 rate-limit 失敗）並增加跨四檔的生命週期。依計劃完成定義記為「有證據不需修改」；沒有實作或宣稱加速。MCP 程序重用與 browser 重用無關（P7 另判）。
- **附帶發現（I1）**：在 sandbox 外跑完整 pytest 時，部分測試會在使用者真實的 `~/.cache/agent-mcp/*.stderr.log` 追加 run header（今日 12:44／12:51 UTC 共 4 行，並建立 alpha／beta／dropin／legacy 等測試 server 的 log）。這是既有測試隔離缺口，非本計劃引入；未刪除任何檔案。之後讀 web_search.stderr.log 時，這些 header 不是使用者回合。建議另案讓 conftest 隔離 `XDG_CACHE_HOME`。
