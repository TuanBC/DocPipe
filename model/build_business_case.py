"""Generate model/business_case.xlsx: a parameterised 12-month business case.

Run: uv run python model/build_business_case.py

Every input below is a PLACEHOLDER ASSUMPTION (not sourced). Replace with interview
or public-source values before quoting any output. Outputs are formulas, so editing
an input in Excel recalculates everything, including the sensitivity table.
"""
from pathlib import Path

import xlsxwriter

# name: (label, value, unit, note)
INPUTS = [
    ("docs_per_month", "Documents per month", 1000, "docs", "ASSUMED"),
    ("pages_total", "Pages per document (whole file)", 80, "pages", "ASSUMED"),
    ("pages_extracted", "Pages sent to extraction after page router", 15, "pages", "ASSUMED"),
    ("manual_min", "Manual minutes per document (read, find, key)", 45, "min", "ASSUMED"),
    ("hourly_cost", "Loaded cost per analyst hour", 150000, "VND", "ASSUMED"),
    ("auto_share", "Share of documents auto-filed (no human touch)", 0.60, "ratio", "ASSUMED; measured in eval"),
    ("review_min", "Review minutes per flagged document", 10, "min", "ASSUMED"),
    ("audit_min", "Audit-sample minutes per auto-filed document", 0.5, "min", "ASSUMED"),
    ("err_before", "Critical-field error rate, manual", 0.02, "ratio", "ASSUMED"),
    ("err_after", "Critical-field error rate, tool + review", 0.005, "ratio", "ASSUMED; measured in eval"),
    ("cost_per_error", "Cost of one critical error (rework, exposure)", 500000, "VND", "ASSUMED"),
    ("usd_per_page", "Model cost per extracted page", 0.0007, "USD", "ESTIMATE: Luna list price x assumed tokens"),
    ("fx", "VND per USD", 26000, "VND", "ASSUMED"),
    ("fixed_month", "Fixed run cost per month (infra, support)", 30000000, "VND", "ASSUMED"),
    ("one_off", "One-off build and rollout cost", 400000000, "VND", "ASSUMED"),
]
V = {k: v for k, _, v, _, _ in INPUTS}


def outputs(v, auto_share=None):
    a = v["auto_share"] if auto_share is None else auto_share
    d = v["docs_per_month"]
    hours_manual = d * v["manual_min"] / 60
    hours_after = (d * (1 - a) * v["review_min"] + d * a * v["audit_min"]) / 60
    hours_saved = hours_manual - hours_after
    labour = hours_saved * v["hourly_cost"]
    model = d * v["pages_extracted"] * v["usd_per_page"] * v["fx"]
    errors = d * (v["err_before"] - v["err_after"]) * v["cost_per_error"]
    net_month = labour + errors - model - v["fixed_month"]
    net_12 = 12 * net_month - v["one_off"]
    payback = v["one_off"] / net_month if net_month > 0 else None
    return dict(hours_manual=hours_manual, hours_after=hours_after, hours_saved=hours_saved,
                labour=labour, model=model, errors=errors, net_month=net_month,
                net_12=net_12, payback=payback)


out_path = Path(__file__).parent / "business_case.xlsx"
wb = xlsxwriter.Workbook(out_path)
f_h = wb.add_format({"bold": True, "bg_color": "#141E3C", "font_color": "white", "border": 1})
f_in = wb.add_format({"bg_color": "#FFF4D6", "border": 1, "num_format": "#,##0.####"})
f_pct = wb.add_format({"bg_color": "#FFF4D6", "border": 1, "num_format": "0.0%"})
f_txt = wb.add_format({"border": 1, "text_wrap": True})
f_out = wb.add_format({"border": 1, "num_format": "#,##0"})
f_out1 = wb.add_format({"border": 1, "num_format": "#,##0.0"})
f_warn = wb.add_format({"bold": True, "font_color": "#B71C1C", "text_wrap": True})
f_title = wb.add_format({"bold": True, "font_size": 14})

ws = wb.add_worksheet("Model")
ws.set_column("A:A", 52)
ws.set_column("B:B", 18)
ws.set_column("C:C", 8)
ws.set_column("D:D", 44)
ws.write("A1", "12-month business case (parameterised)", f_title)
ws.merge_range("A2:D2", "ALL INPUT VALUES ARE PLACEHOLDER ASSUMPTIONS. Replace them with interview or "
               "public-source values before quoting any output. Outputs are estimates, not results.", f_warn)
