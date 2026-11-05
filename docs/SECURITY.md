# WasmBox Security

**Project:** WasmBox Sandbox
**Verified revision:** `2e1c11c`
**Last verification:** 2026-11-05
**Status:** Security controls tested; remaining limitations documented.

## 1. Security architecture

WasmBox executes user-provided Python code through a MicroPython WebAssembly runtime managed by Wasmtime.

The objective is to restrict guest execution, control resource consumption, and prevent one execution from interfering with another.

The main implementation is:

`backend/app/runtime/micropython_runner.py`

### Execution architecture

```text
WasmBox Host Process
│
├── Wasmtime Engine
│   └── Shared compiled MicroPython Module
│
├── Epoch Ticker
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
    ├── WASI execution
    │
    ├── stdout / stderr capture
    │
    └── Result collection
        ├── status
        ├── exec_ms
        └── mem_bytes
```

### Runtime isolation

The runner follows these lifecycle rules:

- The Wasmtime Engine and compiled Module are shared across executions.
- Every `run_plugin()` invocation creates a fresh Store.
- Every execution creates a fresh Instance.
- Execution-specific fuel and timeout deadlines are configured on the Store.
- Guest execution results are collected and converted into a `PluginResult`.

Fresh Store and Instance creation helps prevent guest execution state from being unintentionally shared between separate runs.

This design does not, by itself, establish complete process-level or operating-system isolation.

## 2. Resource-limit enforcement

The runner implements multiple resource-control mechanisms.

| Resource | Configuration | Enforcement mechanism |
|---|---|---|
| MicroPython heap | `2M` | MicroPython heap allocator |
| Wasmtime linear memory | 10 MiB | `Store.set_limits()` |
| Instruction fuel | 30,000,000 | Wasmtime fuel accounting |
| Wall-clock timeout | 0.25 seconds default | Wasmtime epoch interruption |
| Store instances | 1 | Wasmtime Store limits |
| Store memories | 1 | Wasmtime Store limits |
| Store tables | 8 | Wasmtime Store limits |
| Table elements | 10,000 | Wasmtime Store limits |

Configuration constants are maintained in:

`backend/app/runtime/micropython_runner.py`

The wall-clock timeout and fuel mechanisms both protect against excessive execution, but they are different limits.

Fuel exhaustion and timeout interruptions are classified as `timeout`.

### Memory enforcement

WasmBox has two distinct memory boundaries:

**MicroPython heap**

The configured MicroPython heap is 2 MB.

An uncaught `MemoryError` is converted by the guest wrapper into a reserved WASI exit code:

`MEMORY_ERROR_EXIT_CODE = 86`

The host runner recognizes this result and returns `memory_exceeded`.

**Wasmtime linear memory**

The runner also configures a Wasmtime Store memory limit of 10 MiB.

When recognized linear-memory exhaustion occurs, the runner classifies the result as `memory_exceeded`.

A guest-generated error message alone is not sufficient to prove that a host-side resource limit was enforced.

### Memory reporting

The runner implements `_measure_memory()` to inspect exported guest linear memory.

Important distinctions:

- `mem_bytes` represents current guest linear memory in bytes.
- It is not peak guest memory allocation.
- It is not total host-process memory.
- It is not the Docker container's total memory consumption.

If memory inspection is unavailable, the runner may return zero rather than incorrectly report an unavailable measurement.

### Execution-time reporting

`exec_ms` records the execution duration according to the runner's timing boundaries.

Engine and compiled-module initialization are shared and excluded from the documented per-run execution metric.

It should not be interpreted as the complete HTTP response time.

## 3. Timeout and interruption verification

The Linux interruption regression test is:

`backend/tests/test_linux_interruption_regression.py`

It contains two tests:

1. Repeated runner-level timeout and recovery cycles.
2. Backend execution and health-check verification after interruption.

### Linux container regression results

**Environment:**

| Parameter | Result |
|---|---|
| OS | Debian GNU/Linux 13 |
| Python | 3.12.16 |
| Wasmtime | 49.0.0 |
| Container memory cap | 512 MB |
| CPU limit | 2 |
| Pytest result | 2 passed |
| Pytest exit code | 0 |

The runner-level test completed 20 timeout and recovery cycles.

### Live Uvicorn server verification

A separate Docker container was used to verify recovery through the actual HTTP API.

For each of 20 cycles:

1. Submit an infinite-loop program.
2. Confirm the runner returns `timeout`.
3. Submit a normal recovery program.
4. Confirm the recovery execution returns `ok`.
5. Check the `/health` endpoint.

**Results:**

| Check | Result |
|---|---|
| Timeout responses | 20/20 |
| Recovery executions | 20/20 |
| Health checks | 20/20 |
| Docker exit code | 0 |
| OOMKilled | false |
| Container cleanup | Successful |

The Linux verification used Docker Desktop's Linux container environment on a Windows development machine. It was not performed on a native Linux host.

The live API response reports a combined wall-clock or instruction-fuel timeout reason. The test confirms the expected timeout status, not that every live API interruption was exclusively caused by the wall-clock deadline.

## 4. Memory-exhaustion security verification

The memory-bomb plugin is:

`plugins/malicious/memory_bomb.py`

It attempts to allocate 200 MB using repeated 1 MB bytearrays.

The plugin must never be executed directly using ordinary Python on the developer's host.

### Isolated Docker verification

**Environment:**

- Linux Docker container.
- Memory limit: 512 MB.
- Memory swap: 512 MB (configured equal to the memory limit).
- CPU limit: 2.
- Backend running through Uvicorn.

**Observed API result:**

