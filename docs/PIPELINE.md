# WasmBox Pipeline

**Project:** WasmBox Sandbox
**Verified revision:** `2e1c11c`
**Last verification:** 5 November 2026

**Scope:** This document describes the integrated `/run` execution pipeline, from browser request validation and Python source packaging through custom Wasm artifact extraction, Wasmtime execution, resource enforcement, and API response generation.

The repository source and tests remain authoritative. Security and performance observations apply only to the specific environments, revisions, and workloads tested. See `docs/SECURITY.md` and `docs/WASM_REPORT.md` for detailed evidence and limitations.

---

## 1. Overview

WasmBox uses a repository-managed MicroPython WASI interpreter to execute Python scripts inside a Wasmtime-managed WebAssembly environment.

```text
Browser (React)
    |
    | POST /run
    | {"code": "..."}
    v
FastAPI
    |
    | Validate request and source length
    v
package_plugin(code)
    |
    | Read repository-managed MicroPython WASI artifact
    | Append Python source as custom section:
    | wasmbox_script
    v
PluginArtifact
    |
    | Packaged WASM bytes and source metadata
    v
run_plugin(artifact)
    |
    | Obtain shared Wasmtime Engine and compiled Module
    | Extract Python source from wasmbox_script
    | Acquire runner execution lock
    | Create fresh Store
    | Apply memory, fuel, and timeout limits
    | Create fresh Instance
    | Execute Python through MicroPython WASI
    | Capture stdout and stderr
    | Measure current guest linear memory
    v
PluginResult
    |
    | status
    | stdout
    | stderr
    | exec_ms
    | mem_bytes
    v
FastAPI JSON response
    |
    v
Browser (React)
```

The browser sends Python source to:

`http://localhost:8000/run`

The API validates the request, packages the source with the repository-managed interpreter artifact, passes the packaged artifact to the custom runner, and returns the execution result.

A normal successful response contains five fields:

- `status`
- `stdout`
- `stderr`
- `exec_ms`
- `mem_bytes`

A request missing the required `code` field is rejected by FastAPI request validation with HTTP 422. This response uses FastAPI's validation-error structure and does not contain the normal five-field execution response.

Application-level errors using HTTP 400 or 404 return a JSON object with a string `detail` field. FastAPI HTTP 422 validation errors return `detail` as an array of error objects. The frontend handles both formats separately.

## 2. Interpreter Artifact

WasmBox uses a prebuilt MicroPython interpreter compiled to WebAssembly and designed to run through WASI.

