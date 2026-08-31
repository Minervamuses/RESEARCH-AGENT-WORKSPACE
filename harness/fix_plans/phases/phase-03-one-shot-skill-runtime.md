# Phase 03 — One-shot Dynamic Skill Runtime

## Initial Status

Not started.

## Dependencies

None.

## Objective

在 Python core/CLI 建立非 Citation Skill 的 canonical `/<skill-name> <自然語言 prompt>` 一次性執行契約，移除一般 `/skill` persistent activation 與 Task mode 全鏈，讓 Desktop Phase 04 能直接重用同一 parser/resolver/runtime。

## Product Contract

- Dynamic command source 只來自當前 `ChatSession.loaded_skills`，包含 session startup 已合併完成的 built-in 與 applied extension catalog；command namespace 不掃描另一份 filesystem catalog。
- Static built-in command/alias 優先。至少 `/help`、`/status`、mode/thinking、extension management、knowledge commands、`/citation`、clear/quit/exit 等現行 static names 不可被 dynamic Skill 覆寫。
- Command 名稱必須是已驗證、可安全表示為單一 slash token 的 canonical Skill name。Applied extension 既有 lowercase kebab-case validation 要重用；built-in invalid/duplicate/collision 要 fail closed。現行可手動啟用的 `_prompt-master` 保留為唯一 built-in named underscore exception，可用 `/_prompt-master <prompt>`；不得把此例外開放給 extension 或其他名稱，若要移除它需 fresh product authority。
- Canonical input 是 `/<skill-name> <自然語言 prompt>`。Parser 用 `ParsedSlashCommand.raw_text` 等價來源保留 command 後方原始文字，不用 `shlex args` 重組空白/引號。
- Empty prompt 在 model/activation 前回傳 bounded usage error；不建立「armed for next turn」state。
- Slash wrapper 只選 Skill；送進 agent/history/Plan log 的 user input 是 trailing natural-language prompt，不把 command token 當成模型任務內容。
- CLI `/help`、completion 與 available-command diagnostics 都由該 session 的 static registry + validated dynamic catalog 產生，不能使用 global/stale 另一份 catalog。

## Citation Exception and Interaction Matrix

本 phase 不改 Citation handler、registry、finalizer 或 thinking policy，但必須避免 generic runtime 破壞現行 boundary：

1. 起始沒有 Citation：unknown/empty/invalid/load failure 或 turn terminal error 後，沒有任何非 Citation Active Skill/Task mode 殘留。
2. Citation 已 active：unknown command、empty prompt、collision 或 target Skill load failure 發生在成功切換前，現有 Citation/session registry 保持不變；不能因 parser error 提前 teardown。
3. Citation 已 active，且另一個 valid Skill 成功啟動：沿用現行「切換 Skill 會 teardown Citation且不恢復舊 Skill」語意；該 one-shot terminal 後為 none，不把 Citation 偷偷 restore。
4. `/citation` 永遠走 static handler，不進 dynamic resolver。本輪 focused regression 只保護現行 CLI 行為，不宣稱 Citation 已一次性化。

## Causal Scope

### Expected core/CLI production write

- `app/agent/skills/manifest_schema.py`
- `app/agent/skills/runtime.py`
- `app/agent/state.py`
- `app/agent/session.py`
- `app/agent/thinking/orchestrator.py`
- `app/agent/cli/slash_commands.py`
- `app/agent/cli/chat.py`
- `app/agent/cli/prompting.py`

### Expected metadata/docs write

- `app/skills/_prompt-master/manifest.yaml`
- `app/skills/academic-paper-writing/manifest.yaml`
- `app/SKILLS_GUIDE.md`
- 只有 live grep 證明仍向 model 宣告 Task mode 的現行 system-prompt owner。

### Expected tests

- `app/tests/test_slash_commands.py`
- `app/tests/test_chat_cli.py`
- `app/tests/test_skills.py`
- `app/tests/test_skill_runtime.py`
- `app/tests/test_state.py`
- `app/tests/test_citation_slash_command.py`
- `app/tests/test_citation_skill_activation.py`
- `app/tests/test_extension_skill_startup.py`
- `app/tests/test_extension_user_journey.py`

Desktop service/protocol/UI 屬 Phase 04。Phase 03 可更新 minimal fake session interface 讓 Python tests 編譯，但不得提前做 GUI redesign。

## Non-goals / 非目標

- 不重設 Citation handler/registry/finalizer/thinking semantics 或新增 GUI Citation 入口。
- 不修 Fusion/Extended Thinking 與 Skill 的產品相容性，不強制把現行 thinking mode 切到 normal；只做移除共用 Task mode 欄位所需的機械調整並保留可證明的既有行為。
- 不修改 Desktop React/Rust/protocol control surface；留給 Phase 04。
- 不新增 persistent Skill state、compatibility alias、dependency 或 second command registry。

