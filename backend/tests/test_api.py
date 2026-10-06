import sys
from pathlib import Path

# Ensure backend root is on sys.path for direct pytest invocation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.api.schemas import RunResponse

client = TestClient(app)


def test_run_response_from_contract_example():
    """Build a RunResponse from the example in docs/API_CONTRACT.md and check the fields."""
    example_payload = {
        "status": "ok",
        "stdout": "hi\n",
        "stderr": "",
        "exec_ms": 0,
        "mem_bytes": 0,
    }
    response = RunResponse(**example_payload)
    assert response.status == "ok"
    assert response.stdout == "hi\n"
    assert response.stderr == ""
    assert response.exec_ms == 0
    assert response.mem_bytes == 0


def test_health_endpoint():
    """Verify GET /health returns 200 and {'ok': True}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_run_mock_contract_shape():
    """Verify POST /run accepts code and returns expected contract response."""
    test_code = "print('Hello, WasmBox!')"
    response = client.post("/run", json={"code": test_code})

    assert response.status_code == 200
    data = response.json()

    # Verify all expected keys are present
    assert "status" in data
    assert "stdout" in data
    assert "stderr" in data
    assert "exec_ms" in data
    assert "mem_bytes" in data

    # Verify exact Week 1 mock values
    assert data["status"] == "ok"
    assert data["stdout"] == f"[mock] received {len(test_code)} characters\n"
    assert data["stderr"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_run_missing_code_payload():
    """Verify POST /run without required 'code' field returns 422 Unprocessable Entity."""
    response = client.post("/run", json={})
    assert response.status_code == 422


def test_cors_headers_present():
    """Verify CORS headers allow requests from frontend localhost:5173."""
    response = client.options(
        "/run",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
