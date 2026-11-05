# WasmBox High-Concurrency Load Test Report

This report documents the performance, throughput, and latency characteristics of the WasmBox execution endpoint (`POST /run`) under concurrent workloads.

> **Historical baseline notice:** Sections 1 through 4 contain October 2026 measurements and architecture observations from earlier runner revisions. They are retained for historical comparison, not as current performance claims. The November 3 and November 5, 2026 benchmarks are documented separately below. The November 5 benchmark was conducted against the final integrated revision.

---

## 1. Test Environment & Hardware Specifications

The historical benchmark runs were executed on the developer workstation using the automated test script in [`backend/scripts/load_test.py`].

| Specification | Historical value |
| :--- | :--- |
| **Processor (CPU)** | 13th Gen Intel(R) Core(TM) i5 |
| **Installed RAM** | 16.0 GB |
| **Operating System** | Microsoft Windows 11 |
| **Python Version** | 3.11.9 |
| **WebAssembly Engine** | `wasmtime==49.0.0` |
| **Interpreter Binary** | MicroPython WASI (`micropython-wasi.wasm`, 362 KB) |
| **Payload Tested** | `{"code": "print(42)"}` |

These specifications describe the historical benchmark environment and should not be assumed to describe every subsequent run.

---

## 2. Historical Benchmark Results — October 2026

Concurrency batches of 20, 50, and 100 requests were dispatched concurrently using `concurrent.futures.ThreadPoolExecutor` and `httpx` / FastAPI test transport.

Every response was verified for the expected execution result:

- `status: "ok"`
- `stdout: "42\n"`
- `stderr: ""`

