# C10-S0 跨階段詞彙收尾（G2）

- **日期**：2026-11-22，程式狀態 `6e97400`。
- **腳本**：同目錄 [`vocabulary.py`](vocabulary.py)（從 PLANS.md「目標詞彙」解析清單，與 `contract.json` 比對；錯誤碼以 `grep -rn '"<CODE>"'` 搜尋 `app/agent`、`app/skills`、`app/rag` 與 Rust）。

```bash
python3 harness/plans/2026-11-19-repo-debt-cleanup/evidence/C10-S0/vocabulary.py
```

## 輸出

```
methods 25 target 25
  contract-only: []  target-only: []
requestEvents 8 target 8
  contract-only: []  target-only: []
processEvents 4 ['backend.crashed', 'backend.protocol_error', 'backend.ready', 'backend.shutting_down']
errorCodes 25
  PROTOCOL_INVALID: python=54 rust=18 producer=agent/desktop/errors.py:205
  PROTOCOL_VERSION_UNSUPPORTED: python=1 rust=5 producer=agent/desktop/protocol.py:443
  RUNTIME_WRONG_CONDA_ENV: python=1 rust=9 producer=agent/desktop/server.py:465
  SESSION_NOT_READY: python=30 rust=0 producer=agent/desktop/project_ops.py:23
  OPENROUTER_NOT_CONFIGURED: python=2 rust=0 producer=agent/desktop/errors.py:24
  OLLAMA_UNREACHABLE: python=1 rust=0 producer=agent/desktop/errors.py:171
  OLLAMA_MODEL_MISSING: python=1 rust=0 producer=agent/desktop/errors.py:154
  GRAPH_LIMIT_REACHED: python=2 rust=0 producer=agent/desktop/errors.py:22
  BUSY_TURN: python=12 rust=0 producer=agent/desktop/project_ops.py:68
  TURN_CANCELLED: python=4 rust=0 producer=agent/desktop/server.py:316
  BUSY_KNOWLEDGE_MUTATION: python=3 rust=0 producer=agent/desktop/command_ops.py:417
  BUSY_EXTENSION_OPERATION: python=6 rust=0 producer=agent/desktop/errors.py:21
  INVALID_PATH: python=12 rust=0 producer=agent/desktop/errors.py:23
  RAG_READ_FAILED: python=7 rust=0 producer=agent/desktop/errors.py:191
  RAG_WRITE_FAILED: python=7 rust=0 producer=agent/desktop/errors.py:183
  RAG_PARTIAL_WRITE_POSSIBLE: python=1 rust=0 producer=agent/desktop/errors.py:178
  PRUNE_PREVIEW_STALE: python=2 rust=0 producer=agent/desktop/command_ops.py:275
  EXTENSION_PREVIEW_FAILED: python=2 rust=0 producer=agent/desktop/errors.py:131
  EXTENSION_APPLY_FAILED: python=9 rust=0 producer=agent/desktop/errors.py:129
  APPROVAL_DENIED: python=4 rust=0 producer=agent/desktop/approvals.py:142
  PROVIDER_RATE_LIMITED: python=1 rust=0 producer=agent/desktop/errors.py:113
  PROVIDER_REQUEST_FAILED: python=1 rust=0 producer=agent/desktop/errors.py:123
  BIBLIOGRAPHY_CONFLICT: python=1 rust=0 producer=agent/desktop/bibliography_ops.py:82
  BIBLIOGRAPHY_FAILED: python=3 rust=0 producer=agent/desktop/bibliography_ops.py:83
  INTERNAL_ERROR: python=25 rust=3 producer=agent/desktop/errors.py:209
```

## 判讀

- **方法**：contract 25 個，與 PLANS.md 的 25 個完全一致（雙向差集皆空）。
- **request event**：8 個，完全一致。**process event**：4 個，不變。
- **錯誤碼**：25 個都有 producer，沒有新的死錯誤碼，**不移除任何錯誤碼**，因此不需重跑協定測試。輸出中 `errors.py:21–24` 的命中是 `_SELF_EXPLANATORY_FAILURE_CODES` 集合常數（腳本的單行過濾抓不到多行集合）；這 4 個碼的 Python 引用數都 ≥ 2，另有實際 producer：`BUSY_EXTENSION_OPERATION`（`service.py` 的 `_raise_if_knowledge_or_extension_active`、`turn_ops.py`）、`GRAPH_LIMIT_REACHED`／`OPENROUTER_NOT_CONFIGURED`／`INVALID_PATH`（`errors.py` 的 `_map_exception`）。斜線指令使用的 `OLLAMA_*`、`BUSY_KNOWLEDGE_MUTATION`、`RAG_*`、`PRUNE_PREVIEW_STALE` 照舊保留（GOALS A3）。
- C4、C5、C6 都已完成，沒有因阻塞而產生的差異。
