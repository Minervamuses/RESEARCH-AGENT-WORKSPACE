# 執行狀態與證據
本文件是唯一動態狀態擁有者。規劃與修正前審查不代表產品驗收；本次實際執行結果見下方各步驟事件。

## 階段狀態
| 階段 | 狀態 | 實際證據 | 阻塞 | 下一動作 |
| --- | --- | --- | --- | --- |
| P1 | Complete | P1-S1：21 passed，逐句核對通過 | 模型遵循未做付費驗收 | 依步驟 ID 查 commit |
| P2 | Complete | P2-S1a/b/S2：build／13個離線案例通過 | 正文政策續於P3 | P3-S1 |
| P3 | Complete | P3-S1/S2a/S2b：正文、候選、輸出契約通過 | 真讀取續於P6 | P4-S1 |
| P4 | Complete | pool/deadline/取消離線通過；真stdio EOF無殘留 | 公開引擎續P6 | P5-S1 |
| P5 | Complete | env真入口、故障隔離、父層期限與程序收尾通過 | 公開網路續P6 | P6-S1 |
| P6 | In progress | P6-S1本機整合／4組公開觀測通過 | DDG零解析、Brave429為外部限制 | P6-S3完整suite與結案 |

## Authoring A0（2026-10-20，Asia/Taipei）
- 已讀完整原spec、使用者annotation及Citation/連續執行/commit追加指令；將原spec以LF保存於context/source-spec.md。最新決策集中GOALS，沒有覆寫來源快照。
- 唯讀gate：GUI，HEAD 7026a70e1d3368d3fc1617cf735c44e9ff0c1b86；tracked/index乾淨，app/store/既存未追蹤。Linux/Conda app，Python3.13.14、Poetry2.4.1、Node24.18.0、npm11.16.0。
- 已讀root AGENTS、相關vendor/Python/Citation檔與既有測試、installed adapter的stdio及interceptor實作；兩個唯讀子任務協助確認基線，未跑產品程式或動態驗收。
- 已寫計劃骨架、phase細節及驗收對照；結構lint、獨立審查與Git提交的實際結果將於完成後追加，未執行前不預填通過。
- 本次可變更路徑只限harness/plans/2026-10-20-web-search-citation/。產品檔案未修改。

## 後續事件格式
每個實際P?-S?事件記：改動與對應G/R/AC、實際檔案、命令及退出碼/輸出摘要、證據位置、未解決限制、下一步。提交前更新；commit subject包含step ID。需要hash時從git log反查，不為自己的hash再commit一次。取消/未執行/逾時不是通過；保留失敗歷史，不能覆寫成沒有發生。

### A0-V1 結構檢查
- 實際執行 skill 的 validate_plan.py --json，13個檔案，退出1：plan-index.json 的 plan_id 以數字起頭，不符合ASCII字母開頭規則。
- 已改成 web-search-citation-2026-10-20，未變更phase/goal圖；待重新檢查。這是規劃結構失敗，非產品測試。

### A0-V2 結構與來源複驗
- 實際命令：Conda app Python 執行 long-horizon-plan-author/scripts/validate_plan.py 對本計劃 --json；退出0，ok=true，checked_files=13，errors=[]，warnings=[]。
- 修整結尾空白前，原始附件與 context/source-spec.md 以UTF-8且換行正規化後全文相同；當時SHA-256：24482e4f54d230b8a76e351bf75c3a7395205147beeb782d9821cc931295be68。
- 13個計劃檔實際讀回，均為UTF-8／LF。檔案圖、相依順序、GOALS覆蓋、phase索引與本地連結通過結構lint。另人工核對AC01–AC16、開始及中斷恢復流程；這些不代表產品行為已通過。

### A0-R1 獨立審查與修復
- Fresh-context reviewer唯讀看完整13檔與最新人類要求，確認從環境/Git gate→P1-S1→focused測試→log/commit→P2的啟動路徑，以及中斷後按step ID對帳。
- 發現一項major：原草稿把「上限10000」放寬成可被0或更大顯式值繞過的預設。已同步修正GOALS、P2/P3/P5/P6與acceptance：硬上限10000，0採部署預設，超過10000清楚拒絕；保留原spec快照並由最新決策覆寫。
- 修正後reviewer只複核這六檔，確認唯一major已排除，無殘留矛盾；沒有其他未解決critical/major計劃缺口。
- 五分鐘取消／SDK收尾、Chromium與真網站可用性仍屬未來實作驗證，不是已觀察的成功結果。
- 計劃準備狀態：可啟動；所有implementation phase維持Not started。規劃提交使用[A0]，可由git log查實際commit，不在檔案預填未存在hash。

### A0-V3 最終格式與提交範圍核對
- 首次staged whitespace檢查退出2：PLANS一處Markdown尾端空白，原spec快照有多餘EOF空行。已移除該尾空白並將快照結尾正規化為一個LF；未變更原規格文字內容。
- 最終快照與原附件經LF及EOF空行正規化後全文相同；最終SHA-256：8405bec133e1afea0284057652381118439fb4a1b263f2fc0e4b386bce7f63a2。
- 提交範圍精確列出本計劃13檔；只有build中的六個phase Markdown因root ignore規則使用逐檔force-add，沒有納入dist、store或產品程式。
- 修整後再跑結構lint：退出0、13檔、零errors/warnings；git diff --cached --check退出0。

