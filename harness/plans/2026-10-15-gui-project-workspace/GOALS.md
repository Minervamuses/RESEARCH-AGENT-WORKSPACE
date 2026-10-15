# GUI 專案工作區調整：目標與設計邊界

日期：2026-10-15（Asia/Taipei）。對象：Minervamuses/RESEARCH-AGENT-WORKSPACE 的 GUI 分支。

本文件保存使用者需求；[PLANS.md](PLANS.md) 保存執行路線與授權界線，[build-log.md](build-log.md) 是唯一執行狀態來源。這次交付是完整實作計畫，尚未授權或進行功能實作。

## 需求來源

- U1：本次規格「引用必須固定加入當下的文字、來源、範圍與版本」及「歷史對話重新開啟後，也應能還原當時引用的內容」。
- U2：「RESEARCH.md 的作用接近 AGENTS.md／CLAUDE.md」；包含專案說明、Agent 規則與歷史位置指標，「不是聊天資料庫」，不另列 conversations。
- U3：「成功開啟專案後，文件根目錄、專案規則及 conversation 群組必須一致綁定到該專案」；不靜默丟失文件、草稿或引用，執行中禁止切換。
- U4：「完整移除」Research folder、Source file、Open source、Save、Undo Agent edit 及下方狀態區；保留儲存、Agent 復原與錯誤處理，不能改成自動儲存。
- U5：左欄為原寬度 70%；Thinking 與 Permission 移到 composer 底部同列左側，Send 右側，正文取得釋出高度。
- U6：「Ask／Bypass 只決定是否需要操作授權，不免除文件版本檢查與衝突處理」；執行中單輪設定不改動。
- U7：優先沿用既有編輯器、Agent、歷史、權限及版本檢查；必要格式與通訊擴充跨層一致、相容既有資料；不做 RAG 重寫、Skill 管理重做、協作或雲端同步。
- U8：本次明確要求 long-horizon-plan-author「完整模式撰寫計劃」；不是啟動實作。
- R1：使用者提供的 Personal Engineering Defaults 與根目錄 AGENTS.md：Linux、Conda app、Poetry、LF、最小驗證、保留既有資料與無關變更；依賴、格式、Git 與昂貴操作受核准界線約束。執行限制已完整落在 PLANS.md，不必取得原聊天才能遵循。

## 穩定目標與追蹤

| ID | 必須達成的可見結果 | 所屬階段／驗收 | 來源 |
|---|---|---|---|
| G1 | 文件反白附近可加入聊天；加入只附加上下文，顯示可展開全文、可移除、含來源／行範圍／摘要的卡片，焦點到輸入框，不送出、不寫檔 | P2／A08、A09 | U1 |
| G2 | 引用文字、來源、範圍及版本在加入時固定；送出、失敗、同輪重試、重開歷史仍能取回原引用 | P2／A09–A12 | U1 |
| G3 | 聊天反白可加入，保留 project/session/turn/訊息角色與選段；聊天來源不可變成文件可寫選區 | P2／A10、A13 | U1 |
| G4 | 無引用仍可用目前文件背景指定第 X–Y 行；明確引用與背景可區分；過期引用寫回仍經版本與衝突檢查 | P2／A13、A14 | U1、U6 |
| G5 | 每次冷啟動先選專案；成功前不載入或顯示其他專案對話；RESEARCH.md 存在即讀、不存在才初始化 | P1／A01、A02 | U2 |
| G6 | RESEARCH.md 可可靠解析歷史位置；既有說明保留，不存完整對話或清單；歷史可位於專案外，沿用既有 repository/catalog | P1／A02–A04 | U2、U7 |
| G7 | 指標錯誤、資料不可讀不退回全域／他專案或空歷史；保留舊資料，不推測舊對話歸屬 | P1／A03、A04、A07 | U2 |
| G8 | 專案根、規則及對話一致；切換不丟未儲存文件、草稿、引用；任務中禁止切換；延遲結果不得污染新專案 | P1＋P2／A05、A06、A12、A15 | U3 |
| G9 | 完整移除文件上方常駐操作區；精簡專案／檔案選單、dirty 標記；保留 Ctrl/Cmd+S、選單儲存、Agent 專屬復原與必要錯誤處理 | P3／A16、A17 | U4 |
| G10 | 同視窗、字級與縮放下，左欄實測為原寬 70%，長標題無溢出且可看完整內容 | P3／A18 | U5 |
| G11 | Thinking 圖示選單有 Normal／Extended；Permission 顯示 Ask／Bypass；兩者在底部左側，Send 右側，移除頂部說明與空列 | P3／A19、A20 | U5 |
| G12 | 權限、儲存、復原、重試、既有歷史與跨層協議不退化；規則不能繞過 Permission；以實際 GUI 流程完成驗收 | P1–P4／A06、A07、A12–A14、A17、A19、A21 | U6、U7 |

## 必須維持的行為

1. 引用加入不是執行授權；文件及聊天內容作為來源資料處理，不能改寫工具權限。
2. 單一目前專案、單一進行中回合。沿用現有操作序列與 busy guards，不新增多專案背景工作或新併發模型。
3. ConversationRepository 是唯一 canonical conversation writer；catalog 沿用既有職責。RESEARCH.md 只有設定與人類可讀內容。
4. 選區以原始文字的 UTF-16 半開區間為準，保留 emoji、重複段落、BOM、CRLF 及來源行號語意；不以內容搜尋猜位置。
5. 文件實際保存才算寫入成功；Permission Bypass 仍需相同 editor revision、磁碟 fingerprint、專案及操作歸屬檢查。
6. 一般 Ctrl+Z 與「復原上次 Agent 修改」語意分開。此次不新增自動儲存。
7. 既有資料不刪除、不擅自搬移／分配；讀取失敗和「新專案確實沒有對話」有不同可見狀態。
8. 已執行的工具／文件副作用不能因重試或重開自動重播；保留 turnId、callId 與現有去重、崩潰恢復語意。
9. 所有可變資料、prompt、pending approval、錯誤、finally 更新與 UI focus 都有目前專案／操作歸屬，不只比較相對檔名。

## 範圍與非目標

範圍：React/Monaco 工作區、Tauri/Python 協議、DesktopService 專案綁定、既有 canonical history 的必要欄位、Agent 的專案規則／提交上下文，以及相關現有測試與本計畫狀態紀錄。

不包括：RAG 資料與架構、Skill/MCP 管理重新設計、跨裝置或多人功能、通用 registry/framework、新資料庫、專案草稿持久化服務、原生 Windows 支援、改字體或整體縮放、全資料集回放、付費模型驗證、自動舊資料遷移、提交或推送。

原需求未指定 RESEARCH.md 格式、預設歷史位置、UI 選擇器實作及細部 DTO；[contracts.md](context/contracts.md) 的 D1–D9 均是本計畫提出的具體設計，不冒稱使用者已指定。選擇最小可行路線；只有會改變使用者資料歸屬等有實質後果的事項，才在受影響步驟停下取得決定。
