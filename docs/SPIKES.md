# Spikes

Short, time-boxed investigations. Write what you tried, the exact commands and output, and a recommendation.

## Prathamesh: host functions

### Proof A — WASM calls a Python host function

Environment for the original proof:
- Docker Ubuntu 24.04
- Python 3.12.3
- extism 1.1.1
- extism-sys 1.12.0
- WABT 1.0.34

The WASM module imported `app::log` and called the Python host function with the integer value `42`.

Original execution output:

```text
WASM loaded: 54 bytes
Calling WASM...
host received: 42
WASM call completed
```

Result:

**PASS.**

A WASM module successfully imported `app::log` and invoked a Python-defined host function with the integer value `42`.

The proof was later reproduced in the Windows project `.venv` with:
- extism 1.1.1
- extism-sys 1.21.0
- WABT 1.0.34
- Wasmtime 25.0.0

The reproduced Windows test also passed:

```text
WASM loaded: 54 bytes
Creating Extism plugin...
Calling WASM...
HOST RECEIVED: 42
Completed.
```

---

### Proof B — WASM passes pointer and length to a Python host function

Goal:

Test whether a WASM module can pass a pointer and length to a Python host function and allow the host to read guest memory.

The WASM module contained:

```text
hello from the plugin
```

and called the host function with:

```text
pointer = 0
length = 21
```

The host function was successfully invoked and received the expected pointer and length parameters.

However, reading the guest memory through the Extism Python SDK did not succeed. `CurrentPlugin.memory_at_offset()` returned a memory reference whose accessible buffer had length `0`.

Observed result:

```text
ptr: 0
length: 21
memory reference: <extism.extism.Memory object ...>
buffer type: <class '_cffi_backend.buffer'>
buffer length: 0
buffer bytes: b''
```

Result:

**PARTIAL.**

The host-call mechanism works for pointer/length parameters, but guest-memory access from the Python host function was not resolved during this time-boxed spike.

---

### Proof C — Unsupplied host function is rejected

The WASM module imported:

```text
host::delete_everything
```

while the host only supplied the allowed `log` function.

Command:

```powershell
python backend/scripts/host_whitelist_demo.py
```

Observed output:

```text
Blocked as expected: WasmtimeError - incompatible import type for `host::delete_everything`

Caused by:
    types incompatible: expected type `(func)`, found type `(func (param i32))`
```

Result:

**PASS.**

The module was rejected during instantiation because the requested host import was not compatible with the host-provided imports.

This demonstrates that the host controls which imports are available; it does not by itself prove that every possible form of host access is blocked.

---

### Proof D — Extism Route 1: Python-defined host function

Goal:

Determine whether Extism can provide the host-function mechanism required by WasmBox.

Environment:
- Windows PowerShell
- Python project `.venv`
- Python 3.12.x
- extism 1.1.1
- extism-sys 1.21.0
- WABT 1.0.34
- Wasmtime 25.0.0

WAT module:

```wat
(module
  (import "app" "log" (func $log (param i64)))

  (func (export "run")
    i64.const 42
    call $log
  )
)
```

The WAT was compiled using WABT 1.0.34.

The generated WASM was 54 bytes and validated successfully with Wasmtime:

```text
Wasmtime validation: OK
```

Python host function:

```python
@extism.host_fn(name="log", namespace="app")
def log(value: int):
    print(f"HOST RECEIVED: {value}")
```

Execution:

```text
WASM loaded: 54 bytes
Creating Extism plugin...
Calling WASM...
HOST RECEIVED: 42
Completed.
```

Result:

**PASS for WASM → Python host invocation.**

Extism successfully allows a WASM module to invoke a Python-defined host function on Windows in the project `.venv`.

This does not yet prove the complete WasmBox requirement:

```text
Python plugin code
    ↓
Python interpreter running inside WASM
    ↓
host function
    ↓
Python host
```

The repository currently does not contain a Python interpreter running inside WASM. The existing WasmBox runtime uses Wasmtime directly to execute WASI modules.

Therefore the complete Python-plugin → host-function path remains:

**NOT PROVEN.**

The separate Python interpreter/Wizer investigation owned by Vineet needs to establish this part before Extism Route 1 can be selected for the final architecture.

---

### Recommendation

Extism is technically promising for the host-function layer.

Recommended decision:

1. Keep the Extism host-function proof as a feasibility result.
2. Do not integrate Extism into `backend/app/runtime/wasm_host.py` yet.
3. Resolve the Python-in-WASM/interpreter approach first.
4. Re-test whether Python code running inside the WASM interpreter can call the host function.
5. If that path is not practical within the required security and deployment constraints, use the structured stdout/JSON action approach as the fallback.

Current Block D status:

**PARTIAL / PROMISING — dependent on Python-in-WASM interpreter investigation.**

---

## Vineet: Python interpreter in WASM, and Wizer

### Day 3: Python-in-WASI Runtime Evaluation

#### 1. Candidates Investigated

| Candidate | Binary Size | Stdlib on Disk Required? | Startup Latency | Sandbox Isolation |
|---|---|---|---|---|
| **MicroPython WASI** (`micropython-wasm` 0.1a2) | **362.2 KB** (370,907 B) | **No** (Fully self-contained) | ~220ms – 420ms | Excellent (Zero host FS mount required) |
| **CPython WASI** (wasi-sdk / VMware Wasm Labs) | ~25 MB – 35 MB | **Yes** (`/lib/python3.x` required) | ~800ms – 2500ms | Moderate (Requires mounting stdlib directory) |

---

#### 2. Detailed Findings

