# Citation WorkIntent 解析與保存流程落地計畫

日期:2026-07-13

狀態:待審核；尚未修改 production code

依據:`note/20260713/citation_resolution_research.md`、`prob.md`、`RETROSPECTIVE.md`、`CITATION_UPGRADE_PLAN.md`、`deep-research-report.md`

基準 commit:`27b008f`（研究紀錄）

## 決策摘要

本計畫把 citation workflow 的 mutation boundary 從：

```text
session candidate pool -> cX -> mX -> confirm
```

改為：

```text
self-contained WorkIntent
  -> fresh bounded multi-provider resolution
  -> blocking work/version validation
  -> DOI 或 authoritative no-DOI serialization
  -> atomic persistence + stable SourceRef
```

終態仍保留一個 skill-scoped model tool 名稱 `citation_workflow`，避免改動 manifest 與 tool-access isolation；但 action surface 縮成：

```text
search(query + filters)
save(works=[WorkIntent, ...])
sources(page)
source(source_id)
explain()
```

核心變更：

- `search` 每次都是 stateless 新查詢，不建立 active pool，不 mint `cX/mX`。
- 搜尋結果用完整 title/authors/year/venue/type 呈現；可有畫面順序，但沒有可傳回 save API 的 position ID。
- `save` 接受最多 10 個自足的 WorkIntent；每個 intent 都 fresh resolve，不引用先前搜尋狀態。
- 一個 user turn 最多一次有效 `save` mutation batch；whole batch通過 strict shape/normalization、取得 busy lock並 atomic claim後，會在 domain preflight/resolver之前消耗本輪寫入機會，之後不論資訊不足、成功、歧義、找不到或 provider/storage failure都不退回。
- 唯一強匹配才寫入；多版本回人類可讀差異，下一輪由使用者自然語言補條件後 fresh resolve；不保存 `mX`。
- 既有 DOI verification、atomic storage、SourceRef、gate、renderer 與 deterministic finalizer 保留。
- 現有 v1 bundle 不搬移、不重寫；新 schema 必須能驗證並重用它們。

## 目標與非目標

### 目標

1. 從結構上消除 old-`c1` → new-`c1` silent alias。
2. 阻止模型在一次 save 結果後靜默重搜、改條件、再寫第二次。
3. 把「是不是使用者要的作品與版本」變成寫入前的 blocking check。
4. 補足 DataCite discovery，使 Crossref 查不到的 DataCite/arXiv DOI 可被解析。
5. 保存後繼續使用穩定 `src-*`、可信收據、citation gate 與 bibliography renderer。
6. 泛化 storage/receipt，使未來能保存沒有 DOI、但有權威書目來源的作品。
7. 用代表性 corpus 量測 precision/coverage，而不是為 AIAYN/VAE 寫特例。
8. 讓每一階段可獨立測試、可停止、可回退，不做 big-bang rewrite。

### 非目標

- 不追求 metadata matching 100% 自動成功；不確定時允許 clarification/abstention。
- 不建立跨回合 candidate snapshot、generation-aware `w4c1` 或 shadow pool。
- 不因移除 pool 就改寫 `TurnRecord` 去持久化 ToolMessage。
- 不在第一版做任意 publisher HTML scraper；先用明確可信、可測的 adapters。
- 不自動刪除或修改這次事故產生的兩個 bundle。
- 不在本次重構順手開放 citation extended thinking。
- 不全域改名或刪除 `candidate_id`；`app/agent/fusion.py` 與 `app/agent/thinking/*` 的 candidate 是另一個 domain。
- 不把 discovery ranking score 當作 mutation authorization 或 identity proof。

## 不可破壞的不變條件

以下是終態 invariants。Commit 1–5 的新路徑尚未 model-visible，因此必須維持 side-effect free，不能讓半成品繞過 legacy path；Commit 6 一旦切換後，以下條件全部成為 release blockers。原本已成立的 atomicity、可信收據、gate 與 isolation，則從第一個 commit 起就不得退化。

1. **零假成功**：沒有成功 artifact + live registry match，就不能渲染保存成功。
2. **零半套 bundle**：繼續使用 staging + fsync + atomic rename；失敗不可留下可見半成品。
3. **零覆寫衝突**：既有 bundle schema/identity/hash 不一致時 fail closed。
4. **零低信心寫入**：missing/ambiguous/contradictory identity 一律不寫。
5. **一輪一次 mutation**：whole-batch schema/normalization 失敗可修正；一旦合法 domain batch取得 busy lock並 atomic claim（早於 domain preflight/resolver），本輪不得再進第二個 save batch。
6. **批次逐項誠實**：partial success、ambiguity、not-found、provider failure 都逐項進 trusted artifact；全數失敗也 deterministic render。
7. **identifier provenance**：使用者明示的 target identifier、visible-context hint、resolver-discovered identifier 不得混為一談。
8. **經 host 驗證的版本 constraint 是 veto**：使用者本輪明示且由 host 驗證的 year/venue/version/originality 矛盾不能被 relevance score 抵銷；模型從可見上下文帶入的 hint 不能冒充 hard constraint。
9. **既有 DOI identity 穩定**：同 DOI 的 `src-{doi_hash}` 與 bundle directory hash 不變。
10. **v1 只讀相容**：驗證/重用既有 v1 bundle，但不在背景中靜默升級或重寫。
11. **模型不寫 BibTeX**：DOI 走 content negotiation；no-DOI 走 deterministic exporter，再進 parser round-trip。
12. **citation isolation 不退化**：skill inactive 時工具仍不可呼叫；gate/renderer policy 不放寬。

## 現行依賴與影響面

| 元件 | 現況 | 落地影響 | 必須保留的行為 |
|---|---|---|---|
| `app/skills/citation/types.py` | `CitationCandidate`/`CitationMatch`/`ConfirmReceipt`/`PendingMatchNote` 以 c/m/DOI 為中心 | 新增 WorkIntent/ResolvedWork/ResolutionDecision/SaveBatch；切換後刪 legacy types | strict artifact decode、failure 不攜 arbitrary provider prose |
| `coordinator.py` | session pool、generation、view、matches、select/confirm、registry、writer 混在一類 | 拆出 pure resolver；service 只留 stateless search/save + registry | SourceRegistry、provider orchestration、atomic write |
| `ranking.py` | fusion 後 mint `c1...`、related group 也依 candidate ID | discovery record 不帶 workflow/candidate ID；版本群組只供呈現 | deterministic ranking、identity-only dedup、result cap |
| `tool.py` | 13 actions、generic identifier(s)、大量 c/m formatter | 縮成 5 actions；save 接 typed works；source 專用 source_id | busy lock、bounded batch、sanitized output |
| `hub.py` / providers | Crossref、optional OpenAlex、doi.org；無 DataCite | 加 DataCite；之後加 arXiv/venue adapters | process cache、rate limiter、retry、redaction |
| `storage.py` | DOI 是目錄、hash、validate、reuse 的唯一 identity | 泛化 canonical identity；v1/v2 compatibility | atomicity、collision lengthening、hash validation |
| `session.py` | receipt 驗 registry + pending live match；pending recovery | save outcome 只驗 stable source/identity；刪 pending path | finalization chokepoint、source hint、gate/render |
| `graph.py` | select→confirm continuation 與 pending artifact awareness | 刪 citation-specific continuation；加/接 one-shot mutation context | empty reply retry、protocol repair、tool budgets |
| `memory.py` | 只保存 user + final assistant text | 不改 schema；要求搜尋結果在 final answer 中帶足 metadata | recent-turn/historical behavior |
| `SKILL.md` | strict pool/cX/mX/save contract | 重寫成 metadata→WorkIntent→one-shot save | grounding、negative intent、no invention |
| README/guide/SKILLS_GUIDE/gate 文案 | 描述 search→select→confirm、DOI-only storage | 功能切換後同步 | 歷史文件保持歷史，不竄改事故 |
| tests | 多數 citation workflow tests 斷言 generation/cX/mX/pending | 分階段換成 resolver/save contract | provider/net/bibtex/gate/storage 回歸 |

### 特別避雷：其他 domain 的 `candidate_id`

