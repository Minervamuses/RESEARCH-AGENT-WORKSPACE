# 執行狀態與證據
本文件是唯一動態狀態擁有者。規劃交付不代表產品實作；目前沒有實作階段、產品build、產品測試、網路smoke或模型遵循驗收已完成。

## 階段狀態
| 階段 | 狀態 | 實際證據 | 阻塞 | 下一動作 |
| --- | --- | --- | --- | --- |
| P1 | Not started | 無 | 尚未收到執行計劃指令 | 讀P1並完成P1-S1 |
| P2 | Not started | 無 | 同上 | P2-S1搜尋候選契約（必要時拆P2-S1a/b） |
| P3 | Not started | 無 | 相依P2 | P3-S1轉換 |
| P4 | Not started | 無 | 相依P3 | P4-S1資源擁有 |
| P5 | Not started | 無 | 相依P4；P5-S2可獨立 | P5-S1設定傳遞 |
| P6 | Not started | 無 | 相依P1/P3/P5 | P6-S1真實入口驗收 |

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
