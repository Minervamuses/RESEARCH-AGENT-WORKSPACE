# C8-S2 純邏輯模組化（S083）

狀態：變更留在工作樹，未 commit（依指示由使用者審查後提交）。

## 1. 改動前分類（改動前先列；行號為改動前的 `tests/*.test.ts`，與 C8-S1 §6.3 對照一致）

「純函式」＝只呼叫純函式；「元件渲染」＝`renderToStaticMarkup`（含只呼叫元件、不產 markup 的 SafeContent 大陣列測試）。

| 檔案（test 總數） | test（行號） | 分類 | 改動前載入 |
|---|---|---|---|
| `trust.test.ts`（13） | 114、128、137、177 extension flow；205 `acceptApprovalEvent`；289 `reconcilePermissionAck`；382 `approvalHasLiveOwner` | 純函式（7） | `trust.tsx` |
| | 233、261、330、349、363 ApprovalDialog / PermissionControl / ExtensionPanel | 元件渲染（5） | `trust.tsx` |
| | 395 讀 `App.tsx` 原始碼比對清除程式 | 原始碼比對（1；C8-S5 才改寫，本步未動） | 無 SSR |
| `conversations.test.ts`（33） | 176、195、234、381、433、453、462、493、713、755、779、801、820、912 | 純函式（14） | `App.tsx` |
| | 269 `safeExternalUrl` | 純函式（1） | `SafeContent.tsx` |
| | 411、417、423、868 | 純函式（4） | 無 SSR |
| | 149、254、516、559、595、626、651、852 | 元件渲染（8） | `App.tsx` |
| | 286、298、314、326、343、359 | 元件渲染（6） | `SafeContent.tsx` |
| `documents.test.ts`（8） | 35、49、63 | 純函式（3） | `DocumentEditor.tsx` |
| | 80、91、100、139 | 純函式（4） | `App.tsx` |
| | 111 `handleAnnotationKey` + `AnnotationComment` | 元件渲染（混合，1） | `DocumentEditor.tsx` |
| `inline_skills.test.ts`（4） | 21、36、47、56 | 純函式（4） | `App.tsx` |
| `citation_preview.test.ts`（8） | 33、42、51、89 | 純函式（4） | 無 SSR |
| | 69、107、130、144 | 元件渲染（4） | `CitationPanel.tsx`、`CitationText.tsx` |

元件渲染測試共 24（trust 5、conversations 14、documents 1、citation_preview 4）；純函式卻經 SSR 載入的 33 個（trust 7、conversations 15、documents 7、inline_skills 4）→ 改成直接 import。

## 2. 新模組（`app/desktop/src/lib/`，函式本體原樣搬移，只加 `export`）

| 模組 | 內容 | 來源 |
|---|---|---|
| `composer.ts` | `shouldSubmitComposerKey`、`handleComposerKey`、`handleAnnotationKey`（INV-022，只搬移）、`composerSlashCommands`、`slashPrefix`、`filterSlashCommands`、`insertSlashCommand`、`inlineSkillToken`、`insertInlineSkill`、`inlineSkillReferences`、`checkSubmissionSize`、`retrySettingsMatch`；型別 `SlashCommands`、`SlashCatalogOwner`、`InlineSkillReference` | `App.tsx`、`DocumentEditor.tsx` |
| `sidebar.ts` | `sidebarRowsForProject`、`loadSelectedProjectHistory`、`projectDisplayName`、`mergeSessionItems`、`SidebarSessionRow` | `App.tsx` |
| `transcript.ts` | `TRANSCRIPT_PAGE_SIZE`、`TranscriptView`、`mergeTranscriptItems`、`failureLifecycleLabel`、`isPersistedTurnFailure`、`transcriptTailOffset`、`fetchTranscriptPage`、`selectConversationWithPreview`、`transcriptViewFrom`、`visibleMessageRange` | `App.tsx` |
| `documents.ts` | `documentReference`、`backgroundDocumentContext`、`documentContextPayload`、`reconcileSavedDocument`、`submittedDocumentSource`、`documentOperationContext`、`advanceWorkingDocumentSources`、`DocumentAction`、`WorkingDocumentSources` | `App.tsx` |
| `documentSource.ts` | `DocumentSnapshot`、`SourceChange`、`documentOffsetAt`、`documentPositionAt`、`applyDocumentChanges`、`captureDocumentSelection` | `DocumentEditor.tsx` |
| `errors.ts` | `protocolMismatch`、`workspaceError` | `App.tsx` |
| `extensionFlow.ts` | extension flow 型別與全部 `*Extension*` 轉移函式 | `trust.tsx` |
| `approval.ts` | `PendingApproval`、`acceptApprovalEvent`、`ApprovalOwnerRequests`、`approvalHasLiveOwner`、`reconcilePermissionAck` | `trust.tsx` |
| `safeUrl.ts` | `ExternalUrlOpener`、`safeExternalUrl`、`openSafeExternalUrl`（INV-017，只搬移） | `SafeContent.tsx` |

