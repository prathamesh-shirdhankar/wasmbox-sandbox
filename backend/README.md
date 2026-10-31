# WasmBox Backend — Runtime, Security and Testing Documentation

> **Project:** WasmBox Sandbox
> **Component:** Python Backend and WebAssembly Runtime
> **Runtime:** FastAPI + Wasmtime + MicroPython WASI
> **Python:** 3.12
> **Current Wasmtime dependency:** 49.0.0
> **Status:** Runtime implementation and verification completed; peer review required before merging.

---

## 1. Project Overview

WasmBox is a sandboxed Python execution environment. It allows users to submit Python source code and execute it inside a WebAssembly-based MicroPython interpreter.

The backend is responsible for:

- Receiving Python execution requests.
- Validating plugin artifacts.
- Executing Python code inside the MicroPython WASI interpreter.
- Enforcing execution time, instruction-fuel and memory limits.
- Capturing standard output and standard error.
- Reporting execution status, execution time and memory usage.
- Managing saved plugins and webhook execution.
- Preventing guest programs from accessing restricted host resources.

The backend uses FastAPI for its HTTP API and Wasmtime for WebAssembly execution.

### Important architectural decision

WasmBox does not compile each submitted Python script into a new WebAssembly module.

Instead:

1. The MicroPython WASI interpreter is maintained as a repository-managed `.wasm` artifact.
2. User Python source code is stored in a custom WebAssembly section named `wasmbox_script`.
3. The interpreter reads and executes that source code at runtime.

This is a packaging approach, not Python-to-WebAssembly compilation.

---

## 2. Technology Stack

| Component | Technology | Version |
|---|---|---|
| Backend language | Python | 3.12 |
| API framework | FastAPI | 0.115.0 |
| ASGI server | Uvicorn | 0.30.6 |
| WebAssembly runtime | Wasmtime | 49.0.0 |
| Python WASI interpreter package | micropython-wasm | 0.1a2 |
| Data validation | Pydantic | 2.9.2 |
| Testing framework | pytest | 8.3.3 |
| API testing | httpx | 0.27.2 |
| Containerization | Docker | Docker Desktop |
| Guest interpreter | MicroPython WASI | Repository-managed artifact |

### Backend dependencies

The dependency file is:

`backend/requirements.txt`

Current pinned dependencies:

```text
wasmtime==49.0.0
micropython-wasm==0.1a2
fastapi==0.115.0
uvicorn[standard]==0.30.6
pytest==8.3.3
httpx==0.27.2
pydantic==2.9.2
```

Dependencies are pinned to make the development and Docker environments reproducible.

**Dependency decision:** Wasmtime remains pinned to 49.0.0. The memory-exhaustion fix was tested using this existing dependency; no dependency upgrade was required for the verified result.

---

## 3. Backend Directory Structure

Relevant backend structure:

```text
wasmbox-sandbox/
│
├── backend/
│   │
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   └── README.md
│   │   │
│   │   ├── runtime/
│   │   │   ├── micropython_runner.py
│   │   │   ├── _temp_packager.py
│   │   │   ├── artifacts/
│   │   │   │   ├── micropython-wasi.wasm
│   │   │   │   └── README.md
│   │   │   └── README.md
│   │   │
│   │   └── main.py
│   │
│   ├── scripts/
│   │   └── README.md
│   │
│   ├── tests/
│   │   ├── test_api.py
│   │   ├── test_limits.py
│   │   ├── test_plugins_api.py
│   │   ├── test_security_plugins.py
│   │   ├── test_unusual_inputs.py
│   │   └── README.md
│   │
│   ├── Dockerfile
│   └── requirements.txt
│
├── plugins/
│   ├── benign/
│   └── malicious/
│
├── docs/
│
├── docker-compose.yml
└── README.md
```

### Important runtime files

| File | Responsibility |
|---|---|
| `backend/app/runtime/micropython_runner.py` | Core Wasmtime execution engine and resource-limit enforcement |
| `backend/app/runtime/_temp_packager.py` | Test artifact packaging helper |
| `backend/app/runtime/artifacts/micropython-wasi.wasm` | Repository-managed MicroPython WASI interpreter |
| `backend/app/api/routes.py` | HTTP endpoints and execution response handling |
| `backend/app/api/schemas.py` | API request and response schemas |
| `backend/tests/test_limits.py` | Resource-limit and timeout tests |
| `backend/tests/test_security_plugins.py` | Security and malicious-plugin tests |
| `backend/tests/test_plugins_api.py` | Plugin storage and webhook API tests |

