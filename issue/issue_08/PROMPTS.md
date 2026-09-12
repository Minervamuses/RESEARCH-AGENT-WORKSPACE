# Issue 08 — 可複製執行入口

## 啟動／續作 — Start / Resume

```text
請處理 /home/minervamuses/research-agent-workspace 的 issue/issue_08 計劃。
本指令不自動批准 GOALS.md 的待決產品契約或 PLANS.md 尚未批准的變更範圍；
先核對使用者是否已明確批准，未批准只做唯讀 preflight 並回報所缺決定。

先讀所有 applicable AGENTS.md，再依序讀：
1. issue/issue_08/GOALS.md
2. issue/issue_08/PLANS.md
3. issue/issue_08/build-log.md
4. 依 PLANS 依賴順序與 build-log 狀態選出的第一個非 Complete phase file
5. 已存在且相關的 issue/issue_08/context/、issue/issue_08/code_review/ 文件
6. 該 phase 的 live code／tests，以及 issue 02 的完成證據

確認 workspace／Linux runtime、Conda app／Poetry／Git 工具與當下未提交變更。
Observed live repository 優先於過期敘述；發現矛盾先追加 correction，
不得還原使用者既有變更。build-log 是唯一 runtime status owner。

依 PLANS.md 的 execution mode／authorization envelope：
- 每次只選一個 dependencies 已完成的 phase，做唯讀 preflight，
  說明本 phase 範圍、非目標、checks 與停止條件。
- 前置缺失就記錄 Blocked 與具體證據；不推進、不自行做 issue 02。
- 只實作該 phase；用最小能區分錯誤的測試先觀察，再做必要修正。
- 跑 phase 的 required verification；失敗先釐清／修正，不開始 dependent work，
  遵守 PLANS 的失敗次數與昂貴操作門檻。
- 將實際檔案、精確命令、結果、限制寫入 issue/issue_08/build-log.md。
  重大發現才新增 context，真實 review 才新增 code_review。
- 新 evidence 推翻後续路徑時，先修 PLANS 與受影響的未開始 phase，再繼續。
  不自行變更 GOALS，也不消除既有失敗歷史。
- 在授權內自主繼續下一個 eligible phase，直到整體完成或明確 stop condition。
  完成後回報實際結果、檔案與 checks，停止。

不要 commit、push、merge、deploy、切 branch、修改 worktree、使用 credentials、
付費 provider、真實使用者資料或越過 PLANS 的新授權門檻。
```

## 執行一個階段 — Execute One Phase

```text
請只執行我指定的 issue/issue_08 階段。先依
issue/issue_08/PROMPTS.md 的 Start / Resume 讀取同一組 durable sources，
確認 GOALS 待決契約、PLANS 的批准範圍與該階段 dependencies。
在該 phase file 的 scope 內實作／驗證，更新 build-log 和必要 context；
遇到 stop condition 就回報，完成該階段即停止，不開始下一階段。
```

## 驗證／審查 — Verify / Review

```text
請核對 issue/issue_08/GOALS.md、PLANS.md、build-log.md、指定 phase file、
相關 context 與 live diff。直接對照使用者可見結果、來源 cleanup、thinking、
trust gate、恢復不重播與保留行為，不以 builder 敘述代替證據。
唯讀檢查及授權內安全驗證後，把真正 findings 記到相應 code_review；
未執行、unavailable、fake-model 限制要明說。不要直接修改 production code。
```

## 矛盾證據後修訂計劃 — Repair Plan

```text
請只修訂 issue/issue_08 的計劃。讀 GOALS、PLANS、build-log、受影響 phases、
context 與 live source，指出哪項新證據推翻原理解。
保留已核准目標與完成／失敗歷史，只修 roadmap 與受影響的未開始 phase，
追加必要 correction。不因重新規劃而實作程式；不改 AGENTS.md。
```
