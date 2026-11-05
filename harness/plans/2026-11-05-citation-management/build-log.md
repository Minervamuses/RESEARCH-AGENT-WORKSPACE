# 執行紀錄

本文件是本計劃唯一的狀態來源。

## 目前狀態

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| C1 | Complete | C1-S1 基線見事件；`evidence/C1-S2/` | — | — |
| C2 | Complete | C2-S1–S3 見事件 | — | — |
| C3 | Complete | C3-S1–S3 見事件 | — | — |
| C4 | Complete | C4-S1–S4 見事件 | — | — |
| C5 | Complete | C5-S1–S3 見事件 | — | — |
| C6 | Complete | C6-S1、C6-S2 見事件 | — | — |
| C7 | Complete | C7-S1–S3 見事件 | — | — |
| C8 | In progress | C8-S1 見事件 | — | C8-S2 文件 |

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

### C4-S3 citeproc-py 評估：未觸發（2026-11-05）

- **判定**：觸發條件是 C4-S2 中 Pandoc 在核心類別有不一致；實際為 0，所以不安裝 citeproc-py，`app/pyproject.toml`、`app/poetry.lock` 未動（`git diff --quiet HEAD` 確認）。產品照 A8 只用 Pandoc。
- **下一步**：C4-S4。

### C4-S4 渲染與匯出模組（2026-11-05）

- **介面**（`app/skills/citation/csl_render.py`）：`list_styles()`、`style_path(id)`、`find_pandoc()`（先找執行中 Python 旁的 Conda `bin/pandoc`，再找 PATH）、`render(text, library_path, style_id) -> Rendered`（`to_dict()` = `{styleId, citations[] {index, keys, start, end, text, segments}, bibliography[] {key, text, segments}, missing}`）、`export_markdown`、`export_docx(..., resource_dir=None)`、`export_bib`；`RenderError.code` ∈ `pandoc_unavailable`、`pandoc_failed`、`pandoc_timeout`、`style_unknown`、`library_*`。
- **作法**：Pandoc 子程序、不經 shell、正文走 stdin、逾時 60 s。citeproc 一律 `--sandbox`（R4 實測：`--sandbox` 下仍能讀命令列指定的 `--csl` 與 `--bibliography`，遠端與本地圖片都不讀）。逐筆引用取自 JSON AST 的 Cite 節點，並以 C3-S1 解析器的群組（key 序列比對）對回原文 UTF-16 位置；參考文獻取自 `#refs` 的 `ref-<key>` 條目。書目檔不存在時不傳 `--bibliography`，全部 key 列為 missing。
- **與擬定介面不同之處（執行者調整，理由）**：
  1. 預覽字串改為結構化 `segments`（`{text, italic?, bold?, url?}`）加純文字 `text`，不輸出 Markdown：`SafeContent.tsx` 沒有跳脫語法，網址或標題中的 `_`、`*` 會被誤判成斜體；C7 直接用 segments 產生元素。
  2. `.bib` 用 `-t bibtex` 而不是 `biblatex`：bibtex 格式（`year`、`journal`）BibTeX 與 biblatex 都能讀，biblatex 格式（`date`、`journaltitle`）在傳統 BibTeX 樣式下會缺欄位。
  3. docx 匯出：citeproc 在 `--sandbox` 下產生 AST，遠端圖片改成連結（永不抓取），再以文件所在資料夾為 `--resource-path` 執行 docx writer，所以本地圖片會嵌入；沒給 `resource_dir` 時 writer 也用 `--sandbox`、不嵌入任何圖片。
  4. 已排版 Markdown：`-t markdown-citations-smart` 並先拆掉 Div/Span 包裝（否則會留下 `:::`、`{.csl-…}` 或 HTML `<div>`）；Pandoc 會把 `[1]` 跳脫為 `\[1\]`（合法 Markdown）。
