"""
Test configuration.

Set env BEFORE any app module imports so the cached settings pick it up:
* Auth disabled (no BACKEND_API_KEY).
* Ollama base URL pointed at an unreachable port, so the single live-path test
  (test_chat_streams) degrades instantly and deterministically instead of doing
  real local inference. All agent-logic tests inject a deterministic stub LLM.
"""

import os

os.environ.setdefault("BACKEND_API_KEY", "")
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9"  # unreachable → fast graceful failure
os.environ["LLM_TIMEOUT"] = "5"
