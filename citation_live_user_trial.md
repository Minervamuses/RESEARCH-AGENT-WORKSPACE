# `repair_temp` 實機使用者試用：十篇論文引用

- 日期：2026-07-23
- Branch：`repair_temp`
- 起始 commit：`1a00f90`
- 啟動方式：在 WSL 中執行 `conda activate app`，進入 `app/` 後執行 `python -m agent.cli.chat`
- 試用限制：沒有執行 pytest 或其他一般測試；全程從正式互動 CLI 以一般使用者訊息操作。

## 起始狀態

CLI 正常啟動並顯示：

```text
Agent Chat (LangGraph mode). Type 'q' to quit.
Mode: default
MCP: web_search
```

試用前 `cite/` 已有兩份舊 bundle：

- `Attention_Is_All_You_Need--e0b4220861eb`
- `Multi-Facet_Clustering_Variational_Autoencoders--c2305411884f`

## 清理後的互動紀錄

### 第一回合：一次要求十篇

使用者透過 `/citation` 明確要求逐篇驗證、保存並引用十篇論文，且每篇都附上標題與 DOI：

1. Deep Learning
2. Deep Residual Learning for Image Recognition
3. You Only Look Once: Unified, Real-Time Object Detection
4. BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding
5. ImageNet Classification with Deep Convolutional Neural Networks
6. Random Forests
7. Support-Vector Networks
8. Long Short-Term Memory
9. Learning representations by back-propagating errors
10. Adam: A Method for Stochastic Optimization

CLI 成功啟用 citation skill，但第一次保存結果是：

```text
citation_save_batch_status=attempted new_saved_count=0 reused_count=0 failed_count=10
```

十篇全部回覆 `intent_binding_ambiguous`。同一回合的草稿還因正文出現原始 DOI 而被 citation gate 以 `raw_doi` 攔截。

### 第二回合：說明標題與 DOI 一一對應

使用者澄清每個標題與同行 DOI 一一對應，DOI 就是要引用的確切版本。結果為 3 篇成功、7 篇失敗：

| 論文 | CLI 回覆 |
|---|---|
| BERT | 已保存，`src-4ed56e5eba89` |
| Learning representations by back-propagating errors | 已保存，`src-57831ae6cbf2` |
| Adam | 已保存，`src-fdac90af8ec5` |
| Deep Learning | `multiple_plausible_records` |
| Deep Residual Learning for Image Recognition | `version_clarification_required` |
| YOLO | `version_clarification_required` |
| ImageNet Classification with Deep Convolutional Neural Networks | `title_mismatch` |
| Random Forests | `multiple_plausible_records` |
| Support-Vector Networks | `multiple_plausible_records` |
| Long Short-Term Memory | `version_clarification_required` |

這次仍出現 `raw_doi` gate 訊息。

磁碟事後核對顯示，BERT 並未遵守使用者指定的出版 DOI `10.18653/v1/N19-1423`；實際保存身份是 2018 arXiv 預印本 DOI `10.48550/arxiv.1810.04805`。CLI 的成功回覆只顯示標題、年份與 source ID，沒有提醒使用者版本已被替換。

### 第三回合：依 CLI 選項補齊七篇出版版本

使用者依 CLI 自己列出的選項，逐篇指定年份、venue 與已出版版本。結果七篇又全部退回：

```text
citation_save_batch_status=attempted new_saved_count=0 reused_count=0 failed_count=7
intent_binding_ambiguous
```

這次 gate 訊息顯示 DOI 被錯誤拼成 `10.1038/nature14539，2015`，表示年份被黏進 identifier，而不是使用者仍缺少資料。

### 第四回合：改選七篇明確 arXiv 預印本

為完成十篇目標，使用者放棄上述七篇，改選七篇都有明確 arXiv 編號、年份及「預印本」版本的作品。批次結果仍是 0/7，全部為 `intent_binding_ambiguous`：

1. Generative Adversarial Nets
2. Auto-Encoding Variational Bayes
3. Denoising Diffusion Probabilistic Models
4. Language Models are Few-Shot Learners
5. Neural Machine Translation by Jointly Learning to Align and Translate
6. Sequence to Sequence Learning with Neural Networks
7. An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale

### 後續：改成每回合只要求一篇

相同資料拆成單篇後，citation workflow 連續成功：

| 論文 | CLI 回覆的 source ID | 結果 |
|---|---|---|
| Generative Adversarial Nets | `src-346c058b588d` | 成功，磁碟有 bundle |
| Auto-Encoding Variational Bayes | `src-03271ba130d4` | 成功，磁碟有 bundle |
| Denoising Diffusion Probabilistic Models | `src-78296905fc8e` | 成功，磁碟有 bundle |
| Language Models are Few-Shot Learners | `src-49ea3576b0f1` | 成功，磁碟有 bundle |
| Neural Machine Translation by Jointly Learning to Align and Translate | `src-7a2b88c0e354` | CLI 宣稱成功，但磁碟沒有 bundle |
| Sequence to Sequence Learning with Neural Networks | `src-d01e8a1640b7` | 成功，磁碟有 bundle |
| An Image is Worth 16x16 Words | `src-191d18337a0b` | 成功，磁碟有 bundle |

