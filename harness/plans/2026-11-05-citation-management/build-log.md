# 執行紀錄

本文件是本計劃唯一的狀態來源。

## 目前狀態

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| C1 | Complete | C1-S1 基線見事件；`evidence/C1-S2/` | — | — |
| C2 | Complete | C2-S1–S3 見事件 | — | — |
| C3 | Complete | C3-S1–S3 見事件 | — | — |
| C4 | In progress | C4-S1、C4-S2 見事件 | — | C4-S3（條件）|
| C5 | Not started | — | 依賴 C4 | — |
| C6 | Not started | — | 依賴 C3、C5 | — |
| C7 | Not started | — | 依賴 C6 | — |
| C8 | Not started | — | 依賴 C7 | — |

## 事件

每筆事件的格式：標題為步驟 ID（例如 `C2-S1`）與一句結果；內容列出改動、執行的檢查與結果、證據位置、限制、下一步。續作時以步驟 ID 對照 git log 的 commit subject。

### CA0 計劃撰寫（2026-11-05）

- **內容**：根據 2026-11-05 與使用者的討論撰寫本計劃（決策 D1–D8 見 GOALS）。
- **規劃時的唯讀檢查**：
  - 讀過 `for_agents/` 的架構、責任、資料流與 backlog；確認文件編修與引用流程的程式碼位置（見 PLANS 基線）。
  - 確認 Pandoc 不在本機；app 環境沒有 lxml；desktop 沒有 citeproc 相依。
  - 確認使用者論文 `references.json` 以 `indent=1`、`ensure_ascii=False` 加結尾換行重新序列化後逐位元組相同；69 筆、無中日文條目；`proposal.md` 約 46 個不同的 key；`regulations.docx` 即附件十七原文。
  - 確認 root `.gitignore` 忽略 `build/`，計劃目錄下的 `node_modules` 不被忽略。
- **未執行**：任何產品程式修改、依賴安裝、測試執行。

### CA0 撰寫檢查（2026-11-05）

- **結構檢查**：long-horizon-plan-author 的 `validate_plan.py`（只檢查檔案、連結與相依圖）回報 ok，14 個檔案，0 錯誤 0 警告；修正後重跑結果相同。它不證明內容正確或可行。
- **全新情境審查**：由一個沒有對話脈絡的唯讀子代理，以執行者的角度走查。它對照 HEAD 抽查了 20 個以上的程式碼位置，全部相符；也確認論文基線的數字（69 筆、52 筆有 DOI、`indent=1` 逐位元組相同、46 個 key）。它指出的缺口與處理：
  1. C8-S1 沒有建立 session、也沒切到 Bypass，`bibliography.add` 會卡在沒人回應的批准 → 已加入 `session.create` 與 `session.set_bash_permission`。
  2. `bibliography_lookup` 的接線沒點出 `document_edit` 的三個特例（`session.py:149-150`、`:661-663`、`service.py:2347`）→ 已寫進 C3-S3，並加上「不觸發批准」的測試。
  3. catalog 沒有改寫既有 metadata 的函式，且改寫會改變 `researchFingerprint` → 已寫進 C6-S2。
  4. `knowledge.ingest_file` 的位置指錯（`:1728` 是回合內的 slash 路徑）→ 改指 `_knowledge_ingest_file`（`:3362`）與 `_require_operation_approval`（`:2333`）。
  5. 書目路徑的注入點不明 → C2-S3 註明經由 `CitationSessionPolicy`；PLANS 的檔案範圍同步放寬 `session.py` 的說明。
  6. `bibliography.add` 在回合外如何取得批准與服務 → 已寫進 C6-S2。
  7. PROMPTS 沒提醒啟動前要先提交 [CA0] → 已加入。
  8. build-log 的事件格式 → 已加入說明。
- **限制**：審查者與撰寫者使用相同的資料來源；沒有實際執行任何計劃步驟。

