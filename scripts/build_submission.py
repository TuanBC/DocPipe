"""Build the submission PDFs from the Markdown docs (Markdown -> HTML -> PDF in headless Chromium).

Run: uv run --no-project --with markdown --with playwright==1.55.0 --with pymupdf python scripts/build_submission.py
Writes submission/*.pdf and prints page counts (the brief caps the memo at 6 pages and the AI log at 1).
"""
import re
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS, OUT = ROOT / "docs", ROOT / "submission"

PACKS = [
    ("01_Decision_memo_and_business_case.pdf", ["decision-memo.md"], "Decision memo and business case"),
    ("03_Architecture_and_evaluation.pdf", ["architecture.md", "eval-results.md"], "Architecture and evaluation"),
    ("04_Automation_and_rollout_plan.pdf", ["rollout-and-automation.md", "adoption-guide.md"], "Automation and rollout plan"),
    ("05_AI_log_and_reflection.pdf", ["ai-log.md"], "AI log and reflection"),
    ("06_Stakeholders_and_interview_plan.pdf", ["stakeholders.md", "interview-notes.md"], "Stakeholders and interview plan"),
]

CSS = """
@page { size: A4; }
body { font-family: Calibri, Arial, sans-serif; font-size: 10pt; line-height: 1.38; color: #1B2A3A; }
h1 { font-family: Cambria, Georgia, serif; font-size: 18pt; margin: 0 0 6pt; color: #1B2A3A; }
h2 { font-family: Cambria, Georgia, serif; font-size: 13pt; margin: 12pt 0 4pt; color: #1B2A3A; }
h3 { font-size: 11pt; margin: 10pt 0 3pt; }
p { margin: 4pt 0; }
ul, ol { margin: 3pt 0 3pt 16pt; padding: 0; }
li { margin: 1.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 8.6pt; }
th { background: #1B2A3A; color: #fff; text-align: left; padding: 3pt 5pt; }
td { border: 0.5pt solid #D5DCE3; padding: 3pt 5pt; vertical-align: top; }
tr { page-break-inside: avoid; }
code { font-family: Consolas, monospace; font-size: 8.6pt; background: #EEF2F5; padding: 0 2pt; }
pre { background: #EEF2F5; padding: 5pt; font-size: 8pt; white-space: pre-wrap; }
img { max-width: 100%; border: 0.5pt solid #D5DCE3; margin: 4pt 0; }
.doc + .doc { page-break-before: always; }
.foot { color: #5B6B7B; font-size: 8pt; margin-top: 10pt; }
"""


COMPACT = """
body { font-size: 8.8pt; line-height: 1.28; } h1 { font-size: 15pt; } h2 { font-size: 11pt; margin: 7pt 0 3pt; }
table { font-size: 7.8pt; margin: 4pt 0; } td, th { padding: 2pt 4pt; } li { margin: 0.5pt 0; } .foot { display: none; }
"""


def md_to_html(text: str) -> str:
    text = re.sub(r"```mermaid.*?```", "", text, flags=re.S)  # the rendered diagram is embedded as an image
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for name, files, title in PACKS:
            body = "".join(f'<div class="doc">{md_to_html((DOCS / f).read_text(encoding="utf-8"))}</div>' for f in files)
            extra = COMPACT if name.startswith("05_") else ""  # the brief caps the AI log at one page
            html = (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title><style>{CSS}{extra}</style></head>"
                    f"<body>{body}<p class='foot'>DocPipe · TuanBC · Techcombank AI Transformation Expert Challenge 2026 · "
                    f"simulated or public data only</p></body></html>")
            tmp = DOCS / "_print.html"   # inside docs/ so relative image paths resolve
            tmp.write_text(html, encoding="utf-8")
            page.goto(tmp.as_uri())
            page.wait_for_load_state("networkidle")
            page.pdf(path=str(OUT / name), format="A4", print_background=True,
                     margin={"top": "12mm", "bottom": "12mm", "left": "14mm", "right": "14mm"} if extra else
                     {"top": "16mm", "bottom": "16mm", "left": "15mm", "right": "15mm"})
            tmp.unlink()
        browser.close()
    import pymupdf
    for name, _, _ in PACKS:
        print(f"{name}: {len(pymupdf.open(OUT / name))} pages")


if __name__ == "__main__":
    main()
