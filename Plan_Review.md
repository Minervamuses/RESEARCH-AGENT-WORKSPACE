# Plan Review — UPGRADE_PLAN.md

## 審查結論

`Plan_Review.md` 原列的 6 個 findings 已逐一對照程式碼驗證，全部成立，無誤報。

同時抽查 `UPGRADE_PLAN.md` 本身引用的關鍵事實：`PyYAML` 確實未宣告於 `app/pyproject.toml`、`app/tests/` 確實無 `conftest.py`、`session.py` 恰為 1447 行、`thinking.py` 的 `:476` / `:950`、`api.py` 的 `:246` / `:299`、`graph.py` 的 `:131-135`、R1 宣稱的四個 monkeypatch 名稱，均準確。計劃的盤點基礎紮實，方向正確；採納本 review 的修正後即可執行。

## 對 6 項 Findings 的驗證

- **High — Phase 4.1 JSONStore 寫路徑覆蓋風險：成立。**  
  `rag/rag/store/json_store.py:26-33` 與 `:47-53` 的 `add/delete` 都是用記憶體內 `_docs` 全檔覆寫。計劃只在 `get()` 加 `_maybe_reload()`，一旦 4.1 把 store 快取為長壽命實例，跨程序寫入就可能被過期快取蓋掉。R3 目前只兜到讀不兜寫。

- **High — Phase 2.6 漏了第四份 tool-policy：成立，且更關鍵。**  
  `app/agent/policy_tool_node.py:42-74` 不只是第四份重複，它是唯一的執行期 enforcement。前三處分別偏向 graph binding、prompt rendering、read-only proposer 分類；`PolicyToolNode` 則決定工具呼叫是否真正被擋。它還有蓄意語意：policy active 但 `allowed/denied` 皆空時是 deny-all，且用精確名稱比對、無 `base_tool_name` 正規化。這正是 2.6 要求「蓄意分歧變顯式參數」應涵蓋的對象。

- **Medium — Phase 3.1 拆 `thinking.py` package 會弄壞測試：成立。**  
  `app/tests/test_thinking.py:222` 直接 `read_text()` 讀 `app/agent/thinking.py` 檔案內容做 stale-tool-name 掃描。拆成目錄後會直接 `IsADirectoryError`，`__init__.py` re-export 解不了。計劃需明列測試改寫，或改拆分策略。

- **Medium — Phase 3.2 相容面漏 `_append_block_to_md`：成立，且約束更強。**  
  `app/tests/test_plan_mode.py:137` 是 instance-level patch：`setattr(session, "_append_block_to_md", ...)`。所以光在 facade 保留委派方法還不夠；turn 流程的實際寫入路徑必須仍經過 `self._append_block_to_md(...)`。若 `PlanLog` 在內部自己做 IO 而繞過 facade 方法，patch 攔不到，`test_md_write_failure_aborts_turn` 會靜默失去驗證力。

- **Medium — Phase 2.2 違反自家 facade 決策：成立。**  
  `rag/__init__.py` 的 facade 完全沒有 export LLM 相關符號，而 `UPGRADE_PLAN.md` 第 11 行已記錄使用者決策：跨套件耦合應更嚴格地走 facade。2.2 若讓 `app` 直接 import `rag.llm.openrouter`，會與這個決策矛盾；OpenRouter contract 應經 facade export 或放中立模組。

- **Low — Phase 1.2 漏 `session.py:1140`：成立，但實際漏得更多。**  
  全域 grep `thinking_fusion_allow_side_effect_tools` 可見多個引用點，不能只依計劃列出的固定行號刪除。

## 額外發現

1. **Phase 1.2 的死碼清單漏的不只 `session.py:1140`。**  
   `thinking_fusion_allow_side_effect_tools` 至少出現在 `session.py:516`、`:708`、`:1140`。此外 `_run_proposer_candidate` 的 `side_effect` 參數串接，如 `:601`、`:608-616`，也應一併清理。建議 1.2 改為 grep 驅動：刪 config 後以全域引用點為準逐一處理，不要依賴固定行號。固定行號在前面 commit 落地後也會漂移。

2. **Phase 2.6 的統一 API 必須能表達 enforcement 語意。**  
   三處 non-enforcement 實作主要處理「哪些 tool 出現在 prompt 或 binding」；`PolicyToolNode` 處理「執行期擋不擋」。統一模組若不能同時表達 prompt/render/binding/enforcement 四種用途，就會被迫保留第四份邏輯。`deny-all when policy active and no allow/deny` 必須是顯式策略。

## 建議的計劃修訂

按嚴重度排序：

1. **Phase 4.1** 補寫路徑的 reload 與 `deferred_save` 衝突語意。最低限度：mutation 前 reload，並明確定義 last-writer-wins 或 fail-loudly；較安全的預設是偵測外部寫入後 fail-loudly。
2. **Phase 2.6** 納入 `policy_tool_node.py` 為第四個接點，並把 deny-all default、精確名稱比對、base-name 正規化等分歧做成顯式策略。
3. **Phase 3.2** 相容面補 `_append_block_to_md`，並加註「實際寫入呼叫路徑必須經過 facade 的 `self._append_block_to_md(...)`」。
4. **Phase 3.1** 明列 `test_rewrite_messages_do_not_embed_stale_tool_names` 的改寫：拆 package 後掃描 `app/agent/thinking/` 下所有 `.py`，而不是讀單一 `thinking.py`。
5. **Phase 2.2** 改為 facade export 或中立 contract 模組，避免 `app` 直接 import `rag.llm.openrouter`。
6. **Phase 1.2** 改 grep 驅動清理 `thinking_fusion_allow_side_effect_tools`，包含 config、所有 session 引用、metadata 欄位與 `side_effect` 參數串接。

以上修訂都是計劃文字與約束層級的修正，不影響 Phase 排序與整體架構；`UPGRADE_PLAN.md` 的骨架可以維持。
