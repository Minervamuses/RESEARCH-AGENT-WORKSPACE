# 最終彙報：詰問 skill、文體 skill 與文件 context

- 執行日期：2026-11-15。分支 `GUI`，起點 HEAD `10187aa`，最後一個實作步驟是 `ee2af13`［K8-S2］，本報告在 K8-S3 的 commit 中提交。
- 狀態來源：[build-log.md](../../build-log.md)。下文「BL K?-S?」指 build-log 中該步驟的事件段落。
- 執行者沒有呼叫任何付費 API：沒有用 `--live`，沒有啟動會連 OpenRouter 的 CLI 或桌面 app。所有模型行為都用假模型或離線替身測試。

## 1. 目標狀態

K1–K8 全部 Complete，沒有 Blocked 項目。

| 目標 | 狀態 | 證據 |
|---|---|---|
| G1 `@grill` 第一版方法 | 完成（只完成內容交付與流程測試；詰問效果未驗證） | `app/skills/grill/SKILL.md`；BL K5-S1 原則對照表；`tests/test_grill_skill.py`：載入、`@grill` 解析、一回合後失效；留言行為見 BL K5-S3 |
| G2 詰問回合可讀不可改 | 完成 | BL K5-S2；`test_grill_document_turn_reads_the_snapshot_but_cannot_edit`、`test_grill_with_another_skill_and_frozen_references_stays_read_only` |
| G3 評估框架 | 完成（只用假模型跑通） | `app/scripts/grill_eval.py`、`app/tests/fixtures/grill/cases.example.json`、`app/skills/grill/README.md`；`tests/test_grill_eval.py`（15 個）；示範輸出 `evidence/K6-S3/`；BL K6-S1–S3 |
| G4 文體 skill | 完成 | `app/skills/writing-genres/SKILL.md`；BL K7-S1 七文體 × 五點核對表；`tests/test_writing_genres.py` |
| G5 每回合回覆規則 | 完成 | `SYSTEM_PROMPT` 的「Writing rules (every turn)」；BL K7-S2；CLI 與桌面兩條路徑都有測試 |
| G6 文件佔比量測 | 完成 | `turn_trace` `model_end` 新欄位（BL K2-S1）；15 回合量測 `evidence/K2-S2/` |
| G7 歷史只保留最後提交快照 | 完成 | BL K3-S1–S3；`tests/test_document_history_replay.py`；`test_closed_document_keeps_only_the_last_submitted_snapshot`；`evidence/K3-S3/` |
| G8 同回合編輯不累積全文 | 完成 | BL K4-S1–S3；`tests/test_document_edit_compaction.py`；`evidence/K4-S3/` |
| G9 文件、完整測試、彙報 | 完成 | BL K8-S1；完整 pytest **1808 passed**，62.6 秒（`evidence/K8-S2/pytest-tail.txt`）；npm 與 cargo 不適用，因為 `git diff --stat 10187aa..HEAD -- app/desktop app/agent/desktop/protocol.py` 是空的 |

## 2. 文件 context 量測對照

量測條件：同一個 session、15 個帶文件的回合。文件約 21.8 KB（UTF-8，含中文與 emoji）。其中 11 個回合有存檔編輯；第 5 回合同一回合連續編輯兩次；第 7 回合沒有圈選範圍；第 2、6、12 回合只分析；第 9 回合帶一個舊版本的凍結引用。

使用假模型，所以數字都是**字元數**（Python code point）。假模型不回報 input tokens，`document_tokens_estimate` 在這裡無法計算；用真實模型時，`turn_trace` 會記錄這個估計值（`input_tokens × 文件字元 ÷ prompt 字元`）。

每格依序為 before（K2-S2）→ after-history（K3）→ after（K3＋K4）。「first」是該回合第一次模型呼叫，「last」是最後一次，包含同回合的工具結果。

