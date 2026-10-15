# 執行入口

本次只撰寫計畫。下列是供使用者日後選用的文字，不是現在的執行命令。規則與成本以 [PLANS.md](PLANS.md) 為準；狀態只讀 [build-log.md](build-log.md)。

## 開始／恢復

> 請在 Minervamuses/RESEARCH-AGENT-WORKSPACE 的 GUI 分支，執行 harness/plans/2026-10-15-gui-project-workspace/ 的完整計畫。我接受 context/contracts.md 所列 RESEARCH.md metadata、canonical v2 與必要跨層協議／工具參數擴充。先核對 applicable AGENTS.md 與 Linux/Conda app 環境，依序讀 GOALS.md、PLANS.md、context/contracts.md、build-log.md，再讀下一個依賴已滿足的 build/phase 檔；核對實際 diff 與紀錄後，依 PLANS.md 持續完成已授權階段。不要猜測或自行搬移真實舊對話，不新增依賴，不呼叫付費 provider；Git 操作及昂貴檢查仍依該契約另行取得批准。不要把計畫中的預期結果當成已執行證據。

第一個可執行動作是 P1-S1 的唯讀 runtime/branch/dirty 檢查；恢復時則先與 build-log 及實際檔案核對，再選未完成且前置滿足的步驟。未授權 schema 提案時只執行不依賴它的工作。

## 只修訂計畫

> 請僅修訂 harness/plans/2026-10-15-gui-project-workspace/，納入以下新需求：由我在這段文字後提供的變更。先確認目標及實際狀態，保留未受影響的需求與已完成證據；同步更新受影響的 contracts、phase 驗收、依賴、索引及交接入口。本次不執行功能實作。

## 唯讀審核

> 請唯讀審核 harness/plans/2026-10-15-gui-project-workspace/ 與 GUI 分支。檢查需求遺漏、未經證實的基線、資料相容性、權限及版本檢查、可執行性、驗收和中斷恢復。指出具體缺口及位置，不因偏好其他寫法而擴大 scope；未另獲授權不要改計畫或 production code。
