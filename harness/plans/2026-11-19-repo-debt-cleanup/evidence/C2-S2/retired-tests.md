# C2-S2 驗證與測試改寫紀錄（S040）

- **日期**：2026-11-21
- **涵蓋項目**：S040（移除 `ChatSession.activate_citation_skill` 與 `deactivate_citation_skill`）

## 7 個測試檔的改寫與測試退役紀錄

未新增任何等價於 `activate_citation_skill` 的測試啟動輔助函式；所有測試皆改走單回合 `session.turn(..., skill_name="citation")`／`session.turn_outcome(..., skill_name="citation")`（含 `/citation <prompt>` 解析流程）。

| 測試檔案與位置 | 原保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `tests/test_citation_slash_command.py::StubSession` | 驗證 `/citation` 解析不會直接呼叫已刪除的 `activate_citation_skill`／`deactivate_citation_skill` | 刪除 `StubSession` 上該兩個死方法，保留 `calls == []`、`active_skill_runtime` 不變與 `skill_name == "citation"` 轉發斷言 |
| `tests/test_citation_e2e.py`（2 處） | save bundle 旅程與損毀 save receipt 拒絕 | 改以 `session.turn(..., skill_name="citation")` 執行完整單回合流程，所有斷言不變 |
| `tests/test_observability.py::test_turn_trace_links_citation_actions_queries_and_counts` | citation 搜尋動作的 `turn_trace` 雜湊與計數 | 改以 `session.turn_outcome(..., skill_name="citation", turn_id=turn_id)` 執行，所有斷言不變 |
| `tests/test_desktop_citation_keys.py::test_lookup_is_effective_in_citation_turns_only_when_offered` | 桌面提供 `bibliography_lookup` 時只在 citation 回合生效、CLI 不出現 | 改於 `session.turn(..., skill_name="citation")` 的 graph `on_state` 斷言回合期間生效、回合前後不出現 |
| `tests/test_tool_access_matrix.py`（2 處） | citation 啟用期間的工具可用性提示與 fusion proposer 唯讀交集 | 改於 `session.turn(..., skill_name="citation")` 的 graph `on_state` 擷取並驗證全部原斷言 |
| `tests/test_citation_skill_activation.py`（14 處；含 `test_tampered_applied_citation_activation_preserves_state[direct]` 參數分支退役） | SKILL.md 邊界文字、工具清單、強制 `normal` thinking、回合中拒絕切到 `extended`、回合結束清除 registry、切換其他 skill 後清除、未知 skill／無效斜線指令／遭竄改擴充套件在進 graph 前失敗且不改變既有 session 狀態。原 `[direct]` 分支專測直接呼叫已刪除的 `activate_citation_skill()` | 全部改經由 `session.turn(..., skill_name="citation")`（及 `/citation find Paper A` 斜線解析）驗證；移除只測 `activate_citation_skill()` 的 `[direct]` 分支，保留 `/citation` 正式入口的完整防竄改與無洩漏斷言 |
| `tests/test_turn_finalizer.py`（17 處） | citation 標記渲染、原始文獻格式不誤擋、save telemetry 計數、偽造 receipt 攔截與日誌不洩漏、dangling cite 阻擋、回合結束後清除來源提示 | 移除繞過回合入口的 `_finalize_pending`，改走正式 `session.turn_outcome(..., skill_name="citation")` 搭配 scripted `AstreamGraph` updates，全部斷言完整保留 |

## Grep 與測試結果

- `grep -rn --exclude-dir=__pycache__ "activate_citation_skill\|deactivate_citation_skill" app/`：0 筆。
- 7 個測試檔：`126 passed in 4.10s`。