- **檢查**：新 `tests/test_citation_csl_render.py` 13 項通過：APA 與 IEEE 的引用與參考文獻都不同、正文雜湊與書目檔位元組不變；IEEE 參考文獻 = 首次出現順序、APA 依作者排序；引用的 UTF-16 位置對回原文；segments 帶斜體與 DOI 連結；缺 key 回報 missing 不崩潰；書目檔不存在；docx 可用 `zipfile` 開啟、`word/document.xml` 含渲染後引用且無 `@key`；遠端圖片沒送進 writer 當 Image、docx 只嵌入本地圖；Markdown 匯出無 `[@`、無 div；`.bib` 可被 pybtex 解析且含 DOI；Pandoc 不存在 → `pandoc_unavailable`；未知樣式、書目 malformed。範例輸出在 `evidence/C4-S4/`（合成正文）。
- **下一步**：C5-S1。

### C5-S1 附件十七比對基準（2026-11-05）

- **輸入**：論文 repo HEAD `59e9dc1d5096f5f0b7767a4654ca4753ca88012f` 的 `proposal.md`、`proposal.docx`、`references.json`（`git show` 複本放 `$TMPDIR/thesis/`，未寫回論文資料夾）。
- **作法**（`evidence/C5-S1/build_oracle.py`，只用 `zipfile` + ElementTree + Pandoc）：參考文獻 = docx 中樣式為 `Bibliography` 的段落（依 docx 順序）。正文引用：把 `proposal.md` 的 Cite 節點換成哨兵字元後以 Pandoc 轉成純文字，每一行建成「字面文字 + `(.*?)`」的正則，與 docx 段落完全比對，取出各引用位置的字串。bime_word 會略過 `[TODO: …]` 註記與清單符號，比對時同樣去掉（不放寬其他規則）。
- **結果**（`evidence/C5-S1/oracle.json`，只含書目字串與引用字串，不含正文）：docx 參考文獻 42 條；Markdown 有 50 個引用群組、45 個不同 key；其中 4 個群組位在 TODO 註記內，`cohen1960kappa`、`mcnemar1947`、`wilson1927` 只出現在 TODO 中，所以 docx 沒有它們。TODO 以外 42 個不同 key = docx 42 條（相符）。46 個非 TODO 群組全部對齊，對不到的 key：無。
- **下一步**：C5-S2。

### C5-S2 fix：無法重現排版的書目仍可讀取（2026-11-05）

- **問題**：C5-S2 以緊湊 JSON（無縮排）的書目測試附件十七樣式時，`render` 回 `library_format_unsupported`。原因：C2-S2 的 `load` 在偵測不到排版時直接拋錯，但預覽、檢查、查詢都是唯讀，排版只影響寫入。
- **修正**（單一因果、最小改動）：`library.load` 對未知排版回傳 `layout=None`；`write_atomic` 在 `layout is None` 時才拋 `library_format_unsupported`，檔案不變。所以 C2 的「格式不明時不寫入」保持不變，而 `render`、`inspect`、`bibliography_lookup` 與同 DOI 重用（不需寫入）都能使用 Zotero 等匯出的緊湊檔。
- **檢查**：`tests/test_citation_library.py` 新增 `test_unknown_layout_is_readable_and_reuse_needs_no_write`；原 `test_unknown_layout_is_not_written` 仍通過（新增條目時拋錯、檔案不變）。`test_citation_library.py`、`test_citation_project_library.py`、`test_citation_integrity.py`、`test_citation_csl_render.py` 共 60 項通過。

### C5-S2 附件十七 `.csl` 與基準比對（2026-11-05）