---

## 4. Runtime Architecture

### 4.1 Execution pipeline

The current execution pipeline is:

```text
User submits Python source
          |
          v
       FastAPI
          |
          v
    Request validation
          |
          v
   Plugin artifact handling
          |
          v
 Extract wasmbox_script
   custom WASM section
          |
          v
    Shared Wasmtime Engine
          |
          v
   Compiled MicroPython Module
          |
          v
    Create fresh Store
          |
          v
    Apply resource limits
          |
          v
 Configure WASI environment
          |
          v
    Create fresh Instance
          |
          v
 Execute MicroPython WASI
          |
          v
 Capture stdout and stderr
          |
          v
 Measure current WASM memory
          |
          v
 Classify execution result
          |
          v
       FastAPI response
```

### 4.2 Shared Engine and compiled Module

The current runner uses:

- One lazily initialized shared Wasmtime Engine.
- One compiled MicroPython WASM Module associated with that Engine.
- A fresh Store for each execution.
- A fresh Instance for each execution.

The shared Engine and compiled Module avoid recompiling the interpreter for every plugin execution.

The Store and Instance are created separately for each run.

This is intended to provide execution-state separation while reusing the compiled interpreter.

### 4.3 Runtime initialization

The runtime is initialized lazily through `_get_runtime()`.

The initialization process:

1. Creates a Wasmtime configuration.
2. Enables instruction-fuel consumption.
3. Enables epoch interruption.
4. Configures the maximum WASM stack.
5. Creates the Engine.
6. Compiles the repository-managed MicroPython WASI module.
7. Registers the package's existing host-call import implementation.
8. Starts the shared Engine epoch ticker.
9. Stores the initialized runtime for subsequent executions.

The runtime uses a lock to prevent simultaneous first-time initialization.

### 4.4 Fresh Store and Instance

Each execution receives a new Store.

The runner applies Store limits before instantiating the WASM module.

The execution does not reuse another plugin's Store or Instance.

### 4.5 Execution timing

The `exec_ms` field measures the time spent during instantiation and guest execution.

Engine and compiled Module initialization occur separately and are excluded from the execution-time measurement.

Artifact extraction and API request processing are also outside this measurement.

---

## 5. WebAssembly Artifact Format

The runner expects a WebAssembly artifact beginning with:

```python
WASM_HEADER = b"\x00asm\x01\x00\x00\x00"
```

The custom section identifier is:

```python
SECTION_NAME = "wasmbox_script"
```

The runner extracts the custom section and decodes the embedded source as UTF-8.

The artifact parser handles:

- Invalid WebAssembly headers.
- Truncated artifacts.
- Invalid custom-section lengths.
- Invalid section names.
- Missing script sections.
- Invalid UTF-8 source.

Invalid artifacts are returned as errors rather than executed.

### Interpreter path

The interpreter is loaded from:

```text
backend/app/runtime/artifacts/micropython-wasi.wasm
```

The execution environment uses the repository-managed interpreter rather than accepting an arbitrary interpreter supplied by a plugin.

---

## 6. Resource-Limit Configuration

The current production defaults in:

`backend/app/runtime/micropython_runner.py`

are:

| Configuration | Current value | Purpose |
|---|---:|---|
| `DEFAULT_MEMORY_BYTES` | 10 MiB | Wasmtime Store memory-size limit |
| `DEFAULT_FUEL` | 30,000,000 | Instruction-fuel budget |
| `DEFAULT_WALL_TIMEOUT_SECONDS` | 0.05 seconds | Default wall-clock timeout |
| `MICROPYTHON_HEAP_SIZE` | 2M | MicroPython Python heap |
| `TICK_INTERVAL_SECONDS` | 0.005 seconds | Epoch ticker interval |
| `WASM_PAGE_BYTES` | 65,536 bytes | WASM memory-page size |
| `HOST_RESULT_BYTES` | 262,144 bytes | Host-call result buffer configuration |
| `config.max_wasm_stack` | 512 KiB | Maximum WASM stack configuration |

