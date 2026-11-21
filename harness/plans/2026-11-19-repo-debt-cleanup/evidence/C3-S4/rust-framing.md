# C3-S4 Rust 只驗框架，result 只送一次（S002、S003、S011 Rust 部分）

- **日期**：2026-11-22
- **規模**：`src-tauri/src/protocol.rs` 3,638 → 616 行（含測試）；`backend.rs` 2,497 → 2,507 行（測試增加）。

## 1. 框架常數的取法（記錄在 build-log）

採 **優先方案**：`include_str!("../../protocol/v1/contract.json")`，第一次使用時以 serde 反序列化成 `Framework`（`protocolVersion`、`maxLineBytes`、`requestIdMaxBytes`、`errorMessageMaxBytes`、`fullTextResultMethods`、`processEvents`、`processEventOrigins`、`forbiddenDataKeyFragments`），存在 `OnceLock`。contract 是編進 binary 的檔案，解析失敗只會在開發時發生，以 `expect` 處理即可，錯誤處理沒有變複雜，所以不需要備案。

連帶修改：repo 根目錄 `main.py` 的 release 重建輸入加入 `protocol`（`app/desktop/protocol/`）。C3-S2 起 TS 也 import 這份 contract，所以兩端都需要。`tests/test_desktop_launcher.py` 的 fixture 同步加入該目錄，並新增「contract 修改會讓 release 過期」的測試。

## 2. 保留與移除

| 保留（框架） | 移除 |
|---|---|
| JSON 解析；行長上限與 `session.turn`／`session.transcript` 大 result 豁免（依 pending request 的 method）；envelope 形狀（`protocolVersion`、`messageType`、`requestId` 格式、request event 的 `sequence` 為正整數、`ok`／`error` 形狀、error message 長度）；process event 名稱與來源檢查；`validate_safe_data` 禁止鍵掃描；`backend.rs` 的 pending request 關聯與 event 連號。 | `required_params`、`allowed_params`、`validate_params`；`validate_event_data`、`validate_tool_event`、`validate_result_data`、bibliography／document／submitted context／skill reference 的語意副本；`ProtocolTraceValidator`、`RequestTraceState`、`PROTOCOL_METHODS`、`REQUEST_EVENTS`、`PROTOCOL_ERROR_CODES`；只給測試的 `parse_protocol_line(_from_origin)`；`backend.rs` 中 result 的第二次送出（`emit_protocol(..., value.clone())`）與 `validate_result_data` 呼叫。 |

`grep -rn "validate_result_data\|validate_params\|ProtocolTraceValidator\|PROTOCOL_METHODS" app/desktop/src-tauri/src`：0 筆。

`backend.rs` 測試的範例 request 從 `knowledge.overview` 改為 `runtime.diagnostics`。

## 3. 必要檢查對應的測試

| 檢查 | 測試 |
|---|---|
| 超過行長上限的非豁免 result 被拒絕 | `malformed_oversized_and_wrong_id_output_fail_the_pending_request` 新增 `oversized_success` 模式（`runtime.diagnostics` 的成功 result 超過 2 MiB）；既有 `oversized_non_success_stdout_fails_at_the_bounded_framing_limit`（event、failure、無換行、非 JSON）保留。 |
| 含禁止鍵的 event 被拒絕 | `protocol::tests::forbidden_keys_are_rejected_in_events_results_and_error_details`（request event、process event、result data、error details）；端到端：同一個 backend 測試新增 `forbidden_event` 模式。 |
| result 不經 protocol event 通道、只經 invoke 回傳一次 | `readiness_request_event_result_and_graceful_shutdown` 改寫：該 request 在 event 通道只收到 1 則訊息（`request.started`），event 通道沒有任何 `messageType == "result"`；result 由 `request()` 回傳（`requestId` 與 `messageType` 斷言）。invoke 的回傳值經單一 `sync_channel(1)` 的一次 `send`。`progressing_request_can_outlive_the_prior_absolute_deadline` 的順序斷言改為只有三個 event。 |
| 大 result 豁免仍有效 | `complete_large_turn_crosses_python_stdout_without_truncation`、`complete_large_transcript_crosses_python_stdout_without_truncation` 保留並通過。 |
| 框架值來自 contract | `protocol::tests::framework_values_come_from_the_compiled_contract`。 |
| 不再逐方法驗證 request | `protocol::tests::requests_are_framed_without_per_method_param_rules`（`session.turn` 帶 `{}` 通過框架；非 canonical requestId、params 非物件、多餘欄位仍拒絕）。 |
| envelope 規則 | `protocol::tests::envelope_shape_version_and_sequence_are_checked`。 |

## 4. 測試退役紀錄

| 被刪的測試 | 它保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `manifest_matches_rust_constants` | Rust 手抄常數等於 contract（手抄本已刪） | `framework_values_come_from_the_compiled_contract`（同一份檔案編進 binary）。 |
| `rust_request_param_rules_match_manifest`、`rust_event_data_rules_match_manifest`、`rust_result_data_rules_match_manifest` | Rust 逐方法規則與 contract 一致（逐方法規則已刪，U1） | Python `test_desktop_protocol_contract.py` 的 contract 與 fixture 測試；TS request 驗證與 U16 檢查。 |
| `shared_message_fixtures` | Rust 逐方法驗證全部 message fixtures（U1 刪除） | Python 執行全部 message fixtures；Rust 保留的 envelope 與禁止鍵規則由上表的聚焦測試覆蓋。 |
| `shared_raw_lines_and_size_limit` | 只給測試的 `parse_protocol_line`（S011） | Python `rawLines`；Rust production 的行長框架測試 `ordinary_no_newline_input_stops_after_the_bounded_prefix`、`oversized_non_success_stdout_…`、`malformed_oversized_and_wrong_id_…`（含 `malformed`、`oversized`、`oversized_success`）。 |
| `shared_ordering_and_correlation_traces`、`logical_turn_id_must_match_across_a_successful_trace`、`extension_apply_turn_id_must_match_across_a_successful_trace`、`extension_apply_failure_requires_exact_correlated_lifecycle` | 只給測試的 `ProtocolTraceValidator`（S011） | Python `traces` 參數化測試；TS `backend.test.ts` 的回聲測試 (b)(e) 與 `session.turn` 成功回聲；production 的 event 連號與 pending 關聯由 `handle_python_line` 執行，`progressing_request_…` 與 `malformed_oversized_and_wrong_id_…`（`wrong_id`）覆蓋。 |
| `complete_answer_and_transcript_text_have_no_capacity_rejection` | `validate_result_data` 不因大文字拒絕（函式已刪） | `complete_large_turn_…`、`complete_large_transcript_…` 端到端通過 2 MiB 以上的 result。 |
| `shared_process_event_origin_fixtures` | 保留（改用 production 的 `parse_protocol_value_from_origin`，不再經 `parse_protocol_line_from_origin`）。 | — |

## 5. 檢查結果

- `cargo test --locked --manifest-path src-tauri/Cargo.toml`（沙箱外，Conda `app`）：35 passed, 0 failed，無 warning。
- `npm test`：220 pass, 0 fail（`backend.test.ts` 不依賴 result event）。
- `pytest tests/test_desktop_launcher.py`：13 passed。

## 6. 產品邊界檢查

本步沒有新增任何檢查或協調機制，只刪除重複驗證與重複送出。
