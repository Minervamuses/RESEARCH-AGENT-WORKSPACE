# Phase 02 — Desktop completed Citation 精確重送

## 目標與來源

同 session、同 canonical 身分的 completed Citation 重送只讀原 durable answer，即使目前 Citation runtime 已失效；新工作或可重試的未完成回合仍需有效 runtime。
來源：[GOALS](../GOALS.md)、[PLANS](../PLANS.md)、desktop/service.py:_session_turn／_desktop_command_eligible、session.py:turn_outcome／_begin_persisted_turn、conversations/repository.py:_same_logical_input／append_pending。
現有 test_desktop_service.py:test_composer_citation_uses_shared_command_and_available_catalog 只測失效 runtime 下的新請求；test_citation_e2e.py 的 completed duplicate 直接呼叫 Session，均不足以代替本 phase。

## 範圍與非目標

Production 預期為 app/agent/desktop/service.py，若重用 canonical 判斷需調整同層接縫則局部涉及 session.py；不新增 RPC／DTO、持久 schema 或通用 duplicate registry。
測試沿用 test_desktop_service.py／test_desktop_conversations.py、真 ChatSession、_SearchSaveModel、RoutingFetcher、temporary repository 與保存 service。
非目標：一般 restore 改寫、忽略 integrity、跳過 session／輸入核對、為 UI 增加重送按鈕。

## 依賴、前置與停止

Phase 01 Complete；啟動前核對其有效 mode 與 canonical identity，避免重送仍拿錯 metadata。
直接 load_optional 讀檔不等於已做完 append_pending 原有 identity／fingerprint 規則；新捷徑不能以只匹配 turnId 取代既有判斷。
若提案改 public API／protocol／schema 或引入 persistent module，按 PLANS 停止，不先實作。

## 實作與驗證計畫

### Red

在真 DesktopService dispatch 完成一個 Citation 搜尋→save→正式答案；保存原 params、canonical JSON bytes、bundle bytes／mtime 與 model／provider／scope／save 計數。
先以 loader 拋 ValueError 重現同 params 的 PROTOCOL_INVALID；再加一個 tmp applied Citation bundle 實際完整性失效的代表案例，使用既有 integrity fixture，避免把所有證據都綁在 monkeypatch loader。

### Green 與對照

將「精確 completed 讀回」的 canonical 判斷放在新工作 eligibility 之前，沿用現有邊界與 lock，不建立平行解析／保存管線。menu catalog 對失效 runtime 仍不提供新工作，資料讀回不能受目前 menu 是否可列出所限制。
驗證 completed retry=false／true 均返回原答案；新 turnId、不同原始／語意輸入、錯 session/project 或其他 identity 差異不放行。failed/interrupted 且未要求 retry 仍拒絕；可 retry 的未完成回合在 runtime 失效時也不能開始工作。
完成讀回不重新建立 Citation scope、不呼叫 model/provider/save、不重寫 canonical bytes。保留目前回應 protocol 與 final-only 行為。

### Planned verification

cwd app/，依 PLANS 啟用 Conda app；開發先跑新增 nodeid，再跑直接範圍：

```bash
timeout 300s poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py -q
timeout 300s poetry run pytest tests/test_citation_e2e.py -k 'terminal_cleanup or one_shot' -q
```

若 session canonical path 有改動，補跑 test_session_persistence.py 的 duplicate／identity 直接 cases，不機械重跑 Phase 01 全部 checks。無 Node／Rust protocol 變更則不在本 phase 重跑其全套。

## 驗收條件

- [ ] Desktop 原 completed params 在 loader 錯誤與真 tmp bundle 失效兩種代表情境回原答案；不是只測 Session 直呼。
- [ ] 新回合和未完成 retry 仍拒絕 unavailable runtime；不同 identity 不洩漏／冒用他回合答案。
- [ ] completed 即使 retry=true 仍不重播；model/provider/scope/save 計數、JSON 與 bundle 不變。
- [ ] catalog、普通對話、既有 restore／retry 和 protocol checks 保留；無新資料格式或公共介面。

## 復原、證據與交接

只破壞自有 tmp bundle 做 integrity 反例；不動真正已安裝 Skills 或 user history。
記錄 exact params 身分摘要（去敏）、red/green、回應／計數／bytes，以及每個拒絕對照到 ../build-log.md。
required failure 阻擋本 phase 和 dependent phases；必要時依 PLANS 修訂未開始路線。完成後可進 Phase 03，或在其外部阻塞時進已具備產品答案與授權的 Phase 04。
