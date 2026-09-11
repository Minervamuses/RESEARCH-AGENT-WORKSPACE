# Issue 10 — 對話式本機 ZIP Skill 安裝：目標

## Purpose and Background

使用者準備好 skill ZIP，放在既有 skill 存放位置或提供本機路徑，接著在一般
對話要求使用 `skill-installer`，agent 就能完成辨識、整理及安裝。
未來 GUI 拖曳只負責提供同一種檔案路徑，本計畫先完成目前可用的對話流程。

2026-09-11 使用者同意前述研究結論並要求建立計畫及 commit/push。
已確認的設計方向是：安裝器可以是一份標準 skill，讓一般 agent 使用現有
shell／Python 工具處理 ZIP；不需要另外發明 ZIP 匯入平台。
現有 private `extension-management` 是只輸出 JSON 的管理規劃角色，不能
直接當作會解壓、移動檔案的一般工具型 agent。

## Desired Outcomes

- CLI 與既有 Desktop 的一般對話都能明確選用公開 `skill-installer`，例如
  「請用 skill-installer 安裝 /tmp/example.zip」，亦保留 slash 入口。
- ZIP 可以和已展開的 skills 共存於既有 drop-in skill 目錄；只有真正的
  skill 根目錄成為安裝項目。GitHub 外層包裝目錄不要求使用者手動拆解。
- 原始 `SKILL.md` 與支援檔案保持完整，只有使用者指定的 skill 被安裝或更新。
- 成功回報包含名稱、來源與安裝位置、實際結果及啟用時點；新 startup catalog
  能載入它，後續能依 skill 根目錄正確取得資源。

## Success Conditions

- [ ] 固定目錄內單一 skill ZIP 的明確安裝請求，經現有一般 agent 工具迴圈
      完成安裝；使用者不必手動解壓、改寫文件或操作管理 CLI。
- [ ] 包含 GitHub 外層目錄、根層參考檔及 scripts 的標準 skill，可保留原始
      相對結構和檔案 bytes；沒有自訂 manifest 也可安裝。
- [ ] 一包多個候選或既有同名項目時，agent 取得必要選擇／更新授權後能續接；
      完成、取消與會話切換不留下錯誤的 installer 狀態或舊授權。
- [ ] 同時存在未選的 skill／MCP 新增、更新、刪除時，其來源、managed copy
      與 registry entry 不因本次安裝而改動。
- [ ] 失敗、拒絕與過期 preview 不回報成功；未成功項目的既有安裝、使用者
      後續修改及原 ZIP 保留。成功項目的展開 source 仍存在，不被判成移除。
      builtin 同名衝突在寫入前拒絕；部分成功逐項回報，不承諾全批原子性。
- [ ] CLI 與 Desktop 各有一般對話入口的離線整合證據；建立新 startup catalog
      後可發現與選用 skill；目前執行中的 catalog 不假裝已更新。
- [ ] runtime 提供真實絕對 skill root 與相對資源指引，agent 使用一般工具能讀
      到根層 `forms.md` 等檔案；既有 bash cwd 與一般檔案讀取語意維持不變。
- [ ] 至少一份可追溯至上游固定版本的真實 skill ZIP 完成隔離安裝驗收；
      deterministic model 的整合證據與未執行的真實模型自主性驗證清楚區分。

## In Scope

公開 installer skill、明確對話選用、安裝澄清期間的有限續接、ZIP 與目錄共存、
僅針對選定 skill 的既有管理操作、skill root 資訊、既有 CLI/Desktop 對話串接，
以及直接相關的測試與使用文件。

路徑透過既有 `resolve_extension_paths` 決定。Source checkout 的預設目錄為
`app/tool/skill/`；config override 與 wheel 使用者資料目錄必須繼續有效。
`app/skills/` 是 built-in skills，不把使用者下載內容寫入套件原始碼。

## Non-Goals

- GUI 拖曳／上傳 UI、背景監看、自動掃到 ZIP 就安裝、hot reload。
- 遠端 GitHub 下載入口、marketplace、Vercel CLI 整合、多平台套件管理器。
- 通用 skill 自動推薦／語意路由、所有 skills 持續啟用、第二套 agent loop。
- 統一改寫外部 `SKILL.md`、強制自訂 manifest、完整模擬各家私有工具與 metadata。
- 自動執行下載 skill 的腳本、安裝其依賴、建立新的 service／registry／格式。
- MCP 安裝功能擴充、既有 issue 06／07 的全面修復、RAG 或 citation 重構。

