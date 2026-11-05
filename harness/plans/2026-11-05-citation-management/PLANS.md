# 引用管理計劃

- **計劃位置**：harness/plans/2026-11-05-citation-management/
- **準備狀態**：可啟動。這是規劃交付，尚未有任何實作；各階段的執行狀態與實際證據只由 [build-log.md](build-log.md) 擁有。

## 閱讀與責任

| 文件 | 擁有內容 |
|---|---|
| [GOALS.md](GOALS.md) | 目標、決策來源、規劃假設、不變條件 |
| 本文件 | 基線、路線、執行契約、檢查與完成條件 |
| [PROMPTS.md](PROMPTS.md) | 啟動、續作、修訂、審查的入口提示 |
| build/phase-*.md | 各階段的步驟與驗收 |
| [build-log.md](build-log.md) | 目前狀態、事件、證據、阻塞 |
| [plan-index.json](plan-index.json) | 靜態相依圖 |
| [context/appendix17-references.md](context/appendix17-references.md) | 附件十七參考文獻規則原文與使用者的格式決定 |

不得把 index、GOALS 或 phase 檔變成第二份進度表。

## 觀察到的基線（2026-11-05，規劃時唯讀檢查）

- **Git**：repository research-agent-workspace，分支 GUI，HEAD `7c67a33`，tracked 與 index 乾淨。沙箱中 `git status` 會列出宿主掛載的佔位項目（`.bashrc`、`.claude/`、`.mcp.json`、`.vscode` 等），不是 repository 內容，絕不 stage。root `.gitignore` 第 8 行忽略 `build/`，所以本計劃的 `build/phase-*.md` 需要 `git add -f`。計劃目錄下的 `node_modules` **不**在忽略範圍內（`git check-ignore --no-index` 已確認），所以 npm 安裝不得放在 repo 內。
- **工具鏈**：Conda `app` 位於 `/home/minervamuses/miniconda3/envs/app`，Poetry 2.4.1。`app/env/env-app.yml` 目前只有 python 3.13、poetry、nodejs、rust。**這台機器沒有 Pandoc**（PATH 與 app、cui、manga 三個環境都沒有）。app 環境沒有 lxml。
- **測試基線**（2026-10-23，程式在 `0fabe25`，見 `for_agents/testing-strategy.md`）：pytest 1517、npm 260、cargo 40。完整 pytest 需要可寫的 `/tmp`，要在沙箱外執行並把 `TMPDIR`、`XDG_CACHE_HOME`、`AGENT_LOG_DIR` 導到暫存位置；cargo test 也要在沙箱外；npm test 可在沙箱內。標準是「全部通過」，不是固定數量。
- **文件編修現況**：
  - `document_edit` 每次只替換一段連續的 UTF-16 範圍；沒選取時範圍是整份文件（`app/agent/desktop/documents.py:189-208`）。實作在 `app/agent/desktop/service.py:2135-2215`；文件回合的提示文字在 `:2840-2853`。
  - 支援副檔名 `.md`、`.markdown`、`.tex`（`documents.py:17`）。
- **引用現況**：
  - 存檔流程在 `app/skills/citation/service.py:338-380`；DOI 存檔時先以 `fetch_structured` 抓 doi.org 的 CSL-JSON 確認身分（`app/skills/citation/providers/doi_org.py:138-159`，`parse_csl` 只留幾個欄位，原始資料丟棄），再抓 BibTeX。描述式存檔同樣以 doi.org CSL 複驗（`app/skills/citation/resolution.py:456`、`:599`）。
  - 沒有 DOI 的 arXiv 路徑在 `app/skills/citation/authority.py`，用 pybtex 自己組 BibTeX，沒有 CSL。
  - bundle 寫入 `resolve_output_dir` 決定的目錄（`app/skills/citation/storage.py`），桌面後端的 cwd 是 repo 根目錄，所以預設是 repo 的 `cite/`；以 identity 找既有 bundle 的函式是 `storage.py:305 _find_existing`。
  - `citation.save` 的批准在 `app/agent/desktop/service.py:2342-2361`。
  - `[[cite:…]]` 的檢查與渲染只作用在最終聊天回覆（`app/agent/skills/citation/session_policy.py:167`、`:190`）；渲染格式固定（`app/skills/citation/render.py`）。
