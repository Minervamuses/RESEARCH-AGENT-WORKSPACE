# `repair_temp` 實機使用者試用：十次單篇引用

- 日期：2026-07-23
- Branch：`repair_temp`
- 試用規則：每個使用者請求只允許引用一篇；連續提出十個獨立請求。
- 啟動方式：在 WSL 中執行 `conda activate app`，進入 `app/` 後執行 `python -m agent.cli.chat`。
- 沒有執行 pytest 或其他一般測試。

## 更正說明

前一版報告把十篇放在同一個請求中，違反本專案「一次只請求一篇引用」的使用規則，因此該輪批次失敗不能用來判定功能品質。本報告以正確規則重新試用，取代前一版結論。

## 試用前清理

先確認 workspace root 的 `cite/` 只有引用 bundle 與 `.locks`，再刪除其中全部內容：

- 12 個既有引用 bundle
- 13 個 lock files

保留空的 `cite/` 目錄，確保本輪結果全部由此次正式 CLI 互動產生。

## 啟動結果

CLI 在 `app` Conda environment 中正常啟動：

```text
Agent Chat (LangGraph mode). Type 'q' to quit.
Mode: default
MCP: web_search
```

第一個回合使用 `/citation <請求>` 啟用 citation skill；之後 citation skill 持續生效，其餘九個回合都以一般自然語言提出單篇請求。

每個請求都包含一篇論文的完整標題、年份、arXiv ID，並明確指定要保存預印本版本。每次收到 CLI 成功回覆後，立即從另一個 shell 核對 `cite/` bundle 數量、回覆 source ID、metadata identity 與 `reference.bib`。

## 十個獨立回合

| 回合 | 論文 | 指定 arXiv | CLI source ID | 回合後 bundle 數 | 即時磁碟核對 |
|---:|---|---|---|---:|---|
| 1 | Attention Is All You Need | `1706.03762` | `src-a1a0262a54cd` | 1 | 相符 |
| 2 | BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding | `1810.04805` | `src-955cabf3213d` | 2 | 相符 |
| 3 | Generative Adversarial Nets | `1406.2661` | `src-346c058b588d` | 3 | 相符 |
| 4 | Auto-Encoding Variational Bayes | `1312.6114` | `src-03271ba130d4` | 4 | 相符 |
| 5 | Denoising Diffusion Probabilistic Models | `2006.11239` | `src-78296905fc8e` | 5 | 相符 |
| 6 | Language Models are Few-Shot Learners | `2005.14165` | `src-49ea3576b0f1` | 6 | 相符 |
| 7 | Neural Machine Translation by Jointly Learning to Align and Translate | `1409.0473` | `src-241de20942a5` | 7 | 相符 |
| 8 | Sequence to Sequence Learning with Neural Networks | `1409.3215` | `src-d01e8a1640b7` | 8 | 相符 |
| 9 | An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale | `2010.11929` | `src-191d18337a0b` | 9 | 相符 |
| 10 | Adam: A Method for Stochastic Optimization | `1412.6980` | `src-6d41d2f09c02` | 10 | 相符 |

十個回合的 CLI 都回覆「已保存」，並提供 source ID、title、year、type、bundle path 與 `[[cite:...]]` 標記。沒有出現：

- `intent_binding_ambiguous`
- `multiple_plausible_records`
- `version_clarification_required`
- `raw_doi` gate error
- 宣稱成功但磁碟沒有產物
- 指定 arXiv identity 被換成其他版本

觀察到每篇通常會執行 2 至 3 次 `citation_workflow` 呼叫；單篇等待時間約 20 至 40 秒。期間只有 tool-call 狀態，沒有細分的解析進度，但沒有卡死或中斷。

## 最終完整性核對

正式輸入 `/exit` 正常結束 CLI 後，重新掃描全部十份 bundle：

- bundle 數：10
- `citation.json`：10/10 存在且可解析
- `reference.bib`：10/10 存在且非空
- metadata identity：10/10 與各回合指定 arXiv ID 相同
- source ID：10/10 與 CLI 回覆相同
- BibTeX SHA-256：10/10 與 `citation.json` 的 `artifact_hashes.reference.bib` 相同
- `.locks`：10 個，與十份保存結果對應

| Source ID | Metadata title | arXiv identity | BibTeX bytes | Hash |
|---|---|---|---:|---|
| `src-a1a0262a54cd` | Attention Is All You Need | `1706.03762` | 348 | 相符 |
| `src-955cabf3213d` | BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding | `1810.04805` | 326 | 相符 |
| `src-346c058b588d` | Generative Adversarial Networks | `1406.2661` | 361 | 相符 |
| `src-03271ba130d4` | Auto-Encoding Variational Bayes | `1312.6114` | 237 | 相符 |
| `src-78296905fc8e` | Denoising Diffusion Probabilistic Models | `2006.11239` | 255 | 相符 |
| `src-49ea3576b0f1` | Language Models are Few-Shot Learners | `2005.14165` | 807 | 相符 |
| `src-241de20942a5` | Neural Machine Translation by Jointly Learning to Align and Translate | `1409.0473` | 297 | 相符 |
| `src-d01e8a1640b7` | Sequence to Sequence Learning with Neural Networks | `1409.3215` | 274 | 相符 |
| `src-191d18337a0b` | An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale | `2010.11929` | 500 | 相符 |
| `src-6d41d2f09c02` | Adam: A Method for Stochastic Optimization | `1412.6980` | 246 | 相符 |

## 成果判定

在「一次只請求一篇」的正式使用規則下，本輪結果為 **PASS：10/10**。

實際使用者可以啟用 citation skill 後，連續提出單篇引用請求；每篇都能取得可用引用標記，且 CLI 回覆、metadata、BibTeX 與磁碟狀態一致。先前批次測試中觀察到的歧義與假成功，這次遵守單篇規則後都沒有重現。

仍有兩項使用體驗上的非阻斷問題：

1. 每篇約需 20 至 40 秒，十篇總體等待時間明顯。
2. 使用者只看到工作流呼叫開始與返回，沒有更具體的查找、驗證、保存進度。

本試用驗證的是 `repair_temp` 上正式程式啟動與既有 citation 單篇流程，沒有直接執行 Extension-Management 的 drop-in 增、改、刪，因此不把本結果延伸解讀為 extension 管理功能本身的完整驗收。
