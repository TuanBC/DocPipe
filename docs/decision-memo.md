# Decision memo: DocPipe, governed document intake for corporate credit

TuanBC · Techcombank AI Transformation Expert Challenge · 9 November 2026

**Recommendation.** Run a 6-week shadow pilot of DocPipe with one corporate-credit team, then an A/B test for
6 weeks, on the hybrid design: a vision model reads documents; our own checks, review queue, filing, knowledge base
and audit trail decide what is trusted. Gate: an in-bank or contractually approved model endpoint before any
non-public document. Stop if the stop criteria in section 7 are met.

Labels used below: **[measured]** prototype result on public filings or synthetic scans (small samples);
**[assumed]** placeholder in `model/business_case.xlsx`, to be replaced with pilot data; **[public]** vendor or
public source, which brackets a number but is not evidence about Techcombank.

## 1. Problem

A corporate-credit file is a pile of documents: financial statements and annual reports, the business registration,
board resolutions, contracts, invoices, collateral papers, tax filings, bank statements. Most arrive as scans or
phone photos. Today someone reads each one, works out what it is, renames it, files it in a shared drive, and keys
the numbers that matter (for statements: dozens of line items). Three things go wrong:

1. **Time.** Public vendor material puts a manual financial spread at 30 minutes to 6 hours per borrower **[public]**.
   Filing a single onboarding document is minutes, but there are many of them per customer.
2. **Trust.** A keyed number has no link back to its page; "where does this come from" depends on who keyed it.
   A dropped digit can reach a credit memo.
3. **Re-finding.** The same documents are needed again ("what is the collateral on the An Phát facility?"), and the
   answer means asking a colleague or reopening files.

Problem statement: *credit staff spend hours reading, filing and re-keying documents that a machine can read, and the
result is neither traceable nor searchable.*

## 2. Stakeholders and where they conflict

| Role | Wants | Fears |
|---|---|---|
| Credit analysts, RMs (users) | Less keying and hunting; numbers they can trust; fast answers | Blame for tool errors; checking the tool costs as much as doing it by hand |
| Credit operations (process owner) | Throughput, standard folders and names, SLAs | A review queue that grows and must be staffed |
| Risk and compliance | Page-level traceability, access control, no personal data leaving without a legal basis, replayable decisions | Silent numeric errors; unreviewed model changes; data in a foreign API |
| Technology and data | Swappable parts, clear licences, low maintenance, fits existing systems | Lock-in; an AGPL surprise; an unowned model |

Conflicts that shape the design: **speed vs traceability** (every value carries its page, deterministic checks gate
auto-filing); **capability vs data control** (hosted model only for public data; in-bank endpoint before pilot);
**automation vs verification cost** (reviewers see only flagged documents, and the review rate is measured and
alerted on). **Evidence status: no real interview has been held yet.** Until then, each role's needs come from
cited desk research (`docs/stakeholder-research.md`): 70% of institutions lost clients to slow onboarding in 2025
(Fenergo survey); manual spreading takes 2-6 analyst hours per borrower (vendor range); MB reports 75% less
document-checking time with DocAI (bank's own claim); the Personal Data Protection Law (fines up to 5% of revenue for
cross-border violations) and SBV Circular 53/2026 (risk classification, the bank stays responsible for vendor AI) set
the compliance bar. Five interviews across four roles are the first pilot gate (`docs/interview-notes.md`).

## 3. Opportunity (12 months, estimate)

Two workflows, one tool: **A** statement spreading (600 files a month **[assumed]**, 60 manual minutes each
**[assumed, low end of public range]**) and **B** onboarding and credit-file documents (4,000 a month, 6 minutes each
**[assumed]**). Measured inputs: auto-file share (statements 11/14 on the dev set, general documents 14/16 on
synthetic scans, discounted to 60% and 70%) and model cost ($0.004 per statement file, $0.0013 per document).

| Scenario (estimate) | Hours saved / month | FTE released | 12-month net (VND) | Payback |
|---|---|---|---|---|
| Pessimistic: 30% auto-filed, fast manual baseline (30 / 3 min) | ~290 | 1.8 | **-0.54 bn** | 30 months |
| **Base** (inputs above) | **~870** | **5.5** | **+1.2 bn** | **5 months** |
| Optimistic: 85% auto-filed, slow baseline (120 / 10 min) | ~1,790 | 11.2 | +4.0 bn | 2 months |

**What happens if the assumptions are wrong.** The result moves most with the *manual minutes per document*, not the
automation rate: with a 30 / 3 minute baseline the case loses money at every automation level from 20% to 80%; with
60 / 6 minutes it is positive at every level. So the first pilot task is to time the current work, and the business
case is re-run on that number before anything is scaled. The model cost is negligible (~0.2 m VND a month); the costs
that matter are people and run cost. Risk value (errors avoided) is small in the model (18 m VND a month, assumed) and
is not what justifies the project. At bank scale (5x the base volume **[assumed]**) the same per-document economics
give ~27 FTE of capacity. All projections are estimates.

## 4. Options

