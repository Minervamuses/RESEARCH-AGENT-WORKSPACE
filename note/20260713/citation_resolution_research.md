# Citation resolution：從候選池與跨輪編號回到作品身分

日期:2026-07-13

相關檔案:`prob.md`、`RETROSPECTIVE.md`、`CITATION_UPGRADE_PLAN.md`、`deep-research-report.md`、`plan.md`

相關事故資料:`cite/An_Introduction_to_Variational_Autoencoders--b5ee92e3333d/`、`cite/Attention_Is_All_You_Need--69d47b977feb/`

狀態:研究結論；尚未修改 production code

## 摘要

這次事故表面上是「跨回合記錯了 `c1`」，但更深的問題不是快照漏存，也不是編號不夠穩定，而是目前 citation workflow 把**搜尋結果的位置**當成**待保存作品的身分**。

現行流程是：search 建立 session candidate pool，候選被編成 `cX`；select 再產生 `mX`；save/confirm 最後以這些 opaque ID 寫入。為了維持 `cX/mX` 的生命週期，系統逐步加入 generation、跨 candidate 累積 matches、graph continuation 與 pending recovery。這些機制各自解過真實問題，但也讓系統持續投資在「如何保存搜尋位置」而不是「如何重新辨識使用者要的作品」。相對地，atomic storage 與 trusted receipt/failure artifact 是正交的 correctness assets，和 pool 是否存在無關，應保留。

本次研究後的結論是：

- 搜尋結果可以有臨時編號，方便同一畫面說「第一篇」；但編號只能是 UI affordance，不能作為保存 API 的作品身分、授權錨點或跨回合契約。
- 使用者說「存 Attention Is All You Need／Transformer 那篇」時，下一步應把自然語言轉成一次性的作品意圖（WorkIntent），再以標題、作者、年份、venue、已知識別碼與版本偏好重新解析。
- DOI 是某個可引用物件的 persistent identifier，不是「論文」本身，也不是每篇論文都有；BibTeX 則只是輸出格式。作品、版本、identifier、serialization 必須分層。
- 已知 DOI 時，現有 `doi.org` CSL JSON → BibTeX 的驗證鏈值得保留；未知 DOI 時，應做有界的多來源 resolution，而不是只反覆查 Crossref；沒有 DOI 但有權威書目頁時，也應能確定性產生 BibTeX。
- 高信心且只有一個符合版本條件的結果才自動保存；零個結果就明確失敗，多個合理版本就以人類可讀的版本差異要求澄清。寧可 abstain，不可用低信心結果補洞。
- 「90%」是產品設計目標，不是目前量測結果。要以代表性 corpus 量測 auto-resolution、false save、clarification、no-DOI success 與 provider failure，不能用 AIAYN/VAE 兩例宣稱達標。

一句話總結：**不要把 candidate pool 修成跨回合資料庫；在保存當下，直接重新解析使用者所指的作品。**

## 原始情境與事故結果

使用者先要求搜尋兩篇知名原始論文：

1. Transformer 的原始論文 *Attention Is All You Need*。
2. VAE 的原始論文 *Auto-Encoding Variational Bayes*。

第一輪先後建立四個搜尋 workflow：AIAYN 是 `wf-1`，VAE 搜尋一路到 `wf-4`。每次 search 都清空舊 pool 並重新從 `c1` 編號。模型最後卻把不同 workflow 的局部編號混在同一段摘要中：一方面稱 Transformer 是 `c1`，另一方面又把當時 live `wf-4` 的 `c1/c2` 說成 VAE 相關結果。

下一輪使用者說「先存 transformer 那篇」。實際發生兩次寫入：

| 時間（Asia/Taipei） | 寫入物件 | sidecar 身分 | 為何錯誤 |
|---|---|---|---|
| 00:09:04 | *An Introduction to Variational Autoencoders*，2019 monograph | `wf-4 / c1 / m1`，DOI `10.1561/9781680836233` | 使用者只授權 Transformer；這筆既非 Transformer，也非 VAE 原始論文。 |
| 00:09:30 | *Attention Is All You Need*，2025 posted-content | `wf-5 / c2 / m1`，DOI `10.65215/r5bs2d54` | 模型看到第一筆錯誤後自行重搜並補存；使用者沒看過 `wf-5`，且此物件不是 2017 NeurIPS 原始出處。 |

