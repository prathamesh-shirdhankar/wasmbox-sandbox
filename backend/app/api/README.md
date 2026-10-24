# WasmBox API Server

**Owner:** Vineet

The web server receives requests from the frontend or external clients and orchestrates code execution.

## Endpoints

- `GET /health`: Healthcheck endpoint returning `{"ok": true}`.
- `POST /run`: Accepts JSON payload `{"code": "..."}` and returns execution status, stdout, and stderr conforming to `docs/API_CONTRACT.md` (`exec_ms` and `mem_bytes` are always 0 until Week 3).

## How `/run` Works

The `/run` endpoint implements a sandboxed execution pipeline (not yet security-audited; currently runs with no directories preopened and no host functions registered):

```text
Browser / Client (POST /run)
       │
       ▼
1. Input Validation
   • Check non-empty & non-whitespace
   • Enforce MAX_CODE_LENGTH (<= 10,000 characters)
       │
       ▼
2. Packaging (package_plugin)
   • Embeds raw Python script into a custom WASM section ("wasmbox_script")
   • Uses the precompiled MicroPython WASI binary from micropython-wasm 0.1a2 as base
   • Deterministic: identical code yields identical artifact bytes
       │
       ▼
3. Execution (run_plugin)
   • Extracts embedded script from custom section in WASM binary
   • Executes via MicroPython WASI in Wasmtime sandbox
   • Capability restrictions: no preopened directories, no registered host functions (no audit has run yet)
       │
       ▼
4. Response Serialization
   • Standard 5-field contract: status, stdout, stderr, exec_ms (0), mem_bytes (0)
   • Captures syntax/runtime exceptions without crashing server
```

### Script Bundling vs. Native WASM Compilation
It is critical to distinguish **bundling** from native WASM compilation:
- **Bundling (Our Architecture):** The user's Python script is **not** compiled directly to machine-level WASM bytecode (which is slow, complex, and limits dynamic language features). Instead, the Python source code is stored verbatim inside a standard WebAssembly custom section (`wasmbox_script`) appended to the precompiled `micropython-wasi.wasm` interpreter binary.
- **Run-time Execution:** At runtime, the sandbox runtime extracts the script from the custom section and feeds it into the isolated MicroPython interpreter inside Wasmtime. This keeps packaging instantaneous (O(N) byte copy) while keeping the execution environment isolated with no preopened directories or host functions.

### Known Limits
- **Execution Latency:** A whole `run_plugin` call takes about 175–225 ms because `micropython_wasm.run()` compiles the interpreter module on every call (~110–130 ms compilation overhead). The original 50 ms target is not met with `run()` as it is.
- **Resource Defaults:** Execution uses package defaults: 1.0 s wall timeout, 20M fuel limit, and 16 MiB memory cap (resource enforcement and telemetry belong to Week 3).
- **Missing Payload:** Submitting a request without the required `code` field returns HTTP 422 Unprocessable Entity (FastAPI validation error) without the standard five fields.

## Running the API Server

From the repository root in PowerShell:

```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Start development server
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Running with Docker

From the project root:

```bash
# Build and run backend container
docker compose up --build backend
```

The container exposes port `8000` and serves `GET /health` and `POST /run`.

## Running Tests

From the repository root in PowerShell:

```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run tests
cd backend
pytest -q
```

The suite validates:
- GET `/health` availability and response schema
- POST `/run` contract shape and 5-field response (`exec_ms` and `mem_bytes` as 0)
- POST `/run` handling of empty and whitespace-only payloads
- POST `/run` 422 validation on missing fields
- POST `/run` unusual inputs and edge cases (comments, unicode/emojis, tabs, long lines, 5,000 output lines)
- CORS preflight and allowed origins (`localhost:5173`)

## CORS Configuration

CORS middleware is enabled in `app/main.py` allowing cross-origin requests from the React frontend running on `http://localhost:5173` and `http://127.0.0.1:5173`.
