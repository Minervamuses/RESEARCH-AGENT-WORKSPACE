# Extended Thinking／Thinking Effort 多段位控制（延期）

- 狀態：Open / Deferred；未實作、未驗收新段位。
- 使用者在2026-09-12明確表示「這個我打算再擱置」。2026-09-13要求清理已完成問題卡與計畫，僅留下本卡；原09計畫與final_check延期決定收斂於此。
- 需求：未來 Desktop 提供 Thinking Effort button，讓使用者以多個段位調整 thinking effort。恢復前不追問、不代選產品契約。

## 保留現況

現有 UI／CLI／protocol 支援 Normal 與 Extended。Extended 是 prompt rewrite、proposer、reviewer／reviser 與 fusion 工作流，不能當成 provider 的單一 reasoning-effort 參數。本次延期不移除或改寫現有行為。

目前新對話及 backend restart 使用 Normal，同程序 A→B→A 保留各對話選擇；canonical turn 的 thinkingMode 是歷史執行 metadata，不等於下一回合偏好。Citation 與 installer 的 Normal 邊界、installer 結束後恢復原選擇繼續保留。

## 恢復前需決定

| 項目 | 尚未定案內容 |
|---|---|
| 段位 | 數量、名稱、穩定值、順序、預設，以及與 Normal／Extended 的關係。 |
| 行為映射 | workflow、model、provider effort 或明示組合；適用角色、不支援時的可見結果及 CLI 相容方式。 |
| 保存範圍 | 新對話、同程序切換、restart 的行為；對話或全域偏好、是否增加 metadata 與舊資料相容。 |

使用者明確恢復並決定上述契約後，依當時 live code 提出最小必要 API／protocol／schema 差異與成本，取得尚缺的具體實作授權。不得先填 enum、provider 參數、model slug 或 migration；沒有依賴／環境變更或付費 provider 授權。

## 未來最小驗收

- 選擇本身不送出回合、不覆蓋草稿；keyboard／mouse 可操作，UI 只顯示已生效的值。
- 同一 session 切換兩個核准段位後，下一回合的實際 workflow／request 符合映射，包含 model 已建立的情況。
- 新對話、A→B→A、restart、舊資料、busy／approval、失敗及 stale response 符合定案契約。
- Python／JSON contract／TypeScript／Rust／CLI 一致；保留 Citation、installer、Bash approval、final-only、cancel/retry 與 canonical integrity。
- 真 Linux Desktop 與最小離線檢查有實際證據；fake model 結果不作真 provider 品質、速度或成本宣稱。

## Live code / tests

- app/agent/cli/slash_commands.py
- app/agent/session.py
- app/agent/llm/thinking.py
- app/agent/thinking/orchestrator.py
- app/agent/desktop/service.py
- app/agent/conversations/models.py
- app/desktop/protocol/v1/contract.json
- app/desktop/src/protocol.ts
- app/desktop/src-tauri/src/protocol.rs
- app/desktop/src/App.tsx
- app/tests/test_thinking_session.py
- app/tests/test_session_persistence.py
- app/tests/test_desktop_service.py
- app/desktop/tests/protocol.test.ts

原產品需求與延期／驗收歷史保存於 [清理前的 Git 紀錄](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/build-log.md)；這些歷史紀錄不表示本卡的新功能已完成。