- **樣式**：`app/skills/citation/styles/bime-appendix17.csl`（ID `bime-appendix17`，列入 `styles.json`，`origin: custom`，CC BY-SA 3.0，結構參考 `chicago-author-date.csl`）。規則：作者全列、第一作者倒置、名字縮寫、`, and`；`年.`；期刊名 `container-title-short`（無則全名）、`卷(期): 頁`；頁碼用連字號（樣式內 locale 覆寫 `page-range-delimiter`，`page-range-format="expanded"`）；會議錄 `In “…” (叢書), 頁. 編者, eds. 地: 出版者`，無頁碼且無出版者時 `Available at:`；章節、書、學位論文、軟體 `Ver.`、網頁 `Available at:`/`Accessed 日 月 年`、專利、其他（arXiv 照 `number` 原樣）；沒有作者時以 publisher 代替；逗號在引號外（`punctuation-in-quote="false"`）。文中 `(Smith, 1985)`、`(Smith and Kline, 1968)`、三人以上 `et al.`、同作者同年 a/b、多篇以 `; ` 分隔且不合併。排序：第一作者姓氏、全部作者姓氏、年、標題。
- **比對**（`evidence/C5-S2/compare_appendix17.py`、`comparison.json`、`compare.md`）：四輪。最後一輪引用 **46/46**、參考文獻 **32/42**（排序 42/42 全對）。其餘 10 條全屬四類無法以 CSL 表達者：撇號 `'`→`’`（6 條，Pandoc 與 citeproc-js 都會換）、`Wen-tau`→`W.`（3 條，兩個處理器相同）、literal `"et al."` 名字前多 `and`（1 條）、名字括號暱稱 `(Hank)`（1 條）；後三類可由資料修正，但依 D3 與「不改使用者 references.json」只記錄。
- **連帶修正**：`csl_from_authority` 的 arXiv 條目改為 `number = "arXiv:<id>"`、不設 publisher（與論文既有條目的寫法一致，附件十七樣式照樣輸出 `arXiv:…`）；`library.item_arxiv` 對 `arXiv:` 前綴的 `number` 不再要求 arXiv 出版者。測試同步更新（`test_citation_csl.py`、`test_citation_library.py`）。
- **檢查**：新 `tests/test_citation_appendix17.py` 4 項通過（附件十七原文英文範例：期刊 (a)、會議錄 (8)、網站 NSC、軟體 SAS、博士論文 Campbell，以及 (4) 的文中引用形式、排序）。第 4 輪的「Available at」修正就是這組測試發現的。
- **下一步**：C5-S3。

### C5-S3 附件十七中日文規則的合成測試（2026-11-05）

- **作法**：論文語料沒有中日文條目，另建合成語料 `evidence/C5-S3/cjk_corpus.json`（二.8 例 (d)(e)(6)(8b)(10)(12) 的中文條目、一筆日文、一筆英文），以附件十七原文為預期；`run_cjk.py` 渲染並逐條判定，輸出 `results.md`、`output.json`。
- **實測限制**：Pandoc 不會依條目 `language` 切換 locale 用詞；CSL-M 的多個 `<layout>` 被 Pandoc 拒絕（`CiteprocParseError: Multiple layout elements`）。標準 CSL 只能測「有沒有」某欄位，所以樣式以 `<if variable="language">` 切換中日文分支：姓名相連、`、` 分隔、`與`、`等人`（覆寫 `and others` 詞，只有中日文分支使用）、全形 `。`/`：`/`，`、`出自〝…〞`、`主編`、`網址：`、`上網日期：YYYY-MM-DD`；排序加上 `language` 降冪鍵（zh → ja → 其他 → 無 language 的英文）。
- **連帶改動**：`sanitize_csl` 只保留 `zh`/`ja` 開頭的 `language`（Crossref 的 `en` 會被丟掉，否則英文條目會誤入中日文分支）；新增測試。使用者既有 `references.json` 沒有任何 `language` 欄位，所以論文比對不受影響（重跑 C5-S2：引用 46/46、參考文獻 32/42 不變）。
- **結果**（14 條規則）：達成 11（中文二人 `與`、一人與機構、日文、中英混合、(5)(d)(e)(6)(8b)(10)(12) 六種中文條目格式、語言分組〔需 `language` 欄位〕）；部分達成 1：中文三人以上輸出 `(田 等人，1989)`，`等人` 前多一空白（處理器在 et-al 詞前固定加空白；改用 `and` 符號詞可讓 `等人` 緊接，但二人的 `與` 前後會多空白，兩者不能同時正確，實測後選擇讓二人形式正確）；無法以標準 CSL 表達 2：中日文依筆畫排序（Pandoc 只用 Unicode 排序規則）、全中文群組內以全形 `；` 分隔（layout 層級分隔符號）。
- **檢查**：`tests/test_citation_appendix17.py` 新增中文分支測試（共 5 項）；`tests/test_citation_csl.py` 新增 language 測試；兩檔 13 項通過。
- **補記**：C5-S2 所述 `library.item_arxiv` 對 `arXiv:` 前綴的改動與其測試，實際上已隨 `4f026b3`（`[C5-S2 fix]`）一起提交，不在 `4ded113`（`[C5-S2]`）中；內容相同，只是落在前一個 commit。
- **交付**：樣式 ID `bime-appendix17`；已知限制見 `evidence/C5-S2/compare.md` 與 `evidence/C5-S3/results.md`。
- **下一步**：C6-S1。

