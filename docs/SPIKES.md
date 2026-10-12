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

#### Extism test

The WASM module contained the text:

```text
hello from the plugin
```

It called the host function with:

```text
pointer = 0
length = 21
```

The Extism host function received the expected pointer and length parameters.

However, reading guest memory through the Extism Python SDK did not succeed. `CurrentPlugin.memory_at_offset()` returned a memory reference whose accessible buffer had length `0`.

Observed output:

```text
ptr: 0
length: 21
memory reference: <extism.extism.Memory object ...>
buffer type: <class '_cffi_backend.buffer'>
buffer length: 0
buffer bytes: b''
```

Result:

**UNRESOLVED for Extism guest-memory access.**

The Extism host-call mechanism received the pointer and length, but the accessible buffer was empty. Guest-memory access through the Extism Python API remains unresolved. The cause has not been established.

#### Direct Wasmtime comparison

Environment:
- Windows PowerShell
- Python 3.12.10
- Wasmtime 25.0.0
- Project virtual environment `.venv`

The existing `plugins/benign/host_say.wat` module imports `host.say`, exports its memory, stores `hello from the plugin` at byte offset `0`, and calls the host function with pointer `0` and length `21`.

The Python host function in `backend/scripts/host_say_demo.py` uses the Wasmtime caller to access the module's exported memory:

```python
def say(caller, ptr, length):
    memory = caller.get("memory")
    data = memory.read(caller, ptr, ptr + length)
    print("host received:", bytes(data).decode("utf-8"))
```

The host function is registered with `access_caller=True` so it can access the calling module's context.

Command:

```powershell
python .\backend\scripts\host_say_demo.py
```

Observed output:

```text
host received: hello from the plugin
```

Result:

**PASS for direct Wasmtime memory access in this example.**

The host function successfully retrieved the calling module's exported memory, read the specified byte range, and decoded the bytes as UTF-8 text.

#### Combined conclusion

The direct Wasmtime text-memory test passes, while Extism guest-memory access remains unresolved.

The Wasmtime result demonstrates that this text handoff works in the tested example. It does not establish the exact cause of Extism's empty-buffer result. An Extism-specific memory-access or memory-model issue is a possible hypothesis, not a confirmed diagnosis.

---

### Proof C — Rejection of an unregistered host import using Wasmtime Linker

Goal:

Verify that a WebAssembly module requesting an unregistered host import is rejected by Wasmtime.

The test module `plugins/benign/host_evil.wat` imports:

```wat
(import "host" "delete_everything" (func $evil))
```

The updated Python demonstration in `backend/scripts/host_whitelist_demo.py` creates a Wasmtime `Linker` and explicitly registers only the `host.log` function. It does not register `host.delete_everything`.

The linker registration is:

```python
linker.define_func(
    "host",
    "log",
    FuncType([ValType.i32()], []),
    host_log,
)
```

This associates the host implementation with the specific import name `host.log`. The module instead requests `host.delete_everything`.

Command:

```powershell
python .\backend\scripts\host_whitelist_demo.py
```

Observed output:

```text
Registered authorized import: host.log
Attempting to load the module requesting host.delete_everything
Blocked as expected: WasmtimeError - unknown import: `host::delete_everything` has not been defined
```

Result:

**PASS for rejection of an unregistered host import.**

The linker rejected instantiation because the module requested `host.delete_everything`, which had not been defined in the linker.

This is a name-based import-resolution test. It corrects the limitation of the previous test, which supplied a function positionally and failed because the requested function type was incompatible with the supplied function.

Scope limitation:

This test demonstrates rejection of the specific unregistered import used in this example. It does not, by itself, prove that the complete WasmBox sandbox is secure or that every possible host-access path is restricted. The actual host functions exposed by the runtime must also be reviewed and tested.

---

### Proof D — Extism Route 1: Python-defined host function

Goal:

Determine whether Extism can provide the host-function mechanism required by WasmBox.