## Authoring A1（2026-10-21，Asia/Taipei）
### A1-R0 唯讀審查（2026-10-20）
- 依 PROMPTS「審查」對 HEAD 49d7048（產品程式＝7026a70）做唯讀多代理審查，共 6 個維度：基線事實、需求追蹤、內部一致性、環境可執行性、技術可行性、執行契約。
- 每項發現由獨立驗證者嘗試反駁：blocker/major 用 3 個視角，minor 用 1 個。46 項發現中 23 項成立，沒有 blocker。
- 審查只在暫存複本 build 與測試，沒有修改追蹤檔案。觀察摘要寫入 PLANS「A1 唯讀審查觀察」；它們是修正前基線，不是本計劃的實作證據。

### A1-E1 依使用者回覆修訂（S6）
- 使用者逐項回覆，見 GOALS S6。新增 U10–U15；A09 為依審查證據採用的技術預設。
- GOALS：新增 S6、U10–U15、A09；更新 G2、G8 與 content-extractor 不變條件。
- PLANS：
  - 新增「A1 唯讀審查觀察」與「宿主沙箱與執行環境」兩節。
  - 改寫執行契約第 1、3、4、5、7、8、9 項（沙箱外授權、不中途停下、content-extractor 最小型別修改、gitignore 路徑不必 commit、環境失敗歸類）。
  - 必要檢查改為帶暫存與日誌隔離；完整 suite 改為在沙箱外跑，修正後可再跑一次；Chromium 基線依觀察更新；完成判準同步更新。
- PROMPTS：啟動提示加入沙箱外執行與連網授權，以及不中途要求授權或 review。
- P1：檢查第 1、2 點（見 A1-R1）。
- P2：
  - 兩個搜尋工具輸出帶出引擎狀態與來源引擎。
  - 加入輸出文字斷言（格式化純函式，從 dist 匯入）。
  - 允許拆成 P2-S1a/b。
- P3：content-extractor 最小型別相容修改。
- P4：
  - S1：README 交由 P5-S1。
  - S2：局部 timeout = min(操作上限, 剩餘預算)，加入卡住 selector 的案例。
  - S3：stdin end 判定連線結束，點名 index.ts:230 closeAll，真程序與殘留檢查在沙箱外、同一腳本內取證。
- P5：
  - DEFAULT_TIMEOUT 與 U13 的關係；allowlist 不納入 TMPDIR/proxy。
  - README 改為「新增」設定表，並修正 Firefox／評分描述。
  - focused 命令加入隔離。
  - P5-S3 寫入已觀察的 SDK 收尾序列，新增「結果已回、取消落在收尾期」案例。
- P6：
  - 沙箱外執行；經 Python 入口觀察兩個搜尋工具。
  - 只有引擎自身失敗才可停用引擎。
  - 殘留同一腳本取證；完整 suite 可在修正後再跑一次。
  - 列出未 commit 的 gitignore 路徑修改。
- acceptance：更新 AC05、AC08、AC10、AC16 與完整 suite 說明。
- 不改 plan-index.json：goal／phase／相依沒有變動。
- 審查中的其他 minor 項目不在使用者核准的修訂範圍，未改：
  - AC13 描述檢查方式；
  - R11 真實入口驗證；
  - BROWSER_HEADLESS=false 經 Agent 啟動無顯示；
  - discovery 上限值；
  - 網路預算未計 P6-S2。
- 本次只改計劃目錄；產品檔案未修改。A1 是規劃交付，已追蹤的 build/ phase 檔以逐檔 git add -f 一併提交，讓 HEAD 的計劃版本一致；U15 適用於之後的執行步驟。

### A1-V1 結構檢查
- 修訂後實際執行 validate_plan.py --json（Conda app Python）：退出0，ok=true，checked_files=13，errors=[]，warnings=[]。
- git diff --check 退出0；13檔都是UTF-8／LF，沒有CR。

### A1-R1 獨立審查與修復
- 用三個新 context 審查者唯讀檢查修訂版：使用者決策忠實度、end-to-end 不中途停下、跨檔一致與 fresh executor 走查。共 18 項發現，每項由獨立驗證者嘗試反駁。
- 5 項成立，已修復：
  - 隔離把 XDG_CACHE_HOME 指到暫存目錄後，直接用 node 啟動的 Playwright 找不到 ~/.cache/ms-playwright 的 Chromium（審查者實測 executablePath 指向暫存路徑、檔案不存在）。已在 PLANS 規定這類命令另設 PLAYWRIGHT_BROWSERS_PATH，並把 Executable doesn't exist 歸為設定錯誤。
  - U13「每引擎嘗試 4 秒」與程式語意不符：search-engine.ts:58 的值是引擎內單次導覽／HTTP 請求的 timeout，目前實際約 3.3 秒。已改寫 GOALS U13、PLANS 基線與 P4-S2，表明整個引擎嘗試只受剩餘預算限制。這是對使用者已同意的「現有 3／4／6／8 秒」的語意澄清，不是新決策。
  - 沙箱外的殘留程序不會自動回收。已規定由同一腳本只終止本次記錄的 PID／process group，並記錄清理結果。
