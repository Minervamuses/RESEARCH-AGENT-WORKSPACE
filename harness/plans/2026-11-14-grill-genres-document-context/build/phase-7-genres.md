# K7 文體 skill 與每回合回覆規則

- **後置條件**：`app/skills/writing-genres/` 寫好並被載入，七種文體各有格式與副檔名；`SYSTEM_PROMPT` 有一段簡短的跨文體回覆規則，CLI 與桌面每回合都帶到；佔位符寫法在新 skill、回覆規則與 `academic-paper-writing` 一致。
- **涵蓋**：G4、G5。
- **相依**：K1。
- **輸入**：GOALS D9、D10、U3、U4、A2、A4、A5、A6；PLANS「基線」的 Skill 與系統提示兩節。

## 文體 skill 規格

七種文體：論文、教材、筆記、計劃書、Abstract、Poster、投影片。每一種寫明：

1. 目的與讀者，以及這一文體的結構與篇幅慣例。
2. 預設格式與副檔名（A5）。優先選編輯器能開、能圈選修改的 `.md` 或 `.tex`；需要其他輸出（例如 `.docx`、`.pptx`、PDF）時，寫明由 `.md`／`.tex` 原稿經哪個既有工具轉出（例如 Pandoc，或桌面 Export 選單的 Word、Word (BIME)），並說明轉出的檔案不能在編輯器裡圈選修改（D10）。
3. 寫檔方式：用 bash 寫到使用者指定或專案內合理的路徑（D9）；在 Ask 權限下每次 bash 都要核准，所以盡量一次寫成一個檔，並告訴使用者檔案路徑。
4. 引用寫法：文件中的引用用專案文獻庫的 key（Markdown `[@key]`、LaTeX `\cite{key}`），沿用現有規則；缺的內容用 `[TODO: …]`、`[CITE: …]`、`[FIGURE: …]`（A4）。
5. 與其他 skill 的分工：論文與計劃書的學術寫作細節交給 `academic-paper-writing`；邏輯檢查交給 `grill`；本 skill 不重複它們的內容。`paper-writting` 不搬進來（U4）。

篇幅控制：若七種文體寫在一份 SKILL.md 會過長，可把各文體細節放進 `references/` 並用 manifest 的 `resources`（`use_when`、`pinned: false`）宣告，SKILL.md 只留共通規則與索引；作法參考 `academic-paper-writing/manifest.yaml`。

## 回覆規則（`SYSTEM_PROMPT`）

在 `agent/session.py` 的 `SYSTEM_PROMPT` 加一小節（A6），只放每回合都需要的：

- 使用者要寫或改某種文體時，先辨識文體並依該文體的慣例寫；需要完整格式時可建議使用者以 `@writing-genres` 啟用細節。
- 缺內容用 `[TODO: …]`、`[CITE: …]`、`[FIGURE: …]`，不捏造。
- 編輯器只能圈選修改 `.md`、`.markdown`、`.tex`；其他副檔名的產出要先告知使用者。
- 檢查邏輯（`@grill`）與改寫是分開的兩步。

不寫進任何 RESEARCH.md（U3）。保持現有語言政策與 skill 說明不變。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| K7-S1 | 寫 `app/skills/writing-genres/`（SKILL.md，必要時加 manifest 與 references） | 技能探索測試確認被載入、`@writing-genres` 可解析；若有 manifest，通過 `validate_skill_manifest`，`resources` 的檔案都存在；人工核對表：七種文體 × 上方五點，每格指到對應段落，寫進 build-log |
| K7-S2 | `SYSTEM_PROMPT` 回覆規則 | 測試：`SYSTEM_PROMPT` 含這一節；桌面 `_project_system_prompt` 產生的系統提示含這一節且仍在 RESEARCH.md 規則之前；CLI 的 `ChatSession` 預設系統提示含這一節。既有提及 `SYSTEM_PROMPT` 的測試通過 |
| K7-S3 | `academic-paper-writing` 佔位符對齊（A4）：第 93 行改用 `[TODO: …]`、`[CITE: …]` 寫法，其餘內容不動 | `grep -rn "insert citation" app/skills` 無結果；`tests/test_academic_skill_tools.py` 等相關測試通過 |

各步驟各自 commit。

## 交付給後續階段

文體 skill、回覆規則與測試；七種文體預設格式的清單（K8 列入最終彙報，請使用者確認，A5）。