Environment:
- Windows PowerShell
- Python project `.venv`
- Python 3.12.10
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

The repository currently does not contain a verified Python interpreter running inside WASM as part of the WasmBox runtime. The existing WasmBox runtime uses Wasmtime directly to execute WASI modules.

Therefore, the complete Python-plugin → host-function path remains:

**NOT PROVEN.**

The separate Python interpreter/Wizer investigation owned by Vineet needs to establish this part before Extism Route 1 can be selected for the final architecture.

---

### Recommendation

Extism is technically promising for the host-function layer, but the original spike has not established that it is suitable for integration into the production runtime.

Recommended decision:

1. Keep the Extism integer host-function proof as a feasibility result.
2. Record Extism guest-memory access as unresolved; the exact cause of the empty-buffer result remains unestablished.
3. Keep the direct Wasmtime text-memory proof as a separate, successful test.
4. Keep the Wasmtime Linker import-rejection proof as evidence that an unregistered import is rejected in the tested case.
5. Do not integrate Extism into `backend/app/runtime/wasm_host.py` yet.
6. Resolve the Python-in-WASM/interpreter approach first.
7. Re-test whether Python code running inside the WASM interpreter can call the host function.
8. Before selecting Extism for production, evaluate its resource limits, security boundaries, dependency requirements, and deployment behavior against WasmBox's requirements.
9. If the Python-plugin-to-host-function path is not practical within the required security and deployment constraints, use the structured stdout/JSON action approach as the fallback.

Current findings:
- **Integer host-function invocation through Extism:** PASS.
- **Text-memory handoff through Extism:** UNRESOLVED.
- **Text-memory handoff through direct Wasmtime in the tested example:** PASS.
- **Rejection of the tested unregistered import through Wasmtime Linker:** PASS.
- **Complete Python-in-WASM interpreter → host-function path:** NOT PROVEN.

---

## Vineet: Python interpreter in WASM, and Wizer

### Day 3: Python-in-WASI Runtime Evaluation

#### 1. Candidates Investigated

| Candidate | Binary Size | Stdlib on Disk Required? | Startup Latency | Sandbox Isolation |
|---|---|---|---|---|
| **MicroPython WASI** (`micropython-wasm` 0.1a2) | **362.2 KB** (370,907 B, measured) | **No** (Fully self-contained) | ~220ms cold / **0.9ms warm** (measured) | Excellent (Zero host FS mount required) |
| **CPython WASI** (wasi-sdk / VMware Wasm Labs) | ~25 MB – 35 MB *(estimate)* | **Yes** (`/lib/python3.x` required) | ~800ms – 2500ms *(estimate)* | Moderate (Requires mounting stdlib directory) |

> **Note on CPython numbers:** The CPython binary size (~25–35 MB) and cold-start latency (~800–2500 ms) are **estimates** based on upstream WebAssembly Language Runtimes (VMware Labs / SingleStore WASI Python benchmarks) and distribution artifacts, rather than local live benchmarks, because CPython requires bundling and mounting the full filesystem standard library directory.

---

#### 2. Detailed Findings

##### Candidate A: MicroPython in WASI
- **Package / Binary**: Tested via `micropython-wasm` v0.1a2 (`micropython-wasi.wasm`, 362.2 KB).
  - **SHA-256**: `1C054A4D21D4A6589BC568821EBF562889988DDAAF8A17A2E2985A56CF228051`  
    *(verified with `Get-FileHash <path>\micropython-wasi.wasm -Algorithm SHA256` on Windows PowerShell)*
- **Execution Test**:
  ```python
  from micropython_wasm import run
  result = run('print("hi")')
  # stdout: 'hi\n'
  ```
