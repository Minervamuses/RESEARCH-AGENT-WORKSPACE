# Issue 06 — Applied Skill 啟動後完整性：可重用指令

## Start / Resume — 啟動與續作

以下整段可複製使用；執行前仍須滿足 PLANS.md 的 Launch prerequisite：

```text
執行 /home/minervamuses/research-agent-workspace/issue/issue_06 計劃。
在更改檔案前依序閱讀：
1. 所有適用 AGENTS.md，以及本次使用者工程限制。
2. issue/issue_06/GOALS.md。
3. issue/issue_06/PLANS.md。
4. issue/issue_06/build-log.md。
5. 依 build-log 狀態和 PLANS roadmap 選出第一個未 Complete、且依賴已
   Complete 的 phase，讀取其 phase file。
6. issue/issue_06/context/ 與 issue/issue_06/code_review/ 中相關既有紀錄
   （若存在），以及該 phase 的 live code/tests。

先做唯讀 preflight：核對 project/runtime/worktree、已核准的具體 API 變更、
scope、non-goals、planned checks、停止條件與依賴。以 live evidence 修正過時
理解；build-log 是唯一 runtime status owner。若 Launch prerequisite 尚未獲得
明確授權，完成可供檢視的唯讀提案後提出一次具體核准請求，不先實作。

依 PLANS 的 execution mode 和 authorization envelope，對合格 phase：
- 解決有界技術 prerequisite；若需使用者決定或必要證據 unavailable，記錄阻礙。
- 只實作該 phase；適用時先用最小 failing test 觀察 bug，再做最小修正。
- 執行 required focused、broader 與代表驗收；失敗先診斷修復，
  不以缺失或失敗證據推進 dependent phase。
- 將實際命令、環境、pass/fail/skipped/unavailable、結果與限制寫入
  issue/issue_06/build-log.md；重大發現才建立 phase context，
  真實 review 才建立 code_review。
- 新證據推翻後續路線，先修訂 PLANS 與受影響的未開始 phase，
  保留重要失敗與已完成紀錄，不自行改 GOALS。
- Autonomous 模式下繼續下一合格 phase，直到 overall completion 或記錄的
  stop condition。不可重複跑完整 suite、擴大改動、使用外部 provider
  或做 Git mutations，除非既有具體授權涵蓋。
完成後回報實際 diff、驗證與限制，停止。
```

## Execute One Phase — 執行單一階段

```text
只執行 issue/issue_06/phases/phase-01-activation-integrity.md。
依 issue/issue_06/PROMPTS.md 的 Start/Resume 讀取順序與 preflight，
確認 PLANS 的 Launch prerequisite、依賴及 authorization envelope，
完成該 phase 的有界修正、驗證、build-log 與必要 context 後停止。
不得自行開始其他 issue。
```

## Verify / Review — 驗證與審查

```text
審查 issue/issue_06 的實作。讀 GOALS.md、PLANS.md、build-log.md、
phases/phase-01-activation-integrity.md、相關 context 與真實 diff。
先唯讀核對 required checks 的 observed evidence，不重新跑已通過的昂貴或完整 suite。
如缺必要證據，依 PLANS 授權只補最小可辨別檢查。
著重 startup hash 是否保留、兩入口是否繞過 gate、錯誤是否洩漏內容，
以及證據是否過度宣稱原子或所有磁碟資源完整性。
只有實際進行 review 才將 findings／檢查方式／限制寫入
issue/issue_06/code_review/phase-01-activation-integrity-review.md。
不要把 builder 自述當證明，不修正 scope 外問題。
```

## Repair Plan — 依矛盾證據修訂

```text
只修訂 issue/issue_06 計劃，不實作。讀其 GOALS、PLANS、build-log、
affected phase、相關 context/review 與 live repository。
指明被反證的理解及影響，只修正必要 roadmap 與未開始 phase；
保留 stable goal、已完成 evidence 與失敗紀錄，用 append-only correction
記錄重大更正。Scope 或 GOALS 若要改變，先取得使用者決定。
```