##### Candidate A: MicroPython in WASI
- **Package / Binary**: Tested via `micropython-wasm` v0.1a2 (`micropython-wasi.wasm`, 362.2 KB).
- **Execution Test**:
  ```python
  from micropython_wasm import run
  result = run('print("hi")')
  # stdout: 'hi\n'
  ```
- **Benchmark Results** (`backend/scripts/spike_interpreter.py`):
  - `print('hi')`: 422.8 ms (initial cold start)
  - `sum(range(100))`: 223.9 ms
  - Multi-line loops: 268.7 ms
  - Syntax/Runtime Error (`raise ValueError`): ExitTrap with code 1 in 248.4 ms
- **Stdlib on Disk**: **None**. MicroPython bundles core modules directly inside the binary. Does not need any host directory mounted via WASI `preopen_dir`.
- **Security Boundary**: Maximizes isolation. The WASI sandbox can run with zero directory capabilities, preventing filesystem leakage or escape.
- **Runtime Requirement**: Requires wasmtime engine with exceptions proposal support (`wasmtime >= 49.0.0`).

##### Candidate B: CPython in WASI
- **Binary Size & Stdlib**: CPython builds (such as CPython 3.11/3.12 for WASI) are 25–35 MB and require a full extracted standard library directory on disk (`/lib/python3.x`).
- **Disk Impact**: Without preopened directories, CPython panics at startup (`Fatal Python error: init_fs_encoding: failed to get Python codec`).
- **Security Impact**: Mounting host folders creates operational overhead (distributing and packaging stdlib) and increases the attack surface if directory permissions are misconfigured.
- **Startup Latency**: High cold-start time (800ms – 2500ms) without pre-initialization.

---

#### 3. Interim Notes (Day 3)
- MicroPython WASI emerged as the top candidate for Week 2.
- Next step for Day 4: Investigate Wizer pre-initialization on MicroPython and finalize recommendations.

---

### Day 4: Wizer Pre-initialization & Final Spike Evaluation

#### 1. Wizer Investigation (Time-box Findings)

- **Tooling Objective**: Evaluate whether **Wizer** (`bytecodealliance/wizer`) can pre-initialize the Python runtime state into the WASM snapshot to eliminate cold-start latency (aiming for sub-50ms execution).
- **How Wizer Operates**:
  - Requires an exported initialization entrypoint (typically `wizer.initialize`).
  - Executes the init function at build time, takes a snapshot of the instance's linear memory and globals, and outputs an initialized `.wasm` file.
  - **Critical Constraint**: Modules *cannot* call imported host functions that perform external I/O (such as WASI file descriptor reads/writes, clocks, or environment calls) during the initialization phase.

- **Findings & Evidence**:
  - **MicroPython WASI (`micropython-wasi.wasm`)**:
    - **Result**: **Direct off-the-shelf Wizer snapshotting failed / not viable without C source rebuild.**
    - **Evidence**:
      1. Prebuilt binaries export standard WASI `_start` rather than a designated `wizer.initialize` hook.
      2. Standard WASI runtime startup executes initial WASI system calls (`environ_sizes_get`, `fd_read`, `clock_time_get`) to inspect environment and terminal state. Wizer disallows unmocked WASI I/O imports during snapshotting, leading to instant traps or initialization aborts.
      3. Splitting `mp_init()` into an isolated WASM export and stubbing out all WASI calls requires patching the MicroPython C runtime and compiling with `wasi-sdk`, which is beyond the 1-day spike boundary.
  - **CPython WASI (`componentize-py` / CPython)**:
    - **Result**: Tools like `componentize-py` do use Wizer successfully, but they rely on an extensive Rust toolchain, a Component Model wrapper, and hefty runtime assets (>25 MB) with high cold-start times if snapshots are not finely tuned.
- **Is Wizer Necessary for Week 2?**:
  - **No.** MicroPython WASI without snapshotting already executes trivial scripts in **~220ms – 260ms** (and ~420ms on initial cold start). For interactive code execution in a student playground, 220ms is well within acceptable latency bounds.

---

#### 2. Summary & Core Answers

1. **Chosen Interpreter Candidate**:
   - **MicroPython WASI** (`micropython-wasi.wasm` via `micropython-wasm` 0.1a2, binary size: 362.2 KB).
2. **Exact Command and Output to Run Code**:
   ```python
   from micropython_wasm import run
   result = run('print("hi")')
   print(result.stdout)
   # Output:
   # hi\n
   ```
3. **Does it need a stdlib directory on disk?**:
   - **No.** MicroPython compiles core primitives and standard library subsets directly into the WebAssembly binary. No `/lib/python3.x` directory or host directory mount (`preopen_dir`) is required.
4. **Did Wizer work?**:
   - **No.** Off-the-shelf WASI binaries cannot be snapshotted directly due to missing initialization exports and disallowed WASI I/O imports during snapshot creation.
5. **Concrete Recommendation for Week 2 Implementation**:
   - Use **MicroPython WASI** (`micropython-wasi.wasm`) driven by `wasmtime >= 49.0.0` (with the WebAssembly exceptions proposal enabled).
   - Configure a fully sealed `WasiConfig` (pipes for stdin/stdout/stderr, zero pre-opened directories, no network access).
   - Map guest exit codes (such as exit code 1 on unhandled Python exceptions) to the standard API response: `status: "error"`.
6. **Fallback Plan**:
   - If user code requires third-party packages or full CPython standard library modules not supported by MicroPython:
     - **Option 1**: Mount an extracted CPython WASI root read-only in a sandboxed directory.
     - **Option 2**: Run a isolated containerized worker process using standard Docker isolation.

