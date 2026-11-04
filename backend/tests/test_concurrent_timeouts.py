"""Verify concurrent submissions are safely serialized with independent deadlines."""

import concurrent.futures
import threading

from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import run_plugin


INFINITE_LOOP_FUEL = 10_000_000_000


def test_concurrent_timeout_requests_keep_individual_deadlines():
    """Queued executions must each receive their own timeout once started."""
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
        long_result = long_future.result(timeout=15)

    assert short_result.status == "timeout"
    assert long_result.status == "timeout"

    assert long_result.exec_ms > short_result.exec_ms + 300, (
        "The longer execution did not receive its own longer timeout."
    )
