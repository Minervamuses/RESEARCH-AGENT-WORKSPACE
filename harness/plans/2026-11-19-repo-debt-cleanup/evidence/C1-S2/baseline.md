# C1-S2 測試與建置基線

- **日期**：2026-11-21
- **基底 commit**：`4f488eb`（`app/` 程式碼與 `3b6cfd8` 相同）
- **環境**：WSL Ubuntu-24.04，已啟用 Conda 環境 `app`（`source /home/minervamuses/miniconda3/etc/profile.d/conda.sh && conda activate app`）

## 摘要

| 檢查套件 | 執行目錄 | 指令 | 通過 | 失敗 | 略過 | 耗時 | 既有失敗 |
|---|---|---|---:|---:|---:|---:|---|
| Python pytest | `app/` | `/home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider` | 1,808 | 0 | 0 | 64.58 s | 無 |
| 前端單元／整合測試 | `app/desktop/` | `npm test` | 329 | 0 | 0 | 11.25 s (`11247.56 ms`) | 無 |
| 前端型別與打包建置 | `app/desktop/` | `npm run build`（`tsc --noEmit && vite build`） | 通過（739 modules） | 0 | — | 0.87 s (`873 ms` vite build) | 無 |
| Rust 宿主測試 | `app/desktop/` | `cargo test --locked --manifest-path src-tauri/Cargo.toml` | 42 | 0 | 0 | 0.69 s（編譯 49.89 s） | 無 |

## 備註

- 四套檢查全部零失敗，沒有「既有失敗」。後續所有步驟以「零失敗（不新增任何失敗）」為準。
- `cargo test` 的 `backend::tests` 會檢查 `CONDA_PREFIX`，因此必須在啟用 Conda 環境 `app` 後執行，不能只把 `envs/app/bin` 加進 `PATH`。
- `pytest` 既有 2 則非失敗 warning（`LangChainPendingDeprecationWarning` 與 `test_installer_zip_rejects_unsafe_members_without_extracting` 故意測試重複 zip 項目的 `UserWarning`）。
