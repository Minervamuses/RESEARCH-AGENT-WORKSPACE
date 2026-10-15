# P4：代表性完整流程與交付

前置：P1、P2、P3 完成；沒有未解的必要資料／權限／GUI 前提。
目標：G1–G12。此階段補的是跨層串接與真實 GUI 行為證據，不重跑全部歷史測試或另建評測框架。

依據：[GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)。通過單元測試不足以完成本階段。

## P4-S1：既有隔離 fixture

使用現有 `app/agent/desktop/fixture_session.py`，其 opt-in 為 `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02` 與 `RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT`。root 必須是擁有權正確、直接位於 /tmp、名稱以 `research-agent-desktop-phase02-` 開頭的非 symlink 目錄；依現有 require_fixture_root/seed_fixture_root 條件操作。

P1/P2 只擴充現有 fixture 來生成 A、B 小型專案及 RESEARCH.md/typed references，不另建 harness。沿用 `[[fixture:fail-once]]`、`[[fixture:delayed-final]]` 與 fake approval，文件修改使用已存在的 fake document seam；若現有 seam 尚不能直接表達要求，只在同 fixture 局部補一條有必要的路徑，不呼叫 paid provider。

原 fixture 有跨 p1/p2 catalog 的 seed；必須調整成各專案專屬 history，不能為讓 fixture 繼續跑而繞過 production project gate。v1 相容測試另保留舊格式測試樣本。測試輸出不可寫回使用者真實 history。

啟動入口已確認 `python main.py --dev` 會呼叫 Tauri dev；不帶 --dev 可能自動 release build。啟動前檢查既有 dependencies/cache，可能超過十分鐘先批准，不使用會暗中 rebuild 的入口冒充廉價驗證。

## P4-S2：A21 完整使用者流程

在 Linux Tauri/WSLg 或實際支援的 Linux desktop 執行，記錄每步輸入、UI 結果、磁碟或 canonical JSON 必要證據，禁止只看 stage status 判通過。

1. 冷啟動：先看到專案選擇，尚未選前 trace 無全域 history 掃描／其他 project session.list。
2. 選 A：RESEARCH.md 說明及 history pointer 正確，只有 A conversations。開 A/draft.md，輸入但不存。
3. 反白第二個相同段落（含 emoji/換行），加入；卡片可展開移除，焦點到 composer；磁碟與 turn count 不變。
4. 再從 A 的 assistant 訊息反白加入；兩種來源清楚區分。未加入的目前文件背景仍可見標示。
5. 第一個帶引用回合用 fake fail-once 提交，查看 canonical pending/failed 的 frozen context；改 editor 後原 retry 至 completed，確認仍是同一提交，無 duplicate user turn。接著另建第二個帶引用的 fail-once 回合，以不同 turnId 提交並保留在 failed，不在本程序重試。
6. 關閉／重開 App，再選 A，兩回合的歷史卡片還原原文、來源與版本；重試第二個仍 failed 的回合，核對原資料一致。第一個 completed 回合不自動重播；interrupted 恢復另重用 A12 的 pending checkpoint 證據。
7. 不加引用，用目前文件「修改第 40–45 行」；Ask 拒絕無寫入、Ask 同意成功；Bypass 遇 editor/disk 版本失配仍衝突。Agent Undo 及 Save/快捷鍵正常。
8. 草稿含引用、dirty 文件時嘗試切到 B：取消完整保留；保存失敗仍在 A；明確捨棄且 B 成功後才切換。busy turn 中根本不能切換。
9. B/draft.md 與 A 同名但內容不同；重放受控延遲 A success/error/finally/approval，B 不受影響，回到 A 也不能接受舊 epoch。
10. 驗證精簡 UI：原文件操作大區消失、選單功能可用、左欄 70%、底部控制同列、沒有空白頂列，正文高度增加。
11. 將 B 指標改無效或給不可讀 history，再開啟：可見錯誤、原資料不變；不顯示 A/global 或偽造空歷史。
12. 檢查 RESEARCH.md 無 conversations 清單／完整聊天，A/B history 分開；所有實際儲存成功與 user-visible 結果一致。

A01–A20 可重用 P1–P3 已通過且此後未受變更影響的證據；不用為每項重新做一次。A21 必須是此版串起的完整代表流程。UI 操作能力不足時提供具體人工步驟與尚未驗證事項，狀態保留未完成，不以 browser-only preview 宣稱 native Tauri 行為通過。

## P4-S3：相關回歸與一次結尾檢查

可用命令（均先 activate app）；依變更挑選針對集合，已有可信同版結果不重跑。正式完整 suite 的耗時先依紀錄判斷，未知或可能 >10 分鐘需批准。

```bash
# cwd: app
poetry run pytest tests/test_desktop_conversations.py tests/test_desktop_documents.py tests/test_desktop_document_service.py tests/test_desktop_protocol_contract.py tests/test_conversation_repository.py tests/test_session_persistence.py tests/test_conversation_archive_access.py -q

# cwd: app/desktop
npm test
npm run build

# cwd: app/desktop/src-tauri
cargo test protocol

# cwd: app；僅結尾一次，相關且成本可接受時
poetry run pytest

# cwd: repository root
git diff --check
git status --short
```

Rust `cargo test protocol` 是使用現有 Rust test 的建議 filter，執行前先確認當前 test 名稱確有匹配並記錄實際 count；0 tests 不是成功證據。若需編譯但冷 build 昂貴，依契約先批准。Python/TS/Rust 使用相同有效／無效 fixtures，至少包含 project 未開、跨 project、document/chat references、UTF-16 split、過大 payload、v1 absent context、retry changed context。

條件式檢查：
- 改動 crash/pending/retry persistence 時，觸發現有 `tests/test_desktop_crash_recovery.py` 對應 case；使用 fake checkpoint，不能 kill 使用者真實 backend。
- 若修改 session factory 或控制恢復，觸發既有 session lifecycle/thinking/approval 對應 case。
- 真實舊資料遷移若另獲授權，必須先有來源備份與明確 mapping，逐筆核對原 ID、內容、數量及目標可還原，失敗保留來源；未授權時此項不適用而非已通過。
- 不觸及的 RAG/Skills 廣泛工作不新增專項 sweep；若全 suite 出現無關失敗，照實列出不追修。

## P4-S4：交付與完成判斷

build-log 記錄每項必要 A 的證據來源、實際命令及結果；標記所有條件式案例的觸發／不適用理由。檢視 diff 沒有額外 production dependency、環境／lock 變更、第二套 storage 或無關重構。任何必要失敗都保留為 Blocked/In progress，不能標 Complete。

交付給使用者：實際完成行為、改動檔案、驗證與限制、舊資料保留／遷移狀態。未獲 Git 授權只交付未提交 diff；不建立 PR、push 或切分支。全部完成即停止，不啟動可選清理或效能工作。
