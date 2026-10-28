"""Resource-limit and elapsed-time tests for the MicroPython WASM runner.

The infinite-loop test must always pass an explicit wall-clock limit. Do not
remove that limit or run the loop directly with host CPython.
"""

from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import run_plugin


def test_short_wall_timeout_is_reported_as_timeout():
    result = run_plugin(
        temp_package('print("hi")'),
        wall_timeout_seconds=0.05,
    )
    assert result.status == "timeout"
    assert "wall-clock limit exceeded" in result.stderr
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
    assert "instruction fuel exhausted" in result.stderr
    assert result.exec_ms > 0


def test_infinite_loop_stops_with_wall_timeout_enabled():
    result = run_plugin(
        temp_package("while True: pass"),
        fuel=1_000_000_000,
        wall_timeout_seconds=0.25,
    )
    assert result.status == "timeout"
    assert "wall-clock limit exceeded" in result.stderr
    assert result.exec_ms > 0


def test_twenty_timeouts_then_normal_run_still_works():
    artifact = temp_package('print("timeout probe")')
    for _ in range(20):
        result = run_plugin(artifact, wall_timeout_seconds=0.05)
        assert result.status == "timeout"
        assert result.exec_ms > 0

    recovered = run_plugin(temp_package('print("recovered")'))
    assert recovered.status == "ok"
    assert recovered.stdout == "recovered\n"
    assert recovered.exec_ms > 0
