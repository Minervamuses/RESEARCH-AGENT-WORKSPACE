# 主聊天模型固定 4,096-token 上限疑似造成回答無提示截斷

## Issue 定位

- 類型：Final answer completeness／模型輸出上限。
- 優先度：高。
- 狀態：Open；使用者已多次觀察到回答被截斷，但本輪尚未保存一個含 provider `finish_reason` 的代表案例，因此根因仍需用實際回合確認。
- 主要範圍：一般 Normal answer。Extended Thinking 或 Citation 只有在同樣症狀被重現後才納入，不先假設所有模式都有同一個原因。

## 使用者觀察

> 「現在回答長度太短，回答經常被截斷。」

實際影響是長篇回答可能在句子、段落或清單尚未完成時便結束，卻仍被當成正常 final answer 顯示與保存。使用者無法從目前 GUI 判斷這是模型自然結束、provider token 上限，還是其他 finalization／transport 問題。

## 已確認的 Source 證據

- `app/agent/config.py` 將主模型 `llm_max_tokens` 預設固定為 `4_096`。
- `app/agent/llm/openrouter.py` 會把該值直接作為 `ChatOpenRouter(max_tokens=...)` 傳給 provider。
- `finish_reason` 與輸出 token 數目前只由 `app/agent/observability.py` 寫入 redaction-safe debug summary；turn execution／finalization 不會因 `finish_reason` 表示長度耗盡而改變結果。
- Desktop 的 normal answer 採 authoritative final-only delivery；React 直接顯示 terminal `session.turn.text`，沒有已知的前端字數切片。
- Desktop protocol 對一般 frame 有 2 MiB 上限，但 `session.turn`／`session.transcript` 是保留完整文字的例外；Rust 也有 multi-megabyte response／transcript 不截斷測試，現行 answer path 沒有 answer-specific numeric bytes ceiling。現有 source 較支持「上游生成或主模型 token cap」而不是「GUI 顯示層主動裁切」，但在取得真實截斷回合的 metadata 前，這仍是最可能原因而非已證實根因。

## 期望行為

- 一般長回答不應因目前的 4,096-token 預設而經常在內容未完成時結束。
- 若 provider 因長度限制停止，系統不得把明顯未完成的文字靜默冒充成正常完整回答。
- 最終採用提高／設定輸出上限、偵測後續寫，或其他方式，應由代表案例的 `finish_reason`、token usage 與實際 final text 決定；本 issue 不先指定實作方案。
- 修正後仍維持 authoritative final-only：GUI 只顯示已完成 finalization 與 persistence 的結果，不為了繞過長度限制重新引入 provisional token streaming。

## 最小確認方式

1. 先保存一個使用者實際遇到的截斷回合，核對 model、mode、`finish_reason`、output tokens 與 final text 結尾。
2. 使用 deterministic fake model 建立「有內容但以 length／max-token 類原因停止」的回應，確認現行流程會如何標記、保存與顯示。
3. 只針對已證實的停止位置修正，避免同時改動 protocol、Markdown renderer 或 conversation persistence。

## 驗收條件

- 一個超過舊 4,096-token 邊界的代表性 Normal answer 能完整交付，或在確實無法完成時明確標示未完成，而不是無提示截斷。
- Provider 回報 length／max-token 類停止原因時，有可測試的處理行為，不只留在 debug log。
- Canonical conversation 中保存的 final text 與 GUI 顯示內容完全一致，且任何續寫都不重複或漏接文字。
- 一般短回答、tool loop、citation finalization 與既有 final-only delivery 不退化。
- 測試先使用 fake model；除非另行核准，不以大量 live provider 呼叫或付費 sweep 驗證。

## 主要參考檔案

- `app/agent/config.py`
- `app/agent/llm/openrouter.py`
- `app/agent/observability.py`
- `app/agent/turns/execution.py`
- `app/agent/session.py`
- `app/agent/desktop/service.py`
- `app/desktop/protocol/v1/contract.json`
- `app/desktop/src-tauri/src/backend.rs`
- `app/desktop/src/App.tsx`
- `app/tests/test_openrouter_model.py`
- `app/tests/test_observability.py`
