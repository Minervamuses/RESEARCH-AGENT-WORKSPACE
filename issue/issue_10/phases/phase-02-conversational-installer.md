# Phase 02 — 一般對話中的公開 Skill Installer

## Source Inputs

`../GOALS.md`、`../PLANS.md`、Phase 01 實際 evidence，以及 session、graph、
skill runtime、tool access、CLI/Desktop 入口和相關 tests。

## Objective

使用者明確要求 `skill-installer` 安裝本機 ZIP 後，一般 agent 能以現有工具
整理完整 bundle，必要時澄清，再經限定的 host 管理操作完成安裝並如實回報。

## In Scope / Non-Goals

公開 installer skill、明確選用／有限續接、根目錄 context、正常模式工具串接、
安全暫存解壓與所選 skill apply。包含既有 CLI/Desktop normal chat 的接線。
不建立第二套 agent、通用自動選 skill、ZIP import API 或 drag/drop UI。

## Dependencies and Prerequisites

Phase 01 必須 Complete。確認 manager scope 及 registry 不變式已有證據。

**Unresolved:** 先追 session 的 skill-scoped tool 注入及 Desktop turn lifecycle，
找出薄 host action 的既有接點。Desktop `_extension_operation` 拒絕 active turn，
所以不能遞迴 dispatch `extensions.preview/apply` 或管理 CLI。shell approval
只核准 command，不能當作任意管理寫入的通用批准。

## Expected Components Affected

- `app/skills/skill-installer/SKILL.md`，僅必要時加入現有格式 manifest／stdlib helper。
- `app/agent/session.py`、`skills/runtime.py`、`graph.py` 及既有 tool binding／
  policy 接點；優先沿用 citation 提供的 skill-scoped 工具註冊方式，不能複製其
  業務邏輯或建立通用 workflow framework。
- `app/agent/desktop/service.py`、`app/agent/cli/slash_commands.py` 或 chat
  入口，只有接共同 session 路徑及既有互斥／取消所需的最小修改。
- 相關 tests：`test_skill_adherence.py`、`test_skill_runtime.py`、
  `test_skill_broker.py`、`test_slash_commands.py`、`test_desktop_service.py`。
- `read_file.py` 與 `bash.py` 預設不需改；本目標以 root context 與絕對路徑達成。

## Authorization and Stop Conditions

依 PLANS 的 launch envelope。若無法用既有對話回覆及 in-process action 完成
批准關聯，需要 Desktop protocol／UI 新介面，先報告具體原因再取得新授權。
不放寬既有全域互斥或用 Bash bypass 代替安裝批准。

## Implementation and Verification Plan

### Preflight / Red

以既有 scripted/fake model、session 與 Desktop fake service seam 加最小測試：

- 「請用 skill-installer 安裝 /tmp/example.zip」和 slash 都選同一 skill；
  「skill-installer 是什麼」與文件中提及名稱不構成安裝請求。
- 多候選回覆「第二個」仍回到同一次 installer，完成／取消後清除；普通
  one-shot 與 citation 原行為不受影響。不要新增每輪付費 routing 模型。
- active skill context 包含真實 root、原指令與相對引用規則；以正常工具讀
  `<root>/forms.md`，不要求改寫為 references/forms.md 或改 bash cwd。
- 指定 skill action 不能由非 installer、別的會話、取消後或 stale preview 使用。

### Green — 公開 skill 與檔案操作

1. 公開 `SKILL.md` 清楚描述本機 ZIP 安裝、支援輸入及可用管理工具。由同一個
   一般 agent graph 讀此 skill，再使用現有 shell/read 與 Python stdlib。
2. 解析來源為 backend 可讀的 Linux 路徑，使用既有 path resolver 得到 drop-in。
   未提供精確 ZIP 且固定目錄有歧義時列候選澄清；不監看或自動安裝全部 ZIP。
3. 先檢視 ZIP members，再於隔離 temp 解壓候選 bundle；拒絕絕對／越界
   路徑與 symlink，遵守現有每個 bundle 的檔數／容量限制，避免寫到 temp 外。
   repo ZIP 中未選的其他 skill 不必全部解壓或併入所選 bundle 的限制。
   不執行 bundle scripts；安全解壓檢查需重用時用 skill 附帶的最小 stdlib helper。
4. 辨識含 SKILL.md 的真正根目錄，包括外層 repo 包裝與多 skill；用原始 name
   決定最終目錄，不改原文件來迎合 ZIP 檔名。多個有效候選取得選擇；無效候選
   清楚回報，不猜測修復或自動轉格式。
5. 保留完整 bundle 的相對結構及 bytes，含根層文件、scripts、assets 及原有
   metadata。不要只複製 SKILL.md 或被引用的檔案，不自動裝依賴或啟用 MCP。
