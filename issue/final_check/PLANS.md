# Final Check — 執行計畫

## 計畫概況與資訊所有權

- Plan root：issue/final_check；Application / medium。風險集中在 cleanup／canonical identity／mode 時序與原生證據缺口，非 production service 強化。
- Execution mode：Autonomous within authorization envelope；使用者已明確啟動執行，來源見 build-log。當前範圍依 GOALS，延期項目不自動恢復。
- 採 repo 既有 phases/ 格式；根 .gitignore 忽略 build/，不修改 ignore 規則。

| 資訊 | 唯一 owner |
|---|---|
| 穩定目的、成功條件、限制、使用者產品答案 | [GOALS.md](GOALS.md) |
| 階段順序、授權、停止條件、維護、整體完成 | 本文件 |
| 啟動／續作入口 | [PROMPTS.md](PROMPTS.md) |
| 單一階段範圍與 planned checks | phases/phase-*.md |
| 本次補救的 runtime status 與 observed evidence | [build-log.md](build-log.md) |

context/ 只在執行有重大發現時建立；code_review/ 只在實際 review 時建立。舊 Issue logs 保留為當時歷史，本輪狀態只記 final_check，不在多處更新同一狀態。

## 已確認 repository baseline

Authoring 的唯讀快照：2026-09-12，branch GUI、HEAD 83ffa54，初始 git status --short 空；issue/final_check 尚不存在。根是唯一適用 AGENTS，未發現 issue/app 子層 AGENTS。
WSL Ubuntu-24.04 /home/minervamuses/research-agent-workspace；Git /usr/bin/git，Python 3.13.14 與 Poetry 2.4.1 來自 /home/minervamuses/miniconda3/envs/app。恢復執行須重新驗證，不能依此快照跳過 runtime gate。

- session.py:_run_one_shot_skill_turn 先 load，再呼叫 clear_skill_installer 但未檢查 cleanup_conflict。manager.py:SkillInstaller.clear 偵測 staged hash 改變會保留 source／backup 並回傳 conflict。session.finalize_and_record 僅在 active installer 時產生 host 安裝結果文字。
- session.py:turn_outcome 先 _begin_turn，再執行 one-shot；一般 Skill 沒有 mode override。installer pending 暫留 normal，clear 恢復 _installer_previous_mode，_run_turn 依恢復後模式分流。完成保存不改最初 metadata。
- desktop/service.py:_session_turn 在 turn_outcome 之前呼叫 _desktop_command_eligible；Citation 會即時 _load_skill_runtime。session completed 分支則在真正 one-shot load 前返回。repository.py:_same_logical_input／append_pending 是現有身分與不重寫的規則。
- 對應 tests：test_skill_adherence.py、test_citation_skill_activation.py、test_thinking_session.py、test_session_persistence.py、test_desktop_service.py、test_desktop_conversations.py、test_citation_e2e.py。重用 ZIP、_real_installer_session、Fusion fake models、RoutingFetcher／_SearchSaveModel 等局部接縫。
- package.json 的 test 為 Node test runner，build 為 tsc --noEmit + Vite；README 的 Tauri source build 會包含前端 build。現有 server._build_runtime_service 的 phase02 fixture 使用 FixtureSessionFactory，不等於真 Citation。

歷史來源只作範圍與成本參考：issue_08/build-log 的 2026-09-12 記錄報告完整 Python 1122（31.29 秒）、Node 165、TS/Vite；issue_02 有 Rust protocol 子集 12；issue_03(fin) 完整 Rust 36／Tauri 為 9/7。這些不是本計畫目前或未來 diff 的通過證據。先前對話中的暫存重現沒有持久測試檔，Phase 01/02 必須留下自己實際的 red/green 證據。

## 共用 runtime 與命令前置

所有 planned commands 均在 Linux bash 執行；PowerShell 只用 wsl.exe -d Ubuntu-24.04 進入。不要使用 Windows Python／Git／npm／Cargo。先確認各 phase 用到的 command -v 路徑。

```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace/app
```

原生 preflight 須區分使用者可見的 WSLg App 與代理的 X11 觀察能力；X11 root 全黑不能推論 App 黑屏。輸入法依 GOALS「輸入法限縮」跳過，不再安排 IME 診斷／環境處置或以它阻擋階段；其餘 native／可及性與安全 Citation 入口仍須驗證。具體證據與未解問題只記 build-log；不因環境推論加入 rendering／keyboard workaround。

下文 Python 命令 cwd 為 app/；Node／Cargo／Tauri 為 app/desktop/；其餘特別標示。timeout 是時間上限，不是獲准啟動昂貴命令的替代。preflight 預估超約十分鐘就先處理授權；不安裝缺少的工具或依賴。

## 執行授權與停止條件

### 啟動後的例行範圍

使用者明確要求執行本計畫後，可自主完成當前 phase 的直接局部修正、最少既有測試擴充、短離線檢查、自有 tmp fixtures 與可用的安全原生驗收。可更新本 bundle 的 log、重大 context、真實 review 和受新證據影響的未開始計畫；不逐步索權。
Phase 01/02 預期 production 只涉及 session.py 與 desktop/service.py；manager.py 已有正確保留機制，沒有新反例就不改。Phase 03 以驗收為主，若發現直接既有缺陷，只提出一個最小因果修補並遵守下列範圍限制。
Phase 04/05 依 GOALS 的 Issue 09 延期決定不列本輪例行範圍；只有使用者明確恢復，並滿足三項產品答案與具體實作授權，才可修訂路線後執行。不以「執行全部」代替恢復決定或未定 API/schema 授權。原 issue_09 的歷史 Git 授權不適用本輪。

