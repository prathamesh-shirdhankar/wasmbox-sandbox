"""
Fake runner.
Provides simulated execution for testing the API contract and frontend integration
before the real MicroPython WASI runner is connected.

IMPORTANT: This module only matches text patterns in the submitted code string.
It NEVER executes user code. No eval(), exec(), or subprocess call is made here.
"""
from app.api.schemas import RunResponse


def run_code_fake(code: str) -> RunResponse:
    """
    Simulate code execution adhering  API contract.
    Guarantees all 5 response fields are present.

    Note: pattern matching only — user code is never executed.
    """
    # Specific simulation cases for Day 1 verification and UI tests
    if 'print("hi")' in code or "print('hi')" in code:
        return RunResponse(
            status="ok",
            stdout="hi\n",
            stderr="",
            exec_ms=0,
            mem_bytes=0,
        )
    elif "1/0" in code or "ZeroDivisionError" in code:
        return RunResponse(
            status="error",
            stdout="",
            stderr="ZeroDivisionError: division by zero",
            exec_ms=0,
            mem_bytes=0,
        )
    elif "invalid syntax" in code or code.strip().startswith("invalid syntax"):
        return RunResponse(
            status="error",
            stdout="",
            stderr="SyntaxError: invalid syntax",
            exec_ms=0,
            mem_bytes=0,
        )
    else:
        # Default simulated execution — never runs the code
        return RunResponse(
            status="ok",
            stdout=f"Simulated execution: {code.strip()}\n",
            stderr="",
            exec_ms=0,
            mem_bytes=0,
        )
