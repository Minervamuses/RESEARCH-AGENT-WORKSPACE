# Phase 01 — MCP Defaults

## Initial Status

Not started.

## Dependencies

None.

## Objective

讓 CLI 與 Desktop GUI 的正常 session creation 都預設載入 MCP，同時保留 CLI `--no-mcp` 明確 opt-out。這是 default plumbing 修復，不是連接、重設或測試真實 MCP server。

## Confirmed Cause

- CLI parser/entry path 已在沒有 `--no-mcp` 時把 `load_mcp=True` 傳給 session；此行為需保護，不需重寫。
- Desktop Python service 對缺少 `loadMcp` 的 `session.create` 採 `true`。
- React `App.tsx` 正常建立 session 時明確送 `loadMcp: false`，覆蓋 backend 正確 default。

Executor 開始時須重新讀 live source；line number 可能已變，行為才是 authority。

## Causal Scope

### Expected production write

- `app/desktop/src/App.tsx`
- `app/agent/desktop/service.py` 只有在 focused test 證明 backend default 本身不穩定時才修改；否則 read-only。
- CLI production 預期不需修改。

### Expected tests

- `app/tests/test_chat_cli.py`
- `app/tests/test_desktop_service.py`
- `app/desktop/tests/conversations.test.ts`，或 live test topology 中真正覆蓋 `session.create` payload 的既有檔案。

任何擴張先在 `build-log.md` 記錄 exact file 與 causal reason。

## Non-goals / 非目標

- 不連接或重設真實 MCP server，不讀 credential，不測 MCP 功能內容。
- 不新增 GUI MCP settings 頁、dependency、retry framework 或改 CLI 其他 flag。
- 不處理 Fusion、Extended、Skill、streaming 或 conversation restore。

## Implementation Steps

1. Characterize CLI 的 default 與 explicit `--no-mcp`，以及 Desktop service 缺省/explicit false 的 protocol semantics。
2. 加最小 regression tests：
   - CLI default `True`；`--no-mcp` only path `False`。
   - GUI 正常 create 不再送 `false`；可選擇省略欄位讓 backend default 生效，或明確送 `true`，但整個 codebase 只能有一個清楚 default owner。
   - Backend explicit `loadMcp:false` 仍可被 direct caller 使用，不把欄位刪成永遠無法關閉。
3. 修改 React 的單一正常 create path；檢索所有 `session.create` caller，證明沒有另一個 GUI path 保留 hidden false default。
4. 用 injected fake loader/protocol spy 驗證，不啟動 external MCP、provider 或 credential lookup。

## Acceptance Criteria

- CLI 無 flag 預設 on、`--no-mcp` 明確 off。
- GUI normal session create 預設 on。
- Backend explicit false 仍有明確、測過的 opt-out semantics；錯誤修復不等於移除 protocol control。
- Session-create retry/restart path 與首次 create 使用相同 default，不因 cached frontend state 回到 false。
- 沒有 MCP network/process call、dependency、manifest/lockfile 或 unrelated UI change。

## Focused Verification

從 Linux/Conda `app` 執行，selector 可依 live test 名稱縮小但不得省略三種 default/opt-out branch：

```bash
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_chat_cli.py tests/test_desktop_service.py -q

cd /home/minervamuses/research-agent-workspace/app/desktop
node --test --experimental-strip-types tests/conversations.test.ts
```

再執行：

```bash
git diff --check
```

## Handoff Evidence

在 `build-log.md` 記錄：

- CLI default/opt-out spy 收到的 exact boolean。
- GUI normal create payload 是否省略或明確設 `true`，以及為何選此 single owner。
- 檢索到的所有 session-create callers。
- Focused command exact outcomes、diff files 與 local commit disposition。

不得以「backend 本來 default true」取代 GUI caller regression evidence。
