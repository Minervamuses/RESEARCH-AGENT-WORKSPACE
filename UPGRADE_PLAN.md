# 深度審核與重構升級計劃 — research-agent-workspace

## Context（背景）

專案因先前追求開發速度累積技術債。本次由三路並行審核（可運作性／重複與造輪子／模組化與效能）完成全面盤點，並交叉驗證關鍵發現。

**使用者確認的設計決策（不列為問題、不納入計劃）：**
- Conda 管環境與底層依賴、Poetry 管純 Python 套件、不使用 venv（`virtualenvs.create=false`）——刻意設計。
- 現階段只接 OpenRouter；無 key 直接報錯是預期行為。未來成熟後才逐步加 Claude API / OpenAI API 等接口。
- 模型 slug 不做預先驗證；模型失效就讓程式報錯、換掉即可（fail-fast）。
- `app/` 與 `rag/` 本來就是**兩個獨立開發的專案**，合併擺放僅為方便本次審查。因此各自保留 conda env file；且跨套件耦合應更嚴格地走 facade，不伸手進對方內部模組。
- 手刻 SDK 已有的功能：同意移除——官方有 API/SDK/function 就不自己造，除非有顯著提升。
- 結構失衡（session.py god object、rag 投機性 ABC）：同意重構。

**總體結論：專案跑得起來、大方向分層正確，問題集中而非遍地開花。** 最高槓桿的三件事：(1) `JSONStore` 的 O(n²) ingest 成本與每次 tool call 全量重讀、(2) `session.py` 1447 行 god object、(3) 一批已確認的死碼與重複邏輯。

---

## 審核結論（回答四大問題）

### Q1. 專案能否正常運作？ → **能**，唯一真正的潛藏地雷是 PyYAML

- `app` → `rag` path dependency 接線正確（`app/pyproject.toml:11`），import 圖完整、無循環引用、無缺失符號。
- **潛藏地雷 A1**：`PyYAML` 在 4 個模組被 import（`agent/skills/metadata.py:10`、`runtime.py:9`、`broker.py:10`、`cli/slash_commands.py:9`）但 `app/pyproject.toml` 未宣告，目前靠間接依賴碰巧存活——上游依賴鏈一變動就會 ImportError。
- 依使用者確認為設計決策、**不列為問題**：無 key 即 RuntimeError（fail-fast）、模型 slug 不預先驗證、conda+poetry 無 venv 工作流。
- 已排除的誤報：`chroma.sqlite3` 未被 commit（本機殘留、有 gitignore）；`thinking.py` 兩檔非循環引用。

### Q2. 重複設定／重複功能／造輪子？ → 存在，但集中

- **跨套件平行實作**：`app/agent/llm/openrouter.py`（LangChain 棧）vs `rag/rag/llm/openrouter.py`（原生 openai SDK 棧）——內部已分歧不宜合併棧，但 OpenRouter base URL 與 API key 檢查兩邊硬編碼重複。
- **白造的輪子**：`rag` 手刻 exponential backoff（`rag/llm/openrouter.py:30-43`），openai SDK 本身就有 `max_retries`。
- **已分歧的複製貼上**：`agent/thinking.py` 自帶 `invoke_text`（:476）與 `_content_part_to_text`（:950），與 `agent/llm/text.py` 重複且行為已分歧。
- **三重實作**：tool-policy（allowed/denied/base-name）邏輯在 `graph._select_tools`、`skills/runtime.render_tool_availability_block`、`session._proposer_read_only_*` 各寫一份。
- **Chroma 快取模式**複製於 `rag/api.py:22-41` 與 `history_rag/store.py:86-103`（註解自承「Mirrors rag.api._get_store」）。
- **測試零 conftest.py**：`FakeSession` 單檔重複 8 次、`_FakeHistoryStore` 4 份（已分歧）、fake model stub 散落 ~15 檔。
- 排除誤報（架構其實正確）：`history_rag` 是包裝 `rag` 非重寫；`AgentConfig` 繼承 `RAGConfig`；模型名／chunk size 單一來源。

### Q3. 模組化是否確實合理？ → 大方向對，兩處失衡

- 分層方向全部正確：`rag` 不 import `agent`、`agent` 不 import `citation`、`tools/` 不 import `cli/`；rag 的 facade（api.py + tools.py）乾淨。
- **失衡一**：`session.py`（1447 行）ChatSession 吞了 12 種職責，~600 行是 extended-thinking fusion 管線 + plan-mode markdown IO。公開介面窄、只有 `cli/chat.py` 引用，內部拆分對呼叫端低風險。
- **失衡二**：`rag` 有 6 個 ABC，其中 4 個只有單一實作且從未變化（embedder/retriever/chunker/tagger）——投機性抽象。
- 分層小疵：`cli/slash_commands.py:14` 直接 import `rag`（ingest 編排邏輯放在 CLI 層）；`history_rag/store.py:18-19` 繞過 facade 進 rag 內部；`scholar_fallback.py:20` 與 `rag/sync.py:18` 各 import 一個他模組私有符號。

