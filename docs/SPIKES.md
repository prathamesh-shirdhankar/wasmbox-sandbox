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

(to be filled in)