- **專案 metadata**：`RESEARCH.md` 的 metadata 區塊目前只接受恰好 `version`、`historyDirectory` 兩個鍵（`app/agent/desktop/catalog.py:495-501`），多一個鍵就判為 malformed；初始化寫入在 `:651`。
- **協定**：`app/desktop/protocol/v1/contract.json` 有 34 個方法；新增方法的前例是 commit `d87ee6f`（`session.rename`），它同時改了 contract.json、fixtures.json、`src-tauri/src/protocol.rs`、`src/protocol.ts`、`service.py`、App.tsx 與 `tests/test_desktop_protocol_contract.py`。out-of-turn RPC 的批准前例是 `_knowledge_ingest_file`（`service.py:3362`，呼叫 `_require_operation_approval`，`:2333`）；回合內工具的批准 `_desktop_operation_approval` 在沒有進行中的回合時直接拒絕，不能用於回合外。忙碌時回 `BUSY_TURN` 的前例在 `service.py:945`、`:996`。
- **前端**：`app/desktop/src/SafeContent.tsx` 只渲染 text、code、strong、emphasis、link 五種 token，所以預覽可以用 `*斜體*` 表示期刊名的斜體。desktop 的 npm 相依沒有任何 citeproc 套件。
- **使用者論文（唯讀輸入）**：`/home/minervamuses/論文` 是獨立的 git repo（HEAD `59e9dc1`，工作區有使用者未提交的修改，例如 `proposal.docx`、`CLAUDE.md`）。HEAD 中：
  - `references.json`：69 筆 CSL-JSON，類型為 article-journal 28、paper-conference 23、article 10、webpage 7、software 1；52 筆有 DOI；沒有任何中日文條目。以 `json.dumps(data, ensure_ascii=False, indent=1) + "\n"` 重新序列化與原檔逐位元組相同（規劃時已驗證）。
  - `proposal.md`：用 Pandoc 的 `[@key]` 語法，約 46 個不同的 key。
  - `proposal.docx`：bime_word 依附件十七產生（commit `59e9dc1`「regenerate proposal.docx after the Appendix 17 reference fixes」），作為附件十七格式的比對基準。
  - `regulations.docx`：附件十七原文；參考文獻規則 二.8 已抄進 [context/appendix17-references.md](context/appendix17-references.md)。
- **未觀察**：Pandoc、citeproc-js、citeproc-py 的實際輸出；Pandoc 能否表達附件十七的分語言排序與「等人」；原生 GUI 的實際畫面。

## 依相依順序的路線

| 階段 | 單一後置條件 | 相依 | 目標 | 詳細 |
|---|---|---|---|---|
| C1 | 基線已記錄，Pandoc 在 Conda `app` 可用且寫入環境定義 | 無 | CG7、CG8 | [前置與 Pandoc](build/phase-1-preflight.md) |
| C2 | 專案書目庫可讀寫；桌面專案中的 `/citation` 存檔會併入書目並回報 key | C1 | CG1 | [書目庫](build/phase-2-library.md) |
| C3 | 正文 key 可解析與檢查；Agent 能查書目；`document_edit` 拒絕未知 key | C2 | CG2 | [正文引用與檢查](build/phase-3-citations-in-documents.md) |
| C4 | 內建樣式就位；Pandoc 的忠實度已與參考基準比較；後端能渲染與匯出 | C1 | CG4、CG5、CG7 | [渲染引擎與樣式](build/phase-4-rendering.md) |
| C5 | 附件十七 `.csl` 與 bime_word 基準比對完成，可表達的差異已修正 | C4 | CG6、CG4 | [附件十七樣式](build/phase-5-appendix17.md) |
| C6 | 六個 `bibliography.*` 協定方法在四份協定定義與後端都可用 | C3、C5 | CG3、CG4、CG5 | [協定與後端](build/phase-6-backend.md) |
| C7 | GUI 引用面板可管理、預覽、匯出 | C6 | CG3、CG4、CG5 | [GUI 面板](build/phase-7-gui.md) |
| C8 | 端到端驗收、文件、全套回歸與最終彙報完成 | C7 | CG1–CG8 | [驗收交付](build/phase-8-acceptance.md) |

- **建議順序**：C1 → C2 → C3 → C4 → C5 → C6 → C7 → C8。C4 只依賴 C1，若 C2 或 C3 阻塞，可先做 C4、C5。
- 先做 C2、C3，是因為「書目庫 + 正文 key 檢查」即使沒有 GUI 也已讓 Agent 寫出可驗證的引用；用量上限中斷時，最有價值的部分先提交。
- C6 與 C7 會修改同一組協定檔案，必須依序進行。

## 一次執行到底的契約

1. **授權邊界**：
   - [CA0] 只撰寫、驗證並本地 commit 本計劃。
   - 使用者送出 PROMPTS 的啟動提示後，執行者持續完成計劃列明的工作：範圍內的實作、修正、測試、計劃維護、依賴安裝（D4 核准的 Pandoc、citeproc-py、citeproc-js，依各階段的方式）與逐步 commit。
   - **使用者送出啟動提示，就代表授權整份計劃列明的全部工作**。執行中不再向使用者請求任何授權、確認或決定，也不提問。
   - 從啟動到最終彙報，任何時點都不停下來等使用者驗證、review、確認或授權（D8）。遇到問題就記錄在 build-log，依第 9、10 項處理後繼續；需要使用者決定的事只列入最終彙報。
   - 本文件的文字本身不授予權限；宿主的權限控制與使用者後來的指示優先。
