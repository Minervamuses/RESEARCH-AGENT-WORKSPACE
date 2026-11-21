# C3-S3 DTO 一致性檢查（U16）

- **日期**：2026-11-22
- **檔案**：`app/desktop/tests/protocol_types.test.ts`（新增）；`src/protocol.ts` 新增 `MethodResults`、`EventData`。
- **做法**：以已安裝的 `typescript` 6.0.3 compiler API，依 `tsconfig.json` 對 `src/protocol.ts` 建立 Program，取 `MethodResults`／`EventData` 每一列 DTO 的屬性（含 `extends` 繼承），與 `contract.json` 的 `resultDataSchemas`／`eventDataSchemas` 比對欄位名稱、必填、可為 null、列舉、基本型別與巢狀物件（`submittedContext` 對 `submittedContextSchema`）。另比對 `ProtocolMethod`、`RequestEvent`、`ProcessEvent` 三個型別聯集等於 contract 的清單。不產生 TS 型別副本，不新增套件。

## 1. 比對規則中需要說明的兩點

1. **`approval.required` 有兩種線上形狀**：Python 依 operation 選用 `eventDataSchemas["approval.required"]`（指令核准）或 `documentApprovalDataSchema`（文件核准）。DTO `ApprovalRequiredDto` 是兩者的合併，所以測試以「兩個 schema 都必填才必填」合併後比對（`mergeVariantSchemas`）。這是從 contract 推導的規則，不是例外。
2. **DTO 端的 union**：`Reference` 是 discriminated union，`getPropertiesOfType` 只回傳共同屬性。比對函式把物件型別的 union 視為各變體的合併（只有部分變體有的欄位視為選填，欄位型別為各變體型別的聯集）；intersection 型別視為物件。單元測試「DTO comparator merges discriminated union variants」覆蓋這條規則。

## 2. 對目前 contract 與 DTO 的首次比對

- 比對函式修正上述兩點後，**沒有發現 DTO 與 contract 不一致**，不需要修正任何 DTO，也沒有顯示 Python 端錯誤的項目。
- `MethodResults` 需要但原本不存在的 DTO，依 contract 新增：`DocumentOpenDto`、`DocumentResultDto`、`RuntimeShutdownDto`、`BibliographySetStyleDto`、`BibliographyRemoveDto`、`TurnAcceptedDto`、`DocumentProposedDto`。bibliography 的四個既有 DTO（`citations.ts`）以 type-only import 加入對照。
- **與 C3-S2 的關係**：C3-S2 依 S071 刪除了當時 0 引用的 `DocumentOpenDto`、`DocumentResultDto`。本步把它們作為 `document.open`／`document.save`／`document.apply` 的唯一 result DTO 重新加入，同時刪除 `App.tsx` 中與 `DocumentResultDto` 重複的 `DocumentResult` interface，改用 `DocumentResultDto`（S071 的「`App.tsx` 的 `DocumentResult`」部分）。`DocumentSnapshot` 與 `DocumentContextDto` 的統一仍歸 C8。

## 3. 例外清單（測試檔內的 `DTO_EXCEPTIONS`）

都是 C4 會從 contract 移除的詞彙，C4 完成後清單應為空：

| 項目 | 理由 |
|---|---|
| `method:session.shutdown`、`method:extensions.status` | 沒有呼叫者的 RPC，C4 依 P1 移除。 |
| `event:collecting.started`、`collecting.completed`、`tagging.started`、`tagging.folder_completed`、`metadata.written`、`writing.started`、`writing.file_completed`、`ingest.completed`、`ingest.failed` | 從未發出的 request event，C4 依 U7 移除。 |

沒有 result schema 的 12 個方法在測試中逐一列出（`METHODS_WITHOUT_RESULT_SCHEMA`），並斷言它們不在 `MethodResults`。

## 4. 比對函式的單元測試

以 compiler host 載入記憶體中的小型 TS 原始碼，對一份小 schema 比對：

- 「DTO comparator accepts a matching DTO, including inherited fields and readonly arrays」
- 「DTO comparator merges discriminated union variants」
- 「DTO comparator detects each kind of drift」：少一個欄位、多一個欄位、必填改選填、選填改必填、少了 `null`、列舉成員不同、巢狀物件欄位不同、巢狀陣列元素欄位型別不同，八種都被偵測。

## 5. 對真實檔案的負向演練（皆已還原）

**演練 1：把 contract 中 `session.rename` result 的 `title` 改名為 `name`**，執行 `npm test`：exit 1，`pass 219 / fail 1`，輸出：

```
+   'MethodResults["session.rename"].name: missing from the DTO',
+   'MethodResults["session.rename"].title: not in the contract schema'
MethodResults["session.rename"].name: missing from the DTO
MethodResults["session.rename"].title: not in the contract schema
actual: [ 'MethodResults["session.rename"].name: missing from the DTO', 'MethodResults["session.rename"].title: not in the contract schema' ],
```

還原後 `git diff --quiet protocol/v1/contract.json` 成立。

**演練 2：把 `SessionRenamedDto.title` 改成選填（`title?: string`）**，執行 `npm test`：exit 1，`pass 219 / fail 1`，輸出：

```
+   'MethodResults["session.rename"].title: contract required=true but DTO is optional'
MethodResults["session.rename"].title: contract required=true but DTO is optional
actual: [ 'MethodResults["session.rename"].title: contract required=true but DTO is optional' ],
```

還原後 `src/protocol.ts` 中 `title?: string` 出現 0 次。

## 6. 耗時

- 對真實檔案的比對（建立 Program 到完成）：166–246 ms（測試內 `console.log`：`protocol DTO check: 26 results, 3 events in 246 ms`，完整 `npm test` 中）。
- 整個 `protocol_types.test.ts`（含 4 個測試、3 次 in-memory Program）：約 2.0 s。

## 7. 檢查結果

- `npm test`：220 tests, 220 pass, 0 fail。
- `npm run build`：通過（built in 526 ms）。
