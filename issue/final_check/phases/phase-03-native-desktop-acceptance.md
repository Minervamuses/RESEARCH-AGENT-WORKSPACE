# Phase 03 — Issue 02／08 原生 Desktop 剩餘驗收

## 目標與來源

在可操作 Linux Desktop 中補足 menu 與 Citation 原生流程；分別記 Issue 02 和 08 的實際 evidence，不以 Node helper／SSR／假 Session 取代真操作。
來源：[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、[02 menu](../../issue_02/phases/phase-02-composer-menu.md)、[02 integration](../../issue_02/phases/phase-03-integration-acceptance.md)、[08 Desktop](../../issue_08/phases/phase-02-desktop-integration.md)、其各 build-log、README Desktop instructions。

## 範圍、元件與非目標

主要是驗收；App.tsx／SlashComposer／conversations helpers、main.py、desktop/server.py／fixture_session.py 為觀察入口。
直接新反例才形成最小局部修補；不得把候選路徑當成全部可改的清單。
不重開 Issue 01 已豁免矩陣，不修 WSLg／IME 系統，不接付費 provider、不用真使用者 store，不新增專用 retry UI 或通用 GUI test framework。

## 依賴與兩個前置門檻

Phase 01、02 Complete。開始先確認 Linux native 控制／顯示可用；若有 xdotool，可做 timeout 3s xdotool getdisplaygeometry 等短唯讀 query，記工具、display、IME／輔助工具結果。歷史 timeout 只作參考。
先分別記使用者的 App 顯示／輸入觀察與代理工具能否操作該視窗。若使用者回報 Windows 輸入法（例如華碩智慧輸入法），先查明 Windows→WSLg→GTK/WebKit 的輸入鏈與 Linux IME 狀態；不能把 Shift 或 menu composition handler 當成預設根因，也不能用啟用 Linux 注音當成已修復 Windows 輸入法相容性。
沒有可操作原生 surface 就記 Blocked 並停止重複啟動。需要 restart／安裝／環境修復依 PLANS 辦理；使用者可另提供具體原生操作證據或限縮，但未回覆不等於豁免。

第二門檻是安全 Citation 入口：RESEARCH_AGENT_DESKTOP_FIXTURE=phase02 的 FixtureSessionFactory 不執行真 ChatSession，test_desktop_fixture.py 也明確禁止該 factory 呼叫 ChatSession.create。
**尚未確認的命令：** 真 Citation UI 的完整 isolated launch recipe。先讀 server._build_runtime_service、現有 Desktop Citation tests／_fixture_services，核對是否能用既有 dependency-injection 及一個自有 temporary launcher 接真 ChatSession、offline model/fetcher、tmp history/citation/extension paths；確認零外部 provider 與零 user store 觸及，再開始 UI。
若既有接縫不足，先呈現具體最小必要的 local fixture 改動、檔案／測試／成本；涉及新持久 module/framework 或超出 scope 的變動須取得新授權。不得默認普通 python main.py 是安全替代。

## 計畫操作與驗證

### Issue 02 已有隔離入口

沿用原 Issue 02 recipe；已完成 PLANS 的 Conda app gate，cwd repo root：

```bash
SLASH_MENU_FIXTURE_ROOT=$(mktemp -d /tmp/research-agent-desktop-phase02-slash-menu-XXXXXX)
RESEARCH_AGENT_DESKTOP_FIXTURE=phase02 RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT="$SLASH_MENU_FIXTURE_ROOT" python main.py
```

這是 app dev launcher，非自動完成驗收。只在啟動編譯預估符合成本門檻時啟動，監看 readiness 後開始 bounded journey；就緒後的互動時間另記。A/B/restart 保留同一自有 tmp root，完成後先保留必要去敏 evidence。

### Issue 02 原生 checklist

| 操作 | 必須看到的結果 |
|---|---|
| `/`、`/sta`、上下鍵、Enter 選 /status | 篩選與選取正確；插入 `/status `，focus 在 composer、caret 尾端、request delta=0；再 Enter 恰一次 local request，無 LLM。 |
| /ingest 參數、mouse、Escape／blur／清空／多行、Shift+Enter／Tab | 補命令不自執行；滑鼠選取不被 blur 吞掉、active option 可見；關閉規則、換行及焦點移動符合原計畫。 |
| 可用 Linux IME／輔助工具 | menu 情境 composition/commit Enter 不誤選或送出；下一 Enter 才做指定動作；可觀察清單名稱、active option 與關閉狀態。缺工具逐項 unavailable。 |
| A→B→A、restart、tmp extension apply | catalog、draft、selection/generation 正確；current catalog 不因 apply 偷換，新 session/restart 才反映；未知／CLI-only 命令拒絕。 |

menu 的 IME／Shift+Enter 是 Issue 02 自己的互動條件，不延伸為重跑 Issue 01 已豁免資料。

### Issue 08 真 Citation checklist

1. 經 menu 選 Citation，補 fixture 文獻需求：選取本身零送出；送出後 busy／Normal 說明、真工具活動、一份經 gate/render 的正式答案，且與 tmp canonical JSON／save bundle 一致。
2. 完成後送一般問題：無 Citation scope/tool；selector 與 backend 原模式相同。A→B→A 和 backend restart 只讀相同歷史，model/provider/save/scope 計數不增加、bundle 保留。
3. 用可控離線 failure／cancel 見到恢復可操作、failed/interrupted 不自行重跑。嚴格 duplicate/identity 以 Phase 02 跨層測試為主要證據，不另加 GUI 控件。

### 支援檢查與 failure gate

純驗收不形式寫 red/green；發現具體缺陷後才用最小既有 test red、直接修補、green，再重做受影響原生操作。cwd app/desktop/：

```bash
timeout 300s node --test --experimental-strip-types tests/conversations.test.ts tests/backend.test.ts tests/trust.test.ts
```

僅在相關 UI 改動或舊 evidence 無法覆蓋時執行此 focused 組；fixture 有改動才在 app/ 跑 poetry run pytest tests/test_desktop_fixture.py -q。其餘 full regression 由 Phase 06 統一安排。

## 驗收條件

- [ ] Issue 02 原生 checklist 逐項有實際操作／request／focus/caret／可及性證據，不能只記畫面存在。
- [ ] Issue 08 使用真 ChatSession／Citation service；正式答案、工具活動、磁碟產物與 cleanup/lifecycle 相符。
- [ ] required unavailable／skipped 有明確使用者限縮才可移除門檻；僅完成 menu 不代表 Citation 或整階段 Complete。
- [ ] 全程 isolated paths／offline provider，保留 Issue 01 原有限縮，不改 user store 或現有 Issue 歷史。

## 證據、恢復與交接

在 ../build-log.md 分開列 Issue 02 與 08 acceptance→操作與 artifact、實際 revision/diff、native surface、fixture 性質、fail/unavailable 原因；必要 screenshot/log 放 phase 開始後的自有 evidence 目錄，不預建空檔。
只停止自己啟動的程序、清自己的已核對 tmp；不得 kill compositor／重設 WSL。兩項 required evidence 齊全才 Complete；Blocked 時按 PLANS 選其他獨立 eligible phase，不能直接跳最終結案。
