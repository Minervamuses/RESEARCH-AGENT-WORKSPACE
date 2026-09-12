# Issue 02 — Desktop Slash Command Menu：目標

## 目的與背景

依 [Issue 02](../02-desktop-slash-command-menu.md)，讓 Desktop 使用者在 composer
輸入 `/` 後直接探索並以鍵盤選取目前 session 可執行的命令，不必記住命令名稱。
CLI 已有 registry-based completion；Desktop 已有 Python dispatch，但沒有把可用
命令與互動清單交給 GUI。顯示清單不代表新增任何 command 的執行能力。

## 預期成果

- Python 宣告目前 session 的 Desktop command catalog；React 顯示 canonical
  command 名稱與描述、做 prefix 篩選及選取。
- 選取只補入文字；使用者確認內容、補完參數後才另外送出。
- 清單與目前 conversation／backend generation 對齊，不借用上一個 session 的命令。

## 成功條件

- [ ] 空 composer 輸入 `/` 立即列出 Python snapshot 宣告的命令；
      `/sta` 只留下匹配項目，例如目前的 `/status`。
- [ ] session 中已驗證且可 dispatch 的 one-shot Skill commands 出現；
      未知、重複、registry 拒絕的保留名稱、built-in／alias collision 與 CLI-only 項目不出現；
      保留既有合法 `_prompt-master` 例外。
- [ ] 鍵盤可開啟清單、以上下鍵移動、Enter 選取、Escape 關閉；選取後焦點留在
      composer，文字為 `/<canonical-name> `，游標在尾端，尚未送出任何 request。
- [ ] 使用者可繼續輸入參數；清單關閉後另按 Enter 才依既有 send path 送出。
      Shift+Enter 保留換行，IME composition 的 Enter 不選取、不送出。
- [ ] Escape 保留草稿且不在同一文字下立即重開；失焦、清空、進入參數或非 slash
      prefix 時關閉。滑鼠選取、focus 與 screen-reader semantics 不破壞鍵盤流程。
- [ ] A→B→A、backend restart 與生效後的 Skill catalog 更新都採用新的 session
      snapshot；舊 generation、切換中的 response 或尚未驗證的 catalog 不會顯示。
- [ ] command 送出後仍由 Python parser、Desktop eligibility 及既有 handler 驗證。
      手動輸入未知或被排除命令仍被拒絕；menu 不可作為 authorization。
- [ ] 實際 Linux Desktop 的代表性 keyboard／mouse journey 與必要的離線回歸檢查
      有可觀察證據；無法取得的 IME／輔助工具證據明確保留，不當作通過。

## 範圍

- 現有 session registry 到 Desktop catalog 的 projection。
- session snapshot 的 JSON／TypeScript／Rust contract 與對應 fixtures。
- composer prefix 清單、鍵盤優先順序、插入游標、滑鼠與可存取性。
- session／generation 邊界與現有 extension restart lifecycle 的清單替換。
- 直接相關的離線測試與代表性 UI 驗收。

## 非目標

- Issue 08 的 Citation lifecycle、Issue 09 的 Thinking 控制。
- Issue 01 的 WSLg／Linux 輸入法安裝或配置；本項只保護 composer 的組字事件。
- Issue 06 的啟動後 Skill 完整性、Issue 07 的跨 process apply 競態。
- 新增 slash commands、alias dispatch、模糊搜尋、參數補全、command palette framework。
- 重寫 CLI completion、修改 `/help` 的既有全文清單、重構整個 App 或一般 UI 改版。
- Skill hot reload、檔案 watcher、polling、額外 catalog service 或持久化 cache。
- dependency、lockfile、Conda environment、持久資料格式／儲存 schema、Git 狀態變更；
  本 issue 直接需要的 session catalog protocol 欄位屬於 scope。

## 保留行為與限制

- **命令權責：** 同一 session 的 `SlashCommandRegistry` 決定 command 與 collision；
  Python Desktop dispatch 決定可用性。React 不持有 command allowlist，不解析
  shell arguments，不自行決定 Skill 是否可信。來源：Issue 02、現有 service/parser。
- **Canonical 名稱：** 目前 Desktop 拒絕 alias，GUI 只列 canonical name。
  大小寫 prefix matching 對齊 registry 已接受的命名；不擴張 alias 行為。
- **Skill 生效：** apply 後目前 session 仍使用既有 loaded catalog；
  session 重新 materialize／restart 後依新 snapshot 顯示。來源：
  `session.py`、`extensions/startup.py`、`desktop/service.py`、Issue 06。
- **既有互動：** 保留一般文字 Enter-to-send、Shift+Enter、草稿／retry、
  transcript、Bash ask/bypass、Extension/MCP approval 與 backend operation guards。
- **平台與成本：** `AGENTS.md` 規定 Linux、Conda `app`、Poetry 與 LF；
  Windows 只透過 WSL 操作。使用既有 pytest／Node／Rust 工具與 fake session，
  不用 live provider 或使用者 store 驗證本功能。
- **授權：** 本次僅 authoring。之後修改 protocol 或超過三個 production files
  需使用者明確啟動 [PLANS.md](PLANS.md) 的具體範圍；計劃文件本身不是實作授權。

## 未知與待決事項

目前沒有需要先由使用者決定才可完成 authoring 的產品問題。以下技術／環境未知
留給相應 phase，以 live evidence 解決：

- Phase 01：catalog 的字串／筆數上限如何在現有 protocol 2 MiB envelope 內
  保持完整且可驗證；不能截短 canonical name 或靜默漏掉合法命令。
- Phase 02：原生 WebKitGTK 的 composition／blur／pointer 事件順序；
  以真實 UI 觀察選取是否誤送，不預先加入時間延遲或平台特例。
- Phase 03：可用 Linux IME 與 screen reader 尚未在本輪確認。Issue 01 記錄過
  主機無可用 Linux IME；不能把該歷史觀察當作今日狀態，也不能用純函式測試
  聲稱原生組字通過。無法驗證時保留限制，若影響必要成功條件則停下取得使用者決定。

## 來源

- [AGENTS.md](../../AGENTS.md) 與本次使用者提供的 Personal Engineering Defaults。
- [Issue 02](../02-desktop-slash-command-menu.md)；
  [Issue 01](../01-desktop-wslg-chinese-ime-input.md)；
  [Issue 06](../06-extension-skill-post-startup-integrity.md)；
  [Issue 08](../08-citation-skill-flow-deferred.md)。
- `app/agent/cli/slash_commands.py`、`app/agent/cli/prompting.py`、
  `app/agent/desktop/service.py`、`app/agent/session.py`。
- `app/desktop/protocol/v1/contract.json`、`app/desktop/src/protocol.ts`、
  `app/desktop/src-tauri/src/protocol.rs`、`app/desktop/src/App.tsx`。
