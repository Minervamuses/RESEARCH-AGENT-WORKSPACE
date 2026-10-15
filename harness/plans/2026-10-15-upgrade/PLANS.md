# upgrade｜實作路線與執行契約

## 1. 計畫包與閱讀順序

計畫根目錄：`harness/plans/2026-10-15-upgrade/`（相對 repository root）。計劃 ID：`upgrade`。使用 Linux／Conda `app`；目標為既有 `GUI` 分支。

本包只規劃，未授權開始產品實作。使用者明確啟動後，可先做 P0 唯讀確認；新依賴、通訊契約與持久格式等所需批准依第 6 節辦理。各階段的當前狀態以 [build-log.md](build-log.md) 為準。

| 檔案 | 唯一負責內容 |
| --- | --- |
| [GOALS.md](GOALS.md) | G1～G7、D1～D8、來源、範圍與非目標 |
| [PLANS.md](PLANS.md) | 基準、A1～A6／共同設計、階段依賴、執行政策與完成條件 |
| [PROMPTS.md](PROMPTS.md) | 啟動／續作、修訂、審查的可直接使用入口 |
| 第 4 節連結的 `build/phase-*.md` | 該階段的前提、工作、交付與驗收 |
| [build-log.md](build-log.md) | 唯一進度表、實際結果、批准／阻擋與下一步 |
| [plan-index.json](plan-index.json) | 靜態目標／階段／依賴對映，供結構檢查 |

先讀適用專案規範 → [GOALS.md](GOALS.md) → 本檔 → [build-log.md](build-log.md) → 下一個依賴已滿足的階段。完整啟動／續作方式見 [PROMPTS.md](PROMPTS.md)。根目錄 `upgrade.md` 只作導覽，不再維護另一份全文或進度。


## 2. 已核對的基準與整合位置

基準：`GUI`，HEAD `fb055707ba6db6fb48c832887ec164f765ab47ac`。Windows 桌面宿主透過 WSL Ubuntu-24.04 執行 Linux 命令；Python、Poetry、Node、npm、Cargo 使用 Conda `app`，Git 為 Linux `/usr/bin/git`。本次確認 Python 3.13.14、Poetry 2.4.1、Node 24.18.0、npm 11.16.0；這是環境觀察，不是升級版本要求。

| 現況與證據 | 升級含義 |
| --- | --- |
| [App.tsx](../../../app/desktop/src/App.tsx) 的 slashPrefix 只接受草稿開頭指令；sendTurn 傳 text／turnId／retry。 | 新增行內引用與文件上下文需要前後端共同契約，不只是更換顯示符號。 |
| [DesktopService](../../../app/agent/desktop/service.py)、[session.py](../../../app/agent/session.py) 目前一次載入一個 active_skill_runtime；citation 有 Normal 與清理流程。 | 多 Skill 必須處理工具准入、一次性清理、citation 與錯誤／重試，不可只拼接名稱。 |
| [catalog.py](../../../app/agent/desktop/catalog.py) 的 project 只有 projectId／name／sessionIds，沒有研究資料夾 root。 | 不能把現有對話分類 ID 當成檔案系統根目錄；新工作區需明確選定資料夾。 |
| [contract.json](../../../app/desktop/protocol/v1/contract.json)、[fixtures.json](../../../app/desktop/protocol/v1/fixtures.json)、[Python](../../../app/agent/desktop/protocol.py)、[TypeScript](../../../app/desktop/src/protocol.ts)、[Rust](../../../app/desktop/src-tauri/src/protocol.rs) 共同驗證 NDJSON。 | 文件／引用／授權資料須同步更新相應邊界及既有 fixture；先取得契約變更批准。 |
| Bash approval 才讀 bashPermissionMode；citation save、knowledge prune、extension apply 有其他入口。 | 不能只改按鈕文字就宣稱「整份專案 Bypass」；逐一確認所有副作用入口。 |
| [citation service](../../../app/skills/citation/service.py) 的 search 已呼叫 provider.search_text，可接一般查詢文字；[citation types](../../../app/skills/citation/types.py) 的既有輸出不含摘要，provider 搜尋結果也未完整傳遞摘要。 | 重用現有 discovery／核驗分工；只補文件論述上下文與摘要取得／結果傳遞，不重做搜尋系統。 |
| S4 確認側欄 project.list／session.list 重複 reconcile，歷史分頁仍讀完整 JSON。 | 優先減少同次互動的重複讀取；尚不能認定這就是所有 GUI 卡頓原因。 |
| [rag/sync.py](../../../app/rag/sync.py) 不追蹤編輯器內容版本。 | 當前文件任務使用捕捉的來源內容，不能以舊 RAG chunk 當編輯座標或最新文字。 |

