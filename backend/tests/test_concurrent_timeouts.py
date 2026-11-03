"""Verify independent wall-clock deadlines for concurrent WASM executions."""

import concurrent.futures
import threading

from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import run_plugin


INFINITE_LOOP_FUEL = 10_000_000_000


def test_concurrent_timeout_deadlines_are_independent():
    """A short timeout must not interrupt a concurrent longer execution."""
    artifact = temp_package("while True: pass")
    start_barrier = threading.Barrier(2)

    def execute(timeout_seconds):
        start_barrier.wait(timeout=5)
        return run_plugin(
            artifact,
            fuel=INFINITE_LOOP_FUEL,
            wall_timeout_seconds=timeout_seconds,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        short_future = executor.submit(execute, 0.10)
        long_future = executor.submit(execute, 0.80)

        short_result = short_future.result(timeout=15)

        assert short_result.status == "timeout", (
            f"Short execution expected timeout, got {short_result.status}"
        )

        assert not long_future.done(), (
            "The longer execution ended when the shorter deadline expired."
        )

        long_result = long_future.result(timeout=15)

    assert long_result.status == "timeout", (
        f"Long execution expected timeout, got {long_result.status}"
    )

    assert long_result.exec_ms > short_result.exec_ms + 300, (
        "The longer execution did not run substantially longer than the shorter one."
    )
