# C2-S3 驗證與測試退役／搬移紀錄

- **日期**：2026-11-21
- **涵蓋項目**：S061、S062、S063、S109、S122

## 測試退役與搬移紀錄

| 原測試 | 處置與保護的行為 | 留下的證據 |
|---|---|---|
| `tests/test_skill_runtime.py::test_load_skill_runtime_rejects_legacy_capabilities_field`、`test_load_skill_runtime_rejects_legacy_tool_policy_field` | 舊欄位專屬友善字串已隨 S061 刪除；拒絕舊欄位的行為仍由 `SkillManifest` 的 `extra="forbid"` 保護 | 同兩支測試改驗證包含欄位名稱與 `Extra inputs are not permitted` 的 `ValueError` |
| `tests/test_extension_baseline.py::test_skill_scan_ignores_only_regular_zip_sources` | 搬移（S062） | 原樣移入 `tests/test_extension_registry.py::test_skill_scan_ignores_only_regular_zip_sources` |
| `tests/test_extension_baseline.py::test_private_management_skill_is_not_publicly_discovered` | 退役（S062）：內建 skill 探索清單與 `extension-management` 為本地斜線指令而非公開 skill bundle | 由 `tests/test_inline_skills.py`、`tests/test_citation_skill_activation.py::test_citation_bundle_is_discovered_with_architecture_docs` 與 `tests/test_extension_manager.py` 覆蓋 |
| `tests/test_extension_baseline.py::test_default_slash_commands_use_case_insensitive_local_lookup` | 退役（S062）：其中 `get("SKILL") is get("skill")` 實為 `None is None` 無效斷言；本地斜線指令大小寫不敏感查詢 | 由 `tests/test_slash_commands.py`、`tests/test_extension_manager.py`（`/Extension-Management`）與 `tests/test_chat_cli.py` 覆蓋 |
| `tests/test_smoke.py::test_imports` | 退役（S063）：`rag.TOOL_SCHEMAS` 名稱集合與模組匯入 | `rag.TOOL_SCHEMAS` 由 `tests/rag/test_tools_contract.py` 驗證；`agent.graph`／`rag`／`AgentConfig` 匯入由保留的 `tests/test_smoke.py::test_graph_builds_without_error` 覆蓋 |
| `tests/test_smoke.py` 的 3 支 `AgentConfig` 驗證測試 | 搬移（S063） | 原樣移入 `tests/test_graph_skill_loader.py` |
| `tests/test_citation_gate.py` 對 `user_input=` 參數的傳遞 | S109 刪除 `gate.py` 中直接 `del user_input` 的無作用參數 | 保留全部區塊引述掃描斷言（`test_user_quote_block_does_not_exempt_renderer_markers`、`test_quote_is_still_scanned`） |
| `tests/test_ingest.py` | 搬移（S122） | `git mv` 至 `tests/rag/test_ingest.py` |

## 測試結果

- `pytest tests/test_skill_runtime.py tests/test_extension_registry.py tests/test_smoke.py tests/test_graph_skill_loader.py tests/test_citation_gate.py tests/test_turn_finalizer.py tests/test_desktop_crash_recovery.py tests/rag/test_ingest.py`：`134 passed in 9.96s`。