`App.tsx`、`trust.tsx`、`DocumentEditor.tsx`、`SafeContent.tsx`、`CitationText.tsx`、`CitationPanel.tsx` 改為直接 import 這些 `.ts`；沒有保留 re-export（`DocumentSnapshot` 的 import 一併改到 `lib/documentSource.ts`）。`App.tsx` 3000 → 2588 行、`trust.tsx` 547 → 300 行。

`backendClient.request` 預設參數：`loadSelectedProjectHistory`、`selectConversationWithPreview`、`fetchTranscriptPage` 的預設值移除，`request` 為明確參數（`fetchTranscriptPage` 的 `request` 排在有預設值的 `mismatchMessage` 之後，成為必要參數）。`App.tsx` 所有呼叫點傳入 `backendClient.request`（共 6 處：history 1、select 1、`fetchTranscriptPage` 4），行為不變。

## 3. 測試 import 改動

- `inline_skills.test.ts`：整檔改為 `import * as h from "../src/lib/composer.ts"`；移除 Vite server，測試變同步。
- `trust.test.ts`：純函式測試直接 import `lib/extensionFlow.ts`、`lib/approval.ts`（7 個改同步）；5 個渲染測試仍用 Vite SSR 載入 `trust.tsx`，型別改為 `typeof import("../src/trust.tsx")`，移除手寫 `TrustModule`/`ApprovalOwners`。移除 `assert.ok(reconcilePermissionAck, "…must be exported")`（直接 import 後恆真，並非測試退役）。
- `conversations.test.ts`：純函式測試（含 `safeExternalUrl`）直接 import `lib/*.ts`；渲染測試保留 SSR，型別改為 `typeof import("../src/App.tsx")`、`typeof import("../src/SafeContent.tsx")`；移除手寫 `AppHelpersModule`、`SessionSummary` 等。
- `documents.test.ts`：純函式直接 import `lib/documents.ts`、`lib/documentSource.ts`；`annotation Enter` 測試（含 `AnnotationComment` 渲染）保留 SSR 載入 `DocumentEditor.tsx`，型別 `typeof import(...)`。
- `citation_preview.test.ts`：型別改 `typeof import("../src/CitationPanel.tsx")`/`CitationText.tsx`，並移除 `createElement(X as never, …)` 的 `as never`，讓 props 被 tsc 檢查。
- `backend.test.ts`、`citations.test.ts`：僅為通過型別檢查的修正（見 §4）。

## 4. tsc 檢查 `tests/`

做法：新增 `tsconfig.test.json`（`extends ./tsconfig.json`，`include: ["src","tests"]`，`lib` 加 `ES2024.Promise`），`package.json` 的 `build` 改為 `tsc --noEmit && tsc --noEmit -p tsconfig.test.json && vite build`。`tsconfig.json` 本身不動。不直接把 `tests` 加進 `tsconfig.json` 的理由：(1) 測試用 `Promise.withResolvers`，需要 ES2024 lib，不該放寬 `src` 的 lib（Tauri webview 不一定支援）；(2) 與 strip-types 無衝突，`npm test` 指令不變。

`@types/node` 未安裝，且不可新增依賴，所以新增 `tests/node-shim.d.ts`：只宣告測試實際用到的 `node:assert/strict`（沿用 @types/node 的 `asserts` 簽章，斷言仍會收斂型別）、`node:test`、`node:fs`、`node:fs/promises`、`node:path`、`node:url`、`setImmediate`、`ImportMeta.url`。

tsc 浮出的型別錯誤與處理（沒有放寬任何斷言）：

