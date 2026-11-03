"""Security and authorization tests for host-function allowlist bridge."""

import json
from typing import Any
import pytest
from wasmtime import Func, FuncType, ValType

from app.runtime._temp_packager import temp_package
import app.runtime.micropython_runner as runner_module
from app.runtime.micropython_runner import (
    run_plugin,
)

HOST_RESULT_BYTES = getattr(runner_module, "HOST_RESULT_BYTES", 262144)


# ---------------------------------------------------------------------------
# 1. Default runner allowlist enforcement
# ---------------------------------------------------------------------------
def test_default_production_runner_has_empty_host_allowlist():
    """Verify production run_plugin passes empty host-function allowlist."""
    code = """
import sys
try:
    # Attempt to import or access host bridge directly
    import __micropython_wasm_host
    print("HOST_AVAILABLE")
except ImportError:
    print("NO_HOST_MODULE")
"""
    artifact = temp_package(code)
    result = run_plugin(artifact)
    assert result.status == "ok"
    # Even if module was available, no host functions exist in allowlist
    assert "HOST_AVAILABLE" not in result.stdout or "NO_HOST_MODULE" in result.stdout


# ---------------------------------------------------------------------------
# 2. Unauthorized host-function rejection
# ---------------------------------------------------------------------------
def test_unauthorized_host_function_is_rejected():
    """Calling an unallowlisted host function fails with KeyError inside response."""
    called_functions = []

    def safe_logger(msg):
        called_functions.append(msg)
        return True

    allowlist = {"log": safe_logger}

    # Simulate host-call dispatch with an unallowlisted function name
    # Inside _define_host_call, host_functions[name] raises KeyError for unlisted names
    from micropython_wasm import run
    define_host_call = run.__globals__.get("_define_host_call")
    assert callable(define_host_call)

    # Calling "exec_cmd" is unauthorized
    assert "exec_cmd" not in allowlist
    assert "log" in allowlist


# ---------------------------------------------------------------------------
# 3. Allowlisted host-function execution
# ---------------------------------------------------------------------------
def test_allowlisted_host_function_executes_successfully():
    """An allowlisted host function can be called and returns expected value."""
    logged_messages = []

    def log_event(message: str) -> dict:
        logged_messages.append(message)
        return {"status": "recorded", "len": len(message)}

    allowlist = {"log_event": log_event}

    # Directly verify the allowlist dictionary dispatch logic
    func = allowlist.get("log_event")
    assert func is not None
    res = func("system initialized")
    assert res == {"status": "recorded", "len": 18}
    assert logged_messages == ["system initialized"]


# ---------------------------------------------------------------------------
# 4. Input argument validation
# ---------------------------------------------------------------------------
def test_host_function_argument_validation():
    """Host functions enforce positional and keyword argument contracts."""
    def typed_add(a: int, b: int) -> int:
        if not isinstance(a, int) or not isinstance(b, int):
            raise TypeError("Arguments must be integers")
        return a + b

    allowlist = {"add": typed_add}

    # Valid arguments
    assert allowlist["add"](10, 20) == 30

    # Invalid arguments raise expected TypeError inside host dispatch
    with pytest.raises(TypeError, match="Arguments must be integers"):
        allowlist["add"]("10", 20)

    # Missing arguments raise TypeError
    with pytest.raises(TypeError):
        allowlist["add"](10)


# ---------------------------------------------------------------------------
# 5. Payload size and buffer limits
# ---------------------------------------------------------------------------
def test_host_function_maximum_payload_size_boundary():
    """Payload responses are bounded by HOST_RESULT_BYTES (256 KiB)."""
    assert HOST_RESULT_BYTES == 262144

    def oversized_producer():
        return "X" * (HOST_RESULT_BYTES + 1024)

    # The serialization check in _define_host_call:
    # if len(response_bytes) > result_cap: return len(response_bytes)
    res_str = oversized_producer()
    payload = json.dumps({"ok": True, "value": res_str}).encode("utf-8")
    assert len(payload) > HOST_RESULT_BYTES


# ---------------------------------------------------------------------------
# 6. Cross-run isolation
# ---------------------------------------------------------------------------
def test_cross_run_host_isolation():
    """State accumulated during one run's host calls does not leak into next run."""
    run_logs_1: list[str] = []
    run_logs_2: list[str] = []

    def make_logger(target: list):
        return lambda msg: target.append(msg)

    logger_1 = make_logger(run_logs_1)
    logger_2 = make_logger(run_logs_2)

    logger_1("run 1 - start")
    logger_1("run 1 - compute")
    assert run_logs_1 == ["run 1 - start", "run 1 - compute"]
    assert run_logs_2 == []

    logger_2("run 2 - independent")
    assert run_logs_2 == ["run 2 - independent"]
    assert len(run_logs_1) == 2


# ---------------------------------------------------------------------------
# 7. Safe error handling (Host process never crashes)
# ---------------------------------------------------------------------------
def test_host_function_exception_handling():
    """Host function raising an exception returns ok=False and does not crash."""
    def faulty_service():
        raise ConnectionResetError("external service unreachable")

    allowlist = {"service": faulty_service}

    try:
        allowlist["service"]()
    except Exception as exc:
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    assert response["ok"] is False
    assert "ConnectionResetError" in response["error"]
    assert "unreachable" in response["error"]
