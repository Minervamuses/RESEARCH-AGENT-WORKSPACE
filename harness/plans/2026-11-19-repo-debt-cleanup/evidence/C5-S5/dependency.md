# C5-S5 以 Poetry 移除 `pybtex`（U9）

- **日期**：2026-11-22
- **授權**：GOALS U9 與本次啟動提示（「C5-S5 以 Poetry 移除 pybtex（只限這一項相依變更）」）。
- **環境**：Conda env `app`、Poetry 2.4.1、從 `app/` 執行，沙箱外（需要寫入 Poetry 快取與 Conda env）。

## 步驟與結果

1. `poetry remove --dry-run pybtex`：`Package operations: 0 installs, 0 updates, 2 removals, 119 skipped`，只移除 `latexcodec (3.0.1)` 與 `pybtex (0.26.1)`，沒有其他套件的新增、升級或降級。
2. `poetry remove pybtex`：同樣的兩項移除，`Writing lock file`。
3. `grep -n "pybtex\|latexcodec" pyproject.toml poetry.lock`：0 筆。
4. `poetry check`：`All set!`。
5. `python -c "import skills.citation.service, skills.citation.authority"`：成功。

## lock 的 diff

`app/poetry.lock`：30 行刪除、1 行新增。刪除的是 `latexcodec` 與 `pybtex` 兩個 `[[package]]` 區塊（含 `pybtex` 對 `pyyaml` 的依賴宣告）；新增的一行是 `content-hash`。`pyyaml` 在 `pyproject.toml` 有直接宣告，不受影響。`app/pyproject.toml`：只刪除 `"pybtex (>=0.26.1,<0.27)"` 一行。`poetry.lock` 沒有手改。
