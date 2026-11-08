# Automation and rollout plan

Status: plan plus what is already built. "Built" means it runs in `docpipe`; "planned" means it does not exist yet.
All projected impact is an **estimate** from placeholder inputs in `model/business_case.xlsx`.

## 1. The automated step (production standard checklist)

The automated step is: statement pages in, validated line items filed with evidence, or a review ticket.

| Requirement | State | How |
|---|---|---|
| Safe to re-run | Built | Content-hash document id; `_state` marks done; per-page cache makes a re-run resume; re-filing replaces the earlier copy |
| Monitored | Partly | `audit.jsonl` has every call, decision, correction. Dashboards and alerts are planned (Langfuse + queue metrics) |
| Alerts | Planned | See section 3 |
| Kill switch | Built | `docpipe kill on` sends everything to review; verified in the seeded-error test |
| Rollback | Partly built | Re-filing after a correction replaces the earlier copy; a bulk rollback to a previous model or rule version needs the stored raw responses and is planned |
| Human in the loop | Built | Review queue with reasons; `review correct` fixes a value, re-validates, re-files, logs the reviewer |

## 2. Governance (what the tool is allowed to decide)

- **Confidence** comes from signals (validators, two-pass agreement, text-layer agreement). Each failed check halves it. Threshold in `config/pipeline.yaml` (`governance.auto_file_threshold`), to be set from a calibration curve on pilot data.
- **Review queue** receives: failed checks, low confidence, document type outside the taxonomy, kill switch, model errors.
- **Audit log**: model and version, prompt hash, tokens, latency, raw response, check results, decision, reviewer, correction.
- **What breaks if the tool is wrong**

| Failure | What catches it | If not caught |
|---|---|---|
| A digit is dropped or misread | Text-layer check (text PDFs), two-pass agreement (scans), balance and statement identities | Wrong value in a spread; weekly audit sample is the backstop |
| Wrong unit | Unit presence and consistency checks | Values off by 1,000 or 1,000,000; audit sample |
| Wrong document type or company | Fixed taxonomy; low confidence goes to review; cross-period tie-out | Misfiled document; found by the next period's tie-out |
| Hidden instructions in a document | Document text is data in the prompt; the Q&A agent is read-only | See prompt-injection tests (planned) |
| Model behaviour changes silently | Pinned model name, prompt hash, evaluation re-run before any upgrade | Drift; detected by the audit sample and the weekly eval |

## 3. Monitoring and alerts (planned)

| Signal | Alert when |
|---|---|
| Review-queue size and age | Queue above an agreed size or oldest ticket above an agreed age |
| Validator failure rate | A step change versus the trailing week (often means a new template or a model change) |
| Cost per document and tokens per page | Above budget |
| Latency per page, error and retry rate | Above agreed limits |
| Share of auto-filed documents later corrected | Above the agreed ceiling (this is the quality number that matters) |

## 4. Three-month rollout (team of about 5)

Team: product/process owner (1), engineers (2), risk and compliance partner (1, part time), analyst from the pilot team (1, part time).

| Weeks | Phase | Deliverables | Gate to proceed |
|---|---|---|---|
| 1-2 | Foundations | Real interviews; in-bank or contractually approved model endpoint decision; legal review of the KB license and cross-border rules; baseline time and error measurement on the pilot team's current work | Risk signs the data-handling approach; baseline recorded |
| 3-6 | Shadow pilot | Tool runs beside manual work on one team; weekly audit sample; thresholds set from pilot data; evaluation set grown from real (approved) documents | Critical-field error rate on auto-filed documents below the agreed ceiling; review queue below the agreed share |
| 7-10 | Assist mode | Analysts start from pre-filled spreads; review queue live; Q&A agent on approved documents; dashboards and alerts | Handling time per document down versus baseline; no unresolved audit finding |
| 11-13 | Harden and scale | Second team onboards by configuration only; rollback and monitoring complete; risk walkthrough of the audit log; decision memo for wider rollout | Second team live without code changes |

### Key risks and how they are reduced

| Risk | Early signal | Mitigation |
|---|---|---|
| Silent numeric errors that pass every check | Weekly audit sample finds a wrong auto-filed value | Add the check that would have caught it; lower the auto-file share until it does |
| Personal data to a hosted model | Any non-public document in scope | In-bank endpoint before any such document; privacy ladder L1 to L3 |
| Review burden cancels the savings | Review rate and minutes per flagged document | Measure from week 3; tune validators; stop criterion |
| Adoption | Analysts keep re-keying | Embed an analyst in the pilot; show source page next to every value |
| Vendor or license issue (AGPL KB, shared subscription route in the prototype) | Legal review findings | KB behind an adapter; priced, contractual model endpoint for the pilot |

## 5. Before and after, and projection at scale [estimates]

Numbers in the workbook are placeholders; replace them before use. What is measured today (small samples, public filings)
is in `docs/eval-results.md`: cost about $0.0013 per page, 26 to 32 seconds per page, 100% of extracted numbers
printed on the page for clean text PDFs, 97.8% on degraded scans, with the remaining errors routed to review.

To project across teams or branches, set `docs_per_month` to the total volume and keep the per-document inputs from
the pilot: the model cost is linear in pages, the review cost depends on the flagged share, and fixed costs are
shared. The sensitivity table (auto-file share 20% to 90%) shows how much the result depends on that one input.

## 6. Reuse by another team

What another team changes, and nothing else: `config/pipeline.yaml` (taxonomy, statement keywords, thresholds, model,
PII detector), plus validator patterns in `docpipe/validators.py` for statement types not yet covered. A new document type
is a taxonomy entry; a new statement layout is a label pattern. The README documents setup, and `evals/` provides the
harness to measure the new set before trusting it.
