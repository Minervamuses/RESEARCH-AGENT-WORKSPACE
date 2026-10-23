# 對話分析：驗收 web-search-citation 計劃（session 510d4b09）

- Session：`510d4b09-c6f3-4a71-b1c6-7887a26ab77a`，標題「Web search citation plan review」
- 期間：2026-10-21 07:34 → 2026-10-22 03:25（UTC；台北時間 +8）
- 主 agent：Claude Opus 5.5，effort xhigh；subagent：Claude Sonnet 5.5
- 你的訊息：4 則，分別是開場指令、兩次「usage 已重置，請繼續」、一次「Try again」
- 分析日期：2026-10-22

---

## 1. 資料來源與合併方式

| 來源 | 路徑（`~/.claude/projects/-home-minervamuses-research-agent-workspace/` 底下） | 用途 |
|---|---|---|
| 主對話 | `510d4b09….jsonl` | 主 agent 的 64 次 API 呼叫（另有 3 則撞限訊息）、60 次工具調用與工具回報、使用者訊息、task 通知 |
| 外存工具輸出 | `510d4b09…/tool-results/*.txt`（23 個） | 主檔只保留 2KB 預覽的大輸出；分析時讀回原檔計算實際長度 |
| Workflow 狀態 | `510d4b09…/workflows/wf_*.json`、`workflows/scripts/*.js` | 3 個 workflow 的腳本、phase 設計和最終狀態 |
| Workflow journal | `510d4b09…/subagents/workflows/<runId>/journal.jsonl` | 每個 agent 的 started／result／failed 事件、結構化結果、快取 key |
| Subagent 紀錄 | `510d4b09…/subagents/workflows/<runId>/agent-*.jsonl` 和 `.meta.json` | 167 個 subagent 各自的 API 呼叫、工具調用和 usage |

**合併規則：**

- **usage 去重**：一次 API 回覆在串流時會寫成多行，每行都帶 usage，而且數字會逐步累加，總共有 2,340 個 message id 出現這種情形。分析時以 `message.id` 去重，每個欄位取最大值，也就是最終值。直接把每行加總會嚴重高估。
- **工具調用與回報**：用 `tool_use.id` ↔ `tool_result.tool_use_id` 配對，算出每次工具的耗時和回報大小。
- **Subagent 的用途**：用 journal 的 `agentId → label/phase` 對應。label 有固定格式，例如 `review:<維度>`、`verify:<維度>:<發現編號>:<視角>`、`critic:*`。
- **Subagent 屬於哪一次執行**：同一個 runId 的目錄裡混著首跑和續跑的 agent，所以依每個 agent 第一次 API 呼叫的時間，對照主對話裡每次啟動 workflow 的時間來劃分。

**資料的限制：**

- thinking 只存了簽章，內容是空的。只能看到 thinking token 數，看不到推理內容。
- journal 沒有時間戳，時間一律取自 agent 紀錄。
- 背景 task 的輸出檔（`/tmp/claude-1000/.../tasks/*.output`）在第三次撞限後已被清掉，當時的對話本身也是從 journal 重建結果的。
- 從紀錄看不出計費方式：請求帶有 `oauth` beta，看起來是訂閱額度，不是 API 計費。因此本報告只列 token，不換算金額。

---

## 2. 總覽

| 指標 | 主 agent（Opus） | Subagents（Sonnet） | 合計 |
|---|---:|---:|---:|
| API 呼叫（不含撞限的 synthetic 訊息） | 64 | 2,799 | 2,863 |
| 工具調用 | 60 | 3,336 | 3,396 |
| input（未快取） | 132 | 5,598 | 5,730 |
| cache write | 814,581 | 11,958,800 | 12,773,381 |
| cache read | 12,378,822 | 276,952,621 | 289,331,443 |
| output（含 thinking） | 84,031 | 3,528,807 | 3,612,838 |
| 其中 thinking | 35,857 | 1,951,709 | 1,987,566 |
| **四項合計** | **13.28M** | **292.45M** | **305.73M** |

