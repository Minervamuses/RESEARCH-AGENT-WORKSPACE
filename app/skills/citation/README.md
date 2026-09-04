# Citation subsystem

`skills/citation` 是 built-in citation engine，負責 discovery、identity verification、save、session registry、marker gate 與 bibliography rendering。

## Two audiences

- [`SKILL.md`](SKILL.md) 是給模型的 workflow 指令與授權邊界。
- 本 README 是給開發者的 architecture map，不重新定義模型應如何執行 citation 任務。

`agent/skills/citation/session_policy.py` 是 agent integration layer；這個 package 是 citation domain engine，兩者不可混為同一狀態 owner。

## End-to-end flow

```text
search intent
    → provider discovery
    → resolution / ranking / identity checks
    → candidate results for model selection

save intent
    → authority verification
    → canonical identity + BibTeX
    → atomic bundle storage
    → session source registry + trusted receipt
    → [[cite:source-id]] gate and bibliography render
```

Search 與 save 是不同階段；discovery result 不會因被找到就自動成為可引用的 saved source。

## Module groups

| Group | Modules | Responsibility |
|---|---|---|
| Entry/orchestration | `tool.py`, `service.py`, `hub.py` | Workflow tool、service operations 與 process-wide provider hub |
| Discovery | `resolution.py`, `providers/` | Provider query plans、normalization、ranking 與 fallback |
| Identity | `authority.py`, `doi.py`, `normalize.py`, `bibtex_canonical.py`, `types.py` | Canonical identity、verified metadata 與 artifacts |
| Persistence | `storage.py`, `registry.py` | Atomic bundles、session source refs 與 trusted receipts |
| Output safety | `gate.py`, `render.py` | Marker validation、safe blocking 與 bibliography rendering |

## State boundaries

- Provider hub 可在 process 內共用，discovery call 不擁有 session state。
- `CitationService` 與 source registry 是 session-scoped，由 `CitationSessionPolicy` 唯一擁有。
- Saved citation bundle 是 disk-persistent local artifact，不因 skill deactivation 被刪除。
- `[[cite:...]]` 與 `[[citation-needed]]` 的特殊語意只在 citation skill active 時開放。
- Extended thinking 不與 citation skill 同時啟用，避免平行 candidate 共享 registry。

## Correctness invariants

- DOI identity winner 必須經 authority source 重新驗證，不把 discovery snippet 當成權威 metadata。
- Identity-critical conflict 不得產生成功寫入。
- Tool content、artifact、receipt 與 registry 必須反映同一個逐項真實結果。
- Citation gate 必須在 answer 寫入 canonical conversation terminal state 前執行。
- `CitationSessionPolicy` 先以 trusted registry 執行 gate；renderer 只使用呼叫者提供的 resolver 產生輸出，不是獨立 trust boundary。
- 使用者/模型授權規則以 `SKILL.md` 為準，README 不擴大操作範圍。

## Related docs

- [Workspace Citation Skill guide](../../../README.md)
- [Skill execution instructions](SKILL.md)
- [Required tool declaration](manifest.yaml)
- [Skills 規範與建立指南](../../SKILLS_GUIDE.md)
- [Agent citation session policy](../../agent/skills/citation/session_policy.py)
