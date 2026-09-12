# Issue 04 — Citation earliest 歧義：執行紀錄

本檔是唯一 runtime phase status 與實際 implementation／verification evidence
來源。計劃描述預定工作，本檔只記錄已發生的事情。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Earliest ambiguity | Complete | 2026-09-12 | 2026-09-12 | Red, green, representative tool, full suite and acceptance mapping below | None |

狀態只用 `Not started`、`In progress`、`Blocked`、`Complete`。
只有 phase 的必要驗收與驗證都有實際證據，才可標 Complete。

## Evidence Rules

- 記錄 exact command/procedure、working directory、runtime、結果、驗收對應。
- 清楚區別觀察、歷史、計劃和推測；skipped/unavailable 不等於 pass。
- 保留重要失敗、修改與更正歷史；不要只留下最後成功結果。
- 只有重大 discovery 才連到 context；只有真實審查才連到 review。
- 不寫 credentials、完整 provider payload、完整 diff 或例行敘事。
- Evidence 衝突時保留兩者，未釐清前不得標 Complete。
- 不在其他文件複製本表的 mutable status。

## Activity Log

尚未開始實作，沒有 application tests、provider calls 或保存流程驗證證據。
本次僅撰寫計劃；authoring validator 的結果不代表應用程式修正已通過。

日後每筆重要紀錄包含：時間與時區、phase、狀態變化、實際改動、exact checks
與結果、未執行項及理由、驗收條件對應、重大 context/review 連結、剩餘 blocker。

### 2026-09-12（Asia/Taipei）— Phase 01 preflight / baseline

- 使用者明確要求執行 issue_04 且每一步 commit；啟動 routine implementation
  與本任務 commit 授權。唯一 phase 無 dependencies，Not started → In progress。
- 已依序讀取根 AGENTS、GOALS、PLANS、既有 log、phase、live code/tests；
  無其他 applicable AGENTS 或既有 context/review。維持年份限定、exact lane、
  identity/dedup 規則及最多五個 alternatives，不擴張 issue 05。
- Root `/home/minervamuses/research-agent-workspace`，branch `GUI`，起始 HEAD
  `92e602b`。`git status --short`、`git diff --stat` 均空；`uname -s` 為 Linux。
- Shell `/usr/bin/bash`，Git `/usr/bin/git`。初始 PATH 優先指向 Linux pipx
  Poetry 2.3.4；未用它執行測試。指定既有 Conda app bin 優先後，確認 Python
  3.13.14、Poetry 2.4.1 皆位於 `/home/minervamuses/miniconda3/envs/app/bin/`，
  `poetry run python -c 'import sys; print(sys.executable)'` 也為該環境 Python。
- 以下為本次所有 pytest 命令的共同前置（working directory 為 root/app）：

  ```bash
  source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
  conda activate app
  export PATH="$CONDA_PREFIX/bin:$PATH"
  ```

- Baseline exact command：

  ```bash
  poetry run pytest tests/test_citation_resolution.py tests/test_citation_work_resolver.py tests/test_citation_authority.py tests/test_citation_workflow_tool.py -q
  ```

  結果 **54 passed, 1 warning in 0.44s**。Warning 為既有 LangChain
  `allowed_objects` pending deprecation；這是 baseline，不是修正驗收。
- 現場仍有 earliest 非時間排序與 authority fallback 覆寫風險；下一步加入
  最小 red/characterization。所有 provider 使用離線 injection，寫入限 tmp_path。

### 2026-09-12（Asia/Taipei）— Phase 01 red / fallback characterization

- 在三個計劃指定的既有測試檔加入回歸案例，未改 production。重用
  manifestation、SearchProvider、DoiProvider、tmp_path 與 fetcher injection。
- Working directory/runtime 同 preflight。Exact command：

  ```bash
  poetry run pytest tests/test_citation_resolution.py tests/test_citation_work_resolver.py tests/test_citation_authority.py tests/test_citation_workflow_tool.py -q -k earliest --tb=short
  ```

  實際 **14 failed, 6 passed, 52 deselected, 1 warning in 0.49s**（exit 1）。
  此為預定 red，不是 implementation attempt 失敗。
- Unit/resolver 的 10 個失敗皆為應 ambiguous 卻 eligible；score 差異案例
  已先斷言兩筆都通過 identity，且 scores 確實不同。
- 兩個 service 邊界失敗明確觀察到 `saved` 取代原本的
  `earliest_year_tie` / `earliest_year_missing` ambiguity。真實 NeurIPS
  allowlist 能解析該 intent；正常 `not_found` fallback 保存的 control 通過。
  此反例證實 service guard 必要，符合既有 conditional production scope。
- 兩個真實 resolver → service → tool 案例在 DOI CSL refetch seam 被
  `AssertionError` 阻止（`https://doi.org/10.1234/paper-a`），證實歧義尚未
  阻止 winner refetch；沒有實際網路。下一步以同一案例確認無 fetch、無保存。
- 去重、唯一最小年、較晚平手、已知/未知混合的 characterization 通過。
  Phase 維持 In progress；baseline commit `4da5b23`。

### 2026-09-12（Asia/Taipei）— Phase 01 green / representative verification

- Red commit `6fff496`。Production 只改 `resolution.py` 與 `service.py`：
  既有 identity/dedup 後，全缺年份回 `earliest_year_missing`；最小已知年
  多 identity 回 `earliest_year_tie`，兩者都是 ambiguous、record=None。
  alternatives 依現有候選順序保留最多五筆，順序不表示時間先後。
  唯一最小已知年份回傳原 decision/evidence；非 earliest 排序保留。
