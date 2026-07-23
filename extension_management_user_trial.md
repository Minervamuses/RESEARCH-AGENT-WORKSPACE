# Extension Management 使用者沙盒試用紀錄

日期：2026-07-23

分支：`repair_temp`

環境：WSL Ubuntu 24.04、Python 3.12、source checkout

## 試用方式與可信度

這次不是只驗證 registry JSON，也不是把 MCP loader mock 掉。驗收測試從使用者會碰到的 slash command 開始，實際經過：

- `/Extension-Management status`、`--dry-run`、互動確認與 apply handler。
- Package 內的私有 Extension-Management Skill fresh read。
- 真實 drop-in 掃描、hash、staging copy、受管理副本與 atomic registry。
- Restart startup loader、Skill runtime、pinned reference 與 task mode。
- `langchain-mcp-adapters` 加上本機 FastMCP stdio subprocess。
- 真實 MCP tool discovery 與一次 tool call。

唯一替身是「管理規劃用的外部 LLM」：測試用 deterministic model 對 host 提供的每個 authoritative change 回傳一項合法 plan。這樣不需要 OpenRouter credential，也不會讓沙盒結果受模型隨機性影響；plan coverage、bundle validation、批准、copy、registry、startup 與 process execution 都仍是 production code。

沙盒使用 pytest 的獨立 `/tmp` 目錄；測試結束後由 pytest 清除，不碰 source checkout 的 `app/tool/` 或使用者 state。

## 試用 bundle

### Skill

- ID：`sandbox-writer`
- 有 `SKILL.md`、strict `manifest.yaml`、task mode `demo`。
- 有一份 pinned `references/checklist.md`。
- 先安裝 version-one，再改成 version-two，最後從 drop-in 移除。

### MCP

- ID/family：`sandbox`，scope=`global`。
- POSIX bundle executable，stdio transport；不需 build、install 或 network。
- 兩個 environment binding 從 host env 注入；registry 不保存其值。
- 提供 `sandbox_echo`，實際呼叫 `hello` 應回傳 `sandbox:hello`。
- Process 啟動時寫一個沙盒 marker，用來區分 apply 與 restart 後 execution。

## 使用者旅程結果

| 操作 | 實際觀察 | 結果 |
|---|---|---|
| 初始 `status` | 顯示正確 drop-in/state root；desired=2、applied=0、running=0、restart=false | 通過 |
| `--dry-run` | 列出 Skill/MCP add；MCP 顯示 command、args、cwd、env source、family/scope、binding hash | 通過 |
| Dry-run 零寫入 | 執行後 state root 仍不存在 | 通過 |
| Apply add | revision `0 -> 1`，Skill 與 MCP 都為 added，restart=true | 通過 |
| Apply 不執行 MCP | Marker 不存在；原始 Skill/MCP tree hash 完全不變 | 通過 |
| 目前 session 不變 | running revision 仍為 0，Skill catalog 仍為空 | 通過 |
| Restart 載入 Skill | 新 catalog 出現 `sandbox-writer`；task mode、version-one 指令與 pinned reference 可讀 | 通過 |
| Restart 載入 MCP | 真實 subprocess 回報 `sandbox_echo`，family map 為 `sandbox`，global scope 生效 | 通過 |
| 真實 MCP call | Adapter 回傳 text content `sandbox:hello`；此時 marker 才出現 | 通過 |
| Restart 後 `status` | applied=2、revision 1、running revision 1、restart=false、running MCP=`sandbox` | 通過 |
| Skill update | Apply 後 revision `1 -> 2`；舊 runtime 仍是 version-one，新 startup 才是 version-two | 通過 |
| Skill delete | Apply 後 revision `2 -> 3`；當前 session 仍保留 Skill，新 startup 才移除 | 通過 |
| MCP 保留 | Skill 刪除後 registry 只剩 `mcp:sandbox`，MCP spec 仍可載入 | 通過 |

主要實際輸出節錄：

