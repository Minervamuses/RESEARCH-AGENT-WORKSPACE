# Final Check — Build Log

本檔唯一保存這次補救與驗收的 runtime phase status／observed evidence。
計畫文件描述將做什麼；舊 Issue 紀錄僅作歷史來源，不表示本輪已驗證。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Installer Skill switch | In progress | 2026-09-12 | — | 本輪 preflight；待 red/green | — |
| 02 — Completed Citation replay | Not started | — | — | — | — |
| 03 — Native Desktop acceptance | Not started | — | — | — | — |
| 04 — Thinking contract/runtime | Not started | — | — | — | — |
| 05 — Thinking Desktop acceptance | Not started | — | — | — | — |
| 06 — Regression and closure | Not started | — | — | — | — |

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
