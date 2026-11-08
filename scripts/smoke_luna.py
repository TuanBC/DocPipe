"""Day 1 smoke test: gpt-6-luna through LiteLLM's chatgpt/ provider (no containers).

Checks (each PASS/FAIL with the raw error):
  1. text completion + token usage
  2. image input (Vietnamese balance-sheet fragment)
  3. JSON via chat-completions response_format json_schema (bridged route)
  4. JSON via native Responses API text.format json_schema
  5. embeddings on the same route (expected unsupported)

Run: uv run --group gateway python scripts/smoke_luna.py [model]
"""
import json
import sys
import time
from pathlib import Path

import litellm

sys.path.insert(0, str(Path(__file__).parent))
from smoke_common import EXPECT, PROMPT, SCHEMA, png_b64  # noqa: E402

MODEL = sys.argv[1] if len(sys.argv) > 1 else "chatgpt/gpt-6-luna"
PNG = png_b64()


def report(name, ok, detail):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def tokens(resp):
    u = getattr(resp, "usage", None)
    if not u:
        return None
    g = lambda k: getattr(u, k, None)  # noqa: E731
    return {"in": g("prompt_tokens") or g("input_tokens"), "out": g("completion_tokens") or g("output_tokens")}


def check_json(name, text, usage, t0):
    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001
        report(name, False, f"not JSON: {text[:200]!r}")
        return
    ok = all(data.get(k) == v for k, v in EXPECT.items())
    report(name, ok, f"{data} tokens={usage} {time.time() - t0:.1f}s")


# 1 text
t = time.time()
try:
    r = litellm.completion(model=MODEL, messages=[{"role": "user", "content": "Reply with the single word: pong"}])
    report("text", True, f"{r.choices[0].message.content!r} tokens={tokens(r)} {time.time() - t:.1f}s")
except Exception as e:  # noqa: BLE001
    report("text", False, repr(e)[:500])
    sys.exit(1)

content = [
    {"type": "text", "text": PROMPT},
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG}"}},
]

# 2 image
t = time.time()
try:
    r = litellm.completion(model=MODEL, messages=[{"role": "user", "content": [
        {"type": "text", "text": "Transcribe the row 'TỔNG CỘNG TÀI SẢN' exactly (label and both values) and the unit."},
        content[1]]}])
    report("image", True, f"{r.choices[0].message.content!r} tokens={tokens(r)} {time.time() - t:.1f}s")
except Exception as e:  # noqa: BLE001
    report("image", False, repr(e)[:500])

# 3 chat-completions json_schema
t = time.time()
try:
    r = litellm.completion(model=MODEL, messages=[{"role": "user", "content": content}],
                           response_format={"type": "json_schema",
                                            "json_schema": {"name": "bs", "strict": True, "schema": SCHEMA}})
    check_json("chat json_schema", r.choices[0].message.content, tokens(r), t)
except Exception as e:  # noqa: BLE001
    report("chat json_schema", False, repr(e)[:500])


# 4b schema described in the prompt (what we will actually rely on) + local validation
t = time.time()
try:
    r = litellm.completion(model=MODEL, messages=[{"role": "user", "content": [
        {"type": "text", "text": PROMPT + " Reply with JSON only, no prose, matching exactly this JSON schema: "
         + json.dumps(SCHEMA)}, content[1]]}])
    txt = r.choices[0].message.content.strip().removeprefix("```json").removesuffix("```").strip()
    check_json("prompt-embedded schema", txt, tokens(r), t)
except Exception as e:  # noqa: BLE001
    report("prompt-embedded schema", False, repr(e)[:500])
# 4 native Responses text.format
t = time.time()
try:
    r = litellm.responses(
        model=MODEL,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": PROMPT},
            {"type": "input_image", "image_url": f"data:image/png;base64,{PNG}"}]}],
        text={"format": {"type": "json_schema", "name": "bs", "strict": True, "schema": SCHEMA}},
    )
    out = "".join(c.text for item in r.output if getattr(item, "type", "") == "message" for c in item.content)
    check_json("responses json_schema", out, tokens(r), t)
except Exception as e:  # noqa: BLE001
    report("responses json_schema", False, repr(e)[:500])

# 5 embeddings
try:
    r = litellm.embedding(model="chatgpt/text-embedding-3-small", input=["xin chào"])
    report("embeddings", True, f"dim={len(r.data[0]['embedding'])}")
except Exception as e:  # noqa: BLE001
    report("embeddings", False, repr(e)[:300])
