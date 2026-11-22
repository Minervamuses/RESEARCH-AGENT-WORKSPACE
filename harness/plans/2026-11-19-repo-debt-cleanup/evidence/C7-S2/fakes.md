# C7-S2 假物件（S031、S037）

- **日期**：2026-11-22
- **產品邊界**：只改測試接縫；production 一律用完整參數呼叫 `ChatSession.create`，行為不變。

## production（`agent/desktop/service.py`）

| 變更 | 說明 |
|---|---|
| `_materialize_session` | 刪除 4 處 `inspect.signature` 探測（`system_prompt`、`extra_tools`、`operation_approval_handler`、`citation_bibliography_path`）與 `_session_factory_accepts_bash`；一律以完整 kwargs 呼叫 factory（含 `bash_approval_handler`、`bash_command_runner`、`session_id`，`session_id=None` 與 `ChatSession.create` 的預設相同）。刪除 `import inspect`。 |
| 假物件分支 | 刪除 `isinstance(session, ChatSession)` 才設定 final-text validator、`getattr(session, "_set_prompt_persisted_callback")`、兩處 `hasattr(session, "system_prompt_message")`、`getattr(session, "clear_skill_installer")` 與回傳值的 `isinstance(cleanup, dict)`、`getattr(self.session, "mcp_families", {})`（改為 session 為 None 時視為沒有 family）。 |
| 留給後續步驟 | 這些也是私有存取，依 phase-07 由 C7-S4／C7-S5 改成公開介面時一併移除假物件分支：`getattr(session, "_conversation_snapshot")`、citation policy 的 `getattr` 鏈、installer context 與 `_skill_installer` 的 `getattr`、`isinstance(session, ChatSession)` 才預載 skill runtime（`_load_skill_runtime`）。`getattr(event_sink, "request_id", None)`、例外的 `code`／`status_code` 讀取不是為假物件而寫，保留。 |

## 測試

- 6 個明確列出參數的 session factory 加上 `**_kwargs`（`_SessionFactory`、`_DesktopBashFactory`、`_CoordinatorFactory`、`FixtureSessionFactory`，以及 `test_desktop_conversations.py`、`test_desktop_service.py`、`test_skill_adherence.py` 中的區域 factory，共 10 處）。
- 假 session（`_FakeSession`、`_CoordinatorSession`、`FixtureSession`）補上 production 現在無條件呼叫的 `_set_final_text_validator` 與 `clear_skill_installer`（回傳 `{}`）；兩處以 monkeypatch 替換 `clear_skill_installer` 的測試改為回傳 `{}`。
- **S037 集中**：被其他模組 import 的 helper 搬到新的 `app/tests/desktop_support.py`：`_FakeSession`、`_SessionFactory`、`_FakeExtensionManager`、`_service`、`_turn_params`、`_dispatch_approved`、`_open_test_project`（原在 `test_desktop_service.py`）與 `_DocumentModel`、`_Sink`、`_setup`（原在 `test_desktop_document_service.py`）。13 個測試模組改從 `desktop_support` import；原模組也改為 import。同名但語意不同的 helper（例如各模組自己的 `_turn_params`、`_service` 變體）不合併。沒有刪除或改寫測試斷言。
- 發現：第一次改完參數就跑完整 pytest 時超過 10 分鐘——參數錯誤的 factory 讓許多回合失敗後等核准逾時；補上 `**_kwargs` 後恢復正常耗時。

## 檢查

```bash
cd app && /home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider tests/   # 沙箱外
grep -n "inspect.signature\|_session_factory_accepts_bash" app/agent/desktop/service.py
```

- 完整 pytest：1756 passed。
- grep：0。
