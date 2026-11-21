# Repo 債務清理：路線與執行契約

- **計劃根目錄**：`harness/plans/2026-11-19-repo-debt-cleanup/`（相對於 repo 根目錄 `/home/minervamuses/research-agent-workspace`）
- **目標、決策與範圍**：[GOALS.md](GOALS.md)
- **目前狀態與證據**：[build-log.md](build-log.md)（唯一的狀態來源）
- **啟動入口**：[PROMPTS.md](PROMPTS.md)
- **稽核原文**（S-ID 的定義、位置與證據）：[context/repo-debt-audit-2026-11-19.md](context/repo-debt-audit-2026-11-19.md)
- **citation 決策紀錄**（C5 的驗收依據）：[note/20261119/citation_storage_unification_decision.md](../../../note/20261119/citation_storage_unification_decision.md)

## 任務規模與風險

範圍橫跨 Python 桌面後端、agent 核心、citation skill、React 前端、Rust 宿主與三語言的協定測試。大部分是刪除與搬移。新增的程式只有：

- C2 的錯誤出口遮蔽；
- C3 的 DTO 一致性檢查；
- C5 的存檔語意與搬移的驗證檢查；
- C7 的每回合選項、重複忙碌判斷的少量共用 helper（U21）與 `ChatSession` 公開介面；
- C8、C9 抽出的純邏輯模組、hooks、元件與 `api.ts`。

風險集中在四處：

1. **C3 協定收斂**：同時改 TS、Rust、Python 三端與共用 fixtures。拿掉 TS 的逐欄位驗證後，型別漂移改由 U16 的檢查守住。
2. **C5 citation**：存檔語意改變（U13、U20），牽動驗證保證、模型看到的 `SKILL.md`、存檔計數，以及論文實驗的可比性。
3. **C7 後端接縫**：`service.py` 4,643 行；每回合選項、忙碌判斷與 Stop 恢復都碰到回合生命週期。
4. **C8、C9 拆解 `App()`**：`App()` 沒有整合測試；前端沒有互動式 DOM 測試工具，只能以 `react-dom/server` 做靜態渲染測試，而且不得新增相依。執行者看不到畫面，只能靠 `tsc`、`vite build`、`npm test` 與使用者的 GUI 清單。所以可測性要來自**純邏輯模組**，而不是 hooks（U18）。

**產品邊界**（GOALS U12）是每個階段的第一個判斷條件：先問觸發情境是不是支援的正常使用，再決定要不要處理。

## 事實來源

| 事實 | 來源 |
|---|---|
| 目標、使用者決策、否決項、範圍、不變量 | [GOALS.md](GOALS.md) |
| 產品邊界的權威文字 | repo 根目錄 `CLAUDE.md`、`AGENTS.md`、`README.md` |
| S-ID 的位置、證據與原始建議 | [稽核原文](context/repo-debt-audit-2026-11-19.md) §6 |
| 每個 S-ID 由哪個階段處理 | 本檔「S-ID 歸屬」 |
| citation 合併後的行為與必須保留的保證 | [決策紀錄](../../../note/20261119/citation_storage_unification_decision.md) §4–§5（§4 已依 U13 改寫，見 §10） |
| 階段內的步驟與驗收 | `build/phase-*.md` |
| 實際狀態、證據、阻塞 | [build-log.md](build-log.md) 與 `evidence/<步驟 ID>/` |
| 專案規則 | repo 根目錄 `AGENTS.md`、`CLAUDE.md` |

## 基線

2026-11-19 撰寫時以 `3b6cfd8` 讀碼；2026-11-20 修訂時 HEAD 是 `3f87f09`。兩者之間只有本計劃與 README、AGENTS.md、CLAUDE.md 的文件 commit，`git diff --stat 3b6cfd8..3f87f09 -- app` 為空，所以下列行號仍以 `3b6cfd8` 為準。這些都是讀碼與量測的結果，撰寫時沒有執行任何測試。執行前由 C1 依符號重新定位。

### 工作樹

