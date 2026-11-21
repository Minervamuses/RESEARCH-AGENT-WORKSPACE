# C1-S4 拋棄式技術探測（JSON Import 與 TypeScript Compiler API）

- **日期**：2026-11-21
- **環境**：WSL Ubuntu-24.04，Conda `app` 環境，Node `v24.18.0`，TypeScript `6.0.3`
- **探測目錄**：`mktemp -d /tmp/c1-s4-probes.XXXXXX`（執行結束由 `trap` 自動刪除，未修改 repo 任何檔案）

## 1. JSON Import 探測（GOALS A2）

探測程式（`$PROBE_DIR/json-probe.ts`）：

```ts
import contract from "/home/minervamuses/research-agent-workspace/app/desktop/protocol/v1/contract.json" with { type: "json" };
console.log("methods.length =", contract.methods.length);
```

執行指令：

```bash
node --experimental-strip-types "$PROBE_DIR/json-probe.ts"
```

結果：

- **是否接受**：是（Exit code `0`，無任何錯誤或警告訊息）。
- **輸出**：`contract.methods.length = 40`（`Array.isArray(contract.methods) === true`）。
- **交給 C3-S1 的結論**：Node `v24.18.0` 的 `--experimental-strip-types` 原生支援 `import contract from ".../contract.json" with { type: "json" };`；C3-S1 可直接在 repo 內驗證同一寫法是否同時通過 `tsc --noEmit` 與 `vite build`。

## 2. TypeScript Compiler API 探測（GOALS A6）

探測方式：於 `$PROBE_DIR` 建立指向 `app/desktop/node_modules` 的符號連結（模擬 `app/desktop/tests/*.test.ts` 的 ESM 解析路徑而不寫入 repo），由 `app/desktop/` 執行 `node --test --experimental-strip-types "$PROBE_DIR/compiler-api.test.ts"`。

程式重點：`import ts from "typescript"`，讀取 `app/desktop/tsconfig.json`，對 `src/protocol.ts` 建立 `ts.createProgram`，透過 `program.getTypeChecker()` 取得 `SessionListDto` 宣告型別並列出所有屬性與 `(prop.flags & ts.SymbolFlags.Optional) !== 0`。

結果：

- **是否成功**：是（1 pass, 0 fail，無錯誤訊息；不需啟用 GOALS A6 備案）。
- **建立 Program 並解析 `SessionListDto` 耗時**：`322.96 ms`（整個 `node --test` 行程耗時 `604.15 ms`）。
- **列出的 `SessionListDto` 8 個屬性**：

| # | 屬性名稱 | 是否選填（`optional`） | 解析型別 |
|---:|---|---|---|
| 1 | `projectId` | `false` | `string` |
| 2 | `status` | `false` | `"ready" \| "unavailable"` |
| 3 | `issue` | `false` | `string \| null` |
| 4 | `items` | `false` | `SessionSummaryDto[]` |
| 5 | `total` | `false` | `number` |
| 6 | `offset` | `false` | `number` |
| 7 | `limit` | `false` | `number` |
| 8 | `hasMore` | `false` | `boolean` |

- **交給 C3-S3 的結論**：`tests/` 可直接在 `node --test --experimental-strip-types` 中 `import ts from "typescript"` 建立單次 `ts.Program` 比對 DTO 與 `contract.json`，耗時約 0.32 秒。
