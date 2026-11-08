# Day 1 findings (native, no containers)

Measured with `scripts/smoke_luna.py` against `chatgpt/gpt-6-luna` through the LiteLLM SDK
(LiteLLM chatgpt/ provider, existing ChatGPT login in `~/.config/litellm/chatgpt/auth.json`).

| Check | Result | Consequence |
|---|---|---|
| Text completion | PASS, ~2.7 s | Route works. |
| Fixed prompt overhead | 1,637 input tokens for a one-word prompt | The Codex backend injects ~1.6k tokens per call. Cost per document must include this overhead x calls per document. Batch pages per call where possible. |
| Image input (Vietnamese balance-sheet fragment) | PASS; label, both values and unit read correctly, incl. diacritics and `.` thousands separators | VLM path is viable. About 500 input tokens for a 900x420 image. |
| Strict JSON schema, chat-completions `response_format` | FAIL: schema ignored, model invents its own keys | Do not rely on provider-side schema enforcement. |
| Strict JSON schema, native Responses `text.format` | FAIL: same | Same. Not tested whether LiteLLM or the backend drops it. |
| Schema described in the prompt + local validation | PASS: correct keys and numbers | Our contract: schema in the prompt, pydantic validation, bounded retry, failure routes to review. |
| Embeddings on `chatgpt/` | FAIL: unmapped provider | OpenViking needs a separate embedding endpoint (CPU multilingual model). |
| Budgets | Per LiteLLM docs: models have no price in the cost map, so spend is $0 and `max_budget` never triggers | Use rpm/tpm limits on keys. Cost per document is computed by us: measured tokens x Luna list price. |

## Gate status

- Luna via subscription: usable for text, vision, and prompt-enforced JSON.
- Still untested: reasoning-effort control on this route, rate limits under an eval run, OpenAI terms for the shared identity.
- Blocked: Podman (WSL VM creation fails with `0x80072746`), so Langfuse, OpenViking, Presidio, Hermes wait.

## First real-document result (`scripts/test_real_page.py`)

Vinamilk annual report 2025 (public PDF, 111 pages, text layer on every page), page 108, consolidated IFRS statement of financial position, rendered at 150 dpi:

| Measure | Value |
|---|---|
| Items extracted | 42 line items with current/prior values and row quotes |
| Key totals vs text layer | 3/3 exact: TỔNG TÀI SẢN 56.091.826 / 56.993.245, Tài sản ngắn hạn, Tài sản dài hạn; unit `Triệu VND` and both period dates correct |
| Tokens | 7,017 in / 1,893 out (includes the ~1.6k fixed overhead) |
| List-price cost (Luna $0.10 / $0.50 per 1M, third-party reported) | about $0.0016 per page |
| Latency | 37.9 s for one page (single request, no concurrency) |

Observations:

- The PDF text layer lists row labels and numbers in separate blocks, so text-layer extraction does not preserve the table. Native text is useful as an agreement signal, not as the extractor.
- This statement is IFRS format ("Báo cáo tình hình tài chính"), not the VAS "Bảng cân đối kế toán" heading. The page router and validators must handle both naming schemes.
- Latency is dominated by output tokens (row quotes). Sequential processing of 15 pages would take ~10 minutes, so the worker needs concurrency; rate limits on the subscription route are untested.
- One page is one sample. It proves feasibility, not accuracy; the eval set is still to be built.

## Corpus so far (data/raw, git-ignored)

| File | Source | Pages |
|---|---|---|
| VNM_baocaothuongnien_2025.pdf | static2.vietstock.vn (public annual report) | 111 |
| VNM_baocaothuongnien_2024.pdf | static2.vietstock.vn (public annual report) | 95 |

Next: audited BCTC for other issuers (FPT, HPG candidates; official IR pages preferred, direct PDF links not yet verified), plus seeded PII and unit-error variants.

## AI-log candidates

- Assumed `response_format` json_schema would work through the bridge; it does not on this route.
- Assumed Codex route would serve embeddings; it does not.
- An auth file from an earlier login already existed, so no new device-code login was needed.
