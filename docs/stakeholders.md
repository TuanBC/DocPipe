# Stakeholder map and evidence

**Status of evidence: no real interview has been done.** Everything below is either a public source (cited, mostly
vendor material with an incentive to inflate pain) or a simulated persona built from those sources. The brief asks for
5+ people across 3+ roles; at least 2 real conversations are needed before submission. The interview guide is at the end.

Evidence labels: **[Public]** cited source, **[Sim]** simulated persona (my inference from public sources, not a person).

## Roles, interests, conflicts

| Role | Wants | Fears | Evidence |
|---|---|---|---|
| Credit analyst / relationship manager (user) | Less keying and hunting for pages; trustworthy numbers; speed | Being blamed for tool errors; verification that costs as much as doing it by hand | [Public] vendor sources put a manual spread at 30-60 min (LenderAnalyzer) to 3-6 h (Aloan) or 4-6 h (Uptiq) per borrower, 2-4 h in others; keying errors, inconsistent templates, junior analysts spending time on entry. [Public] f2.ai: manual verification of automated output "can take as long as the workflow would have if just done manually". |
| Credit operations / process owner | Throughput, standard folders and naming, SLAs, capacity | Exception queues that grow; inconsistent files across analysts | [Public] Uptiq: for teams doing 15-20 deals a month spreading can take 40-60% of analyst time (vendor-modelled). [Public] Aloan: for smaller banks the bottleneck is analyst capacity. |
| Risk and compliance | Traceability from source page to decision; access control; no data leaving without a legal basis | Silent numeric errors; model changes that nobody reviewed; personal data in a foreign API | [Public] examiners want to reconstruct how a bank got from source documents to a decision (Aloan, on US SR 26-2 / OCC 2026-13; US guidance, not Vietnamese). [Public, Vietnam, secondary sources] Personal Data Protection Law 91/2025/QH15 and Decree 356/2025/ND-CP (effective 1 Jan 2026): cross-border transfers need an impact assessment filed with the authority; Circular 53/2026/TT-NHNN on AI in banking says outsourcing does not shift responsibility and asks vendors to be assessed for data-protection compliance. Full texts not read; confirm with legal. |
| Technology / data | Low maintenance, swappable components, data control, clear license | Vendor lock-in; AGPL surprise; unowned model drift | [Public] OpenViking is AGPL-3.0 (LICENSE file read). [Own finding] provider-side schema enforcement does not work on the subscription route, so the contract is enforced in our code. |

## Where interests conflict (and what the design does about it)

1. **Speed vs traceability.** Analysts want auto-filing; compliance wants every value tied to a page. Design: every value carries its printed row text, deterministic checks gate auto-filing, anything uncertain goes to a review queue with the page.
2. **Capability vs data control.** The hosted model is the best demo; compliance and technology want data in the bank, and Vietnamese law adds cross-border obligations for personal data. Design: public documents only now; the PII ladder (L0 to L3) and an in-bank endpoint are a gate before pilot.
3. **Automation vs verification cost.** If reviewers must re-check everything, savings vanish (f2.ai). Design: reviewers see only flagged documents, and the controls are measured (precision, flagged share) so the review burden is a number, not a hope.

## Simulated personas (clearly labelled)

- **[Sim] Senior credit analyst.** "I do not mind the tool reading; I mind not knowing which numbers to trust. Show me the page and the row."
- **[Sim] Credit operations lead.** "If 40 percent of files land in a queue I have to staff, it is worse than today."
- **[Sim] Compliance officer.** "Which model saw this? Which version? Where did the data go? Can I replay the decision?"
- **[Sim] Platform engineer.** "Can I swap the model and the knowledge base without rewriting the pipeline? Who patches it?"

## What the numbers in the business case rest on

The workbook defaults (45 min per document, 60% auto-filed, etc.) are placeholders. Public vendor ranges
(30 min to 6 h per spread) only bracket the manual-time input; they are not evidence about Techcombank. The values
to replace first, in order of impact on the result: manual minutes per document, auto-file share (measure in the
pilot), review minutes per flagged document, volume.

## Interview guide (30 minutes, one role per call)

All roles: describe the last financial-statement file you handled, from receipt to decision; where did time go?
- **Analyst / RM:** how many pages do you read to find the statements? How do you key them (template, system)? What errors have you caught or missed? What would you need to see to trust a pre-filled spread?
- **Operations:** monthly volume, rework rate, SLA, how files are named and found, what an exception costs.
- **Risk / compliance:** what evidence do you need for an AI-assisted step; which data may go to an external model; who approves a model change; retention and audit expectations.
- **Technology:** where documents live, integration points, hosting constraints, what is already approved (models, vector stores, licenses).
Record for each: role, date, whether real, three quotes, one number.
