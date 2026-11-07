# 引用面板改版：路線與執行契約

- **計劃根目錄**：`harness/plans/2026-11-07-citation-panel-revamp/`（相對於 repo 根目錄 `/home/minervamuses/research-agent-workspace`）
- **目標與決策**：[GOALS.md](GOALS.md)
- **目前狀態與證據**：[build-log.md](build-log.md)，這是唯一的狀態來源
- **啟動入口**：[PROMPTS.md](PROMPTS.md)

## 任務規模

本計劃主要修改桌面前端（React），另外有少量 Python 後端修改、一個協定欄位的修改、新增兩個依賴，以及 vendor 一個本地工具。風險集中在兩處：

1. 協定修改會牽動 Python、TypeScript、Rust 三方的契約測試。
2. bime_word 必須在桌面後端的子行程中跑起來。

GUI 沒有自動化操作視窗的方法，所以 GUI 的行為以單元測試和建置驗收，最終彙報附上手動檢查清單。

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
  - Monaco 的 `fontSize: 14` 寫死在第 183 行。
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
  - `desktop/src-tauri/src/protocol.rs`（所以修改契約後 cargo 測試為必要）
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
- 驗收標準是「全部通過」，不是固定的數字。R1 會重新量測。

## 路線

| 階段 | 後置條件 | 相依 | 涵蓋 | 細節 |
|---|---|---|---|---|
| R1 | 確認分支、工作樹與工具狀態，記錄三套測試的基線；計劃檔已提交 | 無 | G8 | [phase-1-preflight.md](build/phase-1-preflight.md) |
| R2 | Insert 全部拆除；Remove 只在未引用區且有確認；BibTeX 匯出從前端、協定到後端全部移除 | R1 | G1、G2、G3 | [phase-2-remove-controls.md](build/phase-2-remove-controls.md) |
| R3 | `python-docx`、`lxml` 已加入 `app`；bime_word 1.1.5 已 vendor 並通過完整性檢查；從 app 環境能轉出 proposal 副本 | R1 | G5 | [phase-3-bime-vendor.md](build/phase-3-bime-vendor.md) |
| R4 | 一個 `Export ▾` 選單提供 Word（一般）、Word（系上格式）、Markdown；後端能以 vendor 的 bime_word 寫出 `<檔名>.bime.docx` | R2、R3 | G4、G5 | [phase-4-export-menu.md](build/phase-4-export-menu.md) |
| R5 | 面板預設收合成摘要列；編輯器 16px 並支援縮放與記憶；面板文字至少 0.9rem | R4 | G6、G7 | [phase-5-layout-font.md](build/phase-5-layout-font.md) |
| R6 | README 已更新；三套完整測試通過；最終彙報附手動 GUI 檢查清單 | R5 | G8、G9 | [phase-6-readme-acceptance.md](build/phase-6-readme-acceptance.md) |

R2 和 R3 互不相依，但都會修改 repo，所以依序執行：先 R2，再 R3。R5 放在 R4 之後，因為摘要列需要包含 R4 的 `Export ▾`。

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

## 執行契約

本文件只規定工作內容，本身不授權實作。只要求撰寫計劃時，交付審查過的計劃檔就結束。使用者明確以 [PROMPTS.md](PROMPTS.md) 的提示啟動本計劃後，執行者就在授權範圍內連續完成所有可執行的階段，包括一般的實作選擇、修正、檢查與計劃維護。這份授權在交接後仍然有效。宿主或工具的權限控制，以及使用者之後的變更，仍然優先。

**授權的動作**（啟動提示送出後）：

- 計劃列出的程式碼、測試、協定與文件修改，以及本地 commit。
- 以 Poetry 把 `python-docx>=1.2.0,<2.0`、`lxml>=5.2,<7.0` 加入 `app/pyproject.toml` 與 `app/poetry.lock`，並安裝到 Conda `app`，包括為此需要的 PyPI 連線。
- 讀取 `/home/minervamuses/論文/` 中的 bime_word zip 以及 `proposal.md`、`references.json`、`bime-proposal-profile.json`，複製到計劃 `evidence/` 或 `$TMPDIR` 後使用。
- 依上表在沙箱外執行完整 pytest 與 cargo 測試。

**未授權的動作**：

- 其他依賴、修改 `env-app.yml`。
- 寫入 `/home/minervamuses/論文/`（包括還原 `yao2023react`）。
- 修改 `~/.claude/skills/`、編輯 `for_agents/`。
- 付費模型呼叫、push、發佈，以及建立、切換、刪除或重新命名 branch，或建立 worktree。

**每一步的流程**：

1. 先讀 `AGENTS.md`、GOALS、本檔、build-log 與目前相依已滿足的階段檔，再核對實際狀態。
2. 保留與本計劃無關的既有工作：不 stage 根目錄那些未追蹤的檔案。
3. 每個步驟做完必要檢查、更新 build-log 後，在本地 commit，成功之後才進入下一步。
   - commit 主旨格式為 `type(scope): summary [Rn-Sm]`，結尾加上宿主要求的 attribution。
   - 不把多個步驟合併成一個 commit，也不以未提交的修改結束。
   - 檢查失敗而保留證據時，用 `[Rn-Sm checkpoint]` commit。
   - `build/` 被 `.gitignore` 忽略，phase 檔以 `git add -f` 提交。
4. 需要保留的證據放在本計劃的 `evidence/<步驟ID>/`，不要只留在 `/tmp`。

**問題處理**：

- 先診斷，再做範圍內的最小修正；修正步驟加上新的步驟 ID，例如 `R4-F1`。
- 首次嘗試失敗或到了階段邊界，都不是停下來的理由；可以先做不相依的工作。
- 證據顯示路線需要改變時，先修改受影響、尚未開始或進行中的階段，以及 `plan-index.json` 的涵蓋關係，再繼續。不得自行修改使用者的目標、範圍外項目或驗收。
- 只有在缺少無法自行解決的前提，或遇到必須由使用者決定的事時，才停下受影響的工作，並寫明恢復需要什麼。其餘工作照常進行，需要使用者決定的事放進最終彙報。

**完成的判斷**：

- 只能依觀察到的驗收結果判斷完成；寫完程式碼、結構檢查通過或 commit，都不等於完成。
- 略過或無法執行的必要檢查不算通過。
- 證據要標明是觀察到的、沿用的還是歷史紀錄。

**中斷後續作**：先以步驟 ID 對照 build-log 與 `git log`，核對工作樹，再決定從哪裡繼續，不重複已完成的動作。重跑 `poetry add` 前，先檢查 `pyproject.toml` 是否已有這兩個依賴。

## 整體完成

以下全部成立，本計劃才算完成：

- R1–R6 的必要驗收都有觀察到的證據。
- G1–G9 各自的成功觀察都已記錄在 build-log。
- 完整 pytest、npm test、npm run build、cargo test 都通過。
- 每一步都有本地 commit，工作樹中沒有本計劃留下的未提交修改。
- 最終彙報包含：手動 GUI 檢查清單、需要使用者決定的事項，以及「`for_agents/` 可能已過時」的提醒。
