# Issue 01 — WSLg Desktop 中文輸入：執行計劃

## 概覽與資訊歸屬

- **Plan root：** `issue/issue_01`；沿用 `issue/issue_03`、`issue/issue_10`。
  使用 `phases/`，因根 `.gitignore` 的 `build/` 會忽略同名目錄。
- **Project shape：** application；Python agent 加 Tauri/React Desktop。
- **Risk：** medium；原因未完成 GUI 對照，可能需 host IME 設定，但無資料遷移。
- **Execution mode：** 使用者日後明確啟動後，在授權範圍內自主依序執行，
  遇到真實阻塞或額外授權條件才停止。此次 authoring 不啟動任何 phase。

| 文件 | 唯一負責內容 |
|---|---|
| [GOALS.md](GOALS.md) | 穩定目標、成功條件、保留行為與限制 |
| 本文件 | 執行順序、依賴、授權、修訂與整體完成 |
| [PROMPTS.md](PROMPTS.md) | 可直接使用的啟動／續作與審查指令 |
| `phases/phase-*.md` | 各階段工作、驗證與驗收 |
| [build-log.md](build-log.md) | 唯一 runtime 狀態及實際執行證據 |
| `context/`、`code_review/` | 實作後的重大發現、真正發生的 review；目前不建立 |

## 已確認的專案基線

以下是 2026-09-12 的 read-only authoring 觀察，不是實作驗收結果。

- Root：`/home/minervamuses/research-agent-workspace`。WSL Ubuntu 24.04，
  Linux Bash/Git；Conda `app` 提供 Python 3.13.14、Poetry 2.4.1、Node 24.18.0，
  Cargo/rustc 亦解析到 `/home/minervamuses/miniconda3/envs/app/bin/`。
  WSL 未提供 `rg`，檔案搜尋可改用 `git ls-files`／`git grep`。
- 初始 Git：branch `GUI`，HEAD `2870bcd75eb809120f9e4bb7a2ab1668330946d6`；
  `git status --porcelain=v1 --untracked-files=all` 為空。
  接手時重新讀取，不得覆蓋後續使用者改動。
- `main.py:5` 只轉交 `npm run tauri dev`；`app/desktop/src-tauri/tauri.conf.json`
  與 `Cargo.toml` 確認原生 Linux Tauri 路徑。launcher 本身沒有 IME 設定。
- 目前 shell 有 `WAYLAND_DISPLAY=wayland-0`、`DISPLAY=:0`、
  `LANG=C.UTF-8`；未列出 GTK／QT IM module、XMODIFIERS 或 GDK_BACKEND。
  `command -v` 未找到 ibus、fcitx、fcitx5 或常用 GTK demo/editor；
  process 名稱查詢未找到 IBus／Fcitx。這是目前 shell/session 的有限觀察。
- `dpkg-query -W` 查得 `libgtk-3-0t64` 3.24.41-4ubuntu1.3、
  `libwebkit2gtk-4.1-0` 2.52.6-0ubuntu0.24.04.1；同次查詢未列出
  ibus、fcitx5、ibus-chewing、ibus-libpinyin、fcitx5-chewing、im-config 的版本。
  這支持缺少常見 Linux IME 的假說，不證明根因或所有 IME 均不存在。
- `App.tsx:1277` 原樣保存 textarea value；`App.tsx:839–850`
  只以 trim 判空，傳送原 draft。`App.tsx:154–160,1168–1173`
  的 Enter guard 檢查 `nativeEvent.isComposing`。
  `tests/conversations.test.ts:220–227` 只測 predicate，不涵蓋 native IME events。
- `app/agent/desktop/server.py:395–403` 有精確 opt-in 的 `phase02` fixture；
  `fixture_session.py:365–390` 限制 root 為目前使用者擁有、非 symlink、
  `/tmp/research-agent-desktop-phase02-*` 直接子目錄。
  Fixture 保留真實 service／transport／ConversationRepository，使用 deterministic
  session；`app/tests/test_desktop_fixture.py:201–276` 已有保存與重建 service 對照。
- `app/desktop/package.json` 提供 `npm test` 與 `npm run build`；
  根 README 的 Desktop 區段提供 Cargo test、Tauri build；
  根 AGENTS 提供 `cd app && poetry run pytest`。本次未執行它們。

