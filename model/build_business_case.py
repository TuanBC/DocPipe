"""Generate model/business_case.xlsx (12-month business case) and model/business_case_summary.json.

Run: uv run python model/build_business_case.py

Two workflows, one tool:
  A. Financial-statement spreading (corporate credit): read the statements, key line items, check them.
  B. Onboarding / credit-file documents (registration, contracts, invoices, collateral, resolutions, tax, bank
     statements): read, classify, name and file the document, and answer later questions about it.

Every input carries a source tag:
  MEASURED  from the prototype's evaluations (docs/eval-results.md), small synthetic or public samples
  PUBLIC    a public range (vendor material, incentive to inflate); brackets the input, not evidence about the bank
  ASSUMED   a placeholder to replace with pilot / interview data before anyone quotes an output
Outputs are Excel formulas, so changing an input recalculates everything, including the sensitivity tables.
"""
import json
from pathlib import Path

import xlsxwriter

ROOT = Path(__file__).resolve().parent
EVAL = ROOT.parent / "data" / "eval" / "general_docs.json"

# measured values (fallbacks = numbers recorded in docs/eval-results.md)
measured = {"b_auto_share": 0.75, "b_cost_doc_usd": 0.0012, "b_seconds": 12.0}
if EVAL.exists():
    s = json.loads(EVAL.read_text(encoding="utf-8"))["summary"]
    measured = {"b_auto_share": round(s["auto_filed"] / s["documents"], 2), "b_cost_doc_usd": s["cost_per_doc_usd"],
                "b_seconds": s["seconds_per_doc_mean"]}

# key: (label, value, unit, source)
INPUTS = [
    # A. financial statements
    ("a_docs", "A. Statement files per month (one borrower-year each)", 600, "docs", "ASSUMED"),
    ("a_manual_min", "A. Manual minutes per file (find pages, key, check)", 60, "min", "PUBLIC range 30-360 min/spread; ASSUMED low end"),
    ("a_auto_share", "A. Share auto-filed, no human touch", 0.60, "ratio", "MEASURED 11/14 docs on dev set; ASSUMED lower for real mix"),
    ("a_review_min", "A. Minutes to review a flagged file (page shown next to value)", 15, "min", "ASSUMED"),
    ("a_cost_doc_usd", "A. Model cost per file (router keeps ~3 of 100+ pages)", 0.004, "USD", "MEASURED $0.0013/page x ~3 pages"),
    # B. onboarding / credit-file documents
    ("b_docs", "B. Onboarding / credit-file documents per month", 4000, "docs", "ASSUMED"),
    ("b_manual_min", "B. Manual minutes per document (read, classify, rename, file, key header fields)", 6, "min", "ASSUMED; time it in week 1"),
    ("b_auto_share", "B. Share auto-filed, no human touch", min(0.70, measured["b_auto_share"]), "ratio",
     f"MEASURED {measured['b_auto_share']:.0%} on 16 synthetic scans; discounted to 70% for real-world mix"),
    ("b_review_min", "B. Minutes to review a flagged document", 2, "min", "ASSUMED"),
    ("b_cost_doc_usd", "B. Model cost per document", measured["b_cost_doc_usd"], "USD", "MEASURED (list price)"),
    # shared
    ("audit_min", "Audit-sample minutes per auto-filed document (5% sampled x 10 min)", 0.5, "min", "ASSUMED policy"),
    ("hourly_cost", "Loaded cost per staff hour", 250000, "VND", "ASSUMED"),
    ("err_before", "A. Critical-field error rate, manual keying", 0.02, "ratio", "ASSUMED; measure in shadow pilot"),
    ("err_after", "A. Critical-field error rate, tool + review", 0.005, "ratio", "ASSUMED; seeded-error eval 6/6 caught, no real-volume data"),
    ("cost_per_error", "Cost of one critical error reaching a credit memo (rework, delay)", 2000000, "VND", "ASSUMED"),
    ("fx", "VND per USD", 26000, "VND", "ASSUMED"),
    ("fixed_month", "Run cost per month (hosting, model endpoint, 0.5 FTE support)", 60000000, "VND", "ASSUMED"),
    ("one_off", "One-off build and rollout (3 months, team of 5, part time)", 900000000, "VND", "ASSUMED"),
]
V = {k: v for k, _, v, _, _ in INPUTS}


