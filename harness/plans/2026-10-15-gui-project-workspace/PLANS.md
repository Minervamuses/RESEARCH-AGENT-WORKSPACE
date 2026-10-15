# GUI 專案工作區：完整實作計畫

計畫位置：harness/plans/2026-10-15-gui-project-workspace/
計畫就緒狀態：可供審閱並明確啟動。P1–P4 的路線及驗收已定義；舊資料歸屬只在需要承接舊資料時構成條件式決策，不能猜測或自動遷移。功能尚未實作。

## 閱讀與責任

- [GOALS.md](GOALS.md)：使用者目標、邊界與需求來源。
- 本文件：已觀察基線、執行順序、權限／成本及完成契約。
- [context/contracts.md](context/contracts.md)：跨階段共用的具體設計提案、資料與狀態契約、決策界線。
- [build/phase-01-project.md](build/phase-01-project.md) 至 [build/phase-04-acceptance.md](build/phase-04-acceptance.md)：工作與可觀察驗收。
- [build-log.md](build-log.md)：唯一階段狀態、實際證據與下一步。
- [PROMPTS.md](PROMPTS.md)：開始、恢復、修訂及審核入口。
- [plan-index.json](plan-index.json)：靜態依賴及目標索引；不儲存狀態、核准或測試證據。
- 本目錄 .gitignore：只解除 repository 的 build/ 規則對本計畫階段文件的忽略，方便日後納入版本控制；沒有執行 git add 或 commit。

## 已核實的基線

檢查於 2026-10-15，GUI HEAD 為 `1cf54d7ed8a6769e8c9e155fa8bcb6243621c156`；origin 是 `git@github.com:Minervamuses/RESEARCH-AGENT-WORKSPACE.git`。規劃開始前工作樹乾淨。本次未 fetch，不能聲稱遠端最新提交已同步。

| 主題 | 觀察與程式定位 | 對本次計畫的意義 |
|---|---|---|
| 執行環境 | repository root `/home/minervamuses/research-agent-workspace`；Python project 在 `app/`。Ubuntu-24.04 WSL；Git `/usr/bin/git`；Conda app 下 Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0、cargo 1.97.1 | Windows shell 只透過 WSL 呼叫；不能用 Windows git/python/npm 或系統 Python。Linux 無 rg，使用 git grep/grep |
| UI 技術 | `app/desktop/package.json`：React 19、Monaco 0.57、Tauri 2；沒有 folder-dialog plugin | 保留既有編輯器與元件；採 App 內專案開啟對話框，無需加依賴 |
| 開機載入 | `App.tsx:1042` 對 catalog 所有 project 載入 sessions；`:1247` 自動選既有或第一個 project。完整路徑均為 `app/desktop/src/App.tsx` | 必須加前後端專案 gate，不能只遮住 sidebar |
| 文件與歷史分離 | `app/agent/desktop/service.py:260` 使用 config.persist_dir 初始化 repository/catalog 並預選 local；`:1824` workspace.select 只改 DocumentWorkspace | P1 讓既有 service 在一次開啟流程後綁定根、rules、repository、catalog |
| 歷史 | `app/agent/conversations/models.py:11` schemaVersion=1；`repository.py:39` 嚴格欄位；`:340` repository root 是 persist_dir/conversations；`catalog.py:143` 是現有 atomic catalog | 對話仍用 canonical JSON；不另建聊天儲存。引用需要明確 schema 相容路徑 |
| 重試 | `app/agent/conversations/repository.py:313` 同輪比較 semanticInput/thinkingMode；`app/agent/session.py:282` pending 落盤在執行之前；`service.py:1136` transcript 只還原顯示文字 | 將引用及可重試上下文加入同一 turn；重試不能用新游標或新背景重建舊 semanticInput |
| 文件 | `app/desktop/src/DocumentEditor.tsx:4,116,144` 已有 snapshot、UTF-16 選區、Ctrl/Cmd+S；`app/agent/desktop/documents.py:156,189,213` 已有 snapshot 驗證、行範圍與候選修改 | 用原版本／衝突／apply/undo 路徑；卡片不能成為新的寫檔通道 |
| 規則注入 | `app/agent/session.py:1375` create 接受 system_prompt；`service.py:1184` 已注入 repository/project_id。未找到 RESEARCH.md loader | 在既有 prompt/session 建立流程加入 scoped project rules，保留原 system prompt 及 Permission 執行檢查 |
| 歷史工具依賴 | `app/agent/tools/read_file.py:159` 分段讀 canonical history 的 allowlist 綁 config.persist_dir/conversations；`session.py:547` archive hint 已用 repository root | 換 history root 時同步調整既有 read_file 工具根的傳遞；不能為此改整個 persist_dir 連帶搬 RAG |
| 前端防過期 | `App.tsx:1192` conversation 有 generation/operation token；`conversations.ts:361` turn 有 request/project/session/turn identity；文件結果 `App.tsx:757` 主要比較 path | 擴充現有 identity guards 到專案、文件、approval、錯誤及 finally |
| 版面 | `app/desktop/src/styles.css:109` sidebar minmax(14.5rem,17rem)；`:561,1197` conversation grid 四列。App.tsx:1726 文件 toolbar、:1779 頂部 controls、:371 composer footer | P3 兩端乘 0.7；刪實際 toolbar 與空列、重用 save/undo handler |
| 協議與測試 | `app/desktop/protocol/v1/contract.json`、fixtures.json；Python/TS/Rust 各有驗證。Node test runner、pytest、cargo tests 已存在 | 任何欄位變更同批更新契約、三層驗證、fixture 與消費端，不另建測試框架 |

行號只對上述 HEAD 有效，執行時以符號重新定位。未讀取真實聊天內容、秘密、個人 RESEARCH.md；未啟動 GUI、provider、MCP、模型或測試。因此目前沒有視覺量測、測試耗時或實際使用驗收結果。