The Store also applies the following limits:

| Store resource | Limit |
|---|---:|
| Instances | 1 |
| Memories | 1 |
| Tables | 8 |
| Table elements | 10,000 |

### 6.1 Important distinction: 10 MiB versus 2 MiB

There are two separate memory configurations.

**Wasmtime Store memory limit:**

```python
DEFAULT_MEMORY_BYTES = 10 * 1024 * 1024
```

**MicroPython Python heap:**

```python
MICROPYTHON_HEAP_SIZE = "2M"
```

These are not the same thing.

The 10 MiB limit controls the memory available to the WASM Store.

The 2M heap setting configures the memory available to Python objects managed by MicroPython.

MicroPython can therefore exhaust its usable Python heap before the Wasmtime Store reaches its configured 10 MiB limit.

The 10 MiB Store limit must not be interpreted as a guarantee that a Python script can allocate 10 MiB of Python objects.

### 6.2 Memory reporting

The runner reports:

```text
mem_bytes
```

The measurement is obtained by examining the exported WASM linear memory.

The calculation is:

```python
memory.size(store) * WASM_PAGE_BYTES
```

Where:

```python
WASM_PAGE_BYTES = 65536
```

**Important:** `mem_bytes` reports the current exported WASM linear-memory size when it is measured.

It is not:

- Peak memory consumption.
- Total host-process memory.
- Total Docker container memory.
- A direct measurement of Python objects allocated by MicroPython.
- Maximum memory consumption during the entire execution.

If an instance is not available or memory introspection fails, the returned value may be zero.

---

## 7. Fuel-Based Execution Limits

Wasmtime instruction-fuel consumption is enabled.

Current default:

```python
DEFAULT_FUEL = 30_000_000
```

Each execution receives a fuel budget.

The caller can override the default by passing a different positive fuel value to `run_plugin()`.

When the guest consumes all available fuel, execution is stopped.

The runner classifies recognized fuel-exhaustion traps as:

```text
timeout
```

Fuel exhaustion and wall-clock interruption are both reported as timeout conditions, but they have different underlying causes.

---

## 8. Wall-Clock Timeout and Epoch Interruption

The current default wall-clock timeout is:

```python
DEFAULT_WALL_TIMEOUT_SECONDS = 0.05
```

Equivalent to 50 milliseconds.

### 8.1 Epoch interruption

The runner enables:

```python
config.epoch_interruption = True
```

A shared background daemon thread advances the Engine epoch approximately every 5 milliseconds.

The ticker interval is:

```python
TICK_INTERVAL_SECONDS = 0.005
```

### 8.2 Per-execution deadline

For each run, the runner calculates a deadline based on the requested timeout.

The number of ticks is derived from:

```python
math.ceil(
    wall_timeout_seconds / TICK_INTERVAL_SECONDS
)
```

The deadline is set before instantiation because instantiation itself executes WebAssembly.

A lock synchronizes deadline configuration with epoch increments.

### 8.3 Timeout behaviour

The runner recognizes timeout-related diagnostics, including:

- WASM interrupt traps.
- Epoch deadline interruptions.
- Wasmtime interrupt trap codes.
- Fuel exhaustion.
- Out-of-fuel diagnostics.

These failures are reported as:

```text
status = "timeout"
```

### 8.4 Timeout limitations

The 50 ms timeout is an aggressive default.

It is not a hard real-time guarantee.

Actual interruption behaviour can be influenced by:

- Thread scheduling.
- Epoch-ticker timing.
- Host system load.
- Runtime overhead.
- WebAssembly instruction execution.

The default timeout should receive peer review before the runtime is considered ready for production workloads.

---

## 9. Memory-Exhaustion Detection and Classification

One of the main problems investigated during this development cycle was incorrect classification of memory exhaustion.

### 9.1 Original problem

The malicious memory-bomb plugin attempted repeated large allocations.

The observed execution sometimes ended in a Wasmtime trap:

```text
MEMORY_OUT_OF_BOUNDS
```

