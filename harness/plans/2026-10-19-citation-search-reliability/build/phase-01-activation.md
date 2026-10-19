# P1 — 段落留言不遮蔽明確 Citation 選擇

目標 G1；依賴：無其他階段。政策與範圍以 [GOALS](../GOALS.md)、[PLANS](../PLANS.md)為準。

## 輸入、邊界與最小方向

來源 B1／蒐證 E1。讀 `app/desktop/src/conversations.ts:735–746`、`App.tsx:2266–2303`、`app/agent/desktop/service.py:2624–2692,2842–2859` 與 `app/agent/cli/slash_commands.py:111–133,470–488`。

`skillReferences` 是精確 `@name`＋UTF-16 offset 的既有協定；slash 情境的空陣列不是獨立 bug，不能把 `/citation` 塞進該欄位。優先只在現有 `composeTurnText` 中保留主請求明確 Citation 指令的可靠開頭，再由原 backend handler 產生 skill intent。這是待測的最小設計，不是要求新欄位或通用指令掃描。優先 production 檔案為 conversations.ts；其他檔案先只讀。

## 步驟與驗收

| 步驟 | 工作 | 必須觀察的結果 |
|---|---|---|
| P1-S1 | 在現有測試建立「主輸入 /citation 查證＋選取段落＋留言」；呼叫真正 composeTurnText，將輸出交給 DesktopService 的離線 Citation fixture | baseline 能重現未啟用；修復後 session 確實收到 citation skill、可使用 citation_workflow，選取與留言完整 |
| P1-S2 | 修改最小組裝規則，保留 backend 原始自然語言參數處理 | 不用 shlex 重建段落文字，不重寫 turn identity、不新增 wire 欄位 |
| P1-S3 | 執行 targeted checks 與第一批連通案例 | 引用／留言內單獨出現 /citation 不啟動；技能只由主輸入明確選擇；回合後 runtime 恢復 |

反例需覆蓋：`/citationfoo` 不誤認、一般文字與 `@citation` 原行為不退化；`/status` 加留言仍符合既有測試（不讓本機 command 吃掉留言並提前返回）。bare `/citation` 與 `off/none/deactivate` 的既有語義維持，尤其只含停用命令時不能因附加留言變成啟動。新規則只處理明確 Citation 啟動，不能把所有 slash 指令搬到最前。重試沿用 frozen 提交，不再次包裝。

## 可重用檢查

- 前端 `tests/conversations.test.ts:825–854`、`tests/inline_skills.test.ts:36–54`。
- Python `tests/test_desktop_service.py` 的 `test_composer_citation_uses_shared_command_and_available_catalog`；`tests/test_citation_slash_command.py`、`tests/test_citation_skill_activation.py`。
- 提議新增一條跨層測試：在既有 Python module 以 Linux Node 執行真實 TS 函式、取回提交 payload，再走真實 backend skill 選擇與 fake model/provider。目前沒有這條 bridge；不要假稱既有，亦不要另建框架。
- 命令：在 `app/desktop/` 跑 `node --test --experimental-strip-types tests/conversations.test.ts tests/inline_skills.test.ts`；在 `app/` 跑 `poetry run pytest tests/test_desktop_service.py tests/test_citation_slash_command.py tests/test_citation_skill_activation.py -q`。新增跨層測試放入既有檔案後一併跑。

若單檔組裝無法同時保留控制命令與資料邊界，先提供最小替代位置及反例，不擴為 protocol 改造。輸出為 focused diff、實際串接的離線結果及 log；P3/P4 可重用同一代表案例。
