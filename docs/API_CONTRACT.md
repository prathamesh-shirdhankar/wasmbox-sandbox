# API Contract

This document defines the formal API contract agreed upon between Frontend and Backend for WasmBox.
Any modification requires review and approval from both sides.

---

## 1. GET /health

Health check endpoint indicating server readiness.

- **Request:** GET `/health`
- **Success Response (HTTP 200):**
  ```json
  { "ok": true }
  ```

---

## 2. POST /run

Executes user-submitted Python code inside the WebAssembly MicroPython sandbox.

- **Request:** POST `/run`
  ```json
  { "code": "print('hi')" }
  ```

- **Success Response (HTTP 200):**
  ```json
  {
    "status": "ok",
    "stdout": "hi\n",
    "stderr": "",
    "exec_ms": 12.5,
    "mem_bytes": 1114112
  }
  ```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `status` | string | One of: `ok`, `error`, `timeout`, `memory_exceeded`. (See Status Definitions below). |
| `stdout` | string | Captured standard output from guest execution. |
| `stderr` | string | Sanitized traceback or error message; empty on success. Host-side paths are stripped. |
| `exec_ms` | number | Monotonic execution time in milliseconds covering WASM instantiation and guest execution. Excludes Engine/Module initialization, Store/Linker/WASI setup, packaging/custom-section extraction, and lock wait time. `0` for validation rejections. |
| `mem_bytes` | number | Current guest WebAssembly linear memory in bytes exported from the WASM instance at completion (e.g. `1114112` for base MicroPython). `0` for pre-execution validation rejections. |

### Status Definitions

- `ok`: The plugin completed execution without unhandled exceptions or resource exhaustion.
- `error`: The plugin encountered a guest-level exception (e.g., `ZeroDivisionError`, `ImportError`, `OSError`, syntax error).
- `timeout`: The plugin was interrupted by host-side wall-clock deadline or instruction fuel exhaustion.
- `memory_exceeded`: The plugin exceeded the configured memory ceiling (`MemoryError` or guest linear memory boundary trap).

> **Historical / Reserved Status Note:** The `denied` status was reserved in earlier design specifications for host-side sandbox policy rejections. The current runner never emits `denied` (unauthorized file access returns `error` with standard exceptions such as `ENOENT`, and missing network modules return `ImportError`). Frontend implementations must only handle `ok`, `error`, `timeout`, and `memory_exceeded`.

---

## 3. Plugin Storage & Webhook Endpoints (Gate E)

### POST /plugins
Saves a named plugin to persistent SQLite storage.

- **Request Body:**
  ```json
  {
    "name": "My Plugin",
    "code": "print('hello from plugin')"
  }
  ```
- **Success Response (HTTP 200):**
  ```json
  {
    "id": 1,
    "name": "My Plugin"
  }
  ```
- **Error Responses:**
  - `HTTP 400 Bad Request`: When `name` is empty or exceeds 100 characters, or `code` is empty or exceeds 10,000 characters.
    ```json
    { "detail": "Plugin name must be between 1 and 100 characters" }
    ```
  - `HTTP 422 Unprocessable Entity`: When `name` or `code` field is missing from the payload.

### GET /plugins
Lists all saved plugins (summary format).

- **Request:** GET `/plugins`
- **Success Response (HTTP 200):**
  ```json
  [
    { "id": 1, "name": "My Plugin" },
    { "id": 2, "name": "Calculator" }
  ]
  ```

### GET /plugins/{id}
Retrieves a single plugin by its numeric ID for editing or inspection.

- **Request:** GET `/plugins/1`
- **Success Response (HTTP 200):**
  ```json
  {
    "id": 1,
    "name": "My Plugin",
    "code": "print('hello from plugin')"
  }
  ```
- **Error Responses:**
  - `HTTP 404 Not Found`: When the requested `id` does not exist.
    ```json
    { "detail": "Plugin not found" }
    ```
  - `HTTP 422 Unprocessable Entity`: When `id` is not an integer.

