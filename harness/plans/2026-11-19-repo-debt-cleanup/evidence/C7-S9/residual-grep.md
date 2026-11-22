# C7-S9 階段收尾：殘留 grep 與 C7 驗收

- **日期**：2026-11-22，程式狀態 `4fb187e`（之後只有 evidence commit）。
- **完整 pytest（沙箱外）**：1827 passed（C7-S8 最後一次全跑，與目前程式相同）。

## grep 原始輸出

```
$ grep -rn "RESEARCH_AGENT_DESKTOP_FIXTURE\|fixture_session" agent
$ grep -rn "inspect.signature\|_session_factory_accepts_bash" agent/desktop
$ grep -rnE "session\._[a-z]" agent/thinking/
$ grep -rn 'session\._[a-z]' agent/desktop/ | grep -v 'self\._session\b'
$ grep -rn '\(getattr\|hasattr\|setattr\)([^)]*"_[a-z]' agent/desktop/ agent/thinking/
agent/desktop/server.py:317:                lifecycle = getattr(self._service, "_with_turn_lifecycle", None)
$ grep -rnE "bypass_approval|_document_turn_active" agent/desktop/
$ grep -rnE "(10 old turn field names)" agent/desktop/
$ grep -rn "set_thinking_mode" agent/desktop/
agent/desktop/conversation_ops.py:136:                target.set_thinking_mode(control_snapshot.thinking_mode)
agent/desktop/conversation_ops.py:419:        session.set_thinking_mode(params["mode"])
$ grep -n "<raw busy conditions>" agent/desktop/*.py
agent/desktop/service.py:413:        return self._turn_active or self._pending_approval is not None
agent/desktop/service.py:417:        return self._document_apply_lock.locked() or self._document_tool_lock.locked()
```

## 判讀

| 檢查 | 結果 |
|---|---|
| fixture 開關（C7-S1） | 0 |
| `inspect.signature`、`_session_factory_accepts_bash`（C7-S2） | 0 |
| `agent/thinking/` 的 `session._x`（C7-S3） | 0 |
| `agent/desktop/` 的 `session._x`（C7-S4；C7-S4 暫留的兩處已由 C7-S5 移除） | 0 |
| 字串形式的私有存取 | 只剩 `server.py:317` 的 `getattr(self._service, "_with_turn_lifecycle", None)`：存取的是 `DesktopService`（現在定義在 `errors._ErrorMapping`），不是 `ChatSession` |
| `bypass_approval`、`_document_turn_active`（C7-S5） | 0 |
| C7-S5 的 10 個回合欄位舊名 | 0；每回合值只在 `_TurnWork` 的定義與經 `_running_turn` 的讀取處 |
| `set_thinking_mode` | 只有選取對話時套用控制快照，與 `session.set_thinking` 的處理 |
| C7-S6 重複的忙碌條件 | 只剩兩個共用查詢的定義；行為由 62 個參數化案例覆蓋；沒有要求全部 flag 轉由新物件持有 |

## C7 驗收（phase-07「完成後的狀態」）

| 狀態 | 證據 |
|---|---|
| fixture 在 `app/tests/support/`，`server.py` 沒有開關 | C7-S1 |
| 假物件集中，production 不再探測參數 | C7-S2 |
| `ChatSession` 有公開介面，desktop 與 thinking 不再碰私有屬性 | C7-S3、C7-S4、上表 |
| 每回合設定以參數傳入，回合之間不汙染 | C7-S5 與回歸測試 (a)(b)(c) |
| 8 處忙碌判斷的重複條件共用，行為不變 | C7-S6 |
| Retry Stop 可以恢復 | C7-S7 |
| `service.py` 依職責拆成模組 | C7-S8 |
