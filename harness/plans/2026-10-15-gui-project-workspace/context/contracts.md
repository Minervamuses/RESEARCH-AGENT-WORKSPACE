# 跨層資料與工作區契約

這些是根據 GUI HEAD 提出的實作選擇。使用者確定的目標見 [GOALS.md](../GOALS.md)，授權／成本見 [PLANS.md](../PLANS.md)。下列設計不建立第二套 editor、history 或權限系統。

## D1：RESEARCH.md 的可解析設定

提案使用一個具名 HTML comment 包住 JSON，沿用 Python 標準庫；其餘 Markdown 逐位元組保留。範例：

```markdown
# 我的研究專案

專案說明與供 Agent 使用的規則。

<!-- research-agent-project
{"version":1,"historyDirectory":"/home/me/history/my-project"}
-->
```

- `historyDirectory` 是既有 storage 的基底目錄；canonical JSON 位於 `historyDirectory/conversations/`，既有 `desktop-projects.json` 位於基底。這項定義避免更改 ConversationRepository(persist_dir) 的既有目錄布局；不是新增另一份 conversations 清單。
- 恰好一個完整標記；JSON 僅接受 version=1、非空 historyDirectory，拒絕重複 key、重複標記、破損或未支援版本。一般文章中的範例 code fence 不當成有效設定標記。
- 絕對 Linux 路徑直接解析；相對路徑以 RESEARCH.md 所在專案根為基準，`..` 可合法指向專案外。明確拒絕 URL、Windows 路徑、環境變數與 `~` 展開等隱含語法。顯示 canonical resolved path 供確認，不依程序 cwd 解析。
- 新專案預設基底是 `Path(config.persist_dir).resolve()/projects/<projectId>`；這是歷史專屬位置，不改 config.persist_dir、RAG store、extensions 或 citation output。使用者可以改為任何可用的明確位置，不建立強制 .research/。
- projectId 提案為 `p-` 加 canonical project root UTF-8 的 SHA-256 前 32 位十六進位；以完整 canonical root 再核對 session identity，不只靠 basename。專案搬家後不猜測舊 projectId 歸屬，走明確 mapping 的條件決策 D7。
- 規則內容是移除這個 machine block 後的 Markdown；完整保留人類原文，不重新排版、不重寫 frontmatter。

初始化分三種：

1. 沒有 RESEARCH.md：專案開啟流程顯示預定歷史位置，使用者確認後，以不覆寫既有檔案的方式建立最小標題／說明／規則區及設定 block，再初始化新空 history。
2. 有檔但沒有設定標記：讀取並保留原文，開啟流程要求設定歷史位置，預覽僅追加設定 block；同意並確認檔案版本未變才寫入。不能把缺設定當成已存在的有效空歷史。
3. 已有標記：嚴格解析，錯誤即顯示可修正原因；不重寫、不 fallback。指向不存在目錄視為需要處理的問題；只有明確「在此初始化新歷史」操作才可建新資料。已有 catalog／conversation 不可讀，不能用初始化覆蓋。

初始化時明確建立 historyDirectory/conversations/ 空目錄，以及只含目前 projectId 的既有格式 catalog；不使用 bootstrap local 當另一個可選群組。已設定的歷史基底存在但 conversations/ 遺失，仍屬需處理的錯誤，不能視為「正常空專案」。

保存 metadata 前沿用 fingerprint／原子保存思路；建立後再次讀回驗證。跨多檔不宣稱資料庫交易：若新空目錄建立後 RESEARCH.md 寫入失敗，保留並清楚顯示位置，重試只能重用可確認仍為同一次初始化且無資料的目錄，不能刪除或取代已有歷史。

## D2：單一 project-open 邊界

沿用 `workspace.select` 作為「開啟專案」的既有入口，擴充其 request/result；不加平行 project registry。專案狀態只有未開啟、開啟中、已開啟、需處理錯誤等少數 UI 狀態，維持在現有 service/App。

成功結果至少包含 canonical rootPath、projectId、historyDirectory 與 rules fingerprint；前端才啟用 conversation、document 與 Send。`project.list` 若保留，對 GUI 僅回目前已綁定專案，不能 bootstrap/scan 全域資料或 fallback 到第一個 project。

開啟候選專案時先驗證根、設定、讀取權限、catalog 和必要規則；成功後才替換目前 session/repository/catalog/DocumentWorkspace。失敗保留舊專案與草稿；冷啟動則維持無專案。沿用 session shutdown/materialize 生命週期處理資源；若替換 session 失敗，舊專案可重新建立 session，但不能遺失前端草稿／文件。不為新選擇重新讀其他專案的內容。

開啟前 service 不實例化會建立全域 catalog 的 DesktopProjectCatalog，也不掃 conversation。可啟動 transport/runtime diagnostics，但不建立會載入他專案歷史的 session。