Instead of a normal Python `MemoryError`.

This occurred because the WebAssembly interpreter could encounter a linear-memory access failure before the Python-level exception handler could process the allocation failure.

The original runner classified this trap as:

```text
error
```

This did not match the required sandbox status.

### 9.2 Reserved exit code

The runner now defines:

```python
MEMORY_ERROR_EXIT_CODE = 86
```

The guest wrapper catches an uncaught `MemoryError` and raises:

```python
raise SystemExit(86)
```

This provides a way for a normal Python-level memory exception to be reported without writing an error marker or formatting a traceback when the heap may already be exhausted.

The host runner recognizes the reserved exit code and returns:

```text
memory_exceeded
```

### 9.3 MEMORY_OUT_OF_BOUNDS classification

The memory-exhaustion detector also recognizes relevant Wasmtime memory diagnostics.

The detector checks for:

```text
trapcode.memory_out_of_bounds
```

It also recognises the combination of:

```text
memory fault at wasm address
```

and:

```text
out of bounds memory access
```

Other explicit Wasmtime memory-growth and memory-size-limit diagnostics are also recognised.

These cases are classified as:

```text
memory_exceeded
```

### 9.4 Important limitation

A `MEMORY_OUT_OF_BOUNDS` trap can indicate actual memory exhaustion, but it can also indicate an interpreter or runtime defect.

The current classification addresses the observed MicroPython memory-bomb failure.

It does not prove that every out-of-bounds WASM trap is necessarily caused by a resource-limit violation.

This classification should be reviewed and monitored.

---

## 10. Execution Statuses

The runner returns a `PluginResult` containing:

```python
@dataclass(frozen=True)
class PluginResult:
    status: str
    stdout: str
    stderr: str
    exec_ms: float = 0.0
    mem_bytes: int = 0
```

Current runner status behaviour:

| Status | Meaning |
|---|---|
| `ok` | Execution completed without a detected guest or runtime failure |
| `error` | Guest exception, invalid execution or another runtime failure |
| `timeout` | Wall-clock interruption or instruction-fuel exhaustion |
| `memory_exceeded` | Recognised Python or WASM memory exhaustion |

The API schema may support additional statuses such as `denied`; this list describes the classifications handled by the runtime runner.

### Example successful result

```json
{
  "status": "ok",
  "stdout": "hello from wasm\n",
  "stderr": "",
  "exec_ms": 0.93,
  "mem_bytes": 2293760
}
```

### Example timeout result

```json
{
  "status": "timeout",
  "stdout": "",
  "stderr": "Execution timed out: wall-clock or instruction fuel limit exceeded.",
  "exec_ms": 2.91,
  "mem_bytes": 2293760
}
```

### Example memory-exhaustion result

```json
{
  "status": "memory_exceeded",
  "stdout": "",
  "stderr": "Execution stopped: sandbox memory limit exceeded.",
  "exec_ms": 1.99,
  "mem_bytes": 2293760
}
```

These examples illustrate observed runtime outputs; execution times are environment-dependent.

---

## 11. WASI and Host Capability Configuration

The runner creates a WASI configuration for each execution.

The configuration includes:

- The MicroPython executable name.
- The `-X heapsize=2M` argument.
- The `-c` option to execute the wrapped source.
- An empty environment-variable list.
- Custom standard-output capture.
- Custom standard-error capture.

The runner does not configure filesystem directory preopens.

The application does not supply guest-accessible network or application host functions in the host-function mapping used for registration.

### Host-call registration

The runner currently reuses the installed package's existing implementation:

```python
run.__globals__.get("_define_host_call")
```

This is a private implementation detail of the installed `micropython-wasm` package.

The helper is registered with an empty application host-function mapping.

### Compatibility limitation

The runner depends on a private package helper.

A future package version could rename, remove or change this helper.

This dependency should receive peer review. A supported public API would be preferable if available.

---

## 12. API Integration

The backend API is implemented using FastAPI.

Relevant endpoints include:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Backend health check |
| `POST /run` | Execute submitted Python source |
| `POST /plugins` | Save a plugin |
| `GET /plugins` | List saved plugins |
| `POST /webhooks/{id}` | Execute a saved plugin |

