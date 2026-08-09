# Drop-in extension management

`extensions` 管理本機 drop-in Skills 與 MCP descriptors 的 discovery、validation、approval、managed copy、registry 與下次 session startup loading。

## Vocabulary

- **Source drop-in**：使用者放入 drop-in root 的原始 bundle。
- **Scanned desired state**：discovery 檢查後的輸入快照。
- **Applied registry**：已確認版本、hash、execution approval 的權威紀錄。
- **Managed copy**：apply 後存在 agent state root 的 immutable copy。
- **Loaded runtime**：新 session startup 時再度驗證後實際載入的 Skills/MCP specs。

## Lifecycle

```text
scan + validate
    → diff against registry
    → isolated management plan
    → explicit user confirmation
    → apply managed copy + registry revision
    → next session startup revalidates and loads
```

Apply 不熱更新目前 session。Status 顯示的 running revision 與 on-disk revision 可能在重啟前不同。

## Module map

| Module | Responsibility |
|---|---|
| `paths.py` | Source/state roots 與路徑邊界 |
| `models.py` | Scanned/applied extension models |
| `discovery.py` | Bundle scan、validation、hashing 與 diff |
| `mcp_manifest.py` | MCP descriptor validation、environment binding 與 launch candidate |
| `registry.py` | Registry read/write 與 revision persistence |
| `manager.py` | Plan、confirmation、apply 與 status workflow |
| `startup.py` | 驗證 applied entries，轉成 `ExtensionStartup` |

`agent.startup` 是更上層的 session bootstrap coordinator；本 package 的 `startup.py` 只處理 extension state。

## Trust and mutation boundaries

- Source bundle 是不可信資料，必須 scan/validate，不因它在本機就直接執行。
- Management 流程不 install、build 或 download bundle dependencies。
- Apply 寫 managed copy 與 registry，不修改原始 drop-in。
- MCP execution 必須綁定已核准 descriptor/hash；secret 只以 environment variable 名稱參照。
- Startup 失敗的單一 extension 只產生 diagnostic，不放寬驗證或覆寫 built-in Skill。
- Registry/managed-copy mutations 依 `manager.py` 的 process-local lock 與 apply ordering 執行；目前不提供跨 process serialization。

## Related docs

- [Agent architecture](../README.md)
- [Workspace Extension Management](../../../README.md)
- [Skill bundle schema](../../SKILLS_GUIDE.md)
- [Isolated extension-management skill](../../tool/_internal/extension-management/SKILL.md)
- [Local tool v1 limitations](../../tool/local/README.md)
