# C3-S5 Python 與 fixtures（S005、S011 Python 部分、S012）

- **日期**：2026-11-22

## 1. 每則送出的訊息只驗一次（S005）

| 建構函式 | 修改前 | 修改後 |
|---|---|---|
| `request_event`、`process_event`、`failure_result` | builder 內 `validate_message` 一次，`encode_message` → `_encode_message` 再 `validate_message` 一次（共 2 次） | builder 內 `validate_message` 一次；`_encode_message` 不再驗證（共 1 次） |
| `success_result` → `encode_success_result` | `validate_result_data`（含禁止鍵掃描）＋ builder 內 `validate_message`（再掃一次 data）＋ `_encode_message` 的 `validate_message`（第三次）（共 3 次） | `validate_request_id` ＋ `validate_result_data` 一次；envelope 由 builder 自己組成；encode 不再驗證（共 1 次） |

`encode_message` 的呼叫者（`server.py` 的 `ProtocolWriter.send`／`send_nowait`、`write_bootstrap_error`、`RequestContext.failure`）傳入的都是上述 builder 的輸出（以 grep 核對）。`service.py` 中 `session.turn` 在持久化前呼叫 `success_result` 的 pre-persist 檢查屬於稽核 S025，依 S005 的註記另計，本計劃不納入。

## 2. `TraceValidator`（S011 Python 部分）

仍被 `test_desktop_protocol_contract.py` 的 trace fixtures 與兩個 extension apply／turn 測試當 oracle 使用，所以從 `agent/desktop/protocol.py` 移到 `app/tests/protocol_trace_oracle.py`（內容不變，只把私有 `_invalid` 換成本地 `_reject`，並從 production 模組匯入 `validate_result_data` 與 `_validate_turn_error_details`）。production 沒有任何程式使用它（`grep -rn TraceValidator agent` 為 0）。

## 3. 測試與 fixtures（S012）

- 刪除 `test_protocol_manifest_safety_invariants` 中寫死的 28 個 result schema 名稱集合。
- 刪除歷史測試 `test_phase04_approval_correlation_and_extension_action_are_v1_additions`。
- 刪除 `test_bash_permission_mode_protocol_contract` 中與 fixtures 重複的兩個 request 驗證（合法 `bypass`、非法 mode）；result 驗證與 `session.create`／`session.select` 的 `bashPermissionMode`、`thinkingMode` 斷言沒有對應 fixture，保留。
- 約定寫在 `test_desktop_protocol_contract.py` 的模組 docstring（既有的說明處）：每個方法至少一個合法例與一個非法例；TS 只跑 request 例，Rust 只跑 process event 來源例。
- fixtures 只由 Python 完整執行；TS 只跑 request 例（C3-S2），Rust 只跑 `originCases`（C3-S4）。

### 補上的 fixtures

統計腳本（`evidence/C3-S5/fixture_coverage.py`）在修改前發現 17 個方法缺合法例或非法例。其中 12 個是 C4／C6 會移除的方法（8 個 `knowledge.*`、`session.shutdown`、`extensions.status`、`project.list`、`session.retry_registration`），不補；其餘 5 個保留的方法補上 request fixtures：

| 方法 | 新增 |
|---|---|
| `workspace.select` | `workspace-select-open-request`（合法）、`workspace-select-rejects-unknown-action`（非法） |
| `runtime.shutdown` | `runtime-shutdown-request`（合法）、`runtime-shutdown-rejects-params`（非法） |
| `document.open` | `document-open-request`（合法）、`document-open-rejects-missing-path`（非法） |
| `session.select` | `session-select-rejects-missing-session`（非法；已有合法例） |
| `session.set_thinking` | `session-set-thinking-rejects-unknown-mode`（非法；已有合法例） |

統計輸出見 `evidence/C3-S5/fixture-coverage.txt`：目前只剩上述 12 個將被移除的方法缺項。C4、C6 完成後應為 0（C10-S0 重跑）。

## 4. 測試退役紀錄

| 被刪的測試 | 它保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `test_protocol_manifest_safety_invariants` 中 28 個 result schema 名稱的集合斷言 | contract 有哪些 result schema（寫死的清單，每次增刪方法都要手改） | TS `tests/protocol_types.test.ts` 斷言 `MethodResults` 恰好涵蓋所有 result schema，且沒有 result schema 的方法逐一列出；同測試其餘的安全不變量保留。 |
| `test_phase04_approval_correlation_and_extension_action_are_v1_additions` | 歷史 v1 增補：`approval.resolve` 的 `parentRequestId`／`turnId` 參數、`session.turn.extensionAction` 列舉、extension preview binding 欄位 | fixtures `approval-resolve-by-opaque-id`、`document-approval-current-editor-context`（帶 `parentRequestId`）、`turn-completed-safe-result-dto`（`extensionAction`）、`extension-preview-safe-result-dto`（`bindingHash` 等欄位）；TS U16 檢查 `ExtensionBindingDto`、`TurnCompletedDto.extensionAction` 與 contract 一致。 |
| `test_bash_permission_mode_protocol_contract` 中兩個 request `validate_message` | `session.set_bash_permission` request 的合法與非法 mode | fixtures `session-set-bash-permission-bypass`（合法）、`session-set-bash-permission-invalid-mode`（非法），與刪除的斷言在輸入、斷言與執行環境上等價。 |

## 5. 檢查結果

- `pytest tests/test_desktop_protocol_contract.py tests/test_desktop_server.py -q`（沙箱外）：243 passed；連跑 15 次 0 失敗（期間發現並修正 C2-S11 測試的順序依賴，見 build-log C2-S11a）。
- `pytest tests/test_desktop_*.py tests/test_grill_skill.py`：513 passed。
- `npm test`：228 pass, 0 fail（新增的 8 個 request fixtures 也由 TS 執行）。
