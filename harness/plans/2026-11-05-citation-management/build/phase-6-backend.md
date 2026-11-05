# C6 協定與後端方法

- **後置條件**：六個 `bibliography.*` 方法在 `contract.json`、`fixtures.json`、Python、TypeScript、Rust 一致定義，桌面後端都已實作並有測試。
- **目標**：CG3、CG4、CG5 的後端部分。假設 A2、A4、A5、A10；風險 R5。
- **相依**：C3（解析與報告）、C5（完整的樣式清單）。

## 方法（擬定的形狀；欄位名稱可調整，但四份定義必須一致）

| 方法 | 參數 | 結果 | 寫入 | 批准 |
|---|---|---|---|---|
| `bibliography.inspect` | 可選 `documentContext`（目前編輯器快照，含未儲存文字） | 書目路徑與指紋、條目清單、目前文件的使用位置與首次出現順序、缺漏、未引用、重複 DOI、書目錯誤、目前樣式 ID、可用樣式清單 | 無 | 無 |
| `bibliography.render` | `documentContext`、`styleId` | 逐筆引用渲染字串（附 UTF-16 位置）、參考文獻條目 | 無 | 無 |
| `bibliography.set_style` | `styleId` | 新樣式 ID | `RESEARCH.md` metadata 的 `citationStyle` | 無（使用者在 GUI 的設定動作） |
| `bibliography.remove` | `key`、`libraryFingerprint` | 新指紋 | 書目檔 | 無（A10；被引用時由 GUI 先確認） |
| `bibliography.add` | `identifier`（DOI 或 arXiv ID） | key、`added`/`existing`、驗證狀態 | bundle 與書目檔，連網 | 沿用 `citation.save`（Ask 模式下詢問） |
| `bibliography.export` | `documentContext`、`format`（`docx`、`markdown`、`bib`） | 寫出的檔案路徑 | 文件旁的新檔（A5） | 無（A10） |

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C6-S1 | **協定定義**。依 commit `d87ee6f`（`session.rename`）的作法，在 `app/desktop/protocol/v1/contract.json` 加入六個方法的參數與結果結構、大小上限；`fixtures.json` 每個方法至少一個合法與一個非法範例；更新 `app/desktop/src/protocol.ts`、`app/desktop/src-tauri/src/protocol.rs`；`protocolVersion` 維持 1。錯誤沿用既有錯誤碼（例如 `PROTOCOL_INVALID`、`BUSY_TURN`、`APPROVAL_DENIED`）；只有確實需要時才新增（例如書目衝突），並在四處同步 | `tests/test_desktop_protocol_contract.py`、`desktop/tests/protocol.test.ts`、Rust protocol 測試（沙箱外）全部通過；每個新 fixture 在三種語言的驗證器中結果一致 |
| C6-S2 | **後端實作**。在 `DesktopService.dispatch` 加入六個處理器，邏輯放在 `app/skills/citation`（C2–C4 的模組），service 只做轉接：<br>• 所有方法要求已開啟專案；寫入類方法（set_style、remove、add、export）在有進行中的回合時回 `BUSY_TURN`。<br>• `inspect`/`render`/`export` 以 `documentContext` 的文字為準（與文件回合同樣的快照驗證）；`.tex` 文件的 `render` 與 `export docx/markdown` 回明確的不支援訊息（A6），`bib` 可用。<br>• `set_style` 驗證樣式 ID 在清單中。catalog 目前只有 `initialize_project` 會寫 metadata，而且只在沒有 metadata 區塊時寫（`catalog.py:623` 起的 `initialize_project`，`metadata is None` 分支在 `:647`），沒有能改寫既有區塊的函式，所以要在 `catalog.py` 新增一個：只替換 metadata 區塊的 JSON，保留其他鍵與區塊外的規則文字（逐位元組），寫入前比對整檔指紋，暫存檔、fsync、`os.replace`。改寫會改變整檔的 `researchFingerprint`（`catalog.py:555`；GUI 在 `App.tsx:1668` 當作 `expectedFingerprint`），測試要涵蓋：寫入後重新 inspect 得到新指紋、規則文字與其雜湊不變、下一個回合的送出仍成功（風險 R5）。<br>• `remove` 指紋不符時回衝突，不寫入；bundle 不動。<br>• `add` 走與 `citation_workflow` save 相同的驗證與儲存路徑（DOI → doi.org CSL + BibTeX；arXiv → 授權路徑），再併入書目。它在回合外執行，所以不能用回合內的 `_desktop_operation_approval`（沒有進行中的回合時直接回 False，`service.py:2343-2361`）；比照 `_knowledge_ingest_file`（`service.py:3362`）呼叫 `_require_operation_approval`（`service.py:2333`），操作名稱 `citation.save`，payload 含 bundle 目錄與書目路徑。citation 服務透過 `CitationSessionPolicy`（`app/agent/skills/citation/session_policy.py`）或同一個 provider hub 建立，與回合內的設定相同。拒絕或逾時不寫任何東西。<br>• `export` 依 A5 命名，原子寫入，回傳路徑；原始文件不變 | 每個方法的測試（以假 provider，不連網）：成功、未開專案、忙碌、樣式 ID 不存在、指紋衝突、Ask 拒絕時無寫入、Bypass 直接執行、`.tex` 不支援的回覆、匯出後原文件雜湊不變、`set_style` 後送出新回合成功、metadata 的其他內容與規則文字不變。focused：`tests/test_desktop_*.py`、`tests/test_project_permissions.py` |

## 失敗與恢復

- 若 `_require_operation_approval` 不能直接用於 `bibliography.add`，以最小改動讓它使用同一個批准佇列，並記錄差異。
- 若 `set_style` 寫入 metadata 會讓既有的提交情境驗證失敗，改為「metadata 改變不影響規則文字雜湊」的實作並加測試；不得放寬規則文字的驗證。

## 交付給後續階段

六個方法的最終欄位名稱、錯誤碼與 fixtures，供 C7 使用。
