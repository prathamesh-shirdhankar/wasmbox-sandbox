# WasmBox API Contract

**Project:** WasmBox Sandbox
**Verified revision:** `2e1c11c`
**Last verification:** 5 November 2026

This document defines the API contract between the WasmBox frontend and backend.

It covers health checks, Python execution, plugin persistence, webhook execution, request validation, response formats, and error handling.

Any modification to the agreed API contract requires review and approval from both frontend and backend contributors.

The repository implementation and automated tests remain authoritative.

---

## 1. GET /health

Health-check endpoint indicating whether the backend application is responding.

**Request:**

```http
GET /health
```

Success Response (HTTP 200):

```json
{
  "ok": true
}
```

The endpoint is used by the frontend and operational checks to confirm backend availability.

## 2. POST /run

Executes user-submitted Python code inside the WasmBox WebAssembly MicroPython sandbox.

Request:

```http
POST /run
Content-Type: application/json
```

Request Body:

```json
{
  "code": "print('hi')"
}
```

The `code` field must contain a string.

The maximum accepted source length is 10,000 characters.

Successful Execution Response (HTTP 200):

```json
{
  "status": "ok",
  "stdout": "hi\n",
  "stderr": "",
  "exec_ms": 3.37,
  "mem_bytes": 2293760
}
```

The numerical values above are illustrative. Actual execution time and guest-memory measurements depend on the program and runtime state.

### 2.1 Response Fields

| Field       | Type    | Description                                                                                                                                                      |
| ----------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `status`    | string  | Execution outcome: `ok`, `error`, `timeout`, or `memory_exceeded`; `denied` is reserved for verified host-side policy denial where supported by the API adapter. |
| `stdout`    | string  | Captured standard output from guest execution.                                                                                                                   |
| `stderr`    | string  | Sanitized error information or execution-limit message. Empty when there is no reported error.                                                                   |
| `exec_ms`   | number  | Runner execution duration in milliseconds, covering WASM instantiation and guest execution.                                                                      |
| `mem_bytes` | integer | Current exported guest WebAssembly linear memory in bytes when available.                                                                                        |

### 2.2 Execution Status Definitions

`ok`

The plugin completed successfully without an unhandled execution error or recognized resource-limit failure.

`error`

The plugin encountered an ordinary execution failure, such as:

- `ZeroDivisionError`
- `ImportError`
- `OSError`
- Syntax errors
- Other guest-level exceptions
- Artifact or runner errors

`timeout`

The plugin was stopped because of a recognized host-side wall-clock deadline or WebAssembly instruction-fuel exhaustion.

`memory_exceeded`

The plugin exceeded a recognized memory boundary, such as the MicroPython heap limit or Wasmtime guest linear-memory limit.

`denied`

Reserved for verified host-side policy denial where supported by the API adapter.

Ordinary guest exceptions, missing-file errors, and unavailable Python modules must not automatically be classified as `denied`.

The API schema may allow this reserved status, but the current runner does not emit `denied` for ordinary guest failures.

### 2.3 Execution Timing (`exec_ms`)

`exec_ms` records the runner's documented execution interval.

It covers:

- WebAssembly instantiation.
- Guest execution.

It excludes:

- Waiting to acquire the process-wide `_RUNNER_LOCK`.
- Shared Wasmtime Engine initialization.
- Shared compiled Module initialization.
- Per-run Store setup.
- Linker and WASI setup.
- Source packaging.
- Custom-section extraction.
- Complete HTTP request handling.

Validation failures that do not execute the guest return `exec_ms: 0`.

Therefore, `exec_ms` must not be interpreted as total browser response time or HTTP latency.

### 2.4 Guest Linear Memory (`mem_bytes`)

`mem_bytes` reports the current size of exported guest WebAssembly linear memory in bytes when measurement is available.

It does not represent:

- Peak guest-memory allocation.
- Total MicroPython heap usage.
- Total host-process memory.
- Total Docker container memory.
- Peak physical RAM consumption.

A value of `0` can be returned for pre-execution validation failures or when memory introspection is unavailable.

The configured MicroPython heap limit and Wasmtime linear-memory limit are separate resource controls.