- `for_agents/` 有 9 個使用者未提交的修改。
- 未追蹤的檔案：
  - `NOTES-grill-skill-and-document-context.md`、`app/desktop/watch.out`、`note/20261106/`；
  - 沙箱掛載產生的點檔，都是 `/dev/null` 的字元裝置：`.bashrc`、`.bash_profile`、`.profile`、`.zshrc`、`.zprofile`、`.gitconfig`、`.gitmodules`、`.mcp.json`、`.ripgreprc`、`.idea`、`.vscode`，以及 `.claude/` 內的裝置檔；
  - 計劃目錄內與 `harness/plans/` 下的 `.claude/.cc-writes/`（宿主留下的空目錄）。
- 除了 C2-S9 刪除的 `watch.out` 與 `harness/plans/.claude/`，以上一律不動、不提交。

### 規模（行數）

| 檔案 | 行數 |
|---|---|
| `app/agent/desktop/service.py` | 4,643 |
| `app/desktop/src-tauri/src/protocol.rs` | 3,638 |
| `app/desktop/src/App.tsx` | 3,059 |
| `app/desktop/src-tauri/src/backend.rs` | 2,497 |
| `app/desktop/src/protocol.ts` | 2,333 |
| `app/agent/session.py` | 1,555 |
| `app/agent/desktop/fixture_session.py` | 1,493 |
| `app/desktop/src/styles.css` | 1,299 |
| `app/desktop/protocol/v1/contract.json` | 1,261 |
| `app/agent/desktop/catalog.py` | 840 |
| `app/desktop/src/conversations.ts` | 800 |
| `app/agent/desktop/protocol.py` | 760 |
| `app/desktop/src/backend.ts` | 605 |
| `app/desktop/src/trust.tsx` | 549 |
| `app/desktop/protocol/v1/fixtures.json` | 5,194 |

### 協定

- `contract.json` 有 40 個方法、20 個 request event、4 個 process event、25 個錯誤碼。28 個方法有 `resultDataSchemas`。
- schema 用自訂的欄位規則：每個欄位有 `type`、`required`，可選 `enum`、`maxBytes`、`items` 等。`type` 只有 13 種：`string`、`integer`、`boolean`、`nullableString`、`nullableBoolean`、`stringArray`、`object`、`objectArray`、`turnId`、`requestId`、`utcTimestamp`、`submittedContext`、`nullableSubmittedContext`。
- 只有 Python 在 runtime 讀 contract（`agent/desktop/protocol.py`）。TS（`protocol.ts`）與 Rust（`protocol.rs`）各自手抄一份，再以 parity 測試互相監督。TS 的 31 個 DTO interface 是手寫的，parity 測試並不檢查它們。
- Rust production 在 `backend.rs` 用到 `parse_protocol_value`、`parse_protocol_value_from_origin`、`validate_result_data`。
- `backend.rs:1545-1546` 先 `emit_protocol` 再經 invoke 回傳，同一個 result 送了兩次。
- `app/desktop/tsconfig.json` 已開 `resolveJsonModule`，`module: ESNext`，`moduleResolution: Bundler`，`include: ["src"]`。
- `npm test` 是 `node --test --experimental-strip-types tests/*.test.ts`，Node `v24.18.0`，`typescript` devDependency 是 6.0.3。5 個測試檔用 Vite SSR 載入 `.tsx` 模組：`inline_skills`、`citation_preview`、`documents`、`conversations`、`trust`。其中 4 個以 `react-dom/server` 的 `renderToStaticMarkup` 對元件做靜態渲染測試。

### 錯誤訊息

- 所有送往 WebView 的錯誤訊息都經過 `agent/desktop/protocol.py::bounded_error_message`：`protocol.py:636` 的錯誤 result，以及 `server.py:291`、`:370` 的框架錯誤。
- 它目前只截斷長度，不遮蔽。`_map_exception` 只回固定字串；動態字串來自 `DocumentError` 等例外的 `str(exc)`（`service.py:548-556`）與 `_bibliography_error`（含 Pandoc、bime_word 的 stderr）。
- `agent/diagnostics.py::redact_text` 已用於 log 的遮蔽。
- TS 的 `backend.ts:131` `sensitiveMessagePattern` 只要訊息含 `token`、`secret`、`authorization`、`bearer`、`traceback` 或 `api key` 就整句隱藏。

