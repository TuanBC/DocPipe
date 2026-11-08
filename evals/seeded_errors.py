"""Governance test: inject known errors into cached extractions and check where each lands.

Uses the page cache from a real run (no extraction calls; only the cheap classification call).
Run (after `python -m docpipe run data/raw/VNM_baocaothuongnien_2025.pdf`):
  uv run --group gateway python evals/seeded_errors.py
"""
import json
import shutil
from pathlib import Path

from docpipe import config, pipeline

PDF = Path("data/raw/VNM_baocaothuongnien_2025.pdf")
SRC_OUT = Path("data/out")
BASE_OUT = Path("data/eval/seeded")


def load_cache(doc_id):
    d = SRC_OUT / "_cache" / doc_id
    return {f.name: json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("page_*.json"))}


def find_item(page, pattern):
    for it in page["items"]:
        if pattern in it["label"].upper():
            return it
    raise KeyError(pattern)


def baseline(c):
    pass


def digit_flip(c):
    it = find_item(c["page_0108.json"], "TỔNG TÀI SẢN")
    it["current"] = float(str(int(it["current"]))[:3] + "1" + str(int(it["current"]))[4:])  # one digit changed


def unit_mismatch(c):
    c["page_0109.json"]["unit"] = "VND"


def fabricated_critical(c):
    find_item(c["page_0108.json"], "TỔNG TÀI SẢN")["prior"] = 99999999.0


def fabricated_noncritical(c):
    c["page_0108.json"]["items"][1]["current"] = 123456789.0  # a value that is not on the page


def kill_switch(c):
    pass


SCENARIOS = [
    ("baseline (no error)", baseline, False, "auto_filed"),
    ("one digit changed in total assets", digit_flip, False, "review"),
    ("unit differs between statement pages", unit_mismatch, False, "review"),
    ("fabricated total assets (prior)", fabricated_critical, False, "review"),
    ("fabricated NON-critical line item", fabricated_noncritical, False, "review"),
    ("kill switch on, clean document", kill_switch, True, "review"),
]


def main():
    cfg = config.load()
    # the scenarios mutate VNM 2025 statement pages 108-110; pick that document by its cache, not "the first state file"
    doc_id = next(d.name for d in sorted((SRC_OUT / "_cache").iterdir()) if (d / "page_0108.json").exists())
    shutil.rmtree(BASE_OUT, ignore_errors=True)
    rows = []
    for n, (name, mutate, kill, expect) in enumerate(SCENARIOS):
        cache = load_cache(doc_id)
        mutate(cache)
        out = BASE_OUT / f"s{n}"
        cdir = out / "_cache" / doc_id
        cdir.mkdir(parents=True)
        for fname, data in cache.items():
            (cdir / fname).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if kill:
            (out / cfg.governance.kill_switch_file).write_text("on")
        cfg.paths.out = str(out)
        res = pipeline.process(PDF, cfg, force=True)
        caught = [r for r in res["reasons"] if r.startswith("validator_failed") or r.startswith("kill")]
        rows.append({"scenario": name, "expected": expect, "decision": res["decision"], "confidence": res["confidence"],
                     "caught_by": [r.split(" (")[0] for r in caught]})
    print(f"{'scenario':42} {'expected':10} {'decision':10} conf   caught_by")
    for r in rows:
        mark = "OK  " if r["expected"] == r["decision"] else "GAP "
        print(f"{mark}{r['scenario']:38} {r['expected']:10} {r['decision']:10} {r['confidence']:<6} {r['caught_by']}")
    Path("data/eval").mkdir(parents=True, exist_ok=True)
    Path("data/eval/seeded_errors.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
