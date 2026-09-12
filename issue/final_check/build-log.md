# Final Check — Build Log

本檔唯一保存這次補救與驗收的 runtime phase status／observed evidence。
計畫文件描述將做什麼；舊 Issue 紀錄僅作歷史來源，不表示本輪已驗證。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Installer Skill switch | Complete | 2026-09-12 | 2026-09-12 | 下方 Phase 01 red/green 與 acceptance 表 | — |
| 02 — Completed Citation replay | Complete | 2026-09-12 | 2026-09-12 | 下方 Phase 02 red/green 與 acceptance 表 | — |
| 03 — Native Desktop acceptance | Blocked | 2026-09-12 | — | 下方 native launch / screenshot evidence | App 原生 surface 不可觀察／控制；IBus / Orca unavailable；真 Citation UI 入口未驗證 |
| 04 — Thinking contract/runtime | Blocked | 2026-09-12（僅 gate） | — | 下方產品 gate 核對 | 三項產品答案及精確實作授權未定 |
| 05 — Thinking Desktop acceptance | Not started | — | — | — | 前置 04 未 Complete |
| 06 — Regression and closure | Not started | — | — | — | 前置 03–05 未 Complete；未跑完整 suites/build |

狀態只使用 Not started、In progress、Blocked、Complete。
必要前置與待決事項見 GOALS／各 phase；開始 preflight 後才把實際阻塞寫入本表。
Complete 需要 acceptance→observed evidence；explicit deferral 依 PLANS 修訂範圍，不能把未做功能標完成。

## 證據規則

- 每次記日期／時區、phase、code revision 與未提交 diff 範圍、exact command 或操作、cwd/runtime、結果與限制。
- 明示本輪 observed、reported/historical、planned、unavailable 或 skipped；缺驗證不視為 passed。
- failing red 記實際 assertion 與因果；green 記可見輸出、JSON／bytes／計數，不只測試總數。
- 原生記真實工具／視窗、操作前後畫面與對應 request／backend／saved output；SSR／FixtureSession 不能冒充真 Citation。
- 大輸出只連 artifact，先保留需長期使用的去敏證據才清 tmp；不記 credentials、真實使用者資料或完整 diff。

## 活動紀錄

尚無實作活動。本次只建立計畫；application tests、build、GUI 或各 phase planned checks 未作為本計畫執行證據運行。

執行時追加：時間、phase、狀態變化、scope link、直接 changed files、commands/操作與結果、
acceptance 對應、必要 review、限制、blocker、下一個 eligible 行動和 evidence path。
重大更正以追加 correction 保留原始失敗與完成歷史。

## 2026-09-12（Asia/Taipei）— 啟動與唯讀 preflight

- Observed baseline：branch GUI、HEAD 83ffa54；tracked/index diff 空；只有使用者既有的 issue/final_check/ 十個未追蹤計畫檔。此 commit 一併保留原計畫 baseline，並非今日 application 驗收證據。根 AGENTS 為唯一適用檔，未發現 issue/app 子層 AGENTS；context/、code_review/ 尚不存在。
- 使用者本輪明確要求執行並「每一步改動皆必須commit」：授權本計畫直接變更及各邏輯步驟 commit；不授權 push、切 branch/worktree、依賴、昂貴命令、付費 provider 或未定 Issue 09 API/schema。GOALS 三項產品答案仍未定，不代答。
- Runtime gate passed：Windows PowerShell 只作 wsl.exe -d Ubuntu-24.04 啟動器；命令及編輯經 Linux 執行。Linux Git /usr/bin/git 2.43.0；Conda /home/minervamuses/miniconda3/bin/conda 的 app：Python 3.13.14、Poetry 2.4.1 均在 /home/minervamuses/miniconda3/envs/app/bin。app/poetry.toml create=false / in-project=false；.gitattributes 要求 LF。
- Read-only commands（Linux cwd repository root，前面均由 wsl.exe -d Ubuntu-24.04 -- bash -lc 啟動）：pwd; uname -s; command -v git; command -v conda; command -v python；git status --short；git branch --show-current；git diff --stat；git diff --cached --stat；git status --porcelain=v1 --untracked-files=all；git log -5 --oneline；git diff --numstat；git diff --cached --numstat；git config user.name；git config user.email。
- Runtime command：/home/minervamuses/miniconda3/bin/conda run -n app bash -c 'command -v python; command -v poetry; command -v git; python --version; poetry --version; git --version'。Login bash 未自動啟用 Conda，後續明確 source /home/minervamuses/miniconda3/etc/profile.d/conda.sh && conda activate app；不用系統或 Windows Python。Linux rg unavailable，以 find/grep/sed/cat 唯讀替代，未安裝工具。
- 已讀根 AGENTS、GOALS、PLANS、build-log、phase-01；核對 session.py 的 begin/duplicate/load/cleanup/finalization/routing、manager.py clear 與現有 skill/citation/thinking/persistence、CLI/Desktop 公開結果接縫。
- Phase 01 scope：session.py 局部修正與既有 tests 最小 red；公開 cleanup_detail/backup_path、新 graph/model 零執行、source/previous bytes、Fusion routing 與磁碟 metadata 一致。required focused checks 未過不得開始 Phase 02；完整 suites/build 保留 Phase 06。

