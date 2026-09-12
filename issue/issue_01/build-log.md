# Issue 01 — 執行紀錄

本檔是唯一 runtime phase 狀態與實際執行證據來源。
計劃內的命令是預定驗證，不是通過紀錄。

## 階段狀態

| Phase | 狀態 | 開始 | 完成 | 證據 | 阻塞 |
|---|---|---|---|---|---|
| 01 — 重現與分流 | Complete | 2026-09-12 | 2026-09-12 | Native Unicode baseline; engine and next experiment approved below | — |
| 02 — 最小修正 | Complete | 2026-09-12 | 2026-09-12 | X11 native composition/candidate/turn acceptance below | — |
| 03 — 完整驗收 | Complete | 2026-09-12 | 2026-09-12 | Limited acceptance explicitly approved below; required available checks passed | Restart-dependent checks waived by user, not passed |

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

### 2026-09-12 16:49–16:56 +08:00 — Phase 02 installation / control checkpoint

- Executed authorized OS installation from Windows:
  `wsl -d Ubuntu-24.04 -u root -- apt-get install -y --no-install-recommends ibus ibus-chewing ibus-gtk3`.
  Pass, 8.98 s total; fetched 21.4 MB in 4 s. 14 new packages, 3 dconf upgrades,
  +165 MB as estimated; no autoremove or unrelated upgrade.
  Versions: ibus/ibus-gtk3 1.5.29-2, ibus-chewing 2.0.0-1build2.
  Package post-install automatically created the standard GNOME-session user-unit
  dependency under /etc/systemd/user/gnome-session.target.wants/; apt warned that
  gnome-session.target is absent. No custom startup or service was configured.
- Read `ibus-daemon --help`, `ibus help`, chewing.xml, and engine help.
  Existing `preload-engines` / `engines-order` were both @as []; no gsettings
  values changed. Started owned daemon as minervamuses:
  `ibus-daemon --daemonize --emoji-extension=disable` (PID 5750).
  Immediate `ibus engine chewing` raced bus startup and failed; retried after
  daemon readiness. It selected chewing, with a missing-setxkbmap warning and
  nonzero status. A subsequent `ibus engine` confirmed chewing; `ibus im-module`
  returned ibus. Do not treat the CLI warning as proof composition fails.
- Restarted fixture using the literal-env standard main.py command above;
  dev compilation 0.70 s, Desktop PID 5979. Started backend and selected original
  p1 conversation. Real source/transport/fixture unchanged.
- `grep im-ibus /proc/5979/maps` confirms actual Desktop loaded im-ibus.so.
  `ss -xnp` maps Desktop fd 4 inode 16252 to peer 17048 at
  /mnt/wslg/runtime-dir/wayland-0: actual Wayland connection established.
  No GTK_IM_MODULE or GDK_BACKEND override was applied.
- Created two temporary controls only inside the owned fixture root:
  ime-control.ui (GtkWindow with GtkEntry), ime-control.html (plain textarea).
  Launched `gtk-builder-tool preview /tmp/research-agent-desktop-phase02-GrASHQ/ime-control.ui`
  (PID 6355), and
  `/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/MiniBrowser file:///tmp/research-agent-desktop-phase02-GrASHQ/ime-control.html`
  (PID 6396). GTK fd 3 inode 20057 connects to Wayland peer 20925.
- Native sky.press_key c, l, 3 (standard Bopomofo hao3) displayed phonetic preedit
  and converted 好 in both controls; Return committed it. No literal Chinese
  insertion or clipboard operation was used for these composition observations.
  Down (GTK) / space (WebKit) did not expose a visible candidate popup in the
  returned window captures; this remains to be resolved/observed. App sentence,
  candidate Enter and final submit checks have not yet been completed.

### 2026-09-12 16:59–17:06 +08:00 — Phase 02 native acceptance (Complete)

- Wayland observations were insufficient for candidate/preedit UI acceptance:
  GTK/WebKit conversion worked, but no candidate list was visible in captures;
  the app showed committed 請 only after confirmation. No turn was submitted.
  Did not infer a React event defect or add a workaround.
- Compared an explicit X11 recipe. Closed only owned Desktop/control PIDs
  5979/6355/6396, and `ibus exit` stopped this task's daemon 5750.
  `xdotool` was already installed (3.20160805.1); no automation package added.
  Installed the missing keyboard-layout utility under existing authorization:
  `wsl -d Ubuntu-24.04 -u root -- apt-get install -y --no-install-recommends x11-xkb-utils`.
  170 kB download, +500 kB; 4.77 s. This removes the observed ibus engine CLI
  failure when it tries to invoke setxkbmap, without changing keyboard settings.
- Started `GDK_BACKEND=x11 ibus-daemon --daemonize --emoji-extension=disable`
  as minervamuses (PID 6968). After readiness, `ibus engine chewing` and
  `ibus engine` both succeeded. No GTK_IM_MODULE, XMODIFIERS or QT_IM_MODULE
  override was needed. No user gsettings values or shell startup files changed.
