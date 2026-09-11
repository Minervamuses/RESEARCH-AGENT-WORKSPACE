# Issue 10 — 對話式本機 ZIP Skill 安裝：執行計畫

## Plan Overview

- **Plan root:** `issue/issue_10`
- **Execution mode:** 使用者明確啟動後，Autonomous within authorization envelope。
- **Repository shape:** Application；單一 Python/Poetry 專案及既有 Desktop。
- **Change risk:** Medium；涉及檔案安裝、管理範圍與會話授權，但沿用既有儲存
  與工具流程，不改 persistent schema 或建立新服務。
- **Layout:** 沿用 `issue/issue_03` 的 `phases/`，避免被既有 `build/` ignore
  規則忽略。此 bundle 是新計畫，不修改舊計畫。

依 `GOALS.md`，先補既有 manager 的選定項目邊界，再讓標準 installer skill
透過一般 agent 及薄的 host action 使用它，最後完成跨入口與真實 ZIP 驗收。

## Source-of-Truth Map

| 資訊 | 唯一 owner |
|---|---|
| 目標、範圍、約束、研究依據 | `GOALS.md` |
| 順序、依賴、授權、停止條件、計畫修訂 | `PLANS.md` |
| 可複製的啟動與續作指令 | `PROMPTS.md` |
| 單階段作法與 planned checks | `phases/phase-*.md` |
| 階段狀態與 observed evidence | `build-log.md` |
| 實作中的重大發現 | 有需要才建立的 `context/` |
| 實際審查結果 | 有 review 才建立的 `code_review/` |

## Confirmed Repository Baseline

2026-09-11 authoring read-only 檢查：root 為
`/home/minervamuses/research-agent-workspace`，branch `GUI`，HEAD
`54c06085c66abf1d716aa3911173c64f7f414dd4`，worktree clean；當時相對
本機 `origin/GUI` ahead 2。此為起始快照，不是持續更新的執行狀態。
Windows PowerShell 只 dispatch WSL Ubuntu-24.04；Linux Git 與 Conda `app`
的 Python 3.13.14／Poetry 為本專案工具。

| 現有接點 | 已確認行為與實作意義 |
|---|---|
| `app/agent/extensions/paths.py` | 統一解析 drop-in 與 private state；不可硬編碼 checkout 路徑 |
| `app/agent/extensions/discovery.py` | 逐一驗證 `skill/` 直接 children；ZIP 目前被當作非法目錄；展開後 `name` 須符合目錄 ID，manifest 可省略 |
| `app/agent/extensions/manager.py` | preview、LLM authoritative changes、apply 重新掃描及 signature 目前皆是全量；安裝複製到 managed state，registry 記錄結果 |
| `app/tool/_internal/extension-management/SKILL.md` | private JSON planner；不具備解壓／工具迴圈，不應改成第二個通用 agent |
| `app/agent/session.py`、`app/agent/graph.py` | 明確 skill_name 進既有 graph；一般 skill turn 結束清除，catalog 來自 startup；citation 有特殊生命週期 |
| `app/agent/cli/slash_commands.py` | 已有 skill slash 選用，可作為明確選擇的既有路徑 |
| `app/agent/skills/runtime.py` | context 帶原始指令，未帶真實 root |
| `app/agent/tools/read_file.py`、`bash.py` | 根層相對 `forms.md` 目前以 cwd 解讀；bash cwd 固定為 app root；提供絕對 skill 路徑即可沿用工具 |
| `app/agent/cli/extension_management.py` | 管理 CLI 刻意不進 `session.turn` |
| `app/agent/desktop/service.py` | 管理 RPC 禁止 active turn 中執行，apply 建立獨立 display-only turn；不能在 agent turn 內遞迴呼叫該 RPC |
| `app/agent/tools/inventory.py`、session tool universe | 一般 shell/read 已有；不存在對話 installer 的 skill-scoped management action |

既有 `app/tests/test_extension_user_journey.py` 以 deterministic management
model 與真實 host validation 測試；沿用此 seam，不建立新測試框架。
所有 phase 指令均為未執行的 planned checks；authoring 不跑應用測試或 build。

## Execution Authorization

### 本次 authoring 與日後 launch

本次只建立七份計畫 Markdown，使用者已明確授權 commit/push。
此 Git 授權不延伸至日後 implementation 的提交、推送或其他外部寫入。

日後使用者送出 `PROMPTS.md` 的完整 Start/Resume 或等價執行要求後，可在以下
精確 envelope 內連續完成三個階段，不需逐階段再詢問：

- 修改直接必要的既有 production files，即使合計超過三份；預期集中於上表
  接點，加上 `app/skills/skill-installer/SKILL.md`、必要的既有格式 optional
  manifest、相關使用文件及最小回歸測試。
- 對現有 manager 加入 backward-compatible、只處理選定 skill 的 in-process
  參數／preview scope，並加薄的 skill-scoped host action；原全量呼叫語意保留。
