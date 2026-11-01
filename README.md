# WasmBox

WasmBox is a WebAssembly-based Python plugin sandbox built with **Wasmtime, a MicroPython WASI runtime, FastAPI, React, and Monaco Editor**.

It provides a developer portal and backend API for submitting Python source code and executing it inside a WebAssembly runtime with resource limits and restricted host capabilities.

WasmBox is a working prototype. Its execution controls, selected security restrictions and resource-limit behaviour have been tested. However, it still has known limitations and should not be treated as a production-ready security boundary without further validation.

---

## Folders

| Folder | What it holds | Owner |
|---|---|---|
| `backend/app/api/` | FastAPI web server and API request/response handling | Vineet |
| `backend/app/runtime/` | WebAssembly execution and MicroPython runner | Prathamesh |
| `backend/tests/` | Automated API, runtime and security tests | Priya |
| `backend/scripts/` | Helper scripts and runtime demonstrations | Prathamesh |
| `frontend/` | React and Monaco-based developer portal | Sashmita |
| `plugins/benign/` | Benign WebAssembly test programs | Prathamesh |
| `plugins/malicious/` | Security probes used to test restricted behaviour | Priya |
| `docs/` | Architecture, API contract, security findings and spike reports | Everyone |

---

## Prerequisites

- Python 3.12
- Node.js and npm
- Git
- Docker Desktop (required for isolated memory-bomb integration testing)
- Windows PowerShell, Git Bash or another terminal compatible with the setup commands

---

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd wasmbox-sandbox
```

Replace `<repository-url>` with the repository's Git URL.

### 2. Create and activate a Python virtual environment

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

### 3. Install backend dependencies

From the repository root:

```bash
python -m pip install -r backend/requirements.txt
```

The backend dependencies are pinned in `backend/requirements.txt`.

Important dependencies include:

| Package          | Version |
| ---------------- | ------- |
| Wasmtime         | 49.0.0  |
| micropython-wasm | 0.1a2   |
| FastAPI          | 0.115.0 |
| Uvicorn          | 0.30.6  |
| Pydantic         | 2.9.2   |
| pytest           | 8.3.3   |
| httpx            | 0.27.2  |

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Run the application

Start the backend and frontend in separate terminal windows.

### Backend

From the repository root, with the Python virtual environment activated:

```bash
python -m uvicorn app.main:app --app-dir backend --reload
```

The backend should be available at:

`http://127.0.0.1:8000`

Check the health endpoint:

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

```bash
cd frontend
npm run dev
```

Open the local URL printed by Vite, typically:

`http://localhost:5173`

The frontend requires the backend to be running for API operations. If the API is unavailable, the UI should communicate the failure rather than presenting an unsuccessful request as successful execution.

---

## API overview

The backend exposes the following primary endpoints:

| Endpoint              | Purpose                                                         |
| --------------------- | --------------------------------------------------------------- |
| `GET /health`         | Checks whether the backend is responding                        |
| `POST /run`           | Submits Python source code for execution and returns the result |
| `POST /plugins`       | Saves a plugin                                                  |
| `GET /plugins`        | Lists saved plugins                                             |
| `POST /webhooks/{id}` | Executes a saved plugin through its webhook                     |

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

A successful execution returns a response containing fields such as:

| Field       | Description                                       |
| ----------- | ------------------------------------------------- |
| `status`    | Execution outcome                                 |
| `stdout`    | Captured standard output                          |
| `stderr`    | Captured standard error                           |
| `exec_ms`   | Measured elapsed execution time in milliseconds   |
| `mem_bytes` | Current exported WASM linear-memory size in bytes |

### Execution statuses

| Status            | Meaning                                                            |
| ----------------- | ------------------------------------------------------------------ |
| `ok`              | Execution completed successfully                                   |
| `error`           | Python execution or another ordinary runtime operation failed      |
| `denied`          | An operation was explicitly denied where supported by the API      |
| `timeout`         | A configured execution time or instruction-fuel limit was exceeded |
| `memory_exceeded` | A recognised memory-exhaustion condition was detected              |

Refer to [API_CONTRACT.md](docs/API_CONTRACT.md) for the complete request and response contract, validation behaviour and error handling.

---

## How execution works

WasmBox uses a repository-managed MicroPython WASI interpreter to execute submitted Python source code.

