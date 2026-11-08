# Demo script (live 3 minutes, and the 5-minute recorded fallback)

Not yet recorded: no screen recording tool was available in the build environment. Record this script as-is.

Preparation (once): `uv sync --group gateway --group kb`; Luna login present (`~/.config/litellm/chatgpt/auth.json`);
`data/raw/` holds the public PDFs; clean state with `rm -r data/out` for the demo run. Warm the page cache by running every
file once beforehand so the live run is fast (a cold page takes about 30 seconds).

| Step | Command / action | What the audience sees | Say |
|---|---|---|---|
| 1 Drop | `docpipe run data/raw/VNM_baocaothuongnien_2025.pdf` | Router picks 3 of 111 pages; document type, company, year, scope | "Only the statement pages go to the model; the rest of the 111 pages cost nothing." |
| 2 Check | (same output) | 17 checks: identities, cash roll-forward, units, "every number is on the page" | "A wrong digit fails loudly. The checks are ours, not the model's." |
| 3 File | `dir data\out\filed /s` and open the sidecar JSON | Folder by company / year / period; each value with its printed row | "Every value carries its source row; compliance can replay it." |
| 4 Failure | `uv run --group gateway python -m evals.seeded_errors` (or run on the scan-simulated PDF) | One digit changed lands in the review queue with the reasons | "This is the first real error: a dropped digit, caught by a rule." |
| 5 Review | `docpipe review list`, then `docpipe review correct <id> --page 108 --label "..." --field current --value 511184 --reviewer demo` | Corrected, re-validated, filed, logged | "A human fixes one value; the log keeps who and why." |
| 6 Scan | `docpipe run data/eval/scan_pipeline/VNM2025_scan_mild.pdf` | No text layer: statement pages found by the model; two-pass agreement fails on disagreeing values | "Without a text layer the second read is the check." |
| 7 Ask | `uv run --group gateway python -m docpipe ask "Tổng tài sản của Công ty Cổ phần Sữa Việt Nam năm 2025?"` (if the `ask` command is in this build; otherwise `evals/kb_qa.py`) | Answer with document id and page, or "not found" | "Answers cite a page or refuse; document text is data, not instructions." |
| 8 Trace | Open `data/out/audit.jsonl` (Langfuse is the target but was not run) | Per-call model, tokens, latency, decision | "Everything the model did is on a record." |

Live-change candidates for the Q&A: change `governance.auto_file_threshold` in `config/pipeline.yaml` and re-run;
add a document type to `taxonomy.doc_types`; change an input in `model/business_case.xlsx` and read the new payback.

Fallback if the model route fails: all steps except 1, 6 and 7 work from the cache (`data/out/_cache`), and
`evals/seeded_errors.py` needs only the classification call. Say so rather than hide it.