- 加入僅限此 installer 的 in-memory 對話續接／授權關聯；不新增持久化資料格式。
- 優先在既有檔案串接；若 stdlib 解壓檢查確需重用，最多加入 skill 自帶的小型
  helper script，不建立通用 importer 模組、adapter、服務或來源管理平台。
- 在隔離 temp 路徑跑 phase 所列 local checks、測試用無害 shell 操作、一次
  合理且預期十分鐘內的完整 pytest、Poetry build；不執行下載 skill 的腳本。
- 為代表性驗收讀取公開上游固定版本 ZIP，或沿用使用者提供／已快取檔案；
  不以下載來源的指令或 dependency 要求擴大授權。
- 更新本計畫的 observed log、重大 context、實際 review 與被證據推翻的未開始
  phase；完成測試後只做必要的範圍內 cleanup。

以上是將來 launch 明確批准的內容，計畫文件本身不啟動實作。

### Stop and obtain fresh authority

- 目標、非目標、資料保留或既有 approval／互斥行為需要改變。
- 需要新依賴、package manager／環境／lockfile 變更，或超出上述 in-process
  邊界的 public API、Desktop protocol、registry／persistent schema 變更。
- 需要新服務、通用框架、新 concurrency model、背景掃描或 GUI 拖曳 UI。
- 需要操作真實使用者 skill/state、覆寫或刪除未獲授權資料、使用 credentials、
  live/paid provider、執行第三方 skill 程式，或對外部系統寫入。
- 需要 commit/push/merge/rebase、branch/worktree 變更、部署或發布；除非目前
  執行對話另有明確授權，不能沿用本次純計畫 commit/push 的許可。
- 指令預期超過約十分鐘、需第二次 expensive run，或必要證據無法取得。

遵守所有 applicable `AGENTS.md`。兩次 focused 修補仍無法解決同一問題時，
記錄原因與最小下一步並停止；一次 expensive 失敗後不自行再跑。

## Phase Roadmap

| Phase | 可觀察成果 | Depends on | Phase file |
|---|---|---|---|
| 01 | 管理器能僅安裝選定 skill，ZIP 共存不污染 catalog，其餘變更不受影響 | None | `phases/phase-01-scoped-installation.md` |
| 02 | 一般對話可用公開 installer 處理 ZIP、澄清並調用既有 host 管理操作 | Phase 01 | `phases/phase-02-conversational-installer.md` |
| 03 | 真實 ZIP、CLI/Desktop、新 catalog 與原始資源完整性有驗收證據，文件可照做 | Phases 01 and 02 | `phases/phase-03-acceptance-and-documentation.md` |

Phase 01 不把 agent orchestration 混入 manager；Phase 02 不以 UI RPC 重入
active turn。Phase 03 不代替前兩階段應先通過的 focused checks。

## Acceptance Coverage

| GOALS.md 成功條件 | 主要證據 owner |
|---|---|
| ZIP 共存、selected-only、保留其他 pending changes、stale preview | Phase 01 |
| 明確自然語言／slash 選用、澄清續接、批准範圍、取消清理 | Phase 02 |
| 原文及完整 bundle、skill root／絕對資源路徑、normal mode／既有行為 | Phase 02 |
| CLI/Desktop 完整流程、真實上游 ZIP、新 startup catalog、打包與文件 | Phase 03 |

## Plan Maintenance

- 以 `build-log.md` 為唯一 runtime status。必須先核對 live worktree，保留既有
  使用者修改；不能因計畫列了某檔便覆蓋其中無關變更。
- Required check 失敗或缺證據，phase 維持 `In progress`／`Blocked`；禁止開始
  dependent phase。先區分原因，不堆疊猜測修補。
- 新證據推翻後續作法時，先更新本 roadmap 與受影響的未開始 phase，再重新做
  fresh-agent walkthrough；已完成證據及失敗歷史保留，以追加 correction 修正。
- 只有使用者改變穩定意圖才改 `GOALS.md`。重大發現才寫 context，真正 review
  才寫 code_review，不建立空白檔案或新的協調協定。

## Overall Completion Criteria

- [ ] 三個 phase 在 `build-log.md` 都是 `Complete`，每項成功條件都有實際證據。
- [ ] 代表性 ZIP 從一般對話輸入到 managed install、新 catalog 與資源讀取通過。
- [ ] selected-only、批准關聯、取消與 stale preview、原資料保留無未解決回歸。
- [ ] required focused checks、一次完整 pytest、Poetry build／wheel 內容檢查及
      `git diff --check` 有實際結果；缺必要證據時不能直接結案。
- [ ] 使用文件清楚交代路徑、觸發方法、啟用時點與依賴限制；沒承諾未驗證的
      跨產品全部功能相容或 live-model 自主成功率。
- [ ] 最終獨立審查的實質 findings 已修正，或使用者明確接受並記錄限制。