兩筆相隔約 25 秒。第一筆是 stale meaning：字串 `c1` 仍合法，卻已從 Transformer 靜默改指 VAE monograph。第二筆是 unauthorized compensation：模型沒有停下回報已存錯，而是擴張同一句授權的範圍，自行搜尋並再寫一次。

## 事故證據與事件重建

兩份 `citation.json` 能直接證明兩個 saved identities、`wf/c/m` 與寫入時間；下列完整事件序列則是把這些 sidecar、`prob.md` 當時的 CLI 觀察與 final receipt 交叉後所做的重建：

```text
第一輪：
  wf-1: AIAYN search        -> c1 在這個局部 pool 代表 AIAYN
  wf-2..wf-4: VAE searches  -> 每次重建 pool、重新從 c1 編號
  live state at turn end    -> wf-4，c1 是 2019 VAE monograph

第一輪 final prose：
  同時沿用 wf-1 的「Transformer c1」和 wf-4 的 VAE c1/c2

第二輪：
  user: 先存 transformer 那篇
  save(c1) against live wf-4
  -> 寫入 2019 VAE monograph
  -> 收據顯示標題不符
  -> 模型未停下，建立 wf-5 搜 AIAYN
  -> save(c2)
  -> 寫入 2025 posted-content repost
```

現行程式讓這條路徑成立的關鍵點：

- `app/skills/citation/coordinator.py` 的 `_new_generation()` 會清空 candidates/matches 並重設 counter。
- `app/skills/citation/ranking.py` 每次 fusion/filter 後重新賦予 `c1...cN`。
- `CitationCoordinator.get_candidate()` 只比較目前 pool 中的 bare `candidate_id`；它不能知道 prompt 裡的 `c1` 原本指向另一個 workflow。
- `app/agent/memory.py` 的 `TurnRecord` 只保存 user input 與 finalized assistant prose。第一輪的 ToolMessage/candidate lists 不會進入下一輪 prompt。
- `ChatSession._prompt_history()` 會注入 skill、tool availability、plan mode 與已保存 sources；沒有 active candidate pool 的權威投影。
- `app/skills/citation/tool.py` 明定自然語言保存授權由模型判斷；tool 驗 workflow/identifier state，但 sidecar 沒有 user request、作品意圖、版本偏好或授權範圍可供驗證。
- busy lock 只阻止並行的 state mutation，不能阻止同一輪先後兩次 save。

所以現況不是「系統忘了讓舊 `c1` stale」，而是更危險的 **silent alias**：舊名稱恰好也是新 pool 的合法名稱，錯誤不會大聲失敗。

這裡同時暴露一個 audit gap：現行 sidecar 沒有 action/batch/turn ID、WorkIntent 或授權範圍，因此只靠落盤資料無法獨立證明「模型先看到錯誤收據，接著重搜補存」的每個中間動作。新設計不應保存 raw user utterance 或 LLM prose，但至少要保存一個 request/turn correlation ID、結構化 WorkIntent、逐項 resolution decision 與本輪 mutation batch ID，讓未來不必靠對話畫面重建副作用順序。

## 驗證鏈為何全綠仍然存錯

兩份錯誤 sidecar 的 verification 都有三個 passed check，且 `warnings=[]`：

1. selected match DOI 等於重新取得的 CSL DOI。
2. BibTeX 可以安全解析且恰好一筆。
3. BibTeX DOI 等於 CSL DOI。

這三項證明的是：

```text
match DOI == doi.org structured record DOI == BibTeX DOI
```

它沒有證明：

```text
resolved record == 使用者要的作品與版本
```

現行 `_collect_warnings()` 對 candidate/structured record 的 title/year 衝突只產生非阻斷 warning；而本次 AIAYN repost 的 title/author 本來就可能完全相同，所以只比 title 也不夠。作品身分與版本／manifestation 必須成為寫入前的 blocking policy，而不是 DOI pipeline 完成後的附帶提示。

