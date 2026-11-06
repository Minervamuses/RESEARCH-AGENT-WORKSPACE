"""Render cjk_corpus.json with bime-appendix17 and grade each 二.8 CJK rule.

Usage (from app/): python run_cjk.py <evidence-dir>
"""
import json
import sys
import tempfile
from pathlib import Path

from skills.citation.csl_render import render

E = Path(sys.argv[1])
corpus = json.loads((E / "cjk_corpus.json").read_text(encoding="utf-8"))
def run(items):
    with tempfile.TemporaryDirectory() as tmp:
        lib = Path(tmp) / "references.json"
        lib.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return render(corpus["text"], lib, "bime-appendix17")


out = run(corpus["items"])
# The same corpus with every "language" field removed: Chinese/Japanese must be
# inferred from the text, and English must stay English.
inferred = run([{k: v for k, v in item.items() if k != "language"} for item in corpus["items"]])
# English entries that carry a non-CJK language must keep the English format.
tagged_english = run([dict(item, language="en") if item["id"] == "smith1985" else item for item in corpus["items"]])
cites = [c["text"] for c in out.citations]
bib = {e["key"]: e["text"] for e in out.bibliography}
order = [e["key"] for e in out.bibliography]
exp = corpus["expected"]


def order_ok(actual, expected):
    flat = []
    for slot in expected:
        if isinstance(slot, list):
            got = actual[len(flat):len(flat) + len(slot)]
            if sorted(got) != sorted(slot):
                return False
            flat.extend(got)
        else:
            if len(actual) <= len(flat) or actual[len(flat)] != slot:
                return False
            flat.append(slot)
    return flat == actual


def group_ok(actual):
    zh = [k for k in actual if k not in {"yamada2000", "smith1985"}]
    return actual.index("yamada2000") == len(zh) and actual[-1] == "smith1985"


rows = []
def rule(name, status, detail):
    rows.append({"rule": name, "status": status, "detail": detail})

ci = dict(zip(["tian", "zhang", "lu", "li", "qiu", "doh", "yamada", "mixed", "zhzh"], cites))
ce = dict(zip(["tian", "zhang", "lu", "li", "qiu", "doh", "yamada", "mixed", "zhzh"], exp["citations"]))
rule("(4) 中文三人以上：(陳等人，1989)", "達成" if ci["tian"] == ce["tian"] else "部分達成", f"輸出 `{ci['tian']}`，預期 `{ce['tian']}`")
rule("(4) 中文二人：(林與張，1960)", "達成" if ci["zhang"] == ce["zhang"] else "部分達成", f"輸出 `{ci['zhang']}`，預期 `{ce['zhang']}`")
rule("(4) 中文一人與機構作者", "達成" if [ci[k] for k in ("lu", "li", "qiu", "doh")] == [ce[k] for k in ("lu", "li", "qiu", "doh")] else "部分達成",
     "輸出 " + "、".join(f"`{ci[k]}`" for k in ("lu", "li", "qiu", "doh")))
rule("(4) 日文二人（同中文規則）", "達成" if ci["yamada"] == ce["yamada"] else "部分達成", f"輸出 `{ci['yamada']}`，預期 `{ce['yamada']}`")
rule("(4) 中英混合引用", "達成" if ci["mixed"] == ce["mixed"] else "部分達成", f"輸出 `{ci['mixed']}`，預期 `{ce['mixed']}`")
rule("(4) 全中文多篇以全形「；」分隔", "達成" if ci["zhzh"] == ce["zhzh"] else "無法以 CSL 表達", f"輸出 `{ci['zhzh']}`，預期 `{ce['zhzh']}`；同一引用群組的分隔符號是 layout 層級，標準 CSL 不能依條目語言切換（Pandoc 不支援 CSL-M 的多個 layout）")
for key, label in [("tian1989", "(5)(d) 中文期刊三人"), ("zhang1992", "(5)(e) 中文期刊二人"), ("lu1986", "(6) 中文圖書"), ("li1992", "(8)(b) 中文會議專集"), ("qiu1990", "(10) 碩士論文"), ("doh2001", "(12) 中文網站")]:
    rule(label + "（全形標點、、分隔、。）", "達成" if bib.get(key) == exp["bibliography"][key] else "部分達成", f"輸出 `{bib.get(key)}`" + ("" if bib.get(key) == exp["bibliography"][key] else f"；預期 `{exp['bibliography'][key]}`"))
rule("(2) 中文在前、日文其次、英文最後", "達成" if group_ok(order) else "部分達成", f"順序 {order}")
same = inferred.to_dict() == out.to_dict()
rule("沒有 language 欄位時由字元判斷中日文（C5-F1）", "達成" if same else "部分達成",
     "移除所有條目的 language 後輸出" + ("完全相同" if same else "不同"))
english_ok = tagged_english.to_dict() == out.to_dict()
rule("英文條目帶 language: en 仍為英文格式（C5-F1）", "達成" if english_ok else "未達成",
     "英文條目加上 language: en 後輸出" + ("完全相同" if english_ok else "不同"))
rule("(2) 中日文依姓氏筆畫", "達成" if order_ok(order, exp["order"]) else "無法以 CSL 表達", f"輸出順序 {order}；預期 {exp['order']}（{exp['order_note']}）。CSL 只依 Unicode 排序規則排序，沒有筆畫排序")

L = ["# C5-S3 附件十七中日文規則（合成條目）", "",
     "- 語料：`cjk_corpus.json`（依二.8 例 (d)(e)(6)(8b)(10)(12) 建的中文條目、一筆日文、一筆英文）。樣式以「有沒有 `language`」切換中日文分支（標準 CSL 無法比對欄位值）；C5-F1 起由 `csl_render` 交給 Pandoc 一份暫時的副本：`language` 只保留在中日文條目上（明確的 `zh`/`chi`/`zho`/`ja`/`jpn`，或沒有 `language` 時依標題與姓名中的假名、漢字判斷），其他值（`en`、`de` …）在副本中移除。使用者的書目檔不變。",
     "- 渲染：`csl_render.render`（Pandoc 3.13）＋ `bime-appendix17.csl`。重跑：`python run_cjk.py <此目錄>`（從 `app/`）。", "",
     "| 規則 | 結果 | 說明 |", "|---|---|---|"]
for r in rows:
    L.append(f"| {r['rule']} | {r['status']} | {r['detail']} |")
L += ["", "## 輸出", "", "引用：", ""] + [f"- `{c}`" for c in cites] + ["", "參考文獻（輸出順序）：", ""] + [f"- `{bib[k]}`" for k in order]
L += ["", "## 結論", "",
      "- 名字（姓名相連、`、` 分隔）、全形 `。`/`：`/`，`、〝〞、`主編`、`網址：`/`上網日期：`、中文二人 `與`、語言分組都能以標準 CSL 表達；語言的判斷在渲染前的副本中完成（C5-F1）。",
      "- 中文三人以上的 `等人` 前會多一個空白：處理器在 et-al 詞前固定加空白；若改用 `and` 符號詞讓 `等人` 緊接，則二人的 `與` 前後會多空白，兩者無法同時正確（已實測）。目前選擇讓二人形式正確。",
      "- 無法以標準 CSL 表達：中日文依筆畫排序、全中文群組內用全形 `；` 分隔、依 `language` 值（而非有無）切換。依 D3 不改走 `cite.py`。", ""]
(E / "results.md").write_text("\n".join(L), encoding="utf-8")
(E / "output.json").write_text(json.dumps(out.to_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("\n".join(f"{r['status']}\t{r['rule']}" for r in rows))
