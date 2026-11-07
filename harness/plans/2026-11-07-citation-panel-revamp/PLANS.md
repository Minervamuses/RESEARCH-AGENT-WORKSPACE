# 引用面板改版：路線與執行契約

- **計劃根目錄**：`harness/plans/2026-11-07-citation-panel-revamp/`（相對於 repo 根目錄 `/home/minervamuses/research-agent-workspace`）
- **目標與決策**：[GOALS.md](GOALS.md)
- **目前狀態與證據**：[build-log.md](build-log.md)，這是唯一的狀態來源
- **啟動入口**：[PROMPTS.md](PROMPTS.md)

## 任務規模

本計劃主要修改桌面前端（React），另外有少量 Python 後端修改、一個協定欄位的修改、新增兩個依賴，以及 vendor 一個本地工具。風險集中在兩處：

1. 協定修改會牽動 Python、TypeScript、Rust 三方的契約測試。
2. bime_word 必須在桌面後端的子行程中跑起來。

依使用者決策 D14，GUI 驗收由使用者本人於交付後操作。代理負責實作、必要自動檢查與程式碼核對，交付手動清單後即可完成代理工作，不等待使用者驗收；不把清單或單元測試描述成 GUI 已實測。這是明確分工，不以是否有 GUI 自動化工具決定。

## 基線（2026-11-07 撰寫時觀察，HEAD `5aea53c`，分支 `GUI`）

路徑都相對於 `app/`。執行前請以 R1 重新核對。

**面板與編輯器**

- `desktop/src/CitationPanel.tsx`：
  - `CitedRow` 在 `item.entry !== null` 時顯示 `EntryButtons`（Insert 與 Remove）。
  - 未引用區每筆也顯示 `EntryButtons`。
  - 新增成功後的訊息有「Insert at cursor」。
  - Export 按鈕由 `exportFormats(format)` 逐一產生。
  - Preview 只在 Markdown 文件顯示。
  - 面板沒有收合狀態。
- `desktop/src/citations.ts`：
  - `citationInsertion`、`insertIntoSnapshot`（約第 214–219 行）只被面板和 `desktop/tests/citations.test.ts` 使用。
  - `ExportFormat = "docx" | "markdown" | "bib"`，`exportFormats` 對 Markdown 回傳三種，對其他回傳 `["bib"]`，`EXPORT_LABELS` 在約第 272–283 行。
  - `removeConfirmation` 只在條目仍被引用時要求確認。
- `desktop/src/App.tsx`：`editorCursorRef`（約第 1089 行）只用來把 `onCursor`（第 2833 行）傳給面板的 `cursorOffset`（第 2842 行）。
- `desktop/src/DocumentEditor.tsx`：
  - Monaco 的 `fontSize: 14` 寫死在第 183 行，下一行固定 `lineHeight: 23`；R5 必須一併改為自動行高。
  - 第 295 行註冊 `[@`、`; @`、`\cite{` 的 key 補全，補全保留不改。
  - 選取變更時呼叫 `onCursor`（第 276 行）。
- `desktop/src/styles.css`：
  - `.citation-panel` 在第 1266 行：`max-height: 40vh; font-size: .78rem`。
  - `.citation-badge` 為 `.68rem`。
  - 前端目前沒有任何地方使用 `localStorage`。

**後端與協定**

- `agent/desktop/service.py` 約第 2372–2400 行的 `_bibliography_export`：
  - `bib` 分支呼叫 `csl_render.export_bib`。
  - `markdown`、`docx` 分支呼叫 `export_markdown`、`export_docx`。
  - 檔案以 `citation_library.write_bytes_atomic` 寫出。
  - 輸出等於原稿時拒絕。
- `skills/citation/csl_render.py`：
  - 約第 511–540 行：`EXPORT_SUFFIXES` 含 `bib`，`export_target` 有 `bib` 分支，另有 `export_bib`。
  - 約第 68–71 行：Pandoc 先找 `sys.executable` 旁邊，再找 `PATH`。
