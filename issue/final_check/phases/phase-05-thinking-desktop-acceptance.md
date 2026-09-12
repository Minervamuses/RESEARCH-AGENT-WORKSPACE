# Phase 05 — Thinking Effort Desktop 操作與生命週期

本 phase 依 [GOALS 的 Issue 09 延期決定](../GOALS.md) 不列本輪範圍；以下僅保留未來條件式路線與 planned checks。使用者明確恢復後，須先核對當時 live code、定案產品與必要授權並修訂 PLANS，才可開始；延期期間不執行本檔步驟，也不標功能 Complete。實際狀態只見 build-log。

## 目標與來源

核准的 Thinking Effort 控件可由鍵鼠選擇，顯示 authoritative 有效值，下一回合及 new／A→B→A／restart 符合 GOALS 產品契約。
來源：[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、[原 09 UI 計畫](../../issue_09/phases/phase-02-desktop-control-and-acceptance.md)、App.tsx/updateThinkingMode、conversations helpers、既有 protocol/backend/desktop tests。

## 範圍與非目標

依定案差異收斂 App.tsx、必要既有 frontend state/helpers、test_desktop_fixture.py／Node tests；CLI 用法若改，僅更新既有 README 相應段落。
非目標：另做 GUI redesign、修改未核准 runtime 或 storage、新增通用 preference 管理器／測試框架。若精確檔案／介面尚未凍結，不把候選列表當授權。

## 依賴與前置

Phase 04 Complete，GOALS 的產品決策與精確 scope 授權齊全。
原生環境和安全 offline fixture 遵守 Phase 03 同樣門檻；03 的外部阻塞不代表禁止本 phase 獨立離線 UI 實作，但缺原生操作時本 phase 不能 Complete。
Phase 04 若改变 fixture DTO，須先有真 backend 對照，避免只改 fake controls 讓 UI 看似成功。

## 實作與驗證計畫

1. **Red：** 既有 Node／service seam 驗證選擇不送回合、不丟草稿；ack 成功才顯示新有效值，invalid/busy/failure/stale response 不局部更新。保留 retired Product Plan Mode 與 Extended 的既有相容斷言。
2. **Green：** 使用定案控件與名稱，接既有 session control；保留 session ID／generation／operation guards、鍵盤可及性、正常 focus。不要把 implementation 細節放進產品流程。
3. **原生代表流程：** 用安全 tmp/offline 入口，按兩個核准值各送同一代表問題，再切回；觀察控件、backend ack、真正下一回合 routing。選擇可送 session.set_thinking 控制請求並等待 ack；session.turn delta=0、model/provider call delta=0，草稿保留。含已建立 model 的 session。
4. **生命週期與失敗：** new／A→B→A／restart／old history 符合 GOALS；busy／approval、可控取消／失敗後仍可操作。再做 Citation／installer Normal override→完成恢復選擇的代表流程，若它會影響 Phase 01/03 證據則更新其有效性與所需 targeted recheck。

### Planned verification

cwd app/desktop/：

```bash
timeout 300s node --test --experimental-strip-types tests/conversations.test.ts tests/backend.test.ts tests/protocol.test.ts
timeout 300s ./node_modules/.bin/tsc --noEmit
```

cwd app/，依實際 fixture/service 差異跑相應子集：

```bash
timeout 300s poetry run pytest tests/test_desktop_fixture.py tests/test_desktop_conversations.py -q
```

真原生 launch recipe 必須在 preflight 由已核對的 safe fixture 寫入 evidence；目前不猜一條會連 user store 的命令。full suites／Tauri source build 留 Phase 06，planned checks 不表示已跑。

## 驗收條件

- [ ] 控件依核准契約可用；選擇不送回合、不毀草稿，只呈現後端已確認有效值。
- [ ] 同 session 切兩值再切回的下一回合效果與 Phase 04 mapping 相符，非只有 snapshot。
- [ ] new/switch/restart/old history、busy/approval/stale/failure/cancel 與 GOALS 一致。
- [ ] 真原生鍵鼠與可及性操作有證據；假 Session/SSR 不替代 runtime 或 native acceptance。
- [ ] Citation／installer 的暫用 mode、恢復、canonical metadata 不退化；必要 focused/type checks 通過。

## 恢復、證據與交接

失敗保留 authoritative 舊值及資料，僅修自己直接 diff；不以清空歷史／偏好或重啟系統掩蓋問題。
在 ../build-log.md 記 UI操作→backend/routing/JSON 對照、exact commands、實際改動與限制；若 earlier phase evidence 已過時，明示新的補驗範圍。
若未來恢復本 phase，其原生 evidence 仍是功能驗收門檻；無原生工具不能以 offline 通過結案。本輪 Phase 06 前置依 PLANS 的延期後路線，不要求本 phase 完成。
