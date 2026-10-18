# 執行狀態與證據

已依使用者啟動指令開始實作；指令明確核准 T3 最小協定／title 保存調整、每步 local commit，維持 GUI 分支與原工作樹。進度只在本檔維護。

| 階段 | 狀態 | 已有證據 | 阻礙／條件 | 下一動作 |
|---|---|---|---|---|
| P1 | In progress | P1-S1 自動啟動測試／build／實際桌面 ready 通過 | P1-S2 原生整合待實機 | 原生 picker 探測與接入 |
| P2 | Not started | 現有 selection/references／保存掛點已讀 | P1；T3 event | 依 P2-S1 實作草稿與合成 |
| P3 | Not started | 原 reference snapshot 路徑已確認 | P2 | 驗證兩次 edit 的最小案例 |
| P4 | In progress | P4-S1a–c 模型／本地工作／MCP／Stop 協定、保存與文件整合通過 | Send／Stop UI 與實機操作尚未完成 | P4-S2 |
| P5 | Not started | 保存與索引分工已讀 | P4、T3 title/schema | P5-S1 canonical title |
| P6 | Not started | 根 README 缺失已確認 | P1–P5、實機證據 | 完成後先整體確認再寫 README |

## 計劃撰寫紀錄

- A1／2026-10-18：只讀核對 AGENTS、環境、Git 與規格。HEAD 與規格相同；現有 ` D problem.html`、`?? app/store/` 保留，原 staged 為空。
- A2／2026-10-18：靜態查閱桌面 UI、stdio bridge、protocol、service/document/conversation 與現有測試；獨立代理只讀核對 backend。未執行規格內的實作指示。
- A3／2026-10-18：查閱 Microsoft WSL／Windows Forms 官方文件，僅形成 T1 擬採方案，沒有把文件支持當本機成功。
- A4／2026-10-18：以 Conda app Python 執行技能的 `validate_plan.py /home/minervamuses/research-agent-workspace/harness/plans/2026-10-18-desktop-interaction --json`。首輪指出 plan_id 不可用數字開頭，改成 `desktop-interaction-20261018` 後通過：11 個 Markdown/JSON 檔，0 errors、0 warnings。這不是應用測試。
- A5／2026-10-18：獨立 fresh-context 代理讀完整規格、全部計劃及必要保存程式。指出 P1-S2 自行排除其他 WSL 發行版；已刪除這項未核准限制，改成實際不能映射時回報影響、不自行擴建。審閱沒有其他重大接手或過量驗證問題；作者再核對修正文義與 D1、路線、驗收的一致性。
- A6／2026-10-18：人工逐項對照規格 §7 的 13 項結果至 G1–G10／P1–P6；走讀首次啟動、P3 中途停止、未 commit 接手與 D1 受阻轉做 P4/P5。第一步及恢復動作可由計劃本身取得。
- A7／2026-10-18：12 個交付檔案以 UTF-8 解碼、LF 與逐檔 `git diff --no-index --check /dev/null <實際檔案>` 核對，沒有 whitespace 診斷。此命令對新增檔案的 exit 1 表示有差異，非 whitespace 失敗；最初包裝檢查誤將該 exit code 視作失敗後已修正並重驗。規格副本與原檔文字一致（僅 LF 正規化）。
- 所有檢查都是計劃撰寫檢查；實作階段仍全部 Not started。未做產品實機驗證或提交 commit。

## 已採用的修訂

- R1／2026-10-18：使用者明確裁決標註後再手動改原文、agent 執行中同時手動改原文均為錯誤使用，本次不處理，只確保正常流程可用。D1 改為已確認範圍排除，同步 GOALS、PLANS、PROMPTS、P2/P3/P4/P6 及本檔現行條件；不新增防誤用設計或專門測試。agent 自己同回合多段修改的正常要求、每步 commit、不得自行切 branch／建工作樹及 T3 授權邊界維持不變。
- 原始規格副本及 A1–A7 的初版歷史保留；其中 D1 當時待裁決的記錄已由 R1 取代。靜態階段依賴與目標覆蓋未變，plan-index.json 不需修改。

- R2／2026-10-18：修訂後執行計劃結構 lint，11 個 Markdown/JSON 檔、0 errors、0 warnings；8 個修改檔案的 UTF-8／LF 與 Git whitespace 檢查通過，原規格副本文字不變。獨立只讀核對確認影響範圍為上述 8 份文件，靜態 index 不需變更；已核對 D1 不再出現在現行阻礙或驗收門檻。僅做計劃檢查，未跑應用測試或開始實作。

