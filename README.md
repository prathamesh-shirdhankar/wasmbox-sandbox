# WasmBox

WasmBox is a WebAssembly-based Python plugin sandbox built with **Wasmtime, a MicroPython WASI runtime, FastAPI, React, and Monaco Editor**. It provides a developer portal and backend API for submitting Python source code and executing it inside a WebAssembly runtime with resource limits and restricted host capabilities.

WasmBox is a working prototype. Its security controls and resource limits are tested, but some limitations remain and it should not be treated as a production-ready security boundary without further validation.

## Folders

| Folder | What it holds | Owner |
|---|---|---|
| `backend/app/api/` | FastAPI web server and API request/response handling | Vineet |
| `backend/app/runtime/` | WebAssembly execution and MicroPython runner | Prathamesh |
| `backend/tests/` | Automated API, runtime, and security tests | Priya |
| `backend/scripts/` | Helper scripts and runtime demonstrations | Prathamesh |
| `frontend/` | React and Monaco-based developer portal | Sashmita |
| `plugins/benign/` | Benign WebAssembly test programs | Prathamesh |
| `plugins/malicious/` | Security probes used to test restricted behavior | Priya |
| `docs/` | Architecture, API contract, security findings, and spike reports | Everyone |

## Prerequisites

- Python 3.12
- Node.js and npm
- Git
- Windows PowerShell, Git Bash, or another terminal compatible with the setup commands

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd wasmbox-sandbox
```

Replace `<repository-url>` with the repository's Git URL.

### 2. Create and activate a Python virtual environment

**PowerShell:**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

**Git Bash:**

```bash
py -3.12 -m venv .venv
source .venv/Scripts/activate
```

### 3. Install backend dependencies

```bash
python -m pip install -r backend/requirements.txt
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

## Run the application

Start the backend and frontend in **separate terminal windows**.

### Backend

From the repository root, with the virtual environment activated:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload
```

The backend should be available at `http://127.0.0.1:8000`.

Check its health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "ok": true
}
```

### Frontend

In a second terminal:

```powershell
cd frontend
npm run dev
```

Open the local URL printed by Vite, typically `http://localhost:5173`.

The frontend requires the backend to be running for API operations. If the API is unavailable, the UI should communicate the failure rather than presenting a failed request as successful execution.

## API overview

The backend exposes the following primary endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Checks whether the backend is responding |
| `POST /run` | Submits Python source code for execution and returns the result |

### Example: execute Python code

```powershell
$body = @{
    code = "print(1 + 1)"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/run `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

A successful execution should return a response containing fields such as:

- `status` — execution outcome
- `stdout` — standard output
- `stderr` — error output
- `exec_ms` — measured elapsed execution time in milliseconds
- `mem_bytes` — memory metric, currently an unmeasured placeholder

The API uses these execution statuses:

| Status | Meaning |
|---|---|
| `ok` | Execution completed successfully |
| `error` | Python execution or another ordinary runtime operation failed |
| `denied` | An operation was explicitly denied |
| `timeout` | A configured execution time limit was exceeded |
| `memory_exceeded` | A memory-limit failure was detected and mapped to this status |

Refer to [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) for the complete request and response contract, validation behavior, and error handling.

## How execution works

At a high level, the execution pipeline is:

1. The client submits Python source code to the backend.
2. The backend validates the input, including empty input and the configured maximum source length.
3. The packaging layer embeds the source in a WebAssembly custom section named `wasmbox_script`.
4. The backend prepares the module for the repository-managed MicroPython WASI interpreter.
5. Wasmtime executes the module under the configured runtime controls.
6. The backend returns the execution status, output, error information, and available execution metrics.

See [`docs/PIPELINE.md`](docs/PIPELINE.md) for the detailed pipeline.

## Security and resource limits

WasmBox uses WebAssembly execution and explicit runtime configuration to reduce the capabilities available to submitted code. The security posture depends on the runtime, imported interfaces, host configuration, and the behavior actually verified by tests.

Current controls and limitations include:

- **Fuel limit:** bounds Wasmtime execution work.
- **Wall-clock timeout:** provides a time-limit mechanism, but startup overhead means the current implementation does not meet the 50 ms target.
- **Guest-memory limit:** configured in the runtime, but actual per-run memory consumption is not currently measured.
- **Restricted host capabilities:** filesystem and network access are constrained by the available runtime interfaces and imports. Security probes have verified selected restrictions; this is not an exhaustive audit.
- **Execution timing:** `exec_ms` measures elapsed time around the MicroPython WASI run, including engine/module startup and guest execution.
- **Memory reporting:** `mem_bytes` remains `0` as a placeholder and must not be interpreted as measured memory usage.

A WebAssembly runtime does not automatically make every workload secure. WasmBox is a prototype and should not be used as the sole security boundary for untrusted, multi-tenant workloads without additional review and validation.

See [`docs/SECURITY.md`](docs/SECURITY.md) for tested security behavior, evidence, and known gaps. See [`docs/SPIKES.md`](docs/SPIKES.md) for runtime experiments and timing observations.

## Tests and verification

Run the backend test suite from the repository root with the virtual environment activated:

```powershell
python -m pytest -q
```

Run the frontend production build:

```powershell
cd frontend
npm run build
cd ..
```

Run the relevant runtime scripts and tests when changing packaging, execution, or security behavior. Do not rely on a passing frontend build as proof that backend execution or security behavior works.

The latest recorded full-suite result on the documented revision was **71 passed, 2 skipped, and 1 warning**. Test results can change as the code evolves; rerun the tests on the revision you intend to merge.

The two skipped tests relate to resource-limit behavior that has not been demonstrated to meet the intended guarantees. Check the test skip reasons and the security documentation before interpreting the results.

## Current status

- The Wasmtime-based MicroPython WASI execution path is implemented.
- Benign WebAssembly execution from the Python host has been verified.
- The FastAPI execution and health endpoints are implemented.
- The React and Monaco developer portal is integrated with the backend API.
- Runtime limits, API behavior, and selected security restrictions have automated tests.
- Host-function feasibility experiments are documented in `docs/SPIKES.md`.
- Extism host-function experiments are separate from the primary runtime and are not part of the production execution path.
- Execution timing is reported, while actual memory consumption remains unmeasured.
- The project remains a prototype with documented limitations; further testing and security review are needed before production use.

## Development workflow

Follow the team's contribution rules:

- Create one branch per task, using `yourname/short-task`.
- Keep pull requests small and explain what changed, how it was tested, and any unresolved limitations.
- Do not merge your own pull request.
- Ask the team for help if blocked for approximately 90 minutes.

Before opening a pull request, review the changes:

```bash
git status
git diff --check
git diff
```

Then:

1. Run the relevant tests and scripts.
2. Build the frontend if your changes affect it.
3. Review the diff for accidental changes, secrets, generated files, and temporary debugging code.
4. Open a pull request with a clear description and test evidence.

## Documentation

- [API contract](docs/API_CONTRACT.md)
- [Execution pipeline](docs/PIPELINE.md)
- [Security findings](docs/SECURITY.md)
- [Runtime spikes and timing notes](docs/SPIKES.md)
- [WebAssembly design report](docs/WASM_REPORT.md)

For component-specific instructions, see the README files under `backend/` and `frontend/` where available.
