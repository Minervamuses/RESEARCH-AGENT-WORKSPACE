# Phase 03 — 中文保存、重啟與回歸驗收

## 目標

從新的 WSL shell 依已驗證前置步驟啟動 Desktop，真實中文組字及保存／重載
均符合 GOALS；使用者可從既有 README 重現相同輸入環境。

## 來源、範圍與非目標

來源：[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、Phase 02 證據、
`README.md` Desktop 區段、既有 Desktop fixture／conversation tests。

範圍：跨 Desktop 啟動的代表性驗收、必要回歸、移除此次臨時診斷、
更新既有 README 與原 Issue 01。
非目標：新的 runtime 功能、測試框架、provider call、system reboot、
發版、全面效能／模型評測、依賴升級。

## 依賴與前置

- Phase 02 Complete，實際 IME 操作、已驗證 recipe、fixture root 都可取得。
- 使用相同已選定引擎；新的 shell 依 recipe 建立所需環境，
  不是只沿用開發者目前 shell 的隱含設定。
- **未知：** 整體測試／Tauri build 的本機時間，於執行前檢查現有 cache、
  歷史紀錄與相關 tests；可能超過十分鐘即依 PLANS 先取得批准。
- 有些檢查未能執行，必須記錄原因與殘留風險；
  必要 GUI、保存與重啟證據仍缺少時不得完成。

## 預期元件與授權

預期只更新 `README.md` 的 Desktop／IME 前置步驟、
`issue/01-desktop-wslg-chinese-ime-input.md` 的實際結果及本計劃紀錄。
README 記錄一般使用者的環境前置條件與 `python main.py`，
fixture 只留在本計劃的驗收程序，不成為正常產品流程。

不預計新增 test。如果觀察到輸入保存 regression，先回到 Phase 02 的因果判斷，
在批准範圍內復用既有 `app/tests/test_desktop_fixture.py`；
不要更改 schema。通用授權與失敗停止條件見 PLANS。

## 驗證程序

本階段是跨啟動驗收，不另安排 Red／Green／Refactor。

### 原生驗收

使用 Phase 01 建立、Phase 02 沿用的隔離 root。關閉本次 Desktop，
在新的 WSL shell 啟用 Conda app 及 Phase 02 的 IME recipe，
重新設定 fixture 的兩個環境變數指向同一 root，再從 repo root 執行
`python main.py`。確認 seed fixture 環境後開始。

| 操作 | 可觀察判準 |
|---|---|
| 在普通對話實際組出 GOALS 中文訊息；以 Enter 選字／確認候選 | 確認期間無 session.turn／canonical 新 turn；原 draft 仍在 |
| composition 結束後再按 Enter | 新增恰好一個 logical turn，中文逐字正確，輸入框依既有行為清空 |
| 切換另一份 conversation 再切回 | transcript 中文 `userText` 不變，無重複 turn |
| 英文、中文標點、Unicode 貼上，非 composition 時 Shift+Enter | 字串／標點／換行不變；換行不送出，普通 Enter 仍只送出一次 |
| 關閉整個 Desktop 後從新 shell 依 recipe 重啟，沿用相同 fixture root | 舊中文仍可讀回；再次真實組字／送出成功 |

以 fixture 的 `store/conversations/` 內對應 JSON 或現有 repository reader
讀取實際 turn，檢查 `display_input`、普通訊息 `semantic_input` 與 transcript。
保留精確測試文字、conversation ID、turn ID、turn delta 與重啟步驟的證據。
不以回答內容含中文代替 user input 比對。

若 GUI 沒有現成 request counter，可用既有 transcript／turn count 與
canonical JSON before／after；必要時用暫時 event listener 觀察，
不用加永久 instrumentation。只有使用者實際操作時，標示 user-observed。

### 自動檢查

所有命令都在 Linux Conda app。先跑 focused，再按相關性完成 broader：

```bash
# app/desktop
npm test

# app
poetry run pytest tests/test_desktop_fixture.py::test_real_service_round_trip_registration_restore_and_final_only_answer -q
```

- 若本次改到 application code／tests，依根 AGENTS 在最後執行一次
  `cd app && poetry run pytest`；先確認是可在本機合理時間完成的測試，
  若需 live provider 或約超過十分鐘先取得批准。
  純環境／文件修正時，記錄 Python 全套與問題無直接變更關聯而不擴大執行。
- `npm run build` 在 React／TypeScript code 有修改時必需；
  若 Phase 02 已在相同 final source 執行且沒有新變更，引用該 evidence 不重跑。
- 若 launcher 有修改，重跑標準 `python main.py` 驗收；
  若 Tauri／Rust 邊界因另行批准而變更，再要求
  `cargo test --manifest-path src-tauri/Cargo.toml` 與
  `npm run tauri -- build --no-bundle`（cwd `app/desktop`）。
  未涉及 Rust 的 IME 修正不另外要求 release build；原生 dev 啟動本身是必要驗收。
- 最後 repo root：`git diff --check`、`git diff --stat`、
  `git status --short`，確認只改因果範圍內檔案且保留使用者改動。
- 不重跑已在相同 final source 通過的昂貴檢查。
  required failure 阻止完成；無關既有 failures 另記，不擴大修補，
  是否接受必要 evidence 的限制須由使用者決定。

### 文件與復原

把「已測過的 engine／版本、必要套件、實際啟動及切換方式、
候選確認與送出差別、新 shell／Desktop 重啟步驟」補到既有 README。
明確區分 Windows IME 與已驗證 Linux IME 的適用範圍，
不承諾所有 WSLg 版本或零設定支援。

按實際觀察更新原 issue；未通過原生輸入／重啟就維持未完成。
關閉本次 GUI/control，移除暫時 listener／patch。
驗收全部結束並先保存必要證據後，僅清理經 resolve 確认、自己建立的
`/tmp/research-agent-desktop-phase02-*` root；不得刪別人的 fixture 或真實 store。
已批准且供使用者日後使用的 IME 設定保留，復原方式寫清楚。

## 驗收條件

- [ ] GOALS 每項成功條件都有 exact check 或人工觀察證據，字串與 turn 數吻合。
- [ ] 新 shell 的 recipe 可用、Desktop 重啟後舊對話與新組字都正常。
- [ ] 必要 focused／broader checks 通過；未執行項及理由誠實記錄。
- [ ] README 與 Issue 01 只反映觀察結果，沒有宣告尚未測過的支援。
- [ ] 無使用者資料或付費 provider 影響，臨時診斷已清理，diff check 通過。

## 證據與交接

`../build-log.md` 記錄成功條件→實際證據對應、命令、輸入方式、版本、
限制與結案判斷。必要重大發現寫
`../context/phase-03-acceptance-context.md`。
只有實際 review 才建立 `../code_review/phase-03-acceptance-review.md`，
不強制增加一輪無風險依據的審查。

三階段皆 Complete 且 PLANS 整體完成標準滿足才交付，之後停止。
未通過則保留具體 blocker，不以「已有 plan／tests」代替修復完成。
