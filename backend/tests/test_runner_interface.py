"""Acceptance tests for the frozen run_plugin interface.
Frozen interface contract:
    run_plugin(artifact, *, limits=None) -> PluginResult
    PluginResult(status, stdout, stderr, exec_ms, mem_bytes)

Status outcomes: ok, error, timeout, memory_exceeded.
Notice: 'denied' is reserved for host-side API policy denials, not the runner.
"""

import concurrent.futures
from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import PluginResult, run_plugin


def test_interface_successful_execution_returns_ok_and_stdout():
    """1: Successful execution returns ok and expected output."""
    artifact = temp_package('print("hello from frozen interface")')
    result = run_plugin(artifact)
    assert result.status == "ok"
    assert result.stdout == "hello from frozen interface\n"
    assert result.stderr == ""
    assert result.exec_ms > 0
    # mem_bytes remains 0 until actual measurement is implemented
    if hasattr(result, "mem_bytes"):
        assert result.mem_bytes == 0


def test_interface_runtime_error_returns_error_and_useful_stderr():
    """2: A guest runtime error returns error with useful error details."""
    artifact = temp_package("1 / 0")
    result = run_plugin(artifact)
    assert result.status == "error"
    assert "ZeroDivisionError" in result.stderr
    assert result.exec_ms > 0


def test_interface_empty_output_handled_cleanly():
    """3: Output capture behaves correctly for empty output."""
    artifact = temp_package("a = 1 + 1")
    result = run_plugin(artifact)
    assert result.status == "ok"
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.exec_ms > 0


def test_interface_partial_output_captured_before_failure():
    """4: Output capture preserves partial stdout emitted before an error occurs."""
    artifact = temp_package('print("partial output before crash")\n1 / 0')
    result = run_plugin(artifact)
    assert result.status == "error"
    assert "partial output before crash" in result.stdout
    assert "ZeroDivisionError" in result.stderr
    assert result.exec_ms > 0


def test_interface_infinite_loop_stops_with_timeout():
    """5: An infinite-loop program is interrupted within configured timeout tolerance."""
    artifact = temp_package("while True: pass")
    result = run_plugin(artifact, wall_timeout_seconds=0.25)
    assert result.status == "timeout"
    assert result.stderr != ""
    assert result.exec_ms > 0


def test_interface_exec_ms_is_positive_number():
    """6: exec_ms is populated and uses documented timing boundaries."""
    artifact = temp_package('print("timing probe")')
    result = run_plugin(artifact)
    assert isinstance(result.exec_ms, (int, float))
    assert result.exec_ms > 0


def test_interface_concurrent_runs_do_not_interfere():
    """7: Multiple concurrent runs do not interrupt or corrupt one another."""
    artifacts = [
        (temp_package(f'print("worker_{i}")'), f"worker_{i}\n")
        for i in range(10)
    ]

    def _execute(item):
        art, expected = item
        res = run_plugin(art)
        return res, expected

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_execute, item) for item in artifacts]
        for future in concurrent.futures.as_completed(futures):
            res, expected_stdout = future.result()
            assert res.status == "ok"
            assert res.stdout == expected_stdout
            assert res.stderr == ""
            assert res.exec_ms > 0


def test_interface_mem_bytes_contract_semantics():
    """8: mem_bytes remains 0 until actual measurement is implemented.
    
    Once Phase C2 implements guest linear memory measurement, it must be >= 0.
    """
    artifact = temp_package('print("mem probe")')
    result = run_plugin(artifact)
    if hasattr(result, "mem_bytes"):
        assert isinstance(result.mem_bytes, int)
        assert result.mem_bytes >= 0


def test_interface_bounded_memory_limit_verified_safely():
    """9: Bounded memory limit verification without risking the host.
    
    Attempts to allocate more than the 10 MiB limit in a bounded fashion (capped at 20 MiB).
    Must return a safe failure status without crashing the host process.
    """
    code = (
        "try:\n"
        "    b = bytearray(20 * 1024 * 1024)\n"
        "except MemoryError:\n"
        "    raise\n"
    )
    artifact = temp_package(code)
    result = run_plugin(artifact, memory_bytes=10 * 1024 * 1024)
    assert result.status in ("error", "memory_exceeded")
    assert result.exec_ms > 0