## 原先考慮的修法，以及為何研究後修正

事故剛發生時，`prob.md` 提出的第一輪方向合理地瞄準直接症狀：

- 每個使用者輪只能消耗一次 save 授權。
- 把 live candidate snapshot 注入下一輪 prompt。
- 把 `c1` 改成帶 generation 的 `w4c1`，讓過期指涉大聲失敗。
- 加 canonicality warning，阻擋年份明顯矛盾的 repost。
- 補撤銷路徑。

這些能降低本次事故重演機率，但沒有移除核心假設：**搜尋結果的位置就是作品的可攜身分**。它們會要求系統繼續維護：

- 哪一輪顯示過哪些 candidates；
- 模型當時看到哪個 view/filter/page；
- `cX` 屬於哪個 generation；
- 授權綁在哪份 snapshot；
- snapshot 如何跨 TurnRecord、session eviction、skill teardown 與 prompt window；
- pool 更新、refine、more、batch save 後哪些 ID 仍有效。

也就是用更多 state management 修補一個不需要存在的跨回合問題。

研究後的修正不是「所有編號都錯」，而是：

| 用法 | 是否保留 | 理由 |
|---|---|---|
| 同一則搜尋結果中顯示 `1/2/3` 或 `c1/c2/c3` | 可保留 | 降低使用者輸入成本；只是一頁內的 UI locator。 |
| 下一輪把 `c1` 當作品 primary key | 移除 | 位置會重用，無法表達 title/author/year/version。 |
| save API 接受 candidate ID | 移除 | 寫入邊界應接作品意圖或已知 persistent identifier。 |
| 保存後的 `src-*` | 保留 | 它代表已解析、已驗證、已落盤的來源，不是搜尋位置。 |

如果使用者只說「存第一篇」，模型可以從當前可見文字抽出那篇的 title/author/year，組成 WorkIntent；不需要把整個 pool 存到下一輪。若上下文已經被截斷到連作品 metadata 都不存在，就應要求使用者再說一次，而不是猜一個 `c1`。

## 舊文件在這次研究中的角色

### `deep-research-report.md`

這份 07-11 報告把當時八類問題整理成：回合終結與 tool budget、workflow contract/grounding、confirm receipt、discovery/ranking。它促成了空回應修復、protocol leakage 防線、refine、metadata-only 提示、explain contract 與 trusted receipt，這些結論仍有價值。

但它是歷史階段文件。當中「沒有 refine/explain」「bundle 在 platform user-data」等敘述已被後續 commits 改變；其主流程仍接受 candidate pool 與 select/confirm。這次 note 只把它用作設計演化與依賴關係證據，不把過時段落當成 current facts。

### `CITATION_UPGRADE_PLAN.md`

07-12 的三篇批次實測發現單一 selection、stale matches 與部分失敗被遮蔽。升級計畫加入：

- 跨 candidate 累積 matches；
- batch select/confirm；
- 模型語意授權與同輪 confirm；
- batch receipt/failure artifact；
- workspace `cite/` 預設路徑。

這些改動解決的是當時真實 UX/correctness 問題，不能倒果為因地說它們一開始就毫無價值。然而後續又出現 atomic `save(candidate ids)`、pending artifact recovery、graph 在 select/confirm 中間的 continuation，顯示系統持續替 `cX/mX` 的生命週期加機制。本次結論是：保留其中與身分無關的好資產（atomic storage、trusted receipt、batch failure rendering），停止延伸 pool abstraction。

## Citation 的領域模型

「找論文、找 DOI、拿 BibTeX」容易被說成一件事，實際至少有四層：

