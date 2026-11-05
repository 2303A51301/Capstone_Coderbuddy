from pathlib import Path

import pytest

from app.safety import SafeWorkspace


def test_rejects_escaping_file_path(tmp_path: Path):
    safe = SafeWorkspace(tmp_path / "work")
    project = safe.project_path("abc123")
    with pytest.raises(ValueError):
        safe.write_text(project, "../outside.txt", "no")


def test_rejects_unapproved_command(tmp_path: Path):
    safe = SafeWorkspace(tmp_path / "work")
    project = safe.project_path("abc123")
    with pytest.raises(PermissionError):
        safe.run_allowed(project, ["python", "-c", "print('no')"])


def test_clear_project_removes_stale_files(tmp_path: Path):
    safe = SafeWorkspace(tmp_path / "work")
    project = safe.project_path("abc123")
    safe.write_text(project, "stale_test.py", "def test_old(): assert False")
    safe.write_text(project, "nested/inner.txt", "leftover")
    safe.clear_project(project)
    assert list(project.iterdir()) == []

from pathlib import Path

import pytest

from app.safety import SafeWorkspace


def test_generated_python_cannot_import_host_filesystem_or_process_modules(tmp_path: Path):
    safe = SafeWorkspace(tmp_path / "work")
    project = safe.project_path("abc123")
    safe.write_text(project, "app_logic.py", "import os\ndef add(a, b): return a + b")
    with pytest.raises(PermissionError, match="restricted module"):
        safe.run_allowed(project, ["python", "-m", "pytest", "-q"])


def test_generated_process_never_inherits_provider_credentials(tmp_path, monkeypatch):
    import subprocess

    safe = SafeWorkspace(tmp_path / "work")
    project = safe.project_path("abc123")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret-for-environment-test")
    monkeypatch.setenv("GROQ_API_KEY", "another-test-secret")
    seen = []

    def run(command, **kwargs):
        seen.append(kwargs["env"])
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    safe.run_allowed(project, ["python", "-m", "pytest", "-q"])
    assert "AZURE_OPENAI_API_KEY" not in seen[0]
    assert "GROQ_API_KEY" not in seen[0]