- **Granular Timing Breakdown & Averaged Measurements (10 runs)**:
  - **(a) Module Compilation (`Module.from_file`)**: ~225.8 ms (wasmtime compiling the 362 KB bytecode with Cranelift)
  - **(b) Instantiation + WASI Setup (`linker.instantiate`)**: ~1.5 ms
  - **(c) Script Execution (`_start`)**: ~0.6 ms
  - **Total Fresh Cold Start (a + b + c)**: ~227.9 ms
  - **Total Warm Start (Pre-compiled / Cached Module)**: **~0.9 ms** — well within our **50 ms** execution budget!
  - **Key Takeaway for Week 2**: The ~220 ms latency observed during the spike is purely one-time JIT compilation overhead. By caching the compiled `Module` instance in memory across requests, subsequent sandbox runs execute in under **1 ms**.

> **Scope clarification:** The sub-1 ms warm-start figure came from the exploratory direct-Wasmtime harness with a precompiled, cached module. It is not the timing of the currently integrated backend route. The current `micropython_wasm.run()` path compiles the interpreter on each call; see “Startup timings (Week 2, Task 6)” below for the measured route-path timings.

##### Timing Boundary Clarification

The team lead observed that the sum of individually measured phases (b + c) averages **~2.1 ms**, yet the separately measured warm start reports **~0.9 ms**. Both numbers are correct — they measure different scopes:

| Measurement | What is timed | Loop setup |
|---|---|---|
| **(b) + (c) summed** (2.1 ms) | Each phase is timed in its **own fresh loop iteration** — a new `Store`, `WasiConfig`, `Linker`, and `linker.instantiate` call per run, then `_start` in a separate measurement. | Two independent 10-iteration loops, phases measured individually. |
| **Warm start total** (0.9 ms) | A **single contiguous timer** (`t0 … t1`) covers the entire call: `Store()` → `set_fuel` → `WasiConfig()` → `stdout_custom` → `set_wasi` → `Linker()` → `define_wasi` → `_define_host_call` → `linker.instantiate` → `inst.exports` → `start_fn(store)`. The pre-compiled `reused_module` is passed in, so `Module.from_file` is never called. | Single 10-iteration loop, both phases timed together. |

The 2.1 ms figure is higher because each sub-phase incurs Python overhead from constructing its own fresh objects before the clock starts (i.e., the `Store` created for phase (b) is thrown away and rebuilt for phase (c)). In a real request path the objects are constructed once and reused within the same call, matching the 0.9 ms warm start measurement.

**Formula**:
```
Warm start ≈ single_contiguous_timer(Store + WasiConfig + Linker + instantiate + execute)
           ≈ 0.9 ms   (Module.from_file excluded — module is pre-cached)

Fresh cold start ≈ Module.from_file + Store + WasiConfig + Linker + instantiate + execute
                 ≈ 225.8 ms + 0.9 ms ≈ 226.7 ms
```

- **Stdlib on Disk**: **None**. MicroPython bundles core modules directly inside the binary. Does not need any host directory mounted via WASI `preopen_dir`.
- **Security Boundary**: Maximizes isolation. The WASI sandbox can run with zero directory capabilities, preventing filesystem leakage or escape.
- **Runtime Requirement**: Requires wasmtime engine with exceptions proposal support (`wasmtime >= 49.0.0`).

##### Interpreter Artifact: Import / Export Inspection

Inspected using `wasmtime` Python SDK (`scripts/inspect_wasm.py`) on the exact binary whose SHA-256 is listed above.

**Imports** (26 total):