## Required Runtime Lifecycle

1. 在 session turn lock 內 parse/resolve dynamic Skill command。
2. 先驗證 static collision、catalog membership、manifest/runtime load 與 non-empty prompt；失敗時保持 pre-command state。
3. 成功後建立 transient runtime，套用 Skill context/access policy，透過現有 thinking dispatch 執行 exactly one agent work with trailing prompt；不得暗中強制 normal。Fusion/Extended-specific 缺陷不在本 phase acceptance。
4. `try/finally` 等價 cleanup 覆蓋 success、graph/provider/tool/finalizer/persistence error、`CancelledError`、CLI interrupt 與 session/backend shutdown。
5. Cleanup 只清除該次 transient runtime；不得以 snapshot 恢復先前 generic Skill。Citation success-switch 依上節明確 teardown/no-restore。
6. 下一個普通 input 不帶 Skill command時，agent state、thinking status與prompt都不含前次 Skill/Task mode。

## Task-mode and Persistent-control Removal

- 刪除 manifest `task_modes` schema、runtime `task_mode`、agent state/status/prompt/Thinking propagation 與 validation。
- 刪除一般 `/skill <name> [mode]`、`/skill none`、mode-selection/completion/help/status文字。
- 清理 built-in manifests與 `SKILLS_GUIDE.md`，Skill 自己的指令/內容負責路由。
- 不保留 deprecated compatibility alias、hidden persistent activation或 generic adapter。只為 Citation static handler 保留它本身必要的 activation seam；命名/visibility 要讓 generic callers不能繞回 persistent control。
- Applied extension manifest 若仍含已移除的 `task_modes`，必須得到 clear bounded startup/apply unavailable diagnostic；不得 silent ignore，也不得保留 compatibility shim。Extension guide/journey tests 要固定此契約。
- 使用 repository search 證明 production、manifest與user-facing docs 不再含 Task mode contract；test fixture 只可在明確 legacy-input test 中出現。

## Catalog Validation

- 重用現有 startup/discovery validation，新增最小 dynamic command projection；React 不參與。
- Invalid、duplicate或static collision entry 必須無法被 command dispatch。Executor可依現有 startup policy選擇「拒絕該 entry並提供 bounded diagnostic」或「fail session startup」，但要用 test固定且不允許 hijack；不要為此建立第二個 registry。
- `_prompt-master` 依現行手動啟用行為保留為唯一 underscore command exception；startup/help/completion 與 dispatch 都要一致，不把 exception 泛化。

## Acceptance Criteria

- CLI 能用 loaded Skill name執行一次自然語言工作，原始 prompt保留；緊接普通回合沒有Active Skill。
- Empty/unknown/invalid/collision/load failure在model前停止，符合Citation interaction matrix且無generic transient residue。
- Success、provider/graph/finalizer/persistence failure、cancel/interrupt/shutdown都執行cleanup。
- `/skill` persistent command與Task mode全鏈從core/CLI/manifests/docs消失；沒有 compatibility state。
- Session-specific `/help`/completion 列出 validated dynamic commands 與 `/_prompt-master`；legacy extension `task_modes` 得到清楚 unavailable diagnostic 而非忽略。
- `/citation` existing focused tests通過，且額外覆蓋 active Citation→failed generic command保持、active Citation→successful other Skill teardown/no-restore。
- 不新增dependency、不改Citation implementation semantics、不做Desktop UI/protocol、不呼叫provider。

## Focused Verification

```bash
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_slash_commands.py tests/test_chat_cli.py tests/test_skills.py tests/test_skill_runtime.py tests/test_state.py tests/test_extension_skill_startup.py tests/test_extension_user_journey.py -q
poetry run pytest tests/test_citation_slash_command.py tests/test_citation_skill_activation.py -q
```

另以 repository search 檢查 production/manifests/docs 的 `task_mode`、`task_modes` 與 generic persistent `/skill` references；因 WSL 未必安裝 `rg`，可使用 `grep -R` 並排除 cache/generated directories。

```bash
git diff --check
```

## Handoff Evidence

在 `build-log.md` 記錄：

- Static/dynamic namespace集合、invalid/collision disposition與 `_prompt-master` handling。
- Raw trailing prompt round-trip example。
- 各terminal branch cleanup observation與下一普通turn state。
- Citation interaction matrix的spy/registry observations；明確寫「Citation redesign未執行」。
- Task mode/persistent `/skill` search結果、focused tests、diff與local commit disposition。
