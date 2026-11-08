# AI log and reflection (target: one page)

Tool: an AI coding assistant (this session) for research, code, evaluation and drafting; GPT-6 Luna as the model inside the prototype.
The prompts below are **paraphrased from the session**; replace them with the verbatim text before submitting.

## Most important prompts (paraphrased)

1. "Decompose the assignment into a plan for the presentation and slides; focus on document digitalisation into a file system and knowledge base; I plan PaddleOCR, BERTopic or a small LLM for tags, then OpenViking."
2. "Replace OCR with a VLM API call to simplify, and explain it in the plan."
3. "Use GPT-6 Luna through the Codex route of a LiteLLM gateway; add a Hermes agent connected to the KB; add Langfuse tracing."
4. "Mention PII removal (Presidio via LiteLLM, or a local guardrail model); for the demo use Luna."
5. "Start without containers" (after Podman failed), then "continue with all remaining steps until finished".

## Where the AI got it wrong, and how it was fixed

| What went wrong | How it showed up | Fix |
|---|---|---|
| Assumed provider-side JSON schema works on the subscription route | Smoke test returned invented keys | Schema in the prompt, local validation, bounded retry |
| Assumed the Codex route serves embeddings | `Unmapped LLM provider` error | Local CPU embedding service for the KB |
| Planned LiteLLM budgets as a cost control | LiteLLM docs: models have no price in the cost map, spend is $0 | Cost from measured tokens x list price; rpm/tpm limits |
| PII regex flagged a financial figure as a phone number | Real Vinamilk page | Phone validator rejects mixed separators and thousands grouping |
| First text-support check tolerated 5% unsupported numbers | A seeded fabricated value passed | Strict by default; then a real digit drop (511.184 read as 51,184) was caught |
| Validator label patterns were too loose or too narrow | On a bank statement a "net profit" check matched the wrong line; on Hòa Phát the VAS line-code suffix and "Thu nhập thuế TNDN hoãn lại" were missed | Anchored patterns, suffix stripping, per-page tax lines. These were found only by running on new issuers, so the patterns were tuned on those documents: no held-out accuracy claim |
| Router fix broke what worked | A 800-character title window routed 1 of 3 Vinamilk statement pages | Relative title position plus earliest match |
| Memory failures (`malloc` in PyMuPDF, `MemoryError` in tiktoken) | Machine near its commit limit | Grayscale render, 2400 px cap, fewer concurrent jobs |
| Edited files using guessed line numbers three times | Syntax errors and misplaced lines | Re-read the region before every edit |
| A WSL config tweak (`localhostForwarding=false`) crashed the WSL service | `WSLService` stopped | Reverted the file; Podman remains unusable, reported rather than worked around |
| Slide text said a Luna vs Sol comparison existed | It had not been run | Slide corrected to "not measured" |

## What AI helped with / could not help with

Helped: reading docs quickly (LiteLLM, OpenViking, Langfuse, Presidio), writing the pipeline and harnesses, finding failure cases by
running on real documents, drafting memo and plans.
Could not: get Podman working (OS-level), produce real stakeholder evidence (none was collected; sources are public or
simulated and labelled), verify rendering of the deck and workbook (no PowerPoint or Excel here), or set business-case
inputs (placeholders).

## What I learned

The model is the cheap, replaceable part; trust comes from checks around it, and the checks need their own evaluation
(they produced false alarms on every new issuer layout). A single sample proves feasibility, not accuracy; the honest
numbers are the failure cases. The environment (memory, containers, license of a dependency, what a subscription route does
not support) cost more time than the model.
