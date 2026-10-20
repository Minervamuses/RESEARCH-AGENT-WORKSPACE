# 執行與續作入口

## 開始／續作
以下是未來使用者可直接送出的啟動提示；不是 authoring 階段的執行指令。

> 執行 harness/plans/2026-10-20-web-search-citation/ 計劃。先讀適用 AGENTS.md、[GOALS.md](GOALS.md)、[PLANS.md](PLANS.md)、[build-log.md](build-log.md)，再讀下一個相依已滿足的 build 階段檔。先核對目前 GUI 分支、HEAD、dirty/index、Conda app 與 Linux 工具鏈，對帳已完成的步驟 ID 和 commit，保留既有 app/store/ 等無關工作。依 PLANS 的執行契約在授權範圍內一次連續執行到底；一般問題先記錄並做最小修正，完成可做工作後統一彙報，不在階段之間等待人工 review。每個改動步驟檢查與更新紀錄後都必須本地 commit，成功後再進下一步；禁止 push、創造或切換 branch。沒有硬阻塞時持續完成所有必要階段，不能把未驗證項目宣稱通過。這個請求授權執行計劃列明的改動與本地 commit，不授權新依賴、付費呼叫或發佈。

第一個可執行動作是 PLANS「第一個動作」的唯讀環境與 Git 核對；尚無實作證據時先做 [P1](build/phase-01-citation.md) 的 P1-S1，再 [P2](build/phase-02-search-contract.md)。中斷恢復位置只依 build-log 與實際 Git 狀態決定。

## 修訂
> 僅修訂此計劃以納入我接下來的變更。讀 GOALS、PLANS、build-log 及受影響階段，保留既有完成證據與無關需求，同步更新相依、驗收與 index。除非我另行要求開始，這次不執行產品修改。依已授權政策提交計劃改動，仍不 push、不建立／切換 branch。

## 審查
> 唯讀審查此計劃與 context/source-spec.md、GOALS 的最新使用者決策。檢查需求追蹤、相依、第一步、失敗及中斷恢復、每步 commit 與禁止事項；只回報會誤導或阻塞執行的具體缺口，不改檔或實作，除非另有授權。
