# AI log and reflection

Tools: Claude Code (AI coding agent) for research, code, evaluation, documents and the deck; GPT-6 Luna (via LiteLLM)
as the model inside DocPipe. Prompts 1-4 come from earlier sessions whose transcripts are not on this machine
(paraphrased); 5-8 are verbatim.

## The prompts that mattered

1. *(paraphrased)* "Plan the challenge around digitising documents into a file system and a knowledge base: PaddleOCR, BERTopic or a small LLM for tags, then OpenViking." Then: "Replace the OCR stack with a vision-model call, and explain why."
2. *(paraphrased)* "Use GPT-6 Luna through a LiteLLM gateway; connect an agent to the KB; add tracing and PII removal."
3. *(paraphrased)* "Start without containers" (after Podman failed); "continue with all remaining steps until finished."
4. *(paraphrased)* "Measure it: seeded errors, scans without a text layer, cited KB questions, prompt injection."
5. "Review the current status of the code. I want to make sure all components works end 2 end, and you have all right to install new things and dev new things, UI, connect stuffs to make it works for both document organization into folder, organize in openviking knowledge base, and ocr via LLM."
6. "Read the mission, and the deliverable needed to be prepared, including the demo, the presentation files, explain the technical decision, architecture and stuffs. [...] I will approve before you make it. Remember to commit code and stuffs as well"
7. "About the deck, you can build it yourself, don't rely from the build_deck.py"
8. "I will add my voice later. You can record and add the content that you need to narrate as subtitle"

## Where the AI got it wrong, and how it was fixed

| What went wrong | How it showed up | Fix |
|---|---|---|
| Assumed provider-side JSON schema works on the subscription route | Invented keys in replies | Schema in the prompt, local validation, bounded retry |
| OpenViking summaries failed silently | Search matched folder names only | Gateway rejected `temperature=0`: `drop_params`; "no summary" is now a reported status |
| Net-profit check counted the bank's tax three times | Techcombank statements sent to review | Prefer the total tax line |
| Invoice filed under the seller | Folder named after the supplier | Rule: name the bank's customer; 6/6 traps now pass |
| An eval run could publish seeded wrong copies into the real KB | Caught before the first sync | Publish guard on the output folder, unit-tested |
| A "perfect" OCR score (CER 0.000) on a 40%-resolution photo | Looked too good | Checked by hand: genuine. Found the real failure: invented table header |
| Business case used the synthetic 88% auto-file rate as base | Too optimistic | Discounted to 70%; sensitivity shows manual minutes matter most |

## What AI helped with, and what it could not do

Helped: reading unfamiliar docs fast, writing the pipeline, UI and harnesses, generating labelled synthetic scans with
traps, finding failures by running on real documents, drafting the memo, plans and deck. Could not: talk to
stakeholders (no real interview yet; the memo says so), time the real manual work, run containers on this machine, or
choose business-case inputs (labelled assumptions).

## What I learned

The model is the cheap, replaceable part; trust comes from the checks around it, and the checks need their own
evaluation. Silent failures cost more than loud ones, so every component now reports its state. A perfect score is a
reason to look harder.