## 2026-09-12 — Phase 01 red（baseline 40b843c + test_skill_adherence.py）

- Exact command（Linux cwd app，source /home/minervamuses/miniconda3/etc/profile.d/conda.sh && conda activate app）：
  1. timeout 120s poetry run pytest tests/test_skill_adherence.py -k installer_skill_switch -q → 3 failed / 2 passed / 20 deselected，0.59s。
  2. timeout 120s poetry run pytest tests/test_skill_adherence.py -k installer_skill_switch -q --tb=short → 3 failed / 2 passed / 20 deselected，0.52s。
- 第一次 generic conflict 進入 Extended 後遇到 OPENROUTER_API_KEY is not set（model 建構拒絕，沒有 live provider 呼叫）；修正測試邊界，把 Fusion graph/role model 全部接既有 _Factory/_default_models，再取得第二次純離線 red。沒有 production 實作嘗試。
- Confirmed red：Citation Desktop 回答 New skill ran despite cleanup conflict；一般 Skill 回答 fused，兩者未公開 source cleanup conflict。一般 Skill 澄清後真 Fusion p1/p2/p3、aggregator、reviewer 已跑且回答 fused，但 repository thinking_mode=normal，預期 extended。
- Protection controls passed：Citation normal routing 與回復 extended；完成 installer duplicate（含 retry=true）在 loader 前返回，之後 runtime load failure 保留 pending transaction、runtime、mode、全 source/backup bytes。
- 新測試沿用真 ZIP/tool loop、tmp_path 與既有 Desktop service、Fusion seams；未新增 framework。Red commit 刻意保存上述三項失敗，下一步只修 session.py 因果路徑。

## 2026-09-12 — Phase 01 green / Complete（62ff20c + session.py）

- Production 僅 session.py：load 之後檢查 cleanup conflict，沿用 host 結果文字與 finalize_and_record 回傳；未啟用新 Skill。begin 前純計算 effective_mode，一般 Skill 使用 installer 原模式；runtime load failure 前不做 cleanup 或 mode mutation；duplicate 仍在 load/cleanup/execution 前。
- Exact commands（Linux Conda app，cwd app，前置同上）：
  - timeout 120s poetry run pytest tests/test_skill_adherence.py -k installer_skill_switch -q --tb=short → 5 passed / 20 deselected，0.52s。
  - timeout 300s poetry run pytest tests/test_skill_adherence.py tests/test_citation_skill_activation.py -q → 40 passed，1.32s。
  - timeout 300s poetry run pytest tests/test_session_persistence.py tests/test_thinking_session.py -q → 29 passed，0.68s。
  - root：git diff -- app/agent/session.py；git diff --check → passed。
- 一次 focused production 嘗試即 green；只有既有 LangChainPendingDeprecationWarning，未變依賴。未執行完整 suites/build、真模型或原生 UI。