def outputs(v, a_share=None, b_share=None, a_min=None, b_min=None):
    a_share = v["a_auto_share"] if a_share is None else a_share
    b_share = v["b_auto_share"] if b_share is None else b_share
    a_min = v["a_manual_min"] if a_min is None else a_min
    b_min = v["b_manual_min"] if b_min is None else b_min
    a_before = v["a_docs"] * a_min / 60
    a_after = v["a_docs"] * ((1 - a_share) * v["a_review_min"] + a_share * v["audit_min"]) / 60
    b_before = v["b_docs"] * b_min / 60
    b_after = v["b_docs"] * ((1 - b_share) * v["b_review_min"] + b_share * v["audit_min"]) / 60
    hours_saved = a_before - a_after + b_before - b_after
    labour = hours_saved * v["hourly_cost"]
    errors = v["a_docs"] * (v["err_before"] - v["err_after"]) * v["cost_per_error"]
    model = (v["a_docs"] * v["a_cost_doc_usd"] + v["b_docs"] * v["b_cost_doc_usd"]) * v["fx"]
    net_month = labour + errors - model - v["fixed_month"]
    return dict(a_before=a_before, a_after=a_after, b_before=b_before, b_after=b_after, hours_saved=hours_saved,
                fte_saved=hours_saved / 160, labour=labour, errors=errors, model=model, net_month=net_month,
                net_12=12 * net_month - v["one_off"], payback=v["one_off"] / net_month if net_month > 0 else None)


wb = xlsxwriter.Workbook(ROOT / "business_case.xlsx")
F = {
    "h": wb.add_format({"bold": True, "bg_color": "#1F3A5F", "font_color": "white", "border": 1, "text_wrap": True}),
    "in": wb.add_format({"bg_color": "#FFF4D6", "border": 1, "num_format": "#,##0.####"}),
    "pct": wb.add_format({"bg_color": "#FFF4D6", "border": 1, "num_format": "0%"}),
    "txt": wb.add_format({"border": 1, "text_wrap": True}),
    "out": wb.add_format({"border": 1, "num_format": "#,##0"}),
    "out1": wb.add_format({"border": 1, "num_format": "#,##0.0"}),
    "pcto": wb.add_format({"border": 1, "num_format": "0%"}),
    "warn": wb.add_format({"bold": True, "font_color": "#B71C1C", "text_wrap": True}),
    "title": wb.add_format({"bold": True, "font_size": 14}),
}
ws = wb.add_worksheet("Model")
ws.set_column("A:A", 64)
ws.set_column("B:B", 18)
ws.set_column("C:C", 8)
ws.set_column("D:D", 58)
ws.write("A1", "DocPipe: 12-month business case (estimate)", F["title"])
ws.merge_range("A2:D2", "ESTIMATE. Inputs tagged ASSUMED are placeholders; MEASURED values come from small synthetic or "
               "public samples. Replace ASSUMED inputs with pilot data before quoting any output.", F["warn"])
ws.set_row(1, 32)
ws.write_row("A4", ["Input", "Value", "Unit", "Source"], F["h"])
for i, (key, label, val, unit, src) in enumerate(INPUTS):
    r = 4 + i
    ws.write(r, 0, label, F["txt"])
    ws.write(r, 1, val, F["pct"] if unit == "ratio" else F["in"])
    ws.write(r, 2, unit, F["txt"])
    ws.write(r, 3, src, F["txt"])
    wb.define_name(key, f"=Model!$B${r + 1}")