## Preserved Behavior and Invariants

- 既有 Extension-Management 全量操作與 MCP exact-binding approval 保持有效；
  對話 installer 的範圍不能擴大為全量同步。
- 來源驗證、bundle 大小限制、managed state、registry revision 與 stale-preview
  檢查保留。外部 `allowed-tools` 等 metadata 不能自行擴張 host 權限。
- 原始 skill bundle 是安裝資料；其中指令不得改變 installer 的任務與授權。
- 一般 skills 的 one-shot、citation 的既有生命週期，以及 extended mode 的
  工具限制保持有效。installer 以 normal mode 執行，不能全域開放 extended bash。
- 安裝完成與能執行 skill 的全部業務能力分開判定；缺依賴可如實回報，不能以
  已安裝宣稱第三方腳本已測試通過。

## Constraints

- **Authority — 使用者決策：** 使用已有 agent、工具與管理流程完成本機 ZIP
  安裝，優先簡單、低成本；不把「沒有專用 ZIP API」當作不相容的證據。
- **Authority — AGENTS.md：** Linux、Conda `app`、Poetry、LF，禁止未經授權
  的 dependency／環境變更及範圍擴張；只新增最小必要回歸測試，不建新框架。
- **Authority — 現有應用政策：** shell 執行遵守目前 permission policy。
  安裝請求只涵蓋已識別的來源與選定項目；覆寫或新增選擇須有對應使用者意圖。
  不憑空要求重複確認，也不能由模型自行填入「已批准」繞過 host 檢查。
- **Authority — 本次請求：** 只撰寫本 bundle 並 commit/push；實作必須由日後
  明確執行要求啟動，詳見 `PLANS.md` 與 `PROMPTS.md`。

## Known Unknowns and User Decisions

目前沒有尚待使用者決定的產品範圍。以下是待實作觀察的技術事項：

- Phase 01 確認最小 selected-skill scope 如何貫穿 preview／apply 重新掃描，
  不改 persistent schema，也不弱化原本全量流程的驗證。
- Phase 02 確認共同 session 的明確選用與暫存安裝狀態接點，以及 Desktop
  turn 內 host action 的批准關聯；不能假定既有 shell approval 是通用安裝批准。
- Phase 03 固定真實上游 ZIP 的來源版本、archive hash 與隔離驗收程序。
  無可取得的代表性檔案時，最終驗收保持未完成，不能用 synthetic fixture 取代。

## Source Inputs

Repository baseline 與檔案責任見 `PLANS.md`；以下外部資料用於設計參考，
不構成第三方程式碼的執行授權，也不表示各專案都提供本機 ZIP 安裝介面。

| 來源 | 可採用的做法 | 本計畫的使用方式 |
|---|---|---|
| [Agent Skills specification](https://agentskills.io/specification) | `SKILL.md`、name/description、支援檔與根目錄相對引用 | 保留標準 bundle，不新增必要公開格式 |
| [OpenCode v1.18.30 skill tool](https://github.com/anomalyco/opencode/blob/v1.18.30/packages/opencode/src/tool/skill.ts#L31-L54) | 載入指令時明示 base directory 與相對路徑用法 | 仿照 context 呈現，不引入 TypeScript runtime |
| [Hermes 固定版本安裝流程](https://github.com/NousResearch/hermes-agent/blob/d15ed4445207dda418b984e8bda0f68f48b8c6f3/tools/skills_hub_install.py#L141-L200) | 受控安裝、移動完整目錄、記錄來源／hash | 沿用本專案已存在的驗證與 registry，不複製整套 Hub |
| [Pi skill discovery/context](https://github.com/earendil-works/pi/blob/62129190d81067ec86ae5a5fc907c96bfe435a78/packages/coding-agent/src/core/skills.ts#L355-L380) | 提供 skill location，讓一般 agent 依指引讀取 | 參考一般工具配合原文件的方式 |
| [Vercel find-skills](https://github.com/vercel-labs/skills/blob/7ffbeb96f012a63c0583a2e71e24385dc497566d/skills/find-skills/SKILL.md) | skill 指示一般 agent 呼叫既有安裝工具 | 採用相同分工，這一版不新增 Node／npx 依賴 |

外部來源查核日期：2026-09-11；固定版本用於可追溯參考，不宣稱是未來最新版。
