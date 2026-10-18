from fastapi import APIRouter
from app.api.schemas import HealthResponse, RunRequest, RunResponse
from app.api.fake_runner import run_code_fake

router = APIRouter()

MAX_CODE_LENGTH = 10_000


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Health check endpoint indicating API server readiness."""
    return HealthResponse(ok=True)


@router.post("/run", response_model=RunResponse)
def run_code(payload: RunRequest) -> RunResponse:
    """
    Code execution endpoint adhering to API contract.
    Validates input (empty/whitespace and <= 10,000 chars) before running.
    Delegates to fake runner for contract and UI integration.
    """
    code = payload.code

    # Input validation: reject empty or whitespace-only code
    if not code.strip():
        return RunResponse(
            status="error",
            stdout="",
            stderr="No code provided",
            exec_ms=0,
            mem_bytes=0,
        )

    # Input validation: reject code exceeding 10,000 characters
    if len(code) > MAX_CODE_LENGTH:
        return RunResponse(
            status="error",
            stdout="",
            stderr=f"Code exceeds maximum allowed size of {MAX_CODE_LENGTH} characters (received {len(code)})",
            exec_ms=0,
            mem_bytes=0,
        )

    # Delegate to runner
    return run_code_fake(code)
