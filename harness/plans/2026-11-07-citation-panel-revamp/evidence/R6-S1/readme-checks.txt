$ grep -rn -i "insert\|bibtex\|\.bib\b\|export" README.md app/README.md app/skills/citation/README.md
README.md:50:export OPENROUTER_API_KEY='你的金鑰'
README.md:108:- **引用面板**：開啟文件後，編輯器下方的 **Citations** 面板預設收合成一列摘要：引用數與問題數（例如 `3 cited · 1 problem`）、**Style**、**Preview**（只限 Markdo
README.md:109:- **格式與匯出**：**Style** 選單的選擇存在 `RESEARCH.md` 的 `citationStyle`。內建 APA 7、MLA 9、IEEE、Chicago author-date，以及依附件十七撰寫的 `bime-appendix17`。**Preview**
README.md:115:- **附件十七的細節**：渲染前會在書目的暫存副本套用與 bime_word 相同的規則：直撇號 `'` 不會被換成 `’`；`Wen-tau` 這類名字縮寫成 `W.-t.`；去掉名字中的 `(�
README.md:145:| 引用匯出 | 文件旁的 `<檔名>.<樣式>.docx`、`<檔名>.<樣式>.md`，以及系上格式的 `<檔名>.bime.docx` 與報告 `<檔名>.bime.audit.json`、`<檔名>.bime.audit.md`、`<檔名>.bime.
app/skills/citation/README.md:22:    → canonical identity + BibTeX
app/skills/citation/README.md:41:    → csl_render.render | export_docx | export_markdown (Pandoc citeproc)
app/skills/citation/README.md:50:| Identity | `authority.py`, `doi.py`, `normalize.py`, `bibtex_canonical.py`, `types.py` | Canonical identity、verified metadata 與 artifacts |
app/skills/citation/README.md:55:| Styles and export | `csl_render.py`, `styles/` | Pandoc rendering (preview = export), `.docx`/Markdown export, bundled CSL styles. The desktop's BIME Appendix 17 Word export does not us

$ relative link check (README.md, app/README.md, app/skills/citation/README.md)
ok      README.md -> app/vendor/web-search-mcp/README.md
ok      README.md -> app/vendor/bime-word/README.md
ok      README.md -> app/agent/config.py
ok      README.md -> app/rag/README.md
ok      README.md -> app/README.md
ok      README.md -> app/rag/docs/API.md
ok      app/README.md -> ../README.md
ok      app/README.md -> ../README.md
ok      app/README.md -> agent/README.md
ok      app/README.md -> agent/turns/README.md
ok      app/README.md -> agent/thinking/README.md
ok      app/README.md -> agent/tools/README.md
ok      app/README.md -> skills/citation/README.md
ok      app/README.md -> rag/README.md
ok      app/README.md -> rag/docs/API.md
ok      app/skills/citation/README.md -> SKILL.md
ok      app/skills/citation/README.md -> ../../../README.md
ok      app/skills/citation/README.md -> SKILL.md
ok      app/skills/citation/README.md -> manifest.yaml
ok      app/skills/citation/README.md -> ../../agent/skills/citation/session_policy.py
checked 20 missing 0

$ git diff --check
exit=0