The frontend must use accurate terminology such as:

Guest linear memory

It must not label this metric as total system memory or peak RAM consumption.

## 3. Plugin Storage and Webhook Endpoints (Gate E)

The plugin API provides persistent storage and execution of saved Python plugins.

### 3.1 POST /plugins

Saves a named plugin to persistent SQLite storage.

Request:

```http
POST /plugins
Content-Type: application/json
```

Request Body:

```json
{
  "name": "My Plugin",
  "code": "print('hello from plugin')"
}
```

Success Response (HTTP 200):

```json
{
  "id": 1,
  "name": "My Plugin"
}
```

Validation Rules:

| Field  | Rule                                           |
| ------ | ---------------------------------------------- |
| `name` | Required, between 1 and 100 characters         |
| `code` | Required, non-empty, maximum 10,000 characters |

Error Responses:

HTTP 400 Bad Request:

When the plugin name is empty or exceeds 100 characters:

```json
{
  "detail": "Plugin name must be between 1 and 100 characters"
}
```

When the plugin code is empty or whitespace-only:

```json
{
  "detail": "No code provided"
}
```

When the plugin code exceeds 10,000 characters:

```json
{
  "detail": "Code exceeds maximum allowed size of 10000 characters"
}
```

HTTP 422 Unprocessable Entity:

Returned when a required field is missing or its type is invalid.

FastAPI uses its standard validation-error response structure.

### 3.2 GET /plugins

Lists all saved plugins in summary format.

Request:

```http
GET /plugins
```

Success Response (HTTP 200):

```json
[
  {
    "id": 1,
    "name": "My Plugin"
  },
  {
    "id": 2,
    "name": "Calculator"
  }
]
```

The listing returns plugin identifiers and names.

It does not return the complete source code of every saved plugin.

### 3.3 GET /plugins/{id}

Retrieves one saved plugin by numeric ID for editing or inspection.

Request:

```http
GET /plugins/1
```

Success Response (HTTP 200):

```json
{
  "id": 1,
  "name": "My Plugin",
  "code": "print('hello from plugin')"
}
```

Error Responses:

HTTP 404 Not Found:

When the requested plugin ID does not exist.

```json
{
  "detail": "Plugin not found"
}
```

HTTP 422 Unprocessable Entity:

When the ID is not an integer.

For example:

```http
GET /plugins/abc
```

FastAPI returns its standard validation-error structure.

### 3.4 POST /webhooks/{id}

Executes a saved plugin by its numeric ID.

The endpoint retrieves the stored plugin source and passes it through the execution pipeline.

Request:

```http
POST /webhooks/1
```

No request body is required.

Success Response (HTTP 200):

```json
{
  "status": "ok",
  "stdout": "hello from plugin\n",
  "stderr": "",
  "exec_ms": 3.37,
  "mem_bytes": 2293760
}
```

The five-field response follows the same execution contract as `POST /run`.

Execution failures are represented through the execution status and stderr fields.

Error Responses:

HTTP 404 Not Found:

When the requested plugin ID does not exist.

```json
{
  "detail": "Plugin not found"
}
```

HTTP 422 Unprocessable Entity:

When the supplied ID is not an integer.

## 4. Input Validation and Error Handling

The backend distinguishes between application-level errors and FastAPI request-validation errors.



### 4.1 Validation Matrix

| Endpoint              | Input Condition                        | HTTP Status | Response Format                          |
| --------------------- | -------------------------------------- | ----------- | ---------------------------------------- |
| `POST /run`           | `code` field missing                   | 422         | FastAPI validation error                 |
| `POST /run`           | `code` has an invalid type             | 422         | FastAPI validation error                 |
| `POST /run`           | Empty or whitespace-only code          | 200         | Five-field response with `status: error` |
| `POST /run`           | Code exceeds 10,000 characters         | 200         | Five-field response with `status: error` |
| `POST /plugins`       | Name empty or exceeds 100 characters   | 400         | JSON object with string `detail`         |
| `POST /plugins`       | Code empty or whitespace-only          | 400         | JSON object with string `detail`         |
| `POST /plugins`       | Code exceeds 10,000 characters         | 400         | JSON object with string `detail`         |
| `POST /plugins`       | Required field missing or invalid type | 422         | FastAPI validation error                 |
| `GET /plugins/{id}`   | Unknown numeric ID                     | 404         | JSON object with string `detail`         |
| `GET /plugins/{id}`   | Non-integer ID                         | 422         | FastAPI validation error                 |
| `POST /webhooks/{id}` | Unknown numeric ID                     | 404         | JSON object with string `detail`         |
| `POST /webhooks/{id}` | Non-integer ID                         | 422         | FastAPI validation error                 |

