# Final Check — Build Log

本檔唯一保存這次補救與驗收的 runtime phase status／observed evidence。
計畫文件描述將做什麼；舊 Issue 紀錄僅作歷史來源，不表示本輪已驗證。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Installer Skill switch | Complete | 2026-09-12 | 2026-09-12 | 下方 Phase 01 red/green 與 acceptance 表 | — |
| 02 — Completed Citation replay | Complete | 2026-09-12 | 2026-09-12 | 下方 Phase 02 red/green 與 acceptance 表 | — |
| 03 — Native Desktop acceptance | Complete | 2026-09-12 | 2026-09-13 | 下方Phase03完整native表、audit/AX/screenshot/磁碟核對 | IME按決定skipped；其餘required完成 |
| 04 — Thinking contract/runtime | Not started | 2026-09-12（僅 gate） | — | 下方產品 gate 歷史與 Issue 09 明確延期紀錄 | 已延期，不列本輪 required；無功能完成證據 |
| 05 — Thinking Desktop acceptance | Not started | — | — | 下方 Issue 09 明確延期紀錄 | 已延期，不列本輪 required；無功能完成證據 |
| 06 — Regression and closure | In progress | 2026-09-13 | — | 03已Complete，開始最終read-only gate與一次回歸 | suites/build/review待執行；04/05延期 |

狀態只使用 Not started、In progress、Blocked、Complete。
必要前置與待決事項見 GOALS／各 phase；開始 preflight 後才把實際阻塞寫入本表。
Complete 需要 acceptance→observed evidence；explicit deferral 依 GOALS／PLANS 排除本輪範圍，狀態保留 Not started 並明示延期，不把未做功能標完成。

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

## 2026-09-12 — Phase 03 使用者更正與輸入法唯讀調查（364c48c）

- User-reported：使用者自己執行 python main.py 能正常顯示 App，沒有全黑；进入 App 後無法如平常切換中英文。輸入法為華碩輸入法，平時可用 Shift，且多數情況本就支援中英混合輸入、不必切換。此為使用者提供的真實觀察，不冒充代理操作證據。
- Correction：先前 screenshot 是代理 X11 root 的全黑畫面，不能稱為 App 黑屏或 App 無法啟動。Phase 03 的應用輸入問題現聚焦在華碩 Windows 輸入法與 Linux 視窗之間的輸入鏈；代理 GUI 觀察限制仍獨立存在。歷史 EGL 訊息尚不能建立渲染根因。
- Runtime/worktree read-only gate：root /home/minervamuses/research-agent-workspace；Linux Git /usr/bin/git、Python/Poetry 為 Conda app；branch GUI、HEAD 364c48c；開始時 git status --short 空。重新讀根 AGENTS、PLANS、build-log、main.py、SlashComposer 與 Tauri lib.rs，無子層 AGENTS。
- Exact read-only commands / operations：
  - wsl.exe --version：WSL 2.5.7.0 / WSLg 1.0.66（工具輸出有 UTF-16 顯示問題）；cat /mnt/wslg/versions.txt 獨立確認 WSLg 1.0.66+1。
  - dpkg-query -W ibus ibus-chewing ibus-libpinyin fcitx5 fcitx5-chewing fcitx5-chinese-addons im-config libgtk-3-0t64 libwebkit2gtk-4.1-0：ibus 1.5.29-2、ibus-chewing 2.0.0-1build2、GTK 3.24.41、WebKitGTK 2.52.6；Fcitx5/ibus-libpinyin 不存在，整體 exit 1，後接 && xwininfo 未執行。
  - Conda app Python 掃 /proc，只對 comm=ibus*/fcitx* 或 executable 結尾 research-agent-desktop 的程序輸出指定 display/IME/Conda keys：此時無符合程序；未檢視其他程序資料、user store 或輸入內容。
  - timeout 3s ibus engine → exit 1，No engine is set；gsettings get org.freedesktop.ibus.general preload-engines → @as []；gsettings get org.freedesktop.ibus.general.hotkey triggers → ['<Super>space']（只是未啟動 Linux IBus 的設定，不是使用者華碩快捷鍵）。
  - timeout 3s xwininfo -root -tree → exit 0，仍只有 Weston WM 等三個 root children；此時沒有運作中的 App，不能用來否定使用者先前觀察。
  - 唯讀檢查 ~/.profile、~/.bashrc、/etc/environment 中 GTK_IM_MODULE/QT_IM_MODULE/XMODIFIERS/ibus-daemon/fcitx 行：無匹配。未改設定。
  - grep -RnE 'preventDefault|stopPropagation|keydown|keyup|globalShortcut' app/desktop/src app/desktop/src-tauri/src/lib.rs；grep -Rn shouldSubmitComposerKey app/desktop/src；讀 App.tsx 與 trust.tsx 對應 handlers、conversations.test.ts 既有 IME 測試：composer 沒有攔截 Shift；組字時先 return，menu 只對指定 arrows/Escape/Enter preventDefault；approval 只處理 Escape/Tab。沒有證據支持修改前端鍵盤行為。
