# C6-S4 掃描量測（R3：只量測，不加快取）

- **日期**：2026-11-22
- **機器**：Intel Core Ultra 9 285H（16 執行緒）、31 GiB RAM、WSL2（Linux 6.6.87.1-microsoft-standard-WSL2 x86_64）、Python 3.13.14（Conda env `app`）；資料放在 `$TMPDIR`（WSL ext4）。
- **條件**：
  - 以 `ConversationRepository.create`／`append_pending`／`complete_turn` 寫出合法的 v3 對話檔；每個對話 4 個已完成的文件回合，每回合凍結的 `documentContext.sourceText` 約 250 KB，檔案平均 1,011,112 bytes（約 0.96 MiB）。
  - 兩種規模：10 個與 50 個對話。
  - 每次量測都新建 `DesktopService`，量「開啟專案」（`workspace.select` action `open`，含 inspect 與 `open_project_history` 的 scan）與緊接的一次 `session.list`；各跑 3 次取中位數。
  - scan 次數以包裝 `ConversationRepository.scan` 計算。
  - 檔案剛寫完，作業系統的檔案快取是熱的；沒有量冷快取。
- **腳本**：同目錄的 [`scan_cost.py`](scan_cost.py)。

```bash
cd app && /home/minervamuses/miniconda3/envs/app/bin/python \
  ../harness/plans/2026-11-19-repo-debt-cleanup/evidence/C6-S4/scan_cost.py "$TMPDIR/c6s4"
```

## 結果

| 對話數 | 歷史總大小 | 開啟專案（中位數） | 開啟時 scan 次數 | 一次 `session.list`（中位數） | `session.list` scan 次數 |
|---|---|---|---|---|---|
| 10 | 10.1 MB | 0.122 s（0.121／0.122／0.126） | 1 | 0.123 s（0.123／0.126／0.122） | 1 |
| 50 | 50.6 MB | 0.565 s（0.565／0.565／0.562） | 1 | 0.557 s（0.557／0.560／0.557） | 1 |

原始輸出：

```json
[
  {
    "conversations": 10,
    "listed": 10,
    "mean_file_bytes": 1011112,
    "total_bytes": 10111120,
    "open_seconds": [
      0.1211,
      0.1221,
      0.1262
    ],
    "open_median": 0.1221,
    "open_scans": [
      1,
      1,
      1
    ],
    "list_seconds": [
      0.1234,
      0.1259,
      0.1218
    ],
    "list_median": 0.1234,
    "list_scans": [
      1,
      1,
      1
    ]
  },
  {
    "conversations": 50,
    "listed": 50,
    "mean_file_bytes": 1011112,
    "total_bytes": 50555600,
    "open_seconds": [
      0.5653,
      0.5649,
      0.5619
    ],
    "open_median": 0.5649,
    "open_scans": [
      1,
      1,
      1
    ],
    "list_seconds": [
      0.557,
      0.5597,
      0.5568
    ],
    "list_median": 0.557,
    "list_scans": [
      1,
      1,
      1
    ]
  }
]
```

## 解讀（不訂門檻）

- 耗時大致與歷史總位元組數成正比，約每 MB 11 ms：scan 會完整讀取並驗證每個對話檔，包括凍結的文件內容。
- 前端在支援的流程中觸發 scan 的時機：開啟專案（`workspace.select` 一次、接著 `session.list` 一次，共 2 次）、每個回合完成後重新載入清單一次、刪除與 turn 停止／失敗後的重新整理各一次、Load more 一次。以 50 個約 1 MiB 的對話來說，每回合完成後多約 0.56 s 的背景清單載入（此時回答已顯示，回合也已結束），開啟專案約 1.1 s。
- **是否加快取由使用者決定**（R3）。本計劃不加快取；最終彙報會引用這份結果。
