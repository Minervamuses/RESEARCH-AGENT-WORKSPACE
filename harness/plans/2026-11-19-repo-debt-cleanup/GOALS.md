# Repo 債務清理：目標、決策與範圍

- **計劃根目錄**：`harness/plans/2026-11-19-repo-debt-cleanup/`（相對於 repo 根目錄 `/home/minervamuses/research-agent-workspace`）
- **路線與執行契約**：[PLANS.md](PLANS.md)
- **目前狀態與證據**：[build-log.md](build-log.md)
- **稽核原文**：[context/repo-debt-audit-2026-11-19.md](context/repo-debt-audit-2026-11-19.md)，項目 S001–S134
- **citation 決策紀錄**：[note/20261119/citation_storage_unification_decision.md](../../../note/20261119/citation_storage_unification_decision.md)

## 目的

使用者預期之後還會大改 UI/GUI，也會新增或修改功能，因此希望 codebase「簡潔、通暢，歷史債越少越好」（2026-11-19 使用者原話：「為了因應將來的開發，我希望現在的codebase是簡潔的、通暢的，歷史債越少越好」）。

2026-11-19 的唯讀稽核找出四個結構性的放大器：

1. 協定四份手抄本，加上大量沒人使用的詞彙。
2. 線兩端各有一個 god object：`DesktopService` 與 `App()`。
3. 測試與 production 互相綁死。
4. UI 沒有可重設計的地基。

稽核另外列出一批已退役功能的殘留與 7 個缺陷。本計劃處理稽核建議的路線（稽核 §3 的 Phase 0–3 與跨階段項目）、§5 的缺陷，以及使用者已決定的 U1–U9。

## 目標

