import threading
import time
from pathlib import Path

import pytest

from app.llm import LLMError, OllamaClient
from app.models import RunState, RunStatus
from app.orchestrator import Orchestrator
from app.queue import BuildQueue
from app.store import RunStore
from tests.test_llm import valid_payload


def setup_queue(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    orchestrator = Orchestrator(tmp_path / "workspace", provider="demo")
    return store, orchestrator, BuildQueue(store, orchestrator)


def test_fifo_unique_workspaces_and_actual_results(tmp_path):
    store, orchestrator, queue = setup_queue(tmp_path)
    runs = [store.enqueue(orchestrator.initialize(request)) for request in [
        "Build a calculator", "Build a todo app", "Create a landing page",
    ]]
    for index, expected in enumerate(runs):
        assert queue.process_one()
        assert store.get(expected.id).status == RunStatus.COMPLETED
        assert store.get(expected.id).sequence == index + 1
        for later in runs[index + 1:]:
            assert store.get(later.id).status == RunStatus.QUEUED
    assert not queue.process_one()
    assert len({store.get(run.id).workspace for run in runs}) == 3
    assert "passed" in store.get(runs[0].id).validation_output
    assert RunStore(store.path).get(runs[0].id).validation_output


def test_claim_is_atomic_and_only_one_active_across_connections(tmp_path):
    store, orchestrator, _ = setup_queue(tmp_path)
    for _ in range(5):
        store.enqueue(orchestrator.initialize("Build a calculator"))
    barrier = threading.Barrier(8)
    results = []

    def claim():
        other = RunStore(store.path)
        barrier.wait()
        results.append(other.claim_next())

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len([run for run in results if run]) == 1


def test_idempotent_submission_and_conflict(tmp_path):
    store, orchestrator, _ = setup_queue(tmp_path)
    run = orchestrator.initialize("Build a calculator")
    run.request_id = "request-token"
    saved = store.enqueue(run)
    other = orchestrator.initialize(run.requirement)
    other.request_id = run.request_id
    assert store.enqueue(other).id == saved.id
    other.requirement = "Build a different application"
    with pytest.raises(ValueError, match="different request"):
        store.enqueue(other)
    assert len(store.list()) == 1


def test_cancel_survives_reload_and_does_not_cancel_active(tmp_path):
    store, orchestrator, _ = setup_queue(tmp_path)
    one = store.enqueue(orchestrator.initialize("Build a calculator"))
    two = store.enqueue(orchestrator.initialize("Build a todo app"))
    active = store.claim_next()
    assert active.id == one.id
    with pytest.raises(ValueError, match="Only waiting"):
        store.cancel(one.id)
    store.cancel(two.id)
    assert RunStore(store.path).get(two.id).status == RunStatus.CANCELLED


def test_recovery_retains_interrupted_and_resumes_waiting(tmp_path):
    store, orchestrator, queue = setup_queue(tmp_path)
    one = store.enqueue(orchestrator.initialize("Build a calculator"))
    two = store.enqueue(orchestrator.initialize("Build a todo app"))
    store.claim_next()
    store.recover_interrupted()
    interrupted = store.get(one.id)
    assert interrupted.status == RunStatus.FAILED
    assert "Server stopped" in interrupted.error
    assert interrupted.logs[-1].action == "interrupted"
    assert queue.process_one()
    assert store.get(two.id).status == RunStatus.COMPLETED


def test_failed_build_does_not_block_next(tmp_path, monkeypatch):
    store, orchestrator, queue = setup_queue(tmp_path)
    one = store.enqueue(orchestrator.initialize("Build a calculator"))
    two = store.enqueue(orchestrator.initialize("Build a todo app"))
    execute = orchestrator.execute

    def fail_first(requirement, run, **kwargs):
        if run.id == one.id:
            raise ValueError("Observed build failure")
        return execute(requirement, run, **kwargs)

    monkeypatch.setattr(orchestrator, "execute", fail_first)
    assert queue.process_one()
    assert store.get(one.id).status == RunStatus.FAILED
    assert queue.process_one()
    assert store.get(two.id).status == RunStatus.COMPLETED


def test_source_import_preserves_files_without_claiming_old_validation(tmp_path):
    store, orchestrator, _ = setup_queue(tmp_path)
    project = orchestrator.safe_workspace.project_path("old123")
    (project / "CODER_BUDDY_REQUEST.txt").write_text("Build an old app", encoding="utf-8")
    (project / "index.html").write_text("<html>Original source</html>", encoding="utf-8")
    store.import_workspaces(orchestrator.safe_workspace.root)
    store.import_workspaces(orchestrator.safe_workspace.root)
    assert len(store.list()) == 1
    imported = store.get("old123")
    assert imported.mode == "recovered"
    assert imported.status == RunStatus.FAILED
    assert not imported.validation_output
    assert (project / "index.html").read_text() == "<html>Original source</html>"


def test_worker_lock_prevents_second_worker_and_restart_reopens_history(tmp_path):
    store, orchestrator, queue = setup_queue(tmp_path)
    queue.start()
    second = BuildQueue(RunStore(store.path), orchestrator)
    try:
        with pytest.raises(RuntimeError, match="Another CoderBuddy worker"):
            second.start()
        run = store.enqueue(orchestrator.initialize("Build a calculator"))
        queue.notify()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and store.get(run.id).status in {RunStatus.QUEUED, RunStatus.RUNNING}:
            time.sleep(.05)
        assert store.get(run.id).status == RunStatus.COMPLETED
    finally:
        queue.stop()
    restarted = BuildQueue(RunStore(store.path), orchestrator)
    restarted.start()
    restarted.stop()
    assert RunStore(store.path).get(run.id).status == RunStatus.COMPLETED


def test_refinement_receives_real_source_and_preserves_original(tmp_path, monkeypatch):
    store, orchestrator, queue = setup_queue(tmp_path)
    original = store.enqueue(orchestrator.initialize("Build a calculator"))
    queue.process_one()
    source = store.get(original.id)
    project = Path(source.workspace)
    html = (project / "index.html").read_text(encoding="utf-8")
    (project / "index.html").write_text(html + "\n<!-- User customization -->", encoding="utf-8")
    followup = orchestrator.initialize(source.requirement + "\n\nFollow-up change request: Add a title")
    followup.project_id = source.project_id
    followup.source_run_id = source.id
    saved = store.enqueue(followup)
    orchestrator.provider = "ollama"
    monkeypatch.setattr(orchestrator.llm, "model_available", lambda: True)
    seen = []

    def refine(requirement, files):
        seen.append(files)
        payload = valid_payload()
        payload["files"]["index.html"] = files["index.html"] + "\n<!-- New title -->"
        return OllamaClient()._validate_payload(payload)

    monkeypatch.setattr(orchestrator.llm, "refine_project", refine)
    queue.process_one()
    refined = store.get(saved.id)
    assert refined.status == RunStatus.COMPLETED
    assert "<!-- User customization -->" in seen[0]["index.html"]
    assert (project / "index.html").read_text(encoding="utf-8") == html + "\n<!-- User customization -->"
    assert Path(refined.workspace) != project
    assert store.get(source.id).validation_output == source.validation_output


def test_stored_snapshots_do_not_share_mutable_state(tmp_path):
    store, orchestrator, _ = setup_queue(tmp_path)
    run = store.enqueue(orchestrator.initialize("Build a calculator"))
    run.requirement = "Changed but not saved"
    assert store.get(run.id).requirement == "Build a calculator"


def test_invalid_javascript_fails_actual_validation(tmp_path):
    _, orchestrator, _ = setup_queue(tmp_path)
    template = orchestrator.generator.generate("Build a calculator")
    project = orchestrator.safe_workspace.project_path("invalidjs")
    orchestrator._write_template(project, template, "Build a calculator")
    (project / "app.js").write_text("function broken( {", encoding="utf-8")
    result, tool = orchestrator._validate(project, template)
    assert result.returncode != 0
    assert tool == "node --check app.js"
    assert "SyntaxError" in result.stderr


def test_external_images_fail_preview_compatibility_but_svg_namespaces_pass(tmp_path):
    _, orchestrator, _ = setup_queue(tmp_path)
    template = orchestrator.generator.generate("Build a calculator")
    project = orchestrator.safe_workspace.project_path("externalimg")
    template.files["app.js"] += '\nconst image = "https://example.com/image.png";'
    orchestrator._write_template(project, template, "Build a calculator")
    result, tool = orchestrator._validate(project, template)
    assert result.returncode == 1
    assert tool == "validator.preview-compatibility"
    assert "external URLs are blocked" in result.stderr
    template.files["app.js"] = 'const image = \'<svg xmlns="http://www.w3.org/2000/svg"></svg>\';'
    orchestrator._write_template(project, template, "Build a calculator")
    result, _ = orchestrator._validate(project, template)
    assert result.returncode == 0


def test_refinement_repair_failure_never_replaces_source_with_fallback(tmp_path, monkeypatch):
    _, orchestrator, _ = setup_queue(tmp_path)
    orchestrator.provider = "ollama"
    monkeypatch.setattr(orchestrator.llm, "model_available", lambda: True)
    payload = valid_payload()
    payload["files"]["test_app.py"] = "def test_real_failure(): assert False"
    draft = OllamaClient()._validate_payload(payload)
    monkeypatch.setattr(orchestrator.llm, "refine_project", lambda *args: draft)

    def failed_correction(*args):
        raise LLMError("Observed provider repair failure")

    monkeypatch.setattr(orchestrator.llm, "correct_project", failed_correction)
    run = orchestrator.execute("Keep the app, change its title", source_files=valid_payload()["files"])
    assert run.status == RunStatus.FAILED
    assert run.mode == "llm"
    assert not any(log.action == "fallback_started" for log in run.logs)
    assert sum(log.action == "run_failed" for log in run.logs) == 1
