# Phase 01 — 僅套用指定 Skill 的管理邊界

## Source Inputs

`../GOALS.md`、`../PLANS.md`，以及其中列出的 discovery、manager、paths、
registry 與既有 extension tests。使用 live code 核對，不能只依賴先前研究。

## Objective

在其他 skill／MCP 同時有 pending changes 時，host 能只 preview/apply 本次
指定 skill 的 add/update，保持其餘項目不變；固定目錄內 ZIP 不成為 skill entry。

## In Scope / Non-Goals

包含 existing manager 的選定項目 scope、apply 時重新驗證、ZIP 共存及最小回歸
測試。不包含 ZIP 解壓 agent、公開 installer skill、GUI、MCP 新能力或全域掃描重構。

## Dependencies and Prerequisites

無前置 phase。先確認現有全量管理 tests、diff signature、registry revision、
managed copy 與 source 留存行為。

**Unresolved:** scope 最小接點由 `ExtensionPreview`、`_preview`、`_apply_locked`
的 live 資料流決定。用 selected/unselected 混合變更的失敗測試回答，不新增
persistent 欄位。舊 caller 不傳 scope 時必須維持全量語意。

## Expected Components Affected

主要為 `app/agent/extensions/manager.py`、`discovery.py`，及
`app/tests/test_extension_manager.py`、`test_extension_baseline.py`。
只有現有 diff 資料責任確實要求時才改直接相關的既有 extension 型別檔；
`paths.py`、registry 格式、private planner 指令預期沿用。

## Authorization and Stop Conditions

依 `../PLANS.md` 的 launch envelope。若最小方案要求新 registry／public
persistent format、放寬 MCP approval 或放棄來源驗證，停止並取得新授權。

## Implementation and Verification Plan

### Preflight / Red

- 建立 temp drop-in/state，沿用 deterministic management model。測試選定
  skill A，同時存在未選 skill B add/update、已登錄 C 的 delete，以及 MCP
  pending change；斷言只有 A 進 authoritative planning 及實際變更。
- 補一個 ZIP 檔與合法展開 skill 共存的 scanner regression；只辨別 `skill/`
  的一般 ZIP 檔，保留無效目錄的既有診斷，不把所有非目錄項目靜默忽略。
- 捕捉 preview 後指定來源被改動／registry revision 變動時原本應拒絕的行為。

### Green

- 使用 host 驗證的非空 selected skill keys 限定 add/update；不能讓模型加入
  MCP、delete 或其他 skill。無效／不存在選擇回傳具體錯誤，不解讀成全量。
- 將 scope 保存在 in-memory preview，貫穿 diff 建立、LLM request、plan
  validation、apply 重掃與 signature 核對。不能只過濾顯示或最後回報。
- registry 更新從既有 entries 合併，只改所選 key；重掃仍做必要跨 ID collision
  與 revision 檢查。無關檔案變動可維持保守 stale 拒絕，不能因此被順便套用。
- ZIP 是待處理來源，不納入 installed catalog；不需要新 inbox／watcher。
- 安裝成功保留 drop-in source；既有 full preview/apply 與 MCP binding 流程不變。

### Refactor

沒有獨立重構工作。只移除本階段引入且已無用的重複碼，改動後重跑 focused tests。

### Verification

以下命令從 repository root 執行，使用 Conda `app`，均為 planned：

```bash
cd app
conda run -n app poetry run pytest tests/test_extension_manager.py tests/test_extension_baseline.py -q
conda run -n app poetry run pytest tests/test_extension_registry.py tests/test_extension_mcp.py tests/test_extension_skill_startup.py -q
```

第一行 pytest 為 focused，第二行為 broader。以 temp registry entries、檔案
bytes/hash 及實際 ApplyReport 驗證，不能只檢查 model prompt 是否縮短。
無須 live model、使用者真實目錄或應用 build。

## Reliability and Recovery

保留 preview/private-skill/source/registry 驗證與目前 apply lock，不擴大修復
cross-process race 的既有 issue。失敗時不刪使用者 ZIP 或先前有效來源；本
phase 沿用 manager 的既有保存流程，臨時測試資料由 fixture 清理。
Required check 失敗保持 In progress／Blocked，Phase 02 不得開始。

## Acceptance Criteria

- [ ] 所選 A 進入 managed state 與 registry；未選 skill/MCP 的 entries、
      managed content 及 sources 和前測一致。
- [ ] 非法、空、包含非 skill 的 scope 不觸發全量 apply；拒絕與錯誤可觀察。
- [ ] ZIP 共存不產生非法 skill item，正常展開目錄仍按既有規則驗證。
- [ ] 指定來源／registry 變動後舊 preview 無法套用；原本全量及 MCP tests 通過。
- [ ] 安裝後 drop-in source 保留，再次預覽不產生意外 delete；focused/broader 通過。

## Evidence and Handoff

在 `../build-log.md` 記錄實際檔案、命令、結果及限制。若 scope 接點與原理解
不同且會影響 Phase 02，寫 material context 並先修訂未開始計畫。
全部 acceptance 成立才將 Phase 01 標 Complete，按 PLANS 的模式接續 Phase 02。
