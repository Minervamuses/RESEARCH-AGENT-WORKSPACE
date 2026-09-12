# Phase 02 — 依對照證據恢復中文輸入

## 目標

讓同一 WSLg session 的 control 與實際 composer 能完成中文組字，
候選確認 Enter 不送出，結束組字後 Enter 恰好送出一次。
解法可能只有環境設定；程式 patch 不是必備產物。

## 來源、範圍與非目標

來源：[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、Phase 01 log／material context。
範圍限 Phase 01 證據所指向的一條修正路徑及直接回歸檢查。
非目標：同時部署 IBus／Fcitx、多引擎或 backend sweep、Linux desktop 安裝、
WebKit 升級試錯、通用 IME daemon supervisor、無證據的 keyCode／延遲送出 workaround。

## 依賴、前置與未知

- Phase 01 Complete；重讀其控制程式、fixture root 與未解項目。
- engine 選擇、安裝／daemon／持久設定若有需要，必須已有明確批准。
- **待確認：** 本機套件候選版本、相依下載與空間、bus 與 module 啟動需求。
  先查 `apt-cache policy`、相應 package 的 `apt-get -s install`、
  engine 的本機 help／man 及官方文件。不得將文件中的舊 WSLg workaround
  當成目前版本的有效命令。
- 若偏好確認為繁體注音，可評估 Ubuntu noble 的
  [IBus Chewing](https://packages.ubuntu.com/noble/ibus-chewing)；
  若為其他方式，使用者選定後評估相應單一引擎，不默默改成注音。
- environment-only 路徑仍需補足 GTK／最小 WebKit control；
  比較 GTK 成功、WebKit 失敗時不直接編輯 React。

## 預期涉及元件與授權

- 環境路徑：經批准的 Linux IME packages、process-local 啟動／環境設定。
  持久設定檔的具體名稱必須在批准前列清楚；預設不用新增 autostart/service。
- app 路徑：首選既有 `app/desktop/src/App.tsx` 與
  `app/desktop/tests/conversations.test.ts`。僅有獨立證據才調整 `main.py`；
  不改 Python backend、Rust transport、protocol 或 persistence。
- 完整授權與停止條件見 PLANS。提出額外批准前先給出確切命令／檔案、
  較小替代方案為何不足、下載／時間成本與設定復原步驟。
  取得批准後不用為同一已授權操作反覆詢問。

## 實作與驗證計劃

### Preflight 與 Red

重查目前 diff、session／engine 狀態與 Phase 01 baseline。
用原失敗步驟重現一次，固定同一測試文字、引擎與 backend。
若無法重現但三層對照均正常，不製造 failing test 或不必要 patch，
記錄現況並用相同驗收確認。

### Green：環境路徑

1. 先取得明確批准，再配置一個引擎及必要 control 元件。
   不自動升級整個系統，不引入新的專案 dependency／lockfile 變更。
2. 依目前 engine／GTK 的實際需求，先測 process-local 環境與已批准 daemon
   啟動方式，確保和 Desktop 位於同一 GUI／bus session。
   只有需要且證實有效的變數才加入；
   不固定強制 GDK_BACKEND、GTK_IM_MODULE 或 QT_IM_MODULE 的通用組合。
3. 重測 GTK → 最小 WebKit → composer。一次只改一項主變數。
   若三者均恢復且候選 Enter／單次送出正確，停止擴大修正，
   保留 app code 不變；把已實測 recipe 交給 Phase 03 寫入 README。
4. 若需要持久設定，先取得對確切檔案／操作的批准並保存原值；
   不由 `main.py` 自動安裝、拉起或替換 IME daemon。

### Green：僅 app 失敗時

1. 只有同條件最小 WebKit control 可輸入，而 app 事件 trace 顯示
   composition 與 sendTurn 的錯誤關係，才走此路。
2. 在既有測試位置增加能區分「該 trace 提前送出／重複送出」
   與「候選確認零 turn、之後一次 turn」的最小 regression。
   不把字串包含檢查當作 DOM 事件正確性證據。
3. 若 trace 要求 composition state，局部處理 start／end／keydown 與焦點／送出；
   改動應由實測支持。不要預先加入固定 timeout、UA 判斷、
   deprecated keyCode 特例或新 abstraction。
4. 保留原始 value、一般 Enter、Shift+Enter、disabled／busy 與既有送出防重。
   以原生組字重測修正效果；純 predicate green 不等於 GUI green。

不安排獨立 refactor。必要局部簡化只能在 green 後做，並重跑受影響檢查。

### Verification

- **每條路徑都必需：** 同一引擎／session 的 control 對照與實際 composer
  組出 GOALS 訊息；比較候選確認前後 turn delta=0，
  組字結束後 Enter delta=1，UI 與 canonical repository 都僅一個 logical turn。
- **程式有變更時，從 app/desktop：**
  `node --test --experimental-strip-types tests/conversations.test.ts`、
  `npm run build`。若現有 Node test seam 無法表達事件 state，
  先提出最小測法，不為窄修正新建 browser test framework。
- **環境-only：** 重用 Phase 01 的程式基線；驗證成本集中於
  原生對照，不無故重跑 Python／Rust suite。
- **範圍擴展條件：** 若 Rust 或 backend 修改變必要，停止並重新界定
  write set／授權／checks；不把這些改動藏在環境修正。
- required check 失敗或 native 操作缺失，維持 In progress／Blocked；
  Phase 03 不得先行。失敗次數與昂貴命令規則見 PLANS。

## 復原與驗收

process-local 實驗關閉後恢復原 shell 變數。只停止本 phase 經批准啟動的程序。
持久設定只還原此次修改的原值，不覆寫使用者其他設定；
套件移除可能影響依賴，另確認操作而不自動 apt autoremove。
程式修復僅調整本次必要 diff，不用 git reset 覆蓋工作樹。

- [ ] 同 session 對照證明修正路徑；未靠猜測堆疊 environment 與 React patch。
- [ ] 原生中文組字、候選 Enter 零送出、後續 Enter 一次送出均有觀察。
- [ ] 若有程式修改，新增最小 regression 可區分問題且 scoped checks 通過。
- [ ] 必要環境 recipe／設定原值／批准及剩餘限制有紀錄。
- [ ] 無無關資料、依賴、公共介面變更，無永久 diagnostics。

## 證據與交接

實際命令、成本、批准、before／after 與驗收寫 `../build-log.md`；
會影響重啟驗收的選擇、環境與因果寫
`../context/phase-02-minimal-fix-context.md`，只在有重大發現時建立。
Phase 03 接收已驗證 recipe、相同 fixture root、必要 diff 與未解限制。
