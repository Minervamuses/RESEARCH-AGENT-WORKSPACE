# Issue 02 — Desktop Slash Command Menu：執行計劃

## Plan Overview

- **Plan root:** `issue/issue_02`。
- **目的：** 完成 [GOALS.md](GOALS.md) 的 session catalog、composer 選取與生命週期驗收。
- **Execution mode:** Autonomous within authorization envelope；使用者明確啟動後，
  在本節授權範圍內連續完成各 phase，不逐階段重複詢問。
- **Repository shape:** Application；一個 Python/Poetry project 加 Tauri/React Desktop。
- **Change risk:** Medium；跨三語言 contract 且 Enter／IME 錯誤可能誤送訊息，
  但不需資料遷移、provider 呼叫或新基礎設施。
- **Phase directory:** `phases/`。沿用 `issue/issue_03`、`issue/issue_10`；
  根 `.gitignore` 忽略所有 `build/`，因此不用該目錄名稱。

## Source-of-Truth Map

| 內容 | 唯一 owner |
|---|---|
| 穩定目的、成功條件、scope、invariants、使用者決策 | [GOALS.md](GOALS.md) |
| 順序、依賴、授權、停止條件、計劃維護 | 本檔 |
| 可直接複製的啟動與續作指令 | [PROMPTS.md](PROMPTS.md) |
| 各 phase 的做法、檢查、驗收 | `phases/phase-*.md` |
| 實際 phase status 與 observed evidence | [build-log.md](build-log.md) |
| 實作後才出現的 material discoveries | `context/phase-NN-context.md` |
| 實際 review findings | `code_review/phase-NN-review.md` |

初次 authoring 不建立 context 或 review 檔。Live repository 與實際觀察優先於過時計劃。

## 已確認 Repository Baseline

2026-09-12 authoring 的 read-only preflight：

- Root：`/home/minervamuses/research-agent-workspace`；branch `GUI`，
  HEAD `2870bcd75eb809120f9e4bb7a2ab1668330946d6`；initial
  `git status --porcelain=v1 --untracked-files=all` 無輸出。不要重設或切換到此 HEAD。
- Windows PowerShell 透過 `wsl -d Ubuntu-24.04 -- bash -lc` 操作 Linux。
  source `/home/minervamuses/miniconda3/etc/profile.d/conda.sh` 後 activate `app`。
  Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0、Cargo 1.97.1
  均解析到 Conda `app/bin`；Git 是 Linux `/usr/bin/git`。
  Linux 未提供 `rg`，本輪使用 `find`／`grep` 替代，未安裝工具。
- `SlashCommandRegistry.all_commands/matching_commands/get` 已處理 registry 查詢；
  `build_default_registry(session)` 從 loaded skills 建立 dynamic commands，保留
  static／alias collision 規則。`SlashCommand` 已有 name／description，
  沒有 argument schema。直接補 `/<name> ` 足以讓使用者接續參數。
- `DesktopService._session_turn` 共用 Python parser，但用
  `_DESKTOP_SLASH_COMMANDS` 加 dynamic `skill_name` 判定 Desktop eligibility，
  並拒絕 alias。不要把此集合複製到 React。
- `_session_create`／`_session_select` 使用 `_session_snapshot` 回傳
  `loadedSkills`、`extensionRevision` 等資料，但沒有 command catalog。
  同 session select 仍須回傳其當前 snapshot；另一 session 會重新 materialize。
- `ChatSession.create`／`load_session_startup` 建立 session startup Skill catalog；
  extension apply 不替換目前 session。Desktop 已有 restartRequired／revision UI。
- JSON contract 的 nested objectArray 已由 Python generic validator 支援；
  TypeScript result schema／DTO 與 Rust `validate_session_snapshot` 手動 mirror，
  都需要與新增欄位一致。`fixtures.json` 由三語言 tests 共用。
- `App.tsx` 的 `onComposerKeyDown` 目前只呼叫
  `shouldSubmitComposerKey`；已有 IME guard。`selectConversation`／
  `createSession` 已檢查 generation。`backend.ts` 存放 session DTO，
  `conversations.ts` 管理 draft／selection／turn。