```text
Extension Management applied revision 0 -> 1
- mcp:sandbox: added: Accept validated add for next restart.
- skill:sandbox-writer: added: Accept validated add for next restart.
restart_required: true

MCP call after restart:
[{'type': 'text', 'text': 'sandbox:hello', ...}]

Extension Management applied revision 1 -> 2
- mcp:sandbox: unchanged: source hash unchanged
- skill:sandbox-writer: updated: Accept validated update for next restart.
restart_required: true

Extension Management applied revision 2 -> 3
- mcp:sandbox: unchanged: source hash unchanged
- skill:sandbox-writer: removed: Accept validated delete for next restart.
restart_required: true
```

可重現指令：

```bash
cd app
.venv/bin/pytest -q -s tests/test_extension_user_journey.py
```

結果：`1 passed, 1 warning in 1.81s`。Warning 是既有 LangGraph pending-deprecation warning，與 extension flow 無關。

## 額外的負向觀察

第一次真啟動時，沙盒 descriptor 使用泛稱 `python`。在本環境它解析成 `/usr/bin/python3.12`，該直譯器沒有安裝 MCP package，因此 server 出現 `ModuleNotFoundError`。結果是該 MCP 被 loader 跳過、工具清單為空，但 CLI/其他 extension 沒有崩潰。改成真正 ready-to-run 的 bundle executable 後，完整旅程通過。

這件事證明兩點：

1. 單一 MCP startup failure isolation 有效。
2. Apply 刻意不做 probe process，所以只能確認 entrypoint/descriptor/binding 合法，不能保證 runtime dependency 已存在。下載的 MCP 若依賴 host interpreter，使用者仍需確保那個 resolved interpreter 具備依賴；較穩妥的是提供可直接執行的 bundle artifact。

FastMCP 的 INFO log 會從 drop-in process 的 stderr 顯示在終端。現有 adapter 的 stdio connection schema 沒有提供 stderr file handle；為了維持 drop-in 的 direct argv、避免另造 process supervisor，本輪沒有加 shell wrapper。這不影響工具結果，但屬於可見噪音，列為後續可改善項。

## Wheel 與完整回歸

另以 `poetry build -f wheel` 建出 `agent-0.1.0-py3-none-any.whl`，確認 wheel 內含：

- `tool/_internal/extension-management/SKILL.md`
- `tool/local/README.md`
- 全部 `agent/extensions/*` production modules

再把 wheel `--no-deps` 安裝到獨立 `/tmp` target，從非 repo cwd import：

- Private Skill 成功解析到 wheel target 內的 package resource。
- Drop-in root 成功解析到 `$XDG_DATA_HOME/research-agent/tool`。
- State root 成功解析到 `$XDG_STATE_HOME/research-agent/extensions/<workspace-id>`。
- 沒有嘗試寫入 site-packages。

最後完整測試：

```text
673 passed, 1 warning in 8.86s
```

## 成果分析

就原始目標而言，v1 已達到可落地：使用者可以只放入/移走 bundle、跑一個 slash command、確認並重啟，完成 Skill 與 ready-to-run stdio MCP 的增改刪，不必為每個 extension 修改 host Python。Apply 與 runtime 分開，避免同一 session 熱切換帶來的 graph/process 複雜度；私有管理 Skill、model plan 與 host mutation 也有清楚權限界線。

仍需誠實保留的邊界：

- 沒有在本輪呼叫真實 OpenRouter 管理模型；外部模型品質需有 credential 的人工 smoke test，但錯誤/漏項輸出會被 host schema 與 coverage check 拒絕。
- 實際 process 驗收在 WSL/POSIX；native Windows 本輪沒有跑真 MCP executable journey（一般 path/schema 行為有自動測試）。
- Apply 不執行 MCP dependency probe；錯誤依賴會在重啟時顯示 `applied_but_unavailable`。
- Drop-in MCP stderr 目前可能出現在終端。
- v1 仍刻意不支援 Local Tool 動態 import、build/install/download、remote MCP transport、背景 watcher或同 session 熱切換。