### Q4. 冗餘程式碼與效能？ → 有明確死碼清單與一個 HIGH 級效能洞

已確認死碼（grep 驗證零 production 呼叫者）：
`agent/history.py:39 trim_message_history`、`:50 prepare_messages_for_agent`（文件化 no-op）、`rag/llm/ollama.py OllamaLLM`、`app/agent/llm/ollama.py get_ollama_chat_model` + config `filter_llm_model`、`citation/scholar_fallback.py:127 try_scholar_bibtex`、`rag/cli/query.py`（孤兒）、config `thinking_fusion_allow_side_effect_tools` 恆為 False → `session.py:577-583, 609-611, 710-721` 為死分支。

效能：
- **HIGH — `JSONStore`**（`rag/store/json_store.py`）：`__init__` 全量載入 raw.json；每次 `add`/`delete` 全檔重寫（indent=2）；且每次 tool call（`api.py:246,299`）重新建構 → `get_context` 每叫一次全檔重新 parse；`ingest_repo` 每檔 delete+add 兩次全檔序列化 → **O(n²) ingest**。
- MED：ingest 逐 folder 串行 LLM tagging（`cli/ingest.py:152-157`）；逐檔 Chroma add/delete 無跨檔 batch；citation capture 串行 ~5 次網路往返。
- 已刻意做對的（不用動）：模型／graph／ChromaStore 全有 memoize；plan log 是 append；skills manifest 不會每則訊息重讀。

---

## 升級計劃

**執行前**：`cd app && pytest`、`cd rag && pytest` 先建立綠色基線。每個編號項目完成後跑對應測試；每階段結束跑全套 + 手動 CLI 冒煙（一次普通對話、一次 extended thinking、`/plan` 進出、一次觸發 `get_context` 的查詢）。

### Phase 0 — 包裝正確性速贏（工作量 S）

| # | 動作 | 檔案 | 風險 |
|---|------|------|------|
| 0.1 | 宣告 `pyyaml = "^6.0"`、`typing-extensions = "^4.0"`，`poetry lock && poetry install`（在 app conda env 內執行，遵守無 venv 工作流） | `app/pyproject.toml` | 低 |
| 0.2 | 移除未直接 import 的 `mcp = "^1.27.0"`（由 langchain-mcp-adapters 傳遞）——manifest 只宣告直接 import 的套件 | `app/pyproject.toml` | 低 |

（原 0.3 `.env.example` 補項與 0.4 模型 slug 驗證，依使用者確認為設計決策，撤除。）

### Phase 1 — 死碼刪除（工作量 S，每項獨立 commit，先刪再整併）

| # | 刪除 | 連動修改 |
|---|------|---------|
| 1.1 | `agent/history.py` 的 `trim_message_history` + `prepare_messages_for_agent` | 刪 `graph.py:131-135` 呼叫點與 import；刪 config `agent_max_messages`（唯一讀者是被刪呼叫點）；更新 `test_history.py`、`test_session_eviction.py` |
| 1.2 | config `thinking_fusion_allow_side_effect_tools` + `session.py:577-583, 609-611, 710-721` 死分支 | 刪 `test_thinking_session.py:636` 附近測試（能力保留在 git history） |
| 1.3 | `app/agent/llm/ollama.py get_ollama_chat_model` + config `filter_llm_model` | 更新 `test_openrouter_model.py`、`agent/llm/__init__.py` |
| 1.4 | `rag/rag/llm/ollama.py OllamaLLM`（Ollama **embedder** 是活的，不動） | `rag/llm/__init__.py` export |
| 1.5 | `rag/rag/cli/query.py`（孤兒） | 無 |
| 1.6 | `citation/scholar_fallback.py:127 try_scholar_bibtex` | 無 |

### Phase 2 — 去重複（工作量 M/L）

