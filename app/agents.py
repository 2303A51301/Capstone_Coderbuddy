from __future__ import annotations

from dataclasses import dataclass

from app.llm import ProjectDraft
from app.models import PlanStep
from app.templates import Template, select_template


@dataclass(frozen=True)
class Analysis:
    project_type: str
    rationale: str
    features: list[str]
    plan: list[str]


class RequirementsAgent:
    name = "requirements"

    def analyze(self, requirement: str) -> Analysis:
        template = select_template(requirement)
        descriptions = {
            "todo-app": "The request describes an interactive task tracker.",
            "calculator-app": "The request describes a calculator with arithmetic behavior.",
            "ecommerce-store": "The request describes an online clothing storefront with a product catalog and shopping bag.",
            "landing-page": "The request describes a web experience; the offline fallback uses a clear starter page.",
        }
        plans = {
            "ecommerce-store": [
                "Create the apparel catalog and responsive storefront",
                "Implement product search, filters, sizes, and the shopping bag",
                "Run catalog, cart, and subtotal behavior tests",
                "Package Docker/Nginx deployment files and a production checklist",
            ],
        }
        return Analysis(
            project_type=template.name,
            rationale=descriptions.get(template.name, "The request was classified for the deterministic offline starter."),
            features=(
                ["Responsive storefront", "Product search and collection filters", "Size-aware cart and checkout demo", "Container-ready static deployment bundle"]
                if template.name == "ecommerce-store"
                else ["Responsive browser interface", "Validated core behavior"]
            ),
            plan=plans.get(template.name, ["Implement the requested interaction", "Add accessible responsive styling", "Run behavioral tests", "Package the generated project"]),
        )

    def from_draft(self, draft: ProjectDraft) -> Analysis:
        return Analysis(draft.project_type, draft.analysis, draft.features, draft.plan)


class PlanningAgent:
    name = "planner"

    def plan(self, analysis: Analysis) -> list[PlanStep]:
        default_tasks = [
            "Translate the requirement into core user flows",
            "Implement the browser interface and business logic",
            "Run behavior-focused tests and correct defects",
            "Package the app for preview and download",
        ]
        tasks = [*analysis.plan, *default_tasks][:3]
        final_step = (
            "Package the tested storefront with Docker/Nginx deployment files; real orders require payment and backend setup."
            if analysis.project_type == "ecommerce-store"
            else "Execute tests, correct failures, and prepare the verified output."
        )
        descriptions = [analysis.rationale, *tasks[:3], final_step]
        agents = ["requirements", "planner", "generator", "tester", "corrector"]
        titles = ["Analyze requirement", "Plan user flows", "Generate application", "Run behavioral tests", "Correct & deliver"]
        return [
            PlanStep(id=step_id, title=title, description=descriptions[index], agent=agents[index])
            for index, (step_id, title) in enumerate(zip(("analyze", "design", "generate", "validate", "correct"), titles))
        ]


class GenerationAgent:
    name = "generator"

    def generate(self, requirement: str) -> Template:
        return select_template(requirement)

    @staticmethod
    def from_draft(draft: ProjectDraft) -> Template:
        return Template(name=draft.project_type, files=draft.files)


class CorrectionAgent:
    name = "corrector"

    def correction_llm(self, requirement: str, files: dict[str, str], failure_output: str, client) -> ProjectDraft:
        return client.correct_project(requirement, files, failure_output)
