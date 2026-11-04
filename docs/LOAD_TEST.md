# WasmBox High-Concurrency Load Test Report

This report documents the performance, throughput, and latency characteristics of the WasmBox execution endpoint (`POST /run`) under high-concurrency workloads.

> **Historical baseline notice:** Sections 1 through 4 below contain October 2026 measurements and architecture observations from an earlier runner revision. They are retained for historical comparison, not as current performance claims. The November 3, 2026 results are recorded in the updated benchmark section below.

---

## 1. Test Environment & Hardware Specifications

All benchmark runs were executed on the developer workstation using the automated test suite in [`backend/scripts/load_test.py`]

| Specification | Value |
| :--- | :--- |
| **Processor (CPU)** | 13th Gen Intel(R) Core(TM) i5|
| **Installed RAM** | 16.0 GB  |
| **Operating System** | Microsoft Windows 11  |
| **Python Version** | 3.11.9 |
| **WebAssembly Engine** | `wasmtime==49.0.0` |
| **Interpreter Binary** | MicroPython WASI (`micropython-wasi.wasm`, 362 KB) |
| **Payload Tested** | `{"code": "print(42)"}` |

---

## 2. Benchmark Results

Concurrency batches of 20, 50, and 100 requests were dispatched concurrently using `concurrent.futures.ThreadPoolExecutor` and `httpx` / FastAPI test transport. Every response was verified for standard 5-field contract adherence (`status: "ok"`, `stdout: "42\n"`, `stderr: ""`).

| Concurrency Batch | Total Time (s) | Successful Requests | Failed Requests | Throughput (req/s) | Min Latency (ms) | Avg Latency (ms) | Max Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **20 requests** | 2.530 s | 20 / 20 (100%) | 0 (0%) | **7.90 req/s** | 207.3 ms | 1,360.3 ms | 2,470.7 ms |
| **50 requests** | 6.258 s | 50 / 50 (100%) | 0 (0%) | **7.99 req/s** | 185.0 ms | 3,092.7 ms | 6,045.0 ms |
| **100 requests** | 12.840 s | 100 / 100 (100%) | 0 (0%) | **7.79 req/s** | 235.4 ms | 6,340.4 ms | 12,272.6 ms |

---

## 3. Architectural Analysis & Findings

### 3.1 Consistent Single-Worker Throughput (~8 req/s)
Across all three batch tiers (20, 50, 100), system throughput remained remarkably steady at **~7.8 – 8.0 requests per second**.
- Each MicroPython WASI execution requires approximately **125 – 130 ms of CPU time** (including WASM store allocation, custom section parsing, memory initialization, bytecode execution, and output extraction).
- Because 1 second / 0.128 seconds ≈ 7.81 requests, a single execution worker processing requests sequentially reaches saturation at ~8 req/s.

### 3.2 Latency Distribution Under Queueing
- **Fastest Request (Min Latency: ~185 – 235 ms)**: The first request executed with zero queue waiting time, completing in under a quarter of a second.
- **Queueing Delay (Max Latency)**: Because all requests were submitted simultaneously at $t = 0$, requests queued up deterministically:
  - Batch of 20: Max latency was 2.47 s ($\approx 20 \times 125\text{ ms}$).
  - Batch of 50: Max latency was 6.05 s ($\approx 50 \times 125\text{ ms}$).
  - Batch of 100: Max latency was 12.27 s ($\approx 100 \times 125\text{ ms}$).
- **Zero Failures**: 100% of requests in all batches succeeded cleanly without memory leakage or process crashes.

### 3.3 Thread Safety in WebAssembly Runtimes
During concurrent multi-threading tests within a single Python process, `wasmtime-py`'s global `Slab` allocator (`wasmtime._slab.FUNCTIONS`) experienced race conditions when multiple OS threads attempted simultaneous host function allocations.
- **Historical correction:** A dedicated thread lock appeared to resolve the race in the earlier test set. Subsequent November 3 live HTTP testing reproduced an intermittent Wasmtime `FUNCTIONS` slab allocator error during internal host-call registration. The later correction added a process-wide `_RUNNER_LOCK` around the complete `_run_once()` lifecycle. See the November 3 results below for the post-fix verification.

---

