from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.models import CommandResult


class SafeWorkspace:
    """Confinement for generated files and a tiny, explicit command allowlist."""

    ALLOWED_COMMANDS = {
        "python": {("-m", "py_compile"), ("-m", "pytest")},
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def project_path(self, run_id: str) -> Path:
        if not run_id.isalnum():
            raise ValueError("Invalid run identifier")
        path = (self.root / run_id).resolve()
        if self.root not in path.parents:
            raise ValueError("Path escaped workspace")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def clear_project(self, project: Path) -> None:
        """Remove all existing files/directories inside a project workspace so a
        fresh generation attempt never mixes with stale files from a prior
        (possibly failed) attempt, e.g. leftover test files that would otherwise
        be picked up by pytest alongside the new generation."""
        project = self._contained(self.root, project)
        for entry in project.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink(missing_ok=True)


    @staticmethod
    def _contained(base: Path, candidate: Path) -> Path:
        resolved = candidate.resolve()
        if resolved != base and base not in resolved.parents:
            raise ValueError("File path escaped workspace")
        return resolved

    def write_text(self, project: Path, relative_path: str, content: str) -> Path:
        target = self._contained(project, project / relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    @staticmethod
    def _check_generated_python(project: Path) -> None:
        blocked_modules = {"os", "sys", "subprocess", "socket", "ctypes", "shutil", "pathlib", "tempfile", "importlib", "urllib", "http", "requests", "httpx", "multiprocessing", "threading", "pickle", "shelve", "sqlite3", "builtins"}
        blocked_calls = {"open", "eval", "exec", "compile", "__import__", "breakpoint", "__builtins__", "exit", "quit"}
        for path in project.glob("*.py"):
            if path.name not in {"app_logic.py", "test_app.py"}:
                raise PermissionError(f"Generated Python file is not permitted: {path.name}")
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            except (SyntaxError, UnicodeDecodeError) as exc:
                raise PermissionError(f"Generated Python source is invalid: {path.name}: {exc}") from exc
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".", 1)[0] for alias in node.names]
                    if blocked_modules.intersection(names):
                        raise PermissionError(f"Generated Python imports a restricted module in {path.name}")
                elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".", 1)[0] in blocked_modules:
                    raise PermissionError(f"Generated Python imports a restricted module in {path.name}")
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in blocked_calls:
                    raise PermissionError(f"Generated Python uses a restricted operation in {path.name}")
                elif isinstance(node, ast.Name) and node.id in blocked_calls:
                    raise PermissionError(f"Generated Python references a restricted operation in {path.name}")

    def run_python_check(self, project: Path) -> CommandResult:
        files = sorted(str(path.relative_to(project)) for path in project.rglob("*.py"))
        return self.run_allowed(project, ["python", "-m", "py_compile", *files])

    def run_allowed(self, project: Path, command: list[str]) -> CommandResult:
        if command == ["node", "--check", "app.js"]:
            pass
        elif command == ["python", "-m", "pytest", "-q"]:
            pass
        elif len(command) >= 4 and command[:3] == ["python", "-m", "py_compile"]:
            files = command[3:]
            if not files or any(Path(name).is_absolute() or ".." in Path(name).parts or not name.endswith(".py") for name in files):
                raise PermissionError("Only project-relative Python files may be syntax-checked")
        else:
            raise PermissionError("Command is not in the validation allowlist")
        project = self._contained(self.root, project)
        if command[2] == "pytest":
            self._check_generated_python(project)
        executable = shutil.which("node") if command[0] == "node" else sys.executable
        if not executable:
            return CommandResult(command=command, returncode=127, stdout="", stderr="Node.js is required for JavaScript syntax validation. Install it and retry.")
        safe_command = [executable, *command[1:]]
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
        # Windows' standard library requires these OS locations to initialize
        # its async event loop; neither value originates from user input.
        for key in ("SystemRoot", "WINDIR"):
            if os.environ.get(key):
                safe_env[key] = os.environ[key]
        try:
            completed = subprocess.run(
                safe_command,
                cwd=project,
                env=safe_env,
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return CommandResult(command=command, returncode=124, stdout=stdout[-8000:], stderr=(stderr + "\nValidation timed out after 30 seconds.")[-8000:])
        return CommandResult(command=command, returncode=completed.returncode, stdout=completed.stdout[-8000:], stderr=completed.stderr[-8000:])
