"""Run Luna on one rendered page of a real public PDF and compare with the text-layer values.

Run: uv run --group gateway python scripts/test_real_page.py
(Expected values were read from the PDF text layer of VNM annual report 2025, page 108.)
"""
import base64
import json
import time

import litellm
import pymupdf

PDF = "data/raw/VNM_baocaothuongnien_2025.pdf"
PAGE = 108
DPI = 150
MODEL = "chatgpt/gpt-6-luna"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page_type", "unit", "period_current", "period_prior", "items"],
    "properties": {
        "page_type": {"type": "string", "description": "balance_sheet | income_statement | cash_flow | notes | other"},
        "unit": {"type": "string"},
        "period_current": {"type": "string"},
        "period_prior": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "current", "prior", "quote"],
                "properties": {
                    "label": {"type": "string"},
                    "current": {"type": ["number", "null"]},
                    "prior": {"type": ["number", "null"]},
                    "quote": {"type": "string", "description": "the row text exactly as printed"},
                },
            },
        },
    },
}
PROMPT = (
    "You read one page of a Vietnamese financial statement. Extract every line item that has numbers. "
    "Numbers are printed with '.' as thousands separator; return plain numbers without separators. "
    "Reply with JSON only, no prose, matching exactly this JSON schema: " + json.dumps(SCHEMA)
)

EXPECT = {"TỔNG TÀI SẢN": (56091826, 56993245), "Tài sản ngắn hạn": (36207454, 37501520), "Tài sản dài hạn": (19884372, 19491725)}

page = pymupdf.open(PDF)[PAGE - 1]
png = page.get_pixmap(dpi=DPI).tobytes("png")
b64 = base64.b64encode(png).decode()
t = time.time()
r = litellm.completion(model=MODEL, messages=[{"role": "user", "content": [
    {"type": "text", "text": PROMPT},
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}])
dt = time.time() - t
txt = r.choices[0].message.content.strip().removeprefix("```json").removesuffix("```").strip()
u = r.usage
print(f"page {PAGE}: image {len(png) / 1024:.0f} KB, tokens in={u.prompt_tokens} out={u.completion_tokens}, {dt:.1f}s")
data = json.loads(txt)
print("page_type:", data["page_type"], "| unit:", data["unit"], "|", data["period_current"], "vs", data["period_prior"])
print("items:", len(data["items"]))
by_label = {i["label"].strip().lower(): i for i in data["items"]}
for label, (cur, pri) in EXPECT.items():
    got = by_label.get(label.lower())
    ok = bool(got) and got["current"] == cur and got["prior"] == pri
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: expected {cur}/{pri}, got {(got['current'], got['prior']) if got else None}")
for i in data["items"][:6]:
    print("  ", i["label"], i["current"], i["prior"])