### C6-S1 協定定義（2026-11-05）

- **方法**（`protocolVersion` 仍為 1，加法式成長；contract 方法 34 → 40、resultDataSchemas 22 → 28）：
  - `bibliography.inspect`（read）：params `documentContext?`；result `libraryPath`、`libraryStatus` (`ok`/`missing`/`error`)、`libraryFingerprint?`、`libraryErrorCode?`、`libraryError?`、`styleId`、`styleConfigured`、`styles[] {id, name, kind, origin}`、`documentFormat?` (`markdown`/`latex`)、`entries[] {key, authors[], year?, title, doi?, type, verification, citedCount}`、`uses[] {key, start, end, line, group, known?}`、`order[]`、`missing[]`、`uncited[]`、`duplicateDois[] {doi, keys[]}`。
  - `bibliography.render`（read）：params `documentContext`、`styleId?`；result `styleId`、`citations[] {index, keys[], start?, end?, text}`、`entries[] {key, text}`、`segments[] {entry, text, italic, bold, url?}`、`missing[]`。
  - `bibliography.set_style`（mutation）：`styleId` → `{styleId, researchFingerprint}`。
  - `bibliography.remove`（mutation）：`key`、`libraryFingerprint` → `{key, libraryFingerprint}`。
  - `bibliography.add`（mutation）：`identifier` → `{status: added|existing|failed, key?, reasonCode?, libraryFingerprint?}`。
  - `bibliography.export`（mutation）：`documentContext?`、`format` (`docx`/`markdown`/`bib`)、`styleId?` → `{format, path}`。
  - 新錯誤碼 2 個：`BIBLIOGRAPHY_CONFLICT`（書目檔在讀取後被改動）、`BIBLIOGRAPHY_FAILED`（書目讀不到/無法寫入、Pandoc 不可用或失敗）。其餘沿用 `PROTOCOL_INVALID`、`BUSY_TURN`、`APPROVAL_DENIED`、`SESSION_NOT_READY`。
- **與擬定形狀的差異**：Rust 的結果驗證是手寫的，契約測試只檢查一層 objectArray，所以結果都保持「頂層欄位 + 平坦的 objectArray」：參考文獻格式以頂層 `segments`（以 `entry` 索引對應）表示，不巢狀；`inspect` 不回 `firstUse`（GUI 由 `order` 取得）、`missing` 只列 key（位置由 `uses` 中 `known=false` 取得）；`year` 用 nullableString。
- **四份定義**：`contract.json`（以文字插入，未重排既有內容）、`src/protocol.ts`（由 contract 產生的 schema 文字、方法與錯誤碼清單）、`src-tauri/src/protocol.rs`（方法、錯誤碼、required/allowed params、參數檢查、`validate_bibliography_result`）、Python 由 contract 驅動。`fixtures.json` 新增 21 個 messages（每個方法合法 request/result 與非法例）與 8 個 traces（5 個非法 result 需要配對的 request 才能依方法驗證，另 3 個合法 trace）。
- **檢查**：`tests/test_desktop_protocol_contract.py` 204 passed；`npm test` 289/289；`npm run build` 成功；`cargo test --locked`（沙箱外）40 passed（含由 contract 產生樣本與邊界值的測試、fixtures 測試）。三種驗證器對每個新 fixture 結果一致。
- **下一步**：C6-S2。

### C6-S2 後端實作（2026-11-05）

