# Issue 09 — Desktop Thinking Effort 多段位控制：目標

## 目的與背景

依 [Issue 09](../09-desktop-thinking-effort-control-deferred.md)，未來 Desktop
需要 Thinking Effort button，讓使用者以多個段位調整 thinking effort。
現有 Normal／Extended 是兩種工作流；Extended 包含 prompt rewrite、
proposer、reviewer／reviser 與 fusion，不能等同 provider reasoning effort。

本次只撰寫計劃，並依使用者指示 commit 所有變更、push 及核對同步。
原 issue 的未決產品契約繼續有效；本 bundle 描述定案後的完整路線，
不代選段位、映射或保存政策，也不授權實作。

## 預期成果

- 使用者能從 Thinking Effort button 選擇經確認的段位，辨識目前有效選擇。
- 成功選擇確實影響下一回合，而非僅改畫面標籤或 session snapshot。
- 新對話、A→B→A、restart 及舊資料讀取符合確認的保存與相容契約。
- 現有 CLI、Normal／Extended、Skill 和對話保存依核准相容策略維持可用。

## 成功條件

以下是未來實作驗收，並非本次 authoring 已完成的功能。

- [ ] 三項產品決策均有使用者明確答案，沒有任意補入的段位或參數。
- [ ] button 可用鍵盤／滑鼠操作；選擇本身不送出聊天回合，不覆蓋草稿。
- [ ] 同一 session 先選段位甲、送出代表性問題，再選乙並送出同一問題，
      觀察到的 workflow／request 符合各自映射，包含已建立 model 的情況。
      甲／乙指兩個實際核准值，不是新增段位名稱。
- [ ] 新對話、A→B→A、restart 和舊對話讀取逐項符合定案契約；
      historical turn metadata 不被擅自當成下一回合偏好。
- [ ] 無效／不支援設定、busy、pending approval、失敗及 stale response
      均有明確結果，不顯示尚未生效的選擇或部分更新。
- [ ] Python、JSON contract、TypeScript、Rust 對 request／snapshot 一致；
      CLI 與 GUI 遵循同一後端語意及核准的 CLI 相容方式。
- [ ] Citation、Skill installer、Bash approval、final-only 回答、
      cancellation／retry 與 canonical conversation integrity 不因新控制退化。
- [ ] 真實 Linux Desktop 操作和必要離線檢查有證據；fixture／fake model 成功
      不被宣稱為真實 provider 的效果、品質、速度或成本改善。

## 範圍

定案契約必需的 session 控制、model／workflow 生效、Desktop protocol／button、
狀態生命週期、最小相應測試與既有用法說明。
CLI 語法、持久格式及受影響角色範圍須定案後才凍結。

## 非目標

- Issue 01–08、Bash permission 或 ZIP installer 的一般改善。
- 通用 provider capability 平台、model registry、benchmark／模型評比、
  GPU 推論、token 最佳化、回答品質保證。
- 重寫 Extended pipeline、一般 UI 改版、另建服務／storage／concurrency 架構。
- 未核准的 dependency、public API、protocol、schema 或資料遷移。
- 本次實作 production／tests、修改 AGENTS 或原 issue；Git 同步另有明確授權。

## 保留行為與限制

- 現況是預設 normal；同 backend A→B→A 保留各對話 mode，
  新對話及 restart 後 normal。除使用者核准差異外保留此基準。
- Extended 是現有多角色工作流；其保留／取代／並存方式必須明示。
- Canonical conversational turn 的 thinkingMode 只接受 normal／extended，
  display-only 為 null；歷史 metadata 並非 preference storage。
  舊資料不得無聲重寫或因此無法讀取。
- 保留 service idle／approval gates；citation 與 installer 的 normal-only
  邊界不能被新 enum 繞過，installer 結束後的選擇恢復須正確。
- 根 AGENTS 與 Personal Engineering Defaults 要求 Linux、Conda app、
  Poetry、LF、既有測試 seam、短回饋與最小變更。
  Windows 只作 WSL launcher；不執行 live provider 或真實使用者 store 驗證。
- 上述現況來源詳見 [PLANS.md](PLANS.md) baseline；
  授權與停止條件由該文件唯一管理。

## 未知與待決事項

以下尚未定案；不阻擋本次 authoring／Git 同步，但阻擋功能實作。
使用者答案在本節唯一保存，不另建決策狀態系統。

| 使用者需決定 | 必須明示的內容 | 為何不能由程式推導 |
|---|---|---|
| 段位 | 數量、名稱、穩定值、順序、預設；與 Normal／Extended 的 UI 關係 | issue 明確未指定 |
| 行為映射 | provider effort／model／workflow 或明示組合；適用主模型與哪些角色；不支援時可見結果；CLI 相容方式 | factory 尚無 effort，Extended 是不同流程 |
| 保存範圍 | 新對話、同程序切換、重啟各自行為；對話／全域偏好；是否記錄新回合欄位及舊資料相容 | control snapshot 與 durable turn 是不同邊界 |

不先指定新 enum／欄位、provider 參數、model slug、migration 或數值。
定案後如採 provider effort，須確認當時已 pin integration 與官方文件；
SDK 接受 kwargs 不代表遠端一定生效。
GUI 可操作性、fixture 適配及編譯 cache 由相應 phase preflight 查證。

## 來源

- [AGENTS.md](../../AGENTS.md)、本次 Personal Engineering Defaults 與 2026-09-12 指示。
- [Issue 09](../09-desktop-thinking-effort-control-deferred.md)。
- app/agent/session.py、cli/slash_commands.py、llm/openrouter.py、llm/thinking.py、
  graph.py、thinking/orchestrator.py、desktop/service.py、
  conversations/models.py／repository.py。
- app/desktop/protocol/v1/contract.json、src/protocol.ts、src-tauri/src/protocol.rs、
  src/App.tsx 及相應 tests；精確位置和命令見 PLANS 與 phases。
