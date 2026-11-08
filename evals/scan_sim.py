"""Scan-simulation evaluation.

Born-digital PDFs carry a text layer, which gives free ground truth for the numbers on a page.
We render each statement page clean and degraded (skew, blur, noise, low resolution, JPEG) and
measure what the model extracts from the IMAGE against that text layer.

Metrics per condition:
  precision  = share of extracted numbers that are printed on the page (1 - fabrication rate)
  recall     = share of the page's numbers (>= 4 digits) that the model extracted
  exact_pages = pages with zero unsupported numbers
Run: uv run --group gateway python -m evals.scan_sim [--workers 4]
"""
import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter

from docpipe import config, llm, router
from docpipe.extract import PAGE_PROMPT
from docpipe.models import PageExtraction
from docpipe.validators import text_numbers

PDFS = ["data/raw/VNM_baocaothuongnien_2025.pdf", "data/raw/VNM_baocaothuongnien_2024.pdf"]
OUT = Path("data/eval/scan_sim")
MIN_DIGITS = 4  # ignore page numbers, note references and small counts when computing recall


def degrade(png: bytes, angle=1.2, blur=1.0, noise_mix=0.10, scale=0.67, quality=35) -> bytes:
    img = Image.open(io.BytesIO(png)).convert("L")
    img = img.rotate(angle, expand=True, fillcolor=255, resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(blur))
    noise = Image.effect_noise(img.size, 18)
    img = Image.blend(img, noise, noise_mix)
    w, h = img.size
    img = img.resize((int(w * scale), int(h * scale)), Image.BILINEAR)  # 0.67 ~ 100 dpi
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def values(ex: PageExtraction):
    out = []
    for it in ex.items:
        for v in (it.current, it.prior):
            if v is not None and int(abs(v)) != 0:
                out.append(str(int(abs(v))))
    return out


def run_one(job):
    cfg, pdf, page_no, cond = job
    cache = OUT / f"{Path(pdf).stem}_p{page_no}_{cond}.json"
    doc = pymupdf.open(pdf)
    page = doc[page_no - 1]
    truth = {d for d in text_numbers(page.get_text()) if len(d) >= MIN_DIGITS}
    if cache.exists():
        rec = json.loads(cache.read_text(encoding="utf-8"))
        rec["cached"] = True
        return rec
    png = router.render(page, cfg.model.render_dpi)
    img = png if cond == "clean" else degrade(png)
    usage = llm.Usage()
    t0 = time.time()
    try:
        ex = llm.call(cfg.model, PAGE_PROMPT, PageExtraction, images=[img], usage=usage, step=f"eval_{cond}")
    except llm.LLMError as e:
        return {"pdf": pdf, "page": page_no, "cond": cond, "error": str(e)[:200]}
    got = values(ex)
    got_set = {g for g in got}
    unsupported = [g for g in got if g not in text_numbers(page.get_text())]
    rec = {
        "pdf": pdf, "page": page_no, "cond": cond, "n_values": len(got), "n_truth": len(truth),
        "unsupported": unsupported, "missed": sorted(truth - got_set)[:10], "n_missed": len(truth - got_set),
        "tokens_in": usage.tokens_in, "tokens_out": usage.tokens_out, "seconds": round(time.time() - t0, 1),
        "cost_usd": round(usage.cost_usd(cfg.model), 5),
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def main():
    cfg = config.load()
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else cfg.model.workers
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for pdf in PDFS:
        doc = pymupdf.open(pdf)
        pages = router.route(doc, cfg, llm.Usage())
        print(pdf, "statement pages:", pages)
        for p in pages:
            for cond in ("clean", "degraded"):
                jobs.append((cfg, pdf, p, cond))
    with ThreadPoolExecutor(workers) as ex:
        recs = list(ex.map(run_one, jobs))

    print(f"\n{'cond':9} {'pages':>5} {'values':>6} {'precision':>9} {'recall':>7} {'exact_pages':>11} {'s/page':>6} {'$/page':>8}")
    summary = {}
    for cond in ("clean", "degraded"):
        rs = [r for r in recs if r["cond"] == cond and "error" not in r]
        errs = [r for r in recs if r["cond"] == cond and "error" in r]
        nv = sum(r["n_values"] for r in rs)
        nu = sum(len(r["unsupported"]) for r in rs)
        nt = sum(r["n_truth"] for r in rs)
        nm = sum(r["n_missed"] for r in rs)
        exact = sum(1 for r in rs if not r["unsupported"])
        s = {"pages": len(rs), "errors": len(errs), "values": nv, "unsupported": nu,
             "precision": round(1 - nu / nv, 4) if nv else None,
             "recall": round(1 - nm / nt, 4) if nt else None, "exact_pages": f"{exact}/{len(rs)}",
             "sec_per_page": round(sum(r["seconds"] for r in rs) / max(len(rs), 1), 1),
             "usd_per_page": round(sum(r["cost_usd"] for r in rs) / max(len(rs), 1), 5)}
        summary[cond] = s
        print(f"{cond:9} {s['pages']:>5} {nv:>6} {s['precision']:>9} {s['recall']:>7} {s['exact_pages']:>11} "
              f"{s['sec_per_page']:>6} {s['usd_per_page']:>8}" + (f"  ({len(errs)} errors)" if errs else ""))
    print("\nfailure cases (unsupported values):")
    for r in recs:
        if "error" in r:
            print(f"  {Path(r['pdf']).stem} p{r['page']} {r['cond']}: ERROR {r['error']}")
        elif r["unsupported"]:
            print(f"  {Path(r['pdf']).stem} p{r['page']} {r['cond']}: unsupported={r['unsupported'][:6]}")
    (OUT.parent / "scan_sim_summary.json").write_text(json.dumps({"summary": summary, "records": recs}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