以下不是 citation search candidate，必須原封不動：

- `app/agent/session.py` 的 fusion trace `candidate_id`。
- `app/agent/fusion.py` 的 proposer candidate。
- `app/agent/thinking/*` 的 selected/dropped candidate IDs。
- 對應 `test_thinking*.py`、plan log 與 observability assertions。

刪除時只允許 path-scoped search：`app/skills/citation/`、`app/agent/session.py` 的 citation finalizer 區段、`app/agent/graph.py` 的 select/confirm recovery 區段，以及明確 citation tests。禁止全 repo mechanical replace。

## 目標資料契約

### WorkIntent

Pydantic tool input 與內部 frozen dataclass 分離：tool input 負責 shape/limit，domain type 負責 normalization/invariants。

建議欄位：

```json
{
  "requested_label": "transformer 那篇",
  "title": "Attention Is All You Need",
  "authors": ["Ashish Vaswani"],
  "year": 2017,
  "venue": "NeurIPS",
  "work_type": "conference paper",
  "identifiers": [
    {
      "kind": "doi|arxiv",
      "value": "...",
      "provenance": "explicit_current_user|visible_context"
    }
  ],
  "constraints": [
    {
      "field": "year|venue|work_kind|version_kind",
      "value": "2017|NeurIPS|original_research|published",
      "provenance": "explicit_current_user|visible_context",
      "requested_strength": "hard|preference"
    }
  ]
}
```

規則：

- `requested_label` 是短標籤，不保存完整 raw user utterance。
- title/authors/year/venue/work_type 是 resolution hints，不因出現在 payload 就自動成為 veto；除 `requested_label` 外欄位都可缺，但 evaluator 可回 `insufficient_intent`，不代表 partial payload 必須被猜完。
- Commit 6 core只接受 DOI/arXiv ID，且一律 normalize 後再用；URL/PMID只有在對應 authoritative adapter與 enum正式加入後才可出現在 tool input。
- Tool payload裡的 provenance/strength只是一個 claim。Host要獨立從 current user text建立帶 span/polarity的 `HostIntentClaim`，再決定 `effective_provenance/effective_strength`；模型既不能把 visible冒充 explicit/hard，也不能把使用者明示 DOI/constraint降成 visible/preference或省略掉。
- 對 single-work batch，可把唯一且無歧義的 current-user target ID/constraint確定性注入該 item；對 multi-work batch，只有 exact identifier/value與唯一 item對得上時才綁定。若 current-user hard claim被省略、交換到另一 item、可綁多項或無法綁定，整批回 `insufficient_intent` + reason `intent_binding_ambiguous`、zero write，不靜默忽略使用者硬意圖。
- Tool input只能提出 `requested_strength`；內部 frozen domain type另產生不可由模型設定的 `effective_strength`、`effective_provenance`與 `host_verified`。Host可依 current text升級、降級或注入 claim；只有正向、唯一綁定的 `host_verified_current_user + hard` 可成為 hard constraint，negative target則必須阻止對應 item保存。
- `visible_context` 的 title/author/year/venue可協助形成 query與 identity evidence，但不能單獨決定 published/preprint/original manifestation；若它是唯一版本區分依據，就依明文 default policy選擇或 abstain。
- 由 provider 找到的 identifier 不回填成「使用者提供」；它只存在 ResolutionEvidence。
- title-only 可進 resolver，但只有達 minimum evidence 且唯一強匹配時才可保存。
- 「original」拆成 work-level 與 version-level：original research 不等於一定要最早 preprint；只有 current user wording通過 host詞彙/值驗證後，「正式版」才成為 published constraint。語義仍不唯一時必須 abstain/clarify。
- Outer model與每個 nested model都用 strict types + `extra="forbid"`；`identifiers=["c1"]`、legacy `candidate_id/match_id` 或任何 unknown field必須整包 shape-invalid，不能被 Pydantic忽略後繼續保存。
- 初始 hard caps：works 1..10；requested label 160字元；title 512；authors最多32名、每名256；venue/work type各256；identifiers最多8個、每值2048；constraints最多8個、每值256；整包 canonical JSON最多64 KiB。normalize前後都測 boundary，control/NUL字元拒絕或清理規則要固定。

Identifier能力按 rollout分階段，不讓 schema承諾尚未實作的 verifier：

| identifier | Commit 6 | Commit 8／後續 |
|---|---|---|
| DOI | exact normalize + RA discovery/refetch，可保存 | 不變 |
| arXiv ID | exact DataCite DOI resolution；找不到 DOI 時回 `unsupported_no_doi` | official arXiv authoritative identity可保存 |
| authoritative URL | 不在 Commit 6 enum；不能 fetch | Commit 8僅加入 allowlisted typed adapter URL |
| PMID | 不在本計畫 core schema | 另立 NCBI/PubMed adapter、fixtures與 threat model後才加入 |

### DiscoveryRecord

`search` 回傳 method-local records，不帶 workflow/candidate/match ID：

```text
title, authors, year, venue, work_type, url(optional),
provider provenance, version label, ranking evidence
```

Formatter 用 Markdown bullets 呈現，不輸出 `cX`。畫面順序只是人類可見順序；若使用者下一輪說「第一篇」，模型從上一則 final answer 的完整 metadata 建 WorkIntent，tool 永遠收不到 ordinal。

### ResolvedWork 與 ResolutionEvidence

```text
ResolvedWork
  canonical_identity: {kind, value}
  doi: optional
  title/authors/year/venue/work_type/url
  version_kind: published/preprint/repository/repost/unknown
  relations: is_preprint_of/is_version_of/is_reprint_of/...
  field_provenance

ResolutionEvidence
  provider_record_ids
  queries（deterministic、redacted）
  field comparisons
  blocking reason codes
  score components（只供排序/診斷）
  version decision reason codes
```

不保存 raw API payload、HTML、LLM prose、API keys 或帶 secret query parameter 的 URL。

### SourceRef v2

現行 `SourceRef.doi` 已是 optional，但沒有 canonical identity。新 `SourceRef` 必須新增：

```text
canonical_identity: {kind, value}
```

相容規則：

- 新 DOI ref 同時帶 `canonical_identity=doi:<canonical>` 與 `doi=<canonical>`，兩者不一致即 invalid。
- 新 no-DOI ref 帶 non-DOI authoritative identity，`doi=None`。
- Schema v2把 `canonical_identity`設為 required；schema v1 constructors/decoder仍允許欄位 absent，但只可由已驗證 canonical DOI確定性派生 live identity，不能從 title或 bundle path猜。不能把 dataclass欄位直接改成無條件 required而一次弄壞所有 legacy constructors/tests。
- `SourceRegistry.register()` 若遇同 `source_id`、不同 canonical identity，必須 fail closed，不能沿用目前直接 overwrite；同 identity 才能 idempotent re-activate/update live bundle path。
- 新 service在 write前先以 registry檢查預計的 12-hex `source_id`，storage則在 source-ID-slot lock內做 identity-first scan；若同 ID已屬不同 identity，回 `identity_conflict/source_id_collision` 且零 write，明確選擇 fail closed而不是在本次重構發明可變長 cite-marker ID。Registry仍在 register時重驗，避免 TOCTOU/程式誤用。
- v1 bundle reuse 仍由 fresh resolver + verified existing BibTeX 建 live SourceRef，不新增把 sidecar任意反序列化成 SourceRef 的捷徑。

### ResolutionDecision 與 save lifecycle

Pure resolver與 storage lifecycle分成兩層，避免把 `storage_failed` 混進 identity evaluator。每個 intent 的 resolver decision只能是：

```text
eligible              -> exactly one record may continue to serialization/write
insufficient_intent   -> shape合法但沒有足夠可查/可比對 evidence；zero provider/write可成立
ambiguous             -> two or more materially plausible citable objects；zero write
not_found             -> no strong match；zero write
identity_conflict     -> identifier與 title/author/year/type/version有 blocking contradiction；zero write
unsupported           -> identifier/source/version能力尚未支援；zero write
provider_failed       -> bounded provider phase無法形成可驗證 record；zero write
verification_failed   -> refetch/normalized record無法通過 verifier；zero write
```

