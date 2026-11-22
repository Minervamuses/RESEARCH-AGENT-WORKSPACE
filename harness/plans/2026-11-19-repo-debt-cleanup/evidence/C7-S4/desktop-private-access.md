# C7-S4 desktop 端的私有存取（S052）

- **日期**：2026-11-22
- **產品邊界**：純改名與公開唯讀屬性；行為不變。

## 變更（`agent/session.py` 與 `agent/desktop/service.py`）

| S052 項目 | 原本 | 現在 |
|---|---|---|
| final-text validator | `session._set_final_text_validator(...)` | `set_final_text_validator(...)` |
| prompt persisted callback | `session._set_prompt_persisted_callback(...)` | `set_prompt_persisted_callback(...)` |
| citation policy 的讀取 | `getattr(self.session, "_citation_policy", None)` 與其後 3 個 `getattr` | 屬性改名為 `citation_policy`；service 直接讀 `policy.loaded_service.library_path` 或 `policy.bibliography_path()` |
| installer context | `getattr(self.session, "_installer_context", {})`、`getattr(getattr(self.session, "_skill_installer"), "paths", None)` | 唯讀屬性 `installer_context`、`installer_paths`（安裝尚未開始時為 None，service 照舊退回 `resolve_extension_paths`） |
| skill runtime 預載 | `isinstance(session, ChatSession)` 才呼叫 `session._load_skill_runtime(name)`；Citation 是否可派送用 `getattr(session, "_load_skill_runtime", None)` | 公開方法 `skill_runtime_for(name)`，兩處都直接呼叫（S031 留下的 `isinstance` 分支一併刪除）。名稱避開與 `agent.skills.runtime.load_skill_runtime` 函式同名。 |
| conversation snapshot | `getattr(session, "_conversation_snapshot", None)` 加 `isinstance` | 唯讀屬性 `conversation_snapshot` |
| system prompt 的設定 | `session.system_prompt_message = ...` | 本來就是公開屬性；C7-S2 已刪除它前面的 `hasattr`，不需改名 |
| `_reload_and_recover` | 私有 | `reload_and_recover`（C7-S7 使用） |

測試同步改名（`test_session_lifecycle.py`、`test_session_persistence.py`、`test_turn_finalizer.py`、`test_inline_skills.py`、`test_citation_skill_activation.py`、`test_citation_e2e.py`、`test_skill_adherence.py`、`test_desktop_service.py`、`test_desktop_fixture.py`、`test_desktop_conversations.py`、`desktop_support.py`、`support/fixture_session.py`）。假 session 補上 `skill_runtime_for`（`_FakeSession`、`_CoordinatorSession` 一律 `KeyError`，與原本「沒有這個方法就不可派送 Citation」相同；`FixtureSession` 原本就有真的載入，只是改名）。`test_project_permissions.py` 的 `ToolSession` 改設公開的 `installer_context`、`installer_paths`、`citation_policy`，不再設定私有的 `_installer_context`；它的 `_skill_installer` 屬於 installer bypass，留給 C7-S5。

## 暫留（依步驟規格，由 C7-S5 移除）

- `getattr(session, "_skill_installer", None)` 後設定 `bypass_approval`（`_session_turn`）。
- `session._document_turn_active = True／False`（2 處）。

## grep

```bash
grep -rn 'session\._[a-z]' app/agent/desktop/ | grep -v 'self\._session\b'
grep -rn '\(getattr\|hasattr\|setattr\)([^)]*"_[a-z]' app/agent/desktop/
```

結果：

```
agent/desktop/service.py:2741:                session._document_turn_active = False      # 暫留，C7-S5
agent/desktop/service.py:2970:                session._document_turn_active = True       # 暫留，C7-S5
agent/desktop/server.py:317:  lifecycle = getattr(self._service, "_with_turn_lifecycle", None)   # 不是 ChatSession：server 讀 DesktopService 自己的方法
agent/desktop/service.py:2695:        installer = getattr(session, "_skill_installer", None)    # 暫留，C7-S5
```

## 檢查

沙箱外完整 pytest：1756 passed。