base = outputs(V)
r0 = 4 + len(INPUTS) + 2
ws.write_row(r0 - 1, 0, ["Output (per month unless stated)", "Value", "Unit", "How"], F["h"])
OUT_ROWS = [
    ("A. hours before", "=a_docs*a_manual_min/60", "a_before", "hours", "files x manual minutes", "out1"),
    ("A. hours after", "=a_docs*((1-a_auto_share)*a_review_min+a_auto_share*audit_min)/60", "a_after", "hours", "review flagged + audit sample", "out1"),
    ("B. hours before", "=b_docs*b_manual_min/60", "b_before", "hours", "documents x manual minutes", "out1"),
    ("B. hours after", "=b_docs*((1-b_auto_share)*b_review_min+b_auto_share*audit_min)/60", "b_after", "hours", "review flagged + audit sample", "out1"),
    ("Hours saved", "=B{0}-B{1}+B{2}-B{3}", "hours_saved", "hours", "before - after, both workflows", "out1"),
    ("Capacity released (FTE at 160 h/month)", "=B{4}/160", "fte_saved", "FTE", "hours saved / 160", "out1"),
    ("Labour value", "=B{4}*hourly_cost", "labour", "VND", "hours saved x hourly cost", "out"),
    ("Error-cost avoided (A only)", "=a_docs*(err_before-err_after)*cost_per_error", "errors", "VND", "error-rate delta x cost", "out"),
    ("Model cost", "=(a_docs*a_cost_doc_usd+b_docs*b_cost_doc_usd)*fx", "model", "VND", "documents x cost per document", "out"),
    ("Net benefit per month", "=B{6}+B{7}-B{8}-fixed_month", "net_month", "VND", "labour + errors - model - run cost", "out"),
    ("Net benefit, 12 months after one-off", "=12*B{9}-one_off", "net_12", "VND", "12 x monthly - one-off", "out"),
    ("Payback (months)", '=IF(B{9}>0,one_off/B{9},"never")', "payback", "months", "one-off / monthly net", "out1"),
]
rows_at = [r0 + i + 1 for i in range(len(OUT_ROWS))]  # 1-based Excel rows
for i, (label, formula, key, unit, how, fmt) in enumerate(OUT_ROWS):
    r = r0 + i
    ws.write(r, 0, label, F["txt"])
    ws.write_formula(r, 1, formula.format(*rows_at), F[fmt], base[key] if base[key] is not None else "never")
    ws.write(r, 2, unit, F["txt"])
    ws.write(r, 3, how, F["txt"])

# --- what if the assumptions are wrong ---
s0 = r0 + len(OUT_ROWS) + 2
ws.write(s0, 0, "If the assumptions are wrong: 12-month net (VND) by auto-file share (A and B) and manual minutes", F["title"])
shares = [0.2, 0.4, 0.6, 0.8]
mins = [(30, 3), (60, 6), (120, 10)]
ws.write_row(s0 + 1, 0, ["Manual minutes (A / B) \\ auto-file share"] + [f"{int(s * 100)}%" for s in shares], F["h"])
sens = []
for j, (am, bm) in enumerate(mins):
    r = s0 + 2 + j
    ws.write(r, 0, f"A {am} min, B {bm} min", F["txt"])
    row = []
    for k, sh in enumerate(shares):
        o = outputs(V, sh, sh, am, bm)
        net_m = (f"((a_docs*{am}/60-a_docs*((1-{sh})*a_review_min+{sh}*audit_min)/60"
                 f"+b_docs*{bm}/60-b_docs*((1-{sh})*b_review_min+{sh}*audit_min)/60)*hourly_cost"
                 f"+a_docs*(err_before-err_after)*cost_per_error-(a_docs*a_cost_doc_usd+b_docs*b_cost_doc_usd)*fx-fixed_month)")
        ws.write_formula(r, 1 + k, f"=12*{net_m}-one_off", F["out"], o["net_12"])
        row.append(round(o["net_12"] / 1e6))
    sens.append({"manual_min": f"A {am} / B {bm}", "net_12_mVND": row})