`eligible` 的必要條件：

- 沒有 blocking contradiction。
- 達到 minimum evidence policy。
- 若有第二名，第一名與第二名有足夠 margin，或 identifier exact match 已可靠消歧。
- version policy 能唯一決定 manifestation。

完成所有 items 的 resolve/verify後，才按 request order對 `eligible` items進 storage；因此晚一項 provider failure不會發生在早一項已寫入之後。Storage仍非跨 item transaction，後續 storage failure可形成明確 partial success，但 artifact必須逐項誠實記錄。

### SaveBatch artifact

不要在舊 `ConfirmBatchOutcome` 上繼續加 optional 欄位。新增獨立 kind，例如：

```json
{
  "kind": "citation_save_batch",
  "schema_version": 1,
  "batch_id": "...",
  "batch_status": "attempted|rejected",
  "batch_reason_code": "none|workflow_busy|mutation_already_attempted",
  "items": [
    {
      "request_index": 0,
      "requested_label": "transformer 那篇",
      "status": "saved|reused|insufficient_intent|ambiguous|not_found|identity_conflict|unsupported_identifier|unsupported_no_doi|provider_failed|verification_failed|storage_failed",
      "reason_code": "...",
      "receipt": {
        "source_id": "src-...",
        "canonical_identity": {"kind": "doi", "value": "..."},
        "doi": "... or null",
        "title": "...",
        "year": 2017,
        "work_type": "...",
        "bundle_path": "...",
        "verification_level": "doi_identity_verified",
        "cite_marker": "[[cite:src-...]]"
      },
      "alternatives": [
        {"title": "...", "authors": [], "year": 2017, "venue": "...", "version_kind": "published"}
      ]
    }
  ]
}
```

規則：

- strict exact-field decoding；unknown field/version 拒絕整包。
- `attempted` 必須至少一個 item，表示已取得 busy lock並成功 claim本輪 mutation。`rejected` 必須是空 items + `workflow_busy` 或 `mutation_already_attempted`，且不得觸發 resolver/provider/storage；前者保留現有 overlap fail-fast、後者表示 busy已釋放但本輪先前已有 attempted batch。
- alternatives 不帶 `mX`，不帶 raw DOI，不帶 provider arbitrary message。
- Artifact 的 shape/registry linkage 可被信任，不代表 requested_label/title/author/venue 是安全 prose；finalizer 必須做長度上限、control-character cleanup、Markdown escaping 與 DOI redaction，再渲染這些欄位。
- saved/reused receipt 必須和 live SourceRegistry 的 identity/path/verification level 完全一致，否則 finalizer 忽略並記 redacted warning。
- `items` 即使全數 not_found/ambiguous/failed 也觸發 deterministic finalizer。
- finalizer 依 request_index 保持使用者 batch 順序。
- `rejected` 只用於 batch-level MutationGuard，不能當 item resolution status；identifier/metadata矛盾固定映射 `identity_conflict`，不能偽裝成 `not_found`。
- 同一 turn 若同時收到一個 attempted artifact 與後續 rejected artifact，finalizer 先完整渲染 attempted items，再加一條固定「後續保存嘗試已拒絕」訊息；rejection 不得遮蔽第一個 batch 的成功／失敗。若驗到兩個 attempted batches，視為 invariant breach、fail closed 並記錄診斷。

## Resolver 設計

### 查詢策略

Save resolution 不使用 LLM QueryExpander，避免不可重現的 mutation decision。每個 WorkIntent 只產生有界 deterministic queries：

1. exact normalized identifier lookup（若有）。
2. exact title + first/strong author + year/venue constraints。
3. 最多一個放寬但仍保留 title/author 的 fallback query。

每 provider 每 intent 最多 1–2 queries、每 query 固定 rows cap；所有 provider 結果回來後統一判斷，不因 Crossref 有「任何結果」就提前停止。

### Provider 順序與責任

| Provider | Save resolution 用途 | 是否能單獨授權寫入 |
|---|---|---|
| doi.org | 已知 DOI 的 RA-independent CSL/BibTeX lookup | CSL 還須通過 intent/version validation |
| Crossref | Crossref deposited records 的 discovery | 否；需 blocking validation + doi.org refetch |
| DataCite | DataCite DOI metadata discovery | 否；需 blocking validation + doi.org refetch |
| OpenAlex | 可選 enrichment/discovery | 否；不可因 API key 缺失而整體失敗 |
| arXiv official API/record | arXiv ID、preprint metadata、version evidence | adapter policy 通過後可形成 authoritative identity；有 DOI 時仍優先 DOI path |
| curated proceedings adapter | 無 DOI 的官方 venue metadata | 只有 allowlisted/typed adapter 通過才可進 no-DOI path |
| generic web search | discovery/找官方 landing page | 永遠不能直接當保存 verifier |

新增 `providers/datacite.py` 時沿用 injected fetcher、TTL cache、rate limiter、retry 與 sanitized errors。**現有 hub 會先讀完整 `response.content`，不能宣稱已有 network payload cap**；Commit 2 要為 DataCite加入 bounded streaming transport（Content-Length先檢查但不信任，逐 chunk累計、超限立即 abort），或把能力誠實降級成 post-download parse cap。安全基線採前者，不把 DataCite 特例塞進 Crossref client，也不在同 commit冒險遷移所有既有 providers。

`ProviderRecord` 需補 resolver 所需的 publisher、relation/version hints、resource type、repository/landing URL；field provenance 不可丟。

### Blocking matching policy

先做 hard filters，再做 score；score 只能排序 eligible records。

建議 blocking checks：

- normalized title 低於最低相似度：reject。
- 使用者提供作者而 record 無任何可信 author overlap：reject。
- host-verified hard year/venue constraint 明顯矛盾：reject；online/print ±1 的容忍必須是明文政策與 reason code。未驗證/visible-context year或venue只能參與 evidence，不能單獨 veto。
- host-verified `original_research` 遇 review/introduction/monograph/repost/derivative type：reject；若它只是模型推論，最多當 preference。
- host-verified `published` constraint 遇只有 repository/preprint，但另有可靠 published relation：該 preprint 不可勝出。
- host-verified `preprint` constraint 遇 published-only result：不可靜默替代。
- identifier exact match 但 title/author/year 與 intent 衝突：reject，而不是「identifier 一定對」。
- DOI/CSL record 與 provider record 產生 identity-critical conflict：reject。

Non-blocking warnings 只限不影響作品身分的缺欄或 formatting 差異；title/author/year/type/version 不再只是 `_collect_warnings()`。

門檻與 margin 放在一個 versioned policy module，不散落 magic numbers。先用 frozen corpus 校準，再鎖 baseline；不得為 AIAYN/VAE title 寫專名 if/else。

### 版本政策

決策順序：

1. 經 host 驗證的使用者 target identifier與 hard constraint。
2. 經 host 驗證的 current-user preference。
3. visible-context/bibliographic hints只協助確認 work，不得單獨授權某個 manifestation。
4. generic「這篇論文」在可靠 relation 存在時依明文產品政策偏 published/VoR。
5. 無 published record 時接受官方 proceedings/repository/arXiv manifestation。
6. 同時剩兩個 materially plausible versions 時回 ambiguous。

「原始論文」至少包含兩個不同語義，resolver 不可混淆：

- original work：排除 review、tutorial、repost、衍生作品。
- earliest manifestation：在同 work 的版本中偏最早可引用版本。

模型若無法從上下文判斷使用者是哪一種，就讓 WorkIntent 保留 unspecified，resolver 回 ambiguity/insufficient_intent，而不是猜。

## Storage 與相容策略

### Canonical identity

新增 namespaced identity：

```text
doi:<canonical DOI>
arxiv:<normalized arXiv id>
url:<canonical authoritative landing URL>
venue:<adapter-name>:<adapter-stable-record-id>
```

但為了維持既有 DOI hash：

- DOI source ID/hash input 仍用 bare canonical DOI，`src-{doi_hash}` 不變。
- no-DOI 才用 namespaced identity key 算 source/directory hash。
- title hash 不可成為唯一 identity；沒有 authoritative identifier/URL 時 abstain。

