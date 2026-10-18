"""
Provides simulated execution for testing the API contract, frontend integration,
and response shapes before the real MicroPython WASI runner is connected.
"""
from app.api.schemas import RunResponse


def run_code_fake(code: str) -> RunResponse:
    """
    Simulate code execution adhering to the API contract.
    Guarantees all 5 response fields are present.
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
    elif "SyntaxError" in code or "invalid syntax" in code:
        return RunResponse(
            status="error",
            stdout="",
            stderr="SyntaxError: invalid syntax",
            exec_ms=0,
            mem_bytes=0,
        )
    else:
        # Default benign simulated execution
        clean_code = code.strip()
        return RunResponse(
            status="ok",
            stdout=f"Simulated execution: {clean_code}\n",
            stderr="",
            exec_ms=0,
            mem_bytes=0,
        )