The execution route forwards the runner's result fields to the response.

The memory field is obtained from:

```python
mem_bytes=result.mem_bytes
```

This replaces the earlier hard-coded zero value.

The plugin webhook response also reports actual execution metrics.

### API response fields

| Field | Type | Description |
|---|---|---|
| `status` | string | Execution result status |
| `stdout` | string | Captured standard output |
| `stderr` | string | Captured standard error |
| `exec_ms` | number | Execution duration in milliseconds |
| `mem_bytes` | integer | Current exported WASM linear-memory size in bytes |

---

## 13. Automated Test Coverage

The backend test suite verifies API behaviour, plugin handling, execution limits and selected security restrictions.

### 13.1 Latest complete test result

Command:

```powershell
python -m pytest -q
```

Latest recorded output:

```text
.................................................................s..........

75 passed, 1 skipped, 1 warning in 2.81s
```

Summary:

| Result | Count |
|---|---:|
| Passed | 75 |
| Skipped | 1 |
| Failed | 0 |
| Warnings | 1 |
| Total collected | 76 |

The suite completed successfully.

### 13.2 Warning

The test suite reports one deprecation warning:

```text
DeprecationWarning:
The anyio.abc.BlockingPortal alias is deprecated,
use anyio.from_thread.BlockingPortal instead.
```

The warning originates from the installed Starlette TestClient integration.

It is non-blocking and did not cause a test failure.

### 13.3 Resource-limit tests

File:

```text
backend/tests/test_limits.py
```

The resource-limit test module contains eight tests.

| Test | What it verifies |
|---|---|
| `test_short_wall_timeout_is_reported_as_timeout` | Infinite guest execution is interrupted by a short wall-clock deadline |
| `test_normal_run_reports_real_elapsed_time` | Successful execution returns stdout and a positive execution time |
| `test_fuel_exhaustion_is_reported_as_timeout` | Instruction-fuel exhaustion produces timeout status |
| `test_infinite_loop_stops_with_wall_timeout_enabled` | Infinite-loop execution is stopped |
| `test_twenty_timeouts_then_normal_run_still_works` | Runtime remains usable after repeated interruptions |
| `test_memory_out_of_bounds_trap_is_recognized` | MEMORY_OUT_OF_BOUNDS is recognised as memory exhaustion |
| `test_memory_fault_diagnostic_is_recognized` | Out-of-bounds memory-fault diagnostic is recognised |
| `test_fuel_exhaustion_is_not_classified_as_memory_failure` | Fuel exhaustion is not mistaken for memory exhaustion |

### 13.4 Why infinite-loop tests use a high fuel allowance

A timeout is a maximum permitted execution duration. It does not mean that every short Python program should run for at least the timeout duration.

A trivial statement can complete in less than 50 milliseconds and correctly return `ok`.

The timeout tests therefore use an infinite guest loop and a high explicit fuel budget so that the wall-clock deadline can interrupt execution.

The host CPython process must never execute the infinite loop directly.

### 13.5 Repeated timeout recovery test

The repeated-timeout test performs 20 interrupted guest executions.

After all 20 timeouts, it executes a normal Python program and verifies that it still succeeds.

Expected recovery output:

```text
recovered
```

This checks that repeated epoch interruptions do not prevent subsequent normal executions in the tested environment.

### 13.6 API tests

File:

```text
backend/tests/test_api.py
```

The API tests cover the execution and health endpoints, including request validation and execution response behaviour.

### 13.7 Plugin API tests

File:

```text
backend/tests/test_plugins_api.py
```

The plugin API tests cover:

- Saving plugins.
- Listing plugins.
- Plugin validation.
- Empty or whitespace-only code rejection.
- Oversized code rejection.
- Missing request fields.
- Webhook execution.
- Unknown plugin IDs.
- Guest runtime error handling.
- Positive execution-time reporting.
- Positive memory reporting after successful execution.

The webhook test now checks:

```python
assert data["exec_ms"] > 0
assert data["mem_bytes"] > 0
```

This verifies that measured runtime information is returned rather than a hard-coded zero.

### 13.8 Security tests

File:

```text
backend/tests/test_security_plugins.py
```

The security tests cover:

