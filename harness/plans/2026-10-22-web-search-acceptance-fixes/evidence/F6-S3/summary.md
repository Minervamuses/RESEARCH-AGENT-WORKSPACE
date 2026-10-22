# F6-S3 突變複驗彙總

- 腳本：run_mutations.py（突變定義、暫存複本、對照組、判定）；原始結果：results.jsonl（逐筆追加）；較精確的失敗原因：reasons.jsonl（只重跑原因不清楚的已殺突變，判定不變）。
- 暫存複本在 repository 外（`$TMPDIR/f6s3`）：Node 複本含 src、tests、package.json、tsconfig.json，node_modules 為 symlink，以複本自己的 tsc 編出 dist；Python 複本含 app/agent、skills、rag、tests、pyproject.toml、poetry.toml，app/vendor 為 symlink，不含 app/desktop 與 app/store。
- 對照組：Node 四份測試全綠（retention 1.5 s、content-contract 0.5 s、lifecycle 4.4 s、server-entry 13.3 s）；Python focused pytest 全綠（11.5 s）。
- 判定：至少一個測試非 0 退出（含 150 s／400 s 逾時）即為殺死。repo 的 dist 與 production 檔沒有被修改。

| 結果 | 數量 | 突變 |
| --- | --- | --- |
| must / killed | 42 | N02b, N02c, N02d, N02g, N03b, N05d, N06d, N07c, N07e, N07f, N08h, N08i, N09g, N11b, N11c, N11d, N11e, N12, N13, N13b, N14, N14b, N14c, N14d, N14f, N14g, N14h, N14i, N16c, N20b, N26, N28, N29, N42, N43, P07, P27, P13, P13c, P18, P18b, P26 |
| must_conditional / equivalent | 1 | N14j |
| not_applicable / not_applicable | 6 | N04c, N15, N16b, N16e, N16f, N17 |
| optional / killed | 1 | N09b |
| optional / survived | 2 | P07b, P07d |

## 逐項