- 約 **95.7%** 的 token 由 subagent 消耗，主 agent 只佔 4.3%。
- token 主要是 cache read（94.6%）。每個 subagent 每次 API 呼叫都要重讀自己的整段上下文；平均每個 review agent 做 57 次工具調用，上下文越滾越大。
- 牆鐘時間共 19 小時 51 分。其中約 **15 小時 39 分在等 usage 重置**，實際運作約 4 小時 12 分。
- 3 個 workflow 共 6 次執行，派出 167 個 subagent 實例，對應 118 個不同的 label。最後成功 118 個，失敗 35 個，被中止 14 個。

---

## 3. 主對話時間線：每一步做了什麼、用途、消耗

時間為 UTC。「呼叫」是主 agent 的 API 呼叫數；output 含 thinking；「工具秒數」是工具實際執行的時間。

| 階段 | 時間 | 做了什麼 | 用途 | 呼叫 | cache read | output | 工具秒數 |
|---|---|---|---|---:|---:|---:|---:|
| S01 載入 skill | 07:34:39 | 自動載入 `workflow-authoring`；主 agent 呼叫 `long-horizon-plan-author` | 取得 workflow 腳本規則，以及計劃驗收（verification）的規範 | 4 | 79k | 1.1k | 1 |
| S02 讀計劃與證據 | 07:34:47 | 讀 GOALS／PLANS／PROMPTS／acceptance.md、build-log（43KB，外存後再讀回）、`git log/diff 3225a90..HEAD` | 建立「要驗什麼」的基準：G1–G8、AC01–AC16、20 個執行 commit | 5 | 405k | 1.9k | 2 |
| S03 協調者親自先驗 | 07:35:20 | 在 scratchpad 重編 `dist` 並逐位元組比對、跑 3 支 Node 測試、跑 focused pytest 和全套 pytest | 先確認低成本、可直接觀察的事實，這些結論再交給 subagent 作為「已確認、不必重做」 | 6 | 697k | 4.6k | 61 |
| S04 撰寫並啟動 workflow #1 | 07:37:00 | 一次產出 36.5KB 的 workflow 腳本，含 10 個覆核維度、反駁驗證、完整性審查、補漏 | 把驗收拆成可平行、可互相反駁的獨立檢查 | 1 | 121k | **32.9k** | 14 |
| S05 等待中讀 phase 檔 | 07:42:12 | 讀 6 份 build/phase-*.md，向你回報先驗結果 | 為之後判讀 workflow 結果做準備 | 3 | 439k | 1.1k | 0 |
| S06 撞限 #1 | 08:01:52 | 收到 workflow 結束通知，主 agent 一回應就撞到 session limit | — | 1 | 0 | 0 | — |
| S07 續跑 #1 | 12:41:30 | 讀 journal，確認 28 個成功、21 個失敗，用 `resumeFromRunId` 重新啟動 | 只想重跑失敗的部分（實際並非如此，見 §5.3） | 2 | 206k | 1.4k | 3,314¹ |
| S08 讀結果並親自重現 | 13:37:15 | 解析第一輪結果；寫 `nested.mjs`／`nested2.mjs` 重現巢狀表格指數膨脹，以及只取第一個 `main`/`article` 的問題 | 主 agent 對關鍵發現做第二手確認 | 7 | 1,333k | 5.2k | 4 |
| S09 撞限 #2 | 14:10:13 | 同 S06 | — | 1 | 0 | 0 | — |
| S10 續跑 #2 → 中止 → 改寫 | 17:41:30 | 第二次 resume，發現已成功的 agent 又在重跑，改用 TaskStop 中止；檢查有無殘留程序（0 個）；改寫成內嵌既有結果的補充 workflow #2 並啟動 | 止血：避免重跑燒額度，也避免重複發出公開網路請求 | 16 | 3,334k | 12.6k | 752¹ |
| S11 補充 workflow 修正 | 18:21:15 | workflow #2 的 16 個 agent 都完成，但組裝結果時缺少 `coverageDigest` 函式而失敗；補上後 resume（16 個全部命中快取）；親自驗證 owner flag 從未生效 | 修正腳本錯誤，並再確認一項發現 | 6 | 1,472k | 3.6k | 36 |
| S12 撞限 #3 | 19:13:06 | 同 S06 | — | 1 | 0 | 0 | — |
| S13 Try again → 重建 → GAP-2 | 02:41:10 | task 輸出檔已被清除，改從 journal 重建結果；針對失敗的 GAP-2 另寫 workflow #3 啟動 | 補上最後一塊缺口 | 10 | 2,491k | 13.3k | 22 |
| S14 統整 | 03:24:10 | 讀 GAP-2 結果並抽查 3 項；寫 memory（Bash 寫入被沙箱擋下，改用 Edit）；給出最終報告「有條件通過」 | 產出驗收結論並保存跨對話記憶 | 6 | 1,803k | 6.4k | 1 |

