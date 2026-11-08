"""One-time ChatGPT (Codex) device-code login for the LiteLLM chatgpt/ provider.

Writes the verification URL and code to scripts/.login.log (line-buffered) so a
non-interactive launcher can show them, then blocks until the login completes.
Tokens land in ~/.config/litellm/chatgpt/auth.json.
"""
import sys
from pathlib import Path

log = open(Path(__file__).parent / ".login.log", "w", buffering=1, encoding="utf-8")
sys.stdout = sys.stderr = log

from litellm.llms.chatgpt.authenticator import Authenticator  # noqa: E402

Authenticator().get_access_token()
print("LOGIN_OK")
