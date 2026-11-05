from fastapi.testclient import TestClient

from app.main import app
import app.main as main
import pytest

from app.orchestrator import Orchestrator
from app.queue import BuildQueue
from app.store import RunStore


client = TestClient(app)

@pytest.fixture(autouse=True)
def isolated_api(tmp_path, monkeypatch):
    store = RunStore(tmp_path / "runs.sqlite3")
    orchestrator = Orchestrator(tmp_path / "workspace", provider="demo")
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "orchestrator", orchestrator)
    monkeypatch.setattr(main, "queue", BuildQueue(store, orchestrator))


def finish(run_id):
    main.queue.process_one()
    return client.get(f"/api/runs/{run_id}").json()


def test_health_works():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_todo_run_is_generated_and_validated():
    response = client.post("/api/runs", json={"requirement": "Build a todo app to manage daily tasks"})
    assert response.status_code == 202
    run_id = response.json()["run"]["id"]
    run = finish(run_id)
    assert run["status"] == "completed"
    assert run["project_type"] == "todo-app"
    assert {"index.html", "styles.css", "app.js", "app_logic.py", "test_app.py"}.issubset(run["generated_files"])
    assert "passed" in run["validation_output"]
    assert all(step["status"] == "succeeded" for step in run["plan"])


def test_run_can_be_iterated():
    created_response = client.post("/api/runs", json={"requirement": "Create a landing page"})
    created = created_response.json()["run"]
    finish(created["id"])
    response = client.post(f"/api/runs/{created['id']}/iterate", json={"instruction": "Use a brighter call to action"})
    assert response.status_code == 202
    final = finish(response.json()["run"]["id"])
    assert final["id"] != created["id"]
    assert final["project_id"] == created["id"]
    assert final["source_run_id"] == created["id"]
    assert final["status"] == "failed"
    assert "original build is unchanged" in final["error"].lower()
    assert client.get(f"/api/runs/{created['id']}").json()["status"] == "completed"
    assert final["requirement"] == "Create a landing page\n\nFollow-up change request: Use a brighter call to action"
    assert any(log["action"] == "iteration_requested" for log in final["logs"])


def test_preview_and_download_are_available_for_generated_app():
    response = client.post("/api/runs", json={"requirement": "Build a calculator"})
    run_id = response.json()["run"]["id"]
    finish(run_id)
    preview = client.get(f"/api/runs/{run_id}/preview")
    assert preview.status_code == 200
    assert "Calculator" in preview.text
    assert f'<base href="/api/runs/{run_id}/assets/">' in preview.text
    stylesheet = client.get(f"/api/runs/{run_id}/assets/styles.css")
    assert stylesheet.status_code == 200
    assert "color-scheme" in stylesheet.text
    bundle = client.get(f"/api/runs/{run_id}/download")
    assert bundle.status_code == 200
    assert bundle.headers["content-type"] == "application/zip"


def test_misspelled_clothing_store_request_builds_naveen_storefront():
    response = client.post(
        "/api/runs",
        json={"requirement": "Build an ecommerse store for cloth branding Naveen and add some cloths tshirts"},
    )
    assert response.status_code == 202
    run_id = response.json()["run"]["id"]
    run = finish(run_id)
    assert run["status"] == "completed"
    assert run["project_type"] == "ecommerce-store"
    assert {"index.html", "styles.css", "app.js", "app_logic.py", "test_app.py", "Dockerfile", "nginx.conf", "DEPLOYMENT.md"}.issubset(run["generated_files"])
    html = client.get(f"/api/runs/{run['id']}/file", params={"path": "index.html"}).json()["content"]
    app_js = client.get(f"/api/runs/{run['id']}/file", params={"path": "app.js"}).json()["content"]
    assert "Naveen" in html
    assert "Everyday Heavyweight Tee" in app_js
    assert "Demo only, no payment processing" in html


def test_submission_is_durable_idempotent_and_cancellable():
    payload = {"requirement": "Build a calculator", "request_id": "api-stable-token"}
    first = client.post("/api/runs", json=payload).json()["run"]
    duplicate = client.post("/api/runs", json=payload).json()["run"]
    assert first["id"] == duplicate["id"]
    assert len(client.get("/api/runs").json()) == 1
    cancelled = client.post(f"/api/runs/{first['id']}/cancel")
    assert cancelled.json()["status"] == "cancelled"
    assert not main.queue.process_one()
    retry = client.post(f"/api/runs/{first['id']}/retry", json={
        "requirement": first["requirement"], "request_id": "retry-stable-token",
    })
    assert retry.status_code == 202
    retried = retry.json()["run"]
    assert retried["id"] != first["id"]
    assert retried["project_id"] == first["project_id"]
    assert retried["sequence"] > first["sequence"]
    assert finish(retried["id"])["status"] == "completed"
    assert client.get(f"/api/runs/{first['id']}").json()["status"] == "cancelled"


def test_active_cancel_and_duplicate_token_conflict_return_clear_errors():
    first = client.post("/api/runs", json={
        "requirement": "Build a calculator", "request_id": "reused-token",
    }).json()["run"]
    main.store.claim_next()
    assert client.post(f"/api/runs/{first['id']}/cancel").status_code == 409
    assert client.post("/api/runs", json={
        "requirement": "Build a different app", "request_id": "reused-token",
    }).status_code == 409
