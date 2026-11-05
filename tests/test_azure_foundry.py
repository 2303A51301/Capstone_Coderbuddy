import json

import httpx
import pytest

from app.llm import AzureFoundryClient, AzureFoundryConfig, LLMError
from app.orchestrator import Orchestrator
from tests.test_llm import valid_payload


def azure_client(key="test-secret"):
    return AzureFoundryClient(AzureFoundryConfig(
        endpoint="https://example.services.ai.azure.com/openai/v1/responses",
        model="gpt-4.1-mini",
        api_key=key,
    ))


def response_payload(text, status="completed"):
    return {"status": status, "output": [
        {"type": "message", "content": [{"type": "output_text", "text": text}]},
    ]}


def test_generation_and_repair_use_responses_contract(monkeypatch):
    client = azure_client()
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(200, json=response_payload(json.dumps(valid_payload())),
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    assert client.generate_project("Build a quiz").project_type == "sample-app"
    client.correct_project("Build a quiz", valid_payload()["files"], "AssertionError: expected 4")
    assert len(calls) == 2
    for call in calls:
        assert call["headers"] == {"api-key": "test-secret"}
        assert call["json"]["model"] == "gpt-4.1-mini"
        assert call["json"]["store"] is False
        assert call["json"]["text"]["format"]["type"] == "json_object"
        assert call["json"]["max_output_tokens"] == 24000
        assert "test-secret" not in json.dumps(call["json"])
    assert "AssertionError: expected 4" in calls[1]["json"]["input"]
    assert "test-secret" not in repr(client.config)


def test_missing_key_never_makes_network_request(monkeypatch):
    def post(*args, **kwargs):
        pytest.fail("Missing configuration must not send requests")

    monkeypatch.setattr(httpx, "post", post)
    client = azure_client(key="")
    assert client.status_label() == "azure-foundry-key-missing"
    with pytest.raises(LLMError, match="key-missing"):
        client.generate_project("Build a quiz")


@pytest.mark.parametrize("endpoint", [
    "http://example.services.ai.azure.com/openai/v1/responses",
    "https://example.com/openai/v1/responses",
    "https://example.services.ai.azure.com/openai/v1/responses?key=secret",
    "https://example.services.ai.azure.com/openai/v1/chat/completions",
])
def test_rejects_unsafe_or_incorrect_endpoint(endpoint):
    client = AzureFoundryClient(AzureFoundryConfig(endpoint, "gpt-4.1-mini", "test-secret"))
    assert client.status_label() == "azure-foundry-configuration-invalid"


@pytest.mark.parametrize(("code", "label"), [
    (401, "auth-failed"), (403, "auth-failed"), (404, "deployment-missing"),
    (429, "rate-limited"), (500, "unavailable"),
])
def test_provider_errors_are_sanitized(monkeypatch, code, label):
    def post(url, **kwargs):
        return httpx.Response(code, json={"error": "test-secret"},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    client = azure_client()
    assert client.status_label() == f"azure-foundry-{label}"
    with pytest.raises(LLMError) as error:
        client.generate_project("Build a quiz")
    assert "test-secret" not in str(error.value)


def test_probe_is_minimal_and_cached(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(200, json=response_payload("OK"),
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    client = azure_client()
    assert client.model_available()
    assert client.status_label() == "azure-foundry:gpt-4.1-mini"
    assert client.model_available()
    assert calls == [{"model": "gpt-4.1-mini", "store": False,
                      "input": "Reply with OK.", "max_output_tokens": 16}]


@pytest.mark.parametrize("payload", [
    response_payload("partial", status="incomplete"),
    response_payload(""),
    {"status": "completed", "output": []},
    {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "refusal", "refusal": "test-secret"},
    ]}]},
])
def test_incomplete_empty_or_refused_output_rejected(payload):
    with pytest.raises(LLMError):
        AzureFoundryClient._response_text(payload)


def test_azure_workflow_runs_real_generated_tests(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("AZURE_OPENAI_RESPONSES_ENDPOINT",
                       "https://example.services.ai.azure.com/openai/v1/responses")
    draft = valid_payload()
    draft["files"]["test_app.py"] = (
        "import app_logic\n\ndef test_add():\n    assert app_logic.add(2, 3) == 5\n"
    )

    def post(url, **kwargs):
        text = "OK" if kwargs["json"]["input"] == "Reply with OK." else json.dumps(draft)
        return httpx.Response(200, json=response_payload(text),
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    orchestrator = Orchestrator(tmp_path, provider="azure-foundry")
    run = orchestrator.execute("Build a sample application")
    assert run.status == "completed"
    assert run.mode == "llm"
    assert run.provider_name == "Azure Foundry"
    assert run.model_name == "gpt-4.1-mini"
    assert "1 passed" in run.validation_output
    assert any(log.tool == "azure-foundry.generate" for log in run.logs)
    assert "test-secret" not in run.model_dump_json()


def test_missing_azure_key_has_explicit_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    orchestrator = Orchestrator(tmp_path, provider="azure-foundry")
    run = orchestrator.execute("Build a calculator")
    assert run.mode == "deterministic-fallback"
    assert run.model_name is None
    assert any("azure-foundry-key-missing" in log.detail for log in run.logs)


def test_health_reports_actual_provider_without_credentials(monkeypatch, tmp_path):
    import app.main as main

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    monkeypatch.setattr(main, "orchestrator", Orchestrator(tmp_path, provider="azure-foundry"))
    health = main.health()
    assert health["provider"] == "azure-foundry-key-missing"
    assert health["provider_name"] == "Azure Foundry"
    assert health["model_ready"] is False
    assert "api_key" not in health