首次每次 App 冷啟動都先要求選資料夾，不偷偷恢復上次專案。後端 crash/restart 同一 App 視窗可在已明確選定的 project identity 下重新驗證綁定，仍要保留原草稿，不能退回全域列表。

## D3：專案規則與工具

既有 ChatSession 的 system prompt 保留；透過現有建立／恢復 session 路徑加入清楚標記的 project root 與 RESEARCH.md 規則區，不以它取代系統規則或改 Permission 狀態。規則可以影響研究行為，不能直接呼叫 set_bash_permission 或讓工具跳過 approval/version checks。

每次新回合開始前重新核對 RESEARCH.md；只在回合邊界更新規則。若磁碟指標改變，停止下一輪並要求重新開啟／驗證專案，不能在背景切換 history repository。未儲存的 RESEARCH.md 編輯不自動當成已生效設定；保存後下一輪再載入。當輪 rules snapshot／Permission／Thinking 在接受時固定，回合中設定控制停用。

history archive hint 已使用 repository.display_root，維持此來源。讓既有 read_file 工具的 history 分段讀取 allowlist 使用相同選定 repository root；只加必要參數沿 factory 傳遞，不修改全域 persist_dir。工具相對路徑有歧義時，prompt 及 document 操作使用 canonical root/absolute path，不 `os.chdir` 整個服務。不擴張為新的 OS sandbox 或 RAG workspace 系統。

## D4：引用與提交快照

在既有 turn 引入 typed `submittedContext`。建議最小邏輯形狀（實作的 Python 命名遵循既有 snake_case，JSON/TS 遵循 camelCase）：

```text
submittedContext:
  projectId, rootPath
  permissionMode: ask | bypass
  requestedThinkingMode: normal | extended
  skillReferences: 沿用現有 Skill reference DTO 陣列（可空）
  projectRules: { text, fingerprint }
  documentContext?: 原有完整 DocumentSnapshot
  references: Reference[]
Reference:
  referenceId, kind: document | chat, text
  document: { snapshot: 原有 DocumentSnapshot, startLine, endLine }
    或
  chat: { projectId, sessionId, turnId, role: user | assistant,
          messageFingerprint, startUtf16, endUtf16 }
```

canonical turn 既有 thinkingMode 保留實際 effective mode；requestedThinkingMode 只保存使用者當時偏好，以便文件回合強制 Normal 後仍正確顯示與恢復。skillReferences 沿用既有型別與執行路徑，保存是為重開後不丟原提交，不重做 Skill 管理。

這是明確二選一的型別，不允許 chat 帶 document 寫入座標。document snapshot 必須帶加入當下完整 sourceText、root/path、editorRevision、diskFingerprint 及 UTF-16 範圍，text 必須等於該範圍原文；行號由當時 source 算出，僅作顯示。未儲存文字的版本由 editorRevision＋sourceText 表示，不能把磁碟 fingerprint 當作未儲存內容的版本。

聊天引用取單一訊息可見文字的選段，保留角色及穩定來源；坐標明定為該訊息「可見文字」UTF-16 範圍，不冒稱 raw Markdown offset。messageFingerprint 也對同一可見文字計算。跨兩則訊息選取先提示一次選一則，不自動合成錯誤來源。選段出自引用卡、按鈕、工具狀態或隱藏內容時不當成訊息正文。處理 Markdown DOM 的呈現文字與段落換行一致性；不需重建 SafeContent renderer。已完成訊息、目前已提交 user message 與可讀歷史可引用；未具穩定來源的暫態內容不製造 turnId。

前端 draft references、已提交 immutable context 與目前文件背景各自明確表示，但納入現有 conversation state；不另建草稿 store。卡片預設摘要、展開完整 frozen text、來源與範圍、可移除（草稿階段）；送出後在 user message 可檢視原引用，不能改寫歷史卡片。

首次送出整包固定：text、skillReferences、background snapshot、typed references、project rules、Permission、既有 Thinking/turnId。同輪 retry 必須用原封包，後端以 durable turn 為準；不能重新套用目前選區、檔案、規則或新的 Skill 選擇。對失敗草稿修改文字或引用，改為新的 logical turn；原 failed turn 保留。若失敗後使用者選了不同 Permission／Thinking，不能暗中用舊 Bypass／舊設定執行：原回合重試入口顯示當時設定，與目前設定不一致時停用原 retry，提供保留同一引用內容、以目前設定另送新回合的明確操作；不自動切回舊 Permission。legacy 無 structured context 的 turn 不解析 semanticInput 字串來假造引用。