| Test | Purpose |
|---|---|
| Plugin source validation | Checks that plugin files exist and contain valid Python syntax |
| Benign control | Verifies normal guest execution through `/run` |
| Password-file access attempt | Checks that guest code cannot disclose real host password-file contents |
| Network socket attempt | Checks that guest code cannot establish the tested network connection |
| Infinite-loop test | Verifies timeout handling through the actual API |
| Memory-bomb test | Reserved for separately isolated Docker verification |

The malicious Python examples are not executed directly by the host pytest process when that would risk uncontrolled resource consumption.

---

## 14. Memory-Bomb Integration Test

The memory-bomb plugin attempts to allocate large amounts of memory using repeated allocations.

It is located at:

```text
plugins/malicious/memory_bomb.py
```

### 14.1 Why the ordinary pytest test remains skipped

The memory-bomb integration test is deliberately skipped in the ordinary local pytest suite.

It should not be run directly using Windows host Python.

The test is instead executed through the WasmBox runner inside a disposable Docker container with explicit resource limits.

The skipped local test is:

```text
test_memory_bomb_is_stopped
```

The skip is intentional. The integration behaviour has been checked separately.

### 14.2 Docker resource limits

The isolated memory-bomb test used:

| Docker setting | Value |
|---|---|
| Container memory | 512 MiB |
| Container memory plus swap | 512 MiB |
| CPU limit | 1 |
| Wasmtime | 49.0.0 |
| Project default fuel | 30,000,000 |
| Project default wall timeout | 0.05 seconds |

The Docker image was built from the repository root using:

```powershell
docker build -t wasmbox-memory-test -f backend/Dockerfile .
```

The build completed successfully.

### 14.3 Production-default verification

The final memory-bomb integration test deliberately used:

```python
result = run_plugin(artifact)
```

No custom fuel or timeout arguments were supplied.

This confirms the test used the defaults imported from the rebuilt runner.

Observed configuration:

```text
WASMTIME: 49.0.0
DEFAULT FUEL: 30000000
DEFAULT WALL TIMEOUT: 0.05
```

Observed result:

```text
STATUS: memory_exceeded
STDOUT: ''
STDERR: Execution stopped: sandbox memory limit exceeded.
EXECUTION MS: 1.99
WASM MEMORY: 2293760
PROCESS SURVIVED
Docker exit code: 0
```

### 14.4 Interpretation

The result demonstrates that:

1. The actual memory-bomb plugin was executed through the WasmBox runner.
2. The production-default fuel and timeout values were used.
3. Wasmtime 49.0.0 was used.
4. The runner classified the observed memory trap as `memory_exceeded`.
5. The container process survived the execution.
6. Docker returned exit code 0.

The reported WASM memory size was:

```text
2,293,760 bytes
```

This is the observed current exported WASM linear-memory size, not the total memory available to the container and not peak Python heap consumption.

---

## 15. Additional Docker Behaviour Tests

Normal execution and timeout behaviour were also checked separately using Wasmtime 49.0.0 and a 30-million fuel budget.

The container was restricted using:

```text
--memory=512m
--memory-swap=512m
--cpus=1
```

### Test 1 — Simple Python print

Guest source:

```python
print("hello from wasm")
```

Observed output:

```text
STATUS: ok
STDOUT: 'hello from wasm\n'
STDERR:
EXECUTION MS: 0.93
```

Result: **Passed**

### Test 2 — Small calculation

Guest source:

```python
total = 0

for number in range(1, 1001):
    total += number

print("sum:", total)
```

Observed output:

```text
STATUS: ok
STDOUT: 'sum: 500500\n'
STDERR:
EXECUTION MS: 1.25
```

Result: **Passed**

### Test 3 — Infinite loop

Guest source:

```python
while True:
    pass
```

Observed output:

```text
STATUS: timeout
STDOUT: ''
STDERR: Execution timed out: wall-clock or instruction fuel limit exceeded.
EXECUTION MS: 2.91
```

Result: **Passed**

### Summary

| Test | Expected status | Observed status |
|---|---|---|
| Simple print | `ok` | `ok` |
| Small calculation | `ok` | `ok` |
| Infinite loop | `timeout` | `timeout` |
| Memory bomb | `memory_exceeded` | `memory_exceeded` |

