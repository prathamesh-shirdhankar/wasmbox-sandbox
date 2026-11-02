# Security

How the sandbox protects the server, and the evidence that it works.

## How WASI limits access (Priya)

## What is WASI, and why does it protect us?

A WebAssembly (WASM) module runs within a constrained runtime. It cannot use host capabilities unless the runtime exposes them. WASI (WebAssembly System Interface) defines standard host interactions such as writing bytes to stdout (`fd_write`) or opening a file (`path_open`).

A request for a capability is not itself permission to use it. The host/runtime decides which capabilities are available. A module can access a directory only when the runtime explicitly grants access to it.

The current execution path is `backend/app/runtime/micropython_runner.py`. Its call to `micropython_wasm.run` does not pass `readonly_dir` or `host_functions`. The tests below record the observed outcomes for the two audit plugins. These checks are evidence for these specific attempts, not proof against every possible file or network attack.

Execution timing and resource limits are separate protections. At the time of this audit, `exec_ms` is still returned as `0` and memory usage is not measured. See `docs/SPIKES.md` for recorded startup measurements.

## Audit log

**Audit date:** 2026-10-28

**Test path:** local FastAPI `TestClient` posting the plugin source to `POST /run`
**Tested backend revision:** `db0e0f4` (capture this with `git rev-parse --short HEAD` before applying the audit-test and documentation patch; the runner code was unchanged during the tests.)

| Date | Tested revision | Plugin | Attempt | HTTP response | `status` | `stdout` | Exact exception message | Outcome |
|---|---|---|---|---:|---|---|---|---|
| 2026-10-28 | `db0e0f4` | `read_passwd.py` | Read `/etc/passwd` | 200 | `error` | Empty | `OSError: [Errno 44] ENOENT` | Pass: no `root:` content was returned; file open failed. |
| 2026-10-28 | `db0e0f4` | `open_socket.py` | Import `socket` and connect to `1.1.1.1:80` | 200 | `error` | Empty | `ImportError: no module named 'socket'` | Pass: the socket module could not be imported and `connected` was not printed. |

The exact stderr values captured from the API were:

`read_passwd.py`:
```text
Traceback (most recent call last):
  File "<string>", line 4, in <module>
OSError: [Errno 44] ENOENT
```

`open_socket.py`:
```text
Traceback (most recent call last):
  File "<string>", line 4, in <module>
ImportError: no module named 'socket'
```

Both observed outcomes were `error`, not `denied`. The HTTP endpoint itself returned `200`, because the execution outcome is represented in the response body.

### What this audit does not prove

- It tests these two attack scripts only; it does not prove every possible host-file or network attack is blocked.
- It does not test timeout enforcement or memory exhaustion. The infinite-loop test remains skipped until the timeout implementation is verified, and the memory-bomb test remains skipped because measured memory enforcement is not established.
- `mem_bytes` is a placeholder (`0`); memory usage is **not measured**.
- `exec_ms` is currently a placeholder (`0`); real API execution timing remains to be implemented.


---

## Runner Architecture & Security Review

### 1. Architectural Model & Lifecycle Isolation

The runtime redesign replaces black-box invocations with a custom-managed Wasmtime pipeline:

```text
┌─────────────────────────────────────────────────────────────────┐
│ Host Process Lifetime                                          │
│  ├── Engine (Wasmtime, epoch_interruption=True)                │
│  ├── Module (pre-compiled MicroPython WASI binary)             │
│  └── Epoch Ticker Thread (background 5ms increments)           │
└────────────────────────────────┬────────────────────────────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
           │ Per-Execution Invocation (run_plugin)     │
           │  ├── Store (fresh per request)            │
           │  │    ├── Fuel allocation (30M)           │
           │  │    └── Epoch deadline (wall-clock)     │
           │  ├── Instance (instantiated per request)  │
           │  └── Linear Memory Introspection          │
           └───────────────────────────────────────────┘
```

