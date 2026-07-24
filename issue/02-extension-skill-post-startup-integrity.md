# Extension Skill 啟動後的完整性

## 原 annotation

> 這個我看不懂你在說什麼，講白話一點。

## 白話說明

目前流程像是「進門時檢查過包裹封條，但真正使用時只按照地址重新拿包裹，沒有再看封條是否被拆過」：

1. Extension Management 安裝 Skill。
2. 程式啟動時核對 installed bundle 的 hash，確認它是核准版本。
3. Session 之後只記住 Skill 檔案的路徑。
4. 使用者輸入 `/skill <name>` 時，程式重新從該路徑讀取 `SKILL.md`、`manifest.yaml` 與 pinned resources。
5. 這次讀取沒有再次核對 hash。

因此，如果 session 啟動後有其他程式直接修改 `state_root/installed/...`，下一次啟用 Skill 就會讀到修改後內容，不必重新 apply 或 restart。

## 判定

- 優先度：中。
- 狀態：不阻擋目前 branch 整併，後續處理。
- 在單人、本機且不直接修改 installed state 的使用方式下，發生機率低。
- 主要問題是行為與「apply 後重啟才生效」的完整性承諾不完全一致。

## 後續方向

可擇一處理：

1. `/skill` 啟用時重新計算 bundle hash，與 registry 的 `source_hash` 比較，不一致就拒絕啟用；或
2. 啟動時將已驗證的 Skill 指令、manifest 與 pinned resources 載入不可變快照，啟用時不再重讀磁碟。

## 驗收條件

- 建立 session 後修改 installed `SKILL.md`，下一次 `/skill` 必須拒絕修改內容或仍使用啟動時快照。
- 修改 `manifest.yaml` 或 pinned resource 也需得到相同行為。
- 正常 apply、restart、activate 流程維持可用。
