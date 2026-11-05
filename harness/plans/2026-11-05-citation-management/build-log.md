# 執行紀錄

本文件是本計劃唯一的狀態來源。

## 目前狀態

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| C1 | In progress | C1-S1 基線見事件 | — | C1-S2 安裝 Pandoc |
| C2 | Not started | — | 依賴 C1 | — |
| C3 | Not started | — | 依賴 C2 | — |
| C4 | Not started | — | 依賴 C1 | — |
| C5 | Not started | — | 依賴 C4 | — |
| C6 | Not started | — | 依賴 C3、C5 | — |
| C7 | Not started | — | 依賴 C6 | — |
| C8 | Not started | — | 依賴 C7 | — |

## 事件

每筆事件的格式：標題為步驟 ID（例如 `C2-S1`）與一句結果；內容列出改動、執行的檢查與結果、證據位置、限制、下一步。續作時以步驟 ID 對照 git log 的 commit subject。

### CA0 計劃撰寫（2026-11-05）

- **內容**：根據 2026-11-05 與使用者的討論撰寫本計劃（決策 D1–D8 見 GOALS）。
- **規劃時的唯讀檢查**：
  - 讀過 `for_agents/` 的架構、責任、資料流與 backlog；確認文件編修與引用流程的程式碼位置（見 PLANS 基線）。
  - 確認 Pandoc 不在本機；app 環境沒有 lxml；desktop 沒有 citeproc 相依。
  - 確認使用者論文 `references.json` 以 `indent=1`、`ensure_ascii=False` 加結尾換行重新序列化後逐位元組相同；69 筆、無中日文條目；`proposal.md` 約 46 個不同的 key；`regulations.docx` 即附件十七原文。
  - 確認 root `.gitignore` 忽略 `build/`，計劃目錄下的 `node_modules` 不被忽略。
- **未執行**：任何產品程式修改、依賴安裝、測試執行。

### CA0 撰寫檢查（2026-11-05）

- **結構檢查**：long-horizon-plan-author 的 `validate_plan.py`（只檢查檔案、連結與相依圖）回報 ok，14 個檔案，0 錯誤 0 警告；修正後重跑結果相同。它不證明內容正確或可行。
- **全新情境審查**：由一個沒有對話脈絡的唯讀子代理，以執行者的角度走查。它對照 HEAD 抽查了 20 個以上的程式碼位置，全部相符；也確認論文基線的數字（69 筆、52 筆有 DOI、`indent=1` 逐位元組相同、46 個 key）。它指出的缺口與處理：
  1. C8-S1 沒有建立 session、也沒切到 Bypass，`bibliography.add` 會卡在沒人回應的批准 → 已加入 `session.create` 與 `session.set_bash_permission`。
  2. `bibliography_lookup` 的接線沒點出 `document_edit` 的三個特例（`session.py:149-150`、`:661-663`、`service.py:2347`）→ 已寫進 C3-S3，並加上「不觸發批准」的測試。
  3. catalog 沒有改寫既有 metadata 的函式，且改寫會改變 `researchFingerprint` → 已寫進 C6-S2。
  4. `knowledge.ingest_file` 的位置指錯（`:1728` 是回合內的 slash 路徑）→ 改指 `_knowledge_ingest_file`（`:3362`）與 `_require_operation_approval`（`:2333`）。
  5. 書目路徑的注入點不明 → C2-S3 註明經由 `CitationSessionPolicy`；PLANS 的檔案範圍同步放寬 `session.py` 的說明。
  6. `bibliography.add` 在回合外如何取得批准與服務 → 已寫進 C6-S2。
  7. PROMPTS 沒提醒啟動前要先提交 [CA0] → 已加入。
  8. build-log 的事件格式 → 已加入說明。
- **限制**：審查者與撰寫者使用相同的資料來源；沒有實際執行任何計劃步驟。

### CA1 執行政策加嚴（2026-11-05，使用者指示）

- **使用者要求**：「每步改動皆要commit」；「不要停下來等人工授權，應該執行到底，我開始執行就代表授權整份計劃，有問題應該紀錄而不是找我」。
- **改動**：
  - PLANS 第 1 項：送出啟動提示 = 授權整份計劃，執行中不提問。
  - 第 2 項：計劃檔沒被追蹤時，由執行者自己補提交後繼續，不再判為硬阻塞。分支不是 GUI 時，只記錄並寫最終彙報。
  - 第 4 項：任何 repository 改動（含計劃修訂與 evidence）都要進入 commit，不得以未提交的改動結束。
  - 第 9、10、12 項：明文規定不找使用者；硬阻塞只剩兩種（分支不是 GUI、commit 失敗）。
  - PROMPTS 與 GOALS A10 同步修改；A10 註明 GUI 的批准是產品行為，與執行者無關。
- **檢查**：結構檢查重跑。

### C1-S1 唯讀核對與基線測試通過（2026-11-05）

- **Git**：`/home/minervamuses/research-agent-workspace`，分支 GUI，HEAD `6538f69`；tracked 與 index 乾淨（`git diff --cached --name-only` 空）。`git status --short` 只列出宿主掛載的佔位項目（`.bash_profile`、`.bashrc`、`.claude/`、`.gitconfig`、`.gitmodules`、`.idea`、`.mcp.json`、`.profile`、`.ripgreprc`、`.vscode`、`.zprofile`、`.zshrc`），不 stage。計劃 14 個檔案都通過 `git ls-files --error-unmatch`。
- **工具鏈**（`/home/minervamuses/miniconda3/envs/app/bin`）：Python 3.13.14、Poetry 2.4.1、node v24.18.0、npm 11.16.0、cargo/rustc 1.97.1。
- **基線測試**：
  - 完整 pytest（沙箱外，`TMPDIR`/`XDG_CACHE_HOME`/`AGENT_LOG_DIR` 導到 `/tmp/cm-base.*`）：1517 passed，2 warnings，52.6 s，exit 0。
  - `npm test`（沙箱內）：260/260 pass，exit 0。
  - `npm run build`（沙箱內）：exit 0（既有的 chunk > 500 kB 警告）。
  - `cargo test --locked`（沙箱外）：40 passed，exit 0。
- **既有失敗**：無。之後的回歸以此為準（全部通過）。
- **下一步**：C1-S2。

## 最終彙報

（C8-S3 完成後填寫。）
