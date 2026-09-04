# GUI 第一回合 Sidebar 與內容耐久保存不一致（已解決）

## Issue 定位

- 類型：Conversation catalog 與 transcript persistence 的生命週期不一致。
- 優先度：原為已知資料恢復風險；專案擁有者於2026-08-31決定延後，之後納入canonical lifecycle改造。
- 狀態：Resolved（canonical lifecycle，2026-09-05）。
- 現行邊界：canonical JSON是唯一active transcript authority，`ConversationRepository`是唯一writer；catalog registration在prompt已durable後發生。

## 歷史問題描述

以下描述保留2026-08-31記錄當時的舊行為，不再是現行實作。

第一個 normal 問答完成後，舊系統會把「這個對話屬於哪個 project」立即寫進 `desktop-projects.json`。因此 sidebar 可以立刻列出這個對話。

當時真正的問題與回答走另一條保存路徑。它們先放在 Python backend 的 recent-turn 記憶體清單中；預設清單保留 10 回合。只有舊回合超出這個窗口、使用者切換對話而觸發 flush，或 backend 正常 shutdown 時，這些 recent turns 才寫進可供日後恢復的 history store。

因此，sidebar 宣稱「這個對話已存在」與「這個對話的文字已經能抵抗 process crash」不是同一件事。第一回合後若一直留在同一對話，兩者不一致的期間可以持續很久，而不只是幾毫秒的 race window。

## 當時已確認與尚未確認

### 舊source已直接確認

- `TurnJournal.record_turn()` 先把 finalized normal turn 加進記憶體中的 `recent_turns`，只有窗口溢出時才呼叫 long-term store。
- `agent_recent_turns_window` 預設為 10。
- Desktop 在 `session.turn_outcome()` 完成後便 durable-register catalog entry；它沒有先 flush 該第一回合。
- Conversation switch 與正常 shutdown 會明確呼叫 `flush_recent_turns()`。
- 選取 catalog 中的對話時，如果讀不到任何可恢復 transcript，Desktop 會以 `SESSION_NOT_READY` 拒絕開啟。

### 當時尚未實際重現

當時尚未執行「第一回合已完成且 catalog 已註冊、recent turn 尚未 flush 時，直接異常終止真實 Python backend」的 deterministic boundary test。因此：

- 寫入順序與未耐久窗口是已確認事實。
- SIGKILL 後 sidebar 留下不可恢復 entry 的完整使用者旅程仍是待重現結果，不能冒充已發生事故。

## 當時可能的使用者影響

在上述窗口中若 backend crash、被強制終止或整台機器突然關機，可能發生：

1. Sidebar 重啟後仍列出該 conversation。
2. 第一個問題與回答沒有進入 history store。
3. 使用者點擊該 conversation 時，系統找不到可恢復 transcript 並拒絕開啟。

## 當時的使用者決定

> 「在 fix_plans 裡面紀錄這件事我決定保留，本次不修正，之後再處理。」

這項決定在當時代表延後，而不是把風險判定為不存在。後續canonical lifecycle工作已處理這個生命週期缺口；原決策來源仍保留於[`harness/fix_plans/user-decisions.md`](../harness/fix_plans/user-decisions.md)。

## 現行修正

1. Accepted prompt先以temporary file、file fsync、atomic replace與directory fsync成為canonical pending turn，之後才進入provider／tool執行。
2. Desktop在pending已提交後才註冊catalog；若catalog write落後，正常catalog reconciliation會從有效canonical JSON補回，不需要另一份transcript store。
3. Safety／citation finalization完成後，answer才轉成canonical completed；completed寫入成功後才可交付terminal success。
4. 重啟時遺留pending會成為interrupted，不自動重播provider／tool；只有相同logical turn ID的明確retry才重新執行。Completed commit若早於response delivery，重送同ID只回復已存結果。
5. Normal新回合、latest-10 context與exact-text lookup只使用canonical JSON；`recall_history`與active conversation Chroma runtime已移除。

## 已有驗證證據

- `app/tests/test_desktop_conversations.py`直接驗證第一個prompt在provider failure前已是pending且catalog owner已註冊，也驗證A→B→A不依賴flush。
- `app/tests/test_desktop_crash_recovery.py`用真實`python -m agent.desktop.server`子程序，在六個durability checkpoint等待fsync marker後SIGKILL，再以同一隔離root重啟；覆蓋pending→interrupted不自動重播、tool side effect不重複、completed commit後同ID回復既有answer等邊界。
- `app/tests/test_session_lifecycle.py`與`app/tests/test_conversation_repository.py`覆蓋重啟恢復、explicit retry與latest-10 completed／eligible context。
- `app/tests/test_history_retirement.py`與`app/tests/test_conversation_archive_access.py`驗證`recall_history`已移除，canonical exact grep/read-file workflow不fallback到RAG。

這些是isolated fixture／fake external owners與本機subprocess證據。尚未執行真實使用者資料migration、live provider或Ollama，也不把尚待完成的native Tauri人工journey宣稱為已驗收；因此本issue的canonical lifecycle缺口已解決，不代表Phase 07或整體計畫已完成。

## 主要參考檔案

- `app/agent/config.py`
- `app/agent/conversations/repository.py`
- `app/agent/session.py`
- `app/agent/desktop/catalog.py`
- `app/agent/desktop/service.py`
- `app/tests/test_desktop_conversations.py`
- `app/tests/test_desktop_crash_recovery.py`
- `app/tests/test_session_lifecycle.py`
