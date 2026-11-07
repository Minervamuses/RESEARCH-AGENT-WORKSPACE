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

Desktop projects add a second output for the same save:

```text
verified save (doi.org CSL-JSON, or the authority record from the arXiv API or the official NeurIPS proceedings site)
    → csl.sanitize_csl (CSL 1.0.2 whitelist, no abstract, fixed type map)
    → library.merge into the project's references.json (reuse by DOI, arXiv ID or NeurIPS proceedings paper hash, append otherwise)
    → item.bibliography {status, path, key, reason_code} in the save result

document text ([@key] / \cite{key})
    → citekeys.find_citations (UTF-16 positions, Pandoc-compatible)
    → integrity.inspect (missing / uncited / duplicate DOIs / verified-by-bundle via DOI, arXiv ID or NeurIPS URL)
    → csl_render.render | export_docx | export_markdown (Pandoc citeproc)
```

## Module groups

| Group | Modules | Responsibility |
|---|---|---|
| Entry/orchestration | `tool.py`, `service.py`, `hub.py` | Workflow tool、service operations 與 process-wide provider hub |
| Discovery | `resolution.py`, `providers/` | Provider query plans、normalization、ranking 與 fallback |
| Identity | `authority.py`, `doi.py`, `normalize.py`, `bibtex_canonical.py`, `types.py` | Canonical identity、verified metadata 與 artifacts |
| Persistence | `storage.py`, `registry.py` | Atomic bundles、session source refs 與 trusted receipts |
| Output safety | `gate.py`, `render.py` | Marker validation、safe blocking 與 bibliography rendering |
| Project bibliography | `csl.py`, `library.py` | Sanitized CSL-JSON；`references.json` load/layout detection/keys/merge/remove/fingerprint-checked atomic write |
| Document citations | `citekeys.py`, `integrity.py` | Markdown (Pandoc) and LaTeX `\cite` key parsing; integrity report for one document |
| Styles and export | `csl_render.py`, `styles/` | Pandoc rendering (preview = export), `.docx`/Markdown export, bundled CSL styles. The desktop's BIME Appendix 17 Word export does not use it: it runs the vendored bime_word (`agent/desktop/bime_export.py`) |

### Bundled styles

`styles/styles.json` lists the styles the desktop offers. `apa.csl`, `modern-language-association.csl`, `ieee.csl` and `chicago-author-date.csl` are copied unchanged from [citation-style-language/styles](https://github.com/citation-style-language/styles) at commit `205bf7b617f9f8d48e4e0c2998b855eeae18fd65` (downloaded 2026-11-05) and keep their CC BY-SA 3.0 `<rights>` and author headers. `bime-appendix17.csl` is written for 國立臺灣大學生物機電工程學系 Appendix 17 二.8 (CC BY-SA 3.0, structure modelled on Chicago author-date); its measured differences from bime_word and the rules standard CSL cannot express are recorded in the citation plan evidence, which was removed from the tree on 2026-11-07; read it with `git show 05df764:harness/plans/2026-11-05-citation-management/evidence/C5-S2/compare.md`. Pandoc is the only rendering engine; it must be installed in the `app` Conda environment.

## State boundaries

- Provider hub 可在 process 內共用，discovery call 不擁有 session state。
- `CitationService` 與 source registry 是 session-scoped，由 `CitationSessionPolicy` 唯一擁有。
- Saved citation bundle 是 disk-persistent local artifact，不因 skill deactivation 被刪除。
- `[[cite:...]]` 與 `[[citation-needed]]` 的特殊語意只在 citation skill active 時開放。
- Extended thinking 不與 citation skill 同時啟用，避免平行 candidate 共享 registry。
- The project bibliography file belongs to the user: existing entries, keys and JSON layout are never changed; a file whose layout cannot be reproduced is read but never rewritten; every write re-checks the file fingerprint first.
- Bibliography failures never change a bundle's saved/reused outcome.

## Correctness invariants

- DOI identity winner 必須經 authority source 重新驗證，不把 discovery snippet 當成權威 metadata。
- Identity-critical conflict 不得產生成功寫入。
- Tool content、artifact、receipt 與 registry 必須反映同一個逐項真實結果。
- Citation gate 必須在 answer 寫入 canonical conversation terminal state 前執行。
- `CitationSessionPolicy` 先以 trusted registry 執行 gate；renderer 只使用呼叫者提供的 resolver 產生輸出，不是獨立 trust boundary。
- 使用者/模型授權規則以 `SKILL.md` 為準，README 不擴大操作範圍。
- 正文只存 key；預覽、格式切換與匯出都不修改原始文件。

## Related docs

- [Workspace README](../../../README.md)
- [Skill execution instructions](SKILL.md)
- [Required tool declaration](manifest.yaml)
- [Agent citation session policy](../../agent/skills/citation/session_policy.py)
