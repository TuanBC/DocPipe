// DocPipe presentation deck (15-minute talk). Build: cd slides && node build.js  -> DocPipe_deck.pptx
// Numbers come from model/business_case_summary.json and evals/results/general_docs.json.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa6");

const ROOT = path.resolve(__dirname, "..");
const BC = JSON.parse(fs.readFileSync(path.join(ROOT, "model/business_case_summary.json"), "utf8"));
const EV = JSON.parse(fs.readFileSync(path.join(ROOT, "evals/results/general_docs.json"), "utf8")).summary;

// ---------- palette: ink + paper, one seal-red accent, green = verified, amber = review ----------
const INK = "1B2A3A", INK2 = "2C3E52", PAPER = "FFFFFF", MIST = "EEF2F5", LINE = "D5DCE3", MUTED = "5B6B7B";
const SEAL = "C8102E", OK = "2E7D5B", WARN = "B7791F";
const HEAD = "Cambria", BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.author = "TuanBC";
pres.title = "DocPipe: governed document intake for corporate credit";
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "DARK", background: { color: INK },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.3, w: 11.7, h: 1.4, fontFace: HEAD, fontSize: 44, bold: true, color: PAPER, valign: "top", align: "left", margin: 0 }, text: "" } }],
});
pres.defineSlideMaster({
  title: "DARK_TOP", background: { color: INK },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.8, y: 0.6, w: 11.7, h: 1.0, fontFace: HEAD, fontSize: 32, bold: true, color: PAPER, valign: "middle", align: "left", margin: 0 }, text: "" } }],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: PAPER },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.8, fontFace: HEAD, fontSize: 28, bold: true, color: INK, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "DocPipe  ·  TuanBC  ·  simulated / public data only", options: { x: 0.6, y: 7.05, w: 8, h: 0.3, fontFace: BODY, fontSize: 10, color: MUTED, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.05, w: 0.5, h: 0.3, fontFace: BODY, fontSize: 10, color: MUTED, align: "right" },
});

// ---------- helpers ----------
async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
const ICON = {};
async function loadIcons() {
  const want = { file: fa.FaFileLines, clock: fa.FaClock, link: fa.FaLinkSlash, search: fa.FaMagnifyingGlass, user: fa.FaUserTie,
    shield: fa.FaShieldHalved, server: fa.FaServer, bell: fa.FaBell, power: fa.FaPowerOff, check: fa.FaCircleCheck,
    rotate: fa.FaClockRotateLeft, chart: fa.FaChartLine, lock: fa.FaLock, list: fa.FaListCheck, db: fa.FaDatabase, folder: fa.FaFolderTree,
    warn: fa.FaTriangleExclamation, eye: fa.FaEye, scale: fa.FaScaleBalanced, people: fa.FaPeopleGroup, cpu: fa.FaMicrochip,
    redo: fa.FaRotateRight, book: fa.FaBookOpen, flask: fa.FaFlask };
  for (const [k, C] of Object.entries(want)) ICON[k] = await icon(C, PAPER);
}
// seal motif: icon in a solid circle
function seal(slide, key, x, y, d = 0.62, color = SEAL) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color, width: 0 }, objectName: "seal-" + key });
  slide.addImage({ data: ICON[key], x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52, altText: key });
}
function card(slide, x, y, w, h, fill = MIST) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill, width: 0 } });
}
function txt(slide, text, o) {
  slide.addText(text, { isTextBox: true, fontFace: BODY, fontSize: 14, color: INK, margin: 0, valign: "top", ...o });
}
function bullets(slide, items, o) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1 } })),
    { isTextBox: true, fontFace: BODY, fontSize: 14, color: INK, margin: 0, valign: "top", paraSpaceAfter: 6, ...o });
}
function stat(slide, x, y, w, big, label, color = SEAL) {
  txt(slide, big, { x, y, w, h: 0.85, fontFace: HEAD, fontSize: 38, bold: true, color });
  txt(slide, label, { x, y: y + 0.85, w, h: 0.75, fontSize: 12, color: MUTED });
}
function content(title, section) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
}
const fmtBn = (m) => (m / 1000).toFixed(1);
const hdrRow = (cols) => cols.map(t => ({ text: t, options: { bold: true, color: PAPER, fill: { color: INK } } }));

