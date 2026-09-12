# Phase 01 — Session command catalog 與 contract

## 來源

[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、`app/agent/cli/slash_commands.py`、
`app/agent/desktop/service.py`、`app/desktop/protocol/v1/contract.json`、
Python／Node／Rust protocol tests。

## 目標

每次成功 session.create／session.select 回傳與該 session Desktop dispatch
一致的 canonical catalog，三語言 contract validators 接受相同有效資料並拒絕非法資料。

## 範圍與非目標

範圍：registry resolver、共用 Desktop eligibility、snapshot projection、
JSON/TS/Rust mirrors 與最小 fixtures/tests。
非目標：React 清單、CLI 改寫、啟用被排除 commands、新 method、hot reload、
Skill integrity 修復、儲存格式改動。

## 依賴與前置條件

- 無前置 phase；必須已取得 PLANS 的完整 launch scope 授權。
- Read-only preflight 核對 registry override、`_session_turn`、
  `_session_snapshot`、create/select／session.status 使用點，以及現有 tests。
- **待解：** 從 live metadata、既有 wire 限制與 fixtures 決定 entry/array bounds，
  以一個過長描述及筆數界線案例驗證。保留 canonical name 不變；描述可依既有
  UTF-8 bounded-text helper 處理。不可用靜默截清單偽裝完整 catalog。
  若必須新增 protocol paging/method 才能滿足實際案例，先停止並提出具體證據。
- 既有 `fixture_session.build_phase02_fixture_service` 共用真實 DesktopService；
  snapshot 改動應直接覆蓋該路徑。只調整自行手寫舊 DTO 的既有 tests/fixtures，
  不新增另一個 fixture server。

## 預期受影響元件

Production：`app/agent/desktop/service.py`、
`app/desktop/protocol/v1/contract.json`、
`app/desktop/src/protocol.ts`、`app/desktop/src-tauri/src/protocol.rs`；
`app/desktop/src/App.tsx` 僅限既有 `updateBashPermissionMode` 的完整 session DTO
建構處適配新必填欄位，不提前實作 menu。
Shared fixture：`app/desktop/protocol/v1/fixtures.json`。
Tests：`app/tests/test_desktop_service.py`、
`app/tests/test_desktop_conversations.py`、
`app/tests/test_desktop_protocol_contract.py`、
`app/desktop/tests/protocol.test.ts`、`app/desktop/tests/backend.test.ts`、
既有 Rust protocol tests。
只有需要直接保護現有 Skill projection 才補 `app/tests/test_slash_commands.py`。
Python generic protocol validator 已支援 objectArray，預期不改；
`slash_commands.py` 亦預期不需要 production 修改。

## 實作與驗證

1. **Preflight：** 確認 current diff／runtime；依 PLANS 處理授權。
   檢視既有 fixture/test 的 session injection，不呼叫真實 provider。
2. **Red：** 在既有 service fake session 補一個 catalog assertion：
   built-in 可用命令＋合法 one-shot Skill 出現、collision／CLI-only／alias 不出現。
   保留合法 `_prompt-master` 例外。加 create/select 一致與跨 session catalog 不混用的最小案例。
3. **Green：** 在 service 內以一個 session registry resolver 保留既有 injected override；
   從現有 dispatch 邏輯抽出最小共用 eligibility 判定，projection 與實際送出共用。
   不新增 registry framework，也不改變 `SlashCommandResult` 後續驗證。
4. 新增必要 snapshot 欄位
   `slashCommands: [{ name: canonicalName, description: displayText }]`；
   保留 registry 順序，名稱不含開頭 slash，不輸出 handler、路徑或 Skill instructions。
   不新增 argument schema；UI 補 `/<name> ` 即可。
5. 更新 JSON result schemas、TS result validators／SessionCreatedDto（selected 繼承）
   及 Rust `validate_session_snapshot`；同步有效 create/select fixtures。
   新欄位在本次匹配版本間一起更新，不建立舊版 fallback registry。
   `session.status` 若共用 snapshot，確認既有 consumers 仍接受。
   `App.tsx::updateBashPermissionMode` 在 `state.session === null` 分支自行建立
   完整 DTO；同步適配新增欄位。缺少真實 catalog 的該分支只能使用空清單，
   不可猜測命令或補入其他 session catalog；真正 snapshot 到達後才可顯示命令。
   用本階段 `npm run build` 確認所有 existing DTO constructions 仍能編譯。
6. **Negative checks：** 欄位缺失／錯誤型別／非法 nested key／超限必須依既有
   validator 規則拒絕；空合法 catalog 可表示零可用命令。列入 catalog 不等於保證
   handler 的 arguments、外部前置條件或執行一定成功。
7. **Lifecycle：** extension apply 前後現有 session catalog 不變；
   新 materialized session/restart 使用 loaded startup catalog。
   不從 drop-in desired state 或全域磁碟清單推測新命令。
8. **Refactor：** 只允許共用 resolver／eligibility 的必要去重；沒有額外清理工作。

### Planned verification commands

以下在 Linux shell，先 `source /home/minervamuses/miniconda3/etc/profile.d/conda.sh`
及 `conda activate app`。所有命令皆為未來 planned checks。

於 `/home/minervamuses/research-agent-workspace/app`：

```bash
poetry run pytest tests/test_slash_commands.py tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py -q
```

於 `/home/minervamuses/research-agent-workspace/app/desktop`：

```bash
node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts
cargo test --manifest-path src-tauri/Cargo.toml protocol::tests
npm run build
```

開發時先跑被新增／修改的單一 test node，再跑上述 scoped modules；
不在此階段跑完整 app suite。Cargo cache 缺失或預計超十分鐘依 PLANS 停止。

## 驗收

- [ ] create/select 的 snapshot 來源是同一 session registry／eligibility，無第二份 policy。
- [ ] 合法 dynamic Skill 與 static 命令、collision／alias／CLI-only exclusion
      有直接 service evidence；手動送出被排除命令仍失敗。
- [ ] A/B snapshots 各自正確；apply 不熱切換，restart/session materialization 換新 catalog。
- [ ] JSON／Python／TypeScript／Rust 的有效、缺失及 malformed DTO 檢查一致。
- [ ] 既有 snapshot 欄位、CLI parser、one-shot skill、approval 與 final result validation 保留。
- [ ] 上述 required checks 通過；失敗保持 In progress／Blocked，Phase 02 不得開始。

## 證據與交接

在 `../build-log.md` 記錄 exact commands、counts、結果及 DTO/lifecycle cases。
新決策如 bounds、snapshot 時點才記入 `../context/phase-01-context.md`；
不要把計劃建議當成已實作 contract。
Phase 02 只能依經驗證的 final DTO 開始；若 schema 與本提案不同，先修訂未開始 UI plan。
無 migration／資料 recovery；失敗修復自身 scoped diff，不改使用者資料。