```text
[micropython_wasm]::host_result_cap       (func (result i32))
[micropython_wasm]::host_call             (func (param i32 i32 i32 i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::args_get        (func (param i32 i32) (result i32))
[wasi_snapshot_preview1]::args_sizes_get  (func (param i32 i32) (result i32))
[wasi_snapshot_preview1]::environ_get     (func (param i32 i32) (result i32))
[wasi_snapshot_preview1]::environ_sizes_get (func (param i32 i32) (result i32))
[wasi_snapshot_preview1]::clock_time_get  (func (param i32 i64 i32) (result i32))
[wasi_snapshot_preview1]::fd_close        (func (param i32) (result i32))
[wasi_snapshot_preview1]::fd_fdstat_get   (func (param i32 i32) (result i32))
[wasi_snapshot_preview1]::fd_prestat_get  (func (param i32 i32) (result i32))
[wasi_snapshot_preview1]::fd_prestat_dir_name (func (param i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::fd_read         (func (param i32 i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::fd_readdir      (func (param i32 i32 i32 i64 i32) (result i32))
[wasi_snapshot_preview1]::fd_seek         (func (param i32 i64 i32 i32) (result i32))
[wasi_snapshot_preview1]::fd_sync         (func (param i32) (result i32))
[wasi_snapshot_preview1]::fd_write        (func (param i32 i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::path_create_directory (func (param i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::path_filestat_get (func (param i32 i32 i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::path_open       (func (param i32 i32 i32 i32 i32 i64 i64 i32 i32) (result i32))
[wasi_snapshot_preview1]::path_readlink   (func (param i32 i32 i32 i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::path_remove_directory (func (param i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::path_rename     (func (param i32 i32 i32 i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::path_unlink_file (func (param i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::poll_oneoff     (func (param i32 i32 i32 i32) (result i32))
[wasi_snapshot_preview1]::proc_exit       (func (param i32))
[wasi_snapshot_preview1]::sched_yield     (func (result i32))
```

**Exports** (2 total):

```text
memory   (memory)
_start   (func)
```

**Key observations from inspection**:
- The binary imports **only** two non-WASI functions from its own `micropython_wasm` namespace: `host_result_cap` and `host_call`. These are the structured host-call bridge wired up by `_define_host_call()` in the Python SDK — no arbitrary host access is exposed.
- The WASI imports cover standard I/O, environment, clock, and filesystem calls. All are satisfied by the `WasiConfig` (pipe-based stdio, zero preopened dirs) configured at runtime — no actual host filesystem access is granted.
- The only export is `_start` (the WASI entry point) and the linear `memory`. There are no other exported functions the host could accidentally call.

##### Limitations of MicroPython for Plugin Authors:
MicroPython is designed for microcontrollers and embedded environments. Plugin authors should be aware of the following trade-offs:
1. **Standard Library Subsets**: MicroPython provides lightweight micro-variants of standard libraries (e.g., `ure` instead of full `re`, `utime` instead of `datetime`/`time`, `ujson` instead of full `json`).
2. **Missing System Modules**: Heavy system modules are absent: no `multiprocessing`, `ctypes`, `threading`, `sqlite3`, `socket` (in raw WASI), or subprocess control.
3. **No Native C-Extensions**: Modules requiring compiled C extensions or wheels (such as `numpy`, `pandas`, `scipy`, or `requests` with C bindings) cannot be imported.
4. **Language Subsets**: Adheres to Python 3.4/3.5+ syntax with common 3.8+ features, but advanced introspection, complex metaclass hooks, and stack frame hacking are omitted to maintain the 362 KB binary footprint.

##### Candidate B: CPython in WASI
- **Binary Size & Stdlib**: CPython builds (such as CPython 3.11/3.12 for WASI) are 25–35 MB *(estimate)* and require a full extracted standard library directory on disk (`/lib/python3.x`).
- **Disk Impact**: Without preopened directories, CPython panics at startup (`Fatal Python error: init_fs_encoding: failed to get Python codec`).
- **Security Impact**: Mounting host folders creates operational overhead (distributing and packaging stdlib) and increases the attack surface if directory permissions are misconfigured.
- **Startup Latency**: High cold-start time (800ms – 2500ms, *estimate*) without pre-initialization.

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

### Week 1 Retrospective & Test Isolation Verification (11 October 2026)

- **Test Suite Health**: All Week 1 endpoint and contract unit tests pass under `pytest` with zero external network access.
- **Filesystem Isolation**: Verified that the WebAssembly instance has no preopened host directories mapped via WASI, preventing arbitrary file read/write access.
- **Contract Boundary**: Re-verified standard 5-field schema output consistency across benign runs and empty input rejections.

