# 目前問題紀錄

本文件整理 citation workflow 與 skill runtime 實測後仍待處理的問題，並保留最近一次阻斷級回歸的修復紀錄。（最近一次更新：2026-07-12。）

## 2026-07-12 批次保存回歸（已修復）

CLI 實測要求一次保存三篇論文時發現：舊 `select` 會讓其他 candidate 的 match 靜默失效、`confirm` 成功即清空整個候選池，加上強制跨 turn，導致批次保存從狀態機層面不可完成；三篇實際只保存一篇。舊 finalizer 又只在有成功 receipt 時取代模型草稿，因此部分或全數失敗可能完全被遮蔽。

本次修復：

- `select`/`confirm` 支援最多 10 個 ordered identifiers，單次呼叫在 session busy lock 內序列執行；match 可跨 candidate 累積，成功 confirm 只消耗該 match，失敗史亦隔離到單一 match。
- 當前請求本身可構成保存授權，模型可在同 turn 完成 select→confirm，不再硬性多問一輪；否定、條件、疑問與不明確語氣仍禁止 confirm。
- 每個 candidate 依 0/1/多 match 分流；多 DOI 版本必須明確消歧，且舊 pending 與本次授權結果分區，不能被順帶 confirm。
- confirm 改傳單一 batch artifact，內含逐筆嚴格 receipt 與只允許 status/reason code 的 failure；finalizer 在有任一 success 或 failure 時皆確定性渲染，全數失敗不再退回模型草稿，provider 自由文字不進可信通道。
- 預設輸出移至 workspace 根目錄 `cite/` 並納入版控；只有 `.staging-*` 被忽略。config/env override 優先序保留，非 workspace 的安裝環境仍有平台 user-data fail-safe。

並行呼叫造成的 busy 抖動現以「單呼叫 batch identifiers」與 skill 明定不得平行呼叫緩解；仍保留為 live model 行為觀察項，若模型持續拆成多個並行呼叫，再考慮 graph/tool-call 正規化。

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

## 2. Turn 可能以空回應結束，CLI 顯示為「中斷」

2026-07-11 實測中一個 session 內出現三次：工具成功返回後，assistant 完全沒有文字輸出，turn 直接結束。

2026-07-12 citation 批次升級的 live smoke 仍重現一次：替代措辭「第3篇跟第7篇的 bibtex 存起來」已取得工具結果，但模型未完成後續流程，finalizer 正確顯示確定性空總結 fallback。批次狀態機的單元／E2E 測試均通過；此項仍屬 live model 遵循度問題。

- 一次發生在只用了 1 次工具的搜尋 turn（非額度耗盡），使用者追問「剛剛中斷了?」。
- 兩次發生在工具用滿 4 次之後（1 次 citation + 3 次 bash），疑似 `_cap_tool_calls()` 剝掉 tool_calls 後留下 `content=""` 的 AIMessage，graph 路由到 END。
- `finalize_and_record` 與 CLI 都接受空字串答案：空 turn 照樣寫入 TurnRecord，畫面上什麼都沒有。
- 連鎖 UX 失效：使用者以為 CLI 卡在 bash 批准提示，連續輸入 `y`，這些 `y` 被當成新的 user turn 消耗掉。

建議：

- 在 graph 結束路徑或 finalization 加空答案 guard：偵測到空/純空白最終回答時，改走一次禁止工具的總結重試，或回傳確定性訊息（例如「工具結果已取得但總結失敗，請再問一次」）。
- CLI 對空回應至少顯示明確占位訊息，不得靜默。
- 回歸測試：工具返回後模型輸出空 content、以及 tool_calls 被剝除後留下空 content 兩種路徑。

## 3. 候選池、分頁與工具額度不匹配

- 內部候選上限 50、每頁 10，但每 turn 只有 4 次工具互動。
- 若模型逐頁掃描全部候選，五頁天然超過額度。
- 2026-07-11 實測新增：status/sources/source 這類內省 action 與檢索共用同一個額度。一句「出了什麼問題?」燒掉 3 次呼叫；一個 turn 內 1 次 citation + 3 次 bash 直接用滿額度並觸發問題 2 的空輸出。
- 目前缺乏對既有候選做年份、venue、work type、關鍵字等條件精煉的 `refine` action。
- 使用者縮小條件時，模型也可能錯誤選擇逐頁 `list`，而不是重新帶 filter 執行 `search`。