The Python source is stored inside a WebAssembly custom section named:

`wasmbox_script`

The source is not compiled into a new WASM module for every execution. Instead, the existing MicroPython WASI interpreter reads and executes the packaged source.

### Execution pipeline

1. The client submits Python source code to the backend.
2. FastAPI validates the incoming request.
3. The packaging layer embeds the source in the `wasmbox_script` custom WASM section.
4. The runner extracts the Python source from the artifact.
5. A shared Wasmtime Engine and compiled MicroPython Module are reused.
6. A fresh Wasmtime Store and Instance are created for each execution.
7. Fuel, memory and wall-clock interruption limits are configured.
8. Wasmtime executes the MicroPython WASI interpreter.
9. The runner captures standard output and standard error.
10. The runner measures current exported WASM linear memory when available.
11. The execution result is returned through the API.

### Runtime architecture

The current runner uses:

- One lazily initialized shared Wasmtime Engine.
- One compiled MicroPython WASM Module.
- A fresh Store for every execution.
- A fresh Instance for every execution.
- A shared background Engine epoch ticker for wall-clock interruption.

Reusing the Engine and compiled Module avoids recompiling the interpreter for every plugin execution.

Fresh Stores and Instances provide separate execution state for individual plugin runs.

The Engine and compiled Module initialization are excluded from `exec_ms`. The measurement includes instantiation and guest execution.

See [PIPELINE.md](docs/PIPELINE.md) for the detailed execution pipeline.

---

## Security and resource limits

WasmBox uses WebAssembly execution and explicit runtime configuration to restrict the capabilities and resources available to submitted code.

The current recommended runtime configuration is:

| Configuration               | Value            | Purpose                                             |
| --------------------------- | ---------------- | --------------------------------------------------- |
| Wasmtime Store memory limit | 10 MiB           | Configures the Store memory-size limit              |
| MicroPython heap            | 2M               | Configures the Python heap available to MicroPython |
| Instruction fuel            | 30,000,000       | Limits WebAssembly instruction execution            |
| Default wall-clock timeout  | 250 milliseconds | Configures epoch-based execution interruption       |
| Epoch ticker interval       | 5 milliseconds   | Advances the shared Engine epoch                    |
| Maximum WASM stack          | 512 KiB          | Configures maximum WASM stack size                  |
| Instances per Store         | 1                | Limits instance creation                            |
| Memories per Store          | 1                | Limits memory creation                              |
| Tables per Store            | 8                | Limits table creation                               |
| Table elements              | 10,000           | Limits table elements                               |

### Important: WASM memory and MicroPython heap are different

The 10 MiB Wasmtime Store memory-size limit and the 2M MicroPython heap setting are separate limits.

The Store limit applies to WebAssembly memory managed by Wasmtime. It is a Store resource limit, not a configured maximum WASM page count.

The MicroPython heap setting controls the memory available to Python objects managed by MicroPython.

As a result, MicroPython can encounter a Python heap allocation failure before the Store reaches its configured 10 MiB limit.

The 10 MiB Store limit must not be interpreted as a guarantee that a Python script can allocate 10 MiB of Python objects.

During the isolated memory-bomb test, the observed current exported WASM linear-memory size was approximately 2,293,760 bytes. This includes interpreter and runtime overhead; it is not a direct measurement of Python heap consumption.

### Fuel limit

Wasmtime instruction-fuel consumption is enabled.

The current default is:

`30,000,000`

When a guest program exhausts its allocated fuel, execution is stopped and classified as `timeout`.

### Wall-clock timeout

Epoch-based interruption is enabled.

The recommended default timeout is:

`0.25 seconds`

A shared daemon thread advances the Wasmtime Engine epoch approximately every 5 milliseconds.

Each Store receives an epoch deadline calculated from the requested execution timeout.

The previous 50 ms default was considered too aggressive for general plugin workloads. The 250 ms recommendation provides additional execution headroom for legitimate short-running programs.

The configured timeout is not a hard real-time guarantee. Actual interruption behaviour depends on epoch-ticker timing, thread scheduling, runtime overhead and host-system load.

Tests may still use an explicitly configured shorter timeout, such as 50 ms, to verify interruption behaviour. Such test-specific values are not the recommended default.

### Memory-exhaustion handling