## 4. Scaling Recommendations for Production

1. **Multi-Process Architecture (Uvicorn Workers)**:
   - WebAssembly execution is CPU-bound. Deploying Uvicorn with multiple worker processes (`uvicorn app.main:app --workers 4` or `--workers 8`) allows each worker process to maintain its own independent WebAssembly engine, scaling throughput linearly with physical CPU core count:
     $$\text{Estimated Throughput} \approx 8\text{ req/s} \times 8\text{ Cores} \approx 64\text{ req/s}$$
2. **Horizontal Autoscaling (Kubernetes Pods)**:
   - In containerized deployments (Docker), horizontal pod autoscalers (HPA) targeting CPU utilization (~70%) distribute bursts across multiple isolated container instances.
3. **Wizer Pre-Initialization / Ahead-of-Time Snapshots**:
   - The earlier `docs/SPIKES.md` discussion proposed Wizer pre-initialization as a possible way to reduce startup time. The projected reduction to under 15 ms and possible 8x throughput improvement were not measured in the benchmark results here. They remain unverified hypotheses, not WasmBox performance claims.

---

## 5. How to Reproduce

Run the automated load test script directly from repository root:

```bash
# In-process benchmark:
python backend/scripts/load_test.py

# Against a live server on port 8000:
python backend/scripts/load_test.py --url http://127.0.0.1:8000
```

---

# November 3, 2026 � Updated Benchmark Results

**Revision:** `c0405d4`
**Environment:** Linux / Docker Desktop WSL2, Python 3.12.16, Wasmtime 49.0.0, 2 CPUs, 512 MiB RAM limit.
**Workload:** `print(42)` through live HTTP `POST /run`.

## Single-worker results

| Requests | Success | Throughput | HTTP p50 | HTTP p95 |
|---:|---:|---:|---:|---:|
| 20 | 20/20 | 130.73 req/s | 101.15 ms | 112.48 ms |
| 50 | 50/50 | 105.28 req/s | 140.82 ms | 279.62 ms |
| 100 | 100/100 | 99.42 req/s | 354.91 ms | 594.75 ms |

## Two-worker results

| Requests | Success | Run 1 throughput | Run 2 throughput | Run 1 p50 | Run 2 p50 | Run 1 p95 | Run 2 p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 20/20 in both runs | 100.08 | 205.70 | 23.19 ms | 17.62 ms | 95.43 ms | 55.44 ms |
| 50 | 50/50 in both runs | 87.66 | 88.31 | 95.41 ms | 100.32 ms | 204.84 ms | 207.95 ms |
| 100 | 100/100 in both runs | 98.39 | 99.61 | 102.05 ms | 100.06 ms | 203.64 ms | 208.02 ms |

Throughput values are requests per second.

## Runtime timing

- First `run_plugin()` call: 178.9 ms.
- Ten subsequent calls: median 0.9 ms, range 0.8�1.1 ms.
- Separate Engine and Module construction samples: 96.7, 91.7, and 109.3 ms.

## Concurrency correction

An intermittent Wasmtime Python `FUNCTIONS` slab allocator error was reproduced during concurrent host-call registration. A process-wide `_RUNNER_LOCK` was added around `_run_once()`.

After the change:
- Windows suite: 103 passed, 1 skipped.
- Linux suite: 103 passed, 1 skipped.
- Single-worker benchmark: 170/170 successful.
- Two-worker measured batches (20/50/100): 170/170 successful in each run. Run 2 also passed two 8-request warm-up batches (16/16 additional).
- Three additional 16-request batches: 48/48 successful.

The process-wide lock serializes Wasmtime execution within each worker process. Multiple Uvicorn processes have independent runtime state.

## Interpretation and limitations

At 100 concurrent requests, two workers reduced HTTP p95 from 594.75 ms to approximately 204 ms, but throughput remained around 99 requests per second under the two-CPU limit.

These are measurements from one capped Docker environment, not general production-capacity claims. The two-worker first-use warm-up batches were substantially slower and are excluded from steady-state comparisons.

`exec_ms` excludes waiting for `_RUNNER_LOCK`, shared Engine/Module initialization, and per-run Store/Linker/WASI setup. `mem_bytes` reports current guest linear memory, not peak or host memory.