| 層 | 問題 | 例子 |
|---|---|---|
| Work（作品） | 使用者在語意上指哪個研究成果？ | *Attention Is All You Need* 這項工作。 |
| Manifestation / version（可引用版本） | 要引用哪個具體出處或版本？ | 2017 NeurIPS proceedings、arXiv preprint、之後的 repost。 |
| Identifier（識別碼） | 哪個 persistent/local identifier 指向該物件？ | DOI、arXiv ID、PMID、venue URL。 |
| Serialization（輸出格式） | 如何把已選定的書目記錄輸出？ | BibTeX、CSL JSON、RIS。 |

因此：

- DOI 不是論文的同義詞。一項 work 可能沒有 DOI，也可能有多個 DOI 指向不同版本／物件。
- Crossref 不是 DOI 全域搜尋引擎，而是一個 Registration Agency 的 metadata service；其他 DOI 可能在 DataCite 等 RA。
- DOI 系統本身不提供涵蓋所有 DOI 的中央 title search。title/author → DOI 是 metadata matching 問題，天然有 precision/recall 取捨。
- 已知 DOI 後，透過 `doi.org` content negotiation 取得 CSL JSON/BibTeX 是另一個方向的 lookup，而且可由 DOI resolver 導向支援的 RA；這正是現有 code 已經做對的部分。
- BibTeX 是 serialization，不是 authority。權威性來自已選定的 citable object 與其 metadata provenance。

## 2026-07-13 的外部實測

為避免只用概念推論，本次以公開 API 重跑 AIAYN/VAE。這是 failure reproduction，不是完整 benchmark。

### 精確 title + author + 原始年份

Crossref 使用 `query.title`、`query.author`、publication-date filter 與 `rows=5`；DataCite 使用對應的 title/creator metadata query。2026-07-13 本次回應如下：

| 查詢 | Crossref | DataCite |
|---|---|---|
| `query.title=Attention Is All You Need`、`query.author=Vaswani`、2017-01-01..2017-12-31 | Crossref response `items=[]`，沒有目標作 | 命中 `10.48550/arXiv.1706.03762` |
| `query.title=Auto-Encoding Variational Bayes`、`query.author=Kingma`、2013-01-01..2014-12-31 | Crossref response `items=[]`，沒有目標作 | 命中 `10.48550/arXiv.1312.6114` |

### 拿掉年份的 Crossref broad query

- `query.bibliographic=Attention Is All You Need Vaswani` 的前五筆全是 2025 `posted-content`，其中第一筆正是事故寫入的 `10.65215/r5bs2d54`。
- `query.bibliographic=Auto-Encoding Variational Bayes Kingma Welling` 的第一筆是 2019 *An Introduction to Variational Autoencoders* monograph，正是事故寫入的 `10.1561/9781680836233`。

### 已知 DataCite DOI 後

對兩個 `10.48550/arXiv...` DOI 呼叫 `https://doi.org/<doi>` 並要求 `application/x-bibtex`，都能取得標題、作者、arXiv URL 與原始年份正確的 BibTeX。

這說明「把同一個 Crossref query 查幾百次」不會提高資訊量。應做的是有界、異質的 fallback：

```text
known identifier
  -> exact bibliographic match across suitable registries
  -> repository / official venue lookup
  -> authoritative no-DOI citation
  -> abstain
```

AIAYN 也說明「原始」不等於「一定找一個 DOI」：官方 NeurIPS proceedings 頁提供正式 venue metadata 與 BibTeX；arXiv 則是另一個有 DataCite DOI 的合法 manifestation。系統應依使用者版本偏好選擇，而不是把「有 DOI」誤當成「最正式」。

## 為什麼 candidate pool 是錯誤的寫入抽象

Candidate pool 對 discovery UI 有用：它能融合 providers、排序、分頁、群組版本，並讓使用者快速瀏覽。但把它帶進寫入流程會製造五種不必要的耦合：

1. **時間耦合**：save 必須發生在某次 search state 尚未變動時。
2. **位置耦合**：作品身分依賴排序位置，而排序會因 provider、query expansion、年份 filter 與新資料改變。
3. **記憶耦合**：模型 prose、ToolMessage、live coordinator 與跨輪 history 必須保持一致。
4. **授權耦合**：系統得證明使用者授權的是哪一份 pool 的哪個 slot。
5. **恢復耦合**：空回應、budget、malformed tool call 都要知道流程停在 select 還是 confirm。