- 協定定義：`desktop/protocol/v1/contract.json` 第 789、1201 行的 `format` enum 為 `["docx","markdown","bib"]`；`fixtures.json` 約第 2210、2252 行使用 `"bib"`。
- 協定的使用者：
  - `agent/desktop/protocol.py`
  - `desktop/src/protocol.ts`：回應約第 995 行與參數約第 1169 行，各自寫死匯出格式 enum，修改 contract 不會自動更新這兩處。
  - `desktop/src-tauri/src/protocol.rs`：參數約第 999 行、回應約第 2455 行，各自寫死格式 enum；約第 2454 行以 `validate_exact_data_keys` 限定匯出回應只有 format、path。新增 audit 時必須一起更新允許欄位與驗證，不能只改 contract。因此修改契約後 Rust 協定測試為必要。
  - `desktop/tests/protocol.test.ts`
  - `tests/test_desktop_protocol_contract.py`
- 測試中的 bib：
  - `tests/test_desktop_bibliography.py` 約第 236–256 行
  - `desktop/tests/citation_preview.test.ts` 第 39–41 行
  - `tests/test_citation_csl_render.py`

**bime_word 與環境**

- bime_word 1.1.5 的來源是 `/home/minervamuses/論文/bime_word-1.1.5.zip`，只讀：
  - zip SHA-256：`66052fb91d5f9fbccff4b7eb98c3ea56779ec55192360e1772f8179e26303ab2`
  - 解壓後約 512 KB，頂層目錄為 `bime-word/`，內含 `manifest.sha256`，撰寫時 `sha256sum -c` 全部通過。
  - `scripts/bime/__init__.py` 中 `__version__ = '1.1.5'`。
  - 依賴：`requirements.txt` 為 `python-docx>=1.2.0,<2.0`、`lxml>=5.2,<7.0`。
- bime_word 的 `convert` 子命令：
  - 寫出 `-o` 檔，並以 `with_suffix` 另外寫出 `.audit.json`、`.audit.md`、`.bime.json`。輸出為 `proposal.bime.docx` 時，報告檔名是 `proposal.bime.audit.json`、`proposal.bime.audit.md`、`proposal.bime.bime.json`。
  - 輸出已存在時需要 `--overwrite`。
  - 結束碼：0 成功；1 已寫出但稽核有錯誤；2 為錯誤，訊息寫在 stderr。
  - 設定檔中有未知的 key 會報錯。
  - `--scope` 預設為 `fragment`。
- `~/.claude/skills/bime-word` 是 1.1.2 版，本計劃不使用。
- Conda 環境 `app`（`/home/minervamuses/miniconda3/envs/app`）：
  - 沒有 `docx`，也沒有 `lxml`。
  - 有 `pandoc` 3.13、`poetry`、`npm`、`cargo`。
- 技能探索只掃描 `skills_dir.glob("*/SKILL.md")`（`agent/skills/metadata.py:48`），所以 vendor 目錄中的 `SKILL.md` 不應被載入。R3 要確認這一點。

**文件**

- `/README.md` 第 100、101、132 行描述 Insert、Remove、三種匯出與 `.bib` 輸出位置。
- `app/skills/citation/README.md` 第 41、55 行提到 `export_bib` 與 BibTeX 匯出。

**測試基線**

- 2026-11-06 的紀錄：pytest 1736、npm 307、cargo 41，都是通過的測試數。
- 驗收標準是「全部通過」，不是固定的數字。R1 先核對既有紀錄的來源、版本與適用性，不重新跑完整套件；無可用紀錄時記為基線未知，僅做必要的局部檢查。完整套件留至 R6。

## 路線