- `app/desktop/tests/conversations.test.ts` 透過既有 Vite SSR 載入 App helpers；
  有 Enter／Shift+Enter／IME 測試。這不是原生 DOM event 驗證。
- 既有隔離 GUI 入口：`agent/desktop/server.py::_build_runtime_service` 以
  `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02` 啟用 `fixture_session.py`；需要
  `RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT` 指向 owned、非 symlink、直接位於 `/tmp`
  且名稱開頭為 `research-agent-desktop-phase02-` 的目錄。Tauri child 繼承此環境，
  fixture 共用真實 DesktopService，fake session 支援 Skill routing，無 live provider。
- Commands 來源：根 `README.md`、`AGENTS.md`、Desktop `package.json`。
  舊 `issue/issue_03/build-log.md` 曾記錄 pytest 約 24 秒、Node 約 4 秒、
  Tauri build 約 74 秒；這些僅供成本參考，不是本計劃通過證據。

本輪未執行 application tests、build、GUI journey 或 provider 呼叫。

## Execution Authorization

### Launch gate

本 authoring 僅寫七個 planning artifacts。實作前，使用者需送出
`PROMPTS.md` 的完整 Start/Resume prompt，或以等價文字明確批准：

1. 在目前 protocol-v1 的 session.create／session.select snapshot 新增
   `slashCommands` catalog，並同步 JSON、Python producer、TypeScript、Rust、
   shared fixtures；這是可檢閱的 protocol 變更，不宣稱舊版 client 相容。
2. 修改本節列出的超過三個直接必要 production files。
3. 在此 bounded scope 內完成三個 phases，執行既有離線檢查及本機驗收。

一般的「讀計劃」或再次要求規劃不構成 launch。未獲啟動授權只能 read-only preflight，
不得把計劃的未來授權寫法當成使用者已批准。

### 啟動後的日常授權

- 修改以下直接必要既有 production files：
  `app/agent/desktop/service.py`、
  `app/desktop/protocol/v1/contract.json`、
  `app/desktop/src/protocol.ts`、
  `app/desktop/src-tauri/src/protocol.rs`、
  `app/desktop/src/App.tsx`、
  `app/desktop/src/styles.css`。
- `app/desktop/src/backend.ts`／`app/desktop/src/conversations.ts` 只有在既有
  session/draft lifecycle 無法正確失效 catalog 時才修改，先指出具體缺口；
  不新增全域 cache、store 或平行 state pipeline。
- 更新 shared `app/desktop/protocol/v1/fixtures.json` 與各 phase 明列的既有 tests；
  重用 fake session／tmp_path／Node SSR seams，不新增測試 framework 或 dependency。
- 在正確 Linux/Conda runtime 執行各 phase 必要、合理短的離線 tests/build；
  全 pytest suite 只在最後跑一次。估計超過十分鐘的命令不包含在此授權。
- 更新此 bundle 的 evidence、material context、實際 review 與受新證據影響的未開始計劃。
  不修改 `AGENTS.md`，不藉此同步其他 issue／計劃狀態。
- 使用與使用者 store 隔離的暫存資料，啟動既有本機 preview／Desktop 作人工操作驗收。
  不執行 ingestion、prune apply、真實 Skill provider turn 或 MCP 啟動來測清單。

這組檔案跨越 producer、wire validator 與 UI；單純改 textarea 或三個檔案以內
無法讓 registry 驅動的 catalog 通過現有所有 consumer validators。
預期不增加 dependency、長期服務或持久化維護面；總耗時須由實作時 preflight 判斷，
此計劃沒有承諾未量測的完工時間。

### 停止並取得新授權

- 必須改變 GOALS 的成功條件、non-goal、Skill lifecycle、alias 或 Desktop eligibility。
- 需額外 production scope、persistent module、dependency、lockfile、環境定義、
  IME／系統套件安裝、通用 framework 或新的 concurrency model。
- 超出已列 catalog 欄位的 public API、protocol method/version/envelope、儲存 schema、
  extension registry 或其他資料格式變更。
