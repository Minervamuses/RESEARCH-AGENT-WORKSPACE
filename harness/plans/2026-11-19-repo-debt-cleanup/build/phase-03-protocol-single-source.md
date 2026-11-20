# C3 — 協定單一來源（U1、U16）

- **完成後的狀態**：
  - `contract.json` 是唯一手寫的協定詞彙與 schema。
  - TS 在建置與測試時直接讀它，只驗 request 參數與回聲。
  - TS 的 result 與 event DTO 若與 contract 不一致，`npm test` 失敗（U16）。
  - Rust 只驗框架。
  - Python 每則送出的訊息只驗一次。
  - 每個 result 只經由 invoke 回傳一次。
- **涵蓋**：G1、G7（缺陷 #4）、G8（S003–S005、S071 一部分、S072、S085）
- **相依**：C1。需要 `evidence/C1-S4/probes.md`。
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 U1、U16、A2、A6。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S001–S005、S011、S012、S071、S072、S085、S090。

## U1 之後各端的責任

| 端 | 保留 | 移除 |
|---|---|---|
| Python（`agent/desktop/protocol.py`） | • 讀 contract。<br>• 驗證收到的 request 與送出的 result、event，送出時只驗一次。<br>• 禁止鍵掃描。<br>• 錯誤碼對照。<br>• 錯誤出口的遮蔽（C2-S11）。 | • encode 路徑上重複的 `validate_message`（S005）。<br>• production 的 `TraceValidator`：移到測試當 oracle，或刪除（S011）。 |
| TS（`protocol.ts`、`backend.ts`） | • 從 contract 取得常數、方法、event、錯誤碼與參數 schema。<br>• 用既有的泛用欄位規則解譯器（`protocol.ts` 約 1667–1778 行）驗證送出的 request 參數。<br>• 解析 envelope（type、`ok`、錯誤碼是否在 contract 內）。<br>• 回聲比對（見下方「回聲比對規則」）。<br>• 手寫的 DTO interface，只當型別；由 U16 的檢查與 contract 綁在一起。 | • 所有手抄的字面量表與 `*_SCHEMA`。<br>• result 與 event data 的逐欄位驗證，包括 `validateResultData` 及其重複呼叫（S004）。<br>• `ProtocolTraceValidator`，改成直接的回聲比對（S011）。<br>• 對 Rust snapshot 的逐鍵驗證（S090）。<br>• 只給測試用的匯出（S072）。<br>• parity 測試。<br>• grep 原始碼的退役測試（S085）。<br>• 兩個死 DTO（S071）。 |
| Rust（`protocol.rs`、`backend.rs`） | • JSON 解析。<br>• 行長上限，以及 `session.turn`、`session.transcript` 大 result 的豁免（依 pending request 的 method 判斷）。<br>• envelope 形狀：`protocolVersion`、`type`、`requestId` 格式、`sequence` 為整數、`ok`／`error` 形狀。<br>• process event 來源檢查。<br>• `validate_safe_data` 禁止鍵掃描。 | • `required_params`、`allowed_params`、`validate_params`。<br>• `validate_event_data`、`validate_result_data`、bibliography 與 document 的語意副本。<br>• `ProtocolTraceValidator`、`RequestTraceState`、`PROTOCOL_METHODS`。<br>• 只為守住手抄本存在的 manifest 與 shared fixture 測試。<br>• result 的第二次送出（S003）。 |

### 回聲比對規則

回聲比對是既有的最小關聯檢查（GOALS「必須保留的不變量」），守的是支援的循序使用：已結束的操作晚到的回應不可被套用到目前的畫面。

- 一律比對 `requestId`。
- ID 欄位（`projectId`、`sessionId`、`turnId`）只在兩個條件都成立時才比對：
  1. 同一方法的 request 參數與 result schema 都有這個欄位。這份清單要從 contract 推導，不可手寫。
  2. **這次 request 實際帶了這個欄位。**
  例如 `session.create` 的 `projectId` 是選填，沒帶時後端會補上目前的專案再回傳（`service.py` 約 1635 行），這時不比對。若 result 中該欄位是選填而回應沒帶，也不比對。
