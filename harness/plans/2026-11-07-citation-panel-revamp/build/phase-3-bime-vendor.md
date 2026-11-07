# R3 加入依賴並 vendor bime_word 1.1.5

- **後置條件**：
  - Conda `app` 可以 `import docx, lxml`，`pyproject.toml` 與 `poetry.lock` 已記錄這兩個依賴。
  - `app/vendor/bime-word/` 的內容和 1.1.5 zip 完全相同，並通過 manifest 檢查。
  - vendor 的 `doctor` 確認轉檔依賴可用；R3-S3 的正負試轉均已執行，成功或失敗與原因均有紀錄。R3 Complete 只代表工具環境就緒與試轉結果已交接；真實 proposal 的成功驗收由 R4-S3 把關，不能把試轉失敗記成 G5 通過。
- **涵蓋**：G5 的環境與試轉證據；完整成功條件由 R4-S3 驗收。決策 D10、D11、D12。
- **相依**：R1，需要 zip 雜湊值相符與工具都可用。
- **範圍外**：桌面後端的整合（R4）。不修改 vendor 內的任何檔案，也不碰 `~/.claude/skills/bime-word`。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| R3-S1 | **加入依賴**。在 `app/` 中，以 Conda `app` 為目前環境，執行 `poetry add "python-docx>=1.2.0,<2.0" "lxml>=5.2,<7.0"`。需要連到 PyPI；沙箱擋下時在沙箱外重跑。執行前先檢查 `pyproject.toml`，已有這兩個依賴時不要重複加入。不修改 `env-app.yml`。 | `$P/bin/python -c "import docx, lxml"` 成功，並記錄安裝的版本；`poetry check` 通過；`git diff` 只修改 `pyproject.toml` 與 `poetry.lock`；指定的引用相關 pytest 仍然通過 |
| R3-S2 | **vendor bime_word**。<br>1. 把 zip 解壓到 `$TMPDIR` 下新建的空目錄，再次核對 zip 的 SHA-256 與 manifest。<br>2. 把 `bime-word/` 整個複製到 `app/vendor/bime-word/`，不包含任何 `__pycache__`。<br>3. 提交前執行 `git add --dry-run` 確認檔案清單：vendor 內的 `.gitignore` 只忽略 bime_word 自己的報告與 preview，不應影響原始檔。<br>4. 依 `.gitattributes` 保持 LF；如果 zip 裡有 CRLF 檔案，記錄下來，不要轉換，以免 manifest 失效。<br>5. 確認 `agent/skills/metadata.py` 的技能探索根目錄不包含 `app/vendor`，vendor 的 `SKILL.md` 不會被當成 agent 技能載入。<br>6. commit 訊息記錄來源路徑、zip SHA-256 與版本。 | 在 `app/vendor/bime-word` 執行 `sha256sum -c manifest.sha256`，全部 OK；`diff -r <解壓目錄>/bime-word app/vendor/bime-word` 沒有差異（略過 `__pycache__`）；`$P/bin/python app/vendor/bime-word/scripts/bime_word.py doctor` 回報 python-docx、lxml、Pandoc 都可用；以專案的技能清單載入方式確認沒有名為 `bime-word` 的技能 |
| R3-S3 | **以隔離副本試轉**。<br>1. 在新的暫存根目錄中建立 `positive/` 與 `negative/`。記錄論文 repo 的 HEAD commit，從該固定 commit 讀取 `proposal.md`、`references.json`、`bime-proposal-profile.json` 及必要圖片，分別放入兩個目錄。原資料夾只讀。<br>2. 正向副本須包含 `yao2023react`；只在負向副本刪除這一個 key，不依賴使用者工作樹是否仍缺少它。記錄兩份輸入的差異。<br>3. 在 repo 根目錄先設定 `bime_vendor_script="$PWD/app/vendor/bime-word/scripts/bime_word.py"`；分別以 `positive/`、`negative/` 為工作目錄，執行 `$P/bin/python "$bime_vendor_script" convert proposal.md -o proposal.bime.docx --config bime-proposal-profile.json --bibliography references.json --scope fragment`。兩處輸出開始前均不得存在；重試使用新的目錄，避免舊輸出遮蔽缺 key 的錯誤。<br>4. 各自保存 stdout、stderr、結束碼及實際產生的報告到 `evidence/R3-S3/positive/`、`negative/`。正向輸入與報告保持不動，供 R4-S3 複製使用；docx 不提交。 | 試轉的成功標準：正向結束碼 0 或 1，產生 `proposal.bime.docx` 與三份報告，python-docx 能讀出參考文獻段落與封面標題；負向結束碼 2、stderr 指出 `yao2023react`，而非 `Output exists`。R3-S3 的交接條件是兩個案例均有實際結果與診斷，不能省略失敗；任一未達成功標準時在 build-log 記為 G5／R4-S3 的未解驗收項目。`/home/minervamuses/論文/` 的 `git status` 和開始前相同 |

每個步驟各自 commit。R3-S1 的 commit 主旨例如 `build(deps): add python-docx and lxml for bime_word [R3-S1]`。

## 失敗與恢復

- `poetry add` 改到其他套件的鎖定版本時，記錄差異。只要完整測試在 R6 通過，就接受；如果造成測試失敗，在範圍內修正，或以 `[R3-S1 checkpoint]` 保留證據，並列入最終彙報。
- `doctor` 回報缺少字型時，記錄下來，不安裝字型：字型只影響在 Word 中的顯示，不影響轉檔。
- R3-S1、R3-S2 的依賴、完整性或 doctor 未通過時，R3 保持未完成，R4 不開始。
- 環境就緒且 R3-S3 已完整記錄試轉結果時，R3 可完成，R4-S1／S2 可用最小輸入進行整合；這不解除真實案例的驗收問題。正向結束碼 2 或負向未得到指定的缺 key 錯誤時，記錄原因及恢復所需條件，R4-S3／G5 不得宣告通過。
- 只在有新診斷、修正或輸入差異時重試失敗案例，遵守 PLANS 的次數與成本上限；同一問題兩次修正仍失敗後封鎖該問題及 R4-S3 的真實驗收。若工具環境已就緒且試轉紀錄完整，R4-S1／S2 及已滿足前提的 R5 步驟仍可繼續；若環境本身受阻，仍可先做 R5-S2。昂貴失敗依 D15 停止整次執行。不修改 vendor 或使用者原稿來讓驗收通過，也不能以最小輸入成功替代真實 proposal。

## 交付給後續階段

- vendor 腳本的路徑：`app/vendor/bime-word/scripts/bime_word.py`。
- 正向副本的固定來源 commit、檔案內容、CLI 結果與報告；失敗時明列 G5 的未解項目，不能把預期欄位當成已觀察結果。
- 成功時觀察到的 stdout JSON 欄位（`output`、`audit`、`reports`、`operation_report`），R4 依它們解析結果。R3-S1／S2 通過與 R3-S3 試轉結果已記錄，只解鎖 R4-S1／S2；R4-S3 仍須正負案例達到成功標準。
