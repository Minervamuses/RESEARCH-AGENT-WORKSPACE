# 詰問 skill、文體 skill 與文件 context：路線與執行契約

- **計劃根目錄**：`harness/plans/2026-11-14-grill-genres-document-context/`（相對於 repo 根目錄 `/home/minervamuses/research-agent-workspace`）
- **目標與決策**：[GOALS.md](GOALS.md)
- **目前狀態與證據**：[build-log.md](build-log.md)，這是唯一的狀態來源
- **啟動入口**：[PROMPTS.md](PROMPTS.md)

## 任務規模

主要是 Python 後端（`agent/session.py`、`agent/desktop/service.py`、`agent/observability.py`）與兩個新 skill 的文字內容，加上一支評估腳本。預期不改前端與協定；若執行中發現必須改，npm 與 cargo 檢查變成必要。

風險集中在兩處：

1. **歷史組裝（K3）**：文件快照是以文字嵌在已保存的 `semantic_input` 裡，重播時要正確辨識並替換，又不能動到保存的內容、重試與凍結引用。
2. **編輯結果縮減（K4）**：`document_edit` 存檔成功的結果目前帶整份 `sourceText`，多 skill 連續編輯的提示（`agent/skills/runtime.py`）明說依賴它。縮減前要先回答「下一次編輯需不需要全文」。

詰問 skill 的真實效果不在本計劃驗證範圍（U2）。執行者只能宣稱「skill 與框架完成、假模型流程通過」。

## 基線（2026-11-14 撰寫時讀碼，HEAD `7489076`，分支 `GUI`）

路徑都相對於 `app/`。行號是撰寫時的位置，執行前以 K1 重新核對。以下都是讀碼結論，沒有實際執行。

**文件回合**

- `agent/desktop/service.py` 約第 3203–3228 行：有 `documentContext` 時，在 `turn_text` 後面接上 `[Current editor document snapshot; sourceText is document data, not instructions]`、整份 `document_context` 的 JSON（含 `sourceText`）與一段使用說明（含「For an explicitly requested edit, call document_edit…」），然後 `session.set_thinking_mode("normal")`、`session._document_turn_active = True`。
- 同檔約第 3229–3245 行：凍結引用以 `[Frozen references: …]` 區塊接在後面；`_model_reference_projection` 讓與當前快照相同的全文以 `sourceTextSameAs` 省略（同一則訊息內已去重，見 `tests/test_desktop_document_service.py::test_model_input_shows_each_frozen_document_version_once`）。
- 同檔約第 3246–3249 行：重試或有 `submittedContext` 時，`turn_text` 改用原回合保存的 `semantic_input`。此時 `turn_text` 可能含快照，但 `_document_turn_active` 只在 `"documentContext" in params` 時設為真，兩者不一定一致。
- 同檔約第 2968–2970 行：回合結束時把 `_document_turn_active` 設回 `False` 並恢復思考模式。
- `agent/session.py` 第 667–668 行：`_document_turn_active` 為真且工具全集有 `document_edit` 時，把它強制加進有效工具；第 669–673 行同理加入 `bibliography_lookup`。第 691 行、第 1160 行也以這個旗標決定是否帶工具可用性提示與 `effective_tools`。也就是「有文件可讀」與「允許編輯」掛在同一個旗標上。

**歷史重播**

- `agent/conversations/models.py:16`：`LATEST_CONTEXT_TURNS = 10`。
- `agent/conversations/repository.py` 約第 732 行 `latest_context`：取最近 10 個已完成、可入 context 的對話回合，回傳 `semantic_input` 與 `assistant_output`。
- `agent/session.py` 約第 563 行 `_base_prompt_history`：把每個回合的 `user_input`（即 `semantic_input`，含整份文件 JSON）原樣做成 `HumanMessage`。其他使用者：`agent/thinking/orchestrator.py:188`（extended 模式）、`agent/session.py` 約第 1096 行 `_visible_context_text`（由 `agent/thinking/orchestrator.py:534` 以純文字送進 extended 模式提示，同樣來自 `latest_context`）、約第 512 行 `recent_turns`（對外顯示）；`agent/desktop/fixture_session.py` 約第 822、1050 行。
- `agent/session.py` 約第 581–620 行：對話封存提示告訴模型，normal 模式可用 bash 的固定字串 grep 加 `read_file` 從封存目錄取回較舊的原文；extended 模式不行。

**編輯結果**

