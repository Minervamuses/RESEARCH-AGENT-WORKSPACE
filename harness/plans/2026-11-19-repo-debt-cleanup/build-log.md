# 執行紀錄

本檔是本計劃唯一的狀態來源。目前只完成了撰寫；**C1–C10 都還沒有開始，也沒有執行過任何實作或產品測試。**

## 目前狀態

狀態只用四種：

- `Not started`：尚未開始。
- `In progress`：已有步驟 commit，但階段驗收未完成。
- `Blocked`：在「阻塞」欄寫明缺少的前提與受影響的步驟。
- `Complete`：階段驗收已觀察到並記錄。

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| C1 | Not started | — | — | C1-S1 唯讀核對 |
| C2 | Not started | — | — | 等 C1 |
| C3 | Not started | — | — | 等 C1 |
| C4 | Not started | — | — | 等 C3 |
| C5 | Not started | — | — | 等 C3 |
| C6 | Not started | — | — | 等 C3 |
| C7 | Not started | — | — | 等 C2、C4、C5、C6 |
| C8 | Not started | — | — | 等 C3–C6 |
| C9 | Not started | — | — | 等 C8 |
| C10 | Not started | — | — | 等 C2–C9 |

## 撰寫紀錄

### CA0 撰寫計劃（2026-11-19）

**依據**

- 2026-11-19 的唯讀 repo 債務稽核。全文複製在 `context/repo-debt-audit-2026-11-19.md`。
- 使用者當日的決策 U1–U10（見 GOALS）：
  - U1–U4：回覆稽核提出的四個問題；
  - U5–U9：撰寫時以選項確認；
  - U10：要求撰寫計劃。
- U4 的決策紀錄依使用者要求寫成 `note/20261119/citation_storage_unification_decision.md`。

**撰寫時的讀碼範圍**

撰寫時只讀碼，沒有執行任何產品程式或測試。基準是 HEAD `3b6cfd8`，branch `GUI`。讀過：

- citation 的 `storage.py`、`service.py`、`types.py`、`registry.py`、`tool.py`、`session_policy.py`、`providers/doi_org.py`，以及 `resolution.py` 的 DOI 路徑；
- `agent/desktop/catalog.py` 的 catalog 類別與專案載入；
- `service.py` 的 registration、citation 輸出目錄與 runtime diagnostics 相關段落；
- contract 的頂層鍵、方法與 event 清單；
- `app/desktop/package.json`、`tsconfig.json`、`tests/protocol.test.ts` 開頭與 `tests/styles.test.ts`；
- Rust 的 `protocol.rs` 函式清單與 `backend.rs` 的協定呼叫點；
- `pyproject.toml` 與 `poetry.lock` 中的 `pybtex`；
- `for_agents/` 的 INV-010、INV-011、INV-015、INV-016、INV-021、INV-023、INV-027、INV-032，以及 FAIL-022 與 BACKLOG-022。

PLANS「基線」中的行號與行為，都要由 C1 重新核對。

**commit**：`64225d1`（決策紀錄）、`8f4ca06`（計劃）。

### CA1 依獨立審查修訂計劃（2026-11-19）

**審查方式**

- 另一個 agent 在新的 context 中做唯讀走查，只拿到計劃、決策紀錄、稽核原文與使用者原話。
- 結果：0 個 critical、5 個 major、9 個次要問題，共 14 項。
- 撰寫者以 grep 與讀碼逐項複核後才修正。其中一項審查結論是錯的，見第 2 點。

**修正內容**

1. **S023、S024、S026 沒有歸屬。** 這三個 READY 項目已加入 C2-S10，原本的收尾步驟改為 C2-S11。
2. **C4-S1 會刪掉斜線指令仍在用的程式。** 撰寫者讀碼確認：`/init /ingest /sync /prune` 仍使用 `knowledge.*` 名稱做核准 operation、`_map_exception` 的 method key 與 `_KNOWLEDGE_MUTATIONS`（`service.py` 約 1759–1779、1793 行）。
   - 審查認為 `_map_exception` 的 knowledge 分支與 `OLLAMA_*` 錯誤碼只屬於 RPC，這是錯的，沒有照它刪。
   - C4-S1 改為逐一列出要刪與要留的符號。
   - GOALS 的 A3 改寫為已確認的事實。
   - S032 改為整項不納入。
   - C7-S5 的 flag 清單加入 knowledge 操作。
3. **決策紀錄把計劃設計寫得像使用者決策。** 決策紀錄的開頭改為分開寫「使用者決定的內容」與「計劃提出的內容」。新增 P8（不補回 CSL 與 BibTeX 的 DOI 交叉比對）、P9（移除輸出目錄設定與顯示）、P10（近似色合併）。
4. **決策紀錄 §5.2 的 DOI 檢查有誤。** 讀碼確認，`parse_csl` 本來就以回應中的 DOI 為 identity；舊的 BibTeX 檢查比的是 CSL 與 BibTeX 兩種格式是否一致，不是回應與要求是否一致。
   - 原本計劃新增「回應 DOI 必須等於要求 DOI」，這會拒絕 alias DOI，已撤回。
   - 稽核 S105 漏掉這個交叉比對，已在決策紀錄 §2.3 更正。
