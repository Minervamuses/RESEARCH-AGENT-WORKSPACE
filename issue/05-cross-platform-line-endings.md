# Windows 與 WSL 的行尾一致性

## 原 annotation

> 這個我不確定出處，但據我猜測，可能是因為我的專案是在 Linux 上跑，但我現在是在 Codex 桌面使用你，而這個 App 原生大概是 Windows，所以為了測試，你的前面某段對話自己弄的，但沒有告訴我。

## 已知證據

- `394e228`（`Normalize line endings`）將 40 個檔案改成 CRLF；忽略 CRLF/LF 後沒有語意差異。
- Windows Git 的系統設定為 `core.autocrlf=true`。
- WSL Git 沒有設定 `core.autocrlf`。
- Repository 沒有 `.gitattributes` 固定行尾。
- 該提交建立於 2026-07-23 19:52，早於記錄此 issue 的審查回合。

以上證據支持「Windows 端工具對 WSL checkout 執行 add/commit 時自動轉換行尾」這個推測。Codex Desktop、Windows Git、編輯器或其他 Windows 端操作都有可能觸發；Git metadata 無法證明具體是哪一個程式，因此不能確定歸因。

## 判定

- 優先度：中，屬 repository hygiene。
- 狀態：不阻擋以 branch 指標取代的整併方式，但應在整併後清理。
- 目前影響包含 noisy diff、`git diff --check` 大量 trailing-whitespace，以及一般 merge 對 `.gitignore` 產生不必要衝突。

## 後續方向

在 repository root 新增：

```gitattributes
* text=auto eol=lf
```

然後做一次獨立、受控的 renormalize commit。不要把行尾清理混入功能修改，以便審查與必要時回退。

## 驗收條件

- `git add --renormalize .` 後只產生預期的行尾差異。
- `git diff --check` 不再因 CRLF 回報整批 trailing whitespace。
- Python、Markdown、TOML 與 YAML 檔案統一使用 LF。
- Windows 與 WSL 後續編輯不再反覆改變整個檔案。