| 回合 | 呼叫 | 全文份數 | 歷史快照字元 | 工具結果字元 | 文件字元合計 | prompt 字元 | 文件占比 |
|---|---|---|---|---|---|---|---|
| 1 | first | 1 → 1 → 1 | 0 → 0 → 0 | 0 → 0 → 0 | 7,686 → 7,686 → 7,686 | 16,681 → 16,685 → 16,685 | 46.1% → 46.1% → 46.1% |
| 1 | last | 2 → 2 → 2 | 0 → 0 → 0 | 7,697 → 7,697 → 7,697 | 15,383 → 15,383 → 15,383 | 24,975 → 24,981 → 24,981 | 61.6% → 61.6% → 61.6% |
| 5（同回合兩次編輯） | first | 5 → 1 → 1 | 30,788 → 0 → 0 | 0 → 0 → 0 | 38,507 → 7,719 → 7,719 | 52,943 → 22,200 → 22,200 | 72.7% → 34.8% → 34.8% |
| 5（同回合兩次編輯） | last | 7 → 3 → 2 | 30,788 → 0 → 0 | **15,471 → 15,471 → 8,376** | 53,978 → 23,190 → 16,095 | 69,614 → 38,875 → 31,890 | 77.5% → 59.7% → 50.5% |
| 10 | first | 11 → 1 → 1 | 77,194 → 0 → 0 | 0 → 0 → 0 | 84,959 → 7,765 → 7,765 | 108,228 → 29,724 → 29,724 | 78.5% → 26.1% → 26.1% |
| 10 | last | 12 → 2 → 2 | 77,194 → 0 → 0 | 7,777 → 7,777 → 7,777 | 92,736 → 15,542 → 15,542 | 116,605 → 38,103 → 38,103 | 79.5% → 40.8% → 40.8% |
| 15 | first | 12 → 1 → 1 | 85,327 → 0 → 0 | 0 → 0 → 0 | 93,140 → 7,813 → 7,813 | 117,773 → 31,159 → 31,159 | 79.1% → 25.1% → 25.1% |
| 15 | last | 13 → 2 → 2 | 85,327 → 0 → 0 | 7,825 → 7,825 → 7,825 | 100,965 → 15,638 → 15,638 | 126,199 → 39,587 → 39,587 | 80.0% → 39.5% → 39.5% |

- 當前回合的快照與凍結引用（current）在三組中都相同。第 9 回合因為帶舊版引用，current 是兩份全文。
- 讀碼時預估第 15 回合最多 11 份全文，實測修改前是 12～13 份。多出的來源有兩個：歷史中第 9 回合多了一份舊版引用，最後一次呼叫多了一份編輯結果（BL K2-S2）。
- 修改後第 15 回合最後一次呼叫剩 2 份：本回合提交的快照 1 份，加上最新一次存檔結果 1 份。這符合 G7 與 G8 分開計數的目標。
- 來源：`evidence/K2-S2/summary.md`、`evidence/K3-S3/summary.md`、`evidence/K4-S3/summary.md`，以及各自的 JSON。

## 3. K4 的出口：選 B

保留最新一次成功存檔結果的全文；同一回合較早的結果，在每次送進模型的訊息副本中縮成只剩更新後的範圍文字。範圍涵蓋整份文件時，連範圍文字也不留。

理由（BL K4-S1 有情境表）：

- 兩個凍結引用的範圍重疊或相鄰時，伺服器會把它們合併成一個工作範圍。模型從來沒有把這段當成一個整體看過最新文字，只給範圍文字（出口 A）會讓下一次編輯缺資料。
- 多 skill 依序執行時，後一步可能要看前一步存檔後的上下文。

實作位置在 `agent/graph.py` 的 `_agent_requests`，使用 `document_context.compact_edit_results`。graph state、前端收據與 `candidate.result` 都保持完整，並有測試證明原始訊息沒有被原地修改。

## 4. 請你確認或推翻的可逆假設