### CA1 執行政策加嚴（2026-11-05，使用者指示）

- **使用者要求**：「每步改動皆要commit」；「不要停下來等人工授權，應該執行到底，我開始執行就代表授權整份計劃，有問題應該紀錄而不是找我」。
- **改動**：
  - PLANS 第 1 項：送出啟動提示 = 授權整份計劃，執行中不提問。
  - 第 2 項：計劃檔沒被追蹤時，由執行者自己補提交後繼續，不再判為硬阻塞。分支不是 GUI 時，只記錄並寫最終彙報。
  - 第 4 項：任何 repository 改動（含計劃修訂與 evidence）都要進入 commit，不得以未提交的改動結束。
  - 第 9、10、12 項：明文規定不找使用者；硬阻塞只剩兩種（分支不是 GUI、commit 失敗）。
  - PROMPTS 與 GOALS A10 同步修改；A10 註明 GUI 的批准是產品行為，與執行者無關。
- **檢查**：結構檢查重跑。

### C1-S1 唯讀核對與基線測試通過（2026-11-05）

- **Git**：`/home/minervamuses/research-agent-workspace`，分支 GUI，HEAD `6538f69`；tracked 與 index 乾淨（`git diff --cached --name-only` 空）。`git status --short` 只列出宿主掛載的佔位項目（`.bash_profile`、`.bashrc`、`.claude/`、`.gitconfig`、`.gitmodules`、`.idea`、`.mcp.json`、`.profile`、`.ripgreprc`、`.vscode`、`.zprofile`、`.zshrc`），不 stage。計劃 14 個檔案都通過 `git ls-files --error-unmatch`。
- **工具鏈**（`/home/minervamuses/miniconda3/envs/app/bin`）：Python 3.13.14、Poetry 2.4.1、node v24.18.0、npm 11.16.0、cargo/rustc 1.97.1。
- **基線測試**：
  - 完整 pytest（沙箱外，`TMPDIR`/`XDG_CACHE_HOME`/`AGENT_LOG_DIR` 導到 `/tmp/cm-base.*`）：1517 passed，2 warnings，52.6 s，exit 0。
  - `npm test`（沙箱內）：260/260 pass，exit 0。
  - `npm run build`（沙箱內）：exit 0（既有的 chunk > 500 kB 警告）。
  - `cargo test --locked`（沙箱外）：40 passed，exit 0。
- **既有失敗**：無。之後的回歸以此為準（全部通過）。
- **下一步**：C1-S2。

### C1-S2 Pandoc 3.13 已裝入 Conda app 並寫入 env-app.yml（2026-11-05）

- **安裝**：`conda install -y -n app -c conda-forge --freeze-installed "pandoc>=3,<4"`。沙箱內執行失敗（`OSError: [Errno 30] Read-only file system: ~/.cache/conda-anaconda-tos/...`，環境阻塞，不消耗修正額度），改在沙箱外執行成功。
- **路徑與版本**：`/home/minervamuses/miniconda3/envs/app/bin/pandoc`，pandoc 3.13（+server +lua）。
- **清單差異**（`evidence/C1-S2/conda-diff.txt`）：新增 `pandoc=3.13`；另外 `--freeze-installed` 仍更新了 `ca-certificates` 2026.7.22 → 2026.10.23 與 `openssl` 3.6.3 → 3.6.5（pandoc 的相依要求）。python、poetry、nodejs、rust 都沒變。以 `import ssl, httpx` 與 `tests/test_state.py` 檢查，SSL 正常（OpenSSL 3.6.5）。
- **小檔測試**：三筆 CSL-JSON + `[@smith2020deep; @lee2019robot]` 的 Markdown，`pandoc --citeproc -t plain` 輸出排好的引用與參考文獻（`smoke-plain.txt`，預設 Chicago author-date）；`pandoc -f csljson -t bibtex` 輸出三筆 `.bib`（`smoke-bibtex.bib`）。
- **env-app.yml**：加入 `- pandoc>=3,<4`；`conda env create --dry-run -n cm-dryrun-check -f app/env/env-app.yml` exit 0，解出 `pandoc==3.13`（`env-dryrun.txt`），沒有建立環境。
- **下一步**：C2-S1。