6. 寫入前依實際 builtin catalog／startup collision 規則檢查 name；遇到
   `citation`、`skill-installer` 等 builtin 同名項目，拒絕並說明無法覆蓋，不
   自動改原文件或回報安裝可用。一般外部同名不同內容須有更新意圖或澄清。
   通過後才放入 `<dropin>/skill/<name>/`；不得先覆寫才詢問，只清理本次暫存物。

### Green — Host 操作與會話

- 使用薄的 skill-scoped action 直接重用 Phase 01 manager。host 從本次真實
  使用者安裝意圖、選定 key、來源內容及 preview 綁定套用範圍，不接受模型自行
  聲稱已批准。明確單一新 skill 安裝不加無意義重複確認；有選擇、更新或實際
  permission policy 要求時，用既有對話／approval 機制取得所需資訊。
- 澄清與 pending preview 只留在目前 conversation/session 的記憶體；回覆時
  重新核對來源、scope、preview 與 revision。完成、取消、失敗、切換對話或
  shutdown 清除，不建立持久化 workflow。不得跨會話重放批准。
- installer 進 normal mode，向使用者說明需要正常工具模式；結束後依既有
  session 控制恢復進入前模式，不能把 extended 的 shell 限制全域放寬。
- Desktop 保留外部管理 RPC 與其他 mutation 的原互斥；內部 action 屬於目前
  turn，不創建第二個 display-only turn，不把 approval 等待卡成 RPC 重入死結。
- 由 ApplyReport 回報每項 installed／unchanged／blocked／failed、位置與
  restart_required。真正重新建立 startup catalog 的 session／程式啟動後
  才保證可選用；普通 conversation 切換是否重載須依 live lifecycle 說明。
- 成功後 source 與原 ZIP 保留。失敗先依實際 ApplyReport／registry 分辨各項
  是否已套用；部分成功要逐項回報並保留成功項目的 source，不假設全批原子性。
  只有未套用項目且目前 source fingerprint 仍符合本次 staging 時，才可恢復
  本次保存的舊 source 或移除本次新增目錄，再驗證舊 managed entry 未變。
  若 source 已被使用者／其他操作改動，保留最新內容、回報衝突並停止，不用
  備份覆蓋新修改。例外後結果不明時先查 registry，不盲目重試或宣稱已復原。

### Refactor / Verification

沒有獨立重構。以下是 planned commands，從 root 執行：

```bash
cd app
conda run -n app poetry run pytest tests/test_skill_adherence.py tests/test_skill_runtime.py tests/test_skill_broker.py tests/test_slash_commands.py tests/test_desktop_service.py -q
conda run -n app poetry run pytest tests/test_graph_skill_loader.py tests/test_tool_access.py tests/test_tool_access_matrix.py tests/test_tool_inventory.py tests/test_read_file_tool.py tests/test_bash_tool.py tests/test_citation_skill_activation.py tests/test_thinking_session.py -q
```

第一組 focused，第二組 broader。使用 tmp_path ZIP 加真正 stdlib 解壓／檔案
操作驗證 bytes 與範圍；model 以既有 fake 回傳工具呼叫，不做 live provider call。
若追加必要 focused test file，把其 exact command 更新到此 phase 再執行。

## Reliability and Recovery

至少涵蓋一例拒絕／取消、一例 stale preview 與 source 被另行修改、一例越界
ZIP，以及 builtin 同名拒絕；檢查沒有外部檔案寫入、未選項目變動、舊安裝或
使用者新修改遺失、虛假成功訊息。這些直接保護本次檔案寫入
行為；不延伸成通用惡意內容平台。Required check 未過不得進入 Phase 03。

## Acceptance Criteria

- [ ] 兩種既有入口的明確請求都到一般 agent installer 路徑，slash 仍有效。
- [ ] 可在單 ZIP 安裝完成；多候選與同名澄清能續接，取消／切換清理且無舊授權。
- [ ] 原始文件及完整 bundle bytes 保留，host selected-only 生效，沒有執行第三方碼。
- [ ] runtime 暴露實際 root；根層相對引用轉絕對路徑後一般工具讀取成功。
- [ ] CLI/Desktop 不重入管理流程、不弱化互斥或 permission policy，結果如實回報。
- [ ] focused/broader checks 通過；citation、一般 one-shot、extended 限制維持。

## Evidence and Handoff

在 build-log 記錄入口輸入、實際工具呼叫、檔案／registry 前後差異、結果與模式／
生命週期證據。記錄選定的薄 host 接點與批准方式供 Phase 03 使用；若 live 接口
與本計畫矛盾，先修訂未開始 phase。全數 acceptance 完成才接續最終驗收。