建議：

- 內部 retrieval pool 可維持 50，使用者 shortlist 維持 10。
- 新增 server-side `refine`/rerank 能力。
- Skill 指令明定條件改變時優先 refined search，不逐頁掃描。
- 考慮把唯讀內省 action（status/sources/source/show）排除在額度外，或給 citation-specific budget；不建議只提高全域工具上限。

## 4. 論文概略介紹缺乏 grounding

- `show` 通常只提供 title、authors、year、venue、DOI、URL，以及可能存在的短 snippet。
- Crossref/OpenAlex 候選不保證有 abstract 或全文。
- 全域工具重構後，citation skill 已可使用 Web Search、RAG 與 `read_file` 補查，但 skill 指令尚未規範何時必須補查、何時必須標示推測。
- 模型可能依標題、參數知識或推測產生論文介紹，卻未標示資料來源，無法判斷是可靠記憶還是幻覺。

建議：

- 特定論文摘要只有在取得 abstract/full text 時才可作為 grounded summary。
- 只有 metadata 時必須明示「根據標題/metadata 推測」，或先查外部來源。
- 可在 workflow 增加 `inspect`/`abstract` action，減少對外部補查的依賴。
- Web evidence 可支援介紹，但保存 verified citation 仍只能走 citation workflow。

## 5. 模型錯誤解釋 workflow 內部實作與儲存位置

早前實測中模型曾宣稱 `select` 用標題對 Crossref 做 fuzzy search、`confirm` 由模型生成 BibTeX。2026-07-11 實測再次重現，且更嚴重：

- 使用者問「你存在哪裡?」，模型先用三次 bash 在 **package tree**（`skills/citation/`、`find . -path "*/citation*"`）撈儲存檔案——方向錯誤（當時 bundle 預設寫入平台 user-data；現已改為 workspace 根目錄 `cite/`，仍不在 `app/skills/citation/`），白白燒掉三次使用者批准。
- 全程沒有呼叫 `action="source"` 取得 bundle path。
- 最後斷言引用「存在 citation workflow 的 session 狀態中（記憶體內），不是磁碟上的檔案」——與事實相反（confirm 成功即原子寫入 `reference.bib` + `citation.json`），也和它前一輪自己說的「BibTeX 已儲存」矛盾。

實際流程（模型應描述的公開契約）：

1. Discovery provider（Crossref/OpenAlex 等）建立候選並通常已攜帶 DOI。
2. `select` 從 candidate DOI/URL/snippet/title 抽取 DOI candidate。
3. 以 DOI 向 doi.org 取得 CSL JSON，並查詢 registration agency。
4. 當前請求已構成保存授權時（可與 select 同 turn），`confirm` 重新取得 CSL JSON，不信任 discovery copy。
5. 透過 doi.org content negotiation 取得 `application/x-bibtex`；不是由模型生成 BibTeX。
6. 系統解析、正規化並驗證 CSL/BibTeX/selected DOI 的一致性。
7. 成功後原子寫入 `reference.bib` 與 `citation.json` bundle（預設位於 workspace `cite/`，不在 app/rag/skill package tree）。

原因：模型看得到完整 `SKILL.md` 與工具 schema，但 `SKILL.md` 沒描述上述實作與儲存位置；模型看不到 coordinator/provider/storage 程式碼，又沒有 `explain` action，因此以常見系統模式自行補完。

建議：

- 在 skill 的 pinned reference 加入公開、準確的 workflow/data-lineage/儲存位置說明。
- 明定：使用者詢問儲存位置或已存來源時，必須呼叫 `action="source"`，不得用 bash 掃目錄、不得推測內部實作。
- 或新增唯讀 `explain`/`receipt` action 回傳確定性說明。

