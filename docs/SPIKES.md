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

(to be filled in)