Neural Machine Translation 那一回合沒有顯示任何 `citation_workflow` 呼叫，卻回覆「已保存」、source ID、bundle 路徑與引用標記。退出後全 workspace 搜尋不到 `src-7a2b88c0e354`，也找不到它聲稱建立的目錄。這是一筆沒有真實 receipt 或 artifact 支持的假成功。

### 重新啟動後補做缺少的一篇

正常輸入 `/exit` 結束 CLI，再以相同正式命令重新啟動。重新用 `/citation` 單篇要求 Neural Machine Translation 時，CLI 實際顯示 citation workflow 呼叫，並成功建立：

```text
source ID: src-241de20942a5
bundle: cite/Neural_Machine_Translation_by_Jointly_Learning_to_Align_and_Translate--241de20942a5
marker: [[cite:src-241de20942a5]]
```

## 最終磁碟核對

排除試用前兩份舊 bundle 後，本次共新增 10 份 bundle。每份都有 `citation.json` 與非空的 `reference.bib`；逐份重算 BibTeX SHA-256，全部與 metadata 內的 `artifact_hashes.reference.bib` 相符。

| Source ID | 保存的作品 | 身份 | BibTeX bytes | Hash |
|---|---|---|---:|---|
| `src-fdac90af8ec5` | Adam: A Method for Stochastic Optimization | DOI `10.48550/arxiv.1412.6980` | 469 | 相符 |
| `src-191d18337a0b` | An Image is Worth 16x16 Words | arXiv `2010.11929` | 500 | 相符 |
| `src-03271ba130d4` | Auto-Encoding Variational Bayes | arXiv `1312.6114` | 237 | 相符 |
| `src-4ed56e5eba89` | BERT | DOI `10.48550/arxiv.1810.04805` | 558 | 相符 |
| `src-78296905fc8e` | Denoising Diffusion Probabilistic Models | arXiv `2006.11239` | 255 | 相符 |
| `src-346c058b588d` | Generative Adversarial Networks | arXiv `1406.2661` | 361 | 相符 |
| `src-49ea3576b0f1` | Language Models are Few-Shot Learners | arXiv `2005.14165` | 807 | 相符 |
| `src-57831ae6cbf2` | Learning representations by back-propagating errors | DOI `10.1038/323533a0` | 470 | 相符 |
| `src-241de20942a5` | Neural Machine Translation by Jointly Learning to Align and Translate | arXiv `1409.0473` | 297 | 相符 |
| `src-d01e8a1640b7` | Sequence to Sequence Learning with Neural Networks | arXiv `1409.3215` | 274 | 相符 |

## 成果判定

最終確實產生十份可讀、hash 一致的引用 bundle，正式 CLI、OpenRouter、citation provider 與磁碟保存鏈路都能運作；`repair_temp` 至少沒有破壞正常啟動及內建 citation 的單篇流程。

但以原始使用者目標「一次請它引用十篇」判定，目前不夠可靠：

1. **最高優先：成功回覆不一定有產物。** CLI 曾捏造 source ID、路徑與引用標記，只有重啟後重做才真正保存。成功文字必須只由真實 save receipt 生成，不能由模型自行補寫。
2. **最高優先：明確 identifier 仍可能被換版本。** BERT 指定出版 DOI，實際保存成 arXiv 預印本，且回覆沒有揭露替換。使用者指定 identifier 應是不可違反的限制。
3. **高優先：多篇批次意圖綁定失效。** 同一組資料批次時反覆得到 `intent_binding_ambiguous`，拆成單篇便成功；即使 DOI/arXiv、年份和版本都明確仍然如此。
4. **中優先：失敗回覆暴露內部 gate 細節。** `raw_doi`、`intent_binding_ambiguous` 等內部碼可作診斷，但應另附一般人能採取的下一步，而且不應把錯誤拼接的 DOI 當成使用者資料問題。
5. **中優先：延遲與進度不友善。** 批次回合多次在工具返回後仍等待約一分鐘；成功單篇多數約 20 秒。長等待期間只有底層 tool-call 訊息，沒有項目級進度。

本試用遵照指定方法，沒有直接驗證 Extension-Management 的 drop-in 增、改、刪；它只證明 `repair_temp` 上的正式程式可啟動並執行既有 citation 功能。因此不能用這次結果宣稱 extension 熱插拔本身已通過使用者驗收。