若 save 接的是自足的 WorkIntent，這些問題大多消失：

```json
{
  "mention": "transformer 那篇",
  "title_hint": "Attention Is All You Need",
  "author_hints": ["Ashish Vaswani"],
  "year_hint": 2017,
  "venue_hint": "NeurIPS",
  "user_supplied_target_identifiers": {},
  "version_preference": "original published version"
}
```

這個 payload 本身就能被 log、測試、重跑與驗證。它不需要引用過去 pool 的位置；解析結果錯時，也能回答是哪個 constraint 沒被滿足。

Identifier 必須記 provenance。只有使用者明確提供、或從使用者指定 URL 確定抽出的 target identifier，才能成為 hard anchor；resolver/provider 找到的 arXiv ID、DOI 或 related identifier 只是待驗證 evidence，不能由模型記憶冒充成使用者指定條件。

## 目標涵蓋 90% 的主流程（待量測）

### 使用者互動

```text
1. discovery 找到一些論文，用自然語言 + metadata 呈現
2. 使用者說要哪一篇／哪些篇
3. 模型把指涉轉成一個或多個 WorkIntent
4. 一次 resolve-and-save batch call，逐項做有界多來源解析；工具／graph 強制本輪只能有這一次 mutation attempt
5a. 唯一強匹配 -> blocking validation -> 寫入
5b. 多個合理版本 -> 顯示具體差異，要求使用者用自然語言選版本
5c. 無強匹配 -> 不寫入，說明缺少什麼
6. finalizer 確定性呈現逐項成功／失敗／歧義
```

第二輪澄清不需要保存 `mX`。例如系統回「找到 2017 NeurIPS proceedings 與 2017 arXiv preprint；你要正式會議版還是 arXiv 版？」使用者回答「會議版」後，新的 WorkIntent 加上 `version_preference=published`，重新跑一次即可。

這個 one-shot mutation guard 不需要 candidate pool 或授權 snapshot：一個 user turn 最多執行一個 `resolve_and_save(works=[...])` batch；第一次有效嘗試不論是成功、歧義、找不到或 provider failure，都消耗本輪 mutation opportunity。模型不得在看見失敗後自行改 query 再寫；它只能把結果回報給使用者，下一輪取得新指示後再嘗試。批次本身可含多篇，因此不犧牲正常的多篇保存 UX。

### Resolver 優先序

1. 使用者提供的 DOI/arXiv/PMID/URL：直接 lookup，仍要驗 title/author/year/version constraint。
2. 精確 title + author + year：並查適合的 structured sources，例如 Crossref、DataCite、arXiv；合併成 citable-object records。
3. 若 structured source 不足：查官方 venue/repository landing page。
4. 建立版本關係與 evidence；把 user constraint 當 veto，不只是加分。
5. 唯一強匹配才進 serialization/storage。

### 版本政策

- 使用者指定 identifier 或版本時，明確指定優先。
- 使用者只說「這篇論文」時，若能可靠連結，優先正式 published version / version of record。
- 沒有正式 DOI 或正式 venue 就使用官方 proceedings/repository/arXiv record，不因缺 DOI 而換成相似作品。
- 「原始」「2017」「NeurIPS」是 blocking constraint；2025 repost 即使 title/author 相同也不能通過。
- 只有版本差異會實質影響引用意義時才詢問；不要對每篇都強迫多一輪確認。

### DOI 與 no-DOI 分流

```text
resolved citable object
  ├─ has DOI
  │    doi.org CSL JSON
  │      -> identity/version validation
  │      -> doi.org BibTeX
  │      -> parse/canonicalize
  │      -> atomic bundle
  └─ no DOI
       authoritative landing-page metadata
         -> identity/version validation
         -> deterministic BibTeX exporter
         -> atomic bundle
```

no-DOI path 不是降低標準；它把 authority 從 DOI metadata 改為可追溯的官方 landing page，sidecar 必須記錄 evidence URL、retrieval time、parser/adapter 與 normalized fields。

