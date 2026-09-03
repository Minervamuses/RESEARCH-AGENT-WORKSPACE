# Phase 05 — 移除產品 Plan Mode

Status: Not started

## Objective

從產品 UI、CLI、protocol、session runtime、persistence 與 active documentation 中完整移除 Plan Mode，同時保留 normal/extended thinking、一般自然語言規劃能力、Skills 與 Citation 行為。Legacy Plan log parser 只留在 migration boundary，舊檔不刪除。

## In Scope

1. 移除 `/mode`、Plan mode selection/hints、`session.set_mode`、enter/resume/exit Plan methods、plan snapshot/status、journal plan state、plan-only persistence target、Plan-specific request/response fields 與 runtime branches。
2. 移除 React Plan 控制、TypeScript/Rust bridge fields 和相關 protocol fixture 欄位。
3. 停止建立新的 Plan logs；將唯一仍需的 v1/v2 reader 留在 Phase 02 migration namespace/boundary。
4. 更新或刪除只驗證產品 Plan Mode 的測試；保留 legacy migration parser tests。
5. 以 negative residue search 證明 active runtime 不再暴露 Plan Mode。

## Non-goals

- 不移除 `/thinking`、`thinkingMode`、normal/extended provider route 或 reasoning summaries。
- 不禁止使用者用普通提示要求「先規劃」；不移除 planning-related Skills。
- 不修改 Citation、SafeContent、approval 或 document RAG。
- 不刪除 legacy Plan log files，也不把 historical notes/harness 文字做機械式改寫。
- 不同時處理 conversation-history Chroma；留給 Phase 06。

## Dependencies and prerequisites

- Phase 04 host cutover 與 protocol tests 通過，canonical JSON 已承擔所有新 turn durability。
- 先建立 Plan Mode residue inventory，分類為 active runtime、migration-only、historical record、ordinary English usage。
- 先追蹤 `plan_log.py`, session routes, CLI slash commands, desktop protocol, React controls、TS/Rust models 與 tests。
- `GOALS.md` 所稱移除的是產品 feature，不是刪除所有含字串 `plan` 的程式或文檔。

## Expected components

預期變更可能涵蓋：

- `app/agent/session.py` 與 CLI/slash command/mode config 的相鄰模組
- `app/agent/turns/plan_log.py`：runtime writer 移除，strict reader 搬到或委派至 migration boundary
- Python desktop protocol/service/server
- React App、types/reducer 與 TypeScript bridge
- Rust protocol/command structs 與 fixtures
- Plan-specific tests；migration tests 保留 legacy parser coverage
- Active user docs 的 Plan Mode 指令/畫面說明；完整文件一致性仍於 Phase 07 收尾

## Authorization and stop conditions

本階段授權移除 public Plan Mode protocol surface，因 repository 是 lockstep source checkout。若發現受支援的外部 client、plugin 或持久格式仍以該欄位為 contract，停止並請使用者決定版本策略。不得以相容 adapter 永久保留 feature。

若任何 `plan` 名稱其實屬於普通 planning、Skill、test plan 或 migration source，先分類，不可用全域 replace/delete。

## Implementation and verification plan

### Preflight

1. 用 `git grep --untracked -n -i` 搜尋 `plan mode`, `plan_mode`, `set_mode`, `/mode`, `planLog` 等精確 runtime spellings，讓尚未stage的新source/tests也在audit內。
2. 建立 allowlist：`harness/`、歷史 `issue/`/`note/`、migration-only legacy parser；其餘逐項判斷。
3. 記錄 normal/extended thinking 的入口、protocol field 與測試，作為不可退化 guard。

### Red

先更新測試以表達目標介面：

- CLI `/mode` 不再列出或接受；`/thinking` 仍正常。
- Protocol schema 不含 Plan methods/fields/snapshots；未知舊 method 有一致 method-not-found/validation error。
- Desktop UI 不渲染 Plan controls，normal/extended turn 仍可完成與恢復。
- 新 conversation/turn 不建立 Plan log。
- Legacy Plan v1/v2 fixture 仍可由 migration importer 讀取。

### Green

1. 從 UI 往 backend 依 consumer→producer 順序移除 fields/actions，保持 lockstep build 可診斷。
2. 刪除 session Plan branches、mode setter、Plan prompt/history fusion 與新 log writer calls。
3. 將 strict legacy parser 收斂到 migration-only import；不得由 normal execution import。
4. 更新 tool/help text 與 active docs，使使用者不再看到已移除命令。
5. 保持 thinkingMode/normal/extended、citation 與 Skills 路徑原樣，僅修正因 Plan union/enum 移除造成的直接型別問題。

### Refactor

- 清除本次移除造成的 unreachable code/imports/types；不進行其他 mode framework 重構。
- 不保留 deprecated Plan aliases、hidden flags 或空殼 UI。
- 歷史 records 不修改；必要時在 active docs 指向 migration 行為。

### Verification

先從 `app/` 執行受影響的 Python Plan/CLI/thinking/desktop protocol tests：

```bash
conda run -n app poetry run pytest tests/test_plan_mode.py tests/test_chat_cli.py tests/test_slash_commands.py tests/test_thinking.py tests/test_thinking_session.py tests/test_skill_runtime.py tests/test_citation_gate.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py tests/test_desktop_service.py -q
```

再從 `app/desktop/` 執行：

```bash
conda run -n app node --test --experimental-strip-types tests/protocol.test.ts tests/conversations.test.ts
conda run -n app ./node_modules/.bin/tsc --noEmit
conda run -n app cargo test --manifest-path src-tauri/Cargo.toml protocol::tests
```

若Plan removal新增/搬移測試，build log記錄精確replacement selector。本機`node_modules/.bin/tsc --noEmit`是必要typecheck；binary不存在時依dependency gate停止，不得隱式下載。此階段不跑完整npm/Cargo suite或Vite build。再以`git grep --untracked`執行residue search並逐筆分類，不要因普通「plan」字樣造成假陽性而刪錯。

## Reliability, security, and recovery

- 舊 Plan logs 保留，只讀 importer 仍可遷移，不做 destructive cleanup。
- 移除 mode 不得繞過 canonical pending/completed commit ordering。
- Unknown legacy protocol input 必須清楚拒絕，不能默默轉成另一 thinking mode。
- Citation、tool approval 和 SafeContent tests 是 removal regression guards。

## Acceptance Criteria

- [ ] UI、CLI、Python protocol、TS/Rust bridge、session runtime 都不再提供 Plan Mode。
- [ ] 新執行不寫 Plan logs；normal execution 不 import migration-only parser。
- [ ] Legacy Plan v1/v2 importer tests 仍通過，舊檔未被刪除或改寫。
- [ ] Normal 與 extended thinking 都可執行、持久化與重啟恢復。
- [ ] Skills、Citation、普通規劃提示與 `/thinking` 未被誤刪。
- [ ] Residue search 的每個剩餘精確 Plan Mode reference 都有 migration/historical/harness 理由。

## Evidence to record

在 build log 記錄移除的 public surface、保留的 thinking surface、residue command 與分類結果、測試命令/exit code。若 active runtime 尚有 Plan-only caller，Phase 05 不得標 Completed。

## Handoff

Phase 06 將移除 conversation-history Chroma。開始前確認 legacy Plan reader 已完全位於 migration boundary，且 active runtime 的唯一 conversation authority 是 JSON。