| 檔案 | 問題 | 處理 |
|---|---|---|
| `backend.test.ts` | `SessionCreatedDto` fixture 缺必填的 `permissionMode` | 補 `permissionMode: "ask"`（全部測試仍通過） |
| `citations.test.ts` | `selectUse` 的 snapshot 沒宣告 range 欄位 | 為變數加上含 optional range 欄位的型別 |
| `documents.test.ts` | `kind`/`status` 為 `string`；`working` 可能為 `null` | `as const`、`WorkingDocumentSources` 型別、`advance()` 包裝（內含 `assert.ok(next !== null)`）、`!` |
| `citation_preview.test.ts` | `new Promise(...)` 型別 | `new Promise<JsonObject>(...)` |
| `trust.test.ts` | `flow` 被函式回傳 `null` 的型別 | 對 `interruptExtensionFlow`/`observeExtensionRevision` 加 `!`（執行期原本就非 null） |
| `conversations.test.ts` | `opened.push` 回傳 `number` 不符 `void` | `(url) => { opened.push(url); }` |

## 5. 指令與結果

環境：`PATH=/home/minervamuses/miniconda3/envs/app/bin:$PATH npm_config_cache=$TMPDIR/npm-cache`（在 `app/desktop`）。

| 指令 | 改動前 | 改動後 |
|---|---|---|
| `npm test` | 224 pass（基準） | **224 pass、0 fail** |
| `npm run build` | 通過（未檢查 tests） | **exit 0**（含 `tsc -p tsconfig.test.json`） |
| 測試數：trust / conversations / documents / inline_skills / citation_preview | 13 / 33 / 8 / 4 / 8 | 13 / 33 / 8 / 4 / 8（無刪除） |
| 經 Vite SSR 載入 `.tsx` 的元件渲染測試 | 24 | 24 |

### 故意型別錯誤證明

在 `tests/inline_skills.test.ts` 末尾加 `const deliberateTypeError: number = "not a number";`，執行 `npm run build`：

```
> research-agent-desktop@0.1.0 build
> tsc --noEmit && tsc --noEmit -p tsconfig.test.json && vite build

tests/inline_skills.test.ts(44,7): error TS2322: Type 'string' is not assignable to type 'number'.
tests/inline_skills.test.ts(44,7): error TS6133: 'deliberateTypeError' is declared but its value is never read.
EXIT 2
```

還原後 `npm run build` 再次 exit 0（`✓ built`）。

### `grep -ln "ssrLoadModule\|createServer" tests/`

```
tests/citation_preview.test.ts   元件渲染 4（ExportMenu、CitedRow/UncitedRow、CitationPanel、CitationText）；其餘 4 個純函式測試不經 SSR
tests/conversations.test.ts      元件渲染 14（App.tsx 8、SafeContent.tsx 6）；其餘 19 個純函式測試不經 SSR
tests/trust.test.ts              元件渲染 5（ApprovalDialog、PermissionControl、ExtensionPanel）；其餘為純函式與 1 個原始碼比對
tests/documents.test.ts          元件渲染 1（AnnotationComment，混合測試）；其餘 7 個純函式測試不經 SSR
```

`inline_skills.test.ts` 已不在清單內。`protocol.test.ts` 本來就不用 Vite SSR（grep 無命中，沿用 C3 的非 SSR 作法），不需註明例外。

## 6. 判斷與未做事項

- 被刪的測試：無。
- `trust.test.ts` 的原始碼比對測試（原 395 行）依計劃留給 C8-S5；它比對的 `App.tsx` 段落（`approvalHasLiveOwner(…)` 呼叫、`citationRequestRef`）本步未動，仍通過。
- `shutdownSummary`、`newLogicalTurnId`、`phaseLabels`、`isTauriRuntime` 不是測試匯出、也不被已搬函式依賴，留在 `App.tsx`（`isTauriRuntime` 由 C8-S4 處理）。
- `modelSource`（`DocumentEditor.tsx`）是元件內部 helper，未搬。
- 渲染元件（`DeleteConversationDialog`、`SlashCommandList`、`ComposerFooter`、`RestoredTurn`、`ConversationTurns`、`ReferenceCards`、`DocumentHeader`）仍從 `App.tsx` 匯出，留給 C9 拆元件時處理。
- `lib/transcript.ts` 的 `visibleMessageRange` 使用 DOM `Node` 型別（無 JSX、可在 node 下以假節點測試），因此放在 `.ts`。
- 未做：`api.ts`（C8-S3）、刪除 browser preview（C8-S4）、reducer／approval 擁有者（C8-S5）、拆 `App()`（C8-S6）。
