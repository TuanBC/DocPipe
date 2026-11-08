"""Cross-document tie-out: the prior-year column of year N must equal the current-year column of year N-1.

Works on the sidecars/review items already produced by the pipeline. A mismatch is either a restatement or an
extraction error; both need a human. This is a KB-level check no single-document validator can do.
Run: uv run python -m evals.cross_period [data/out]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

from docpipe.filing import slug_company
from docpipe.models import PageExtraction
from docpipe.validators import find

KEYS = ["total_assets", "total_le", "revenue", "gross_profit", "pbt", "net_profit", "cash_close"]


def load(out: Path):
    docs = []
    for f in list((out / "filed").rglob("*.json")) + list((out / "_review").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        r = d.get("result", d)
        docs.append(r)
    return docs


def items_of(r):
    items = []
    for ex in r["extraction"].values():
        items += PageExtraction.model_validate(ex).items
    return items


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/out")
    groups = defaultdict(dict)
    for r in load(out):
        m = r["meta"]
        if m.get("fiscal_year") and m.get("period") == "FY":
            groups[(slug_company(m["company"]), m.get("scope"))][m["fiscal_year"]] = r
    n_ok = n_bad = 0
    for (company, scope), years in sorted(groups.items()):
        for y in sorted(years):
            if y - 1 not in years:
                continue
            cur, prev = items_of(years[y]), items_of(years[y - 1])
            for k in KEYS:
                a, b = find(prev, k), find(cur, k)
                if a is None or b is None or a.current is None or b.prior is None:
                    continue
                ok = abs(a.current - b.prior) <= 2
                n_ok += ok
                n_bad += not ok
                print(f"[{'OK ' if ok else 'DIFF'}] {company} {scope} FY{y - 1} current vs FY{y} prior  {k}: "
                      f"{a.current:,.0f} vs {b.prior:,.0f}")
    print(f"\n{n_ok} tie, {n_bad} differ")


if __name__ == "__main__":
    main()