| Acceptance | Observed evidence |
|---|---|
| Citation / 一般 Skill conflict 對外阻擋 | Desktop dispatch 兩例 text 包含 Installation stopped: source cleanup conflict.、cleanup_detail: staged source changed; preserving user changes and backup、正確 backup_path；completed/final_only/chunkCount=0；canonical answer 等於回傳文字。 |
| 新工作零呼叫 | 兩例 _run_turn runs=[]、normal graph.states=[]、Fusion factory.calls=[]、所有 role model calls=[]，installer model.calls 未增加。 |
| source / 全備份完整 | source 與 backup 遞迴所有檔案 path→bytes map 完全相等，包含 preview 後的 User modification after preview；沒有重新安裝／刪除。 |
| mode 與 routing | 真兩候選 ZIP 澄清讓 session 暫 normal；slash academic-paper-writing 後 p1/p2/p3、aggregator/reviewer 執行，answer=fused；repository 與磁碟 JSON thinkingMode=extended；session 恢復 extended。Citation 對照 graph 執行時 pending mode=normal，磁碟/repository=normal，結束 extended。 |
| 原狀態與既有流程 | completed installer duplicate retry=true 零 loader；runtime failure 保留 pending/preview_id/runtime/mode/source/backup；40+29 focused checks 覆蓋下一 installer request、cancel、Citation teardown、durability 與 Fusion 行為。 |

下一 eligible phase：02，依檔案路線執行；09 的三項產品決策依然未定。

## 2026-09-12 — Phase 02 preflight / red（d52101a + test_desktop_service.py）

- Phase 01 Complete 後讀 phase-02、live Desktop service / Session / repository identity/fingerprint、Citation e2e、applied-integrity 與 Desktop tests。未有相關 context/code_review；runtime / branch 不變，既有 diff 僅本 phase 測試。
- Scope：service.py 的 Citation eligibility 時序；canonical 回讀必須繼續走 Session turn lock + _begin_persisted_turn / append_pending，不能直接回傳 load_optional 的答案。無 API/schema 變更。
- Exact command（Linux Conda app，cwd app）：timeout 120s poetry run pytest tests/test_desktop_service.py -k composer_citation -q --tb=short → 2 failed / 68 deselected，0.65s。
- 兩例先經真 Desktop dispatch / ChatSession / graph / offline RoutingFetcher 完成搜尋→save→正式回答「已保存並引用來源 [1]。」；model=3、scope=1、save=1。之後分別讓 loader ValueError、真 tmp applied Citation SKILL.md 完整性失效。相同 params 重送在 service.py eligibility 拋 That slash command is not available in the desktop composer.（PROTOCOL_INVALID），未到 canonical duplicate。
- 已保存 assertions：原 params / durable text / JSON 與 bundle bytes+mtime / model-provider-scope-save 計數；green 必須驗證 retry=false/true 不增加任何呼叫，以及 identity/unfinished/new-work 對照。只操作自有 tmp，無 provider 網路呼叫。

## 2026-09-12 — Phase 02 green / Complete（c1bfcb1 + service.py / test_desktop_service.py）

- Production 僅 desktop/service.py：bounded repository read 只辨識 completed Citation 候選以延後 runtime eligibility；沒有在 service 直接回答案。原 slash parser/handler、Session turn_outcome lock、project check、append_pending 的完整 logical-input 與 fingerprint 核對仍是必經路徑。新回合與 unfinished retry 保留原 eligibility；catalog 不變；無 session canonical/API/schema 修改。
- Exact commands（Linux Conda app，cwd app，前置同上；依序 observed）：
  1. timeout 120s poetry run pytest tests/test_desktop_service.py -k composer_citation -q --tb=short → 2 passed / 68 deselected，0.43s（production 一次 focused 嘗試 green）。
  2. timeout 120s poetry run pytest tests/test_desktop_service.py -k citation -q --tb=short → 11 passed / 2 failed / 67 deselected，0.70s：新增 unfinished fixture 使用未知 failure code=fixture，尚未 dispatch；屬測試 setup 錯誤，不是產品 red。
  3. 同命令 → 12 passed / 1 failed / 67 deselected，0.66s：改 execution_failed 後 failed 對照通過，interrupted fixture 必須使用 interrupted/cancelled，仍為 setup 錯誤。
  4. timeout 300s poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py -q → 229 passed / 1 failed，2.60s，同一 interrupted fixture setup；未進 dependent phase。
  5. timeout 300s poetry run pytest tests/test_citation_e2e.py -k 'terminal_cleanup or one_shot' -q → 5 passed / 11 deselected，0.50s。
  6. 修正 fixture 成 interrupted / execution_failed 對應後：timeout 120s poetry run pytest tests/test_desktop_service.py -k unfinished_citation -q --tb=short → 2 passed / 78 deselected，0.29s。
  7. 上述第 4 個 required focused command 因 fixture 修正重跑 → 230 passed，2.46s。未改 production 因果解法，沒有第三次 implementation 嘗試。
  8. root：git diff -- app/agent/desktop/service.py；git diff --stat；git diff --check → passed。
