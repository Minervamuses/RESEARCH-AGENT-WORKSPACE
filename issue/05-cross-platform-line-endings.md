# Windows Codex Desktop 與 WSL Checkout 的行尾一致性

## Issue 定位

- 類型：Repository hygiene／跨平台工具一致性。
- 優先度：中。
- 狀態：已於 commit `3ac4f8b` 修正。
- 整併判定：不涉及功能語意；已以獨立 commit 完成行尾正規化。

## 專案背景

Repository 實際位於 WSL Ubuntu：

```text
/home/minervamuses/research-agent-workspace
```

Codex Desktop 原生執行於 Windows，透過以下 UNC workspace 存取同一份檔案：

```text
\\wsl.localhost\Ubuntu-24.04\home\minervamuses\research-agent-workspace
```

因此同一個 working tree 可能同時被：

- WSL Git／Linux Python 工具。
- Windows Git。
- Codex Desktop 的檔案 patch／命令工具。
- Windows 編輯器。

行尾政策若沒有寫進 repository，不同工具會依各自預設處理 LF／CRLF。

## 原 annotation

> 專案在 Linux 上跑，但目前透過原生 Windows 的 Codex Desktop 操作；可能是先前某段 Codex 對話為了測試自行改了行尾，卻沒有告知。

## 已確認證據

- Commit `394e228` 的訊息是 `Normalize line endings`，建立於 2026-07-23 19:52 +0800。
- 該 commit 修改 40 個檔案，加入與刪除行數相等。
- 使用 `git diff --ignore-cr-at-eol 394e228^ 394e228` 檢查，沒有語意差異；它是純行尾轉換。
- Windows Git system config：`core.autocrlf=true`，來源為 `C:/Program Files/Git/etc/gitconfig`。
- WSL Git 沒有設定 `core.autocrlf`。
- 修正前 repository 尚無 `.gitattributes`。
- 修正前部分檔案曾透過不同工具修改，造成同一檔案內混合 CRLF 與 LF。

## 處理結果

- Commit `3ac4f8b` 新增 repository-owned `.gitattributes`，一般文字固定為 LF，僅為未來的 `.bat`／`.cmd` 保留 CRLF 例外。
- 使用 WSL Git 執行 `git add --renormalize .`；忽略 CR-at-EOL 後，該 commit 除 `.gitattributes` 外沒有內容差異。
- 228 個 tracked files 的 index 與 working tree 現在都是 LF，沒有 CRLF 或 mixed-line-ending 檔案。
- Windows Git 的全域 `core.autocrlf=true` 不需修改；repository attributes 會優先決定此專案的行尾。
- 修正後 app 672 項測試與 rag 19 項測試全數通過；兩邊的 Poetry lock check、sdist／wheel build 與 import smoke 亦通過。

## 能與不能下的結論

可以合理推論：某次 Windows-side 工具對 WSL working tree 執行 checkout、add 或 commit 時，Windows Git 的 autocrlf 政策參與了轉換。Codex Desktop 是可能來源之一，其他 Windows Git／編輯器操作也可能造成相同結果。

無法只靠 Git metadata 證明具體是哪個程式或哪一段對話。Commit author 只反映 Git user identity，不記錄呼叫 Git 的應用程式。因此接手者不應把推測寫成已證實歸因。

## 實際影響

- `git diff --check repair..repair_temp` 曾產生約 10,271 筆 trailing-whitespace 報告；主要是 CR 被當成行尾空白。
- 一般 three-way merge 曾在語意相容的 `.gitignore` 產生衝突。
- Diff stat 被整檔行尾變更放大，降低 code review 品質。
- Windows 與 WSL 工具可能反覆改寫同一檔案。
- Python 執行與 packaging 測試目前仍通過；這不是已知 runtime failure。

## 已採用政策

此 repository 主要在 Linux/WSL 執行，因此一般文字檔應在 Git 與 working tree 中統一使用 LF。政策應由 repository 的 `.gitattributes` 決定，而不是依賴每台機器的 global Git config。

Repository 規則：

```gitattributes
* text=auto eol=lf
```

Windows batch 檔使用明確例外：

```gitattributes
*.bat text eol=crlf
*.cmd text eol=crlf
```

## 建議執行順序

1. 確認 working tree 乾淨並使用 WSL Git。
2. 新增 `.gitattributes`，只包含已決定的行尾政策。
3. 執行 `git add --renormalize .`。
4. 審查變更，確認沒有編碼、內容或 binary 誤判。
5. 執行 app 與 rag 測試、Poetry check、必要的 packaging smoke。
6. 建立只含行尾正規化的 commit。
7. 從 Windows Git 與 WSL Git 各做一次乾淨 checkout／status 驗證。

不要在 renormalize commit 中順便修改程式邏輯，否則無法可靠區分語意變更與行尾噪音。

## 接手 Agent 的注意事項

- 使用 WSL Git 執行 stage／commit，避免 Windows system `core.autocrlf=true` 在清理途中再次改寫。
- 在刪除或覆寫前確認使用者是否有未提交修改。
- 檢查 `git diff --numstat` 與 `git diff --ignore-cr-at-eol`，確認預期只有行尾。
- `.gitattributes` 加入後，以 attributes 結果為準，不要求使用者修改全域 Git 設定才能維持一致。

## 驗收條件

- Python、Markdown、TOML、YAML 與一般文字檔統一為 LF。
- `git diff --check` 不再因 CRLF 產生整批 trailing-whitespace。
- `git add --renormalize .` 完成後再次執行不產生變更。
- App 與 RAG 測試及 package checks 通過。
- Windows Codex Desktop 與 WSL 工具後續編輯小範圍檔案時，不再造成整檔行尾 diff。

## 主要參考位置

- Commit `394e228`
- Repository root 的 `.gitattributes`
- Windows Git system config
- `app/`
- `rag/`
