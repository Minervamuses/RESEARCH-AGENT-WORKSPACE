# D8-S2 完整回歸紀錄（2026-11-27，本次觀察）

## 測試與建置結果

| 檢查 | 指令（Conda `app` 環境） | 結果 | 耗時 | 證據檔 |
|---|---|---|---|---|
| 前端單元／SSR 測試 | `cd app/desktop && npm_config_cache=/tmp/npm-cache npm test` | **297 passed, 0 failed**（D1 基線 256，新增 +41） | wall 8.95 s（runner 8,341 ms） | `npm-test.log` |
| 型別檢查與打包 | `cd app/desktop && npm_config_cache=/tmp/npm-cache npm run build` | **通過**（`tsc --noEmit`、`tsc --noEmit -p tsconfig.test.json`、`vite build` 979 modules） | wall 5.41 s（vite 696 ms） | `npm-build.log`、`dist-assets.txt` |
| 補全控制器打包確認 | `grep -c editor.contrib.suggestController dist/assets/*.js` | `dist/assets/suggestController-B_e4S7NY.js:1`（D1 基線為 0） | — | `suggest-check.txt` |
| 完整 Python 測試（沙箱外） | `cd app && python -m pytest -q -p no:cacheprovider`（`TMPDIR`/`XDG_CACHE_HOME`/`AGENT_LOG_DIR` 指向暫存目錄，Conda `app` PATH） | **1,826 passed, 0 failed**, 2 warnings | wall 58.36 s（pytest 57.49 s） | `pytest.log` |
| Rust `cargo test` | 不需執行（`app/desktop/src-tauri/` 無任何改動） | N/A | — | `boundary-diff.txt` |

## Bundle 大小比較（對照 D1-S2 基線）

| 產物 | D1-S2 基線（含 `monacoFeatures`） | D8-S2 最終 | 變化 |
|---|---|---|---|
| 主程式 `index-*.js` | 393,428 B（393.42 kB，gzip 112.00 kB） | 430,984 B（430.98 kB，gzip 123.92 kB） | +37,556 B（+37.56 kB，gzip +11.92 kB） |
| 主樣式 `index-*.css` | 25,339 B（25.33 kB，gzip 6.14 kB） | 30,167 B（30.16 kB，gzip 7.17 kB） | +4,828 B（+4.83 kB，gzip +1.03 kB） |
| 延遲載入 Monaco JS 合計 | 3,305,374 B | 3,425,229 B（含 `suggestController` 114,897 B） | +119,855 B（+119.86 kB，皆源自 D1A `suggestController`） |
| 延遲載入 Monaco CSS 合計 | 147,388 B | 159,613 B（含 `suggestController` 12,225 B） | +12,225 B（+12.23 kB，皆源自 D1A `suggestController`） |

## 授權邊界檢查

```bash
git diff --stat bc9f651 -- app/agent app/desktop/protocol app/desktop/src-tauri app/desktop/package.json app/desktop/package-lock.json for_agents
```

- 輸出長度：**0 bytes**（`boundary-diff.txt` 為空）。
- 本計劃未新增或修改任何 npm／Python／Rust 依賴，未修改後端、協定、`src-tauri` 或 `for_agents/`，無回歸修復例外項目。
