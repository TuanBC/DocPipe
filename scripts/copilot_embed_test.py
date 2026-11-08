"""GitHub Copilot device login (first call) and embedding smoke test via LiteLLM.

Output is written to scripts/.copilot.log so a non-interactive launcher can show the device code.
Token is stored by LiteLLM in ~/.config/litellm/github_copilot/.
Run: uv run --group gateway python scripts/copilot_embed_test.py
"""
import sys
from pathlib import Path

log = open(Path(__file__).parent / ".copilot.log", "w", buffering=1, encoding="utf-8")
sys.stdout = sys.stderr = log

import litellm  # noqa: E402

try:
    r = litellm.embedding(model="github_copilot/text-embedding-3-small",
                          input=["Tổng tài sản của Vinamilk", "total assets of Vinamilk"])
    v = r.data[0]["embedding"]
    print("EMBED_OK dim=", len(v), "n=", len(r.data), "usage=", r.usage)
except Exception as e:  # noqa: BLE001
    print("EMBED_FAIL", type(e).__name__, str(e)[:500])
