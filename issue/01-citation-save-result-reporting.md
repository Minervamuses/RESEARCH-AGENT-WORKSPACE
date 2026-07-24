# Citation 儲存結果的回報方式

## 原 annotation

> 其實我仔細想了一下，這東西原本在 repair 的做法就是造輪子，自己打造一套超複雜的系統來攔截，結果變成正常儲存一直出錯。我現在想到，只要在負責儲存的程式裡面追加 print，然後讓 agent 看著 CLI Log 來寫儲存成功或失敗的訊息，這樣不就好了？

## 判定

- 狀態：接受目前簡化架構，不阻擋 branch 整併。
- 核心方向正確：不恢復 `repair` 中複雜的 finalizer 攔截與覆寫系統。
- 需要修正的一點：單純 `print()` 到 CLI 通常只有使用者看得到，agent 不會自動取得終端 stdout。Agent 應讀取工具回傳的 `ToolMessage`。

## 目前流程

1. Citation 儲存程式產生 `SaveBatchOutcome`。
2. `citation_workflow` 將實際狀態、原因及 receipt 以結構化內容回傳。
3. 工具結果成為 agent 當輪上下文的一部分。
4. Agent 根據工具結果撰寫成功或失敗訊息。

目前 `app/skills/citation/tool.py` 已回傳 `Actual citation save result` 與 artifact；因此不必再建立一套讓 agent 解析 CLI log 的通道。

## 後續方向

- 保留結構化工具回傳作為 agent 的唯一事實來源。
- Skill prompt 明確要求 agent 只能依最後一次工具結果回報保存狀態。
- 若希望使用者能獨立核對，可由 CLI 另外顯示同一份 `SaveBatchOutcome`，但不要要求 agent 回頭解析 CLI log。
- 可使用 `logger.info()` 或專用 status block；避免散落的 `print()` 污染互動輸出。

## 驗收條件

- 成功、重用與失敗結果都完整出現在 `ToolMessage`。
- Agent 在測試中能依 tool result 正確報告混合成功／失敗批次。
- CLI 額外顯示狀態時，內容與同一個 `SaveBatchOutcome` 一致。
- 不重新引入 deterministic finalizer 覆寫模型全文的舊架構。
