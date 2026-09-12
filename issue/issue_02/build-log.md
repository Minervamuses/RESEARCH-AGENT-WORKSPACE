# Issue 02 — Build Log

本檔是唯一 runtime phase status 與 observed implementation evidence owner。
計劃描述將做什麼；此處只記錄真正發生的事情。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Command catalog | Complete | 2026-09-12 | 2026-09-12 | Phase 01 evidence below | — |
| 02 — Composer menu | Blocked | 2026-09-12 | — | Phase 02 evidence below | Required native Linux UI journey unavailable |
| 03 — Integration acceptance | Not started | — | — | — | — |

只使用 `Not started`、`In progress`、`Blocked`、`Complete`。
必要驗收有實際證據才可 Complete；前置授權或 checks 缺失時不得繼續 dependent phase。

## 證據規則

- 記錄時間、phase、狀態變化、實際 changed files、exact command／操作、
  cwd／runtime、pass/fail/skipped/unavailable、簡短結果與相關 artifact。
- 分開實際觀察、歷史參考與 planned checks；預定命令不等於已執行。
- 不寫入 credentials、使用者資料、整份輸出或日常操作流水帳。
- 原生 keyboard、mouse、IME／screen reader 檢查記錄具體環境與看到的行為；
  不以 helper test 或 SSR markup 推論全部通過。
- 矛盾或錯誤以追加 correction 保留歷史，並更新本表。
- material discovery 才新增 `context/phase-NN-context.md`，
  真實 review 才新增 `code_review/phase-NN-review.md`。

## 活動紀錄

尚無 implementation activity。本次僅 authoring；application tests、build、
GUI 操作與各 phase planned verification 都尚未作為本計劃實作證據執行。


### 2026-09-12 — Phase 01 Complete

- Launch authorization: 使用者要求「執行 issue/issue_02，入口在 PROMPTS.md」，
  並明確要求「每一步皆需 commit」；依 Start/Resume 執行 bounded phases，
  每個 phase 一個 commit。後者覆蓋計劃內原有不含 commit 的限制；未授權 push。
- Preflight: root `/home/minervamuses/research-agent-workspace`、branch `GUI`、
  initial worktree clean。Linux bash/Git；使用 non-login bash，source Conda script
  並 `conda activate app` 後，Python 3.13.14、Poetry 2.4.1、Node 24.18.0、
  npm 11.16.0、Cargo 1.97.1 均在 Conda app。最初 login shell 找到 pipx Poetry，
  已改用專案規定的 explicit activation 並確認 interpreter，才開始 edits/checks。
- Changed: `service.py` 共用 registry resolver/eligibility 與 snapshot projection；
  JSON contract、TS DTO/validator、Rust validator 同步 required slashCommands；
  App permission fallback 使用空 catalog；shared fixtures 與 backend DTO fixture 適配；
  既有 service/conversation tests 增加 projection、bounds、排除命令與 lifecycle。
- Red (cwd app): `poetry run pytest tests/test_desktop_service.py -q -k session_catalog`
  → 2 failed，均為缺少 slashCommands 的 KeyError，確認缺失。
- Green (cwd app): `poetry run pytest tests/test_slash_commands.py tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py -q`
  → 225 passed；新增 lifecycle/shared negative cases 後執行
  `poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py -q`
  → 214 passed。既有 LangChain pending-deprecation warning 1 項。
- 一次 cwd 錯置：從 repo root 執行後一 pytest 命令，Poetry 找不到 pyproject；
  沒有執行 tests，隨即從 app 正確執行，結果如上。
- Desktop cwd: `node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts`
  → 首輪 112 passed，shared negative cases 後 117 passed；
  `cargo test --offline --manifest-path src-tauri/Cargo.toml protocol::tests`
  → 兩輪皆 12 passed（第二輪因 fixtures 更新）；`npm run build` → passed。
  既有 Rust manifest-driven tests 直接覆蓋 maxItems、缺失、nested keys/type/byte bounds；
  Python/TS/Rust shared traces 同時拒絕 missing/type/private nested key/過長 name/description。
