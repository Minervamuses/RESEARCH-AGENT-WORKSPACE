# Issue 06 — Applied Skill 啟動後完整性：目標

## Purpose and Background

依 [原 issue](../06-extension-skill-post-startup-integrity.md)，session startup
已核對 installed Skill 與 registry 的 source hash，但 catalog 只留下 metadata
與路徑；稍後 activation 會重新讀磁碟。若 startup 後、activation 前 installed
copy 已被修改，未經 apply/restart 的 instructions、manifest 或 pinned reference
可能進入 active runtime。

本計劃只補這個啟用邊界，採原 issue 方案 A 的「每次啟用前重新驗證」。
本次請求僅 authoring，並未授權開始實作。

## Desired Outcomes

- 對已套用的 Skill，啟用時以當前 session 啟動時核准的 hash 為基準；
  啟用前已異動的 installed bundle 被拒絕，不進入模型或工具權限。
- 正常 apply → restart → activate 仍可使用；drop-in desired state 不被偷渡進
  現有或新 session。
- 拒絕時提供可辨識的 applied bundle changed／restart or re-apply required
  訊息，不帶出檔案內容、YAML 摘錄或其他敏感資料。

## Success Conditions

- [ ] Startup 建立 catalog 後，分別修改 installed SKILL.md、manifest.yaml
      的工具或 resource 宣告、pinned reference，下一次 activation 均拒絕。
      測試中修改在 activation 開始前完成。
- [ ] 真 ChatSession one-shot 拒絕時不呼叫 graph/model、不採用被改內容或工具權限，
      並保留先前 Citation runtime／service／thinking 狀態。
- [ ] Applied catalog 走 activate_citation_skill() 的受控測試也拒絕；
      一般 built-in Citation 的啟用、停用與 normal thinking 行為保持。
- [ ] 未修改 bundle 可正常啟用；drop-in 改為 B 但尚未 apply 時，舊 session
      與新 startup 都仍使用 applied A。正常 apply B 後，舊 catalog 仍固定 A，
      新 startup/restart 才採用 B。
- [ ] installed 檔案遺失、無效 YAML、symlink 或 fingerprint 限制失敗時均拒絕；
      使用者可見錯誤與紀錄不含測試敏感 marker。
- [ ] 既有 built-in/custom skills_dir、manifest、resource 大小與工具權限行為不退化；
      必要 focused checks、代表旅程及一次合理便宜的完整 suite 有實際證據。

## In Scope

Applied Skill 啟動基準的記憶體傳遞、共用 runtime activation 檢查、
既有 session/CLI 入口的拒絕行為，以及對應的最小離線 pytest。
後續非 pinned 內容由普通 file/shell tools 讀取的語意保持既有行為。

## Non-Goals

- Issue 07 的跨 process apply 競態、registry repair、檔案鎖或新 concurrency model。
- 啟動時預載全部 Skill、建立第二份 snapshot/cache、修改 registry schema 或 hash 格式。
- 為 built-in/custom skills_dir 強加 registry 身分或允許 applied Skill 覆蓋 built-in。
- 同 OS 使用者惡意程序持續寫入下的原子讀取／ABA 防護、MCP 隔離、
  所有 ordinary file/shell 讀取的完整性保證。
- Citation 查詢／保存、其他 issue、UI 改版、依賴升級、效能 sweep 或 live provider。

## Preserved Behavior and Invariants

- Session 的 hash 基準只能來自該次 startup 核准的 registry entry；activation
  不重讀最新 registry、不從 desired drop-in 重新 discovery、不 hot reload。
- Failed load 在 active state 變更之前結束。正常非 Citation one-shot 的結束清理，
  Citation 的 workflow teardown、工具解析與 thinking 規則照舊。
- 保留現有 fingerprint 的路徑、bytes、executable bit、檔案數／大小與 symlink
  限制；不另寫簡化 hash 或只 hash SKILL.md。
- Registry、drop-in、installed copy 不因拒絕而被自動修復、刪除或改寫。
- SKILL.md instructions 和 pinned resources 維持 lazy loading 及既有 char limits。

## Constraints

- **Authority — 使用者 Personal Engineering Defaults 與 root AGENTS.md：**
  Linux 是支援 runtime；Conda app 管 runtime、Poetry 管依賴；LF；
  保留使用者變更；只做直接必要修正。具體授權與停止規則由 PLANS.md 管理。
- **Authority — 原 issue 方案 A 與現有載入行為：**
  此方案的一次 precheck 防止啟用前已完成的異動被採用；檢查後再次讀磁碟仍有
  TOCTOU 視窗，不宣稱驗證與解析是同一次原子 bytes snapshot。
  如需保護載入期間的對抗性持續修改，屬明確擴大目標，需另定範圍與授權。
- **Authority — config.py:60–69：**
  預設最多 512 files、8 MiB/file、64 MiB/bundle；pinned reference 65,536 chars、
  total active context 200,000 chars。無已知全 catalog 記憶體上限；
  因此選 lazy A，不做 eager B。每次 applied activation 多一次 bundle 掃描，
  沒有實測 latency 改善或效能保證。
- **Authority — startup.py 與 registry.py：**
  Built-in collision 仍拒絕。普通 Citation 通常是 built-in，沒有 applied hash。
  同 hash 的 corrupted installed destination 不會被普通 unchanged re-apply 修好；
  restart 可讓 startup 拒絕它，但不等於修復。

## Known Unknowns and User Decisions

沒有阻止撰寫計劃的產品決策；原 issue 已提供可觀察案例，A/B 是可由 repository
證據判定的技術選擇。排序在 issue 04/05 之後是工作優先度，沒有程式依賴，
本計劃不要求先執行別的 issue。

實作前的明確授權事項：擬在已匯出的 SkillMetadata 增加 optional
applied_source_hash，預設 None，保留既有三參數呼叫；這是 additive public
Python type 變更，即使不改 persistent schema，也應依使用者 public API gate
取得該具體變更的核准。單純請求 authoring 不算核准，詳見 PLANS.md。

技術 preflight 要確認循環 import 的最小接法、實際測試 fixture 入口與當時
worktree；由唯一 phase 解決，不另建探索階段。未執行 application tests。

## Source Inputs

- 根 AGENTS.md、使用者提供的 Personal Engineering Defaults；2026-09-12
  「先閱讀 AGENTS.md，然後把 issue 裡面的 06 寫出計劃」。
- issue/06-extension-skill-post-startup-integrity.md。
- app/agent/extensions/{startup,discovery,registry}.py。
- app/agent/skills/{metadata,runtime}.py、app/agent/session.py、app/agent/config.py。
- app/tests/test_extension_skill_startup.py、test_extension_user_journey.py、
  test_skill_runtime.py、test_citation_skill_activation.py。