| 階段 | 後置條件 | 相依 | 涵蓋 | 細節 |
|---|---|---|---|---|
| R1 | 確認分支、工作樹與工具狀態，記錄可沿用的測試基線及其限制；計劃檔已提交 | 無 | G8 | [phase-1-preflight.md](build/phase-1-preflight.md) |
| R2 | Insert 全部拆除；Remove 只在未引用區且有確認；BibTeX 匯出從前端、協定到後端全部移除 | R1 | G1、G2、G3 | [phase-2-remove-controls.md](build/phase-2-remove-controls.md) |
| R3 | 依賴與 vendor 完整性、doctor 檢查通過；正負試轉已執行並記錄結果，未通過的真實案例移交 R4-S3，不能視為 G5 通過 | R1 | G5（環境與試轉證據；真實案例由 R4 驗收） | [phase-3-bime-vendor.md](build/phase-3-bime-vendor.md) |
| R4 | 一個 Export 選單提供三種匯出；整合測試與真實 proposal 副本驗收通過；GUI 操作交付使用者確認 | R2、R3；R4-S3 另須 R3-S3 的正負案例通過 | G4、G5 | [phase-4-export-menu.md](build/phase-4-export-menu.md) |
| R5 | 面板預設收合成摘要列；編輯器 16px 並支援縮放與記憶；面板文字至少 0.9rem | R1；S2 另需 R2-S1 完成，S1 另需 R4-S2 完成 | G6、G7 | [phase-5-layout-font.md](build/phase-5-layout-font.md) |
| R6 | README 已更新；三套完整測試通過；最終彙報附手動 GUI 檢查清單 | R4、R5 全部完成 | G8、G9 | [phase-6-readme-acceptance.md](build/phase-6-readme-acceptance.md) |

正常順序仍是 R1→R2→R3→R4→R5→R6，依序修改 repo，不新增平行執行。遇到局部阻塞時，按實際步驟前提選下一個可執行項目，不讓階段編號阻止獨立工作。

上表與 `plan-index.json` 記錄進入階段的共同前提；各步驟的額外前提以階段檔為準。R5 可以先完成獨立的 S2，但缺少 S1 時不能將整個 R5 標為 Complete。R6 同時依賴 R4、R5 完成，避免 R5 先做完就略過真實匯出驗收。

| 可繼續的步驟 | 必須已具備的前提 | 不必等待的項目 |
|---|---|---|
| R4-S1／S2 整合 | R2 完成、R3 工具就緒與試轉結果已交接；S2 在 S1 通過後進行 | 真實 proposal 的 R4-S3 驗收 |
| R5-S2 字體與縮放 | R2-S1 完成，Insert／游標管線已拆除；無須等待 R2-S2／S3 | R3 的試轉問題、R4 的匯出整合／真實案例 |
| R5-S1 收合摘要列 | R2 完成且 R4-S2 的 Export 選單已完成 | R4-S3 的真實 proposal 驗收 |
| R6 最終文件與驗收 | R4、R5 的必要工作全部完成 | GUI 本人驗收結果（D14） |

## 檢查指令

以下指令都在撰寫時從現有檔案或記錄中得知。`P=/home/minervamuses/miniconda3/envs/app`。

| 檢查 | 指令（工作目錄） | 沙箱 |
|---|---|---|
| 前端測試 | `PATH=$P/bin:$PATH npm_config_cache=$TMPDIR/npm-cache npm test`（`app/desktop`） | 沙箱內可跑 |
| 前端建置與型別 | `PATH=$P/bin:$PATH npm_config_cache=$TMPDIR/npm-cache npm run build`（`app/desktop`） | 沙箱內可跑 |
| 指定的 Python 測試 | `$P/bin/python -m pytest -q -p no:cacheprovider <檔案>`（`app`） | 沙箱內可跑 |
| 完整 pytest | `TMPDIR=… XDG_CACHE_HOME=… AGENT_LOG_DIR=… $P/bin/python -m pytest -q -p no:cacheprovider`（`app`）；三個變數指向計劃 `evidence/` 下或 `$TMPDIR` 中可寫的新目錄 | **必須在沙箱外**（fixture 寫死 `/tmp`） |
| Rust 測試 | `PATH=$P/bin:$PATH CONDA_PREFIX=$P CONDA_DEFAULT_ENV=app cargo test --locked --manifest-path src-tauri/Cargo.toml`（`app/desktop`） | **必須在沙箱外** |
| 加入依賴 | `$P/bin/poetry add "python-docx>=1.2.0,<2.0" "lxml>=5.2,<7.0"`（`app`，Conda `app` 為目前環境） | 需要連到 PyPI；沙箱擋下時在沙箱外重跑 |

用管線把輸出接到 `tail` 時，以 `${PIPESTATUS[0]}` 判斷結束碼。

**檢查範圍與次數**：