引用內容以資料區塊提供 Agent，與 project rules、目前文件背景分開；同一語意提交的 prompt 組裝需穩定。延用現有 1 MiB 輸入及 2 MiB transport 邊界，計算實際序列化大小（含必要 snapshot）。超限在送出前／後端驗證拒絕並保留草稿，告知移除引用或縮小來源；不能截斷 frozen text、擴大限制或任意丟卡。相同來源多段引用可在同一提交內重用已捕捉 snapshot 以避免重複，但僅在現有界線確實需要時做局部去重，不新增快取層。

## D5：持久化、協議與舊版本

canonical history 提案升為 schemaVersion=2，turn 多一個可空 submittedContext；仍由原 ConversationRepository atomic writer 寫入，不 sidecar、不在 RESEARCH.md 存內容。reader 同時明確支援嚴格 v1 及嚴格 v2，未知版本明確失敗。

- v1 讀取映射 submittedContext=null；既有 display/semantic/turn state 不變，不補猜引用、來源版本或 Permission。
- 只讀 v1 不改檔；對既有 v1 的首次實際寫入以既有 fingerprint 檢查原子升級，歷史 turns 保留，null context 明確表示未記錄。
- 引用／原提交資料與 pending turn 一起落盤，發出 provider/tool 工作之前就已 durable。完成、失敗、interrupted 與 retry 均保留同一 context；同一 turnId 不接受變更 context。
- 歷史 transcript DTO 回傳 references/必要 retry context，不把 semanticInput 長字串當公開 UI JSON 解析介面。只有使用者明確重試時才使用舊 context；讀歷史卡片不依賴原文件仍存在。
- 舊版程式會拒絕 v2，不宣稱雙向可寫。若執行時需改寫真實 v1，先保留原檔備份且位置／用途可見；若要回到舊程式，保存新 v2 資料，使用原 v1 備份供舊版讀取，不把新對話硬降級或丟棄。本計畫不操作使用者真實資料。

NDJSON envelope 先維持 protocolVersion=1，沿現有 additive optional request/result 欄位方式擴充；GUI bundle 的 TS/Rust/Python/shared contract 同步發布，不承諾新舊 backend binary 混用。必需欄位在新 GUI 工作流由 service 語意 gate 檢查，舊呼叫如缺 project 綁定明確拒絕。若執行證據顯示現有 v1 無法安全表示，再提出具體版本變更，不偷偷放寬 unknown-field 檢查。

需同步的 consumers：contract.json、fixtures.json、Python protocol validator/service DTO、TS protocol/types/state/backend consumers、Rust method/field/semantic validation、fixture session、canonical repository/session、各層既有 tests。新增「document/chat」union 需要在三層額外驗證 mutually-exclusive 欄位與 range，而非只增加 loose object。

## D6：文件背景與引用的寫回邊界

保留目前文件背景，即使 references=[] 也支援「修改第 40–45 行」。新提交的 background 不再暗中將未加入的滑鼠反白當作明確引用；若沒有明確修改引用要求，沿用 resolve_range 對使用者行號的判定及既有整檔背景能力。

對文件引用的修改須指向特定 referenceId，或只有一個無歧義引用時由 service 固定選出；不能憑最後反白、最後一張卡或相同文字搜尋。必要時在既有 document_edit 增加 optional reference_id，無此欄位仍沿用目前背景。chat referenceId 不能選作 writable target。有多個文件引用而要求不明確時，先由 Agent 問清楚，不自行選一個。

本次仍以目前編輯器文件為可寫目標；引用其他文件可以作分析上下文，若要修改須先明確開啟該文件並重新驗證，不能背景開另一套編輯器。針對引用的 candidate 用加入時 snapshot 建立，apply 時仍比較目前編輯器、磁碟與 root。文件改過、插行、重複段落或開了別檔均不得依舊行號覆寫；呈現原 snapshot、目前版本與 candidate，讓既有衝突流程決定。Bypass 只略過授權，不略過這些檢查。

歷史 retry 的目標文件不可用時，原引用照常可讀、不能用當前檔案替換；涉及寫回則回報檔案或版本問題。重試不得自動重播已保存 document call；沿用現有 turnId/callId 完成紀錄與非自動重播邊界。

## D7：切換、歷史歸屬與延遲結果

不新增持久化草稿功能。切換專案前採最小可理解流程：

- 有 active turn、approval、提交未終結時，前後端都拒絕切換，等待結束。不提供多專案背景並行。
- 有進行中 document save/apply/open 或其他會使用目前 session 的 mutation，沿用 busy guards 等待結果；不在中途換依賴。
- dirty 文件：儲存並切換／明確捨棄／取消。儲存失敗或衝突停留原專案。
- 未送文字或 references：明確「捨棄並切換」或取消回原稿；不自動送出、不默默清除。不提供「保留」卻未實作的承諾。
- 有待處理 candidate／版本衝突：先處理或取消；不能切完才套用到新專案。
- 全部通過且目標開啟成功後才清除舊 project 的 document、draft、submitted refs、Skill selections、conflict、undo receipt、preview、approval 和 UI notice。開啟失敗時仍保留原狀態。