| ID | 目前做法 | 請確認的重點 |
|---|---|---|
| A1 | 詰問回覆固定先寫 `## 還原`，再寫 `## 發現`、`## 判斷`；作者回應之後加 `## 回應檢查` | 還原段要不要一直顯示？太長時要不要縮短？ |
| A2 | skill 名稱用 `grill` 與 `writing-genres` | — |
| A3 | 唯讀判斷用具名常數 `READ_ONLY_DOCUMENT_SKILLS = {"grill"}`（`agent/session.py`），沒有新增 manifest 欄位 | 之後如果出現第二個唯讀 skill，再改成 manifest 欄位 |
| A4 | 佔位符統一為 `[TODO: …]`、`[CITE: …]`、`[FIGURE: …]`；`academic-paper-writing` 第 93 行已改成同樣寫法 | 注意：bime_word 匯出 Word 時只會略過 `[TODO: …]`，`[CITE: …]` 與 `[FIGURE: …]` 會原樣留在 Word 裡（BL K1-S1）。這是否符合你的需要？ |
| A5 | 七種文體的預設格式：論文、教材、筆記、計劃書、Abstract 用 `.md`；Poster 用 `.md` 內容稿，因為本機沒有 TeX，有 TeX 時改用 `.tex` 加 `tikzposter`；投影片用 Pandoc 投影片格式的 `.md`，再轉成 `.pptx` | 特別請確認 Poster 與投影片的格式 |
| A6 | 每回合規則四條（見 `SYSTEM_PROMPT`）：辨識文體並建議 `@writing-genres`；佔位符；只有 `.md`／`.markdown`／`.tex` 能在編輯器圈選修改；詰問與改寫分開 | 內容與長度是否合適 |
| A7 | 文件 token 估計 = `input_tokens × 文件字元 ÷ prompt 字元`，欄位名稱標明是估計值 | — |
| A8 | 只提會影響作者實際主張是否成立的問題，字面與風格不在範圍內；反例必須針對作者實際提出的主張 | 依你的真實測試結果修改 |

另外有幾個執行中做的選擇，也可以推翻：

- 歷史佔位保留選取文字的條件：最多 2,000 字元，而且少於全文的一半（BL K3-S1 checkpoint）。
- 工具可用性提示中，同一 family 的工具如果分在「可用」與「不可用」兩邊，就改成逐一列出工具名稱（BL K5-S2）。不這樣做的話，`document_edit` 與 `bibliography_lookup` 都會顯示成 `desktop_document`，模型看不出哪一個被遮蔽。
- `for_agents/` 只修了兩處與新行為矛盾的描述（BL K8-S1），其他內容沒有更新，建議之後用 `$infrastructure` 重新整理。

## 5. 段落留言中的 `@grill`（K5-S3）

**實際上會啟用，而且作用於整個回合。** 前端的 `composeTurnText` 會把留言組進送出的 `text`，前後端也都會解析整段文字中的 `@名稱`。因此留言裡的 `@grill` 會讓主請求與所有引用都變成唯讀；同一回合其他留言要求的改寫不會執行，需要另外送出。前端部分只讀過程式碼，本計劃沒有修改前端。測試：`test_grill_typed_in_a_passage_comment_activates_for_the_whole_turn`。

## 6. 你自己跑真實詰問測試的方法

**執行者沒有用真實模型測試過詰問。** 目前只證明了流程與格式可以跑通，不代表詰問的品質。

1. 照 `app/tests/fixtures/grill/cases.example.json` 的格式，把真實段落寫成案例檔，`source` 設為 `real`。案例檔放在 repo 外，例如 `~/grill-cases/real.json`。格式說明見 `app/skills/grill/README.md`。
2. 先用離線替身跑一次，確認格式沒有問題（在 `app/` 下執行，免費）：

```bash
python scripts/grill_eval.py --cases ~/grill-cases/real.json --out ~/grill-runs/check --dry-run
```

3. 再跑真實模型（**會呼叫 OpenRouter 並產生費用**）。開跑前會印出案例數和最多的 `@grill` 回合數：每個案例最多 1 加作者回應數個回合，總數以 `--max-rounds`（預設 4）為上限，而每個回合可能包含多次模型呼叫。MCP（web search）預設關閉，需要時加上 `--mcp`。

```bash
python scripts/grill_eval.py --cases ~/grill-cases/real.json --out ~/grill-runs/2026-11-20 --live
```