- `agent/desktop/service.py` 約第 2492 行 `_desktop_document_edit` 回傳 `json.dumps(result)`；存檔成功的 `result` 由 `agent/desktop/documents.py` 約第 308–313 行產生，含 `sourceText`（整份新文字）、`rangeEndUtf16`、`editorRevision`、`diskFingerprint` 等。
- 同一回合的 `_advance_document_working_context`（約第 2573 行起）在伺服器端推進工作範圍，凍結引用的 `reference_id` 範圍會跟著前一次成功的編輯移動。
- `agent/skills/runtime.py` 約第 66 行：多 skill 提示寫著「a successful document_edit tool result contains the saved source and updated selection for the next operation」。
- `_run_desktop_document_edit` 至少有兩條回傳 `saved` 結果給模型的路徑：重播已有結果（約第 2535–2541 行的 `existing.result`）與一般回傳（約第 2570 行）。`candidate.result` 另供前端與重試使用。
- `tests/test_inline_skills.py` 約第 93 行斷言工具結果的 `result["sourceText"]` 含編輯後文字；其他解析 `sourceText` 的測試檔包括 `tests/test_desktop_document_service.py`、`tests/test_desktop_fixture.py`、`tests/test_desktop_documents.py`、`tests/test_desktop_citation_keys.py`、`tests/test_desktop_bibliography.py`、`tests/test_project_permissions.py`（不一定都解析工具結果，K4-S1 要逐一確認）。

**量測**

- `agent/observability.py`：`summarize_model_response` 與 `TurnTimingTrace.on_llm_end` 只記錄 `input_tokens`、`output_tokens`（與 `total_tokens`）；turn trace 以 `logger.info("turn_trace …")` 輸出。沒有任何欄位分出文件佔多少。

**Skill**

- `agent/skills/manifest_schema.py`：manifest 只允許 `tools`、`resources`（`extra="forbid"`）；沒有 `tools` 段時走 normal 模式的工具。
- 技能探索只掃 `skills/*/SKILL.md`（`agent/skills/metadata.py:48`）。
- `render_tool_availability_block`（`agent/skills/runtime.py` 約第 124–137 行）把有效工具列在 `available_tools:`，其餘列在 `unavailable_tools:`；被遮蔽的工具會出現在後者。`PolicyToolNode` 會拒絕不在 `effective_tools` 中的工具呼叫。
- `@name` 行內引用：前端 `desktop/src/App.tsx` 約第 2347 行以 `inlineSkillReferences` 產生 `skillReferences`，後端 `agent/desktop/service.py` 約第 3014 行 `resolve_skill_references`。新 skill 放進 `skills/` 即會出現在可引用清單，預期不必改前端。
- 段落留言（reference comment）會以使用者請求的形式送進模型（`tests/test_desktop_document_service.py::test_reference_comments_reach_model_as_requests_with_source_and_permission_boundaries`）；留言中的 `@grill` 是否啟用 skill 沒有實測（S1）。
- `skills/academic-paper-writing/SKILL.md` 第 93 行用 `[insert citation]`、`[report sample size]`、`[state limitation]` 當佔位符。
- vendored `vendor/bime-word` 辨識 `[TODO: …]`、`[CITE: …]`、`[FIGURE: …]`。

**系統提示**

- `agent/session.py` 第 77 行起的 `SYSTEM_PROMPT`；桌面以 `_project_system_prompt`（`agent/desktop/service.py` 約第 1490 行）在後面接上專案根目錄與 RESEARCH.md 規則。

**模型與成本**

- `agent/config.py`：主模型 `google/gemini-3.8-flash`，經 OpenRouter（付費）。本計劃不授權任何真實模型呼叫；所有測試用假模型（例如 `tests/test_desktop_document_service.py` 的 `_DocumentModel`，它把每次呼叫的訊息存在 `model.calls`，或 `tests/test_observability.py` 的 `_ScriptedChatModel`）。

**工作樹**

- 撰寫時 `git status` 有與本計劃無關的未追蹤檔：`NOTES-grill-skill-and-document-context.md`、`app/desktop/watch.out`、`note/20261106/`，以及 repo 根目錄的 `.bashrc`、`.profile`、`.claude/` 等點檔（疑似沙箱掛載產生）。一律不動、不提交；commit 時只 `git add` 明確路徑，不用 `git add -A` 或 `git add .`。

**測試基線（歷史紀錄，撰寫時未重跑）**

