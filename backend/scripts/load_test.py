"""
High-concurrency load testing script for WasmBox /run endpoint.

Uses concurrent.futures.ThreadPoolExecutor and httpx (or FastAPI TestClient)
to benchmark execution throughput and latency under concurrency batches of 20, 50, and 100.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import platform
import sys
import time
from typing import Any, Dict, List

import httpx

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app  
from fastapi.testclient import TestClient  


def run_single_request(client: Any, url: str, payload: dict) -> dict:
    start_time = time.perf_counter()
    try:
        response = client.post(url, json=payload, timeout=30.0)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if response.status_code == 200:
            data = response.json()
            is_success = (
                data.get("status") == "ok" and data.get("stdout") == "42\n"
            )
            return {
                "success": is_success,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "error": None if is_success else f"unexpected payload: {data}",
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "error": f"HTTP {response.status_code}",
            }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "success": False,
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "error": str(exc),
        }


def run_batch(
    concurrency: int,
    base_url: str | None,
    payload: dict,
    use_in_process: bool,
) -> dict:
    print(f"\n--- Running batch: {concurrency} concurrent requests ---")
    client_url = "/run" if use_in_process else f"{base_url.rstrip('/')}/run"

    overall_start = time.perf_counter()
    results: List[dict] = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:
        def worker() -> dict:
            if use_in_process:
                # TestClient is thread-safe and wraps ASGI synchronously
                with TestClient(app) as client:
                    return run_single_request(client, client_url, payload)
            else:
                with httpx.Client() as client:
                    return run_single_request(client, client_url, payload)

        futures = [executor.submit(worker) for _ in range(concurrency)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    total_time_sec = time.perf_counter() - overall_start
    successes = sum(1 for r in results if r["success"])
    failures = concurrency - successes
    rps = concurrency / total_time_sec if total_time_sec > 0 else 0
    latencies = [r["elapsed_ms"] for r in results]
    min_latency = min(latencies) if latencies else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0

    print(f"Completed {concurrency} requests in {total_time_sec:.3f}s")
    print(
        f"Success: {successes}/{concurrency} | Failures: {failures} | Throughput: {rps:.2f} req/s"
    )
    print(
        f"Latency: min={min_latency:.1f}ms, avg={avg_latency:.1f}ms, max={max_latency:.1f}ms (slowest)"
    )

    return {
        "concurrency": concurrency,
        "total_time_sec": total_time_sec,
        "successes": successes,
        "failures": failures,
        "rps": rps,
        "min_latency_ms": min_latency,
        "avg_latency_ms": avg_latency,
        "max_latency_ms": max_latency,
    }


def main():
    parser = argparse.ArgumentParser(
        description="WasmBox Concurrent Load Testing Script"
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Base URL of live server (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Force in-process TestClient execution instead of HTTP network calls",
    )
    parser.add_argument(
        "--batches",
        nargs="+",
        type=int,
        default=[20, 50, 100],
        help="Concurrency batches to run (default: 20 50 100)",
    )
    args = parser.parse_args()

    # Determine whether live server is running
    use_in_process = args.in_process
    if not use_in_process:
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{args.url.rstrip('/')}/health")
                if res.status_code == 200:
                    print(
                        f"Connected to live WasmBox backend at {args.url} (Health: OK)"
                    )
                else:
                    print(
                        f"Live server returned status {res.status_code}. Falling back to in-process execution."
                    )
                    use_in_process = True
        except Exception:
            print(
                f"No running server found at {args.url}. Using high-efficiency in-process TestClient."
            )
            use_in_process = True

    payload = {"code": "print(42)"}
    print("=" * 72)
    print(
        f"WasmBox Load Benchmark | Payload: {payload['code']} | Batches: {args.batches}"
    )
    print(
        f"Mode: {'In-process TestClient execution' if use_in_process else f'Network HTTP -> {args.url}'}"
    )
    print(f"System: {platform.system()} ({platform.machine()}) | Python {platform.python_version()}")
    print("=" * 72)

    batch_metrics = []
    for count in args.batches:
        metric = run_batch(count, args.url, payload, use_in_process)
        batch_metrics.append(metric)

    print("\n" + "=" * 72)
    print("BENCHMARK SUMMARY RESULTS TABLE")
    print("=" * 72)
    print(
        f"{'Batch':<8} | {'Total Time (s)':<14} | {'Success':<9} | {'RPS':<10} | {'Avg Lat (ms)':<12} | {'Max Lat (ms)':<12}"
    )
    print("-" * 75)
    for m in batch_metrics:
        print(
            f"{m['concurrency']:<8} | {m['total_time_sec']:<14.3f} | {m['successes']}/{m['concurrency']:<6} | {m['rps']:<10.2f} | {m['avg_latency_ms']:<12.1f} | {m['max_latency_ms']:<12.1f}"
        )
    print("=" * 72)


if __name__ == "__main__":
    main()