| ID | 必須達成的結果 | 驗收時觀察什麼 | 來源 |
|---|---|---|---|
| G1 | 協定只有一份手寫來源。<br>• `contract.json` 是唯一手寫的方法、事件、錯誤碼與 schema 清單。<br>• TS 在建置與測試時直接讀它。<br>• Rust 只檢查框架。<br>• 只有 Python 做 schema 驗證。<br>• 每個 result 只送到 WebView 一次。 | • `protocol.ts` 與 `protocol.rs` 沒有手抄的方法、事件、錯誤碼清單，也沒有逐方法 schema 分支。<br>• parity 測試不存在。<br>• 對既有方法做「新增一個方法要改哪裡」的走查：只剩 contract、Python handler／dispatch、TS DTO 與呼叫端，以及 fixtures。<br>• 三語言測試通過。 | U1；S001–S005、S011、S012、S090 |
| G2 | 線上詞彙只剩有人用的部分。 | contract 剛好是 [PLANS.md](PLANS.md#目標詞彙) 列出的 26 個方法與 8 個 request event。<br>• 沒有 `streamKind`、`chunkCount`、`ollamaReachable`、`ollamaModelAvailable`、`citationOutputPath`、`registrationStatus`、`registrationIssue`、`bashPermissionMode`。<br>• 沒有 producer 的錯誤碼與欄位已移除。 | U2、U3、U4、U7、U8、P1–P3；S006–S010、S016 |
| G3 | citation 只有一套儲存：專案書目庫。<br>• CLI 不寫檔。<br>• BibTeX 鏈與 `pybtex` 移除。<br>• 驗證保證不弱化。 | • 桌面存檔只改寫書目庫，不產生 `cite/`。<br>• CLI 存檔不寫任何檔案，但當次對話可引用，工具結果明說未寫入磁碟。<br>• doi.org 回傳不同 DOI 時存檔失敗且不寫入。<br>• `pyproject.toml` 與 `poetry.lock` 沒有 `pybtex`、`latexcodec`。<br>• 細節依決策紀錄 §4–§5。 | U4、U9；S105、S106 |
| G4 | 桌面的對話清單由對話目錄掃描推導。 | • 程式不讀寫 `desktop-projects.json`。<br>• 沒有 `session.retry_registration` 與 registration 狀態。<br>• 既有對話照常列出，新對話在第一次送出後出現。<br>• 專案擁有權與歷史健康檢查照舊 fail closed（INV-016）。<br>• GUI 只有單一專案的路徑。 | U3；S018、S019、S027、S070 |
| G5 | 後端有清楚的接縫。 | • `agent/desktop` 與 `agent/thinking` 不再存取 `ChatSession` 的私有屬性。<br>• 「是否忙碌」只由一個 operation-state 物件判斷。<br>• Retry Stop 會重試清理，成功後恢復可用（FAIL-022）。<br>• `fixture_session.py` 位於 `tests/`，`server.py` 沒有 fixture 開關。<br>• `service.py` 只剩 dispatch、生命週期與接線，其餘職責在各自模組。 | 使用者要求依稽核路線規劃（U10）；S020、S028、S031、S037、S052 |
| G6 | 前端有可重設計的地基。 | • `App()` 只做組裝：domain state 在 hooks，不直接呼叫 backend 或 `invoke`。<br>• 只有 `api.ts` 呼叫後端。<br>• 純邏輯在 `.ts` 模組，測試直接 import 且受 `tsc` 檢查。<br>• dialog 與 menu 各只有一份實作。<br>• 顏色經由 CSS 變數。<br>• browser-preview 降級模式不存在。<br>• 釘住 layout 的測試改成行為斷言。 | U5、U10；S078、S080–S083、S086–S088、S093、S096、S097 |
| G7 | 稽核 §5 的缺陷已修正。 | • FAIL-022 由 G5 修正。<br>• `.error-text` 有錯誤樣式。<br>• 「超過 context token 上限」之類的正當錯誤原文顯示，含憑證格式的內容仍被 Python 遮蔽。<br>• Rust 每個 result 只傳一次。<br>• `TurnJournal.turn_logs` 不再無限累加。<br>• `doi_org` 的型別標註正確，或該函式已移除。<br>• `app/desktop/watch.out` 已刪除。 | U10；稽核 §5；S003、S047、S089、S128 |
| G8 | 稽核標為 READY 的清理全部完成或附理由回報；對話 schema 只剩 v3。 | • 每個 READY 項目在最終彙報的狀態是 APPLIED 或附理由。<br>• 讀到 v1/v2 對話檔時明確拒絕，不靜默升版。 | U6、U10；S003–S005、S008、S014、S021–S024、S026、S029、S031、S038–S044、S046、S061–S063、S071–S076、S085、S092、S098、S101、S102、S108–S110、S114、S115、S117–S120、S122、S128、S129 |
| G9 | 可交付、可驗證。 | • 起點有基線。<br>• 完成時 pytest、`npm test`、`npm run build`、`cargo test --locked` 全部通過。<br>• 文件與現況一致。<br>• 最終彙報列出每個 S-ID 的結果、量測前後數字、使用者可見的行為改變、過時的 `for_agents/` 條目、GUI 手動檢查清單與未處理的決策。 | 使用者執行慣例 |

## 使用者已確認的決策

| ID | 決策 | 來源 | 後果 |
|---|---|---|---|
| U1 | 協定驗證縮減：<br>• Rust 只驗框架。<br>• TS 直接讀 `contract.json`，只驗 request 參數與 id 回聲。<br>• Python 是唯一的 schema 驗證者。 | 使用者對稽核問題回覆「好」。問題原文：「協定驗證要不要縮減？目前一個訊息最多被驗 7 次。我建議 Rust 只驗框架，TS 直接讀 contract。如果論文要主張『三層驗證邊界』，就不能這樣縮。」驗證範圍依稽核 §4 #1 的建議「TS import contract，只驗 request 與 id 回聲」。 | • 論文不能宣稱 TS 或 Rust 是獨立的逐方法驗證層。<br>• event 是否連號只由 Python 保證並由 fixture 測試覆蓋，執行時不再交叉檢查。<br>• INV-011 過時。 |
| U2 | 10 個 `knowledge.*` RPC 全部刪除。 | 先回覆「好」，再以選項確認「全部刪除」（2026-11-19）。 | 桌面的 RAG 仍走 composer 指令 `/init /ingest /sync /prune` 與 agent 的 `rag_*` 工具，兩者必須照常運作。 |
| U3 | `desktop-projects.json` catalog 改成由對話目錄掃描推導。同時刪除 registration retry 與多專案殘留。 | 使用者回覆「好」。問題原文：「desktop-projects.json catalog 要不要改成直接掃描對話目錄？這樣可以一併刪掉註冊重試和多專案殘留。」 | 「catalog 指向不存在的對話時拒絕開啟專案」這個 fail-closed 行為消失：遺失的對話只是不出現在清單。稽核 §4 #4 把這列為前提。 |
| U4 | citation bundle 併入專案書目庫，書目庫成為唯一儲存。CLI 不再存檔。 | 「同意，但是要在note裡面紀錄這個決定，寫詳細點」。決策紀錄已在撰寫計劃時寫成 `note/20261119/citation_storage_unification_decision.md`。 | 行為細節與必須保留的保證以決策紀錄 §4–§5 為準。 |
| U5 | browser-preview 降級模式直接刪除，不改成假資料預覽。 | 選項「直接刪除」（2026-11-19）。 | 前端只支援在 Tauri 內執行；在一般瀏覽器開啟時顯示一般的後端無法連線錯誤。 |
| U6 | 刪除對話 schema v1/v2 讀取器。 | 選項「刪除」（2026-11-19）。使用者已知道 `app/store` 以外的 `historyDirectory` 無法由我檢查。 | v1/v2 檔案在開啟專案時被拒絕。C2-S5 執行前要先唯讀確認 `app/store` 下沒有非 v3 檔案。 |
| U7 | 移除未使用的協定詞彙：<br>• 12 個從未發出的 event。<br>• `streamKind`／`chunkCount`。<br>• 永遠是 null 的 Ollama 欄位。 | 勾選「移除未使用的協定詞彙」（2026-11-19）。 | GUI 的「Ollama: unknown」顯示一併消失。 |
| U8 | 權限欄位統一命名為已持久化的 `permissionMode`。對象是線上的 `bashPermissionMode` 與參數 `mode`。 | 勾選「權限欄位統一命名」（2026-11-19）。 | 對話檔不受影響。 |
| U9 | 核准從 `pyproject.toml` 與 `poetry.lock` 移除 `pybtex`。 | 勾選「移除 pybtex 相依」（2026-11-19）。這是 AGENTS.md 要求的明確核准。 | 只授權這一項相依變更，不授權其他新增、升級或移除。 |
| U10 | 依稽核撰寫計劃，處理上述優化與問題。 | 「寫計劃來處理上述優化和問題」（2026-11-19）。 | 範圍是稽核 §3 的路線、§5 的缺陷與 U1–U9，邊界見下方「範圍」。 |

## 計劃提出、未經使用者逐項確認的做法

下列做法都可逆，且在 U10 的範圍內。使用者若不同意，可在啟動前修改本表，或在啟動提示中說明；沒有否決就照本表執行。最終彙報會逐項列出。

| ID | 做法 | 理由 |
|---|---|---|
| P1 | 一併移除另外 3 個沒有呼叫者的 RPC：`session.status`、`session.shutdown`、`extensions.status`。<br>只刪 RPC 註冊；`workspace.select` 與 `session.delete` 仍會用到的內部函式保留。 | 證據與 U2 相同：GUI 與 Rust 都不呼叫（稽核 S007）。 |
| P2 | 方法 `session.set_bash_permission` 改名為 `session.set_permission`，元件 `BashPermissionControl` 改名為 `PermissionControl`。 | 與 U8 是同一筆命名債：這個權限管的不只 bash（`trust.tsx:387` 的 tooltip）。 |
| P3 | C4、C5、C6 完成後，移除沒有任何 producer 的錯誤碼。 | 與 U7 同類，屬於未使用的詞彙。 |
| P4 | FAIL-022 的修法：Retry Stop 重新執行清理。成功就回到可用狀態；失敗就回報這次的新錯誤，服務繼續封鎖。 | 根目錄 `README.md` 承諾 Retry Stop 可以恢復；BACKLOG-022 列出的兩個方向中，這個與現有承諾一致。 |
| P5 | `fixture_session.py` 移到 `tests/support/`。`server.py` 的環境變數開關改成測試自有的啟動入口。 | 稽核 §4 #8 建議如此。這個開關只有測試在用，README 沒有記載使用者流程依賴它。 |
| P6 | 錯誤訊息的遮蔽只由 Python 負責：<br>• 以值的格式辨識憑證。<br>• 刪除 TS 依關鍵字整句隱藏的做法。 | 修正稽核 §5 #3。目前的做法會隱藏正當訊息。 |
| P7 | CLI 存檔的狀態語意：<br>• `saved` 表示這次 task 新驗證並登記，`reused` 表示這次 task 已有同一 identity。<br>• 不新增狀態值。<br>• 是否持久化只看 `bibliography` 連結。 | 決策紀錄 §4.2。這樣可避免 `CitationSaveMetrics` 與 turn trace 的計數語意改變。 |

## 範圍

### 納入

- 稽核 §3 Phase 0 的 READY 清單。唯一例外是 S106：選了 U4 之後，它隨 bundle 一起消失。
- Phase 1 的 S001、S002、S006–S012、S016、S090。
- Phase 2 的 S020、S028、S031、S037、S052，以及 `service.py` 模組化。S034 的錯誤對照表隨模組化搬到 `errors.py`。
- Phase 3 的 S078（依 U5）、S083、S096、S097。
- 跨階段的 S086–S088。
- 隨上述項目自然發生的部分：
  - S022、S032 中只屬於 knowledge 的部分、S036 中只因移除功能而失效的測試。
  - S043、S066 中只與 S052 改動有關的部分。
  - S070、S079–S082、S093。
  - S121 中只因 U4 而失效的測試。
  - S123 中 bibliography handler 抽出成模組的部分。
- 稽核 §5 的 7 個缺陷。
- U1–U9 與 P1–P7。

### 不納入（留待使用者決定，最終彙報列出）

| 項目 | 不納入的理由 |
|---|---|
| S125 刪除已完成的計畫紀錄 | 使用者的 GUI checklist 與 live grill eval 尚未完成。 |
| S134 把 `GUI` 合回 `main`、刪除 `clean` 分支 | 使用者的執行規則禁止建立、切換、刪除 branch 與 push。 |
| S084 `styles.test.ts` 與 INV-021 | 屬於之後的 UI 重設計。本計劃保持 INV-021 的數值不變。 |
| S067 `chromadb`、`openrouter` 相依 | 相依變更需要另外核准；U9 只核准 `pybtex`。 |
| S131 `AGENTS.md` 過時 | 使用者的治理文件。 |
| S126、S127 根目錄筆記與 `note/20261106/` | 使用者的研究資料。 |
| S132 `tool/local/` 預留區 | 產品方向決定。 |
| S133 README 改寫成「概念＋流程」 | 文件風格決定。C10 只更新與行為不符的段落。 |
| 長尾 DECIDE 項目：<br>• S013、S015、S017、S025、S030、S033、S045<br>• S048–S051、S053–S060、S064<br>• S077、S091、S094、S099、S100、S103<br>• S111–S113、S116、S130<br>• S032、S036、S066、S121、S123 中未列入「納入」的其餘部分 | 不在稽核 §3 的路線內，或證據信心較低，或會改變行為卻沒有使用者決策覆蓋。 |

### KEEP（稽核確認有用途，不動）

S034（只搬家）、S035、S065、S068、S069、S095、S104、S107、S124。

## 必須保留的不變量

除了 U1–U9、P1–P7 明列的改變，下列行為必須維持。驗收以既有測試與各階段列出的檢查為準。

- **Python 擁有 policy 與持久化寫入**（INV-015）。React 只經由協定到達 domain 操作；Rust 只管一個 Python child generation。
- **安全邊界照舊**：
  - 禁止鍵掃描：Rust 的 `validate_safe_data` 與 Python 的 `FORBIDDEN_DATA_KEY_FRAGMENTS`。
  - 工具存取與核准（INV-004、INV-018）。
  - 不可信內容的顯示（INV-017）。
  - 擴充信任（INV-009、INV-013）。
  - 文件存取範圍（INV-025）。
  - 本地紀錄最小化（INV-028）。
- **對話持久化**：canonical JSON 是唯一權威，寫入照常是 atomic 且 prompt-first（INV-006）。唯一改變是讀取版本只剩 v3（U6）。
- **回合語意**：INV-005、INV-026、INV-027（P4 只補強恢復路徑）、INV-033、INV-034 不變。
- **Citation**：只有驗證成功的存檔可被引用（INV-010 的主體）；書目庫合併規則（INV-032 的其餘部分）；`/citation` 的 provider 限制（INV-030）。
- **桌面 RAG 指令**：`/init /ingest /sync /prune` 與 `rag_*` 工具的行為不變。
- **畫面數值**：INV-021 的字級數值不變，`styles.test.ts` 不修改也要通過。

## 限制

- **環境**：Linux、Conda env `app`、Poetry 管理相依（不用 venv，不用 pip）、檔案用 LF。測試放在 `app/tests/` 或 `app/desktop/tests/`（AGENTS.md）。
- **相依**：除了 U9 的 `pybtex`（連同 lock 中只被它依賴的 `latexcodec`），不新增、不升級、不移除。前端不新增 npm 套件，所以不引入 jsdom 或 testing-library。
- **付費 API**：不呼叫任何付費 API，也不啟動會連 OpenRouter 的 CLI 或桌面 app。免費的 citation provider（Crossref、DataCite、doi.org）可用於選擇性的冒煙測試。
- **版本控制**：不建立、切換、刪除或重新命名 branch，不 push，不建立 worktree。
- **不修改**：
  - `for_agents/`：由 `$infrastructure` skill 維護，且使用者有未提交的修改。
  - `AGENTS.md`、`note/` 既有內容、其他 `harness/plans/` 計劃。
  - `~/.claude/`、使用者論文資料夾與任何使用者專案的 `RESEARCH.md`。
  - `app/store/` 的資料，以及 `cite/` 的殘留檔案。
- **不提交**：與本計劃無關的未追蹤檔案。包括根目錄的 `NOTES-grill-skill-and-document-context.md`、`note/20261106/`，以及沙箱產生、指向 `/dev/null` 的點檔（`.bashrc`、`.profile`、`.claude/` 內的裝置檔等）。commit 時只 `git add` 明確路徑。
- **GUI 驗收**：由使用者本人操作。執行者交付手動檢查清單，不宣稱 GUI 行為已驗證。

## 待確認的假設

| ID | 假設 | 若不成立 | 處理 |
|---|---|---|---|
| A1 | 存檔批次的 artifact（`citation_save_batch`）不會寫進對話 JSON。 | 改 receipt 欄位會讓舊回合無法讀取。 | C5-S1 確認。若會寫入，C5 停在 S1 並回報。 |
| A2 | 有一種 JSON import 寫法能同時滿足 `tsc --noEmit`、`vite build` 與 `node --test --experimental-strip-types`。 | TS 測試載入 `protocol.ts` 的方式要改。 | C1-S4 探測，C3-S1 決定。備案是讓測試透過 Vite SSR 載入，不另外產生 TS 副本。 |
| A3 | 斜線指令 `/init /ingest /sync /prune` 的核准不使用 `knowledge.*` 這組 operation 名稱。 | `trust.tsx:329-331` 的標籤仍有人用，不能刪。 | C4-S1 先查再刪。 |
| A4 | `app/store` 下的對話檔都是 schema v3（2026-11-19 讀到 4/4 是 v3）。 | U6 會讓這些檔案無法開啟。 | C2-S5 執行前重新確認；發現非 v3 時停下該步並回報。 |
| A5 | `ChatSession` 的私有屬性只被 `agent/desktop`、`agent/thinking` 與測試存取。 | S052 的範圍會變大。 | C7-S3 以 grep 盤點。 |
