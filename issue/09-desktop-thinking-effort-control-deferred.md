# Desktop Thinking Effort 多段位控制（延後設計）

## Issue 定位

- 類型：Desktop session control／thinking product contract。
- 優先度：Deferred。
- 狀態：Open；目前只記錄產品意圖，不指定實作方法。
- 排序理由：段位、映射與 persistence 都尚未決定，因此放在目前 backlog 最後。

## 使用者需求

未來 GUI 應提供 Thinking Effort button，讓使用者可以用多個段位調整 thinking effort。

## 已確認的現況

- React 目前已有一個 `Thinking` select，但只有 `Normal` 與 `Extended`。
- Python `/thinking` command、session state 與 Desktop protocol enum 同樣只有 `normal`／`extended`。
- 現行 `Extended` 代表一套 prompt rewrite、reviewer／reviser 與 fusion workflow，不等同於任意 provider 的單一 reasoning-effort 參數。

## 本輪刻意不決定

依使用者指示，這份紀錄先不寫具體方法，包括：

- 有幾個段位或各段位名稱。
- 段位如何映射到 provider reasoning effort、模型選擇或現有 Extended Thinking workflow。
- 設定的 session／conversation／restart persistence。
- protocol、UI state 與測試的具體修改方式。

上述產品契約確定後，再把本 issue 改成可驗收的實作項目；在此之前不得用任意段位先行實作。

## 完成這份紀錄的條件

- 未來需要多段位 Thinking Effort button 的意圖已被保留。
- 目前沒有把未決的段位、參數映射或 persistence 寫成既定方案。
- 本輪不修改現行 `Normal`／`Extended` 行為。

## 主要參考檔案

- `app/agent/cli/slash_commands.py`
- `app/agent/session.py`
- `app/agent/llm/thinking.py`
- `app/desktop/protocol/v1/contract.json`
- `app/desktop/src/protocol.ts`
- `app/desktop/src/App.tsx`
- `app/tests/test_slash_commands.py`
- `app/tests/test_thinking_session.py`
- `app/tests/test_desktop_service.py`
- `app/desktop/tests/protocol.test.ts`
