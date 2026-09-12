# Phase 04 — 定案後的 Thinking Effort 後端

本 phase 依 [GOALS 的 Issue 09 延期決定](../GOALS.md) 不列本輪範圍；以下僅保留未來條件式路線與 planned checks。使用者明確恢復後，須先核對當時 live code、定案產品與必要授權並修訂 PLANS，才可開始；延期期間不執行本檔步驟，也不標功能 Complete。實際狀態只見 build-log。

## 目標與來源

GOALS 三項產品決策定案後，核准段位確實影響下一回合，且現有 cached model／workflow、偏好生命週期及跨語言契約一致。
來源：[GOALS 決策](../GOALS.md)、[PLANS](../PLANS.md)、[原 09 runtime 計畫](../../issue_09/phases/phase-01-thinking-contract-and-runtime.md)。原計畫為候選設計來源；本輪狀態／答案／evidence 只在 final_check，不能把原 Not started 視作完成。

## 範圍與非目標

候選元件為 agent/session.py、CLI、desktop/service.py、llm/openrouter.py／thinking.py、graph.py、thinking/orchestrator.py；若核准 wire/資料差異才涉及 contract.json、TS/Rust validators 與 conversations models/repository。
**不是全改清單。** 定案後刪去沒有因果必要的路徑，將實際 paths／方法／DTO／schema 及 compatibility 預期寫回本未開始 phase，才可開工。
非目標：本 phase 新 GUI 控件、通用 provider adapter/cache 框架、模型評比、新 storage、替換 Extended 或擅自定 enum。

## 依賴、決策與授權門檻

Phase 01/02 Complete；不依賴 Phase 03 原生可用性。GOALS 的段位、映射、保存三項都必須有明確答案，並取得尚缺的精確 scope／public API／schema／超三 production files 等授權。
未定案就不寫 application code/tests、不用 provisional enum。採 provider effort 時，先讀當時 pinned integration 實作與官方來源，確認參數與可測 request 接縫；SDK 接受 kwargs 不代表遠端生效。必要 live check 另外取得授權。
如只批准延期 09，依 PLANS 修訂未開始路線，不將本 phase 標為功能 Complete。

## 實作與驗證計畫

1. **Preflight／Red：** 將定案映射與 new／A→B→A／restart／old data 預期列為具體驗收。用真 session 加既有 fake transport/model，先選兩個核准值再切回，連續送同一代表問題；觀察 request/routing 與已建 model 的生效差異，不能只看 config。
2. **Green：** 只實作所選 mapping／validation／局部 model 更新；成功回 authoritative snapshot，失敗無部分更新。若 wire 格式獲准變動，同步所有現有 consumers；不把破碎 contract 留給 UI phase。
3. **相容對照：** 非法／不支援值、busy／pending approval 保持原有效設定；Citation／installer 的 Normal 邊界和原模式恢復不退化。舊 durable data 只在 tmp 測定案相容政策；歷史 turn metadata 不擅自當 preference。
4. **整理：** 無獨立 refactor；只保留直接通過行為所需修改。cached model／role 範圍只驗定案實際會受影響的代表值，不建模型乘角色大矩陣。

### Planned verification

cwd app/，每組先選實際改動相關 node/module；以下是候選回歸邊界，定案後刪去不適用部分，不全跑後宣稱完整：

```bash
timeout 300s poetry run pytest tests/test_slash_commands.py tests/test_thinking_session.py tests/test_thinking_models.py tests/test_openrouter_model.py -q
timeout 300s poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_citation_skill_activation.py tests/test_skill_adherence.py -q
```

真的改 durable 格式才跑 tests/test_conversation_repository.py／test_conversation_archive_access.py；改 orchestrator 才加 tests/test_thinking.py。cwd app/desktop/，wire 或 TS consumer 有改才跑：

```bash
timeout 300s node --test --experimental-strip-types tests/protocol.test.ts
timeout 300s cargo test --offline --manifest-path src-tauri/Cargo.toml protocol::tests
```

必要 TypeScript check 使用既有 node_modules/.bin/tsc --noEmit；不安裝缺件。完整 suites/build 由 Phase 06 擁有。

## 驗收條件

- [ ] 三項產品決策與精確授權已保存；實際 changed paths 不超出收斂後清單。
- [ ] 定案段位在真 session 的下一回合及既建 model 生效；request/workflow 證據對應映射，非單純 label。
- [ ] mode／preference／canonical metadata 關係、新舊資料與 new/switch/restart 行為符合定案結果。
- [ ] invalid/unsupported/busy/approval 無部分更新；三個 P2 與 Citation／installer 權限不退化。
- [ ] 必要 focused／wire/type 檢查通過；缺 provider 必要證據不以 fake 結果冒充。

## 恢復、證據與交接

資料變更僅用 tmp，migration 若需要，先提供獲准的明確 recovery 策略；沒有 migration 就不造回滾流程。
記 exact routing/request/lifecycle、red/green、相容結果於 ../build-log.md；重大模型 cache 發現才建 context。
失敗或未驗證阻擋 Phase 05，兩次 focused 嘗試失敗依 PLANS 停止；完成才交接 UI。
