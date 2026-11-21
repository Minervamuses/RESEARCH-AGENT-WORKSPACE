# C2-S1 驗證與測試改寫紀錄

- **日期**：2026-11-21
- **涵蓋項目**：S038、S039、S041、S042、S044

## 測試退役與改寫紀錄

| 原測試／斷言 | 保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `tests/test_thinking.py` 的 10 個同步 helper 測試（`rewrite_prompt`、`review_draft`、`parse_reviser_output`、`aggregate_candidates`） | 同步版 thinking LLM 包裝（S038 已刪除，production 只呼叫 async 版） | 同檔案改為對應的 async 版測試（`arewrite_prompt`、`areview_draft`、`aparse_reviser_output`、`aaggregate_candidates`），輸入分區與斷言完全保留 |
| `tests/test_openrouter_model.py::test_invoke_text_invokes_chat_model_with_human_message` | `agent.llm.text.invoke_text` 字串包裝（S039 已刪除） | 改為 `test_invoke_text_messages_invokes_chat_model_with_human_message`，測正式路徑 `invoke_text_messages` |
| `tests/test_text_normalization.py::test_text_invoke_text_drops_unknown_parts_and_strips` | `agent.llm.text.invoke_text` 的單一 `HumanMessage` 包裝與 `drop_unknown_parts=True` 正規化（S039 已刪除 `invoke_text`） | 改為 `test_normalize_content_drops_unknown_parts_and_strips`，保留全部 9 組 `normalize_content(..., drop_unknown_parts=True)` 參數化案例；`thinking.invoke_text`（`invoke_text_messages` 別名）的 9 組案例原樣保留 |
| `tests/test_session_lifecycle.py`、`test_session_persistence.py`、`test_desktop_conversations.py` 共 3 處 `ChatSession.restore(...)` | `ChatSession.restore` 轉手建構函式（S042 已刪除） | 改呼叫正式入口 `ChatSession.create(..., session_id=...)` |
| `tests/test_turn_finalizer.py`、`test_citation_e2e.py`、`test_observability.py`、`test_citation_skill_activation.py`、`test_inline_skills.py`、`test_desktop_service.py`、`test_desktop_conversations.py` 對 `session.citation_service`／`session._citation_service` 的存取與注入 | 只為測試存在的 `citation_service` 屬性與 `_citation_service` setter（S041 已刪除） | 改透過 `_fixture_services`（monkeypatch `CitationService`／`get_provider_hub`）與 `session._citation_policy.service`／`loaded_service` 驗證相同的生命週期與清理行為 |

## Grep 與測試結果

- `grep -rn --include="*.py" -E '\b(rewrite_prompt|review_draft|aggregate_candidates|parse_reviser_output|citation_service|_citation_service|set_loaded_service)\b|ChatSession\.restore' agent skills rag tests`：0 筆。
- `grep -rn --include="*.py" -E '\binvoke_text\b' agent skills rag tests`：僅剩 `agent/thinking/__init__.py` 的 `invoke_text_messages as invoke_text` 別名與 `tests/test_text_normalization.py` 對該別名的測試。
- 13 個受影響 pytest 模組：`359 passed in 13.43s`。