### 需要新授權或停止的條件

- 穩定目標／相容性／必要驗收要改；選擇延期或用離線證據取代 required native 驗收。
- dependency／lockfile／environment／package manager、service／storage／concurrency、新 public API／protocol／schema／持久格式、重大框架替換或廣泛重構尚未獲准。
- 一個 focused fix 超過三個 production files、局部可解卻新增 persistent module、新 test／fixture／evaluation framework，或其他超出具體 phase 的 work item。
- live paid-provider、全資料／模型／GPU sweep、外部寫入、真實 store 操作、需使用憑證，或預估超約十分鐘的命令。缺原生工具、需安裝／下載或需 WSL shutdown／compositor／IME 重啟，不自行修環境。
- commit、push、merge、rebase、切 branch／worktree、部署，除非當下已有另一項明確授權；保留既有使用者 diff，不使用 reset/checkout 清場。

Focused implementation 兩次嘗試失敗就停下，保存因果證據與最小下一選項；一次昂貴嘗試無效不自行再跑。無關失敗只報告，不能藉驗收廣泛加修。

## 階段路線與依賴

| Phase | 可觀察結果 | Depends on | Phase file |
|---|---|---|---|
| 01 — Installer Skill switch | 衝突阻擋新工作、正常切換 mode 與 durable metadata 一致 | 無 | [phase-01](phases/phase-01-installer-skill-switch.md) |
| 02 — Completed Citation replay | Desktop 精確重送讀舊答案，runtime 失效仍不擋讀回 | 01 | [phase-02](phases/phase-02-desktop-completed-replay.md) |
| 03 — Native Desktop acceptance | Issue 02／08 各自原生互動有足夠證據 | 01、02 | [phase-03](phases/phase-03-native-desktop-acceptance.md) |
| 04 — Thinking contract/runtime | 延期保留路線：定案段位生效、資料／wire 契約一致 | 明確恢復範圍後：01、02；產品與具體 scope 門檻 | [phase-04](phases/phase-04-thinking-contract-runtime.md) |
| 05 — Thinking Desktop acceptance | 延期保留路線：定案 UI 與原生操作可驗收 | 明確恢復範圍後：04 | [phase-05](phases/phase-05-thinking-desktop-acceptance.md) |
| 06 — Regression and closure | 當前 diff 一次整合回歸及逐 Issue 結論有證據，09 明確記延期 | 01、02、03；04/05 依 GOALS 延期，不列本輪前置 | [phase-06](phases/phase-06-regression-and-closure.md) |

本輪 required 路線為 01 → 02 → 03 → 06。01/02 共用 canonical/mode 邊界，依序實作；04/05 的未來條件式內容保留，但延期期間不選取、不追問其產品答案，也不標功能 Complete。未來若恢復 09，須先依新決定與當時 live code 修訂 roadmap、各 phase 和回歸範圍。
僅在 GOALS／本 roadmap 的本輪範圍內，選第一個 dependencies Complete 的未完成 phase；Blocked 的外部條件沒有變化就不重試，可前進其他獨立且已獲准的 eligible phase。沒有可執行 phase 就彙報具體 blocker 並停止；06 仍不得繞過 03 未驗收依賴。

## 驗證成本安排

開發只跑直接 focused checks；所有階段自己的 required evidence 完成才能交接。Phase 06 擁有本輪唯一完整 Python suite、完整 Node suite、完整 Rust suite 與 Tauri source build。前段只跑需要的模組、protocol 子集或 tsc；不機械重複現有 evidence。
依 GOALS 的 09 延期決定，本輪只驗當前實際 diff 與保留行為，不執行未開始的 04/05 planned checks；既有 Normal／Extended 相容性仍由相關既有回歸保護。若 full suite 已跑後又有必要 production 修正，先跑最小受影響 check，第二次完整 suite 依使用者成本門檻辦理。

## 計畫維護與恢復

- build-log 是唯一狀態來源；恢復前比對 live code、diff、環境、先前 evidence，不依賴聊天記憶。
- required check fail／unverified 阻擋該 phase 及其 dependent phase；一般失敗保持 In progress，缺外部條件／決策或達嘗試上限為 Blocked。
- 新證據否定假設時，先更新本 roadmap 與受影響未開始 phase；不堆疊預防性修補。穩定目標只依明確使用者決策更新 GOALS。
- 完成／失敗的實質證據以 append correction 更正，不擦除歷史；已完成 phase 的驗收如被後續變更破壞，記錄失效與重新驗證需求。
- 重大發現才建 context/phase-NN-名稱-context.md；真 review 才建 code_review/phase-NN-名稱-review.md。初始不建立空目錄或虛構證據。

## 整體完成標準

- [ ] build-log 中本輪 required phases 01、02、03、06 Complete，每項 acceptance 有 observed evidence；04/05 依 GOALS 保留延期，不當成已完成功能。
- [ ] GOALS 的三個 P2、原生互動、定案 09 或明確延期、逐 Issue 處置均被覆蓋。
- [ ] 最終代表案例與適用回歸對應同一實際 code diff；歷史計數不當成最新結果。
- [ ] Issue 01 限縮不被改寫；02/08 各自缺口與 09 功能狀態清楚；無 evidence 的功能不結案。
- [ ] 必要 review 發現處理完、diff 只含核准因果範圍、git diff --check 通過、暫存證據先保留所需內容再清理；完成即停止。

## Authoring write set

初始 authoring 只新增四個 core Markdown 與上表六個 phase files，共十檔，當時全部 Not started；後續授權修改與實際 write set 見 build-log。
不修改既有 Issue bundle、AGENTS、application/tests、manifest、依賴、Git branch/index 或生成假 context/review。