### v2 sidecar

```json
{
  "schema_version": 2,
  "identity": {"kind": "doi", "value": "..."},
  "doi": "... or null",
  "source_ref": {},
  "creation_evidence": {
    "correlation_id": "...",
    "batch_id": "...",
    "request_index": 0,
    "normalized_hints": {},
    "verified_constraint_reason_codes": []
  },
  "resolution": {
    "record_source": "datacite",
    "provider_record_ids": [],
    "version_kind": "preprint",
    "decision_reason_codes": []
  },
  "provider_states": [],
  "verification": {},
  "artifact_hashes": {}
}
```

Sidecar 不存 absolute bundle path；其目錄本身就是位置。`creation_evidence` 只記首次建立時經 bounds/normalization/redaction的書目 hints與 verified constraint reason codes，不存 `requested_label`、raw user text、ordinal phrase或完整 provider payload。現行 v1 sidecar 在 `bundle_path` 回填前建立，因此 `source_ref.bundle_path` 本來可能是 null；v2 明確把這件事定義成 schema，而不是嘗試補寫絕對路徑。

Sidecar 是 **creation evidence**，不是每次 reuse的操作日誌。後續不同 batch重用同一 identity時只在該 turn的 trusted SaveBatch artifact/metrics留下結果，不回寫 bundle；bytes、mtime與原 creation evidence全部不變。

### 相容矩陣

| 既有/新資料 | validate | reuse | rewrite |
|---|---:|---:|---:|
| v1 DOI bundle，schema/DOI/BibTeX hash 正確 | 是 | 是；同目錄、同 source ID | 否 |
| v1 DOI bundle 損壞或 DOI 不符 | fail closed | 否 | 否 |
| v2 DOI bundle | 以 identity + DOI + hash 驗證 | 是 | 否 |
| v2 no-DOI bundle | 以 authoritative identity + hash 驗證 | 是 | 否 |
| 歷史 v1 的20/64-hex目錄 | 驗證其 DOI/source ID/path一致性 | 同 identity可重用 | 否 |
| 新寫入遇目錄/source-ID短 hash collision | `source_id_collision` fail closed | 否 | 不覆寫、不做20/64新 allocation |

Implementation 上先新增 generalized v2 API，保留 legacy `write_bundle(canonical_doi=...)` wrapper，直到舊 coordinator 移除。legacy wrapper 明確 stamp schema v1；v2 writer 明確 stamp schema v2，不能共用一個會在 commit 中途改值的 global current-version constant。兩個 writer從 Commit 4起都在 source-slot lock內對新 collision fail closed；12→20→64只保留作歷史目錄的 scanner/validator能力，不再配置新衝突目錄。不要在功能切換 commit 同時改掉所有 storage call sites。

Reuse 必須改成 **identity-first**，不能只以「本次 title 算出的完整目錄名」lookup。相同 DOI 的 metadata title 改變時，suffix hash 不變但 title stem 會變；writer 應先在 output directory 依 identity hash suffix 找既有 bundle、完整驗證後重用，再考慮建立新 title path。否則同 DOI 會悄悄出現第二份 bundle。

Identity-first scan與 rename之間還有 TOCTOU，單靠現有「相同 final path 的 rename race」不夠：兩個不同 title stem可各自 rename成功。因此 storage 必須提供 **per-output-directory + stable source-ID slot 的跨程序 exclusive lock**；同一 canonical identity一定落在同 slot，任何 12-hex truncated-hash collision也會被同一把鎖序列化。鎖內重新 scan → validate/reuse/collision-check → stage → rename，直到 directory fsync完成才釋放。Lockfile放在 reserved `.locks/`，名稱用 `sha256("citation-source-slot:" + source_id)` 的完整64 hex，不使用 title或 raw identity；bundle scan與 stale-staging cleanup必須明確忽略 `.locks/`。POSIX 可用 `fcntl.flock`，其他支援平台必須有等價 adapter，不能悄悄退化成 process-local/no lock。lock acquisition採 non-blocking + bounded deadline，整段同步 storage critical section放入 worker thread，不能阻塞 async event loop；timeout失敗回 `storage_failed` 且零可見寫入。不要自製靠刪 lockfile判斷 owner 的 stale-lock protocol。

Atomic rename仍是「bundle何時可見」的 commit point；source-slot lock只負責讓不同 title、v1/v2 writer與不同 process對同一 identity或短-hash collision序列化。取得鎖後必須重做 identity lookup，不能沿用鎖外 scan結果。測試至少含 multiprocessing same DOI/different title、v1 existing + v2 writer title drift、v1 writer ↔ v2 writer race與人工注入的 source-ID prefix collision，並斷言前3者只剩一個 bundle、loser重用同 path/source ID、bytes/mtime不被改寫；collision case則零 write且原 bundle/registry不變。

Hash collision 與 corruption 也必須分開：

- 若既有目錄 suffix 符合其 sidecar canonical identity 的 hash，但和 target identity 不同，才是真 collision。任何 writer都回 `source_id_collision`零 write；只能讀取/重用在升級前已存在且完整驗證通過的20/64歷史 bundle，不能只延長新目錄卻留下相同 `src-*`。
- 若 sidecar identity/DOI 自己算出的 hash不符合目錄 suffix，代表 sidecar/path遭竄改或損壞，必須 `bundle_conflict`，不可假裝 collision後另寫一份。

v1 compatibility validation 至少要檢查：top-level DOI、`source_ref.doi`、預期 `source_id`、legacy verification level、directory hash suffix彼此一致；`reference.bib` hash正確且可由既有 canonical parser解析為一筆，BibTeX DOI和 target DOI一致。即使通過，也不用 v1 sidecar直接 rehydrate registry；live SourceRef來自 fresh resolver + 已驗證的 existing BibTeX。若既有 BibTeX與 fresh CSL有 identity-critical conflict，停止重用並回報衝突，不靜默重寫。

### Verification level

保留 v1 的 `identity_verified` 可讀語意，新增明確 level：

```text
doi_identity_verified
authority_metadata_verified
```

Session/gate 不再用 `== "identity_verified"` 硬編碼，而透過 `is_citable_source(ref)` 集中判斷。這個 helper 不只查 enum membership：legacy `identity_verified` 必須有可派生的 DOI identity；`doi_identity_verified` 必須 identity 與 DOI一致；`authority_metadata_verified` 必須是 non-DOI authoritative identity。Unknown level 或 level/identity/DOI shape矛盾都 fail closed。`_finalize_answer()` 的 verified-ID集合與 `_build_sources_hint()` 的來源清單必須共用同一 helper，避免 gate與 prompt看到不同集合。

### no-DOI BibTeX

- 只接受 typed authoritative adapter 的 normalized record。
- 以 pybtex data model 建 entry，不用字串拼接。
- serialize 後再走既有 canonical parser round-trip、size/one-entry/preamble checks。
- BibTeX key deterministic 且不作 identity。
- native venue BibTeX 若存在也要 parse/normalize，不可直接信任 raw text。

## 每輪一次 mutation 的實作

不要用 candidate snapshot 實作。新增單純 `MutationGuard`：

