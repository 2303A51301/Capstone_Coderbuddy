from __future__ import annotations

import io
import mimetypes
import os
import re
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.models import ActivityEvent, CreateRunRequest, IterateRequest, RunResponse, RunState, RunStatus, RunSummary, StepStatus
from app.orchestrator import Orchestrator
from app.store import RunStore
from app.queue import BuildQueue

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", str(BASE_DIR / "workspace")))
store = RunStore(Path(os.getenv("RUN_DATABASE", str(BASE_DIR / "data" / "coderbuddy.sqlite3"))))
orchestrator = Orchestrator(WORKSPACE_ROOT, provider=os.getenv("AI_PROVIDER", "demo"))
queue = BuildQueue(store, orchestrator)


@asynccontextmanager
async def lifespan(app: FastAPI):
    queue.start()
    try:
        yield
    finally:
        queue.stop()


app = FastAPI(title="CoderBuddy-CaPStone", version="3.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def _get_run_or_404(run_id: str) -> RunState:
    run = store.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


def _enqueue(run: RunState) -> RunResponse:
    if queue.error:
        raise HTTPException(503, queue.error)
    run.logs.append(ActivityEvent(agent="queue", action="request_queued", detail="Request saved to the local durable queue."))
    try:
        saved = store.enqueue(run)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    queue.notify()
    return RunResponse(run=saved, summary={"status_url": f"/api/runs/{saved.id}"})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    status = orchestrator.status_label()
    return {
        "status": "ok",
        "provider": status,
        "provider_name": orchestrator.provider_name,
        "model": orchestrator.model_name,
        "model_ready": status.startswith(("ollama:", "azure-foundry:")),
        "queue_error": queue.error or "",
    }


@app.post("/api/runs", response_model=RunResponse, status_code=202)
def create_run(payload: CreateRunRequest) -> RunResponse:
    run = orchestrator.initialize(payload.requirement.strip())
    run.request_id = payload.request_id
    return _enqueue(run)


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs() -> list[RunSummary]:
    return [RunSummary.from_state(run) for run in store.list()]


@app.get("/api/runs/{run_id}", response_model=RunState)
def get_run(run_id: str) -> RunState:
    return _get_run_or_404(run_id)


@app.get("/api/runs/{run_id}/files")
def list_run_files(run_id: str) -> dict[str, list[str]]:
    run = _get_run_or_404(run_id)
    return {"files": run.generated_files}


@app.get("/api/runs/{run_id}/file")
def get_run_file(run_id: str, path: str) -> dict[str, str]:
    run = _get_run_or_404(run_id)
    normalized = path.replace("\\\\", "/")
    if normalized not in run.generated_files or normalized == "CODER_BUDDY_REQUEST.txt":
        raise HTTPException(404, "Generated file not found")
    project = Path(run.workspace or "")
    try:
        target = orchestrator.safe_workspace._contained(project, project / normalized)
    except ValueError as exc:
        raise HTTPException(400, "Invalid file path") from exc
    if not target.is_file():
        raise HTTPException(404, "Generated file not found")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(415, "File is not UTF-8 text") from exc
    return {"path": normalized, "content": content}


@app.get("/api/runs/{run_id}/preview", response_class=HTMLResponse)
def preview_run(run_id: str) -> Response:
    run = _get_run_or_404(run_id)
    if "index.html" not in run.generated_files or not run.workspace:
        raise HTTPException(404, "This generated project has no browser preview")
    project = Path(run.workspace)
    target = orchestrator.safe_workspace._contained(project, project / "index.html")
    if not target.is_file():
        raise HTTPException(404, "Preview is not ready")
    document = target.read_text(encoding="utf-8")
    base_tag = f'<base href="/api/runs/{run.id}/assets/">'
    if re.search(r"<head\b[^>]*>", document, flags=re.I):
        document = re.sub(r"(<head\b[^>]*>)", r"\1" + base_tag, document, count=1, flags=re.I)
    else:
        document = base_tag + document
    return HTMLResponse(
        document,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; form-action 'none';",
        },
    )


@app.get("/api/runs/{run_id}/assets/{asset_path:path}")
def preview_asset(run_id: str, asset_path: str) -> FileResponse:
    run = _get_run_or_404(run_id)
    normalized = asset_path.replace("\\\\", "/")
    allowed_suffixes = {".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".woff", ".woff2", ".ico"}
    if normalized not in run.generated_files or Path(normalized).suffix.lower() not in allowed_suffixes:
        raise HTTPException(404, "Preview asset not found")
    project = Path(run.workspace or "")
    try:
        target = orchestrator.safe_workspace._contained(project, project / normalized)
    except ValueError as exc:
        raise HTTPException(400, "Invalid asset path") from exc
    if not target.is_file():
        raise HTTPException(404, "Preview asset not found")
    return FileResponse(target, media_type=mimetypes.guess_type(target.name)[0], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/api/runs/{run_id}/download")
def download_run(run_id: str) -> StreamingResponse:
    run = _get_run_or_404(run_id)
    if not run.workspace or not run.generated_files:
        raise HTTPException(409, "No generated files are available yet")
    project = Path(run.workspace)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for relative in run.generated_files:
            if relative == "CODER_BUDDY_REQUEST.txt":
                continue
            try:
                target = orchestrator.safe_workspace._contained(project, project / relative)
            except ValueError as exc:
                raise HTTPException(400, "Invalid generated file path") from exc
            if target.is_file():
                bundle.write(target, arcname=relative)
    archive.seek(0)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", run.project_type or "coder-buddy-app").strip("-") or "coder-buddy-app"
    return StreamingResponse(archive, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'})


@app.post("/api/runs/{run_id}/iterate", response_model=RunResponse, status_code=202)
def iterate(run_id: str, payload: IterateRequest) -> RunResponse:
    previous = _get_run_or_404(run_id)
    if previous.status == RunStatus.RUNNING or previous.status == RunStatus.QUEUED:
        raise HTTPException(409, "Wait for the current build to finish before iterating")
    combined = f"{previous.requirement}\n\nFollow-up change request: {payload.instruction.strip()}"
    run = orchestrator.initialize(combined)
    if not previous.generated_files:
        raise HTTPException(409, "This build has no source to refine. Retry the request first.")
    run.project_id = previous.project_id or previous.id
    run.source_run_id = previous.id
    run.request_id = payload.request_id
    run.logs.append(ActivityEvent(agent="user", action="iteration_requested", detail=payload.instruction.strip()))
    return _enqueue(run)


@app.post("/api/runs/{run_id}/cancel", response_model=RunState)
def cancel_run(run_id: str) -> RunState:
    _get_run_or_404(run_id)
    try:
        return store.cancel(run_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/runs/{run_id}/retry", response_model=RunResponse, status_code=202)
def retry_run(run_id: str, payload: CreateRunRequest) -> RunResponse:
    previous = _get_run_or_404(run_id)
    if previous.status not in {RunStatus.FAILED, RunStatus.CANCELLED}:
        raise HTTPException(409, "Only failed or cancelled builds can be retried.")
    run = orchestrator.initialize(previous.requirement)
    run.project_id = previous.project_id or previous.id
    run.source_run_id = previous.source_run_id
    run.request_id = payload.request_id
    run.logs.append(ActivityEvent(agent="user", action="retry_requested", detail=f"Retry of request #{previous.sequence}. Previous output is retained."))
    return _enqueue(run)
