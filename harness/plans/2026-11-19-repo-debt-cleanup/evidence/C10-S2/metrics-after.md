# C10-S2 完整驗證與量測（G9）

- **日期**：2026-11-22，程式狀態 `e9436fc`（之後只有本 evidence 與兩個 evidence 檔的行尾空白清理）。

## 四套檢查

| 檢查 | 指令 | 結果 | 耗時 |
|---|---|---|---|
| 完整 pytest（沙箱外） | `cd app && /home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider tests/` | **1827 passed**（2 warnings） | 79 s |
| `npm test` | `cd app/desktop && npm test` | **253 pass**、0 fail | 13 s |
| `npm run build` | `cd app/desktop && npm run build`（`tsc`、`tsc -p tsconfig.test.json`、`vite build`） | 通過 | 8 s |
| `cargo test --locked`（沙箱外，Conda env `app`） | `cd app/desktop/src-tauri && cargo test --locked` | **35 passed** | 9 s |
| `git diff --check` | 本計劃第一個 C 步驟 commit 是 `4f488eb`（`[C1-S1]`）：`git diff --check 4f488eb~1..HEAD` | 第一次執行有 14 行行尾空白，全部在本計劃的兩個 evidence 檔（`C10-S1/doc-grep.md` 的 grep 截斷輸出、`C5-S4/skill-text.md` 的空白行）；清除後以工作樹重跑無輸出，commit 後再以 `HEAD` 確認 | — |

（第一次以 `--grep="[C1-S1]"` 找起點時抓到另一個計劃 2026-11-05 的 `[C1-S1]`，輸出包含其他計劃的舊 evidence；已改用本計劃 build-log 的歷史定位起點。）

基線（C1 時）：pytest 1808、`npm test` 329、cargo 42（記憶與 C1 evidence）；本計劃刪除的功能（knowledge RPC、bundle、catalog、browser preview 等）連同其測試退役，各步驟的退役紀錄在 evidence。

## 量測前後（C1-S3 → C10-S2）

原始輸出：

```
### 1
   461 app/agent/desktop/service.py
   301 app/agent/desktop/bibliography_ops.py
   501 app/agent/desktop/command_ops.py
   486 app/agent/desktop/conversation_ops.py
   317 app/agent/desktop/document_ops.py
   607 app/agent/desktop/extension_ops.py
   121 app/agent/desktop/project_ops.py
   680 app/agent/desktop/turn_ops.py
   325 app/agent/desktop/approvals.py
   258 app/agent/desktop/errors.py
   214 app/agent/desktop/transcript.py
   152 app/agent/desktop/turn_context.py
   429 app/agent/desktop/project.py
   616 app/desktop/src-tauri/src/protocol.rs
  1932 app/desktop/src/App.tsx
  2505 app/desktop/src-tauri/src/backend.rs
  1100 app/desktop/src/protocol.ts
  1519 app/agent/session.py
  1480 app/tests/support/fixture_session.py
   288 app/desktop/src/styles.css
   295 app/desktop/src/styles/conversation.css
   200 app/desktop/src/styles/dialogs.css
   101 app/desktop/src/styles/document.css
   110 app/desktop/src/styles/responsive.css
    90 app/desktop/src/styles/sidebar.css
   205 app/desktop/src/styles/workspace.css
  1020 app/desktop/protocol/v1/contract.json
   844 app/desktop/src/conversations.ts
   695 app/agent/desktop/protocol.py
   591 app/desktop/src/backend.ts
   178 app/desktop/src/api.ts
wc: app/desktop/src/trust.tsx: No such file or directory
  5104 app/desktop/protocol/v1/fixtures.json
 23725 total
### 2
methods: 25
requestEvents: 8
processEvents: 4
errorCodes: 25
messages: 125
traces: 60
### 3
useState 33 34
useRef 33 34
useEffect 11 12
useCallback 46 47
### 4
110
16
### 5
app/agent/desktop/server.py 0 0 1
end
```

