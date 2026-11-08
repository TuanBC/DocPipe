# Adopting DocPipe in another team (about one day)

DocPipe is configured, not re-coded, per team. A trade-finance, retail-lending or HR team can reuse the same
pipeline for its own documents by following these steps.

## 1. Copy and edit the configuration

```bash
cp config/pipeline.yaml config/tradefinance.yaml
```

Change only these sections:

| Section | What to set | Example (trade finance) |
|---|---|---|
| `taxonomy.doc_types` | One line per document type the team files; keep `other` last | `letter_of_credit`, `bill_of_lading`, `commercial_invoice`, `packing_list`, `certificate_of_origin`, `other` |
| `taxonomy.statement_doc_types` | Types that must contain financial statements (empty list if none) | `[]` |
| `paths.out` | The team's output folder (its filing root) | `data/out_tradefinance` |
| `kb.openviking.root` | The team's branch of the knowledge base | `viking://resources/tradefinance` |
| `model.name` / `model.api_base` | The approved model endpoint (through the LiteLLM gateway) | `openai/inbank-vlm`, `http://gateway:4010/v1` |
| `governance.auto_file_threshold` | Start strict (0.95) and lower it only with eval evidence | `0.95` |
| `monitoring` | Alert thresholds and the team channel webhook | `webhook_url: https://.../teams-webhook` |
| `pii.entities` | Identifier types to mask | add a recognizer if the team handles passport numbers |

Folder layout is automatic: `{customer company}/{year}/{period or document type}/`. The classifier is told to name the
bank's customer, never the bank itself; adjust the wording in `docpipe/extract.py` only if the team's "customer"
means something else.

## 2. Measure before trusting it

1. Put 15 to 20 representative, approved sample documents in a folder, including hard ones (bad scans, the bank
   printed as a party, a document outside the taxonomy).
2. Write `labels.json` next to them, one entry per file (`text` is the printed text, used for the OCR error rate):

```json
[{"file": "lc_0012.pdf", "doc_types": ["letter_of_credit"], "company_slug": "an-phat",
  "fiscal_year": 2025, "expected": "auto_filed", "difficulty": "clean", "note": "", "text": "..."}]
```

3. Run the evaluation into a scratch folder (it never publishes to the knowledge base):

```bash
uv run --group gateway python -m evals.general_docs --set data/eval/tf_set --out data/eval/tf_out --report data/eval/tf.json
```

4. Go live only if **wrong-but-auto-filed is 0** and the review share is acceptable to the team lead. Keep the
   set: it is the regression test before any model or prompt change.

## 3. Run it

```bash
scripts/start_services.ps1
uv run --group gateway python -m docpipe --config config/tradefinance.yaml serve --port 8810
```

Staff use the web UI (Inbox, Library, Review, Knowledge base, System). Operations watch the System tab or the
webhook channel; the kill switch and rollback are there.

## 4. What needs code (rarely)

- A new financial-statement layout: label patterns in `docpipe/validators.py`.
- A new identifier to mask: a regex in `docpipe/pii.py` plus a case in `evals/pii_eval.py`.
- A different filing scheme than company / year / period: `filing.folder_parts`.

## 5. Ownership

| Who | Owns |
|---|---|
| Team lead | Taxonomy, thresholds, the eval set, who may approve |
| Platform team | Gateway, model endpoint, OpenViking, upgrades (eval re-run before each) |
| Risk | Sign-off on thresholds, audit-sample policy, retention |
