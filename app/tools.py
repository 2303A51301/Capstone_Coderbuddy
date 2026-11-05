from __future__ import annotations

import json
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.safety import SafeWorkspace


class WriteFileArgs(BaseModel):
    path: str = Field(description="Relative output file path")
    content: str = Field(description="UTF-8 text file contents")


class NoArgs(BaseModel):
    pass


def workspace_tools(safe_workspace: SafeWorkspace, project: Path) -> tuple[StructuredTool, StructuredTool]:
    """Create bounded LangChain tools bound to one validated run workspace."""

    def write_file(path: str, content: str) -> str:
        written = safe_workspace.write_text(project, path, content)
        return str(written.relative_to(project))

    def run_project_tests() -> str:
        result = safe_workspace.run_allowed(project, ["python", "-m", "pytest", "-q"])
        return json.dumps(result.model_dump())

    writer = StructuredTool.from_function(
        func=write_file,
        name="write_project_file",
        description="Safely write a generated text file inside the current isolated run directory.",
        args_schema=WriteFileArgs,
    )
    tester = StructuredTool.from_function(
        func=run_project_tests,
        name="run_generated_tests",
        description="Execute the fixed pytest validation command in the current isolated run directory.",
        args_schema=NoArgs,
    )
    return writer, tester
