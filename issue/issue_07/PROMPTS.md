# Issue 07 — 可重用執行提示

以下是供使用者日後選擇傳送的提示文字，不是本次已授予的實作權限。
單純讀取此文件不授權新增跨程序鎖。實作與新同步機制的具體核准見 PLANS。

## 啟動／續作（Start / Resume）

```text
請執行 /home/minervamuses/research-agent-workspace/issue/issue_07 計劃。
我明確核准 PLANS.md 中的 Linux 非阻塞 flock 方案：在既有 state root
使用固定 .apply.lock，同 revision 的 apply 衝突立即報錯，沿用現有
threading lock、registry 格式和 CLI／Desktop 契約。
依該文件的局部檔案與離線測試範圍自主完成；其他 approval gates 維持。

修改前依序閱讀：
1. 所有 applicable AGENTS.md，並完成 root／runtime gate。
2. issue/issue_07/GOALS.md。
3. issue/issue_07/PLANS.md。
4. issue/issue_07/build-log.md。
5. 根據 log 與 roadmap 選擇第一個尚未 Complete、且依賴均 Complete
   或無依賴的 phase，閱讀其 phase file。
6. issue/issue_07/context/、issue/issue_07/code_review/ 中相關的既有文件；
   不存在就略過，不建立空檔。
7. 該 phase 涉及的 live code、tests 與 current diff。

以 build-log.md 為唯一 runtime status source；重新核對 live repository，
保留既有工作。文件聲稱 Complete 但必要 evidence 不成立時，先追加修正，
不能靠對話記憶或舊狀態跳過驗證。

每個 eligible phase：
- 做 read-only preflight，重述範圍、非目標、planned checks 與停止條件。
- 解決必要 prerequisites；缺少授權或關鍵證據時記錄 Blocked 並停止相關工作。
- 只實作選定 phase，使用有因果意義的 Red／Green 及最少必要 cleanup。
- 跑該 phase 的 required verification；失敗先診斷修正，不開始 dependent phase。
- 在 issue/issue_07/build-log.md 記錄實際命令、環境、結果、限制與失敗嘗試。
- 重大發現才寫入 context；實際 review 才記錄 code_review。
- 新證據推翻後續工作時，先修訂 PLANS 與受影響的未開始 phase，
  保留原目標及已發生的 evidence，不擴張授權。
- 依 PLANS 的 autonomous mode 繼續至整體完成或明列的停止條件；
  不為修正失敗而無限重跑，不順便處理其他 issue。

交付實際改動、驗證結果與未驗證限制；未獲另行授權不得執行 Git mutation、
依賴／格式變更、外部或不可逆操作。完成即停止。
```

## 執行單一階段

```text
只執行 issue/issue_07/phases/phase-01-cross-process-apply-lock.md。
我明確核准 issue/issue_07/PLANS.md 擬採的固定 .apply.lock、
Linux 非阻塞 flock 方案及其局部實作／離線驗證範圍。
先按 issue/issue_07/PROMPTS.md 的 Start / Resume 讀取順序核對 live state
與依賴；依 PLANS 的授權和停止條件完成此 phase，寫入實際 log／重大 context，
驗證失敗不得 Complete。結束後停止，不執行其他工作。
```

## 驗證／審查計劃的實作

```text
請核對 issue/issue_07/GOALS.md、PLANS.md、build-log.md、phase file、
相關 context 與實際 diff，只審查不修正程式。
逐項比對 acceptance 與 observed evidence，特別檢查整段持鎖範圍、
失敗方沒有成功回報或安裝副作用、child crash 後釋鎖，以及入口契約。
先重用已執行的輸出；只跑授權內且尚缺的 focused checks，
不因 review 再跑完整 suite。若要寫審查結果，只在確實 review 後
建立 issue/issue_07/code_review/phase-01-cross-process-apply-lock-review.md。
提供具體 findings 與未驗證項，不將計劃文字當成通過證據。
```

## 矛盾證據後修訂計劃

```text
請依 issue/issue_07/GOALS.md、PLANS.md、build-log.md、phase files、
重大 context 與 live repository，找出新證據否定的假設。
只修訂受影響的 roadmap／未開始 phase；active phase 可在原授權內澄清。
保留已完成與失敗紀錄，以追加更正記錄原因。
穩定目標改變須由我決定。這次只修計劃，不實作或修改 AGENTS.md。
```

## 最終整合核對

```text
依 issue/issue_07/GOALS.md 與 PLANS.md 的整體完成標準，
核對 live diff、build-log 及代表流程證據。
重用已完成的 required checks；未執行的檢查須按既有授權／成本限制處理，
不得重跑完整 suite 來取代核對。必要 evidence 缺少時不得宣告完成；
列出具體缺口及最小下一步。不要擴張範圍或實作額外修正。
```
