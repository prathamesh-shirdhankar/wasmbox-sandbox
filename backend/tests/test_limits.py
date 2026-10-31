"""Resource-limit and elapsed-time tests for the MicroPython WASM runner.

Infinite-loop tests must always pass an explicit wall-clock limit and a high
fuel allowance. Never run an infinite loop directly with host CPython.

Memory exhaustion trap detection is tested using diagnostic strings rather
than executing the memory-bomb plugin in the host pytest process. The actual
memory-bomb integration test must remain isolated inside Docker.
"""

from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import (
    _memory_limit_failure,
    run_plugin,
)


# High fuel ensures the wall-clock deadline can stop infinite loops first.
INFINITE_LOOP_FUEL = 10_000_000_000


def test_short_wall_timeout_is_reported_as_timeout():
    result = run_plugin(
        temp_package("while True: pass"),
        fuel=INFINITE_LOOP_FUEL,
        wall_timeout_seconds=0.05,
    )

    assert result.status == "timeout"
    assert "timed out" in result.stderr.lower()
    assert result.exec_ms > 0


def test_normal_run_reports_real_elapsed_time():
    result = run_plugin(temp_package('print("hi")'))

    assert result.status == "ok"
    assert result.stdout == "hi\n"
    assert result.exec_ms > 0


def test_fuel_exhaustion_is_reported_as_timeout():
    result = run_plugin(
        temp_package('print("hi")'),
        fuel=1_000,
        wall_timeout_seconds=1.0,
    )

    assert result.status == "timeout"
    assert "instruction fuel" in result.stderr.lower()
    assert result.exec_ms > 0


def test_infinite_loop_stops_with_wall_timeout_enabled():
    result = run_plugin(
        temp_package("while True: pass"),
        fuel=INFINITE_LOOP_FUEL,
        wall_timeout_seconds=0.25,
    )

    assert result.status == "timeout"
    assert result.stderr != ""
    assert result.exec_ms > 0


def test_twenty_timeouts_then_normal_run_still_works():
    # Each execution must run long enough to reach its wall-clock deadline.
    infinite_loop = temp_package("while True: pass")

    for _ in range(20):
        result = run_plugin(
            infinite_loop,
            fuel=INFINITE_LOOP_FUEL,
            wall_timeout_seconds=0.05,
        )

        assert result.status == "timeout"
        assert result.exec_ms > 0

    # Verify that the runtime still works after repeated interruptions.
    recovered = run_plugin(temp_package('print("recovered")'))

    assert recovered.status == "ok"
    assert recovered.stdout == "recovered\n"
    assert recovered.exec_ms > 0


def test_memory_out_of_bounds_trap_is_recognized():
    diagnostic = (
        "exception_type=Trap | "
        "message=wasm trap: out of bounds memory access | "
        "trap_code=<TrapCode.MEMORY_OUT_OF_BOUNDS: 1>"
    )

    assert _memory_limit_failure(diagnostic) is True


def test_memory_fault_diagnostic_is_recognized():
    diagnostic = (
        "memory fault at wasm address 0x61207972 "
        "in linear memory of size 0x230000 | "
        "wasm trap: out of bounds memory access"
    )

    assert _memory_limit_failure(diagnostic) is True


def test_fuel_exhaustion_is_not_classified_as_memory_failure():
    diagnostic = (
        "exception_type=Trap | "
        "trap_code=<TrapCode.OUT_OF_FUEL: 9> | "
        "all fuel consumed by WebAssembly"
    )

    assert _memory_limit_failure(diagnostic) is False