## 自動、澄清與 abstain 的界線

| 情境 | 行為 | 禁止行為 |
|---|---|---|
| DOI/arXiv ID 已知，metadata 與 intent constraints 一致 | 自動保存 | 不得跳過版本／年份衝突。 |
| 精確 title/author/year 唯一強匹配 | 自動保存 | 不得因 provider rank 高就忽略 blocking mismatch。 |
| 同 work 有 preprint 與 published 兩種合理版本 | 依明確版本政策選；若政策不足則澄清 | 不用 `mX` 要使用者解讀內部 match。 |
| 同名不同作品或作者/year 資訊不足 | 澄清或 abstain | 不可挑搜尋第一名。 |
| 無 DOI，但有官方 proceedings/repository metadata | deterministic no-DOI save | 不可換存另一篇有 DOI 的相似作品。 |
| provider timeout/rate limit | 回傳 retriable failure；不寫 | 不可把 partial result 當成功。 |
| CSL/BibTeX/landing-page metadata 互相矛盾 | blocking failure | 不可只放 warning 後寫入。 |
| 使用者的「原始／正式版／某年份」無法滿足 | 明確失敗或詢問是否接受替代版本 | 不可靜默降級成 repost/review。 |
| storage conflict/write failure | 保留原子性並確定性回報 | 不可報保存成功。 |

這個政策刻意偏向 precision。Citation save 是有副作用的資料操作；false positive 的成本通常比多問一次或少存一次更高。

## 現行資產：保留、擴充、退役

### 保留

- process-level provider cache、rate limiter、retry 與 redaction。
- `doi.org` RA-independent CSL/BibTeX content negotiation client。
- BibTeX parser、canonicalizer、DOI injection/consistency checks。
- atomic bundle write、hash validation、idempotent reuse 與 workspace `cite/`。
- `SourceRef`/`SourceRegistry`、`src-*` 引用標記、citation gate 與 renderer。
- trusted receipt/failure artifact 與 finalizer 的確定性成功／失敗回報。
- discovery provider adapters、ranking、refine、version grouping；但降為 discovery/read-only concerns。

### 擴充或重構

- 新增 WorkIntent、ResolvedWork/ResolutionEvidence 與三分結果（resolved/ambiguous/not_found）。
- 新增 DataCite discovery 與 arXiv/official venue lookup。
- 把 title/author/year/type/version contradiction 從 warning 升為 blocking validation。
- 新增 no-DOI metadata adapter 與 deterministic BibTeX exporter。
- storage key 從 DOI-only 泛化為 canonical citation identity；舊 DOI bundle 必須保持可讀與可重用。
- receipt 從 `accepted_doi` 必填改成 canonical identifier/evidence，可兼容 no-DOI source。
- sidecar 從 `candidate_snapshot`/`match_snapshot` 改存 request/turn correlation ID、mutation batch ID、requested_work、resolved_record、resolution_evidence 與 version decision。
- 新增明確的 quarantine/revoke 管理路徑；它應是可稽核的獨立使用者動作，不由 resolver 在發現錯誤後自動刪除。

### 在新路徑穩定後退役

- active candidate pool 作為 save 的前置狀態。
- workflow generation 與 `cX/mX` save/confirm API。
- select/confirm pending state machine。
- `PendingMatchNote`、select→confirm graph continuation 與 pending recovery finalizer。
- 跨回合 candidate snapshot / generation-aware ID 的提案。

退役必須分階段，不應 big-bang。先新增不寫入的 resolver shadow mode 與 characterization tests，再切換保存 contract，最後刪舊路徑。

## 剩餘失敗模式

精簡流程不會讓 metadata matching 變成 100%。剩餘風險主要是：

