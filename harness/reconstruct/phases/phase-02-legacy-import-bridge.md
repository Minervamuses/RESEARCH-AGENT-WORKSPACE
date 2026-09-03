# Phase 02 — 建立非破壞性 legacy import bridge

Status: Not started

## Objective

建立只讀、可重跑、以 conversation 為原子單位的 legacy importer，將目前 conversation-history Chroma 與 Plan logs 轉成 Phase 01 的 canonical JSON。來源資料永不刪除、改寫或標記；任何 conversation 若無法完整且確定地轉換，就不得產生看似成功的部分 JSON。

本階段用合成 fixtures 驗證 importer，不對使用者真實 store 執行 migration，也不把 importer 接到正常啟動流程。

## In Scope

1. 將既有 Chroma role-pair reader 與 Plan log v1/v2 strict reader 收斂成 migration-only boundary。
2. 定義 legacy conversation identity、turn ordering、Plan/normal source 合併與重複偵測規則。
3. 將能確定還原的完整 turn 轉成 canonical completed records；無法安全還原的內容明確拒絕或以不進 context 的 display metadata 保存。
4. 實作 preflight read、完整 staging、來源 re-read/fingerprint compare、最後 atomic JSON publish。
5. 建立 migration tests，覆蓋 idempotency、partial failure、來源變動、malformed logs、已存在 JSON 與嚴格 parser 行為。

## Non-goals

- 不在 application startup 自動執行 importer。
- 不移除 `history_rag`, `plan_log.py` 或 Plan Mode runtime。
- 不對真實 Chroma directory、Plan log 或使用者 conversation 執行寫入。
- 不猜測已遺失的 pairing、時間、mode 或融合 Plan turns。
- 不新增 migration database、global success flag 或永久雙寫。

## Dependencies and prerequisites

- Phase 01 全部 acceptance criteria 與 focused tests 通過，schema 不再有未決欄位。
- 先讀 `app/agent/history_rag/store.py`, `app/agent/turns/plan_log.py`, `app/agent/turns/journal.py` 與相關 legacy tests。
- Chroma 與 Plan log 的限制是輸入事實，不是新 schema 的規範。已知 Plan fusion records 不能安全還原為普通對話時，必須 fail closed 或依已核准規則標為 non-context display metadata。
- 測試只可用 temporary directories、mock/fake legacy records 或既有小型 fixtures；不得需要 Ollama 或 live model。

## Expected components

預期最小變更面：

- `app/agent/conversations/legacy.py` 或等價 migration-only reader boundary
- `app/agent/conversations/migration.py`
- `app/tests/test_conversation_migration.py`
- 必要時調整既有 `test_history_rag_store.py`、`test_plan_mode.py`，把仍需保留的 strict-reader coverage 搬到 migration 語境

Importer API 應回傳結構化結果，例如 `created`, `already_present`, `skipped`, `failed` 與原因；不要只回傳布林值或以 log 猜結果。

## Authorization and stop conditions

本階段未授權真實 migration、legacy source cleanup、runtime cutover 或 schema 修改。遇到以下情況停止：

- 相同 legacy conversation 可合理映射到多個 canonical identity，且 repo 無法決定唯一規則。
- 必須載入或執行 live provider/Ollama 才能重建內容。
- 來源在兩次讀取間變化，而 importer 無法證明 output 對應同一 snapshot。
- importer 需要修改 legacy source 才能達成 idempotency。

## Implementation and verification plan

### Preflight

1. 列出目前 Chroma metadata、pairing/order 規則與 Plan v1/v2 record shape。
2. 以測試 fixture 建立 source-to-target mapping table，明列不可恢復情況。
3. 固定 output-exists 規則：有效 canonical JSON 已存在即視為完成；若存在但無效或 identity 不符，fail closed，不覆蓋。
4. 在 build log 記錄 importer 不會刪除或寫回任何 legacy source。

### Red

先建立會失敗的測試：

