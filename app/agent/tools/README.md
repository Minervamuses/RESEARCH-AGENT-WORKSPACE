# Tool definitions and enforcement

`tools` 同時放置 app-layer tool implementations 與共用 access policy。「Tool 存在」不等於「當前 mode 可呼叫」。

## Three layers

1. **Implementation**：`bash.py`、`read_file.py` 及 inventory 組裝的 document RAG tools。
2. **Resolution**：`inventory.py` 定義 local base inventory；session 再合併 MCP、extra 與 citation workflow tools，`access.py` 依 normal/active-skill policy 算出 effective tools。
3. **Enforcement**：`policy_node.py` 在執行當下重新檢查 call，拒絕 forged 或當前 mode 不可用的 tool。

## Module map

| Module | Responsibility |
|---|---|
| `bash.py` | 每次需使用者核准、以 app root 為預設 cwd 的 shell tool；不提供 filesystem sandbox |
| `read_file.py` | Controlled local file reading tool with bounded 1 MiB chunks |
| `inventory.py` | Base tool creation、names 與 system-prompt inventory |
| `access.py` | Global/skill-scoped access resolution |
| `policy_node.py` | LangGraph `ToolNode` execution-time enforcement |

## Resolution flow

```text
local base inventory + session-loaded MCP/extra/skill tools
    → session actual universe
    → active-skill ToolAccessResolution
    → graph binding and prompt availability
    → PolicyToolNode execution recheck
```

## Security invariants

- 模型偽造不在 effective set 的 tool call 時，execution layer 仍必須拒絕。
- Skill-scoped tool 不會因它存在於 universe 就自動向 normal mode 開放。
- Graph binding、prompt availability、Fusion proposer intersection 與 runtime enforcement 共用同一個 `ToolAccessResolution`。
- Tool implementation 不決定 session/skill access policy。
- Citation workflow 的 business rules 屬於 citation subsystem，這裡只控制它是否可呼叫。
- `tools/__init__.py` 保持輕量，不 eager import access/policy graph。

完整 tool 清單與 MCP/skill 使用方式以根目錄 README 為準。

## Related docs

- [Agent architecture](../README.md)
- [Workspace tools、MCP 與 Skills](../../../README.md)
- [Skill tool-access contract](../../SKILLS_GUIDE.md)