- **轉接**（`agent/desktop/service.py`）：六個處理器，`bibliography.*` 列入需要已開啟專案的 project operation。共用：`_citation_settings`（書目路徑、有效樣式 ID；未設定或不在清單時用預設 `apa`，`styleConfigured=false`）、寫入類方法在回合進行中回 `BUSY_TURN`、`documentContext` 以 `DocumentWorkspace.validate_snapshot` 驗證（與文件回合相同）、錯誤對應（`library_conflict` → `BIBLIOGRAPHY_CONFLICT`；其他書目與 Pandoc 錯誤 → `BIBLIOGRAPHY_FAILED`；未知樣式、`.tex` 的 render/docx/markdown → `PROTOCOL_INVALID`，訊息建議改匯出 `.bib`）。
  - `inspect`：`integrity.inspect` + 指紋 + 樣式清單；沒有文件時 `uses/order/missing/uncited` 為空、`citedCount` 為 0。
  - `render`：`csl_render.render`，`segments` 攤平成頂層陣列。
  - `set_style`：新增 `catalog.update_project_metadata`（只替換 metadata 區塊中的 JSON 物件：保留其他鍵與順序、保留原本的緊湊或縮排格式、區塊外文字逐位元組不變；寫入前重讀比對整檔指紋，衝突回 `CatalogConflictError`；暫存檔、fsync、保留權限、`os.replace`），之後以 `inspect_project` 更新快取的 `_project`。`_metadata_and_rules` 拆成 `_metadata_span` + `_parse_metadata`，行為不變。
  - `remove`：比對 `libraryFingerprint`，以 `library.remove_entry` + `write_atomic` 寫入；bundle 不動。
  - `add`：解析 DOI 或 arXiv ID；比照 `_knowledge_ingest_file` 在回合外呼叫 `_require_operation_approval("citation.save", <bundle 目錄>, …含書目路徑…)`；然後以 `CitationService(get_provider_hub(), config, library_path)` 走與 `citation_workflow` save 相同的驗證與儲存，再併入書目。拒絕或逾時不寫任何東西。
  - `export`：`csl_render.export_target`（A5：`<文件主檔名>.<樣式>.docx|md`、`<書目主檔名>.bib`，在文件旁；沒有文件時 `.bib` 在書目旁）、`library.write_bytes_atomic`；docx 以文件資料夾為 resource path；不可能覆蓋原文件（另有檢查）。
- **檢查**：新 `tests/test_desktop_bibliography.py` 10 項（每個結果都過 `validate_result_data`）：未開專案 → `SESSION_NOT_READY`；inspect（書目不存在、含未儲存文字、malformed）；render（IEEE/APA 不同、UTF-16 位置、未知樣式、`.tex` 拒絕且 inspect 可用）；set_style（只改 metadata、規則文字與雜湊不變、新指紋、未知樣式、`BUSY_TURN` 不寫入）；set_style 後送出新回合成功（R5）；remove（指紋衝突、未知 key 不寫、成功只少一筆）；add（Ask 拒絕 → `APPROVAL_DENIED` 且書目與 bundle 都不存在；Ask 同意 → added；Bypass 直接執行 → existing；不存在的 DOI → failed；非識別碼 → `PROTOCOL_INVALID`）；export（docx/markdown/bib 路徑與內容、原文件雜湊不變、`.tex` 的 docx 拒絕而 bib 可用）；錯誤分型（書目壞掉、Pandoc 不在）；`update_project_metadata` 單元測試（縮排 JSON 保留鍵序與區塊外文字、不可改其他鍵、寫入前檔案被改 → 衝突且無暫存檔殘留）。`test_project_permissions.py`、`test_citation_project_library.py` 通過；完整 pytest（沙箱外）1678 passed（加上新單元測試前），exit 0。
- **交付給 C7**：方法與欄位見 C6-S1；預設樣式 `apa`；錯誤碼 `BIBLIOGRAPHY_CONFLICT`、`BIBLIOGRAPHY_FAILED`。
- **下一步**：C7-S1。

### C7-S1 引用面板：檢視與跳轉（2026-11-05）

- **改動**：
  - `src/citations.ts`（純函式，無 React）：協定 DTO 型別、`buildPanelModel`（依 `order` 的首次出現順序；數字制樣式只替書目中存在的 key 依序編號；每個 key 的次數與位置；問題分為找不到的 key 與重複 DOI，書目錯誤轉成訊息）、`describeEntry`、`selectUse`（只有編輯器文字仍與檢查時相同才產生選取範圍；範圍以 UTF-16 為單位、越界拒絕）。
  - `src/CitationPanel.tsx`：在文件開啟時顯示於編輯器下方；分區「Cited in this document」（編號、key、作者年份標題、次數、驗證狀態，展開列出行號按鈕）、「Problems」、「Not cited in this document」；書目不存在時顯示說明。所有書目字串都以 React 文字節點顯示（不經 HTML）。呼叫 `bibliography.inspect` 的時機：文件開啟、手動儲存成功、`document.apply` 存檔成功（`App.tsx` 的 `citationRefresh` 計數）與按下 Refresh；不在每次按鍵時呼叫。
  - 跳轉：面板把帶 `rangeStartUtf16/rangeEndUtf16` 的快照（同一個 `editorRevision`）交給 `updateDocument`，`DocumentEditor` 既有的受控邏輯就會選取並捲到該範圍。
  - 介面文字沿用 GUI 的英文；`styles.css` 新增面板樣式。
