# C9-S5 階段收尾與 C9 驗收

基準：C9-S4 之後的 HEAD `65e9cab`。

## 一、檢查

- `npm test`：**253 pass、0 fail**（C9 起點 247＋S1 7＋S2 2＋S4 的 +1 縮放測試 −4 合併）。
- `npm run build`（`tsc --noEmit`、`tsc --noEmit -p tsconfig.test.json`、`vite build`）：通過。

## 二、行數

| 檔案 | 行數 |
|---|---|
| `src/styles.css` | 288 |
| `src/styles/workspace.css` | 205 |
| `src/styles/sidebar.css` | 90 |
| `src/styles/conversation.css` | 295 |
| `src/styles/dialogs.css` | 200 |
| `src/styles/responsive.css` | 110 |
| `src/styles/document.css` | 101 |
| 樣式合計 | 1,289（原 `styles.css` 1,294；差額是區段間的空白行） |
| `App.tsx` | 1,932（C8-S7：2,462；C1 前：3,000） |
| `components/`：`Annotation` 41、`ApprovalDialog` 98、`Composer` 177、`ComposerControls` 62、`ConversationDialogs` 79、`DocumentPane` 90、`ExtensionPanel` 102、`Modal` 61、`ProjectChooser` 63、`RuntimeDetails` 27、`Sidebar` 92、`StatusNotices` 106、`Transcript` 134、`messageParts` 90、`phaseLabels` 11 | 1,233 |

## 三、共用與保留的互動語意複核

- 共用原語仍在使用：`dialogKeyDecision`（`Modal.tsx`）、`menuShouldClose`／`menuNextIndex`／`focusLeftContainer`（`ConversationDialogs.tsx`、`DocumentPane.tsx`、`useDisclosureMenu`）、`useDisclosureMenu`（`ComposerControls.tsx` 的 `ThinkingControl`、`CitationPanel.tsx` 的 `ExportMenu`）。
- 保留的差異（`evidence/C9-S1/primitives.md` 第三節）以 `ModalDialog` 的 props 或呼叫端表達；C9-S3、S4 沒有動 `Modal.tsx`、`interaction.ts` 與 `useDisclosureMenu.ts`，`tests/interaction.test.ts` 7 個測試通過。
- U22 三種 Transcript 渲染的靜態渲染測試都在 `tests/conversations.test.ts`：live（「a live turn renders its own cards…」）、pending（「a pending turn renders the prompt…」）、restored（「restored turns keep tool details lazy…」、「restored transcript renders durable non-completed…」及另一個 restored 測試；原多 MB 答案測試併入 S4 的合併測試，仍呼叫 `RestoredTurn`）。
- `grep -rn "api\." src/components` → 0；`src/*.tsx`、`src/components/*.tsx` 沒有超過 600 字元的行。

## 四、C9 驗收（對照 phase-09「完成後的狀態」）

| 完成後的狀態 | 結果 | 證據 |
|---|---|---|
| 主要畫面區塊有清楚的元件邊界；`App()` 主要負責 hooks、跨 domain 協調與 JSX 組裝；transcript 三種入口按語意保留 | 通過：元件 15 個、`App.tsx` 2,462 → 1,932；三入口＋`ConversationTurns` 分派器保留；三種靜態渲染測試存在 | `evidence/C9-S2/components.md`、本檔第三節 |
| dialog／menu 只共用相容的互動原語，不強制不同語意使用同一元件 | 通過：4 個純函式＋`ModalDialog`＋`useDisclosureMenu`，差異留在呼叫端 | `evidence/C9-S1/primitives.md` |
| CSS 切成依原順序排列的區段檔，打包規則順序不變；被借用的 class 依角色命名；顏色值不變 | 通過：7 個連續區段；打包後 CSS diff 只有 `.dialog-error` 一行；`#hex` 與 `rgb()/rgba()` 集合相同；`styles.test.ts` 未改且通過 | `evidence/C9-S3/css-split.md` |
| grep 原始碼與釘住 class name 的測試已改為行為斷言 | 通過：讀 `.tsx` 的測試 0；測試不再斷言 presentation class；`styles.test.ts` 讀 CSS 保留（S084） | `evidence/C9-S4/tests.md` |
| 步驟必要檢查（每個 commit 的 `npm test`、`npm run build`） | 通過：C9-S3、S4、S5 最終皆 253 pass、build 通過 | 本檔第一節 |

## 五、GUI 清單指標（均需人工；本計劃沒有看到畫面）

- `evidence/C9-S1/primitives.md` 第七節：5 個 dialog 的 Tab／Shift+Tab／Esc／焦點還原，以及 4 個選單的 Esc／點外部／鍵盤操作。
- `evidence/C9-S2/components.md` 第六節：Sidebar、DocumentPane、Transcript、Composer、ProjectChooser、通知、核准框與 `ThinkingControl`／`PermissionControl`。
- C9-S3：全畫面外觀不變（CSS 規則順序與內容相同，但仍請目視檢查）；刪除／改名／選專案對話的錯誤文字仍是紅色（`.dialog-error`），擴充面板錯誤仍是紅色（`.extension-error`）。
- C9-S4：編輯器 Ctrl/Cmd 加 `=`／`+`／`-`／`0` 縮放與 line height 不重疊（`DocumentEditor.tsx` 改呼叫 `editorFontOptions`／`zoomKeybindings`）。