1. 同一 `ChatSession` 新增 turn-execution lock，**唯一 acquire chokepoint是 `turn_outcome()`**；`turn()`/`turn_with_trace()`維持委派給它，不各自上鎖。必須先取得 lock，才可建立任何 turn context，然後包住 graph → finalizer → record/store整段。Concurrent public turns依到達順序序列化，這是 general session behavior change，需非 citation regression與 cancellation tests。
2. Lock內建立 `CitationTurnContext`：fresh opaque token，加上 host從 current user text獨立抽出的 DOI/arXiv與帶 span/polarity的 year/venue/version/originality claims；再交 `HostIntentBinder`逐 item綁定。不使用 `_turn_counter + 1`，也不在 lock外預先覆寫 active context。
3. Tool factory透過 getter只取得 token + host claims/bindings，不取得或持久化整段 raw user text；citation extended thinking維持禁止。沒有 active context的 `save` 回固定 non-artifact tool error `turn_context_missing`，不得碰 provider/storage；`rejected` SaveBatch仍專指有效 context內的 busy/第二次 mutation。
4. 先對 outer batch與所有 nested items做 whole-schema validation：strict types、`extra=forbid`、normalization與size caps任一失敗，整包 shape-invalid、不建立 domain batch、不 consume，允許模型只修正 malformed call。Mixed batch不能跳過壞 item後執行其餘 items。
5. Whole batch可形成 frozen WorkIntent後，由 HostIntentBinder完成 upgrade/downgrade/injection與 multi-item binding；binding不唯一時只在 frozen batch標記 `intent_binding_ambiguous`，此時尚不短路、不產 outcome，也不碰 provider。
6. 接著保留現有 citation busy lock的 **不排隊** 語意：`locked()` 時立即回 `batch_status=rejected + workflow_busy`，不 claim mutation。這讓 concurrent第二個 call fail-fast；busy釋放後若尚無 attempted mutation，合法 save仍可執行。
7. 取得 busy lock後，立刻在任何 per-item domain preflight/evaluator/provider前由獨立 atomic claim lock consume token。Claim後才把 binding marker映射為 whole-batch `insufficient_intent/intent_binding_ambiguous` outcome；即使因此全 batch零 provider call，或後續 ambiguous/not_found/provider/storage failure，也保持 consumed。這是刻意阻止模型在一次語義完整但資訊不足的 save後自行補造內容重試。
8. Claim成功後先對所有 items做 domain preflight與 resolve/verify，再對 eligible items寫入；batch內的不足/不支援項逐項回 outcome，不重新開 mutation window。
9. Busy已釋放後的同輪第二個 save取得 busy lock、但 atomic claim失敗，回 `batch_status=rejected + mutation_already_attempted`；resolver/provider/storage完全不執行。
10. 兩個 parallel save calls先競爭既有 busy lock；winner取得 lock後立即 claim，loser收到 `workflow_busy` rejected artifact。平行 calls本來就違反 skill contract，不承諾哪個 payload勝出，只保證最多一個 resolver/write；formatter/SKILL繼續要求所有 works放在單一 batch。
11. `turn_outcome()`在 `finally` compare-and-clear自己的 active token/context後才釋放 turn lock；下一輪一定 fresh，graph/finalizer/store exception或 cancellation也不能殘留或清錯 token。

測試必須覆蓋：第一次 success/failure/ambiguity/insufficient-intent（包括零 provider preflight）後 sequential第二次收到 `mutation_already_attempted`、whole-schema/mixed-item shape-invalid 後可修正且零 side effect、parallel two saves只有一次 provider/write且 loser收到 `workflow_busy`、read-only overlap busy不消耗 save mutation、無 active context fail closed、finalizer exception後下一輪不被舊 guard卡住、concurrent session turns被序列化且各自取得不同 token/constraint snapshot。

## Session、graph 與 memory

### Session finalizer

功能切換前先讓 finalizer 同時接受 legacy `citation_confirm_receipt_batch` 與新 `citation_save_batch`，但兩者各自 strict decode，不做猜測式轉換。

新路徑：

- receipt 對 live registry 比對 source ID、canonical identity、bundle path、verification level。
- ambiguity/not-found/failure 只渲染 stable reason code + sanitized bibliographic facts。
- 移除 live pending match lookup。
- finalizer priority：`save outcome（任何 item） > model text/generic recovery`。
- 空 model response 但 save artifact 已存在時，仍確定性回報每項結果。

### Graph

功能切換穩定後刪：

- `CONFIRM_BATCH_KIND` import。
- `_CONTINUATION_INSTRUCTION`。
- `_has_confirm_batch_artifact()`。
- `_between_select_and_confirm()`。
- `_continuation_attempted()`。
- agent node 的 select→confirm tool-capable continuation branch。

保留：

- truly empty upstream response identical retry。
- general tool-protocol artifact detection。
- no-tool repair 與 deterministic fallback。
- primary/local tool budgets。

`_LOCAL_CITATION_ACTIONS` 終態只含 `sources/source/explain`；`search/save` 都是 primary/external operation。移除 continuation 測試時，通用 empty/protocol recovery coverage 要搬到非 citation-specific graph test，不能連防線一起刪。

### Memory

`TurnRecord` 維持 user input + final assistant answer：

- search formatter/skill 必須要求 assistant final answer 帶完整 title/authors/year/venue/type，不能只說「c1」。
- 下一輪「第一篇／那篇」由模型從人類可見 final answer 展開 WorkIntent。
- 若那段 metadata 已不在 recent context，模型應請使用者重述；不建 hidden snapshot。
- Saved SourceRef 仍由 `_build_sources_hint()` 注入。

## 分階段 implementation commits

每一個 commit 必須 green；若 stop condition 觸發，不進下一步。

### Commit 1 — `test(citation): define the work identity resolution contract`

範圍：

- 新增 `app/skills/citation/resolution.py` 的純 domain types/normalizers/evaluator與 `HostIntentBinder` skeleton；binder輸入是已抽出的 host claims，不直接依賴 session/raw history。
- 新增 `app/tests/fixtures/citation_resolution_cases.json`。
- 新增 `app/tests/test_citation_resolution.py`。
- 不接 tool/coordinator/storage，不改 model-visible behavior。

Golden cases：

- AIAYN / Vaswani / 2017 / original：2025 posted-content repost 必須 veto。
- VAE / Kingma-Welling / 2013 original：2019 introduction monograph 必須 veto。
- exact DOI + matching metadata：eligible。
- exact DOI + title/year conflict：`identity_conflict`。
- title match + author mismatch：`identity_conflict` 或在尚無足夠 identity anchor時 `not_found`，由 corpus reason code固定，不使用泛稱 rejected。
- published/preprint 同時合理：ambiguous 或依明確 preference 唯一化。
- insufficient title-only/surname-only：not_found/insufficient，零 side effect。
- year online/print ±1 policy 有固定 reason code。
- 同一 year/venue/version值分別標為 host-verified current-user hard constraint與 visible-context hint；只有前者能 veto/唯一化 manifestation。
- Host binder覆蓋 model claim的 upgrade、downgrade、single-item omission injection、multi-item omission/ambiguous binding、item swap與negative target；後四類不得造成錯 item write。
- outer/nested unknown field、legacy `c1/m1`、超長欄位與 mixed malformed batch皆 strict reject。

驗證：

```bash
cd app
/home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q \
  tests/test_citation_resolution.py \
  tests/test_citation_normalize.py
```

Stop condition：無法用通用 feature/rules 同時擋兩個事故案例並保留正例；不得用 title-specific exception 硬過。

### Commit 2 — `feat(citation): add DataCite discovery provider`

範圍：

- 新增 `providers/datacite.py` 與 parser/client tests。
- `hub.py` 新增 limiter/cache/client。
- DataCite HTTP path使用 bounded streaming；測 Content-Length缺失/說謊與 chunk累計超限時中止，不能先把完整 body讀入記憶體。
- `ProviderRecord` 補 resolver 所需 metadata，但現有 Crossref/OpenAlex behavior 不變。
- DataCite search 尚不影響 model tool。

測試：URL encoding、title/creator/year parsing、resource type、relations、empty/error/rate-limit/timeout、cache key 不含 secret、record cap、streamed payload cap與超限不進 parser/cache。

Live contract fixture 必須包含兩個 DataCite arXiv DOI，但單元測試使用 frozen response，不依賴網路。

Stop condition：DataCite schema 無法穩定 normalize 到共用 record；先調整 record contract，不把 provider-specific dict 洩漏到 resolver。

### Commit 3 — `feat(citation): resolve WorkIntent across bibliographic providers`

範圍：

- 建立 bounded `WorkResolver`。
- Crossref/DataCite/OpenAlex 並行查詢、dedup、blocking evaluator、version decision。
- 已知 DOI 走 doi.org CSL refetch，refetch 後再次 evaluate。
- 此階段 read-only：不得呼叫 storage/register。
- 新增 redacted ResolutionEvidence 與 metrics hooks。

保留 current discovery QueryExpander，但 resolver 不呼叫它。