| 突變 | 類別 | 結果 | 殺死它的測試或理由 |
| --- | --- | --- | --- |
| N04c | not_applicable | not_applicable | Brave URL cleaning was deleted with Brave in F3-S2 (FU01). |
| N15 | not_applicable | not_applicable | Brave's transient retry loop was deleted with Brave in F3-S2 (FU01). |
| N16b | not_applicable | not_applicable | Brave's goto was deleted with Brave in F3-S2 (FU01). |
| N16e | not_applicable | not_applicable | Bing's homepage form flow and its waitForNavigation were deleted in F3-S2; Bing now navigates the search URL directly. |
| N16f | not_applicable | not_applicable | Brave's result selector wait was deleted with Brave in F3-S2 (FU01). |
| N17 | not_applicable | not_applicable | The DuckDuckGo axios request was deleted with DuckDuckGo in F3-S2 (FU01). |
| N02b | must | killed | test-search-result-retention.mjs：not ok - four kinds of zero candidates read differently |
| N02c | must | killed | test-search-result-retention.mjs：not ok - a blocked Google (Google returned HTTP 429) is filled by Bing and keeps its facts |
| N02d | must | killed | test-search-result-retention.mjs：not ok - engine lines keep errors, strategy_stopped engines, reasons and merged provenance |
| N02g | must | killed | test-search-result-retention.mjs：not ok - engine lines keep errors, strategy_stopped engines, reasons and merged provenance |
| N03b | must | killed | test-search-result-retention.mjs：not ok - only the needed wrappers are resolved; a duplicate lets the next one in, in order |
| N05d | must | killed | test-server-entry.mjs：not ok - invalid deployment settings stop the server at startup (N43, N05d, N08i) |
| N06d | must | killed | test-content-contract.mjs：AssertionError [ERR_ASSERTION]: Expected values to be strictly equal: |
| N07c | must | killed | test-content-contract.mjs：AssertionError [ERR_ASSERTION]: text removed for nav |
| N07e | must | killed | test-content-contract.mjs：AssertionError [ERR_ASSERTION]: The input did not match the regular expression /\[Observed destination\]\(<https:\/\/example.org\/next\?q=%252F&x=1>\)/. Input: |
| N07f | must | killed | test-content-contract.mjs：AssertionError [ERR_ASSERTION]: The input did not match the regular expression /\[Next\]\(<https:\/\/final\.example\/docs\/sub\/next>\)/. Input: |
| N08h | must | killed | test-server-entry.mjs：not ok - browser fallback launches full Chromium with the configured headless mode and a normal UA |
| N08i | must | killed | test-server-entry.mjs：not ok - invalid deployment settings stop the server at startup (N43, N05d, N08i) |
| N09g | must | killed | test-content-contract.mjs：timed out after 150.1 s |
| N11b | must | killed | test-server-entry.mjs：not ok - stdin during a stuck read aborts it before the bounded pool close and exits 0 (N11b, N11d) |
| N11c | must | killed | test-server-entry.mjs：AssertionError [ERR_ASSERTION]: Expected values to be strictly equal: null !== 0 |
| N11d | must | killed | test-server-entry.mjs：not ok - stdin during a stuck read aborts it before the bounded pool close and exits 0 (N11b, N11d) |
| N11e | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N12 | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N13 | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N13b | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N14 | must | killed | test-server-entry.mjs：not ok - _meta work budget, transport cancellation and the cleanup reserve bound a stuck read |
| N14b | must | killed | test-server-entry.mjs：not ok - _meta work budget, transport cancellation and the cleanup reserve bound a stuck read |
| N14c | must | killed | test-server-entry.mjs：not ok - _meta work budget, transport cancellation and the cleanup reserve bound a stuck read |
| N14d | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N14f | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N14g | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N14h | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N14i | must | killed | test-server-entry.mjs：not ok - wiring: includeContent, summaries, engine lines, invalid input and single-page limits |
| N14j | must_conditional | equivalent | After F5-S3 both search tools validate limit twice: the schema transform and the handler (validateSearchQuery -> parseInteger(limit, 1, 10)). Removing the summaries schema transform leaves the handler check, so limit 11 is still rejected before any engine runs |
| N16c | must | killed | test-browser-lifecycle.mjs：AssertionError [ERR_ASSERTION]: page goto ended after 2005.8888809999999 ms code: 'ERR_ASSERTION', actual: false, expected: true, |
| N20b | must | killed | test-content-contract.mjs：AssertionError [ERR_ASSERTION]: Expected values to be strictly deep-equal: |
| N26 | must | killed | test-browser-lifecycle.mjs：Error: condition not reached (the explicit-abort case: the stalled socket was not closed within 1000 ms after budget.abort()) |
| N28 | must | killed | test-browser-lifecycle.mjs：AssertionError [ERR_ASSERTION]: Expected values to be strictly equal: null !== 'SIGKILL' |
| N29 | must | killed | test-browser-lifecycle.mjs：AssertionError [ERR_ASSERTION]: Expected values to be strictly equal: 'hung' !== 'closed' |
| N42 | must | killed | test-server-entry.mjs：not ok - _meta work budget, transport cancellation and the cleanup reserve bound a stuck read |
| N43 | must | killed | test-server-entry.mjs：not ok - invalid deployment settings stop the server at startup (N43, N05d, N08i) |
| N09b | optional | killed | test-browser-lifecycle.mjs：AssertionError [ERR_ASSERTION]: Expected values to be strictly equal: 1 !== 0 |
| P07 | must | killed | tests/test_mcp.py::test_web_search_reaps_detached_grandchild_after_intermediate_exits：test_mcp.py:767: AssertionError: assert (41690.824047258 - 41690.022838168) < 0.8 |
| P27 | must | killed | tests/test_mcp.py::test_web_search_observer_failure_keeps_received_result：test_mcp.py:750: assert 0 == 1 |
| P13 | must | killed | tests/test_mcp.py::test_startup_reports_load_failures_and_unavailable_loader[False]：>       assert any(item.startswith("mcp:broken: applied_but_unavailable: load: RuntimeError: broken refused to load") |
| P13c | must | killed | tests/test_mcp.py::test_startup_reports_load_failures_and_unavailable_loader[False]：test_mcp.py:914: AssertionError: assert 'MCP loader unavailable: RuntimeError' in ('mcp:web_search: resolve: enabled but launch prerequisites are missing (entrypoint/node or co |
| P18 | must | killed | tests/test_mcp.py::test_web_search_budget_comes_from_spec_env_and_is_capped：E       AssertionError: assert (41590.143949908 - 41588.114986984) < 1.2 |
| P18b | must | killed | tests/test_mcp.py::test_web_search_budget_comes_from_spec_env_and_is_capped：E       AssertionError: must not start |
| P26 | must | killed | tests/test_mcp.py::test_web_search_stuck_cancellation_still_returns_within_budget：test_mcp.py:832: AssertionError: Regex pattern did not match. |
| P07b | optional | survived | Every process the tests reap is its own group leader (setsid/start_new_session), so killing only the PID still ends it; a group with other members that survive a PID kill is not reproduced by the lifecycle server. |
| P07d | optional | survived | Dropping the start-time check only matters after PID reuse, which cannot be reproduced reliably in a test (mutation-survivors already marks it optional for this reason). |
