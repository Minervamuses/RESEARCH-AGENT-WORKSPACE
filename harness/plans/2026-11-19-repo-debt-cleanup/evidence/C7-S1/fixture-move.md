# C7-S1 P5：fixture 移到測試（S020、S021、S022）

- **日期**：2026-11-22
- **產品邊界**：純搬移與刪除測試接縫，不改支援流程的行為。

## 變更

| 項目 | 內容 |
|---|---|
| 搬移 | `app/agent/desktop/fixture_session.py` → `app/tests/support/fixture_session.py`（`git mv`），新增 `tests/support/__init__.py`。4 個測試模組改為 `from support.fixture_session import …`（`test_desktop_fixture.py`、`test_desktop_document_service.py`、`test_desktop_crash_recovery.py`、`test_desktop_service.py`；第 5 個 `test_desktop_server.py` 原本只為環境變數開關 import，見下）。 |
| `server.py` | 刪除 `_build_runtime_service` 的 `RESEARCH_AGENT_DESKTOP_FIXTURE` 開關。`main(build_service=None)` 與 `run_backend(..., build_service=None)` 接受可選的 service 建構函式；不傳時用 `_build_production_service`（`DesktopService(original_cwd=...)`）。production（Tauri 啟動的 `python -m agent.desktop.server`）不傳。 |
| 測試入口 | 新增 `tests/support/fixture_server.py`：把 `app/tests` 加入 `sys.path`，以 `build_phase02_fixture_service` 呼叫 `server.main`。`test_desktop_crash_recovery.py` 的子程序改跑這個檔案，不再設定 `RESEARCH_AGENT_DESKTOP_FIXTURE`。 |
| 失效常數 | `FIXTURE_MODE_ENV`、`FIXTURE_MODE` 只服務被刪的開關，一併刪除（`test_desktop_fixture.py::_environ` 同步）。 |
| S021 | 刪除 `documents.selected_text`（production 沒有呼叫者）。fixture 改用模組內的 `_selected_text`；`test_desktop_documents.py` 的斷言改用測試檔內同義的 helper。 |
| S022 | 刪除 `DesktopKnowledgeOperations.workspace_root` 與 `/init` 核准目標的 `getattr(..., "workspace_root", None)` 分支；核准目標一律是 `find_app_root().parent`（production 的 `init_workspace` 實際匯入的位置）。`test_project_permissions.py` 的 `/init` 核准目標期望值同步改為 `find_app_root().parent`，假物件不再帶 `workspace_root`。 |

## 退役紀錄

被刪的測試 → 它保護的行為（或已刪除的細節） → 留下的證據

- `test_desktop_server.py::test_runtime_service_uses_production_for_unset_or_nonexact_fixture_gate` → 環境變數不是精確的 `phase02` 時用 production（開關已刪除） → 改寫為 `test_production_service_ignores_the_retired_fixture_environment_switch`（即使設定 `phase02` 也用 production）與 `test_main_forwards_only_an_explicit_service_builder`（`main` 只轉交明確傳入的 builder）。
- `test_desktop_server.py::test_exact_fixture_gate_refuses_startup_without_caller_root` → 開關開啟但沒有 fixture root 時拒絕啟動（開關已刪除；root 必填的檢查仍在 fixture builder） → `test_desktop_fixture.py::test_fixture_root_rejects_missing_relative_or_unsafe_paths` 新增 `""`（未設定）參數，對 `FixtureConfigurationError` 的檢查不變。

## 檢查

```bash
cd app && /home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider tests/test_desktop_*.py tests/test_project_permissions.py   # 沙箱外
grep -rn "RESEARCH_AGENT_DESKTOP_FIXTURE\|fixture_session" app/agent
ls app/agent/desktop/
```

- pytest：522 passed（含 `test_desktop_crash_recovery.py` 以新入口啟動子程序的全部案例）。
- grep：0。
- `app/agent/desktop/`：`__init__.py`、`bime_export.py`、`documents.py`、`project.py`、`protocol.py`、`server.py`、`service.py`，沒有 fixture 程式。