- Restarted main.py with the same fixture variables plus GDK_BACKEND=x11
  (Desktop PID 7207; cached dev compilation 0.64 s). Both temporary controls
  were also restarted with GDK_BACKEND=x11 (GTK 7430, MiniBrowser 7517).
  `xdotool search --onlyvisible --name '^Research Agent$'` returned 10485763;
  GTK 14680067, WebKit 16777234. ss -xnp confirms actual Desktop X11 sockets
  to /tmp/.X11-unix/X0, including fd 12 inode 28166 -> peer 31030.
- Control comparison: xdotool native XTEST key events c,l,3 displayed 好;
  Down exposed the numbered candidate list in both GTK and WebKit; 1,Return
  selected and committed the character. This uses the real installed IBus
  engine; no DOM dispatch, literal Chinese insertion or paste stands in for IME.
- App selected same p1 conversation (initial 2 turns). Native keys fu/3
  produced 請 preedit; Down exposed candidate list; Return confirmed candidate
  and closed that list. Canonical count remained 2, last input 中文測試.
- First punctuation shortcut Ctrl+period opened GTK's emoji popup. Dismissed it
  with Escape and cleared the pending preedit; no turn was submitted. Consulted
  installed docs and upstream Chewing usage; used Shift+period for 。 instead.
  This was an input-sequence correction, not a production-code change.
- Final exact physical-key sequence in focused composer:
  `xdotool type --clearmodifiers --delay 120 'fu/31; ji35/3xu35k4qu0 xjp4jp62k7u06ru.4z; z83'`
  then `xdotool key shift+period`.
  Preedit showed 請幫我整理這篇論文的研究方法。 (standard Bopomofo).
  `xdotool key Return` committed the composition into draft; screenshot retained
  draft and canonical count remained 2. Subsequent `xdotool key Return` cleared
  the composer and added exactly one completed logical turn (count 3).
- Conda app Python/json assertions passed: third turn
  326aad8f319543d4a0ff58b603955fa7 has displayInput == semanticInput ==
  請幫我整理這篇論文的研究方法。, state completed; UI user transcript matches.
- This establishes an environment-only working recipe on this host. It does not
  prove every Wayland setup is broken, or isolate the Windows capture/activation
  tool's contribution to the earlier missing popup. No app patch is needed for
  the demonstrated successful path. Phase 01 code checks remain applicable.
- Phase 02 criteria: matching X11 controls and app composition pass; visible
  candidate confirmation delta=0; composition commit delta=0; final Enter
  delta=1; exact persisted Chinese pass. No production/test/schema changes.
  Phase 03 receives the same fixture root and X11/IBus recipe for fresh-shell
  restart, retained conversation and remaining input regressions.

### 2026-09-12 17:08–17:18 +08:00 — Phase 03 restart / host-failure checkpoint

- Closed owned X11 Desktop/controls 7207/7430/7517, and stopped owned daemon
  6968 with ibus exit. In separate fresh WSL invocations, ran:
  `GDK_BACKEND=x11 ibus-daemon --daemonize --emoji-extension=disable`,
  `ibus engine chewing`, `ibus engine` (chewing), then the recorded fixture
  standard main.py launch with GDK_BACKEND=x11. Daemon 8090, Desktop 8318;
  dev compilation 0.72 s. No inherited shell-only recipe was assumed.
- Started fixture backend, selected p1 conversation 28b222e0cc6543aa8d7bbdc423de99a7.
  Native screenshot displayed restored turn 3 with the exact accepted Chinese
  sentence. This is positive Desktop-restart persistence evidence.
- A subsequent native fu/3 attempt did not complete as expected. Tried one slower
  key sequence after clearing preedit; no turn was submitted. Later screenshots
  were residual Windows surfaces: /proc showed Desktop 8318, its WebKit processes,
  IBus panel and Chewing engine had exited. xdotool commands hung in do_sys_poll.
  Owned waiting xdotool PIDs 8751/8757 were stopped (kill -TERM).
- Corrected the initial process-lifetime hypothesis using host evidence:
  `free -m` showed about 27 GB available; dmesg had no OOM/segfault record.
  `/mnt/wslg/stderr.log` ended with Xwayland fatal error:
  `request could not be marshaled: can't send file descriptor`.
  `wsl -d Ubuntu-24.04 --system -- ps -eo pid,ppid,stat,comm` showed
  Xwayland PID 24 as Zs/defunct, parent Weston PID 11; xprop -root timed out.
  Thus later input observations cannot be counted as app/IME regression evidence.
- To capture startup diagnostics, launched one owned session-local daemon with
  Conda app Python subprocess.Popen(['ibus-daemon','--emoji-extension=disable'],
  env including GDK_BACKEND=x11, stdin=DEVNULL, stdout/stderr redirected to
  fixture root / ime-daemon.log, start_new_session=True), PID 8912.
  This did not restore the already failed X server; it is not a new launcher,
  persistent module or required product recipe. No replacement app was launched.
