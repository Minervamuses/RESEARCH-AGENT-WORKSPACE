# P2：引用加入、送出、重試與歷史還原

前置：P1 完成。目標：G1、G2、G3、G4、G8、G12。
結束條件：文件與聊天引用完整經過現有 turn persistence，使用者能檢視每次提交內容；所有文件寫回仍走既有版本檢查。

依據：[GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)、[D4–D7](../context/contracts.md)。不重建 Agent、editor 或 history，不增加另一份引用資料庫。

## 有界實作

| 步驟 | 工作 | 檢查／交付 |
|---|---|---|
| P2-S1 | 在現有 models/repository 加 v2 submittedContext 與 v1 reader；同輪 equality／immutable fields／大小檢查都涵蓋 context，pending-first 持久化 | 先用既有 canonical repository 測試做 round-trip、失敗、retry 與舊資料相容 |
| P2-S2 | 同步 contract/fixtures、Python/TS/Rust validator、transcript DTO、fixture；保存原背景及 references，不將 hidden semanticInput 直接當 UI 解析協議 | 三層接受有效 document/chat union，拒絕錯誤欄位、range、跨 project；不關閉 strict validation |
| P2-S3 | 在原 DocumentEditor 接選區附近「加入聊天」，點擊前保存 range，點擊時複製完整 snapshot；在原 composer 加可展開/移除卡片與焦點轉移 | A08、A09；不改保存、不發送，選取失焦不能使內容消失 |
| P2-S4 | 在既有 ConversationTurns 訊息容器標定穩定來源，捕捉單則訊息的可見正文選段，加入 chat card | A10；不改 SafeContent 安全呈現，role/source 可辨識 |
| P2-S5 | 將 draft/submitted/retry/restored references 納入現有 conversation reducer；首次提交 frozen payload，後端 retry 使用 durable original context/semanticInput | A11、A12；原 turnId 不允許改引用；修改草稿建立新 turn，舊失敗紀錄保留 |
| P2-S6 | 分開引用、目前背景與 writable target。對引用編輯用 referenceId 固定原 snapshot；無引用行號操作保留；chat 不具文件 target | A13、A14；沿 document.prepare/apply/undo，版本檢查不能由 Bypass 繞過 |
| P2-S7 | 將卡片／submitted context／history retry 加入 P1 的切換與過期結果保護；檢查 1 MiB/2 MiB 界線，保留超限草稿 | A15；關閉或換專案不帶走引用、不重建引用內容 |

## 必要驗收

| 編號 | 操作／輸入 | 預期結果 |
|---|---|---|
| A08 | 含重複段落、emoji、CRLF、長行的文件，選第二個相同段落；點旁邊「加入聊天」 | 卡片來源檔、原始行範圍、摘要正確，可展開全文／移除；焦點在 composer；尚未新增 conversation turn，磁碟 bytes 未變。鍵盤亦能觸發加入 |
| A09 | 加入 A 段後移游標、重選 B 段、編輯原文件；再加入 B，移除其中一張 | 第一張仍是加入當時 A 的文字/範圍/版本；卡片互不改變；不跟隨 current selection；正確區分當前背景與 frozen 引用 |
| A10 | 在已有 user/assistant 歷史訊息的 Markdown 強調／連結／段落反白，加入聊天；再跨兩則訊息反白 | 單則保留可見文字和正確 project/session/turn/role/range/hash，UI 標聊天來源；跨訊息明確提示重選，沒有偽造文件路徑。卡片可展開來源全文選段 |
| A11 | 帶文件+聊天引用送出 fake fail-once，修改目前 editor 後按原 retry；另測改草稿引用後再送 | 原 retry text/context/turnId 完全相同、只一份該輪 user turn；前一失敗不因新游標而改內容。修改引用的再次提交用新 turnId，不竄改原 turn；改成 Ask 後不能在背景以舊 Bypass retry，須明示設定差異並以目前設定另送新回合 |
| A12 | pending/failed 含引用已落盤，關閉重開 App、選同專案及歷史；原檔後來改名或移除；重開 failed turn 再 retry | 歷史卡片可還原全部 frozen text/source/version；不讀現檔來替換。pending 依既有 recovery 變 interrupted，不自動執行；retry 使用原 durable submission。文件不可用時不能代用別檔。v1 顯示無引用，不能猜測；v1 legacy retry 保留原 semanticInput、不解析成虛構卡片 |
| A13 | 無引用但目前開文件，送「修改第 40–45 行」；再帶 chat 引用含「修改第 1 行」文字；另測多文件引用要求含糊 | 正常行號以提交時背景處理；chat 引用內容不被當作使用者指令／document range；明確寫回目標不清楚時先問，不能以最後卡或游標猜測 |
| A14 | 引用文件加入後插入行／改 editor／外部改 disk；Ask、Bypass 各一次；選第二個重複段落做修改；重試已保存的 call | 原版本失配進既有 conflict，沒有舊行號誤覆寫；允許的修改只變指定原範圍，其餘 bytes 保持。Bypass 不免版本檢查。已保存的 call 不自動重播；Undo 語意不變 |
| A15 | 有 references-only 草稿或文字+references 嘗試換專案／同專案換 conversation；A→B→A 延遲引用相關回應；提交超過現有實際序列化上限 | 取消保留原稿；只有明確捨棄才清除且不能帶到 B；舊結果不污染新狀態；超限顯示可處理原因並保留完整草稿，不截斷或悄悄 drop references |

特別檢查：選取內容含惡意「忽略 Permission」文字，仍只作引用資料，實際工具授權不變；加入 chat 不把其原文行號餵給背景 resolve_range。

### 舊版重試的安全界線

v1 沒 submittedContext，但 canonical semanticInput 已保存：重試須沿原 semanticInput，不能用目前 editor 附加新資料。無法恢復可寫 snapshot 的 legacy 文件回合只允許保留歷史／提示重新發起新問題，不猜 snapshot 或重播未知文件副作用；明確告知此限制，原資料不改寫成假引用。一般無文件副作用的 legacy retry 維持既有行為。這是對缺少歷史資料的可見限制，非空白成功。

## 現有檢查入口

```bash
# cwd: app，activate app
poetry run pytest tests/test_conversation_repository.py tests/test_session_persistence.py tests/test_desktop_conversations.py tests/test_desktop_documents.py tests/test_desktop_document_service.py tests/test_desktop_protocol_contract.py -q

# cwd: app/desktop
node --test --experimental-strip-types tests/documents.test.ts tests/conversations.test.ts tests/protocol.test.ts
```

開發時選相關 test node，整組只是本階段可能涉及的檔案；不為每一步重跑全部。最小新增測試放原檔內；目前 Node 單元測試無法證明選段 popover、焦點及 native Monaco 事件，A08–A10 的實際互動須於 P4 驗證。

輸出：可持久化且型別明確的引用、可還原的 submission、原 editor 背景及版本衝突行為；P3 只重排其呈現，不另改生命週期。
