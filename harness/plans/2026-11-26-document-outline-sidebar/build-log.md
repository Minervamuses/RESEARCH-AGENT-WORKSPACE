# 執行紀錄

本檔是本計劃唯一的狀態來源。撰寫時尚未執行任何實作。

## 目前狀態

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| D1 | Not started | — | — | D1-S1 唯讀核對 |
| D1A | Not started | — | — | 等 D1 |
| D2 | Not started | — | — | 等 D1 |
| D3 | Not started | — | — | 等 D1 |
| D4 | Not started | — | — | 等 D2、D3 |
| D5 | Not started | — | — | 等 D4 |
| D6 | Not started | — | — | 等 D1A、D5 |
| D7 | Not started | — | — | 等 D5 |
| D8 | Not started | — | — | 等 D1A、D2–D7 |

## 撰寫紀錄

### DA0 撰寫計劃（2026-11-26）

- 依 GOALS 的來源 S1–S4 撰寫：使用者在 Claude Code 對話中貼上的需求書（未存進 repo，U9）、`for_agents/briefs/2026-11-26-document-outline.md`（`78cd9ac`）、使用者 2026-11-26 的決策 U1–U9。
- 撰寫時只讀碼（HEAD `78cd9ac`），沒有執行任何測試、建置或 GUI；PLANS「基線」的行號與行為由 D1 重新核對。
- 撰寫時的檢查（只檢查計劃本身，與產品行為無關）：
  - 長程計劃 skill 附的結構 lint `validate_plan.py --json`：修正前後皆 `ok: true`，0 錯誤、0 警告，檢查 13 個檔案。
  - 一次獨立的新手執行者走查（另一個 agent，只拿計劃、使用者原話與選項回答、S2 brief 與現行程式）：U1–U9 都有對應，沒有遺漏或多加的需求；基線行號與事實相符。找到 8 項會誤導執行的缺口，已全部修正：跳轉保護需要 `scrollTop` 且捲動回報經 rAF 延後、`revealLineNearTop` 必須指定 `Immediate`；tracker 在重新解析後重算與換檔重設；側欄收合時的格線排位；格線規則只在原檔修改、D3 只有一種格線做法；寬度依目前視窗夾限；INV-029 誤標；編輯器 handle 尚未註冊時的點擊；收合時 backend 控制一起隱藏的後果。另依建議把跳轉序列改成可注入假編輯器的純函式測試。

### DA1 計劃審核修訂（2026-11-26）

- 依使用者確認更新引用補全載入與四種指令驗收、窄視窗收合、同名章節過期點擊與文末跳轉；啟動提示及交付檢查沿用 PLANS 的回歸修復例外。D1–D8 仍待執行。

### DA2 補全清單缺陷拆成獨立階段（2026-11-26）

- 授權來源：使用者對 Claude 審核 Codex 修訂的三點回覆「同意」（GOALS U10），並在 GUI 實測確認文件編輯器打 `@`、`/` 沒有清單、Ctrl+F 沒反應。
- 撰寫時讀碼確認：`editor.api` 與 markdown 語言定義的 import 圖（約 704 個檔案）不含任何 `editor/contrib/` 功能；`dist/assets/` 沒有 `editor.contrib.suggestController`、`contextmenu`、`findController`；`suggestController.js` 沒有 `.d.ts`；已載入的 `editorWorkerService.js` 含字詞建議提供者；Markdown 的 `[...]` 是 `string.link` token 且 `[` 會自動補 `]`。
- 修訂：新增 D1A（G11）載入補全清單、本地型別宣告、`wordBasedSuggestions: "off"`、`quickSuggestions.strings: "on"`；D6 改為依賴 D1A、不再處理清單控制器；G7 與 PLANS 基線改寫為既有缺陷；其他缺漏的 Monaco 功能列入範圍外並由最終彙報提出。同時提交 DA1（Codex 的五項修訂）尚未提交的改動。
- 檢查（只檢查計劃本身）：結構 lint `validate_plan.py --json` 為 `ok: true`，0 錯誤、0 警告，檢查 14 個檔案；`git diff --check` 通過。D1、D1A、D2–D8 仍未開始。

### DA3 其他 Monaco 功能改由計劃外工作處理（2026-11-27）

- 使用者 2026-11-27 決定補回文件編輯器的右鍵選單（Monaco 選單加剪貼簿）、搜尋／取代、編輯輔助（括號配對、註解切換、行操作、多游標、字詞移動等）、懸停、摺疊與相同字詞標示，以 Monaco 附 `.d.ts` 的 `features/<名稱>/register` 逐項匯入。已在本計劃之外完成：`src/monacoFeatures.ts`、`tests/monacoFeatures.test.ts`。
- 修訂：GOALS「範圍外」、PLANS「基線／編輯器」、D1A 背景（`suggestController` 不放進該檔；`features/suggest/register` 不含清單控制器；bundle 基準改為含該檔的建置）、D8-S3 不再列出缺漏功能。D1、D1A、D2–D8 仍未開始。

## 執行事件

（尚無）
