# Demo script: recorded video, live demo, and the live change

## Recorded video (about 3 minutes)

`submission/DocPipe_demo.mp4` was recorded by driving the real UI (`scripts/record_demo.py`, Playwright) with the
narration burned in as subtitles; the wait for the jobs is shown 10x faster and says so. The same narration is in `submission/DocPipe_demo.srt` with timings, so a voice-over
can be recorded over it line by line. To re-record: start the services, then

```bash
uv run --group gateway --with playwright==1.55.0 python scripts/record_demo.py
```

```bash
uv run python scripts/make_video.py
```

## Live demo in the presentation (3 minutes)

Before the talk: `scripts/start_services.ps1`; open http://127.0.0.1:8800; have `data/eval/general_set/` open in
Explorer; warm the cache by processing the files once (re-runs are then instant and free).

| # | Do | Say |
|---|---|---|
| 1 | Inbox: drop the contract, the invoice and the menu | "Three scans; one does not belong." |
| 2 | Watch the job log | "OCR by a vision model; text layers read for free; then classify, check, file, publish." |
| 3 | Library: open the contract, Pages tab, then Checks | "Filed under the borrower, not the bank. Evidence and company name must be in the text." |
| 4 | Review tab: the menu | "Outside the taxonomy: a person decides. Nothing here reaches the knowledge base." |
| 5 | Knowledge base: ask the Hung Thinh question, click the citation | "Answers cite a page or refuse." |
| 6 | System tab: monitoring, the live alert, kill switch on/off | "Thresholds in config; alerts to a webhook; one-click kill switch." |
| 7 | Library: an invoice's Versions tab, roll back | "Every version kept; rollback re-publishes and logs who did it." |

## The live change (the brief asks for one)

Pick one when asked; each takes under two minutes and shows a trade-off.

1. **Stricter automation** (trade-off: fewer errors vs more review work). In `config/pipeline.yaml` set
   `governance.auto_file_threshold: 0.995`, restart `docpipe serve`, re-run a document whose confidence is below that
   (tick "re-run"): it now goes to review, and the review rate rises in the System tab.
2. **A new document type** (trade-off: coverage vs auditability). Add `- guarantee_letter` under `taxonomy.doc_types`,
   re-run a document of that type: it is now filed instead of going to review.
3. **The business case** (trade-off: what the case depends on). In `model/business_case.xlsx` change "A. Manual minutes
   per file" from 60 to 30 and "B" from 6 to 3: the 12-month net goes negative. The point: time the real work first.
4. **An alert threshold**. Set `monitoring.review_queue_max: 0`, click "Check now": a review-queue alert fires and is
   written to `alerts.jsonl` and the audit log.

## Fallback if the model route fails

Re-runs of documents already processed come from the page cache and need no model call; the Library, Review,
monitoring, rollback and kill switch work without the model. The recorded video covers the rest. Say so rather than
hide it.
