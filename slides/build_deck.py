"""Build the 15-minute presentation deck (python-pptx).

Run:  uv run python slides/build_deck.py
Output: slides/deck.pptx

Rule: no measured result is invented. Anything that needs the prototype or the
business-case sheet is shown as a visible placeholder ("TBD after eval").
"""
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

NAVY = RGBColor(0x14, 0x1E, 0x3C)
RED = RGBColor(0xC8, 0x10, 0x2E)
GREY = RGBColor(0x5A, 0x63, 0x73)
LIGHT = RGBColor(0xF2, 0xF4, 0xF8)
MID = RGBColor(0xD5, 0xDA, 0xE3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1E, 0x84, 0x5A)
AMBER = RGBColor(0xB7, 0x79, 0x10)
FONT = "Calibri"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height


def _run(p, text, size, bold=False, color=NAVY, italic=False):
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = FONT
    r.font.color.rgb = color
    return r


def text(slide, x, y, w, h, content, size=16, bold=False, color=NAVY,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    lines = content if isinstance(content, list) else [content]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        _run(p, line, size, bold, color, italic)
    return tb


def bullets(slide, x, y, w, h, items, size=16, color=NAVY, gap=6):
    """items: str or (str, level) tuples. Level 1 is indented, smaller."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05)
    first = True
    for it in items:
        txt, lvl = (it, 0) if isinstance(it, str) else it
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(gap)
        mark = "\u2022 " if lvl == 0 else "\u2013 "
        pad = "" if lvl == 0 else "    "
        _run(p, pad + mark + txt, size - (2 if lvl else 0), color=color if lvl == 0 else GREY)
    return tb


def box(slide, x, y, w, h, fill=LIGHT, line=MID, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = line
    s.line.width = Pt(1)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.08
    return s


def label_box(slide, x, y, w, h, content, fill=LIGHT, line=MID, size=12, color=NAVY, bold=False):
    s = box(slide, x, y, w, h, fill, line)
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    lines = content if isinstance(content, list) else [content]
    for i, line_txt in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        _run(p, line_txt, size if i == 0 else size - 2, bold if i == 0 else False,
             color if i == 0 else (GREY if color == NAVY else color))
    return s


def arrow(slide, x1, y1, x2, y2, color=GREY, dashed=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(1.5)
    ln = c.line._get_or_add_ln()
    if dashed:
        d = etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}prstDash")
        d.set("val", "dash")
    t = etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd")
    t.set("type", "triangle")
    return c


def table(slide, x, y, w, rows, col_w, size=12, row_h=0.4, header=True):
    nrows, ncols = len(rows), len(rows[0])
    gs = slide.shapes.add_table(nrows, ncols, x, y, w, Inches(row_h * nrows))
    tbl = gs.table
    total = sum(col_w)
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = int(w * cw / total)
    for r in range(nrows):
        tbl.rows[r].height = Inches(row_h)
        for c in range(ncols):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.07)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            is_head = header and r == 0
            _run(p, rows[r][c], size, bold=is_head or c == 0,
                 color=WHITE if is_head else NAVY)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if is_head else (LIGHT if r % 2 else WHITE)
    return tbl


def new_slide(title, kicker=None, notes="", n=None):
    s = prs.slides.add_slide(BLANK)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), SH)
    bar.fill.solid()
    bar.fill.fore_color.rgb = RED
    bar.line.fill.background()
    if kicker:
        text(s, Inches(0.55), Inches(0.28), Inches(11), Inches(0.3), kicker.upper(), 11, True, RED)
    text(s, Inches(0.55), Inches(0.55), Inches(12.2), Inches(0.9), title, 28, True, NAVY)
    text(s, Inches(0.55), Inches(7.05), Inches(9), Inches(0.3),
         "Techcombank AI Transformation Division | Expert Challenge 2026 | simulated/public data only",
         9, False, GREY)
    if n:
        text(s, Inches(12.2), Inches(7.05), Inches(0.8), Inches(0.3), str(n), 10, False, GREY,
             align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def tbd(slide, x, y, w, h, content, size=12):
    """Visible placeholder for numbers that must come from the prototype/sheet."""
    return label_box(slide, x, y, w, h, content, fill=RGBColor(0xFF, 0xF4, 0xD6),
                     line=AMBER, size=size, color=AMBER, bold=True)


X0 = Inches(0.55)
W = Inches(12.2)
n = 0

# ---------------------------------------------------------------- 1 Title
n += 1
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; bg.line.fill.background()
acc = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(2.35), Inches(1.2), Inches(0.08))
acc.fill.solid(); acc.fill.fore_color.rgb = RED; acc.line.fill.background()
text(s, Inches(0.8), Inches(2.6), Inches(11.5), Inches(1.6),
     "From financial statements to a trusted knowledge base", 40, True, WHITE)
text(s, Inches(0.8), Inches(4.1), Inches(11.5), Inches(0.9),
     "Governed document digitalisation for corporate credit: extract, validate, file, search, with a human in the loop",
     20, False, MID)
text(s, Inches(0.8), Inches(5.9), Inches(11.5), Inches(0.9),
     ["Expert Challenge 2026 | Problem Bank #2 (document processing) + #5 (trusted knowledge)",
      "[Full Name] | [Product Name]"], 14, False, MID)
s.notes_slide.notes_text_frame.text = (
    "0:00-0:15. One sentence: we turn piles of Vietnamese financial statements into filed, validated, "
    "searchable knowledge, and every number is traceable to a page and checkable by a rule.")

# ---------------------------------------------------------------- 2 Problem
n += 1
s = new_slide("Credit teams read, check and re-key financial statements by hand",
              "Frame the opportunity", n=n,
              notes="0:15-1:15. Pain is real but must be evidenced by interviews. Use the number from the "
                    "business-case sheet only after it is filled in; label it an estimate.")
bullets(s, X0, Inches(1.6), Inches(7.4), Inches(4.8), [
    "Corporate customers submit BCTC (separate, consolidated, audited, unaudited) and annual reports as PDFs and scans",
    "Analysts locate the right pages, read them, and key line items into spreadsheets or credit systems",
    "Files land in shared drives with inconsistent names; finding last year's audited statement is a search job",
    "Unit mix-ups (dong / thousand / million) and transcription slips are caught late, if at all",
    "Answers to 'where does this number come from?' depend on whoever did the keying",
], size=17, gap=10)
label_box(s, Inches(8.4), Inches(1.7), Inches(4.35), Inches(1.5),
          ["Who feels it", "Credit analysts, relationship managers, credit operations, risk reviewers"],
          fill=LIGHT, size=15, bold=True)
tbd(s, Inches(8.4), Inches(3.5), Inches(4.35), Inches(1.4),
    ["TBD: hours per month spent on spreading/keying", "from the business-case sheet (estimate)"], 13)
label_box(s, Inches(8.4), Inches(5.2), Inches(4.35), Inches(1.2),
          ["Scope: one flow, end to end", "Public Vietnamese BCTC and annual reports only"],
          fill=WHITE, size=14, bold=True)

# ---------------------------------------------------------------- 3 Stakeholders
n += 1
s = new_slide("Four stakeholder groups, and where their interests collide",
              "Frame the opportunity", n=n,
              notes="1:15-2:15. Label evidence honestly: Real interview / Public source / Simulated persona. "
                    "The brief needs 5+ people across 3+ roles; say how many were real.")
table(s, X0, Inches(1.55), W, [
    ["Role", "Wants", "Fears", "Evidence"],
    ["User: credit analyst / RM", "Less keying, fast retrieval, trust in the numbers", "Tool errors blamed on them; slower than Excel", "[Real / Public / Simulated]"],
    ["Process owner: credit operations", "Throughput, standard folder and naming, SLA", "Exceptions piling up in a review queue", "[Real / Public / Simulated]"],
    ["Risk and compliance", "Traceability, access control, no made-up numbers", "Silent errors; data leaving the bank", "[Real / Public / Simulated]"],
    ["Technology / data", "Low maintenance, swappable components, data control", "Vendor lock-in; AGPL surprises; unowned model drift", "[Real / Public / Simulated]"],
], [2.3, 3.4, 3.4, 2.0], size=13, row_h=0.62)
label_box(s, X0, Inches(4.85), Inches(5.9), Inches(1.7),
          ["Conflict 1: speed vs traceability",
           "Analysts want auto-filing; compliance wants every value tied to a page. Resolution: evidence quote + validator on every field."],
          fill=LIGHT, size=14, bold=True)
label_box(s, Inches(6.85), Inches(4.85), Inches(5.9), Inches(1.7),
          ["Conflict 2: capability vs data control",
           "A hosted model is best for the demo; IT and risk want data in the bank. Resolution: in-bank endpoint is a gate before pilot."],
          fill=LIGHT, size=14, bold=True)

# ---------------------------------------------------------------- 4 Options
n += 1
s = new_slide("Build the governance layer, buy the model: the chosen direction",
              "Frame the opportunity", n=n,
              notes="2:15-3:45. Be explicit that 'do nothing' has a cost, and that we would not buy a full IDP "
                    "suite for a first flow. Decision memo holds the detail.")
table(s, X0, Inches(1.55), W, [
    ["Direction", "Speed to value", "Control / auditability", "Cost", "Lock-in", "Verdict"],
    ["Do nothing", "None", "Manual, inconsistent", "Grows with volume", "None", "Baseline only"],
    ["Buy a full IDP suite", "Fast to start", "Vendor-defined; Vietnamese financials unproven [to test]", "Licence + per-page", "High", "Not for a first flow"],
    ["Build everything (own OCR, own models)", "Slow", "Full", "High build + GPU", "Low", "Over-engineered"],
    ["Hybrid: API model + own validators, filing, KB, audit", "Fast", "High: rules and evidence are ours", "Per-page model cost, small", "Low, model swappable", "CHOSEN"],
], [3.1, 1.6, 3.0, 2.0, 1.6, 1.5], size=12, row_h=0.72)
bullets(s, X0, Inches(5.35), W, Inches(1.5), [
    "Why: the scarce asset is not text recognition, it is trust, meaning checks, evidence and an audit trail around it",
    "Not built: credit decisioning, model fine-tuning, an analytics database, a core-system replacement",
], size=15, gap=8)

# ---------------------------------------------------------------- 5 Business case
n += 1
s = new_slide("Business case: a parameterised 12-month model, not a single number",
              "Frame the opportunity", n=n,
              notes="3:45-5:15. Open the spreadsheet; change one input live. Every figure is an estimate and "
                    "labelled as such. Do not state savings that the sheet does not produce.")
label_box(s, X0, Inches(1.6), Inches(3.9), Inches(2.9),
          ["Inputs (editable)",
           "documents / month | pages per document | manual minutes per document | loaded hourly cost | auto-file share | review minutes per flagged doc | error rate before/after | cost per page | fixed run cost"],
          fill=LIGHT, size=15, bold=True)
arrow(s, Inches(4.55), Inches(3.05), Inches(5.0), Inches(3.05), color=RED)
label_box(s, Inches(5.05), Inches(1.6), Inches(3.9), Inches(2.9),
          ["Outputs",
           "hours saved | net cost over 12 months | payback month | risk reduced (errors avoided) | sensitivity: auto-file share 40 / 60 / 80%"],
          fill=LIGHT, size=15, bold=True)
tbd(s, Inches(9.2), Inches(1.6), Inches(3.55), Inches(1.35),
    ["TBD: base-case saving", "(estimate, from sheet)"], 13)
tbd(s, Inches(9.2), Inches(3.15), Inches(3.55), Inches(1.35),
    ["TBD: break-even auto-file share", "(from sheet)"], 13)
bullets(s, X0, Inches(4.8), W, Inches(2.0), [
    "Assumptions are labelled estimates; each has a stated source or 'assumed'",
    "Cost side uses measured tokens x list price (a flat subscription hides the true per-document cost)",
    "If assumptions are wrong: the sheet shows the point where the project stops paying back, which feeds the stop criteria",
], size=15, gap=8)

# ---------------------------------------------------------------- 6 Success / stop / metrics
n += 1
s = new_slide("Success after 90 days, and the evidence that would make us stop",
              "Frame the opportunity", n=n,
              notes="5:15-6:15. Numeric targets are set after the first evaluation; say so. Stop criteria are "
                    "commitments made in advance.")
label_box(s, X0, Inches(1.55), Inches(12.2), Inches(0.95),
          ["North Star: straight-through rate",
           "Share of documents filed and extracted with no human touch and no critical-field error"],
          fill=NAVY, line=NAVY, size=18, color=WHITE, bold=True)
table(s, X0, Inches(2.75), Inches(6.0), [
    ["Supporting metric", "Target"],
    ["Handling time per document", "TBD after eval"],
    ["Review-queue rate", "TBD after eval"],
    ["Correct-with-citation rate on staff questions", "TBD after eval"],
], [3.6, 1.6], size=13, row_h=0.55)
label_box(s, Inches(6.85), Inches(2.75), Inches(5.9), Inches(2.2),
          ["Stop if (thresholds set after the first eval)",
           "Fabrication rate on critical fields stays above the ceiling after validators; review queue stays above the agreed share; cost per document exceeds manual cost"],
          fill=RGBColor(0xFD, 0xEC, 0xEF), line=RED, size=14, color=RED, bold=True)
bullets(s, X0, Inches(5.2), W, Inches(1.7), [
    "Test: 4-6 week shadow pilot with one credit team, tool runs beside manual work; compare time and error rates",
    "Then assist mode: analysts review pre-filled outputs; weekly audit sample of auto-filed documents",
], size=15, gap=8)

# ---------------------------------------------------------------- 7 Demo
n += 1
s = new_slide("Live demo: a document goes in, a cited answer comes out",
              "Working prototype", n=n,
              notes="6:15-9:15 (3 min). Fallback: play the 5-minute recording if anything stalls. Show the "
                    "Langfuse trace of the same document at the end.")
steps = [
    ("1 Drop", "BCTC PDF / scan into the intake folder"),
    ("2 Read", "Page router + Luna transcribe and extract, with page and quote"),
    ("3 Check", "Validators: assets = liabilities + equity, subtotals, units"),
    ("4 File", "Folder by ticker / year / period; sidecar JSON; PII masked"),
    ("5 Review", "A failing doc lands in the review queue; approve one"),
    ("6 Ask", "Hermes (via MCP) answers from the KB with a citation"),
]
bw, gap_ = Inches(1.92), Inches(0.13)
for i, (h, d) in enumerate(steps):
    x = X0 + i * (bw + gap_)
    label_box(s, x, Inches(1.8), bw, Inches(2.2), [h, d], fill=LIGHT, size=15, bold=True)
    if i < len(steps) - 1:
        arrow(s, x + bw, Inches(2.9), x + bw + gap_, Inches(2.9), color=RED)
bullets(s, X0, Inches(4.35), W, Inches(2.4), [
    "Also shown: the same document as a Langfuse trace (spans, tokens, cost) and its line in the audit log",
    "Failure shown on purpose: a document with a seeded unit error is caught by a validator and routed to review",
    "Fallback ready: recorded 5-minute video of the same run",
], size=16, gap=10)

# ---------------------------------------------------------------- 8 Architecture
n += 1
s = new_slide("Target architecture: every model call goes through one governed gateway",
              "Architecture", n=n,
              notes="9:15-10:45. Walk left to right. Stress: the model is swappable behind LiteLLM, OpenViking "
                    "is swappable behind the adapter, and the validators and audit log are ours.")
y1 = Inches(1.65)
bh, bw2 = Inches(0.95), Inches(1.55)
flow = [("Ingest", "PDF / scan"), ("Page router", "cheap pass"), ("Extract", "Luna VLM + evidence"),
        ("PII guard", "detect + mask"), ("Validators", "rules + 2-pass"), ("Auto-file", "folder + sidecar"),
        ("KB adapter", "OpenViking")]
g = Inches(0.2)
for i, (h, d) in enumerate(flow):
    x = X0 + i * (bw2 + g)
    fill = LIGHT if h not in ("Validators", "PII guard") else RGBColor(0xFD, 0xEC, 0xEF)
    label_box(s, x, y1, bw2, bh, [h, d], fill=fill, size=13, bold=True)
    if i < len(flow) - 1:
        arrow(s, x + bw2, y1 + bh // 2, x + bw2 + g, y1 + bh // 2, color=RED)
# review queue under validators/auto-file
vx = X0 + 4 * (bw2 + g)
label_box(s, vx, Inches(3.0), bw2, Inches(0.8), ["Review queue", "conf < threshold"], fill=WHITE, size=12, bold=True)
arrow(s, vx + bw2 // 2, y1 + bh, vx + bw2 // 2, Inches(3.0), color=AMBER)
ax = X0 + 5 * (bw2 + g)
arrow(s, vx + bw2, Inches(3.4), ax + bw2 // 2, Inches(3.4), color=AMBER)
arrow(s, ax + bw2 // 2, Inches(3.4), ax + bw2 // 2, y1 + bh, color=AMBER)
# user + hermes under KB
kx = X0 + 6 * (bw2 + g)
label_box(s, kx, Inches(3.0), bw2, Inches(0.8), ["Hermes agent", "read-only, via MCP"], fill=WHITE, size=12, bold=True)
arrow(s, kx + bw2 // 2, Inches(3.0), kx + bw2 // 2, y1 + bh, color=GREY, dashed=True)
label_box(s, kx, Inches(4.0), bw2, Inches(0.6), ["Analyst"], fill=WHITE, size=12, bold=True)
arrow(s, kx + bw2 // 2, Inches(4.0), kx + bw2 // 2, Inches(3.8), color=GREY)
# platform band
label_box(s, X0, Inches(4.95), Inches(5.7), Inches(0.85),
          ["LiteLLM gateway", "Luna via chatgpt/ route (demo); per-component keys, rpm/tpm limits"],
          fill=NAVY, line=NAVY, size=14, color=WHITE, bold=True)
label_box(s, Inches(6.4), Inches(4.95), Inches(3.1), Inches(0.85),
          ["Langfuse (target, not run)", "traces, tokens, cost, eval scores"], fill=NAVY, line=NAVY, size=13, color=WHITE, bold=True)
label_box(s, Inches(9.65), Inches(4.95), Inches(3.1), Inches(0.85),
          ["Audit log", "who / what / which model / which rule"], fill=NAVY, line=NAVY, size=13, color=WHITE, bold=True)
bullets(s, X0, Inches(6.0), W, Inches(1.0), [
    "At scale: stateless workers behind a queue; the gateway enforces rate limits and, on a priced API route, budgets; access control sits in front of the KB",
    "Run natively: router, extraction, validators, review, KB Q&A, LiteLLM proxy, OpenViking. Not run (WSL/Podman failed): Langfuse, Presidio containers",
], size=14, gap=4)

# ---------------------------------------------------------------- 9 Privacy ladder
n += 1
s = new_slide("PII protection is a ladder; the demo is the bottom rung, and we say so",
              "Architecture: privacy by design", n=n,
              notes="10:45-12:00. Key honesty point: a Presidio guardrail only sees text, and the VLM path sends "
                    "page images. The Luna guard shows the policy flow but cannot stop the first hop.")
table(s, X0, Inches(1.5), W, [
    ["Level", "Detector", "Runs where", "Protects the first hop?", "Use"],
    ["L0", "Luna classifies PII in the transcript", "Same hosted provider", "No: image already sent", "Demo of the policy flow"],
    ["L1", "Presidio + Vietnamese regex recognizers (CCCD, tax code, phone, email)", "Local container, LiteLLM guardrail", "Yes for text calls (e.g. Hermes)", "Switchable in the demo stack"],
    ["L2", "L1 + local Vietnamese NER for names and addresses", "Local container, CPU", "Yes for text", "Pilot, if latency is acceptable"],
    ["L3", "In-bank VLM endpoint, or local OCR then mask then LLM", "Inside the bank", "Yes, including images", "Production target"],
], [0.7, 4.0, 2.6, 2.4, 2.5], size=12, row_h=0.62)
bullets(s, X0, Inches(4.85), Inches(6.4), Inches(2.1), [
    "Presidio has no built-in Vietnamese; we add recognizers and optionally a NER model",
    "pre_call masks before the model; during_call is not a privacy barrier",
    "output_parse_pii only restores masked values; it does not find new PII",
], size=14, gap=6)
label_box(s, Inches(7.2), Inches(4.85), Inches(5.55), Inches(1.9),
          ["Data classification in the demo",
           "KB indexes masked text; originals sit in a restricted folder with an access check; Hermes sees masked text unless cleared; company names are not masked"],
          fill=LIGHT, size=14, bold=True)

# ---------------------------------------------------------------- 10 Decisions
n += 1
s = new_slide("Four decisions and what each one costs us",
              "Architecture", n=n,
              notes="12:00-13:00. One breath per decision: what we gain, what we pay, how we limit the loss.")
table(s, X0, Inches(1.55), W, [
    ["Decision", "Gain", "Price", "How we limit it"],
    ["1. VLM instead of OCR + rules", "One call; Vietnamese diacritics; no OCR tuning", "Hallucinated digits; no per-field confidence; images leave the bank", "Validators, evidence quotes, 2-pass check, in-bank endpoint gate"],
    ["2. Fixed taxonomy + LLM classifier, not BERTopic", "Auditable labels with confidence", "Less discovery of new categories", "BERTopic kept as an offline discovery tool"],
    ["3. OpenViking behind an adapter", "Filesystem model matches the folder design", "AGPL-3.0; RBAC unverified; single-vendor governance", "Adapter keeps it swappable; our own access layer; legal review before production"],
    ["4. PII detector placement", "Hosted LLM is simple; Presidio is local", "Hosted detection is not a barrier; regex misses names", "Ladder L0-L3; measured precision and recall"],
], [2.8, 3.0, 3.4, 3.4], size=12, row_h=0.9)

# ---------------------------------------------------------------- 11 Evaluation
n += 1
s = new_slide("We measure the model: evaluation set, failure cases, cost, latency",
              "Evaluation", n=n,
              notes="13:00-14:00 compressed; fill every TBD from the harness output before presenting. "
                    "Never show a number the harness did not produce.")
table(s, X0, Inches(1.5), W, [
    ["Test", "What is measured", "Result"],
    ["Scan simulation (text-layer truth, 7 pages)", "Precision / recall of extracted numbers", "Clean 100% / 95.3%; degraded 97.8% / 92.8%"],
    ["End-to-end scan test (real pages, no text layer)", "Wrong values caught by two-pass agreement", "Mild 4 of 4, harsh 129 of 130; both sent to review"],
    ["Multi-issuer: IFRS, VAS, bank; 5 documents", "Filed or escalated as expected; false alarms", "Cross-year tie-out 6/6; first-run false alarms on 2 of 3 new issuers (rules then fixed)"],
    ["Injected errors + a real digit drop", "Routed to review", "6/6; real 511.184 read as 51,184 caught, corrected, logged"],
    ["KB Q&A: 24 answerable, 6 unanswerable", "Correct / cited / refused / ungrounded", "22/24 / 22 of 22 / 6/6 / 0"],
    ["Prompt injection: page image; poisoned KB chunk", "Instruction followed?", "Resisted 9/9 and 1/1 (obvious cases only)"],
    ["PII, seeded synthetic lines", "Precision / recall", "Luna 1.00 / 1.00; regex 0 recall on names, addresses"],
    ["Cost and latency", "Tokens x list price", "$0.0013 per page; $0.003-0.011 per text PDF; 26-32 s per page"],
], [3.4, 3.4, 5.4], size=11, row_h=0.55)
text(s, X0, Inches(6.55), W, Inches(0.45),
     "Development-set results (rules were tuned on these documents). Not measured: classification accuracy, Luna vs Sol, "
     "Langfuse traces, Hermes + OpenViking. Cost = list price x measured tokens; the demo runs on a flat subscription.",
     12, False, GREY, italic=True)

# ---------------------------------------------------------------- 12 Governance
n += 1
s = new_slide("Governance: the tool is allowed to be unsure, and it must say so",
              "Automate safely", n=n,
              notes="Part of the 13:00-14:00 block. Ask: what breaks if the tool is wrong? Answer with the "
                    "row on the right, not with reassurance.")
bullets(s, X0, Inches(1.6), Inches(6.3), Inches(5.0), [
    "Confidence from signals: validator results, two-pass agreement, PDF text-layer agreement; threshold set from the calibration curve",
    "Human review queue for anything below threshold, with the page and the quote side by side",
    "Audit log: model and version, prompt hash, raw response, rule results, reviewer, timestamp",
    "Safe to re-run: content-hash idempotency; resumable runs after rate limits",
    "Kill switch: one flag stops auto-filing and sends everything to review; rollback restores the previous folder state",
    "Alerts on queue growth, validator failure spikes, cost per document",
], size=15, gap=9)
table(s, Inches(7.1), Inches(1.6), Inches(5.65), [
    ["If the tool is wrong...", "Then"],
    ["A digit is misread", "Validator fails; review queue"],
    ["A wrong doc type", "Low confidence or a mismatch rule; review"],
    ["Validators pass but value is wrong", "Weekly audit sample finds it; kill switch"],
    ["A document hides instructions", "Treated as data; Hermes is read-only"],
    ["Model changes behaviour", "Pinned version; eval re-run before upgrade"],
], [2.8, 2.9], size=12, row_h=0.62)

# ---------------------------------------------------------------- 13 Rollout / reuse
n += 1
s = new_slide("Three-month rollout, the biggest risk, and how another team adopts it",
              "Rollout", n=n,
              notes="14:00-15:00. Name the biggest risk plainly: silent numeric errors that pass validators. "
                    "End on the ask.")
cols = [("Month 1: shadow pilot", "Runs beside manual work; tune thresholds; baseline time and error"),
        ("Month 2: assist mode", "Analysts review pre-filled output; review queue live; weekly audit sample"),
        ("Month 3: harden and scale", "In-bank model endpoint; second team onboards by config; risk walkthrough of the audit log")]
cw = Inches(3.95)
for i, (h, d) in enumerate(cols):
    x = X0 + i * (cw + Inches(0.175))
    label_box(s, x, Inches(1.55), cw, Inches(1.5), [h, d], fill=LIGHT, size=15, bold=True)
label_box(s, X0, Inches(3.3), Inches(6.0), Inches(1.7),
          ["Biggest risk", "Silent numeric errors that pass the validators. Found early by a weekly audit sample in the pilot; stop criteria apply."],
          fill=RGBColor(0xFD, 0xEC, 0xEF), line=RED, size=14, color=RED, bold=True)
label_box(s, Inches(6.75), Inches(3.3), Inches(6.0), Inches(1.7),
          ["Reuse by another team", "A YAML taxonomy, validator set and thresholds; templates, README and a Compose stack. Add a document type without code changes."],
          fill=LIGHT, size=14, bold=True)
bullets(s, X0, Inches(5.25), W, Inches(1.6), [
    "Team of ~5: product/process owner, two engineers, one risk and compliance partner, one analyst from the pilot team",
    "Not building: credit decisioning, fine-tuning, an analytics database, a core-system replacement",
    "Ask: approve a 6-week shadow pilot with one credit team and an in-bank endpoint decision",
], size=15, gap=8)

# ---------------------------------------------------------------- Appendix
n += 1
s = new_slide("Appendix A: validators", "Appendix", n=n)
table(s, X0, Inches(1.5), W, [
    ["Validator", "Rule", "Fails when"],
    ["Balance identity", "Total assets = total liabilities + equity", "Mismatch beyond rounding"],
    ["Subtotals", "Each subtotal = sum of its line items", "Any difference"],
    ["Cross-period", "Prior-year column agrees with the previous filing", "Restatement not flagged"],
    ["Cash tie-out", "Closing cash (cash-flow) = cash on balance sheet", "Mismatch"],
    ["Units", "dong / thousand / million detected and normalised", "Missing or inconsistent unit"],
    ["Dates and periods", "Fiscal year and period consistent across pages", "Conflict"],
], [2.2, 5.6, 3.4], size=13, row_h=0.58)

n += 1
s = new_slide("Appendix B: PII guard configuration and known issues", "Appendix", n=n)
bullets(s, X0, Inches(1.5), Inches(6.2), Inches(5.2), [
    "LiteLLM guardrail: guardrail: presidio, mode: pre_call, analyzer and anonymizer URLs, output_parse_pii, presidio_language",
    "Vietnamese: regex recognizers with supported_language vi and context words; optional NER (e.g. a Hugging Face Vietnamese model); the community package vipii is an option, to be reviewed",
    "Entity config masks personal data only (person, ID numbers, phone, email, personal address); ORG is not masked",
], size=14, gap=10)
bullets(s, Inches(7.0), Inches(1.5), Inches(5.7), Inches(5.2), [
    "Streaming breaks restoration (LiteLLM issue 49638): use non-streaming",
    "One Presidio call at a time per proxy process (issue 47579): scale with more processes",
    "Check whether masking happens before Langfuse logs; use turn_off_message_logging in production",
    "Language models must exist in the analyzer container or detection is skipped",
], size=14, gap=10)

n += 1
s = new_slide("Appendix C: demo stack (Podman Compose)", "Appendix", n=n)
table(s, X0, Inches(1.5), W, [
    ["Service", "Role", "Note"],
    ["LiteLLM + Postgres", "Gateway, virtual keys, spend tracking", "Luna via chatgpt/ route; needs a database for spend"],
    ["Langfuse (web, worker, Postgres, Redis, ClickHouse, object store)", "Tracing and eval scores", "Volumes on the WSL filesystem"],
    ["OpenViking server", "Knowledge base", "AGPL-3.0; behind the adapter"],
    ["Embedding service (CPU)", "Multilingual embeddings for OpenViking", "Needed if the subscription route has no embeddings (to be tested)"],
    ["Presidio analyzer + anonymizer", "L1 PII guard", "Switchable with the Luna guard by config"],
    ["Pipeline worker, review UI", "The prototype", "Idempotent, resumable"],
    ["Hermes agent", "Q&A over the KB", "MCP to OpenViking; read-only"],
], [3.8, 3.4, 4.0], size=12, row_h=0.55)

out = Path(__file__).parent / "deck.pptx"
prs.save(out)
print("saved", out, "slides:", len(prs.slides))
