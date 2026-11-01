# WasmBox Backend — Runtime, Security and Testing Documentation

> **Project:** WasmBox Sandbox
> **Component:** Python Backend and WebAssembly Runtime
> **Runtime:** FastAPI + Wasmtime + MicroPython WASI
> **Python:** 3.12
> **Current Wasmtime dependency:** 49.0.0
> **Status:** Runtime implementation and verification completed; peer review addressed, with further testing recommended.

---

## 1. Project Overview

WasmBox is a sandboxed Python execution environment. It allows users to submit Python source code and execute it inside a WebAssembly-based MicroPython interpreter.

The backend is responsible for:

- Receiving Python execution requests.
- Validating plugin artifacts.
- Executing Python code inside the MicroPython WASI interpreter.
- Enforcing execution-time, instruction-fuel and memory limits.
- Capturing standard output and standard error.
- Reporting execution status, execution time and memory usage.
- Managing saved plugins and webhook execution.
- Restricting guest access to host resources.

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

Dependency decision: Wasmtime remains pinned to 49.0.0. The memory-exhaustion fix was tested using this dependency; no dependency upgrade was required.

## 3. Backend Directory Structure

Relevant backend structure:

```text
wasmbox-sandbox/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── runtime/
│   │   │   ├── micropython_runner.py
│   │   │   ├── _temp_packager.py
│   │   │   ├── artifacts/
│   │   │   │   └── micropython-wasi.wasm
│   │   │
│   │   └── main.py
│   │
│   ├── scripts/
│   ├── tests/
│   │   ├── test_api.py
│   │   ├── test_limits.py
│   │   ├── test_plugins_api.py
│   │   ├── test_security_plugins.py
│   │   └── test_unusual_inputs.py
│   │
│   ├── Dockerfile
│   └── requirements.txt
│
├── plugins/
│   ├── benign/
│   └── malicious/
│
├── docs/
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
| `backend/tests/test_limits.py` | Resource-limit, timeout and memory-classification tests |
| `backend/tests/test_security_plugins.py` | Security and malicious-plugin tests |
| `backend/tests/test_plugins_api.py` | Plugin storage and webhook API tests |

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

The Store and Instance are created separately for each run. This is intended to provide execution-state separation while reusing the compiled interpreter.

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

## 6. Resource-Limit Configuration

The runtime configuration is maintained in:

`backend/app/runtime/micropython_runner.py`

The documented defaults are:

| Configuration | Value | Purpose |
|---|---|---|
| `DEFAULT_MEMORY_BYTES` | 10 MiB | Wasmtime Store memory-size limit |
| `DEFAULT_FUEL` | 30,000,000 | Instruction-fuel budget |
| `DEFAULT_WALL_TIMEOUT_SECONDS` | 0.25 seconds | Default wall-clock timeout |
| `MICROPYTHON_HEAP_SIZE` | `2M` | MicroPython Python heap |
| `TICK_INTERVAL_SECONDS` | 0.005 seconds | Epoch ticker interval |
| `WASM_PAGE_BYTES` | 65,536 bytes | WASM memory-page size |
| `HOST_RESULT_BYTES` | 262,144 bytes | Host-call result buffer configuration |
| `config.max_wasm_stack` | 512 KiB | Maximum WASM stack configuration |

The Store also applies resource limits:

| Store resource | Limit |
|---|---|
| Instances | 1 |
| Memories | 1 |
| Tables | 8 |
| Table elements | 10,000 |

### 6.1 Important distinction: 10 MiB versus 2 MiB

There are two separate memory configurations.

Wasmtime Store memory limit:

```python
DEFAULT_MEMORY_BYTES = 10 * 1024 * 1024
```

MicroPython Python heap:

```python
MICROPYTHON_HEAP_SIZE = "2M"
```

These are not the same thing.

The 10 MiB setting is passed to Wasmtime through the Store resource limits. It is a Store memory-size limit; it should not be described as a configured maximum WASM page count or as a guarantee that Python scripts can allocate 10 MiB of Python objects.

The `2M` heap setting configures the memory available to Python objects managed by MicroPython.

MicroPython can therefore exhaust its usable Python heap before the Wasmtime Store reaches its configured 10 MiB memory-size limit.

During the isolated memory-bomb verification, the observed current exported WASM linear-memory size was approximately 2,293,760 bytes. This includes interpreter and runtime memory overhead; it is not a direct measurement of Python heap consumption.

Important: The effective Python allocation constraint observed in this test was the MicroPython heap configuration, not the 10 MiB Store ceiling.

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

`mem_bytes` reports the current exported WASM linear-memory size when it is measured.

It is not:

- Peak memory consumption.
- Total host-process memory.
- Total Docker container memory.
- A direct measurement of Python objects allocated by MicroPython.
- Maximum memory consumption during the entire execution.

If an instance is not available or memory introspection fails, the returned value may be zero.

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

## 8. Wall-Clock Timeout and Epoch Interruption

The recommended default wall-clock timeout is 250 milliseconds.

```python
DEFAULT_WALL_TIMEOUT_SECONDS = 0.25
```

The 250 ms default provides more execution headroom for legitimate short-running Python programs than the previous 50 ms setting.

It is not a hard real-time guarantee.

### 8.1 Why the default changed

The previous 50 ms default was considered too aggressive for a general-purpose Python execution environment.

A short but legitimate computation could be interrupted unnecessarily, depending on runtime overhead and host-system conditions.

Vineet's review recommended increasing the default to 250 ms before merging.

This change improves the available execution window, but does not guarantee that every program completing within 250 ms of ideal execution time will succeed.

### 8.2 Epoch interruption

The runner enables:

```python
config.epoch_interruption = True
```

A shared background daemon thread advances the Engine epoch approximately every 5 milliseconds.

The ticker interval is:

```python
TICK_INTERVAL_SECONDS = 0.005
```

### 8.3 Per-execution deadline

For each run, the runner calculates a deadline based on the requested timeout.

The number of ticks is derived from:

```python
math.ceil(
    wall_timeout_seconds / TICK_INTERVAL_SECONDS
)
```

The deadline is set before instantiation because instantiation itself executes WebAssembly.

A lock synchronizes deadline configuration with epoch increments.

### 8.4 Timeout behaviour

The runner recognizes timeout-related diagnostics, including:

- WASM interrupt traps.
- Epoch deadline interruptions.
- Wasmtime interrupt trap codes.
- Fuel exhaustion.
- Out-of-fuel diagnostics.

These failures are reported as:

```python
status = "timeout"
```

### 8.5 Timeout limitations

The 250 ms timeout is a configured execution limit, not a hard real-time guarantee.

Actual interruption behaviour can be influenced by:

- Thread scheduling.
- Epoch-ticker timing.
- Host system load.
- Runtime overhead.
- WebAssembly instruction execution.

The default should be evaluated against actual plugin workloads.

Tests that explicitly pass a 50 ms timeout remain valid for testing short-deadline interruption behaviour. Such test-specific values do not represent the recommended production default.

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

The runner defines:

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

### 9.3 Narrowed MEMORY_OUT_OF_BOUNDS classification

Vineet's review identified that classifying every `trapcode.memory_out_of_bounds` diagnostic as memory exhaustion could incorrectly classify an interpreter or runtime defect.

The fallback classification must therefore be narrow.

The detector recognizes explicit memory-growth or memory-size-limit diagnostics, such as:

```text
forcing a memory growth failure to be a trap
forcing trap when growing memory
memory size limit exceeded
memory limit exceeded
```

For the specific out-of-bounds fallback, the diagnostic must contain all three of the following markers:

```text
trapcode.memory_out_of_bounds
memory fault at wasm address
out of bounds memory access
```

A generic out-of-bounds trap without the additional memory-fault diagnostic is not sufficient.

The intended detection logic is:

```python
def _memory_limit_failure(exception_text: str) -> bool:
    """Recognize memory-limit and verified linear-memory exhaustion failures."""
    normalized = exception_text.lower()

    reliable_markers = (
        "forcing a memory growth failure to be a trap",
        "forcing trap when growing memory",
        "memory size limit exceeded",
        "memory limit exceeded",
    )

    if any(marker in normalized for marker in reliable_markers):
        return True

    if (
        "trapcode.memory_out_of_bounds" in normalized
        and "memory fault at wasm address" in normalized
        and "out of bounds memory access" in normalized
    ):
        return True

    return False