- 其餘 13 項經驗證判定不成立或已被其他條文涵蓋。其中幾項雖被駁回，但為了更貼近使用者原話與 end-to-end 原則，仍做了低成本澄清：
  - U15 的措辭改回「不必 commit」；
  - 環境阻塞只記未驗證、不擋後續步驟；
  - 不論上游是否阻塞都執行 P6-S3 可做部分與最終彙報；
  - A 假設遇新證據時自行修訂並記錄，不停下詢問；
  - P1-S1「人工逐句確認」改為執行者自行核對；
  - P1-S1／P5-S2 的 pytest 命令標明隔離；
  - P2-S1 恆真的「同一格式化結果」斷言改為靜態檢查兩個 handler；
  - AC05 類型欄恢復使用者原話「離線＋輸出文字」，P6 觀察列為補充；
  - P5 在 P4 只有環境阻塞時照常進行；
  - PROMPTS 加一行給使用者看的宿主權限模式前提。
- 修復後已重跑結構檢查，結果見 A1-V2。

### A1-V2 修復後複驗
- validate_plan.py --json：退出0，ok=true，checked_files=13，零errors／warnings。git diff --check 退出0，沒有CR。
- 用 grep 掃舊規則殘留（最多一次、不修改未使用、尚未確認、所有局部timeout取剩餘預算、每引擎嘗試、首次新增此計劃、外部阻塞、人工逐句、需你核准），只剩兩處合理用法：P2-S1「每引擎最多一次策略嘗試」、P6-S2「必要重跑同一小例最多一次」。
- 計劃準備狀態：可啟動。所有 implementation phase 維持 Not started。提交使用 [A1]，可由 git log 查實際 commit。

## Execution（2026-10-21，Asia/Taipei）
### E0 — 環境與續跑對帳
- 使用者已明確啟動整個計劃並授權範圍內本地 commit；禁止新依賴、付費呼叫、push、發佈、建／切分支。宿主 danger-full-access，檢查直接在無沙箱的 WSL Linux 執行。
- root /home/minervamuses/research-agent-workspace；分支 GUI，起始 HEAD 3225a90f4d482ccabdabcd2adaa447852741be7c（A1），A0＝49d7048。沒有已完成 P?-S? commit，與原進度表相符。
- 起始 tracked/index 乾淨，只有既存未追蹤 app/store/；不讀改或提交該資料。沒有下層 AGENTS.md。
- WSL Ubuntu-24.04；/usr/bin/bash、/usr/bin/git；Conda app 的 Python 3.13.14、Poetry 2.4.1、Node v24.18.0、npm 11.16.0，工具均為 Linux。以既有 conda.sh 啟用 app，未安裝任何工具。rg 缺少，使用 git ls-files/find/grep。

### P1-S1 — Provider-only Citation prompt（G1/G8，R01，AC13/15）
- 唯一產品改動：app/skills/citation/SKILL.md introduction 後增加計劃所列一段，禁止找論文、補 metadata/abstract 或修復失敗／不完整／歧義 provider 結果時轉 Web Search；要求誠實呈現可用結果與限制。
- 執行者逐句對照原文，保留可見 DOI/arXiv、doi.org、儲存授權、既有 provider／摘要／重試規則及工具可見性；沒有 runtime 封鎖。
- 實際檢查：在 app/、Conda app 啟用後，隔離 XDG_CACHE_HOME/AGENT_LOG_DIR/TMPDIR，PYTHONDONTWRITEBYTECODE=1；poetry run pytest tests/test_citation_skill_activation.py tests/test_tool_access_matrix.py -q -p no:cacheprovider，exit 0：21 passed，0.57s；一個既有 LangChainPendingDeprecationWarning。
- 模型遵循沒有動態驗證，沒有付費呼叫；prompt-only 不保證消除違規。
- 下一步：P2-S1，先讀階段檔與相關搜尋原始碼。

### P2-S1a — 跨引擎候選與執行事實（G2/G4/G8，R02/04/06）
- 因共用文字 formatter 需 utils.ts，採原計劃允許的 S1a/b 拆步；本步產品檔案為 src/search-engine.ts、src/types.ts，修改既有 tests/test-search-result-retention.mjs。
- 刪除 query 詞彙評分、閾值與勝出批次路徑；Bing→DDG→Brave 依原排序附加到 limit，URL 標準解析後完全相同才合併來源，保留首筆 metadata；足額引擎標 strategy_stopped。
- 引擎回傳 attempted、實際傳輸 attempts、parsedCount、completed/zero_parsed/error；候選正文初始 not_requested。保留現有最多一次傳輸重試與 Brave 403/429 快失敗，移除 DDG 二次 URL decode、無效 scheme 與依 captcha/title 詞彙猜測的診斷。
- 驗證：Conda app 中於 vendor 執行 npm run build（exit 0）；node tests/test-search-result-retention.mjs（exit 0，11/11）。涵蓋2+重複+3補足5、第三引擎未呼叫、失敗保留、全失敗/全零解析、中文/AI/運動/天氣、URL、403/429。
- 目前工具文字與候選過量取回仍待 S1b 接通；Firefox／共享資源與 deadline 依 P4。未作網路 smoke。