- WSLg-only recovery, within the authorized environment repair, without terminating
  Ubuntu or its other Codex/background jobs:
  `wsl -d Ubuntu-24.04 --system -u root -- kill -TERM 11` did not exit Weston;
  `wsl -d Ubuntu-24.04 --system -u root -- kill -KILL 11` also did not recover it.
  Subsequent /proc/11/status showed D (disk sleep), Xwayland still zombie.
  Do not repeat these signals or claim compositor restart succeeded.
  WSLGd normally supervises/restarts Weston per the official repository;
  this kernel wait prevents normal recovery. Whole-WSL restart timing was asked
  separately because it interrupts other active work and is outside the plan's
  ordinary GUI-session restart scope; no wsl --shutdown was run.
- Cleanup: `timeout 3 ibus exit` stopped owned daemon 8912 and its children;
  no live Desktop/control/IME/xdotool process remained in the inspected user
  namespace (a reparented ibus-portal zombie remained). No user processes were
  deliberately stopped. The temporary fixture/control files remain for resuming
  acceptance; deleting them before acceptance is complete would lose the baseline.
- Post-failure Conda Python/json assertions: exactly three canonical turns remain;
  turn 326aad8f319543d4a0ff58b603955fa7 still has exact matching displayInput /
  semanticInput 請幫我整理這篇論文的研究方法。. No provider or real-store writes.

Automated checks (same application source, Linux Conda app):

```bash
cd /home/minervamuses/research-agent-workspace/app/desktop
npm test
# PASS: 155 tests, 0 failed, 0 skipped; 5041.64 ms test duration.
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_desktop_fixture.py::test_real_service_round_trip_registration_restore_and_final_only_answer -q
# PASS: 1 passed, 1 existing LangChainPendingDeprecationWarning; 0.31 s.
```

Python full suite, npm build and Rust release/test build were not run: this is
an environment/documentation change with unchanged application/tests/Rust source;
Phase 03 explicitly permits focused checks for this path. No stricter gates or
new test framework were introduced.

| Required acceptance | Evidence / remaining work |
|---|---|
| Native target sentence from keyboard | Pass, Phase 02 X11 physical Bopomofo keys |
| Candidate/commit Enter zero turns, next Enter one | Pass, Phase 02 counts 2 -> 2 -> 3 |
| Exact canonical Chinese and rendered user text | Pass, Phase 02 and post-failure assertions |
| Switch away/back | Pass for 中文測試 baseline; repeat for target sentence still pending |
| Desktop restart reads saved target sentence | Pass, native restored turn 3 in fresh launch |
| Fresh-launch new composition/submission | Pending after WSLg host failure |
| English IME test 123, mixed punctuation, Shift+Enter | Native acceptance pending; existing predicate test passes |
| Unicode clipboard | Pass, Phase 01 native copy/clear/paste/send/reload |
| Reproducible final recipe and overall closure | README records successful X11 recipe plus explicit host limitation; not yet closed |

README.md and the original Issue 01 now reflect exactly this scope and limitation.
Phase 03 stays In progress; no success criterion was relaxed or skipped as passed.
After WSL recovery, reuse the same fixture root, verify live process IDs before
input, finish only the pending native rows, update docs/log, and commit that step.
Do not repeat package installation or already-passing suites without a new reason.

Host context references (local logs above are the actual evidence):
- https://github.com/microsoft/wslg — WSLGd supervision of Weston/Xwayland.
- https://github.com/microsoft/wslg/issues/1483 — another reported unkillable
  compositor/kernel wait; not proof this host has the identical root cause.

### 2026-09-12T17:20:20+08:00 — User-approved limited acceptance / final scope

- User explicitly answered: 「跳過需要重啟的部分，如實記錄即可」.
  This supersedes the prior pending restart decision and the requirement to finish
  native checks that depend on restoring the failed WSLg session. No whole-WSL
  or Windows restart was performed. GOALS/PLANS record this user-driven scope
  change; Phase 03 Complete means this limited deliverable, not full original
  matrix success. No Blocked status is used.
- Accepted skip / still unverified: post-restart new composition and submission,
  target-sentence switch-away/back, native English IME test 123, mixed punctuation
  and non-composition Shift+Enter. All now require graphical-service recovery;
  they are not substituted by the 155 passing Node tests or fixture test.
- Confirmed evidence remains: real Bopomofo target sentence, visible candidates,
  candidate/commit Enter delta=0, later Enter delta=1, exact canonical Chinese,
  baseline Unicode paste/switch/reload, and saved target sentence visibly restored
  after Desktop restart before the host failure. App code remained unchanged.
- Available final checks already passed on this source: npm test (155), focused
  Python fixture test (1; existing warning), canonical integrity assertions.
  Documentation-only final edits do not justify rerunning those suites.
- README/original issue explicitly state the limited verification. Installed OS
  IME prerequisites remain; no custom autostart or shell profile edits were made.
  Prior fixture retention instruction is superseded by the user's decision to end
  this run: remove only this task's owned temporary fixture after retaining the
  exact relevant evidence above. No generated fixture data is committed.
- Final cleanup passed: resolved /tmp/research-agent-desktop-phase02-GrASHQ, verified exact name/direct /tmp parent/non-symlink/current owner, then removed it with Linux Conda app Python shutil.rmtree. No user store was touched.
