# Citation 儲存結果如何交給 Agent 與 CLI

## Issue 定位

- 類型：架構決策紀錄與後續驗證。
- 優先度：中。
- 整併判定：不阻擋將 `repair` fast-forward 至 `main`；本 issue 保留作後續驗證。
- 重要限制：不要恢復舊版以 host finalizer 全面攔截、解析並覆寫模型回覆的架構。

## 專案背景

本專案的 `app/` 是 LangGraph chat agent。使用者啟用內建 citation Skill 後，模型可呼叫 `citation_workflow` StructuredTool 搜尋或保存引用資料。

保存相關元件：

- `app/skills/citation/service.py`
  - 執行解析、權威資料查詢、BibTeX 驗證與 bundle 寫入。
  - 回傳 `SaveBatchOutcome`，其中每個 item 都有 `saved`、`reused`、`not_found`、`verification_failed` 等實際結果。
- `app/skills/citation/tool.py`
  - 將 `save` action 暴露給模型。
  - 把 `SaveBatchOutcome` 同時放進可讀文字與 tool artifact，形成模型可見的 `ToolMessage`。
- `app/agent/session.py`
  - 收集 citation save metrics，執行一般 finalization 與 history persistence。
  - 目前不再依 artifact 重寫模型的完整最終回答。
- `app/skills/citation/SKILL.md`
  - 告訴模型必須依實際工具結果回報保存狀態。

## 歷史背景

舊 `repair` 實作曾在 `session.py` 建立一套 host-side finalizer：重新解析 tool artifact、判斷可信 receipt，然後用固定格式取代模型全文。這套機制原意是避免模型宣稱假成功，但它同時複製了 citation workflow 已有的驗證邏輯，並導致正常保存流程經常被額外政策攔截或改寫。

`repair` 現行架構在 commit `5918387`（`refactor(citations): trust agent-selected save intent`）移除了這個複雜覆寫層。這是刻意的架構方向，不是需要回復的 regression。

## 原 annotation

> 原本在 repair 的做法是造輪子，自己打造超複雜系統攔截，結果讓正常儲存一直出錯。是否只要在儲存程式追加 print，讓 agent 看 CLI log，再寫成功或失敗訊息即可？

## 需要釐清的資料通道

核心想法「讓真正執行保存的程式成為唯一事實來源」是正確的，但 `print()` 不是可靠的 agent 輸入：

- `print()`／一般 logger output 通常寫到 CLI 終端，只保證人類可見。
- 模型能可靠讀到的是 LangGraph message state 中的 `ToolMessage`。
- 若再建立「擷取 CLI log 並餵回模型」的機制，會多出一條容易失序、截斷或洩漏內部資訊的資料通道。

目前 `citation_workflow` 已回傳：

```text
Actual citation save result:
<SaveBatchOutcome JSON>
```

因此 agent 並不缺保存結果；它應直接根據 ToolMessage 撰寫回覆。

## 已決定的方向

1. `SaveBatchOutcome` 繼續作為保存事實的單一來源。
2. ToolMessage 是提供給 agent 的正式通道。
3. 不重新加入 deterministic finalizer 來覆寫模型全文。
4. 若希望使用者能獨立核對，可由 CLI 額外顯示同一份 outcome 的簡短 status block；這是給人看的 observability，不是 agent 的輸入來源。
5. CLI 顯示應從結構化 outcome 產生，避免散落的 `print()` 各自組字串。

## 接手 Agent 的工作範圍

接手時先確認上述 ToolMessage 是否確實在模型產生最終答案前進入 message state。不要假設 stdout 會被模型看到。

可進行的改善：

- 改善 tool result 的人類可讀摘要，使成功、重用、失敗原因清楚但仍保留 artifact。
- 在 citation Skill 指令中保留「只能根據實際 tool result 宣稱保存結果」的要求。
- 視需要在 CLI progress/output 層顯示權威 status block。
- 補齊模型或 deterministic fake-model 測試，驗證混合成功／失敗批次的回覆依據。

## 非目標

- 不重新驗證 provider metadata；那是 `CitationService`／resolver 的責任。
- 不讓 finalizer 重新推斷使用者意圖。
- 不把 CLI log parser 引入 agent graph。
- 不保證語言模型永遠不會違反 tool result；若需要硬性 UI 保證，使用獨立的 CLI status block，而不是重寫模型全文。

## 驗收條件

- `saved`、`reused` 與每種 failure 都完整出現在模型可見的 ToolMessage。
- 最終答案生成發生在 tool result 已加入 message state 之後。
- 測試覆蓋全成功、全失敗、部分成功與 retry 後成功。
- CLI status 若存在，內容與同一個 `SaveBatchOutcome` 一致。
- 不重新引入舊版 host-side receipt renderer／全文覆寫流程。

## 主要參考檔案

- `app/skills/citation/service.py`
- `app/skills/citation/tool.py`
- `app/skills/citation/types.py`
- `app/skills/citation/SKILL.md`
- `app/agent/session.py`
- `app/tests/test_citation_save_outcomes.py`
- `app/tests/test_citation_workflow_tool.py`
- `app/tests/test_turn_finalizer.py`