¹ Workflow 工具「從呼叫到回報 launched」的時間。續跑 #1 花了 55 分鐘（12:41:56→13:37:10），續跑 #2 花了 12 分鐘。這段期間沒有任何 subagent 活動，也沒有 token 消耗，紀錄裡也沒有說明原因。可能是等待確認或啟動 replay，無法從紀錄判定。

**主 agent 的工具組成**：Bash 48 次、Workflow 6、Skill／Read／ToolSearch／TaskStop／Write／Edit 各 1。

主 agent 最大的單筆 output 是 S04 撰寫腳本（32.9k，佔主 agent output 的 39%）。cache read 則隨上下文膨脹逐步上升：後期每次呼叫要讀 20–30 萬 token。

---

## 4. Subagent 調用細節（重點）

### 4.1 三個 workflow 的設計

**Workflow #1 `accept-web-search-citation-plan`（`wf_f82a84a2-a4e`）**：主驗收，分四個 phase。

1. **Review**：10 個獨立維度的 reviewer，各自對照程式碼、測試、git 和自己寫的 probe 驗證，並被明確要求「不要相信 build-log」。
   - 維度：citation、search、content、length-stats、node-lifecycle、python-integration、integration-measurement、git-process、code-review、spec-trace。
2. **Verify**：每個發現都交給對抗式驗證者嘗試推翻。
   - major／blocker 用 3 個視角各派一個 agent：reproduction（缺陷真的存在嗎）、requirement（計劃真的要求這件事嗎）、impact（實際影響和嚴重度）。投票規則：≥2 個推翻就 DROPPED；≥2 個確認就 CONFIRMED；其餘為 PLAUSIBLE。
   - minor 用 1 個合併視角（single）。
3. **Critic**：完整性審查，找出沒查到或證據薄弱的地方。
4. **Gaps**：針對 critic 提出的缺口做補查。

**Workflow #2 `accept-web-search-citation-followup`（`wf_28a993f0-567`）**：S10 改寫的版本。把 #1 已有的結果直接內嵌進腳本，只跑還缺的部分：code-review 維度、尚未驗證的 F5、critic，以及 5 項補漏檢查 fgap1-1 至 fgap1-5。

**Workflow #3 `accept-web-search-citation-gap2`（`wf_2d41714c-f20`）**：只重試在 #2 撞限失敗的 fgap1-2（測試敏感度：用 155 個單點 mutant 檢驗測試會不會抓到錯），再跑最終 critic。

### 4.2 六次執行一覽

| 執行 | 時間（UTC） | agent 數 | 成功 | 失敗／中止 | 重跑已成功者 | token 合計 | output | 工具調用 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| R1 wf#1 首跑 | 07:42–08:01 | 49 | 28 | 21 | 0 | 101.2M | 1.14M | 976 |
| R2 wf#1 續跑 #1 | 13:37–14:10 | 57 | 45 | 12 | **14** | 87.9M | 1.05M | 1,085 |
| R3 wf#1 續跑 #2（手動中止） | 17:54（35 秒） | 14 | 0 | 14 | **13** | 5.2M | 0.04M | 126 |
| R4 wf#2 首跑 | 17:56–18:21 | 16 | 16 | 0 | 0 | 24.2M | 0.31M | 308 |
| R5 wf#2 resume | 18:22–19:13 | 18 | 16 | 2 | 0 | 49.2M | 0.65M | 521 |
| R6 wf#3 GAP-2 | 02:43–03:24 | 13 | 13 | 0 | 0 | 24.7M | 0.33M | 320 |

R5 的 16 個「成功」是新跑的 critic 和 gap agent。R4 的 16 個結果在 R5 是命中快取，沒有產生新的 agent 紀錄。

### 4.3 各類 subagent 的平均成本（只計成功者）

