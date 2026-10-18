# Research Agent

供個人研究使用的本地桌面工作區：開啟研究文件、與 agent 討論、對文件或對話逐段留言，再由 agent 依要求修改目前文件。對話、知識庫與產出保存在本地；模型及啟用的外部工具仍可能需要網路服務。

**文件編輯器只開啟目前研究專案內的 `.md`、`.markdown`、`.tex`。研究資料放在 WSL 檔案系統。**

## 環境與首次準備

支援的執行環境是 Linux。這套桌面選檔流程使用 Windows 上的 WSL／WSLg：Python、Node、Rust、Git 與後端都在 Linux 執行，Windows 只提供原生資料夾與檔案選擇視窗。WSL 須能呼叫 `powershell.exe` 與 `wslpath`。

本機驗證環境為 Ubuntu 24.04。建置使用的系統套件包括 `build-essential`、`pkg-config`、`libgtk-3-dev`、`libwebkit2gtk-4.1-dev`、`libssl-dev`、`librsvg2-dev`；請先備妥相應的 Linux 桌面建置環境。

在 **WSL terminal、workspace 根目錄**執行首次安裝：

```bash
conda env create -f app/env/env-app.yml
conda activate app
cd app
poetry install
cd desktop
npm ci
cd ../..
```

已存在 `app` 環境時直接啟用，不必重新建立。Conda 管理 Python、Poetry、Node 與 Rust；Poetry 在這個環境內管理 Python 套件，專案已停用 Poetry 自建虛擬環境。

模型使用啟動 shell 繼承的 `OPENROUTER_API_KEY`，例如：

```bash
export OPENROUTER_API_KEY='你的金鑰'
python main.py
```

程式不會自動讀取 `.env`。模型設定在 [AgentConfig](app/agent/config.py)。知識庫語義檢索另需可連線的 Ollama 與 `bge-m3` 模型，可用 `ollama pull bge-m3` 準備；其餘 RAG 設定見 [RAG 文件](app/rag/README.md)。

## 日常啟動

每次從 workspace 根目錄啟動：

```bash
conda activate app
python main.py
```

啟動器會使用正式版桌面程式；首次啟動，或桌面原始碼比執行檔新時，會先建置。它不會代替首次的 `poetry install`／`npm ci`。開發時可用 `python main.py --dev` 啟用即時重新載入；`--rebuild` 可強制重建正式版。

桌面開啟後自動啟動本地後端並顯示準備狀態，正常使用不需要再按 Start。Backend ready 表示本地連線就緒，尚未送出研究或模型請求。若啟動或環境檢查失敗，依畫面的錯誤與 `Retry start`、`Retry runtime check` 或 `Restart backend` 重試。

側欄的 Restart 仍用於重新載入已設定的 MCP servers，也供需要重啟的擴充管理流程使用。停止目前回合請使用 Stop。

## 開啟專案、文件與對話

1. 按 **Choose project folder…**，在 Windows 原生視窗選取 WSL 資料夾，例如 `\\wsl.localhost\Ubuntu-24.04\home\你的帳號\research`。
2. 檢查畫面顯示的 Linux 專案路徑與 history directory。已有設定時按 **Open project**；首次設定時確認歷史位置，再按 **Initialize and open project**。專案的 `RESEARCH.md` 保存研究規則及對話歷史位置。
3. 在文件區右上方選單選 **Open file**，選取目前專案內的 `.md`、`.markdown` 或 `.tex`。編輯後以 **Ctrl+S** 保存。Windows 選取路徑會對應到原本的 Linux 文件，開啟與保存使用同一份實體檔案。
4. 從側欄手動選取既有對話，或按 **New conversation** 建立新對話。

每次重新開啟程式都要手動選專案、文件與對話；既有歷史仍保留，但不自動回到上次位置。取消原生選檔視窗會保留目前文件與未送出的草稿。

## 逐段留言與整批送出

在目前文件或一則對話訊息內選取文字，按 **Add comment** 或 **Comment on selection**。agent 回覆也可以作為引文來源。每段都有對應留言框與數字入口。