未提交的既有修改：`app/desktop/src/App.tsx`、`styles.css`、`tests/conversations.test.ts`、`app/rag/embedder/ollama.py`、`app/rag/store/chroma_store.py`、`app/tests/rag/test_tools_contract.py`、`main.py`。另有未追蹤的 `.project-audit/`、`app/tests/test_desktop_launcher.py`、`hallucination.md`。不得還原或收編為本次新成果。GUI memo、延後建立工具內容、對話載入並行、release 啟動與 RAG lazy import 已在工作樹，P5 先檢查再決定是否還需變更。

S4 曾回報 10 項 Skill／Bash 定向測試通過；本次沒有重跑，該歷史結果不能當成升級實作完成證據。原生 GUI、真實 provider、摘要可取得比例、Tauri 中的新編輯器都尚未驗證。

## 3. 擬採設計與尚待審閱的界線

本節是為落實 D1～D8 提出的最小方案；未標為 D 的技術選擇不是使用者已批准的依賴、格式或介面。

### 3.1 文件與版本

- **A1（可調整的首版範圍）：** 開啟既有 UTF-8 文字稿，支援 Markdown 與單一 `.tex` 的來源編輯。Markdown 預覽可沿用現有安全 renderer；不承諾公式排版或 TeX 編譯。P0 審閱時確認範圍；若需要多檔編譯或 Word／PDF，先調整本計劃再估算，不能默認加入。
- **A2（工作區邊界）：** 使用者選定研究資料夾，再開啟其中稿件；本次先在活動工作區記住 root，不要求新增持久 catalog 格式。Bypass 以此專案及本回合相關操作為界；既有 citation、索引、MCP 服務可有專案外的儲存／網路目標，須在操作資訊明示。若要記住 root 跨重啟，另列 schema 變更批准。Bash／MCP 不是新增的 OS sandbox，不宣稱能阻擋任意程式存取整台機器。
- **A3（編輯器候選）：** 優先提案 Monaco：官方將它定位為來自 VS Code 的編輯器，具有文字 model 與編輯歷史；它不等同完整 VS Code，也不保證可執行 VS Code extensions。[官方說明](https://github.com/microsoft/monaco-editor)；Vite 整合需要處理 worker 載入，[官方 ESM／Vite 指引](https://github.com/microsoft/monaco-editor/blob/main/docs/integrate-esm.md)。在 Tauri／WSLg 實際可用性仍須 P1 驗證。加入 monaco-editor、lockfile 及 worker 配置前取得批准；不預設增加 React wrapper 或 CDN。若不批准此依賴，先提出具有正確來源行號、選取與 Undo 的較小替代方案供選擇，不能默默降低功能。
- **A4（範圍與上下文）：** 選取限制「可修改區域」，可以讀取同份文件必要的周邊內容；要求跨段改寫時，說明需要擴大範圍，不自行外擴。預覽視圖不可靠的 DOM 選取不可假裝已有來源座標；首版精確行號／選取從來源編輯器取得，預覽清楚引導切回來源定位。這是首版提案，不宣稱已確認預覽直接選取需求。

送出時捕捉「專案與文件身分、編輯器修訂號、來源文字快照、選取或明確行範圍、讀取時的磁碟內容指紋」。沒有選取的行號問題解析於同一快照；文件不明、行號越界或範圍歧義時先釐清，不猜位置。

改寫結果是對該快照的指定範圍操作，不能對目前文字做全域字串取代。跨 Python／TypeScript 明確固定行／欄位與字元單位，測試中文、emoji、tab、空行、CRLF／LF 與尾端換行；保留不相關內容與原有換行形式，repo 自身檔案仍遵守 LF。

套用前同時比較編輯器修訂與磁碟版本。確認無衝突後寫入完整結果、同步編輯器狀態，顯示實際已儲存；不要等待中鎖死編輯器。比較到寫入之間不得讓本程式的其他儲存交錯；對不配合的外部編輯器不聲稱具有跨程式交易保證，最小實作須縮小並說明競態窗口，不引入分散式鎖或版本資料庫。

衝突呈現本次基準、目前內容與 Agent 候選，必要時分開顯示磁碟與未儲存編輯器差異。使用者可保留目前稿件、採用候選，或取消後重新要求 Agent；採用會覆蓋哪些內容必須可見。選擇後重新驗證版本，若再次改變，重新顯示衝突，不沿用舊同意。

存檔失敗保留目前文字與候選並顯示失敗，不誤報成功、不無限自動重試。操作結果包含檔案、範圍、儲存狀態，可跳回修改處供肉眼檢查。**A5（有限復原提案）：** 同次編輯工作階段內，Agent 的一次文件操作成為一個 Undo 單位；復原後存檔亦做版本檢查。Bash／MCP／外部副作用不承諾通用 Undo。

### 3.2 Skill、摘要與權限

**Skill 輸入契約：** 保留原始 prompt，將選單選取或經可用 catalog 精確解析的 @ 引用帶上真實名稱與文字位置；前後端重新核對，避免一般 email／普通 @ 文字被錯當 Skill。編輯草稿後重新核對位置；重複引用保留其自然語言位置，但同一 Skill 指引不重複載入。不存在、已移除或不適用的 Skill 明確顯示原因，不靜默改成普通文字。

多 Skill 由同一回合的 Agent 使用，不建立獨立並行流程。明確「先 A 再 B」時讓後一步讀到前一步產物；未要求順序時共同使用指引即可。遇到真正矛盾或缺少選擇才提問。需合併各 Skill 的已允許工具，同時保留全域工具准入；Bypass 不能產生未安裝的工具或把 Extended 變成具任意工具的模式。**A6：** 文件修改／citation 所需工具不在 Extended 時，沿用 citation 的 Normal 路徑並在介面說明本回合模式，結束後還原原選擇；若這會改變既有 Extended 契約，P0 先列出並批准，不默默降級。

摘要工作重用既有 CitationService.search → provider.search_text 與 DOI／書目核驗。由選取論述形成有界的主題查詢，不能拿完整段落冒充 search_work 的已知論文標題。對現有 provider 能取得的摘要做最小傳遞與清理，列明來源及可用性；若需要新的 API 契約先走批准。無摘要時只報 metadata 與「未取得摘要」，不得編造摘要或宣稱支持。讀到摘要也只說明摘要層級的相關／限制；不自動下載全文。

**權限契約：** 進入回合時固定 Ask／Bypass 與活動專案；執行中（含等待批准）不切換。可在回合結束後更改下一回合模式。Ask 在副作用前批准一項具體操作，顯示動作、目標及必要參數；拒絕後該操作不發生。分析與唯讀查詢不因新文件權限被額外擋住，但既有 Bash Ask 仍按命令逐次詢問。

Bypass 涵蓋文件寫入、Bash、citation 保存、知識庫匯入／刪除索引、MCP 工具及 extension 安裝／啟動等專案操作的批准步驟。釐清 prune confirmation、extension binding consent 是批准還是資料一致性驗證，僅免除前者；不再以舊入口繞出第二套強制詢問。仍執行版本衝突、路徑／身分／schema、工具可用性、來源有效性及防重複套用等正確性檢查。對沒有副作用標示的 MCP 工具，在 Ask 下按受控工具操作處理；Bypass 可執行，但不變更外部服務本身的權限。

不設新的永久批准 registry；優先復用現有 request／turn／approval 識別。未知狀態或重啟不自動重播寫入：先核對磁碟與既有回合結果，再讓使用者明確重試。文件寫入已成功但回傳中斷時，不因 retry 再次套用相同變更。

## 4. 執行路線與驗收入口

依賴順序為 **P0 → P1 → P2 → P3 → P4 → P5**。P1 先交付不依賴新多 Skill 語義的文件閉環；全產品完成仍需 P5。階段細節與驗收程序只在各階段檔維護；進度及實際結果只在 [build-log.md](build-log.md) 維護。

| 階段 | 交付後條件 | 直接依賴 | 涵蓋目標 | 詳細工作與驗收 |
| --- | --- | --- | --- | --- |
| P0 | 確認環境、範圍及必要批准 | 無 | G1、G2、G3、G4、G5、G6、G7 的執行前提 | [P0](build/phase-00-preflight.md) |
| P1 | 一份文件可精確修改、處理衝突並存檔 | P0 | G3、G4、G5 | [P1](build/phase-01-document-workspace.md) |
| P2 | 行內多 Skill 真正作用於文件 | P1 | G2、G6 | [P2](build/phase-02-inline-skills.md) |
| P3 | 所有已列操作的 Ask／Bypass 一致生效 | P2 | G7 | [P3](build/phase-03-project-permissions.md) |
| P4 | 選取論述取得可追溯的文獻與摘要 | P2、P3 | G6 | [P4](build/phase-04-citation-abstracts.md) |
| P5 | 代表性桌面流程與整體驗收完成 | P1、P2、P3、P4 | G1、G2、G3、G4、G5、G6、G7 的最終整合驗收 | [P5](build/phase-05-interaction-validation.md) |

P0 的前提核對不算達成 G1～G7；P5 也不能只因前階段已勾選就免除實際走查。靜態對映由 [plan-index.json](plan-index.json) 表達，不在 index 儲存狀態、批准或證據。相依工作等待前提時，仍可完成既定範圍內的獨立唯讀核對。


## 5. 驗證命令與成本界線

以下命令來自已存在的工具／測試位置，**本次撰寫沒有執行應用測試或建置**。執行時先確認相應測試仍存在；只跑變更相關子集，不在每階段重跑全部。

在 Linux shell 初始化 Conda；本機已核對的入口如下，其他主機先查其 Conda 路徑：

```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace
git status --short
git branch --show-current
```

| 檢查 | 工作目錄與既有命令 | 使用時機 |
| --- | --- | --- |
| 通訊契約 | app：`poetry run pytest tests/test_desktop_protocol_contract.py -q` | 修改 wire schema／fixtures 後；另跑 TS／Rust 對應 checks |
| GUI 邏輯 | app/desktop：`npm test` | 修改輸入、選取、授權狀態等；必要時用既有 node test runner 選單檔 |
| TS 與前端打包 | app/desktop：`npm run build` | P1 編輯器接入及最終前端變更；不等於原生 GUI 通過 |
| Desktop／Skill 路由 | app：`poetry run pytest tests/test_desktop_service.py tests/test_skill_runtime.py tests/test_slash_commands.py -q` | 僅選當次影響的測試／既有 -k 篩選，不必整組反覆執行 |
| 權限／工具准入 | app：`poetry run pytest tests/test_bash_tool.py tests/test_tool_access.py tests/test_policy_tool_node.py -q` | P3 與多 Skill 工具合併後 |
| Citation | app：`poetry run pytest tests/test_citation_workflow_tool.py tests/test_citation_gate.py tests/test_citation_save_outcomes.py -q` | P4；provider 有修改才加該 provider 既有測試 |
| Rust | app/desktop/src-tauri：`cargo test` | Rust 契約／bridge 有變更；先評估是否會長時間編譯 |
| 完整 Python suite | app：`poetry run pytest` | 全部相關定向檢查通過後，收尾至多一次；預期超過約十分鐘則先批准 |
| 原生啟動 | repository 根目錄：`python main.py` | 目前 launcher 可能自動 release build；先檢查現有 binary／build 成本，不能當作廉價唯讀命令 |

既有隔離 fixture 由 `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02` 選擇（見 [server.py](../../../app/agent/desktop/server.py)）；P0 先確認它隔離的外部效果及涵蓋能力，現有 fixture 不代表已能測新文件功能。在既有測試旁新增最少 regression cases，不建立新測試框架。

必需驗證以離線為主；真 provider／付費模型的整合試用須另外批准具體範圍與成本上限。沒有現成 recorded output 能證明模型實際合作時，離線結果只能證明資料傳遞與控制流程；最終報告必須標明真模型行為是否仍待驗收，不將 stub 觀察冒充實際模型品質。

## 6. 執行契約、失敗處理與完成條件

1. 本次只授權撰寫與驗證 `harness/plans/2026-10-15-upgrade/` 計畫包，以及更新根目錄 `upgrade.md` 導覽。明確啟動本計劃後，才可依已批准範圍實作；本文件內的啟動提示不是立即命令。
2. 修改範圍限於達成 G1～G7 的 GUI、desktop transport／service、session／Skill 工具准入、citation、直接相關測試。新增檔案、持久資料、依賴或格式各自通過專案適用批准界線；不修改 AGENTS.md，也不追加其他報告。
3. 依賴／package manager／lockfile／環境定義、服務／資料庫／cache／worker 或新並行模型、API／schema／protocol／持久格式變更仍須明確批准。Monaco worker 即包含在具體編輯器提案內，不可只因它是套件內部功能而略過規則。
4. Git commit、push、merge、rebase、切分支與 worktree 變動都要另有明確授權。本次不做；後續檔案與 [build-log.md](build-log.md) 紀錄可作 checkpoint，不自動提交，也不要求使用者批准同一事項兩次。
5. 每次只處理一個有因果依據的改動，跑最小有意義檢查，記錄結果再前進。兩次聚焦實作仍失敗則停止該問題，報告證據與最小下一步；一次昂貴嘗試失敗／無改善，不再自動重試。
6. 未預期的新發現，只調整直接受影響的階段；不得把假說改寫為已確認需求，或以更嚴格 gate 靜默丟棄有用結果。新增大重構／超過原批准範圍，先說明較小方案為何不足。
7. 斷線／重啟先核對實際磁碟、回合紀錄及已完成外部效果，不自動重播副作用。更新 [build-log.md](build-log.md)，保留歷史失敗與舊證據適用範圍；只有受影響工作等待決策，其他獨立可做的核對可繼續。

**完成條件：** G1～G7 有對應實際驗收證據；A～E 代表情境、版本衝突與存檔失敗分支通過；必要定向測試及收尾完整 suite 通過或阻礙已清楚列明；未執行的必要檢查不算通過。若真模型或原生 GUI 尚待驗收，只能交付「程式／離線檢查完成，指定驗收未完成」，不能宣稱整體升級完成。Diff 僅含必要變更，不以 commit 或 lint 通過代替產品驗收。
