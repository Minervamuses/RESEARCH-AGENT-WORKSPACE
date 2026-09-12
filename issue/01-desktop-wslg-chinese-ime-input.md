# WSLg Desktop 對話輸入框無法使用中文輸入法

## Issue 定位

- 類型：Desktop input／CJK IME integration。
- 優先度：高。
- 狀態：In progress；Linux IBus Chewing／X11 的原生組字、候選 Enter 零送出與後續單次送出已通過；完整重啟驗收受到本機 WSLg 圖形服務故障中斷。
- 排序理由：直接阻止中文使用者以主要語言和 agent 對話，列為第一個處理項目。
- 主要範圍：從 WSL/Linux 專案根目錄執行 `python main.py` 後開啟的 Tauri Desktop composer。CLI、模型回覆語言與其他原生 Windows 應用程式不先納入。

## 使用者觀察

> 「我跟 agent 對話時打字打不出中文，只能英文。」

目前 textarea 可以接收一般英文字母，但 Windows 中文輸入法的組字、候選字選取或中文 commit 無法正常進入 composer。這使 GUI 雖能顯示及保存 Unicode 回覆，使用者仍無法直接輸入中文問題。

## 已確認的 Source 與環境證據

- 根目錄 `main.py` 執行 `npm run tauri dev`；Desktop 是在 WSL 內啟動的 Linux Tauri/WebKitGTK 應用程式，透過 WSLg 顯示於 Windows，而不是原生 Windows GUI。
- 2026-09-06 的目前主機診斷顯示 `WAYLAND_DISPLAY=wayland-0`、`DISPLAY=:0`、`LANG=C.UTF-8`，但沒有 `GTK_IM_MODULE`、`XMODIFIERS` 或 `QT_IM_MODULE`，也沒有安裝或執行 IBus／Fcitx。
- `app/desktop/src/App.tsx` 的 composer 是一般受控 textarea；`onChange` 直接保存 `event.target.value`，沒有 ASCII-only 過濾或中文正規化。
- Enter 送出判斷已檢查 `event.nativeEvent.isComposing`，純函式測試也覆蓋 composition 中不得送出的情況。這能在 WebView 正確提供 composition event 時保護 IME，但不是 WSLg/Linux 輸入法是否存在的端到端保證。
- Desktop protocol、conversation persistence 與既有大型 Unicode 回答測試均可承載中文；現有證據不支持 Python backend 或儲存格式拒絕中文字元。
- Microsoft WSLg 的 IME 追蹤指出，Linux IME（例如 IBus）可用但需要手動配置與啟動；Windows IME 到 Linux 視窗的直接整合不能視為既有保證：<https://github.com/microsoft/wslg/issues/9>。

現有證據最支持「WSLg 執行環境缺少可用的 Linux IME」而不是「React composer 限制中文」。不過在同一環境以簡單 GTK/WebKit 輸入框做對照前，仍保留 WebKitGTK／WSLg 特定事件相容性問題的可能性。

## 期望行為

- 使用者可在 Desktop composer 以中文輸入法完成組字、選擇候選字並送出繁體中文文字。
- composition 期間按 Enter 只確認候選字，不得提前送出訊息；composition 結束後按 Enter 才送出一次。
- `Shift+Enter` 換行、英文輸入、貼上 Unicode 文字與既有對話保存行為不得退化。
- 解法應明確區分應用程式事件處理與 WSLg/Linux IME 環境需求，不在無證據時加入自製中文轉換器或 ASCII 特例。

## 最小確認方式

1. 在目前 `python main.py` 啟動的 composer 重現：切換 Windows 中文輸入法後輸入注音或拼音、選字並 commit。
2. 對照直接貼上 `中文測試`；若貼上與保存正常，先排除 textarea、protocol 與 persistence 的 Unicode 限制。
3. 在同一 WSLg session 使用最小 Linux GTK/WebKit 文字輸入框測試 IME，區分全域 WSLg／IME 問題與本應用程式問題。
4. 配置一種受支持的 Linux IME 後重測 composer，記錄輸入法程序、必要環境變數與 WebKitGTK backend。
5. 若 Linux 對照正常而本 app 失敗，再保存 composition event sequence，針對 Tauri/WebKitGTK 事件路徑修正。

## 驗收條件

- 從專案標準 WSL/Linux 啟動流程進入 Desktop 後，可直接輸入並送出一段繁體中文訊息。
- 候選字確認不會觸發 premature submit，訊息只在 composition 完成後送出一次。
- 保存後與重新載入 conversation 時，使用者中文輸入逐字一致。
- 英文、標點、`Enter` 送出與 `Shift+Enter` 換行行為維持不變。
- 所需的 WSLg／IME 前置條件可重現，且重啟 Desktop 後仍可正常使用。

## Issue 01 編號沿用

- 原 Issue 01「主聊天模型固定 4,096-token 上限疑似造成回答無提示截斷」依使用者決定視為已處理。
- Commit `eb5405b` 已將主模型 `llm_max_tokens` 提高為 OpenRouter 上 Gemini 3.8 Flash 公布的 65,536 completion-token 上限；該問題不再由本檔案追蹤。

## 主要參考檔案

- `main.py`
- `app/desktop/src/App.tsx`
- `app/desktop/tests/conversations.test.ts`
- `app/desktop/src-tauri/src/backend.rs`
- `app/desktop/src-tauri/src/lib.rs`
- `app/agent/desktop/service.py`

## 2026-09-12 實作與驗收進度

- 已依使用者授權安裝 `ibus ibus-chewing ibus-gtk3 x11-xkb-utils`，採用 session-local `GDK_BACKEND=x11`，啟動 IBus 並選取 chewing；未修改 application code、dependency manifest 或儲存格式。
- 同 session 的原生 GTK、最小 WebKit 與 Desktop 均可用注音按鍵組字；X11 下實際看見候選清單。組出「請幫我整理這篇論文的研究方法。」後，候選確認／組字確認 Enter 的 turn delta 均為 0，之後 Enter 的 delta 為 1。
- 隔離 fixture 的 canonical `displayInput` 與 `semanticInput` 逐字等於該句；Desktop 重啟後曾在 transcript 讀回該已保存句子。使用既有 deterministic fixture，沒有模型呼叫或真實使用者 store 寫入。
- 新啟動後的再次組字及剩餘英文／Shift+Enter 等原生回歸仍未完成：WSLg Xwayland 日誌出現 `request could not be marshaled: can't send file descriptor`，Xwayland 成為 zombie，Weston 隨後卡在核心 D 狀態；局部 compositor 復原未成功。這不是已確認的 React 或 persistence regression。
- Desktop `npm test` 155 passed；既有 Python fixture round-trip test 1 passed（1 個既有 LangChain deprecation warning）。測試不能替代未完成的原生驗收。
- 重現命令、turn ID、授權、失敗與復原紀錄集中於 [issue_01/build-log.md](issue_01/build-log.md)；目前保持未結案。