2. **第一個動作**：見 [C1-S1](build/phase-1-preflight.md)。若分支不是 GUI：依 D8 不得切換，也不得在其他分支 commit，所以記為硬阻塞，只做唯讀檢查並寫最終彙報，不向使用者提問。確認本計劃所有檔案（GOALS、PLANS、PROMPTS、build-log、plan-index.json、context/appendix17-references.md、八份 build/phase-*.md）都通過 `git ls-files --error-unmatch -- <路徑>`；任一份沒有，就由執行者自己把它們提交為 `docs(plan): track citation management plan [CA0]`（phase 檔用 `git add -f`），然後繼續。
3. **檔案範圍**：
   - 可改：`app/skills/citation/**`（引用正確性）、`app/agent/skills/citation/**`、`app/agent/desktop/{service,catalog,documents}.py`（轉接）、`app/agent/session.py`（只限工具接線與把書目路徑傳給 citation 服務）、`app/desktop/protocol/v1/*`、`app/desktop/src/**`、`app/desktop/src-tauri/src/protocol.rs`、`app/desktop/tests/**`、`app/tests/**`、`app/env/env-app.yml`、`app/pyproject.toml`、`app/poetry.lock`、README 類文件、本計劃目錄。
   - 不改：`AGENTS.md`、`for_agents/**`（由 `$infrastructure` 管理，最終彙報提醒已過時）、`app/rag/**`、`app/agent/thinking/**`（D6）、`app/vendor/**`、desktop 的 `package.json`/`package-lock.json`（A8：citeproc-js 不進產品）。
   - 不讀寫 `app/store/` 的使用者對話。
4. **每一步強制 commit（D8）**：
   - 每個 C?-S? 完成 focused 檢查、更新 build-log（事件與頂端狀態表）後，立即在 GUI 本地 commit，成功後才開始下一步。不合併多步。
   - 檢查失敗、步驟被隔離或阻塞時，同樣 commit 一個保留證據的 checkpoint，subject 寫 `[C?-S? checkpoint]`；依賴該成功條件的步驟不得繼續。
   - 對 repository 的任何改動都要進入某個步驟的 commit：程式、測試、文件、manifest、evidence、build-log，以及第 12 項的計劃修訂。計劃修訂可以併入觸發它的步驟的 commit，或單獨提交為 `docs(plan): … [C?-S? replan]`。不得帶著未提交的改動進入下一步，整個執行也不得以未提交的改動結束。Conda 環境本身不在 repository 內，但記錄它的 `env-app.yml` 改動要提交。
   - subject 格式 `type(scope): outcome [C?-S?]`，body 說明改動、檢查與限制，結尾附 repository 規定的 attribution 行。
5. **commit 作法**：先看 `git status --short`、`git diff`、`git diff --cached --name-only`；只 `git add --` 本步的明確路徑（phase 檔用 `git add -f --`）；`git diff --cached --check`；不用 `git add .`，不帶入別人已 staged 的變更；不 force-add 生成資料（dist、node_modules、cache）；需要 hash 時以步驟 ID 反查 git log，不為記錄 hash 再 commit。
6. **禁止事項**：不 push；不建立、切換、刪除、重新命名 branch，不切到 detached HEAD，不建立 worktree；不改 Git identity、不繞過 hooks；不刪除未追蹤資料；不使用付費模型或服務（包括 OpenRouter 的模型回合）；不新增 D4 以外的依賴；不寫入使用者論文資料夾。
7. **宿主沙箱與網路**：
   - 完整 pytest 與 cargo test 在沙箱外執行，並把 `TMPDIR`、`XDG_CACHE_HOME`、`AGENT_LOG_DIR` 導到 `$TMPDIR` 下的子目錄（作法見 `for_agents/testing-strategy.md`）。
   - 需要連網的主機：`conda.anaconda.org`（Pandoc）、`registry.npmjs.org`（citeproc-js，只在 `$TMPDIR`）、`pypi.org` 與 `files.pythonhosted.org`（citeproc-py，僅條件步驟）、`raw.githubusercontent.com`（CSL 樣式檔）、`api.crossref.org`、`api.datacite.org`、`doi.org`（C8 的公開驗證存檔）。被宿主拒絕時記為環境阻塞，繼續其他工作。
   - 公開文獻 API 的預算：整個計劃最多 8 次存檔請求（每次一個 DOI 或 arXiv ID），全部在 C8-S1；已發出的請求記在 `evidence/C8-S1/requests.jsonl`，續作時不重發。
