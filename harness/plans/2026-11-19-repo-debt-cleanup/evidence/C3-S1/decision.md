# C3-S1 TS 讀取 contract 的寫法（探索）

- **日期**：2026-11-21
- **環境**：Node `v24.18.0`、TypeScript `6.0.3`、Vite 8（`app/desktop/`）
- **方法**：在 `src/protocol.ts` 開頭暫時加入兩行（import 與 `export const PROBE_CONTRACT_METHOD_COUNT: number = contract.methods.length;`），分別執行 `npx tsc --noEmit`、`npx vite build`、`node --test --experimental-strip-types tests/protocol.test.ts`，以及直接以 Node 匯入 `src/protocol.ts`。結束後以備份還原，暫時改動未提交（`git status --short src/` 為空）。

## 結果

| 寫法 | `tsc --noEmit` | `vite build` | `node --test`（`protocol.test.ts`） | Node 直接匯入 |
|---|---|---|---|---|
| (a) `import contract from "../protocol/v1/contract.json" with { type: "json" };` | exit 0 | exit 0（built in 524 ms） | 209 pass, 0 fail | `count 40` |
| (b) `import contract from "../protocol/v1/contract.json";` | exit 0 | exit 0（built in 509 ms） | 0 pass, 1 fail：`TypeError [ERR_IMPORT_ATTRIBUTE_MISSING]: Module ".../contract.json" needs an import attribute of "type: json"` | 同一錯誤 |

另以寫法 (a) 跑完整 `npm test`：330 pass, 0 fail（包含以 Vite SSR 載入的 5 個測試檔）。

## 決定

採用 **(a)**：三個工具都接受，不需要讓 `protocol.test.ts` 改用 Vite SSR 載入，也不產生任何 TS 副本。
