# DocPipe: submission pack

TuanBC · Techcombank AI Transformation Expert Challenge 2026 · Problem Bank #2 (document processing) + #5 (trusted
knowledge assistant). All data is public company filings or synthetic scans of fictional companies.

| # | Brief item | Files |
|---|---|---|
| 1 | Decision memo and business case (max 6 pages) | `01_Decision_memo_and_business_case.pdf` (3 pages) · workbook `02_Business_case_model.xlsx` (inputs tagged MEASURED / PUBLIC / ASSUMED, sensitivity, scenarios, scale) |
| 2 | Working prototype: demo video + repository with README | `DocPipe_demo.mp4` (about 3 minutes, narration as subtitles; `DocPipe_demo.srt` for the voice-over) · repository root `../README.md` · run with `scripts/start_services.ps1`, then http://127.0.0.1:8800 |
| 3 | Architecture and evaluation | `03_Architecture_and_evaluation.pdf`: target architecture, 3 key decisions and trade-offs, security / privacy / audit, all evaluation results with failure cases, cost and latency |
| 4 | Automation and rollout plan | `04_Automation_and_rollout_plan.pdf`: production-standard checklist (re-run, monitoring, alerts, kill switch, rollback), governance, what breaks if it is wrong, before / after, projection at scale, 3-month plan, adoption guide |
| 5 | AI log and reflection (max 1 page) | `05_AI_log_and_reflection.pdf` (1 page) |
| - | Presentation (15 min + 15 min discussion) | `DocPipe_deck.pptx` and `DocPipe_deck.pdf` (16 slides, speaker notes); live demo and live-change runbook in `../docs/demo-script.md` |
| - | Stakeholders | `06_Stakeholders_and_interview_plan.pdf`: roles, conflicts, simulated personas (labelled), the interview plan and notes template |

Headline results (small samples; see item 3 for the caveats):

- 16 synthetic scans with deliberate traps: 16/16 type, customer and year correct; 106/106 printed numbers exact;
  0 wrong results auto-filed; $0.0013 and 13 s per document.
- Real public filings: a real dropped digit caught and corrected with an audit trail; 6/6 injected errors routed to review.
- Cited Q&A: 31/31 answerable questions correct with a page citation, 6/6 unanswerable refused, no access-control leak.
- 19 offline unit tests; monitoring fired a real alert; rollback drill re-published to the knowledge base.

Open items, stated plainly: no real stakeholder interview has been held yet (plan and template ready); the manual
"before" times are assumptions until the pilot's week-1 timing; accuracy on real branch scans is unmeasured.
