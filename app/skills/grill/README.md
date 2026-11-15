# grill：使用與評估說明

`SKILL.md` 是模型讀的指示；本檔寫給人看：怎麼在桌面使用 `@grill`，以及怎麼用 `scripts/grill_eval.py` 自己評估它。

## 在桌面使用

1. 在編輯器開啟 `.md`、`.markdown` 或 `.tex` 文件，圈起要檢查的段落。
2. 在輸入框打 `@grill`，可附一句說明，例如 `@grill 這段推論成立嗎？`。
3. 回覆依序是 `## 還原`、`## 發現`、`## 判斷`。每條發現附逐字引用、理由與要你回應的事。
4. 回應質疑時再打一次 `@grill`，skill 只在打了 `@grill` 的那一回合生效。之後的回覆會多一段 `## 回應檢查`。
5. 詰問回合只讀不改：`document_edit` 不可用，回覆中缺的內容以 `[TODO: …]`、`[CITE: …]`、`[FIGURE: …]` 建議，由你通過後另外改寫。

注意：段落留言裡的 `@grill` 會作用於**整個回合**。主請求與所有引用都變成唯讀，同一回合其他留言要求的改寫不會執行。要改寫的請求請另外送出。

「通過」只表示在目前材料與檢查範圍內沒找到具體問題，不保證段落正確。這套「還原 → 試著推翻 → 提出」是第一版做法，還沒有用真實段落驗證過效果。

## 評估框架

### 案例格式

案例檔是 JSON：`{"note": "…", "cases": [ … ]}`。示範檔在 `tests/fixtures/grill/cases.example.json`。

| 欄位 | 說明 |
|---|---|
| `id` | 案例名稱，不可重複 |
| `kind` | `flawed` 或 `clean`，是你目前的標註，不是完整真值 |
| `source` | `synthetic` 或 `real` |
| `document` | 整份上下文（Markdown） |
| `selection` | 要檢查的段落，必須在 `document` 中逐字出現且只出現一次 |
| `known_issues` | 你已知的問題：`id`、`quote`（逐字在 `document` 中）、`note`。`flawed` 至少一條，`clean` 為空。`clean` 也可能被找出其他有效問題 |
| `author_turns` | 腳本化的作者回應：`targets`（這則回應預設要回答哪一項質疑）、`type`、`expected`、`text` |

`type` 與 `expected` 固定對應：`rephrase` → `maintain`（只換說法，有根據的質疑應維持）、`supply_step` → `request_write_in`（補上缺步，應要求寫進文字）、`valid_rebuttal` → `withdraw`（有理由的反駁，應撤回）。`expected` 只在模型實際提出的質疑與這則回應對得上時才適用。對不上就在報告中記「此輪不適用」，不拿預期來評判。

格式錯誤時腳本會拒絕執行，並說明哪個案例的哪個欄位有問題。

### 放入你自己的真實段落

把案例檔放在 repo 外，或放在不提交的位置，例如 `~/grill-cases/real.json`，`source` 設為 `real`。報告也輸出到 repo 外，因為它們包含段落全文與模型回覆。腳本只在 `--out` 下建立暫存專案，不會改動原始論文檔案。

### 執行

在 `app/` 目錄，於 Conda `app` 環境執行：

```bash
python scripts/grill_eval.py --cases tests/fixtures/grill/cases.example.json --out /tmp/grill-dry --dry-run
```

`--dry-run` 用內建的離線替身，不連網也不花錢。它只檢查流程能不能跑通，回覆是固定文字，不是研究結果。

```bash
python scripts/grill_eval.py --cases ~/grill-cases/real.json --out ~/grill-runs/2026-11-20 --live
```

`--live` 會呼叫 `agent/config.py` 設定的 OpenRouter 模型，**會產生費用**。開跑前會印出案例數和最多的 `@grill` 回合數。每個案例最多跑 1 加作者回應數個回合，總數以 `--max-rounds`（預設 4）為上限。每個回合可能包含多次模型呼叫。MCP（web search）預設不載入；要讓模型查網路時，加上 `--mcp`。

兩個旗標都沒給時，腳本拒絕執行，不會建立任何模型。

### 讀報告

- `summary.md`：每個案例一列，記錄輪數、各輪有沒有還原段、逐字引用數、各輪的判斷行、首次宣告通過的輪次、有沒有 `document_edit`、文件有沒有被改動。
- `reports/<id>.md`／`.json`：每輪的作者輸入、模型回覆全文、呼叫的工具和機械記錄，最後是人工觀察表。

機械記錄只反映看得到的格式和流程。它不能證明模型讀懂了原文，也不能證明質疑成立；報告也沒有品質分數。研究判斷請填在人工觀察表（`.json` 的 `observations`），重點如下：

- 還原是否忠於原文的限定和主張強度（是／部分／否）；
- 每條質疑和理由是否成立（成立／部分成立／不成立／無法判斷）；
- 你標註的已知問題有沒有被找到；
- 有沒有標註之外的有效問題，或硬挑出來的問題（各附引用和說明）；
- 每則作者回應是否針對模型實際提出的質疑（適用／此輪不適用，附理由）。只有「適用」時才評估模型後續處理是否合理。也記下一段要幾輪才通過。

填完後可以用 `validate_observations` 檢查填寫的值是否在允許範圍內：

```bash
python -c "import json,sys; sys.path.insert(0,'scripts'); import grill_eval as g; g.validate_observations(json.load(open(sys.argv[1]))['observations'])" REPORT.json
```

腳本的回應常常和模型實際提出的質疑對不上。這時請在該輪記「此輪不適用」，後續輪次也註明這個限制。真正的多輪檢查，可以在桌面針對實際質疑打 `@grill` 接續回應，另外保存對話紀錄，不要和固定腳本的回放混在同一份評估裡。