- 限制：單一既有 LangChain deprecation warning；無 Node/Rust/全 Python suite/build，皆留 Phase 06。上述 230 為指定三個模組，不是完整 suite；Phase 01 checks 未機械重跑。

| Acceptance | Observed evidence |
|---|---|
| 失效 runtime 的 completed Desktop replay | loader ValueError 與真 tmp applied SKILL.md hash 失效兩例，原 /CiTaTiOn off topic: 搜尋並保存 Paper A 的相同 params 回原 durable answer 與 turnNumber；retry=false/true 皆 completed/final_only/chunkCount=0，protocol success_result 驗證通過。 |
| 零重執行／重寫 | 初次 model=3/scope=1/save=1；重送 model/fetcher/scope/save 計數均不增加，loader calls=[]；JSON 與所有既有 Citation bundle 檔案 bytes/mtime_ns 相等。 |
| 完整 identity 與 snapshot | display、semantic、kind、context eligibility、mode、project、session 八類（含 fingerprint concurrent byte change）拒絕；graph 零呼叫、沒有 Citation scope，canonical bytes 除測試主動注入的 fingerprint 換行外不變。 |
| 新工作與未完成 retry | 兩種失效 runtime 下新 turnId 返回 PROTOCOL_INVALID；failed/interrupted 各 retry=false/true 都拒絕，原 canonical bytes 不變、graph/scope 零執行。 |
| 相容回歸 | 230 個 Desktop service/conversation/protocol focused checks 與 5 個 Citation terminal/one-shot checks 通過，覆蓋 catalog、一般對話、restore/retry、final-only 與 cleanup。 |

下一 eligible phase：03 的短 native preflight。若原生外部阻塞，04 僅在三項產品決策及具體授權齊全時可執行；06 仍不得繞過 03–05。

## 2026-09-12 — Phase 03 native preflight（8743c52；worktree clean）

- 已讀本 phase、Issue 02 menu/integration 與 Issue 08 Desktop phase / 歷史 logs，核對 main.py、server._build_runtime_service、fixture_session.py、test_desktop_fixture.py、SlashComposer / conversations tests。
- Exact read-only commands（Linux Conda app，cwd root）：
  - command -v python poetry git node npm cargo xdotool xdpyinfo wayland-info fcitx5-remote ibus orca gdbus busctl → Python/Poetry/Node/npm/Cargo 全在 Conda app，Git /usr/bin/git；xdotool/xdpyinfo/ibus/gdbus/busctl 可用；wayland-info/fcitx5-remote/orca 不存在。
  - printenv DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS GTK_IM_MODULE QT_IM_MODULE XMODIFIERS → :0、wayland-0、/run/user/1000/、unix:path=/run/user/1000/bus；最後三項未設定（printenv exit 1）。
  - timeout 3s xdotool getdisplaygeometry → passed，2560 1600。此為今日新 evidence，歷史 timeout 仍保留，不沿用為今日阻塞。
  - timeout 3s ibus engine → unavailable，exit 1，IBUS_IS_BUS assertion / No engine is set.；未重啟或安裝。
  - command -v ffmpeg gst-launch-1.0 gnome-screenshot scrot → /usr/bin/ffmpeg、/usr/bin/scrot；timeout 3s xwininfo -root -tree → passed，只有 Weston WM 等三個 root children，尚未啟動 App。
  - ls -l app/desktop/node_modules/.bin/tauri app/desktop/node_modules/.bin/vite app/desktop/src-tauri/target/debug/research-agent-desktop → 現有 Linux npm dependencies 與 Sep 7 debug binary 存在。