### P2-S1b — 兩搜尋工具的可見輸出（G2/G4/G8，AC01/03/05）
- src/utils.ts 增加無 stdio 副作用的 formatSearchResponse；src/index.ts 的 full-web-search／get-web-search-summaries 均使用同一 formatter，src/types.ts 最小增加 engines 交付欄位。
- 文字區分全失敗、零解析、部分成功，逐引擎列 attempted/attempts/parsed_count/status/error，逐候選列來源引擎、搜尋 title/snippet 與 read status。移除 index 的錯誤詞彙分類與正文模式過量取候選；不再以正文成功補換搜尋候選。
- 初次 build exit 1：新增 formatter 的換行字串被編輯腳本展成實際換行（TS1002）；針對字串修正後 npm run build exit 0。
- node tests/test-search-result-retention.mjs exit 0，12/12；新增輸出文字差異、候選來源斷言，靜態讀 index.ts 確認兩個 handler 都調用 formatter。未 import index 啟動 server。
- P3 仍須修復既有 extractor 的 PDF 過濾與成功優先；本步未將它宣稱通過。下一步 P2-S2。
- 提交前 git diff --check 首次指出 utils.ts 原檔尾端的空白在追加內容後成為變更行；已移除該處空白後重驗。

### P2-S2 — 明確長度與入口傳遞（G4/G8，R07，AC06）
- 產品範圍 src/index.ts、src/utils.ts、src/enhanced-content-extractor.ts；沿既有 Node 回歸檔增加單一參數案例。
- 移除模型型態猜測與自動覆寫；limit 嚴格整數1–10、includeContent 只接受 boolean 或 true/false 字串，預設5/true。maxContentLength 嚴格0–10000，省略／0使用嚴格1–10000的 MAX_CONTENT_LENGTH，內建10000；兩工具 schema/handler 共用 resolver。
- 參數一路送至搜尋後與單頁擷取；以 Unicode code points 單次裁正文，HTTP 品質檢查在裁切之前，不因小上限觸發 fallback。舊 parseContent 的部署上限提前裁切已移除；Markdown/品質判斷本體在P3處理。
- npm run build exit 0。初次 Node 測試12/13：靜態禁止 parseInt 的正則誤中本步 helper 名稱 parseInteger；改成匹配 parseInt( 後重跑13/13，exit 0，沒有產品行為失敗。
- 案例覆蓋省略、0、7/'7'、部署預設9、10001/負值/NaN/非整數/部分數字拒絕、中文emoji，以及兩入口共用resolver與參數傳遞。
- 截斷標記、原長度與保留連結目的地、PDF候選及真正文資料仍由P3完成；未提前宣稱這些驗收通過。

### P3-S1 — 保守 Markdown 與連結截斷（G3/G4/G8，AC02/03/07）
- 產品範圍 src/enhanced-content-extractor.ts、src/utils.ts；新增計劃指定的少量原生 assert 檔 tests/test-content-contract.mjs，inline HTML、沒有依賴／fixture framework。
- 以有限 Cheerio DOM 走訪保留 heading、段落、list、pre/code、table逐列（明示span簡化）、圖像alt來源文字與caption、實際公式文字；只移除script/style/noscript/template。移除class/id子字串、topic words刪除與短文品質判斷。
- href 依實際最終URL及有效base解析，保留百分比參數；非HTTP協定只列來源文字並標不可導覽。HTTP空文字可有限fallback，短文和robotics/captcha/privacy/legal等詞不再觸發。
- truncateMarkdown 按Unicode code points，邊界落在連結或URL內就捨去整個該連結，回原長度／交付長度／truncated；不補造新目的地。P3-S2將把資料與截斷標記接上文字輸出。
- 驗證：npm run build exit 0；node tests/test-content-contract.mjs exit 0（來源詞、shadow/metadata、結構、alt/caption、base、百分比、短文、emoji、10000、連結邊界）；既有retention 13/13，exit 0。
- 沒有改未呼叫的content-extractor.ts；無需型別相容例外。下一步P3-S2。

### P3-S2a — 固定候選與每頁取得事實（G3/G4/G8，AC04/06）
- 為每步維持最多3個產品檔，S2細分a（extractor/types/index最小接線）與b（純文字格式與統計）；不改後置條件。
- 新增小型PageRead資料（不是持久格式）：requested/final URL、真正page title、HTTP status/media、技術狀態、逐HTTP/browser嘗試與錯誤、截斷長度；每次attempt資訊屬於本次呼叫。
- 移除PDF預過濾、成功優先、補換候選與未取消的race；所有候選原順序交付。依實際Content-Type及PDF magic判斷，未知media不猜HTML；PDF bytes不送HTML parser，.pdf後綴也不決定媒體。HTTP最多10MiB讀取，超額為明確失敗。
- extractor保留同一條HTTP→有限browser fallback路徑，回傳實際metadata；移除與新媒體讀取衝突的舊隨機指紋／重複browser分支。單頁最小接線使用真正page title，未知不再從URL捏造。
- 驗證：npm run build exit 0；正文契約與混合PDF(無後綴)/404/短文/空文字/取消/缺失及錯誤media案例通過，來源嘗試總計等於spy事件；retention 13/13，exit 0。
- 可見統計、截斷標記與兩入口一致輸出在S2b；資源併發／取消清理由P4完成。
- 首次stage命令因cd層級錯誤把明確路徑算到repo外，exit 1；沒有改分支／index污染，改用repo-root完整相對路徑後重新檢查。

### P3-S2b — 可見頁面資訊與真實統計（G3/G4/G8，AC04/06/07/13）
- 產品範圍src/index.ts、src/utils.ts；single與full共用formatPageRead，逐頁列真實requested/final URL、page title、HTTP/media、狀態、實際各transport嘗試與失敗、原長度/交付長度/有效limit。
- 截斷標記在正文外，明示未交付範圍；metadata不計入Unicode正文上限。來源搜尋snippet與Page content分開，unsupported/失敗候選保留。
- 文字統計來自實際attempt陣列：selected、開始讀取候選數、source/HTTP/browser attempts、同transport retries、各狀態與returned；includeContent=false不呼叫extractor，固定候選不改。
- 三工具描述指明Citation責任，不再承諾完整全文／已驗證摘要或支持。
- 驗證npm run build、正文契約與retention皆exit 0：混合5候選實際6來源讀取與spy一致、false=0、URL順序一致、兩入口共享頁面文字、標記/Unicode長度一致；retention13/13。
- 尚未將stub當實機；實際Python→Node及HTTP/Chromium媒體驗證依P5/P6。

### P4-S1 — 程序唯一 Chromium pool（G5/G8，AC08/09）
- 產品範圍browser-pool.ts、search-engine.ts、enhanced-content-extractor.ts共3檔，預設注入sharedBrowserPool，無需第四檔index。所有實際建立路徑改由pool：同時launch合併promise；失敗清promise可重試；context/page與HTTP各最多2。
- 移除所有src內Firefox/WebKit launch、browser rotation/MAX_BROWSERS/BROWSER_TYPES/last-used及dedicated browsers；Brave改Chromium。每項工作用自己的context並finally釋放，close失敗只記錄；不因滿載evict。
- 引擎attempt計數改為本次呼叫state，不共用Map；移除未再呼叫且會額外建立context的health helpers。Bing保留既有homepage/form及direct fallback，各取同一受管page。
- 驗證：npm run build；新node tests/test-browser-lifecycle.mjs；content-contract；retention，皆exit 0。並行3次getBrowser僅launch1；7工作context峰值2、HTTP峰值2；工作期間不提前close；launch失敗恢復；預設search/extractor同pool；Brave403/429快速失敗與Chromium stub通過。
- 以上為受控stub，不當作實機Chromium／公開引擎可用證明。排隊deadline、真實abort及每次summaries的closeAll由S2/S3完成。

### P4-S2a — 共用單調預算與可取消資源等待（G5/G8，AC10）
- S2依相依拆a（pool預算primitive）、b（搜尋/正文/限流）、c（server邊界），每步可build/檢查/commit；本步只改browser-pool.ts與既有生命週期測試，沒有新模組。
- CallBudget用performance.now期限、AbortController與可清timer；子預算繼承取消。具名操作上限集中；DEFAULT_TIMEOUT僅整次總預算，內建300000、工作285000／清理15000。
- pool等待／launch／context建立均檢查同一budget；取消後queued callback不開始工作；不可取消launch晚完成時若已無等待者立即納管關閉。context取消時關自有資源；close有界且錯誤只診斷，cleanup不完整時拒絕新context。
- 初次Node生命週期測試因deadline timer使用unref且stub只剩pending promise，Node以unsettled top-level await提前退出；移除unref，保留明確dispose後修復。
- 重驗npm run build及三份Node測試皆exit 0；短排隊deadline後spy請求0、取消前不開page、慢launch晚完成關閉1、所有CallBudget dispose後Timeout資源0。全程毫秒級，不等五分鐘。
- 本步尚未把budget傳入各引擎/正文操作；續S2b。

### P4-S2b — 搜尋與正文全程傳遞預算（G5/G8，AC10）
- 產品範圍search-engine.ts、enhanced-content-extractor.ts、rate-limiter.ts；入口可接既有CallBudget，獨立使用也有自有budget/finally dispose。排隊、每引擎／重試不重設整段期限。
- 引擎單次導覽/HTTP≤4s，form selector≤2s、results selector≤3s；正文HTTP/導覽≤6s，搜尋後每頁總計≤8s（含排隊）。所有timeout再取剩餘budget最小值；Brave只對明確暫態錯誤重試一次，403/429不重試。
- HTTP把同一signal交Axios，browser透過受管context取消；fallback前檢查剩餘預算。HTTP讀取事件在真正取得slot才計數；未開始候選not_attempted，已取得候選在deadline後仍回傳；剩餘引擎標策略停止及deadline原因。
- rate-limiter排隊也受budget控制，queued callback再次檢查；沒有另建全域限流／新worker。
- 驗證：build與三份Node測試exit 0；retention新增到14/14，短deadline保留既有候選且第三引擎不啟動。生命週期測試用20ms selector上限，實際等待逾時後仍進DDG並有剩餘預算；本機真HTTP慢回應35ms取消，收到1次、socket已close、fallback0；timer最後0。
- Node server跨search/body共用budget尚待S2c；Python程序啟動與stdio收尾在P5。

### P4-S2c — Node三入口共用同一呼叫budget（G5/G8，AC10）
- 只改產品src/index.ts，所有tool callback在驗參前建立budget、finally dispose；full的search/body、summaries與single均傳相同實例，不分段重開DEFAULT_TIMEOUT。
- 保留預設總300000／工作285000；接受標準MCP _meta.web_search_work_ms縮短為Python父層剩餘工作預算，不能放寬部署上限。傳輸signal也連到budget，active集合供S3斷線取消。
- 驗證npm run build與三份Node回歸均exit 0，retention14/14；靜態入口斷言已隨明確budget傳遞更新。
- 真stdin/程序收尾依S3，Python啟動與初始化有界依P5-S3；目前沒有宣稱父層300秒已驗證。

### P4-S3 — stdin EOF與有界程序收尾（G5/G8，AC08/10）
- 產品範圍index.ts、browser-pool.ts。stdin end/close、SIGINT/SIGTERM中止active budgets，再關唯一pool後退出；重複shutdown/close共用promise。summaries不再每次closeAll，正常工具只釋放自己的lease，不關其他呼叫的browser。
- pool有界等待launch與browser.close；close失敗不蓋既有結果。Linux /proc只記錄本Node直接子程序、帶本process專屬ownerFlag的Chromium及其starttime/獨立pgid；有界close後僅對仍符合原身分的自有程序群組收尾，不碰其他browser。
- 縮短部署timeout的reserve採min(15000,max(1500,total×5%),total/2)，預設仍285000/15000；讓可控短期限留合理清理時間。
- 真實檢查：Conda app、隔離暫存/日誌、timeout40 Python create_session(_spec_to_connection(_web_search_spec()))，本機HTTP空HTML→真Chromium fallback；回Page read status=text、HTTP/browser共2次、真正title及22字內容。call含startup 1.290s；退出session關stdin後0.023s返回（未等SDK2秒SIGTERM）。
- 同一腳本在呼叫中記錄sh PID42814/PGID42814、Node42816、grep42817及Chromium group42830（含42832/42833/42846/42850/42863）；返回後同腳本核對原starttime，存活殘留[]，無需補殺。沒有公開網路請求。
- 後續檢查補上pending launch＋shutdown不能互等、close failure保留known result、重複close一次；build及三Node檔exit0（retention14/14），最後Timeout資源0。故障注入輸出兩條Resource cleanup診斷屬預期。
- P5真入口將在最新程式上複驗；父層startup/initialize/cleanup總上限仍待P5-S3。

### P5-S1a — Node設定消費群（G5/G6/G8，AC07/09/11）
- S1按設定群拆a（Node三消費處）與b（Python allowlist／README）；本步只改browser-pool.ts、index.ts、search-engine.ts，遵守3產品檔上限。
- MAX_CONCURRENT_PAGES/HTTP從部署設定取正整數，預設各2；BROWSER_HEADLESS只接受true/false。server啟動即驗DEFAULT_TIMEOUT及MAX_CONTENT_LENGTH，不留silent NaN。
- 原DEBUG_BING_SEARCH只剩未使用變數、DEBUG_BROWSER_LIFECYCLE已無consumer，依計劃刪除而非留假開關；P5-S1b清楚列不支援。
- build與browser-lifecycle、retention皆exit0（14/14）。新增部署HTTP=1實際peak1、pages=0及HTTP=1junk明確拒絕；沒有新增環境依賴。

### P5-S1b — Python allowlist與真env行為（G5/G6/G8，AC07/11）
- 產品app/agent/mcp.py只傳MAX_CONTENT_LENGTH/DEFAULT_TIMEOUT/BROWSER_HEADLESS/MAX_CONCURRENT_PAGES/MAX_CONCURRENT_HTTP；嚴格驗值。停用最優先，自訂command不混入dist參數，收到同一allowlist；不轉TMPDIR/proxy、舊開關或其他provider秘密。
- vendor README新增直接設定表、優先序與Unicode/0/timeout語意，修正Firefox安裝與評分敘述；列出失去consumer的debug及舊設定不再支援。未執行安裝。
- 首次編輯腳本Python字串嵌套docstring語法錯誤，exit1，未修改檔案；修正編輯腳本後完成。focused pytest隔離執行tests/test_mcp.py tests/test_mcp_stderr_log.py -q -p no:cacheprovider：exit0、26 passed、0.74s。
- 真Agent MCP loader→vendored dist→本機長HTML：MAX_CONTENT_LENGTH=37，省略返回37、顯式71返回71、0返回37，original=699且實際Unicode正文長度一致，10001明確拒絕；呼叫各0.359/0.365/0.346s。這不是只查spec.env。
- 同一腳本監測discovery與4次call共15個wrapper/Node/grep PID，返回後存活殘留[]；無公開網路請求、無需補殺。下一步P5-S2故障隔離。

### P5-S2 — Resolver／準備／載入各別隔離（G6/G8，AC12）
- 只改產品app/agent/mcp.py與startup.py。每resolver捕捉並列server/resolve/原因；缺dist或node與enabled卻缺command進diagnostics。_spec_to_connection與stderr準備放進per-server try，load錯誤保留原隔離並標stage。
- startup有無extension一律共用同一diagnostics與spec合併入口；單server失敗不清空其他已載工具。沒有改paths.py／stdout filter／log rotation。
- 最少回歸覆蓋resolver拋錯、prepare PermissionError、get_tools RuntimeError、missing build診斷、有/無extension兩情境仍保留healthy MCP與read_file/bash/rag_search。
- 隔離環境執行pytest tests/test_mcp.py tests/test_mcp_stderr_log.py tests/test_extension_mcp.py -q -p no:cacheprovider：exit0、39 passed、0.77s；補強既有失敗stage斷言後tests/test_mcp.py重驗exit0、24 passed。只有既有LangChain deprecation warning。
- 下一步P5-S3：按installed adapter hook實際能力涵蓋startup/initialize/call/cleanup。

### P5-S3 — Python完整呼叫與收尾預算（G5/G6/G8，AC10/11）
- 已讀installed MultiServerMCPClient/convert_mcp_tool_to_langchain_tool/create_session及mcp1.27 stdio_client。實驗重現原handler：結果已發送、取消落SDK收尾後0.5s仍pending（總0.809s）；同腳本僅清理本次PID44005群組。也確認adapter的request hook不傳call_tool(meta)，且handler直到session退出才交付結果。
- 依具體證據在mcp.py的既有tool_interceptor局部接native create_session：沒有新client框架／持久session／site-packages修改。discovery及每次call從啟動前計單調期限，預留清理、把剩餘工作時間用標準_meta交Node；Node再提前最多250ms回傳，避免deadline競速丟掉已知候選。
- 每call用opaque內部ID標記自有stdio子程序；只檢查本Python直接子程序env並沿其後代記PID/starttime/pgid，取消／逾時清理保留到總預算內，必要時僅終止本次原身分群組。已接收結果先保存，清理失敗只記warning；未收到結果則明確timeout，不偽造部分資料。
- 首次真37/71/0/10001複驗在10001遇到SDK TaskGroup把McpError包成ExceptionGroup，錯誤文字不再可見（exit1）。仿adapter原本既有的capture-then-reraise方式，在context外重拋原協定錯誤；新增最小回歸後修復，沒有掩蓋失敗歷史。
- 隔離focused pytest三模組最後exit0、46 passed（新增7個本機真程序案例：slow startup/initialize/tool/close、剩餘meta、cleanup期caller cancellation、協定錯誤）；800ms部署案例皆斷言<0.8s、同腳本記錄PID已退出。caller取消與已收結果以result_received診斷區分。
- 最新真Agent env複驗：37/71/0與10001拒絕通過，0.359/0.400/0.353s，15個本次PID，殘留[]。
- 最新真Node、DEFAULT_TIMEOUT=5000：本機HTTP空字→Chromium正文0.789s；慢HTTP3.394s回明確timeout，兩者均<5s；同腳本15個wrapper/Node/Chromium PID殘留[]。
- 另以故意忽略EOF/SIGTERM的本機Node＋真Chromium驗父層強制收尾：DEFAULT_TIMEOUT=3000，結果先取得，2.504s內返回known browser result並warning；同腳本追蹤sh44975/Node44977/grep44978/Chromium獨立群44990及子程序，殘留[]，無需腳本額外補殺。
- 沒有公開網路或付費呼叫。測試工具JS拼接曾誤用index而非indexOf，工具腳本在啟動檢查前失敗；修正後執行，產品不受影響。下一步P6-S1真入口整合與有限公開smoke。

### P6-S1 — 新dist、實際Python入口與公開觀測（G7/G8，AC03–11/14）
- 續跑gate：仍GUI，HEAD741e5f4，tracked/index乾淨、僅原app/store/未追蹤。重新npm run build exit0；retention14/14、content-contract、browser-lifecycle皆exit0（兩個cleanup故障注入診斷屬預期）。
- 本機整合只控制引擎的HTTP邊界，MCP client、resolver/loader、shell wrapper、新dist、策略B、formatter、HTTP/browser均為實際實作；以暫存Node --import覆寫兩個引擎方法回指定候選，沒有改產品或mock MCP client。
- 受控2+重複+3候選：redirect、無.pdf的PDF、404、動態DOM、缺Content-Type五筆。full(false)/full(true)/summaries URL與順序相同，false正文請求0；true0.879s，實際HTTP5＋browser1次，text2/unsupported_media2/http_error1、returned5，第三引擎策略停止。HTTP redirect的兩跳仍是一個來源HTTP讀取，未當作重試；server觀察7個HTTP請求（含redirect下一跳及browser導覽）。
- 實際finalURL /landing?encoded=%252F、自己的page title、有效base解析 /next?q=%252F 均正確；PDF bytes不出現在正文；動態頁script插入Actual DOM text，Axios無文字後真正Chromium取得，兩個attempt可見。相同腳本18個wrapper/Node/Chromium PID、殘留[]。
- 以下四組為唯一已做的公開請求組；工具組皆經agent.mcp→新dist，沒有LLM：
  1. full-web-search：Python 3.13 asyncio task cancellation documentation，limit3、部署正文500；5.153s，Bing3候選，其他兩引擎足額策略停止。三來源HTTP200皆是Bing導向中介頁，輸出實際中介文字與href、未知page title，未冒稱目標文章或核實內容。
  2. get-web-search-summaries：technology news 2026-10-21，limit3；2.225s，Bing3候選、正文0次，來源與引擎狀態可見。返回的是字典／百科等廣泛結果，不是已驗證新聞。
  3. get-single-web-page-content：https://docs.python.org/3.13/library/asyncio-task.html；0.957s，HTTP200 text/html、真正title/finalURL，原正文62510 code points，因完整連結邊界實際交付453≤500，明確truncated。三組discovery0.861s、24個本次PID、殘留[]。完整可讀輸出在/tmp/web-search-p6-public-SM9W9z/public-results.json。
  4. 同dist adapter（清楚不等同Python tool call）的三引擎觀測，共4.726s：Bing3.438s、2次傳輸／3筆；DDG0.366s、1次／0解析；Brave0.316s、Chromium實際導覽回HTTP429、不重試。Chromium139.0.7258.5、無Firefox；同腳本8個PID殘留[]。完整觀測在/tmp/web-search-p6-public-iuAwuk/public-results.json；只在log記必要查詢與status，不複製匿名登入導覽的nonce等冗餘參數。
- Bing實際search導航q仍是完整技術查詢（含3.13/asyncio/cancellation），沒有程式截成單詞；排序偏廣是本次引擎結果，沒有新增語意過濾或猜redirect目的地。DDG本次零解析與Brave429各自如實記錄，沒有以一次觀測推斷永久不可用或擅自停用。
- 公開組累計13.061s（4/6組，低於480s）；沒有環境網路阻塞。引擎結果能否回答技術／新聞問題不在MCP保證內，不把這次資料取得驗收當作研究相關性或新聞準確性驗收。
- 真env37/71/0/10001、真timeout/cancel/EOF與強制收尾復用P5-S3最新證據；無未滿足的本步技術驗收。下一步量測分段及D05，最後完整suite。

### P6-S2 — 分段生命週期與D05（G7/G8，R12，AC14）
- 量測沿agent.mcp resolver/loader→wrapper→新dist。只在repo外暫存Node --import以方法wrapper寫stderr計時、Python暫存context wrapper記native session階段；未改產品／site-packages，沒有MCP stdout診斷。三類各取一次，沒有benchmark campaign或第二輪測量。
- discovery總0.704s，其中stdio建立3.825ms、Node初始化681.344ms、close9.079ms；測量含首次module/程序冷啟動，不當成穩定分布。

| 路徑 | stdio＋initialize ms | search ms | body ms | SDK/session close ms | 端到端 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 搜尋資訊（公開第5組，同technology news 2026-10-21、limit3） | 328.155 | 6319.365 | 不適用 | 28.084 | 6686.912 |
| 本機純HTTP | 314.958 | 不適用 | 23.865（HTTP23.338） | 5.974 | 350.593 |
| 本機動態DOM／真Chromium | 344.932 | 不適用 | 90.437（HTTP11.914＋browser77.909） | 35.596 | 480.284 |

- Chromium取得另量search201.474ms、正文35.195ms，已含相應search/body時間，不重複加總。Node pool close分別20.770/0.194/30.010ms；SDK close另含stdin/wrapper返回。
- 同一腳本24個本次wrapper/Node/Chromium PID，存活殘留[]；實際browser讀到Actual DOM timing text、attempts2。完整輸出與數據在/tmp/web-search-p6-timings-1L7BIF/timings.json。暫存diagnostics只在該次child命令生效，產品src/dist沒有加入量測程式。
- 公開第5組6.687s，累計5/6組、19.748s<480s；未使用第6組，不再追加公開請求。
- **D05決策：保留逐次session，不實作重用。** 本樣本startup/init約0.315–0.345s，在極快本機HTTP路徑佔大部分，但絕對耗時小；close6–36ms，沒有本樣本長timer收尾。使用頻率與真實任務收益未知，現有證據不足支持新增ChatSession持久client及其狀態管理。這是量測後取捨，不宣稱相對基線的性能改善或普遍延遲分布。
- 下一步P6-S3：最終完整app suite（最多兩次授權，尚未執行本次完整suite）與AC/commit/範圍核對。

### P6-S3-V1 — 首次完整suite與最終對照
- 已檢查pytest設定／shared fakes及既有baseline；沒有需live付費provider的前提。Conda app、repo外/tmp/web-search-p6-suite-o3AVPX的cache/log/tmp隔離，PYTHONDONTWRITEBYTECODE=1。
- 從app實際執行timeout 600 poetry run pytest -q -p no:cacheprovider：exit0、1512 passed、43.62s；兩個warning為LangChain既有deprecation及既有zip重複member故障fixture。完整輸出/tmp/web-search-p6-suite-o3AVPX/pytest.log。
- 同指令在suite前後只讀app/store路徑/型別/size/mtime/mode指紋，比對相同；tracked/index仍乾淨，只有原app/store/未追蹤。
- structural lint：Conda app Python執行既有validate_plan.py --json，exit0，13檔、0 errors/warnings。16個變更檔案無CR；沒有AGENTS/依賴/lock/env/store改動。
- 對照P2資料契約時發現兩處尚存缺口，以下P2-S3最小修補後，才將第二次完整suite當作最終證據；本次通過歷史保留。

### P2-S3 — 驗收發現的搜尋metadata／相對URL缺口（G2/G4/G8，R04/05/06，AC03/05）
- 修補前在當時dist直接離線重現：Bing snippet「AI.」被既有>20字門檻丟成空字串；以實際base https://www.bing.com/search/path/ 解析../item?q=%252F，原程式錯成根目錄/item，正確應/search/item。
- 只改產品search-engine.ts：移除搜尋snippet長度／時間詞門檻；所有實際引擎parser傳實際final URL及有效HTML base作標準解析；DDG相對/l/?uddg也只解碼一次。依原「未知留空」契約保留沒有title但有URL的候選，不再從snippet捏造Brave title。
- 在既有retention檔新增單一inline parser案例，覆蓋短snippet、缺title、實際頁面base／base href、DDG相對wrapper和%252F；兩份既有fake page補url()接點，沒有新測試框架。
- npm run build及三份Node檢查exit0；retention15/15、正文契約與資源/取消/清理檢查通過。公開觀測的絕對URL／正常snippet與Python/正文/生命週期路徑未改，不再追加公開請求；仍5/6組、19.748s。
- 本步檢查與紀錄後獨立commit，再跑最後一次完整suite；未改計劃phase檔或擴大目標。