| 指標 | C1-S3 | C10-S2 |
|---|---:|---:|
| `app/agent/desktop/service.py` 行數 | 4,643 | 461（handler 分到 11 個模組，合計 3,962 行；C7-S8） |
| `protocol.rs` | 3,638 | 616 |
| `App.tsx` | 3,059 | 1,932 |
| `backend.rs` | 2,497 | 2,505 |
| `protocol.ts` | 2,333 | 1,100 |
| `session.py` | 1,555 | 1,519 |
| `fixture_session.py` | 1,493（`agent/desktop/`） | 1,480（`tests/support/`） |
| `styles.css` | 1,299 | 288（另 6 個區段檔合計 1,001 行，規則順序不變） |
| `contract.json` | 1,261 | 1,020 |
| `catalog.py` → `project.py` | 840 | 429 |
| `conversations.ts` | 800 | 844 |
| `agent/desktop/protocol.py` | 760 | 695 |
| `backend.ts` | 605 | 591（另 `api.ts` 178） |
| `trust.tsx` | 549 | 已拆為 `components/` 下的元件（C9-S2） |
| `fixtures.json` | 5,194 | 5,104 |
| contract 方法／request event／process event／錯誤碼 | 40／20／4／25 | 25／8／4／25 |
| fixtures messages／traces | 127／60 | 125／60 |
| `App()` 本體 `useState`／`useRef`／`useEffect`／`useCallback` | 35／35／14／42 | 33／33／11／46 |
| 整檔 `App.tsx`（含 import 一次） | 43／39／16／43 | 34／34／12／47 |
| 不同 hex 色值／`rgba(...)` 字面值（所有 CSS） | 110／16 | 110／16（不變，R4） |
| `agent/desktop/` 對 `ChatSession` 私有成員：直接存取／`self.session._`／字串形式 | 4／0／6（`service.py`） | 0／0／1（唯一命中是 `server.py` 讀 `DesktopService` 的 `_with_turn_lifecycle`，不是 `ChatSession`） |

## residual grep（C3–C9 彙整）

```
$ grep -rnE "streamKind|chunkCount|ollamaReachable|ollamaModel" agent desktop/src desktop/src-tauri/src desktop/protocol --include=*.py --include=*.ts --include=*.tsx --include=*.rs --include=*.json
(hits: 0)
$ grep -rnE "\"knowledge\.(init_workspace|ingest_file|ingest_folder|prune_apply|status|search|diff|prune_preview|sync|list)\"" desktop/protocol/v1/contract.json | grep -v "\"operation\"\|enum" 
(hits: 0)
$ grep -rnE "bundle_path|reference\.bib|citation_output_dir|CITATION_OUTPUT_DIR|citationOutputPath|pybtex" agent skills desktop/src desktop/src-tauri/src --include=*.py --include=*.ts --include=*.tsx --include=*.rs
agent/extensions/startup.py:36:def _installed_bundle_path(
agent/extensions/startup.py:64:    bundle = _installed_bundle_path(paths, entry)
agent/extensions/startup.py:87:    bundle = _installed_bundle_path(paths, entry)
(hits: 3)
$ grep -rnE "desktop-projects|CATALOG_FILENAME|register_session|retry_registration|registrationStatus|project\.list|_project_list" agent desktop/src desktop/src-tauri/src desktop/protocol --include=*.py --include=*.ts --include=*.tsx --include=*.rs --include=*.json
agent/desktop/project.py:22:LEGACY_CATALOG_FILENAME = "desktop-projects.json"
agent/desktop/project.py:392:            if names - {"conversations", LEGACY_CATALOG_FILENAME}:
(hits: 2)
$ grep -rn "RESEARCH_AGENT_DESKTOP_FIXTURE\|fixture_session" agent
(hits: 0)
$ grep -rn "inspect.signature\|_session_factory_accepts_bash" agent/desktop
(hits: 0)
$ grep -rnE 'session\._[a-z]' agent/desktop agent/thinking | grep -v 'self\._session\b'
(hits: 0)
$ grep -rnE "bypass_approval|_document_turn_active" agent/desktop
(hits: 0)
$ grep -rn "invoke(\|invoke<\|backendClient\.\|\.request(\|as unknown as\|listen<" desktop/src | grep -v "^desktop/src/api.ts\|^desktop/src/backend.ts"
desktop/src/protocol.ts:64:// justified `as unknown as` outside api.ts and backend.ts (checked in evidence/C8-S3).
desktop/src/protocol.ts:65:const CONTRACT = contract as unknown as ProtocolContract;
(hits: 2)
$ grep -rn "browserPreview\|isTauri\|__TAURI" desktop/src desktop/tests
(hits: 0)
$ grep -rn "api\." desktop/src/components
(hits: 0)
$ grep -rlE "readFile" desktop/tests | xargs grep -lE "src/[A-Za-z/]+\.tsx"
(hits: 0)
$ grep -rnE "schemaVersion.{0,3}(1|2)\b|SCHEMA_VERSION_V[12]" agent/conversations
(hits: 0)
```

| 命中 | 判讀 |
|---|---|
| `agent/extensions/startup.py` 的 `_installed_bundle_path` | 擴充安裝包的路徑，與引用 bundle 無關 |
| `project.py` 的 `LEGACY_CATALOG_FILENAME` | C6-S2 規格要求的具名常數（容許殘留檔、永不讀寫）及其使用 |
| `protocol.ts:64–65` 的 `as unknown as` | contract JSON 模組的型別轉換，C8-S3 已註明 |

其餘（協定死詞彙、catalog、fixture 開關、`inspect.signature`、私有存取、回合狀態、`api.ts` 以外的後端呼叫、browser preview、元件內的 `api.`、讀 `.tsx` 原始碼的測試、v1／v2 schema）皆為 0。DTO 一致性（含 `MethodParams`）由 `npm test` 的 `protocol_types.test.ts` 檢查並通過。
