# WasmBox API Server

**Owner:** Vineet

The web server receives requests from the frontend or external clients and orchestrates code execution.

## Endpoints

- `GET /health`: Healthcheck endpoint returning `{"ok": true}`.
- `POST /run`: Accepts JSON payload `{"code": "..."}` and returns execution status, output, and telemetry conforming to `docs/API_CONTRACT.md`.

## How `/run` Works

The `/run` endpoint implements a secure, sandboxed execution pipeline:

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
   • Uses the official precompiled MicroPython WASI binary as base
   • Deterministic: identical code yields identical artifact bytes
       │
       ▼
3. Execution (run_plugin)
   • Extracts embedded script from custom section in WASM binary
   • Executes via MicroPython WASI in Wasmtime sandbox
   • Strict capability isolation: no filesystem mounts, no network sockets
       │
       ▼
4. Response Serialization
   • Standard 5-field contract: status, stdout, stderr, exec_ms, mem_bytes
   • Captures syntax/runtime exceptions without crashing server
```

### Script Bundling vs. Native WASM Compilation
It is critical to distinguish **bundling** from native WASM compilation:
- **Bundling (Our Architecture):** The user's Python script is **not** compiled directly to machine-level WASM bytecode (which is slow, complex, and limits dynamic language features). Instead, the Python source code is stored verbatim inside a standard WebAssembly custom section (`wasmbox_script`) appended to the precompiled `micropython-wasi.wasm` interpreter binary.
- **Run-time Execution:** At runtime, the sandbox runtime extracts the script from the custom section and feeds it into the isolated MicroPython interpreter inside Wasmtime. This keeps packaging instantaneous (O(N) byte copy) while enforcing strict capability-based security boundaries.

## Running the API Server

From the `backend/` directory:

```bash
# Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
# or .venv\Scripts\activate on Windows

# Start development server
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

From the `backend/` directory:

```bash
pytest -q
```

The suite validates:
- GET `/health` availability and response schema
- POST `/run` contract shape and telemetry fields
- POST `/run` handling of empty and whitespace-only payloads
- POST `/run` 422 validation on missing fields
- CORS preflight and allowed origins (`localhost:5173`)

## CORS Configuration

CORS middleware is enabled in `app/main.py` allowing cross-origin requests from the React frontend running on `http://localhost:5173` and `http://127.0.0.1:5173`.