The runner uses a reserved guest exit code to identify a Python-level `MemoryError`:

```python
MEMORY_ERROR_EXIT_CODE = 86
```

The guest wrapper handles an uncaught `MemoryError` by raising:

```python
raise SystemExit(86)
```

The host runner recognizes this reserved exit code and returns:

`memory_exceeded`

The runner also recognises explicit Wasmtime memory-growth and memory-size-limit diagnostics.

For the `MEMORY_OUT_OF_BOUNDS` fallback, classification is deliberately narrow. The diagnostic must contain all three markers:

- `trapcode.memory_out_of_bounds`
- `memory fault at wasm address`
- `out of bounds memory access`

A generic out-of-bounds trap without all three markers is not sufficient to classify the failure as memory exhaustion.

This distinction matters because an out-of-bounds trap can also indicate an interpreter or runtime defect unrelated to resource exhaustion.

The reserved guest `MemoryError` exit code remains the primary memory-exhaustion signal.

### Memory reporting

The API reports `mem_bytes` using the current exported WASM linear-memory size.

The measurement is calculated from the number of allocated WASM memory pages multiplied by 65,536 bytes per page.

It is important to understand what this metric does and does not represent.

It reports:

- Current exported WASM linear-memory size when measurement is available.

It does not report:

- Peak memory consumption.
- Peak MicroPython heap usage.
- Total host-process memory.
- Total Docker container memory.
- Maximum memory usage during the entire execution.

If an instance is unavailable or memory introspection fails, the reported value may be zero.

### Restricted host capabilities

The current runner:

- Does not configure filesystem directory preopens.
- Uses an empty WASI environment-variable list.
- Does not supply application host functions to guest scripts through the registered host-call mapping.
- Captures standard output and standard error.

Security tests have checked selected filesystem and network access attempts.

These checks provide evidence for the tested scenarios. They are not an exhaustive security audit.

### Runtime security limitations

A WebAssembly runtime does not automatically make every workload secure.

The sandbox remains a prototype. Further security review, concurrency testing and validation are required before using it as the sole security boundary for untrusted multi-tenant workloads.

See [SECURITY.md](docs/SECURITY.md) for tested security behaviour, evidence and known gaps.

See [SPIKES.md](docs/SPIKES.md) for runtime experiments and timing observations.

---

## Tests and verification

Run the backend test suite from the repository root with the virtual environment activated:

```bash
python -m pytest -q
```

### Latest backend test results

The latest recorded full-suite result is:

76 passed, 1 skipped, 0 failed, 1 warning.

Recorded execution time:

`4.90 seconds`

The warning is a Starlette/AnyIO deprecation warning concerning the deprecated `anyio.abc.BlockingPortal` alias.

It did not cause a test failure.

### Skipped test

One test is intentionally skipped:

`test_memory_bomb_is_stopped`

The memory-bomb integration test is not executed directly during ordinary local pytest runs because uncontrolled memory allocation can put the development host at risk.

It is tested separately inside a disposable Docker container with explicit resource limits.

### Automated test coverage

The backend test suite covers the following areas:

| Test file                                | Coverage                                                                                                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `backend/tests/test_api.py`              | API request handling, execution responses and health endpoint                                                               |
| `backend/tests/test_limits.py`           | Wall-clock timeout, fuel exhaustion, repeated timeouts, memory-trap classification                                          |
| `backend/tests/test_plugins_api.py`      | Plugin save/list, input validation, webhook execution and execution metrics                                                 |
| `backend/tests/test_security_plugins.py` | Benign plugin execution, selected filesystem and network restrictions, infinite-loop timeout and memory-bomb test isolation |
| `backend/tests/test_unusual_inputs.py`   | Unusual inputs, formatting, Unicode and edge cases                                                                          |

### Resource-limit regression tests

The resource-limit test module includes checks for:

- Short wall-clock timeout behaviour.
- Normal execution and elapsed-time reporting.
- Instruction-fuel exhaustion.
- Infinite-loop interruption.
- Runtime recovery after 20 consecutive timeouts.
- Recognition of verified memory-exhaustion diagnostics.
- Rejection of generic out-of-bounds diagnostics as sufficient memory-exhaustion evidence.
- Ensuring fuel exhaustion is not incorrectly classified as memory exhaustion.