* **Store & Instance Lifecycle:** Every `run_plugin` call creates a fresh `Store` and `Instance`. State does not persist across executions; global variables, heap allocations, and modified buffers in guest memory are immediately garbage-collected with the `Store` teardown.
* **Engine & Module Sharing:** The Wasmtime `Engine` and compiled `Module` are immutable and thread-safe, initialized once under `_RUNTIME_LOCK` via double-checked locking (`_get_runtime()`).
* **Timeout Isolation:** Epoch ticks are driven by a dedicated daemon ticker thread (`wasmbox-epoch-ticker`) advancing epochs every 5 ms. Synchronization between `engine.increment_epoch()` and `store.set_epoch_deadline()` is mediated via `tick_lock`. Deadlines are per-Store, ensuring concurrent requests do not corrupt or prematurely trigger each other's deadlines.

---

### 2. Resource Limit Enforcement & Dual-Ceiling Model

The investigation resolved the exact memory-exhaustion classification boundary by identifying the dual memory ceiling:

| Limit Layer | Configured Size | Mechanism | Failure Manifestation | Status Classification |
|---|---|---|---|---|
| **MicroPython Heap** | `2M` (`MICROPYTHON_HEAP_SIZE`) | MicroPython internal heap allocator | Guest `MemoryError` trapped in `_wrap` → `SystemExit(86)` | `memory_exceeded` |
| **Wasmtime Linear Memory** | `10 MiB` (`DEFAULT_MEMORY_BYTES`) | Wasmtime Store memory boundary / page growth | `TrapCode.MEMORY_OUT_OF_BOUNDS` / memory fault trap | `memory_exceeded` |
| **Instruction Fuel** | `30,000,000` | Wasmtime deterministic fuel counter | `TrapCode.OUT_OF_FUEL` trap | `timeout` |
| **Wall-Clock Timeout** | `0.05s` (default) | Wasmtime epoch interruption | Epoch deadline trap | `timeout` |

* **Observation:** The 2M MicroPython heap is the binding limit for guest Python allocations. Attempts by plugins to allocate unbounded arrays/lists exhaust the MicroPython heap at ~2.29 MiB of total linear memory (observed in Docker with `plugins/malicious/memory_bomb.py`), generating a `MEMORY_OUT_OF_BOUNDS` trap before the 10 MiB Wasmtime ceiling is reached. Both paths are now correctly classified as `memory_exceeded`.

---

### 3. Security Findings & Risk Matrix

| Finding ID | Component | Description | Severity | Status / Mitigation |
|---|---|---|:---:|---|
| **SEC-01** | `micropython_runner.py` | **Aggressive Default Wall Timeout:** The default wall-clock limit was lowered to 50 ms. While infinite loops are halted, legitimate compute-heavy plugins may experience false timeouts. | **Medium** | Recommended increasing `DEFAULT_WALL_TIMEOUT_SECONDS` to `0.25s` (250 ms) in production configuration. |
| **SEC-02** | `micropython_runner.py` | **OOB Trap Specificity:** `TrapCode.MEMORY_OUT_OF_BOUNDS` is mapped to `memory_exceeded`. However, native runtime bugs or invalid pointer dereferences in the interpreter could theoretically be masked as memory exhaustion rather than runner errors. | **Low** | Current heuristic also inspects fault address strings. Hardened in test suite (`test_limits.py`). |
| **SEC-03** | `micropython_runner.py` | **Private Host-Call Coupling:** Host function registration accesses `run.__globals__["_define_host_call"]` from `micropython-wasm==0.1a2`. While functional, dependency updates could break initialization. | **Low** | Mitigated by fail-fast check in `_get_runtime()` with explicit error message. Recommend pin enforcement or vendored bridge in Phase D. |
| **SEC-04** | `routes.py` / `_wrap` | **Information Leakage in Stderr:** Guest exceptions strip wrapper frames via `_clean_error()` and error marker regex, ensuring host paths (e.g. `micropython_runner.py`) are not leaked in the API response. | **Informational** | Verified in `test_unusual_inputs.py` and `test_runner_interface.py`. |
| **SEC-05** | Host Allowlist | **WASI Preopens & Host Function Surface:** `_run_once` registers an empty dict of host functions `{}` and passes no directory preopens to WASI. No file read/write, socket operations, or environment access are available to guest code. | **Informational** | Verified in `test_security_audit.py` and `test_security_plugins.py`. |

---