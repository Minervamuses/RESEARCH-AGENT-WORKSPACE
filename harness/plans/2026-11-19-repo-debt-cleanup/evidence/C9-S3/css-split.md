# C9-S3 CSS 分檔與 class 改名（S096、P12）

基準：C9-S2 之後的 HEAD `3760f23`。腳本：`normalize-css.sh`（`vite build --outDir <tmp>` 後把 CSS 去註解、去空白差異、一條規則一行；at-rule 容器拆成開頭、內部規則、結尾）。

## 一、分檔（原檔連續區段，原順序）

| 檔案 | 原行數範圍 | 主要畫面區塊 |
|---|---|---|
| `src/styles.css` | 1–288 | 全域基礎（第一個 `:root` 含 `font-size: clamp(…)`）、app shell、sidebar 外框、狀態點、按鈕列 |
| `src/styles/workspace.css` | 290–494 | main workspace、empty state、notice、runtime details、spinner、session meta |
| `src/styles/sidebar.css` | 496–585 | 專案群組、對話清單 |
| `src/styles/conversation.css` | 587–881 | transcript、訊息卡片、composer、slash list、history notice |
| `src/styles/dialogs.css` | 883–1081 | 擴充卡片、approval、錯誤文字、modal |
| `src/styles/responsive.css` | 1083–1192 | 三個 `@media (max-width…)` 區塊（原本就連續，未整併） |
| `src/styles/document.css` | 1194–1294 | 文件 pane、annotation、citation panel、後段 media query |

`src/main.tsx` 在 `import "./styles.css"` 之後依序 import 其餘 6 檔，沒有 CSS `@import`，元件不 import 樣式。把 7 檔依序串接與原檔比對：只差區段間的空白行與下方的改名一行。`tests/styles.test.ts` 未修改並通過。

## 二、class 改名

`extension-error` 在 `ExtensionPanel.tsx`（擴充流程錯誤，真的是擴充用途）仍使用；`ConversationDialogs.tsx`（3 處）與 `ProjectChooser.tsx`（1 處）是借用（刪除／改名／選專案對話的錯誤）。所以：借用處的 `className` 改為 `dialog-error`，並在同一條規則的選擇器清單加上 `.dialog-error`（`.extension-error, .dialog-error, .error-text { color: … }`），宣告與值未動；`.extension-error` 保留給擴充面板。

## 三、打包後 CSS 比對（`css-before.txt` vs `css-after.txt`，共 1061 行）

完整 diff（只有這一行）：

```
936c936
< .extension-error,.error-text{color:#843c38!important}
---
> .extension-error,.dialog-error,.error-text{color:#843c38!important}
```

規則內容與順序其餘完全相同。

## 四、色值集合

`grep -rnoE "#[0-9a-fA-F]{3,8}\b" src --include=*.css` 的不同色值（小寫去重）：前 110 個、後 110 個，`diff colors-before.txt colors-after.txt` 為空：**相同**。另依 build-log 的備註檢查 `rgb()/rgba()` 字面值：前 16、後 16，`diff` 為空：**相同**。

## 五、檢查

`npm test`：256 pass、0 fail；`npm run build`：通過。