- 在段落留言框按 **Enter** 只會確認並收合這則留言；**Shift+Enter** 換行，輸入法組字中的 Enter 不會送出。
- 可以繼續標註其他段落，或點數字入口重開修改、移除留言。
- 最後按主輸入區的 **Send**，將主訊息、本批全部留言及引文一起送成一個回合。主訊息可以空白；在主輸入框按 Enter 也會送出，Shift+Enter 換行。

引文是來源資料，留言與主訊息才是使用者要求。批次留言不等於批次授權；Ask／Bypass 仍由使用者決定。對話引文可以用來討論，但不會回寫原對話訊息。

後端確認本回合已保存並接受後，清除本批草稿與數字標記；尚未接受的送出失敗會保留草稿。已接受後若回合失敗，依畫面的保存狀態與重試入口處理。不要用反覆 Send 判斷是否送達。

未送出的草稿與標註只存在本次程式記憶體中，不跨程式重啟恢復，也沒有獨立標註歷史。已送出的合成訊息與必要 context 仍按一般對話保存，並依正常 context window 規則使用或移出；載入舊訊息不會重新建立留言標記或額外注入標註歷史。

## 修改文件與權限

agent 可在同一回合依留言依序修改目前文件的多個段落，後續修改保留本回合先前已保存的成果。

**Ask** 會在需要核准的文件寫入或工具操作前顯示確認；核對目標與內容後才批准。**Bypass** 依目前權限策略略過這些確認，檔案範圍與版本檢查仍適用。多段留言不會自動把 Ask 改成 Bypass。

正常操作順序是：選取原文 → 留言並確認收合 → 整批送出 → 等待回合完成或確實停止 → 再手動編輯原文。標註後又手動改原文、或 agent 執行中同時手動改原文，屬於目前不支援的操作；介面不另提供鎖定、標記重定位或合併機制。

## 停止回合

送出後 **Send** 變成 **Stop**。按下後顯示 **Stopping…**，等待模型呼叫、核准等待、工具及本回合可控制的本地工作真正收束，才恢復送出下一回合的操作。本地子程序會終止並回收；已進入的短同步操作會等返回，不會提前顯示停止完成。

已接受回合的使用者訊息會保留，中斷狀態顯示為 **interrupted／Turn stopped**。Stop 不會重啟整個後端；停止完成後可直接繼續對話。若停止失敗，畫面保留實際錯誤與 **Retry Stop**，尚未收束時不能再送新回合。

Stop 保留已完成的文件寫入及工具效果，不是復原操作，也不保證撤銷外部服務已接受的請求。若回合已經完成，就保留實際完成結果。

## 重新命名與刪除對話

在側欄對話上按右鍵，選 **Rename** 或 **Delete**。這個區域使用對話專用選單。

Rename 適用於已保存的對話；新名稱會持續保存，重新開程式後仍可見，不修改原訊息。尚未送出第一則訊息的暫時對話可以刪除，但不能重新命名。

Delete 會先確認範圍：**只刪這則對話紀錄，不刪研究專案或產出文件**。取消不改資料。刪除正在執行的對話時，會先 Stop 並等回合收束；停止失敗不會繼續刪除。成功後該對話及其清單項消失。若刪除目前選中的對話，會清除選中狀態，可手動選其他對話或新建；刪除其他對話則保留目前內容。

## 其他入口與開發檢查

對話輸入 `/` 可查看目前後端提供的命令；可用命令與 skills 取決於該次 session。CLI 可用 `/help` 查看命令。

以下命令在 `app/`、Conda `app` 環境內執行：

```bash
python -m agent.cli.chat --no-mcp
poetry run pytest
poetry build
```

桌面前端檢查位於 `app/desktop/`：`npm test`、`npm run build`；Rust 檢查位於 `app/desktop/src-tauri/`：`cargo test --locked`。

程式結構與開發入口見 [app/README.md](app/README.md)，知識庫 API 見 [RAG API](app/rag/docs/API.md)。本次桌面改版的分段實機驗收、檢查結果與限制記於 [build-log.md](harness/plans/2026-10-18-desktop-interaction/build-log.md)。