ws.set_row(1, 32)
ws.write_row("A4", ["Input", "Value", "Unit", "Source / status"], f_h)

cell = {}
for i, (key, label, val, unit, note) in enumerate(INPUTS):
    r = 4 + i
    ws.write(r, 0, label, f_txt)
    ws.write(r, 1, val, f_pct if unit == "ratio" else f_in)
    ws.write(r, 2, unit, f_txt)
    ws.write(r, 3, note, f_txt)
    cell[key] = f"$B${r + 1}"
    wb.define_name(key, f"=Model!$B${r + 1}")

base = outputs(V)
r0 = 4 + len(INPUTS) + 2
ws.write_row(r0 - 1, 0, ["Output (per month unless stated)", "Value", "Unit", "Formula idea"], f_h)
rows = [
    ("Manual hours per month", "=docs_per_month*manual_min/60", base["hours_manual"], "hours", "docs x manual min / 60", f_out1),
    ("Hours per month with tool", "=(docs_per_month*(1-auto_share)*review_min+docs_per_month*auto_share*audit_min)/60", base["hours_after"], "hours", "review flagged + audit sample", f_out1),
    ("Hours saved per month", None, base["hours_saved"], "hours", "difference", f_out1),
    ("Labour saving", None, base["labour"], "VND", "hours saved x hourly cost", f_out),
    ("Error-cost saving", "=docs_per_month*(err_before-err_after)*cost_per_error", base["errors"], "VND", "error rate delta x cost", f_out),
    ("Model cost", "=docs_per_month*pages_extracted*usd_per_page*fx", base["model"], "VND", "pages x price x fx", f_out),
    ("Net benefit per month", None, base["net_month"], "VND", "labour + errors - model - fixed", f_out),
    ("Net benefit over 12 months (after one-off)", None, base["net_12"], "VND", "12 x monthly - one-off", f_out),
    ("Payback (months)", None, base["payback"] if base["payback"] is not None else 0, "months", "one-off / monthly net", f_out1),
]
ref = {}
for i, (label, formula, value, unit, note, fmt) in enumerate(rows):
    r = r0 + i
    ref[label] = f"B{r + 1}"
formula_map = {
    "Hours saved per month": f"={ref['Manual hours per month']}-{ref['Hours per month with tool']}",
    "Labour saving": f"={ref['Hours saved per month']}*hourly_cost",
    "Net benefit per month": f"={ref['Labour saving']}+{ref['Error-cost saving']}-{ref['Model cost']}-fixed_month",
    "Net benefit over 12 months (after one-off)": f"=12*{ref['Net benefit per month']}-one_off",
    "Payback (months)": f'=IF({ref["Net benefit per month"]}>0,one_off/{ref["Net benefit per month"]},"never")',
}
for i, (label, formula, value, unit, note, fmt) in enumerate(rows):
    r = r0 + i
    ws.write(r, 0, label, f_txt)
    ws.write_formula(r, 1, formula or formula_map[label], fmt, value)
    ws.write(r, 2, unit, f_txt)
    ws.write(r, 3, note, f_txt)

# Sensitivity on auto-file share (formulas reference named inputs)
s0 = r0 + len(rows) + 2
ws.write(s0 - 1, 0, "Sensitivity: auto-file share vs 12-month net benefit", f_title)
ws.write_row(s0, 0, ["Auto-file share", "12-month net (VND)", "", "Payback (months)"], f_h)
for i, share in enumerate([0.2, 0.4, 0.6, 0.8, 0.9]):
    r = s0 + 1 + i
    ws.write(r, 0, share, f_pct)
    a = f"$A${r + 1}"
    net_m = (f"((docs_per_month*manual_min/60-(docs_per_month*(1-{a})*review_min+docs_per_month*{a}*audit_min)/60)*hourly_cost"
             f"+docs_per_month*(err_before-err_after)*cost_per_error-docs_per_month*pages_extracted*usd_per_page*fx-fixed_month)")
    o = outputs(V, share)
    ws.write_formula(r, 1, f"=12*{net_m}-one_off", f_out, o["net_12"])
    ws.write_formula(r, 3, f'=IF({net_m}>0,one_off/{net_m},"never")', f_out1,
                     o["payback"] if o["payback"] is not None else "never")
wb.close()
print("saved", out_path)
print({k: round(v, 1) if v is not None else None for k, v in base.items()})
