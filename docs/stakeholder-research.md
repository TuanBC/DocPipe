# Stakeholder needs: desk research with sources

**What this is.** A synthesis of public research, surveys, regulation and bank disclosures, organised by the four
stakeholder roles, to stand in for interviews until real ones are held. **It is not interview evidence.** Each line
says what the need is, the number behind it, where the number comes from, and how trustworthy that source is.
Vendor figures are labelled: vendors have a reason to make the pain look large, so they bracket a number, they do
not prove it. Researched on 9 November 2026.

Source quality: **[R]** regulator or law; **[B]** bank disclosure; **[S]** independent or industry survey;
**[A]** academic / peer-reviewed; **[V]** vendor material (incentive to inflate); **[N]** news report of a bank's own claim.

## 1. Users: credit analysts and relationship managers

| Need | Evidence | Source | What it means for DocPipe |
|---|---|---|---|
| Less time keying statements | Manual spreading takes about 2-6 analyst hours per borrower, depending on entity complexity and the number of guarantors; a three-year spread can take a senior analyst 3-5 hours | [V] [Scry AI](https://scryai.com/blog/automated-financial-spreading-commercial-lending); [V] [FintechSpecs](https://fintechspecs.com/blog/best-ai-credit-memo-financial-spreading-software-commercial-lenders/) | The business case uses 60 minutes per statement file, the *low* end of this range, to stay conservative |
| A measured "after" from a real lender | Spreading complex statements fell from 3-4 hours to 30-45 minutes at a credit union after automation | [V] [nCino customer case study](https://www.casestudies.com/company/ncino/case-study/768c-1st-community-fcu-achieves-greater-efficiency-and-faster-decisions-with-ncino) | Consistent with DocPipe's design (machine reads, analyst reviews flagged items); still a vendor case |
| More time with customers | RMs are said to spend up to 60-70% of their time on administrative work; only 25-30% in direct client dialogue | [V] [Backbase](https://www.backbase.com/blog/rm-productivity-crisis) (attributes it to McKinsey, study not located); [V] [Vis Banking](https://visbanking.com/commercial-relationship-management) | Treated as directional only; the pilot measures the real share with time sampling |
| Find documents and answers fast | Knowledge workers spend about 1.8 hours a day (about 19% of the week) searching for and gathering information | [S] McKinsey Global Institute, *The social economy* (2012), as cited by [Cottrill Research](https://cottrillresearch.com/various-survey-statistics-workers-spend-too-much-time-searching-for-information/) | Justifies the cited Q&A and the predictable folder layout; not banking-specific |
| Trust what the tool produces | Manual transcription error rates range from about 0.5% to over 10% depending on the field; numeric fields around 1% | [A] peer-reviewed clinical data-entry studies summarised in [PMC6351970](https://rcastoragev2.blob.core.windows.net/c574f27f2402bd611609f94fe89855c3/PMC6351970.pdf) | Manual keying is not error-free: the baseline error rate must be measured (week 1) before claiming the tool is better |

**Synthesised persona (from the sources above, not a person).** A corporate credit analyst spends a few hours per
borrower re-keying statements and re-checking totals, and more time hunting for the right version of a contract or
registration. They will use a tool only if they can see the source page next to each value; otherwise checking it
costs as much as doing it.

## 2. Process owner: credit operations

| Need | Evidence | Source | What it means for DocPipe |
|---|---|---|---|
| Faster onboarding, fewer lost clients | 70% of financial institutions lost clients in the past year because onboarding was slow; abandonment averages about 10%; UK corporate banks report onboarding often over six weeks (survey of 600 decision-makers, August 2025) | [S/V] Fenergo *Financial Crime Industry Trends 2025*, reported by [Crowdfund Insider](https://www.crowdfundinsider.com/2025/10/254227-global-financial-institutions-are-losing-clients-due-to-inefficient-digital-onboarding-processes-fenergo/) and [FinTech Global](https://fintech.global/?p=217350) | Speed of document handling is a commercial issue, not only a cost issue |
| Lower cost per file | Banks took on average 95 days to complete a corporate KYC review in 2023 (84 days the year before); over half spend USD 1,500-3,000 per client KYC review | [S/V] Fenergo 2023 study of 1,100+ executives, via [A-Team Insight](https://a-teaminsight.com/blog/fenergo-study-reveals-true-cost-of-kyc) | Document reading and filing is a slice of this cost; DocPipe does not claim the whole of it |
| Proof that it works in Vietnam | MB reports its DocAI cut document-checking time by 75% and serves 350,000+ businesses on Biz MBBank; MB reported SME credit processing falling from about 10 days to 2; VietBank reports 35% shorter approval time with in-house AI; MSB digitised credit approval using national tax and invoice data | [N] [The Investor](https://theinvestor.vn/mb-showcases-comprehensive-financial-solution-biz-mbbank-at-digital-transformation-day-event-d15830.html), [Báo Nghệ An](https://baonghean.vn/en/print/10298538.html), [ecosistemastartup](https://ecosistemastartup.com/mb-recorta-el-credito-pyme-de-10-a-2-dias-con-ia/), [Pulse](https://www.pulse.bot/cto-pulse/news/the-lean-ai-plan-for-action-at-vietbank-64826290-f245-4d85-a256-9b60bc9e94a2/), [The Investor](https://theinvestor.vn/vietnamese-banks-leverage-national-data-integration-to-reach-customers-d15945.html) | Competitors are already doing this: "do nothing" has a competitive cost. All figures are the banks' own claims |
| Volume that keeps growing | Vietnam registered 195,100 new enterprises in 2025 (+24.1%), plus 92,900 returning in the first ten months | [N] National Statistics Office figures via [Vietstock](https://en.vietstock.vn/2026/01/business-capital-surges-778-on-new-reactivated-firms-in-2025-38-627651.htm) and [VOV](https://english.vov.vn/en/economy/ten-months-of-2025-see-average-25600-new-and-returning-businesses-monthly-post1243827.vov) | More new business customers means more onboarding documents per year |
| Scale at Techcombank | ~18.0 million customers, 2.7 million added in 2025; corporate credit VND 452.1 trillion (+13.4%); retail credit including SME VND 372.0 trillion (+30.8%); cost-to-income ratio 30.8% | [B] [Techcombank FY2025 results press release](https://techcombank.com/content/dam/techcombank/public-site/documents/FY25-Press-Release-ENG.pdf) | A bank this size, with an already low cost-to-income ratio, gains from capacity (handling growth without more headcount) more than from cost cuts |

**Synthesised persona.** An operations lead wants every credit file named and filed the same way, a review queue
that does not grow faster than reviewers can clear it, and a number showing time per file falling. Their red line is
a tool that creates a second queue they have to staff.

## 3. Risk and compliance

| Need | Evidence | Source | What it means for DocPipe |
|---|---|---|---|
| A legal basis before personal data leaves Vietnam | Personal Data Protection Law 91/2025/QH15, in force 1 January 2026: cross-border transfers need a transfer impact assessment dossier filed with the authority (A05); fines for cross-border violations up to 5% of the previous year's revenue | [R] summarised by [Tilleke & Gibbins](https://tilleke.com/insights/vietnams-new-personal-data-protection-law-a-closer-look), [Allen & Gledhill](https://www.allenandgledhill.com/sg/publication/articles/31075/upcoming-changes-to-vietnam-s-personal-data-protection-regime), [Vietnam Briefing](https://www.vietnam-briefing.com/news/vietnam-law-on-personal-data-protection-latest-developments-and-insights.html/) | Sending page images to a hosted model abroad triggers this; the in-bank endpoint is a gate before any non-public document |
| AI rules specific to banking | SBV Circular 53/2026/TT-NHNN (issued 30 September 2026, effective 15 November 2026): classify every AI system by risk before deployment, keep an inventory reviewed at least yearly, notify customers when AI interacts with them | [R] [Luat Viet Nam](https://luatvietnam.vn/legal-updates/circular-no-53-2026-tt-nhnn-ai-automated-payments-for-individual-customers-must-not-exceed-vnd-100-million-per-day-892-113479-article.html), [VNBA](https://vnba.org.vn/en/on-the-issuance-of-regulations-on-the-safety--risk-management-and-deployment-conditions-for-the-application-of-artificial-intelligence-systems-in-the-banking-sector-23849.htm), [Vietnam News](https://vietnamnews.vn/economy/1766000/central-bank-moves-to-tighten-ai-use-in-banking-requires-prior-customer-notification.html) | DocPipe needs a risk-classification dossier before the pilot; it is internal-facing (no customer interaction), which should keep it out of the strictest tier, to be confirmed |
| Responsibility stays with the bank | The draft circular said banks remain "fully responsible for the safety and compliance" of outsourced AI, must audit vendors, log AI operations, and report serious incidents to the SBV within 24 hours | [R] draft text summarised by [Baker McKenzie](https://www.bakermckenzie.com/en/insight/publications/2026/04/vietnam-draft-circular-on-ai-deployment-in-banking) (final text to be checked) | The audit log, monitoring alerts, kill switch and model/prompt versioning map directly onto these duties |
| Replayable decisions | Customers can ask for human review of AI decisions; disputed outputs need human reassessment (draft circular) | [R] same as above | Every DocPipe decision is logged with its reasons and can be re-run, corrected or rolled back by a named person |

**Synthesised persona.** A compliance officer asks: which model saw this document, which version, where did the data
go, can I replay the decision, and who approved it? Their red lines: personal data abroad without a filed assessment,
and an AI system missing from the inventory.

## 4. Technology and data

| Need | Evidence | Source | What it means for DocPipe |
|---|---|---|---|
| Swappable model, no lock-in | The bank's investment is concentrated in IT: FY2025 operating expenses rose 6.9%, "primarily driven by" IT infrastructure | [B] [Techcombank FY2025 press release](https://techcombank.com/content/dam/techcombank/public-site/documents/FY25-Press-Release-ENG.pdf) | Fits a gateway (LiteLLM) in front of any model, hosted or in-bank |
| Clear licences | OpenViking is AGPL-3.0 (licence file read) | Own check of the repository | Legal review before production; the adapter keeps the knowledge base replaceable |
| Vietnamese document AI is a known category | Local vendors (FPT.AI, GreenNode, Lac Viet) market OCR and document processing for Vietnamese banking documents | [V] [FPT.AI](https://fpt.ai/digitize-documents-ai-finance-sector), [GreenNode](https://greennode.ai/blog/ocr-and-automated-document-processing-solutions-for-bank), [Lac Viet](https://lacviet.vn/en/giai-phap-so-hoa-du-lieu-ngan-hang/) | "Buy" is a real option: run one vendor on the same evaluation set during the pilot |

## 5. Where the roles conflict (from the evidence)

| Conflict | Evidence on each side | Design response |
|---|---|---|
| Speed (operations, users) vs control (risk) | Clients are lost to slow onboarding (Fenergo 2025) / the bank stays fully responsible for AI outputs (SBV draft) | Automate only what passes deterministic checks; everything else goes to a person with the page shown |
| Best model (technology, users) vs data location (risk) | Hosted models are the most capable today / PDPL cross-border assessment, fines up to 5% of revenue | Public documents only on the hosted route; in-bank endpoint before pilot |
| Automation savings (operations) vs verification cost (users) | Manual keying has its own 1-10% error rates (clinical studies) / a tool that must be fully re-checked saves nothing | Measure both: the baseline error rate in week 1, and reviewer minutes per flagged document |

## 6. What the interviews still have to settle

The desk research cannot answer these; they are the first five interviews (`docs/interview-notes.md`):
1. Minutes per statement spread and per onboarding document **at Techcombank**: the input the business case is most sensitive to.
2. Monthly volume of corporate and SME credit files by document type.
3. The current error and rework rate on keyed statements.
4. Which model endpoints and data locations risk will approve, and how Circular 53 classifies an internal document tool.
5. Where documents live today (DMS, shared drives, loan-origination system) and the integration point.