```

The Python-level `MemoryError` handling through reserved exit code 86 remains the primary classification mechanism.

### 9.4 Classification tests

The tests should verify:

| Diagnostic | Expected classification |
|---|---|
| Reserved guest memory-error exit code | `memory_exceeded` |
| Explicit Wasmtime memory-growth failure diagnostic | `memory_exceeded` |
| Out-of-bounds diagnostic containing all three required markers | `memory_exceeded` |
| Generic `trapcode.memory_out_of_bounds` without the additional address and access diagnostics | Not classified as memory exhaustion |
| Fuel-exhaustion diagnostic | `timeout`, not `memory_exceeded` |

This prevents a generic out-of-bounds trap from automatically being treated as proof of memory exhaustion.

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
| `memory_exceeded` | Recognized Python or WASM memory exhaustion |

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

These examples illustrate observed runtime outputs. Execution times are environment-dependent and should not be treated as guaranteed values.

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

The dependency is accepted for the current implementation because the package version is pinned to `micropython-wasm==0.1a2` and the existing runtime includes a compatibility guard.

A supported public API would be preferable if one becomes available. Replacing or vendoring this helper is a follow-up engineering task, not a prerequisite for the current reviewed implementation.

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

The plugin webhook response also reports execution metrics.

### API response fields

| Field | Type | Description |
|---|---|---|
| `status` | string | Execution result status |
| `stdout` | string | Captured standard output |
| `stderr` | string | Captured standard error |
| `exec_ms` | number | Execution duration in milliseconds |
| `mem_bytes` | integer | Current exported WASM linear-memory size in bytes |

## 13. Automated Test Coverage

The backend test suite verifies API behaviour, plugin handling, execution limits and selected security restrictions.

### 13.1 Latest complete local test result

Command:

```bash
python -m pytest -q
```

Latest recorded output:

```text
..................................................................s
..........                                                           [100%]

