# P5 — 有限 timeout 與真實 SDK 重試政策

目標 G5；獨立階段，不依賴 P4 或兩筆歷史耗時歸因。共通 [政策](../PLANS.md)／[目標](../GOALS.md)。

## 已確認與待決定

`app/agent/llm/openrouter.py:46–56` 傳 `llm_max_retries`，未傳 timeout；config.py:27 預設 10。Conda app 已安裝 langchain-openrouter 0.2.6、openrouter 0.10.8。wrapper 的 timeout 是**毫秒**；正值 max_retries × 150,000 ms 是 backoff window，非重試次數。0 不傳 retry_config，SDK fallback 為 3,600,000 ms；未指定 timeout 則 HTTP timeout 為 None。來源行號見 E5。

先決策 O5：每個 HTTP request 的 timeout、有限重試時間／次數政策及慢但有效回答可等待多久。執行者提出有據的小方案與使用者可見取捨，確認後記錄，不捏造秒數。backoff window 在例外後才檢查，下一次 sleep＋request 可越過它；不得宣稱它是總呼叫硬 deadline。如需求含嚴格總截止，須另驗證整體 cancellation／deadline，不能只改 timeout。

## 實作路線與離線驗收

P5-S1：先恢復 brief 提到的 503／timeout 探針。本次在有限搜尋範圍未找到；不依賴 /tmp。找不到時在 `tests/test_openrouter_model.py` 沿用 pytest 加最小 fake HTTP transport＋可控時鐘／sleep，確實走已安裝 wrapper/SDK，無網路、無真實長等待。

P5-S2：優先在既有 `agent/llm/openrouter.py` factory 使用該固定版本支持的參數／SDK 設定路徑，使政策真正傳入。已核實 wrapper 有公開 client 欄位（chat_models.py:162），傳入 client 後不再自行建構（484–488）；SDK OpenRouter 接受 timeout_ms 與 retry_config，顯式 retry_config=None 與 UNSET 不同，前者可避免預設重試。優先提出「顯式 SDK client＋有限 HTTP timeout＋不做 SDK 內部重試」作為最小穩定性選項，再由使用者確認一次暫時 503 即失敗的取捨。若選擇保留內部重試，須另證明 Retry-After／backoff／下一次 request 都受接受的預算約束；SDK 現行有限 window 本身不足。保留 base URL、憑證取得、attribution headers、sync／async 支援及已設定參數；不能只根據 kwargs mock 得出成功，也不能任意 monkeypatch site-packages、升級套件或替換框架。若公開設定不能表達接受的政策，提出最小局部替代及 API／檔案成本待核准，不預建 adapter。如需更改 AgentConfig 公共設定語義，列明相容性取捨並先批准。

P5-S3：對使用者接受的具體政策跑以下可觀察案例，檢查實際 HTTP timeout 單位、呼叫次數／虛擬經過時間、SDK 最終錯誤與取消傳遞。

| 情境 | 預期 |
|---|---|
| 持續 503 | 在接受的有限政策內停止，不回到 25／60 分鐘預設窗 |
| request timeout | HTTP 已收到毫秒轉換後的有限 timeout；按政策有界重試並結束 |
| 極長 Retry-After | 不因 server header 跳出接受的有限等待政策；使用假時鐘，不真的等待 |
| 一次暫時錯誤後成功 | 若政策容許重試，正確回傳成功；不吃掉回應／usage |
| 停用重試（只有選擇此政策時） | 真正一次 HTTP 嘗試；不能用 max_retries=0 的表面斷言代替 |
| 取消／不可重試失敗 | 不重新啟動重試，不轉成成功或空回答 |

P5-S4：檢查 main graph 的 async invoke 與 `agent/llm/text.py` 同步 helper 都經過 factory 的政策；`graph.py` 的 empty-response retry 是另一層，不在本階段默默改掉或當作 SDK 次數。以既有模型工廠／thinking tests 驗證工具綁定、model override、token設定與取消不退化。

命令（app/）：`poetry run pytest tests/test_openrouter_model.py -q`；如實際觸及 model invocation/recovery，再按引用關係選既有相應 tests，避免全域掃描。沒有真模型／paid call。

交付包含接受的數值／單位／政策語義、實際 SDK 離線結果與限制。這是穩定性修正，不據此斷言歷史 341 秒曾觸發 timeout 或重試。