- **2.1 先建 `app/tests/conftest.py`**（本階段最大項）：統一 `FakeHistoryStore`（四份取聯集，用 `raise_on_add: bool = False` 參數化分歧）、`QueuedModel`、`make_astream_graph(events)` 工廠、`FakeSession` 工廠、通用 `invoke_fake_model(responses)`。先遷移四個重度使用檔（`test_thinking_session.py`、`test_plan_mode.py`、`test_session_eviction.py`、`test_chat_cli.py`）。**純測試 PR、零 production 改動、全套必須原樣通過。** 風險：中。
- **2.2 單一來源 OpenRouter 契約**：在 `rag/rag/llm/openrouter.py` 增 `OPENROUTER_BASE_URL` 常數與 `get_openrouter_api_key()`；`app/agent/llm/openrouter.py:40-45` 改 import 使用。兩邊客戶端棧不合併。風險：低。
- **2.3 刪手刻 retry**：`rag/llm/openrouter.py` 刪 `_call_with_retry`，改 `OpenAI(..., max_retries=10)`。風險：低-中（429 下退避節奏改變，可接受）。
- **2.4 整併 thinking.py 重複**（須在 3.1 拆分前落地）：`_content_part_to_text` 採 `agent/llm/text.py` 版（超集）；`invoke_text` 先用表格測試釘住 thinking.py 現行輸出再換實作（pin-then-swap）；ToolMessage 分組函式移入 `agent/history.py`，`session.py:390-396` 改呼叫。風險：中（行為已分歧）。
- **2.5 泛用 Chroma 快取**：新增 `rag/rag/store/cache.py::get_chroma_store(collection, cfg)`（Lock + dict by (persist_dir, collection)，附 SharedSystemClient race 說明）；`rag/api.py::_get_store` 改委派；facade export `get_chroma_store`/`ChromaStore`/`VectorRetriever`；改寫 `history_rag/store.py:86-103` 並移除 rag 內部 import（順帶關掉 E4 分層小疵）。風險：低-中（快取 key 語意須完全一致）。
- **2.6 單一 tool-policy 模組**：新增 `app/agent/tool_policy.py`（`base_tool_name`、`filter_tools`、`render_availability_block`、read-only 分類）；改接三個實作點（`graph.py:93-109`、`skills/runtime.py:107-128`、`session.py:465-489`）。**先 diff 三份實作，蓄意分歧變成顯式參數，不得默默統一。** 風險：中。
- **2.7 單一 skill 檔案載入器**：`skills/metadata.py` 增 `load_skill_file(path) -> (frontmatter, body)` 一次讀取一次 parse；`metadata.py:61` 與 `runtime.py:202` 共用（消掉 SKILL.md 讀兩次）。風險：低。
- **2.8 citation LLM 標註去重**：`discovery.py` 的 `_enrich_with_llm`（:279-337）與 `_annotate_and_rank`（:511-576）~80% 相同，抽 `_llm_annotate(...)`，prompt 字串須位元組級一致。風險：低-中。
- **2.9 slash_commands 數字選單去重**：四對 render/resolve（:237-257、:346-370、:414-436、:459-480）抽成一對泛用函式。風險：低。

### Phase 3 — 結構重構（工作量 L）

- **3.1 `thinking.py` 拆成 package**：`app/agent/thinking/` = `schemas.py` + `prompts.py`（zh-TW 模板）+ `parsers.py`（含修復啟發式）+ `review.py` + `trace.py`；`__init__.py` re-export 現有名稱。已驗證僅 `session.py` 與 `test_thinking.py` 兩個 importer、無 monkeypatch 內部符號 → re-export 相容即足夠。排在 2.4 之後（程式碼只搬一次）。風險：低-中。
- **3.2 拆 ChatSession 為 facade + 三協作者**（本計劃最大項，**分三個依序 commit，每個之間全套綠**）：
  1. `app/agent/plan_log.py::PlanLog` — plan-mode markdown IO（session.py:260-430 區段）
  2. `app/agent/turn_store.py::TurnStore` — `_store_turn`/`_evict_overflow`/`flush_recent_turns` 持久化半邊
  3. `app/agent/fusion.py::FusionOrchestrator` — fusion 管線（:459-735、:1020-1369，policy 部分已被 2.6 抽走變薄）
  - ChatSession 公開介面不變 → `cli/chat.py` 零改動。
  - **關鍵約束（已驗證）**：`test_thinking_session.py` monkeypatch `agent.session.build_graph`／`get_chat_model_for_role`／`get_fusion_aggregator_model`／`find_app_root`，並觸碰 `_prompt_history`、`_turn_counter`、`_store_turn`、`_prompt_master_skill_text_cache`、`_apply_final_skill_validation`。因此：(a) 四個被 patch 的名稱保留為 `agent.session` module attribute，以建構子注入（callable）傳給協作者、在 session 建構時解析——monkeypatch 繼續有效；(b) 五個被觸碰的私有成員保留在 facade 上（委派）。風險：高（有 2.1 共用 fixture + 1.2 先刪死分支 + DI 設計三重緩解）。
- **3.3 其餘分層修正**：從 `slash_commands.py:560-702` 抽 `app/agent/ingest.py` service（CLI 不再直接 import rag）；`rag` 的 `_collect_folders` 等移到 `rag/rag/collect.py` 公開命名（`sync.py` 不再 import CLI 私有符號）；`discovery._coerce_text` 改公開 `coerce_text`。風險：低。
- **3.4 rag ABC 修剪**：**保留 `BaseStore`（兩個活實作、真多型）與 `BaseLLM`（library 的合理擴充縫，也對應未來加 Claude API/OpenAI API 接口的計劃）；刪 `BaseEmbedder`／`BaseRetriever`／`BaseChunker`／`BaseTagger`**（各僅一實作、無外部消費者），型別註記改具體類。風險：低。