- R1 優先沿用仍適用的歷史證據，記錄來源與差異；R2–R5 只跑修改相關的 Python 模組、前端測試檔、Rust 協定測試及必要建置。
- 前端局部指令：在 `app/desktop` 執行 `PATH=$P/bin:$PATH node --test --experimental-strip-types tests/citations.test.ts tests/citation_preview.test.ts tests/protocol.test.ts`，依本步修改只保留相關檔案；編輯器改動使用現有 `tests/documents.test.ts`，新增縮放測試時加入實際新增的測試檔。
- Rust 局部指令：在 `app/desktop` 執行 `PATH=$P/bin:$PATH CONDA_PREFIX=$P CONDA_DEFAULT_ENV=app cargo test --locked --manifest-path src-tauri/Cargo.toml protocol::tests`，並確認有測試執行；完整 Rust 套件留至 R6。
- 完整 pytest、`npm test`、完整 `cargo test --locked` 各最多一次，安排於 R6；預估任一命令超過十分鐘時先取得明確授權。開發中的局部檢查與建置只在相關修改後重跑，已通過且仍適用的證據沿用。
- 完整套件失敗後不自動重跑；若修正後需要第二輪完整驗收，記錄原因、預估耗時與用量，待使用者明確授權。啟動提示中的一般授權不包含這類追加成本。

## 執行契約

本文件只規定工作內容，本身不授權實作。只要求撰寫計劃時，交付審查過的計劃檔就結束。使用者明確以 [PROMPTS.md](PROMPTS.md) 的提示啟動本計劃後，執行者就在授權範圍內連續完成所有可執行的階段，包括一般的實作選擇、修正、檢查與計劃維護。這份授權在交接後仍然有效。宿主或工具的權限控制，以及使用者之後的變更，仍然優先。

**授權的動作**（啟動提示送出後）：

- 計劃列出的程式碼、測試、協定與文件修改，以及本地 commit。
- 以 Poetry 把 `python-docx>=1.2.0,<2.0`、`lxml>=5.2,<7.0` 加入 `app/pyproject.toml` 與 `app/poetry.lock`，並安裝到 Conda `app`，包括為此需要的 PyPI 連線。
- 讀取 `/home/minervamuses/論文/` 中的 bime_word zip 以及 `proposal.md`、`references.json`、`bime-proposal-profile.json`，複製到計劃 `evidence/` 或 `$TMPDIR` 後使用。
- 依上表執行相關局部檢查，並在 R6 各執行一次完整測試；仍須遵守耗時、重跑及宿主權限限制。

**未授權的動作**：

- 其他依賴、修改 `env-app.yml`。
- 寫入 `/home/minervamuses/論文/`（包括還原 `yao2023react`）。
- 修改 `~/.claude/skills/`、編輯 `for_agents/`。
- 付費模型呼叫、push、發佈，以及建立、切換、刪除或重新命名 branch，或建立 worktree。

**每一步的流程**：

1. 先讀 `AGENTS.md`、GOALS、本檔與 build-log，再依「可繼續的步驟」及階段檔的步驟前提核對實際狀態；有 Blocked 項目時仍檢查其他獨立步驟，不只沿階段編號尋找下一步。
2. 保留與本計劃無關的既有工作：不 stage 根目錄那些未追蹤的檔案。
3. 每個步驟做完必要檢查、更新 build-log 後，在本地 commit，成功之後才進入下一步。
   - commit 主旨格式為 `type(scope): summary [Rn-Sm]`，結尾加上宿主要求的 attribution。
   - 不把多個步驟合併成一個 commit，也不以未提交的修改結束。
   - 檢查失敗而保留證據時，用 `[Rn-Sm checkpoint]` commit。
   - `build/` 被 `.gitignore` 忽略，phase 檔以 `git add -f` 提交。
4. 需要保留的證據放在本計劃的 `evidence/<步驟ID>/`，不要只留在 `/tmp`。

**問題處理**：