| 類型 | 數量 | 平均耗時 | 平均工具調用 | 平均 output | 平均 token 合計 |
|---|---:|---:|---:|---:|---:|
| review／gap（深度覆核） | 17 | 15.8 分 | 56.6 | 85.9k | 7.62M |
| verify（對抗驗證） | 99 | 2.1 分 | 16.7 | 12.6k | 0.84M |
| critic（完整性審查） | 2 | 7.0 分 | 25.0 | 51.1k | 2.26M |

一個 review agent 的成本大約等於 9 個 verify agent。subagent 的工具幾乎全是 Bash（例如 code-review 是 Bash 72 次、StructuredOutput 1 次），也就是大量實際執行 probe，而不是只讀檔。

### 4.4 每個 review／gap agent 的產出

| 執行 | agent | 發現數 | 耗時 | 工具 | output | 做了什麼（摘自 agent 回報） |
|---|---|---:|---:|---:|---:|---|
| R1 | review:citation | 3 | 3.7 分 | 39 | 26k | 確認 SKILL.md 只新增 2 行，且與 phase-01 逐字相同；實際載入 citation skill 驗證 |
| R1 | review:search | 8 | 11.1 分 | 41 | 73k | 對照 search-engine.ts／utils.ts／types.ts 驗證 G2、AC01、AC03、AC05 |
| R1 | review:content | 10 | 15.3 分 | 36 | 72k | 用本機 node:http 和 dist 的 extractor 做 probe |
| R1 | review:length-stats | 9 | 15.8 分 | 63 | 101k | 經由 MCP stdio 呼叫真正的 dist/index.js，本機 HTTP 提供頁面 |
| R1 | review:node-lifecycle | 7 | 17.2 分 | 60 | 103k | 讀 browser-pool 等 5 支檔案，跑 20 個 probe |
| R1 | review:integration-measurement | 7 | 15.2 分 | 73 | 106k | 對照 P6 證據，並在沙箱外重新觀察 Python→sh→Node 路徑（會發出公開網路請求） |
| R1 | review:git-process | 6 | 10.6 分 | 58 | 65k | 逐 commit 重編並重測，驗證 G8／AC16 |
| R2 | review:python-integration | 9 | 19.7 分 | 62 | 108k | 讀 langchain_mcp_adapters 0.2.2／mcp 1.27 原始碼，重跑 pytest（R1 撞限失敗後重做） |
| R2 | review:spec-trace | 11 | 14.3 分 | 66 | 98k | 追溯 R01–R12、AC01–AC14、G1–G8 到 HEAD（R1 撞限失敗後重做） |
| R2 | review:integration-measurement | 8 | 20.1 分 | 74 | 112k | **重跑**：R1 已成功，因快取前綴失效又跑一次 |
| R2 | review:git-process | 3 | 11.4 分 | 64 | 70k | **重跑**：同上 |
| R4 | review:code-review | 14 | 21.0 分 | 73 | 131k | 審 3225a90..HEAD 的完整 diff，每個疑點都寫 probe 重現（前兩次都撞限失敗，第三次才完成） |
| R5 | critic:f1 | — | 7.8 分 | 28 | 55k | 對所有累積結果做完整性審查 |
| R5 | review:fgap1-1 | 5 | 14.1 分 | 49 | 89k | 沙箱外測 SIGTERM／SIGINT／stdin EOF／SIGSTOP 的 Chromium |
| R5 | review:fgap1-3 | 3 | 7.7 分 | 46 | 47k | 以真實 Chromium 量測 browser fallback 延遲渲染的回歸 |
| R5 | review:fgap1-4 | 7 | 32.4 分 | 54 | 80k | 經真實 Python→Node 路徑測 event loop 阻塞 |
| R5 | review:fgap1-5 | 4 | 11.1 分 | 44 | 58k | 用真實 stdio 子程序測 loader 和 startup |
| R6 | review:fgap1-2-retry | 10 | 28.0 分 | 60 | 121k | 對應每條 phase 最低測試要求到實際 assertion，跑 155 個 mutant |
| R6 | critic:final | — | 6.2 分 | 22 | 48k | 最終完整性判定 |

### 4.5 對抗驗證的結果

成功的 99 個 verify agent 中：**confirmed 94、refuted 5**，推翻率約 5%。

