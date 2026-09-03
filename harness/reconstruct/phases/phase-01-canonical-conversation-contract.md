# Phase 01 — 建立 canonical conversation contract

Status: Not started

## Objective

在不切換既有 CLI 或 Desktop 執行路徑的前提下，建立唯一、可測試的對話 JSON 契約與 repository 邊界。完成後，每個 conversation 都能以一份 schema-versioned UTF-8 JSON 表示，並具備原子寫入、衝突拒絕、局部損壞隔離，以及「最近 10 個可進入 context 的 completed turns」查詢語義。

本階段只建立新資料契約與最小持久化元件；不做 runtime cutover、不遷移真實資料，也不移除 Plan Mode 或 Chroma。

## In Scope

1. 在 `app/agent/` 下建立最小 conversation persistence package；預期是 `app/agent/conversations/`，但實作者須先以現有命名與 import 邊界為準。
2. 固定 schema version、conversation metadata、turn identity、turn state、display/context eligibility、tool activity 摘要、錯誤與時間欄位的精確拼字和型別。
3. 實作一個 conversation 一個 JSON 檔的 load/create/append-transition/list-summary API。
4. 實作同目錄 temporary file、flush/fsync、atomic replace，以及載入後再寫入前的 fingerprint/conflict 檢查。
5. 建立最小 repository 測試，覆蓋 round trip、排序、latest-10、Unicode、損壞檔案隔離、未知版本與外部改寫。

## Non-goals

- 不改 `Session`, Desktop service、CLI、React、TypeScript 或 Rust 呼叫流程。
- 不讀寫既有 conversation Chroma 或 Plan logs。
- 不加入 SQLite、服務、背景 worker、lock server、通用 event-sourcing framework 或新 dependency。
- 不定義跨多程序 writer 協調；本計畫的 runtime contract 是單一 writer。
- 不把 `app/rag/` 的 JSON store 直接匯入 agent domain；可參考其原子寫入慣例，但不能反轉模組邊界。

## Dependencies and prerequisites

- Baseline 必須仍是 `GUI` 分支、HEAD `b145b040f014560157ef9444544f4102b81e485e`，或由 build log 明確記錄並重新審核後續 drift。
- 使用 WSL/Linux 與 Conda `app` 環境；所有 Python 命令從 `app/` 執行。
- 先讀 `GOALS.md`、`PLANS.md`、本檔，以及目前的 `app/agent/turns/memory.py`, `journal.py`, `store.py`, `desktop/catalog.py`。
- 精確 schema 尚未由既有程式碼決定；必須在本階段第一個 implementation checkpoint 固定，之後若需改 persistent schema，先停下取得新的使用者授權。

## Expected components

預期最小變更面如下；實作者可因現有結構改名，但不得擴大責任：

- `app/agent/conversations/__init__.py`
- `app/agent/conversations/models.py`
- `app/agent/conversations/repository.py`
- 必要時，現有 config 中一個取得 `<persist_dir>/conversations` 的小型 helper
- `app/tests/test_conversation_repository.py`

建議 contract 必須至少表達：

- conversation：`schemaVersion`, `conversationId`, 所屬 `projectId`（依現行 projectless 規則允許明確空值時亦須驗證）、建立/更新時間、可推導 sidebar title/turn count/updatedAt 的資料，以及 ordered turns；空白未送出的 transient UI session 不必先建立 canonical file。
- turn：stable logical `turnId`、conversation-local monotonic `turnNumber`、原始 display input、semantic/context input、state、context eligibility、時間、final display output、受限的 tool activity display metadata、failure/interruption metadata。
- lifecycle status至少可明確區分`pending`, `completed`, `failed`, `interrupted`，並與`conversational`/`display-only`呈現種類或等價欄位正交；本機command能先以pending display-only kind保存，再完成/失敗，且永遠不進context。若使用不同拼字，必須在`GOALS.md`和跨語言fixture中唯一固定。
- schema 必須能 round-trip normal、extended 與 display-only turns 所需的最小安全 metadata，但不得保存 chain of thought 或 raw provider/tool payload。
- Error/tool/display metadata 必須使用封閉的 allowlisted fields與逐欄 bounds；不得提供任意 `metadata: dict` 入口，secret-like keys、raw stderr、unfiltered tool arguments/results、provider response、LangGraph message/object 或 reasoning trace 一律拒絕，不能靠 caller自律。
- context query 只回傳最新 10 個 `completed` 且 context-eligible 的完整 user/assistant pair，依 turnNumber 升冪輸出；目前 prompt 由 caller 另行加入且恰好一次。
- retry contract 必須固定：同 logical ID 與同一輸入可從 failed/interrupted 明確重試或讀回既有 completed 結果；同 ID 不同輸入一律 conflict，且 retry attempt 本身不額外占 context turn。
- Sidebar title derivation固定為最低turnNumber的第一個有效、已接受、非display-only conversational prompt：semantic input nonblank才有效，title由bounded original display input推導；pending/failed/interrupted仍可提供title，後續turn與catalog cache不能取代它。

## Authorization and stop conditions

本階段未授權改 public protocol、刪舊資料、執行真實資料 migration、加入 dependency 或更動 `app/rag/`。遇到下列任一情況立即停止並記入 `build-log.md`：

- 既有支援中的外部 consumer 需要同時相容兩個 persistent schema。
- 無法在單 writer 前提下用現有標準函式庫安全完成原子 replace。
- 精確 turn identity 或 retry 語義需要 public API 決策，而 repository-only 測試無法先固定。
- 完成本階段需觸及超出新 package、config helper 與相鄰測試的廣泛 production files。

## Implementation and verification plan

### Preflight