## 後續每步記錄格式

`步驟 ID／日期 — 真正改動；實際命令或操作及結果；證據或檔案；限制／失敗；commit 主旨（含步驟 ID）；下一動作。`

不要保存秘密、provider raw payload 或整份研究內容。不要在計劃與 index 另建一套狀態。未完成檢查寫未完成，未做 commit 寫未提交。

## 實作紀錄

- P1-S1／2026-10-18 — 從 GUI、HEAD `207e4f3` 開始；原 staged 空，保留 ` D problem.html`、`?? app/store/` 及未追蹤計劃。WSL Ubuntu-24.04，Linux Git；Conda app Python 3.13.14／Poetry 2.4.1／Node 24.18.0／npm 11.16.0／Rust 1.97.1。未改環境／依賴。
  - `backend.ts` 一次初始化採用已有 starting/ready backend，只有 stopped 且無 child 才啟動；失敗不自動循環，可透過原 start/restart 手動重試。`App.tsx` 先 listen 再 initialize，顯示 preparing，保留手動工作位置選擇與 MCP Restart。
  - Linux Conda app：`cd app/desktop && node --test --experimental-strip-types tests/backend.test.ts`，13 passed；`npm run build` 通過；保留既有大型 bundle 提示，未擴充處理。`git diff --check -- app/desktop/src/App.tsx app/desktop/src/backend.ts app/desktop/tests/backend.test.ts` 通過。
  - 根目錄 `python main.py` 實際啟動，增量 release build 1m06s 成功。Windows Computer Use 觀察 Research Agent (Ubuntu-24.04)：Backend ready、Generation 1／0 pending、專案 chooser 打開，沒有選歷史或研究回合。Linux ps 核對一個 desktop child、一個 `python -m agent.desktop.server`。快速 preparing 過場未截到；其渲染及啟動回呼由程式／測試核對。啟動出現 EGL warning，但畫面正常可見。
  - Scoped commit：`feat(desktop): start the backend automatically [P1-S1]`。下一步 P1-S2。
- P4-S1a／2026-10-18 — P1-S1 commit `a98d47c`。在 P1 原生視窗探測等待期間，依獨立 P4 路線有限追查可達工作，將 S1 細分為模型 await、本地工作收束、Stop 整合三個可驗證子步驟（詳 phase-04-stop.md）。沒有新增 dependency／module／concurrency model。
  - `graph.py` 以既有 RunnableLambda 保留 sync invoke 及加入 native async ainvoke；同一本地 generator 共用三個模型請求的 recovery 決策。`llm/text.py`、thinking review/parsers/orchestrator 的 rewrite／aggregate／review／repair 都走 native async，保留同步 helper。相關假模型補上 async stub，production 無同步 fallback。
  - Linux Conda app／app：`poetry run pytest tests/test_graph_skill_loader.py tests/test_thinking.py tests/test_thinking_session.py -q`：89 passed／0.75s；`poetry run pytest tests/test_citation_e2e.py tests/test_conversation_archive_access.py tests/test_desktop_document_service.py tests/test_policy_tool_node.py tests/test_inline_skills.py tests/test_skill_adherence.py -q`：73 passed／3.06s。7 個必要取消案例涵蓋 main 初次／重試／repair 及 extended 四個模型階段，核對 cleanup、未執行後續、interrupted/cancelled 保存與 main 下一次呼叫。初次新增 repair 測試的工具名錯誤已修正，未改 production 來迎合測試。Scoped whitespace 通過，根代理已審閱 production diff。
  - 未使用 live provider；Stop protocol/UI、bash、RAG、MCP／文件工作收束尚未完成。Scoped commit：`fix(agent): await cancellable model requests [P4-S1a]`；下一步 P4-S1b。