### 4.2 HTTP 400 and 404 Application Errors

Application-level errors return a JSON object with a string `detail` field.

Example:

```json
{
  "detail": "Plugin not found"
}
```

The frontend can display this string directly in its status or notification banner.

### 4.3 HTTP 422 FastAPI Validation Errors

FastAPI uses its standard validation-error structure.

Example:

```json
{
  "detail": [
    {
      "loc": [
        "body",
        "code"
      ],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

The `detail` value is an array of validation error objects, not a string.

The frontend must check its type before attempting to render it.

### 4.4 Execution Errors Versus HTTP Errors

A successful HTTP response does not necessarily mean guest execution succeeded.

For example, a Python division-by-zero error can return HTTP 200 while the response body contains:

```json
{
  "status": "error",
  "stdout": "",
  "stderr": "ZeroDivisionError",
  "exec_ms": 1.2,
  "mem_bytes": 2293760
}
```

| `POST /run` | Unexpected internal runner exception | 200 | Five-field response with `status: error`, empty stdout, generic stderr, `exec_ms: 0`, and `mem_bytes: 0` |

Unexpected exceptions raised during packaging or runner execution
are logged by the backend and returned as a generic execution error.
Internal exception details are not returned directly to the client.

The frontend must distinguish:

- HTTP request success.
- API application errors.
- Request-validation errors.
- Guest execution outcomes.

## 5. Frontend and Backend Integration Rules

### 5.1 Execution Request

The frontend sends the editor's Python source as a JSON string:

```js
{
  code: editorContent
}
```

The request must follow the `RunRequest` schema.

### 5.2 Response Handling

The frontend should process the five execution fields:

- `status`
- `stdout`
- `stderr`
- `exec_ms`
- `mem_bytes`

The output interface should distinguish successful execution from runtime errors, timeouts, and memory-limit failures.

### 5.3 HTTP 400/404 and HTTP 422 Handling

The frontend error handler must distinguish the two supported application-response formats.

Application errors:

```js
const detail = error.response?.data?.detail;