外部資料只作分流依據，不當作本機通過證據：
[Microsoft WSLg issue #9](https://github.com/microsoft/wslg/issues/9)
於查閱時仍為 Open，描述 Linux IME 需要配置／啟動，Windows IME 整合是期望方向。
Ubuntu 24.04 的 [ibus-chewing 套件頁](https://packages.ubuntu.com/noble/ibus-chewing)
確認該引擎可取得；是否適合使用者、依賴成本及 WSLg 啟動方式仍需本機確認。
不得照抄舊 issue 中的變數清單當作通用解法。

## 執行授權與停止條件

### 啟動後的日常授權

使用者送出 PROMPTS 的 Start/Resume 指令或等價的明確實作要求後，才可：

- 進行 phase 範圍內本機、可逆、低成本的實作與既有測試；
  重用現成 Desktop fixture，建立自己擁有的暫存資料。
- 依實際證據最小修改既有 `App.tsx` 及 `tests/conversations.test.ts`；
  只有 launcher 環境傳递被證實有缺陷才考慮 `main.py`。
  若 helper 定義需配合改動，先確認是否確實定義在 `App.tsx`，
  不任意搬到新 module。
- Phase 03 可補充既有根 `README.md` 的 IME 前置條件，並按觀察更新
  原 Issue 01；這是本計劃明列的未來交付，不是本次 authoring write set。
- 更新本計劃的 log、重大 context、實際 review 與被證據推翻的未開始 phase。
  現有環境已具備時可作 process-local 診斷；不得擅自接管使用者 IME daemon。

### 額外授權與阻塞

遵守使用者 Personal Engineering Defaults 的 Approval Gates。尤其：

- 安裝／升級 OS、Python、Node、Rust 套件或變更 manifest、lockfile、Conda
  定義之前，先提出確切包名、操作、下載／空間與時間估計，再取得明確批准。
  缺少 IME 不授權直接執行 apt install。
- Linux IME daemon 的新增、啟動／停止／替換，使用者／系統持久設定、
  shell startup、autostart 或 systemd service 變更，需先提出可審閱方案並取得批准；
  不停止別人的 daemon，不自動改 Windows IME／WSL 設定。
- 不預授權 dependency、public API、protocol、schema、儲存格式、新服務、
  concurrency model、通用 adapter 或 test framework；若有需要先說明因果與成本。
- 直接必要 production files 超過三個，或欲新增持久 module 而可用更小解法，
  需先說明完整 write set；不得藉 phase 拆分繞過此界線。
- 不預授權 credentials、live/paid providers、模型或 GPU sweep、真實 store 修改、
  外部寫入、commit、push、merge、rebase、branch/worktree 變更或部署。
- 命令預計約超過十分鐘須批准；一個昂貴嘗試失敗後不自動重跑。
  兩次 focused 修正失敗後，停止並回報證據、未解原因與最小下一步。
- 原生 GUI、必要引擎或必需驗證不可用時，將對應 phase 記為 Blocked。
  可先完成不依賴它的同 phase 檢查；不得用 skipped 當成 pass，
  不開始 dependent phase。需人工操作時說明工具限制。
- 目標、輸入方式範圍或必要驗收必須改變時，由使用者決定；
  計劃不能自行放寬成功條件以結案。

## 階段路線圖

| Phase | 可觀察成果 | Depends on | 文件 |
|---|---|---|---|
| 01 | 重現、Unicode 對照與目前 IME 條件已記錄，選定有證據的下一個最小實驗 | 無 | [重現與分流](phases/phase-01-ime-diagnosis.md) |
| 02 | 同一 session 對照與原生 composer 能完成組字、候選確認及單次送出；最小修正有直接因果證據 | Phase 01 | [最小修正](phases/phase-02-minimal-fix.md) |
| 03 | 中文保存、切換、Desktop 重啟與既有輸入行為通過；必要前置條件可重做 | Phase 02 | [完整驗收](phases/phase-03-acceptance.md) |

Phase 01 必要，因 Linux IME 與應用事件兩種原因會導向不同 write set。
Phase 02 是「依分流選一條修正路徑」，不是同時建置兩套方案。
Phase 03 只補跨啟動／保存驗收，不替前階段補做它自己的必要檢查。

## 計劃維護

- 必需檢查失敗時維持 In progress 或 Blocked，修正後重驗再推進。
- 新證據推翻計劃，先更新此 roadmap 及受影響的未開始 phase；
  不為符合原先猜測而保留不必要程式修正。
- `build-log.md` 保存實際命令與結果；重大失敗或更正採追加紀錄，
  completed evidence 不覆寫。穩定 GOALS 只隨使用者決定改變。
- 只有省略後會影響下階段判斷的發現才建立 `context/phase-NN-*-context.md`；
  只有真正 review 才建立 `code_review/phase-NN-*-review.md`。
- 中斷後比較 log、目前 diff 與 live code；不要盲目重做安裝、daemon 啟動或設定。

## 整體完成標準

- [ ] 三階段在 build-log 都是 Complete，且成功條件逐項連到實際證據。
- [ ] 真實組字、候選 Enter 零送出、後續 Enter 單次送出有原生 WSLg 觀察。
- [ ] fixture 中的中文 input、切換／重啟後 transcript 與 canonical JSON 一致。
- [ ] 回歸檢查按 Phase 03 完成；必要未驗證項不被隱藏。
- [ ] README 只記錄實測可用前置條件；取得所需額外授權並列明操作與復原方式。
- [ ] 實際 diff 只含必要修正與本計劃文件；暫時診斷已移除，
      `git diff --check` 通過，無未經授權 Git 或外部操作。
