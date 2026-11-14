# K1 前置核對與基線

- **後置條件**：分支、HEAD、工作樹、工具與 PLANS「基線」列出的程式位置已核對；可沿用的測試基線已記錄；本計劃檔已提交。
- **涵蓋**：G9（後續回歸檢查以這裡的基線為比較對象）。
- **相依**：無。
- **標準與政策**：[GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| K1-S1 | **唯讀核對**：<br>1. 分支是 `GUI`，記錄 HEAD；HEAD 不是 `7489076` 時，記錄中間的 commit 並判斷是否影響基線。<br>2. 本計劃檔都已提交；沒有的話補一個 `docs(plan): …` commit，`build/` 下用 `git add -f`。<br>3. `git status` 中與本計劃無關的檔案：只記錄，不動。<br>4. 用 `grep -n` 確認 PLANS「基線」每一項仍成立（行號可略有位移，同樣的程式碼必須存在），特別是：快照標頭字串、`_document_turn_active` 的所有使用處、`LATEST_CONTEXT_TURNS`、`_base_prompt_history` 的所有使用者、存檔成功結果中的 `sourceText`、`runtime.py` 的多 skill 提示、`academic-paper-writing` 的佔位符。<br>5. Conda `app` 的 Python 可執行，`$P/bin/python -c "import agent, skills"` 成功（在 `app` 下）。 | 每項的指令與結果寫進 build-log。不符時判斷影響哪些階段，修改那些階段檔（並 commit）後再繼續 |
| K1-S2 | **核對可沿用的測試基線**：讀 PLANS 的歷史紀錄來源（先前計劃的 build-log，可用 `git show` 讀已刪除的檔案），比較與目前 HEAD 的差異，標示仍可沿用的範圍。跑一次本計劃會動到的局部測試模組（PLANS「檢查範圍」列出的那些），作為修改前的局部基線。不跑完整套件。 | 記錄來源、版本、結果與限制；局部測試的指令、通過數與耗時另記，不冒充完整基線。已存在的失敗列明測試名稱，不修無關問題；K8 仍要求全部通過 |

K1-S1、K1-S2 各自 commit（只提交 build-log 與必要時修改的計劃檔）。

## 交付給後續階段

已核對的程式位置、局部測試基線、已知的既有失敗。
