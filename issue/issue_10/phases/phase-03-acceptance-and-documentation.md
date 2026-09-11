# Phase 03 — 真實 ZIP 驗收與使用文件

## Source Inputs

`../GOALS.md`、`../PLANS.md`、前兩階段 observed evidence，以及
`app/tests/test_extension_user_journey.py`、`test_extension_skill_startup.py`、
`test_extension_packaging.py`、`README.md`、`app/SKILLS_GUIDE.md` 和
`app/pyproject.toml` 的現有 package include 設定。

## Objective

用可追溯的真實上游 skill ZIP，證明從 CLI/Desktop 一般對話到安裝、新 catalog
載入與資源讀取的完整路徑，並提供使用者可照做的文件。

## In Scope / Non-Goals

代表性跨入口驗收、原始內容完整性、啟用時點、必要文件與 wheel 內容檢查。
不補作前兩階段遺漏的 required focused verification，不進行模型評測活動、
GUI 拖曳、跨平台 runtime 或下載平台開發。

## Dependencies and Prerequisites

Phase 01、02 均 Complete。先讀實際 evidence，查明 CLI/Desktop 各自何時重新
建立 startup catalog，以及 installer 的 tool binding／approval 方式。

**Unresolved:** 真實驗收 ZIP 的精確版本與 SHA256。優先使用已取得且可追溯的
官方 bundle／使用者 ZIP；否則讀取 `anthropics/skills` 官方 repo 的固定 commit
archive，選擇含根層 reference 與 scripts 的 PDF skill。先確認在既有 bundle
限制內並記錄來源 URL、commit、ZIP hash、被選路徑與 license，再進行驗收。
若外部來源不可得或條件不符，保留 blocker，不把合成 fixture 宣稱為真實驗收。
不將整個上游倉庫、generated state 或下載包提交本專案。

## Expected Components Affected

主要為 `app/tests/test_extension_user_journey.py`、既有 session／Desktop tests、
`test_extension_skill_startup.py`、`test_extension_packaging.py`，以及 README
和 SKILLS_GUIDE 的直接相關段落。Application code 只修復驗收指出、直接造成
本目標失敗的缺陷；若需改前階段假設，先修訂計畫及記錄因果。

## Authorization and Stop Conditions

遵守 PLANS。允許公開來源 read-only 取得與 temp 安裝；不使用真實外部 skill
目錄，不啟動第三方程式，不呼叫 live/paid LLM。若必須新增 dependency／修改
packaging manifest 才能包含資源，提出具體缺檔證據並先取得新授權。
完整 pytest 若預期超過約十分鐘，先取得執行許可；未跑不是通過。

## Implementation and Verification Plan

### Preflight / Characterization

沿用現有 user journey 的 deterministic model seam，將真實 ZIP 作為檔案來源。
公開上游檔案只在取得時需要網路；後續驗收使用同一份固定 archive，避免每次
測試重新下載。必要時把驗收安排為明確本機 procedure，不將網路變成 pytest
永久依賴。本文指令皆是 planned checks。

### Representative acceptance procedure

1. 在 temp 下配置 drop-in/state，記錄 ZIP 與選定 skill 所有相對檔案的 hash。
   ZIP 放在 `<dropin>/skill/`，同時放入未選的 skill／MCP pending changes。
2. 透過 CLI 正常輸入入口送出明確 installer 要求；scripted model 僅替代外部
   推理，真實 session/tool loop、stdlib 檔案動作、manager／registry 均執行。
   驗證回報、selected-only、source 留存及 managed copy bytes。
3. 重設另一份 temp workspace，透過既有 Desktop `session.turn` 輸入同類請求，
   至少完成一次多候選選擇的第二輪回覆，驗證既有批准／busy/cancel 機制，不
   直接呼叫 manager 來冒充 Desktop 對話完成。
4. 比對原 archive 中選定 bundle、drop-in source 與 managed copy 的檔案清單
   和 bytes；確認原 ZIP 與未選 skill／MCP 未被修改，原外層 wrapper 未被誤裝。