## 依賴路線

| 階段 | 結束時應可觀察的結果 | 前置 | 覆蓋 | 詳細工作 |
|---|---|---|---|---|
| P1 | 冷啟動選專案後，只讀該專案歷史與規則；安全切換根、history、session，錯誤不 fallback | 無；先完成執行 preflight | G5–G8、G12 | [專案入口](build/phase-01-project.md) |
| P2 | 文件／聊天引用從加入、顯示、送出、失敗重試到歷史還原完整串通；寫回仍版本檢查 | P1 | G1–G4、G8、G12 | [引用生命週期](build/phase-02-references.md) |
| P3 | 文件和聊天上方冗餘區塊消失；功能保留、側欄 70%、底部控制同列且正文空間增加 | P2 | G9–G12 | [介面收斂](build/phase-03-layout.md) |
| P4 | 同一 Linux GUI 代表案例通過，舊資料／協議／權限相關回歸有實際證據 | P1、P2、P3 | G1–G12 | [整體驗收](build/phase-04-acceptance.md) |

先交付專案開啟這個可用切片，再接引用；不先鋪通用框架。執行者可平行做互不相依的唯讀檢查或測試規劃，但同一檔案的修改與跨層 schema 更新需協調；不因此改變 App 的併發模型。

## 實作與授權契約

本計畫描述工作，不自行授權實作。這次 planning-only 到計畫交付即止。使用者明確要求開始此計畫後，才能在該授權範圍持續執行 P1–P4；階段邊界本身不需重新詢問。更高層權限限制及後續使用者修訂始終有效。

開始後先讀適用 AGENTS.md、本計畫 goals/route/log 與 relevant source，重查 branch、dirty state、runtime。若不在 GUI 或工具不屬於 Linux/app 環境，不自動 checkout、不改 worktree、不混用 Windows runtime；停下受影響工作說明所需切換。保留無關 staged/unstaged 內容。

必要預計範圍：

- 前端現有 `app/desktop/src/{App.tsx,DocumentEditor.tsx,conversations.ts,protocol.ts,trust.tsx,styles.css}`。
- desktop service/catalog/documents/protocol、`app/agent/session.py`、`app/agent/conversations/{models.py,repository.py}`。
- 僅為所選 archive root 傳遞而必要的既有 tools factory/read_file 接點；開始前追蹤實際呼叫鏈，不改整體工具管理。
- shared contract/fixtures、Rust protocol、既有 fixture_session 及相關現有 tests；本計畫 log。
- 優先在現有模組加入局部函式／資料型別；不新建 project subsystem、adapter、registry、第二套 conversation API 或持久化模組。

這是使用者明確提出的跨層功能計畫，並非三檔內的窄 bug fix；多檔變更僅限上述因果鏈。使用者已要求必要資料／通訊擴充，但 D1/D4/D5 的具體格式仍是計畫提案。啟動文字若明確接受本計畫所列格式，該接受即為所列 schema 變更授權；若只授權部分或保留格式決定，先完成不依賴部分，再請求相應明確批准。不得用本文件假造批准。

下列仍需額外明確授權：新增 production dependency、lock/environment/package-manager 變更、資料庫／服務／新併發機制、未列出的 public API/格式變更、真實舊資料搬移或 projectId 改寫、廣泛重構、提交／push／merge／rebase／切分支或 worktree 操作。沒有 Git commit 授權時，以檔案 diff 與 build-log checkpoint 交接，不代替使用者提交。

成本限制：不呼叫付費 provider、不跑模型／GPU、不全資料回放；使用現有 fake/recorded fixture。任何可能超過約十分鐘的操作先估算並取得批准，尤其冷 Rust/Tauri build；未知耗時不得宣稱廉價。既有 full pytest suite 僅在相關且可於成本上限內時於結尾跑一次；昂貴時先說明範圍及代價請求批准。每次只跑能區分新假設的 targeted check，無關失敗另報，不追修。

## Checkpoint、失敗與恢復

一個一致的修改片段完成後，保存實際 diff、最小相關檢查命令／結果與 A 編號至 build-log。只記錄事實，失敗與跳過必須可見；不以代理狀態、編譯成功或結構 lint 代替使用者行為驗收。

兩次聚焦修補仍失敗：停止該問題，寫下支持／反對假設、最可能尚未解決原因與最小下一步；一次昂貴嘗試失敗或無改善，不再自行重跑。可繼續不依賴該阻塞的授權工作，不擴大架構。

中斷恢復：先比對當前 HEAD/diff、build-log、磁碟的 RESEARCH.md/history 與已完成副作用。不要因 log 落後而重建指標、重寫版本或重播工具。若 branch/source 已不同，只重查受影響基線與驗收，再調整尚未完成階段；不得降低 GOALS 的要求。

RESEARCH.md 初始化／欄位設定要可重入且防止覆寫同時變更；資料遷移不是初始化。新程式讀 v1、寫 v2 的回復方式見 D5；不以將舊程式直接指向 v2 歷史當 rollback。資料是否需遷移無法確定時，保留原位置並只阻塞該資料的接入。

## 完成條件

所有 G 目標及 A01–A21 所需案例有實際通過證據；條件式案例已逐項標示觸發／不適用理由。未通過的必要 GUI 驗收不得稱功能完成。diff 只含本次必要變更；舊資料未被猜測歸屬、覆蓋或丟棄；無未授權依賴/Git/外部效果。

本次計畫撰寫完成的條件不同：需求追蹤、依賴、契約、驗收與 handoff 完整；結構 lint、語意審查與 diff 檢查結果寫入 build-log。完成規劃不代表任何 P 階段完成。