- 原生觀察可走既有 xdotool + scrot；暫不宣稱互動通過。Linux IME / Orca 必要 evidence 仍 unavailable。
- Issue 02 安全入口已確認：phase02 fixture opt-in + require_fixture_root，全部 store/citations/extensions/knowledge 指向 caller-owned /tmp；FixtureSessionFactory / offline extension model，test_fixture_never_uses_chat_session_factory_or_exposes_credentials 明示禁止真 ChatSession.create。
- 使用既有 main.py / npm tauri dev、CARGO_NET_OFFLINE=true、timeout 540s 上限嘗試原生 fixture；不執行完整 suite/source build、不安裝依賴。現有 Rust cache + dev Vite，預期啟動低於十分鐘；觀察 startup 後再操作。
- 真 Citation 第二門檻仍未驗證：phase02 fixture 不是真 Citation；必須另外確認自有 tmp launcher 的既有 dependency injection，不能用一般 python main.py 接真 user store。

## 2026-09-12 — Phase 03 原生嘗試 / Blocked（1929acf；未改 application/tests）

### Exact launch / observations

下列 Python launcher 經 /home/minervamuses/miniconda3/bin/conda run --no-capture-output -n app python - 執行；stdin 由 PowerShell literal here-string 傳入 wsl.exe -d Ubuntu-24.04（Windows 僅 launcher）：

~~~python
import os, subprocess, sys, tempfile
from pathlib import Path
root = Path(tempfile.mkdtemp(prefix="research-agent-desktop-phase02-slash-menu-", dir="/tmp"))
print("FIXTURE_ROOT=" + str(root), flush=True)
os.environ.update(RESEARCH_AGENT_DESKTOP_FIXTURE="phase02", RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT=str(root), CARGO_NET_OFFLINE="true")
os.chdir("/home/minervamuses/research-agent-workspace")
result = subprocess.run(["timeout", "540s", sys.executable, "main.py"])
print("LAUNCH_EXIT=" + str(result.returncode), flush=True)
~~~

- Owned tmp root：/tmp/research-agent-desktop-phase02-slash-menu-a4d2wp3s。Observed 啟動：Vite v8.2.2 ready 277ms；cargo dev profile finished 3.65s，target/debug/research-agent-desktop 已執行。這是 dev launcher 的增量編譯，不是 Phase 06 的完整 suites / Tauri source build。
- stderr：libEGL failed to retrieve device information / MESA ZINK failed to choose pdev / egl failed to create dri2 screen。這是 observed 訊息；是否為 UI 不可見的根因尚未確認，不以猜測修改 rendering 或系統。
- Native queries（root cwd）：
  - timeout 3s xwininfo -root -tree → exit 0，仍僅 Weston WM 與兩個 unnamed X11 root children，沒有 App window。
  - timeout 3s xdotool search --name Research → exit 1，沒有可操作的匹配 window id；串接的 scrot 因 && 未執行，未誤記為有截圖。
  - 另執行 timeout 3s scrot /tmp/research-agent-desktop-phase02-slash-menu-a4d2wp3s/native-start.png → exit 0；view_image 實際查看 2560×1600 全黑 X11 root 畫面，沒有 menu 或 App 內容。
