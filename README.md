# CoderBuddy-CaPStone

Turn a plain-English app idea into a generated web project you can inspect,
test, preview, refine, and export. Runs on your laptop with a VS Code-inspired
studio, a persistent build queue, and version history.

**Stack:** Python, FastAPI, LangGraph, LangChain, SQLite, and vanilla HTML/CSS/JavaScript.

## What it does

- Plans and generates small HTML/CSS/JavaScript apps with Python behavior tests.
- Runs checks and sends failures back to the model for up to two repair attempts.
- Shows source beside an expandable, sandboxed app preview.
- Queues builds one at a time; saves activity, results, and project versions.
- Refines an existing version without overwriting it and exports projects as ZIPs.

## Prerequisites

Install these on your laptop and make sure their commands are available:

| Software | Purpose |
|---|---|
| [Python 3.12+](https://www.python.org/downloads/) | Runs the server and tests |
| [Node.js 18+](https://nodejs.org/) | Checks generated JavaScript syntax; no npm install needed |
| Azure Foundry access | Your own Responses API endpoint, model deployment, and API key |
| [Ollama](https://ollama.com/download) (optional) | Alternative to Azure for local model processing |
| [Git](https://git-scm.com/downloads) (optional) | Clones the repository; Download ZIP also works |
| Modern browser | Opens the studio and generated app preview |

Internet is needed for dependency downloads and Azure requests. The app runs on
your laptop; Azure provides the AI model. No application hosting is required.

## Install and run

### Windows test installer

The MSI bundles Python, Node.js, and Python dependencies for **Windows x64**;
recipients do not need to install those runtimes separately.

1. Install `dist\CoderBuddy-CaPStone-3.0.0-x64.msi`.
2. Open **CoderBuddy-CaPStone** from the Windows Start menu.
3. On first launch, enter an Azure Responses endpoint, deployment name, and key.
   The key is not included in the installer.
4. The studio opens in your browser. Keep its console open; press `Ctrl+C` to stop.

Settings, generated apps, and history are saved under
`%LOCALAPPDATA%\CoderBuddy-CaPStone`, outside the installation directory.
The key is saved in a local plaintext `.env`; do not share that folder.
Uninstalling the app leaves this user data intact. Internet and valid Azure
credentials are still required. This is an unsigned test installer, not a
code-signed production release, and Windows may show a publisher warning.

To build the MSI on 64-bit Windows with Python 3.12:

```powershell
.\.venv\Scripts\python.exe packaging\build_msi.py
```

The builder downloads official Python, Node.js, and WiX binaries and installs
dependencies into an isolated payload. Build output is ignored by Git.
Use a fresh build directory for each build. Publish the MSI as a GitHub Release
asset rather than uploading bundled runtimes into the source repository.

### Run from source

### 1. Get the code

Clone this repository using its GitHub **Code** button, or download and extract
its ZIP. Open a terminal in the folder containing `requirements.txt`.

### 2. Install dependencies

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS / Linux:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Copy `.env.example` only on first setup; do not overwrite an existing `.env`.
Virtual environment activation is not required for these commands.

### 3. Configure Azure Foundry

The current project uses Azure Foundry with a `gpt-4.1-mini` deployment.
New users must supply their own credentials in `.env`:

```dotenv
AI_PROVIDER=azure-foundry
AZURE_OPENAI_RESPONSES_ENDPOINT=https://YOUR-RESOURCE.services.ai.azure.com/openai/v1/responses
AZURE_OPENAI_DEPLOYMENT=YOUR-DEPLOYMENT-NAME
AZURE_OPENAI_API_KEY=YOUR-KEY
AZURE_OPENAI_TIMEOUT_SECONDS=240
```

Use the exact deployment name from your Azure resource; it may differ from the
model name. Ollama is **not required** for this setup. Prompts and source needed
for generation/refinement/repair are sent to Azure. Readiness checks and builds
use quota and may incur costs. Never commit `.env` or share API keys.
For local model processing instead, see the optional Ollama setup below.

### 4. Start the app

**Windows PowerShell:**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

**macOS / Linux:**

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Open **http://127.0.0.1:8010**. Keep the terminal open; press `Ctrl+C` to stop.
No hosting or deployment is needed. Windows users can also use
`start-coder-buddy.bat` after installing the prerequisites.

## Use it

1. Describe an app, for example: "Build a task planner with add, complete, delete, and filters."
2. Queue the build and review its plan, activity, and check results.
3. Use the preview and inspect the generated source. Passing checks do not prove every feature works.
4. Request changes to create a new version, or export the generated project.

If the model is unavailable or generation cannot be repaired, a new build may
deliver a **labelled offline starter**, not a fully custom app. Source-preserving
refinement requires a working model and fails explicitly rather than replacing
your project with a starter.

## Optional: Ollama instead of Azure Foundry

Install Ollama, start it, and download the model:

```text
ollama pull qwen2.5-coder:3b
```

If Ollama is not already running, run `ollama serve` in a separate terminal.
Change these settings in `.env`, then restart the app:

```dotenv
AI_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5-coder:3b
```

No Azure key is needed for this option. Model processing runs locally after
the initial download; speed and memory needs depend on your laptop.

## How it works

```text
Studio -> FastAPI -> SQLite queue -> single worker -> LangGraph
         analyze -> plan -> generate -> write -> check -> repair/recheck
         -> preview / new version / ZIP export
```

| Folder | Contents |
|---|---|
| `app` | API, queue, agents, model adapters, validation, and offline starters |
| `static` | Studio interface |
| `tests` | Automated tests |
| `presentation` | Slides, final report, and speaker notes |
| `data` / `workspace` | Local history / generated files; created at runtime and ignored by Git |

Run one server worker per database. Waiting builds can be cancelled; active
builds cannot. Queued work survives restarts; interrupted active builds are
marked failed for deliberate retry. To back up projects, stop the app and copy
**both** `data` and `workspace`.

## Tests and troubleshooting

Run tests from the project folder:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

On macOS/Linux, use `.venv/bin/python -m pytest -q`.
The optional live-Ollama integration test needs a running model service.

- **Cannot connect:** keep the server running and use the exact printed URL.
- **Port blocked or occupied:** change `--port 8010` to `--port 8011`.
- **Model unavailable:** check your Azure endpoint, deployment, and key in `.env`,
  then http://127.0.0.1:8010/api/health. For Ollama, also check `ollama list`.
  Restart after configuration changes.
- **JavaScript check unavailable:** install Node.js and reopen your terminal.
- **Slow builds:** local model generation can take several minutes on a CPU.

API documentation: http://127.0.0.1:8010/docs.

## Scope and safety

This is a local capstone/demo, **not a public production service**. Keep it
bound to `127.0.0.1` and use trusted prompts. Generated Python tests run on your
machine with bounded execution guards, not an OS/container security boundary.
There is no authentication or multi-user isolation.

Current scope is small static browser apps with Python logic tests, not arbitrary
full-stack systems. Generated commerce checkout is a demo; payments, production
backends, and external deployment are not configured. Review exported code before
using it elsewhere.

## Contributing and license

Issues and pull requests are welcome. Describe the change, add relevant tests,
and run the test suite. Do not include credentials, local history, or generated
private projects.

Released under the [MIT License](LICENSE). You may use, modify, and redistribute
the code, including commercially, subject to its license notice. MIT does not
deploy or host the application; local laptop setup is the default.
