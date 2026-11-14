# K2 量出文件佔多少

- **後置條件**：turn trace 的每次模型呼叫多出文件佔比欄位（只有計數，不含文字）；15 個編輯回合的假模型量測可重複執行，修改前的數字存進 `evidence/K2-S2/`。
- **涵蓋**：G6。
- **相依**：K1。
- **輸入**：PLANS「基線」的文件回合、歷史重播、編輯結果、量測各節；GOALS A7。

## 為什麼先做這一步

S1 的影響估計（第 15 回合最多 11 份全文）全部來自讀碼。K3、K4 的效果要拿實際數字比，所以先能量、先留下修改前的數字。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| K2-S1 | **文件佔比欄位**。新增一個純函式（建議放 `agent/observability.py`），輸入一次模型呼叫的訊息列表，回傳：`prompt_chars`（全部訊息字元數）、`document_chars_current`（最後一則使用者訊息中快照的 `sourceText` 字元數）、`document_chars_history`（較早的使用者訊息中快照與凍結引用的全文字元數）、`document_chars_tool_results`（工具訊息中 `document_edit` 結果的 `sourceText` 等全文字元數）、`document_full_copies`（全文副本數）。辨識依據是 `service.py` 實際使用的快照標頭、凍結引用標頭與工具結果 JSON；無法解析時計為 0 並設 `document_parse_issue`，不丟例外。把這些欄位接進 `TurnTimingTrace`：在能拿到完整訊息的回呼（優先 `on_chat_model_start`；先確認 LangChain 版本實際呼叫哪一個）計算，於 `model_end` 一併輸出，並加上 `document_tokens_estimate = input_tokens × 文件字元 ÷ prompt_chars`（`input_tokens` 為空時為空），欄位名稱或說明標明是估計值（A7）。不記錄任何文字內容。 | 新增單元測試：手造含快照、凍結引用、`sourceTextSameAs`、`document_edit` 工具結果、以及無文件的訊息列表，斷言各欄位等於獨立計算的值；格式壞掉的快照得到 `document_parse_issue` 而非例外；`tests/test_observability.py` 既有測試通過；檢查 turn trace 輸出不含 `sourceText` 內容 |
| K2-S2 | **15 回合假模型量測**。新增測試檔（建議 `tests/test_document_context_budget.py`），沿用 `tests/test_desktop_document_service.py` 的 `_setup`／`_DocumentModel` 方式（必要時把共用輔助函式抽到該檔可匯入的位置，不改其行為），跑同一個 session 的 15 個帶文件回合：文件約 20 KB、含中文與 emoji；至少 10 個回合呼叫 `document_edit` 並存檔成功；至少 1 個回合在同一回合內連續兩次編輯；至少 3 個回合只分析不編輯；至少 1 個回合帶一個舊版本的凍結文件引用。用 K2-S1 的函式量測每一回合每次模型呼叫的欄位，寫成 JSON。設環境變數（例如 `DOCUMENT_BUDGET_REPORT=<路徑>`）時把 JSON 寫到該路徑，未設時只做斷言。本步斷言只檢查量測本身與流程正確（例如 15 回合都完成、每回合的全文副本數 ≥ 1、編輯確實存檔），不斷言要被 K3／K4 改變的數字。 | 以 `DOCUMENT_BUDGET_REPORT=<計劃>/evidence/K2-S2/before.json` 跑一次，存下 JSON 與一份人讀摘要（第 1、5、10、15 回合的全文副本數、文件字元數與占比）；摘要與讀碼預估（第 15 回合最多 11 份）比較，不同時記錄實際數字與原因。不呼叫任何真實模型 |

K2-S1、K2-S2 各自 commit。

## 交付給後續階段

量測函式、可重跑的 15 回合測試、`evidence/K2-S2/before.json` 與摘要。K3、K4 用同一個測試產生 after 數字。