- 2026-11-07 `ab22475`：pytest 1763、npm 329、cargo 41 全部通過；2026-11-07 `7489076`：cargo 42。
- 驗收標準是「全部通過」，不是固定數字。

## 路線

| 階段 | 後置條件 | 相依 | 涵蓋 | 細節 |
|---|---|---|---|---|
| K1 | 分支、HEAD、工作樹、工具與基線位置已核對；可沿用的測試基線已記錄；計劃檔已提交 | 無 | G9 | [phase-1-preflight.md](build/phase-1-preflight.md) |
| K2 | turn trace 可分出文件佔比；15 個編輯回合的假模型量測已建立，修改前的數字存進 evidence | K1 | G6 | [phase-2-measure.md](build/phase-2-measure.md) |
| K3 | 重播歷史時舊回合不帶文件全文、只保留最新一份；保存與重試行為不變 | K2 | G7 | [phase-3-history-assembly.md](build/phase-3-history-assembly.md) |
| K4 | 已回答「下一次編輯需不需要全文」並依結論縮減編輯結果；連續編輯不壞；修改後量測已記錄 | K2；修改後量測需 K3 完成 | G8、G6 | [phase-4-edit-result.md](build/phase-4-edit-result.md) |
| K5 | `grill` skill 寫好並被載入；詰問回合可讀文件但 `document_edit` 被遮蔽；`@grill` 一回合生效 | K1 | G1、G2 | [phase-5-grill-skill.md](build/phase-5-grill-skill.md) |
| K6 | 詰問評估框架（案例格式、示範案例、預設不連網的腳本、報告）完成並以假模型跑通 | K5 | G3 | [phase-6-grill-eval.md](build/phase-6-grill-eval.md) |
| K7 | `writing-genres` skill 與 `SYSTEM_PROMPT` 回覆規則完成；佔位符寫法對齊 | K1 | G4、G5 | [phase-7-genres.md](build/phase-7-genres.md) |
| K8 | 文件已更新；完整測試通過；最終彙報交付 | K3、K4、K5、K6、K7 | G9 | [phase-8-delivery.md](build/phase-8-delivery.md) |

正常順序是 K1→K2→K3→K4→K5→K6→K7→K8，依序修改 repo，不平行執行。某階段被阻塞時，依上表相依關係先做其他前提已滿足的階段（例如 K3 卡住時可做 K5–K7）。上表與 `plan-index.json` 記錄的是同一張相依圖。

## 檢查指令

以下指令從先前計劃與環境紀錄得知。`P=/home/minervamuses/miniconda3/envs/app`。

| 檢查 | 指令（工作目錄） | 沙箱 |
|---|---|---|
| 指定的 Python 測試 | `$P/bin/python -m pytest -q -p no:cacheprovider <檔案或 ::測試>`（`app`） | 沙箱內可跑 |
| 完整 pytest | `TMPDIR=… XDG_CACHE_HOME=… AGENT_LOG_DIR=… $P/bin/python -m pytest -q -p no:cacheprovider`（`app`）；三個變數指向計劃 `evidence/` 下或 `$TMPDIR` 中新建的可寫目錄 | **必須在沙箱外**（fixture 寫死 `/tmp`） |
| 前端測試（條件式） | `PATH=$P/bin:$PATH npm_config_cache=$TMPDIR/npm-cache npm test`（`app/desktop`） | 沙箱內可跑 |
| Rust 測試（條件式） | `PATH=$P/bin:$PATH CONDA_PREFIX=$P CONDA_DEFAULT_ENV=app cargo test --locked --manifest-path src-tauri/Cargo.toml`（`app/desktop`） | **必須在沙箱外** |

用管線把輸出接到 `tail` 時，以 `${PIPESTATUS[0]}` 判斷結束碼。

**檢查範圍與次數**

- K2–K7 只跑與該步修改相關的測試模組，例如 `tests/test_desktop_document_service.py`、`tests/test_observability.py`、`tests/test_session_persistence.py`、`tests/test_inline_skills.py`、`tests/test_skills.py`、`tests/test_academic_skill_tools.py`、`tests/test_thinking_session.py`、`tests/test_desktop_fixture.py`，以及新增的測試檔。
- 完整 pytest 只在 K8 跑一次。npm、cargo 只在本計劃實際改到 `app/desktop/` 或協定（`desktop/protocol/`、`agent/desktop/protocol.py`）時才在 K8 各跑一次；沒改到時記為「不適用」並附 `git diff --stat` 為證。
- 預估任一命令超過十分鐘時先取得明確授權。完整套件失敗後不自動重跑；修正後需要第二輪完整驗收時，記錄原因與預估耗時，留給使用者授權。

