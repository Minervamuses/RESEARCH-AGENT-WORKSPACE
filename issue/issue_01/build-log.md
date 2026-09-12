# Issue 01 — 執行紀錄

本檔是唯一 runtime phase 狀態與實際執行證據來源。
計劃內的命令是預定驗證，不是通過紀錄。

## 階段狀態

| Phase | 狀態 | 開始 | 完成 | 證據 | 阻塞 |
|---|---|---|---|---|---|
| 01 — 重現與分流 | Complete | 2026-09-12 | 2026-09-12 | Native Unicode baseline; engine and next experiment approved below | — |
| 02 — 最小修正 | Not started | — | — | — | — |
| 03 — 完整驗收 | Not started | — | — | — | — |

只使用 Not started、In progress、Blocked、Complete。
只有該階段所有必要驗收均有觀察證據才標 Complete。
尚待決定的前置條件由 GOALS／phase 保存，不在此複製計劃內容。

## 證據規則

- 每筆記錄包含日期與時區、phase、狀態變更、直接相關檔案、
  exact command／人工程序、pass／fail／skipped／unavailable、觀察與限制。
- 區分親自觀察、使用者回報、歷史資料與預定行為。
- 實際 IME journey 記錄引擎／輸入方式、控制程式與 backend、
  測試文字、候選確認前後的 turn 數、canonical input 與重載結果。
- 記錄額外授權的確切範圍與來源；不含 secrets、整份環境 dump、
  私人對話或無關終端輸出。
- 每個完成條件連結到對應證據；必要證據缺失或矛盾就保持未完成。
- 重大更正追加到活動紀錄，不刪除影響後續判斷的失敗歷史。
  material discovery 放 context，真正 review finding 放 code_review。

## 活動紀錄

尚無 implementation 活動。此次只撰寫計劃與做 authoring 檢查，
未啟動 Desktop、安裝 IME、修改應用、執行應用測試或完成中文輸入驗收。

### 2026-09-12 16:22–16:35 +08:00 — Phase 01 baseline (In progress)

- Authorization: user requested execution of issue/issue_01 and a commit for every
  completed step. This explicitly authorizes these commits; the package/IME daemon
  approval gates in PLANS still apply. User subsequently handed over the computer
  and requested continued execution without marking the temporary UI interruption
  Blocked. No Blocked state was written.
- Root / runtime: /home/minervamuses/research-agent-workspace; Windows is only the
  WSL invocation / native window control host. All project commands use Ubuntu-24.04
  Bash, /usr/bin/git and Conda app Python/Poetry/Node/npm/Cargo/rustc.
  Python 3.13.14, Poetry 2.4.1; branch GUI, initial HEAD
  2e54f804e2ec9003e97213fb17c7d33a9b6dd4c4; initial working tree clean.
  Root AGENTS.md is the only repository AGENTS.md. rg unavailable; used find/git.
- Reviewed main.py, App.tsx composer/sendTurn, server.py fixture opt-in,
  fixture_session.py root restriction, existing conversation/fixture tests, and all
  issue_01 plan files. No production/test code changes.
- Environment observations: DISPLAY=:0, WAYLAND_DISPLAY=wayland-0, LANG=C.UTF-8;
  no GTK_IM_MODULE/XMODIFIERS/QT_IM_MODULE/GDK_BACKEND reported.
  command -v found no ibus/ibus-daemon/fcitx/fcitx5 or listed GTK demo/editors;
  dpkg-query found no ibus/fcitx5/ibus-chewing; no matching IME processes.
  GTK 3.24.41-4ubuntu1.3 and WebKitGTK 2.52.6-0ubuntu0.24.04.1 installed.
  busctl --user --no-pager list succeeds, with no active IBus service observed.
  Presence of both display variables does not establish the actual WebView backend.
- Existing controls: /usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/MiniBrowser
  supports --editor-mode and GTK options; gtk-builder-tool supports preview of a
  temporary GtkBuilder input. No additional control package is currently required.
  Same-engine control comparison is not yet run because the engine is absent.

Commands below ran in Bash after:
```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace
command -v bash git python poetry node npm cargo rustc
git branch --show-current
git rev-parse HEAD
git status --short
printenv DISPLAY WAYLAND_DISPLAY LANG GTK_IM_MODULE XMODIFIERS QT_IM_MODULE GDK_BACKEND
command -v ibus ibus-daemon fcitx5 fcitx gtk3-demo gtk4-demo gedit gnome-text-editor
dpkg-query -W ibus fcitx5 ibus-chewing libgtk-3-0t64 libwebkit2gtk-4.1-0
ps -eo pid,comm | grep -E 'ibus|fcitx|research-agent|cargo|tauri'
busctl --user --no-pager list
/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/MiniBrowser --help
gtk-builder-tool --help
```

Focused checks (pass; neither is native IME evidence):
```bash
cd /home/minervamuses/research-agent-workspace/app/desktop
node --test --experimental-strip-types --test-name-pattern="composer sends" tests/conversations.test.ts
# 1 passed, 0 failed; duration 3745 ms.
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_desktop_fixture.py::test_real_service_round_trip_registration_restore_and_final_only_answer -q
# 1 passed, 1 existing LangChainPendingDeprecationWarning; 0.27 s.
```