### C2-S1 驗證流程保留清理過的 CSL-JSON（2026-11-05）

- **改動**：
  - 新增 `app/skills/citation/csl.py`：`sanitize_csl`（CSL 1.0.2 書目變數白名單；人名只留 family/given/literal/suffix/兩種 particle，Crossref 的 `name` 轉 `literal`；標題類欄位只留 `<i>`/`<b>`/`<sup>`/`<sub>`，其他標記去掉並解 HTML entity；舊式 `event` 轉 `event-title`；一律不含 abstract、reference、license、link、funder、assertion、ORCID、affiliation、`id`），`normalize_type`＋固定對應表 `TYPE_MAP`（例：posted-content → article、journal-article → article-journal、proceedings-article → paper-conference；不認得的 → `document`），`csl_from_authority`（arXiv：type `article`、URL、`number` = arXiv ID、`publisher` = arXiv；NeurIPS：paper-conference），`minimal_csl`（只用已驗證的顯示欄位，供拿不到 CSL 的路徑用）。
  - `StructuredRecord.csl`（`parse_csl` 填入並把 `DOI` 設為正規 DOI；24 h 快取存的就是含 csl 的 record）；`ProviderRecord.csl`（預設 None；只有 doi.org 驗證後的 record 帶值）；`resolution.py` 兩處（精確 DOI、描述式複驗）把 csl 帶到 eligible record。
  - bundle 格式與寫入完全未動。
- **檢查**：新 `tests/test_citation_csl.py` 7 項通過（模擬 Crossref payload 含 abstract、reference、ORCID、`<i>`/`<scp>` 標題、posted-content；arXiv CSL；resolver 的 eligible record 帶 csl）。`test_citation_provider_doi_org.py`、`test_citation_authority.py`、`test_citation_storage.py`、`test_citation_save_outcomes.py` 與全部 `test_citation_*.py`：392 → 加入新檔後全部通過。`test_desktop_service.py` 在沙箱內有 1 項因 `/tmp` 唯讀失敗（既知環境限制，與本步無關；完整回歸在沙箱外跑）。
- **下一步**：C2-S2。

### C2-S2 書目庫模組（2026-11-05）

- **最終介面**（`app/skills/citation/library.py`）：`Library`（`path`、`items`、`layout`、`fingerprint`）、`MergeResult`（`status` = `added`/`existing`、`key`、`item`、`library`）、`load`、`fingerprint`、`serialize`、`parse_items`、`detect_layout`、`base_key`、`generate_key`、`item_doi`、`item_arxiv`、`find_existing`、`merge`、`write_atomic`、`add_item`；`LibraryError.code` ∈ `library_malformed`、`library_format_unsupported`、`library_conflict`、`library_write_failed`；`DEFAULT_LIBRARY_FILENAME = "references.json"`。
- **規則**：排版依序試 `indent=1`、`2`、`4`、`"\t"`（`ensure_ascii=False` + 結尾換行），新檔用 1；key = 第一作者 family（或 literal 第一個字）ASCII 化 + 年份（缺則 `nd`）+ 標題第一個非停用字，只含 `[a-z0-9]`，作者部分為空用 `ref`，撞名加 `a`…`z`、`aa`…；同 DOI（不分大小寫）或 arXiv ID（DOI `10.48550/arXiv.*`、`arxiv.org/abs|pdf/*` URL、或 publisher/container-title/archive 含 arXiv 時的 `number`）重用既有條目且不改動；`write_atomic` 寫入前（暫存檔 fsync 後、`os.replace` 前）再比對指紋，不符就 `library_conflict` 並刪暫存檔；保留檔案權限；fsync 目錄。
- **檢查**：新 `tests/test_citation_library.py` 18 項通過（模仿使用者格式的 fixture：1 空格縮排、`–`、`’`、手寫 webpage 與 literal 作者、arXiv URL 條目）。新增一筆時與原檔的 diff **只有新增行**（新條目插在原最後一筆的 `}` 之前，沒有任何既有行被改）。
- **論文副本驗證**（`$TMPDIR/thesis/`，論文 HEAD `59e9dc1`，只讀）：69 筆、偵測為 `indent=1`；在副本新增一筆得 `zed2025new`；以大寫 DOI 查第一筆得 `agrawal2024references`（重用）。產生規則對既有 69 筆有 23 筆與使用者手選 key 相同（其餘是使用者選了不同的標題字，例如 `agrawal2024references` vs 規則的 `agrawal2024language`）；既有 key 永不改，所以只影響新條目。
- **下一步**：C2-S3。

