# Phase 04 — Desktop Dynamic Skill Command

## Initial Status

Not started.

## Dependencies

Phase 03 Complete.

## Objective

讓 Desktop composer 直接使用 Phase 03 的 Python-owned `/<skill-name> <自然語言 prompt>` resolver 執行一次性工作，並完整移除 GUI Active Skill control、Task mode presentation、persistent activation RPC 與 restart snapshot residue。

## Confirmed Cause

- React 目前顯示 Active Skill dropdown/button 與 Task mode state。
- Desktop protocol/Python service 目前提供 `session.list_skills`、`session.activate_skill`、`session.deactivate_skill`，並在 control snapshot 中保存/恢復 active Skill/task mode。
- Composer 目前只接受 bounded static slash allowlist，不會把 dynamic Skill command交給 Python resolver。
- 移除 UI 而不補 command route 會讓 GUI 完全無法啟動一般 Skill；只開 allowlist 而保留 RPC 又會留下兩套互相衝突的 lifecycle。

## Required End-to-end Flow

1. React 把 composer 原始文字送到既有 `session.turn` boundary，不解析 Skill name、catalog、collision 或 lifecycle。
2. Python Desktop service 先尊重 static built-in dispatch，再用當前 session 的 Phase 03 resolver辨識 dynamic Skill command。未知/invalid slash command在model前回傳 bounded error。
3. Valid `/<skill-name> <prompt>` 是會執行 agent 的 `responseKind=answer` turn，不是純 local `responseKind=command`；它使用 trailing raw prompt、正常 busy/cancel/persistence/catalog-registration semantics。
4. Phase 04 可暫時沿用現有 finalized answer delivery；真正 live delta由 Phase 05處理。但不得另做 Skill-specific streaming path。
5. Transcript/history保存自然語言 prompt與final answer，不把 persistent Active Skill state存進 control snapshot，也不等待下一回合。
6. Success/error/cancel/shutdown cleanup由 Phase 03 session lifecycle擁有，Desktop不得自行 restore或deactivate race。

## Causal Scope

### Python Desktop

- `app/agent/desktop/service.py`
- `app/agent/desktop/fixture_session.py`
- `app/agent/desktop/protocol.py` only if live contract owner requires it
- `app/tests/test_desktop_service.py`
- `app/tests/test_desktop_conversations.py`
- `app/tests/test_desktop_protocol_contract.py`
- `app/tests/test_desktop_fixture.py`

### Shared contract / Rust / React

- `app/desktop/protocol/v1/contract.json`
- Existing protocol fixtures under `app/desktop/protocol/v1/`
- `app/desktop/src/protocol.ts`
- `app/desktop/src/App.tsx`
- Directly related stylesheet only for removing the control without layout gap
- `app/desktop/src-tauri/src/protocol.rs`
- `app/desktop/tests/protocol.test.ts`
- `app/desktop/tests/conversations.test.ts`
- `app/desktop/tests/backend.test.ts` only if RPC inventory is asserted there

Phase 04不得修改 general Skill/Citation core semantics established by Phase 03；若 shared contract shape requires另檔，先記錄 exact expansion。

## Non-goals / 非目標

- 不在 React 建立 dynamic Skill allowlist/parser、active state 或 second catalog。
- 不新增 Citation GUI 替代入口、不改 Citation lifecycle。
- 不實作 live streaming attribution（Phase 05）、Plan v2（Phase 06）或其他 UI redesign。
- 不新增 dependency、protocol major version、generic RPC framework 或 persistent control compatibility layer。

## Removal Checklist

- React Active Skill dropdown/button、Task mode label/selection與associated local state/event handlers。
- Protocol methods `session.list_skills`、`session.activate_skill`、`session.deactivate_skill` 及 Python/Rust dispatch/fixtures/tests。
- DTO/control fields `activeSkill`、`taskMode`、`taskModes`、`activeTaskMode` 和相應 snake_case state。
- Conversation control snapshot中的active/task capture與restart/session-select restore。
- Desktop fake session的persistent activate/deactivate API，除非 Citation static CLI test seam需要且不由Desktop公開。
- User-facing help/status若仍暗示 GUI dropdown或兩步 `/skill`，同步改成dynamic one-shot command。

`loadedSkills` 可保留為 bounded diagnostics/catalog evidence，但不得是 selectable control、active state或React-owned validation source。

## Citation Deferred Boundary

- `/citation` 仍是保留 static name，dynamic resolver不能接管。
- 本 phase 移除通用 GUI Skill controls後不新增 Citation button、alias或hidden RPC；GUI Citation暫時無入口是 `issue/08-citation-skill-flow-deferred.md` 已明記的deferred gap。
- 不刪/改 Citation CLI handler、registry/finalizer/thinking lifecycle；focused tests只證明 Desktop generic cleanup沒有從protocol側誤觸它。

## Acceptance Criteria

- GUI輸入一個fixture-loaded `/<skill-name> <prompt>`，Python resolver收到exact raw text，agent只執行一次，呈現/persist一個answer turn。
- 下一普通turn沒有Skill context；error/cancel/shutdown path也沒有generic Active Skill residue。
- Empty/unknown/collision command不呼叫agent，React顯示bounded error且draft可修正。
- Busy時第二個dynamic command與普通turn都不能重疊；cancel屬同一request，不留control snapshot。
- UI、protocol contract、Rust/Python dispatcher與fixtures不再含generic list/activate/deactivate RPC或active/task fields。
- Static slash commands仍走原handler；React沒有變成slash parser。
- Citation deferred gap在help/status/issue中誠實呈現，不被臨時兼容層掩蓋。

## Focused Verification

```bash
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py -q

cd /home/minervamuses/research-agent-workspace/app/desktop
node --test --experimental-strip-types tests/protocol.test.ts tests/conversations.test.ts tests/backend.test.ts
./node_modules/.bin/tsc --noEmit
cargo test --manifest-path src-tauri/Cargo.toml protocol::tests
```

完整 `npm test` 保留到 Phase 07 的唯一 broader pass；本 phase 不重跑 frontend build。

```bash
git diff --check
```

## Handoff Evidence

在 `build-log.md` 記錄：

- Dynamic command raw input、resolved Skill、agent invocation count、stored user text與next-turn state。
- Error/cancel/shutdown cleanup observations。
- Removed method/field inventory與repository search結果。
- Citation GUI gap仍deferred的explicit audit。
- Contract fixture同步、focused outcomes、diff與local commit disposition。
