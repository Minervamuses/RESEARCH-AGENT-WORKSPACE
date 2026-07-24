# Extension apply 的多 CLI 競爭

## 原 annotation

> 這個我也需要你講白話一點。

## 白話說明

問題只會在兩個獨立 CLI 幾乎同時執行 Extension Management apply 時出現：

1. CLI A 讀到 registry 版本 5，準備加入 Skill A。
2. CLI B 也讀到 registry 版本 5，準備加入 MCP B。
3. A 寫入版本 6，內容包含 Skill A，並回報成功。
4. B 隨後也寫入版本 6，但它是根據舊版本 5 產生，可能只包含 MCP B。
5. B 最後寫入，覆蓋 A 的 registry；A 已回報成功的 Skill A 消失。

目前的 `threading.Lock` 只能防止同一個 Python process 內同時 apply，無法協調兩個不同終端中的 CLI process。

## 判定

- 優先度：低至中。
- 狀態：不阻擋 branch 整併，後續處理。
- 若實際操作規則是一次只在一個 CLI 執行 Extension Management，便不會發生。

## 後續方向

- 在 registry 的「重新讀取 revision、套用變更、寫回」整段流程外加跨 process 檔案鎖；或
- 實作原子 compare-and-swap，只有 registry 仍是預期 revision 時才允許 replace。

## 驗收條件

- 兩個 process 同時以 revision N apply 時，最多一個成功寫入。
- 另一個 process 必須收到 registry changed／retry 訊息，不得回報假成功。
- Registry 仍維持完整 JSON，不產生部分寫入或遺失更新。
