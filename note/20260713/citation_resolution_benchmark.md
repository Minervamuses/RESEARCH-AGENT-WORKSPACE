# Citation resolution baseline

日期：2026-07-13

本報告量的是 checked-in identity regression corpus，不宣稱代表整體文獻
coverage，也不宣稱達到 90%。執行命令：

```bash
cd app
python -m pytest -q tests/test_citation_resolution.py tests/test_citation_work_resolver.py tests/test_citation_authority.py
```

結果：17 個 identity/binding policy cases、7 個 multi-provider resolver cases、
3 個 authority-adapter cases 全數通過。

目前 golden save-eligibility corpus 含 1 個 strong positive 與 2 個已知事故
negative（AIAYN 2025 repost、VAE 2019 monograph）：

```text
auto_resolve_rate: 1/3 = 0.333
auto_save_precision: 1/1 = 1.000
false_save_rate: 0/2 = 0.000 (gold negatives)
clarification/abstention_rate: 2/3 = 0.667
```

這些數字只是一個 correctness baseline；corpus 太小，不能推論 production
coverage。新增 provider/adapter 前應擴充 multilingual、online/print 跨年、
同名異作者、preprint/published 與 timeout/rate-limit cases；release 原則仍是
false-save corpus 必須為零，coverage 不足時 abstain。