- **檢查**：新 `tests/citations.test.ts` 6 項（排序、計數、問題分類、數字制編號、書目錯誤、描述字串、emoji 造成的 UTF-16 位移、過期或越界位置不選取）；`npm test` 295/295；`npm run build`（tsc + vite）成功。
- **限制**：原生視窗的實際外觀與點擊未觀察（R6），列入 C8 手動檢查清單。
- **下一步**：C7-S2。

### C7-S2 增刪、插入與補全（2026-11-05）

- **刪除**：每個書目條目有 Remove；仍被本文引用時先以 `window.confirm` 說明次數並註明「Other documents were not checked」，確認後帶 inspect 回傳的 `libraryFingerprint` 呼叫 `bibliography.remove`；`BIBLIOGRAPHY_CONFLICT` 時提示重新整理。
- **新增**：輸入 DOI 或 arXiv ID → `bibliography.add`。這個請求在回合外執行，原本的事件監聽只接受進行中回合或文件操作的 `approval.required`，所以 `App.tsx` 以 `requestCitationAdd` 追蹤它的 requestId（`citationRequestRef`），讓 Ask 模式的 `citation.save` 批准沿用既有的批准對話框；請求結束時清掉殘留的待批准狀態。結果分為 added/existing（顯示 key 並提供「Insert at cursor」）、failed（顯示原因代碼）、denied（`APPROVAL_DENIED`，說明沒有寫入任何東西）。
- **插入**：只改 Monaco 中的未儲存文字（新的本地 `editorRevision`），Markdown 插入 `[@key]`、LaTeX 插入 `\cite{key}`；位置取自編輯器回報的游標（`DocumentEditor` 新增 `onCursor`），沒有時用選取結尾或文末。
- **補全**：`DocumentEditor` 新增 `citationEntries`，為目前 model 的語言註冊 Monaco completion provider（觸發字元 `@`、`{`、`,`；只回應自己的 model；隨編輯器一起 dispose），在 `[@`、`; @`、`[-@`、`\cite{` 與其中的逗號之後列出 key（key 前綴優先，其次 key 包含、標題/作者/年份包含），細節欄顯示作者年份標題。行文中的 `@` 與 email 不觸發。
- **寫入停用**：回合進行中、文件操作中或有待批准時，Remove 與新增都停用。
- **檢查**：`tests/citations.test.ts` 新增 6 項（共 12）：確認條件與文字、衝突訊息、新增的四種結果、依副檔名的插入文字與 UTF-16 插入、補全觸發條件、候選排序與內容；`npm test` 301/301；`npm run build` 成功。
- **下一步**：C7-S3。

### C7-S3 格式、預覽與匯出（2026-11-05）

