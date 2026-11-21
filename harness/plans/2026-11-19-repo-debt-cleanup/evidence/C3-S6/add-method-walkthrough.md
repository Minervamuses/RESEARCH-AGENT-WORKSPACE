# C3-S6 階段收尾與「新增一個方法」走查

- **日期**：2026-11-22

## 1. 走查：`session.rename`

指令：`grep -rln "session\.rename" app main.py`（排除 `node_modules`、`dist`、`target`、`__pycache__`、`store`）。

| 檔案 | 位置 | 分類 |
|---|---|---|
| `app/desktop/protocol/v1/contract.json` | method 定義與 `resultDataSchemas` | **必須手改**：contract |
| `app/agent/desktop/service.py` | dispatch 表 `"session.rename": self._session_rename` 與 handler | **必須手改**：Python handler 與 dispatch |
| `app/desktop/src/protocol.ts` | `MethodResults` 的一列 `"session.rename": SessionRenamedDto`（加上 DTO `SessionRenamedDto`） | **必須手改**：TS DTO 與 `MethodResults` 的一列 |
| `app/desktop/src/App.tsx` | `backendClient.request("session.rename", …)` | **必須手改**：呼叫端 |
| `app/desktop/protocol/v1/fixtures.json` | 3 個 request fixtures | fixtures |
| `app/desktop/tests/protocol.test.ts` | 回聲欄位推導與缺必填參數測試 | 測試 |
| `app/tests/test_desktop_conversations.py` | rename 的服務測試 | 測試 |

Rust 與 `backend.ts` 不需要修改。

**走查中發現並修正的一處**：第一次走查時，`protocol.ts` 還有 `ProtocolMethod` 型別聯集中的一行 `| "session.rename"`，是步驟規格清單以外的手改處，屬於本階段範圍。已改為：

```ts
export type ProtocolMethod = keyof MethodResults | MethodWithoutResultDto;
export type RequestEvent = keyof EventData | RequestEventWithoutDataDto;
```

`MethodWithoutResultDto` 只列沒有 result DTO 的方法（目前 12 個沒有 result schema 的方法，加上 C4 會移除的 `session.shutdown`、`extensions.status` 兩個例外）。新增一個有 result 的方法時，只需要 `MethodResults` 的一列；`tests/protocol_types.test.ts` 仍斷言 `ProtocolMethod`、`RequestEvent` 等於 contract 的清單。修正後 `grep -n "session\.rename" app/desktop/src/protocol.ts` 只剩 `MethodResults` 那一列。

結論：必須手改的地方只剩 contract、Python handler 與 dispatch、TS DTO 與 `MethodResults` 的一列、呼叫端，其餘是 fixtures 與測試，符合 G1。

## 2. 行數

| 檔案 | C3 前（PLANS 基線） | C3 後 |
|---|---:|---:|
| `app/desktop/src/protocol.ts` | 2,333 | 1094 |
| `app/desktop/src-tauri/src/protocol.rs` | 3,638 | 616 |
| `app/agent/desktop/protocol.py` | 760 | 699 |
| `app/desktop/protocol/v1/fixtures.json` | 5,194 | 5,301 |

`fixtures.json` 增加來自 C3-S5 補上的 8 個 request fixtures（每個方法至少一個合法與一個非法例）。

## 3. 完整檢查（最後程式狀態）

| 檢查 | 結果 |
|---|---|
| `pytest`（`app/`，沙箱外） | 1816 passed, 2 warnings in 53.75 s |
| `npm test` | 228 pass, 0 fail |
| `npm run build` | 通過 |
| `cargo test --locked`（沙箱外，Conda `app`） | 35 passed, 0 failed |

走查修正（只改 `protocol.ts` 的型別別名）之後重跑 `npx tsc --noEmit`、`npm test`（228 pass）與 `npm run build`（通過）；Python 與 Rust 未受影響。