8. **證據**：需保留的證據放在本計劃的 `evidence/<步驟ID>/`；`$TMPDIR` 只放可重建的複本與安裝（論文副本、citeproc-js 的 node_modules）。論文正文不得進入 `evidence/`；可以提交計數、書目字串、渲染後的引用字串與差異。
9. **問題處理**：任何問題都不找使用者、不停下來等待。先記錄，提出單一因果假設，做最小修正，focused 重驗；同一問題最多兩次修正，仍失敗就隔離該步、記錄，繼續互不相依的工作。環境類失敗（沙箱、網路被拒）不消耗修正額度。不論上游是否阻塞，最後都執行 C8-S3 能做的部分與最終彙報。
10. **硬阻塞**：只有兩種：分支不是 GUI（第 2 項），以及 commit 失敗。commit 失敗時不宣稱已提交，也不累積下一步改動；先做不破壞他人狀態的修復，仍失敗就完成剩餘唯讀分析與紀錄，在最終彙報說明。硬阻塞同樣只記錄、不向使用者提問。宿主的權限提示不受本計劃控制，被宿主拒絕的動作記為環境阻塞，然後繼續其他工作。
11. **中斷與續作**：只依 build-log 與 git 實際狀態續作：以步驟 ID 對帳 git log；未提交的 diff 屬於哪一步，就從該步的檢查繼續；`$TMPDIR` 的複本與安裝不存在就依原步驟重建；公開請求以 `evidence/C8-S1/requests.jsonl` 為準。
12. **重新規劃**：證據顯示路線要改（例如 Pandoc 的 `--sandbox` 擋住必要的讀取），可直接修改尚未開始或進行中的階段與相依（不需問使用者），在 build-log 記錄原因，並依第 4 項提交；不得更改 GOALS 的目標、決策 D1–D8、範圍外項目或驗收強度。

## 檢查指令（從 `app/` 執行；實際路徑以 C1-S1 核對結果為準）

| 檢查 | 指令 | 環境 |
|---|---|---|
| focused pytest | `/home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider tests/<檔案>` | 沙箱內可 |
| 完整 pytest | 同上不帶檔案，`TMPDIR`、`XDG_CACHE_HOME`、`AGENT_LOG_DIR` 導到暫存目錄；以 `${PIPESTATUS[0]}` 判斷結束碼 | 沙箱外 |
| 前端測試 | `cd desktop && npm test` | 沙箱內可 |
| 前端建置 | `cd desktop && npm run build`（tsc + vite） | 沙箱內可 |
| Rust 測試 | `cd desktop && cargo test --locked --manifest-path src-tauri/Cargo.toml`，PATH 含 Conda app 的 bin | 沙箱外 |
| Pandoc | `/home/minervamuses/miniconda3/envs/app/bin/pandoc --version` | 沙箱內可 |

## 主要風險與待定事項

| ID | 風險或未定 | 影響 | 處理 | 阻擋 |
|---|---|---|---|---|
| R1 | Pandoc 在某些 CSL 行為上與 citeproc-js 不一致 | 渲染品質 | C4-S2 量化；核心類別不一致時執行條件步驟 C4-S3，結果列入最終彙報，產品仍用 Pandoc | 不阻擋 |
| R2 | 標準 CSL 表達不了附件十七的分語言排序、中文「等人」與全形標點 | CG6 只能部分達成 | C5 逐項列出；依 D3 不改走 `cite.py` | 不阻擋 |
| R3 | Crossref CSL 帶有非標準 type、HTML 標記的標題、ORCID 等欄位 | 書目污染或渲染錯誤 | C2-S1 白名單清理並對非標準 type 做固定對應；測試覆蓋 | C2 |
| R4 | `--sandbox` 若擋住讀取 `--csl`/`--bibliography` | 匯出失敗 | C4-S4 驗證；不行時改用只讀 stdin 與明確檔案、關閉遠端資源的替代旗標，記錄原因 | C4 |
| R5 | 修改 `RESEARCH.md` metadata（寫入 `citationStyle`）可能讓進行中的提交情境失效 | 送出失敗 | C6-S2 只允許閒置時寫入，並測試寫入後下一個回合仍能送出 | C6 |
| R6 | 原生 GUI 無法由執行者實際操作 | CG3 的視覺部分未觀察 | 以後端 RPC 與前端測試驗收，最終彙報附手動檢查清單 | 不阻擋 |
| R7 | Agent 實際插入 key 的行為需要付費模型回合 | 未做 live 驗證 | 以假模型/工具呼叫測試；列入手動檢查清單 | 不阻擋 |

## 完成條件

全部階段在 build-log 為 Complete，或被隔離的項目已在最終彙報中具體說明；CG1–CG8 的驗收都有觀察到的證據；全套 pytest、npm test、npm run build、cargo test 通過；每一步都有對應 commit；沒有 push、沒有切換 branch。被跳過或無法執行的必要檢查不算通過。
