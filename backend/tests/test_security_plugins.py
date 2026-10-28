from pathlib import Path

import pytest

# This file lives in backend/tests/, so the repo root is two folders up.
REPO_ROOT = Path(__file__).resolve().parents[2]
MALICIOUS_DIR = REPO_ROOT / "plugins" / "malicious"

PLUGINS = [
    "benign_control.py",
    "read_passwd.py",
    "open_socket.py",
    "infinite_loop.py",
    "memory_bomb.py",
]


@pytest.mark.parametrize("name", PLUGINS)
def test_plugin_file_exists_and_is_valid_python(name):
    path = MALICIOUS_DIR / name
    assert path.exists(), f"{name} is missing"
    # compile() only CHECKS the syntax. It does NOT run the code.
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


# ---- Real /run security checks ----


def test_benign_control_runs_ok():
    """Verify that a benign plugin executes cleanly with status 'ok' through real /run."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    source = (MALICIOUS_DIR / "benign_control.py").read_text(encoding="utf-8")
    response = client.post("/run", json={"code": source})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stdout"] == "hello from the control plugin\n"
    assert data["stderr"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_read_passwd_is_blocked():
    """File-reading plugin must not disclose real host file contents."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    source = (MALICIOUS_DIR / "read_passwd.py").read_text(encoding="utf-8")
    response = client.post("/run", json={"code": source})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] in {"error", "denied"}, data
    assert "root:" not in data["stdout"] + "\n" + data["stderr"], data
    assert data["stderr"].strip(), data


def test_open_socket_is_blocked():
    """Network plugin must fail without printing that it connected."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    source = (MALICIOUS_DIR / "open_socket.py").read_text(encoding="utf-8")
    response = client.post("/run", json={"code": source})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] in {"error", "denied"}, data
    assert "connected" not in data["stdout"], data
    assert data["stderr"].strip(), data


@pytest.mark.skip(reason="Needs the 50 ms timeout (Week 3)")
def test_infinite_loop_times_out():
    # Expect: status "timeout" after about 50 ms
    pass


@pytest.mark.skip(reason="Needs the memory cap (Week 3)")
def test_memory_bomb_is_stopped():
    # Expect: status "memory_exceeded"
    pass