"""End-to-end scan test: build a scanned PDF (no text layer) from real pages and run the full pipeline.

Measures whether model errors on scans are caught by the controls that work without a text layer
(two-pass agreement and the accounting identities). Ground truth = numbers in the ORIGINAL text layer.
Run: uv run --group gateway python -m evals.scan_pipeline
"""
import json
import shutil
from pathlib import Path

import pymupdf

from docpipe import config, pipeline, router
from docpipe.validators import text_numbers
from evals.scan_sim import degrade

SRC = Path("data/raw/VNM_baocaothuongnien_2025.pdf")
PAGES = [1, 108, 109, 110]  # cover + three statements
BASE = Path("data/eval/scan_pipeline")
VARIANTS = {
    "mild": dict(angle=1.2, blur=1.0, noise_mix=0.10, scale=0.67, quality=35),
    "harsh": dict(angle=2.5, blur=1.6, noise_mix=0.18, scale=0.55, quality=25),
}


def build_scan(variant: str, params: dict) -> Path:
    src = pymupdf.open(SRC)
    out = pymupdf.open()
    for p in PAGES:
        page = src[p - 1]
        jpg = degrade(router.render(page, 150), **params)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=jpg)
    path = BASE / f"VNM2025_scan_{variant}.pdf"
    out.save(path)
    return path


def main():
    cfg = config.load()
    src = pymupdf.open(SRC)
    truth = {i + 1: text_numbers(src[p - 1].get_text()) for i, p in enumerate(PAGES)}
    shutil.rmtree(BASE, ignore_errors=True)
    BASE.mkdir(parents=True)
    rows = []
    for variant, params in VARIANTS.items():
        pdf = build_scan(variant, params)
        cfg.paths.out = str(BASE / f"out_{variant}")
        res = pipeline.process(pdf, cfg, force=True)
        wrong = []  # (scan page, value) extracted but not printed on the original page
        nvals = 0
        for pg, ex in res["extraction"].items():
            for it in ex["items"]:
                for v in (it["current"], it["prior"]):
                    if v is None:
                        continue
                    nvals += 1
                    d = str(int(abs(v))).lstrip("0")
                    if d and d not in truth[int(pg)]:
                        wrong.append((int(pg), int(abs(v))))
        flagged = {c["name"]: c["status"] for c in res["checks"] if c["status"] != "skip"}
        agree = next((c for c in res["checks"] if c["name"] == "two_pass_agreement"), None)
        rows.append({"variant": variant, "statement_pages": res["statement_pages"], "values": nvals,
                     "wrong_values": wrong, "decision": res["decision"], "confidence": res["confidence"],
                     "failed_checks": [k for k, s in flagged.items() if s == "fail"],
                     "agreement": agree["detail"] if agree else None, "usage": res["usage"], "seconds": res["seconds"]})
        print(f"\n[{variant}] decision={res['decision']} conf={res['confidence']} statement_pages={res['statement_pages']}")
        print(f"  values={nvals} wrong_vs_original_text={len(wrong)} {wrong[:8]}")
        print(f"  failed checks: {rows[-1]['failed_checks']}")
        print(f"  agreement: {rows[-1]['agreement']}")
        print(f"  usage: {res['usage']} in {res['seconds']}s")
    (BASE / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