Native baseline:
- Created owned /tmp/research-agent-desktop-phase02-GrASHQ using mktemp -d
  /tmp/research-agent-desktop-phase02-XXXXXX. The first PowerShell/WSL invocation
  lost the shell-expanded fixture-root argument: /proc/1250/environ showed an empty
  RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT. No backend was started or message sent.
  Closed only that process (kill -TERM 1250), then used literal env arguments:
```powershell
wsl -d Ubuntu-24.04 -- env RESEARCH_AGENT_DESKTOP_FIXTURE=phase02 RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT=/tmp/research-agent-desktop-phase02-GrASHQ bash -lc 'source /home/minervamuses/miniconda3/etc/profile.d/conda.sh && conda activate app && cd /home/minervamuses/research-agent-workspace && python main.py'
```
- Verified both opt-in values in /proc/1702/environ. Cached Tauri dev compilation
  finished in 0.17 s. The native window was captured through @oai/sky.
  A user-input notification interrupted the first UI attempt; no backend/send
  action occurred. Closed that owned window via kill -TERM 1702.
  After user handed over the computer, reran the exact literal-env command above;
  cached dev compilation finished in 0.19 s. EGL/MESA warnings appeared, but the
  native app rendered and accepted input.
- Native UI steps through sky: Start local backend; confirm Project One with two
  seeded conversations and Project Two with one; select p1 conversation
  28b222e0cc6543aa8d7bbdc423de99a7 (initial 1 turn).
- Focus composer; Control_L+space, then physical a: only ASCII a appeared, with no
  visible preedit/candidate window. This is a limited absent-engine observation,
  not proof about the user's intended engine or every Windows input shortcut.
- Selected draft, inserted literal 中文測試 via sky.type_text. This is explicitly
  not composition evidence. Then Control_L+a, Control_L+c, BackSpace,
  Control_L+v: the native composer visibly restored 中文測試 from the clipboard.
- Return once: composer cleared; transcript showed 中文測試 and fixture response;
  count changed from 1 to 2. Switched to conversation f2ddf2369f994905afa0b85d8cca79b1
  and back: restored user turn still displayed 中文測試, count remained 2.
- Read fixture canonical JSON with Conda app Python/json:
  store/conversations/28b222e0cc6543aa8d7bbdc423de99a7.json.
  Second turn 26f68174f5a34c6291204004331aeb11: completed/conversational,
  displayInput == semanticInput == "中文測試"; exactly two total turns.
  No model provider, real user store, tool marker or crash path was used.

Next checkpoint:
- Unicode path passes the native comparison. Missing Linux IME is the supported
  next hypothesis; no evidence currently justifies an App.tsx/main.py patch.
- Input-method preference was requested (Chewing/Bopomofo, Cangjie, Pinyin, or
  Windows-only) and is still pending. No engine has been chosen for the user.
- Read-only candidate sizing for the conditional Bopomofo option:
```bash
apt-cache policy ibus ibus-chewing
apt-get -s --no-install-recommends install ibus ibus-chewing
apt-get --print-uris --assume-no --no-install-recommends install ibus ibus-chewing ibus-gtk3
```
  Last command reports 21.4 MB download, +165 MB disk, 14 new packages and 3
  dconf upgrades. Candidate ibus/ibus-gtk3 1.5.29-2, ibus-chewing 2.0.0-1build2.
  No download/install/daemon/configuration action was performed.
  Planned install, only if user selects and approves:
  sudo apt-get install --no-install-recommends ibus ibus-chewing ibus-gtk3.
  Then inspect installed help, start one session-local IBus daemon and select
  chewing; use process-local GTK_IM_MODULE only if the comparison requires it.
  No shell startup/autostart/systemd change is proposed.
- Phase 01 remains In progress pending preference and agreed next experiment.
  Phase 02/03 have not started. Native real composition, candidate Enter,
  same-session controls and Desktop-restart acceptance remain unverified.
- External context checked, not substituted for local evidence:
  https://github.com/microsoft/wslg/issues/9 (still Open; Linux IME requires setup);
  https://packages.ubuntu.com/noble/ibus-chewing (package/version/dependencies).
  Ubuntu manpages web lookup failed; installed help will be used after approval.

### 2026-09-12 +08:00 — Phase 01 completed; Phase 02 authorized

- User approved the proposed Traditional Chinese Bopomofo / IBus Chewing option,
  package installation, session-local daemon and acceptance work, and explicitly
  granted all additional approvals required within issue_01. Do not repeat these
  requests. Authorization remains scoped to issue_01.
- Phase 01 criteria: native absent-engine physical-key attempt and clipboard /
  persistence comparison are recorded above; environment/control availability,
  input preference and both focused checks are established. Same-engine controls
  are deferred under Phase 01's explicit missing-IME exception to Phase 02.
- Next experiment: install ibus, ibus-chewing, ibus-gtk3; compare existing GTK /
  WebKit controls with the actual composer in the same session. No app patch is
  justified by the present evidence.
- Resume preflight: same Linux / Conda app toolchain and GUI branch; clean tree
  at 7d9a9e8. No research-agent or IME process found. sudo -n true reports a
  password is required; use WSL's authorized root invocation for OS installation,
  while project commands and IME/Desktop stay under minervamuses.
