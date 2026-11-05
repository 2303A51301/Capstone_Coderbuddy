# Coder Buddy — Final Project Report

## Abstract

Coder Buddy is a local-first agentic software-engineering prototype. It accepts a natural-language web-application request, interprets the requested product, prepares an ordered plan, creates a small web project, runs behavioral tests on its business logic, and uses test diagnostics for bounded correction. It provides a dashboard for progress and activity, an isolated preview, source-file inspection, project ZIP download, and natural-language iteration.

## Problem and motivation

AI code generation alone does not close the software-development loop. Users still need to plan work, integrate files, execute the application, detect defects, and refine results. Coder Buddy focuses on making those steps visible and repeatable for a local capstone demonstration.

## Objectives

- Accept plain-language application requirements.
- Expose requirement interpretation and a structured development plan.
- Generate a runnable browser application and testable business logic.
- Execute behavior tests, inspect failures, and retry corrections within a limit.
- Preview and export generated files, then accept natural-language modifications.
- Keep model calls and project files local by default.

## System architecture

The browser UI is served by FastAPI. API requests are saved transactionally in a SQLite FIFO queue; a process-locked single worker executes them in submission order and saves progress snapshots for polling. A LangGraph `StateGraph` contains nodes for analysis, planning, generation, file writing, validation, correction, fallback, and final status. Azure Foundry's configured `gpt-4.1-mini` deployment is the current provider; Ollama/Qwen remains available. LangChain Core `StructuredTool`s expose a per-build file writer and fixed test action. Generated artifacts are written beneath `workspace/<build-id>`.

The local LLM is asked to return a structured draft containing project type, an interpretation summary, features, plan steps, HTML, CSS, JavaScript, Python business logic, pytest tests, and a README. Output paths, file count, text sizes, and required files are checked before writing. Tests run with `python -m pytest -q`, `shell=False`, a 30-second timeout, minimal environment, and basic static restrictions on generated Python. Static assets are allow-listed, and the browser preview is sandboxed with network access disabled.

## Main workflow

1. **Requirement intake:** validate and trim the user's request.
2. **Analysis and planning:** use the configured local model where available; display the interpreted requirements and ordered tasks.
3. **Generation:** create a complete small web-app bundle inside a unique run workspace.
4. **Tool execution:** write files through a confined LangChain tool.
5. **Testing:** execute the generated pytest behavior tests.
6. **Correction:** provide failing test output to the model for up to two complete correction attempts, then rerun the tests.
7. **Fallback and delivery:** if the model cannot produce a passing app, a deterministic starter can be delivered only with a visible fallback label; otherwise the run remains failed with source and diagnostics available.
8. **Iteration:** send the selected version's actual source with the follow-up change, create a separate build, and repeat verification without overwriting prior output.

## Durable queue and project history

Every request gets an atomic sequence number and separate workspace. New builds,
refinements, and retries share a project identity where appropriate but not a
write directory. Only waiting requests can be cancelled; active builds use bounded
timeouts. Queued work survives restarts. Interrupted active builds retain saved
events/source and become failed with an explicit retry action. Requests with the
same idempotency token return the original build. Database failure stops the
worker with a visible error instead of silently consuming work.

The studio includes searchable project history, a build-version selector,
queue positions/statuses, source highlighting, validation/activity navigation,
expanded preview, and a compact composer while a project is active. Browser
local storage remembers only the selected build and submission token; source and
history live in server-side SQLite and workspace folders. Older source-only
folders are recovered with validation explicitly unknown.

## User interface

The studio includes a prompt composer with examples, actual provider status, live queue progress, interpreted features, a five-stage plan, side-by-side source and preview, test output, persistent history, ZIP download, and a refinement form. The layout adapts to narrow screens and includes focus states and accessible labels. The preview is isolated from the parent studio; generated files are not directly served from arbitrary filesystem paths.

## Technology choices

| Layer | Technology |
|---|---|
| UI | HTML, CSS, JavaScript |
| API | FastAPI, Pydantic |
| Workflow orchestration | LangGraph |
| Bounded tool layer | LangChain Core StructuredTools |
| Local model interface | Ollama HTTP API |
| Current model | Qwen2.5-Coder 3B (configurable) |
| Cloud model | Azure Foundry Responses API / gpt-4.1-mini (configurable) |
| Persistence | SQLite snapshots and FIFO single-worker queue |
| Validation | pytest and targeted API/safety tests |

