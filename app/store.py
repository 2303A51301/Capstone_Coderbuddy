from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.models import ActivityEvent, RunState, RunStatus, StepStatus, utcnow


class RunStore:
    """SQLite snapshots plus atomic FIFO claiming; files live in per-build folders."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    request_id TEXT UNIQUE,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _decode(row: sqlite3.Row) -> RunState:
        run = RunState.model_validate_json(row["payload"])
        run.sequence = row["sequence"]
        run.status = RunStatus(row["status"])
        return run

    def enqueue(self, run: RunState) -> RunState:
        run.project_id = run.project_id or run.id
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if run.request_id:
                row = db.execute("SELECT * FROM runs WHERE request_id=?", (run.request_id,)).fetchone()
                if row:
                    prior = self._decode(row)
                    if prior.requirement != run.requirement or prior.source_run_id != run.source_run_id:
                        raise ValueError("This request token was already used for a different request")
                    return prior
            db.execute(
                "INSERT INTO runs(id,request_id,project_id,status,payload) VALUES(?,?,?,?,?)",
                (run.id, run.request_id, run.project_id, run.status.value, run.model_dump_json()),
            )
            run.sequence = db.execute("SELECT sequence FROM runs WHERE id=?", (run.id,)).fetchone()[0]
        return run

    def save(self, run: RunState) -> RunState:
        with self._connect() as db:
            changed = db.execute(
                "UPDATE runs SET status=?,payload=? WHERE id=?",
                (run.status.value, run.model_dump_json(), run.id),
            ).rowcount
        if not changed:
            return self.enqueue(run)
        return run

    def get(self, run_id: str) -> RunState | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return self._decode(row) if row else None

    def list(self) -> list[RunState]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM runs ORDER BY sequence DESC").fetchall()
        return [self._decode(row) for row in rows]

    def claim_next(self) -> RunState | None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM runs WHERE status='running' LIMIT 1").fetchone():
                return None
            row = db.execute("SELECT * FROM runs WHERE status='queued' ORDER BY sequence LIMIT 1").fetchone()
            if not row:
                return None
            run = self._decode(row)
            run.status = RunStatus.RUNNING
            run.phase = "planning"
            run.updated_at = utcnow()
            run.logs.append(ActivityEvent(agent="queue", action="build_started", detail=f"Started request #{run.sequence}."))
            db.execute("UPDATE runs SET status=?,payload=? WHERE id=?",
                       (run.status.value, run.model_dump_json(), run.id))
        return run

    def cancel(self, run_id: str) -> RunState:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            run = self._decode(row)
            if run.status != RunStatus.QUEUED:
                raise ValueError("Only waiting requests can be cancelled. Active builds finish within bounded timeouts.")
            run.status = RunStatus.CANCELLED
            run.phase = "cancelled"
            run.updated_at = utcnow()
            run.logs.append(ActivityEvent(agent="queue", action="cancelled", detail="Waiting request cancelled by the user."))
            db.execute("UPDATE runs SET status=?,payload=? WHERE id=?",
                       (run.status.value, run.model_dump_json(), run.id))
        return run

    def recover_interrupted(self) -> None:
        for run in self.list():
            if run.status == RunStatus.RUNNING:
                run.status = RunStatus.FAILED
                run.phase = "interrupted"
                run.error = "Server stopped during this build. Saved files and events were retained. Retry to create a new build."
                run.updated_at = utcnow()
                run.logs.append(ActivityEvent(agent="queue", action="interrupted", detail=run.error, status=StepStatus.FAILED))
                self.save(run)

    def import_workspaces(self, root: Path) -> None:
        """Recover pre-database output without inventing validation results."""
        for project in sorted(root.iterdir()):
            if not project.is_dir() or not project.name.isalnum() or self.get(project.name):
                continue
            request = project / "CODER_BUDDY_REQUEST.txt"
            if not request.is_file():
                continue
            files = sorted(
                str(path.relative_to(project)).replace("\\", "/")
                for path in project.rglob("*")
                if path.is_file() and not any(part.startswith(".") or part == "__pycache__"
                                              for part in path.relative_to(project).parts)
            )
            run = RunState(
                id=project.name, project_id=project.name,
                requirement=request.read_text(encoding="utf-8").strip(),
                workspace=str(project.resolve()), generated_files=files,
                status=RunStatus.FAILED, phase="recovered", mode="recovered",
                analysis_summary="Recovered an existing project from this machine.",
                error="Source recovered. Historical validation was not persisted by the older version; preview/export are available. Retry to validate a new build.",
            )
            run.logs.append(ActivityEvent(agent="storage", action="source_recovered", detail=run.error))
            self.enqueue(run)