- 正常 Chroma pairs 能按原順序變成 completed canonical turns。
- 可恢復來源的 conversation/project identity、turn count、順序、文字與 timestamp 依 mapping table 等價；無法證明的欄位不被捏造。
- Plan v1/v2 中可確定的完整 records 能轉換；malformed、orphan、fusion ambiguity 不能產生部分成功檔。
- 同一 import 執行兩次只建立一次相同 JSON，不重複 turns。
- staging 後 legacy source 發生變化時，publish 被拒絕。
- canonical target 已有效存在時不覆寫；target 壞掉或 identity 不符時回報衝突。
- 一個 conversation 失敗時，其他 conversation 仍可獨立成功。
- Legacy Plan tool activity含未知欄位、secret-like key、raw argument/result、reasoning或超限文字時，不能穿透到canonical metadata或model context；依固定policy安全捨棄整項或使該conversation import失敗。

### Green

1. 重用既有 strict readers 的已驗證 parsing 行為；把 runtime-specific side effects 排除在 importer 之外。
2. 對每個 conversation 完整讀取並驗證，再建立記憶體內 canonical document。
3. 發布前重新取得來源 fingerprint/metadata；不一致即放棄該 conversation。
4. 只透過 Phase 01 repository 原子建立 target；不得直接拼 path 或自行寫 JSON。
5. 用 deterministic legacy-to-canonical ID/ordering 規則保證重跑一致。

### Refactor

- 僅抽取 importer 真正共用的 strict-reader code；不要建立一般化 migration framework。
- 若暫時仍有 runtime caller 使用 legacy reader，保留其既有行為，直到對應 cutover phase。
- 移除測試中不再代表實際 legacy contract 的重複 fixture，但不要刪除歷史使用者檔。

### Verification

從 `app/` 執行：

```bash
conda run -n app poetry run pytest tests/test_conversation_migration.py -q
```

如有移動既有 strict-reader coverage，再執行其實際受影響的單一測試模組。不得在本階段對 `app/store/` 或使用者 persist directory 執行 importer。

## Reliability, security, and recovery

- 每個 conversation 是 migration transaction 邊界：要嘛完整 target 發布，要嘛沒有 target。
- 成功判定來自有效 target JSON，而不是另設可漂移的 database 或 marker。
- legacy sources 永遠保留，因此失敗後可在修正 importer 後重跑。
- log/error 僅記 source kind、conversation identity 與安全原因，不複製 prompt/answer 全文。
- 任何 path、ID 或 version 不合法時拒絕，避免 traversal 或覆寫其他 conversation。

## Acceptance Criteria

- [ ] Chroma 與 Plan legacy reader 都只讀且有 strict malformed coverage。
- [ ] 每個 conversation 的 import 是 all-or-nothing，並在 publish 前偵測來源改變。
- [ ] 重跑 importer 不重複 turn、不覆寫有效 canonical JSON。
- [ ] 無法安全還原的 records 有明確結果，沒有猜測性 completed/context records。
- [ ] Canonical re-read 與 legacy strict-reader output 對 turn count、order、text、recoverable timestamp/identity 完成欄位級比對。
- [ ] Legacy activity cannot-smuggle tests證明raw/secret/reasoning/oversized metadata不進JSON或context；採drop或fail的規則固定且可見。
- [ ] 一個 legacy conversation 的失敗不阻斷其他 conversation。
- [ ] 測試未接觸真實使用者 store，legacy source 未被改寫或刪除。

## Evidence to record

在 `build-log.md` 記錄 mapping table 的定稿位置、可/不可遷移案例、實際變更、測試命令與 exit code、idempotency/source-change fault 結果。若任何 legacy shape 尚未理解，列為 blocker 而非假設成功。

## Handoff

Phase 03 的model/tool turn execution不得直接呼叫 importer；但host在選取尚無canonical JSON的legacy session時，可以先經這個明確migration boundary做單會話import，成功後才建立/執行Session。若 importer仍會partial publish或canonical target規則不明，先修復Phase 02；不要藉由runtime dual-write或source merge掩蓋問題。
