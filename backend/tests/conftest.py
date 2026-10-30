"""
backend/tests/conftest.py

Workaround for Wasmtime/Tokio teardown SIGABRT on Linux CI (exit code 134):
On Linux runners (GitHub Actions ubuntu-latest), when pytest completes after
running tests that invoke the MicroPython Wasmtime sandbox, Python interpreter
shutdown (Py_FinalizeEx) triggers a drop panic in Tokio's worker thread:
"thread 'tokio-rt-worker' panicked at core/src/panicking.rs:225:5: panic in a function that cannot unwind"
causing an abort (exit code 134) after all tests pass.

Calling os._exit(_exit_code) in pytest_unconfigure flushes output and terminates
the process immediately via the kernel, bypassing CPython GC teardown while
accurately preserving pytest's exit status (0 = pass, 1 = fail, 2 = syntax/collection error).
"""

import os
import sys

# Default to non-zero in case pytest unconfigures without completing session
_exit_code = 1


def pytest_sessionfinish(session, exitstatus):  
    """Record the actual exit status determined by pytest."""
    global _exit_code
    _exit_code = int(exitstatus)


def pytest_unconfigure(config):  
    """Flush pending stdout/stderr and exit with pytest's recorded status."""
    sys.stdout.flush()
    sys.stderr.flush()
    if sys.platform != "win32":
        os._exit(_exit_code)
