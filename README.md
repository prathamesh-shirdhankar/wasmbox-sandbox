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
2. From the repo folder, create and activate a virtual environment:
```
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
```
   (Git Bash: `source .venv/Scripts/activate`)
3. Install the backend packages:
```
   pip install -r backend/requirements.txt
```

## How to run each part

Each folder explains how to run its own part:

- WASM runtime and scripts: `backend/app/runtime/README.md` and `backend/scripts/README.md`
- Web server: `backend/app/api/README.md`
- Tests: `backend/tests/README.md`
- Frontend: `frontend/README.md`
