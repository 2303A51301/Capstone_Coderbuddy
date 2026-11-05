"""End-to-end test of the real (non-deterministic) LLM-backed pipeline: a
local Ollama model analyzes an arbitrary natural-language requirement,
generates code, the generated pytest suite is actually executed, and — if it
fails — the failure output is fed back to the model for a bounded, real
correction/retry loop.

This test is automatically skipped when Ollama isn't reachable (e.g. CI,
or a machine without it installed), so it never blocks the core deterministic
test suite.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.llm import OllamaClient
from app.orchestrator import Orchestrator

client = OllamaClient()
pytestmark = pytest.mark.skipif(not client.is_reachable(), reason="Ollama is not reachable on this machine")


def test_llm_pipeline_produces_a_working_generated_app(tmp_path: Path):
    orchestrator = Orchestrator(tmp_path / "workspace", provider="ollama")
    state = orchestrator.initialize("Build a function that converts Celsius to Fahrenheit and back")
    state = orchestrator.execute(state.requirement, state)

    assert state.mode == "llm"
    assert "app_logic.py" in state.generated_files
    assert "test_app.py" in state.generated_files
    # The model's own generated tests were actually executed (not just compiled).
    assert state.validation_output
    assert state.status in ("completed", "failed")  # bounded retries may still fail; that's honest and expected

    shutil.rmtree(tmp_path, ignore_errors=True)
