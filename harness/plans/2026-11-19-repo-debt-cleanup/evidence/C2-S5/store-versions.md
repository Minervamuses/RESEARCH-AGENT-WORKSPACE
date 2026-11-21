# C2-S5 `app/store` 對話 Schema 版本唯讀核對與測試退役紀錄

- **日期**：2026-11-21
- **涵蓋項目**：U6、S046

## 1. `app/store` 對話檔案版本檢查（唯讀，不含任何對話內容）

檢查路徑：`app/store/projects/*/conversations/*.json` 與 `app/store/conversations/*.json`

| 路徑 | `schemaVersion` |
|---|---:|
| `app/store/projects/p-c673e2df20456bc65ca0e4e23143255a/conversations/4f0e51add3144059b06699dfda3f286b.json` | 3 |
| `app/store/projects/p-c673e2df20456bc65ca0e4e23143255a/conversations/5983f50ef583466e85a46c212cae8b6f.json` | 3 |
| `app/store/projects/p-c673e2df20456bc65ca0e4e23143255a/conversations/59d9d09c2e084bdbab47390aca492d23.json` | 3 |
| `app/store/projects/p-c673e2df20456bc65ca0e4e23143255a/conversations/9f11eb8db7874881af25da36ec63f30f.json` | 3 |
| `app/store/conversations/*.json` | （0 個檔案） |

結論：`app/store` 下 4/4 個既有對話檔全部為 `schemaVersion = 3`，沒有任何非 v3 檔案。

## 2. 測試退役與新增紀錄

| 原測試 | 保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `tests/test_conversation_repository.py::test_rename_upgrades_only_target_preserving_legacy_turns_and_context[1, 2]` | v1/v2 對話檔讀取與 rename 升版為 v3（U6／S046 已刪除 v1/v2 讀取與升版） | 拆為：(1) `test_rename_updates_only_target_preserving_turns_and_context` 保留 v3 rename 隔離與內容保護斷言；(2) `test_legacy_schema_versions_are_rejected_without_upgrade[1, 2]` 驗證 v1/v2 在 `load()` 拋出 `ConversationMalformedError("unsupported schema version")` 且在 `scan()` 回報 `unsupported_version`、原檔位元組不變 |