- 極短或錯拼的 title、同名作者、譯名與 title variant。
- 使用者只說「那篇」但 prompt 已沒有足夠 metadata。
- preprint、accepted manuscript、conference、journal extension、reprint 間關係沒有被 metadata 正確標注。
- Registration Agency 或 publisher deposit 缺漏、錯誤、過時。
- 沒 DOI 的網站改版，landing-page parser 失效。
- DOI resolve 成功但 content negotiation 不支援某格式或回傳欄位不足。
- correction/retraction/withdrawal 關係未被 source 提供或未被 resolver 消化。
- provider outage、rate limit、網路中斷。
- 惡意或異常 metadata、超大 BibTeX、路徑碰撞與既有 bundle corruption。

對這些問題的共同策略不是再建一個長壽 pool，而是：保留 evidence、設定 blocking contradictions、限制嘗試次數、允許 abstain、提供 retriable failure，並建立可量測的 benchmark。

## 驗收指標

在宣稱「完成 90% 工作」之前，至少要用代表性 corpus 記錄：

- `auto_resolve_rate`：不澄清即可唯一解析的比例。
- `auto_save_precision`：自動寫入中，作品與版本都正確的比例。
- `false_save_rate`：錯作品、錯版本或未授權寫入；目標應接近零。
- `clarification_rate` 與 `abstention_rate`。
- `no_doi_success_rate`。
- 各 provider 的 exact-hit、timeout、rate-limit、metadata-conflict 分布。
- 使用者後續 correction/undo rate。
- 每篇平均 provider calls、latency 與 tool interactions。

測試 corpus 至少要包含：知名 CS preprints、正式 journal DOI、conference-only no-DOI、同名作品、preprint/published 雙版本、repost、review vs original、多語 title、錯誤年份、provider outage 與 corrupted metadata。

## 結論

這次不是單純的 stale-ID bug，而是 abstraction boundary 放錯。Discovery 的排序位置被帶進了 mutation contract，後續工程只好維護 pool、generation、matches、pending、receipt 與跨輪恢復的一致性。

更小也更可靠的邊界是：

```text
自然語言作品指涉
  -> self-contained WorkIntent
  -> fresh bounded resolution
  -> blocking work/version validation
  -> DOI or authoritative no-DOI serialization
  -> atomic persistence + stable SourceRef
```

這不承諾完美 matching；它把不可避免的不確定性放在可見的 resolution/abstention 階段，避免把不確定性藏在 `c1` 指向誰的 session state 裡。詳細 migration、相容性與測試順序記錄於 `plan.md`。

## 外部參考

- DOI Foundation, [DOI Handbook](https://www.doi.org/the-identifier/resources/handbook/)：DOI system、metadata 與 Registration Agency 的權責。
- DOI Foundation, [DOI FAQs](https://www.doi.org/the-identifier/resources/faqs)：DOI system 不提供涵蓋所有 DOI 的中央搜尋；reverse lookup 通常是 RA/其他服務的 value-added function。
- DOI Foundation, [What Are Registration Agencies?](https://www.doi.org/the-community/what-are-registration-agencies/)：不同 RA 服務不同社群並維護各自 metadata service。
- Crossref, [Content negotiation](https://www.crossref.org/documentation/retrieve-metadata/content-negotiation/)：透過 `doi.org` 依 DOI 所屬 RA 取得單筆 CSL/BibTeX 等 representation。
- Crossref, [The myth of perfect metadata matching](https://www.crossref.org/blog/the-myth-of-perfect-metadata-matching/)：metadata matching 的不完美、precision/recall 取捨與針對單一案例 overfit 的風險。
- DataCite, [Queries and filtering](https://support.datacite.org/docs/api-queries)：DataCite REST API 的 metadata query 能力。
- DataCite, [Content Negotiation](https://support.datacite.org/docs/datacite-content-resolver)：DataCite DOI 經 `doi.org` 取得 CSL JSON/BibTeX 的流程。
- NeurIPS, [Attention is All you Need](https://proceedings.neurips.cc/paper_files/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html)：官方 2017 proceedings metadata 與 BibTeX。
- arXiv, [Attention Is All You Need](https://arxiv.org/abs/1706.03762)：arXiv manifestation 與 DataCite DOI。
- arXiv, [Auto-Encoding Variational Bayes](https://arxiv.org/abs/1312.6114)：原始 arXiv record 與 DataCite DOI。
