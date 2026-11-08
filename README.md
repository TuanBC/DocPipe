# docpipe: governed document digitalisation for corporate credit

Turns Vietnamese financial statements (BCTC) and annual reports into filed, validated, searchable knowledge.
Expert Challenge 2026, Problem Bank #2 (document processing) + #5 (trusted knowledge).
Public documents only; no customer data.

```
PDF / scan / photo -> page router -> full-text OCR (text layer free, vision model for image pages)
         -> classify (taxonomy: statements, registrations, contracts, invoices, ...) -> Luna extraction for statement pages
         -> validators (+ two-pass for scans; evidence + company checks for non-statement documents)
         -> PII guard -> auto-file  filed/{company}/{year}/{period | doc_type}/  (+ sidecar JSON, masked KB export)
                      or review queue (approve / correct in the UI or CLI)
         -> OpenViking KB, same folder layout (semantic summaries + embeddings) -> cited Q&A with access filter
Web UI (docpipe serve): inbox/jobs, folder library with page viewer + OCR text, review queue, KB tree/search/ask.
```

Documents: `docs/decision-memo.md`, `docs/architecture.md`, `docs/eval-results.md`, `docs/rollout-and-automation.md`,
`docs/stakeholders.md`, `docs/ai-log.md`, `docs/demo-script.md`, `docs/day1-findings.md`; slides in `slides/deck.pptx`;
business case in `model/business_case.xlsx` (inputs are placeholders).

## What runs and what does not

| Part | State |
|---|---|
| Router, extraction, validators (balance, income, cash flow, units, text-layer support, cross-statement), two-pass agreement for scans | Working, native Python |
| PII guard (regex L1, Luna L0), filing, review queue, correction flow, kill switch, idempotent re-run, route/page cache, audit log | Working |
| Full-text OCR via the vision model (`docpipe/ocr.py`): images and scanned PDFs, cached per page, capped per document; image uploads (PNG/JPG/TIFF…) | Working; verified on synthetic scanned registration certificate, 2-page contract and invoice photo (`scripts/make_samples.py`) |
| Filing of non-statement documents (registration, contract, invoice, resolution, tax, bank statement, collateral) with deterministic evidence/company checks | Working |
| OpenViking KB (`docpipe/ov_adapter.py`): auto-publish on filing/approval, folder layout mirrors `filed/`, re-filing moves the node; `OpenVikingKB` = OpenViking ranks documents, local index picks cited pages | Working: 8 documents published, summaries generated, Q&A cited from statements and scans |
| Web UI + API (`docpipe/web/`, `docpipe serve`, port 8800) | Working; driven end to end in a browser (upload, live job log, library, review approve, KB ask with citations) |
| KB: local backend (BM25, optional dense) with access filter; cited Q&A (`docpipe ask`) | Working. Dense uses GitHub Copilot `text-embedding-3-small` via LiteLLM (`DOCPIPE_DENSE=1 DOCPIPE_EMBED_MODEL=github_copilot/text-embedding-3-small`); the local ONNX model cannot load on the dev machine (memory). The ChatGPT/Codex route has no embeddings |
| Evaluation harnesses | Working; results in `docs/eval-results.md` |
| LiteLLM proxy, OpenViking server, embedding shim (`services/sdk_embed_server.py`, Copilot embeddings), run natively (no containers) | Start all with `scripts/start_services.ps1`. Fixed: OpenViking's semantic summaries had been failing silently (gateway rejected `temperature=0` for luna; `drop_params: true` in `deploy/litellm_config.yaml`), so earlier OpenViking search matched folder names only. Earlier run: gateway answered `docpipe ask`; 4 documents ingested into OpenViking with 1536-dim Copilot embeddings; retrieval compared (`docs/eval-results.md` 7d). Start commands in `deploy/litellm_config.yaml` and `deploy/openviking/ov.native.conf`. Slow startup; the `ov` CLI would not start alongside the server (paging file). Copilot route is a demo path, terms unreviewed |
| Langfuse, Presidio, TEI embeddings, container compose (`deploy/compose.yaml`) | **Written, never run**: Podman/WSL does not start on the dev machine (`0x80072746`) |
| Hermes agent over the KB | Not run by me (user reports it works with the OpenViking MCP server) |
| Langfuse tracing | Wired through LiteLLM metadata + env switch; untested against a server |

## Run

Quick start (Windows, everything native):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_services.ps1    # embed :8081, LiteLLM :4010, OpenViking :1933, UI :8800
# open http://127.0.0.1:8800 ; stop with: scripts/start_services.ps1 -Stop
```

The UI covers the whole flow: drop PDFs/images (Process & file, or OCR only), watch the job log, browse the filed folders
with page images next to the OCR text, approve/correct review items, browse/search the OpenViking tree, ask cited questions.

Requires [uv](https://docs.astral.sh/uv/) and a ChatGPT login for LiteLLM
(`uv run --group gateway python scripts/chatgpt_login.py`; token in `~/.config/litellm/chatgpt/auth.json`).

```bash
uv sync --group gateway --group kb
uv run --group gateway python -m docpipe run data/raw/<file>.pdf          # idempotent; --force re-runs
uv run --group gateway python -m docpipe review list
uv run --group gateway python -m docpipe review correct <doc_id> --page 108 --label "text in the row" \
       --field current --value 511184 --reviewer NAME                    # fix a value, re-validate, re-file
