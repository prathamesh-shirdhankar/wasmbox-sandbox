# Spikes

Short, time-boxed investigations. Write what you tried, the exact commands and output, and a recommendation.

## Prathamesh: host functions

(to be filled in)

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

#### 3. Recommendation for Week 2

1. **Primary Runtime**: **MicroPython WASI** is the clear winner for our lightweight sandbox:
   - Ultra-small binary footprint (362 KB vs >25 MB)
   - Zero disk dependencies
   - Clean security posture (no host directory mounts)
2. **Next Step (Day 4)**: Investigate **Wizer** pre-initialization on the chosen candidate to evaluate if snapshotting can reduce the ~220ms execution latency down to sub-50ms.