### POST /webhooks/{id}
Executes a saved plugin by ID and returns the standard 5-field execution response.

- **Request:** POST `/webhooks/1` (empty body)
- **Success Response (HTTP 200):**
  ```json
  {
    "status": "ok",
    "stdout": "hello from plugin\n",
    "stderr": "",
    "exec_ms": 14.2,
    "mem_bytes": 1114112
  }
  ```
- **Error Responses:**
  - `HTTP 404 Not Found`: When the requested `id` does not exist.
    ```json
    { "detail": "Plugin not found" }
    ```
  - `HTTP 422 Unprocessable Entity`: When `id` is not an integer.

---

## 4. Input Validation & Error Handling Rules

| Endpoint | Input Condition | HTTP Status | Response Format |
|---|---|---|---|
| `POST /run` | `code` field missing from JSON | **422** | FastAPI default validation error (no 5-field body). Frontend handles 422 separately. |
| `POST /run` | `code` is empty string or whitespace-only | 200 | `{"status": "error", "stderr": "No code provided", "stdout": "", "exec_ms": 0, "mem_bytes": 0}` |
| `POST /run` | `code` exceeds 10,000 characters | 200 | `{"status": "error", "stderr": "Code exceeds maximum allowed size of 10000 characters ...", "stdout": "", "exec_ms": 0, "mem_bytes": 0}` |
| `POST /plugins` | `name` empty or > 100 characters | 400 | `{"detail": "Plugin name must be between 1 and 100 characters"}` |
| `POST /plugins` | `code` empty or whitespace-only | 400 | `{"detail": "No code provided"}` |
| `POST /plugins` | `code` exceeds 10,000 characters | 400 | `{"detail": "Code exceeds maximum allowed size of 10000 characters"}` |
| `POST /plugins` | `name` or `code` field missing | 422 | FastAPI validation error object |
| `GET /plugins/{id}` | Unknown numeric ID | 404 | `{"detail": "Plugin not found"}` |
| `GET /plugins/{id}` | Non-integer ID (e.g. `/plugins/abc`) | 422 | FastAPI validation error object |
| `POST /webhooks/{id}` | Unknown numeric ID | 404 | `{"detail": "Plugin not found"}` |
| `POST /webhooks/{id}` | Non-integer ID | 422 | FastAPI validation error object |

---

## 5. Implementation Notes for Frontend & Integration

1. **422 Validation Handling:** When a required field is missing or has the wrong type, FastAPI returns HTTP 422 with its standard detail array, not the 5-field execution result. The frontend must inspect HTTP status codes and handle non-200 responses via the banner/status display rather than attempting to parse 5-field execution results.
2. **Execution Timing Boundaries (`exec_ms`):** `exec_ms` captures guest execution and WASM instantiation. It excludes pre-execution validation, packaging, Store/Linker/WASI setup, and runner lock acquisition. Requests rejected during validation return `exec_ms: 0`.
3. **Linear Memory Scope (`mem_bytes`):** `mem_bytes` reports the current guest WebAssembly linear memory exported from the module upon run completion. It does **not** represent peak memory consumption during execution, the internal MicroPython heap usage (bounded at 2 MiB), or the host process memory footprint.
4. **CORS & Editor Integration:** CORS headers on the backend allow preflight `OPTIONS` requests from `http://localhost:5173`. The Monaco editor state binds directly to the `{"code": "..."}` string payload.
5. **Error Message Formats (400/404 vs 422):**
   - **Application Errors (HTTP 400 / 404):** Return a JSON object with a string message: `{"detail": "..."}`. The frontend can display this string directly in the UI status/banner.
   - **Validation Errors (HTTP 422):** Return FastAPI's standard validation structure where `detail` is an array of error objects (`[{"loc": [...], "msg": "...", "type": "..."}]`). Frontend handlers should verify whether `detail` is a string or an array before displaying it to avoid rendering `[object Object]` or crashing.
