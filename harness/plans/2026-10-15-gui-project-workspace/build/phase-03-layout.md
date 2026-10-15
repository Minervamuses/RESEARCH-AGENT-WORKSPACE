# P3：縮減固定控制，保留必要操作

前置：P2 完成。目標：G9、G10、G11、G12。
結束條件：同視窗與字級下文件／Agent 回應實際可用空間增加，側欄寬度為舊版 70%，原功能仍可操作。

依據：[GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)、[D8](../context/contracts.md)。不引入新 design system、圖示依賴、原生對話框依賴或自動儲存。

## 有界實作

1. P3-S1：刪除 App.tsx 原 document-toolbar 及其下正常 document-notice 整塊 markup 和僅供該區的 layout。建立精簡檔名／dirty／文件選單，重用 open/save/apply/undo handlers；文件 open 不再呼叫 workspace.select。
2. P3-S2：把 Save、Undo last Agent edit 放入文件選單，Ctrl/Cmd+S 保留。將 error/conflict 放在需要處理時的局部區域；儲存中標記簡短，成功無固定大段文字列。
3. P3-S3：sidebar grid 依 D8 改為 minmax(10.15rem,11.9rem)，重排內部控制與 title truncation/完整提示，保留 root font scale、窄視窗 breakpoint，不使用 zoom/transform。
4. P3-S4：搬 Thinking、Permission 到 SlashComposer footer 左側，Send 右側。Thinking 用小圖示及 Normal/Extended 選單；Permission 沿用 Ask/Bypass、當前值與 ACK/disabled guard，只改標題與位置。
5. P3-S5：刪除舊 session-controls、常駐長說明及對應 grid tracks。核對 transcript/composer/session metadata 的實際剩餘列，不能僅把原四列規則照搬。以基線相同條件比較 editor/transcript 高度。
6. P3-S6：執行相關測試與 build；實際鍵盤、縮視窗、長標題、卡片多張、錯誤及 busy 狀態走查。修正直接的 overflow/focus 問題，不做無關風格重整。

## 必要驗收

| 編號 | 操作 | 預期結果 |
|---|---|---|
| A16 | 正常工作區查看文件上方；用專案切換及檔案選單開同 root 的另一份 .md/.tex | 原 Research folder／Source file／Open source／Save／Undo／大段 notice 區完整消失；無常駐路徑輸入；精簡入口可用；開檔前 dirty guard 生效；不偷偷換 project |
| A17 | 編輯後用 Ctrl+S 與文件選單 Save；fake Agent 修改成功後執行 Undo last Agent edit；另測磁碟衝突／保存失敗 | dirty 標記隨真實保存結果更新，沒有自動儲存。Agent Undo 經原 undoOfCallId/版本核對，Ctrl+Z 仍是 editor undo。錯誤與衝突清楚持續可處理，沒有成功假象 |
| A18 | 在相同實際視窗（例如現有 1080×720，再加使用者實際寬視窗）、相同 root 字級／zoom，以同一長標題清單量測新舊 sidebar bounding box | newWidth/oldWidth=0.70，記錄量測值與像素取整差，不以字體縮小達成。長標題不溢出，hover/focus 可看完整內容；最窄支援視窗仍可操作 |
| A19 | 底部點 Thinking 圖示選 Normal/Extended；Permission 選 Ask/Bypass；fake turn 中再嘗試改設定 | 左側同列為兩控制、右側 Send，名稱 Permission 且現值可辨識；鍵盤 focus/menu/ESC 正常。當輪 controlDisabled、後端 busy guard 不變；文件回合既有 effective Normal／偏好恢復不退化 |
| A20 | 同內容、同尺寸的空閒對話，比較改版前後 editor 與 transcript 高度；再開卡片展開／錯誤／approval | 正常狀態 editor/transcript 都得到實際增加的高度；頂部 controls／長說明無空列殘留。卡片與必要提示正常佔用自身空間，Send／輸入框沒有被遮蔽或擠出 |

Linux 實測 Ctrl+S；既有 platform-neutral Mod+S 綁定保留 Cmd 路徑，但不得聲稱執行了 macOS runtime 驗證。本專案不新增 macOS/Windows 支援。

## 檢查

```bash
# cwd: app/desktop，activate app
node --test --experimental-strip-types tests/documents.test.ts tests/trust.test.ts tests/styles.test.ts tests/conversations.test.ts
npm run build
```

只更新對改名／位置／可存取操作有意義的現有斷言。CSS 字串測試與 build 不能取代 A18/A20 的實際尺寸；用可用 GUI 工具或人工測量記錄。若沒有改版前 screenshot/量測，從同 HEAD 的既有執行產物取得；不擅自切分支或修改 worktree 取基線。仍無法取得時，記為未完成基線驗收，不虛構數值。

輸出：compact UI 及保存／復原／權限回歸證據，供 P4 串完整流程。
