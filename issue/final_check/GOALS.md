# Final Check — 剩餘補救與驗收目標

## 目的與背景

將 Issue 01–10 剩餘工作收斂為可續作、可核對的補救與驗收；已完成工作的證據繼續有效，但不能用歷史測試數量取代尚缺的使用者流程。
本次使用者要求在 issue/final_check 新增計畫；只授權 authoring，不啟動實作或再次驗收。

## 預期成果與成功條件

| 成果 | 可觀察成功條件 |
|---|---|
| 安裝器切換正確 | preview 後的來源衝突公開回報原因與備份位置，新 Skill／模型零呼叫，修改與備份 bytes 不變；成功切換後持久 thinkingMode 與實際 workflow 一致。 |
| Desktop 重送正確 | completed Citation 以相同 canonical 身分重送，不依賴目前 runtime 可用性，回原 durable answer；scope／model／provider／save 均不增加。 |
| 原生 Desktop 驗收完整 | Issue 02 menu 與 Issue 08 Citation 各自缺少的原生互動有直接證據，或使用者另行明確接受具體限縮；兩者不能互相豁免。 |
| Thinking Effort 缺口有實際處置 | Issue 09 三項產品決策定案後完成核准功能與驗收；若使用者明確延期，保留為延期而非功能完成。 |
| 最終結論可追溯 | 每個 Issue 可對應當前補救／驗收、歷史依據、限縮／延期或阻塞，沒有把 unavailable、skipped、Not started 寫成 passed。 |

## 範圍

三個已定位 P2、Issue 02／08 未完成原生驗收、Issue 09 待決功能的完整條件式路線，以及補救後一次適度的跨層回歸。
Issue 03–07 依現有證據與此次實際 diff 決定直接回歸範圍，不重啟全面審查或新增無關改善。
Issue 10 原有 ZIP 主流程證據保留，新增的是切換邊界驗證。

## 非目標

- 不重做 Issue 01 已同意略過的舊驗收矩陣，不修改其限縮結論。
- 不新增通用 fixture／benchmark／provider framework，不更換 package manager、runtime 或架構。
- 不做模型品質、速度、成本比較；不以假模型證據宣稱真 provider 表現。
- 不遷移或修補既有真實歷史 JSON，不測真實使用者 store，不重寫既有 Issue 計畫／log。
- 不修改 AGENTS.md，不延用舊 Issue 的 commit／push 授權。

## 保留行為與限制

1. **檔案與身分完整性。** 重用 SkillInstaller.clear 的保留策略；不刪除使用者修改或備份。duplicate 須核對 session/project、turnId、kind、display/semantic input、context eligibility、thinking mode 與現有 snapshot 一致性；不能只憑 turnId 放行。
2. **順序。** completed duplicate 先返回，不載入 Skill、不 cleanup、不重新保存；completed 加 retry=true 仍返回原答案。只有可重試的 failed/interrupted 明確 retry 才能開始新工作。新工作 runtime 驗證失敗前不清理原 installer／Citation 狀態。
3. **模式與權限。** Citation／installer 使用 Normal；installer 結束恢復原選擇。Extended 是多角色 workflow，不等同 provider reasoning effort。保留 busy／approval、final-only、cancel/retry 及 Skill tool scope。
4. **Runtime 與資源。** 根 AGENTS 與使用者 Personal Engineering Defaults 為權威：Linux、Conda app、Poetry、LF；Windows 只作 WSL launcher。最小直接修改、既有測試接縫、短命令；不自行安裝、升級、GPU／全資料掃描或呼叫付費 provider。
5. **證據與既有授權。** Issue 01 的 2026-09-12「跳過需要重啟的部分，如實記錄即可」保留。Issue 02 menu 自己的 IME／Shift+Enter 驗收仍可做，不能藉此重新要求 Issue 01 整套測試。Issue 08 沒有獲豁免自身原生驗收。

## 未知與使用者待決事項

### Issue 09 產品決策

本計畫先保留完整條件式實作路線；尚未收到將 Issue 09 排除／延期的明確決定，不能代填 enum 或先做 UI。
本輪決策以本節為唯一 owner；原 issue_09/GOALS.md 為先前需求來源，保留原文，不同時運行兩套執行計畫。

| 待決 | 必須明示 | 影響 |
|---|---|---|
| 段位 | 數量、名稱、穩定值、順序、預設，與 Normal／Extended 的關係 | UI、合法值與預設相容性 |
| 行為映射 | workflow／model／provider effort 或明示組合；適用角色、不支援時行為與 CLI 相容 | 實際下一回合、cached model 與驗證 oracle |
| 保存範圍 | 新對話、同程序 A→B→A、restart；對話／全域偏好，是否記錄新 metadata | 持久格式、migration 與跨語言契約 |

三項定案後，先呈現精確必要 production paths／API／schema 差異與成本，取得尚缺的實作授權；本次寫計畫不等於批准這些變更。已有相同具體授權則引用來源，不重複詢問。
若使用者明確延期 09，只更改此穩定範圍決策，依 PLANS 修訂未開始路線；不能自行把延期階段標 Complete。

### 技術／驗收未知

- Linux Desktop／IME／輔助工具能否操作：由原生驗收階段的短 read-only preflight 查證。歷史 timeout 不表示今日一定失敗；不得自行重啟 WSLg／WSL 或安裝工具。
- 現有 phase02 GUI FixtureSession 不是真 Citation。原生 Citation 必須有真 ChatSession、既有 offline fetcher/model、tmp store 的安全入口；目前沒有已確認的完整啟動命令，由該階段查明最小接縫。
- 原生或 provider 必要證據仍不可得時，由使用者決定修復環境、提供操作證據或明確限縮；時間經過不等於豁免。

## 來源

- [根 AGENTS](../../AGENTS.md) 與本次使用者 Personal Engineering Defaults、2026-09-12 建立 final_check 指示。
- [01 限縮授權](../issue_01/build-log.md)、[02 驗收缺口](../issue_02/build-log.md)、[08 主流程與原生阻塞](../issue_08/build-log.md)。
- [09 產品需求](../issue_09/GOALS.md)、[09 原有路線](../issue_09/PLANS.md)、[10 既有證據](../issue_10(fin)/build-log.md)。
- app/agent/session.py、extensions/manager.py、desktop/service.py、conversations/repository.py；確切因果路徑與測試見 PLANS 和各 phase。
