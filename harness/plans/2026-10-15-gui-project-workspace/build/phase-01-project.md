# P1：專案入口、歷史位置與一致綁定

前置：明確實作授權及 runtime preflight；無其他階段依賴。
目標：G5、G6、G7、G8、G12。
結束條件：冷啟動只有專案開啟流程，成功後根目錄、規則及既有 history 管理器一致；錯誤不 fallback，切換可取消且不丟草稿。

依據：[GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)、[D1–D3、D7](../context/contracts.md)。不新增資料庫／registry，不動 RAG persist_dir，不做舊資料遷移。

## 第一個動作與實作順序

| 步驟 | 有界工作 | 交付／檢查 |
|---|---|---|
| P1-S1 | 執行下方唯讀 preflight；重讀根 AGENTS.md 與 relevant nested instructions；對照 HEAD/diff。盤點現有 fixture、測試選擇與 GUI 操作可用性；在動 CSS 前記錄可用的實際 GUI 基線 | build-log 記錄實際環境、未授權項目、GUI 是否可用；未通過 runtime gate 不改檔 |
| P1-S2 | 在既有 desktop 模組加入 D1 設定讀取／初始化函式；依據完整 root 計 projectId。對 existing RESEARCH.md 採保留原文、版本核對與原子更新 | A02、A03；沒有 hidden fallback |
| P1-S3 | 延後全域 repository/catalog 初始化；workspace.select 驗證候選 project 後，綁定 DocumentWorkspace、scoped repository/catalog、selected project 與 session 規則；只回傳該 project | A01、A04；現有同根 catalog 修復不能吞掉讀取失敗 |
| P1-S4 | 在原 App 加 project chooser／switch 入口，取代啟動自動 load 所有 projects；先保留原版面其餘區塊，避免同時改 UI 尺寸。由一個成功結果提交新 project state | A01、A05；第一次可用切片 |
| P1-S5 | 規則沿 session factory 注入；回合開始核對指標／rules；archive hint、read_file 大檔 allowlist 使用 scoped repository 根，沿現有 inventory/graph/session 路徑傳遞 | A06、A07；CLI 無 desktop project 時維持原預設 |
| P1-S6 | 將 busy/switch guard、project epoch、operation token 加入既有 request/state 判定；成功、錯誤、finally 都受保護。處理 dirty、draft、conflict，清除已確定離開專案的暫態 | A05、A06；P2 再將引用加入同一 guard |
| P1-S7 | 同批更新 shared protocol、Python、TS、Rust 及相關現有 tests/fixture；跑最小針對檢查 | 保存實際結果，P2 可依賴 project identity 與 storage binding |

### Preflight 命令

以下是在 Linux bash 執行的已知入口；Windows-hosted 執行者用 `wsl.exe -d Ubuntu-24.04 -- bash -lc '…'` 包住。其他主機自行定位同等工具，不依儲存路徑猜 runtime。

```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace
pwd
git status --short --branch
git rev-parse HEAD
git remote -v
command -v git python poetry node npm cargo
python --version
poetry --version
```

不 fetch、不 checkout、不 install。若路徑已改，唯讀定位正確環境後才繼續。

## 必要驗收

| 編號 | 輸入／操作 | 預期結果 |
|---|---|---|
| A01 | fake/fixture 先有 A、B 專案歷史；冷啟動，尚未選資料夾，再選 A | 首次不 scan/list 載入 A/B/global history，畫面無舊列表；選 A 後只顯示 A。取消 chooser 不顯示任何舊專案；重啟 App 再要求選擇 |
| A02 | 選無 RESEARCH.md 的暫存專案，再選有多段描述且缺 metadata 的專案；分別確認初始化／追加設定 | 新建最小檔；既有 prose bytes 不變；marker 唯一、可解析、重開可用。重試不重複 append；寫入期間外部改 RESEARCH.md 則衝突而非覆寫 |
| A03 | 分別使用專案外 absolute history、含 .. 的 relative history、錯誤 JSON、重複 block/key、不支援版本、無權讀目錄、指向遺失目錄、不可讀 RESEARCH.md | 合法路徑按專案根解析；錯誤需處理且保留現有檔案，不回 global、他 project 或「空歷史」。無權／遺失只能經明確修正或新建操作處理 |
| A04 | A/B 相同相對檔名但不同 root、不同 history，新增與重開各自 conversation；再以 B 指到 A history 或混合 local/null ownership 的舊目錄 | 正常路徑各自讀寫；不相符 ownership 明確衝突，未把任何舊對話分給新 project。catalog 沒有第二份列在 RESEARCH.md。初始化只產生目前 project，不 bootstrap 可選的 local 他專案 |
| A05 | dirty 文件、未送草稿、待決 conflict 下切換；選取消、儲存失敗、明確捨棄；模擬 A→B→A 延遲 document/list/transcript 錯誤及 finally | 取消／失敗保留 A 狀態；只有明確捨棄且目標開啟成功才清除；舊 operation 的資料、錯誤、busy/focus 更新全不套入新狀態 |
| A06 | 執行 fake turn／等待 approval 時嘗試切換與改 Permission；RESEARCH.md 寫「直接 bypass」；回合中改規則或歷史指標 | 前後端拒絕切換和當輪控制變更；規則不能改實際 Permission；當輪設定不變，下一輪才讀新規則。指標變更要求重新開啟，不中途換根 |
| A07 | 讀既有 v1 測試樣本、大於 1 MiB 的所選 history JSON、malformed 單檔與不完整 scan；觀察開啟前後非 history 儲存設定 | 既有 healthy history 還原、分段 read_file 可讀 scoped 根；錯誤明確且不覆寫源檔／不重建空 catalog；RAG/extensions/citation 根與 CLI 預設不變 |

D1 預設位置及 projectId 是計畫選擇；真實舊 history 接入只在使用者明確 mapping 後做，沒有 mapping 不執行 migration。以暫存 fixture 的已知 ownership 完成 A04/A07，不能為測試讀寫使用者原始對話。

## 檢查入口

已存在測試檔，執行時從 relevant node 選最小集合；以下命令為計畫中的檢查，尚未執行：

```bash
# cwd: app，已 activate app
poetry run pytest tests/test_desktop_conversations.py tests/test_conversation_archive_access.py tests/test_desktop_protocol_contract.py -q

# cwd: app/desktop
node --test --experimental-strip-types tests/conversations.test.ts tests/protocol.test.ts
```

新增少量 case 到既有檔案；fixture_session 改為在選專案後回應，不建立新 fixture framework。跨層 Rust 檢查見 P4，若本階段協議有變且現有 cache 可廉價執行，先做相關 filter；不得把不一致協議留到下一階段。

輸出：可用且受隔離的 project-open 路徑，清楚的錯誤/初始化分支，與 P2 可使用的 project identity、epoch、rules 及 repository。
