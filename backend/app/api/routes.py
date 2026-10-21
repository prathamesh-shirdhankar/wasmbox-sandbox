import logging

from fastapi import APIRouter
from app.api.schemas import HealthResponse, RunRequest, RunResponse
from app.runtime.packaging import package_plugin
from app.runtime.micropython_runner import run_plugin

router = APIRouter()
logger = logging.getLogger(__name__)

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
    Executes through the real pipeline: package_plugin(code) -> run_plugin(artifact).
    Any unexpected runner exception is caught and returned as a 5-field error response.
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
            stderr=(
                f"Code exceeds maximum allowed size of {MAX_CODE_LENGTH} characters "
                f"(received {len(code)})"
            ),
            exec_ms=0,
            mem_bytes=0,
        )

    # Real execution pipeline: package_plugin -> run_plugin
    try:
        artifact = package_plugin(code)
        result = run_plugin(artifact.wasm_bytes)
        return RunResponse(
            status=result.status,
            stdout=result.stdout,
            stderr=result.stderr,
            exec_ms=0,
            mem_bytes=0,
        )
    except Exception as exc:
        logger.exception("Runner raised an unexpected exception")
        return RunResponse(
            status="error",
            stdout="",
            stderr=f"Internal runner error: {exc}",
            exec_ms=0,
            mem_bytes=0,
        )