測試：provider order independence、partial provider failure、all providers fail、duplicate DOI across RA/open index、same-title different-work、score cannot override veto、deterministic query cap、stable reason codes。

Stop condition：任何 gold negative 被判 eligible，或 provider outage 會退化成 low-confidence write eligibility。

### Commit 4 — `feat(citation): persist canonical identities with v1 compatibility`

範圍：

- generalized identity hash/name/validate/write API。
- identity-first lookup與 per-source-ID-slot跨程序 storage lock；鎖內重新 scan/validate/collision-check/write。
- 新增獨立的 bundle schema v2 常數與 supported schema set；legacy v1 writer 不得因全域常數改值而誤寫成殘缺 v2。
- nested `SourceRef.schema_version` 也由 caller顯式指定：Commit 6前 legacy coordinator/ConfirmReceipt仍完整輸出/只解碼 v1 + `identity_verified`；只有新 writer/SaveBatch輸出 v2 levels。
- v2 sidecar builder。
- SourceRef verification helper與新 levels。
- 以同一個 `is_citable_source(ref)` 取代 `_finalize_answer()` 與 `_build_sources_hint()` 各自的 level 判斷；對既有 `identity_verified` 行為先做等價回歸。
- legacy DOI writer wrapper 保留。
- 尚不切 model tool。

測試：

- 新增 checked-in、frozen、貼近 legacy writer 實際 shape 的 v1 fixture；目前 repository 只有測試動態建立的 v1 bundle，不能把它誤當既有 fixture。
- frozen v1 fixture驗證/重用、不改 mtime/bytes；validation涵蓋 top-level DOI、SourceRef DOI/source ID/level、path suffix與 BibTeX DOI一致性。
- v1 corrupt sidecar/path mismatch與真正 truncated-hash collision分成不同 deterministic failure，兩者都 fail closed。
- v2 DOI path/source ID與 v1相同。
- 同一 DOI 但 provider title改變時 identity-first reuse原 bundle，不依新 title建立第二份。
- 不同 batch重用既有 v2時 sidecar/bytes/mtime與首次 creation evidence不變。
- v2 no-DOI identity path、collision、idempotency。
- multiprocessing same-identity/different-title與 v1↔v2 concurrent race；只容許一個 visible bundle，loser必須 reuse。
- 人工注入12-hex source-ID prefix collision：new/legacy writers都零 write、original不變；已存在的合法20/64歷史 v1仍可讀/重用，不得混成 sidecar corruption。
- multiprocessing different-identity/same-12-prefix writers共用 source-slot lock，只能保留原 identity；另一方固定 `source_id_collision`。
- sidecar 不含 raw payload、secret URL、absolute bundle path。
- `.locks/` 不被 identity scan或 stale-staging cleanup誤認為 bundle/staging；lock timeout/cancellation零 visible write。
- legacy與新 verification levels在 finalizer gate、sources hint得到一致的 `is_citable_source` 判定；矛盾 identity/DOI/level一律排除。

Stop condition：任何合法 v1 bundle 被重寫、產生第二份同 DOI bundle，或既有 `src-*` 改變。

### Commit 5 — `feat(citation): add trusted save-batch outcomes`

範圍：

- 新增 `SaveReceipt`/`SaveItemOutcome`/`SaveBatchOutcome` strict artifact。
- `session.py` finalizer 同時支援 legacy confirm batch + new save batch。
- 新 reason-code renderer。
- SourceRegistry 增加 canonical identity lookup/validation；相同 `source_id` 若對到不同 canonical identity必須 fail closed，不得覆寫原 entry。
- 仍不向模型公開新 save contract。

測試：valid receipt、registry mismatch、source-ID identity collision、unknown schema/field、`rejected/workflow_busy`、`rejected/mutation_already_attempted`、all ambiguous、all failed、partial success、order preservation、provider arbitrary prose 不進 artifact、raw DOI gate collision、empty model text + trusted artifact。

Stop condition：artifact invalid 時仍可能渲染成功，或全數失敗回到 model prose。

### Commit 6 — `refactor(citation): switch the tool to stateless WorkIntent save`

這是垂直功能切換 checkpoint，必須同一 commit 內保持 tool schema、SKILL 指令、service、finalizer E2E 一致。

範圍：

- `CitationWorkflowInput` 改成 `search/save/sources/source/explain` contract。
- `search` method-local，不存 pool；所有 filters 直接作用於該次 query，並把 Commit 2的 DataCite provider納入 discovery（不能只改善 hidden save resolver）。
- `save(works=...)` 接 resolver → serializer → storage → registry。
- 在 `turn_outcome()` 實作 general session turn lock、`CitationTurnContext`/host claim extractor/binder與 MutationGuard；新增 non-citation serialization、exception/cancellation/finally regression tests。
- formatter 移除 `cX/mX`；ambiguity 顯示 title/year/venue/version facts。
- `SKILL.md` 切成新流程與一輪一次 mutation 規則。
- `format_explain()` 同步。
- 同步 `gate.py` safe-message 與 README/guide/SKILLS_GUIDE 的最小公共契約，避免功能已切換但仍教使用者走 select/confirm；Commit 9 再補完整限制與 benchmark 說明。
- 同一 commit 內遷移 `test_citation_workflow_tool.py`、`test_citation_e2e.py`、`test_citation_skill_activation.py`、`test_skill_adherence.py`、`test_academic_skill_tools.py`、`test_policy_tool_node.py`、`test_tool_access.py`/`test_tool_access_matrix.py` 與 `test_graph_skill_loader.py` 的 model-facing action/budget expectations；不能讓 production contract先切換、舊 c/m/list/refine assertions留到刪除 commit才修。
- legacy coordinator code暫留但 tool 不可達，便於功能切換與刪除分開 review。

Tool schema rules：

- `save` 要求 `works` 1..10；其他 action 禁止 works。
- outer/action-specific/nested models全部 strict `extra=forbid`並套用 WorkIntent hard caps；整包先驗證，unknown legacy field不能被忽略。
- `source` 只接受 `source_id`；不再有 generic identifier/identifiers。
- `search` 只接受 query + search filters；沒有 more/refine/list/show/status/cancel。
- invalid parameter 組合 deterministic error，不消耗 mutation token。

E2E：

- search → assistant final answer含完整 metadata且無 c/m。
- 下一輪「存 AIAYN／第一篇／Transformer 那篇」送完整 WorkIntent。
- 同輪「找 X 並存」最多 search + one save。
- save success/ambiguity/failure 後第二次 save 被拒且零 provider/write。
- skill inactive forged call仍被 PolicyToolNode拒絕。
- deactivate citation清 registry/guard，下一次 activation為新 service state。

Stop condition：任何 user flow仍需要 c/m、final answer只剩位置不含 metadata、或第二次 save能進 resolver。

### Commit 7a — `refactor(citation): remove candidate and pending-match state`

範圍：

- 刪 `_generation/_workflow_id/_candidates/_view_candidate_ids/_matches/_match_counter/_attempts`。
- 刪 `more/refine/list/show/select/confirm/status/cancel` 與相關 formatter/types。
- `CitationCandidate` 改為/被 `DiscoveryRecord` 取代，ranking 不再 mint IDs。
- 刪 active `PendingMatchNote` state與 production pending recovery；legacy confirm artifact decoder暫時保留成只讀 compatibility邊界，若需要其 shape則使用獨立 frozen DTO，不重新引入 coordinator state。
- 刪 graph select→confirm continuation。
- 刪/重寫 c/m/pending-centric tests。
- 可將 coordinator 拆為 `discovery.py`、`resolution.py`、`service.py`；保留小 compatibility import與 legacy decoder到 7b。

刪除驗證：

```bash
rg -n "workflow_id|candidate_id|match_id|PendingMatchNote|action=.?(select|confirm|more|refine|list|show|status|cancel)" \
  app/skills/citation app/tests/test_citation* app/tests/test_graph_citation_continuation.py app/tests/test_turn_finalizer.py
```

搜尋結果必須人工分類；不可刪 extended-thinking candidate IDs。

Stop condition：通用 empty/protocol recovery coverage、source registry、gate/render 或 tool access isolation 因刪除 legacy code一起下降。

