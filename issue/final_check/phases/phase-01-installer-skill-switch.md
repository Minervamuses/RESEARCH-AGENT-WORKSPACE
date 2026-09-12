# Phase 01 — Installer 切換的 cleanup 與有效模式

## 目標與來源

改選 Citation／一般 Skill 時，清理衝突必須停止新工作並公開原因、backup_path；無衝突時同一回合持久 thinkingMode 與實際 routing 一致。
來源：[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、session.py 的 turn_outcome／_begin_turn／_run_one_shot_skill_turn／clear_skill_installer／finalize_and_record；extensions/manager.py 的 SkillInstaller.clear；test_skill_adherence.py:340/472 與 test_citation_skill_activation.py:198/264。

## 範圍、預期元件與非目標

Production 預期只改 app/agent/session.py。測試延伸 app/tests/test_skill_adherence.py，必要時局部使用 test_thinking_session.py、test_citation_skill_activation.py、test_session_persistence.py 的既有 helpers。
非目標：修改 clear 的檔案保留機制、改 manager、重構模式管理、遷移舊 JSON、修改 Desktop duplicate 或增加新 framework。

## 依賴、前置與停止

無前置 phase；須使用者啟動實作、PLANS runtime gate 通過。先核對現有 error 對 CLI／Desktop 的可見格式，確定 cleanup_detail／backup_path 不被通用錯誤吞掉。
若需要額外 production 檔案，先以直接失敗證據說明局部替代不足，再按 PLANS 的具體 scope／三檔門檻處理；不先順便動 caller。

## 實作與驗證計畫

### Preflight／Red

1. 重用真 ZIP、tmp_path、_real_installer_session、現有腳本模型。preview 且未 apply，保留 previous 備份，修改 staged forms.md；改選 citation 與 academic-paper-writing 各一次。記新 Skill graph/model 呼叫數、最終對外結果、source 全檔與 backup 全檔 bytes。red 必須是新工作仍執行／衝突未公開，非 setup 或 import 失敗。
2. 真安裝候選澄清從 Extended 暫留 Normal，再經 slash handler 切一般 Skill。重用 _Factory／_default_models 跑真 Fusion orchestration；讀取磁碟 JSON 與 repository，而非只 inspect config。red 應看到 Fusion proposer/aggregator/reviewer 已執行、thinkingMode 卻 normal。
3. 保護對照：新 runtime 載入失敗，原 pending transaction、active runtime、mode、source/backup 不變；completed duplicate 在 loader／cleanup／model 前返回，原 pending installer 也不應被 duplicate 清掉。

### Green

沿用 cleanup 結果及現有錯誤／host 結果機制，在衝突時停止新 Skill，對外保留 detail／backup。不要只設定 _installer_context 卻依賴新 Skill finalizer 幫忙顯示。
在持久化前以無 mutation 的方式決定本回合有效模式，執行使用相同值；Citation／installer override Normal，一般 Skill 使用成功清理後應恢復的原模式。保留 load-before-cleanup 與 duplicate-before-execution；不要把 cleanup 無條件移到 turn_outcome 最前面。
不安排獨立 refactor；有局部必要整理才在 green 後做並重跑直接 checks。

### Planned verification

以下 cwd app/，採 PLANS 的 Conda app 前置；均未在 authoring 執行。

```bash
timeout 300s poetry run pytest tests/test_skill_adherence.py tests/test_citation_skill_activation.py -q
timeout 300s poetry run pytest tests/test_session_persistence.py tests/test_thinking_session.py -q
```

開發時只選新測試 nodeid 跑 red/green；上述為 phase 邊界回歸，各組無新變更不重跑。重用既有 CLI／Desktop service test seam 核對衝突結果的最終公開文字，必要時只加該小案例；不啟動 live model。

## 驗收條件

- [ ] Citation／一般 Skill 的衝突案例皆停止本次新執行，graph/model 零呼叫，公開 cleanup 原因與正確 backup_path。
- [ ] 使用者 source 與全部 previous 備份 bytes 保持不變，沒有替使用者重新安裝／刪檔。
- [ ] 澄清後改一般 Skill：真 Fusion orchestration 可見，JSON／repository mode=extended，完成後 session=extended；Citation 對照持久及執行 normal，結束恢復 extended。
- [ ] completed duplicate 與 runtime 驗證失敗的原狀態保護成立；既有下一 installer request／cancel 行為保留。
- [ ] required focused checks 與最終對外回報有直接證據，不能只斷言 internal last_result。

## 復原、證據與交接

失敗只修當前因果範圍，不刪任何 conflict 保留資料；測試只清自己 tmp。
在 ../build-log.md 記 red/green、實際公開文字、模式／routing、bytes/計數與 acceptance 對照；重大時序發現才建 phase-01 context。
必要驗收未通過就保持未完成並阻擋 Phase 02；完成後依 PLANS 接續，不自行 commit。