### C2-S3 存檔流程與桌面專案接上書目庫（2026-11-05）

- **改動**：
  - `skills/citation/types.py`：新增 `BibliographyLink`（`status` = `added`/`existing`/`failed`、`path`、`key`、`reason_code`）；`SaveItemOutcome.bibliography`（可選）。artifact 只在有書目結果時才多出 `bibliography` 鍵，所以 CLI 的 artifact 與工具文字不變；`from_artifact` 兩種形狀都接受。
  - `skills/citation/service.py`：`CitationService(..., library_path=None)`。全部 bundle 寫完後，對 saved/reused 的項目以驗證過的 CSL（doi.org 的清理版；authority 用 `csl_from_authority`；沒有 CSL 時用 `minimal_csl` 只取已驗證欄位）一次載入、逐項 `merge`、最多寫入一次。書目失敗只記在該項的 `bibliography`（`failed` + 代碼），bundle 的 saved/reused 不變。
  - `skills/citation/tool.py`：有書目結果時，在 JSON 之後附上「Project bibliography: <路徑>」、每項的 key 與狀態，並提示文件中用 `[@key]`（Markdown）或 `\cite{key}`（LaTeX），聊天回覆仍用 `[[cite:…]]`。
  - `agent/skills/citation/session_policy.py`：`CitationSessionPolicy(config, bibliography_path=<callable>)`，每次建 service 時才呼叫（metadata 改了下一個 Citation 任務就生效）；`None` 時不傳 `library_path`（CLI 完全不變）。
  - `agent/session.py`：`ChatSession.__init__`/`create` 只多一個轉接參數 `citation_bibliography_path`。
  - `agent/desktop/catalog.py`：metadata 接受可選 `bibliography`（相對路徑、`.json`、不得含 `..`、`~`、`$`、反斜線、URL scheme）與 `citationStyle`（非空、≤128 字元）；其他未知鍵仍 malformed；新增 `project_citation_settings(root)` 回傳 `bibliographyPath`（預設 `references.json`，解析後含 symlink 也必須在根目錄內）與 `citationStyle`。`inspect_project` 的回傳鍵不變（Rust 端驗證確切鍵集合）；`initialize_project` 不變。
  - `agent/desktop/service.py`：`_materialize_session` 在工廠接受時傳 `citation_bibliography_path`；`_project_bibliography_path` 只對已開啟的同一專案回傳路徑，metadata 有問題時記 log 並退回 bundle-only；`citation.save` 的批准描述在有書目時加上「Verified works are also added to the project bibliography <路徑>.」。
  - 測試配合：`tests/test_citation_e2e.py` 的假 `CitationService` 工廠接受 `library_path`，`_save_content` 用 `raw_decode` 讀 JSON（專案存檔會在 JSON 後附文字）；`tests/test_desktop_conversations.py` 的 `_CoordinatorFactory` 接受新參數。