```json
{
  "status": "memory_exceeded",
  "stdout": "",
  "stderr": "Execution stopped: sandbox memory limit exceeded.",
  "exec_ms": 2.15,
  "mem_bytes": 2293760
}
```

### Recovery verification

Following the memory-bomb execution:

- A normal Python program executed successfully.
- The recovery output was `memory recovery successful`.
- The API health endpoint returned `{"ok": true}`.
- Docker reported a subsequent memory snapshot of 76.22 MiB out of 512 MiB.
- Container exit code was 0.
- `OOMKilled` was false.

The container was stopped and removed successfully.

**Conclusion:** The tested memory-intensive workload was classified as `memory_exceeded`, and the backend remained operational afterwards.

This is evidence for the tested MicroPython heap-exhaustion scenario. It is not proof against every possible memory-exhaustion attack.

### Automated test status

The automated test `test_memory_bomb_is_stopped()` in `backend/tests/test_security_plugins.py` remains intentionally skipped on the ordinary development test run.

Its skip reason requires execution in an isolated environment with an explicit process/container memory cap.

The separate Docker verification above is recorded as manual security-test evidence. The skipped pytest test has not been converted into an automatically passing test.

## 5. Filesystem and network access audit

An earlier security audit was conducted on 2026-10-28 against revision `db0e0f4`.

The audit used the FastAPI TestClient and two malicious plugins.

| Plugin | Attempt | Observed result |
|---|---|---|
| `read_passwd.py` | Read `/etc/passwd` | `OSError: [Errno 44] ENOENT` |
| `open_socket.py` | Import socket and connect to `1.1.1.1:80` | `ImportError: no module named 'socket'` |

Both requests returned HTTP 200 with execution status `error`.

The filesystem probe returned no `root:` content. The socket probe could not import the socket module and did not print `connected`.

### Important qualification

These are historical results from revision `db0e0f4`.

They are not presented as fresh verification of every filesystem and network restriction in revision `2e1c11c`.

The current runner's WASI configuration and host-capability registration should be reviewed against the final revision before making broader claims about filesystem or network isolation.

## 6. Host functions and capability boundaries

The project contains host-function implementation and acceptance-test work.

The focused regression suite included:

`backend/tests/test_host_functions.py`

The test suite passed as part of the 36-test regression run.

However, a passing test suite does not automatically prove that every possible host capability is restricted.

The security review should establish:

- Which host functions are actually registered.
- Which arguments each function accepts.
- Whether arguments are validated and size-limited.
- Whether host calls are available only to intended executions.
- Whether one execution can access another execution's state.
- Whether unregistered capabilities are inaccessible.

Only explicitly verified capabilities should be described as part of the supported host-function allowlist.

Arbitrary host filesystem access, unrestricted networking, and unrestricted host callbacks must not be exposed to guest code.

## 7. API status and error handling

The runner and API distinguish different execution outcomes.

| Status | Meaning |
|---|---|
| `ok` | Guest execution completed successfully |
| `error` | Guest execution or other execution failure |
| `timeout` | Fuel exhaustion or timeout interruption |
| `memory_exceeded` | Recognized memory-limit exhaustion |
| `denied` | Reserved for a verified host-side policy denial where supported by the API contract |

A guest-generated error string alone must not be interpreted as proof of host-side enforcement.

Likewise, an ordinary missing-file error must not automatically be classified as `denied`.

## 8. Security findings and limitations

| Finding | Severity | Current position |
|---|---|---|
| MicroPython heap exhaustion | High relevance | Tested Docker memory-bomb execution returned `memory_exceeded` |
| Wasmtime linear-memory enforcement | High relevance | Configured; tested exhaustion classification requires interpretation of the specific failure path |
| Timeout interruption | High relevance | 20 runner cycles and 20 live-server cycles passed |
| Concurrent execution isolation | High relevance | Focused concurrency regression tests passed |
| Filesystem restrictions | Medium | Historical probe passed; final-revision revalidation remains necessary |
| Network restrictions | Medium | Historical socket-import probe passed; final-revision revalidation remains necessary |
| Host-function capability boundary | High relevance | Focused tests passed; complete allowlist review should be documented |
| Guest memory reporting | Informational | Current linear memory, not peak or total host memory |
| Error disclosure | Review area | Continue checking that host paths and internal implementation details are not exposed |

### Known limitations

WasmBox security testing does not establish that the sandbox is immune to every possible attack.

In particular:

- Only specific malicious workloads have been tested.
- Filesystem and network audit results come from an older revision.
- The memory metric does not measure peak physical or host-process memory.
- Docker container limits are additional isolation controls, not substitutes for guest memory enforcement.
- The tested Linux environment was Docker Desktop rather than a native production Linux server.
- Security tests do not constitute an independent penetration test.
- Further review of the host-function capability boundary remains important.

## 9. Security verification summary

**Verified revision:** `2e1c11c`

| Verification | Observed result |
|---|---|
| Full backend tests | 103 passed, 1 skipped |
| Focused regression suite | 36 passed |
| Linux runner interruption | 20 cycles passed |
| Live Linux server recovery | 20/20 cycles passed |
| Memory-bomb Docker test | `memory_exceeded` |
| Post-memory recovery | Passed |
| Container OOMKilled | false |
| Container shutdown | Exit code 0 |
| Historical filesystem probe | No `/etc/passwd` content returned |
| Historical network probe | Socket import failed |

### Final security position

The tested WasmBox runtime demonstrates timeout interruption, execution recovery, guest memory exhaustion handling, and continued backend availability under the recorded test conditions.

These results provide evidence for the specific controls tested. They should not be represented as proof of complete sandbox security.

Future security work should prioritize final-revision filesystem and network testing, host-function allowlist review, and broader adversarial testing.
