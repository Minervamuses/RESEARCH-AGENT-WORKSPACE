# Phase 06 — 一次整合回歸與逐 Issue 結案核對

## 目標與來源

對最終實際 diff 執行一次適度回歸，給 Issue 01–10 明確且不誇大的處置與 evidence。把「程式補救完成」「限縮接受」「功能延期」「仍缺原生證據」分清。
來源：[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、[build-log](../build-log.md)、前五個 phase 的 actual evidence，及 issue_01、02、03(fin)、04、05、06、07、08、09、10(fin) 原有 logs。

## 範圍與非目標

本 phase 以整合驗證／review／log 為主；不另立全 repo audit，不新增測試框架或 live provider campaign，不回填舊 Issue 的 phase status、不修改 AGENTS。
發現由本次 diff 導致的具體回歸，歸回對應 phase 的因果範圍修正；無關缺陷單列，不順便修。

## 依賴與 preflight

Phase 01–05 Complete，或 GOALS 已有明確使用者延期/限縮決策、PLANS 與未開始路線已正式修訂。未做功能不能靠最終表格變成 Complete。
核對 git status／diff、final code revision 及未提交檔案指紋；有未提交修改時，HEAD 相同不代表相同 code。證據須對應目前實際 code，不要求為此 commit。
先盤點已跑 checks 及成本；cached offline Cargo/Tauri 不足或預估超十分鐘，按 PLANS 先處理授權。新資料與模型一律 tmp/offline。

## 驗證計畫

### 代表案例與 review

以既有 regression tests／前段 evidence 核對「installer preview→衝突／成功切換→有效 mode」「completed Citation→runtime 失效→精確重送」「普通下一回合與 history restore」三個跨邊界輸出。
針對本次 diff 做一次 fresh-context bounded review，挑戰 identity、load/cleanup 時序、正式公開回報、metadata 與未覆蓋反例。review 不是全 repo 掃描；實際發生後才建立 code_review/phase-06-regression-and-closure-review.md。

### Planned full checks — 本輪各一次

cwd app/，Linux Conda app：

```bash
timeout 540s poetry run pytest
```

cwd app/desktop/：

```bash
timeout 300s npm test
timeout 540s cargo test --offline --manifest-path src-tauri/Cargo.toml
CARGO_NET_OFFLINE=true timeout 540s npm run tauri -- build --no-bundle
```

Cargo 的 --offline 與 CARGO_NET_OFFLINE 是本計畫的防下載成本限制，基礎命令來自 README/package.json；cache 不足記 Blocked，不自行下載。
Tauri source build 包含 npm run build 的 TypeScript/Vite，因此不再為同一 final diff 重跑 npm run build。protocol 子集不是完整 Rust suite；記實際測試總數與日期，不沿用舊 12/36 或 1122/165。
完整 suite 失敗先保留 evidence、查直接因果，按 PLANS 嘗試／第二次 full-suite 門檻處理；不能為湊全綠無限制重跑。

cwd repo root：git diff --check。若最後才改自己的少量文件，補文件檢查，不重新跑 application 全套。

### 逐 Issue 處置（寫入 build-log，不另建狀態表文件）

| Issue | 結案必須說明 |
|---|---|
| 01 | 引用已核准限縮；原 skipped 不改 passed，不要求重建舊 fixture。 |
| 02、08 | 各自 native checklist 的實際證據／明確限縮；08 再連 Phase 02 重送修正。 |
| 03、04、05 | 對照既有 permission／earliest ambiguity／save reporting 證據及本次相關 regression；區分歷史與新執行。 |
| 06、07、10 | integrity／apply-lock／ZIP 主流程歷史證據保留，直接 diff 回歸有對照；10 補 Phase 01 切換邊界。 |
| 09 | 三決策與功能驗收，或明確延期來源；不能把現有 Normal／Extended 當多段位完成。 |

## 驗收條件

- [ ] GOALS 每項成功條件有直接 evidence；三個 P2 在最終 code 上被相關 regression 保護。
- [ ] 適用 full Python／Node／Rust 與 Tauri source build 實際通過；required unavailable 只能按已批准限縮處理。
- [ ] 逐 Issue 表完整區分接受／限縮／延期／阻塞，以及歷史／本輪結果；沒有 unsupported 全批完成宣稱。
- [ ] bounded independent review 的必要發現已修正或明確接受，git diff --check 通過，diff 未擴大到無關元件。
- [ ] required evidence 有可讀持久來源，自己的臨時診斷／無用程式已清理，未刪 user changes 或 conflict backup。

## 證據、失敗恢復與最終交接

將 exact commands、runtime、diff fingerprint／revision、實際 counts/time、native artifact、逐 Issue 表、review 結論和限制記 ../build-log.md；不用複製整份輸出。
必要失敗／原生缺證據保持 Blocked 或 In progress，明確指出最小下一行動；不要修改舊 logs 製造結案。
全部 current required outcomes 成立才標 Complete，報告實際 changed files／checks 與保留限縮後停止；不自動 commit/push、部署或開始新改善。