不過 confirmed 往往伴隨嚴重度下修（例如 `major -> minor`），所以 verifier 的主要作用是**校正嚴重度**，不是過濾假發現。若要用在論文中評估「對抗驗證是否值得成本」，這是一個可以討論的數據點：verify 共花約 96M token（含失敗與重跑），佔 subagent 總量的 33%。

完整清單見 [data/subagents_detail.csv](data/subagents_detail.csv) 的 `verdict`、`severity`、`result_summary` 欄。

---

## 5. Usage 用完與接續跑的完整過程

### 5.1 時序

```
07:34  開始（額度窗 W1）
07:42  R1 啟動，49 個 agent
08:00:58–08:01:51  W1 用完：21 個 agent 在同一分鐘內收到
       "You've hit your session limit · resets 8:40pm (Asia/Taipei)"
08:01:52  主 agent 處理 task 通知 → 同樣撞限，對話停止
          ── 等待 4h40m（重置 12:40；你 12:41 回來） ──
12:41  「Please continue」→ 主 agent 讀 journal → resume wf#1
12:41:56→13:37:10  Workflow 工具 55 分鐘才回報 launched（期間無 agent 活動）
13:37  R2 開始，57 個 agent（其中 14 個是重跑已成功者）
13:58:17–13:58:35  W2 用完：11 個 agent 撞限（resets 1:40am）
14:10:11–12  最後 2 個 agent 撞限；主 agent 14:10:13 撞限
          ── 等待 3h31m（重置 17:40；你 17:41 回來） ──
17:41  「Please continue」→ 第二次 resume wf#1
17:41:45→17:53:57  啟動又花 12 分鐘
17:54  R3 啟動 35 秒內，主 agent 讀 journal 發現同 key 已有兩次 result
       （已成功的又在重跑）→ TaskStop 中止 14 個 agent
17:54:46  檢查殘留 Chromium 程序：0
17:55  改寫成 wf#2（內嵌既有結果，只跑缺的）→ R4
18:21  R4 的 16 個 agent 全部完成，但腳本組裝失敗（缺 coverageDigest）
18:21  修腳本 → resume（R5）：16 個命中快取；開始 critic 與 5 個 gap
19:13:04  W3 用完：fgap1-2（已跑 43 分鐘、15.3M token）與 critic:f2 失敗
19:13:06  主 agent 撞限（resets 6:40am）
          ── 等待 7h28m（重置 22:40；你 02:41 回來，即台北時間隔天 10:41） ──
02:41  「Try again」→ task 輸出檔已被清除 → 從 journal 重建結果
02:43  wf#3 只重試 GAP-2 → R6，13 個 agent 全部成功
03:25  最終驗收報告：有條件通過
```

### 5.2 每個額度窗消耗多少

這三個撞限的窗，等於提供了「一個 session 額度大約多大」的實測數據：

| 額度窗 | 主 agent 呼叫 | subagent 呼叫 | cache read | cache write | output | 結果 |
|---|---:|---:|---:|---:|---:|---|
| W1（→08:01） | 17 | 824 | 98.4M | 3.51M | 1.19M | 撞限 |
| W2（12:40→14:10） | 9 | 890 | 84.8M | 3.85M | 1.06M | 撞限 |
| W3（17:40→19:13） | 22 | 809 | 78.6M | 4.06M | 1.02M | 撞限 |
| W4（22:40→結束） | 16 | 276 | 27.5M | 1.35M | 0.35M | 未撞限 |

三個撞限的窗，消耗量都落在 **約 800–900 次 API 呼叫、output 約 1.0–1.2M、cache read 約 80–100M**。以這種「十幾個 Sonnet agent 平行跑 Bash probe」的工作型態，一個額度窗大約只撐得住 20–30 分鐘的牆鐘時間。

### 5.3 為什麼續跑會重跑已成功的 agent

Workflow 的 resume 規則是：**只有「最長未變前綴」的 agent() 呼叫會取用快取；從第一個不同或新的呼叫開始，之後全部即時重跑。**

R1 的失敗者（code-review、spec-trace、python-integration）在呼叫順序上排在前面，所以 resume 時前綴很早就斷了。後面已成功的 agent 也跟著被重跑，例如 integration-measurement 和 git-process 的 reviewer。它們的新結果又產生新的 verify 呼叫。R2 的對話紀錄裡，主 agent 說「已完成的結果會直接取用快取」，事實上並非如此。