- Service guard 僅排除以上兩個 ambiguous reason 的 authority fallback，
  走既有 SaveAlternative/status 轉換。不改 WorkResolver refetch、tool、
  provider、types、schema、dependency 或儲存格式。
- Working directory/runtime 同 preflight。Exact command：

  ```bash
  poetry run pytest tests/test_citation_resolution.py tests/test_citation_work_resolver.py tests/test_citation_authority.py tests/test_citation_workflow_tool.py -q
  ```

  實際 **72 passed, 1 warning in 0.47s**，第一次 focused implementation green。
  Warning 同 baseline。新增 18 個案例（含參數展開）皆通過。
- 代表 tool 案例使用真實 WorkResolver、CitationService、StructuredTool，
  只在 provider search/fetch seam 注入離線 fake。2017 同年與全缺年份兩者的
  ToolMessage content JSON == artifact，item status=ambiguous、reason 分別
  為上述兩碼、receipt=None。兩 alternatives 保留 title、year（含 None）、
  實際 published/preprint、DOI_A/DOI_B、arXiv 1706.03762 與空缺欄位；
  無 earliest 觀測種類。Crossref/DataCite 各一次 fake search、fetcher calls=[]、
  registry.list()=[]、output_dir 不存在。
- 真實 resolver unit 案例保留 crossref/datacite 的 ok states，DOI calls=[]。
  Service fallback 兩種歧義保持原 alternatives；正常 no_provider_records
  fallback 仍 saved 且 receipt trusted，exact arXiv 與 exact DOI 既有測試通過。
- Phase 維持 In progress，待最後一次 broader suite 與最終 diff 檢查。

### 2026-09-12（Asia/Taipei）— Phase 01 final verification / Complete

- Green commit `359669b`。Working directory/runtime 同 preflight，最後且唯一
  一次 full-suite exact command：

  ```bash
  timeout 600s poetry run pytest -q
  ```

  實際 **1061 passed, 2 warnings in 26.98s**（exit 0），沒有 failed、skipped
  或 unavailable。Warnings：同 baseline 的 LangChain pending deprecation，
  以及既有 `test_installer_zip_rejects_unsafe_members_without_extracting`
  刻意建立重複 ZIP member 所觸發的 duplicate-name warning。
- 從 repository root 實際執行：

  ```bash
  git diff 92e602b --check
  git diff 92e602b --stat
  git status --short
  git diff 92e602b -- app/tests/test_citation_resolution.py app/tests/test_citation_work_resolver.py app/tests/test_citation_authority.py
  ```

  整體 whitespace check 通過，當時工作樹乾淨。已檢視 production diff
  （green commit 前）及完整測試 diff；無越界修改或需追加修正的發現。
  本次最終 log 更新亦以 `git diff --check` 與整體 diff check 檢查後 commit。

#### Acceptance evidence（GOALS 順序）

| 條件 | 實際通過的證據 |
|---|---|
| 2020 published/preprint 不同 DOI 同年 ambiguous、無 winner | `test_earliest_year_tie_cannot_be_resolved_by_nontemporal_ranking[original]` |
| 順序、rank/provider、score 不消除平手且 identity 合格 | 同測試的 reversed、rank_provider、score 參數；先驗證兩筆 eligible，score 變體確有差異 |
| 全缺年份含單一 identity 都 ambiguous | `test_earliest_without_any_year_is_ambiguous_even_for_one_identity[1/2]` |
| 2020/2022 選 2020、較晚平手不影響、已知/未知保留既有語意 | 既有 `test_earliest_selection_chooses_oldest_dated_manifestation`；新增 `test_earliest_unique_known_minimum_survives_later_ties_and_unknown_years` |
| canonical DOI 重複不誤判；不同 DOI 不因同標題合併 | `test_earliest_deduplicates_canonical_doi_before_comparing_years` 與同年不同 DOI 測試；`test_earliest_alternatives_only_include_eligible_minimum_identities_and_cap_at_five` 另驗證排除不合格/較晚候選、去重和五筆上限 |
| alternatives 欄位與缺值如實保留、無 earliest 觀測種類 | `test_earliest_real_resolver_service_tool_returns_ambiguity_without_saving` 兩組參數逐欄檢查 title/authors/year/venue/version_kind/doi/arxiv，content 與 artifact 相同 |
| 真實 resolver/service/tool 歧義不 refetch、不保存、不被 authority 覆寫 | 上述 tool 測試兩組；`test_earliest_ambiguity_returns_before_doi_refetch` 兩組；`test_earliest_authority_fallback_preserves_year_ambiguity_only` 的兩組 ambiguity 及正常保存 control |
| preserved behaviors 與 broader regression | 72 focused tests 含既有指定版本/未指定版本、exact DOI/arXiv、provider failure、DOI/BibTeX/save 邊界；完整 suite 1061 passed |

- Changed files（全部）：
  `app/skills/citation/resolution.py`、`app/skills/citation/service.py`、
  `app/tests/test_citation_resolution.py`、`app/tests/test_citation_work_resolver.py`、
  `app/tests/test_citation_authority.py`、`issue/issue_04/build-log.md`。
- 沒有擴張 provider 日期/relations、identity 規則、exact lane、public schema、
  dependencies、儲存層或 issue 05；AGENTS 與其他 issue 未修改。未建立
  context/review 文件，必要 fallback 證據已完整記於本 log。
- 未執行 live/paid provider、model/GPU、真實 citation store、wheel build。
  本證據僅涵蓋離線真實 application path，不證明 live metadata 完整性或
  模型追問行為。仍只比較年份；混合未知年份只能選已知年份中的最早者。
- 所有 required checks 與代表驗收皆取得實際成功證據，In progress → Complete。
  無剩餘 blocker；完成後停止，不接續其他 issue。