# --- scenarios ---
c0 = s0 + 2 + len(mins) + 2
ws.write(c0, 0, "Scenarios", F["title"])
ws.write_row(c0 + 1, 0, ["Scenario", "Auto-file share", "Manual min (A/B)", "12-month net (VND)", "Payback (months)"], F["h"])
SCEN = [("Pessimistic: low automation, fast manual baseline", 0.3, 30, 3),
        ("Base: measured automation discounted, assumed baseline", None, None, None),
        ("Optimistic: high automation, slow manual baseline", 0.85, 120, 10)]
scen_out = []
for i, (name, sh, am, bm) in enumerate(SCEN):
    o = outputs(V, sh, sh, am, bm) if sh is not None else base
    r = c0 + 2 + i
    ws.write(r, 0, name, F["txt"])
    ws.write(r, 1, sh if sh is not None else f"A {V['a_auto_share']:.0%} / B {V['b_auto_share']:.0%}", F["pcto"] if sh else F["txt"])
    ws.write(r, 2, f"{am}/{bm}" if am else f"{V['a_manual_min']}/{V['b_manual_min']}", F["txt"])
    ws.write(r, 3, o["net_12"], F["out"])
    ws.write(r, 4, o["payback"] if o["payback"] else "never", F["out1"])
    scen_out.append({"scenario": name, "net_12_mVND": round(o["net_12"] / 1e6), "payback_months": round(o["payback"], 1) if o["payback"] else None,
                     "fte_saved": round(o["fte_saved"], 1)})

# --- projection at scale (estimate) ---
p0 = c0 + 2 + len(SCEN) + 2
ws.write(p0, 0, "Projection at scale [ESTIMATE]: same per-document economics, more teams", F["title"])
ws.write_row(p0 + 1, 0, ["Rollout", "Volume multiplier vs pilot", "Hours saved / month", "FTE released", "12-month net (VND, one-off unchanged)"], F["h"])
scale = []
for i, (name, mult) in enumerate([("Pilot: one credit team", 0.1), ("One region (base volumes above)", 1.0), ("Bank-wide corporate + SME (ASSUMED 5x)", 5.0)]):
    v2 = {**V, "a_docs": V["a_docs"] * mult, "b_docs": V["b_docs"] * mult,
          "fixed_month": V["fixed_month"] * (0.5 if mult < 1 else mult ** 0.5)}
    o = outputs(v2)
    r = p0 + 2 + i
    ws.write_row(r, 0, [name, mult], F["txt"])
    ws.write(r, 2, o["hours_saved"], F["out"])
    ws.write(r, 3, o["fte_saved"], F["out1"])
    ws.write(r, 4, o["net_12"], F["out"])
    scale.append({"rollout": name, "hours_saved_month": round(o["hours_saved"]), "fte": round(o["fte_saved"], 1),
                  "net_12_mVND": round(o["net_12"] / 1e6)})
ws.write(p0 + 6, 0, "Run cost scales with the square root of volume (shared platform); one-off cost held constant. Estimate only.", F["warn"])
wb.close()

summary = {"inputs": {k: {"value": v, "source": s} for k, _, v, _, s in INPUTS},
           "base": {k: (round(x, 1) if isinstance(x, float) else x) for k, x in base.items()},
           "sensitivity": {"auto_file_shares": shares, "rows": sens}, "scenarios": scen_out, "scale": scale}
(ROOT / "business_case_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved", ROOT / "business_case.xlsx")
print(json.dumps(summary["base"], indent=1))
print(json.dumps(scen_out, indent=1, ensure_ascii=False))
print(json.dumps(scale, indent=1, ensure_ascii=False))
