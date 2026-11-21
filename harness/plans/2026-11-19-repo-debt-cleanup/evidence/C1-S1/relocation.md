# C1-S1 唯讀核對與定位紀錄

- **日期**：2026-11-21
- **分支**：`GUI`（`git rev-parse --abbrev-ref HEAD` → `GUI`）
- **起點 HEAD**：`651cdd3`（`docs(plan): clarify mixed citation writes and avoid forced refactors [CA6]`）

## `git log --oneline 3b6cfd8..HEAD`

```text
651cdd3 docs(plan): clarify mixed citation writes and avoid forced refactors [CA6]
08e2ff9 docs(plan): rewrite repo debt plan around the product boundary [CA5]
c8715dd docs(note): record citation save success semantics [CA5]
3f87f09 docs(claude): record single active research workflow boundary
90d8d58 docs(agents): prohibit unnecessary multi-workflow concurrency design
19a661d docs(scope): document sequential desktop workflow in README
b99dbe3 docs(plan): accept P11 and apply third Codex review [CA4]
fbf1e5f docs(plan): apply second Codex review to repo debt plan [CA3]
052649a docs(plan): apply Codex review to repo debt plan [CA2]
e3f65a3 docs(plan): revise repo debt plan after independent review [CA1]
8f4ca06 docs(plan): add repo debt cleanup plan [CA0]
64225d1 docs(note): record citation storage unification decision [CA0]
```

全部皆為本計劃的 `[CA0]`–`[CA6]` 規劃／決策紀錄 commit 與使用者的三筆文件 commit（`19a661d`、`90d8d58`、`3f87f09`），尚未有任何 `[C1-*]`–`[C10-*]` 實作 commit。

## `git diff --stat 3b6cfd8..HEAD -- app`

輸出為空（0 個檔案變更）。`app/` 相對稽核基準 `3b6cfd8` 沒有任何程式碼異動，S001–S134 不需額外重新定位；後續步驟仍依規則以符號與 grep 確認實際位置。

## `git status --short`

```text
 M for_agents/README.md
 M for_agents/architecture-map.md
 M for_agents/dangerous-assumptions.md
 M for_agents/data-flow.md
 M for_agents/future-work-backlog.md
 M for_agents/invariants.md
 M for_agents/known-failure-modes.md
 M for_agents/module-responsibilities.md
 M for_agents/testing-strategy.md
?? NOTES-grill-skill-and-document-context.md
?? app/desktop/watch.out
?? note/20261106/
```

與 PLANS「基線 → 工作樹」一致：`for_agents/` 9 個使用者未提交修改，以及 `NOTES-grill-skill-and-document-context.md`、`app/desktop/watch.out`、`note/20261106/` 三項未追蹤路徑（目前非 Claude 沙箱掛載環境，因此無 `/dev/null` 字元裝置點檔，不影響任何檢查或實作）。除 C2-S9 預定清理的項目外，其餘既有修改與未追蹤檔案一律保留不動。