- [原生 root 截圖](evidence/phase-03-native-root.png)，SHA256 f16b1f3806b329eaa287434ed37cafd23930008a34ab771706a59d15073bf939。這只證明本操作 surface 未呈現可觀察內容，不能推論其他 display surface 也沒有視窗，更不是 UI acceptance passed。
- Linux /proc 以精確 RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT 篩選（未輸出其他 env），確認自行啟動的 timeout / python main.py / npm / Vite / Tauri / WebKit processes 都在 pgid=6464。沒有 backend readiness / fixture store materialization 證據；停止前 tmp 只有 native-start.png。
- 無可觀察／控制 App surface 後依 phase stop gate 停止，不再換 rendering 參數或反覆啟動。未執行 xdotool key/type/click，未聲稱 keyboard/mouse/focus/caret/request checks 通過。

### Owned cleanup

- 透過 Conda app Python 檢查 /proc/6464/environ 包含上述精確 tmp root、cmdline 前兩欄為 timeout / 540s、os.getpgid(6464)==6464 後，執行 os.killpg(6464, signal.SIGTERM)，只停止本次自行啟動的 process group；launcher 回報 LAUNCH_EXIT=-15（主動停止，非 passed）。
- 再檢查 /proc 精確 fixture env 沒有任何存活程序；將 screenshot 複製至上方 evidence path 後，驗證 fixture.resolve()==fixture、parent=/tmp、完整名稱完全相同且非 symlink，才 shutil.rmtree(fixture)。已確認 tmp 不存在。沒有停止 compositor、WSL、IBus 或使用者服務。

| Acceptance | 本輪狀態與具體缺口 |
|---|---|
| Issue 02 menu 原生操作 | Unavailable：尚無 /、/sta、arrows、Enter/zero request、mouse、Escape/blur、Shift+Enter/Tab、focus/caret、A→B→A/restart/apply 的直接原生證據。Dev compile/readiness 不能取代它。 |
| Issue 02 IME / accessibility | Unavailable：ibus engine exit 1 / No engine is set；Orca 未安裝；未做系統配置或重啟。 |
| Issue 08 真 Citation UI | Unavailable：沒有可操作的 native surface，且 phase02 FixtureSessionFactory 不是真 ChatSession/Citation。第二門檻的完整 isolated Citation UI launcher 未驗證，沒有為繞過 blocker 建新 fixture module。Phase 02 的真服務離線 evidence 保留為不同層。 |
| 隔離與成本 | Passed 僅指啟動配置：caller-owned tmp、明確 fixture opt-in、offline Cargo、無 dependency install / paid provider / user store 操作；沒有把這些當成原生驗收。 |

### Phase 04 gate / 最終停止條件

- Phase 01/02 Complete，故檢查與 Phase 03 不互為前置的 Phase 04。已讀本 phase、原 issue_09 phase-01；唯讀核對 live session.set_thinking_mode、slash /thinking、Desktop controls 與 thinking/slash tests。現有 normal/extended 不能代替新段位的使用者決定。
- GOALS 的唯一決策表仍無答案：①段位數量/名稱/穩定值/順序/預設及與 Normal/Extended 關係；②workflow/model/provider effort 映射、角色、不支援與 CLI 相容；③new/A→B→A/restart 的保存範圍、metadata。精確必要 production paths / API / schema 授權須於產品答案後收斂；本啟動與 commit 授權不代答上述事項。
- Phase 04 為 Blocked（僅授權/產品 gate，沒有實作或新增 tests）；未自行延期 Issue 09。Phase 05/06 前置未完成，保持 Not started。
- 無其他前置完整且授權齊全的 phase。路線／穩定目標未變，無須改寫 PLANS 或未開始 phase；沒有新增猜測性 context/review，既有 Issue logs 保持歷史。Issue 01 已准略過的矩陣完全未重做。
- 恢復所需：能操作並觀察 App 的 Linux native surface、Issue 02 所需 IME/輔助工具證據，以及真 ChatSession + offline provider + tmp store 的 Citation UI 安全入口；或使用者明確接受具體限縮。獨立 Phase 04 需上述三項產品答案及必要精確 scope 授權。
- 本輪 production write set：app/agent/session.py、app/agent/desktop/service.py；tests：test_skill_adherence.py、test_desktop_service.py；其餘為本 plan baseline、build-log 及真實 screenshot evidence。無 AGENTS、依賴、API/schema、branch/worktree 變更，無 push。