### citation、catalog 與回合狀態

- citation 的現況見[決策紀錄](../../../note/20261119/citation_storage_unification_decision.md) §2。另外讀碼確認：
  - `skills/citation/service.py::_link_library` 對同一批次的作品依序合併。若某筆的 `existing` 是因為同一批次較早的一筆剛加入記憶體中的書目庫，而之後的寫入失敗，這筆仍被報成 `existing`。這就是 U13 的「同批重複誤報」。
  - `SourceRegistry.register` 對同一 identity 重複登記不會拒絕。
  - `agent/skills/citation/session_policy.py` 依 `saved`／`reused`／其他計算 `CitationSaveMetrics`。
- `catalog.py` 的 production 路徑一律是 `_scoped_catalog`，每個 `historyDirectory` 一份 `desktop-projects.json`。`load_project_catalog` 以 `ConversationRepository.scan()` 檢查歷史健康與擁有權，再 reconcile catalog。
- `project.list`（`service.py:859`）唯一的呼叫者是 `App.tsx:207` 的 `loadSelectedProjectHistory`，它要求專案數剛好是 1。`App.tsx` 約 2237 行的 effect 以 `catalog.selectedSessionId` 或 `resumeSelectionRef` 恢復選取的對話。
- 每回合狀態：`_session_turn`（`service.py:2950`）在回合開始時設定 `installer.bypass_approval`，文件回合在 `:3276-3277` 設定 `session.set_thinking_mode("normal")` 與 `session._document_turn_active = True`，`finally`（`:3021-3036`）再逐一還原，連同 `DesktopService` 自己的 10 個 `_active_*`、`_turn_*`、`_tool_*` 欄位。`finally` 中較早的呼叫若拋錯，之後的還原就不會執行。

### fixture 模式

- `server.py:421` 在 `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02` 時改用 `fixture_session.build_phase02_fixture_service`。使用者文件沒有記載這個開關。
- 使用者是 5 個測試模組：`test_desktop_crash_recovery.py`（以 `python -m agent.desktop.server` 啟動子程序）、`test_desktop_fixture.py`、`test_desktop_document_service.py`、`test_desktop_server.py`、`test_desktop_service.py`。
- `app/tests/` 沒有 `__init__.py`，測試輔助模組如 `citation_fixtures.py` 由 pytest rootdir 匯入。

### 測試基線

撰寫時沒有重跑，以下是歷史紀錄：2026-11-15 `3b6cfd8` pytest 1808 通過；2026-11-07 npm 329、cargo 42。驗收標準是「全部通過」，不是固定數字。C1-S2 會重新建立實際基線。

## 目標詞彙

C4、C5、C6 完成後，contract 應剛好有下列內容（G2）。

**方法（25 個）**

- `runtime.diagnostics`、`runtime.shutdown`
- `workspace.select`
- `document.open`、`document.save`、`document.apply`
- `session.create`、`session.list`、`session.select`、`session.delete`、`session.rename`、`session.transcript`、`session.turn`、`session.set_thinking`、`session.set_permission`（P2 改名）、`session.stop`
- `extensions.preview`、`extensions.apply`
- `approval.resolve`
- `bibliography.inspect`、`bibliography.render`、`bibliography.set_style`、`bibliography.remove`、`bibliography.add`、`bibliography.export`

**移除的方法（15 個）**

- 10 個 `knowledge.*`（U2，C4）
- `session.status`、`session.shutdown`、`extensions.status`（P1，C4）
- `session.retry_registration`（U3，C6）
- `project.list`（U19，C6）

**request event（8 個）**

`request.started`、`turn.accepted`、`stage.changed`、`tool.started`、`tool.finished`、`tool.failed`、`document.proposed`、`approval.required`