async function main() {
  await loadIcons();
  const base = BC.base, scen = BC.scenarios, scale = BC.scale;
  const hoursSaved = Math.round(base.hours_saved / 10) * 10;

  // ===== 1. Title =====
  pres.addSection({ title: "Frame" });
  let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Frame" });
  s.addText("DocPipe", { placeholder: "title" });
  txt(s, "Scans in, trusted and searchable credit files out", { x: 0.8, y: 3.35, w: 11, h: 0.6, fontFace: HEAD, fontSize: 26, color: "CAD6E2" });
  txt(s, "Governed document intake for corporate credit: a vision model reads, our checks decide, a person approves what is uncertain.",
    { x: 0.8, y: 4.15, w: 10.5, h: 0.8, fontSize: 16, color: "B7C3CF" });
  txt(s, "TuanBC  ·  Techcombank AI Transformation  ·  Expert Challenge 2026", { x: 0.8, y: 6.4, w: 10, h: 0.4, fontSize: 14, color: "B7C3CF" });
  seal(s, "file", 11.4, 0.7, 1.1);
  s.addNotes("Introduce yourself. One sentence: DocPipe turns the pile of scans in a credit file into filed, checked, searchable documents, and it only acts alone when it can prove it is right.");

  // ===== 2. Answer first =====
  s = content("Recommendation: a 6-week shadow pilot with one credit team", "Frame");
  txt(s, "A vision model reads every document; deterministic checks, a review queue and an audit trail decide what is trusted. The model is the cheap, swappable part; the controls are ours.",
    { x: 0.6, y: 1.35, w: 12, h: 0.8, fontSize: 16 });
  const stats = [[`${EV.fully_correct}/${EV.documents}`, "synthetic scans: type, customer and year all correct (incl. 6 traps)"],
    [EV.numbers_exact, "printed amounts and codes read exactly"], [String(EV.wrong_but_auto_filed), "wrong results auto-filed"],
    ["~" + hoursSaved + " h", "per month saved at base volumes (ESTIMATE, " + base.fte_saved + " FTE)"]];
  stats.forEach(([b, l], i) => { card(s, 0.6 + i * 3.08, 2.45, 2.85, 1.95); stat(s, 0.85 + i * 3.08, 2.6, 2.4, b, l, i === 2 ? OK : SEAL); });
  card(s, 0.6, 4.65, 12.1, 1.95, "F7EDEE");
  seal(s, "flask", 0.85, 4.9, 0.62);
  txt(s, "The ask", { x: 1.7, y: 4.9, w: 4, h: 0.4, fontFace: HEAD, fontSize: 20, bold: true, color: SEAL });
  bullets(s, ["Weeks 1-2: interviews, timed baseline, in-bank model endpoint decision, legal review",
    "Weeks 3-6 shadow mode, weeks 7-12 A/B by batch; stop rules signed by risk before day 1",
    "Measured on real scans before any scale-up: synthetic results prove the flow, not the accuracy"], { x: 1.7, y: 5.35, w: 10.8, h: 1.2 });
  s.addNotes("Lead with the decision. Four numbers: all correct on a trap-laden synthetic set, every printed number exact, zero wrong auto-filings, and an estimated ~870 hours a month at base volumes. Be explicit: the accuracy numbers are synthetic; the pilot exists to measure real scans.");

  // ===== 3. Problem =====
  s = content("A credit file is a pile of scans that people read, file and re-key", "Frame");
  const pains = [["clock", "Time", "A financial spread takes 30 min to 6 h per borrower (public vendor range). Each onboarding document is minutes, and there are many per customer."],
    ["link", "Trust", "A keyed number has no link back to its page. A dropped digit can reach a credit memo, and nobody can replay where it came from."],
    ["search", "Re-finding", "\"What is the collateral on this facility?\" means asking a colleague or reopening folders with inconsistent names."]];
  pains.forEach(([ic, h, b], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.45, 3.85, 3.55);
    seal(s, ic, x + 0.3, 1.7, 0.7);
    txt(s, h, { x: x + 0.3, y: 2.6, w: 3.3, h: 0.5, fontFace: HEAD, fontSize: 22, bold: true });
    txt(s, b, { x: x + 0.3, y: 3.15, w: 3.3, h: 1.75, fontSize: 14, color: INK2 });
  });
  txt(s, "Documents in scope: financial statements and annual reports, business registration, board resolutions, contracts, invoices, collateral papers, tax filings, bank statements.",
    { x: 0.6, y: 5.3, w: 12.1, h: 0.6, fontSize: 14, color: MUTED });
  txt(s, "Problem statement: credit staff spend hours reading, filing and re-keying documents a machine can read, and the result is neither traceable nor searchable.",
    { x: 0.6, y: 5.95, w: 12.1, h: 0.8, fontFace: HEAD, fontSize: 17, italic: true, color: SEAL });
  s.addNotes("Problem Bank #2 plus #5: document processing and a trusted knowledge assistant over the same documents. The public time range comes from vendor material, so it brackets the input; it is not evidence about this bank.");

  // ===== 4. Stakeholders =====
  s = content("Four roles, three conflicts the design must settle", "Frame");
  const roles = [["user", "Analysts, RMs", "Less keying; numbers they can trust", "Checking costs as much as doing"],
    ["people", "Credit operations", "Throughput, standard folders, SLAs", "A queue that must be staffed"],
    ["scale", "Risk, compliance", "Page-level traceability; no data leaving", "Silent errors; unreviewed model changes"],
    ["server", "Technology", "Swappable parts, clear licences", "Lock-in; an AGPL surprise"]];
  roles.forEach(([ic, r, want, fear], i) => {
    const y = 1.4 + i * 1.12;
    card(s, 0.6, y, 6.0, 0.98);
    seal(s, ic, 0.78, y + 0.18, 0.62, INK2);
    txt(s, r, { x: 1.6, y: y + 0.12, w: 4.8, h: 0.35, fontSize: 15, bold: true });
    txt(s, [{ text: "Wants: ", options: { bold: true, color: OK } }, { text: want + "   " }, { text: "Fears: ", options: { bold: true, color: SEAL } }, { text: fear }],
      { x: 1.6, y: y + 0.48, w: 4.9, h: 0.45, fontSize: 12, color: INK2 });
  });
  const conflicts = [["Speed vs traceability", "Every value carries its page; checks gate auto-filing"],
    ["Capability vs data control", "Hosted model for public data only; in-bank endpoint is a gate"],
    ["Automation vs verification cost", "Reviewers see only flagged documents; review rate is alerted on"]];
  txt(s, "Conflicts and how the design responds", { x: 7.0, y: 1.4, w: 5.7, h: 0.4, fontFace: HEAD, fontSize: 18, bold: true });
  conflicts.forEach(([c, r], i) => {
    const y = 1.95 + i * 1.05;
    txt(s, c, { x: 7.0, y, w: 5.7, h: 0.35, fontSize: 15, bold: true, color: SEAL });
    txt(s, r, { x: 7.0, y: y + 0.38, w: 5.7, h: 0.55, fontSize: 13, color: INK2 });
  });
  card(s, 7.0, 5.25, 5.7, 1.3, "FBF3E4");
  txt(s, [{ text: "Evidence status: ", options: { bold: true, color: WARN } },
    { text: "no real interview yet. Roles come from public sources and labelled simulated personas. Five interviews across four roles are the first pilot gate (guide and template ready)." }],
    { x: 7.2, y: 5.4, w: 5.3, h: 1.2, fontSize: 13 });
  s.addNotes("Be upfront: the brief asks for five interviews and they have not happened. Say what you expect to hear and what would change the design, for example if operations cannot staff a review queue.");

  // ===== 5. Options =====
  s = content("Five directions; the hybrid keeps trust in the bank's hands", "Frame");
  const opt = [["Do nothing", "None", "Manual, inconsistent", "Grows with volume", "None", "Baseline"],
    ["Staff use a chat assistant", "Fast", "None; data leaves", "Low", "Medium", "Rejected: shadow IT"],
    ["Buy a document-AI suite", "Fast start", "Vendor-defined; VN statements unproven", "Licence + per page", "High", "Bake-off on our eval set"],
    ["Build own OCR + layout models", "Slow", "Full", "High: GPUs, templates", "Low", "Over-engineered"],
    ["Hybrid: model reads, our checks decide", "Fast", "High: rules, review, audit ours", "Model ≈ 0; people dominate", "Low: swappable", "Chosen"]];
  const rows = [hdrRow(["Option", "Speed", "Control and audit", "Cost", "Lock-in", "Verdict"]),
    ...opt.map((r, i) => r.map((c, j) => ({ text: c, options: i === 4 ? { bold: true, fill: { color: "F7EDEE" }, color: j === 5 ? SEAL : INK } : {} })))];
  s.addTable(rows, { x: 0.6, y: 1.4, w: 12.1, colW: [3.0, 1.2, 2.9, 1.9, 1.4, 1.7], fontFace: BODY, fontSize: 13, color: INK,
    border: { type: "solid", pt: 0.75, color: LINE }, rowH: 0.62, valign: "middle", margin: 0.08 });
  seal(s, "check", 0.6, 5.6, 0.62, OK);
  txt(s, "Reading text is now the cheap, replaceable part. The scarce part is trust: checks, evidence, a review path and an audit trail. Keep those; swap the model (hosted today, in-bank tomorrow).",
    { x: 1.45, y: 5.6, w: 11.2, h: 0.9, fontSize: 15 });
  s.addNotes("Include 'do nothing' and 'buy'. Buy is not rejected: run one vendor on the same evaluation set during the pilot. Say what you would not build: credit decisioning, fine-tuning, a warehouse, a DMS replacement.");

  // ===== 6. Opportunity =====
  s = content("~1.2 bn VND net in 12 months, if the baseline holds", "Frame");
  s.addChart(pres.charts.BAR, [{ name: "12-month net (bn VND)", labels: ["Pessimistic", "Base", "Optimistic"], values: scen.map(x => +(x.net_12_mVND / 1000).toFixed(2)) }], {
    x: 0.6, y: 1.35, w: 6.3, h: 4.3, barDir: "col", chartColors: [SEAL, INK, OK], varyColors: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", dataLabelFontFace: BODY, dataLabelFontSize: 13, dataLabelColor: INK,
    showTitle: true, title: "12-month net benefit, bn VND (ESTIMATE)", titleFontFace: BODY, titleFontSize: 13, titleColor: MUTED,
    catAxisLabelColor: MUTED, valAxisLabelColor: MUTED, catAxisLabelFontFace: BODY, valAxisLabelFontFace: BODY, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    valGridLine: { color: "E3E8ED", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, valAxisLabelFormatCode: "0.0" });
  txt(s, "Scenario inputs: pessimistic 30% auto-filed, 30/3 manual min · base 60-70%, 60/6 min · optimistic 85%, 120/10 min. Model cost ≈ 0.2 m VND a month.",
    { x: 0.6, y: 5.75, w: 6.3, h: 0.7, fontSize: 11, color: MUTED });
  card(s, 7.3, 1.35, 5.4, 2.3);
  txt(s, "Base case (ESTIMATE)", { x: 7.55, y: 1.5, w: 5, h: 0.4, fontFace: HEAD, fontSize: 18, bold: true });
  bullets(s, ["600 statement files + 4,000 documents a month (assumed)",
    `~${hoursSaved} hours saved, ${base.fte_saved} FTE of capacity`,
    `Payback ~${base.payback} months after a 0.9 bn VND one-off`], { x: 7.55, y: 2.0, w: 5, h: 1.6, fontSize: 14 });
  card(s, 7.3, 3.9, 5.4, 2.55, "FBF3E4");
  seal(s, "warn", 7.55, 4.1, 0.6, WARN);
  txt(s, "If the assumptions are wrong", { x: 8.3, y: 4.15, w: 4.3, h: 0.45, fontFace: HEAD, fontSize: 17, bold: true, color: WARN });
  txt(s, "Manual minutes move the result more than automation: at 30/3 min the case is negative at every automation level (20-80%); at 60/6 min it is positive at every level. So week 1 times the real work and the case is re-run before anything scales.",
    { x: 7.55, y: 4.75, w: 4.95, h: 1.65, fontSize: 13 });
  s.addNotes("Walk the trade-off: the business case is mostly a people-time model. Name the input that flips the sign. Every input in the workbook is tagged measured, public or assumed; change one live if asked.");

  // ===== 7. How it works =====
  pres.addSection({ title: "Build" });
  s = content("A model reads, our checks decide, a person approves", "Build");
  const steps = [["file", "Upload", "PDF, scan or phone photo; web UI or API"], ["eye", "OCR", "Text layer free; image pages to the vision model"],
    ["list", "Classify", "Fixed taxonomy; must quote evidence and name the customer"], ["check", "Check", "Evidence in text; statement identities; two reads agree"],
    ["folder", "File", "company / year / period-or-type, sidecar JSON, PII masked"], ["book", "Publish + ask", "OpenViking tree; answers cite the page"]];
  steps.forEach(([ic, h, b], i) => {
    const x = 0.6 + i * 2.05;
    card(s, x, 1.5, 1.85, 2.9);
    seal(s, ic, x + 0.6, 1.7, 0.65, i === 3 ? OK : SEAL);
    txt(s, h, { x: x + 0.12, y: 2.5, w: 1.6, h: 0.4, fontSize: 16, bold: true, align: "center" });
    txt(s, b, { x: x + 0.12, y: 2.95, w: 1.6, h: 1.4, fontSize: 12, color: INK2, align: "center" });
    if (i < 5) s.addShape(pres.shapes.LINE, { x: x + 1.87, y: 2.95, w: 0.16, h: 0, line: { color: MUTED, width: 1.5, endArrowType: "triangle" } });
  });
  card(s, 0.6, 4.7, 5.9, 1.9, "FBF3E4");
  seal(s, "user", 0.8, 4.9, 0.6, WARN);
  txt(s, "Uncertain? A person decides", { x: 1.55, y: 4.95, w: 4.8, h: 0.4, fontSize: 16, bold: true, color: WARN });
  txt(s, "Failed check, low confidence, type outside the taxonomy or kill switch on: the document waits in the review queue with its reasons and the page image. Nothing unapproved reaches the knowledge base.",
    { x: 1.55, y: 5.4, w: 4.8, h: 1.15, fontSize: 12.5 });
  card(s, 6.8, 4.7, 5.9, 1.9);
  seal(s, "db", 7.0, 4.9, 0.6, INK2);
  txt(s, "Every step is on the record", { x: 7.75, y: 4.95, w: 4.8, h: 0.4, fontSize: 16, bold: true });
  txt(s, "Audit log: model, prompt hash, tokens, latency, raw reply, checks, decision, reviewer, correction, rollback, alert. Any filed value can be traced to a page and replayed.",
    { x: 7.75, y: 5.4, w: 4.8, h: 1.15, fontSize: 12.5 });
  s.addNotes("This is the demo flow. Point out the customer rule: the classifier must name the bank's customer, not the bank, the seller or the auditor; six of the sixteen test documents are built to trap exactly that.");

  // ===== 8. Architecture =====
  s = content("Target architecture: stateless workers, one gateway", "Build");
  const box = (x, y, w, h, t, sub, fill = MIST, color = INK) => {
    card(s, x, y, w, h, fill);
    txt(s, t, { x: x + 0.12, y: y + 0.1, w: w - 0.24, h: 0.35, fontSize: 13.5, bold: true, color });
    if (sub) txt(s, sub, { x: x + 0.12, y: y + 0.45, w: w - 0.24, h: h - 0.5, fontSize: 11, color: color === PAPER ? "D8E0E8" : INK2 });
  };
  const arrow = (x1, y1, x2, y2, dash) => s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    flipH: x2 < x1, flipV: y2 < y1, line: { color: MUTED, width: 1.5, endArrowType: "triangle", dashType: dash ? "dash" : "solid" } });
  box(0.6, 1.45, 2.3, 1.05, "Intake", "Web upload, API, branch scanners, mailbox / SFTP");
  box(0.6, 2.8, 2.3, 0.85, "Job queue", "one document per job");
  box(3.4, 1.45, 3.4, 2.2, "Stateless workers (N)", "1 route pages\n2 OCR (text layer free, images to VLM)\n3 classify + evidence\n4 extract + validate\n5 mask PII\nIdempotent: content-hash id, page cache", INK, PAPER);
  box(7.3, 1.45, 2.5, 1.0, "Model gateway", "LiteLLM: keys, rate limits, budgets");
  box(10.3, 1.45, 2.4, 0.95, "In-bank VLM", "target endpoint", "E6F2EC", OK);
  box(10.3, 2.6, 2.4, 0.95, "Hosted model", "prototype only, public data", "F7EDEE", SEAL);
  box(3.4, 4.05, 1.9, 1.1, "Review queue", "uncertain: approve / correct; page image", "FBF3E4", WARN);
  box(5.7, 4.05, 1.9, 1.1, "Filing", "company / year / period; sidecar JSON");
  box(8.0, 4.05, 2.0, 1.1, "Knowledge base", "OpenViking tree, masked text, summaries");
  box(10.4, 4.05, 2.3, 1.1, "Q&A + access layer", "clearance from AD groups; cites pages");
  box(3.4, 5.5, 4.2, 1.05, "Audit log (append-only) → monitor → alerts", "metrics, thresholds, Teams / Slack webhook, UI banner");
  box(8.0, 5.5, 2.0, 1.05, "Version history", "rollback per document or release");
  box(10.4, 5.5, 2.3, 1.05, "Existing systems", "LOS / spreading tool read the sidecar; DMS holds files");
  arrow(1.75, 2.5, 1.75, 2.8); arrow(2.9, 3.2, 3.4, 3.2); arrow(6.8, 1.95, 7.3, 1.95); arrow(9.8, 1.9, 10.3, 1.9); arrow(9.8, 2.2, 10.3, 3.05, true);
  arrow(4.4, 3.65, 4.4, 4.05); arrow(6.3, 3.65, 6.6, 4.05);  // uncertain -> review; confident -> filing
  [5.38, 7.68, 10.08].forEach(x => s.addShape(pres.shapes.RIGHT_ARROW, { x, y: 4.48, w: 0.24, h: 0.24, fill: { color: MUTED }, line: { color: MUTED, width: 0 } }));
  s.addNotes("Thousands of users: ingestion scales by adding workers behind a queue; review and Q&A scale separately so one cannot starve the other. Integration is the sidecar JSON; DocPipe never becomes the system of record. Access control lives in our layer, not in the KB vendor.");

  // ===== 9. Decisions =====
  s = content("Three decisions and what they cost in money, speed and risk", "Build");
  const dec = [["cpu", "Vision model for OCR, not an OCR engine + rules",
    `Gain: reads diacritics, stamps, skewed photos, tables; no templates. ${EV.numbers_exact} numbers exact.`,
    `Price: $${EV.cost_per_doc_usd} and ${EV.seconds_per_doc_mean} s per document; can invent text (seen: a table header); images leave the bank if hosted.`,
    "Limit: checks, review, in-bank endpoint gate; text layer used free when present."],
  ["scale", "Checks and people decide, not model confidence",
    "Gain: every auto-filed result passed rules we can explain to an auditor; failures are countable.",
    "Price: correct documents sometimes wait (false alarms on new layouts); reviewer minutes.",
    "Limit: page image next to the value; thresholds from pilot data; review rate alerted."],
  ["db", "OpenViking behind an adapter, our own access layer",
    "Gain: viking:// tree mirrors the folders; per-document summaries rank well; agents via MCP.",
    "Price: AGPL-3.0, young project, RBAC unverified; ~40 s summary call per document.",
    "Limit: local BM25 fallback built; citations and access filter stay in our code; legal review."]];
  dec.forEach(([ic, h, g, p, l], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.4, 3.85, 5.25);
    seal(s, ic, x + 0.25, 1.6, 0.65);
    txt(s, h, { x: x + 0.25, y: 2.4, w: 3.4, h: 0.85, fontFace: HEAD, fontSize: 17, bold: true });
    txt(s, g, { x: x + 0.25, y: 3.3, w: 3.4, h: 1.0, fontSize: 12.5, color: OK });
    txt(s, p, { x: x + 0.25, y: 4.35, w: 3.4, h: 1.15, fontSize: 12.5, color: SEAL });
    txt(s, l, { x: x + 0.25, y: 5.55, w: 3.4, h: 1.0, fontSize: 12.5, color: INK2 });
  });
  s.addNotes("Pick one to walk through live as the trade-off discussion: decision 2 is the core idea. If time allows, show the threshold in config and what changes when you move it.");

  // ===== 10. Security, privacy, audit =====
  s = content("Security, privacy and audit are designed in, not bolted on", "Build");
  const sec = [["lock", "Data classification", "Each document tagged internal or restricted from what it publishes. Originals and the PII map stay in a restricted store; the KB gets masked text only."],
    ["shield", "Access control", "Q&A drops chunks above the caller's clearance before the model sees them; a restricted chunk never reached an internal user in tests."],
    ["list", "Audit trail", "Append-only log of every model call, check, decision, approval, correction, rollback, alert and kill-switch change, with actor and time."],
    ["eye", "Prompt injection", "Document text is data, never instructions. A contract telling the model to reclassify it was filed correctly; Q&A is read-only."]];
  sec.forEach(([ic, h, b], i) => {
    const x = 0.6 + (i % 2) * 6.15, y = 1.4 + Math.floor(i / 2) * 1.75;
    card(s, x, y, 5.95, 1.55);
    seal(s, ic, x + 0.22, y + 0.25, 0.6, INK2);
    txt(s, h, { x: x + 1.0, y: y + 0.18, w: 4.8, h: 0.35, fontSize: 15, bold: true });
    txt(s, b, { x: x + 1.0, y: y + 0.55, w: 4.8, h: 0.95, fontSize: 12.5, color: INK2 });
  });
  const lad = [["L1", "Local regex: Vietnamese IDs, phones, e-mails", "Built, measured", OK], ["L2", "+ local Vietnamese NER for names, addresses", "Not built: names are a known gap", WARN],
    ["L3", "In-bank VLM endpoint: images never leave", "Gate before pilot", SEAL]];
  txt(s, "Privacy ladder: a text filter cannot mask an image, so the real barrier is where the model runs", { x: 0.6, y: 5.0, w: 12, h: 0.4, fontSize: 14, bold: true });
  lad.forEach(([l, d, st, c], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 5.5, 3.85, 1.1, "F4F6F8");
    txt(s, l, { x: x + 0.2, y: 5.62, w: 0.7, h: 0.5, fontFace: HEAD, fontSize: 24, bold: true, color: c });
    txt(s, d, { x: x + 0.95, y: 5.6, w: 2.8, h: 0.55, fontSize: 12 });
    txt(s, st, { x: x + 0.95, y: 6.15, w: 2.8, h: 0.35, fontSize: 11, bold: true, color: c });
  });
  s.addNotes("Design for the auditor: every claim here is testable in the repo. Vietnamese PDP law 91/2025 and Decree 356 require an impact assessment for cross-border personal data, which is why the in-bank endpoint is a gate, not an optimisation.");

  // ===== 11. Evaluation =====
  s = content("Measured, not trusted: quality, failures, cost and latency", "Build");
  const evrows = [hdrRow(["What", "Set", "Result"]),
    ["Type, customer, year", "16 synthetic scans, 6 traps", `${EV.fully_correct}/16 all correct`], ["Printed amounts and codes", "same", `${EV.numbers_exact} exact`],
    ["Character error rate", "same", `median ${EV.median_cer.toFixed(3)}, mean ${EV.mean_cer.toFixed(3)}`], ["Wrong result auto-filed", "same", `${EV.wrong_but_auto_filed} (menu and faint receipt went to review)`],
    ["Injected statement errors", "real public filings", "6/6 routed to review"], ["Real dropped digit (511.184 → 51,184)", "Vinamilk annual report", "caught by a rule, corrected, logged"],
    ["Cited Q&A over filed documents", "31 answerable + 6 unanswerable", "31/31 cited correctly, 6/6 refused"],
    ["Cost / latency per document", "list price", `$${EV.cost_per_doc_usd} · ${EV.seconds_per_doc_mean} s (max ${EV.seconds_per_doc_max} s)`]];
  s.addTable(evrows, { x: 0.6, y: 1.4, w: 7.6, colW: [2.8, 2.3, 2.5], fontFace: BODY, fontSize: 12, color: INK, border: { type: "solid", pt: 0.75, color: LINE }, rowH: 0.55, valign: "middle", margin: 0.06 });
  card(s, 8.5, 1.4, 4.2, 5.25, "F7EDEE");
  seal(s, "warn", 8.72, 1.6, 0.6);
  txt(s, "Honest failure cases", { x: 9.45, y: 1.68, w: 3.2, h: 0.45, fontFace: HEAD, fontSize: 17, bold: true, color: SEAL });
  bullets(s, ["The OCR model added text: an invented table header and a stamp description (numbers still exact)",
    "A faint receipt was filed under the payee; a receipt rule is needed",
    "New issuer layouts caused false alarms until patterns were fixed",
    "Synthetic scans are easier than branch scans, and I wrote the labels: this proves the flow, not real accuracy"],
    { x: 8.72, y: 2.4, w: 3.8, h: 4.1, fontSize: 12.5 });
  s.addNotes("An evaluation with honest failures says more than a perfect demo. The CER of 0.27 on one invoice came from invented text, not wrong numbers. First pilot task: 200 real approved documents as a held-out set.");

  // ===== 12. Automation =====
  pres.addSection({ title: "Automate" });
  s = content("Automated to production standard, human in the loop", "Automate");
  const auto = [["redo", "Safe to re-run", "Content-hash id, per-page cache, re-filing replaces the old copy"],
    ["chart", "Monitored", "Review rate, queue age, validator failures, schema errors, p95 latency, cost / doc"],
    ["bell", "Alerts", "Thresholds in config; fire once, resolve once; file, audit, UI banner, webhook"],
    ["power", "Kill switch", "One toggle: nothing auto-files, everything to review; logged"],
    ["rotate", "Rollback", "Every replaced version kept; per document or whole release; reversible"],
    ["user", "Human review", "Approve or correct one value; re-validated, re-filed, reviewer logged"]];
  auto.forEach(([ic, h, b], i) => {
    const x = 0.6 + (i % 3) * 4.1, y = 1.4 + Math.floor(i / 3) * 1.6;
    card(s, x, y, 3.85, 1.4);
    seal(s, ic, x + 0.2, y + 0.22, 0.58, i === 2 || i === 4 ? SEAL : INK2);
    txt(s, h, { x: x + 0.95, y: y + 0.18, w: 2.8, h: 0.35, fontSize: 15, bold: true });
    txt(s, b, { x: x + 0.95, y: y + 0.55, w: 2.8, h: 0.8, fontSize: 12, color: INK2 });
  });
  card(s, 0.6, 4.75, 12.1, 1.9, "F4F6F8");
  txt(s, "Shown on real output", { x: 0.85, y: 4.9, w: 5, h: 0.4, fontFace: HEAD, fontSize: 17, bold: true });
  bullets(s, ["The monitor fired a real alert: a review ticket had waited 51 h against a 24 h limit",
    "Rollback drill: a filed invoice restored to v1, re-published to the KB, actor logged, and the quality alarm tripped as designed",
    "Governance: confidence comes from checks (each failure halves it); threshold 0.90; nothing unapproved is published"],
    { x: 0.85, y: 5.35, w: 11.6, h: 1.25, fontSize: 13 });
  s.addNotes("Show this live in the System tab: metrics, the active alert, the kill switch. Then a document's Versions tab and a rollback. What breaks if the tool is wrong is in the rollout document: the worst case is a wrong value that passes every check, which the weekly audit sample catches.");

  // ===== 13. Impact =====
  s = content("Before and after, and projected at scale (estimate)", "Automate");
  const ba = [hdrRow(["", "Before (manual)", "After (DocPipe)"]),
    ["Statement file", "60 min (assumed; public 30-360)", "30-60 s machine; 15 min review if flagged (~40%)"],
    ["Onboarding document", "6 min (assumed)", `${EV.seconds_per_doc_mean} s machine; 2 min review if flagged (~30%)`],
    ["Model cost", "n/a", `$${EV.cost_per_doc_usd} per document (measured)`],
    ["Traceability", "Depends on who keyed it", "Page, check and log line for every value"]];
  s.addTable(ba, { x: 0.6, y: 1.4, w: 6.6, colW: [1.8, 2.2, 2.6], fontFace: BODY, fontSize: 12, color: INK, border: { type: "solid", pt: 0.75, color: LINE }, rowH: 0.62, valign: "middle", margin: 0.06 });
  s.addChart(pres.charts.BAR, [{ name: "FTE of capacity", labels: ["Pilot team", "One region", "Bank-wide (5x)"], values: scale.map(x => x.fte) }], {
    x: 7.5, y: 1.35, w: 5.2, h: 3.25, barDir: "col", chartColors: [INK], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0",
    dataLabelFontFace: BODY, dataLabelFontSize: 13, dataLabelColor: INK, showTitle: true, title: "FTE of capacity released (ESTIMATE)", titleFontFace: BODY, titleFontSize: 13, titleColor: MUTED,
    catAxisLabelColor: MUTED, valAxisLabelColor: MUTED, catAxisLabelFontFace: BODY, valAxisLabelFontFace: BODY, catAxisLabelFontSize: 12, valAxisLabelFontSize: 11,
    valGridLine: { color: "E3E8ED", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false });
  card(s, 0.6, 4.75, 12.1, 1.9, "FBF3E4");
  txt(s, "Labelled as estimates", { x: 0.85, y: 4.9, w: 5, h: 0.4, fontFace: HEAD, fontSize: 17, bold: true, color: WARN });
  bullets(s, [`One region (base volumes): ~${scale[1].hours_saved_month} h a month, ${scale[1].fte} FTE, ${fmtBn(scale[1].net_12_mVND)} bn VND net in 12 months`,
    `Bank-wide at 5x volume (assumed): ~${scale[2].hours_saved_month.toLocaleString("en-US")} h a month, ${scale[2].fte} FTE; run cost grows with the square root of volume`,
    `A single pilot team does not pay back the one-off (${fmtBn(scale[0].net_12_mVND)} bn VND): the case needs at least a region`],
    { x: 0.85, y: 5.35, w: 11.6, h: 1.25, fontSize: 13 });
  s.addNotes("Every 'before' number is an assumption until week 1 times the real work. The 'after' machine numbers are measured. Saying the pilot alone does not pay back is part of the honest case.");

  // ===== 14. Metrics =====
  s = content("One North Star, four supporting metrics, shadow then A/B", "Automate");
  card(s, 0.6, 1.4, 5.6, 2.6, INK);
  txt(s, "NORTH STAR", { x: 0.9, y: 1.6, w: 5, h: 0.35, fontSize: 12, bold: true, color: "F2B8C0", charSpacing: 2 });
  txt(s, "Straight-through correct rate", { x: 0.9, y: 1.95, w: 5.1, h: 0.6, fontFace: HEAD, fontSize: 24, bold: true, color: PAPER });
  txt(s, "Share of documents filed with no human touch and no critical error found by the weekly audit sample. Target at day 90: at least 60%.",
    { x: 0.9, y: 2.6, w: 5.1, h: 1.3, fontSize: 13.5, color: "D8E0E8" });
  const sup = [["Handling minutes per document", "−50% vs week-1 baseline"], ["Critical error rate on auto-filed (5% audit)", "≤ manual and < 0.5%"],
    ["Review queue share / oldest ticket", "< 30% / < 24 h"], ["Questions with a correct page citation", "≥ 90% of 50"]];
  sup.forEach(([m, t], i) => {
    const y = 1.4 + i * 0.66;
    card(s, 6.5, y, 6.2, 0.56);
    txt(s, m, { x: 6.7, y: y + 0.13, w: 3.7, h: 0.32, fontSize: 13, bold: true });
    txt(s, t, { x: 10.3, y: y + 0.13, w: 2.3, h: 0.32, fontSize: 13, color: OK, bold: true, align: "right" });
  });
  const phases = [["Weeks 1-2", "Baseline", "Time the manual work; audit its errors"], ["Weeks 3-6", "Shadow", "DocPipe runs beside the team; nothing used; compare"],
    ["Weeks 7-12", "A/B by batch", "Randomised by day: half start from DocPipe, half manual"], ["Later", "Stepped wedge", "A second team joins: a second comparison"]];
  phases.forEach(([w, h, b], i) => {
    const x = 0.6 + i * 3.08;
    card(s, x, 4.35, 2.85, 1.65, "F4F6F8");
    txt(s, w, { x: x + 0.2, y: 4.48, w: 2.5, h: 0.3, fontSize: 11, bold: true, color: MUTED });
    txt(s, h, { x: x + 0.2, y: 4.78, w: 2.5, h: 0.4, fontSize: 16, bold: true, color: SEAL });
    txt(s, b, { x: x + 0.2, y: 5.2, w: 2.5, h: 0.75, fontSize: 12, color: INK2 });
  });
  txt(s, "Stop if: audited error rate stays above manual after two tuning cycles · review queue above 50% after week 6 · timed saving under 20% · any PII or access leak · no approved endpoint by week 4",
    { x: 0.6, y: 6.2, w: 12.1, h: 0.6, fontSize: 12.5, color: SEAL, bold: true });
  s.addNotes("The North Star only rewards automation that is right. Stop criteria are agreed with risk before the pilot starts, so stopping is a decision already made, not an argument.");

  // ===== 15. Rollout =====
  s = content("Three months, five people, a gate at every phase", "Automate");
  const ro = [["1-2", "Foundations", "Interviews, timed baseline, model endpoint, legal review (AGPL, cross-border)", "Risk signs data handling; case re-run"],
    ["3-6", "Shadow pilot", "One credit team; weekly audit; 200 real documents labelled; alerts to team channel", "Error ≤ manual; review < 50%"],
    ["7-10", "A/B assist", "Half the batches start from DocPipe; Q&A on approved documents", "Handling time −20% or better"],
    ["11-13", "Harden, scale", "Second team by configuration only; rollback drill; audit walkthrough", "Go / no-go for the region"]];
  ro.forEach(([w, h, d, g], i) => {
    const x = 0.6 + i * 3.08;
    card(s, x, 1.4, 2.85, 3.15);
    txt(s, "Weeks " + w, { x: x + 0.2, y: 1.55, w: 2.5, h: 0.3, fontSize: 11, bold: true, color: MUTED });
    txt(s, h, { x: x + 0.2, y: 1.85, w: 2.5, h: 0.45, fontFace: HEAD, fontSize: 18, bold: true });
    txt(s, d, { x: x + 0.2, y: 2.35, w: 2.5, h: 1.2, fontSize: 12, color: INK2 });
    txt(s, [{ text: "Gate: ", options: { bold: true, color: OK } }, { text: g }], { x: x + 0.2, y: 3.65, w: 2.5, h: 0.8, fontSize: 12 });
  });
  txt(s, "Team: product and process owner · 2 engineers · risk partner (part time) · analyst from the pilot team (part time)", { x: 0.6, y: 4.7, w: 12.1, h: 0.35, fontSize: 13, color: MUTED });
  const risks = [["A wrong value passes every check", "Weekly audit sample + 'auto-filed then corrected' alarm; add the missing check"],
    ["Real scans are harder than the test set", "Week-3 eval on 200 real documents; thresholds set on real data"],
    ["Review burden cancels the savings", "Review rate monitored; tune false alarms; stop rule"]];
  txt(s, "Biggest risks and how we find out early", { x: 0.6, y: 5.15, w: 12, h: 0.4, fontSize: 15, bold: true });
  risks.forEach(([r, m], i) => {
    const x = 0.6 + i * 4.1;
    txt(s, r, { x, y: 5.6, w: 3.85, h: 0.35, fontSize: 13, bold: true, color: SEAL });
    txt(s, m, { x, y: 5.95, w: 3.85, h: 0.75, fontSize: 12, color: INK2 });
  });
  s.addNotes("Name the biggest risk plainly: a wrong value that passes every check. The early signal is the audit sample from week 3. Personal data to a hosted model is blocked by the endpoint gate.");

  // ===== 16. Close =====
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "DARK_TOP", sectionTitle: "Close" });
  s.addText("Built to be reused, and honest about what it is not", { placeholder: "title" });
  const colTitle = { fontFace: HEAD, fontSize: 18, bold: true, color: PAPER };
  txt(s, "Another team adopts it by configuration", { x: 0.8, y: 2.1, w: 5.6, h: 0.45, ...colTitle });
  bullets(s, ["Copy config: taxonomy, model endpoint, thresholds, KB root, alert webhook",
    "Drop 15-20 labelled samples; run the eval; go live only if wrong-auto-filed is 0",
    "Same UI, same audit, same rollback: one platform, many teams"], { x: 0.8, y: 2.65, w: 5.6, h: 2.0, fontSize: 14, color: "D8E0E8" });
  txt(s, "What I would not build", { x: 7.0, y: 2.1, w: 5.6, h: 0.45, ...colTitle });
  bullets(s, ["Credit decisioning: a different risk class; DocPipe prepares inputs",
    "Fine-tuning: no labelled data yet; checks already meet the bar on samples",
    "A warehouse or a DMS / LOS replacement: DocPipe files into them",
    "Unsupervised filing outside the taxonomy"], { x: 7.0, y: 2.65, w: 5.6, h: 2.0, fontSize: 14, color: "D8E0E8" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: 5.0, w: 11.7, h: 1.45, rectRadius: 0.08, fill: { color: INK2 }, line: { color: INK2, width: 0 } });
  txt(s, [{ text: "Decision requested: ", options: { bold: true, color: "F2B8C0" } },
    { text: "approve a 6-week shadow pilot with one credit team, with the in-bank endpoint gate and the stop rules above. I will bring back real-scan accuracy, timed savings and a re-run business case." }],
    { x: 1.1, y: 5.2, w: 11.1, h: 1.1, fontSize: 16, color: PAPER });
  s.addNotes("Close on the decision. Live change options for Q&A: (1) raise governance.auto_file_threshold in config and re-run a document to show it go to review; (2) add a document type to the taxonomy; (3) change the manual minutes in the business case and read the new payback.");

  const out = path.join(__dirname, "DocPipe_deck.pptx");
  await pres.writeFile({ fileName: out });
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(fs.readFileSync(out));
  // copy file entries only: folder entries upset cloud co-editing (JSZip's remove() on a folder deletes its children)
  const clean = new JSZip();
  for (const name of Object.keys(zip.files)) {
    if (!zip.files[name].dir) clean.file(name, await zip.files[name].async("nodebuffer"), { createFolders: false });
  }
  fs.writeFileSync(out, await clean.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  console.log("wrote slides/DocPipe_deck.pptx");
}
main().catch(e => { console.error(e); process.exit(1); });