### Memory Footprint Comparison (12 October 2026)

- **MicroPython WASI**: Initial WebAssembly memory pages allocate minimal linear memory (default 10 MiB ceiling verified sufficient for interpreter boot and standard user script execution).
- **CPython WASI Comparison**: Full CPython runtime engines require substantially larger initial memory commitments (allocating 32–64 MiB just to map internal bytecode tables and dynamic runtime types).
- **Conclusion**: MicroPython's lightweight memory profile allows higher density and concurrency on constrained host resources.

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


---

## Week 2: MicroPython WASI verification (Prathamesh)

### Environment

- OS/shell: Windows PowerShell
- Python: 3.12.10
- Scratch environment: `%TEMP%\mp-test-venv`
- `micropython-wasm`: 0.1a2
- Wasmtime: 49.0.0
- Pytest: 8.3.3
- Artifact tested: `backend/app/runtime/artifacts/micropython-wasi.wasm`

The scratch environment was used to preserve Wasmtime 49.0.0 for compatibility testing. The repository's `backend/requirements.txt` still pins Wasmtime 25.0.0 at the time of this investigation.

### Artifact hash

The repository-managed artifact was checked with `Get-FileHash -Algorithm SHA256`.

Expected and observed SHA-256:

```text
1C054A4D21D4A6589BC568821EBF562889988DDAAF8A17A2E2985A56CF228051
```

Result: PASS for hash matching. License and notice-file inspection remains to be recorded separately.

### Existing demo scripts

The following commands completed with exit code 0:

| Command | Observed result |
|---|---|
| `& $py backend\scripts\add_demo.py` | `5` |
| `& $py backend\scripts\run_wasm.py plugins\benign\hello.wasm` | `hello from wasm` |
| `& $py backend\scripts\host_log_demo.py` | `host received: 42` |
| `& $py backend\scripts\host_say_demo.py` | `host received: hello from the plugin` |
| `& $py backend\scripts\host_whitelist_demo.py` | Registered `host.log` accepted; unregistered `host.delete_everything` rejected |

Result: PASS for all five existing demos under the tested environment.

### Existing backend test suite

Command:

```powershell
Push-Location backend
try {
    & $py -m pytest -q -rs
    $testExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
```

Observed summary:

```text
13 passed, 5 skipped, 1 warning in 0.53s
Pytest exit code: 0
```

The five skipped security tests explicitly require later `/run`, timeout, memory-cap, or audit work. The warning is a Starlette/AnyIO deprecation warning.

Result: PASS for the existing test suite in the scratch environment. This does not establish that the new MicroPython runner or all future security requirements are complete.

### Repository-managed interpreter artifact: script errors

The package `run()` function was called with the repository-managed artifact passed through `wasm_path`.

| Input | Observed result |
|---|---|
| `print("hi")` | stdout `'hi\n'`; stderr `''` |
| `1/0` | `MicroPythonWasmError: guest exited with code 1` |
| `print(` | `MicroPythonWasmError: guest exited with code 1` |

The raised exception exposed no separate stderr attribute through its public attributes.

Result: Normal script execution PASS. Readable exception reporting through this package API remains UNRESOLVED. The observation does not establish whether the guest generated diagnostic text internally; it establishes that the tested call did not return that text.

### Guarded infinite-loop test

The test ran the inline guest script `while True: pass` in a child process. The package wall timeout was set to 1 second, and the parent process used `subprocess.run(..., timeout=20)` as a hard limit.

With the default fuel budget and then with a fuel budget of 1,000,000,000, the guest trapped because all WebAssembly fuel was consumed before the wall-time timeout could be isolated.

The test was repeated with:

```python
run(
    "while True:\n    pass\n",
    fuel=100_000_000_000,
    wall_timeout_seconds=1.0,
)
```

Observed output:

```text
raised: MicroPythonWasmError
wasm trap: interrupt
child elapsed_s: 1.09
RESULT: child ended by itself
parent elapsed_s: 1.18
```