**不變的部分**：

- process event（4 個）不變。
- 錯誤碼依 P3 移除沒有 producer 的部分，結果記在 C4-S5 與 C10-S0。
- 斜線指令仍會用到的錯誤碼都**保留**，包括 `OLLAMA_UNREACHABLE`、`OLLAMA_MODEL_MISSING`、`BUSY_KNOWLEDGE_MUTATION`。
- approval operation enum 中的 `knowledge.init_workspace`、`knowledge.ingest_file`、`knowledge.ingest_folder`、`knowledge.prune_apply` 是斜線指令的核准名稱，不是 RPC 方法，同樣**保留**（GOALS A3）。

## 路線

| 階段 | 完成後的狀態 | 相依 | 涵蓋 | 細節 |
|---|---|---|---|---|
| C1 | 起點已核對，基線測試與量測已記錄，JSON import 與 TS compiler API 已探測 | 無 | G9 | [phase-01-preflight.md](build/phase-01-preflight.md) |
| C2 | 不屬於後續階段的 READY 項目、U6、S047、錯誤出口遮蔽與小缺陷完成 | C1 | G7、G8 | [phase-02-ready-cleanup.md](build/phase-02-ready-cleanup.md) |
| C3 | contract 成為唯一手寫來源；TS 直接讀它，DTO 漂移會讓測試失敗；Rust 只驗框架；Python 只驗一次；result 只傳一次 | C1 | G1、G7、G8 | [phase-03-protocol-single-source.md](build/phase-03-protocol-single-source.md) |
| C4 | 線上詞彙縮到目標，權限命名統一 | C3 | G2 | [phase-04-wire-vocabulary.md](build/phase-04-wire-vocabulary.md) |
| C5 | citation 只存在書目庫，存檔結果誠實（U13），BibTeX 鏈與 `pybtex` 移除，驗證保證保留 | C3 | G3、G7、G8 | [phase-05-citation-single-store.md](build/phase-05-citation-single-store.md) |
| C6 | 對話清單由掃描推導，`project.list` 與 registration 移除，選取恢復保留，掃描成本已量測 | C3 | G4、G2 | [phase-06-derived-catalog.md](build/phase-06-derived-catalog.md) |
| C7 | fixture 移到 tests，`ChatSession` 有公開介面，每回合選項取代共用狀態，重複忙碌判斷以最少抽象共用（U21），Stop 可恢復，`service.py` 模組化 | C2、C4、C5、C6 | G5、G7 | [phase-07-backend-seams.md](build/phase-07-backend-seams.md) |
| C8 | 前端純邏輯模組化並受型別檢查，`api.ts` 唯一呼叫後端，preview stub 移除，`App()` 依 domain 拆解 | C3、C4、C5、C6 | G6 | [phase-08-frontend-logic.md](build/phase-08-frontend-logic.md) |
| C9 | 元件拆出，dialog／menu／transcript 共用相同語意的部分（U22），CSS 依區塊分檔，釘住 layout 的測試改為行為斷言 | C8 | G6 | [phase-09-frontend-presentation.md](build/phase-09-frontend-presentation.md) |
| C10 | 跨階段詞彙已比對，文件與現況一致，完整測試通過，最終彙報完成 | C2–C9 | G9、G2 | [phase-10-delivery.md](build/phase-10-delivery.md) |

**執行順序**：依表格順序。

- C2 在 C3 之前：C2 的錯誤出口遮蔽會改 `backend.ts`，C3 接著改寫同一檔案。
- C4、C5、C6 都只依賴 C3，彼此獨立。依序做是為了讓同一時間只有一個階段在改 contract 與 fixtures。
- C7 與 C8 互不依賴。其中一個被阻塞時，可以先做另一個。

**先收斂協定再刪詞彙（C3 → C4）的理由**：C3 改寫的內容與詞彙多寡無關。C3 之後刪一個方法只要改 contract、Python、TS DTO 與 fixtures，而 U16 的檢查會指出漏改的 DTO。

