# 規劃蒐證與限制

蒐證日期：2026-10-19（Asia/Taipei）。這是規劃時的唯讀檢查；沒有執行修復、app tests、build、模型或 live provider。E1–E10 對應 [來源文件](SOURCE-BRIEF.md)的十項。根據使用者授權，只讀相關程式／少量結構化本機實錄，不複製研究全文或憑證。未讀任意私人歷史。

## 可重現定位

主專案基準 `450f6d3c3733a01b6b448c92c2f73b253b487523`。下列主專案相對路徑均從 repo root 解析，行號對此 commit。外部 source 基準 `eeb03f88525cbf74c4019e59a3fea45a537a760b`。機器特有 log／tmp 僅是歷史定位；階段文件已寫出必要案例，未來執行不依賴 tmp 存活。

| ID | 直接檢查與結論 | 證據邊界 |
|---|---|---|
| E1 | conversations.ts:735–746 會在留言時加 Main request；App.tsx:281–295,2266–2303 的 inline refs 只辨識 @；skills/runtime.py:262–282 驗證 @/UTF-16；slash_commands.py:111–133 僅讀開頭 slash；desktop/service.py:2624–2692,2842–2859 傳 skill intent | 根因是組裝遮蔽 slash，skillReferences=[] 對 slash 本身正常；不能改成全文掃描 |
| E2 | 外部 source search-engine.ts:42–102 與 installed dist:32–86 的 bestResults 分支會漏回既得結果；Brave 達門檻不比先前 best；品質 0 不初始化 best | 本輪讀碼與讀既有離線腳本，沒有重跑；不是修復驗收 |
| E3 | App.tsx:768–784 保存完整 snapshot；desktop/service.py:2803–2835 分開加入 documentContext 與 references；2836–2839 retry 用原 semanticInput | 模型投影可去重；不表示 wire JSON、儲存 JSON 或 1 MiB 限制改變 |
| E4 | session.py:441–475 存粗摘要；turns/journal.py:9–38 只在記憶體；execution.py:37–60 觀測批次 updates；graph.py:319–341 真 invoke；diagnostics.py:147–197 及 desktop/server.py:454 已有持久 log | 既有 logger 可復用，但 callback 傳遞、ID 串接、取消與候選計數仍須實作期驗證 |
| E5 | app/agent/config.py:27、llm/openrouter.py:46–56；已安裝 wrapper chat_models.py:221–230,453–466；SDK chat.py:596–606,1353–1363、basesdk.py:213–223、utils/retries.py:225–280 | 真實版 timeout 是 ms；10→25 分鐘窗，0→SDK 60 分鐘 fallback；None HTTP timeout。重試窗不等於硬 deadline，並非歷史延遲原因證明 |
| E6 | mcp.py:260–264；adapter client.py:152–200、tools.py:366–399 每 call 建 session；startup.py:13–76 尚無持續 session resource owner | session 重用需生命週期設計，不能只換 get_tools 一行；echo 不代表實際搜尋成本 |
| E7 | 外部 search-engine.ts:35–53,120 起,216 起,1025–1032,1072 附近：順序 fallback、每次 browser、中文 keyword 清理／學術詞誤罰風險 | 實際各段耗時與品質影響待新資料；不能直接決定 pooling／降門檻 |
| E8 | citation/service.py:55–113 gather；providers/net.py:324–420 分類 retry；已存在 provider states 與只 cache 成功的設計 | 新 query 可再等故障來源；10/19 無 Citation，不用此機制解釋該筆 |
| E9 | citation/service.py:89–113 去重保摘要後截斷，tool.py:331–343 再年分過濾；types.py:PublishedDateFilter.admits_year 已存在 | 反例可離線建立；不能因此推估時間或重寫排名 |
| E10 | tools/access.py:68–112 技能與全域工具聯集；citation/SKILL.md:20–67 真摘要規則；tool.py:313–371 五 actions 無 DOI 補摘要 action | 舊十次 calls 無 action，冗餘與停止問題需新 trace；新增 action 是待批准 API 變更 |

## 本機回合實錄：只保留診斷結構

資料根位於 `app/store/projects/p-c673e2df20456bc65ca0e4e23143255a/conversations/`（生成輸出，**不納入此次 commit**）。