uv run --group gateway python -m docpipe review approve <doc_id> --reviewer NAME
uv run --group gateway python -m docpipe kill on|off                      # kill switch: everything goes to review
uv run --group gateway python -m docpipe ask "Tổng tài sản của ... năm 2025?" [--clearance restricted] [--backend local|openviking]
uv run --group gateway python -m docpipe ocr data/samples/dkkd_an_phat.png [--force-llm] [--out x.md]   # OCR only
uv run --group gateway python -m docpipe kb sync all | kb status | kb tree | kb search "<query>"         # OpenViking
uv run --group gateway python -m docpipe serve                                                          # web UI :8800
uv run --group gateway --with pytest pytest -q                                                          # offline unit tests
```

Output under `data/out/`: `filed/{company}/{year}/{period or doc_type}/*.pdf|json`, `fulltext/` (masked OCR text), `_review/`, `kb_export/*.md` (PII-masked),
`_restricted/` (PII mapping), `_cache/` (per-page results and routing; makes re-runs resumable and cheap),
`_corrections/`, `audit.jsonl` (every model call and decision).

Public test documents (downloaded to `data/raw/`, git-ignored), all publicly posted by the issuers or Vietstock:
- Vinamilk annual report 2025: `static2.vietstock.vn/data/HOSE/2025/BCTN/VN/VNM_Baocaothuongnien_2025.pdf`
- Vinamilk annual report 2024: `static2.vietstock.vn/vietstock/2025/3/21/20250321_20250320___vnm___bao_cao_thuong_nien_2024.pdf`
- Hòa Phát annual reports 2025 and 2024: `file.hoaphat.com.vn/hoaphat-com-vn/2026/04/bao-cao-thuong-nien-2025-1.pdf`, `.../2025/04/bao-cao-thuong-nien-hpg-2024.pdf`
- Techcombank consolidated financial statements 4Q25 (VAS): `techcombank.com/content/dam/techcombank/public-site/documents/techcombank-vas-bao-cao-tai-chinh-hop-nhat-4q25-searchable.pdf`

Check each issuer's terms before redistributing the files; they are not committed.

## How it decides

1. **Route**: statement pages by title keywords (first 60% of the page text) + numeric density; pages without a text layer are classified by a cheap low-resolution model call (cached).
2. **Extract**: one call per page returns line items with `current`, `prior` and the printed row. The schema is in the prompt and validated locally with a bounded retry (provider-side schema enforcement does not work on the `chatgpt/` route).
3. **Validate** (deterministic): balance identities, gross profit, net profit, cash roll-forward, net change, cash tie-out between statements, unit presence/consistency, every number printed in the page text layer; for pages without a text layer, an independent second read must agree.
4. **Confidence** comes from these signals: each failed check halves it.
5. **Decide**: below `governance.auto_file_threshold`, kill switch on, or type outside the taxonomy -> review queue.
   Documents without statement tables (contracts, certificates…) are checked deterministically instead: the classifier's
   evidence quote and the company name must appear in the OCR text. Only `taxonomy.statement_doc_types` require statement pages.
6. **Publish**: filed documents (auto or human-approved) go to OpenViking under the same folder keys; review items never do.
   Only the configured output directory publishes (eval harnesses that redirect `paths.out` cannot write to the KB). Pages the extractor says are not statements are demoted and logged.

## Adopt it for another document set

Edit `config/pipeline.yaml`: taxonomy, statement keywords, thresholds, model, PII detector. Statement layouts the validators
do not recognise are label patterns in `docpipe/validators.py`; unrecognised layouts skip arithmetic checks rather than fail.

## Evaluate

```bash
uv run --group gateway python -m evals.seeded_errors        # injected errors vs governance decisions
uv run --group gateway python -m evals.scan_sim             # clean vs degraded pages against the text layer
uv run --group gateway python -m evals.scan_pipeline        # scanned PDF (no text layer) end to end
uv run --group gateway python -m evals.cross_period         # FY N-1 current vs FY N prior tie-out
uv run --group gateway python -m evals.kb_qa                # KB Q&A: correctness, citations, refusals, injection, access
uv run --group gateway python -m evals.injection_extract    # hostile text on the page image
uv run --group gateway python -m evals.pii_eval             # regex (L1) vs Luna (L0) on seeded synthetic lines
uv run --group gateway python -m evals.rate_probe           # concurrency / rate limits on the subscription route
```

## Known limits

- Results are development-set behaviour on a few public documents from three issuers; rules were tuned on them. No held-out accuracy claim.
- Router recall is imperfect (a cash-flow page was missed in one report); two passes by the same model can repeat the same wrong value.
- Luna as PII detector (L0) is not a privacy barrier: the page image has already gone to the provider.
- Cost per document is computed from measured tokens x list price; the subscription route records $0 and cannot enforce budgets.
- About 26-32 s per page sequentially; the worker uses a thread pool (`model.workers`).
- The machine runs near its memory commit limit: pages are rendered in grayscale with a 2400 px cap, and the embedding model could not load.