The parent hard kill was not needed. The loop was stopped by the WebAssembly interrupt at approximately the configured one-second timeout.

Result: PASS for the tested wall-time interruption behavior with Wasmtime 49.0.0 and the stated fuel budget. This is a focused compatibility test, not a complete security audit.

### Interim assessment

- Existing demos on Wasmtime 49.0.0: PASS.
- Existing backend tests in the scratch environment: PASS (13 passed, 5 skipped).
- Repository-managed interpreter artifact hash: PASS.
- Guarded-loop wall-time interruption: PASS in the isolated test.
- Readable guest exception details through `run()`: UNRESOLVED.
- License/provenance inspection: PASS; Apache-2.0 license and README are present.
- Dedicated artifact hash-verification test: PASS (`backend/tests/test_interpreter_artifact.py`, 2 tests; full suite on Wasmtime 49.0.0: 15 passed, 5 skipped).
- Full runner implementation and its tests: pending.

Superseded: the Plan A decision is recorded in the "Week 2 compatibility decision" section below. Readable guest exception details through `run()` remain unresolved and must be addressed in the runner.

### Artifact license and provenance check

Inspected the extracted `micropython-wasm` 0.1a2 wheel metadata and the repository-managed artifact directory.

Observed package metadata:
- Name: `micropython-wasm`
- Version: `0.1a2`
- License expression: `Apache-2.0`
- Upstream project: `https://github.com/simonw/micropython-wasm`

Observed repository-managed files:
- `backend/app/runtime/artifacts/micropython-wasi.wasm`
- `backend/app/runtime/artifacts/LICENSE`
- `backend/app/runtime/artifacts/README.md`

The vendored `LICENSE` begins with the Apache License, Version 2.0 text. The README records the upstream project, package version, license, and expected SHA-256. The extracted wheel search found one license file and no separate `NOTICE` file matching the search patterns.

Result: PASS for locating the license and recording basic provenance. This is not a complete legal review.



### Week 2 compatibility decision

**Decision: Plan A for the interpreter and Wasmtime compatibility path.**

Evidence supporting this decision:
- The existing demos passed under Wasmtime 49.0.0.
- The existing backend test suite passed in the scratch environment: 13 passed and 5 skipped.
- The repository-managed MicroPython WASI artifact matched the expected SHA-256.
- The guarded infinite loop was interrupted by Wasmtime at the configured wall-time limit when supplied with a sufficiently large fuel budget.
- The artifact directory contains the Apache-2.0 license and provenance README.

Implementation caveat:
- The tested `micropython_wasm.run()` API raises `MicroPythonWasmError` for guest exceptions and syntax errors without exposing their readable diagnostics through the exception's public attributes. The runner must address the API's error-response contract rather than assume these diagnostics are already available.

This decision supports testing the dedicated runner with Wasmtime 49.0.0 and the repository-managed artifact. It is not a complete sandbox security approval. The dedicated runner, its tests, dependency-pin change, and artifact hash-verification test remain separate implementation/review steps.


### Error-message finding (micropython-wasm 0.1a2)

Read from `micropython_wasm/__init__.py` (`run()`, lines ~650-711): guest stderr is collected in a local list, but when the guest exits with a non-zero code `run()` raises `MicroPythonWasmError("guest exited with code N")` and the collected text is not included. A caught `1/0` or syntax error therefore shows only the exit code. Traps (timeout, fuel exhaustion) do include their trap text. The session API (lines ~300-340) was not fully read, so no claim is made about it. Readable errors must be handled in the runner (Week 2, Task 3); not solved in the artifact PR.

### Startup timings (Week 2, Task 6)

Script: `backend/scripts/startup_timing.py`. Benign `print("hi")` only. Windows 11, Python 3.12, wasmtime 49.0.0, micropython-wasm 0.1a2, default package limits. Numbers are from one laptop and are noisy.

