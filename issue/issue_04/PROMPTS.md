# Issue 04 — Citation earliest 歧義：可重用指令

以下可複製指令只有在使用者實際送出時才啟動對應工作；計劃文件本身不構成
implementation 授權。目標、授權、階段及狀態各自以所引用文件為準。

## Start or Resume End-to-End Execution

```text
請在 /home/minervamuses/research-agent-workspace 執行 issue/issue_04 計劃。
我授權依 PLANS.md 的 routine authorization 完成其中直接必要的局部實作、
既有 pytest 內的最小測試及規定的離線驗證；不需逐 phase 再確認。
仍遵守 PLANS.md 的 fresh-authority stop conditions。

修改前依序讀取：
1. 所有 applicable AGENTS.md。
2. issue/issue_04/GOALS.md。
3. issue/issue_04/PLANS.md。
4. issue/issue_04/build-log.md。
5. 依 roadmap 順序，第一個尚非 Complete 且 dependencies 都為 Complete
   的 phase file。
6. 若已存在，issue/issue_04/context/ 與 issue/issue_04/code_review/ 中
   與該階段及先決階段有關的材料。
7. 該階段相關的 live application files、tests 及目前 diff。

從 durable files 恢復工作，不依賴對話記憶。以 build-log.md 為唯一執行狀態，
以 live repository 與觀察結果優先於 stale plan。先做 read-only runtime gate：
確認 Linux/WSL、Conda app、Linux Git/Python/Poetry；核對並保留既有修改。
環境不符時停止，不改用 Windows 或系統 Python。

對每個 eligible phase：
- 做 read-only preflight，確認 scope、non-goals、planned checks、前置與停止條件。
- 前置或必要授權缺少時停止；環境 gate 通過後才可記錄 Blocked。
- 只實作該 phase；先取得最小 red 或 characterization，再做最小 green。
- 執行 required focused、代表流程和 broader verification。
  必要 check 失敗或缺證據時先修正，不標 Complete、不開始 dependent phase；
  遵守 PLANS.md 的失敗次數及成本上限。
- 將 exact commands、實際 pass/fail/skipped/unavailable、驗收對應與限制寫入
  issue/issue_04/build-log.md。只有重大發現才寫 context，實際 review 才寫
  code_review；不得虛構通過結果。
- 若證據推翻後續工作，保留歷史，先修訂 PLANS.md 和受影響未開始 phase，
  再繼續。不自行改變 GOALS 的穩定需求。
- 依 execution mode 繼續下一個 eligible phase，直到 overall completion
  或已記錄的停止條件。全部已有有效完成證據時直接交接，不重跑整套驗證。

結束時列出實際 changed files、checks、結果與剩餘限制；勿超出計劃範圍。
```

## Execute One Phase

```text
只執行 /home/minervamuses/research-agent-workspace 的 issue/issue_04
之 phases/phase-01-earliest-ambiguity.md。先依同 bundle PROMPTS.md 的
Start/Resume 讀取順序恢復目標、授權、狀態、現場與前置，確認 dependencies
完成後，執行該 phase 的 preflight、最小實作及必要驗證，記錄實際 evidence。
本指令授權 PLANS.md 的 routine actions；例外停止條件仍有效。
只完成這一個 phase，不啟動其他 issue。
```

## Verify a Phase / Final Integration Review

```text
審查 /home/minervamuses/research-agent-workspace 的 issue/issue_04。
讀取 applicable AGENTS.md、GOALS.md、PLANS.md、build-log.md、
phases/phase-01-earliest-ambiguity.md、actual diff 及存在時的 context/review。
將每項成功條件對應到實際證據，特別確認時間歧義不是非時間排序所消除、
重複 identity 不誤判、保存邊界未覆寫歧義，以及 exact/non-earliest 路徑保留。
依 phase 的成本與重跑限制檢查既有結果，只有新變更、失敗或證據缺口才追加
最小必要檢查。缺證據即明列，不能把 builder narrative 當成 proof。
本次為 review；不修改 application code。只有實際 review 後可將 findings、
所檢證據和限制記入 issue/issue_04/code_review/phase-01-earliest-ambiguity-review.md。
```

## Repair the Plan After Contradictory Evidence

```text
只修訂 /home/minervamuses/research-agent-workspace 的 issue/issue_04 計劃。
依 PROMPTS.md 的 Start/Resume 讀取順序檢查 durable files 和 live repository。
指出哪項理解被什麼證據推翻，只更新必要的 roadmap、受影響未開始 phase 與
交接指令；重大 correction 追加至 build-log.md，不抹去完成或失敗歷史。
GOALS 的改變必須先有使用者明確需求。重新做結構/path 驗證與 fresh-agent
walkthrough；此指令不授權 application implementation 或 AGENTS.md 修改。
```