- **檢查**：新 `tests/test_citation_project_library.py` 21 項通過：存一個 DOI → 書目只多尾端一筆、工具輸出含 key 與 `[@key]`/`\cite{key}`；再存 → 檔案逐位元組不變、同 key；手寫條目（大寫 DOI）被重用且不變；書目 malformed → bundle 仍 saved、書目回 `library_malformed`、檔案不變；CLI（無 library_path）→ artifact 無 `bibliography`、不產生 JSON 檔；policy 只在專案時傳 `library_path`；metadata：預設路徑、接受新鍵、10 種非法值與 symlink 逃逸皆 malformed、`initialize_project` 仍只寫兩鍵；桌面端到端（`/citation` 回合）→ 批准描述含書目路徑、`references.json` 建立且無 abstract。全部 `test_citation_*`、`test_desktop_*` 與完整 pytest（沙箱外）1563 passed，exit 0。
- **交付**：書目結果欄位 `items[].bibliography = {status, path, key, reason_code}`；metadata 鍵 `bibliography`、`citationStyle`；`project_citation_settings`。
- **下一步**：C3-S1。

### C3-S1 正文引用 key 解析器（2026-11-05）

- **介面**（`app/skills/citation/citekeys.py`）：`find_citations(text, fmt) -> list[CitationUse]`（`key`、`start`/`end` 為 UTF-16 offset、`line` 從 1 起、`group`；`to_dict()`），`keys_in`，`format_for_path`（`.md`/`.markdown` → markdown、`.tex` → latex），`LATEX_CITE_COMMANDS`。
- **作法**：先以 Pandoc 實測邊界（`@` 前為字母/數字含中文時不是引用；行首 `(@x)` 是 example list；`/@user` 的裸 URL 是引用；`@{含空白}` 不是引用），再寫解析器。Markdown 遮蔽 YAML front matter、fenced 與縮排 code block、行內 code、HTML 註解、autolink、`$`/`$$` 數學；註腳內的引用依 Pandoc 排在註腳參照的位置，未被參照的註腳定義略過。LaTeX：`\cite` 家族（含星號、0–2 個 `[...]`、多 key、`\nocite{*}` 略過），略過 `%` 註解（`\%` 除外）與 verbatim/lstlisting/minted/comment 環境。
- **交叉比對**（`evidence/C3-S1/crosscheck.py`、`crosscheck-result.jsonl`）：以 `pandoc -f markdown -t json` 的 Cite 節點 key 序列比較。
  - 合成語料 `synthetic.md`（36 次使用）、`ex.md`：完全相同。
  - 論文 `proposal.md`（`$TMPDIR` 複本，HEAD `59e9dc1`）：55 次使用、45 個不同 key，序列完全相同（規劃時的「約 46 個」實為 45）。
  - 修正兩輪：第一輪修 `@{含空白}`、縮排 code block、行中 `(@x)`；第二輪修註腳順序。
  - **已知限制**：同一個註腳被參照兩次時，Pandoc 會把註腳內容複製到每個參照處，所以 Pandoc 的使用次數較多（`footnote.md`：解析器 4、Pandoc 6）；key 集合與首次出現順序仍相同。
- **檢查**：新 `tests/test_citation_citekeys.py` 42 項通過（各語法、email、code、註解、數學、全形標點與中文前後文、emoji 的 UTF-16 位移、LaTeX 家族）；其中 26 個 Markdown 例子的期望值另以 Pandoc 逐一驗證相同。
- **下一步**：C3-S2。

### C3-S2 完整性報告（2026-11-05）

