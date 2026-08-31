# GUI 第一回合 Sidebar 與內容耐久保存不一致

## Issue 定位

- 類型：Conversation catalog 與 transcript persistence 的生命週期不一致。
- 優先度：已知資料恢復風險；由專案擁有者決定延後處理。
- 狀態：Open／deferred（2026-08-31）。
- 本次處理：只留下可追蹤紀錄，不修改 persistence 實作。

## 白話問題描述

第一個 normal 問答完成後，系統會把「這個對話屬於哪個 project」立即寫進 `desktop-projects.json`。因此 sidebar 可以立刻列出這個對話。

真正的問題與回答走另一條保存路徑。它們先放在 Python backend 的 recent-turn 記憶體清單中；預設清單保留 10 回合。只有舊回合超出這個窗口、使用者切換對話而觸發 flush，或 backend 正常 shutdown 時，這些 recent turns 才寫進可供日後恢復的 history store。

因此，sidebar 宣稱「這個對話已存在」與「這個對話的文字已經能抵抗 process crash」不是同一件事。第一回合後若一直留在同一對話，兩者不一致的期間可以持續很久，而不只是幾毫秒的 race window。

## 已確認與尚未確認

### Source 已直接確認

- `TurnJournal.record_turn()` 先把 finalized normal turn 加進記憶體中的 `recent_turns`，只有窗口溢出時才呼叫 long-term store。
- `agent_recent_turns_window` 預設為 10。
- Desktop 在 `session.turn_outcome()` 完成後便 durable-register catalog entry；它沒有先 flush 該第一回合。
- Conversation switch 與正常 shutdown 會明確呼叫 `flush_recent_turns()`。
- 選取 catalog 中的對話時，如果讀不到任何可恢復 transcript，Desktop 會以 `SESSION_NOT_READY` 拒絕開啟。

### 尚未實際重現

目前尚未執行「第一回合已完成且 catalog 已註冊、recent turn 尚未 flush 時，直接異常終止真實 Python backend」的 deterministic boundary test。因此：

- 寫入順序與未耐久窗口是已確認事實。
- SIGKILL 後 sidebar 留下不可恢復 entry 的完整使用者旅程仍是待重現結果，不能冒充已發生事故。

## 可能的使用者影響

在上述窗口中若 backend crash、被強制終止或整台機器突然關機，可能發生：

1. Sidebar 重啟後仍列出該 conversation。
2. 第一個問題與回答沒有進入 history store。
3. 使用者點擊該 conversation 時，系統找不到可恢復 transcript 並拒絕開啟。

## 使用者決定

> 「在 fix_plans 裡面紀錄這件事我決定保留，本次不修正，之後再處理。」

本問題不納入目前 GUI 修復實作。這是延後，不是把風險判定為不存在或已修好。決策來源見 [`harness/fix_plans/user-decisions.md`](../harness/fix_plans/user-decisions.md)。

## 日後重新處理時的最小順序

1. 先建立 deterministic abnormal-loss boundary test，證實從第一回合完成到重啟選取的實際結果。
2. 再依測試結果選擇最小修法：第一回合 write-through、延後 catalog registration，或在 flush 完成前明確顯示 pending durability。
3. 除非測試證明現有格式無法安全修正，否則不要先建立新的 persistence framework 或 machine-readable ledger。

## 後續驗收方向

- 第一個 normal answer 回傳成功後，在尚未發生 conversation switch／正常 shutdown／window eviction 前模擬 abnormal backend loss。
- 重啟後只能出現兩種一致結果：conversation 可完整恢復，或它尚未被宣稱為已保存且不出現在 durable catalog。
- 不得保留一個使用者可見、卻沒有任何可恢復 transcript 的已保存 conversation entry。
- 測試使用本地 deterministic backend，不依賴 live provider。

## 主要參考檔案

- `app/agent/config.py`
- `app/agent/turns/journal.py`
- `app/agent/turns/store.py`
- `app/agent/desktop/catalog.py`
- `app/agent/desktop/service.py`
- `app/tests/test_desktop_conversations.py`