5. 在實際會重新執行 extension startup 的 lifecycle 建立新 session/catalog，
   發現並選用該 skill，確認 context 的 root 指向真實可用資源。只讀一個根層
   reference，必要時另以自製無害 script 測試相對路徑指引；不執行上游腳本。
6. 以最小 fixture 另驗證拒絕／取消、同名未授權更新與來源在 preview 後變動。
   利用已存在的 focused tests，不重建大型 edge-case matrix。

Fake-model journey 可以證明檔案與 host 整合及對話續接；不能證明真實模型必然
自主選對工具。live-model smoke 不列本次必要驗證、不代為消費，最終報告必須
標示未驗證。若使用者另行授權，才作一次同樣隔離的實際對話測試並另記結果。

### Documentation / Packaging

- 更新 README、SKILLS_GUIDE 的直接相關內容：ZIP 可放哪裡、明確自然語言和
  slash 範例、多候選／同名處理、成功後哪種 restart/session 才生效。
- 說明外部 skill 保持原文件，沒有自訂 manifest 也可安裝；第三方依賴／私有
  工具能力另行處理；GUI 拖曳與遠端來源尚未實作。
- 以既有 Poetry build 產生 wheel，使用 Conda app Python stdlib zipfile
  查看公開 installer SKILL.md／必要 helper／manifest 是否被打包，並驗證
  config override 與 wheel path resolver；不在全域環境安裝或建立新 venv。

### Focused and broader verification

以下命令由 repository root 執行；先執行 focused，再進行一次完整 suite：

```bash
cd app
conda run -n app poetry run pytest tests/test_extension_user_journey.py tests/test_extension_skill_startup.py tests/test_extension_packaging.py tests/test_skill_adherence.py tests/test_desktop_service.py -q
conda run -n app poetry run pytest -q
conda run -n app poetry build
```

在 repo root 另跑 `git diff --check`。wheel inspection 與實際 ZIP procedure 的
exact command、路徑和 hash 由執行 agent 記入 build-log；目前沒有已確認的
獨立 ZIP journey CLI，不捏造測試參數或宣稱現有 journey 已測過 ZIP。
已通過項目只在新改動、失敗或未解疑慮需要時重跑；完整 suite 至多一次，除非
取得再次 expensive run 授權。無關失敗分開回報，不能擴張成旁支修復。

## Reliability, Review and Recovery

所有真實檔案動作限於已確認的 temp roots。保留失敗 evidence，刪除測試暫存
前核對路徑；不刪使用者 ZIP/state。一次 fresh-context review 對照 actual diff
與驗收 evidence，優先檢查 selected-only、批准關聯、原始內容及生命週期。
不建立新的 review framework；有實際 review 才寫 code_review 文件。

Required acceptance、full suite 或 packaging 證據缺失時保持 In progress／
Blocked，記錄限制並按 PLANS 停止條件處理；不得靜默降低成功標準。

## Acceptance Criteria

- [ ] 真實上游 ZIP 有版本、hash、license 與選定 bundle 的可追溯記錄。
- [ ] CLI/Desktop 各一次完整對話 journey 有實際 host／檔案結果，其中至少一個
      情境完成多候選澄清續接；沒有只直接呼叫 manager 的替代證據。
- [ ] 原始 bundle、來源、managed copy 的檔案 bytes 一致，未選項目未變。
- [ ] 新 startup catalog 可載入／選用 skill，root 資源讀取成功，啟用說明吻合
      真實 lifecycle；未聲稱第三方依賴與腳本業務功能已經通過。
- [ ] focused、一次完整 pytest、build／wheel 檢查與 diff check 有成功證據。
- [ ] 使用文件完整涵蓋目前可用流程，獨立 review 無未解決的實質 findings。
- [ ] GOALS 每項成功條件已映射到 observed evidence；live-model 自主性限制
      清楚列出，沒有未授權 provider 呼叫或 scope 擴張。

## Evidence and Handoff

build-log 記 exact procedures、入口輸入、hash 比對、測試／build 結果、review
及未測範圍。重大發現才寫 context。全部整體完成條件成立後停止，回報實作範圍
與最重要限制；沒有當次另外授權時不 commit/push，不開始 optional follow-up。
