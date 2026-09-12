# Issue 02 — 可重用指令

以下是未來使用者可複製送出的指令；本檔的存在不代表現在已授權實作。

## Start / Resume — 啟動與續作

```text
請開始／繼續 issue/issue_02 的 Desktop Slash Command Menu 計劃。
我批准 issue/issue_02/PLANS.md 的 Execution Authorization：新增 session snapshot
的 slashCommands protocol-v1 catalog，同步既有 JSON／Python／TypeScript／Rust
邊界，修改該節列出的超過三個直接必要 production files，以及必要既有 fixtures/tests。
請在該範圍自主完成全部 phases；不新增依賴、服務、persistent module 或其他功能。

先讀所有適用 AGENTS.md，並核對使用者的 Personal Engineering Defaults；
再讀 issue/issue_02/GOALS.md、issue/issue_02/PLANS.md、
issue/issue_02/build-log.md。由 build-log 的實際 status 與 PLANS 的依賴順序，
選擇第一個尚未 Complete、且其依賴皆 Complete 的 phase，閱讀其
issue/issue_02/phases/phase-*.md，以及已存在的相關
issue/issue_02/context/、issue/issue_02/code_review/ 和 live code/tests。

每個 phase 先做 read-only preflight：確認 project/runtime、Conda app、
worktree、前置條件、scope、non-goals、planned checks 與停止條件。
對照既有 evidence 與當前 repository；保留 pre-existing changes。
僅實作選定 phase，採用最小可判別缺失行為的 test/check。
執行該 phase 的必要驗證；失敗或未驗證時先診斷修復，不進下一個 dependent phase。
把實際命令、結果、限制、失敗和 status 寫入 issue/issue_02/build-log.md；
只有 material discoveries 才建立對應 context，真正 review 才建立 review 檔。
新證據推翻未開始的計劃時，先修訂 PLANS 與受影響 phase，保留已完成歷史。
在授權範圍內繼續到全部成功條件有證據，或遇到 PLANS 的停止條件。
不要把本次啟動解讀成 commit/push、環境安裝、昂貴或 live provider 操作授權。
```

## Execute One Phase — 執行單一階段

```text
請先按 issue/issue_02/PROMPTS.md 的 Start/Resume read order 重建上下文。
只執行依 issue/issue_02/build-log.md 與 PLANS.md 判定的第一個合法未完成 phase。
若尚無 PLANS.md launch scope 的使用者批准，僅完成 read-only preflight，說明具體缺口。
已有批准時，只修改該 phase scope、執行必要 checks、記錄真實 evidence，
完成後停止，不開始下一階段。
```

## Verify / Review — 驗證與審查

```text
請讀 issue/issue_02/GOALS.md、PLANS.md、build-log.md 與所檢查 phase 的文件，
比對 live diff、相關 context、實際測試結果及使用者可觀察行為。
先使用現有 evidence；不足時依既有授權只跑最小相關 check。
特別確認 catalog 與 dispatch 的一致性、選取 Enter 零送出、
session/generation 失效，以及 SSR/純函式證據是否被誤當成原生 IME 或 focus 驗證。
不實作修改；將真正的 findings 記錄於 issue/issue_02/code_review/phase-NN-review.md，
其中 NN 使用本次實際 review phase 編號，並在 build-log 記錄 evidence reference。
不要憑作者敘述給予通過結論。
```

## Repair Plan — 矛盾證據後修訂計劃

```text
請依 issue/issue_02/PROMPTS.md 的 read order，讀取 live repository 與矛盾證據。
指出哪個理解已被推翻、影響哪些未開始 phases；只修訂
issue/issue_02/PLANS.md 與相關未開始 phase files。
保留 GOALS 的穩定需求，除非使用者明確改變；保留已完成與失敗歷史，
在 build-log 追加 material correction。這是 planning-only，不順便實作修訂內容。
```

## Final Integration Review — 最終驗收

```text
請逐條對照 issue/issue_02/GOALS.md 成功條件、
issue/issue_02/PLANS.md 整體完成標準與
issue/issue_02/phases/phase-03-integration-acceptance.md。
使用 build-log 的已觀察證據，避免沒有新理由就重跑 full suite。
找出沒有 evidence 的條件及不在授權 scope 的 diff；
只在必要證據完整或使用者明確修訂成功條件後標示完成。
如實列出不能執行的 Linux IME／screen-reader 或 GUI 檢查，不用其他平台替代宣稱通過。
```