76 passed, 1 skipped, 1 warning in 4.90s
```

Summary:

| Result | Count |
|---|---|
| Passed | 76 |
| Skipped | 1 |
| Failed | 0 |
| Warnings | 1 |
| Total collected | 77 |

The suite completed successfully.

The skipped test is intentional and is reserved for isolated Docker verification of the memory-bomb plugin.

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

The resource-limit test module covers:

| Test area | What it verifies |
|---|---|
| Short wall timeout | Infinite guest execution is interrupted by a short wall-clock deadline |
| Normal execution timing | Successful execution returns stdout and a positive execution time |
| Fuel exhaustion | Instruction-fuel exhaustion produces timeout status |
| Infinite-loop interruption | Infinite-loop execution is stopped |
| Repeated timeout recovery | Runtime remains usable after repeated interruptions |
| Memory diagnostic classification | Verified memory-exhaustion diagnostics are recognized |
| Generic out-of-bounds diagnostic | An unrelated generic out-of-bounds trap is not automatically classified as memory exhaustion |
| Fuel versus memory classification | Fuel exhaustion is not mistaken for memory exhaustion |

### 13.4 Why infinite-loop tests use explicit timeout values

A timeout is a maximum permitted execution duration. It does not mean every short Python program should run for at least the timeout duration.

A trivial statement can complete in less than 250 milliseconds and correctly return `ok`.

Timeout tests may use a shorter explicit timeout and a high fuel allowance so that the wall-clock deadline can interrupt execution.

The host CPython process must never execute an unbounded guest loop directly.

### 13.5 Repeated timeout recovery test

The repeated-timeout test performs 20 interrupted guest executions.

After all 20 timeouts, it executes a normal Python program and verifies that it still succeeds.

Expected recovery output:

```text
recovered
```

This checks that repeated epoch interruptions do not prevent subsequent normal executions in the tested environment.

It is sequential coverage, not a complete concurrent stress test.

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

The webhook test checks:

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

The security assertions should reflect the statuses actually emitted by the runner. For the tested password-file and network attempts, the expected status is `error`, not `denied`.

The malicious Python examples are not executed directly by the host pytest process when that would risk uncontrolled resource consumption.

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

```python
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
| Project default fuel at time of test | 30,000,000 |
| Project default wall timeout at time of test | 0.05 seconds |

The Docker image was built from the repository root using:

```bash
docker build -t wasmbox-memory-test -f backend/Dockerfile .
```

The build completed successfully.

### 14.3 Recorded production-default verification

The memory-bomb integration test used:

```python
result = run_plugin(artifact)
```

No custom fuel or timeout arguments were supplied.

The recorded configuration at the time of this test was:

```text
WASMTIME: 49.0.0
DEFAULT FUEL: 30000000
DEFAULT WALL TIMEOUT: 0.05
```

Recorded result:

```text
STATUS: memory_exceeded
STDOUT: ''
STDERR: Execution stopped: sandbox memory limit exceeded.
EXECUTION MS: 1.99
WASM MEMORY: 2293760
PROCESS SURVIVED
Docker exit code: 0
```

### 14.4 Interpretation and verification boundary

The result demonstrates that, with the configuration used at the time:

1. The actual memory-bomb plugin was executed through the WasmBox runner.
2. The configured default fuel and timeout values were used.
3. Wasmtime 49.0.0 was used.
4. The runner classified the observed memory failure as `memory_exceeded`.
5. The container process survived the execution.
6. Docker returned exit code 0.

The reported WASM memory size was:

```text
2,293,760 bytes
```

This is the observed current exported WASM linear-memory size, not the total memory available to the container and not peak Python heap consumption.

Important review clarification: The recorded Docker memory-bomb test used the earlier 50 ms default. The recommended default has since been increased to 250 ms following Vineet's review. The Docker integration test should be rerun after the timeout change so that the final report can claim verification using the final default configuration.

The earlier result remains useful evidence for the memory-classification behaviour under its recorded configuration. It must not be presented as a test performed with the updated 250 ms default.

## 15. Additional Docker Behaviour Tests

Normal execution and timeout behaviour were also checked separately using Wasmtime 49.0.0 and a 30-million fuel budget.

The container was restricted using:

```bash
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

Result: Passed

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

Result: Passed

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

Result: Passed

### Summary

| Test | Expected status | Observed status |
|---|---|---|
| Simple print | `ok` | `ok` |
| Small calculation | `ok` | `ok` |
| Infinite loop | `timeout` | `timeout` |
| Memory bomb | `memory_exceeded` | `memory_exceeded` |

The recorded behaviours matched the expected statuses under the configurations used for those tests.

The memory-bomb result used the earlier 50 ms default, as documented in Section 14.

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

The final recorded memory-bomb test used the existing 49.0.0 dependency.

No Wasmtime dependency upgrade is included in this change.

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

```bash
docker build -t wasmbox-memory-test -f backend/Dockerfile .
```

The Docker build was completed successfully during verification.

### Docker Compose

The root `docker-compose.yml` defines the backend build context and port mapping.

The backend is exposed on port 8000.

## 18. Reproducing the Verification

Run the following from the repository root.

### Step 1 — Activate the virtual environment

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### Step 2 — Install backend requirements

```bash
python -m pip install -r backend/requirements.txt
```

### Step 3 — Run the complete test suite

```bash
python -m pytest -q
```

Latest recorded result:

```text
76 passed, 1 skipped, 1 warning
```

Test results can vary if the code, environment or dependency versions change.

### Step 4 — Check whitespace and patch formatting

```bash
git diff --check
```

For staged changes:

```bash
git diff --cached --check
```

### Step 5 — Rebuild the Docker image

```bash
docker build -t wasmbox-memory-test -f backend/Dockerfile .
```

### Step 6 — Run isolated malicious-plugin tests

Memory-bomb tests must run inside a disposable Docker container with explicit memory, swap and CPU limits.

Do not run the memory-bomb plugin using ordinary host CPython.

After changing the default timeout from 50 ms to 250 ms, repeat the isolated memory-bomb test with no custom timeout or fuel arguments. Record the actual configuration and output.

## 19. Known Limitations and Engineering Review Points

The implementation and tests have been reviewed, but the following items remain relevant engineering considerations.

### 19.1 Default wall-clock timeout

Current recommended configuration:

```python
DEFAULT_WALL_TIMEOUT_SECONDS = 0.25
```

The previous 50 ms default was considered too aggressive for general plugin workloads.

The 250 ms setting provides additional execution headroom but is not a hard real-time guarantee.

A legitimate Python script may still require more time depending on:

- Script complexity.
- Host machine performance.
- CPU contention.
- Concurrent plugin executions.
- Interpreter startup and runtime overhead.

The Docker memory-bomb integration test must be repeated with the updated default before documenting it as verified under that configuration.

### 19.2 Different memory boundaries

Current configuration:

```python
DEFAULT_MEMORY_BYTES = 10 * 1024 * 1024
MICROPYTHON_HEAP_SIZE = "2M"
```

The 10 MiB Wasmtime Store memory-size limit and 2M MicroPython Python heap are independent.

The effective Python allocation constraint observed in the memory-bomb test was the MicroPython heap configuration.

Documentation, API responses and user-facing messaging must not imply that Python code can necessarily allocate 10 MiB of Python objects.

### 19.3 MEMORY_OUT_OF_BOUNDS classification

The runner must not classify every generic `MEMORY_OUT_OF_BOUNDS` trap as `memory_exceeded`.

The primary signal is the guest `MemoryError` handled through the reserved exit code.

The fallback diagnostic requires all three markers:

- `trapcode.memory_out_of_bounds`
- `memory fault at wasm address`
- `out of bounds memory access`

Explicit memory-growth and memory-size-limit diagnostics are also recognized.

Regression tests should ensure that a generic out-of-bounds trap without the additional evidence is not classified as memory exhaustion.

This reduces the risk of reporting an interpreter or runtime defect as a resource-limit event.

### 19.4 Private host-call registration helper

The runner currently accesses:

```python
run.__globals__.get("_define_host_call")
```

This is a private implementation detail of `micropython-wasm`.

It works with the currently installed pinned package, but an upstream package change could break it.

The current implementation is accepted for this change with the package pinned to `0.1a2`.

A supported public interface or a maintained local helper would be preferable as a future improvement.

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

The existing sequential repeated-timeout test provides useful recovery coverage, but it is not a complete concurrency stress test.

Additional testing should verify:

- Multiple plugins executing concurrently.
- Repeated timeout interruptions under concurrency.
- Memory-exhaustion handling during concurrent execution.
- Runtime stability when multiple requests are received.
- Epoch deadline isolation between Stores.

A concurrent two-to-four-run stress test is recommended as follow-up work.

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

## 20. Current Change Summary

The runtime investigation and implementation introduced the following improvements:

1. Shared Wasmtime Engine and compiled MicroPython Module.
2. Fresh Store and Instance per execution.
3. Fuel-based execution control.
4. Epoch-based wall-clock interruption.
5. MicroPython heap configuration.
6. Current exported WASM linear-memory reporting.
7. Python `MemoryError` handling through a reserved exit code.
8. Narrow classification of relevant `MEMORY_OUT_OF_BOUNDS` diagnostics.
9. Improved timeout and memory-exhaustion diagnostics.
10. API propagation of actual memory measurements.
11. Regression tests for timeout, fuel and memory-trap behaviour.
12. Improved plugin API and security test coverage.

### Latest local verification

```text
Local pytest:

