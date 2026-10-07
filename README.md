# WasmBox

Secure multi-tenant Python plugin sandbox using WebAssembly (Wasmtime), with a React and Monaco developer portal.

## Folders

| Folder | What it holds | Owner |
|---|---|---|
| `backend/app/api/` | The web server: receives requests and sends answers | Vineet |
| `backend/app/runtime/` | Runs `.wasm` files safely from Python | Prathamesh |
| `backend/tests/` | Automatic checks that prove things work | Priya |
| `backend/scripts/` | Small helper scripts you run by hand | Prathamesh |
| `frontend/` | The website in the browser (React and Monaco) | Sashmita |
| `plugins/benign/` | Safe test programs | Prathamesh |
| `plugins/malicious/` | Attack programs we use to test our security | Priya |
| `docs/` | Our notes, findings and explanations | Everyone |

## Rules

- One branch per task, named `yourname/short-task`
- Small pull requests, and nobody merges their own
- Stuck for 90 minutes? Ask in the team chat

## Setup (everyone)

1. Install Python 3.12 (check with `py -0` on Windows)

2. From the repo folder, create and activate a virtual environment.

   PowerShell:

```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
```

   Git Bash:

```bash
   py -3.12 -m venv .venv
   source .venv/Scripts/activate
```

3. Install the backend packages:

```bash
   pip install -r backend/requirements.txt
```

## How to run each part

Each folder explains how to run its own part:

- WASM runtime and scripts: `backend/app/runtime/README.md` and `backend/scripts/README.md`
- Web server: `backend/app/api/README.md`
- Tests: `backend/tests/README.md`
- Frontend: `frontend/README.md`

## Current Status

- Wasmtime-based WASM runtime is working.
- Benign WASM execution has been verified from the Python host.
- Backend API endpoints and frontend are integrated.
- Host-function feasibility experiments are documented in `docs/SPIKES.md`.
- Extism is currently being evaluated as a separate runtime option for Python-in-WASM host functions; it is not part of the production runtime yet.
- The Python-in-WASM → host-function path remains under investigation.

## Development Workflow

Before opening a pull request, run:

```bash
git status
git diff
git grep --cached -n -e "EOF" -e "cat >"
```

Then:

1. Run the relevant tests and scripts for your changes before pushing.
2. Create a small PR with a clear description of:
   - What changed
   - How it was tested
   - Any limitations or unresolved findings