### Commit 7b — `refactor(citation): retire ephemeral legacy citation decoders`

只有在 7a 的 full suite、事故重演與 live smoke都通過，並以 code search確認 legacy confirm artifacts不會跨 process持久化/replay後才執行：

- 移除 legacy confirm artifact decoder、frozen DTO與 compatibility imports。
- `rg` 證明 production與tests都沒有舊 action/type call site。
- 再跑 strict artifact、turn finalizer、graph recovery、full app/rag suites與 live smoke。

若稽核發現 persisted/replayed legacy artifact consumer，7b 不刪 decoder；改成明確 versioned read-only migration window與 sunset條件，不能假裝相容需求不存在。

Stop condition：仍有 persisted legacy consumer、刪除後無法 finalize in-flight舊 turn，或 compatibility import仍有外部 call site。

### Commit 8 — `feat(citation): support trusted non-DOI records`

範圍：

- 先加 arXiv official record adapter與一個明確 proceedings adapter（以 NeurIPS fixture驗證）。
- authority registry/allowlist與 canonical landing URL policy。
- deterministic pybtex exporter + canonical parser round-trip。
- `authority_metadata_verified` SourceRef/receipt/render path。
- 未支援網站明確 `unsupported_no_doi_source`，不 fallback 到相似 DOI。

不要在此 commit 做 generic HTML crawler。若之後擴充 Highwire/JSON-LD parser，必須另外 threat model redirect、SSRF、HTML drift、domain authority 與 payload cap。

Stop condition：任意 web search hit可直接成為 verified source，或 no-DOI record只能靠 title hash識別。

### Commit 9 — `docs(citation): document stateless resolution and measured limits`

在 Commit 6 已完成最小契約同步的前提下，補齊完整說明與量測結果：

- `README.md`
- `guide.md`
- `app/SKILLS_GUIDE.md`
- `app/skills/citation/__init__.py`
- `app/skills/citation/SKILL.md`（若 implementation wording仍需調整）
- `app/skills/citation/gate.py` safe-message 的「搜尋→選擇→確認」文案
- config comments 與 `format_explain()`

歷史文件處理：

- `prob.md`/`RETROSPECTIVE.md`/`deep-research-report.md` 保留當時事實，只追加狀態指向新 note/plan，不重寫歷史。
- 對外文件明示舊 pool/snapshot 方向已被本 `plan.md` supersede。`CITATION_UPGRADE_PLAN.md` 在規劃當下是使用者的 untracked 檔；除非使用者另行授權把它納入版控，implementation commits 不修改、不 stage 它。

文件不得宣稱「90%」已達成，除非 benchmark 有數字。

## 測試遷移矩陣

### 大幅重寫或刪除

| 測試 | 現況 | 終態 |
|---|---|---|
| `test_citation_workflow_tool.py` | c/m、batch select/confirm、pending artifacts | 5-action schema、WorkIntent batch、MutationGuard、stateless search |
| `test_citation_coordinator.py` | generation/more/refine/select/confirm | discovery/service/resolver/write orchestration |
| `test_citation_types.py` | ConfirmReceipt/PendingMatchNote | WorkIntent/SaveBatch/identity schema |
| `test_turn_finalizer.py` | confirm + pending recovery | save success/failure/ambiguity deterministic render |
| `test_graph_citation_continuation.py` | select→confirm continuation | 刪 citation-specific部分；通用 recovery另置 |
| `test_graph_skill_loader.py` | list/refine等舊 local-action與 mixed budget assertions | Commit 6同步切成 `sources/source/explain` local、`search/save` primary；不等7a |
| `test_citation_e2e.py` | search→cX→save/confirm | search metadata→fresh WorkIntent save；same-turn search+save |
| `test_citation_ranking*.py` | candidate ID、related group IDs | ID-free discovery order/dedup/determinism + resolver quality |

### 保留並擴充

- `test_citation_doi.py`
- `test_citation_provider_doi_org.py`
- `test_citation_provider_crossref.py`
- `test_citation_provider_openalex.py`
- `test_citation_net.py`
- `test_citation_bibtex_canonical.py`
- `test_citation_gate.py`
- `test_citation_render.py`
- `test_citation_storage.py`
- `test_citation_skill_activation.py`
- `test_policy_tool_node.py`
- `test_skill_adherence.py`
- `test_tool_access_matrix.py`

### 必要 regression cases

1. old `c1` → new `c1` 類錯誤在 API shape 上不可表達。
2. AIAYN 2025 repost zero write。
3. VAE 2019 monograph zero write。
4. exact DataCite arXiv records可被找到。
5. AIAYN明示 arXiv/preprint時 Commit 6可走 DataCite DOI；明示 NeurIPS/published時 Commit 6回 `unsupported_no_doi`、Commit 8才走官方 proceedings identity；generic版本依已審核 policy決定或回 ambiguity，絕不拿preprint DOI冒充 published record。
6. DOI exact但 intent conflict zero write。
7. no DOI official proceedings成功；untrusted URL fail closed。
8. provider all-fail zero write；partial provider failure仍可在強證據下 resolve。
9. batch 2 success + 1 ambiguous + 1 not-found，finalizer順序與狀態完整。
10. batch全失敗仍 deterministic render。
11. 同輪第二次 mutation無 network/storage call。
12. shape-invalid mixed batch不 consume；shape-valid `insufficient_intent` 即使零 provider call仍 consume。
13. host-verified constraint可 veto；相同 visible-context hint不能冒充 hard constraint。
14. v1/v2 bundle重用 bytes/mtime不變；同 identity title drift與 multiprocessing v1↔v2 race只留一份。
15. sidecar creation evidence不含 requested label/raw prose；不同 batch reuse不回寫。
16. SourceRegistry同 source ID/different identity fail closed，原 entry不變。
17. skill inactive/cross-skill forged tool call拒絕。
18. raw DOI/citation marker gate行為不退化。
19. `app/agent/fusion.py`/thinking candidate tests全綠。

## Benchmark 與量測

現行 `zero_false_saves` benchmark 先人工找到 gold candidate/DOI再 confirm，沒有測 resolver會不會選錯；要改成直接餵 WorkIntent。

Corpus 類別：

- Crossref journal DOI。
- DataCite/arXiv DOI。
- conference-only no-DOI。
- preprint + published雙版本。
- repost/review/tutorial vs original。
- 同 title不同作者／同作者相似 title。
- online/print跨年。
- multilingual/punctuation/title variant。
- incomplete intent。
- provider timeout/rate limit/invalid payload。
- malformed BibTeX、bundle conflict、concurrent save。

Metrics：

```text
auto_resolve_rate
auto_save_precision
false_save_rate
clarification_rate
abstention_rate
no_doi_success_rate
provider_exact_hit/error/timeout/rate_limit
mean provider calls and latency per work
user correction/quarantine rate（live observation）
```

Release gate 建議：false-save corpus 必須為 0；coverage 未達標可以先 abstain，不得放寬 blocking constraints換 recall。90% coverage 是後續量測目標，不是切換 core correctness 的前置謊言。

## 全套驗證與 live smoke

### 每個 commit

先跑相關 tests，再跑完整 app suite：

```bash
cd app
/home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q
```

Citation code未直接修改 `rag/`，但功能切換與最終 commit各跑一次 rag suite確認 package/import無波及：

```bash
cd rag
/home/minervamuses/miniconda3/envs/rag/bin/python -m pytest -q
```

Import smoke：

```bash
cd app
/home/minervamuses/miniconda3/envs/app/bin/python -c \
  "import agent, skills.citation; print('app ok')"
```

### Live smoke 隔離

使用 temporary output dir，不污染現有 `cite/`：

```bash
tmpdir="$(mktemp -d)"
cd app
CITATION_OUTPUT_DIR="$tmpdir/cite" \
  /home/minervamuses/miniconda3/envs/app/bin/python -m agent.cli.chat
```

場景：

