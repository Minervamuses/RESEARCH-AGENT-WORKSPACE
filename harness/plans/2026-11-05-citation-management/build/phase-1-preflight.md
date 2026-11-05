# C1 前置核對與 Pandoc

- **後置條件**：目前的基線（Git、工具鏈、三套測試）已記錄；Pandoc 在 Conda `app` 可用，並寫入 `app/env/env-app.yml`。
- **目標**：CG7、CG8。意圖與政策見 [GOALS](../GOALS.md)、[PLANS](../PLANS.md)。
- **相依**：無。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C1-S1 | 唯讀核對：`pwd`、branch（必須是 GUI）、HEAD、`git status --short`、`git diff --cached --name-only`；記錄原有的 dirty/index 項目（不 reset、stash、clean）。確認計劃檔都已被追蹤（PLANS 契約第 2 項）。核對 Conda `app` 的 python、poetry、node、npm、cargo 路徑與版本。執行完整 pytest（沙箱外）、`npm test`、`npm run build`、`cargo test --locked`（沙箱外），把通過數與耗時記入 build-log | 四項檢查的結束碼與數量都記錄；任何一項失敗時，先判斷是否為環境問題（例如 `/tmp` 唯讀），重跑仍失敗就記錄為「既有失敗」，之後的回歸以這份基線為準 |
| C1-S2 | 安裝 Pandoc 到 Conda `app`：先 `conda list -n app --export` 存成安裝前清單；執行（擬定指令）`conda install -n app -c conda-forge --freeze-installed "pandoc>=3,<4"`；再存安裝後清單並比較。在 `app/env/env-app.yml` 加入 `- pandoc>=3,<4`（若實裝版本的主版本不是 3，就改成實裝主版本的範圍，並記錄理由） | `…/envs/app/bin/pandoc --version` 成功；兩份清單的差異只有 pandoc（若有其他套件被改動，逐一記錄）；以一個三筆的 CSL-JSON 小檔與一段含 `[@a; @b]` 的 Markdown 執行 `pandoc --citeproc -t plain` 得到排好的引用；`pandoc -f csljson -t bibtex` 能輸出 `.bib`；`env-app.yml` 仍可被 `conda env create --dry-run -f env/env-app.yml` 解析（若 dry-run 不可用，記錄並以 YAML 解析代替） |

C1-S2 的證據（安裝前後清單差異、版本、小檔測試輸出）存 `evidence/C1-S2/`。commit 範例：`build(env): add Pandoc to the app environment [C1-S2]`。

## 失敗與恢復

- conda 連網被宿主拒絕：記為環境阻塞。C2、C3 不需要 Pandoc 的部分可以繼續（C3-S1 的 Pandoc 交叉比對改為條件檢查，Pandoc 可用時補做）；C4 以後阻塞。
- `--freeze-installed` 無法求解：改用不帶該旗標的指令，但必須記錄並檢查被改動的套件；若 python、poetry、nodejs、rust 任何一個版本被改動，回復並記為阻塞。

## 交付給後續階段

Pandoc 的實際路徑與版本（記在 build-log），以及基線測試數量。
