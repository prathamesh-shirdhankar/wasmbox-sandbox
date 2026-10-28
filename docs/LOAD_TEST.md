# WasmBox High-Concurrency Load Test Report

This report documents the performance, throughput, and latency characteristics of the WasmBox execution endpoint (`POST /run`) under high-concurrency workloads.

---

## 1. Test Environment & Hardware Specifications

All benchmark runs were executed on the developer workstation using the automated test suite in [`backend/scripts/load_test.py`](file:///d:/intership%20project/New%20folder/wasmbox-sandbox/backend/scripts/load_test.py).

| Specification | Value |
| :--- | :--- |
| **Processor (CPU)** | 13th Gen Intel(R) Core(TM) i5-1335U (10 Cores: 2 Performance + 8 Efficient, 12 Logical Threads) |
| **Installed RAM** | 16.0 GB (15.69 GB visible) |
| **Operating System** | Microsoft Windows 11 Home Single Language (64-bit, Build 10.0.26300) |
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
- **Solution Applied**: Serializing WASM runtime invocation with a dedicated thread lock (`_RUNNER_LOCK`) in `micropython_runner.py` completely eliminated race conditions and guaranteed 100% test reliability.

---

## 4. Scaling Recommendations for Production

1. **Multi-Process Architecture (Uvicorn Workers)**:
   - WebAssembly execution is CPU-bound. Deploying Uvicorn with multiple worker processes (`uvicorn app.main:app --workers 4` or `--workers 8`) allows each worker process to maintain its own independent WebAssembly engine, scaling throughput linearly with physical CPU core count:
     $$\text{Estimated Throughput} \approx 8\text{ req/s} \times 8\text{ Cores} \approx 64\text{ req/s}$$
2. **Horizontal Autoscaling (Kubernetes Pods)**:
   - In containerized deployments (Docker), horizontal pod autoscalers (HPA) targeting CPU utilization (~70%) distribute bursts across multiple isolated container instances.
3. **Wizer Pre-Initialization / Ahead-of-Time Snapshots**:
   - As documented in [`docs/SPIKES.md`](file:///d:/intership%20project/New%20folder/wasmbox-sandbox/docs/SPIKES.md), pre-initializing the MicroPython heap with Wizer can cut cold-start time down from ~125 ms to under ~15 ms, which would increase per-core throughput by up to 8x.

---

## 5. How to Reproduce

Run the automated load test script directly from repository root:

```bash
# In-process benchmark:
python backend/scripts/load_test.py

# Against a live server on port 8000:
python backend/scripts/load_test.py --url http://127.0.0.1:8000
```
