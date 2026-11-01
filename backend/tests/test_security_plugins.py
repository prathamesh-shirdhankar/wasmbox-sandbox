"""Security tests for benign and malicious WasmBox plugins."""

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
    """Verify every security-test plugin exists and has valid Python syntax."""
    path = MALICIOUS_DIR / name

    assert path.exists(), f"{name} is missing"

    # compile() checks syntax only. It does not execute the code.
    compile(
        path.read_text(encoding="utf-8"),
        str(path),
        "exec",
    )


# ---- Real /run security checks ----


def test_benign_control_runs_ok():
    """Verify a benign plugin executes through the real /run endpoint."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    source = (MALICIOUS_DIR / "benign_control.py").read_text(
        encoding="utf-8"
    )

    response = client.post("/run", json={"code": source})

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["stdout"] == "hello from the control plugin\n"
    assert data["stderr"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_read_passwd_is_blocked():
    """Verify guest code cannot disclose real host file contents."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    source = (MALICIOUS_DIR / "read_passwd.py").read_text(
        encoding="utf-8"
    )

    response = client.post("/run", json={"code": source})

    assert response.status_code == 200

    data = response.json()

    # The current runner reports this guest failure as "error".
    assert data["status"] == "error", data

    # Never allow real host password-file contents to be disclosed.
    assert "root:" not in data["stdout"] + "\n" + data["stderr"], data
    assert data["stderr"].strip(), data


def test_open_socket_is_blocked():
    """Verify guest code cannot establish a network connection."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    source = (MALICIOUS_DIR / "open_socket.py").read_text(
        encoding="utf-8"
    )

    response = client.post("/run", json={"code": source})

    assert response.status_code == 200

    data = response.json()

    # The current runner reports this guest failure as "error".
    assert data["status"] == "error", data

    assert "connected" not in data["stdout"].lower(), data
    assert data["stderr"].strip(), data


def test_infinite_loop_times_out():
    """Verify an infinite-loop plugin is interrupted through the real API."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    source = (MALICIOUS_DIR / "infinite_loop.py").read_text(
        encoding="utf-8"
    )

    response = client.post("/run", json={"code": source})

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "timeout", data
    assert "timed out" in data["stderr"].lower(), data
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


@pytest.mark.skip(
    reason=(
        "Memory-bomb execution must be tested in an isolated environment "
        "with an explicit process/container memory cap."
    )
)
def test_memory_bomb_is_stopped():
    """Keep the memory-bomb test disabled on the development host."""
    # Do not execute this plugin directly on the developer's machine.
    # Its bounded Docker verification is performed separately.
    pass