if (typeof detail === "string") {
    return detail;
}
```

Validation errors:

```js
if (Array.isArray(detail)) {
    return detail
        .map(item => item.msg)
        .join(", ");
}
```

Unknown error formats should fall back to a readable generic message.

This prevents `[object Object]` rendering and frontend runtime errors.

### 5.4 Plugin Workflow

The frontend must follow this sequence:

1. Submit a plugin name and source code using `POST /plugins`.
2. Retrieve saved plugin summaries using `GET /plugins`.
3. Retrieve a selected plugin using `GET /plugins/{id}`.
4. Load its code into the editor.
5. Trigger saved plugin execution using `POST /webhooks/{id}`.

The frontend should avoid duplicate submissions while an API operation is pending.

### 5.5 CORS and Editor Integration

The backend must permit browser requests from the configured frontend development origins.

The current development frontend normally runs at:

```text
http://localhost:5173
```

The backend CORS configuration must remain aligned with the actual frontend development and deployment origins.

The editor state is sent as the `code` string in the request body.

## 6. Integration Verification Evidence

Verified integrated revision: `2e1c11c`

The following integration evidence was recorded during the final project verification.

| Verification                     | Result                |
| -------------------------------- | --------------------- |
| Backend full test suite          | 103 passed, 1 skipped |
| Focused backend regression suite | 36 passed             |
| Frontend production build        | Passed                |
| Backend GitHub Actions CI        | Passed                |
| Frontend GitHub Actions CI       | Passed                |
| Independent frontend review      | Approved              |
| End-to-end integration cases     | 8/8 passed            |
| Manual frontend testing          | Passed                |
| Plugin save/list/load workflow   | Reported working      |
| Webhook execution workflow       | Reported working      |
| Backend health endpoint          | Passed                |

### 6.1 Timeout and Recovery

Linux container verification completed:

- 20 runner-level timeout and recovery cycles.
- 20 live-server timeout and recovery cycles.
- 20/20 recovery executions succeeded.
- 20/20 health checks succeeded.
- Docker exit code: 0.
- Docker `OOMKilled`: false.

### 6.2 Memory Enforcement

A bounded Docker execution of:

`plugins/malicious/memory_bomb.py`

returned:

`status: memory_exceeded`

A subsequent normal Python execution succeeded, and the health endpoint remained available.

The automated memory-bomb pytest placeholder remains skipped during the ordinary full test suite. The bounded Docker execution is separate manual security-test evidence.

### 6.3 HTTP Load Benchmark

The final-main live HTTP benchmark executed 36 requests using `print(42)`.

| Concurrency | Success | Throughput  | Average HTTP latency | p95 HTTP latency |
| ----------- | ------- | ----------- | -------------------- | ---------------- |
| 1           | 1/1     | 2.43 req/s  | 192.89 ms            | 192.89 ms        |
| 5           | 5/5     | 10.55 req/s | 7.54 ms              | 18.31 ms         |
| 10          | 10/10   | 16.18 req/s | 12.36 ms             | 22.45 ms         |
| 20          | 20/20   | 16.83 req/s | 15.14 ms             | 30.85 ms         |

All 36 requests succeeded, with zero failures.

The backend health endpoint remained available after the benchmark.

These measurements represent a short-duration test, not sustained production capacity.

Detailed results are maintained in `docs/LOAD_TEST.md`.

## 7. Related Implementation Files

| File                                        | Responsibility                                    |
| ------------------------------------------- | ------------------------------------------------- |
| `backend/app/main.py`                       | FastAPI application and application configuration |
| `backend/app/api/routes.py`                 | API route handling                                |
| `backend/app/api/schemas.py`                | Request and response schemas                      |
| `backend/app/runtime/packaging.py`          | Python source packaging                           |
| `backend/app/runtime/micropython_runner.py` | Wasmtime execution and resource limits            |
| `backend/tests/test_api.py`                 | API-level tests                                   |
| `backend/tests/test_plugins_api.py`         | Plugin persistence API tests                      |
| `backend/tests/test_runner_interface.py`    | Runner interface tests                            |
| `backend/tests/test_status_mapping.py`      | Execution-status mapping tests                    |
| `frontend/src/api.js`                       | Frontend HTTP API integration                     |
| `frontend/src/components/OutputPanel.jsx`   | Execution output and metric presentation          |

## 8. Change Management

The API contract is shared between frontend and backend development.

Changes to any of the following must be reviewed by both sides:

- Endpoint paths.
- HTTP methods.
- Request schemas.
- Response schemas.
- Execution statuses.
- Error formats.
- Timing definitions.
- Memory measurement semantics.
- Plugin persistence behavior.
- Webhook execution behavior.

Any approved modification must update the relevant implementation, automated tests, and documentation.

The API contract should remain synchronized with the actual backend implementation.

## 9. Final Contract Summary

WasmBox exposes the following principal endpoints:

| Method | Endpoint         | Purpose                         |
| ------ | ---------------- | ------------------------------- |
| GET    | `/health`        | Backend health check            |
| POST   | `/run`           | Execute submitted Python source |
| POST   | `/plugins`       | Save a named plugin             |
| GET    | `/plugins`       | List saved plugins              |
| GET    | `/plugins/{id}`  | Retrieve a saved plugin         |
| POST   | `/webhooks/{id}` | Execute a saved plugin          |

The API separates transport-level HTTP errors from guest execution outcomes.

It also distinguishes current guest linear-memory measurement from total or peak memory usage.

The contract is designed to provide a stable integration boundary between the WasmBox React frontend and Python backend.

Final documented revision: `2e1c11c`