76 passed
1 skipped
0 failed
1 warning
```

### Recorded Docker verification

```text
Memory-bomb -> memory_exceeded
Normal print -> ok
Small calculation -> ok
Infinite loop -> timeout
```

### Runtime dependency

```text
Wasmtime:

49.0.0
```

### Recommended runtime defaults

```text
Fuel:

30,000,000

Wall timeout:

0.25 seconds

Wasmtime Store memory-size limit:

10 MiB

MicroPython Python heap:

2M
```

### Recorded memory-bomb Docker configuration

```text
512 MiB container memory
512 MiB memory + swap limit
1 CPU
```

The recorded memory-bomb run used the earlier 50 ms timeout default. It must be repeated with the recommended 250 ms default to establish final-default verification.

## 21. Pull Request Review Summary

Vineet reviewed the runtime implementation and approved the architecture, with minor changes and follow-up recommendations.

| Review item | Resolution |
|---|---|
| Shared Engine and Module architecture | Accepted |
| Fresh Store and Instance | Accepted |
| Fuel enforcement | Implemented |
| Epoch-based timeout | Implemented |
| Default wall timeout of 50 ms | Increase to 250 ms before merging |
| MicroPython heap versus Store memory | Clarified in documentation |
| Broad out-of-bounds memory classification | Narrowed to require all three diagnostic markers |
| Reserved guest MemoryError exit code | Retained as primary memory-exhaustion signal |
| Private host-call helper | Accepted for this PR with pinned package version; future improvement recommended |
| Repeated timeout recovery | Sequential test coverage added |
| Concurrent execution stress testing | Recommended follow-up |
| Full local pytest suite | Passed |
| Docker integration verification | Passed under the previously recorded configuration |
| Final-default Docker memory-bomb verification | Repeat after applying the 250 ms default |

### Review decisions and remaining work

Before merging:

1. Confirm `DEFAULT_WALL_TIMEOUT_SECONDS` is `0.25` in the runtime code.
2. Confirm the memory detector uses the narrowed diagnostic checks.
3. Confirm regression tests cover both the positive diagnostic and generic out-of-bounds negative case.
4. Run the full pytest suite.
5. Repeat the isolated Docker memory-bomb test using the updated default timeout.
6. Record the actual final Docker configuration and result.

The following are recommended follow-up improvements rather than blockers identified for this PR:

- Add concurrent execution stress tests.
- Replace the private host-call helper with a supported public API if available.
- Investigate a reliable peak-memory measurement.

## 22. Final Status

The runtime implementation has passed the current local test suite and received peer review. The review changes must be reflected in the final code and the Docker memory-bomb test should be repeated with the updated default before final merge verification.

Latest recorded local test result:

- 76 passed.
- 1 skipped.
- 0 failed.
- 1 non-blocking deprecation warning.

The actual memory-bomb plugin was verified inside Docker using the project's pinned Wasmtime 49.0.0. That recorded run used the earlier 50 ms wall-timeout default.

Normal Python execution, a small calculation and infinite-loop interruption were also verified.

No Wasmtime dependency upgrade was made.

The runtime remains a prototype and should not be considered production security-certified.