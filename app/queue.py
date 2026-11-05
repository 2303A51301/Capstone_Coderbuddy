from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Event, Thread

from app.models import ActivityEvent, RunStatus, StepStatus, utcnow
from app.orchestrator import Orchestrator
from app.store import RunStore

logger = logging.getLogger(__name__)


class BuildQueue:
    """One bounded worker, protected against concurrent server processes."""

    def __init__(self, store: RunStore, orchestrator: Orchestrator) -> None:
        self.store = store
        self.orchestrator = orchestrator
        self._stop = Event()
        self._wake = Event()
        self._thread: Thread | None = None
        self._lock_file = None
        self.error: str | None = None

    def start(self) -> None:
        self._lock_file = open(self.store.path.with_suffix(".worker.lock"), "a+b")
        self._lock_file.seek(0)
        if os.name == "nt":
            import msvcrt
            self._lock_file.write(b"0")
            self._lock_file.flush()
            self._lock_file.seek(0)
            try:
                msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                self._lock_file.close()
                raise RuntimeError("Another CoderBuddy worker owns this database. Run one server worker.") from None
        else:
            import fcntl
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self._lock_file.close()
                raise RuntimeError("Another CoderBuddy worker owns this database. Run one server worker.") from None
        self.store.recover_interrupted()
        self.store.import_workspaces(self.orchestrator.safe_workspace.root)
        self._stop.clear()
        self._thread = Thread(target=self._loop, name="coderbuddy-build-queue", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            # Finish the bounded active build before releasing the process lock.
            self._thread.join()
        if self._lock_file:
            self._lock_file.close()

    def notify(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        try:
            while not self._stop.is_set():
                if not self.process_one():
                    self._wake.wait(0.5)
                    self._wake.clear()
        except Exception:
            self.error = "Build worker stopped because persistence failed. Restart the server; saved queued work is retained."
            logger.exception("Build worker stopped")

    def process_one(self) -> bool:
        run = self.store.claim_next()
        if not run:
            return False
        try:
            source_files = None
            if run.source_run_id:
                source = self.store.get(run.source_run_id)
                if not source or not source.workspace or not source.generated_files:
                    raise ValueError("The source build has no files to refine. Retry the original request instead.")
                project = self.orchestrator.safe_workspace.project_path(source.id)
                source_files = {}
                for name in source.generated_files:
                    if name == "CODER_BUDDY_REQUEST.txt":
                        continue
                    path = self.orchestrator.safe_workspace._contained(project, project / name)
                    if path.is_file():
                        source_files[name] = path.read_text(encoding="utf-8")
            result = self.orchestrator.execute(
                run.requirement, run, progress=self.store.save, source_files=source_files,
            )
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.phase = "failed"
            run.error = f"Build stopped: {type(exc).__name__}: {exc}"
            run.updated_at = utcnow()
            run.logs.append(ActivityEvent(agent="queue", action="build_failed", detail=run.error, status=StepStatus.FAILED))
            result = run
        self.store.save(result)
        return True
