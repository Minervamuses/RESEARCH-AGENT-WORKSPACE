# C1-S3 清理前量測（基線指標）

- **日期**：2026-11-21
- **基底 commit**：`dffb14b`（`app/` 程式碼與 `3b6cfd8` 相同）
- **執行目錄**：repo 根目錄 `/home/minervamuses/research-agent-workspace`

## 1. 熱點檔案行數

指令：

```bash
wc -l \
  app/agent/desktop/service.py \
  app/desktop/src-tauri/src/protocol.rs \
  app/desktop/src/App.tsx \
  app/desktop/src-tauri/src/backend.rs \
  app/desktop/src/protocol.ts \
  app/agent/session.py \
  app/agent/desktop/fixture_session.py \
  app/desktop/src/styles.css \
  app/desktop/protocol/v1/contract.json \
  app/agent/desktop/catalog.py \
  app/desktop/src/conversations.ts \
  app/agent/desktop/protocol.py \
  app/desktop/src/backend.ts \
  app/desktop/src/trust.tsx \
  app/desktop/protocol/v1/fixtures.json
```

結果：

| 檔案 | 行數 |
|---|---:|
| `app/agent/desktop/service.py` | 4,643 |
| `app/desktop/src-tauri/src/protocol.rs` | 3,638 |
| `app/desktop/src/App.tsx` | 3,059 |
| `app/desktop/src-tauri/src/backend.rs` | 2,497 |
| `app/desktop/src/protocol.ts` | 2,333 |
| `app/agent/session.py` | 1,555 |
| `app/agent/desktop/fixture_session.py` | 1,493 |
| `app/desktop/src/styles.css` | 1,299 |
| `app/desktop/protocol/v1/contract.json` | 1,261 |
| `app/agent/desktop/catalog.py` | 840 |
| `app/desktop/src/conversations.ts` | 800 |
| `app/agent/desktop/protocol.py` | 760 |
| `app/desktop/src/backend.ts` | 605 |
| `app/desktop/src/trust.tsx` | 549 |
| `app/desktop/protocol/v1/fixtures.json` | 5,194 |

## 2. 協定詞彙與 Fixtures 數量

指令：

```bash
/home/minervamuses/miniconda3/envs/app/bin/python -c '
import json
c = json.load(open("app/desktop/protocol/v1/contract.json"))
print("methods:", len(c["methods"]))
print("requestEvents:", len(c["requestEvents"]))
print("processEvents:", len(c["processEvents"]))
print("errorCodes:", len(c["errorCodes"]))
f = json.load(open("app/desktop/protocol/v1/fixtures.json"))
print("messages:", len(f["messages"]))
print("traces:", len(f["traces"]))
'
```

| 指標 | 數值 |
|---|---:|
| `contract.json` 方法（`methods`） | 40 |
| `contract.json` request event（`requestEvents`） | 20 |
| `contract.json` process event（`processEvents`） | 4 |
| `contract.json` 錯誤碼（`errorCodes`） | 25 |
| `fixtures.json` message 案例（`messages`） | 127 |
| `fixtures.json` trace 案例（`traces`） | 60 |

## 3. `App()` 與 `App.tsx` 的 React Hook 數量

`export default function App()` 位於 `app/desktop/src/App.tsx` 第 1026–3059 行（檔尾）。同時記錄 `App()` 函式本體與整檔 `App.tsx` 的計數，方便 C8、C10 以相同指令重測。

指令：

```bash
# App() 函式本體（自 export default function App( 至檔尾；若未來檔尾有其他宣告則改取函式區塊）
awk '/^export default function App\(/,0' app/desktop/src/App.tsx | { grep -oE '\buseState\b' || true; } | wc -l
awk '/^export default function App\(/,0' app/desktop/src/App.tsx | { grep -oE '\buseRef\b' || true; } | wc -l
awk '/^export default function App\(/,0' app/desktop/src/App.tsx | { grep -oE '\buseEffect\b' || true; } | wc -l
awk '/^export default function App\(/,0' app/desktop/src/App.tsx | { grep -oE '\buseCallback\b' || true; } | wc -l

# 整檔 App.tsx（排除 import 行外的呼叫出現次數：import 行含 1 次，下表為 grep -oE 原始計數與扣除 import 後的呼叫數）
{ grep -oE '\buseState\b' app/desktop/src/App.tsx || true; } | wc -l
{ grep -oE '\buseRef\b' app/desktop/src/App.tsx || true; } | wc -l
{ grep -oE '\buseEffect\b' app/desktop/src/App.tsx || true; } | wc -l
{ grep -oE '\buseCallback\b' app/desktop/src/App.tsx || true; } | wc -l
```

| Hook | `App()` 函式本體 | `App.tsx` 整檔（含頂端 import 1 次） | `App.tsx` 整檔呼叫數 |
|---|---:|---:|---:|
| `useState` | 35 | 43 | 42 |
| `useRef` | 35 | 39 | 38 |
| `useEffect` | 14 | 16 | 15 |
| `useCallback` | 42 | 43 | 42 |

## 4. `styles.css` 不同色數

指令：

```bash
grep -rnoE '#[0-9a-fA-F]{3,8}\b' app/desktop/src/styles.css | cut -d: -f2 | sort -u | wc -l
grep -rnoE 'rgba\([^)]+\)' app/desktop/src/styles.css | cut -d: -f2 | sort -u | wc -l
```

（C10 重測時對 `app/desktop/src` 加 `--include=*.css` 改取第 3 欄 `cut -d: -f3 | sort -u | wc -l`。）

| 指標 | 數值 |
|---|---:|
| 不同 hex 色值數（大小寫敏感與轉小寫皆同） | 110 |
| 不同 `rgba(...)` 字面值數 | 16 |

## 5. `service.py` 對 `ChatSession` 私有成員的存取次數

指令：

```bash
{ grep -oE '(^|[^a-zA-Z0-9_.])session\._[a-zA-Z0-9_]*' app/agent/desktop/service.py || true; } | wc -l
{ grep -oE '\bself\.session\._[a-zA-Z0-9_]*' app/agent/desktop/service.py || true; } | wc -l
{ grep -n '\(getattr\|hasattr\|setattr\)([^)]*"_[a-z]' app/agent/desktop/service.py || true; } | wc -l
```

| 指標 | 數值 | 明細 |
|---|---:|---|
| `session._` 直接屬性存取 | 4 | 1513 `_set_final_text_validator`、3026 `_document_turn_active`、3075 `_load_skill_runtime`、3277 `_document_turn_active` |
| `self.session._` 直接屬性存取 | 0 | — |
| `getattr`/`hasattr`/`setattr` 字串私有存取 | 6 | 616 `(session, "_conversation_snapshot")`、2770 `(self.session, "_citation_policy")`、2788 `(self.session, "_installer_context")`、2789 `(self.session, "_skill_installer")`、2980 `(session, "_skill_installer")`、3564 `(session, "_load_skill_runtime")` |