| Option | Speed to value | Control and auditability | Cost | Lock-in | Verdict |
|---|---|---|---|---|---|
| Do nothing | None | Manual, inconsistent | Grows with volume | None | Baseline; the cost is staff time |
| Let staff use a chat assistant on their own | Fast | None: no audit, data leaves, no checks | Low licence | Medium | Rejected: shadow IT with customer data |
| Buy a document-processing suite | Fast start | Vendor-defined; Vietnamese statements and bank-specific checks unproven | Licence + per page | High | Test one vendor in parallel with the pilot on the same eval set |
| Build our own OCR + layout models | Slow | Full | High build, GPUs, templates | Low | Over-engineered for the value at stake |
| **Hybrid: a model reads, our checks decide (chosen)** | Fast | High: rules, evidence, review, audit are ours | Model cost ~zero; run cost and people dominate | Low: model and KB are swappable | **Chosen** |

Why: reading text is now the cheap, replaceable part. The scarce part is trust: checks, evidence, a review path and
an audit trail. The hybrid keeps those in the bank's hands and lets the model be swapped (hosted today, in-bank
tomorrow) without rewriting the pipeline.

## 5. What the prototype shows [measured, small samples]

- **End to end works**: upload a scan, OCR, classify, file into `company/year/period-or-type`, mask personal data,
  publish to an OpenViking knowledge base, answer questions with page citations; uncertain documents wait in a review
  queue; monitoring raises alerts; any filed version can be rolled back. Web UI and CLI.
- **General documents** (16 synthetic scans with traps): 16/16 type, customer and year correct; 106/106 printed amounts
  and codes exact; 0 wrong results auto-filed; the menu and a faint receipt went to review; a hidden instruction in a
  contract was ignored. $0.0013 and 13 s per document. Failure found: the model sometimes *adds* text (an invented
  table header).
- **Financial statements** (real public filings from three issuers): a real dropped digit (511.184 read as 51,184) was
  caught by a rule, corrected by a reviewer and re-filed with the correction logged; 6/6 injected errors routed to
  review; two-pass agreement flagged 129 of 130 wrong values on a harsh scan simulation. New issuer layouts produced
  false alarms that had to be fixed: reviewer time is a real cost.
- **Questions over filed documents**: 31/31 answerable questions correct with a valid page citation, 6/6 unanswerable
  refused, injected instructions not followed in the cases tried, no restricted-chunk leak.
- **Honest limits**: synthetic scans are easier than branch scans (clean fonts, no handwriting, I wrote the labels);
  retrieval rules were tuned on the questions they are scored on; the personal-data detector misses names.

## 6. Decision

Proceed to the pilot (section 7 and `docs/rollout-and-automation.md`), conditional on: an in-bank or contractually
approved model endpoint before any non-public document; legal review of the OpenViking licence (AGPL-3.0) and of
cross-border data rules; five stakeholder interviews and a timed baseline before targets are fixed.

**Not building**, and why: credit decisioning (a different risk class; DocPipe only prepares inputs); fine-tuning
(no labelled data yet, and prompting plus checks already meet the bar on the samples); an analytics warehouse
(the sidecar JSON feeds existing systems); a replacement for the document-management or loan-origination system
(DocPipe files into them); unsupervised filing of documents outside the taxonomy.

## 7. Success and stop criteria

**North Star metric: straight-through correct rate**, the share of incoming documents filed (and, for statements,
extracted) with no human touch *and* no critical error found by the weekly audit sample. It rewards automation only
when it is right.

| Supporting metric | Target at day 90 |
|---|---|
| Handling minutes per document (timed, vs the week-1 baseline) | -50% |
| Critical-field error rate on auto-filed documents (5% weekly audit sample) | at or below the manual error rate measured in week 1, and under 0.5% |
| Review queue: share of documents and age of oldest ticket | under 30%; under 24 h |
| Staff questions answered with a correct page citation | at least 90% on a 50-question audit set |

North Star target at day 90: at least 60% of documents straight-through correct, with the error target met.

**How impact is tested.** Weeks 1-2: baseline timing and error audit of current work. Weeks 3-6: shadow mode (DocPipe
runs beside manual work; nothing it produces is used; we compare). Weeks 7-12: A/B by document batch, randomised by
day, within the same team (half the batches start from DocPipe's output, half are done manually), measuring handling
time and audited errors; a second team joins later as a stepped-wedge comparison.

**Stop** (agreed with risk before the pilot starts) if any of: the audited critical error rate on auto-filed
documents stays above the manual rate after two tuning cycles; the review queue stays above 50% of documents after
week 6; the timed saving is under 20% (the business case is negative below roughly that); a personal-data or
access-control leak; no approved model endpoint by week 4.

## 8. Biggest risk, and how we find out early

**A wrong value that passes every check** (for example, a scanned page where both reads agree on the same wrong digit,
or invented text in a transcript of a document that has no validator). Early signal: the weekly audit sample of
auto-filed documents, compared with the source page, from week 3; any finding adds the check that would have caught
it and lowers the auto-file share until it does. The monitor's "auto-filed then corrected" alarm makes every such case
visible on the day it happens. Second risk: personal data reaching a hosted model once documents are not public,
which is mitigated by the in-bank endpoint gate and the privacy ladder.