## 6. Confirm 收據跨 turn 遺失；gate 封鎖會把成功 confirm 偽裝成失敗

既有問題：`confirm` 的 ToolMessage 含 source ID、DOI、bundle path，但 `TurnRecord` 只保存最終 assistant answer；下一 turn 的 source hint 沒有 bundle path/provenance。

2026-07-11 實測發現更糟的交互：

- 「儲存」那一輪 confirm **實際成功**（來源已寫入、後續查到 `identity_verified`），但模型同輪草稿含 raw DOI，整個回答被 citation gate 換成封鎖訊息。
- 副作用已提交、敘述被丟棄：TurnRecord 只剩封鎖訊息，confirm 成功的事實完全不見。
- 下一輪模型只看得到「被封鎖」，於是 confabulate 出自相矛盾的解釋（「我沒有呼叫 confirm」「對話狀態過期、c5 已不在候選清單」），而來源明明存在。

建議：

- Gate 封鎖訊息必須保留該輪已完成的工具事實：例如「confirm 已成功（source ID、DOI、bundle path），但回應文字違規已被攔下」；或封鎖後執行一次禁止 raw DOI 的 repair 重寫，而不是直接丟棄。
- Confirm 成功的最終回答強制包含 source ID、DOI 與 bundle path。
- 在後續 prompt 注入 compact verified-source receipt（path、DOI、provenance）。

## 7. 自然語言確認指令未映射到 confirm action

- 模型要求使用者輸入「確認 m1」；使用者回「儲存」——語義等價，但模型沒有轉成 `action="confirm"`，反而輸出帶 raw DOI 的說明文字觸發 gate（見問題 6）。
- 模型在 confirm 之前的回覆就把 DOI 字面值寫進 prose（markdown link 形式），gate 攔下是正確行為，但整個互動以硬錯誤收場，沒有 repair。

建議：

- SKILL.md 明定：使用者以任何形式表達確認（儲存／確認／OK／要這篇／就這篇）時，一律呼叫 `action="confirm"`；有歧義才追問。
- 明定 confirm 之前的所有回覆不得出現 DOI 字面值；提及候選一律用 cX/mX 編號。
- 加入「儲存」等同義詞觸發 confirm 的行為測試。

## 8. Citation discovery 品質與重複候選

- 搜尋結果可能包含與主題關聯薄弱、只借用相近字面的論文。2026-07-11 實測：「AI 推論加速」的候選含 POMDP inference（「推論」另一語義）與無 venue 的 stochastic computation 條目；SSRN/低審查來源與 IEEE Access、FPGA 2025 混排，無任何分層提示。
- 年份標示不一致：使用者要求「近三年」（2026-07 時點應為 2023–2026），模型標題寫「2022–2025」，清單卻含多筆 2026 論文。
- 同一作品的 reprint/版本可能佔據多個 candidate ID；related-version grouping 與 DOI identity merge 仍不足以消除所有 reprint 噪音。
- 「頂會」不是 provider 原生欄位，若只靠模型讀 venue 字串判斷，結果不穩定。

建議：

- 強化版本/reprint clustering 與 canonical-work grouping。
- 對 query-title parody/低語意相關結果加 reranking。
- 建立 venue normalization 與可維護的 conference tier/allowlist，而不是交給模型自由判斷。
- Search 回應應回帶實際使用的年份 filter，skill 指令要求模型照實轉述，不得自行改寫範圍。

## 核心設計結論

- `SKILL.md` 是行動指引；citation engine 是由 skill 授權的本地 stateful tool，兩者不應混為同一個黑箱概念。
- 搜尋、介紹與閱讀可以使用 Web/RAG 證據；verified citation 的選擇、確認與寫入仍必須由 deterministic workflow 控制。
- 封裝本身不是問題；缺少透明契約、grounding fallback 與 compact receipt，才是目前模型開始腦補的主要原因。
- Gate 與 budget 這類安全機制需要「失敗出口」：封鎖或耗盡時要嘛 repair、要嘛給確定性訊息，靜默空輸出與丟棄成功收據都會製造新的失效模式。