4. 讀 `summary.md` 與 `reports/<id>.md`，把判斷填進 `reports/<id>.json` 的 `observations`：
   - 還原是否忠於原文的限定與強度；
   - 每條質疑及理由是否成立；
   - 你標註的已知問題有沒有被找到；
   - 有沒有標註之外的有效問題或硬挑；
   - 每則作者回應是否針對模型實際提出的質疑，記為「適用」或「此輪不適用」並附理由。只有「適用」時才評估模型後續處理是否合理。
   
   填寫範例見 `evidence/K6-S3/filled-example.md`。填完後可以用 README 中的 `validate_observations` 指令檢查。
5. 腳本中的作者回應如果和模型實際提出的質疑對不上，請改在桌面上針對實際質疑打 `@grill` 接續回應，並另外保存那段對話紀錄。

## 7. 手動 GUI 檢查清單（請你本人操作；執行者沒有驗證過 GUI）

- [ ] 開一份 `.md`，圈一段，輸入 `@grill 檢查這段`。回覆應該包含可供人工檢查的還原，以及有理由的發現；或者說明資料不足，或給出有範圍的通過。不要因為格式正確就認定詰問品質合格。過程中不應出現編輯核准，文件也不應改變。
- [ ] 下一回合不加 `@grill`，明確要求修改：應照常出現編輯核准，並且能存檔。
- [ ] 在段落留言中寫 `@grill`：預期 skill 會啟用，而且整個回合唯讀（對照第 5 節）。
- [ ] 對同一份文件連續做十幾個編輯回合：檢查模型有沒有混淆版本。要求取回某個已封存回合的提交版本時，模型應能依照佔位從封存中取回（會出現 bash 核准）。沒有進入任何提交快照的中間存檔版本，不在這個保證範圍內。
- [ ] 最後一輪把 A 編輯並存成 B，然後關閉文件，再進行普通對話：模型只會保留最後提交的 A 快照，並明確標示那是提交時的內容，不能聲稱那是最新存檔的 B。沒有自動載入 B 屬於預期行為，不算本計劃驗收失敗。
- [ ] 用 `@writing-genres` 要求產出一份投影片或 Poster 原稿：寫出的副檔名應與 skill 說明一致，`.md`／`.tex` 能在編輯器中開啟；Ask 模式下寫檔時會出現 bash 核准。
- [ ] 可選：用真實模型跑幾回合後，`grep turn_trace` 查看 `model_end` 的 `document_full_copies` 與 `document_tokens_estimate`，和第 2 節的假模型數字對照。

## 8. Commit 清單與分支

全部都在 `GUI` 上，依時間由舊到新排列。沒有 push（`git status -sb` 顯示 `ahead 24`，K8-S3 提交後為 25），沒有建立、切換、刪除或重新命名 branch，沒有 detached HEAD，也沒有建立 worktree。

| 步驟 | Commit |
|---|---|
| K1-S1 | `eddd29c` |
| K1-S2 | `091d830` |
| K2-S1 | `5da6a26` |
| K2-S2 | `9e2b1e7` |
| K3-S1 checkpoint | `e7e4cf6` |
| K3-S1 | `f93d6b1` |
| K3-S2 checkpoint | `4c086d8` |
| K3-S2 | `1539387` |
| K3-S3 | `bb2d878` |
| K4-S1 | `a4c593c` |
| K4-S2 checkpoint | `9dab1aa` |
| K4-S2 | `0a90b0c` |
| K4-S3 | `ddadaa0` |
| K5-S1 | `d851d94` |
| K5-S2 | `39252be` |
| K5-S3 | `b05b514` |
| K6-S1 | `d0a8e23` |
| K6-S2 | `93c166d` |
| K6-S3 | `01ca539` |
| K7-S1 | `2e7a56a` |
| K7-S2 | `52dac52` |
| K7-S3 | `1c21e0a` |
| K8-S1 | `55e53c0` |
| K8-S2 | `ee2af13` |
| K8-S3 | 本報告所在的 commit |

與本計劃無關的未追蹤檔都保留原狀，沒有提交：`NOTES-grill-skill-and-document-context.md`、`app/desktop/watch.out`、`note/20261106/`，以及沙箱掛載產生的根目錄點檔。