| Concurrency Batch | Total Time (s) | Successful Requests | Failed Requests | Throughput (req/s) | Min Latency (ms) | Avg Latency (ms) | Max Latency (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **20 requests** | 2.530 s | 20 / 20 (100%) | 0 (0%) | **7.90 req/s** | 207.3 ms | 1,360.3 ms | 2,470.7 ms |
| **50 requests** | 6.258 s | 50 / 50 (100%) | 0 (0%) | **7.99 req/s** | 185.0 ms | 3,092.7 ms | 6,045.0 ms |
| **100 requests** | 12.840 s | 100 / 100 (100%) | 0 (0%) | **7.79 req/s** | 235.4 ms | 6,340.4 ms | 12,272.6 ms |

These measurements represent the earlier runner architecture and are retained as a historical baseline.

---

## 3. Historical Architectural Analysis & Findings

### 3.1 Consistent Single-Worker Throughput (~8 req/s)

Across the historical batch sizes of 20, 50, and 100 requests, system throughput remained relatively steady at approximately 7.8–8.0 requests per second.

- Each MicroPython WASI execution was estimated to require approximately 125–130 ms of processing time in the earlier implementation.
- The observed throughput suggested that a single execution worker processing requests sequentially reached saturation at approximately 8 requests per second.

These observations describe the earlier runner revision, not the current benchmark results.

### 3.2 Latency Distribution Under Queueing

- **Fastest request:** Minimum latency ranged from approximately 185–235 ms.
- **Queueing delay:** Because requests were submitted concurrently, later requests experienced additional waiting time.
  - Batch of 20: Maximum latency was 2.47 seconds.
  - Batch of 50: Maximum latency was 6.05 seconds.
  - Batch of 100: Maximum latency was 12.27 seconds.
- **Failures:** All requests in the historical batches completed successfully.

### 3.3 Thread Safety in WebAssembly Runtimes

During concurrent multithreading tests within a single Python process, the `wasmtime-py` global `Slab` allocator (`wasmtime._slab.FUNCTIONS`) experienced race conditions when multiple OS threads attempted simultaneous host-function allocations.

**Historical correction:**

A dedicated thread lock appeared to resolve the initial race in earlier testing. Subsequent November 3 live HTTP testing reproduced an intermittent Wasmtime `FUNCTIONS` slab allocator error during internal host-call registration.

A later correction added a process-wide `_RUNNER_LOCK` around the complete `_run_once()` lifecycle.

The November 3 benchmark section documents the post-fix verification results.

The process-wide lock serializes Wasmtime execution within each worker process. Multiple Uvicorn worker processes maintain independent runtime state.

---

## 4. Scaling Recommendations for Production

The following are architectural recommendations, not verified production-capacity results.

### 4.1 Multi-Process Architecture (Uvicorn Workers)

WebAssembly execution is CPU-intensive. Multiple Uvicorn worker processes can maintain independent WebAssembly runtime state.

Example:

```bash
uvicorn app.main:app --workers 4
```

The earlier architecture used an estimated throughput of approximately 8 requests per second as a reference point.

Any linear scaling estimate based on worker count or CPU cores must be validated with actual measurements.

### 4.2 Horizontal Autoscaling (Kubernetes Pods)

In containerized deployments, horizontal pod autoscaling can distribute incoming requests across multiple isolated application instances.

CPU utilization targets, resource limits, workload characteristics, and actual throughput should be measured before establishing production scaling configurations.

### 4.3 Wizer Pre-Initialization / Ahead-of-Time Snapshots

The earlier `docs/SPIKES.md` discussion proposed Wizer pre-initialization as a possible way to reduce startup time.

The projected reduction to under 15 ms and possible 8x throughput improvement were not measured in the benchmark results documented here.

They remain unverified hypotheses, not WasmBox performance claims.

---

## 5. How to Reproduce

Run the automated load-test script directly from the repository root.

### 5.1 Live HTTP benchmark

Start the backend server first.

Then run:

```powershell
python backend/scripts/load_test.py `
  --url http://127.0.0.1:8000 `
  --batches 1 5 10 20
```

The script sends requests to the live backend using HTTP.

### 5.2 In-process benchmark

To use FastAPI `TestClient` instead of a live HTTP server:

```powershell
python backend/scripts/load_test.py --in-process --batches 1 5 10 20
```

### 5.3 Default configuration

The script defaults to:

- Live HTTP mode.
- Base URL: `http://127.0.0.1:8000`.
- Concurrency batches: 20, 50, and 100.
- Payload: `{"code": "print(42)"}`.

### 5.4 Recorded metrics

The benchmark records:

- Successful and failed requests.
- Total batch execution time.
- Throughput in requests per second.
- Minimum HTTP latency.
- Average HTTP latency.
- p50 HTTP latency.
- p95 HTTP latency.
- Maximum HTTP latency.
- Runner execution time (`exec_ms`).

Latency percentiles use the nearest-rank method.

For reproducible comparisons, record the Git commit, Python version, operating system, Wasmtime version, execution mode, and concurrency settings.

---

# November 3, 2026 — Updated Benchmark Results

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
- Ten subsequent calls: median 0.9 ms, range 0.8–1.1 ms.
- Separate Engine and Module construction samples: 96.7, 91.7, and 109.3 ms.

## Concurrency correction

An intermittent Wasmtime Python `FUNCTIONS` slab allocator error was reproduced during concurrent host-call registration.

A process-wide `_RUNNER_LOCK` was added around `_run_once()`.

After the change:

- Windows suite: 103 passed, 1 skipped.
- Linux suite: 103 passed, 1 skipped.
- Single-worker benchmark: 170/170 successful.
- Two-worker measured batches (20/50/100): 170/170 successful in each run.
- Run 2 also passed two 8-request warm-up batches (16/16 additional).
- Three additional 16-request batches: 48/48 successful.

The process-wide lock serializes Wasmtime execution within each worker process. Multiple Uvicorn processes have independent runtime state.

## Interpretation and limitations

At 100 concurrent requests, two workers reduced HTTP p95 from 594.75 ms to approximately 204 ms, but throughput remained around 99 requests per second under the two-CPU limit.

These are measurements from one capped Docker environment, not general production-capacity claims.

The two-worker first-use warm-up batches were substantially slower and are excluded from steady-state comparisons.

`exec_ms` excludes waiting for `_RUNNER_LOCK`, shared Engine/Module initialization, and per-run Store/Linker/WASI setup.

`mem_bytes` reports current guest linear memory, not peak guest allocation or total host-process memory.

---

# November 5, 2026 — Final Integrated Main Benchmark

**Revision:** `2e1c11c`

**Environment:**

- Operating system: Windows (AMD64).
- Python: 3.12.10.
- Execution mode: Live HTTP.
- Backend URL: `http://127.0.0.1:8000`.
- Endpoint: `POST /run`.
- Payload: `{"code": "print(42)"}`.
- Wasmtime version: Not separately captured for this Windows benchmark.

This benchmark was conducted against the final integrated `main` revision, which includes the merged contributions from Prathamesh, Vineet, and Sashmita.

## 1. Benchmark configuration

Four concurrency levels were tested:

- 1 concurrent request.
- 5 concurrent requests.
- 10 concurrent requests.
- 20 concurrent requests.

**Total requests:** 36.

Every request was checked for:

- HTTP status code 200.
- Runner status `ok`.
- Expected stdout `42\n`.
- Empty stderr.

## 2. Benchmark results

| Concurrency | Total Time (s) | Successful Requests | Failed Requests | Throughput (req/s) |
|---:|---:|---:|---:|---:|
| 1 | 0.411 | 1/1 | 0 | 2.43 |
| 5 | 0.474 | 5/5 | 0 | 10.55 |
| 10 | 0.618 | 10/10 | 0 | 16.18 |
| 20 | 1.188 | 20/20 | 0 | 16.83 |

**Result:** All 36 requests succeeded, with zero failures.

## 3. HTTP latency results

| Concurrency | Minimum (ms) | Average (ms) | p50 (ms) | p95 (ms) | Maximum (ms) |
|---:|---:|---:|---:|---:|---:|
| 1 | 192.89 | 192.89 | 192.89 | 192.89 | 192.89 |
| 5 | 3.85 | 7.54 | 4.94 | 18.31 | 18.31 |
| 10 | 6.02 | 12.36 | 11.22 | 22.45 | 22.45 |
| 20 | 3.72 | 15.14 | 9.86 | 30.85 | 32.25 |

The first request recorded 192.89 ms HTTP latency. This measurement is retained rather than excluded from the results.

Subsequent batches recorded lower HTTP latencies. The available measurements do not independently establish the exact cause of the first-request difference.

## 4. Runner execution time

| Concurrency | Average exec_ms | p50 exec_ms | p95 exec_ms |
|---:|---:|---:|---:|
| 1 | 1.42 ms | 1.42 ms | 1.42 ms |
| 5 | 0.52 ms | 0.51 ms | 0.62 ms |
| 10 | 0.61 ms | 0.64 ms | 0.77 ms |
| 20 | 0.63 ms | 0.61 ms | 0.68 ms |

Runner execution time and HTTP latency measure different parts of the request lifecycle.

HTTP latency includes additional request-handling overhead, while `exec_ms` represents the runner's documented execution timing.

## 5. Backend recovery after load testing

After the benchmark completed, the backend health endpoint was checked again.

Command:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Observed response:

```json
{
  "ok": true
}
```

The backend remained operational after all 36 benchmark requests.

## 6. Result

**BENCHMARK PASSED**

| Acceptance check | Result |
|---|---|
| Total requests | 36 |
| Successful requests | 36 |
| Failed requests | 0 |
| Highest tested concurrency | 20 |
| Highest measured throughput | 16.83 req/s |
| p95 HTTP latency at concurrency 20 | 30.85 ms |
| Maximum HTTP latency at concurrency 20 | 32.25 ms |
| Post-benchmark health check | Passed |

## 7. Interpretation and limitations

The benchmark demonstrates successful short-duration concurrent execution through the live WasmBox HTTP API at the tested concurrency levels.

At concurrency 20:

- Throughput reached 16.83 requests per second.
- Average HTTP latency was 15.14 ms.
- p95 HTTP latency was 30.85 ms.
- Maximum HTTP latency was 32.25 ms.
- All 20 requests succeeded.

The first request recorded a higher latency of 192.89 ms and is retained as part of the benchmark evidence.

These measurements apply to the tested Windows development environment and the simple `print(42)` workload.

This test involved only 36 requests. It is not a sustained-load, soak, or production-capacity benchmark.

The 50 ms performance target should not be considered universally achieved based on this benchmark. HTTP p95 latency, first-request latency, and runner `exec_ms` measure different aspects of execution.

**Final assessment:** The final integrated revision passed the tested HTTP concurrency benchmark without request failures or backend health degradation.

---

## Overall Benchmark Conclusion

The historical October, November 3, and November 5 measurements represent different runner revisions, environments, execution modes, and concurrency configurations.

They should not be directly compared without accounting for those differences.

The November 5 benchmark provides the latest recorded live HTTP performance evidence for final integrated revision `2e1c11c`.

The current evidence demonstrates:

- Successful execution of all 36 benchmark requests.
- Successful operation at concurrency levels of 1, 5, 10, and 20.
- No observed request failures.
- Successful backend health verification after the benchmark.

Further sustained-load and production-environment testing would be required before making broader performance or capacity guarantees.