# Issue 01 — WSLg Desktop 中文輸入：目標

## 目的與背景

依據 [Issue 01](../01-desktop-wslg-chinese-ime-input.md)，使用者從專案根目錄執行
`python main.py` 開啟 WSLg Desktop 後只能輸入英文，中文組字／候選字無法正常進入 composer。
本計劃要恢復實際中文輸入；根因仍需同一 WSLg session 的對照實驗確認。
已確認的程式與環境基線由 [PLANS.md](PLANS.md) 保存。

## 預期成果

- 使用者能在既有 Linux Tauri/WebKitGTK composer 直接組字、選字、送出繁體中文。
- 候選字確認與訊息送出清楚分開；保存與重啟後仍保有原始中文輸入。
- 必要的 Linux IME 前置條件與啟動步驟可重現，修正範圍由證據決定。

## 成功條件

- [ ] 在既有 `python main.py` 啟動路徑、具備已驗證 IME 前置條件時，
      實際用鍵盤組出「請幫我整理這篇論文的研究方法。」並送出。
- [ ] composition／候選字確認期間按 Enter 不產生任何新 turn；
      composition 結束後再按 Enter，恰好新增一個 turn。
- [ ] 切換到另一個 conversation 再切回、關閉並重新啟動 Desktop 後，
      transcript 的 `userText` 與 canonical conversation 的 `display_input`、
      一般訊息的 `semantic_input` 均逐字等於送出文字。
- [ ] 英文 `IME test 123`、中英文標點、Unicode 貼上、一般 Enter 送出、
      非 composition 時 Shift+Enter 換行均維持既有行為。
- [ ] 從新的 WSL shell 按已記錄前置步驟重新啟動 Desktop，仍能完成中文輸入。
      不要求 Windows 開機自動啟動 IME，也不要求 WSL／Windows 系統重啟測試。
- [ ] 每項結果都有實際觀察。單元測試、Unicode 貼上或 Chromium 自動化不能代替
      WSLg 原生視窗內的實際候選字與組字驗收。

## 範圍與非目標

範圍是目前主機的 WSL/Linux IME、標準 Desktop 啟動流程、composer 事件處理、
上述輸入與保存驗收，以及既有 README 中必要的前置條件說明。
純環境修正且程式零修改可以是完整解法。

非目標：原生 Windows port、Windows IME bridge、自製中文轉換器、支援所有 CJK
引擎或桌面環境、CLI 輸入改造、模型／RAG／citation 改善、其餘 issues、
UI 重設計、通用 IME 管理服務、protocol／storage schema 變更。

## 保留行為與限制

- **執行環境：** 根 `AGENTS.md` 要求 Linux runtime、Conda `app`、Poetry，
  保留 LF。Windows 僅用來呼叫 WSL，不混用 Windows Python、Node、Git 或 Cargo。
- **最小修正：** 使用者的 Personal Engineering Defaults 要求因果範圍、
  最小代表性驗證與低成本；同時保留原本輸入容量、送出防重與 trust controls。
- **資料與成本：** 驗收重用既有 isolated Desktop fixture，保留使用者 store、
  對話與設定；不以真實模型呼叫、GPU 或新測試框架取得證據。
- **授權：** 本次只建立計劃。日後實作啟動與額外授權界線見
  [PLANS.md](PLANS.md#執行授權與停止條件)；不可把此文件解讀成安裝或設定授權。
- **完成判準：** 上述代表性訊息為普通對話，避免 slash command 或 fixture 控制字串。
  fixture 使用相同原生 composer、transport 與 canonical repository，
  足以驗收輸入與保存；模型回答品質不在範圍內。

## 待決事項與技術未知

- 使用者實際輸入方式尚待回覆；繁體注音只是規劃範例，不代表已選定或核准引擎。
  Phase 01 記錄實際偏好；若未回覆，可完成與引擎無關的基線，
  但安裝或驗收引擎前必須確認。若使用者要求僅用 Windows IME，
  必須先確認這是否改變本計劃的 Linux IME 解法範圍。
- 主因可能是缺少 Linux IME，也可能是 WebKitGTK／composer 事件相容性：
  Phase 01 分流，Phase 02 用同 session 對照確認並只修正有證據的路徑。
- 適用的 IME 啟動方式、GTK module 與 display backend 尚未實測；
  Phase 02 依本機套件與引擎文件確定，不預設環境變數的固定組合。
- 原生 GUI 控制工具與實際中文鍵盤操作是否可用，須在 Phase 01 確認；
  若工具不能操作 WSLg／IME，由使用者實際操作並提供觀察。
  缺少這項證據時不得宣告功能完成。

## 來源

- [Repository AGENTS.md](../../AGENTS.md) 與本次使用者提供的 Personal Engineering Defaults。
- [Issue 01](../01-desktop-wslg-chinese-ime-input.md)。
- 使用者於 2026-09-12 要求先閱讀 AGENTS，再以 long-horizon-plan-author 撰寫 Issue 01 計劃。
- [PLANS.md：基線與來源](PLANS.md#已確認的專案基線)。