1. 執行 `git status --short`，保留使用者既有變更並記錄 baseline。
2. 以 `git grep` 追蹤 `persist_dir`, `ConversationCatalog`, `TurnRecord`, `atomic`, `fsync` 的既有慣例。
3. 在 build log 寫下精確 schema 欄位、transition table、writer ownership 與檔名規則，再開始 production code。
4. 確認檔名只由已驗證 UUID/conversation ID 產生，不接受任意 path component。

### Red

先加入會失敗的最小測試，證明尚缺少以下行為：

- 建立 conversation 後，以同一 stable turn ID 寫入 `pending`，再 transition 成 `completed`，round trip 不改變 identity 或順序。
- 12 個 completed eligible turns 只選最後 10 個；failed、interrupted、display-only 與 context-ineligible turns 不進 context。
- Unicode、換行與 display/semantic input 差異可無損 round trip。
- 現有 protocol/config 所允許的最大 message 可 round trip；超過明確 per-field/per-document bounds 時只拒絕該操作或隔離該檔案。
- 單一 malformed/unknown-version JSON 不妨礙列出其他 conversation。
- load 後被外部改寫時，舊 snapshot 的 save fail closed，不能覆蓋較新的檔案。
- Normal、extended、display-only 與同-ID retry 都可 round trip；completed duplicate 不新增 turn，不同 prompt duplicate 被拒絕。
- 第一個accepted conversational prompt即使仍pending或後來failed也穩定產生title；blank/invalid/display-only commands不產生title，後續prompt不改寫既有title。
- 嘗試寫入 chain-of-thought/reasoning、raw provider payload/stderr、未過濾 tool args/results、secret-like metadata、React/LangGraph object時，schema/repository拒絕且磁碟不留下部分內容；允許的 display metadata受逐欄與總量 bounds。

### Green

1. 實作最小 immutable/validated data model 與顯式 parser；拒絕缺欄、型別錯誤、重複 turn ID、非單調 turnNumber、非法 transition。
2. 實作 repository create/load/save/query，寫入只經同一 repository 邊界。
3. 寫入 temporary file 時確保 UTF-8、可重現 JSON encoding，file flush/fsync 後以 atomic replace 發布，再 fsync parent directory；平台不支援時必須明確失敗或以已驗證的既有 Linux慣例處理，不得假稱 durable。
4. 在 replace 前比對先前 fingerprint；不一致時回傳可辨識 conflict，而不是自動 merge 或覆蓋。
5. list/summary 掃描逐檔隔離錯誤，保留可操作 conversation；錯誤須可供 host 顯示，但不得把壞檔內容注入 prompt。
6. 以專用 typed/allowlisted DTO接受最小 failure與display metadata；禁止任意 dict或物件序列化，驗證失敗必須發生在temp publish前。

### Refactor

- 只移除本階段新增的重複程式；不順手重構 `journal.py`, `store.py`, `history_rag/` 或 catalog。
- 保持 repository API 足夠支援後續階段，但不要預建 adapter/registry/plugin 抽象。
- 用名稱與型別表達 state transition；註解只解釋 durability 或 safety 原因。

### Verification

從 `app/` 執行：

```bash
conda run -n app poetry run pytest tests/test_conversation_repository.py -q
```

若本階段修改既有 config，再加最接近的 config 測試模組。不要在此階段跑 live provider、Ollama 或完整 migration。

## Reliability, security, and recovery

- 原始 prompt 的 durability 最終會依賴本 repository，因此 pending write 必須能明確確認成功或失敗。
- 單檔 corruption 不能造成全域不可用；錯誤需帶 conversation ID/path 的安全摘要，不回傳整份敏感內容。
- 不建立自動修復未知 schema 的猜測路徑；未知版本只讀失敗並保留原檔。
- conflict 是安全失敗：重新載入後由上層決定，不允許 silent last-writer-wins。
- temporary 檔命名與清理不得誤刪其他 conversation 或 legacy source。

## Acceptance Criteria

- [ ] Schema 與 transition table 在程式、測試與 build log 使用同一組名稱。
- [ ] 一個 conversation 對應一個 versioned UTF-8 JSON，且 repository 測試證明 atomic publish 路徑。
- [ ] Stable logical turn identity 與 monotonic turnNumber 可 round trip。
- [ ] Normal、extended、display-only 及同-ID retry/duplicate/conflict 的 schema 與 transition tests 都已固定。
- [ ] latest-10 query 排除所有不合格 state，並維持時間/turnNumber 順序。
- [ ] display input 與 semantic/context input 可不同且皆被保存。
- [ ] Project identity 與 sidebar summary 可由 JSON 驗證/推導；第一個 durable prompt 足以使 conversation 成為可恢復項目。
- [ ] Title tests固定first-valid rule，並證明pending/failed first prompt、display-only first record、blank input與later turns的行為。
- [ ] 最大合法 message、oversized field/document 與 bounded parse 行為有 executable coverage。
- [ ] Forbidden hidden/dangerous payloads有逐類negative tests；允許的 error/tool/display metadata是封閉、bounded且不會進model context。
- [ ] malformed、未知版本與外部 rewrite 均 fail closed，其他 conversation 仍可使用。
- [ ] 沒有 runtime caller 被切換，也沒有舊資料被修改。

## Evidence to record

在 `build-log.md` 的 Phase 01 區塊記錄：實際變更檔案、固定 schema 摘要、transition table、測試命令與 exit code、失敗注入結果、任何 baseline drift。不得預先寫「pass」。

## Handoff

下一個 fresh agent 應先讀 Phase 01 build-log evidence 與最終 schema，再執行 Phase 02。若 schema 尚有 TODO、測試未通過或 repository 仍會 silent overwrite，Phase 02 不得開始。