- **介面**（`app/skills/citation/integrity.py`）：`inspect(text, fmt, library_path, bundle_check=None) -> dict`、`bundle_checker(output_dir) -> (item -> bool)`、`entry_summary(item, verified)`。報告欄位（C6 直接序列化）：`format`；`bibliography {path, status: ok|missing|error, error {code, message}|null}`；`entries[] {key, authors, year, title, doi, type, verification: verified|unverified, citedCount, firstUse}`；`uses[] {key, start, end, line, group, known}`（書目讀不到時 `known` 為 null）；`order`（首次出現順序）；`missing[] {key, uses[] {start, end, line}}`；`uncited`；`duplicateDois[] {doi, keys}`。
- **驗證狀態**：條目的 DOI 或 arXiv ID 在 citation 輸出目錄有通過 `storage.validate_identity_bundle` 的 bundle 才是 `verified`（先以目錄名的 identity hash 建索引，不逐條掃描）；手寫條目、被竄改的 bundle 都是 `unverified`。
- **檢查**：新 `tests/test_citation_integrity.py` 6 項通過（缺 key 與位置、重複 DOI、首次出現順序、手寫為 unverified、有 bundle 為 verified、bundle 被改為 unverified、書目 malformed 回報錯誤不拋例外、書目不存在時全部 key 為缺漏、LaTeX）。
- **論文副本**（`evidence/C3-S2/thesis-report-summary.json`，只有數量與 key）：69 條目、55 次使用、45 個被引用 key、缺漏 0、未被 proposal 引用 24（書目與 thesis 共用，屬預期）、重複 DOI 0、verified 0（repo 的 `cite/` 目前沒有 bundle）。
- **下一步**：C3-S3。

### C3-S3 Agent 接線：bibliography_lookup 與未知 key 防護（2026-11-05）

- **改動**：
  - `agent/desktop/service.py`：新增唯讀工具 `bibliography_lookup(query)`（`_desktop_bibliography_lookup`；回傳 `status`、`path`、`exists`、`total`、最多 20 筆 `entries`，每筆 key、authors、year、title、doi、type、verification），與 `document_edit` 一起放進 `extra_tools`。`document_edit` 準備候選前呼叫 `_unknown_new_citation_keys`：以 `citekeys` 解析 replacement 與被替換的原範圍（UTF-16 切片），只看「新出現」的 key；不在書目的 → `{"status": "failed", "issue": …, "unknownKeys": […]}`，不準備候選、不發 `document.proposed`；書目讀不到時只擋有新 key 的修改。文件回合提示加上一句：用 key（`[@key]`/`\cite{key}`）、以 `bibliography_lookup` 找 key、不自行打作者年份或編號、不捏造 key、缺來源時建議 `/citation`。
  - `agent/session.py`（只做接線）：(1) `bibliography_lookup` 與 `document_edit` 一樣歸入 family `desktop_document`（所以 `service.py` 的批准判斷 `family != "desktop_document"` 不會要求批准）；(2) `tool_access_resolution` 在文件回合或 citation skill 啟用時把 `bibliography_lookup` 加入 effective tools（只在 session 的工具宇集有它時，即桌面）。
  - `skills/citation/library.py`：`search_bibliography(items, query, limit)`（完全相同的 key 優先，否則每個查詢字都要出現在 key/標題/作者/年份/DOI 中）。
  - `skills/citation/SKILL.md`：新增「Project bibliography (desktop projects)」一節。
  - `agent/thinking/**` 未改，`bibliography_lookup` 不在 `FUSION_READ_ONLY_ALLOWLIST`（D6）。
- **檢查**：新 `tests/test_desktop_citation_keys.py` 8 項通過：文件回合呼叫 `bibliography_lookup` 成功且沒有 `approval.required`；引入未知 key → failed、`unknownKeys`、沒有 `document.proposed`/`approval.required`、檔案不變；已知 key → 正常候選並存檔；原範圍已有的未知 key 保留不擋；書目壞掉時無 key 的修改照常、新增 key 的修改被擋；提示文字；不在 proposer 清單；citation 回合有效、CLI session 沒有此工具。既有 `test_desktop_document_service.py`、`test_desktop_documents.py`、`test_inline_skills.py`、`test_citation_skill_activation.py` 通過；完整 pytest（沙箱外）1619 passed，exit 0。
- **交付**：工具描述見 `service.py` 的 `_bibliography_tool`。
- **下一步**：C4-S1。

