# C8 端到端驗收、文件與交付

- **後置條件**：以真實的桌面後端程序完成一次端到端流程並留下證據；文件反映新功能；全套回歸通過；最終彙報完成。
- **目標**：CG1–CG8。
- **相依**：C7。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C8-S1 | **端到端（不呼叫模型）**。在 `$TMPDIR` 建一個暫存專案：`RESEARCH.md`（以後端的初始化流程建立）、一份合成的 Markdown 文件、一份合成的書目（含一筆手寫條目）。以 NDJSON 啟動 `python -m agent.desktop.server`（cwd 與 PYTHONPATH 依桌面主機的作法），依序送出：`workspace.select` → `session.create`（不載入 MCP；整個流程不送任何 `session.turn`，不呼叫模型）→ `session.set_bash_permission {mode:"bypass"}`（Bypass 是 session 層級設定，需閒置 session，見 `service.py:2986`；沒有 GUI 能回應批准，所以必須先切換）→ `document.open` → `bibliography.add`（一個真實 DOI，經公開 Crossref/doi.org 驗證）→ `bibliography.add` 同一 DOI（應為 existing）→ `bibliography.add` 一個 arXiv ID → `bibliography.inspect` → `set_style` APA → `render` → `set_style` IEEE → `render` → `export` docx、markdown、bib → `remove` 一筆未引用條目。每個公開請求在發出前寫入 `evidence/C8-S1/requests.jsonl`，總數不超過 PLANS 的預算。bundle 寫到暫存的 `CITATION_OUTPUT_DIR`，不寫 repo 的 `cite/` | NDJSON 對話（去除不必要的大段內容）存 `evidence/C8-S1/`；觀察：書目只多出新條目、手寫條目不變；同 DOI 第二次為 existing；APA 與 IEEE 的渲染不同；文件雜湊在所有步驟前後相同；三個匯出檔存在且 docx 含渲染後的引用；remove 後條目消失；`citation.json` 與書目中都沒有 abstract。公開 API 失敗時記錄並以重試一次為限，仍失敗就把 add 部分記為環境阻塞，其餘步驟以 C2 的假 provider 結果繼續 |
| C8-S2 | **文件**。更新根目錄 `README.md`（功能說明與「記錄了哪些資訊」若受影響）、`app/skills/citation/README.md` 與 `SKILL.md`（書目庫、key、格式、匯出、Agent 在正文用 key 的規則）、`app/agent/README.md`（若描述到桌面工具）；說明既有 Conda 環境要補裝 Pandoc 的指令（擬定：`conda install -n app -c conda-forge "pandoc>=3,<4"`）；記錄內建樣式的來源與授權。不修改 `AGENTS.md`、`for_agents/` | 以 grep 確認文件中的新方法名、樣式 ID、檔名與實作一致；相對連結都能解析 |
| C8-S3 | **全套回歸與最終彙報**。沙箱外完整 pytest、`npm test`、`npm run build`、沙箱外 `cargo test --locked`；與 C1-S1 基線比較（新增測試使數量增加，既有測試不得變成失敗）。最終彙報（寫在 build-log 末尾並回覆使用者）包含：CG1–CG8 各自的證據與狀態；C4 比較測試的結論（以及 C4-S3 是否觸發）；附件十七剩餘差異與中日文規則結果；A1–A10 假設清單（請使用者確認或修改）；未做 live 驗證的項目（R6、R7）與下列手動檢查清單；`for_agents/` 已過時、建議執行 `$infrastructure`；所有 commit 的步驟 ID 對照 | 四項檢查全部通過，或失敗項有具體紀錄；最終彙報的每個聲明都能對到 evidence 或測試 |

## 手動檢查清單（給使用者，執行者不需完成）

注意：在論文資料夾裡新增文獻會寫入你真正的 `references.json`（這正是 A1 的設計）。只想試用時，先把論文資料夾複製一份再開。

1. 用 `python main.py` 開啟 GUI，開啟論文資料夾（或其副本），開 `proposal.md`：面板列出約 46 個本文引用與未引用的條目；沒有 bundle 的手寫條目顯示 unverified。
2. 點一個引用的位置，編輯器捲到正確段落。
3. 選 APA、IEEE、附件十七各預覽一次，正文不變。
4. 以 DOI 新增一篇已在書目中的論文：書目檔內容不變、該條目變成 verified。
5. 在一個文件回合中用 `/citation` 找一篇新文獻並請 Agent 插入引用（會使用付費模型）：正文出現 `[@key]`，書目多一筆；請 Agent 插入一個不存在的 key 時被拒。
6. 匯出 DOCX，用 Word 開啟檢查引用與參考文獻。

## 完成

見 [PLANS 完成條件](../PLANS.md#完成條件)。