The supplied concept PDF discusses GPT-OSS + Groq. This implementation keeps the existing local Qwen model configuration per the team's request; no cloud API key is required. A Groq/GPT-OSS adapter is not claimed as implemented.

## Safety considerations and limitations

This is a local educational demo, not a production code-execution service. The validation process starts Python tests with the current user's process permissions; AST restrictions are defense-in-depth only and cannot prove generated code safe. Do not expose the app publicly or use it for untrusted prompts. Strong production isolation would require a separately constrained OS account or container/VM and additional resource/network restrictions.

Models may fail to produce a correct app. Two repair attempts bound model work,
but do not guarantee arbitrary requirements. An offline starter may not fulfill
a custom request and is disclosed. Refinement requires a ready provider and does
not replace an existing project with a fallback. Current generation targets static
browser apps and Python business logic; it does not provision databases, publish
to hosting, or launch arbitrary backend processes. JavaScript syntax checks and
Python tests do not prove every browser feature works. There is no multi-user
authentication, OS-level isolation, or active-build cancellation.

## Validation

The release automated suite reports **55 passed, 1 skipped** (optional live
Ollama integration); JavaScript syntax and Windows launcher parsing also pass.
Run the suite again for the current result. It covers provider contracts,
queue ordering, atomic claiming, cancellation, restart recovery, process locking,
idempotency, actual generated tests, versioned refinement, preview/export and
path/command restrictions. The optional Ollama integration case is skipped when
that service is unavailable:

```powershell
.\.venv\Scripts\python.exe -m pytest -v -s tests\test_llm_integration.py
```

The test suite covers health status, generation, validation, iteration, path confinement, command allowlisting, workspace cleanup, preview, and download. A complete final rehearsal should also verify the user's local Ollama/model and perform a live browser build, correction, iteration, and ZIP download.

### Release rehearsal evidence

- Two live Azure builds (jewellery and quiz) completed in FIFO order. Persisted
  timestamps confirm the second started after the first finished.
- A third waiting request was cancelled without running. Completed and cancelled
  records, events and outputs survived an actual server restart.
- The jewellery refinement initially hit provider output limits; those failed
  requests remain recorded. Incremental changed-file/exact-edit refinement was
  implemented to avoid requiring every unchanged file as model output.
- The final source-aware jewellery build completed after one observed JavaScript
  syntax failure, model repair and recheck: **six Python tests passed**, and Node's
  syntax check passed. All six local SVG images loaded; browser search, product
  details, cart addition and quantity/subtotal changes worked. The original source
  was retained and ZIP contents matched the new source bytes.
- The generated quiz passed **five Python tests**. Browser checks exercised
  unanswered validation, a three-out-of-three score and restart.
- Studio checks covered file selection and syntax highlighting, expanded/restored
  preview, project search/version selection, selected-build restoration on reload,
  desktop layout and a 390px mobile layout without page-level horizontal overflow.
- A credential-value comparison found no configured key in source/generated
  text, documentation or saved run metadata. Generated subprocess environments
  exclude provider credentials.

These are observed release checks, not a guarantee of arbitrary generated apps
or production readiness. Historical source-only imports remain explicitly
unvalidated; earlier versions are not retroactively labelled as passing new checks.

## How to run

Use `start-coder-buddy.bat` or follow the Windows instructions in the repository `README.md`. The local dashboard opens at `http://127.0.0.1:8010` (or the next free port selected by the launcher). API docs are available at `/docs`.

## Future work

- Better plan/execution separation and structured acceptance criteria.
- Broader deterministic recovery templates and explicit user approval for fallback.
- Production-grade isolated execution with CPU/memory/network limits.
- Persistent project editing and stronger incremental patching.
- Database/backend scaffolding, deployment integrations, GitHub workflows, and multiple language stacks.
- Optional GPT-OSS/Groq provider adapter while keeping the local Ollama path.
