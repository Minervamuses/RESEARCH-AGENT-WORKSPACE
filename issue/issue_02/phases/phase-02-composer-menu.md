# Phase 02 — Composer discovery 與安全選取

## 來源

[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、Phase 01 observed contract；
`app/desktop/src/App.tsx`、`backend.ts`、`conversations.ts`、`styles.css`、
`app/desktop/tests/conversations.test.ts`。

## 目標

使用者在正確 session 的 composer 內，以鍵盤或滑鼠找到命令並填入文字；
選取本身零送出，文字、游標、focus 與後續正常送出行為一致。

## 範圍與非目標

範圍：catalog snapshot 顯示、prefix 篩選、active option、鍵盤／pointer／blur、
游標與必要 ARIA、session/generation catalog 失效。
非目標：新 command policy、arguments parser、fuzzy search、快捷鍵系統、
拆分整個 App、額外 component/test dependency、IME 系統配置。

## 依賴與前置條件

- Phase 01 在 build-log Complete 且具 observed evidence。
- Preflight 檢查真正 DTO、App lifecycle、form submit、workspace operation guards、
  draft/retry 與現有 `shouldSubmitComposerKey` tests。
- **待解：** 原生 WebKit 的 blur／pointer／composition event 次序；
  必須以實際事件觀察驗證。沒有證據時不加 `keyCode 229`、timer 或平台 workaround。
- **待解：** 現有 Node SSR 可測 helpers／markup，不能 dispatch 真 DOM events。
  重用既有測試載入方式與本機 GUI 人工檢查；不因此引入新 harness。
- 使用 PLANS baseline 的既有 `phase02` fixture gate 與 caller-owned tmp root；
  真實 service 搭配 fake session，無需新增 GUI harness。啟動後先由 diagnostics／
  fixture conversation 確認隔離已生效，再操作 composer。啟動命令見 Phase 03。

## 預期受影響元件

Production：`App.tsx`、`styles.css`；優先保留局部 component/helper 在既有檔案。
只有已證明既有 lifecycle 需要直接修正，才改 `backend.ts`／`conversations.ts`。
Tests：現有 `conversations.test.ts`、`backend.test.ts`；
必要 markup/style assertion 留在既有對應檔，不為簡單 CSS 建立大批 tests。

## 實作與驗證

1. **Red：** 在既有 Node test 中用 Python 宣告的自訂 catalog 測 prefix／選取。
   換一個任意合法 Skill 名稱仍會出現，證明不是固定 built-in allowlist。
   最小 cases 區分 `select` 與 `submit`，明確驗證 selection request count 為零。
2. **Catalog ownership：** 使用已驗證 session DTO。缺少／失效 catalog 時不顯示
   可選命令，不從 `loadedSkills` 或舊 session 補清單。
   backend 非 ready、開始 create/select/restart 或 workspace operation 時關閉清單；
   成功且 generation／project／session 對應後才採用新 snapshot。
   舊 response、失敗切換、重啟後相同 session ID 均不能令 stale catalog 可選。
3. **Open/filter：** 在 focused、可互動 composer 的第一個 token 為 slash prefix，
   且游標位於 token 末端／無跨區選取時顯示。對齊 CLI 的 leading whitespace
   tolerance，保持可編輯內容；一般句子內的 slash、參數、多行文本不觸發。
   `/` 列全 catalog；prefix 依 canonical name 不分大小寫篩選。
4. **Active option：** 新 prefix／catalog 從第一個匹配開始；上下鍵只在清單有結果且
   非 composition 時移動，採循環選取並保持 active item 可見。
   空結果可顯示無符合項目但不產生可選 option，不把第一筆舊結果殘留。
5. **Keyboard ordering：** composition guard 最先處理；再處理清單的
   ArrowUp/Down、Escape、未按 Shift 的 Enter；最後才進既有 Enter-to-send。
   Enter 選取必須 preventDefault 並停止後續 submit path。
   Shift+Enter 一律保留換行；Tab 不補全、不送出，沿用 focus traversal。
6. **Insert：** 選取以 `/<name> ` 替換正在編輯的 command prefix；
   保留合法 leading whitespace，不破壞其他草稿／retry state。關閉清單、維持
   textarea focus，React 更新 value 後用 ref 的 selection range 把 cursor 放到尾端。
   不插入假的參數 placeholder，不直接呼叫 sendTurn。
7. **Close：** Escape 保留文字並抑制同一 prefix 在下一個 render 重開；
   後續真正編輯可重新搜尋。blur、清空、加入參數空白／換行或非 slash prefix 關閉。
   清單關閉後別攔截一般箭頭鍵。零 matches 時不自動補或自動發 request，
   明確送出仍交既有 parser 最終處理。
8. **Mouse/accessibility：** pointer 選取使用與 Enter 相同 action，處理 blur-before-click；
   click 後焦點回 composer，不因 focus 離開丟失選取或重送。
   使用具可存取名稱的 listbox/options、有效的 active-descendant 對應與 selected state；
   依有效 HTML/ARIA 關係連結 textarea，不把不支援的 role 強貼到多行輸入框。
   選項由 React text rendering 顯示，description 不當作 HTML。
9. **Refactor：** 僅必要的 event decision／prefix helpers 方便既有 tests；
   不新增獨立 registry 或 reusable command framework。

### Planned verification commands

Linux Conda `app`，於 `/home/minervamuses/research-agent-workspace/app/desktop`：

```bash
node --test --experimental-strip-types tests/conversations.test.ts tests/backend.test.ts tests/trust.test.ts
npm run build
```

開發先跑新增 test cases；上述 scoped regression 保護 retry、conversation、
generation 與 Bash/Extension UI。Phase 01 contract 未再變更就不重跑全部三語言 checks。

**Required UI procedure：** 用已確認的隔離本機 UI 依序輸入 `/`、`/sta`、
上下鍵、Enter、`/ingest ` 後補文字但不執行 ingestion、Escape、blur、mouse click、
Shift+Enter，觀察 text/cursor/focus 及零送出。若 runtime 未提供 GUI 操作工具，
由可操作 Linux Desktop 的使用者／代理提供此證據；不可用 helper tests 代替。

## 驗收

- [ ] 前端可展示任意合法 backend catalog entry，沒有 allowlist 或 eligibility 複製。
- [ ] 上下鍵、篩選與 active option 正確；Enter 只插字串、尾端 cursor、零送出。
- [ ] Escape／blur／清空／參數／非 prefix 按規則關閉，pointer 不被 blur 吞掉。
- [ ] IME composition、Shift+Enter、一般 Enter、retry／draft 與 approvals 回歸通過。
- [ ] create/select/restart、generation mismatch、缺失 catalog 不會露出舊清單。
- [ ] markup 檢查與實際 keyboard/mouse UI 檢查皆有證據；SSR 不冒充原生 IME。
- [ ] required checks 與 build 通過；不通過不進 Phase 03。

## 證據、恢復與交接

在 `../build-log.md` 寫入 command/result、UI 操作、零 request evidence 來源，
以及焦點／cursor 實際觀察。事件順序新發現才寫 `../context/phase-02-context.md`。
失敗保留草稿並修正本 phase；不清除使用者 store 或停用最終 parser。
Phase 03 接收已完成互動和失效邏輯，僅補跨層整合與 broader acceptance，
不能替本 phase 補上本應先通過的 checks。