5. **「書目庫失敗即不可引用」是撰寫時自己加的行為改變，而且需要調整登記順序。** 已撤回，改為維持現行 INV-032：書目庫失敗不改變存檔狀態（P7、決策紀錄 §4.0）。這也解決了審查指出的登記順序問題。
6. **U6 的後果寫得不足。** 已補上：一個 v1/v2 檔案會讓整個專案無法開啟。
7. **幾項驗收檢查改成能觀察到、會失敗的形式：**
   - C3-S2：詞彙常數必須引用 contract。
   - C3-S3：新增測試，確認 result 只送一次。
   - C6-S2：新增壞檔與缺目錄這兩個 fail-closed 測試。
   - C7-S4：grep 也涵蓋 `getattr` 字串形式的私有存取。
   - C7-S6：逐一分類 `service.py` 剩下的方法。
   - C8-S3：遞迴 grep，並包含 `backendClient.`。
   - C8-S6：逐一標明 `App()` 剩下的 hook。
   - C9-S3：hex 之外也檢查 `rgba`。
   - C8-S1：effect 數量改以 C1-S3 的量測為準。
8. **決策紀錄與程式不符時沒有處理規則。** GOALS 的限制改為：允許在本計劃決策紀錄末尾追加更正。
9. **build-log 的狀態值沒有定義。** 已定義四種狀態。

審查提出的「計劃目錄未提交」，是因為審查在 `8f4ca06` 之前讀取，不需要修正。

### CA2 依 Codex 審核修訂計劃（2026-11-19）

使用者轉來 Codex 的唯讀審核，共 5 點。撰寫者逐點對照程式碼確認都成立後修正。

1. **C3 回聲比對會把成功報成失敗。**
   - 讀碼確認：`document.apply` 與 `approval.resolve` 的 request 參數有 `turnId`，result schema 沒有。
   - C3 改為「只比對 request 參數與 result schema 都有的 ID 欄位，清單從 contract 推導」，並列出撰寫時推導出的組合，加上正反兩面的測試。
   - C8-S3 的 `api.ts` 改為引用同一規則。
2. **C5 的刪除順序與文字。**
   - 讀碼確認：`agent/desktop/service.py` 第 107 行 import `skills.citation.storage`。`tests/test_inline_skills.py` 經由 `agent.desktop.service` 間接 import 它，原本的順序會讓測試在收集階段就失敗。
   - 調整順序：C5-S3 先在桌面端移除 import 與 4 處 `resolve_output_dir`，C5-S4 才刪模組，並以 `pytest --collect-only` 檢查。
   - fixture 的 `citation_output_dir` 留到 C5-S4 才刪，避免測試寫進 repo 的 `cite/`。
   - C5-S5 殘留的舊說法「書目庫失敗等於存檔失敗」改成與 P7 一致。
   - 評估分界 commit 改指 C5-S4。
3. **C6 空歷史目錄失去歸屬保護。**
   - 讀碼確認：`_check_catalog_owner` 在沒有對話時也會拒絕他專案。
   - GOALS 的 U3 後果加入這一點，並新增 P11：預設接受這個改變，否決時改寫擁有者標記檔。C6 也寫入兩種做法。
4. **C7 的 Retry Stop 只改桌面端不夠。**
   - 讀碼確認：`agent/ingest.py::LocalWorkScope.finish_stop` 把失敗的清理 task 存在 `_bash_cleanup`，之後每次呼叫都重拋同一個例外。
   - 既有的 `test_failed_stop_cleanup_keeps_new_turn_blocked` 整個替換了 `finish_stop`，測不到這個問題。
   - C7-S5 改為兩層都修，驗收要在底層清理動作注入失敗，並加上 `LocalWorkScope` 的單元測試。
5. **C8 不能全面移除 Vite SSR。**
   - 讀碼確認：`citation_preview`、`documents`、`conversations`、`trust` 這 4 個測試檔以 `renderToStaticMarkup` 渲染元件，例如 `trust.test.ts` 約 250 行的 `ApprovalDialog`。
   - C8-S2 改為：只有純函式測試改成直接 import，元件渲染測試保留 SSR 載入。
   - PLANS 原本寫「前端沒有 DOM 測試工具」，不夠精確，已改為「沒有互動式 DOM 測試，但有靜態渲染測試」。
   - C9 的新元件沿用同一方式做靜態渲染測試。

## 事件

（執行開始後在此依步驟 ID 追加事件：觀察到的改變、執行的指令與結果、證據位置、限制、下一步。）