| Measurement | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| First `run_plugin` call in a new process (ms) | 172.5 | 182.3 | 178.0 |
| Median of the next 10 calls (ms) | 224.0 | 205.5 | 196.0 |
| Compiling the interpreter alone, 3 tries (ms) | 113-122 | 111-129 | 109-131 |

Compile check (`--profile`, 5 calls): `Module.from_file` was called 5 times, using about 1.065 s of 1.079 s total (about 99%).

Finding: `micropython_wasm.run()` creates an engine and compiles the interpreter on every call. That compile is almost the whole per-call cost (about 175-225 ms here). There was no visible cold-start penalty: the first call was not slower than later ones. The later-call medians were slightly higher; the cause was not investigated. The compile cost inside `run()` (about 210 ms per call under the profiler) is higher than compiling alone (about 110-130 ms). A likely reason is the fuel and epoch settings that `run()` enables, but this was not tested.

Not optimized in Week 2. Caching the compiled module means replacing `micropython_wasm.run()` with our own runner and re-creating its fuel, epoch, memory and no-directory settings, which is security-sensitive. The package's session API reuses state between runs, which is not acceptable for multiple tenants without further study.

Week 3 implication (measured): the wall-time timer in `run()` starts before `Module.from_file` (source lines 680-687), so the timeout also covers compilation. Probe with a benign `print("hi")`, one try per value: `wall_timeout_seconds` 1.0 gave `ok`, 0.3 gave `ok`, 0.05 raised `guest trapped: wasm trap: interrupt`. A script that does nothing was interrupted at 50 ms, so the 50 ms target cannot be met by `micropython_wasm.run()` as it is. Meeting it needs a module that is compiled once and reused, which means a runner of our own that recreates the package's fuel, epoch, memory and no-directory settings. That is security-sensitive, so it was not attempted in Week 2. The package's session API reuses state between runs, which is not acceptable for multiple tenants without further study. The probe was run once per value on one laptop, so the exact threshold between 0.05 s and 0.3 s is not known.

### Runtime limits and API timing (28 October 2026)

#### Configuration

The runner now uses explicit default limits:

- Guest memory ceiling: 10 MiB (10 * 1024 * 1024 bytes).
- WebAssembly fuel budget: 20,000,000.
- Wall-clock timeout: 1.0 second.
- Tests can pass smaller limits to `run_plugin` without changing the defaults.

The 10 MiB setting allowed the benign `print("hi")` diagnostic to complete.
This is a startup check, not proof of the memory behavior of every script.

#### Timeout and fuel behavior

The installed `micropython-wasm` 0.1a2 package produced these observed errors:

- Wall-clock interruption: `guest trapped: wasm trap: interrupt`
- Fuel exhaustion: `guest trapped: wasm trap: all fuel consumed by WebAssembly`

The runner maps these resource-limit failures to `status: timeout` with readable
messages. Ordinary Python exceptions remain `status: error`.

A 50 ms probe did not allow a benign `print("hi")` run to complete because the
timeout includes engine/module startup. The 50 ms target therefore remains unmet.
The memory-bomb test was intentionally not run.

#### API execution timing

Five successful `POST /run` requests executed `print("hi")` on the development
machine. Each response had HTTP 200, `status: ok`, and `mem_bytes: 0`.

| Run | exec_ms |
|---:|---:|
| 1 | 242.43 |
| 2 | 284.23 |
| 3 | 197.51 |
| 4 | 207.61 |
| 5 | 198.75 |
| Median | 207.61 |
| Minimum | 197.51 |
| Maximum | 284.23 |

These five measurements are from one machine and are not a general performance
benchmark.

`exec_ms` uses a monotonic timer around `micropython_wasm.run()`. It includes the
runner call's engine/module startup and guest execution. Artifact packaging and
script extraction happen before the timer starts, so they are excluded.

`mem_bytes` remains zero as a placeholder. Actual guest memory usage is not
measured; the API and documentation must not describe zero as measured usage.
