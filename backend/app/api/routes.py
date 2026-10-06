from fastapi import APIRouter
from app.api.schemas import HealthResponse, RunRequest, RunResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Health check endpoint indicating API server readiness."""
    return HealthResponse(ok=True)


@router.post("/run", response_model=RunResponse)
def run_code(payload: RunRequest) -> RunResponse:
    """
    Mock code execution endpoint adhering to Week 1 API contract.
    Returns status: 'ok' and formatted mock stdout with character count.
    """
    char_count = len(payload.code)
    return RunResponse(
        status="ok",
        stdout=f"[mock] received {char_count} characters\n",
        stderr="",
        exec_ms=0.0,
        mem_bytes=0,
    )