## S-ID 歸屬

稽核 S001–S134 中，每個納入的項目只歸一個階段。未列在此表的項目，處置見 [GOALS.md](GOALS.md) 的「不納入」與「KEEP」。

| 階段 | S-ID 與其他項目 |
|---|---|
| C2 | • Agent 核心：S038、S039、S040、S041、S042、S044、S046（U6）、S047<br>• Skills 與測試：S061、S062、S063、S109、S122<br>• RAG：S114、S115、S117<br>• Rust 與啟動器：S014、S098、S101、S102<br>• 前端：S073、S074、S075、S076、S092，以及 `.error-text` 樣式（缺陷 #2）<br>• 錯誤出口遮蔽：S089（U15，缺陷 #3）<br>• Repo：S128（缺陷 #7）、S129<br>• 桌面後端：S023、S024、S026 |
| C3 | • S001、S002、S003（缺陷 #4）、S004、S005<br>• S011、S012、S090<br>• S071 的兩個死 DTO、S072、S085<br>• U16 的 DTO 一致性檢查 |
| C4 | • S006、S007（U2＋P1）、S008、S009、S010、S016（U8＋P2）、P3<br>• 只因移除功能而失效的 S036 測試 |
| C5 | • S105（U4、U13、P8、P13）、S106（隨 S105 消失）<br>• S108、S110、S118、S119、S120<br>• S029<br>• U9、P9、只因 U4 而失效的 S121 測試<br>• `doi_org._encoded` 型別（缺陷 #6） |
| C6 | S018、S019、S027、S070、`session.retry_registration` 與 registration 欄位（U3）、`project.list`（U19）、掃描量測（R3） |
| C7 | • S020（P5）、S021、S022<br>• S031、S037<br>• S052、S043、與 S052 有關的 S066 部分<br>• U17 每回合選項<br>• S028<br>• FAIL-022（U14，缺陷 #1）<br>• `service.py` 模組化，其中 S034 搬到 `errors.py`、S123 的 bibliography handler 抽出 |
| C8 | • S083、S082、S093、S071 的 snapshot 型別統一<br>• S078（U5）<br>• S079、S080<br>• S097 的 domain 邏輯（U18） |
| C9 | S081、S097 的元件、S096 的分檔與 class 改名（P12）、S086、S087、S088 |
| C10 | 跨階段詞彙收尾（C10-S0）、文件更新、完整驗證、最終彙報 |

缺陷 #5（`turn_logs`）就是 S047，歸 C2。

## 檢查指令

以下指令都已在 repo 現有設定中確認存在。

**Python**

- 從 `app/` 執行（AGENTS.md 的寫法）：`poetry run pytest`。
- 本機常用的等價寫法：`/home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider`。
- 單一模組加上路徑，例如 `tests/test_desktop_service.py -q`。
- 完整 suite，以及 `test_desktop_fixture.py`、`test_desktop_document_service.py`、`test_desktop_crash_recovery.py` 需要可寫的 `/tmp`：**在沙箱外執行**。
- 只跑 citation、agent 核心、rag 的模組時可以在沙箱內跑。
- 接 `| tail` 時要檢查 `${PIPESTATUS[0]}`。

**前端**

- 從 `app/desktop/` 執行。先設定 `PATH=/home/minervamuses/miniconda3/envs/app/bin:$PATH`。
- 在沙箱內加上 `npm_config_cache=$TMPDIR/npm-cache`。
- `npm test`：Node 內建測試。
- `npm run build`：`tsc --noEmit` 加 `vite build`，輸出到被忽略的 `dist/`。

**Rust**

- 從 `app/desktop/` 執行 `cargo test --locked --manifest-path src-tauri/Cargo.toml`。PATH 同上。
- **在沙箱外執行**，因為 supervisor 測試寫死 `/tmp`。
- `target/` 已被 `app/desktop/.gitignore` 忽略。

**相依（只用於 C5-S5）**

