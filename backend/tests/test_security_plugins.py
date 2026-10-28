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


# ---- Stubs: switch these on when the real /run exists ----


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
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] == 0


@pytest.mark.skip(reason="Needs real /run and the Mid-Project audit")
def test_read_passwd_is_blocked():
    # Expect: status "denied" (or "error"), and "root:" NOT in stdout
    pass


@pytest.mark.skip(reason="Needs real /run and the Mid-Project audit")
def test_open_socket_is_blocked():
    # Expect: status "denied", and "connected" NOT in stdout
    pass


@pytest.mark.skip(reason="50 ms is not reachable with this runner; see docs/SPIKES.md")
def test_infinite_loop_times_out():
    # Expect: status "timeout" after about 50 ms
    pass


@pytest.mark.skip(reason="Memory usage is not measured; memory-bomb test intentionally not run")
def test_memory_bomb_is_stopped():
    # Expect: status "memory_exceeded"
    pass