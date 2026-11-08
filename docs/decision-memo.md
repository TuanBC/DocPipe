# Decision memo: governed intake of financial statements for corporate credit

Status: draft. Numbers marked **[assumed]** are placeholders in `model/business_case.xlsx` and must be replaced
with interview or Techcombank data before anyone quotes them. Numbers marked **[measured]** come from the prototype
(`docs/eval-results.md`) on public Vietnamese filings, small samples.

## 1. Problem

Corporate credit teams receive company financial statements (báo cáo tài chính) and annual reports as PDFs and
scans, find the statement pages, read them and re-key line items. Files end up in shared drives with inconsistent
names, and "where does this number come from" depends on whoever keyed it. The same documents are then needed
again for questions that today are answered by asking a colleague or re-opening the file.

Public vendor material puts a manual spread at 30 minutes to 6 hours per borrower and reports keying errors,
template inconsistency and verification effort that can cancel the savings. These are vendor claims with an
incentive to inflate; they bracket the input, they are not evidence about Techcombank. No interview has been done
yet (`docs/stakeholders.md`).

## 2. Stakeholders and where they conflict

Users (analysts, relationship managers) want less keying and numbers they can trust. Operations want throughput and a
standard filing structure. Risk and compliance want traceability from source page to decision, access control, and
no personal data leaving without a basis. Technology wants swappable components and clear licenses.

The conflicts that shape the design: speed vs traceability (resolved by evidence per value and deterministic
checks), capability vs data control (resolved by a staged privacy ladder and an in-bank endpoint before pilot), and
automation vs verification cost (resolved by measuring how many documents reach a reviewer).

## 3. Opportunity

Parameterised 12-month model, not a single number. Inputs and outputs are in the workbook; under the placeholder
inputs (1,000 documents a month, 45 manual minutes, 60% auto-filed, 10 review minutes for flagged documents) the
model gives about 680 analyst hours a month saved and a payback near month 5 **[assumed, illustrative only]**.
The sensitivity table shows the result at 20% to 90% auto-filed. The value that moves the result most is the
auto-file share, which is exactly what the pilot measures.

Risk side: a silent numeric error that reaches a credit decision. The prototype's controls target this; value of
avoided errors is an input, set to a placeholder.

## 4. Options

| Option | Speed to value | Control and auditability | Cost | Lock-in | Verdict |
|---|---|---|---|---|---|
| Do nothing | None | Manual, inconsistent | Grows with volume | None | Baseline |
| Buy a full document-processing suite | Fast to start | Vendor-defined; Vietnamese financials unproven (to be tested) | Licence + per page | High | Not for a first flow |
| Build everything (own OCR, own models) | Slow | Full | High build + GPU | Low | Over-engineered |
| **Hybrid: hosted/in-bank model + own validators, filing, KB, audit** | Fast | High: rules and evidence are ours | Per-page model cost, small | Low (model and KB swappable) | **Chosen** |

Why: the scarce part is not reading text, it is trust: checks, evidence, an audit trail, a review path. Those are
ours in the hybrid. The model is the replaceable part.

## 5. What the prototype shows [measured, small samples]

- A VLM reads Vietnamese statement pages including diacritics; on 7 real pages from two reports, 100% of extracted numbers were printed on the page when clean, 97.8% on degraded scans.
- One real digit drop (511.184 read as 51,184) was caught by a deterministic check, queued for review, corrected by a reviewer, re-validated and filed, with the correction logged.
- Injected errors: 6 of 6 scenarios routed to review as designed.
- Scans (no text layer): second-pass agreement flagged every wrong value in a mild degradation test (4 of 4) and 129 of 130 in a harsh one; the full pipeline sent both to review.
- Cost about $0.0013 per page at list price; 26 to 32 seconds per page.
- Three formats (Vinamilk IFRS-style, Hòa Phát VAS including a hybrid scanned report, Techcombank bank VAS): the controls filed documents whose arithmetic checks pass and escalated the one with disagreeing scan reads. **The first run on two of the three new issuers produced false alarms** (label patterns) that I had to fix; false alarms are reviewer time and are a real cost of the approach. Cross-year tie-out agreed on 6 of 6 key items.
- Question answering over the filed documents: 22 of 24 answerable questions correct with a valid page citation, 6 of 6 unanswerable refused, no ungrounded number; a poisoned chunk and a hostile instruction on a page image were not followed in the cases tried (9/9 and 1/1: obvious attacks only); a restricted chunk did not leak.
- All results are development-set behaviour: rules were tuned on the same documents. A held-out set from other issuers is the first pilot task.

What it does not show: accuracy on a statistically meaningful corpus, other statement types, behaviour under
production volume, or anything about real customer documents.

## 6. Decision

Proceed to a **6-week shadow pilot** with one credit team, running beside the manual process, on the hybrid design.
Conditions: an in-bank (or contractually approved) model endpoint before any non-public document; legal review of the
knowledge-base license (AGPL-3.0) and of cross-border data rules; real stakeholder interviews before the pilot
metrics are fixed.

Not building: credit decisioning, model fine-tuning, an analytics database, a core-system replacement,
unsupervised tagging in production.

## 7. Success and stop criteria

North Star: straight-through rate, the share of documents filed and extracted with no human touch and no
critical-field error. Supporting: handling time per document, review-queue rate, correct-with-citation rate on staff
questions. Numeric targets are set after the first evaluation on pilot data; the evaluation harness exists.

Stop if, after the controls are applied: the critical-field error rate on auto-filed documents stays above the
agreed ceiling, or the review queue stays above the agreed share of documents, or cost per document exceeds manual
cost. Thresholds are agreed with risk before the pilot starts.

## 8. Biggest risk

Silent numeric errors that pass every validator (for example, a wrong value on a scanned page that two passes
repeat identically). Early signal: a weekly audit sample of auto-filed documents during the pilot, compared with the
source page. Second risk: personal data reaching a hosted model once documents are not public; mitigated by the
privacy ladder and the in-bank endpoint gate.
