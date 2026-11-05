"""Test isolation: force the deterministic provider so the suite is fast and
independent of the developer's local .env / Ollama state. Real LLM-backed
behavior is covered separately in test_llm_integration.py, which is skipped
when Ollama is not reachable.
"""

import os

os.environ["AI_PROVIDER"] = "demo"
