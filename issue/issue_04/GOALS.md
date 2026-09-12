# Issue 04 — Citation earliest 歧義：目標

## Purpose and Background

來源：`issue/04-citation-earliest-version-ambiguity.md`。當使用者要求同一作品
的最早版本，現行 `decide_resolution()` 會在年份相同或全缺年份時，仍用
score、provider rank、provider 名稱及輸入順序選出一筆。這些不是時間證據。

第一版只修正 issue 明列的年份歧義，讓 agent 收到可說明的 alternatives，
而不把無法唯一判定的結果當成已選定、可保存的版本。

## Desired Outcomes

- 在既有 identity 篩選與去重後，有足夠年份資訊時仍能選定最小年份候選。
- 最小年份有多個不同 identity，或所有候選都沒有年份時，回傳
  `ambiguous` 與 alternatives，不靜默選出 winner。
- 此歧義抵達現有 save/tool 回傳邊界時仍可見，不產生該項目的 receipt、
  citation bundle 或 registry entry。

## Success Conditions

以下是穩定驗收條件，不是執行進度；實際狀態只記在 `build-log.md`。

- [ ] 同標題且符合 identity 條件的 published DOI A（2020、rank 0）與
      preprint DOI B（2020、rank 1），在無 exact identifier 的 earliest
      請求下回傳 `ambiguous`，沒有 winner；兩個版本都可在 alternatives 辨識。
- [ ] 調換上述輸入順序、rank，或改變非時間的描述相符程度，都不能讓平手
      成為 `eligible`；用於測試的兩筆 records 必須仍符合 identity 條件。
- [ ] 非空 eligible 集合全部缺年份時回傳 `ambiguous`；只有一個去重後
      identity 也不宣稱它是最早版本。
- [ ] 2020 與 2022 仍選 2020；最小年份唯一時，較晚年份彼此平手不造成歧義。
- [ ] 同一 canonical identity 的重複 provider hits 不被當成多個版本；
      不同 DOI 不能因標題相同而合併。
- [ ] alternatives 保留現有 title、year、version kind、DOI／arXiv 等欄位，
      缺值如實呈現；`earliest` 不被寫成觀測到的版本種類。
- [ ] 真實 resolver → service → tool 路徑的離線代表案例回傳上述歧義，
      不執行 winner 的 DOI metadata／BibTeX refetch、不保存；即使 authority
      fallback 能找到相似的權威作品，也不能覆寫本次 earliest 歧義。
- [ ] 下列 preserved behavior 的既有回歸檢查通過；新測試與必要的 broader
      檢查有實際結果，未執行者不得宣稱通過。

## In Scope

- 描述式搜尋候選經既有 identity 篩選、去重後的 earliest 年份選擇。
- 歧義結果的 alternatives，以及直接必要的 save 傳遞保護。
- 既有 pytest 檔案內的最小回歸案例和離線 tool/service 驗證。

## Non-Goals

- 不新增或使用完整日期、online-first／print／deposit 日期比較、arXiv 版本
  時間或 manifestation relation 來判斷 earliest。
- 不改 provider query、identity score／閾值、year hint 容忍度或去重規則；
  不處理同 identity 的 metadata 年份衝突、跨 DOI alias／DOI-arXiv 關係融合、
  authority refetch 後的年份重比較。
- 不改 exact DOI／arXiv 優先路徑；有明確 identifier 的既有選定語意維持。
- 不實作 issue 05 的 save 結果回報工作、issue 08 的技能流程改造，
  不新增 UI、互動追問機制或 agent policy。只提供既有 alternatives 給 agent。
- 不引入 dependency、module、service、儲存層、schema、公開介面或新測試框架。
- 本次 authoring 不修改 application code、tests、AGENTS.md 或原始 issue，
  不將 issue 標為 resolved，不執行 implementation。

## Preserved Behavior and Invariants

- `published`、`preprint`、`repository`、`repost` 與未指定版本的行為維持；
  exact identifiers、provider failure 與 DOI/BibTeX 驗證邊界維持。
- 沿用 resolver 的 canonical DOI → normalized arXiv → provider/id 去重優先序；
  此處的 identity 是現有 resolver key，不另造 identity 系統。
- 有已知年份與缺年份候選混合時，第一版保留已知年份優先的行為；
  只能說選出了已知年份中的最早者，不能宣稱解決了未知年份的時間先後。
- 沒有 records 或沒有 eligible candidates 的既有結果維持，不把所有失敗改成
  earliest ambiguity。正常的非歧義 authority save／exact arXiv fallback 維持。
- 保留 save artifact 欄位、版本、status 列舉及最多五個 alternatives 的既有
  對外限制；不得使用排序位置暗示 alternatives 的時間先後已獲證明。

## Constraints

- **權威：使用者提供的 Personal Engineering Defaults（2026-09-12）及根
  AGENTS.md。** 小型學生自用專案；只做解決本問題直接必要的最小修正，
  不進行鄰近清理、架構改造或額外 benchmark。
- **Runtime：根 AGENTS.md、app/env/env-app.yml、app/poetry.toml。**
  Linux／WSL Ubuntu；Conda `app` 管 runtime，Poetry 管套件。
  不用系統 Python、Windows Python、pip、venv；文字檔維持 UTF-8、LF。
- **驗證成本：使用者 Personal Engineering Defaults。** 使用現有 fake
  providers／fetchers 與 pytest 暫存目錄；不使用 live/paid provider、模型、
  GPU、真實 citation store 或 full-dataset replay。完整既有 suite 最後最多
  一次，超過約十分鐘的操作須另外授權。
- **檔案/Git：使用者要求與技能邊界。** 保留所有其他工作；implementation
  授權與停止條件由 `PLANS.md` 管理，計劃本身不授權執行。

## Known Unknowns and User Decisions

目前沒有阻擋撰寫此計劃、必須請使用者決定的事項。

- 「全部缺年份」包含單一候選，是對 issue「不得靜默選擇」的明示解讀；
  混合已知／未知年份採保留既有行為的第一版範圍。若使用者要求更嚴格語意，
  應先修訂本檔，不由執行者默默擴充。
- Service authority fallback 是否會覆寫新歧義：靜態控制流程顯示風險，
  尚未執行重現。由唯一 phase 的最小離線案例確認；只有確認後才做局部 guard。
- 即時 provider 資料完整性、完整日期語意與真實模型如何追問使用者，
  不是本版驗證內容，也不以離線測試宣稱已證明。

## Source Inputs

- `AGENTS.md`；使用者於 2026-09-12 提供的 Personal Engineering Defaults。
- `issue/04-citation-earliest-version-ambiguity.md`。
- `app/skills/citation/resolution.py`、`providers/base.py`、
  `types.py`、`service.py`、`authority.py`、`tool.py`。
- `app/tests/test_citation_resolution.py`、
  `app/tests/test_citation_work_resolver.py`、
  `app/tests/test_citation_authority.py`、
  `app/tests/test_citation_workflow_tool.py`。
