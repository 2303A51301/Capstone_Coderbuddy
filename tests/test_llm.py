import pytest

from app.llm import LLMError, OllamaClient


def valid_payload():
    return {
        "project_type": "sample-app",
        "analysis": "A small example application.",
        "features": ["Add items", "Remove items"],
        "plan": ["Implement logic", "Build UI", "Test behavior"],
        "files": {
            "index.html": "<!doctype html><html><head></head><body></body></html>",
            "styles.css": "body { font-family: sans-serif; }",
            "app.js": "console.log('ready');",
            "app_logic.py": "def add(a, b): return a + b",
            "test_app.py": "def test_add(): assert 1 + 1 == 2",
            "README.md": "Open index.html",
        },
    }


def test_json_extractor_handles_reasoning_and_raw_newlines():
    response = 'A brief note {not json}\n{"files": {"app_logic.py": "line one\nline two"}}'
    parsed = OllamaClient._extract_json(response)
    assert parsed["files"]["app_logic.py"] == "line one\nline two"


def test_project_contract_requires_preview_and_tests():
    client = OllamaClient()
    draft = client._validate_payload(valid_payload())
    assert draft.project_type == "sample-app"
    assert "styles.css" in draft.files["index.html"] or "<head" in draft.files["index.html"]
    assert {"index.html", "app.js", "test_app.py"}.issubset(draft.files)


def test_rejects_path_traversal_in_model_output():
    payload = valid_payload()
    payload["files"]["../escape.py"] = "print('unsafe')"
    with pytest.raises(LLMError, match="Unsafe generated file path"):
        OllamaClient()._validate_payload(payload)


def test_rejects_extra_executable_python_modules():
    payload = valid_payload()
    payload["files"]["server.py"] = "print('no')"
    with pytest.raises(LLMError, match="restricted to"):
        OllamaClient()._validate_payload(payload)


def test_refinement_applies_exact_edits_and_retains_unchanged_files(monkeypatch):
    import json

    client = OllamaClient()
    files = valid_payload()["files"]
    before = dict(files)
    patch = {"project_type": "sample-app", "analysis": "Update title", "files": {},
             "edits": [{"path": "index.html", "old": "<head></head>",
                        "new": "<head><title>Updated</title></head>"}]}
    monkeypatch.setattr(client, "_call", lambda *args, **kwargs: json.dumps(patch))
    draft = client.refine_project("Add a title", files)
    assert "<title>Updated</title>" in draft.files["index.html"]
    assert draft.files["app_logic.py"] == before["app_logic.py"]
    assert files == before


@pytest.mark.parametrize("old", ["missing substring", " "])
def test_refinement_rejects_missing_or_ambiguous_edits(monkeypatch, old):
    import json

    client = OllamaClient()
    patch = {"files": {}, "edits": [{"path": "app_logic.py", "old": old, "new": "new"}]}
    monkeypatch.setattr(client, "_call", lambda *args, **kwargs: json.dumps(patch))
    with pytest.raises(LLMError, match="match exactly once"):
        client.refine_project("Change logic", valid_payload()["files"])


@pytest.mark.parametrize("plan", [[], ["Update images"], ["Update images", "Verify"], ["One", "Two", "Three"]])
def test_planner_handles_short_model_plans(plan):
    from app.agents import Analysis, PlanningAgent

    steps = PlanningAgent().plan(Analysis("sample-app", "A source refinement", [], plan))
    assert len(steps) == 5
    assert [step.id for step in steps] == ["analyze", "design", "generate", "validate", "correct"]
    if plan:
        assert steps[1].description == plan[0]