- 依 `3b6cfd8` 的 contract，`document.apply` 與 `approval.resolve` 的 request 帶 `turnId`，但成功回應沒有這個欄位。若一律比對，文件已寫入或核准已生效，畫面卻會報錯。
- **失敗回應也要比對**：`session.turn` 與 `extensions.apply` 失敗時，回合 ID 放在 `error.details.turnId`。現行 `protocol.ts` 約 2314–2318 行會比對它與 request 的 `turnId`。移除舊驗證器時要保留這項比對，可以從 contract 的 `turnErrorDetailsSchema` 適用的方法推導，或沿用現行的方法判斷。
- 撰寫時從 contract 推導出的需比對組合如下（C4、C6 之後依新的 contract 重新推導）：
  - `session.create`、`session.list`：`projectId`
  - `session.select`、`session.delete`、`session.rename`、`session.transcript`：`projectId`、`sessionId`
  - `session.turn`：`turnId`
  - `session.stop`：`sessionId`、`turnId`
  - `extensions.apply`：`turnId`

### DTO 一致性檢查（U16）

問題：U1 拿掉 TS 的逐欄位驗證之後，若 Python 改了 contract 的欄位，TS 手寫的 DTO 不會跟著改，畫面讀到 `undefined`，而測試仍然通過。

做法：

- 在 `protocol.ts` 定義兩個型別對照：`MethodResults`（方法名稱 → result DTO）與 `EventData`（request event 名稱 → data DTO）。這是之後 `api.ts`（C8-S3）與 event listener 實際使用的對照，不是只為測試存在的清單。
- 新增 `app/desktop/tests/protocol_types.test.ts`。它用已安裝的 `typescript` 套件的 compiler API，以 `tsconfig.json` 的設定對 `src/protocol.ts` 建立 Program，取得上述兩個對照中每個 DTO 的屬性，與 `contract.json` 的對應 schema 比對。
- 比對規則：
  - **涵蓋**：每個有 `resultDataSchemas` 的方法都在 `MethodResults` 中，每個有 `eventDataSchemas` 的 request event 都在 `EventData` 中；反之亦然。沒有 result schema 的方法在測試中逐一列出。
  - **欄位名稱**：DTO 的屬性集合（含 `extends` 繼承來的）等於 schema 的欄位集合。
  - **必填**：`required: true` ⇔ 屬性不是選填。
  - **可為 null**：`nullableString`、`nullableBoolean`、`nullableSubmittedContext` ⇔ 型別包含 `null`。
  - **列舉**：schema 有 `enum` ⇔ DTO 的型別剛好是這些字串字面值的聯集（可為 null 時另加 `null`）。
  - **基本型別**：`string`、`turnId`、`requestId`、`utcTimestamp` 對 `string`（或字面值聯集）；`integer` 對 `number`；`boolean` 對 `boolean`；`stringArray` 對 `string[]` 或 `readonly string[]`。
  - **巢狀**：`object`、`objectArray`、`submittedContext` 遞迴比對（`submittedContext` 對 contract 的 `submittedContextSchema`）。
  - **例外**：只能寫在測試檔內一個具名清單，每項附理由。預期為空。
- request 參數的對照（`MethodParams`）在 C8-S3 建立 `api.ts` 時加入，沿用同一個比對函式。
- 不從 contract 產生 TS 型別副本；不新增套件。若 GOALS A6 不成立，改用 A6 的備案（`npm run build` 執行的 Node 腳本），規則不變。

Rust 需要的框架常數有兩種取法：

- **優先**：以 `include_str!("../../protocol/v1/contract.json")` 在第一次使用時用 serde_json 解析取得。改用這種方式時，`main.py` 的監看路徑要加入 `app/desktop/protocol/`。
- **備案**：若錯誤處理因此變得複雜，保留約十個常數，並加一個與 contract 比對的單一測試。

