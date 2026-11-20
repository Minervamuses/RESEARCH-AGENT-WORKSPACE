# C1 — 前置核對與基線

- **完成後的狀態**：
  - 起點已核對，必要時已重新定位 S-ID。
  - 四套檢查的實際基線已記錄。
  - 熱點檔案與協定的量測已存證，供最終彙報比較。
  - TS 讀取 JSON 的方式，以及測試能否使用 TypeScript compiler API，都已探測。
- **涵蓋**：G9
- **相依**：無
- **目標與政策**：[../GOALS.md](../GOALS.md)、[../PLANS.md](../PLANS.md)

本階段不修改任何產品程式碼。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C1-S1 | **唯讀核對起點。**<br>1. 讀 `AGENTS.md`、`CLAUDE.md`、GOALS、PLANS、build-log。<br>2. 確認分支是 `GUI`。<br>3. 執行 `git log --oneline 3b6cfd8..HEAD` 與 `git diff --stat 3b6cfd8..HEAD -- app`：除了本計劃的 `[CA*]` commit 與使用者的文件 commit（`19a661d`、`90d8d58`、`3f87f09`），若有其他 commit 改到 `app/`，就依符號重新定位受影響的 S-ID，結果寫入 `evidence/C1-S1/relocation.md`。<br>4. 列出 `git status --short`，確認與 PLANS「基線」的工作樹描述一致。 | 分支、HEAD、工作樹與預期一致，或差異已記錄並判斷不影響。 |
| C1-S2 | **建立基線。** 在目前程式上依 PLANS「檢查指令」執行完整 pytest（沙箱外）、`npm test`、`npm run build`、`cargo test --locked`（沙箱外）。<br>把每套的通過、失敗、略過數、耗時與失敗名稱寫入 `evidence/C1-S2/baseline.md`。 | 四套都有結果。若基線本來就有失敗，記為「既有失敗」並附名稱：它不阻塞本計劃，也不在本計劃修正，除非剛好屬於某個 S-ID；之後的步驟只要求不新增失敗。 |
| C1-S3 | **量測。** 把 PLANS「規模」表列的檔案行數寫入 `evidence/C1-S3/metrics-before.md`，再加上：<br>• contract 的方法、request event、process event、錯誤碼數量；<br>• `fixtures.json` 的 message 與 trace 數；<br>• `App()` 內的 `useState`、`useRef`、`useEffect`、`useCallback` 數；<br>• `styles.css` 中不同的 hex 與 rgba 色數；<br>• `service.py` 中 `session._` 與 `self.session._` 的出現次數。<br>量測方式（指令）一併記錄，C10 用同樣方式重量。 | 每個數字都附產生它的指令。 |
| C1-S4 | **探測（拋棄式，不改 repo）。** 探測檔都放在 `$TMPDIR`，不進 repo。結果寫入 `evidence/C1-S4/probes.md`。<br>1. **JSON import**（GOALS A2）：建一個 `.ts` 檔，以 `import contract from "<絕對路徑>/app/desktop/protocol/v1/contract.json" with { type: "json" };` 讀取 contract 並印出 `contract.methods.length`，用 `node --experimental-strip-types` 執行。`tsc` 與 Vite 是否接受同一寫法，由 C3-S1 在 repo 內實測。<br>2. **TypeScript compiler API**（GOALS A6）：從 `app/desktop/` 以 `node --test --experimental-strip-types` 執行一個測試檔，內容是 `import ts from "typescript"`、以 `app/desktop/tsconfig.json` 的設定對 `src/protocol.ts` 建立 Program、取得 checker，再列出 `SessionListDto` 的屬性名稱與是否選填。記錄耗時。 | • 記錄 Node 是否接受 JSON import，以及錯誤訊息。<br>• 記錄 compiler API 能否列出 `SessionListDto` 的 8 個屬性、每個是否選填，以及執行耗時。不能時記錄錯誤訊息，C3-S3 改用 GOALS A6 的備案。 |

每一步完成後更新 build-log 並 commit，例如 `docs(plan): record preflight baseline [C1-S2]`。

## 驗收

- `evidence/C1-S1`～`C1-S4` 都存在，內容是實際執行的結果。
- build-log 的 C1 列為 Complete，下一步指向 C2-S1。

## 交給後續階段

- **基線**：之後的步驟以「不新增失敗」為準。
- **量測方式**：C10 用同一套指令量測完成後的數字。
- **探測結果**：JSON import 是 C3-S1 的輸入；compiler API 是 C3-S3 的輸入。
