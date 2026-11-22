# C5-S4 模型看到的文字（決策紀錄 §4.5）

- **日期**：2026-11-22
- **模型指令已改變（實驗條件）**：`skills/citation/SKILL.md` 是 citation skill 的模型指令。本步改寫其中描述 bundle、BibTeX 與存檔狀態的句子；`tool.py` 的工具描述、`explain` 與存檔說明文字已在 C5-S3 改寫。

## 改寫內容

`SKILL.md`：description 改為「verified saving to the project bibliography」；第 11 行、第 68 行、第 98 行刪除「BibTeX」；「A later task must save or reuse a bundle…」改為「後續 task 必須再次存檔才能取得自己的 receipt」並刪除「Cleanup keeps saved bundles」；「Project bibliography」一節改寫為新狀態：`saved`／`reused` 在書目庫中、回報 key、可引用；`storage_failed` 表示沒有存檔、不可引用，應告知使用者並可重試；沒有書目庫（CLI）時成功狀態是 `verified`，只在本次對話可引用、沒有寫到磁碟，不可說成已存檔；結尾 bundle 寫入的一段改為書目庫寫入的 fingerprint 與原子替換，以及穩定的 `src-*`。

`README.md`：save 流程圖改為「桌面合併進書目庫（每批一次寫入）；CLI 不寫入」；desktop 流程中的連結欄位與狀態；模組表刪除 `bibtex_canonical.py` 與 `storage.py`（Persistence 列改為 Session sources）；State boundaries 中 bundle 的兩句改為新的持久化與失敗語意（含 U20）。

## 檢查

- `grep -rn "bundle\|bibtex_canonical\|reference.bib\|cite/" app/skills/citation --include=*.md`：只剩 `README.md:55` 的「bundled CSL styles」，指的是隨套件附帶的 CSL 樣式檔，與 citation bundle 無關，保留（「### Bundled styles」標題同理）。
- `git diff --stat app/skills/citation`：`README.md` 18 行、`SKILL.md` 33 行，只改了 bundle、BibTeX 與存檔狀態相關的句子（diff 附在下方）。
- `pytest tests/test_skills.py tests/test_skill_runtime.py tests/test_citation_skill_activation.py tests/test_citation_slash_command.py tests/test_skill_adherence.py tests/test_graph_skill_loader.py`：125 passed。沒有測試釘住被改寫的句子（grep 確認）。

## diff

```diff
diff --git a/app/skills/citation/README.md b/app/skills/citation/README.md
index d836a58..90e9fc1 100644
--- a/app/skills/citation/README.md
+++ b/app/skills/citation/README.md
@@ -19,21 +19,21 @@ search intent

 save intent
     → authority verification
-    → canonical identity + BibTeX
-    → atomic bundle storage
-    → session source registry + trusted receipt
+    → canonical identity
+    → desktop: merge into the project bibliography (one write per batch); CLI: nothing written
+    → session source registry + trusted receipt (desktop: only for works in the bibliography)
     → [[cite:source-id]] gate and bibliography render
 ```

 Search 與 save 是不同階段；discovery result 不會因被找到就自動成為可引用的 saved source。