（原 3.5 conda 環境整併撤除——app 與 rag 為獨立專案，各自保留 env file 是正確的。）

### Phase 4 — 效能（工作量 M）

- **4.1（HIGH，本階段主菜）JSONStore 快取 + 延遲寫入**：**保留 JSON 檔案格式**（sqlite/jsonl 遷移 DEFER——會改變 BM25/備份的磁碟契約）。
  - `json_store.py`：載入時記 `_loaded_mtime`；`get` 開頭 `_maybe_reload()`（一次 stat，跨程序寫入時重載）；新增 `deferred_save()` context manager（批次期間抑制 `_save`，退出時寫一次）。
  - `rag/api.py`：仿 `_get_store` 增 `_get_json_store(cfg)`（dict + lock，key 為 raw_json_path），用於 :246、:299；`sync.py:31,107` 同。
  - `cli/ingest.py::ingest_repo`：整個檔案迴圈包 `with json_store.deferred_save():` → 消滅 O(n²)。
  - 同 commit 順帶 B5：`VectorRetriever` 隨 ChromaStore 一起快取，`api.search` 不再每次重建。
  - 風險：中（跨程序過期由 mtime 檢查兜底）。驗證：新增 deferred_save 單寫入與 mtime 重載單元測試；ingest 前後計時；CLI 觸發一次 `get_context`。
- **4.2 Chroma 批次寫入**：`ChromaStore` 增 `delete_many(pids)`（`where={"pid": {"$in": [...]}}`），ingest 以 folder 為單位批次 delete 後 ~256 docs 一批 add（folder 級批次保住中斷後的 upsert 正確性）。風險：中。
- **4.3 並行 folder tagging**：`_tag_folders` 用 `ThreadPoolExecutor(max_workers=4)`（openai client 執行緒安全；2.3 的 SDK retry 兜 429），結果排序後輸出保持確定性。風險：低-中。
- **4.4 citation 併發**：`discovery.py:460-503` 內互相獨立的 tool await 改 `asyncio.gather`；`capture.py` 的 5 hop 鏈有資料依賴，**DEFER**（先畫依賴圖再並行可證明獨立的部分）。風險：中。

---

## 風險登記簿

| # | 風險 | 階段 | 緩解 |
|---|------|------|------|
| R1 | 3.2 拆分打斷 `monkeypatch.setattr("agent.session.build_graph", ...)` 類測試縫 | 3.2 | 被 patch 名稱保留為 module attribute + 建構子注入；被觸碰私有成員保留在 facade |
| R2 | 2.4 整併默默改變文字抽取行為（已分歧） | 2.4 | pin-then-swap：先表格測試釘住兩種 content-part 形狀的現行輸出再換實作 |
| R3 | 4.1 快取吃到過期 raw.json（另一程序改寫） | 4.1 | 每次讀取 mtime 檢查；deferred_save 寫入後更新記錄的 mtime |
| R4 | 2.1 fake 合併削弱測試斷言 | 2.1 | 純測試 PR、零 production diff、全套原樣通過；分歧參數化而非丟棄 |
| R5 | 2.3 SDK 退避比舊 10s 倍增短 → ingest 期 429 風暴 | 2.3/4.3 | `max_retries=10`、tagging 併發上限 4 |
| R6 | 2.6 policy 統一抹掉三處蓄意分歧 | 2.6 | 先 diff 三份實作；分歧升級為顯式參數 |
| R7 | 重構期間模型 slug 剛好失效，被誤判為重構破壞 | 全程 | fail-fast 為設計決策：遇模型錯誤先確認是 OpenRouter 端問題再排查重構 |

## 工作量總估

Phase 0：**S** ｜ Phase 1：**S** ｜ Phase 2：**M/L**（conftest 佔一半）｜ Phase 3：**L**（3.2 為大宗，三個依序綠 commit）｜ Phase 4：**M**（4.1 是回報最大項）

## 驗證方式（總結）

1. 每個編號項目 → 跑該項列出的對應 pytest 檔。
2. 每階段結束 → `cd app && pytest` + `cd rag && pytest` 全綠。
3. 每階段結束手動冒煙：`python -m agent.cli.chat` 跑一次普通對話、一次 extended-thinking、`/plan` 進出、一次觸發 `get_context` 的查詢。
4. Phase 4 額外：ingest 同一 repo 前後計時對比；重複 ingest 兩次驗證 chunk 數穩定（冪等）。