| Item             | Value                                                                                                           |
| ---------------- | --------------------------------------------------------------------------------------------------------------- |
| File             | `backend/app/runtime/artifacts/micropython-wasi.wasm`                                                           |
| Source package   | `micropython-wasm` 0.1a2                                                                                        |
| Upstream project | [https://github.com/simonw/micropython-wasm](https://github.com/simonw/micropython-wasm?utm_source=chatgpt.com) |
| Licence          | Apache-2.0 (`LICENSE` beside the artifact)                                                                      |
| Size             | 370,907 bytes                                                                                                   |
| SHA-256          | `1c054a4d21d4a6589bc568821ebf562889988ddaaf8a17a2e2985a56cf228051`                                              |

The interpreter is a repository-managed binary artifact.

WasmBox does not compile a new WebAssembly binary from every user's Python source.

The user's Python script is packaged as data and subsequently extracted by the runtime.

### Artifact integrity

The file:

`backend/tests/test_interpreter_artifact.py`

checks the expected interpreter artifact hash.

If the hash test fails, investigate the artifact change and its source before modifying the expected hash.

Do not update the expected hash merely to make a failing test pass.

## 3. Packaging: `package_plugin(code)`

Implemented in:

`backend/app/runtime/packaging.py`

The `package_plugin(code)` function accepts Python source and returns a `PluginArtifact`.

The artifact contains:

- Packaged WebAssembly bytes.
- Original Python source.
- Custom-section name.
- `script_sha256`, the SHA-256 hash of the UTF-8 source text.

### Packaging process

The function performs the following operations:

1. Rejects empty or whitespace-only source.
2. Rejects source longer than 10,000 characters.
3. Reads the repository-managed base MicroPython interpreter artifact.
4. Checks the base WebAssembly header.
5. Encodes the user's Python source as UTF-8.
6. Appends the source in a custom WebAssembly section named `wasmbox_script`.
7. Returns the packaged artifact and source hash.

Packaging is deterministic for a fixed base interpreter artifact and source because the same source produces the same custom-section bytes.

The packaged artifact is passed to the custom runner for execution.

## 4. Custom-Section Format and Extraction

The custom-section name is:

`wasmbox_script`

The corresponding constants are:

- `CUSTOM_SECTION_NAME` in `packaging.py`.
- `SECTION_NAME` in `micropython_runner.py`.

The custom section is WebAssembly section ID `0`.

Its binary layout is:

| Part                        | Meaning                                   |
| --------------------------- | ----------------------------------------- |
| Section ID `0x00`           | WebAssembly custom section                |
| LEB128 size                 | Byte length of the custom-section payload |
| LEB128 name length and name | UTF-8 name `wasmbox_script`               |
| Remaining payload           | User's Python source encoded as UTF-8     |

### LEB128 encoding

The packaging utility uses standard unsigned LEB128 (`u32`) encoding.

Each byte contributes seven bits of value. The most significant bit (`0x80`) indicates whether another byte follows.

This allows variable-length payload sizes to be represented in accordance with the WebAssembly binary format.

### Source extraction

`extract_script()` is implemented in:

`backend/app/runtime/micropython_runner.py`

It:

1. Checks the WebAssembly header.
2. Walks through the WebAssembly sections.
3. Finds the custom section with the agreed name.
4. Extracts the remaining payload.
5. Decodes the Python source as UTF-8.

Malformed, truncated, missing-section, and invalid UTF-8 artifacts are reported as artifact errors.

## 5. Execution: `run_plugin(artifact)`

Implemented in:

`backend/app/runtime/micropython_runner.py`

The custom runner manages Wasmtime execution rather than relying on the earlier black-box `micropython_wasm.run()` execution path.

The public interface accepts a prepared artifact and optional execution limits.

Conceptually:

```python
run_plugin(
    artifact,
    *,
    memory_bytes=DEFAULT_MEMORY_BYTES,
    fuel=DEFAULT_FUEL,
    wall_timeout_seconds=DEFAULT_WALL_TIMEOUT_SECONDS,
)
```

### Execution lifecycle

The current execution path follows these steps:

1. Accepts the packaged artifact or an object exposing `wasm_bytes`.
2. Extracts the source from the `wasmbox_script` custom section.
3. Obtains the shared Wasmtime Engine and compiled interpreter Module.
4. Acquires the process-wide runner lock.
5. Creates a fresh Wasmtime Store for the execution.
6. Applies Store memory, instance, memory-count, table, and fuel limits.
7. Configures the per-execution epoch deadline.
8. Creates a fresh execution Instance.
9. Sets up the WASI execution environment and registered host capabilities.
10. Executes the MicroPython interpreter with the extracted Python source.
11. Captures stdout and stderr.
12. Determines the execution status.
13. Measures current exported guest linear memory when available.
14. Returns a `PluginResult`.

### Engine and Module reuse

The Wasmtime Engine and compiled interpreter Module are shared across executions.

They are initialized once through `_get_runtime()`.

This avoids repeatedly compiling and initializing the same interpreter artifact for every plugin execution.

### Store and Instance isolation

Every `run_plugin()` invocation creates a fresh Store and Instance.

Execution-specific limits and runtime state belong to that Store.

This helps ensure that guest state from one execution is not unintentionally reused by another execution.

### Concurrent execution protection

The custom runner uses a process-wide `_RUNNER_LOCK` around the `_run_once()` lifecycle.

This lock was introduced after an intermittent Wasmtime Python `FUNCTIONS` slab allocator race was observed during concurrent host-call registration.

The lock serializes Wasmtime execution within each worker process.

Multiple Uvicorn worker processes have independent runtime state and locks.

### Error handling

The runner captures guest stdout and stderr and converts recognized execution outcomes into `PluginResult`.

A wrapper around guest execution improves Python exception reporting.

An uncaught MicroPython `MemoryError` is converted into a reserved WASI exit code:

`MEMORY_ERROR_EXIT_CODE = 86`

The host runner recognizes this exit code and classifies the result as `memory_exceeded`.

The wrapper improves error readability. It is not itself a security boundary.

## 6. Runtime Limits and Execution Timing

The current implementation configures the following defaults.

### 6.1 Resource limits

| Setting                        | Default            | Meaning                      |
| ------------------------------ | ------------------ | ---------------------------- |
| MicroPython heap               | 2 MiB              | MicroPython guest heap limit |
| Wasmtime linear-memory ceiling | 10 MiB             | Wasmtime Store memory limit  |
| WebAssembly fuel               | 30,000,000         | Instruction-fuel budget      |
| Wall-clock timeout             | 0.25 seconds       | Default execution deadline   |
| Epoch ticker interval          | Approximately 5 ms | Background epoch advancement |
| Store instances                | 1                  | Maximum instances per Store  |
| Store memories                 | 1                  | Maximum memories per Store   |
| Store tables                   | 8                  | Maximum tables per Store     |
| Table elements                 | 10,000             | Maximum table elements       |

These settings are maintained in:

`backend/app/runtime/micropython_runner.py`

Relevant configuration constants include:

```python
DEFAULT_MEMORY_BYTES = 10 * 1024 * 1024
DEFAULT_FUEL = 30_000_000
DEFAULT_WALL_TIMEOUT_SECONDS = 0.25
MICROPYTHON_HEAP_SIZE = "2M"
TICK_INTERVAL_SECONDS = 0.005
```

Tests can supply smaller limits to `run_plugin()` without changing the defaults.

### 6.2 Memory enforcement

WasmBox has two separate guest memory boundaries.

MicroPython heap

The MicroPython interpreter uses its own heap limit configured as `2M`.

When an uncaught `MemoryError` occurs, the guest wrapper raises the reserved exit code.

The runner recognizes this result and returns:

`memory_exceeded`

Wasmtime linear memory

The runner also configures a 10 MiB Wasmtime Store memory ceiling.

Recognized Wasmtime memory-limit failures are classified as:

`memory_exceeded`

The MicroPython heap and Wasmtime linear-memory ceiling are separate controls.

The MicroPython heap can be exhausted before the larger Wasmtime linear-memory limit is reached.

### 6.3 Instruction fuel

Fuel provides a deterministic budget for instrumented WebAssembly execution.

Fuel exhaustion is classified as:

`timeout`

Fuel is not a direct count of Python source lines or Python statements.

### 6.4 Wall-clock timeout

The default wall-clock timeout is 0.25 seconds.

The runner uses Wasmtime epoch interruption with a shared background ticker advancing approximately every 5 ms.

The configured ticker interval is not a guarantee that every execution will be interrupted with exactly 5 ms precision.

Actual interruption timing can vary with runtime scheduling.

Wall-clock interruption is classified as:

`timeout`

### 6.5 Execution-time measurement

`exec_ms` represents the runner's documented execution interval.

It measures WebAssembly instantiation and guest execution.

It excludes:

- Waiting to acquire `_RUNNER_LOCK`.
- Shared Engine initialization.
- Shared Module initialization.
- Per-run Store setup.
- Linker and WASI setup.
- Source packaging.
- Custom-section extraction.
- Complete HTTP request handling.

Therefore, `exec_ms` is not equivalent to the total time observed by a browser or HTTP client.

### 6.6 Guest-memory measurement

The runner implements `_measure_memory()`.

It inspects exported guest linear memory and returns its current size in bytes.

The `mem_bytes` field represents:

Current exported guest WebAssembly linear memory.

It does not represent:

- Peak guest memory allocation.
- Total MicroPython heap usage.
- Total host-process memory.
- Total Docker container memory.
- Peak physical RAM consumption.

If memory introspection is unavailable, the runner may return zero.

The value must not be presented as peak memory usage.

## 7. API Response and Input Rules

A normal successful `/run` response contains five fields.

Example:

```json
{
  "status": "ok",
  "stdout": "hi\n",
  "stderr": "",
  "exec_ms": 210,
  "mem_bytes": 2293760
}
```

The values above illustrate the response structure. Actual execution values depend on the workload and runtime state.

### 7.1 Response fields

| Field       | Meaning                                                      |
| ----------- | ------------------------------------------------------------ |
| `status`    | Execution outcome                                            |
| `stdout`    | Captured standard output                                     |
| `stderr`    | Captured error text or execution-limit details               |
| `exec_ms`   | Runner execution time in milliseconds                        |
| `mem_bytes` | Current exported guest linear memory in bytes when available |

### 7.2 Execution statuses

The internal runner outcomes are:

| Status            | Meaning                                                           |
| ----------------- | ----------------------------------------------------------------- |
| `ok`              | Guest execution completed successfully                            |
| `error`           | Ordinary guest, artifact, or other execution failure              |
| `timeout`         | Recognized wall-clock interruption or instruction-fuel exhaustion |
| `memory_exceeded` | Recognized guest memory-limit exhaustion                          |

The API schema may additionally allow:

`denied`

This status is reserved for verified host-side policy denial where supported by the API adapter. It must not be used automatically for ordinary guest exceptions, missing files, or unverified resource failures.

### 7.3 Application errors and validation errors

Application-level errors using HTTP 400 or 404 return a JSON object with a string `detail` field.

Example:

```json
{
  "detail": "Plugin not found"
}
```

FastAPI HTTP 422 validation errors return an array of validation error objects.

Example:

```json
{
  "detail": [
    {
      "loc": ["body", "code"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

The frontend must distinguish between string and array values in `detail` before displaying them.

### 7.4 Input rules

| Input                           | Expected behavior                                                     |
| ------------------------------- | --------------------------------------------------------------------- |
| Empty or whitespace-only source | Execution error with an appropriate message                           |
| More than 10,000 characters     | Rejected by application-level source-length validation                |
| Missing `code` field            | HTTP 422 validation response                                          |
| Valid Python source             | Packaged and passed to the runner                                     |
| Backend unavailable             | Frontend request fails and should display a friendly connection error |

The normal five-field response should not be confused with FastAPI validation or application error responses.

## 8. Bundling Is Not Compiling

The WasmBox pipeline bundles the user's Python source. It does not compile each submitted Python script into a new WebAssembly binary.

The distinction is important:

- The repository-managed MicroPython interpreter is a real WebAssembly/WASI program.
- The user's Python source is stored as data in a custom section.
- The custom section is named `wasmbox_script`.
- At runtime, the runner extracts the source.
- The MicroPython interpreter executes that source.

The user's Python script is not transformed into a separately compiled WASM program.

A requirement for a separate, self-contained WASM binary for every plugin would need a different compilation pipeline and additional investigation.

That is not the current WasmBox implementation.

## 9. Security and Capability Boundaries

The current runner manages Wasmtime execution using a custom Store, Instance, Linker, and WASI execution environment.

Guest capabilities depend on the interfaces and host functions made available through the runtime configuration.

The project has conducted specific filesystem, network, resource-limit, concurrency, and host-function tests.

### 9.1 Filesystem and network tests

An earlier audit on 28 October 2026 tested:

`plugins/malicious/read_passwd.py`

The attempt to read `/etc/passwd` returned:

`OSError: [Errno 44] ENOENT`

No `root:` content was returned.

The network probe:

`plugins/malicious/open_socket.py`

attempted to import `socket` and connect to `1.1.1.1:80`.

The observed result was:

`ImportError: no module named 'socket'`

These results apply to the specific tested attempts on the earlier audit revision. They do not constitute a comprehensive filesystem or network security assessment of every possible attack.

### 9.2 Host-function controls

The project includes host-function implementation and test work.

The focused regression suite includes:

`backend/tests/test_host_functions.py`

The suite passed during the focused regression run.

The exact registered host capabilities, argument-validation behavior, and cross-run restrictions should be documented from the actual runner implementation and tests.

Arbitrary filesystem access, unrestricted network access, and unrestricted host callbacks should not be exposed to guest code.

### 9.3 Memory-exhaustion testing

The memory-bomb plugin:

`plugins/malicious/memory_bomb.py`

attempts to allocate 200 MB using repeated 1 MB bytearrays.

It was tested in an isolated Linux Docker container with:

- 512 MB container memory limit.
- 512 MB memory-plus-swap limit.
- 2 CPU limit.

The API returned:

`status: memory_exceeded`

The observed response included:

```json
{
  "status": "memory_exceeded",
  "stdout": "",
  "stderr": "Execution stopped: sandbox memory limit exceeded.",
  "exec_ms": 2.15,
  "mem_bytes": 2293760
}
```

After the memory-intensive execution:

- A normal Python recovery program succeeded.
- The health endpoint returned `{"ok": true}`.
- Docker reported a post-test memory snapshot of 76.22 MiB out of 512 MiB.
- Container exit code was 0.
- `OOMKilled` was false.

The 76.22 MiB value is a post-test container snapshot, not peak memory usage.

The automated `test_memory_bomb_is_stopped()` pytest placeholder remains intentionally skipped during the ordinary suite. The bounded Docker execution is separate manual verification evidence.

### 9.4 Known security limitations

The security tests demonstrate the behavior of specific workloads and configurations.

They do not constitute:

- A comprehensive penetration test.
- Proof that all host filesystem access is impossible.
- Proof that every form of network access is blocked.
- Proof against every possible memory-exhaustion attack.
- Independent security certification.
- A guarantee of production isolation under every deployment configuration.

Refer to `docs/SECURITY.md` for the detailed test records and limitations.

## 10. Performance and Verification Evidence

The following results were recorded against the final integrated revision:

`2e1c11c`

### 10.1 Backend regression tests

The complete backend suite reported:

```text
103 passed, 1 skipped
```

The skipped test is:

`backend/tests/test_security_plugins.py::test_memory_bomb_is_stopped`

Its skip reason requires execution in an isolated environment with an explicit process or container memory cap.

The separate Docker memory-bomb verification passed, but the pytest placeholder remains skipped.

The focused regression suite reported:

```text
36 passed
```

The focused modules included:

- `test_runner_interface.py`
- `test_concurrent_timeouts.py`
- `test_limits.py`
- `test_status_mapping.py`
- `test_host_functions.py`
- `test_linux_interruption_regression.py`

### 10.2 Linux interruption and recovery

Linux container regression:

- Debian GNU/Linux 13.
- Python 3.12.16.
- Wasmtime 49.0.0.
- 512 MB container memory limit.
- 2 CPU limit.
- 2 regression tests passed.

The direct runner regression completed 20 timeout/recovery cycles.

A separate live Uvicorn container test completed 20 repeated cycles of:

1. Timeout execution.
2. Normal recovery execution.
3. Health verification.

Observed results:

| Check               | Result |
| ------------------- | ------ |
| Timeout requests    | 20/20  |
| Recovery executions | 20/20  |
| Health checks       | 20/20  |
| Container exit code | 0      |
| Docker OOMKilled    | false  |

The Linux verification used Docker Desktop on a Windows development machine, not a native Linux production server.

### 10.3 Final-main HTTP load benchmark

The final-main live HTTP benchmark tested:

`POST /run`

with payload:

```python
print(42)
```

Environment:

- Windows AMD64.
- Python 3.12.10.
- Revision `2e1c11c`.
- Live HTTP mode.

| Concurrency | Successful requests | Throughput  | Average HTTP latency | HTTP p95  |
| ----------- | ------------------- | ----------- | -------------------- | --------- |
| 1           | 1/1                 | 2.43 req/s  | 192.89 ms            | 192.89 ms |
| 5           | 5/5                 | 10.55 req/s | 7.54 ms              | 18.31 ms  |
| 10          | 10/10               | 16.18 req/s | 12.36 ms             | 22.45 ms  |
| 20          | 20/20               | 16.83 req/s | 15.14 ms             | 30.85 ms  |

Total successful requests: 36.

Failed requests: 0.

The backend health endpoint remained available after the benchmark.

The first request recorded higher latency than the subsequent batches. This measurement is retained rather than excluded.

These were short-duration measurements, not a sustained-load or production-capacity benchmark.

The 50 ms target must not be claimed as universally achieved based on these results.

Full benchmark details are maintained in:

`docs/LOAD_TEST.md`

### 10.4 Frontend integration

The final frontend integration was merged through PR #30.

The independent review verified:

- Frontend styling and responsive layout.
- API integration with `/run`.
- Plugin save/list/load endpoints.
- Webhook execution endpoint.
- Application error handling for HTTP 400/404.
- FastAPI validation error handling for HTTP 422.
- Output and execution-state presentation.
- Eight end-to-end integration test cases.
- Frontend production build.

Both backend and frontend GitHub Actions checks passed before merge.

## 11. Pipeline Design Decisions and Limitations

The current WasmBox pipeline follows these decisions:

1. Reuse a repository-managed MicroPython WASI interpreter instead of compiling every Python submission into a new WASM binary.
2. Package the user's Python source into the `wasmbox_script` custom section.
3. Extract the source at runtime and execute it through the MicroPython WASI interpreter.
4. Reuse the shared Wasmtime Engine and compiled Module.
5. Create fresh Store and Instance objects for each execution.
6. Apply explicit instruction-fuel, wall-clock, and guest-memory limits.
7. Use epoch interruption for time-based execution control.
8. Use a process-wide runner lock to protect Wasmtime's Python host-call registration lifecycle.
9. Capture stdout, stderr, execution status, runner execution time, and available guest-memory measurements.
10. Preserve the distinction between normal guest exceptions, timeouts, and recognized memory-limit failures.

### Remaining limitations

- Peak guest-memory allocation is not measured.
- Total host-process memory and peak physical memory are not reported through `mem_bytes`.
- Filesystem and network audit tests cover specific attempts rather than all possible attacks.
- The host-function capability boundary requires ongoing review.
- The memory-bomb pytest placeholder remains skipped in ordinary local test runs, although separate bounded Docker verification succeeded.
- Linux interruption verification was performed using Docker Desktop's Linux container environment rather than a native Linux production host.
- The 50 ms end-to-end performance target has not been established as achieved.
- The final-main load test is a short benchmark and does not establish sustained production capacity.

The current implementation demonstrates a working WebAssembly-based Python execution pipeline with tested resource controls and documented limitations.

These results do not constitute complete security certification or unrestricted production-readiness approval.

## 12. References and Related Documentation

| Document               | Purpose                                                |
| ---------------------- | ------------------------------------------------------ |
| `docs/API_CONTRACT.md` | API request, response, and error contracts             |
| `docs/SECURITY.md`     | Security architecture, audit evidence, and limitations |
| `docs/LOAD_TEST.md`    | Historical and final-main performance benchmarks       |
| `docs/WASM_REPORT.md`  | WebAssembly design, trade-offs, and technical findings |
| `README.md`            | Project setup and usage instructions                   |

Additional references:

1. [WebAssembly Security Overview](https://webassembly.org/docs/security/?utm_source=chatgpt.com)
2. [WASI Design Principles](https://github.com/WebAssembly/WASI/blob/main/docs/DesignPrinciples.md?utm_source=chatgpt.com)
3. [WASI Capability Model](https://github.com/WebAssembly/WASI/blob/main/docs/Capabilities.md?utm_source=chatgpt.com)
4. [Wasmtime: Interrupting Wasm Execution](https://docs.wasmtime.dev/examples-interrupting-wasm.html?utm_source=chatgpt.com)
5. [MicroPython WASI Interpreter](https://github.com/simonw/micropython-wasm?utm_source=chatgpt.com)
6. [Wizer: WebAssembly Pre-initializer](https://github.com/bytecodealliance/wizer?utm_source=chatgpt.com)

## 13. Final Pipeline Summary

The WasmBox execution pipeline is:

```text
Python Source
    |
    v
FastAPI Validation
    |
    v
Plugin Packaging
    |
    v
WASM Custom Section
    |
    v
Custom Wasmtime Runner
    |
    v
Fresh Store and Instance
    |
    v
MicroPython WASI Execution
    |
    v
Resource Enforcement
    |
    v
Output and Metric Collection
    |
    v
PluginResult
    |
    v
FastAPI JSON Response
    |
    v
React Frontend
```

The final integrated revision demonstrates successful Python execution, timeout handling, memory-exhaustion classification, repeated execution recovery, and concurrent HTTP requests under the tested configurations.

The repository's tests and documentation should continue to distinguish verified behavior from historical observations, measured performance, untested assumptions, and future improvements.