- 從 `app/`，在 Conda env `app` 內執行 `poetry remove pybtex`。
- 可能需要連 `pypi.org` 與 `files.pythonhosted.org`。在沙箱內要宣告這兩個網域，或改在沙箱外執行。
- 不可手改 `poetry.lock`。

**差異檢查**：`git diff --check <起點>..HEAD`。

## 執行契約

本計劃只規範工作內容，本身不授權實作。只要求撰寫或修訂計劃的指令，到審查過的計劃檔案為止。

使用者明確啟動本計劃後，執行者要在授權範圍內連續完成所有可執行的階段，包括一般的實作選擇、修正與檢查，以及維護計劃檔案。這份授權在交接後仍然有效。宿主與工具的權限控制，以及使用者後來的變更，優先於計劃文字。計劃文字不能推導出付費服務、遠端寫入、發佈、部署、破壞性操作或更大的目標範圍。已經取得的明確授權直接沿用，不重複詢問。

### 每個步驟

1. 讀適用的專案規則（`AGENTS.md`、`CLAUDE.md`）、[GOALS.md](GOALS.md)、本檔、[build-log.md](build-log.md)，以及相關的實際檔案狀態。
2. 保留與本計劃無關的工作，尤其是 `for_agents/` 的未提交修改與未追蹤檔案。
3. 做一個有邊界、一致的步驟。
4. 執行有意義的檢查，記錄觀察到的結果與限制。
5. 更新 build-log，然後 commit。
6. 前提滿足後才進入相依的工作。

### 產品邊界檢查

- 新增任何檢查、鎖、旗標或協調邏輯時，在該步驟的 evidence 寫一行：`機制 → 觸發情境 → 支援的正常使用（理由）`。寫不出支援的正常使用，就不新增。
- 修正失敗時，不得以「使用者應該照順序操作」為理由放過支援流程中的錯誤；也不得把不支援的同時操作寫成新的測試或驗收。
- C10 的最終彙報把這些紀錄彙整成一節。

### commit 與 checkpoint

- 使用者的既定規則：**每一步都強制 commit**。這包括執行中新增的修正步驟、計劃修訂，以及檢查失敗時保留證據的 checkpoint。
- subject 用 Conventional Commits 加步驟 ID，例如 `refactor(protocol): import contract in TS [C3-S2]`。
- 若一個步驟拆成多個 commit，ID 加上小寫字母，例如 `[C7-S8a]`、`[C7-S8b]`。
- 失敗或阻塞的步驟也要有 `[Cn-Sm checkpoint]` commit。
- 只 `git add` 明確路徑，不用 `git add -A` 或 `git add .`。`build/` 被 `.gitignore` 的 `build/` 規則忽略，計劃階段檔要用 `git add -f`。
- 不在 commit 裡記錄自己的 hash。build-log 以步驟 ID 對應 git log。
- 不 push，不建立、切換、刪除或重新命名 branch，不建立 worktree，不改 Git 身分，不繞過 hooks。

### 證據

- 需要保留的證據放在 `evidence/<步驟 ID>/`，例如測試輸出摘要、量測、對照表與盤點。不要只放在 `/tmp`，重開機會遺失。
- 證據裡不放 secret、對話內容或使用者文件內容。

### 失敗與重新規劃

- 診斷失敗原因，在範圍內修正。同一個問題兩次聚焦修正都失敗時：
  - 只封鎖該問題與相依它的步驟，在 build-log 記為 Blocked；
  - 繼續其他前提已滿足的工作；
  - 剩下的工作全部被阻塞時，才停止並彙報。
- 不可為了通過而削弱斷言、守衛、快照或測試設定。測試數量下降是預期的，但每個被刪的測試都要符合下面的退役規則。
- 新證據改變路線時，先修訂受影響的未開始或進行中階段，以及 `plan-index.json`，再繼續；修訂本身也要 commit。不可在沒有授權的情況下改變 G1–G9、U1–U22、R1–R6、限制或必要驗收。
- 遇到需要使用者決定的事，在不違反決策的安全前提下繼續其他工作，並把該事項寫進最終彙報，不停下來等。

