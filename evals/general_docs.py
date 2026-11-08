"""Evaluate OCR, classification, filing and governance on the labelled general-document set.

For each document (see evals/make_eval_set.py): run the full pipeline into a scratch output folder (the publish guard
keeps the real knowledge base untouched), then compare with the labels:
  - OCR: character error rate (CER) and word recall against the printed text (markdown stripped, whitespace
    collapsed), and exact recall of every number/code printed on the page (amounts, tax codes, dates);
  - classification: doc type in the acceptable set, customer company (folder) and year;
  - governance: decision vs expected (auto_filed / review / either), and whether a WRONG result was auto-filed
    (the failure that matters);
  - cost (list price) and wall time per document.

Run: uv run --group gateway python -m evals.general_docs [--set FOLDER] [--out FOLDER] [--report FILE]
Another team points --set at its own folder of samples plus a labels.json in the same format.
"""
import json
import re
import shutil
import time
import unicodedata
from collections import Counter
from pathlib import Path

from docpipe import config, filing, pipeline

SET = Path("data/eval/general_set")
OUT = Path("data/eval/general_out")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[#*|`>_]+", " ", s)          # markdown the OCR prompt may add
    s = re.sub(r"-{3,}|:?-{2,}:?", " ", s)    # table rules
    s = s.replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def lev(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


NUM = re.compile(r"\d[\d.,/\-]*\d|\d")


def ocr_scores(pred: str, truth: str) -> dict:
    p, t = norm(pred), norm(truth)
    words_t, words_p = Counter(t.lower().split()), Counter(p.lower().split())
    nums_t = [n for n in NUM.findall(t) if len(n) >= 4]   # amounts, codes, dates: the values a banker keys
    nums_p = set(NUM.findall(p))
    return {"cer": round(lev(p, t) / max(1, len(t)), 4),
            "word_recall": round(sum((words_t & words_p).values()) / max(1, sum(words_t.values())), 4),
            "numbers": len(nums_t), "numbers_exact": sum(n in nums_p for n in nums_t),
            "numbers_missed": [n for n in nums_t if n not in nums_p]}


def main():
    import argparse
    global SET, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=str(SET), help="folder with the samples and labels.json")
    ap.add_argument("--out", default=str(OUT), help="scratch output folder (wiped)")
    ap.add_argument("--report", default="data/eval/general_docs.json")
    a = ap.parse_args()
    SET, OUT = Path(a.set), Path(a.out)
    cfg = config.load()
    cfg.paths.out = str(OUT)
    shutil.rmtree(OUT, ignore_errors=True)
    labels = json.loads((SET / "labels.json").read_text(encoding="utf-8"))
    rows = []
    for lab in labels:
        src = SET / lab["file"]
        t0 = time.time()
        res = pipeline.process(src, cfg, force=True)
        wall = round(time.time() - t0, 1)
        m = res["meta"]
        doc_id = res["doc_id"]
        pages = sorted((OUT / "_cache" / doc_id).glob("ocr_page_*.json"))
        pred = "\n".join(json.loads(f.read_text(encoding="utf-8"))["text"] for f in pages)
        o = ocr_scores(pred, lab["text"])
        companies = lab["company_slug"] if isinstance(lab["company_slug"], list) else [lab["company_slug"]]
        got_company = filing.slug_company(m["company"]) if m.get("company") else None
        type_ok = m["doc_type"] in lab["doc_types"]
        company_ok = lab["company_slug"] is None or got_company in companies
        year_ok = lab["fiscal_year"] is None or m.get("fiscal_year") == lab["fiscal_year"]
        correct = type_ok and company_ok and year_ok
        decision = res["decision"]
        exp = lab["expected"]
        decision_ok = exp == "either" or (exp == "review") == (decision == "review")
        rows.append({"file": lab["file"], "difficulty": lab["difficulty"], "note": lab["note"],
                     "doc_type": m["doc_type"], "type_ok": type_ok, "company": m.get("company"), "company_slug": got_company,
                     "company_ok": company_ok, "year": m.get("fiscal_year"), "year_ok": year_ok, "correct": correct,
                     "decision": decision, "expected": exp, "decision_ok": decision_ok,
                     "wrong_but_auto_filed": (not correct) and decision != "review",
                     "confidence": res["confidence"], "reasons": res["reasons"], "folder": "/".join(filing.folder_parts(m)),
                     **o, "cost_usd": res["usage"]["cost_usd_list_price"], "model_calls": res["usage"]["calls"],
                     "tokens_in": res["usage"]["tokens_in"], "seconds": wall, "pages": res["total_pages"]})
        r = rows[-1]
        print(f"{'OK ' if correct and decision_ok else 'GAP'} {lab['file']:36} {m['doc_type']:20} {str(got_company):24} "
              f"{m.get('fiscal_year')} {decision:11} cer={o['cer']:.3f} nums={o['numbers_exact']}/{o['numbers']} "
              f"${r['cost_usd']:.5f} {wall}s", flush=True)
    n = len(rows)
    summary = {
        "documents": n,
        "doc_type_accuracy": round(sum(r["type_ok"] for r in rows) / n, 3),
        "company_accuracy": round(sum(r["company_ok"] for r in rows) / n, 3),
        "year_accuracy": round(sum(r["year_ok"] for r in rows) / n, 3),
        "fully_correct": sum(r["correct"] for r in rows),
        "decision_as_expected": sum(r["decision_ok"] for r in rows),
        "auto_filed": sum(r["decision"] != "review" for r in rows),
        "wrong_but_auto_filed": sum(r["wrong_but_auto_filed"] for r in rows),
        "mean_cer": round(sum(r["cer"] for r in rows) / n, 4),
        "median_cer": sorted(r["cer"] for r in rows)[n // 2],
        "mean_word_recall": round(sum(r["word_recall"] for r in rows) / n, 4),
        "numbers_exact": f"{sum(r['numbers_exact'] for r in rows)}/{sum(r['numbers'] for r in rows)}",
        "cost_per_doc_usd": round(sum(r["cost_usd"] for r in rows) / n, 5),
        "seconds_per_doc_mean": round(sum(r["seconds"] for r in rows) / n, 1),
        "seconds_per_doc_max": max(r["seconds"] for r in rows),
        "by_difficulty": {d: {"n": sum(r["difficulty"] == d for r in rows),
                              "correct": sum(r["correct"] for r in rows if r["difficulty"] == d),
                              "auto_filed": sum(r["decision"] != "review" for r in rows if r["difficulty"] == d)}
                          for d in sorted({r["difficulty"] for r in rows})},
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")


if __name__ == "__main__":
    main()
