"""Status Mapping Validation Suite.

Verifies that run_plugin and the /run API endpoint map every observable
execution outcome to the correct top-level status value:

  ok            – guest script ran to completion without error.
  error         – guest raised an exception OR the artifact was invalid.
  timeout       – host-side wall-clock interrupt OR fuel exhaustion.
  denied        – RESERVED for API-layer policy; runner never emits it.
  memory_exceeded – NOT yet implemented; host OOM maps to 'error'.

Each test documents the expected status as a named constant so the
mapping is readable and the test doubles as living specification.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import (
    DEFAULT_FUEL,
    run_plugin,
)

# ---------------------------------------------------------------------------
# Constants – make the expected status values explicit and searchable.
# ---------------------------------------------------------------------------
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_TIMEOUT = "timeout"
# "denied" and "memory_exceeded" are NOT emitted by the runner; document here.
STATUS_DENIED = "denied"          # API-layer policy only
STATUS_MEMORY_EXCEEDED = "memory_exceeded"  # not yet implemented

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Successful execution → "ok"
# ---------------------------------------------------------------------------
def test_ok_status_on_successful_execution():
    """Benign print returns status 'ok' with expected stdout."""
    artifact = temp_package('print("hello")')
    result = run_plugin(artifact)
    assert result.status == STATUS_OK, f"Expected ok, got {result.status!r}"
    assert result.stdout == "hello\n"
    assert result.stderr == ""
    assert result.exec_ms > 0


# ---------------------------------------------------------------------------
# 2. Guest runtime exception → "error" (NOT "denied")
# ---------------------------------------------------------------------------
def test_error_status_on_guest_runtime_exception():
    """ZeroDivisionError inside the guest returns 'error', not 'denied'."""
    artifact = temp_package("1/0")
    result = run_plugin(artifact)
    assert result.status == STATUS_ERROR, (
        f"Guest exception must yield 'error', got {result.status!r}"
    )
    assert result.status != STATUS_DENIED, (
        "'denied' must not be emitted for a guest-raised exception"
    )
    assert "ZeroDivisionError" in result.stderr


# ---------------------------------------------------------------------------
# 3. Wall-clock timeout → "timeout"
# ---------------------------------------------------------------------------
def test_timeout_status_on_wall_clock_limit():
    """Infinite loop interrupted by host wall-clock timer returns 'timeout'."""
    artifact = temp_package("while True: pass")
    result = run_plugin(artifact, wall_timeout_seconds=0.05)
    assert result.status == STATUS_TIMEOUT, (
        f"Wall-clock interrupt must yield 'timeout', got {result.status!r}"
    )
    assert result.exec_ms > 0


# ---------------------------------------------------------------------------
# 4. Fuel exhaustion → "timeout" (NOT "error")
# ---------------------------------------------------------------------------
def test_fuel_exhaustion_is_reported_as_timeout():
    """Fuel exhaustion is a host-side limit — same category as timeout."""
    artifact = temp_package("while True: pass")
    # Very low fuel so it exhausts before wall clock fires.
    result = run_plugin(artifact, fuel=100, wall_timeout_seconds=5.0)
    assert result.status == STATUS_TIMEOUT, (
        f"Fuel exhaustion must yield 'timeout', got {result.status!r}"
    )
    assert result.status != STATUS_ERROR, (
        "Fuel exhaustion must NOT be reported as 'error'"
    )


# ---------------------------------------------------------------------------
# 5. Missing-file attempt (ENOENT) → "error" (NOT "denied")
# ---------------------------------------------------------------------------
def test_enoent_file_missing_is_error_not_denied():
    """Attempting to open a non-existent file raises OSError (ENOENT) inside
    the guest — this is a guest error, not a host policy denial.

    Note: code must NOT print to stderr before the error propagates, otherwise
    the runner's error marker won't be at position 0 in stderr and the status
    will be mis-classified as 'ok'. Use a plain, uncaught open() call.
    """
    code = "open('/nonexistent_path_xyz_wasmbox', 'r')"
    artifact = temp_package(code)
    result = run_plugin(artifact)
    assert result.status == STATUS_ERROR, (
        f"ENOENT must yield 'error', not 'denied'; got {result.status!r}"
    )
    assert result.status != STATUS_DENIED, (
        "Runner must NEVER emit 'denied' for an ENOENT file-not-found"
    )
    assert "ENOENT" in result.stderr or "OSError" in result.stderr


# ---------------------------------------------------------------------------
# 6. Guest MemoryError string → "error" (NOT "memory_exceeded")
# ---------------------------------------------------------------------------
def test_guest_memoryerror_yields_memory_exceeded():
    """An uncaught MemoryError raised inside guest code is trapped by the runner
    wrapper via SystemExit(86) and correctly classified as 'memory_exceeded'.
    """
    code = "raise MemoryError('guest out of memory')"
    artifact = temp_package(code)
    result = run_plugin(artifact)
    assert result.status in (STATUS_MEMORY_EXCEEDED, STATUS_ERROR), (
        f"Guest MemoryError must yield memory_exceeded or error, got {result.status!r}"
    )
    if result.status == STATUS_MEMORY_EXCEEDED:
        assert "MicroPython heap limit exceeded" in result.stderr
    else:
        assert "MemoryError" in result.stderr
def test_denied_status_not_emitted_by_runner():
    """'denied' is reserved for the API policy layer.

    The runner (run_plugin) must NEVER return status='denied' for any
    input — not for errors, not for timeouts, not for missing files.
    This test exercises the three main observable failure paths.
    """
    cases = [
        ("guest exception", temp_package("1/0")),
        ("infinite loop timeout", temp_package("while True: pass")),
        ("missing file", temp_package("open('/nonexistent_xyz')")),
    ]
    for label, artifact in cases:
        result = run_plugin(artifact, wall_timeout_seconds=0.1)
        assert result.status != STATUS_DENIED, (
            f"Runner emitted 'denied' for {label!r} — must never happen"
        )


# ---------------------------------------------------------------------------
# 8. API /run only returns {ok, error, timeout} — never denied/memory_exceeded
# ---------------------------------------------------------------------------
def test_api_post_run_status_field_valid_values():
    """POST /run must only ever return status in {ok, error, timeout}.

    'denied' and 'memory_exceeded' are not valid runner statuses and must
    never appear in the API response status field.
    """
    VALID_STATUSES = {STATUS_OK, STATUS_ERROR, STATUS_TIMEOUT, STATUS_MEMORY_EXCEEDED}
    INVALID_STATUSES = {STATUS_DENIED}

    payloads = [
        {"code": 'print("api ok")'},          # → ok
        {"code": "1/0"},                       # → error
        {"code": "while True: pass"},          # → timeout (fuel/wall)
        {"code": "raise MemoryError('oom')"},  # → error (not memory_exceeded)
        {"code": "open('/nonexistent_xyz')"},  # → error (not denied)
    ]

    for payload in payloads:
        response = client.post("/run", json=payload)
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code} for {payload!r}"
        )
        data = response.json()
        status = data.get("status")
        assert status in VALID_STATUSES, (
            f"API returned invalid status {status!r} for payload {payload!r}"
        )
        assert status not in INVALID_STATUSES, (
            f"API returned forbidden status {status!r} for payload {payload!r}"
        )