1. 搜 AIAYN + VAE，回答無 c/m，完整呈現 metadata。
2. Commit 6下一輪明示「先存 transformer 的 arXiv/preprint版」只產生一個 WorkIntent save batch並命中 DataCite DOI；明示 NeurIPS/published版則誠實回 `unsupported_no_doi`且零 write。Commit 8後重跑 published版，才以官方 proceedings identity成功。
3. 2025 repost與 VAE monograph不得出現在 output dir。
4. published vs arXiv 有明確差異時，依 preference決定或自然語言澄清，無 `mX`。
5. 同輪故意誘發第一個 save failure，再讓模型嘗試補救；第二次 mutation必須被工具拒絕。
6. provider故障後 output dir為空，final receipt誠實。
7. 成功 receipt含 title/year/type/source ID/bundle，不靠 model prose。
8. deactivate/reactivate skill，registry與 guard隔離正常。
9. `git status --short` 確認既有兩個事故 bundle、user修改與其他檔案未被動到。

## Rollout 與刪除時機

不加永久 feature flag。採以下 checkpoint：

1. Commit 1–5 新路徑是 internal/read-only/dual-decoder，model-visible behavior仍 legacy；任何時點可停。
2. Commit 6 是唯一功能切換 commit；若 live smoke失敗，可單獨 revert，不影響前面 pure resolver/provider/storage compatibility資產。
3. Commit 6 通過完整 suite + live smoke 後才做 Commit 7a 刪除 active candidate/pending state。
4. Commit 7a 後至少再跑一次事故重演、full suite與 persisted-artifact consumer audit，全部通過才做 7b 移除 legacy artifact decoder/import shim；若存在 consumer，保留 versioned read-only decoder並定義 migration window。
5. no-DOI coverage是後續增量；core switch前可明確回 `unsupported_no_doi`，其行為不比現況差，且絕不能用相似 DOI替代。

每個 deletion 必須先用 `rg` 證明 call site為零，再刪 type/function/test。不要用 LOC 減少當驗收；以 unreachable state、API不可表達 silent alias、tests/metrics為準。

## 連帶影響檢查表

### Tool budget

- stateless `search` 與 `save` 各算一個 graph primary tool call。一般跨輪流程是 discovery turn `search`=1、後續 save turn `save`=1；同一輪確實先 search再 save時=2。
- 若使用者已給足 WorkIntent且直接要求「找出並保存」，resolver在 `save` 內完成 provider discovery，無需為了形式先呼叫 `search`，因此該輪可維持1個 primary call。
- Crossref/DataCite/OpenAlex/doi.org fan-out是單一 `save` 內部的 bounded provider calls，不另計 graph tool budget；但要各自受 query/rows/time budget與metrics約束。
- sources/source/explain算 local。
- 移除 list/show/refine/continuation應降低 tool-call壓力。
- 一次 batch save取代逐項 calls；上限仍為10。

### Extended thinking

- Citation active期間繼續強制 normal。
- 原因從「candidate pool會交錯」變為「多 proposer不能重複執行 registry/filesystem mutation」。
- 若未來要開放，必須先做 read-only proposer + single committer設計，另案處理。

### SourceRegistry、gate、renderer

- `src-*` 只在成功保存後 mint。
- gate仍只接受 registry中 citable source IDs。
- renderer已支援 `doi` 缺失時 URL fallback；新增 verification levels tests。
- `_build_sources_hint()` 改用 `is_citable_source`，不硬編舊 level。

### History 與 plan log

- 不把 tool artifacts放進 TurnRecord/Chroma。
- deterministic final save outcome進 final assistant answer，因此跨輪可見。
- plan log仍可記 tool trace；sidecar只存 correlation/batch ID，不存 raw prose。

### Config 與 dirty worktree

- `citation_ranking_mode` 保留，僅控制 discovery。
- `citation_output_dir` 保留。
- DataCite public API第一版不需 key；若新增 mailto/UA另寫 config。
- 規劃時 `app/agent/config.py` 已有使用者未提交修改。實作碰該檔前必須先 inspect/diff，逐 hunk整合，不可覆蓋。
- 每個 commit精準 pathspec stage；不得帶入兩個事故 bundle或其他 untracked文件。

### Security

- provider error/URL全程 redaction。
- no-DOI adapter限制 scheme/domain/redirect/payload size/content type。
- 不 fetch任意 user URL直到 authority policy通過；防 SSRF/private address。
- artifact不帶 provider自由文字。
- BibTeX繼續 size、single-entry、preamble與 DOI consistency validation。

### Quarantine/revoke

本次 core重構不自動刪事故 bundle。另設明確管理 action：

- 使用者指定 stable source ID/bundle。
- 先 validate、產 audit receipt，再移至 quarantine，不直接 unlink。
- registry deactivate/remove 與 filesystem move要有清楚 partial-failure semantics。
- 不和 save resolver共用 mutation authorization；另案 threat model與測試。

## 風險矩陣

| 風險 | 可能後果 | 防線 | 停止條件 |
|---|---|---|---|
| Matching threshold過鬆 | false save | hard veto + corpus + margin + abstain | 任一 gold negative被寫入 |
| Matching threshold過嚴 | 多 clarification/not-found | 分開量 coverage；不以放寬 correctness修 | precision不能維持時不切換 |
| DataCite/Crossref schema差異 | field誤映射 | provider adapter fixtures + provenance | provider-specific raw dict洩漏domain |
| v2 storage破壞 v1 | duplicate/overwrite | compatibility matrix + byte/mtime tests | v1被改寫或 source ID變化 |
| 新 artifact被偽造 | 假成功 | strict decode + live registry identity match | invalid artifact可render success |
| one-shot guard跨輪殘留 | 後續合法save被拒 | fresh token + finally cleanup tests | finalizer failure後新輪仍blocked |
| parallel tool calls | double write | atomic mutation claim + busy fail-fast + source-slot cross-process storage lock | 同 turn provider被執行兩次，或同 identity留下兩個 bundle |
| 刪錯 candidate_id | extended thinking壞掉 | path-scoped deletion + full suite | thinking/fusion tests回歸 |
| no-DOI authority太寬 | untrusted citation | curated adapters/allowlist + SSRF policy | generic web hit可被verified |
| 文件與工具不同步 | 模型仍呼叫c/m | vertical switch含SKILL/tool tests | skill adherence仍產legacy actions |

## 完成定義

只有以下全部成立，才算本計畫完成：

- Model-facing save API 無 candidate/match/generation ID。
- Active citation pool/matches/pending state從 production path移除。
- old-`c1`→new-`c1` 在型別/API層不可表達。
- 同一 user turn第二次 save mutation零 provider/storage side effect。
- AIAYN/VAE事故 fixtures與 live smoke通過。
- DataCite exact records可解析；Crossref repost/monograph被blocking veto。
- success/partial/all-failure/ambiguity皆由trusted artifact deterministic render。
- v1 bundles驗證/重用且未重寫；DOI source IDs/paths不變。
- no-DOI至少有一條可信 proceedings path；未支援來源會abstain。
- citation gate/renderer/tool access/skill teardown/empty reply recovery全綠。
- app full suite與rag suite全綠。
- README、guide、SKILLS_GUIDE、SKILL/explain/gate文案一致。
- Benchmark報告 precision、coverage、abstention，不把「90%」當未量測宣稱。

## 建議執行邊界

最小可發布核心是 Commit 1–7a：它已讓錯誤抽象從 production path不可達、加入 DataCite、blocking identity validation、one-shot mutation與 v1-compatible storage。Commit 7b是通過 persisted-consumer audit後的相容層清理；Commit 8擴充 no-DOI coverage。如果 adapter threat model尚未準備好，可以明確 abstain，不應阻塞核心 correctness switch，也不能用相似 DOI填洞。

Commit 1建立 corpus/evaluator前，先由使用者審核：

1. generic「這篇」預設偏 published/VoR，還是版本不明一律詢問。
2. `original` 預設解讀為 original work、earliest manifestation，或要求模型分辨後填兩個欄位。

Commit 8開始前再審核：

3. 第一批 no-DOI authority adapters 除 NeurIPS/arXiv 外要涵蓋哪些 venues/repositories；此項不阻塞 DOI core 1–7a。

這三項只影響版本 policy 與 coverage，不改變已確定的核心邊界：保存接受 WorkIntent，不接受 pool position。