### C4-S1 內建樣式就位（2026-11-05）

- **來源**：CSL 官方樣式庫 `citation-style-language/styles`，commit `205bf7b617f9f8d48e4e0c2998b855eeae18fd65`（2026-11-04），以該 SHA 的 raw URL 下載，與當時 master 逐位元組相同；下載日 2026-11-05。四個檔案都是 independent style、`<rights>` 為 CC BY-SA 3.0，檔頭作者資訊原樣保留。
- **檔案**：`app/skills/citation/styles/{apa,modern-language-association,ieee,chicago-author-date}.csl`；清單 `styles.json`（`id`、`name`、`file`、`kind`、`origin`，以及來源 repository、commit、日期、授權）。`kind` 取自各檔的 `citation-format`：APA、Chicago 為 author-date，MLA 為 author，IEEE 為 numeric。
- **檢查**：以 C1-S2 的三筆小檔，四個樣式各自 `pandoc --citeproc` 成功（exit 0），四份輸出的雜湊互不相同（`evidence/C4-S1/*.txt`）。`poetry build -f wheel -o <暫存目錄>` 產生的 wheel 含四個 `.csl` 與 `styles.json`（`evidence/C4-S1/wheel-contents.txt`）；wheel 建在暫存目錄後刪除，`app/dist/` 未動（該目錄本來就被 `.gitignore` 忽略）。
- **下一步**：C4-S2。

### C4-S2 Pandoc 與 citeproc-js 比較（2026-11-05）

- **基準安裝**（只在 `$TMPDIR/cpjs`，不進 repo、不進 desktop 的 `package.json`）：npm `citeproc` 2.4.63（`--save-exact`；`package.json`、`package-lock.json` 複製到 evidence，node_modules 不提交）。沙箱內 `~/.npm` 唯讀（EROFS），以 `npm_config_cache=$TMPDIR/npm-cache` 解決（環境問題）。en-US locale 取自 `citation-style-language/locales` commit `8bef426f89f38c0789223c50e53ec2197bc50bb3`。
- **語料**（`corpus.json`，16 案例）：1、2、3、8、21 位作者；同作者同年；同姓不同名；機構作者；`van der` 前綴；缺年份；頁碼與章節 locator；省略作者；一次多篇；數字制首次出現順序與多篇；標題大小寫；會議論文 DOI 與網頁 URL/accessed。
- **腳本**：`citeproc_js.js`（`rebuildProcessorState` 取最終引用字串、`makeBibliography`）、`pandoc_run.py`（每個 cluster 一段，`--citeproc -t json` 取 Cite 節點與 `#refs`，再轉 plain）、`compare.py`（NFC 與空白正規化後逐字串比較、分類）。輸出 `out-citeproc-js.json`、`out-pandoc.json`、`comparison.json`、`summary.md`。
- **結果**：64 組（4 樣式 × 16 案例）中 63 組完全一致；**Pandoc 在核心類別（作者清單/et al.、消歧、排序/編號、locator）的不一致數 = 0**。唯一差異：MLA 的 `[-@key]` 無頁碼時，Pandoc 輸出空字串、citeproc-js 輸出 `[NO_PRINTED_FORM]`（類別「其他」）。另記：此版 IEEE 樣式的多篇引用兩邊都是 `[1], [2], [3], [4]`（不合併成範圍），計劃寫的「[1]–[3]」與官方樣式不同，以樣式為準；APA 不會把小寫標題改成句首大寫（CSL 只能轉大寫），兩邊一致。
- **下一步**：C4-S3 的觸發條件（核心類別不一致）未成立。

## 最終彙報

（C8-S3 完成後填寫。）
