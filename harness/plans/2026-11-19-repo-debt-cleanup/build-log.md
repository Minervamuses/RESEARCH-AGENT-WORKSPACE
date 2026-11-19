# 執行紀錄

本檔是本計劃唯一的狀態來源。目前只完成了撰寫；**C1–C10 都還沒有開始，也沒有執行過任何實作或產品測試。**

## 目前狀態

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

## 事件

（執行開始後在此依步驟 ID 追加事件：觀察到的改變、執行的指令與結果、證據位置、限制、下一步。）