- 需 live/paid provider、credentials、真實使用者 store 寫入或外部系統操作。
- 需 commit、push、merge、rebase、branch/worktree change、deploy 或破壞性操作。
- 必要檢查無法取得，而接續或完成將失去成功條件的必要證據；不得默認視為通過。
- 預估命令超過約十分鐘，或昂貴驗證已失敗／未產生有意義結果而需要再跑。

同一問題兩次 focused implementation attempt 失敗後停止、記錄 causal hypothesis
與最小下一步；不得以擴張 scope 或反覆 full suite 嘗試解決。所有 applicable
`AGENTS.md` 與使用者工程規則持續有效。

## 階段路線圖

| Phase | 可觀察結果 | Depends on | Phase file |
|---|---|---|---|
| 01 — Command catalog | session snapshot 提供和 dispatch 一致、通過三語言驗證的 catalog | None | [phase-01-command-catalog.md](phases/phase-01-command-catalog.md) |
| 02 — Composer menu | 使用者能安全地探索、選取、補參數；catalog 不跨 session/generation 殘留 | Phase 01 | [phase-02-composer-menu.md](phases/phase-02-composer-menu.md) |
| 03 — Integration acceptance | 代表性跨層流程、Linux UI 與一次 broader regression 支持整體成功條件 | Phases 01 and 02 | [phase-03-integration-acceptance.md](phases/phase-03-integration-acceptance.md) |

Phase 01 將 producer 與所有 validators 放一起，避免用未對齊 contract 作為完成點。
Phase 02 擁有自己的互動與失效檢查；Phase 03 不代替前兩階段的 focused verification。

## 驗收覆蓋

| GOALS 中的情境 | 主要證據 owner |
|---|---|
| canonical built-ins／dynamic skills／collision／CLI-only | Phase 01 service + registry tests |
| catalog DTO、安全界線、舊欄位保留 | Phase 01 Python／Node／Rust contract tests |
| prefix／方向鍵／Enter selection／cursor／Escape／blur | Phase 02 focused helpers + 真實 UI；Phase 03 journey |
| 一般 Enter／Shift+Enter／IME／mouse／accessibility | Phase 02 regressions；Phase 03 Linux 原生操作 |
| A→B→A／restart／Skill revision／stale response | Phase 01 lifecycle；Phase 02 UI state；Phase 03 整合 |
| 最終 parser、CLI、trust 與資料行為不退化 | Phase 01 negative cases；Phase 03 broader suite |

## 計劃維護

- 唯一 runtime status 位於 `build-log.md`。任何 required check 失敗或缺失，
  phase 維持 `In progress`／`Blocked`，不得開始 dependent phase。
- 先診斷最小 causal hypothesis；live evidence 推翻未開始階段時，先修訂此 roadmap
  與受影響 phase，再繼續。不能強迫 repository 遷就錯誤計劃。
- 用 append-only correction 保留失敗與完成證據；GOALS 穩定需求只依使用者決策修改。
- interrupted work 先對照 live diff、已有 evidence 與 runtime，再跑最小確認，
  不盲目重跑昂貴或具副作用的步驟。
- 小型可逆改動以修復自己 scoped diff 回復，不 reset 使用者變更、不清除 store。

## 整體完成標準

- [ ] 三個 phases 在 build-log 均為 `Complete`，每個成功條件可連到實際證據。
- [ ] catalog／dispatch 一致，沒有 React allowlist、alias 擴張或額外 command 能力。
- [ ] Enter 選取零送出，之後明確送出恰一次；IME、mouse、focus 與 lifecycle
      都有對應驗證，沒有用 SSR 或 helper test 取代未觀察的原生行為。
- [ ] 三語言 protocol、focused tests、一次完整 pytest／npm／Rust checks 與 Linux
      source build 通過；不可用項目依停止條件處理，不能默認豁免。
- [ ] 檔案只涉及核准因果範圍，沒有 dependencies／persistent data／Git mutation。
- [ ] `git diff --check` 通過，未解限制、真實失敗及使用者接受的變更如實記錄。
