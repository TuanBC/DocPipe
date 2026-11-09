# Development notes

Detail moved out of the README: how the local services fit together, what was run on the development machine and
what was not, output layout, and the public test documents. For what DocPipe is and how to start it, see the
[README](../README.md).

## Services

All services run natively on Windows (no containers). `scripts/start_services.ps1` starts them in order and
`scripts/start_services.ps1 -Stop` stops them.

| Service | Port | What it does | Config |
|---|---|---|---|
| Embedding shim (`services/sdk_embed_server.py`) | 8081 | OpenAI-compatible embeddings endpoint for OpenViking | env vars in the script |
| LiteLLM proxy | 4010 | One gateway in front of every model call (vision OCR, extraction, Q&A); records tokens and cost | `deploy/litellm_config.yaml` |
| OpenViking server | 1933 | Knowledge base: folder tree, semantic summaries, embeddings, search | `deploy/openviking/ov.native.conf` |
| DocPipe web UI + API | 8800 | Upload, jobs, library, review, KB, monitoring | `config/pipeline.yaml` |

The model route used in development is `chatgpt/gpt-6-luna` through LiteLLM (ChatGPT login:
`uv run --group gateway python scripts/chatgpt_login.py`, token in `~/.config/litellm/chatgpt/auth.json`). Dense
embeddings use GitHub Copilot `text-embedding-3-small` via LiteLLM
(`DOCPIPE_DENSE=1 DOCPIPE_EMBED_MODEL=github_copilot/text-embedding-3-small`). Both are demo routes whose terms were not
reviewed for production; a pilot replaces them with an in-bank or contractually approved endpoint, which only needs a
change in `deploy/litellm_config.yaml`.

## What was run, and what was not

| Part | State |
|---|---|
| Router, extraction, validators (balance, income, cash flow, units, text-layer support, cross-statement), two-pass agreement for scans | Working, native Python |
| PII guard (regex L1, model L0), filing, review queue, correction flow, kill switch, idempotent re-run, page cache, audit log | Working |
| Full-text OCR via the vision model (`docpipe/ocr.py`): images and scanned PDFs, cached per page, capped per document | Working; verified on synthetic scans (`scripts/make_samples.py`, `evals/make_eval_set.py`) |
| Filing of non-statement documents with deterministic evidence and company checks | Working |
| OpenViking KB (`docpipe/ov_adapter.py`): auto-publish on filing or approval, folder layout mirrors `filed/`, re-filing moves the node | Working |
| Web UI + API (`docpipe/web/`) | Working; driven end to end in a browser and recorded for the demo video |
| Local KB backend (BM25, optional dense) with access filter; cited Q&A | Working. The local ONNX embedding model could not load on the dev machine (memory); the ChatGPT route has no embeddings, hence the Copilot route |
| Monitoring and alerts (`docpipe/monitor.py`) | Working; fired a real alert (stale review ticket) |
| Version history and rollback | Working; rollback drill re-published to OpenViking |
| Langfuse, Presidio, TEI embeddings, container compose (`deploy/compose.yaml`) | **Written, never run**: Podman/WSL does not start on the dev machine (`0x80072746`) |
| Langfuse tracing | Wired through LiteLLM metadata and an env switch; untested against a server |
| Hermes agent over the KB | Not run by me (reported working with the OpenViking MCP server) |

## Issues found while running the stack

- **OpenViking summaries failed silently.** The gateway rejected `temperature=0` for the luna model, so OpenViking's
  semantic summaries were empty and search matched folder names only. Fixed with `drop_params: true` in
  `deploy/litellm_config.yaml`.
- **Provider-side JSON schema enforcement does not work** on the `chatgpt/` route. The schema is in the prompt and
  validated locally with a bounded retry.
- **Memory.** The machine runs near its commit limit: pages are rendered in grayscale with a 2400 px cap, the local
  embedding model could not load, and the `ov` CLI would not start alongside the server (paging file).
- **Slow startup.** OpenViking takes a while to come up.
- **Cost on the subscription route** is recorded as $0. Reported costs are measured tokens times list price.
- **Throughput.** About 26-32 s per statement page sequentially; the worker uses a thread pool (`model.workers`).

## Output layout

Everything is written under `data/out/` (git-ignored):

| Path | Contents |
|---|---|
| `filed/{company}/{year}/{period or doc_type}/` | Filed PDF plus sidecar JSON (fields, evidence, checks, decision) |
| `fulltext/` | PII-masked OCR text |
| `_review/` | Review tickets |
| `kb_export/` | PII-masked markdown published to the knowledge base |
| `_restricted/` | PII mapping (restricted access) |
| `_cache/` | Per-page results and routing; makes re-runs resumable and cheap |
| `_corrections/` | Reviewer corrections |
| `_history/` | Earlier filed versions, for rollback |
| `_monitor/` | Active alerts |
| `audit.jsonl` | Every model call and decision |
| `alerts.jsonl` | Alert history |

## Public test documents

Downloaded to `data/raw/` (git-ignored), all posted publicly by the issuers or Vietstock. Check each issuer's terms
before redistributing them.

- Vinamilk annual report 2025: `static2.vietstock.vn/data/HOSE/2025/BCTN/VN/VNM_Baocaothuongnien_2025.pdf`
- Vinamilk annual report 2024: `static2.vietstock.vn/vietstock/2025/3/21/20250321_20250320___vnm___bao_cao_thuong_nien_2024.pdf`
- Hòa Phát annual reports 2025 and 2024: `file.hoaphat.com.vn/hoaphat-com-vn/2026/04/bao-cao-thuong-nien-2025-1.pdf`,
  `file.hoaphat.com.vn/hoaphat-com-vn/2025/04/bao-cao-thuong-nien-hpg-2024.pdf`
- Techcombank consolidated financial statements 4Q25 (VAS):
  `techcombank.com/content/dam/techcombank/public-site/documents/techcombank-vas-bao-cao-tai-chinh-hop-nhat-4q25-searchable.pdf`