選了哪一種要記錄在 build-log。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C3-S1 | **決定 TS 讀取 contract 的寫法（探索）。** 依序嘗試：<br>(a) `import contract from "../protocol/v1/contract.json" with { type: "json" };`<br>(b) 不帶 import attribute 的 `resolveJsonModule` 寫法。<br>在 `src/` 一個暫時的小改動中，分別執行 `npm run build`（`tsc` 加 Vite）與 `npm test`。<br>出口有三種：<br>• 同一寫法三者都接受：採用它。<br>• Node 測試不接受但 `tsc` 與 Vite 接受：讓 `tests/protocol.test.ts` 等直接匯入 `protocol.ts` 的測試，改用其他 5 個測試檔已在用的 Vite SSR 載入方式。<br>• 兩種寫法都被 `tsc` 拒絕：標為 Blocked 並回報。<br>任何情況都**不可**產生第二份 TS 副本（codegen）。<br>結論寫入 `evidence/C3-S1/decision.md`，暫時改動不提交。 | 決策檔記錄三個工具在各寫法下的實際輸出。 |
| C3-S2 | **TS 改讀 contract。** 依 C3-S1 的寫法：<br>• 以 contract 取代 `protocol.ts` 的手抄常數與 schema。<br>• request 參數驗證改由解譯器讀 contract 的 `methods[].params`，必填資訊取自 `params[].required`。<br>• 移除上表 TS「移除」欄的項目。<br>• `backend.ts` 只保留 envelope 解析與回聲比對。<br>• 先盤點 production 中哪些地方會捕捉「result 驗證失敗」的 `ProtocolContractError`，記入 evidence。U1 之後這些路徑已不可能發生，因為 Python 送出前已驗證；直接移除，不另造替代檢查。<br>• `conversations.ts` 這類「應用層解析」（例如判斷 `streamKind`）不在本步範圍，留到 C4。 | • `npm test`、`npm run build` 通過。<br>• `protocol.ts` 匯出的每個詞彙常數（版本、行長與 id 上限、方法、event、process event、錯誤碼、禁止鍵片段、大 result 方法）的定義式都引用 `contract`，不是字面量：逐一列出定義行存證。<br>• 一個測試斷言這些常數等於從 `contract.json` 直接讀出的值，放在 `protocol.test.ts`。這不是 parity 測試，因為兩邊來自同一份檔案；它只防止有人改回字面量。<br>• 方法名稱字串只出現在型別對照或呼叫端：以 grep 找出 `src/protocol.ts` 中所有 `"<前綴>.<名稱>"` 形式的字串（前綴取 contract 方法名稱中的 `session`、`document`、`bibliography`、`knowledge`、`extensions`、`runtime`、`project`、`workspace`、`approval`），每一行在 evidence 標明用途，不可有 runtime 陣列或物件字面量列出它們。<br>• 舊的 parity 測試已刪。<br>• 缺少必填參數的 request 在送出前被 TS 拒絕（既有或改寫的測試）。<br>• 回聲測試（既有或改寫）：<br>(a) `document.apply` 與 `approval.resolve` 的 request 帶 `turnId`、成功回應沒有 `turnId` 時，被接受；<br>(b) `session.stop` 回應的 `turnId` 與 request 不同時，被拒絕；<br>(c) `session.select` 回應的 `sessionId` 不同時，被拒絕；<br>(d) `session.create` 沒帶 `projectId`、回應帶後端補上的 `projectId` 時，被接受；有帶而回應不同時，被拒絕；<br>(e) `session.turn` 與 `extensions.apply` 的失敗回應中，`error.details.turnId` 與 request 不同時被拒絕、相同時被接受。沿用 `protocol.test.ts` 與 `fixtures.json` 現有的錯誤 ID 案例；改寫時保留它們涵蓋的情況，並寫退役紀錄。 |
| C3-S3 | **U16：DTO 一致性檢查。** 依上方「DTO 一致性檢查」：<br>• 在 `protocol.ts` 定義 `MethodResults` 與 `EventData`。<br>• 寫 `tests/protocol_types.test.ts`。比對函式本身另有單元測試：以 compiler host 載入一段記憶體中的小型 TS 原始碼，對一份小 schema 比對。<br>• 先讓它對目前的 contract 與 DTO 跑一次。找到的每個不一致，依 contract 修正 DTO（contract 是事實來源），在 evidence 逐項列出。若某個不一致顯示是 Python 端的錯誤，記錄並回報，不在本步改 Python。 | • `npm test`、`npm run build` 通過。<br>• 比對函式的單元測試涵蓋並能偵測：少一個欄位、多一個欄位、必填與選填不符、少了 `null`、列舉成員不同、巢狀物件內的欄位不同。<br>• 對真實檔案的負向演練：暫時把 contract 某個 result 欄位改名，`npm test` 失敗並指出方法與欄位；暫時把某個 DTO 的必填屬性改成選填，同樣失敗。兩者都還原，輸出寫入 evidence。<br>• 例外清單為空，或每項有理由。<br>• 測試耗時寫入 evidence。 |
| C3-S4 | **Rust 只驗框架，result 只送一次（S002、S003、S011 Rust 部分）。**<br>• 依上表縮減 `protocol.rs`，`backend.rs` 改呼叫縮減後的介面。<br>• 刪掉 `backend.rs:1545-1546` 的 `emit_protocol(..., value.clone())`，result 只經 `sender.send(Ok(value))` 回傳；同時移除 `:1532` 的 `validate_result_data`。<br>• 調整依賴雙重送出或逐方法驗證的 Rust 測試，例如 `readiness_request_event_result_and_graceful_shutdown`。<br>• `backend.rs` 約 1914 行以 `knowledge.overview` 當範例 request，改成一個 C4 後仍存在的方法，例如 `runtime.diagnostics`。<br>• 框架常數的取法見上方說明。 | • `cargo test --locked`（沙箱外）通過。<br>• `npm test` 通過，`backend.test.ts` 不依賴 result event。<br>• grep `validate_result_data\|validate_params\|ProtocolTraceValidator\|PROTOCOL_METHODS` 在 `src-tauri/src` 為 0。<br>• 一則超過行長上限的非豁免 result 仍被 Rust 拒絕；一則含禁止鍵的 event 仍被 Rust 拒絕。兩者都要有測試（保留既有的，或改寫）。<br>• 新的或改寫的 Rust 測試：一個 request 得到 result 時，WebView 的 protocol event 通道只收到該 request 的 event（若有），沒有收到 result 本身；result 只出現在 invoke 回傳值中，而且只出現一次。 |
| C3-S5 | **Python 與 fixtures（S005、S011 Python 部分、S012）。**<br>• encode 路徑每則訊息只驗一次。<br>• `TraceValidator` 若仍被 fixture 測試當 oracle 使用，就移到 `app/tests/` 下，例如 `tests/protocol_trace_oracle.py`，否則刪除。<br>• 刪掉 `test_desktop_protocol_contract.py` 中寫死的 result schema 名稱集合（約 28 個）、重複的 bash-permission fixtures，以及歷史測試 `test_phase04_…v1_additions`。<br>• fixtures 只由 Python（與 TS 的 request 驗證）執行。<br>• 在 contract 旁或測試模組的 docstring 寫下「每個方法至少一個合法例與一個非法例」的約定。位置選既有的說明處，不新增說明文件。 | • `pytest tests/test_desktop_protocol_contract.py tests/test_desktop_server.py -q` 通過。<br>• 每個方法仍至少有一個合法 fixture 與一個非法 fixture；以一段小腳本統計，輸出存證。 |
| C3-S6 | **階段收尾與「新增一個方法」走查。**<br>• 完整 pytest（沙箱外）、`npm test`、`npm run build`、`cargo test --locked`（沙箱外）。<br>• 走查：以 `session.rename` 為例，grep 它出現的所有檔案，分類成「必須手改」與「測試或 fixture」，寫入 `evidence/C3-S6/add-method-walkthrough.md`。<br>• 量測 `protocol.ts`、`protocol.rs`、`protocol.py`、`fixtures.json` 的行數。 | • 四套都通過。<br>• 走查中必須手改的地方只剩：`contract.json`、Python handler 與 dispatch、TS DTO 與 `MethodResults` 的一列、呼叫端；其餘只是 fixtures 與測試。<br>• 若還有其他必須手改的地方，記錄原因並判斷是否屬於本階段範圍；屬於就修正。 |

## 驗收

- 上方責任表中的「移除」欄都已移除，「保留」欄的行為有測試覆蓋。
- DTO 一致性檢查存在、對目前檔案通過，負向演練確認它會失敗。
- 四套檢查都在最後狀態上通過。
- 走查結果符合 G1。

## 失敗與續作

- C3-S2 與 C3-S4 可能讓 TS 與 Rust 暫時不相容。每一步都要讓 `npm test` 與 `cargo test` 各自通過才 commit。
- 若某一步無法讓兩端同時通過，就以 `[C3-Sm checkpoint]` 保存證據，並標記阻塞。
- C3-S3 若因 compiler API 無法使用而受阻，改用 GOALS A6 的備案，不可略過 U16。

## 交給後續階段

C4、C5、C6 修改協定時，只需改：

- `contract.json`；
- Python；
- TS 的 DTO、型別對照與呼叫端；
- fixtures。

漏改 DTO 時 `npm test` 會失敗。Rust 不再需要隨詞彙變動而修改。
