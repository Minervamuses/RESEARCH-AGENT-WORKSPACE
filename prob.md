# 目前問題紀錄

本文件只整理 citation workflow 與 skill runtime 實測後仍待處理的問題與設計缺口。已完成項目不列入本文件。

## 1. 工具額度耗盡後洩漏 DSML/tool-call 標記

- 每個使用者 turn 的全域工具互動上限為 4。
- 額度耗盡後 graph 改用未綁工具的模型要求直接總結。
- DeepSeek 仍可能把下一次工具意圖輸出成普通文字，例如 DSML `citation_workflow(action="list", page=5)`。
- `_cap_tool_calls()` 只能移除結構化 `AIMessage.tool_calls`，無法辨識普通 content 裡的協定標記。
- finalization 只檢查 citation 格式，沒有攔截 tool protocol leakage，最終由 CLI 原樣顯示並保存。

建議：

- 在 exhausted path 與 finalization 增加 tool-protocol artifact 檢查。
- 若偵測到工具標記，回傳確定性的額度耗盡訊息，或執行一次禁止工具的 repair。
- 加入 DeepSeek/DSML 形式的回歸測試。

## 2. 候選池、分頁與工具額度不匹配

- 內部候選上限 50、每頁 10，但每 turn 只有 4 次工具互動。
- 若模型逐頁掃描全部候選，五頁天然超過額度。
- 目前缺乏對既有候選做年份、venue、work type、關鍵字等條件精煉的 `refine` action。
- 使用者縮小條件時，模型也可能錯誤選擇逐頁 `list`，而不是重新帶 filter 執行 `search`。

建議：

- 內部 retrieval pool 可維持 50，使用者 shortlist 維持 10。
- 新增 server-side `refine`/rerank 能力。
- Skill 指令明定條件改變時優先 refined search，不逐頁掃描。
- 不建議只提高全域工具上限；若仍有需求，應考慮 citation-specific budget。

## 3. 論文概略介紹缺乏 grounding

- `show` 通常只提供 title、authors、year、venue、DOI、URL，以及可能存在的短 snippet。
- Crossref/OpenAlex 候選不保證有 abstract 或全文。
- Citation skill 啟用後，模型目前只有 `citation_workflow`，無法使用一般 Web Search、RAG 或 `read_file` 補足資訊。
- 模型可能依標題、參數知識或推測產生論文介紹，卻未標示資料來源，無法判斷是可靠記憶還是幻覺。

建議：

- 特定論文摘要只有在取得 abstract/full text 時才可作為 grounded summary。
- 只有 metadata 時必須明示「根據標題/metadata 推測」，或先查外部來源。
- 可讓 citation skill 使用 Web Search，或在 workflow 增加 `inspect`/`abstract` action。
- Web evidence 可支援介紹，但保存 verified citation 仍只能走 citation workflow。

## 4. 模型錯誤解釋 citation verification 流程

實測中模型曾宣稱：

- `select` 用標題向 Crossref 做 fuzzy search 找 DOI。
- `confirm` 根據 metadata 自動生成 BibTeX。

實際流程是：

1. Discovery provider（Crossref/OpenAlex 等）建立候選並通常已攜帶 DOI。
2. `select` 從 candidate DOI/URL/snippet/title 抽取 DOI candidate。
3. 以 DOI 向 doi.org 取得 CSL JSON，並查詢 registration agency。
4. 使用者跨 turn 明確確認後，`confirm` 重新取得 CSL JSON，不信任 discovery copy。
5. 透過 doi.org content negotiation 取得 `application/x-bibtex`；不是由模型生成 BibTeX。
6. 系統解析、正規化並驗證 CSL/BibTeX/selected DOI 的一致性。
7. 成功後原子寫入 `reference.bib` 與 `citation.json` bundle。

原因：模型看得到完整 `SKILL.md` 與工具 schema，但 `SKILL.md` 沒描述上述實作；模型看不到 coordinator/provider/storage 程式碼，又沒有 `explain` action，因此以常見系統模式自行補完。

建議：

- 在 skill 的 pinned reference 加入公開、準確的 workflow/data-lineage 說明。
- 明定不得推測工具內部實作；資訊不足時只能描述公開契約。
- 或新增唯讀 `explain`/`receipt` action 回傳確定性說明。

## 5. Confirm receipt 跨 turn 遺失，導致路徑誤判

- `confirm` 的 ToolMessage 本來包含 source ID、DOI、bundle path 與驗證結果。
- 模型可能在最終自然語言回答中省略 bundle path。
- `TurnRecord` 只保存使用者輸入與最終 assistant answer，不保存原始 ToolMessage。
- 下一個 turn 的 source hint 只有 source ID、title 與 cite marker，沒有 bundle path/provenance。
- 模型因此曾錯誤宣稱工具沒有暴露儲存路徑；實際上 `action="source"` 可重新取得 bundle path。

建議：

- Confirm 成功的最終回答強制包含 source ID、DOI 與 bundle path。
- 在後續 prompt 注入 compact verified-source receipt（path、DOI、provenance）。
- 使用者詢問已儲存來源時，skill 應要求呼叫 `source`，不得直接宣稱無法存取。

## 6. Skill tool policy 與「base tools 常駐」語義衝突

基礎工具文件將下列工具描述為 always available：

- RAG search
- history search
- `read_file`
- `bash`（每次執行需使用者批准）

Web Search MCP 在成功載入時也是普通模式可用工具。但目前 active skill policy 使用封閉 allowlist；citation manifest 只要求 `citation.workflow`，因此啟用後實際只剩 `citation_workflow`，其他 base/MCP tools 全部被移除，包括 Web Search 與 `read_file`。`bash` 不是等待批准，而是根本沒有綁給模型。

這與「安全 base tools 常駐、危險工具逐次批准、skill 增量加入能力」的預期不一致，也直接造成論文介紹無法補查與 workflow 實作無法查證。

建議優先決策：

1. 全域方案：安全 base tools 預設繼承，skill capability 採增量授權；只有 explicit deny 才移除。
2. 局部方案：citation manifest 保留 `citation.workflow` required，加入 `file.read` required、`web.search` optional。
3. 不論採哪一方案，`bash` 維持每次呼叫使用者批准。
4. Web/RAG 得到的內容只能作為閱讀證據，不能繞過 citation confirm 成為 verified source。

## 7. Citation discovery 品質與重複候選

- 搜尋結果可能包含與主題關聯薄弱、只借用知名標題的論文。
- 同一作品的 reprint/版本可能佔據多個 candidate ID。
- 目前 related-version grouping 與 DOI identity merge 仍不足以消除所有 reprint 噪音。
- 「頂會」不是 provider 原生欄位，若只靠模型讀 venue 字串判斷，結果不穩定。

建議：

- 強化版本/reprint clustering 與 canonical-work grouping。
- 對 query-title parody/低語意相關結果加 reranking。
- 建立 venue normalization 與可維護的 conference tier/allowlist，而不是交給模型自由判斷。

## 核心設計結論

- `SKILL.md` 是行動指引；citation engine 是由 skill 授權的本地 stateful tool，兩者不應混為同一個黑箱概念。
- 搜尋、介紹與閱讀可以使用 Web/RAG 證據；verified citation 的選擇、確認與寫入仍必須由 deterministic workflow 控制。
- 封裝本身不是問題；缺少透明契約、grounding fallback、compact receipt 與清楚的能力繼承語義，才是目前模型開始腦補的主要原因。