### 測試退役規則

只有在下列情況可以刪除或改寫測試：

- 它保護的行為已被本計劃刪除或改變；
- 或它與留下的測試在行為、輸入分區、斷言與執行環境上都等價。

每個被刪的測試都要在該步驟的 evidence 記一行：`被刪的測試 → 它保護的行為（或已刪除的細節） → 留下的證據`。

### 中斷與續作

- 續作時先對照 build-log、`git log` 與實際檔案狀態，再決定下一步。
- 歸屬不明的修改保留下來，並封鎖受影響的步驟。不因為檔案在本計劃範圍內就整檔還原。
- 同一問題的嘗試次數不因再次送出提示而歸零。

### 完成

- 只有觀察到驗收結果並完成交付，才標記完成。寫了程式碼、通過結構 lint 或已經 commit，都不算完成。
- 跳過或無法執行的必要檢查不算通過。

## 整體完成條件

1. C1–C10 在 build-log 都是 Complete，或者 Blocked 附理由；Blocked 的部分在最終彙報列為未完成。
2. 最後一次完整 pytest、`npm test`、`npm run build`、`cargo test --locked` 都通過，而且是在最終程式狀態上執行。
3. `evidence/C10-S3/final-report.md` 存在，內容依 [phase-10](build/phase-10-delivery.md) C10-S3 的清單。
4. 所有步驟都已 commit，工作樹中屬於本計劃的修改都已提交。

## 風險與對策

| 風險 | 對策 |
|---|---|
| `App()` 沒有整合測試，拆解時的回歸自動檢查看不到 | • C8-S1 先寫行為盤點，並分類每個 ref。<br>• 狀態轉移與守衛抽成純函式並測試；hook 只是薄包裝。<br>• 每個抽出各自一個 commit。<br>• 交付 GUI 清單給使用者。 |
| 拆 `App()` 時把相依關係換成 hooks 互傳 ref 與 setter | U18 的規則：hook 之間不互傳 ref 或 setter；跨 domain 的協調集中在一處；C8-S6 逐一檢查每個 hook 的參數。 |
| U1 之後 Python 驗證器的錯誤不再被 TS 或 Rust 攔下 | 這是 U1 接受的後果。Python 端的 contract 與 fixture 測試保持完整，每個方法至少一個合法例與一個非法例。TS DTO 的漂移由 U16 的檢查守住。 |
| C5 拆掉 BibTeX 時驗證保證中斷 | C5-S1 先建立保證對照，C5-S2 先補檢查，C5-S3 才在同一個 commit 內刪除模組、改存檔語意並切換桌面端。 |
| C5 的存檔語意改變影響論文評估 | C5-S6 記錄評估分界 commit；決策紀錄 §6.2 與 §10 列出改變的欄位與計數。 |
| C7 的每回合選項或 Stop 修正改變回合生命週期 | 先寫回歸測試（中途失敗的回合、清理失敗後重試），再改程式；每一步讓 desktop 測試全部通過才 commit。C7-S6 不強制把所有 Busy flag 搬到新物件（U21）。 |
| 為不支援的同時操作加機制，或反過來以產品邊界為由放過真缺陷 | 「產品邊界檢查」：每個新機制都要寫出支援的觸發情境；R1–R6 不得重新引入。 |
| U6 讓 `app/store` 以外的舊對話無法讀取 | 使用者已接受。C2-S5 先確認 `app/store` 內沒有非 v3 檔案。 |
| 行號漂移 | 一律以符號與 grep 重新定位。稽核行號只當線索。 |
| 用量上限中斷 | 每步 commit。依 build-log 與 git log 續作。 |
| 沙箱限制（`/tmp`、`~/.cache`、`~/.npm`、PyPI） | 依「檢查指令」的說明在沙箱外執行，或宣告網域。 |
| 執行者看不到 GUI | 不宣稱 GUI 已驗證。每個改到畫面的階段都把檢查項目加進最終清單。CSS 只依原順序分檔，不改層疊與顏色（P12、R4）。 |
