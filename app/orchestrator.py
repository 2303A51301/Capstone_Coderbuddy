from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import Analysis, CorrectionAgent, GenerationAgent, PlanningAgent, RequirementsAgent
from app.llm import AzureFoundryClient, LLMError, OllamaClient, ProjectDraft
from app.models import ActivityEvent, CommandResult, RunState, RunStatus, StepStatus, utcnow
from app.safety import SafeWorkspace
from app.templates import Template
from app.tools import workspace_tools


class AgentGraphState(TypedDict, total=False):
    requirement: str
    run: RunState
    started_at: float
    use_llm: bool
    used_llm: bool
    fallback_used: bool
    template: Template
    draft: ProjectDraft
    validation: CommandResult
    validation_tool: str
    correction_error: str
    source_files: dict[str, str]


class Orchestrator:
    """LangGraph-controlled agent workflow using bounded LangChain tools."""

    MAX_LLM_RETRIES = 2

    def __init__(self, workspace_root: Path, provider: str | None = None, ollama_client: OllamaClient | None = None) -> None:
        self.safe_workspace = SafeWorkspace(workspace_root)
        self.requirements = RequirementsAgent()
        self.planner = PlanningAgent()
        self.generator = GenerationAgent()
        self.corrector = CorrectionAgent()
        self.provider = (provider or os.getenv("AI_PROVIDER", "demo")).strip().lower()
        self.ollama = ollama_client or OllamaClient()
        self.llm = AzureFoundryClient() if self.provider == "azure-foundry" else self.ollama
        self._progress: Callable[[RunState], object] | None = None
        self.workflow = self._build_graph()

    def _use_llm(self) -> bool:
        return self.provider in {"ollama", "azure-foundry"} and self.llm.model_available()

    @property
    def provider_name(self) -> str:
        return "Azure Foundry" if self.provider == "azure-foundry" else "Ollama"

    @property
    def model_name(self) -> str:
        return self.llm.config.model

    def status_label(self) -> str:
        if self.provider == "azure-foundry":
            return self.llm.status_label()
        if self.provider != "ollama":
            return "demo-fallback"
        if not self.ollama.is_reachable():
            return "ollama-offline"
        if not self.ollama.model_available():
            return f"ollama-model-missing:{self.ollama.config.model}"
        return f"ollama:{self.ollama.config.model}"

    def _log(self, state: RunState, agent: str, action: str, detail: str, tool: str | None = None, status: StepStatus = StepStatus.SUCCEEDED) -> None:
        state.logs.append(ActivityEvent(agent=agent, action=action, detail=detail, tool=tool, status=status))
        state.updated_at = utcnow()
        if self._progress:
            self._progress(state)

    @staticmethod
    def _mark(state: RunState, step_id: str, status: StepStatus) -> None:
        step = next((step for step in state.plan if step.id == step_id), None)
        if step:
            step.status = status

    @staticmethod
    def _elapsed(graph: AgentGraphState) -> float:
        return round(time.perf_counter() - graph["started_at"], 2)

    def _write_template(self, project: Path, template: Template, requirement: str) -> list[str]:
        self.safe_workspace.clear_project(project)
        writer, _ = workspace_tools(self.safe_workspace, project)
        generated: list[str] = []
        for path, content in template.files.items():
            written = writer.invoke({"path": path, "content": content})
            generated.append(str(written))
        writer.invoke({"path": "CODER_BUDDY_REQUEST.txt", "content": requirement.strip() + "\n"})
        generated.append("CODER_BUDDY_REQUEST.txt")
        return generated

    def _validate(self, project: Path, template: Template) -> tuple[CommandResult, str]:
        for name, content in template.files.items():
            if not name.endswith((".html", ".css", ".js", ".svg")):
                continue
            urls = re.findall(r"https?://[^\s\"'<>`\\)]+", content)
            remote = [url for url in urls if url not in {
                "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink",
            }]
            if remote:
                return CommandResult(
                    command=["internal", "preview-compatibility"], returncode=1, stdout="",
                    stderr=f"Preview compatibility failed in {name}: external URLs are blocked by the sandbox. Replace remote images, fonts or dependencies with inline SVG, CSS illustrations or data URLs. Do not use external services.",
                ), "validator.preview-compatibility"
        js_output = ""
        if "app.js" in template.files:
            js_result = self.safe_workspace.run_allowed(project, ["node", "--check", "app.js"])
            if js_result.returncode:
                return js_result, "node --check app.js"
            js_output = "JavaScript syntax check passed (node --check app.js).\n"
        test_files = [name for name in template.files if name.startswith("test_") and name.endswith(".py")]
        if test_files:
            _, tester = workspace_tools(self.safe_workspace, project)
            try:
                result = CommandResult.model_validate_json(tester.invoke({}))
            except PermissionError as exc:
                result = CommandResult(command=["internal", "execution-guard"], returncode=1, stdout="", stderr=str(exc))
            result.stdout = js_output + result.stdout
            return result, "langchain.run_generated_tests → python -m pytest -q"
        html_path = project / "index.html"
        if html_path.exists():
            document = html_path.read_text(encoding="utf-8")
            checks = {
                "complete HTML document": bool(re.search(r"<html\b.*</html\s*>", document, re.I | re.S)),
                "local stylesheet": "styles.css" in document,
                "local interaction script": "app.js" in document,
            }
            failed = [name for name, passed in checks.items() if not passed]
            output = "Static app checks passed: " + ", ".join(checks) if not failed else "Static app checks failed: " + ", ".join(failed)
            return CommandResult(command=["internal", "html-check"], returncode=0 if not failed else 1, stdout=js_output + output if not failed else js_output, stderr="" if not failed else output), "validator.html"
        return CommandResult(command=["internal", "no-check"], returncode=1, stdout="", stderr="No runnable tests or index.html found."), "validator.none"

    def _build_graph(self):
        builder = StateGraph(AgentGraphState)
        builder.add_node("analyze", self._node_analyze)
        builder.add_node("plan", self._node_plan)
        builder.add_node("generate", self._node_generate)
        builder.add_node("write", self._node_write)
        builder.add_node("validate", self._node_validate)
        builder.add_node("correct", self._node_correct)
        builder.add_node("fallback", self._node_fallback)
        builder.add_node("finish", self._node_finish)
        builder.add_node("fail", self._node_fail)
        builder.add_edge(START, "analyze")
        builder.add_edge("analyze", "plan")
        builder.add_edge("plan", "generate")
        builder.add_edge("generate", "write")
        builder.add_edge("write", "validate")
        builder.add_conditional_edges("validate", self._route_validation, {"finish": "finish", "correct": "correct", "fallback": "fallback", "fail": "fail"})
        builder.add_conditional_edges("correct", self._route_correction, {"write": "write", "fallback": "fallback", "fail": "fail"})
        builder.add_conditional_edges("fallback", self._route_fallback, {"finish": "finish", "fail": "fail"})
        builder.add_edge("finish", END)
        builder.add_edge("fail", END)
        return builder.compile()

    def _node_analyze(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        state.status = RunStatus.RUNNING
        state.phase = "planning"
        self._log(state, "orchestrator", "state_transition", "queued ? requirement analysis")
        use_llm = self._use_llm()
        state.provider_name = self.provider_name if use_llm else None
        state.model_name = self.model_name if use_llm else None
        self._mark(state, "analyze", StepStatus.RUNNING)
        if use_llm:
            self._log(state, "requirements", "llm_analysis_started", f"Analyzing the full request with {self.provider_name} model {self.model_name}.", f"{self.provider}.generate")
            try:
                if graph.get("source_files"):
                    draft = self.llm.refine_project(graph["requirement"], graph["source_files"])
                else:
                    draft = self.llm.generate_project(graph["requirement"])
            except LLMError as exc:
                if graph.get("source_files"):
                    raise LLMError(f"Refinement failed; the original build is unchanged. {exc}") from exc
                self._log(state, "generator", "llm_generation_error", f"{self.provider_name} could not produce a valid project ({exc}). Switching to the explicit offline starter.", status=StepStatus.FAILED)
                state.mode = "deterministic-fallback"
                use_llm = False
            else:
                state.project_type = draft.project_type
                state.analysis_summary = draft.analysis
                state.features = draft.features
                state.model_name = self.model_name
                self._mark(state, "analyze", StepStatus.SUCCEEDED)
                self._log(state, "requirements", "analysis_ready", draft.analysis, f"{self.provider}.generate")
                for feature in draft.features:
                    self._log(state, "requirements", "feature_identified", feature)
                return {"use_llm": True, "draft": draft, "template": self.generator.from_draft(draft)}
        if self.provider in {"ollama", "azure-foundry"} and not use_llm:
            state.mode = "deterministic-fallback"
            self._log(state, "requirements", "provider_unavailable", f"{self.provider_name} is not ready ({self.status_label()}). Using the disclosed offline starter.", status=StepStatus.FAILED)
        if graph.get("source_files"):
            raise LLMError("Refinement requires a ready AI provider to preserve the existing source. The original build is unchanged.")
        analysis = self.requirements.analyze(graph["requirement"])
        state.project_type = analysis.project_type
        state.analysis_summary = analysis.rationale
        state.features = analysis.features
        state.model_name = None
        state.provider_name = None
        self._mark(state, "analyze", StepStatus.SUCCEEDED)
        self._log(state, "requirements", "offline_analysis", analysis.rationale, "local.rules")
        return {"use_llm": False, "template": self.generator.generate(graph["requirement"])}

    def _node_plan(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        if graph.get("use_llm"):
            draft = graph["draft"]
            analysis = Analysis(draft.project_type, draft.analysis, draft.features, draft.plan)
            state.plan = self.planner.plan(analysis)
            for task in draft.plan:
                self._log(state, "planner", "planned_task", task)
        else:
            analysis = Analysis(state.project_type or "starter-app", state.analysis_summary, state.features, [])
            state.plan = self.planner.plan(analysis)
        self._mark(state, "analyze", StepStatus.SUCCEEDED)
        self._mark(state, "design", StepStatus.RUNNING)
        self._log(state, "planner", "plan_started", "Creating ordered implementation tasks from the interpreted request.", "langgraph.plan")
        self._mark(state, "design", StepStatus.SUCCEEDED)
        self._log(state, "planner", "plan_ready", "Implementation plan is ready; generated files will be validated before delivery.")
        return {}

    def _node_generate(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        state.phase = "building"
        self._mark(state, "generate", StepStatus.RUNNING)
        template = graph["template"]
        if graph.get("use_llm"):
            state.mode = "llm"
            self._log(state, "generator", "llm_generation", f"Prepared {len(template.files)} application files from the custom requirement.", f"{self.provider}.generate")
            return {"used_llm": True, "template": template}
        state.project_type = template.name
        state.mode = "deterministic" if state.mode != "deterministic-fallback" else state.mode
        self._log(state, "generator", "offline_generation", f"Selected the local {template.name} starter. This fallback has a narrower feature set than LLM mode.", "local.template")
        return {"used_llm": False, "template": template}

    def _node_write(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        project = self.safe_workspace.project_path(state.id)
        state.workspace = str(project)
        generated = self._write_template(project, graph["template"], graph["requirement"])
        state.generated_files = generated
        self._mark(state, "generate", StepStatus.SUCCEEDED)
        self._log(state, "tool", "files_written", f"Wrote {len(generated)} files inside the isolated run workspace.", "langchain.write_project_file")
        return {}

    def _node_validate(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        state.phase = "testing"
        self._mark(state, "validate", StepStatus.RUNNING)
        self._log(state, "tester", "validation_started", "Executing the generated project's validation checks.")
        project = self.safe_workspace.project_path(state.id)
        result, tool_name = self._validate(project, graph["template"])
        state.validation_output = (result.stdout + result.stderr).strip()
        state.duration_seconds = self._elapsed(graph)
        if result.returncode == 0:
            self._mark(state, "validate", StepStatus.SUCCEEDED)
            self._log(state, "tester", "validation_passed", state.validation_output or "Validation passed.", tool_name)
        else:
            self._mark(state, "validate", StepStatus.FAILED)
            self._log(state, "tester", "validation_failed", state.validation_output or "Validation failed.", tool_name, StepStatus.FAILED)
            self._mark(state, "correct", StepStatus.RUNNING)
        return {"validation": result, "validation_tool": tool_name}

    def _route_validation(self, graph: AgentGraphState) -> str:
        if graph["validation"].returncode == 0:
            return "finish"
        if graph.get("used_llm") and not graph.get("fallback_used"):
            if graph["run"].retries < self.MAX_LLM_RETRIES:
                return "correct"
            return "fail" if graph.get("source_files") else "fallback"
        return "fail"

    def _node_correct(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        state.phase = "repairing"
        state.retries += 1
        self._log(state, "corrector", "repair_started", f"Repair attempt {state.retries} based on observed failures.")
        current = graph["template"]
        try:
            draft = self.corrector.correction_llm(graph["requirement"], current.files, state.validation_output, self.llm)
        except LLMError as exc:
            self._log(state, "corrector", "correction_error", f"Attempt {state.retries} could not produce a valid correction: {exc}", f"{self.provider}.correct", StepStatus.FAILED)
            return {"correction_error": str(exc)}
        state.project_type = draft.project_type
        state.analysis_summary = draft.analysis
        if draft.features:
            state.features = draft.features
        state.mode = "llm"
        self._log(state, "corrector", "correction_generated", f"Attempt {state.retries}: regenerated the complete app in response to real test failures.", f"{self.provider}.correct")
        return {"template": self.generator.from_draft(draft), "draft": draft}

    def _route_correction(self, graph: AgentGraphState) -> str:
        if graph.get("source_files") and graph.get("correction_error"):
            return "fail"
        return "fallback" if graph.get("correction_error") else "write"

    def _node_fallback(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        state.mode = "llm-then-deterministic-fallback"
        state.analysis_summary += " | Model could not self-correct; trying an offline starter as a fallback."
        self._log(state, "orchestrator", "fallback_started", f"The model did not pass validation within {self.MAX_LLM_RETRIES} attempts. Trying a deterministic starter; this may not satisfy every custom feature.", "local.template", StepStatus.FAILED)
        template = self.generator.generate(graph["requirement"])
        project = self.safe_workspace.project_path(state.id)
        state.project_type = template.name
        state.generated_files = self._write_template(project, template, graph["requirement"])
        self._log(state, "tool", "fallback_files_written", f"Wrote offline {template.name} starter; verify its scope against the original request.", "langchain.write_project_file")
        result, tool_name = self._validate(project, template)
        state.validation_output = (result.stdout + result.stderr).strip()
        state.workspace = str(project)
        state.duration_seconds = self._elapsed(graph)
        if result.returncode == 0:
            self._mark(state, "validate", StepStatus.SUCCEEDED)
            self._log(state, "tester", "fallback_validated", state.validation_output, tool_name)
        else:
            self._mark(state, "validate", StepStatus.FAILED)
            state.error = "The offline fallback also failed validation. Review the activity log and test output."
            self._log(state, "tester", "fallback_validation_failed", state.error, tool_name, StepStatus.FAILED)
        return {"validation": result, "validation_tool": tool_name, "fallback_used": True}

    def _route_fallback(self, graph: AgentGraphState) -> str:
        return "finish" if graph["validation"].returncode == 0 else "fail"

    def _node_finish(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        self._mark(state, "correct", StepStatus.SUCCEEDED)
        state.status = RunStatus.COMPLETED
        state.phase = "ready"
        state.error = None
        state.duration_seconds = self._elapsed(graph)
        self._log(state, "orchestrator", "delivery_ready", f"Validated project ready for preview and download ({state.duration_seconds:.1f}s).")
        return {}

    def _node_fail(self, graph: AgentGraphState) -> dict:
        state = graph["run"]
        self._mark(state, "correct", StepStatus.FAILED)
        state.status = RunStatus.FAILED
        state.phase = "failed"
        if not state.error:
            state.error = f"Validation did not pass after {state.retries} correction attempt(s). The generated source and failure output are retained for review."
        state.duration_seconds = self._elapsed(graph)
        self._log(state, "orchestrator", "run_failed", state.error, status=StepStatus.FAILED)
        return {}

    def execute(
        self, requirement: str, existing: RunState | None = None,
        progress: Callable[[RunState], object] | None = None,
        source_files: dict[str, str] | None = None,
    ) -> RunState:
        self._progress = progress
        run = existing or self.initialize(requirement)
        run.requirement = requirement
        run.status = RunStatus.RUNNING
        try:
            result = self.workflow.invoke({
                "requirement": requirement, "run": run, "started_at": time.perf_counter(),
                "source_files": source_files or {},
            })
            return result["run"]
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.phase = "failed"
            run.error = f"Agent workflow stopped unexpectedly: {type(exc).__name__}: {exc}"
            self._log(run, "orchestrator", "workflow_exception", run.error, status=StepStatus.FAILED)
            return run
        finally:
            self._progress = None

    def initialize(self, requirement: str) -> RunState:
        analysis = self.requirements.analyze(requirement)
        run = RunState(requirement=requirement, project_type=analysis.project_type, analysis_summary="Waiting for model analysis." if self.provider in {"ollama", "azure-foundry"} else analysis.rationale, features=analysis.features)
        run.plan = self.planner.plan(analysis)
        return run