- P1-S2 探測／2026-10-18 — 可丟棄 PowerShell STA／Windows Forms probe 已從 WSL 顯示資料夾視窗。Computer Use 無法列出或取得該 PowerShell-hosted 視窗，使用者明確回覆「看得到」，並手動完成測試選取；stdout 成功返回含中文／空白的 WSL UNC 路徑。這不是未顯示或 interop 失敗；先前等待是自動操作工具可見性限制。`wslpath -u` 本機不能直接處理該 UNC，正式接入將採計劃允許的明確 UNC→目前 distro Linux 路徑映射，再 realpath 核對。正式 picker／同檔保存仍待驗證。
- P4-S1b／2026-10-18 — S1a commit `0cd9489`。既有 `agent/ingest.py` 增加當前回合的 context-local 停止／worker 等待，RAG 接收通用 callbacks，沿原 event loop 等 native async provider；cached store 不保留 turn scope。既有 ingest／sync／chunk／folder 及 store 副作用邊界檢查停止，保留原 folder executor 並等待已開始工作。bash 沿現有 runner 持有 process group，停止時 TERM／必要 KILL，等待退出並回收直接 shell；read_file/RAG async wrapper 等實際 worker 返回。同步 CLI、timeout/retry、依賴與儲存格式不變，未新增 module／concurrency model。
  - Linux Conda app／app：`poetry run pytest tests/test_ingest.py tests/test_bash_tool.py tests/test_read_file_tool.py tests/rag/test_ingest_guards.py tests/rag/test_store_batching.py tests/rag/test_component_flow.py tests/rag/test_tools_contract.py tests/test_policy_tool_node.py -q`：60 passed／5.91s；包含最後 store 邊界修改。`poetry run pytest tests/test_text_normalization.py -q`：18 passed／0.19s。Scoped whitespace 通過，根代理審閱 production diff。曾有新增測試字串換行錯誤及一次指定不存在測試檔，已修正後跑上述正確命令。
  - 最小本地案例確認停止後不啟動下一個 ingest 檔案、provider cleanup 已完成、既有四個 folder workers 的 context 傳遞及已結束 shell 留下的同群組 child 終止。無外網 MCP ephemeral probe 經 actual loader／converted tool／每次 call 的 stdio context：direct 與預設 shell/server/grep 路徑各約 4.004s 收束，忽略 SIGTERM 的 stub 最終退出，process group 空；不需修改 MCP production。未使用 live provider、embedding 或 GPU。
  - `LocalWorkScope.bind/request_stop/finish_stop` 尚待 S1c 綁入桌面；`await_sync_work` 會無條件等短同步保存後重新拋取消，接受邊界結果由 session 層接續處理。已完成效果不回滾；不宣稱撤銷遠端請求或控制自行 detached 的後代。Scoped commit：`fix(agent): drain controlled local work on cancellation [P4-S1b]`；下一步 S1c。
- P4-S1c／2026-10-18 — S1b commit `9eba231`。`session.stop` 核對 session／turn／parent request，原回合只有一個 terminal；停止主回合、核准及可控制工作，等待 document.apply 與保存真正完成。停止後的候選不因開始下一回合又可遲到 apply，已保存文件保留 Undo。cleanup 失敗或 canonical 仍 pending 時不放行新回合。pending 保存取消後留下使用者訊息及 interrupted，completed 保存已成功的競態維持 completed。依 T3 新增最小 method／TURN_CANCELLED 與三側 contract，未新增儲存格式。沿既有 phase02 無 provider fixture 加 `[[fixture:wait-stop]]`，供後續 UI 驗證，沒有另建框架。
  - Linux Conda app／app：`poetry run pytest tests/test_desktop_service.py tests/test_desktop_document_service.py tests/test_desktop_server.py -q`：109 passed／4.78s；`poetry run pytest tests/test_session_persistence.py tests/test_session_lifecycle.py tests/test_skill_adherence.py -q`：44 passed；`poetry run pytest tests/test_thinking_session.py tests/test_graph_skill_loader.py tests/test_inline_skills.py tests/test_conversation_archive_access.py -q`：62 passed。最後保留原 turn body 縮排、縮小 diff 後，`poetry run pytest tests/test_desktop_document_service.py -q`：11 passed／0.80s；根代理 `poetry run pytest tests/test_desktop_service.py tests/test_desktop_fixture.py -k stop -q`：1 passed／0.28s，確認 fixture 中斷保存與下一回合。保留既有 LangGraph deprecation warning。
  - 協定：`poetry run pytest tests/test_desktop_protocol_contract.py -q`：161 passed／0.40s；desktop `node --test --experimental-strip-types tests/protocol.test.ts`：155 passed；src-tauri `cargo test --locked protocol::tests -- --nocapture`：12 passed；`npm run build` 通過（既有 large chunk warning）。stop result 只接受真實 terminal 或未接受的 null，核對關聯 ID；Stop 失敗不終結原 request。Scoped whitespace 及根代理 production review 通過。
  - 首次整合檢查的 EOF 舊測試預期「沒有 terminal」，已依新的 exactly-one cancellation terminal 更新後通過。沒有 live provider、GPU 或完整 suite 重跑。P1-S2 正式選取視窗仍等待使用者選取，與本階段無依賴；未降低其實機驗收。Scoped commit：`feat(desktop): stop and settle the active turn [P4-S1c]`；下一步 P4-S2。