- **樣式**：面板的 Style 下拉選單列出 `inspect.styles`（含 `bime-appendix17`），選擇後經 `styleChangeParams`（只在閒置、樣式不同且在清單中時）呼叫 `bibliography.set_style`，然後重新 inspect；回合或文件操作進行中停用並顯示說明。
- **預覽**（只有 Markdown）：`bibliography.render` 以目前編輯器文字（含未儲存）渲染，列出每筆引用（key → 渲染字串）與參考文獻。參考文獻以新的 `CitationText` 元件顯示 `segments`：斜體/粗體是 `<em>`/`<strong>` 元素，文字永遠是 React 文字節點（HTML 與 `*` 不會被解析），連結只在 `safeExternalUrl` 通過（http/https）時成為按鈕並以 `openSafeExternalUrl` 開啟 —— 與 `SafeContent` 同一套網址檢查。這是 C4-S4 改用 segments 的對應做法（計劃原寫「經 SafeContent 顯示」，SafeContent 沒有跳脫語法會把 `_` 誤判為斜體）。
- **匯出**：Markdown 文件有 Word、Formatted Markdown、BibTeX 三個按鈕，LaTeX 文件只有 BibTeX；完成後顯示寫出的路徑並註明原文件未改變。
- **檢查**：新 `tests/citation_preview.test.ts` 4 項（樣式請求的條件、`.tex` 只有 bib、segments 分組、SSR 渲染：`<em>`、HTML 被跳脫、只有 https 連結成為按鈕、`javascript:` 不成為按鈕）；`npm test` 305/305；`npm run build` 成功；`cargo test --locked`（沙箱外）40 passed。
- **面板操作清單**（C8 手動檢查用）：開啟 .md/.tex → 面板出現；Refresh；展開條目 → Line 按鈕跳到並選取引用；Problems 顯示未知 key 與重複 DOI；Remove（被引用時確認對話框）；Verify and add（Ask 模式批准對話框；拒絕 → 未寫入）；Insert / Insert at cursor；在 `[@`、`\cite{` 後輸入看到補全；Style 選單（回合中停用）；Preview；Export Word/Markdown/BibTeX（.tex 只有 BibTeX）。
- **下一步**：C8-S1。

### C8-S1 端到端（真實桌面後端，不呼叫模型）（2026-11-05）

- **作法**（`evidence/C8-S1/drive.py`）：在 `$TMPDIR/c8s1` 建暫存專案（合成的 `draft.md` 與含兩筆手寫條目的 `references.json`），依桌面主機的方式啟動 `python -m agent.desktop.server`（cwd = repo 根目錄、`PYTHONPATH=app`、`CONDA_PREFIX`/`CONDA_DEFAULT_ENV=app`），`KMS_STORE_DIR`、`CITATION_OUTPUT_DIR`、`AGENT_LOG_DIR`、`XDG_CACHE_HOME`、history 都導到暫存目錄。順序：`workspace.select` inspect → initialize（以後端流程建立 `RESEARCH.md`）→ `document.open` → `bibliography.inspect` → `bibliography.add` DOI `10.1038/s41586-021-03819-2` → 同一 DOI → arXiv `1706.03762` → `inspect` → `set_style` APA/IEEE/附件十七各 + `render` → `export` docx/markdown/bib → `remove` 未引用的手寫條目 → `inspect` → `runtime.shutdown`。
- **與計劃不同**：計劃寫先 `session.create` 再 `set_bash_permission bypass`，因為「沒有 GUI 能回應批准」。這個環境沒有 `OPENROUTER_API_KEY`，`session.create` 會失敗；而 `approval.resolve` 不需要 session，所以改由驅動程式回應 `approval.required`（`citation.save`，3 次），走的是真實的 Ask 批准路徑。整個流程沒有任何 `session.*` 呼叫、沒有 `session.turn`、沒有模型呼叫。
- **公開請求**（`requests.jsonl`，發出前寫入）：3 次存檔請求（預算 8）。網路經沙箱代理放行 doi.org、api.crossref.org、export.arxiv.org 等文獻主機；arXiv 的授權查詢走 export.arxiv.org（PLANS 主機清單未列，屬「公開文獻 API」）。一次成功，沒有重試。
- **觀察**（`observations.json`、`transcript.jsonl`，長字串已截斷）：16 項檢查全部通過 —— 文件雜湊在所有步驟前後相同；手寫條目不變；第一個 DOI → `added jumper2021highly`；同 DOI → `existing` 同 key；arXiv → `added vaswani2017attention`；新增後沒有缺漏 key、新增的兩筆為 verified、手寫為 unverified；APA 與 IEEE 渲染不同（例：`(Jumper et al., 2021)` vs `[2]`，`(see Vaswani et al., 2017, p. 3)` vs `see [3, p. 3]`）；三個匯出檔存在，docx 含 `[1]`、Markdown 不含 `[@`；remove 後 `old1999notes` 消失，最終書目 = 手寫 FAO + 兩筆新條目；書目與 `citation.json` 都沒有 abstract；bundle 只寫在暫存的 cite 目錄，repo 的 `cite/` 未變。
- **下一步**：C8-S2。

## 最終彙報

（C8-S3 完成後填寫。）