- `df153d4fef5348bf8062887224d1eb12.json`，turn `cbdca28b90654445b7863cfa9bffe9ee`：displayInput 前綴 Main request＋/citation；skillReferences=[]；背景全文 14,696 字元；唯一 document reference 選取 283 字元，但 snapshot 全文同為 14,696，rootPath/path/editorRevision/diskFingerprint/sourceText 相等。semanticInput 32,205 字元、sourceText 欄位兩次。工具摘要 rag_explore=1、read_file=1、get-web-search-summaries=14、無 citation_workflow。submitted→finished 差 341.446504 秒，只是整回合時間。
- `db57ad107f9e4357831e4104f0f86879.json`，turn `29f3b12a4c5443f1a3c6f5a0b047a11d`：以 /citation 開始、citation_workflow=10；相同 14,696 字元全文也重複。未據此推估 action 或模型輪數。

這些欄位由子代理唯讀抽取長度／前綴／工具統計確認；未輸出全文。原文中「五分鐘」可對應第一筆約 341 秒，但不能拆成特定模型、搜尋或 retry 時間。規劃不要求把使用者真實研究文本提交成 fixture。

## 外部 source、安裝與既有腳本

- Source checkout：`/home/minervamuses/mcp-servers/web-search-mcp`；Git HEAD eeb03f8；既有 dirty 為 ` M package-lock.json`。
- 標準 runtime 安裝：`/home/minervamuses/.local/share/mcp-servers/web-search-mcp`，package 0.3.1，無 .git／src。本 repo mcp.py:62–64,80–100 與 paths.py:16–19 指向此 XDG fallback。**未讀執行中 GUI launch env**，故實作 P2 仍須核對有效覆寫。
- source 的 dist/search-engine.js 與標準安裝同檔 `cmp` exit 0，兩者 SHA256：`dad8f4484c321522314f3e7981cee4f6b19f82984d12373458f224fc597a9758`。未重新 build，這是現有產物一致性，不宣稱可重現 build 已通過。
- `/tmp/web-search-dist-repro-20261019.mjs:2–48` 已含 network／fetch／browser 封鎖與四情境，但 asserts 是故障期望；完整修復驗收情境已寫在 P2，無需該暫存路徑仍存在。50–59 的 heuristic 檢查屬後續議題。
- `/tmp/mcp-echo-lifecycle-aUZFqw/` 的 probe.py／echo_server.py／events.jsonl：A 的 list＋兩次 call 使用 PID 16344、16348、16352；B 一個 persistent session PID 16356。歷史 A 約 0.932065442 秒、B 約 0.309159554 秒，差約 0.622905888 秒。只讀檔，不重跑。
- `/home/minervamuses/.cache/agent-mcp/web_search.stderr.log:5399–5401,5761–5763,5863–5865,6051–6053` 有 Bing 解析十筆紀錄；未找到可串接的 final-zero 記錄，因此「歷史 Bing 十筆→最終零筆」完整鏈仍為原文提供、未獨立核實。
- 原文提到的 503／timeout 離線探針在限縮的 repo relevant paths 與 /tmp 檔名搜尋未找到。P5 有恢復／最小重建路線，不能記作本輪跑過。

## SDK 與工具版本

已在 Conda app 確認 Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0；langchain-openrouter 0.2.6、openrouter 0.10.8、langchain-mcp-adapters 0.2.2、mcp 1.27.0。site-packages 基準為 `/home/minervamuses/miniconda3/envs/app/lib/python3.13/site-packages/`。

補充 P5 可行接點：wrapper 的 `client` 為公開 constructor field（chat_models.py:162），validate_environment:484–488 在 client 未提供才建構；sync send:570、async send_async:588 均使用它。SDK sdk.py:142–143 接受 retry_config 與 timeout_ms；chat.py 分辨 None 與 UNSET。SDK retries.py:118–123 可直接採 Retry-After，故有限 backoff window 不保證有限且準確的總截止。以上為讀碼證據；顯式 client 的實際 HTTP 行為仍由 P5 offline test 驗證。

## 既有工作區狀態及未做事項

規劃前主專案 git status：

```text
 D harness/plans/2026-10-18-desktop-interaction/build-log.md
 D harness/plans/2026-10-18-desktop-interaction/build/phase-04-stop.md
 D issue/20261018-desktop-interaction-feedback.html
 D problem.html
?? app/store/
```

起始 staged 為空。舊 harness/plans 在工作樹不存在，不恢復、不引用為本計劃前提。根 .gitignore 的 `build/` 也會忽略新計劃 build/ 階段文件，提交時需對**這個新計劃的確切文件** force-add；不修改 .gitignore 或 force-add 整個 workspace。

未做 app tests、build、安裝、provider 呼叫、任何修復、Git branch／worktree 變更；未讀取 secrets 值。無法用只讀蒐證證明修復有效，所有實作階段維持 Not started。
