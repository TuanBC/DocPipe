# AI log and reflection

Tools: Claude Code (AI coding agent) for research, code, evaluation, documents and the deck; GPT-6 Luna (through
LiteLLM) as the model inside DocPipe. Prompts 6-9 are verbatim; 1-5 are from earlier sessions whose transcripts are
not on this machine, so they are paraphrased.

## The prompts that mattered

1. *(paraphrased)* "Plan the challenge around document digitalisation into a file system and a knowledge base; I am thinking PaddleOCR, BERTopic or a small LLM for tags, then OpenViking."
2. *(paraphrased)* "Replace the OCR stack with a vision-model call to simplify, and explain why in the plan."
3. *(paraphrased)* "Use GPT-6 Luna through a LiteLLM gateway; connect an agent to the KB; add tracing and PII removal."
4. *(paraphrased)* "Start without containers" (after Podman failed), then "continue with all remaining steps until finished."
5. *(paraphrased)* "Measure it: seeded errors, scans without a text layer, KB questions with citations, prompt injection."
6. "Review the current status of the code. I want to make sure all components works end 2 end, and you have all right to install new things and dev new things, UI, connect stuffs to make it works for both document organization into folder, organize in openviking knowledge base, and ocr via LLM."
7. "Read the mission, and the deliverable needed to be prepared, including the demo, the presentation files, explain the technical decision, architecture and stuffs. Read the whole document and give me the plan to make all of them. I will approve before you make it. Remember to commit code and stuffs as well"
8. "About the deck, you can build it yourself, don't rely from the build_deck.py"
9. "I will add my voice later. You can record and add the content that you need to narrate as subtitle"

## Where the AI got it wrong, and how it was fixed

| What went wrong | How it showed up | Fix |
|---|---|---|
| Assumed provider-side JSON schema works on the subscription route | Smoke test returned invented keys | Schema in the prompt, local validation, bounded retry |
| OpenViking summaries failed silently | Search matched folder names only; found only when reading `.overview.md` | Gateway rejected `temperature=0`; `drop_params: true`; status `ingested_no_summary` is now reported, all documents re-synced |
| Net-profit check counted the bank's tax three times | Techcombank statements sent to review | Prefer the total tax line; sum components only when no total is printed |
| Invoice filed under the seller | Folder named after the supplier, not the bank's customer | Classifier rule: name the bank's customer (buyer, borrower, account holder), never the bank, auditor or a government office; 6/6 traps now pass |
| An evaluation run could publish seeded wrong copies into the real KB | Noticed before the first sync, run stopped | Publish guard: only the configured output folder publishes; unit-tested |
| Concurrent evaluation runs raced on the same files | One result contaminated | Re-ran sequentially; harnesses use their own folders |
| Synthetic test set looked "perfect" (CER 0.000) | Suspicious score on a 40%-resolution photo | Checked the raw output by hand: genuinely exact. Also found the real failure: the model invents a table header row |
| Business case first used the synthetic auto-file rate (88%) as the base | Too optimistic for real scans | Discounted to 70% and labelled; sensitivity shows manual minutes matter more than automation rate |
| Validator label patterns too loose or too narrow on new issuers | False alarms on Hòa Phát and the bank format | Anchored patterns; tuned on those documents, so no held-out accuracy claim |

## What AI helped with, and what it could not do

Helped: reading unfamiliar docs fast (LiteLLM, OpenViking, pptxgenjs), writing the pipeline, the UI and the harnesses,
generating labelled synthetic scans with traps, finding failure cases by running on real documents, drafting the memo,
plans and deck. Could not: talk to stakeholders (no real interview yet; the memo says so), time the real manual work,
get containers running on this machine, or decide the business-case inputs (they are labelled assumptions).

## What I learned

The model is the cheap, replaceable part; trust comes from the checks around it, and those checks need their own
evaluation. Silent failures (a summary that never generated, an eval that could write to production) cost more than
loud ones, so every component now reports its state. A perfect score is a reason to look harder, not to stop.