同專案換 conversation 也不得使本次新增引用孤立或默默遺失草稿；重用上述草稿提示，不擴張為草稿保存產品。

以現有 backend generation/request/turn identity 加上 project epoch 與本次操作 token。新的專案開啟／關閉使 epoch 前進；A→B→A 也不能接收第一次 A 的舊結果。新回合請求、文件、session list/transcript、project open、save/apply、approval、success/catch/finally 皆核對 owning identity。後端在 await 前捕捉綁定，完成前核對，不能把舊結果寫入新 service state。不能只靠 root/path 相等或全域 busy 布林值。

歷史 ownership：
- 只掃明確選定 historyDirectory 下的既有 repository；catalog 作同一根的索引。catalog 修復僅可基於這個根的有效 canonical JSON 與已驗證 projectId；任何無法讀取／不完整掃描不能重建成空清單。
- 若根內有不同 projectId、null ownership 或兩個專案共指向同一混合目錄，顯示衝突，禁止將它當作新空專案或混入他專案內容。不由文件名、時間、local ID 猜歸屬。
- 既有全域歷史保持原位。只有使用者提供明確來源目錄、session 清單與目標專案 mapping 後，才規劃／執行被批准的搬移或 projectId 調整；本計畫不附自動匯入功能。沒有 mapping 不阻擋新空專案路線，但阻擋該舊資料接入。
- 搬家改 root 導致 hash projectId 不同屬同一條件決策，明示成本，不新增永久 root alias registry。

## D8：精簡 UI 的具體選擇

App 內 project chooser 對話框先提供現有 Linux 資料夾路徑輸入／確認及 history 設定預覽，選完即消失；這是本計畫對「選擇資料夾」的最小實作解讀。沒有原生 dialog plugin；若要求 OS 原生資料夾瀏覽器，需再確認新增依賴與 capability，不私自安裝。工作區只保留專案名稱／切換入口。

文件頁首僅檔名、dirty 點與操作選單；Open file 透過選單開出暫時的相對路徑開檔對話框，既有 root confinement 仍生效。Save 與 Undo last Agent edit 在同一選單，原快捷鍵不變；沒有常駐路徑輸入框。正常成功狀態用短暫／局部提示，不占固定正文列；失敗／衝突持續可見到處理完成。

sidebar CSS 兩端乘 0.7：14.5→10.15rem、17→11.9rem。以實際 bounding box 確認 70%，不只看 CSS 字串。長標題 ellipsis、hover/focus 可見完整標題；內部控制重排，字級與 App scale 不變。

composer footer 使用同一操作列，左為 Thinking 圖示 menu 與 Permission（含當前值），右為 Send；圖示有可辨識 accessible label、目前 mode 提示、鍵盤可開關及選項。Normal／Extended、Ask／Bypass 沿原 ACK 與 disabled logic。文件編輯既有 effective Normal 規則保留，若偏好 Extended，執行時短提示說明並在完成恢復偏好，不擴張模型 pipeline。

移除舊 session-controls、長說明及對應 grid row；必要的錯誤／approval 動態佔空間合理，正常狀態不能留下空白 placeholder。比較同尺寸同內容的 editor/transcript bounding box，高度應增加，數值由基線實測記錄，不虛構百分比。

## D9：決策與不確定性

| 項目 | 類型／處置 | 負責與阻塞範圍 |
|---|---|---|
| D1/D4/D5 具體格式 | 本計畫提案，明確啟動並接受格式後才寫 production schema | 執行者確認授權；影響 P1/P2 |
| 舊 history 的實際歸屬 | 未讀取真實資料，不猜測；需要時請使用者提供 mapping | 使用者；只阻塞其遷移／接入 |
| 原生 OS chooser | 非此最小方案必要；目前用 App 對話框 | 若使用者指定原生，再提出依賴批准 |
| RESEARCH.md 超出既有輸入上限／不可讀 | 明確錯誤，保留原檔，不截斷規則或忽略 | P1 邊界驗收；使用者修正內容或另批上限方案 |
| GUI 操作工具／WSLg 可用性 | 規劃未啟動 GUI；執行先確認 native 或人工可操作途徑 | P4 必要驗收；只做 browser/靜態檢查不能宣稱 Tauri 通過 |
| Rust build/full suite 時間 | 未量測；以現有 cache/紀錄判斷，可能 >10 分鐘先批准 | 僅阻塞該昂貴驗證 |