The infinite-loop tests use explicit wall-clock limits and high fuel budgets so that the guest execution can reach the wall-clock interruption.

A trivial Python statement is expected to finish normally before a timeout deadline. A timeout is a maximum allowed execution duration, not a minimum execution duration.

### Plugin API test coverage

Plugin API tests verify:

- Saving plugins.
- Listing plugins.
- Empty and whitespace-only code rejection.
- Oversized code rejection.
- Missing required request fields.
- Webhook execution.
- Unknown plugin ID handling.
- Guest runtime error handling.
- Positive execution-time reporting.
- Actual memory-metric propagation.

### Security test coverage

Security tests verify selected behaviours:

- Benign plugin execution.
- Plugin file existence and Python syntax validation.
- Host password-file access attempts.
- Network socket access attempts.
- Infinite-loop timeout behaviour.
- Memory-bomb integration-test isolation.

These tests demonstrate the tested behaviours but do not constitute a complete security audit.

### Frontend production build

Run the frontend production build when frontend changes are involved:

```bash
cd frontend
npm run build
cd ..
```

The frontend build is separate from backend runtime verification. A successful frontend build does not establish that backend execution or security behaviour works.

---

## Docker integration testing

The actual memory-bomb plugin is tested separately inside Docker.

The purpose is to verify memory-exhaustion handling without exposing the development host to uncontrolled allocation.

### Build the backend Docker image

From the repository root:

```bash
docker build -t wasmbox-memory-test -f backend/Dockerfile .
```

The Docker image includes the backend and plugin directory.

### Resource limits used during the recorded memory-bomb test

| Docker setting                             | Value        |
| ------------------------------------------ | ------------ |
| Container memory limit                     | 512 MiB      |
| Container memory plus swap limit           | 512 MiB      |
| CPU limit                                  | 1            |
| Wasmtime version                           | 49.0.0       |
| Default fuel at time of test               | 30,000,000   |
| Default wall-clock timeout at time of test | 0.05 seconds |

The test executes the actual:

`plugins/malicious/memory_bomb.py`

The plugin source is packaged in the `wasmbox_script` custom section and passed to the runner.

### Recorded memory-bomb integration test

The integration test intentionally called:

```python
result = run_plugin(artifact)
```

No custom fuel or timeout values were passed.

The recorded configuration was:

```
WASMTIME: 49.0.0
DEFAULT FUEL: 30000000
DEFAULT WALL TIMEOUT: 0.05
```

Observed output:

```
STATUS: memory_exceeded
STDOUT: ''
STDERR: Execution stopped: sandbox memory limit exceeded.
EXECUTION MS: 1.99
WASM MEMORY: 2293760
PROCESS SURVIVED
Docker exit code: 0
```

Result: Passed under the recorded configuration.

The memory-bomb plugin was classified as `memory_exceeded`, the container process survived and Docker returned exit code 0.

The reported `2,293,760` bytes represent current exported WASM linear memory, not peak Python heap usage or total container memory.

Verification boundary: This recorded Docker test used the earlier 50 ms default. The recommended default has since been increased to 250 ms following peer review. The Docker memory-bomb test must be repeated with the updated 250 ms default before claiming that the final default configuration has been verified.

### Additional isolated Docker tests

The following tests were also performed using Wasmtime 49.0.0 and a 30-million fuel budget.

| Test              | Guest behaviour                     | Observed status   |
| ----------------- | ----------------------------------- | ----------------- |
| Simple print      | `print("hello from wasm")`          | `ok`              |
| Small calculation | Sum of numbers from 1 through 1,000 | `ok`              |
| Infinite loop     | `while True: pass`                  | `timeout`         |
| Memory bomb       | Repeated large allocations          | `memory_exceeded` |

Observed output for the simple print test:

```
STATUS: ok
STDOUT: 'hello from wasm\n'
EXECUTION MS: 0.93
```

Observed output for the calculation test:

```
STATUS: ok
STDOUT: 'sum: 500500\n'
EXECUTION MS: 1.25
```

Observed output for the infinite-loop test:

```
STATUS: timeout
STDOUT: ''
STDERR: Execution timed out: wall-clock or instruction fuel limit exceeded.
EXECUTION MS: 2.91
```

Execution timings are specific to the test environment and should not be treated as performance guarantees.

### Wasmtime compatibility

