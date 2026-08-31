# Desktop 固定 600 秒 Request Deadline 會終止長研究回合

## Issue 定位

- 類型：Long-operation supervision／liveness。
- 優先度：高。
- 狀態：Open；專案擁有者已決定取消固定十分鐘總時限（2026-08-31）。
- 範圍：一般 Desktop request；Fusion 與 Extended Thinking 的修正另行處理。

## 白話問題描述

Desktop 的 Rust supervisor 現在替一般 request 設定固定 600 秒期限。計時從 request 送出後開始，等待的是該 request 的最終成功或失敗結果。

Python backend 在這十分鐘內即使持續送出 stage、tool 或其他 progress event，也不會把期限重新起算。因為 progress event 與最終 response 走不同處理路徑；Rust 等待 final response 的 `recv_timeout()` 仍然只使用最初那一個固定期限。現行程式沒有一個會被 progress 重設的 inactivity timeout 或 heartbeat deadline。

一旦超過 600 秒，Rust 會：

1. 回報 `BACKEND_REQUEST_TIMEOUT`。
2. 將目前 backend generation 標記為 fatal／degraded。
3. 終止 Python child process。
4. 讓該 backend generation 內其他 pending requests 一併失敗。

所以這不是「十分鐘都沒有任何動靜才判定掛掉」，而是「不論是否仍有合理進度，總執行時間一到就終止」。

## 已確認的 Source 證據

- `app/desktop/src-tauri/src/backend.rs` 定義 `REQUEST_TIMEOUT = Duration::from_secs(600)`。
- `SupervisorTimeouts::default()` 把這個值套用為一般 request timeout。
- Request 送入 child 後，Rust 以單次 `receiver.recv_timeout(timeout)` 等待終端 response。
- Timeout 分支建立 `BACKEND_REQUEST_TIMEOUT`，並呼叫 `fatal_generation(..., kill=true)`。
- Progress events 不會影響這個 receiver 的 deadline；現行實作也沒有一個可由 progress 重設的 liveness heartbeat。

## 重現狀態

本輪沒有真的等待超過 600 秒，也沒有用縮短時鐘的 fake backend 跑端到端重現。上面的 timeout、fatal state 與 kill 順序是由 Rust source 直接確認的現行控制流程，不冒充已觀察到的真實長回合事故。

## 使用者決定

> 「在 fix_plans 裡面紀錄，取消十分鐘設置。然後去 issue 裡面開新檔紀錄 timeout 問題。」

修復方向因此確定為：移除一般長研究回合的固定 600 秒 absolute deadline。不能只把 600 改成 3600 或另一個任意常數，因為那只會把相同誤判延後。決策來源見 [`harness/fix_plans/user-decisions.md`](../harness/fix_plans/user-decisions.md)。

## 必須保留的邊界

- 取消固定總時限不等於所有操作永遠不能 timeout。
- Backend startup、shutdown handshake 與短 RPC 可以保留各自明確、較短的期限。
- Child process 真正退出、protocol pipe 關閉或已確定無法再完成時，supervisor 仍須失敗並清理 pending requests。
- 長回合是否存活，必須與「總共跑了多久」分開判斷。
- 本 issue 不藉 timeout 修正擴張到 Fusion 或 Extended Thinking。

## 最小重現測試方向

不需要讓測試真的等待十多分鐘。將測試用 supervisor timeout 注入為很短的值，並使用 deterministic fake backend：

1. Backend 正常 ready。
2. Fake long turn 的最終 response 刻意晚於舊的 absolute request deadline；可在途中送出 progress，表示這是一個已知仍健康的代表案例。
3. Fake turn 最後回傳成功 terminal response。
4. 驗證 supervisor 沒有只因總經過時間跨過舊界線而 kill child，且最終 response 能交付。
5. 另以 child exit／pipe close 測試證明真正 backend failure 仍會被偵測與清理。

此處的 progress 只是建立一個明顯仍健康的案例，不預先決定日後要使用 heartbeat、inactivity timeout 或其他 liveness 設計。核心驗收是不再用 request 的總經過時間當成終止長回合的充分條件。

## 驗收方向

- 一個仍健康執行的長研究回合不因經過 600 秒而被終止。
- Progress 本身不是假成功；真正失去 child／protocol 的狀況仍能明確失敗。
- Startup 與 shutdown deadlines 不因本修正被無限制放寬。
- Timeout error 不得把仍健康的 backend generation 誤標為 fatal。
- 測試不依賴 live model、付費 provider 或實際等待 600 秒。

## 主要參考檔案

- `app/desktop/src-tauri/src/backend.rs`
- `app/desktop/src-tauri/src/protocol.rs`
- `app/agent/desktop/server.py`
- `app/agent/desktop/service.py`
- `app/desktop/src-tauri/tests/`
