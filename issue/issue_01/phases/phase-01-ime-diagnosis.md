# Phase 01 — 原生重現與 IME 問題分流

## 目標

取得目前主機的原生 composer 基線，區分 Unicode 資料路徑與真實組字問題，
確定 Phase 02 的一個最小實驗及其缺少的環境／授權前置條件。
此階段不以「讀過原始碼」或「看不到 IME 變數」宣告找到根因。

## 來源、範圍與非目標

來源：[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、原 Issue 01、
`main.py`、`app/desktop/src/App.tsx`、`app/agent/desktop/fixture_session.py`。

範圍：本機 read-only 檢查、既有 fixture 原生 GUI 重現、
既有可用 GTK／WebKit 對照及最小事件觀察。
非目標：程式修正、IME 安裝、持久設定、跨版本或多引擎測試。

## 依賴與前置條件

- 使用者已啟動本計劃；沒有前置 phase。
- 依 PLANS 完成 Linux／Conda app gate。確認使用者實際輸入方式；
  尚未回覆可先做不依賴引擎的檢查，不能代替使用者選定安裝引擎。
- **待確認：** 能否操作原生 WSLg 視窗與 IME。若 agent 只能用網頁瀏覽器，
  排定使用者操作並記錄來源；不能合成事件假裝真實組字。
- **待確認：** 同 session 可用的 GTK 與 WebKit control。
  查詢已安裝檔案及程式 help，選既有 editor／GTK demo 與 WebKit test browser
  的簡單文字欄位；不得假定 gtk3-demo、MiniBrowser 或 Python GI 已存在。
  沒有 control 時，記下 Phase 02 需取得的最小元件／批准，不安裝整個桌面。

## 預期涉及元件與授權

此階段不改 production／test files。只可建立本階段自有暫存 fixture，
更新 log 及重大 context。其他停止條件見 PLANS。
Tauri 第一次編譯若可能超過十分鐘，先提供成本估計取得批准。

## 實作與驗證計劃

### Preflight

在 WSL Linux shell 執行（敏感環境只查存在與否，不 dump values）：

```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace
command -v bash git python poetry node npm cargo rustc
git status --short
printenv DISPLAY WAYLAND_DISPLAY LANG GTK_IM_MODULE XMODIFIERS QT_IM_MODULE GDK_BACKEND
command -v ibus ibus-daemon fcitx5 fcitx gtk3-demo gtk4-demo gedit gnome-text-editor
dpkg-query -W ibus fcitx5 ibus-chewing libgtk-3-0t64 libwebkit2gtk-4.1-0
ps -eo comm= | grep -E 'ibus|fcitx'
```

未設定、找不到指令或 package 時的非零退出是診斷資料，不是環境已修復的判據。
另外確認 session bus、實際 WebView display backend／GTK IM context（若可觀測）。
僅有 WAYLAND_DISPLAY 與 DISPLAY 不足以斷言 app 實際使用哪個 backend。

### 原生基線（本階段以觀察代替 Red／Green）

先確認 fixture opt-in 仍如 PLANS 的原始碼所述，再執行標準入口：

```bash
ime_fixture_root=$(mktemp -d /tmp/research-agent-desktop-phase02-XXXXXX)
export RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT="$ime_fixture_root"
export RESEARCH_AGENT_DESKTOP_FIXTURE=phase02
python main.py
```

保存本次 fixture root 的絕對路徑供 Phase 02／03 沿用。
在 GUI 中確認 fixture 的 p1／p2 與 seed conversations 確實出現，
再選 p1 的對話操作；fixture 未啟用時不要按 Send。
不要輸入 fixture control markers、調用工具或測試 crash path。

1. 先記錄初始 turn 數。以目前使用者的輸入法實際組字、選字，
   記錄候選窗／preedit／commit 各步是否可見；未能輸入也記錄確切步驟。
2. 貼上 `中文測試`，送出一次並切換 conversation 後切回；
   比對 transcript 與 fixture canonical JSON，確認 Unicode 對照。
3. 若已有可用 Linux IME，於同 session、相同引擎及已知 backend 下測
   GTK control、最小 WebKit 文字欄位與 app。若缺少 engine/control，
   明列未做的格子及原因，不把未測視為失敗。
4. 只有不能區分事件層原因時，短暫觀察 `compositionstart/update/end`、
   `beforeinput/input`、`keydown/keyup` 的 key、isComposing、
   value 與發送時機。優先 DevTools 暫時 listener；
   不為蒐集 trace 提交持久 diagnostics，也不要修改正常文字內容。

### 分流與交接決策

| 觀察 | Phase 02 最小下一步 |
|---|---|
| Unicode 貼上／保存正常，未找到可用 Linux IME | 提出一種符合偏好的 engine／啟動方案，取得批准後驗證；尚不能宣告根因確定 |
| 已有 IME，GTK control 也無法組字 | 查該 session 的 engine／bus／module；不修改 React |
| GTK 正常，但最小 WebKit 與 app 都失敗 | 查 WebKit／GTK input context 或 backend；不把共同失敗歸因於 composer |
| 最小 WebKit 正常，只有 app 失敗 | 記錄 app 的事件 sequence，再考慮 composer 最小修正 |
| 本次無法重現，三者均正常 | 保存現況與所需前置條件；Phase 02 只重驗、不製造 patch |
| 貼上或保存也失敗 | 停止原假說，界定實際資料路徑；超出本計劃日常 write set 時先修訂並取得批准 |

control 不可用但「IME 前置條件缺失」可確定時，可完成本階段的分流；
Phase 02 取得前置條件後必須補做 control 才能選擇 app 修正。
其他原因仍無法區分則保持 Blocked。

### Focused 與 broader checks

從 `app/desktop`：
```bash
node --test --experimental-strip-types --test-name-pattern="composer sends" tests/conversations.test.ts
```

從 `app`，檢查既有無 provider 保存 seam：
```bash
poetry run pytest tests/test_desktop_fixture.py::test_real_service_round_trip_registration_restore_and_final_only_answer -q
```

本階段無程式變更，不跑 full suite／release build。上述測試不是 native IME 證據。
required baseline check 失敗先診斷；不堆疊修補或直接進 Phase 02。

## 安全、復原與驗收

沒有 schema／migration 工作。只保留自己建立的 fixture root；
關閉自己啟動的 Desktop，不終止既有使用者程序或 IME。

- [ ] 實際 composer 的組字嘗試與 Unicode 貼上／保存有明確觀察。
- [ ] 環境、輸入偏好、control availability、未測項與來源完整記錄。
- [ ] 下一個最小實驗與必要批准明確；未把缺少變數視為確定根因。
- [ ] 兩個 focused baseline checks 有結果且必要失敗已解釋／處理。
- [ ] Phase 02 的路徑已依 evidence 修訂，未提前進行安裝或 app patch。

## 證據與交接

結果與命令只寫 `../build-log.md`。重大診斷、fixture root、
控制程式選擇與下一步理由寫 `../context/phase-01-ime-diagnosis-context.md`
（僅當確實產生）。必要 GUI 基線未取得時停在本階段；
前置安裝方案可交給 Phase 02，但批准未到前不得執行。