| 浪費類型 | agent 數 | token 合計 | output |
|---|---:|---:|---:|
| 撞限失敗或被中止（工作成果丟失） | 49 | 74.95M | 0.72M |
| 重跑已成功者（結果重複） | 14 | 29.43M | 0.32M |
| **合計** | 63 | **104.4M（佔 subagent 總量 36%）** | 1.03M（29%） |

撞限失敗中最貴的幾筆：

- R1 spec-trace：17.1M
- R5 fgap1-2：15.3M
- R1 code-review：10.5M
- R2 code-review：10.5M
- R1 python-integration：7.5M

code-review 維度失敗兩次、中止一次，第三次才在 wf#2 完成，累計約 34M token。

R1 有 13 個 agent 在撞限那一刻剛啟動，token 是 0，所以不算成本，只佔 agent 數。critic:round1 連續兩次都是這種情形。

### 5.4 續跑帶來的副作用

- **公開網路請求超量**：integration-measurement 因重跑共發出 4 組公開搜尋（Bing／DuckDuckGo／Brave），超過腳本設定的 2 組上限。主 agent 在 17:56 主動揭露了這件事。這也是 R3 被立刻中止的原因之一：避免第三次重跑它。
- **證據檔遺失**：背景 task 的輸出檔放在 `/tmp`，跨夜後被清掉，只能從 journal 重建。`/tmp/web-search-p*` 和 playwright 暫存目錄在 02:42 也已不存在。
- **工具結果和 workflow JSON 的數字不一致**：`wf_f82a84a2-a4e.json` 記錄的 `agentCount 52`、`totalTokens 852,824` 只反映最後一次被中止的執行，不是三次執行的累計。分析成本時要以 agent 紀錄為準。

---

## 6. 觀察（可作為論文素材）

1. **成本結構**：主 agent 負責規劃、親自先驗和統整，只用 4%；成本幾乎都在 subagent 的深度覆核上。其中 review／gap 類 agent 成功的只有 17 個，卻消耗約 66% 的 subagent token（含失敗與重跑）。
2. **撞限是這次對話最大的成本放大器**：直接浪費 36% 的 subagent token，牆鐘時間拉長到約 4.7 倍（19h51m 對比 4h12m 實際運作）。
3. **resume 的前綴快取對「平行且部分失敗」的情況不友善**：主 agent 第二次才察覺，之後改為「把既有結果內嵌進新腳本、只跑缺的」，從 R4 開始就沒有再浪費。
4. **對抗驗證的推翻率很低（5%）**，主要價值在嚴重度校正。
5. **主 agent 會親自做第二手確認**（S03、S08、S11、S14），對 subagent 的關鍵結論不全盤採信。

---

## 7. 檔案

| 檔案 | 內容 |
|---|---|
| [data/main_calls.csv](data/main_calls.csv) | 主 agent 每次 API 呼叫一列（多工具時一個工具一列，usage 只記在第一列）：階段、usage、thinking、工具名稱、工具說明、耗時、回報大小、外存檔實際大小、是否錯誤 |
| [data/subagents_detail.csv](data/subagents_detail.csv) | 每個 subagent 實例一列：workflow、執行輪次、label、phase、模型、結果（result／failed／unknown）、第幾次嘗試、先前結果、起訖時間、API 和工具次數、主要工具、usage、verdict、嚴重度、發現數、結果摘要 |
| [data/summary.json](data/summary.json) | 各 workflow 的設計摘要、主 agent usage 合計、階段切分 |
| [scripts/analyze_session.py](scripts/analyze_session.py) | 合併主檔、外存輸出、workflow 和 subagent，產生前兩份 CSV 的前身；用法：`python3 analyze_session.py <session-id> <out-dir>` |
| [scripts/runs.py](scripts/runs.py) | 劃分執行輪次、標記重跑和失敗、併入 journal 的 verdict；用法：`python3 runs.py <out-dir>` |

腳本直接讀 `~/.claude/projects/...` 的原始紀錄。換成其他 session 時，`analyze_session.py` 裡的 `STAGES` 和 `runs.py` 裡的時間邊界 `B` 要依該 session 手動調整。
