# R3 加入依賴並 vendor bime_word 1.1.5

- **後置條件**：
  - Conda `app` 可以 `import docx, lxml`，`pyproject.toml` 與 `poetry.lock` 已記錄這兩個依賴。
  - `app/vendor/bime-word/` 的內容和 1.1.5 zip 完全相同，並通過 manifest 檢查。
  - 以 app 環境的 Python 執行 vendor 的 `bime_word.py`，能把 proposal 的副本轉出 Word。
- **涵蓋**：G5。決策 D10、D11、D12。
- **相依**：R1，需要 zip 雜湊值相符與工具都可用。
- **範圍外**：桌面後端的整合（R4）。不修改 vendor 內的任何檔案，也不碰 `~/.claude/skills/bime-word`。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| R3-S1 | **加入依賴**。在 `app/` 中，以 Conda `app` 為目前環境，執行 `poetry add "python-docx>=1.2.0,<2.0" "lxml>=5.2,<7.0"`。需要連到 PyPI；沙箱擋下時在沙箱外重跑。執行前先檢查 `pyproject.toml`，已有這兩個依賴時不要重複加入。不修改 `env-app.yml`。 | `$P/bin/python -c "import docx, lxml"` 成功，並記錄安裝的版本；`poetry check` 通過；`git diff` 只修改 `pyproject.toml` 與 `poetry.lock`；指定的引用相關 pytest 仍然通過 |
| R3-S2 | **vendor bime_word**。<br>1. 把 zip 解壓到 `$TMPDIR` 下新建的空目錄，再次核對 zip 的 SHA-256 與 manifest。<br>2. 把 `bime-word/` 整個複製到 `app/vendor/bime-word/`，不包含任何 `__pycache__`。<br>3. 提交前執行 `git add --dry-run` 確認檔案清單：vendor 內的 `.gitignore` 只忽略 bime_word 自己的報告與 preview，不應影響原始檔。<br>4. 依 `.gitattributes` 保持 LF；如果 zip 裡有 CRLF 檔案，記錄下來，不要轉換，以免 manifest 失效。<br>5. 確認 `agent/skills/metadata.py` 的技能探索根目錄不包含 `app/vendor`，vendor 的 `SKILL.md` 不會被當成 agent 技能載入。<br>6. commit 訊息記錄來源路徑、zip SHA-256 與版本。 | 在 `app/vendor/bime-word` 執行 `sha256sum -c manifest.sha256`，全部 OK；`diff -r <解壓目錄>/bime-word app/vendor/bime-word` 沒有差異（略過 `__pycache__`）；`$P/bin/python app/vendor/bime-word/scripts/bime_word.py doctor` 回報 python-docx、lxml、Pandoc 都可用；以專案的技能清單載入方式確認沒有名為 `bime-word` 的技能 |
| R3-S3 | **以真實內容試轉**。<br>1. 在 `$TMPDIR` 下建立輸入目錄，放入以下檔案：`git -C /home/minervamuses/論文 show HEAD:proposal.md`、`HEAD:references.json`、`HEAD:bime-proposal-profile.json` 的內容，以及 `proposal.md` 引用的本地圖片（如果有）。這些都是只讀的 git 操作。<br>2. 以 `$P/bin/python app/vendor/bime-word/scripts/bime_word.py convert proposal.md -o proposal.bime.docx --config bime-proposal-profile.json` 轉檔。<br>3. **負面案例**：使用者工作樹中目前的 `references.json` 少了 `yao2023react`。用它再轉一次，確認 bime_word 因為未知的 key 停止。<br>4. 把 stdout、stderr、結束碼與 `.audit.md`、`.bime.json` 複製到 `evidence/R3-S3/`；docx 不提交。 | 正向案例的結束碼是 0 或 1，產生 `proposal.bime.docx`，以及 `proposal.bime.audit.json`、`proposal.bime.audit.md`、`proposal.bime.bime.json`；用 python-docx 打開輸出，確認其中有參考文獻段落與封面標題。負向案例的結束碼是 2，stderr 指出 `yao2023react`。`/home/minervamuses/論文/` 的 `git status` 和開始前相同 |

每個步驟各自 commit。R3-S1 的 commit 主旨例如 `build(deps): add python-docx and lxml for bime_word [R3-S1]`。

## 失敗與恢復

- `poetry add` 改到其他套件的鎖定版本時，記錄差異。只要完整測試在 R6 通過，就接受；如果造成測試失敗，在範圍內修正，或以 `[R3-S1 checkpoint]` 保留證據，並列入最終彙報。
- `doctor` 回報缺少字型時，記錄下來，不安裝字型：字型只影響在 Word 中的顯示，不影響轉檔。
- 正向案例的結束碼是 2 時，依 stderr 診斷。設定或輸入的問題記錄在 build-log。bime_word 本身的缺陷不修改 vendor 檔案，列入最終彙報；R4 仍然可以用測試用的最小輸入繼續。

## 交付給後續階段

- vendor 腳本的路徑：`app/vendor/bime-word/scripts/bime_word.py`。
- 正向案例觀察到的 stdout JSON 欄位（`output`、`audit`、`reports`、`operation_report`），R4 依它們解析結果。
