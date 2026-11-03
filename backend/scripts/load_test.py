"""WasmBox HTTP and in-process concurrency benchmark."""

from __future__ import annotations

import argparse
import concurrent.futures
import math
import os
import platform
import sys
import time
from typing import Any

import httpx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app
from fastapi.testclient import TestClient


def percentile(values: list[float], fraction: float) -> float:
    """Calculate percentile using the nearest-rank method."""
    if not values:
        return 0.0

    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def run_single_request(client: Any, url: str, payload: dict) -> dict:
    started = time.perf_counter()

    try:
        response = client.post(url, json=payload, timeout=30.0)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        try:
            body = response.json()
        except Exception:
            body = response.text[:1000]

        is_success = (
            response.status_code == 200
            and isinstance(body, dict)
            and body.get("status") == "ok"
            and body.get("stdout") == "42\n"
            and body.get("stderr") == ""
        )

        exec_ms = None
        runner_status = None

        if isinstance(body, dict):
            runner_status = body.get("status")
            value = body.get("exec_ms")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                exec_ms = float(value)

        error = None
        if not is_success:
            error = f"HTTP {response.status_code}; response={body!r}"

        return {
            "success": is_success,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "exec_ms": exec_ms,
            "runner_status": runner_status,
            "error": error,
        }

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "success": False,
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "exec_ms": None,
            "runner_status": None,
            "error": repr(exc),
        }


def run_batch(
    concurrency: int,
    base_url: str,
    payload: dict,
    use_in_process: bool,
) -> dict:
    print(f"\n--- Running batch: {concurrency} concurrent requests ---")

    endpoint = "/run" if use_in_process else f"{base_url.rstrip('/')}/run"
    results: list[dict] = []

    overall_start = time.perf_counter()

    def worker(request_number: int) -> dict:
        if use_in_process:
            with TestClient(app) as client:
                result = run_single_request(client, endpoint, payload)
        else:
            with httpx.Client(timeout=30.0) as client:
                result = run_single_request(client, endpoint, payload)

        result["request"] = request_number
        return result

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:
        futures = [
            executor.submit(worker, number)
            for number in range(1, concurrency + 1)
        ]

        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    total_time = time.perf_counter() - overall_start

    successes = sum(1 for result in results if result["success"])
    failures = concurrency - successes
    throughput = concurrency / total_time if total_time > 0 else 0.0

    latencies = [result["elapsed_ms"] for result in results]
    execution_times = [
        result["exec_ms"]
        for result in results
        if result["exec_ms"] is not None
    ]

    print(f"Completed {concurrency} requests in {total_time:.3f}s")
    print(f"Success: {successes}/{concurrency} | Failures: {failures}")
    print(f"Throughput: {throughput:.2f} requests/second")

    print(
        "HTTP latency: "
        f"min={min(latencies):.2f}ms, "
        f"avg={sum(latencies) / len(latencies):.2f}ms, "
        f"p50={percentile(latencies, 0.50):.2f}ms, "
        f"p95={percentile(latencies, 0.95):.2f}ms, "
        f"max={max(latencies):.2f}ms"
    )

    if execution_times:
        print(
            "Runner exec_ms: "
            f"avg={sum(execution_times) / len(execution_times):.2f}ms, "
            f"p50={percentile(execution_times, 0.50):.2f}ms, "
            f"p95={percentile(execution_times, 0.95):.2f}ms"
        )

    failed_results = [
        result for result in results if not result["success"]
    ]

    for result in sorted(failed_results, key=lambda item: item["request"]):
        print(
            f"FAILURE request={result['request']} "
            f"http={result['status_code']} "
            f"runner_status={result['runner_status']} "
            f"error={result['error']}"
        )

    return {
        "concurrency": concurrency,
        "total_time_sec": total_time,
        "successes": successes,
        "failures": failures,
        "throughput": throughput,
        "avg_latency_ms": sum(latencies) / len(latencies),
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "max_latency_ms": max(latencies),
        "failures_found": failures > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WasmBox concurrent load benchmark"
    )

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Base URL of the live WasmBox server",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Use FastAPI TestClient instead of live HTTP",
    )
    parser.add_argument(
        "--batches",
        nargs="+",
        type=int,
        default=[20, 50, 100],
        help="Concurrency levels to benchmark",
    )

    args = parser.parse_args()

    if any(value <= 0 for value in args.batches):
        parser.error("All concurrency batch sizes must be positive.")

    use_in_process = args.in_process

    if not use_in_process:
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{args.url.rstrip('/')}/health")

            if response.status_code != 200:
                print(
                    f"ERROR: Live server health check returned "
                    f"HTTP {response.status_code}."
                )
                return 2

        except Exception as exc:
            print(f"ERROR: Cannot reach live backend: {exc!r}")
            print("No automatic in-process fallback will be performed.")
            return 2

    payload = {"code": "print(42)"}

    print("=" * 72)
    print(f"WasmBox load benchmark | Batches: {args.batches}")
    print(f"Mode: {'In-process TestClient' if use_in_process else 'Live HTTP'}")
    if not use_in_process:
        print(f"URL: {args.url}")
    print(
        f"System: {platform.system()} ({platform.machine()}) | "
        f"Python {platform.python_version()}"
    )
    print("Payload: print(42)")
    print("Latency percentiles: nearest-rank method")
    print("=" * 72)

    metrics = []

    for count in args.batches:
        metrics.append(
            run_batch(
                count,
                args.url,
                payload,
                use_in_process,
            )
        )

    print("\n" + "=" * 100)
    print("BENCHMARK SUMMARY")
    print("=" * 100)
    print(
        f"{'Batch':<8} {'Success':<12} {'Failures':<10} "
        f"{'RPS':<10} {'Avg ms':<10} {'p50 ms':<10} "
        f"{'p95 ms':<10} {'Max ms':<10}"
    )

    for item in metrics:
        print(
            f"{item['concurrency']:<8} "
            f"{item['successes']}/{item['concurrency']:<10} "
            f"{item['failures']:<10} "
            f"{item['throughput']:<10.2f} "
            f"{item['avg_latency_ms']:<10.2f} "
            f"{item['p50_latency_ms']:<10.2f} "
            f"{item['p95_latency_ms']:<10.2f} "
            f"{item['max_latency_ms']:<10.2f}"
        )

    print("=" * 100)

    total_failures = sum(item["failures"] for item in metrics)

    if total_failures:
        print(f"BENCHMARK FAILED: {total_failures} request(s) failed.")
        return 1

    print("BENCHMARK PASSED: Every request succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