- 先診斷，再做範圍內的最小修正；修正步驟加上新的步驟 ID，例如 `R4-F1`。
- 一次便宜的局部嘗試失敗時，先診斷原因；階段邊界本身不是停止條件。依 D15，局部阻塞只影響該問題與實際相依步驟，其他已滿足前提的工作繼續。
- 同一問題兩次聚焦修正仍失敗時，停止修正該問題，將問題與依賴它的步驟標為 Blocked。在 build-log 記錄嘗試次數、證據、受影響步驟及恢復條件，再繼續不相依且前提已滿足的工作；不得換步驟 ID 或換階段重置同一問題的次數。
- **「昂貴嘗試」只指付費 API 呼叫**；本專案中基本上只有 OpenRouter 的模型呼叫（D16）。本計劃不授權任何付費 API，所以某個步驟看起來需要呼叫時，視為需要追加授權：只隔離該動作，不嘗試呼叫。萬一仍發生一次付費呼叫，而且失敗或沒有實質改善，就停止整次執行並彙報，不自行再試。完整測試套件、`poetry add`、cargo 編譯這類本機或免費的操作不算昂貴嘗試，依兩次修正上限和十分鐘規則處理。沒有昂貴失敗時，只有剩餘工作都被阻塞或尚無必要授權、已無可執行的獨立步驟，才停止整次執行並彙報最小下一步。宿主限制與使用者明確停止指示仍優先。
- 任何約超過十分鐘的命令或完整套件追加重跑，須有具體成本說明與明確授權；等待新增授權時先隔離該動作，仍可做不依賴它的已授權工作。「一次執行到底」不授權突破這些成本限制。
- 既有測試失敗可以不阻止無關實作，但不因此降低「必要自動檢查全部通過」的完成標準。不要順便修復無關失敗；未解決時如實交付未完成項目，G8／R6 不標為 Complete，除非使用者明確變更驗收。
- 證據顯示路線需要改變時，先修改受影響、尚未開始或進行中的階段，以及 `plan-index.json` 的涵蓋關係，再繼續。不得自行修改使用者的目標、範圍外項目或驗收。
- 缺少無法自行解決的前提或需要新決定時，只封鎖受影響的工作並寫明恢復條件；局部問題達到兩次修正上限後，獨立工作仍須繼續。只有上述昂貴失敗／無可執行獨立步驟等整次停止條件才結束本次執行。
- 例如 R3-S3 的試轉問題被封鎖：保留已完成的 R2、R3 環境檢查與試轉紀錄，封鎖 R4-S3 的真實驗收；環境就緒時 R4-S1／S2 仍可做，R5-S2 可先做，R4-S2 完成後也可做 R5-S1。未通過的真實案例仍阻止 G5／R4 與 R6 完成。
- 階段內仍有可執行步驟時維持 In progress，逐項記錄 Blocked；剩餘步驟全被封鎖時才把該階段標為 Blocked。完成的步驟及其證據不因其他步驟受阻而撤銷。

**完成的判斷**：

- 代理交付完成須有實作、必要自動檢查及程式碼核對證據；寫完程式碼、結構檢查通過或 commit 本身不等於完成。GUI 實測依 D14 交由使用者，不是代理完成的前置條件。
- 略過或無法執行的必要自動檢查不算通過。GUI 手動項目記為「交由使用者驗收，尚無結果」，不算代理阻塞，也不宣稱已通過。
- 證據要標明是觀察到的、沿用的還是歷史紀錄。

**中斷後續作**：先以步驟 ID 對照 build-log 與 `git log`，核對工作樹、局部阻塞及實際步驟前提，再選擇可繼續的工作；同一問題的修正次數跨交接保留，只有記錄的恢復條件成立或使用者明確允許追加嘗試，才重開該問題。不重複已完成的動作。重跑 `poetry add` 前，先檢查 `pyproject.toml` 是否已有這兩個依賴。

## 代理交付完成

以下全部成立，代理即完成本計劃的交付；GUI 實測由使用者本人接手，不需等待其結果：

- R1–R6 的代理工作與必要自動檢查都有證據。R3 的環境就緒不能代替 R4-S3 的真實 proposal 驗收。
- G1–G9 的自動檢查／程式碼證據已記錄在 build-log；GUI 手動項目另列負責人與尚未回報的結果。
- 完整 pytest、npm test、npm run build、cargo test 都通過。
- 每一步都有本地 commit，工作樹中沒有本計劃留下的未提交修改。
- 最終彙報包含：手動 GUI 檢查清單、需要使用者決定的事項，以及「`for_agents/` 可能已過時」的提醒。
