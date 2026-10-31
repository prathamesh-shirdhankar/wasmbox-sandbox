
import sys
from pathlib import Path

# Ensure backend root is on sys.path for direct pytest invocation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.api.schemas import RunResponse

client = TestClient(app)


def test_run_response_from_contract_example():
    """Build a RunResponse from the example in docs/API_CONTRACT.md."""
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


def test_run_print_hi():
    """Verify POST /run executes a simple print statement."""
    response = client.post("/run", json={"code": 'print("hi")'})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["stdout"] == "hi\n"
    assert data["stderr"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_run_handled_exception():
    """Verify POST /run returns a readable error for division by zero."""
    response = client.post("/run", json={"code": "1/0"})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert "ZeroDivisionError" in data["stderr"]
    assert data["stdout"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_run_syntax_error():
    """Verify POST /run returns a readable syntax error."""
    response = client.post("/run", json={"code": "invalid syntax ("})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert "SyntaxError" in data["stderr"]
    assert data["stdout"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_run_missing_code_payload():
    """Verify a missing code field returns 422."""
    response = client.post("/run", json={})

    assert response.status_code == 422


def test_run_empty_code_payload():
    """Verify empty code is rejected before execution."""
    response = client.post("/run", json={"code": ""})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["stderr"] == "No code provided"
    assert data["stdout"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_run_whitespace_code_payload():
    """Verify whitespace-only code is rejected before execution."""
    response = client.post("/run", json={"code": "   \n\t   "})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["stderr"] == "No code provided"
    assert data["stdout"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_run_code_exceeding_10k_chars():
    """Verify code exceeding 10,000 characters is rejected."""
    oversized_code = "x = 1\n" + ("# comment\n" * 1200)
    assert len(oversized_code) > 10_000

    response = client.post("/run", json={"code": oversized_code})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert "10000" in data["stderr"]
    assert data["stdout"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_run_code_boundary_10k_chars():
    """Verify exactly 10,000 characters are accepted."""
    code_exact_10k = "a = 1\n" + ("#" * (10_000 - 6))
    assert len(code_exact_10k) == 10_000

    response = client.post("/run", json={"code": code_exact_10k})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["stderr"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_run_code_10001_chars_is_rejected():
    """Verify exactly 10,001 characters are rejected."""
    code_10001 = "a = 1\n" + ("#" * (10_001 - 6))
    assert len(code_10001) == 10_001

    response = client.post("/run", json={"code": code_10001})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert "10000" in data["stderr"]
    assert data["stdout"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_run_runner_raises_exception(monkeypatch):
    """Verify an unexpected runner exception returns a standard error response."""
    import app.api.routes as routes_module

    def boom(*args, **kwargs):
        raise RuntimeError("simulated runner crash")

    monkeypatch.setattr(routes_module, "run_plugin", boom)

    response = client.post("/run", json={"code": 'print("hi")'})

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "error"
    assert data["stderr"] == (
        "Internal runner error: execution failed unexpectedly"
    )
    assert data["stdout"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_cors_headers_present():
    """Verify CORS allows the Vite frontend at localhost:5173."""
    response = client.options(
        "/run",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "http://localhost:5173"
    )
