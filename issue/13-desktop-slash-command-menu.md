# Desktop Composer 缺少 Slash Command 鍵盤清單

## Issue 定位

- 類型：Desktop composer discovery／keyboard interaction。
- 優先度：高。
- 狀態：Open。
- 關聯：這是通用 GUI command-discovery 基礎；Citation 是否能在 Desktop 執行仍由 [`09-citation-skill-flow-deferred.md`](09-citation-skill-flow-deferred.md) 另行決定。

## 使用者需求

使用者在 GUI composer 按下 `/` 時應立即看到 slash-command list，並可用鍵盤上／下鍵直接選擇。CLI 已有這個操作，GUI 目前沒有成功繼承。

## 已確認的現況

- CLI 的 `SlashCommandCompleter` 直接讀取 `SlashCommandRegistry`，在輸入 `/` 或 command prefix 時提供 matching commands；`prompt_toolkit` 負責 completion menu 與鍵盤選擇。
- Desktop backend 會從同一套 Python registry 解析已送出的 slash command，再套用 Desktop eligibility 規則；完整 registry 中仍有 Citation、Thinking、Clear、Quit 等目前不能從 Desktop composer dispatch 的項目。`session.create`／`session.select` 尚未把這份 Desktop-filtered command catalog 提供給 GUI。
- React composer 目前只有 textarea 與 Enter-to-send handler；沒有 command list、active option 或 ArrowUp／ArrowDown navigation。
- 因此 Desktop 使用者必須事先知道完整 command 名稱；GUI 能執行部分已輸入的 command，不等於具備 CLI 的 discovery／selection UX。

## 期望行為

- Composer 為空或正在輸入 command prefix 時，按下 `/` 立即顯示目前 session 真正可用的 command list。
- 繼續輸入字元時依 prefix 過濾；清單必須包含該 session 通過驗證的 dynamic Skill commands，並遵守 built-in／alias collision 規則。
- ArrowDown／ArrowUp 在清單中移動 active option；Enter 選取該 command。
- 選取只填入 composer，並把游標留在需要輸入參數的位置；不得意外直接送出尚未完成的 command。
- Escape 關閉清單並保留可編輯文字；composer 失焦、清空或不再是 slash prefix 時清單關閉。
- GUI 不維護一份手寫 command allowlist；Python 應以同一個 session 的 `SlashCommandRegistry` 與 Desktop dispatch 規則產生可執行 projection，GUI 只顯示這份 Desktop-filtered catalog。

## 與 Citation 的執行順序

1. 先完成一般 built-in 與 one-shot Skill commands 的 catalog／menu。
2. [`09-citation-skill-flow-deferred.md`](09-citation-skill-flow-deferred.md) 先決定 Citation 的 one-shot／multi-turn lifecycle、cleanup 與 thinking 契約。
3. 只有 backend 宣告 Citation 可供該 Desktop session 使用時，menu 才能列出它。把 `/citation` 字樣放進清單本身不算完成 Citation 支援。

## 驗收條件

- 輸入 `/` 可看到 Python 宣告為該 Desktop session 可 dispatch 的命令；未知、衝突、CLI-only 或不可用命令不出現。
- 只用鍵盤即可完成開啟、上下移動、選取與關閉。
- IME composing 與 Enter-to-send 不會造成誤送；選取需要參數的命令後可繼續輸入。
- 送出時仍由 Python parser 做最終驗證，React 不自行實作 command policy。
- Conversation switch、backend restart 與 Skill catalog 更新後，清單不沿用舊 session catalog。
- Focus、screen-reader semantics 與 mouse selection 不得破壞鍵盤主流程。

## 非目標

- 不藉通用 menu 猜定 Citation lifecycle。
- 不在 React 複製 static／dynamic command registry 或 Desktop eligibility 規則。
- 本 issue 只記錄需求，本輪不修改 GUI 或 protocol。

## 主要參考檔案

- `app/agent/cli/prompting.py`
- `app/agent/cli/slash_commands.py`
- `app/agent/desktop/service.py`
- `app/desktop/protocol/v1/contract.json`
- `app/desktop/src/protocol.ts`
- `app/desktop/src/App.tsx`
- `app/tests/test_slash_commands.py`
- `app/tests/test_desktop_service.py`
- `app/tests/test_desktop_protocol_contract.py`
- `app/desktop/tests/`
