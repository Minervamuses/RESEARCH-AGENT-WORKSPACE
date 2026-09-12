# Issue 06 — Phase 01 獨立 review

日期：2026-09-12（Asia/Taipei）。Reviewer：fresh-context agent
`/root/issue06_review`；由 builder 將其實際回報記錄於此。

## 範圍與方法

- 先讀 root AGENTS、GOALS、PLANS、phase 與 build-log，確認 Linux/Conda app
  Python 3.13.14、Poetry 2.4.1。唯讀檢查 `git diff 931684f..38bc4b7`，
  特別是三 production 檔與兩個 test 檔，再追蹤 live discovery/session/slash code。
- 獨立 `git diff 931684f..38bc4b7 --check` 通過；reviewer 沒有編輯檔案、
  commit 或重跑 application tests。另以獨立程序核對兩種 package import 順序。

在 `app/` 實際執行：

```bash
conda run -n app python -B -c 'import agent.extensions.discovery; import agent.skills.runtime; import agent.extensions.startup; print("discovery-first imports OK")'
conda run -n app python -B -c 'import agent.skills.runtime; import agent.extensions.discovery; import agent.extensions.startup; print("runtime-first imports OK")'
```

兩者 exit 0，分別輸出 `discovery-first imports OK`、`runtime-first imports OK`；
均只有既有 LangChain pending deprecation warning。

## 結論

**無 required findings，不需要追加 production 修正。**

- `startup.py:64–73` 先驗證 bundle 與 registry hash 相等，才將 entry hash
  存入 frozen metadata；activation 沒有查最新 registry 或 desired drop-in。
- `runtime.py:171–186` 在 resolve、runtime 內容載入與工具授權解析前，
  以原 bundle 路徑重用 inspect_bundle，root symlink 不會先被 resolve 隱藏。
  invalid scan、hash mismatch 與支援的 I/O failure 回固定錯誤，不帶 parser 細節。
- `metadata.py:26` 預設 None，保留三參數建構與 built-in/custom 分支。
  applied branch 的局部 import 避免 package cycle。
- 真 Session 的兩種 activation 都先完成 load，才改 Citation runtime/service/
  thinking 狀態。Generic slash 只先解析 followup；Citation handler 直接 activation，
  與新增驗收測試所走入口一致。
- 測試沒有 mock 掉核心 install/startup/fingerprint/runtime/session gate；
  三種內容異動、failure representatives、A/B revision 及 graph 不執行都有直接斷言。

## Evidence 與限制

- Focused **67 passed**、broader **42 passed** 是 reviewer 在 build-log 檢查的
  builder 執行證據。Full suite **1092 passed, 2 warnings in 23.64s** 是 builder
  完成後提供的結果；reviewer 未重跑，不能稱為 reviewer 獨立測試結果。
- 一次 precheck 不是 atomic bytes snapshot；檢查後持續寫入與普通 resource
  讀取不在此保證內。Unchanged re-apply 也不必然修復損毀的 installed destination。
  沒有 live-provider 或 GUI-rendering 驗證。