The project dependency remains pinned to:

`wasmtime==49.0.0`

Wasmtime 50.0.1 was temporarily tested inside disposable Docker containers during the investigation.

The final compatibility verification was performed using the project's pinned Wasmtime 49.0.0.

No Wasmtime dependency upgrade was included in this change.

Safety instruction: Never execute `plugins/malicious/memory_bomb.py` directly with host CPython. Run the integration test only inside a disposable container with explicit resource limits.

---

## Current status

- The Wasmtime-based MicroPython WASI execution path is implemented.
- Benign WebAssembly execution from the Python host has been verified.
- The FastAPI execution and health endpoints are implemented.
- Plugin storage and webhook execution are implemented and tested.
- The React and Monaco developer portal is integrated with the backend API.
- Runtime instruction-fuel limits and epoch-based interruption are implemented.
- The recommended default wall-clock timeout is 250 ms.
- MicroPython heap configuration is enabled.
- Current exported WASM linear-memory reporting is implemented.
- Python `MemoryError` handling uses a reserved guest exit code.
- The fallback memory-trap classification requires specific diagnostic evidence.
- Normal Python execution has been verified.
- Infinite-loop execution has been verified to return `timeout`.
- The actual memory-bomb integration test has passed inside Docker under the previously recorded 50 ms default configuration.
- The memory-bomb Docker test must be repeated using the updated 250 ms default.
- Host-function feasibility experiments are documented in `docs/SPIKES.md`.
- Extism host-function experiments are separate from the primary runtime and are not part of the current execution path.
- The latest recorded local test result is 76 passed, 1 skipped and 1 warning.
- The project remains a prototype with documented limitations; further testing and security review are required before production use.

---

## Known limitations and follow-up work

The following items require continued engineering attention:

### 1. Final-default Docker verification

The recorded memory-bomb Docker test used the earlier 50 ms default.

Repeat the test with the recommended 250 ms default and record the actual configuration and result.

### 2. MicroPython heap and Wasmtime memory

The MicroPython heap is configured to 2M, while the Wasmtime Store memory-size limit is 10 MiB.

These limits must not be conflated. The observed Python allocation constraint was the MicroPython heap configuration.

### 3. Memory-trap classification

The primary memory-exhaustion signal is the reserved guest `MemoryError` exit code.

The fallback `MEMORY_OUT_OF_BOUNDS` classification requires all three diagnostic markers. Generic out-of-bounds traps must not automatically be classified as memory exhaustion.

### 4. Private host-call helper

The runner currently reuses the installed `micropython-wasm` package's private `_define_host_call` helper.

This is accepted for the current implementation with `micropython-wasm==0.1a2` pinned and a runtime compatibility guard in place.

A supported public interface would be preferable if available.

### 5. Memory measurement

`mem_bytes` measures current exported WASM linear memory, not peak memory or total host-process memory.

A future implementation could introduce a more detailed and precisely defined memory metric.

### 6. Concurrency testing

The shared Engine and Module architecture uses fresh Stores and Instances.

The existing sequential repeated-timeout test provides recovery coverage.

Additional concurrent-execution stress testing is recommended, particularly for simultaneous timeouts, memory exhaustion and runtime recovery. A two-to-four-run concurrent stress test would provide useful additional evidence.

### 7. Production security

Passing the existing tests does not establish that the sandbox is free of security vulnerabilities.

Further security testing and code review are necessary before production use.

---

## Development workflow

Follow the team's contribution rules:

- Create one branch per task, using `yourname/short-task`.
- Keep pull requests focused and explain what changed, how it was tested and any unresolved limitations.
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
3. Review the diff for accidental changes, secrets, generated files and temporary debugging code.
4. Confirm that the documentation reflects the actual implementation and test results.
5. Open a pull request with a clear description and test evidence.
6. Obtain peer review before merging.

---

## Documentation

- [API contract](docs/API_CONTRACT.md)
- [Execution pipeline](docs/PIPELINE.md)
- [Security findings](docs/SECURITY.md)
- [Runtime spikes and timing notes](docs/SPIKES.md)
- [WebAssembly design report](docs/WASM_REPORT.md)
- [Backend Runtime, Security and Testing Documentation](backend/README.md)

For component-specific instructions, see the README files under `backend/` and `frontend/` where available.