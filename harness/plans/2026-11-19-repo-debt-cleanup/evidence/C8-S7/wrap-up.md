# C8-S7 階段收尾與 C8 驗收

- **日期**：2026-11-22，程式狀態 `096b679`。

## 檢查

| 檢查 | 結果 |
|---|---|
| `npm test`（`app/desktop`） | 247 pass、0 fail（C8 開始前 224；+`api.test.ts`、approvalOwner、reducerOnce、各 domain 純函式測試） |
| `npm run build`（`tsc`、`tsc -p tsconfig.test.json`、`vite build`） | 通過 |

## 量測（以 `evidence/C1-S3/metrics-before.md` §3 的指令）

| 項目 | C1-S3 | C8-S1 | C8-S7 |
|---|---:|---:|---:|
| `App.tsx` 行數 | 3,059 | 3,000 | 2,462 |
| `App()` 本體 `useState` | 35 | 34 | 33 |
| `App()` 本體 `useRef` | 35 | 36 | 33 |
| `App()` 本體 `useEffect` | 14 | 13 | 11 |
| `App()` 本體 `useCallback` | 42 | 44 | 46 |
| 整檔 `useState`／`useRef`／`useEffect`／`useCallback`（含 import 一次） | 43／39／16／43 | 42／40／15／45 | 41／37／13／47 |

判讀：行數減少主要來自純函式移到 `src/lib/`（C8-S2）、後端呼叫與回聲檢查移到 `api.ts`（C8-S3）、核准清除集中（C8-S5）。hook 數量變化小：依拆解原則，只有 extensions 符合「state／ref／effect 都屬於自己」而抽成 `useExtensions`；核准、文件、回合等 domain 的判斷抽成純函式並測試，state 留在 `App()`（理由見 `evidence/C8-S6/domains.md`）。`useCallback` 增加是因為部分薄包裝以 callback 形式接到純函式。

## C8 驗收（phase-08「完成後的狀態」）

| 狀態 | 證據 |
|---|---|
| 純邏輯在 `.ts`，測試直接 import，`tsc` 也檢查測試 | C8-S2 |
| `api.ts` 是唯一呼叫後端與原生 picker 的地方，參數受 DTO 一致性檢查 | C8-S3（`listen` 也在 C8-S6 移入 `api.ts`） |
| browser preview 已刪除 | C8-S4 |
| `App()` 依 domain 拆解：判斷在純模組、`useExtensions` 一個 hook、跨 domain 協調集中在 `App()` | C8-S6 |
| 重啟、Stop、核准、過期回應、文件衝突的檢查保留且有純函式測試 | C8-S6 原則 5 對照表 |

## GUI 清單

C8 各步新增的項目分別在 `evidence/C8-S3/api.md`、`C8-S4/browser-preview.md`、`C8-S5/reducer-approval.md`、`C8-S6/domains.md` §七；流程基礎是 `C8-S1/app-behaviors.md` §1。C10-S3 彙整成單一清單，高風險項目（核准框接線、擴充重啟順序、重啟後的過期事件）照標註保留。

## 註記

`096b679` 的標題是 `docs(plan)`，但也包含把 `listen` 移入 `api.ts` 的小幅程式修改（`App.tsx` 6 行、`api.ts` 7 行），測試與 build 均通過。