All four observed behaviours matched the expected status.

---

## 16. Wasmtime Version Compatibility Verification

The project dependency remains:

```text
wasmtime==49.0.0
```

During investigation, Wasmtime 50.0.1 was temporarily installed inside disposable Docker containers for diagnostic comparisons.

The final compatibility tests were also performed using Wasmtime 49.0.0.

The following behaviours were confirmed on 49.0.0:

| Behaviour | Result |
|---|---|
| Memory-bomb classification | `memory_exceeded` |
| Normal print execution | `ok` |
| Small calculation | `ok` |
| Infinite-loop interruption | `timeout` |
| Container process survival | Yes |

The final production-default memory-bomb test used the existing 49.0.0 dependency.

No Wasmtime dependency upgrade is included in this change.

---

## 17. Docker Configuration

Backend Dockerfile:

```text
backend/Dockerfile
```

The container uses:

```dockerfile
FROM python:3.12-slim

WORKDIR /code

COPY backend/requirements.txt .

RUN python -m pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY backend/ .

COPY plugins/ /plugins

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build from the repository root:

```powershell
docker build -t wasmbox-memory-test -f backend/Dockerfile .
```

The Docker build was completed successfully during verification.

### Docker Compose

The root `docker-compose.yml` defines the backend build context and port mapping.

The backend is exposed on port 8000.

---

## 18. Reproducing the Verification

Run the following from the repository root.

### Step 1 — Activate the virtual environment

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### Step 2 — Install backend requirements

```powershell
python -m pip install -r backend/requirements.txt
```

### Step 3 — Run the complete test suite

```powershell
python -m pytest -q
```

Expected latest verified result:

```text
75 passed, 1 skipped, 1 warning
```

Test results can vary if the code, environment or dependency versions change.

### Step 4 — Check whitespace and patch formatting

```powershell
git diff --check
```

For staged changes:

```powershell
git diff --cached --check
```

### Step 5 — Rebuild the Docker image

```powershell
docker build -t wasmbox-memory-test -f backend/Dockerfile .
```

### Step 6 — Run isolated malicious-plugin tests

Memory-bomb tests must run inside a disposable Docker container with explicit memory, swap and CPU limits.

Do not run the memory-bomb plugin using ordinary host CPython.

---

## 19. Known Limitations and Engineering Review Points

The implementation and tests have been verified, but the following items require additional engineering review.

### 19.1 Default wall-clock timeout

Current configuration:

```python
DEFAULT_WALL_TIMEOUT_SECONDS = 0.05
```

The 50 ms default is aggressive.

A legitimate Python script may require more time depending on:

- Script complexity.
- Host machine performance.
- CPU contention.
- Concurrent plugin executions.
- Interpreter startup and runtime overhead.

The default should be reviewed against expected workloads before production deployment.

### 19.2 Different memory boundaries

Current configuration:

```python
DEFAULT_MEMORY_BYTES = 10 * 1024 * 1024
MICROPYTHON_HEAP_SIZE = "2M"
```

The 10 MiB Wasmtime Store limit and 2M Python heap setting are independent.

Documentation, API responses and user-facing messaging must not imply that Python code can necessarily allocate 10 MiB of Python objects.

### 19.3 MEMORY_OUT_OF_BOUNDS classification

The runner classifies recognised `MEMORY_OUT_OF_BOUNDS` diagnostics as `memory_exceeded`.

This fixed the observed MicroPython memory-exhaustion case.

However, an out-of-bounds trap could also indicate a bug or defect in the interpreter or runtime.

The classification should be reviewed to ensure that unrelated runtime failures are not incorrectly reported as memory-limit failures.

### 19.4 Private host-call registration helper

The runner currently accesses:

```python
run.__globals__.get("_define_host_call")
```

This is a private implementation detail of `micropython-wasm`.

It works with the currently installed pinned package, but an upstream package change could break it.

A supported public interface would be preferable.

### 19.5 Memory metric limitations

The current `mem_bytes` measurement is the current exported WASM linear-memory size.

It does not report:

- Peak memory consumption.
- Peak MicroPython heap usage.
- Total process RSS.
- Total Docker container memory.
- Per-plugin peak allocation.

A future memory metric should define exactly what is measured and how the measurement is made safe and reliable.

### 19.6 Concurrency testing

The shared Engine and Module architecture uses fresh Stores and Instances.

Additional stress testing should verify:

- Multiple plugins executing concurrently.
- Repeated timeout interruptions under concurrency.
- Memory-exhaustion handling during concurrent execution.
- Runtime stability when multiple requests are received.
- Epoch deadline isolation between Stores.

The existing tests establish the tested single-process behaviours but are not a complete concurrency stress test.

### 19.7 Security review

The current tests check selected attack scenarios:

- Host password-file disclosure attempt.
- Network socket access attempt.
- Infinite-loop execution.
- Memory-bomb execution.

Passing these tests does not establish that the complete runtime is free of security vulnerabilities.

Further security testing and code review are required before production use.

### 19.8 Production readiness

WasmBox remains a prototype under active engineering review.

The successful test results demonstrate the observed behaviour of the tested revision and environment.

They should not be interpreted as a full production security certification.

---

## 20. Current Change Summary

The runtime investigation and implementation introduced the following improvements:

1. Shared Wasmtime Engine and compiled MicroPython Module.
2. Fresh Store and Instance per execution.
3. Fuel-based execution control.
4. Epoch-based wall-clock interruption.
5. MicroPython heap configuration.
6. Current exported WASM linear-memory reporting.
7. Python `MemoryError` handling through a reserved exit code.
8. Classification of relevant `MEMORY_OUT_OF_BOUNDS` traps.
9. Improved timeout and memory-exhaustion diagnostics.
10. API propagation of actual memory measurements.
11. Regression tests for timeout, fuel and memory-trap behaviour.
12. Improved plugin API and security test coverage.

### Latest verification

```text
Local pytest:
75 passed
1 skipped
0 failed
1 warning