- Primary-source research：
  - [ASUS 官方](https://www.asus.com/tw/support/faq/1048621/) 確認華碩智慧輸入法支援注音／英文混合、不需每次 Shift，列出的系統支援是 Windows 10/11。
  - [WSLg IME 支援追蹤 #9](https://github.com/microsoft/wslg/issues/9) 本次讀取仍為 Open，描述沿用 Windows IME 的待補整合與可配置 Linux IBus 的替代；[Windows input-method #955](https://github.com/microsoft/wslg/issues/955) 記錄同類 Windows 輸入法無法在 WSL GUI 組字的回報。
- Inference（尚未 end-to-end 證實）：Windows 華碩輸入法與 WSLg Linux GTK/WebKit 間未接通組字最符合目前證據；本機 Linux IBus/Chewing 已安裝但未啟用，沒有可用的 Linux 組字引擎。不能宣稱已修復華碩相容性，也不把啟用 Linux 注音等同於保留華碩的混合輸入體驗。
- 因新證據修正 preflight 判斷路線，先同步 PLANS 與本 phase 的 Windows/Linux IME 辨識規則；GOALS／required outcomes 不變，Phase 03 保持 Blocked，沒有重做 Issue 01 矩陣。
- 本次僅改三個計畫／證據檔；未改 production/tests，未啟動／重啟 App、IBus、WSL 或服務，未安裝依賴、未執行 suites/build。後續涉及 IME 啟用／設定或 Windows 前端路線，須依既有 scope/環境授權門檻處理。

## 2026-09-12（Asia/Taipei）— 使用者略過輸入法；核對剩餘工作（b8f440a）

- 新授權來源：使用者「跳過輸入法的部分，後面還有什麼問題」。已在 GOALS 保存精確限縮，同步 PLANS / phase-03；輸入法記 skipped / accepted limitation，沒有改為 passed，也沒有豁免其他 native 項目或代答 Issue 09。
- Read-only gate：root /home/minervamuses/research-agent-workspace，Linux Conda app；command -v git python poetry 為 /usr/bin/git 與 Conda app/bin；branch GUI、HEAD b8f440a；git status --short 空。重新讀根 AGENTS、GOALS、PLANS、build-log、phases 03–06。
- 01/02：既有三個 P2 補救及本輪 required focused evidence 維持 Complete；沒有新的 production diff 或已確認功能缺陷。
- 03：使用者回報 App 能正常顯示，仍欠 menu 的鍵鼠/focus/caret/零送出、A→B→A/restart/apply、輔助工具，以及真 ChatSession 的 Citation 原生搜尋→保存→正式回答／後續普通回合／取消失敗等證據；完整安全 Citation UI 啟動入口尚未驗證。輸入法不再是 blocker，但上述其餘缺口仍存在，故保持 Blocked。
- 04：Thinking Effort 三項產品答案（段位／行為映射／保存範圍）及其後精確實作授權仍缺；保持 Blocked。05 依賴 04，保持 Not started。
- 06：待當前 required 前置完成後，才執行一次完整 Python/Node/Rust suites、Tauri source build、bounded review 與逐 Issue 結案；保持 Not started。此次詢問未執行 tests/build/GUI。
- 修改限 GOALS.md、PLANS.md、phases/phase-03-native-desktop-acceptance.md、build-log.md；原始失敗／輸入法調查紀錄保留為歷史。沿用本輪每一步 commit 授權；無 production/tests、環境、依賴或 Git branch/worktree 變更。

- 規劃檔案檢查（Linux Conda app，cwd root）：python /mnt/c/Users/garyc/.codex/skills/long-horizon-plan-author/scripts/validate_harness.py --repo /home/minervamuses/research-agent-workspace --plan-root issue/final_check --project-shape application --risk medium --harness-only --strict --json --proposed-path issue/final_check/GOALS.md --allowed-path issue/final_check/GOALS.md --proposed-path issue/final_check/PLANS.md --allowed-path issue/final_check/PLANS.md --proposed-path issue/final_check/phases/phase-03-native-desktop-acceptance.md --allowed-path issue/final_check/phases/phase-03-native-desktop-acceptance.md --proposed-path issue/final_check/build-log.md --allowed-path issue/final_check/build-log.md → valid=true，0 errors / 0 warnings；git diff --check → passed。此為文件檢查，不是 application acceptance。
- 交接核對：PROMPTS 仍從 build-log/PLANS 計算 eligible phase，沒有硬編碼 current phase；GOALS 唯一保存輸入法限縮，03 移除 IME 門檻，05 引用03且沒有另設IME條件，06 引用GOALS的核准限縮。原生其餘門檻、產品決策及依賴順序不變。

## 2026-09-12（Asia/Taipei）— Issue 09 明確延期與剩餘路線（ca7efa7）

- User decision：使用者在列出全部待決事項後表示「除了extended thinking沒有其他東西了嗎?這個我打算再擱置」。穩定決定保存於 GOALS：延期的是 Issue 09 Thinking Effort 多段位新增功能，既有 Normal／Extended 保留。本輪不再追問段位／映射／保存三項答案或其實作授權；輸入法限縮照舊，其他 native 項目未豁免。
- Read-only runtime/worktree preflight：WSL Ubuntu-24.04，cwd /home/minervamuses/research-agent-workspace；source /home/minervamuses/miniconda3/etc/profile.d/conda.sh && conda activate app；pwd、command -v git python poetry、python --version、git status --short、git branch --show-current、git rev-parse --short HEAD → root 正確，Git /usr/bin/git，Python/Poetry 皆 Conda app/bin，Python 3.13.14，GUI / ca7efa7，初始工作樹乾淨。根 AGENTS 與 find issue -name AGENTS.md 核對：issue 下無其他適用檔。
- 已重讀 GOALS、PLANS、PROMPTS、build-log、phases 04–06，沿用本輪已核對的 phase03 native 缺項與 live code；context/、code_review/ 尚不存在。本次沒有新的 application 因果發現或實際 code review，不建立額外文件。
- Exact edit operation：以 Linux Conda app python - 從 stdin 對七個已凍結 Markdown 做唯一匹配斷言後替換並以 UTF-8/LF 寫回。GOALS 保存決定；PLANS 將本輪 required 路線收斂為 01→02→03→06；PROMPTS 依動態範圍排除延期 phases；04/05 保留未來條件式計畫但不執行；06 移除04/05前置並保留03；本 log 更新狀態表、追加紀錄。未覆寫任何歷史 failed/passed/unavailable evidence，未修改其他 Issue bundle。
- Phase 04：Blocked（僅 gate，無功能實作）→ Not started／明確延期；Phase 05 保留 Not started／明確延期。這只反映範圍決定，沒有 application acceptance passed。
- Phase 01/02 已有 Complete evidence 保留。Phase 03 仍缺 menu 鍵鼠／焦點／caret／零送出與生命週期、可及性、真 Citation 原生流程及完整安全入口，保持 Blocked；沒有新的可操作原生 surface 或豁免證據，不重複啟動 App。Phase 06 的本輪前置改為01/02/03，因03未完成仍 Not started。
- Acceptance→evidence：Issue09 有明確延期處置 → 使用者原話與 GOALS；恢復不誤啟延期功能 → PLANS／PROMPTS 範圍篩選與04/05前置說明；原生門檻未被誤免 → phase06仍要求03、log保留具體缺項。沒有其他已識別的本輪產品決策；原生工具／操作證據是驗收阻塞。
- 沿用使用者「每一步改動皆必須commit」授權，此次為一個計畫修訂步驟。無 production/tests/API/schema/依賴/環境變更；無 tests/full suites/build/GUI/provider 呼叫；不 push、不切 branch/worktree。

- 規劃檔案驗證（Linux Conda app，cwd root）：`python /mnt/c/Users/garyc/.codex/skills/long-horizon-plan-author/scripts/validate_harness.py --repo /home/minervamuses/research-agent-workspace --plan-root issue/final_check --project-shape application --risk medium --harness-only --strict --json --proposed-path issue/final_check/GOALS.md --allowed-path issue/final_check/GOALS.md --proposed-path issue/final_check/PLANS.md --allowed-path issue/final_check/PLANS.md --proposed-path issue/final_check/PROMPTS.md --allowed-path issue/final_check/PROMPTS.md --proposed-path issue/final_check/build-log.md --allowed-path issue/final_check/build-log.md --proposed-path issue/final_check/phases/phase-04-thinking-contract-runtime.md --allowed-path issue/final_check/phases/phase-04-thinking-contract-runtime.md --proposed-path issue/final_check/phases/phase-05-thinking-desktop-acceptance.md --allowed-path issue/final_check/phases/phase-05-thinking-desktop-acceptance.md --proposed-path issue/final_check/phases/phase-06-regression-and-closure.md --allowed-path issue/final_check/phases/phase-06-regression-and-closure.md` → valid=true，0 errors / 0 warnings；`git diff --check` → passed；`git diff --stat` 與逐檔 diff 確認僅上述七個 Markdown。此為文件驗證，非 application acceptance。
- 從 PROMPTS 做恢復核對：由 GOALS 排除延期04/05，再由 PLANS 和 log 選03；外部 blocker 未變即停止，06仍不得開始。產品答案及必要具體 scope 只在未來恢復09後收斂；延期不自動產生新實作權限。

## 2026-09-12 — 原生工具恢復與最後收尾授權（9489e8e）

- 使用者新指示：完成最後工作、commit所有變更、清理issue最後只留extended thinking一份問題卡、全數完成後push。已同步 PLANS／phase06，保留Issue09明確延期與IME限縮；這不豁免其他 required native evidence。
- Read-only gate：WSL Ubuntu-24.04 /home/minervamuses/research-agent-workspace；Linux Git /usr/bin/git、Python3.13.14／Poetry／Node／npm／Cargo皆Conda app/bin；GUI /9489e8e，初始git status --short空。git remote -v為既有git@github.com:Minervamuses/RESEARCH-AGENT-WORKSPACE.git，git branch -vv顯示origin/GUI ahead10；未更改remote／branch。find app issue -name AGENTS.md排除node_modules/target後無子層檔；已讀根AGENTS、GOALS、PLANS、build-log、03/06與live server/fixture/Tauri launcher/Citation tests。
- 新工具 evidence：ALL_TOOLS出現先前工作階段未提供的mcp__node_repl__js；按Computer Use技能匯入@oai/sky，sky.list_windows()可列出WSLg的msrdc Research Agent (Ubuntu-24.04)視窗。sky.get_window_state真截圖可見App；Windows UIA僅外層pane。Linux gdbus call --session --dest org.a11y.Bus --object-path /org/a11y/bus --method org.a11y.Bus.GetAddress → unix:path=/run/user/1000/at-spi/bus；沿Accessible.GetChildren／Properties.GetAll讀到WebKitGTK的Slash commands／Message／option名稱。依新證據恢復03 In progress；不是沿用X11黑圖為阻塞。
- Exact isolated launch：沿前次Conda app python - stdin方式，tempfile.mkdtemp(prefix="research-agent-desktop-phase02-final-",dir="/tmp")得到/tmp/research-agent-desktop-phase02-final-6e7ayl45；env=RESEARCH_AGENT_DESKTOP_FIXTURE=phase02、RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT=該root、CARGO_NET_OFFLINE=true；root cwd subprocess.run(["timeout","540s",sys.executable,"main.py"])。Vite8.2.2 ready227ms；cargo dev增量0.65s；EGL/MESA警告仍有，但真App畫面可見，不能當黑屏根因。
- Actual native operations（sky每次一個action後刷新；觀察到RDP畫面延遲，後段立即讀UIA再600ms後取一次新截圖）：click Start local backend→Backend ready與3個seed對話；開A→A seed歷史；composer type_text("/")→7項選單；type_text("sta")→唯一/status；press_key(Return)→只插入/status空白，AT-SPI CharacterCount=8/CaretOffset=8，歷史仍1turn；第二次Return→一份local command output，turns=2，無model。再"/"→Down選/status→Up選/help→Escape關閉保留草稿；續"ing"→/ingest；滑鼠點選→/ingest空白，直接type fixture-notes.md成功置尾；Shift+Return換行，CharacterCount=25，歷史仍2turn；Tab→Send可見焦點框，Message state由1124211072變1124206976（差4096），CaretOffset=-1；Shift+Tab回composer。
- Read-only AT-SPI操作：gdbus call --address unix:path=/run/user/1000/at-spi/bus --dest <實際GetChildren回傳bus> --object-path <實際path> --method org.a11y.atspi.Accessible.GetChildren／GetRoleName／GetState／GetAttributes，或org.freedesktop.DBus.Properties.GetAll org.a11y.atspi.Accessible／Text。僅沿此自有App subtree，最多120nodes，實際79nodes、queue清空。AX暫存ax-menu.json，真/status結果截圖menu-status-result.png在owned root。GetText 0 -1一次被CLI選項解析拒絕，未当passed；關閉選單後舊optionpath UnknownMethod是已移除節點，後續需重新發現。
- 第一次540s到期LAUNCH_EXIT=124；下一次A→B click遇foreground window did not report a process id，立即停止舊handle並list_windows確認App已關閉。這是自設互動期限，不是App功能失敗；尚未驗的切換／restart／apply／Citation不記passed。後續啟動同owned root，記增量啟動成本與互動時間分開，只停止自有程序。
- 真Citation入口因果核對：Tauri source_conda_launch固定Conda app Python -m agent.desktop.server，PYTHONPATH=app；stock phase02僅FixtureSessionFactory。按03既有DI與temporary launcher範圍，用精確root/opt-in條件的臨時app/sitecustomize.py啟動接縫，替換fixture service的session_factory為真ChatSession及既有offline model/fetcher，記request/model/save/scope，完成即移除；不修改正式API/schema或新增持久module/framework。

## 2026-09-13 — 原生中斷入口核對
- 已實際取得真 ChatSession Citation 搜尋/save/正式答案、普通下一回合、menu/AT-SPI、A/B、extension apply/rematerialization/removal、restart、failure證據，完整對照與artifact待本phase結束附錄。
- App.tsx 無cancel控件，server沒有cancel RPC；首個 [[native:cancel]] 只延遲6秒/模型步，實際完成，僅計入busy/tool evidence，不能記取消passed。依live入口先具體化PLANS/03為自有backend中斷後restart觀察interrupted；沒有新增控件或縮減恢復/不自動重跑要求。既有test_citation_e2e保留task.cancel cleanup直接證據。
- tmp registry移除成功revision2；一次變更delay的唯一匹配assert失敗，因原碼為多行，未改hook，不冒充已延長。普通restart後真Session僅citation，models/fetch/scopes皆0，bundle SHA256與mtime完全相同。後續保留6秒delay，在首個model等待時停止精確owned backend PID。

## 2026-09-13 — Phase03 原生驗收完成（d3647c5；production與前兩phase相同）

### Runtime / exact temporary launch
- Windows @oai/sky 操作真正 WSLg Research Agent視窗；Linux Conda app執行App/backend/Git。window5112398，msrdc；Linux AT-SPI只讀。第二個launcher啟動UTC 2026-09-12 15:48:42，完成互動16:06:37（17m55s人工互動）；Vite ready243ms，Cargo增量0.79s。沒有長編譯/模型/資料命令，沒有付費或網路provider。
- 既有main.py source launcher，Linux Conda app python -：env={RESEARCH_AGENT_DESKTOP_FIXTURE:phase02, RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT:/tmp/research-agent-desktop-phase02-final-6e7ayl45, RESEARCH_AGENT_DESKTOP_NATIVE_AUDIT:final-check-9489e8e, CARGO_NET_OFFLINE:true}；subprocess.Popen([sys.executable,"main.py"],cwd=repo,env=env,stdout=owned native-dev.log,stderr=STDOUT,start_new_session=True)，PGID10638。自有root/skills/citation複製既有app/skills/citation，不含cache。
- Exact bootstrap保存為[evidence/phase-03-temporary-launcher.txt](evidence/phase-03-temporary-launcher.txt)。app/sitecustomize.py只是一個指到自有root的臨時symlink；僅上述exactroot/opt-in且agent.desktop.server -m進程生效。真ChatSession.create強制load_mcp=False（原UI傳true另記），AgentConfig由既有fixture隔離，real CitationService使用_SearchSaveModel、RoutingFetcher、_fixture_services；save/request僅旁路記錄，不偽造正式答覆或持久JSON。零userstore/外部provider。
- 原生操作全部使用sky.click/press_key/type_text/scroll，每次一個action後立即get_window_state(include_screenshot:false,include_text:true)，再600ms取得新真截圖。下表按實際操作次序；所有 session.turn 請求保存於[evidence/phase-03-native-audit.jsonl](evidence/phase-03-native-audit.jsonl)。

### Acceptance → observed evidence
| Acceptance | Exact actions / actual result |
|---|---|
| /status補命令不送出 | A input /sta→Return，插入/status空白，before/after session.turn=0，models/fetch/scopes=0；再Return恰一個session.turn，完成local output、turnNumber3。前次AT-SPI CharacterCount/CaretOffset8/8，mouse /ingest+fixture-notes.md置尾已有上節實測。 |
| 一般鍵鼠 / focus / closure | 既有上節 /→Down→Up→Escape、滑鼠/ingest、ShiftReturn/Tab保留；本次 /→Up 環繞到最後/citation，active item自動捲入；Tab關menu且Send焦點框，ShiftTab回composer；Ctrl+A/BackSpace清空；再/→ShiftReturn成兩行且menu消失，turns仍5。首次BackSpace在caret0沒清掉/，觀察後用全選清空，非功能修補。 |
| 可及性 | Linux gdbus沿實際App GetChildren，Properties.GetAll Accessible/Text、GetAttributes/GetState。Slash commands computed-role=listbox，Message textbox/haspopup=listbox；選/help時state1132468480、未選/status1124073728；Up後/citation state1132468480，/help1090519296且不在可見區；截圖顯示最後option可見。AX兩次各107nodes且queue清空，檔案ax-current/ax-citation-selected；關閉由實際UI確認。IME按使用者決定skipped，未聲稱screen reader朗讀。 |
| 真Citation與正式輸出 | /cit→Return→Search and save Paper A，仍僅前一個/status請求；Return後真search/save兩個citation_workflow摘要ok，model3/fetch4/scope1/save1，final_only/chunkCount0。一份正式答案「已保存並引用來源 [1]。」及Ada Lovelace/2021/Paper A/DOI10.1234/paper-a；canonical第4turn與response逐字相同，mode normal。screenshots citation-complete/citation-live-tools/citation-busy；UI工作時控件disabled、Normal說明保留。 |
| 後續普通問題 | ordinary question→Return，ordinary answer；增量model1，fetch/save/scope零，模型tools沒有citation_workflow，selector Normal。citation-ordinary-next截圖。 |
| A→B→A及catalog隔離 | A的多行/草稿→click B（空draft，只有B seed）；B /nat可見native-writer→click A（空draft，不混B草稿或selection）；A讀回Citation與ordinary歷史，model4/fetch4/scope1/save1保持。citation-restored-tools截圖可見兩筆真工具歷史。 |
| apply/rematerialization | 使用既有test_extension_skill_startup._write_skill/_apply_skill及AgentConfig，把native-writer套用到自有extensions/desired/state、revision1；running A的/仍8commands，重新載入B/A才loadedSkills含native-writer、revision1。A輸入/native-writer explain→Return，真one-shot回ordinary answer，僅一次model、無Citationscope。 |
| 移除/restart/拒絕 | 用既有write_registry(ExtensionRegistry(revision=2,source_root=owned/desired,extensions={}))移除自有applied entry；click Restart→重新選A，generation2，loadedSkills僅citation、revision2，model/fetch/scope全零；failed草稿可讀、未重試。手打/native-writer explain→Return，Unknown slash command；/thinking normal→Return，not available in desktop composer。兩者未增canonical turn或model，截圖removed-skill-rejected/cli-command-rejected。 |
| failure | /citation [[native:fail]]→Return，模型刻意RuntimeError，真canonical state failed、UI Prompt saved/Failed且可編輯；重啟仍同failed，不自行重跑。第一次model記錄9次但base model.invocations8，差額是此刻意失敗，不能把8當實際呼叫數。 |
| 中斷/recovery | 初次/citation [[native:cancel]]僅每步delay6s，最後完成，提供busy及真tool活動而非cancel證據；第二次/citation [[native:cancel]] interrupted check→Return，核對PID14395的/proc environ精確root/opt-in、cmdline含agent.desktop.server，audit最後為此PID第一個model，再os.kill(pid,SIGTERM)。UI立即Backend crashed，不自動重送。click Restart backend→generation3→選A：Prompt saved/Interrupted、Retry saved draft、canonical第9turn interrupted，新process model/fetch/scope皆0。修改成ordinary recovery question→Return完成ordinary answer；截圖citation-interrupted-restored/citation-recovered-next。task.cancel cleanup仍由既有直接tests在06執行。 |
| 磁碟/隔離 | Citation bundle僅一份Paper_A--df54325721de（citation.json1427bytes、reference.bib114bytes），兩次成功save第二次重用；初次保存後至切換/兩次restart/失敗/中斷所有bundle SHA256及mtime_ns相同，見bundle-before-lifecycle指紋。沒有commit store或bundle。 |

### Exact evidence checks / cleanup / handoff
- Conda app python - 執行[evidence/phase-03-native-assertions.txt](evidence/phase-03-native-assertions.txt)：實際canonical/final text、normal metadata、search/save toolActivities、catalog0→1→2、3rdprocess restore零effects、bundle SHA256+mtime、failed/interrupted/completed尾端狀態、10筆UI session.turn（含2次拒絕）皆通過，1.45s。初次check最後一項誤用params.message KeyError；讀actual DTO確認text後修觀察script重跑，非application失敗或重做native旅程。
- AT-SPI exact只讀遍歷script另存phase-03-accessibility-reader.txt；native中斷PID安全檢查script存phase-03-owned-interruption.txt。
- 支援focused checks為conditional：沒有正式UI/fixture code變更，既有Python/Node直接證據仍適用；本phase不重跑full suites/build，交由06統一。
- 點UI Shut down觀察Backend stopped/gracefully；核對/proc/10638精確root及getpgid==10638後killpg(SIGTERM)，只停止自有launcher/Vite/Tauri。確認app/sitecustomize.py為指到ownedroot/sitecustomize.py的symlink後unlink，僅移除自有app/__pycache__/sitecustomize.*.pyc。截圖及去敏audit/AX/recipe已保存；root暫留至最終證據驗證，不再有會啟動hook的repo入口。
- Phase03 Complete：Issue02與08分別取得直接native evidence；IME明確skipped；無production/tests修改、無新增依賴/API/schema/持久module、無新的功能缺陷。既有先前unavailable/timeout保留歷史。下一eligible為06，04/05明確延期。

## 2026-09-13 — Phase06 once-only suites / Rust red and route correction

- Baseline ec9175f；Linux Conda app runtime／Git 重新核對，working tree clean，GUI ahead13 origin/GUI。自有 native App 已停止、app/sitecustomize.py 與其編譯快取已移除，以下 suite 沒有 fixture hook。三套 independent suites 各只執行一次。
- cwd app/: timeout 540s poetry run pytest → PASS 1138 passed, 2 warnings，pytest41.16s／wrapper44.359s，exit0。警告為 LangChain allowed_objects 未來預設與既有 ZIP duplicate member 測試。
- cwd app/desktop/: timeout 300s npm test → PASS165，0fail，Node5997.740858ms／wrapper6.285s，exit0。
- cwd app/desktop/: timeout 540s cargo test --offline --manifest-path src-tauri/Cargo.toml → FAIL35passed／1failed，test0.25s／wrapper1.297s，exit101。失敗 backend::tests::a_new_generation_cannot_reuse_the_prior_shutdown_report，backend.rs:2023，observed Degraded / expected Crashed。未重跑完整 suite。原始輸出見 evidence/phase-06-rust-red.txt。
- 直接查因：kill_child 只送 kill；stdout reader 的 EOF 可早於 try_wait 可見退出，stdout_closed 因而用 BACKEND_OUTPUT_CLOSED／Degraded，child_exited 保留該終態；exit monitor 先觀察則為 Crashed。原測試欲驗證新 generation 不重用舊 Graceful report，kill-only setup 卻依賴兩條 thread 排序。
- 先修 PLANS／Phase06 的路線：只讓該既有測試在 child mutex 下 kill＋wait 完成，再交由兩條既有監看 thread 處理；保留原 Crashed 與 NotRunning 斷言，不修改 production、不新增框架／依賴。此完整 run 是最小實際 red；下一步一次 focused green，若失敗不跳過。

## 2026-09-13 — Phase06 Rust focused green

- f8e12ec + backend.rs 的既有 cfg(test) setup 局部修改：同一 child mutex 下 kill/wait，沒有放寬 assertion，沒有 production lifecycle 或 API 變更。
- Exact command（cwd app/desktop/，Linux Conda app）：timeout 120s cargo test --offline --manifest-path src-tauri/Cargo.toml backend::tests::a_new_generation_cannot_reuse_the_prior_shutdown_report -- --exact → PASS1，35filtered，test0.05s／compile5.09s／wrapper5.167s，exit0。binary test target 0 tests。
- 一次實作嘗試 green：真 child process 退出，snapshot Crashed，shutdown NotRunning，確認沒有重用舊 generation Graceful report。35個其他案例已在唯一完整 run 通過；不將原35／1 red改寫為完整36 passed。原始 focused output 見 evidence/phase-06-rust-target-green.txt。
