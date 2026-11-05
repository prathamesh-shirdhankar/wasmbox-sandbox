# WasmBox: WebAssembly Design Report

**Project:** WasmBox Sandbox
**Date:** 5 November 2026
**Verified revision:** `2e1c11c`
**Scope:** Architecture, isolation approach, runtime limits, performance, security trade-offs, and verification evidence.
**Status:** Team integration completed. Final engineering verification and documentation completed or being finalized.

---

## 1. What WebAssembly and WASI Provide

WebAssembly (Wasm) is a portable bytecode format executed by a WebAssembly runtime. Its execution model provides a sandbox boundary: a module cannot directly access arbitrary host resources through ordinary Wasm instructions. Access to external functions and resources depends on interfaces supplied by the embedding runtime.

The WebAssembly security overview emphasizes that the embedding environment's policies are part of the effective security model.

Reference: [WebAssembly Security](https://webassembly.org/docs/security/).

WASI is a system-interface family for WebAssembly programs. Its capability-oriented design makes external access something the runtime explicitly provides instead of assuming unrestricted ambient authority.

The general principle is that a guest can use only the capabilities made available through its interfaces.

References:
- [WASI Design Principles](https://github.com/WebAssembly/WASI/blob/main/docs/DesignPrinciples.md)
- [WASI Capabilities](https://github.com/WebAssembly/WASI/blob/main/docs/Capabilities.md)

This does not automatically make every Wasm application secure. Host configuration, imported functions, mounted directories, resource limits, and guest program behavior all matter.

### 1.1 WasmBox Execution Model

WasmBox packages user-written Python as data and executes it using a repository-managed, prebuilt MicroPython WASI interpreter.

The user's Python source is stored in a custom section named:

`wasmbox_script`

WasmBox does not compile every submitted Python script into a separate WebAssembly module.

The execution pipeline consists of:

1. FastAPI request validation.
2. Python source extraction and validation.
3. Plugin packaging.
4. Custom-section extraction.
5. MicroPython WASI interpreter initialization and reuse.
6. Wasmtime execution with configured resource limits.
7. Output and error collection.
8. `PluginResult` generation.
9. API response serialization.

The main execution implementation is:

`backend/app/runtime/micropython_runner.py`

---

## 2. Runner Architecture and Lifecycle Isolation

The redesigned runner replaces black-box execution calls with a custom-managed Wasmtime pipeline.

### 2.1 Runtime Architecture

```text
WasmBox Host Process
│
├── Wasmtime Engine
│   └── Shared compiled MicroPython Module
│
├── Shared Epoch Ticker
│   └── Background interruption mechanism
│
└── Individual Plugin Execution
    │
    ├── Fresh Store
    │   ├── Memory limits
    │   ├── Instruction fuel
    │   └── Execution deadline
    │
    ├── Fresh Instance
    │
    ├── WASI execution environment
    │
    ├── stdout / stderr capture
    │
    └── Result collection
        ├── status
        ├── stdout
        ├── stderr
        ├── exec_ms
        └── mem_bytes
```

### 2.2 Store and Instance Lifecycle

Every `run_plugin()` invocation creates a fresh Wasmtime `Store` and execution `Instance`.

This provides per-execution runtime state and reduces the possibility of guest state being unintentionally shared between separate runs.

The Store contains execution-specific configuration, including:

- Memory limits.
- Fuel allocation.
- Epoch deadline.
- Runtime resources.

The Instance contains the instantiated guest module and its associated execution state.

### 2.3 Engine and Module Reuse

The Wasmtime `Engine` and compiled interpreter `Module` are shared across executions.

They are initialized once through the runtime initialization mechanism in `_get_runtime()`.

Reusing the compiled module avoids repeatedly performing the same interpreter compilation and loading work for every plugin execution.

Engine and Module initialization are excluded from the documented per-run `exec_ms` measurement.

### 2.4 Timeout Isolation

The runner uses Wasmtime epoch interruption.

A background ticker advances the engine epoch approximately every 5 ms.

Each execution configures its own Store deadline. This allows execution deadlines to be associated with individual Store instances.

The runner also uses a process-wide `_RUNNER_LOCK` around the execution lifecycle to protect against the previously observed Wasmtime Python `FUNCTIONS` slab allocator race.

This lock serializes Wasmtime execution within a worker process. Multiple Uvicorn worker processes maintain independent runtime state.

The 5 ms ticker interval is a configured interval, not a guarantee that actual interruption always occurs with exactly 5 ms precision.

## 3. Security and Capability Decisions

WasmBox uses the MicroPython WASI interpreter within a Wasmtime-managed execution environment.

The effective sandbox boundary depends on the runtime configuration and the capabilities exposed to guest programs.

The project has tested filesystem access, socket imports, resource limits, concurrent execution, and host-function behavior.

### 3.1 Filesystem and Network Audit

An earlier security audit on 28 October 2026 tested two representative malicious scripts through the `/run` endpoint.

The audit was performed against revision `db0e0f4`.

| Test             | Attempt                                     | Observed result                                                                                   |
| ---------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `read_passwd.py` | Read `/etc/passwd`                          | HTTP 200, `status: error`, empty stdout; stderr contained `OSError: [Errno 44] ENOENT`            |
| `open_socket.py` | Import `socket` and connect to `1.1.1.1:80` | HTTP 200, `status: error`, empty stdout; stderr contained `ImportError: no module named 'socket'` |

The filesystem probe returned no `root:` content.

The network probe could not import the socket module and did not print `connected`.

These outcomes establish that the tested attempts did not successfully access the requested resources.

They do not establish that every possible filesystem or network attack is blocked.

These are historical results from revision `db0e0f4`, not fresh penetration-test evidence against every possible configuration of revision `2e1c11c`.

Further final-revision testing of filesystem and network restrictions remains recommended.

### 3.2 Host Functions

The project contains host-function implementation and testing work.

The focused regression suite includes:

`backend/tests/test_host_functions.py`

The test module passed as part of the focused 36-test regression run.

However, a successful test suite does not automatically establish that every possible host capability is restricted.

Security review must consider:

- Registered host functions.
- Function argument validation.
- Maximum input sizes.
- Execution-specific host capabilities.
- Cross-run state isolation.
- Concurrent host-call behavior.
- Access to unregistered functions.

Only explicitly verified host capabilities should be represented as part of the supported allowlist.

The project should not expose arbitrary filesystem operations, unrestricted network connections, or unrestricted host callbacks to guest code.

Additional host-function security review remains part of the engineering acceptance scope.

## 4. Fuel, Wall-Clock Timeout, and Memory

The current runner configures multiple resource limits.

### 4.1 Default Resource Limits

| Resource               | Configuration    | Enforcement mechanism       |
| ---------------------- | ---------------- | --------------------------- |
| MicroPython heap       | 2 MiB            | MicroPython heap allocator  |
| Wasmtime linear memory | 10 MiB           | Wasmtime Store limits       |
| Instruction fuel       | 30,000,000 units | Wasmtime fuel accounting    |
| Wall-clock timeout     | 0.25 seconds     | Wasmtime epoch interruption |
| Store instances        | 1                | Wasmtime Store limits       |
| Store memories         | 1                | Wasmtime Store limits       |
| Store tables           | 8                | Wasmtime Store limits       |
| Table elements         | 10,000           | Wasmtime Store limits       |

These configuration values are maintained in:

`backend/app/runtime/micropython_runner.py`

### 4.2 Instruction Fuel

Fuel provides a deterministic budget for instrumented WebAssembly execution.

It is not a direct count of Python source lines or Python statements.

Fuel exhaustion is classified as:

`timeout`

### 4.3 Wall-Clock Timeout

The default wall-clock timeout is:

`DEFAULT_WALL_TIMEOUT_SECONDS = 0.25`

The runner uses Wasmtime epoch interruption and a shared ticker that advances approximately every 5 ms.

Actual interruption timing can vary with runtime scheduling and execution behavior.

Timeout interruption is classified as:

`timeout`

The earlier 50 ms experiment was too aggressive for the initial cold-start configuration. The current default is 250 ms.

### 4.4 Memory Enforcement

WasmBox has two separate memory boundaries.

MicroPython heap

The MicroPython heap is configured as:

`MICROPYTHON_HEAP_SIZE = "2M"`

An uncaught MicroPython `MemoryError` is converted into a reserved guest exit code:

`MEMORY_ERROR_EXIT_CODE = 86`

The host runner recognizes this result and returns:

`memory_exceeded`

Wasmtime linear memory

The runner configures:

`DEFAULT_MEMORY_BYTES = 10 * 1024 * 1024`

The Store enforces this linear-memory limit through Wasmtime's Store limits.

Recognized Wasmtime memory-limit failures are classified as:

`memory_exceeded`

Both memory limits are separate. The MicroPython heap can be exhausted before the Wasmtime linear-memory ceiling is reached.

### 4.5 Memory Reporting

The runner implements `_measure_memory()` to inspect exported guest WebAssembly linear memory.

The `mem_bytes` field represents the current size of exported guest linear memory in bytes.

It does not represent:

- Peak guest-memory allocation.
- Total MicroPython heap usage.
- Total host-process memory.
- Total Docker container memory.
- Peak physical RAM consumption.

If memory inspection is unavailable, the runner may return zero.

### 4.6 Execution-Time Reporting

The `exec_ms` field reports the runner's documented execution duration.

It measures WebAssembly instantiation and guest execution.

It excludes:

- Waiting to acquire `_RUNNER_LOCK`.
- Shared Engine initialization.
- Shared Module initialization.
- Per-run Store setup.
- Linker and WASI setup.
- Python source packaging.
- Custom-section extraction.
- Total HTTP request handling.

Consequently, `exec_ms` must not be interpreted as complete API response latency.

Fuel and wall-clock interruption provide complementary protections. Neither is equivalent to total HTTP request time.

## 5. Linux Interruption and Recovery Verification

The Linux interruption regression test is:

`backend/tests/test_linux_interruption_regression.py`

It contains:

1. Runner-level timeout and recovery testing.
2. Backend execution and health-check testing after interruptions.

### 5.1 Linux Container Environment

The regression tests were executed inside a Linux Docker container.

| Parameter              | Observed value      |
| ---------------------- | ------------------- |
| Operating system       | Debian GNU/Linux 13 |
| Python                 | 3.12.16             |
| Wasmtime               | 49.0.0              |
| Container memory limit | 512 MB              |
| CPU limit              | 2                   |
| Pytest result          | 2 passed            |
| Pytest exit code       | 0                   |

The runner-level regression test successfully completed 20 timeout and recovery cycles.

### 5.2 Live Uvicorn Server Verification

A separate Linux Docker container was started with:

- 512 MB container memory limit.
- 512 MB memory-plus-swap limit.
- 2 CPU limit.
- Uvicorn running on port 8000 inside the container.
- Host port 8001 mapped to container port 8000.

The live HTTP test performed 20 repeated cycles.

Each cycle:

1. Submitted an infinite-loop program.
2. Verified that the API returned `timeout`.
3. Submitted a normal recovery program.
4. Verified `status: ok`.
5. Confirmed the expected recovery output.
6. Checked the `/health` endpoint.

### 5.3 Live Server Results

| Verification              | Result     |
| ------------------------- | ---------- |
| Total cycles              | 20         |
| Timeout responses         | 20/20      |
| Recovery executions       | 20/20      |
| Health checks             | 20/20      |
| Docker shutdown exit code | 0          |
| Docker `OOMKilled`        | false      |
| Container cleanup         | Successful |

No timeout-related server failure or recovery failure was observed during these 20 cycles.

The verification used Docker Desktop's Linux container environment on a Windows development machine. It was not performed on a native Linux production server.

The live API response identifies a combined wall-clock or instruction-fuel timeout reason. The repeated test confirms the expected timeout status; it does not establish that every live API interruption was exclusively caused by the wall-clock deadline.

## 6. Memory-Exhaustion Security Verification

The memory-bomb test is based on:

`plugins/malicious/memory_bomb.py`

The plugin attempts to allocate 200 MB using repeated 1 MB bytearrays.

It is intended to test whether the sandbox stops guest Python heap exhaustion.

The plugin must not be executed directly using ordinary Python on the developer's host.

### 6.1 Isolated Docker Configuration

The test was executed in a dedicated Docker container.

| Parameter              | Value                              |
| ---------------------- | ---------------------------------- |
| Container environment  | Linux                              |
| Container memory limit | 512 MB                             |
| Memory swap limit      | 512 MB                             |
| CPU limit              | 2                                  |
| Endpoint               | `POST /run`                        |
| Test payload           | `plugins/malicious/memory_bomb.py` |

### 6.2 Observed Memory-Bomb Result

The API returned:

```
{
  "status": "memory_exceeded",
  "stdout": "",
  "stderr": "Execution stopped: sandbox memory limit exceeded.",
  "exec_ms": 2.15,
  "mem_bytes": 2293760
}
```

The returned `memory_exceeded` status confirms that the tested MicroPython heap-exhaustion workload was correctly classified.

### 6.3 Recovery After Memory Exhaustion

After the memory-bomb request, a normal Python program was executed through the same backend container.

Observed output:

`memory recovery successful`

The health endpoint subsequently returned:

```
{
  "ok": true
}
```

A Docker memory snapshot after the workload and recovery showed:

| Metric                       | Result     |
| ---------------------------- | ---------- |
| Container memory usage       | 76.22 MiB  |
| Container memory limit       | 512 MiB    |
| Container memory percentage  | 14.89%     |
| Container shutdown exit code | 0          |
| Docker `OOMKilled`           | false      |
| Container cleanup            | Successful |

The 76.22 MiB measurement is a post-test container snapshot, not peak memory usage during allocation.

### 6.4 Automated Test Status

The test:

`test_memory_bomb_is_stopped()`

in `backend/tests/test_security_plugins.py` remains intentionally skipped during the normal development test suite.

Its skip reason requires execution in an isolated environment with an explicit process or container memory cap.

The successful Docker memory-bomb verification is separate manual test evidence. It does not mean that the skipped pytest test was executed or passed.

The full backend suite therefore remains:

`103 passed, 1 skipped`

### 6.5 Security Conclusion

The tested memory-intensive workload was stopped with `memory_exceeded`.

The backend subsequently executed normal Python code and continued serving health requests.

The Docker container shut down gracefully without an OOM kill.

These results demonstrate the tested MicroPython heap-exhaustion handling under the recorded configuration. They are not proof against every possible memory-exhaustion attack.

## 7. Timing Evidence: Historical and Current Measurements

### 7.1 Historical Measurements

An earlier runner revision recorded five successful `POST /run` requests for `print("hi")` on a Windows development machine:

- 242.43 ms
- 284.23 ms
- 197.51 ms
- 207.61 ms
- 198.75 ms

The median was 207.61 ms, with a minimum of 197.51 ms and a maximum of 284.23 ms.

These measurements belong to the earlier runner implementation and are not directly comparable with measurements from the shared-runtime implementation.

The earlier 50 ms wall-clock experiment was too aggressive for the original cold-start configuration.

The current default wall-clock timeout is 250 ms.

### 7.2 November 3 Linux Startup Measurements

Measured in the Linux Docker environment using the startup-timing experiment:

| Measurement                                   | Result               |
| --------------------------------------------- | -------------------- |
| First `run_plugin()` call                     | 178.9 ms             |
| Ten subsequent calls: minimum                 | 0.8 ms               |
| Ten subsequent calls: median                  | 0.9 ms               |
| Ten subsequent calls: maximum                 | 1.1 ms               |
| Separate Engine + Module construction samples | 96.7, 91.7, 109.3 ms |

The first call includes lazy shared Engine and Module initialization as well as execution.

Later calls reuse the initialized runtime.

The separate construction measurements include creating a new Engine, so they are not pure Module-only compilation times.

### 7.3 November 5 Final-Main HTTP Benchmark

The final integrated `main` revision was tested using live HTTP:

Revision: `2e1c11c`

Environment:

- Windows AMD64.
- Python 3.12.10.
- Live backend at `http://127.0.0.1:8000`.
- Payload: `print(42)`.
- Execution mode: Live HTTP.

| Concurrency | Successful requests | Throughput  | Average HTTP latency | HTTP p50  | HTTP p95  |
| ----------- | ------------------- | ----------- | -------------------- | --------- | --------- |
| 1           | 1/1                 | 2.43 req/s  | 192.89 ms            | 192.89 ms | 192.89 ms |
| 5           | 5/5                 | 10.55 req/s | 7.54 ms              | 4.94 ms   | 18.31 ms  |
| 10          | 10/10               | 16.18 req/s | 12.36 ms             | 11.22 ms  | 22.45 ms  |
| 20          | 20/20               | 16.83 req/s | 15.14 ms             | 9.86 ms   | 30.85 ms  |

All 36 requests succeeded.

The average runner execution times were:

| Concurrency | Average `exec_ms` |
| ----------- | ----------------- |
| 1           | 1.42 ms           |
| 5           | 0.52 ms           |
| 10          | 0.61 ms           |
| 20          | 0.63 ms           |

The first request recorded 192.89 ms HTTP latency and is retained in the results.

The backend health endpoint returned `{"ok": true}` after the benchmark.

These measurements show the difference between complete HTTP response latency and the runner's execution-time metric.

The 50 ms target should not be considered universally achieved based on these measurements. The first-request latency was higher, and `exec_ms` excludes several parts of the overall request lifecycle.

Full benchmark details are recorded in:

`docs/LOAD_TEST.md`

### 7.4 Performance Limitations

The November 5 benchmark involved only 36 requests and a simple `print(42)` workload.

It is not a sustained-load, soak, or production-capacity test.

The November 3 and November 5 results use different environments, revisions, and configurations. They should not be compared without accounting for those differences.

The earlier Wizer-related performance estimates remain unverified hypotheses.

## 8. What Wizer Is — and Is Not in WasmBox

[Wizer](https://github.com/bytecodealliance/wizer?utm_source=chatgpt.com) is a WebAssembly pre-initializer.

It runs a module's initialization function ahead of time and snapshots the initialized state into a new Wasm module, potentially reducing repeated startup work.

Reference: [Wizer Project Documentation](https://github.com/bytecodealliance/wizer?utm_source=chatgpt.com).

Wizer is not currently part of the WasmBox execution pipeline.

It remains a possible future experiment if startup time becomes a priority.

Using it would require checking compatibility with the bundled interpreter, initialization behavior, resource handling, and reproducibility.

No Wizer speedup should be claimed without an implementation and reproducible measurements.

## 9. Why Wasm Can Fit Serverless Work

Short-lived serverless functions often benefit from portable artifacts, explicit host interfaces, and the ability to instantiate isolated workloads without building a full operating-system environment for each function.

Wasm can therefore be a useful execution target for small, separately bounded tasks.

These are architectural advantages, not a guarantee that every Wasm workload starts or runs faster.

Runtime choice, language-runtime startup, host integration, workload type, and configuration all affect performance.

WasmBox's historical and current measurements demonstrate that interpreter startup and host integration remain relevant parts of the performance profile.

The November 5 benchmark illustrates that runner execution time and complete API response latency are substantially different measurements.

## 10. WebAssembly Compared with Docker Containers

Wasm and Docker solve related but different deployment problems. Neither is a universal replacement for the other.

| Consideration         | WebAssembly in WasmBox                                                                | Docker Container                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Main unit             | A Wasm module executed by a Wasm runtime                                              | A packaged process environment with filesystem layers and user-space dependencies                            |
| Host access           | Depends on imported interfaces and capabilities supplied by the host                  | Depends on container configuration, OS permissions, namespaces, mounts, network settings, and runtime policy |
| Best fit              | A compact, bounded plugin or function with a narrow interface                         | Applications needing a fuller Linux userland, multiple processes, or existing container tooling              |
| Operational trade-off | Requires compatible Wasm/WASI support; guest-language/runtime limitations still apply | Mature ecosystem and broad compatibility, but images and isolation configuration can be more involved        |

This comparison is a design guide rather than a security ranking.

Containers can provide strong isolation when correctly configured, and Wasm workloads can also run inside containers.

Reference:

[CNCF: Components vs. Containers](https://www.cncf.io/blog/2025/04/09/components-vs-containers-fight/?utm_source=chatgpt.com).

## 11. WasmBox Design Decisions and Remaining Limitations

The current design decisions are:

1. Reuse a repository-managed MicroPython WASI interpreter instead of compiling every Python submission into a new Wasm module.
2. Embed source code in the `wasmbox_script` custom section, then extract and execute that source at runtime.
3. Validate empty input and enforce the documented maximum source length of 10,000 characters before packaging.
4. Apply explicit instruction fuel, wall-clock timeout, and guest-memory limits.
5. Use a shared Engine and compiled Module with fresh per-execution Store and Instance objects.
6. Apply a process-wide execution lock to protect the Wasmtime Python runtime from the previously observed concurrent host-call registration race.
7. Return `exec_ms` for the documented runner execution interval.
8. Report current exported guest linear memory through `mem_bytes`, without representing it as peak guest or host memory.
9. Keep host filesystem and network capabilities narrow and verify concrete behavior through tests rather than assuming complete isolation.

### Remaining Limitations

The following limitations must remain visible in the final project report:

- Peak guest-memory allocation is not measured.
- Total host-process and peak physical memory are not measured by `mem_bytes`.
- The filesystem and network probes are historical and limited to the specific tested attempts.
- The host-function capability boundary requires ongoing security review.
- The memory-bomb pytest placeholder remains skipped during ordinary test-suite execution, although a separate bounded Docker test passed.
- Linux interruption testing was performed in a Docker Desktop Linux environment, not on a native Linux production host.
- The 50 ms end-to-end performance target has not been established as achieved.
- The November 5 load benchmark is short-duration and does not establish sustained production capacity.
- The project has not undergone a comprehensive independent penetration test.

These results support a working prototype with documented and tested resource controls. They do not constitute a complete security certification or unrestricted production-readiness assessment.

## 12. Final Engineering Verification Summary

Verified main revision: `2e1c11c`

### Backend and Runtime

| Verification                   | Observed result       |
| ------------------------------ | --------------------- |
| Full backend test suite        | 103 passed, 1 skipped |
| Focused regression suite       | 36 passed             |
| Linux interruption regression  | 2 passed              |
| Direct runner timeout/recovery | 20 cycles passed      |
| Live Linux server recovery     | 20/20 cycles passed   |
| Docker server exit code        | 0                     |
| Docker server OOMKilled        | false                 |

### Memory and Security

| Verification                     | Observed result                   |
| -------------------------------- | --------------------------------- |
| Memory-bomb execution            | `memory_exceeded`                 |
| Post-memory recovery execution   | Passed                            |
| Post-memory health check         | Passed                            |
| Docker post-test memory snapshot | 76.22 MiB / 512 MiB               |
| Docker memory-test exit code     | 0                                 |
| Docker memory-test OOMKilled     | false                             |
| Historical filesystem probe      | No `/etc/passwd` content returned |
| Historical socket probe          | Socket module import failed       |

### Performance

| Verification                       | Observed result |
| ---------------------------------- | --------------- |
| Final-main HTTP benchmark          | Passed          |
| Successful HTTP requests           | 36/36           |
| Failed requests                    | 0               |
| Highest tested concurrency         | 20              |
| Highest measured throughput        | 16.83 req/s     |
| p95 HTTP latency at concurrency 20 | 30.85 ms        |
| Post-benchmark health check        | Passed          |

### Frontend and Integration

| Verification                 | Observed result |
| ---------------------------- | --------------- |
| Team PR integration          | Complete        |
| PR #30 backend CI            | Passed          |
| PR #30 frontend CI           | Passed          |
| Frontend production build    | Passed          |
| End-to-end integration cases | 8/8 passed      |
| Manual UI testing            | Passed          |

### Final Assessment

The final integrated WasmBox revision demonstrates:

- Successful Python execution through the MicroPython WASI interpreter.
- Fresh per-execution Store and Instance creation.
- Fuel and wall-clock execution controls.
- Memory-exhaustion classification for the tested malicious workload.
- Repeated timeout and recovery behavior.
- Successful recovery of a live Linux-containerized backend.
- Successful concurrent HTTP execution at the tested concurrency levels.
- Frontend and backend integration with the agreed API contract.

These conclusions apply to the specific environments, revisions, configurations, and workloads documented in this report.

The project should be presented as a working WebAssembly-based Python execution sandbox with tested resource controls and explicitly documented security limitations, not as a completely audited or universally secure sandbox.

## References

1. [WebAssembly Security Overview](https://webassembly.org/docs/security/?utm_source=chatgpt.com)
2. [WASI Design Principles](https://github.com/WebAssembly/WASI/blob/main/docs/DesignPrinciples.md?utm_source=chatgpt.com)
3. [WASI Capability Model](https://github.com/WebAssembly/WASI/blob/main/docs/Capabilities.md?utm_source=chatgpt.com)
4. [Wasmtime: Interrupting Wasm Execution](https://docs.wasmtime.dev/examples-interrupting-wasm.html?utm_source=chatgpt.com)
5. [Wizer: WebAssembly Pre-initializer](https://github.com/bytecodealliance/wizer?utm_source=chatgpt.com)
6. [CNCF: Components vs. Containers](https://www.cncf.io/blog/2025/04/09/components-vs-containers-fight/?utm_source=chatgpt.com)