- Observable service evidence: built-ins、writer、_prompt-master 有序列出；duplicate、
  reserved/alias collision、非法名稱及 CLI-only 被排除；手動未知/CLI-only 送出拒絕且
  model inputs 為空。create snapshot 包含 research；同 session select 保持 loaded catalog；
  A→B→A rematerialize 換新 skill，shutdown/select 換新 skill；fake extension apply 不更換
  當前 catalog。既有 dynamic skill one-shot routing tests 通過。
- Bounds decision: [context/phase-01-context.md](context/phase-01-context.md)。
- `git diff --check` passed；未新增依賴、未操作 live provider/user store。


### 2026-09-12 — Phase 02 implementation verified offline; Blocked on native UI

- Phase 01 committed as `b0ef3c7` (`feat(desktop): expose session slash command catalog`).
  Phase 02 preflight confirmed Phase 01 Complete, clean worktree, same Linux/Conda app
  toolchain and cached Node dependencies. No production changes outside App.tsx/styles.css.
- Changed: `app/desktop/src/App.tsx` adds local slash composer/list helpers and session
  catalog ownership gating; `styles.css` styles bounded scrollable list; existing
  `tests/conversations.test.ts` adds prefix/key-action/ownership/markup checks.
  No backend.ts/conversations.ts production edits, new modules, dependencies or stores.
- Catalog stays in the validated backend session DTO. Local ownership records only
  generation/project/session identity, invalidated at create/select/lifecycle start.
  Failed switching cannot restore the prior catalog. Composer remounts on session/generation
  changes; workspace operations and non-ready backend suppress selectable commands.
- Interaction implementation: focused single-token slash prefix, leading horizontal
  whitespace preserved, case-insensitive prefix matching, cyclic arrow navigation,
  Enter insertion followed by layout-effect focus/caret placement, Escape suppression
  until editing, blur close, pointer default suppression to preserve focus, inert descriptions,
  named listbox/options with active-descendant. Composition guard precedes all key actions;
  Shift+Enter/Tab retain defaults. The existing sendTurn path is unchanged.
- Red (cwd app/desktop, Conda app):
  `node --test --experimental-strip-types --test-name-pattern 'slash menu|menu Enter' tests/conversations.test.ts`
  → 2 failed because new helper functions did not yet exist.
- First green focused command:
  `node --test --experimental-strip-types tests/conversations.test.ts tests/backend.test.ts tests/trust.test.ts`
  → 36 passed. `npm run build` initially failed TS2345: nullable selection passed to
  sameSelection. Added the explicit null guard, then added ownership and markup assertions.
- Final same focused Node command → **38 passed**, 0 failed (~4.2 s).
  `npm run build` → **passed** (TypeScript and Vite). `git diff --check` → passed.
  Key-handler callback assertions observe selection request count 0, then explicit next
  Enter count 1; native request dispatch/focus/caret remain unobserved. SSR proves escaped
  description text and ARIA relationships only; no claim of screen-reader operation.
- Required UI preflight (read-only): DISPLAY=:0, WAYLAND_DISPLAY=wayland-0; X11 and WSLg
  Wayland socket paths exist. `timeout 3 xdotool getdisplaygeometry` → **124 timeout**;
  an earlier unbounded query was interrupted without GUI operations. `timeout 3 ibus engine`
  → **1**, IBUS_IS_BUS assertion / “No engine is set.” `command -v orca` found no executable;
  process-name scan found no local ibus/fcitx/orca/Xwayland/weston process. Environment variables
  and socket existence are not evidence that native UI is operable from this agent.
- No functioning native GUI operation tool is available in this session. No fixture GUI
  journey was claimed or run; no input-method/system package installation attempted.
  Required /, /sta, arrows, Enter, /ingest argument editing, Escape, blur, mouse, Shift+Enter,
  actual caret/focus and zero-request observations must be supplied on an operable Linux Desktop.
  Native IME/screen-reader evidence also remains unavailable for Phase 03.
- Per PLANS “必要檢查無法取得” stop condition, Phase 02 is **Blocked**, not Complete;
  Phase 03 stays Not started. Full pytest, full npm/Rust suites and Tauri source build are
  reserved for Phase 03 and have **not** been run. Resume after native UI evidence/environment
  is provided, or the user explicitly revises the required acceptance criteria.
- Phase 02 implementation and this truthful blocker record are committed together per
  the user's per-step commit instruction. No push/branch/worktree operation performed.