-Desktop projects add a second output for the same save:
+In a desktop project the bibliography is the only store for a save:

 ```text
 verified save (doi.org CSL-JSON, or the authority record from the arXiv API or the official NeurIPS proceedings site)
     → csl.sanitize_csl (CSL 1.0.2 whitelist, no abstract, fixed type map)
     → library.merge into the project's references.json (reuse by DOI, arXiv ID or NeurIPS proceedings paper hash, append otherwise)
-    → item.bibliography {status, path, key, reason_code} in the save result
+    → item status saved / reused (with bibliography {status, path, key}) or storage_failed (reason = library error code)

 document text ([@key] / \cite{key})
     → citekeys.find_citations (UTF-16 positions, Pandoc-compatible)
@@ -47,8 +47,8 @@ document text ([@key] / \cite{key})
 |---|---|---|
 | Entry/orchestration | `tool.py`, `service.py`, `hub.py` | Workflow tool、service operations 與 process-wide provider hub |
 | Discovery | `resolution.py`, `providers/` | Provider query plans、normalization、ranking 與 fallback |
-| Identity | `authority.py`, `doi.py`, `normalize.py`, `bibtex_canonical.py`, `types.py` | Canonical identity、verified metadata 與 artifacts |
-| Persistence | `storage.py`, `registry.py` | Atomic bundles、session source refs 與 trusted receipts |
+| Identity | `authority.py`, `doi.py`, `normalize.py`, `types.py` | Canonical identity、verified metadata 與 artifacts |
+| Session sources | `registry.py` | Session source refs 與 trusted receipts |
 | Output safety | `gate.py`, `render.py` | Marker validation、safe blocking 與 bibliography rendering |
 | Project bibliography | `csl.py`, `library.py` | Sanitized CSL-JSON；`references.json` load/layout detection/keys/merge/remove/fingerprint-checked atomic write |
 | Document citations | `citekeys.py`, `integrity.py` | Markdown (Pandoc) and LaTeX `\cite` key parsing; integrity report for one document |
@@ -62,11 +62,11 @@ document text ([@key] / \cite{key})

 - Provider hub 可在 process 內共用，discovery call 不擁有 session state。
 - `CitationService` 與 source registry 是 session-scoped，由 `CitationSessionPolicy` 唯一擁有。
-- Saved citation bundle 是 disk-persistent local artifact，不因 skill deactivation 被刪除。
+- 唯一的持久化是桌面專案的書目庫；CLI 的存檔不寫任何檔案，`verified` 的來源只在當次 task 可引用。
 - `[[cite:...]]` 與 `[[citation-needed]]` 的特殊語意只在 citation skill active 時開放。
 - Extended thinking 不與 citation skill 同時啟用，避免平行 candidate 共享 registry。
 - The project bibliography file belongs to the user: existing entries, keys and JSON layout are never changed; a file whose layout cannot be reproduced is read but never rewritten; every write re-checks the file fingerprint first.
-- Bibliography failures never change a bundle's saved/reused outcome.
+- A bibliography failure is the item's `storage_failed` status: nothing was saved and the work is not citable. A work already in the bibliography before the batch stays `reused` even when a new work in the same batch fails to write.

 ## Correctness invariants

diff --git a/app/skills/citation/SKILL.md b/app/skills/citation/SKILL.md
index dc6bda8..f52cc49 100644
--- a/app/skills/citation/SKILL.md
+++ b/app/skills/citation/SKILL.md
@@ -1,6 +1,6 @@
 ---
 name: citation
-description: Conversational citation selection, verified bundle saving, and [[cite:...]] rendering.
+description: Conversational citation selection, verified saving to the project bibliography, and [[cite:...]] rendering.
 ---

 # Citation Skill
@@ -8,7 +8,7 @@ description: Conversational citation selection, verified bundle saving, and [[ci
 Use `citation_workflow` to discover and save persistent citation identities.
 Its actions are `search`, `save`, `sources`, `source`, and `explain`. You own
 the conversational decision about which work/version the user requested and
-whether they authorized a write; the tool owns metadata retrieval, BibTeX,
+whether they authorized a write; the tool owns metadata retrieval,
 storage, and the factual save outcome.

 For paper discovery and citation work, use only citation_workflow and its existing Crossref, DataCite, and optional OpenAlex providers, preserving the workflow's existing authoritative identifier resolution and save behavior. Do not use Web Search or browse other websites to find papers, fill missing metadata or abstracts, or repair failed, incomplete, or ambiguous provider results. When the workflow cannot provide a reliable result, honestly report the returned failure, uncertainty, or missing information and present any usable results with their limitations; follow the existing bounded retry rules instead of searching the web. This instruction applies even when Web Search tools remain available.
@@ -64,8 +64,8 @@ task; visible prior conversation still supplies metadata and authorization.
   unaddressed confounders.
 - This workflow stops at abstracts. Do not download/read full text or start
   a separate evidence-verification pipeline. Abstracts exist only in this
-  turn's discovery results; saving still verifies bibliographic identity
-  and BibTeX, without upgrading the result to claim verification.
+  turn's discovery results; saving still verifies bibliographic identity,
+  without upgrading the result to claim verification.
 - If some providers fail, present the remaining results and the incomplete
   search scope. A provider failure or missing abstract is not a zero-hit
   result and is not evidence that relevant literature does not exist.
@@ -95,7 +95,7 @@ task; visible prior conversation still supplies metadata and authorization.
 - DOI first. When the selected record, or the conversation, shows a DOI or
   arXiv identifier, the WorkIntent is `requested_label` plus that one
   identifier in `identifiers`, and nothing else. Copy it from the record the
-  user chose. The workflow fetches authoritative doi.org metadata and BibTeX
+  user chose. The workflow fetches authoritative doi.org metadata
   for it without searching again, so re-typing title, authors, year, venue,
   or type adds nothing but chances for error.
 - Each version (preprint, published article, repository copy) has its own
@@ -142,19 +142,24 @@ task; visible prior conversation still supplies metadata and authorization.
   bibliography are allowed, but do not present invented bibliographic facts.
 - `sources` lists this task's sources and `source` accepts only a stable
   `source_id`. `explain` gives the public verification/storage contract.
-- A later task must save or reuse a bundle through the tool to obtain a
-  receipt trusted by its own registry. Historical markers or receipts alone
-  do not make a source citable in the new task. Cleanup keeps saved bundles.
+- A later task must save the work through the tool again to obtain a receipt
+  trusted by its own registry. Historical markers or receipts alone do not
+  make a source citable in the new task.
 - Each save's tool content contains the actual per-item status and any receipt.
   Base your response on that result and preserve ambiguity/failure honestly;
   no finalizer will replace your prose with a deterministic save summary.

 ## Project bibliography (desktop projects)

-- In a desktop research project, every saved or reused work is also merged
-  into the project's CSL-JSON bibliography, and the save result reports its
-  `key` (`bibliography.status` is `added`, `existing`, or `failed` with a
-  reason; a bibliography failure never changes the bundle outcome).
+- In a desktop research project, a save merges the verified work into the
+  project's CSL-JSON bibliography, the only citation store. `saved` (newly
+  added) and `reused` (already there) works are in the bibliography, report
+  their `key`, and are citable. `storage_failed` means the bibliography could
+  not be updated: nothing was saved and the work is not citable; tell the user
+  and offer to retry the save.
+- Without a project bibliography (the CLI), a successful save is `verified`:
+  citable in this conversation only and not written to disk. Do not describe
+  it as saved.
 - Text written into a project document cites by key only: `[@key]` or
   `[@a; @b]` in Markdown, `\cite{key}` in LaTeX. Do not type author-year or
   numbered references into the document yourself and never invent a key;
@@ -165,5 +170,5 @@ task; visible prior conversation still supplies metadata and authorization.
   bibliography does not contain; save the work first, or say which claims
   still lack a source.

-Bundles are staged, fsynced, and atomically renamed. DOI identities keep their
-stable `src-*`; schema-v1 bundles are validated and reused without rewriting.
+Bibliography writes re-check the file fingerprint and replace the file
+atomically. Each canonical identity keeps a stable `src-*` source ID.
```