Docker:
Memory-bomb -> memory_exceeded
Normal print -> ok
Small calculation -> ok
Infinite loop -> timeout

Wasmtime:
49.0.0

Production default fuel:
30,000,000

Production default wall timeout:
0.05 seconds

Memory-bomb Docker configuration:
512 MiB memory
512 MiB memory + swap limit
1 CPU

Memory-bomb process:
Survived

Docker exit code:
0
```

---

## 21. Pull Request Review Checklist

The following items should be reviewed before merging.

| Review item | Status |
|---|---|
| Shared Engine and Module architecture | Implemented |
| Fresh Store and Instance | Implemented |
| Fuel enforcement | Implemented |
| Epoch-based timeout | Implemented |
| Memory measurement | Implemented |
| Memory-bomb classification | Implemented and Docker-tested |
| Regression tests | Added |
| Full local pytest suite | Passed |
| Docker integration verification | Passed |
| Existing Wasmtime dependency retained | Verified |
| Timeout default suitability | Requires peer review |
| MicroPython heap versus Store memory | Requires peer review |
| MEMORY_OUT_OF_BOUNDS classification | Requires peer review |
| Private host-call helper dependency | Requires peer review |
| Concurrent execution stress testing | Further testing recommended |

### Required reviewer attention

The runtime changes should receive review from the backend/security owner, particularly:

1. Is a 50 ms default wall-clock timeout suitable for intended plugin workloads?
2. Is the 2M MicroPython heap configuration appropriate alongside the 10 MiB Store memory limit?
3. Should all matching `MEMORY_OUT_OF_BOUNDS` traps be classified as `memory_exceeded`?
4. Is relying on the private `_define_host_call` helper acceptable, or should it be replaced?

---

## 22. Final Status

**The current implementation and recorded verification are complete. Peer review is required before merging.**

The latest verified test suite reports:

- 75 passed.
- 1 skipped.
- 0 failed.
- 1 non-blocking deprecation warning.

The actual memory-bomb plugin was verified inside Docker using the project's pinned Wasmtime 49.0.0 and production-default fuel and timeout settings.

Normal Python execution, a small calculation and infinite-loop interruption were also verified.

No Wasmtime dependency upgrade was made.

The runtime changes should be reviewed before being considered ready for production deployment.