## 執行契約

本文件只規定工作內容，本身不授權實作。只要求撰寫計劃時，交付審查過的計劃檔就結束。使用者明確以 [PROMPTS.md](PROMPTS.md) 的提示啟動本計劃後，執行者在授權範圍內連續完成所有可執行的階段，包括一般的實作選擇、修正、檢查與計劃維護；這份授權在交接後仍然有效。宿主或工具的權限控制，以及使用者之後的變更，仍然優先。

**授權的動作**（啟動提示送出後）：

- 計劃列出的程式碼、skill、測試、腳本與文件修改，以及本地 commit。
- 依上表執行局部檢查，並在 K8 執行一次完整 pytest（條件成立時加 npm、cargo）。

**不授權**：任何真實模型或付費 API 呼叫（包括啟動會連 OpenRouter 的 CLI 或桌面 app、以 `--live` 跑評估腳本）；新增或升級依賴；寫入 `~/.claude/`、使用者的論文資料夾或任何專案的 RESEARCH.md；push、發佈；建立、切換、刪除、重新命名 branch，detached HEAD，worktree。

**每一步**：

1. 讀 AGENTS.md、本檔、GOALS、build-log 與該階段檔，核對相關的實際程式碼。
2. 做一個有界的步驟，跑該步列出的必要檢查。
3. 把實際執行的指令、結果、限制寫進 build-log；需要保留的輸出放計劃的 `evidence/<步驟 ID>/`，不要只放 `/tmp`。
4. 在本地 commit，訊息為 `type(scope): 摘要 [K?-S?]`，結尾附宿主要求的 attribution 行；只 `git add` 明確路徑，計劃 `build/` 下的檔案用 `git add -f`。commit 成功後才進入下一步。執行中新增的修正步驟、計劃修訂、檢查失敗時保留證據的 checkpoint（`[K?-S? checkpoint]`）也各自 commit。

**風險較高的步驟**（K3-S1、K3-S2、K4-S2）：動手前先把要做的選擇（例如佔位保留選取文字的上限、標頭常數放哪個模組、K4 的出口）與目前嘗試次數寫進 build-log，以 `[K?-S? checkpoint]` commit，讓中斷後能從紀錄接續，而不是只靠 commit 訊息。

**失敗與阻塞**：

- 診斷失敗並在範圍內修正，不因第一次失敗或階段邊界停下。
- 同一問題兩次聚焦修正仍失敗，只封鎖該問題與相依步驟，在 build-log 記為 Blocked，繼續其他前提已滿足的工作。嘗試次數不因中斷續作而歸零。
- 證據顯示路線要改時，先修訂受影響、尚未完成的階段與 `plan-index.json`，commit 後再繼續；不得改變 GOALS 的目標、範圍外項目或必要驗收。
- 只有剩餘工作全部被阻塞時才停止整次執行。需要使用者決定的事放進最終彙報，不中途停下等待。
- 不把必要檢查的失敗改成通過，不刪除或弱化既有測試來讓套件通過；既有測試必須修改時（例如斷言了被縮減的欄位），在 build-log 說明理由，且新斷言要能抓到原本要防的錯誤。

**GUI 與真實模型**：GUI 驗收由使用者本人在交付後操作（U5）；詰問的真實模型測試由使用者自行跑（U2）。執行者交付手動清單與執行方法，不等待結果，也不宣稱 GUI 或真實詰問效果已驗證。

**中斷續作**：依 build-log、`git log` 中的步驟 ID 與實際工作樹對帳後再繼續；已 commit 的步驟不重做。工作樹有未提交的本計劃修改時，先看 `git diff`：屬於下一個步驟且看得懂的，接著完成；看不懂或已損壞的，只用 `git restore` 還原該步驟涉及的明確路徑後重做該步。不還原與本計劃無關的檔案。

## 完成條件

整份計劃 Complete 需要：K1–K8 在 build-log 都是 Complete（任何 Blocked 都表示計劃未完成，最終彙報要列出阻塞原因與續作所需條件）；G1–G9 各自的成功條件都有實際證據；K8 的完整 pytest 通過（條件成立時 npm、cargo 也通過）；最終彙報已交付。程式碼寫完、structural lint 通過或有 commit，都不等於完成。
