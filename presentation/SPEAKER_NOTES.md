# CoderBuddy-CaPStone: final review and live demo

**Target:** 7-9 minutes plus questions. Start the server before presenting.

## Preparation

1. Run `start-coder-buddy.bat` from the project folder. Install Python and Node.js as documented.
2. Confirm the top bar shows the real configured provider as ready. The current setup uses Azure Foundry / gpt-4.1-mini; Ollama remains an alternative. Never show `.env`, keys, or the Azure credentials screen.
3. Keep the studio open. Open `Coder_Buddy_Final_Presentation.pptx`. Do not claim production deployment or browser-feature coverage beyond what was demonstrated.

## Slides 1-3: purpose and scope

Introduce the team and guide. Explain the problem: generating a snippet does not
perform integration, testing or repair. The project makes an agentic build loop
inspectable. Scope includes static web apps, Python business logic and tests,
source-aware refinement, sequential requests, local project persistence, preview
and export. Backends, databases, public execution and cloud publishing are not
claimed as implemented.

## Slides 4-5: workflow and architecture

FastAPI saves each request in SQLite with a sequence number. One process-locked
worker runs requests in order. LangGraph coordinates interpretation, planning,
generation, file writes, validation, bounded repair and delivery. LangChain
exposes confined file/test tools. Azure Foundry or Ollama supplies the model;
provider configuration stays server-side.

The model returns a structured project draft. Plan, source and features are
produced together, then processed through explicit workflow nodes. Do not claim
that independent research or an external deployment happened.

## Slides 6-7: artifacts and execution

Explain the six required files: HTML, CSS, JS, Python logic, pytest tests, README.
Node checks JS syntax without executing it on the host. Python behavior tests run
in a restricted subprocess with timeouts and minimal environment. Test output
is used for up to two model repair attempts. Each build has its own folder.

The browser preview is sandboxed and cannot connect to external services.
These guards are not an OS/container sandbox. The studio is for local trusted
prompts, not public multi-user code execution.

## Slides 8-10: product and verification

Show the sidebar queue, Projects search, explorer, syntax-highlighted source,
actual validation output, agent activity and live preview. "Checks passed" means
the recorded checks passed; it is not a guarantee of all requirements.

The automated suite exercises atomic claims, FIFO order, cancellation,
idempotency, interruption recovery, locking, independent versions, source-aware
refinement, providers and existing preview/export behavior. Use the actual latest
test result from your terminal; never invent metrics. The optional Ollama test
may be skipped when that service is offline.

## Slide 11: live demonstration

1. Submit: **"Build a calculator with arithmetic, keyboard input, clear and divide-by-zero validation."**
2. While it works, submit: **"Build a three-question quiz with scoring and restart."** Show their unique request numbers and that only one is active.
3. Add a third waiting request and cancel it. Explain that active builds finish under timeouts rather than unsafe termination.
4. Open the calculator from Projects. Show its plan, source and actual checks. Calculate `12 / 3` in its preview.
5. Select `app.js`, expand and restore the app preview, then export its ZIP.
6. Submit a refinement: **"Keep the existing calculator and make the keys larger with a blue accent."** Show that it is a separate build under the same project. Open the earlier version to demonstrate retained output.
7. Reload the page and reopen a project. Explain that SQLite and workspace folders persist across server restarts, while browser storage remembers the selected build.

If a model request fails or falls back, disclose it. Demonstrate the saved
failure, diagnostics and deliberate retry instead of describing it as success.
If the server is forcibly stopped, queued work survives and interrupted active
work becomes failed with a retry option.

## Slide 12: closing and questions

The result is a transparent local engineering studio: requirements, artifacts,
tests, repair, versions and delivery in one workflow.

**Is this production ready?** It is release-ready as a local capstone demonstrator,
not a hardened production execution platform. Real hosting, payments, databases,
authentication and OS-level isolation require additional work.

**Why Azure instead of GPT-OSS/Groq?** The brief lists those technologies. The
working user-provided Azure deployment was retained; Ollama/Qwen is available.
Groq is not claimed as implemented.

**What is persistent?** SQLite holds requests/events/results and workspace folders
hold source. Back up both while the app is stopped. Older recovered source is
labelled as unvalidated rather than given fabricated historical test results.

**Can requests mix?** Each request has a unique folder; one worker executes at a
time. Refinement reads the selected version and writes a new version.
