"""Mid-project audit tests for file and network isolation via the real /run API.

These tests submit the attack source to WasmBox's WebAssembly runner. Do not
execute the source directly with CPython on the host machine.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
MALICIOUS_DIR = REPO_ROOT / "plugins" / "malicious"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def run_plugin_source(client: TestClient, filename: str) -> dict:
    source = (MALICIOUS_DIR / filename).read_text(encoding="utf-8")
    response = client.post("/run", json={"code": source})
    assert response.status_code == 200, response.text
    data = response.json()
    assert {"status", "stdout", "stderr", "exec_ms", "mem_bytes"}.issubset(data)
    return data


def test_read_passwd_cannot_disclose_host_file(client: TestClient):
    """The guest cannot read the host /etc/passwd contents through /run."""
    data = run_plugin_source(client, "read_passwd.py")

    assert data["status"] in {"error", "denied"}, data
    combined_output = data["stdout"] + "\n" + data["stderr"]
    assert "root:" not in combined_output, data
    assert data["stderr"].strip(), data


def test_open_socket_cannot_connect_to_network(client: TestClient):
    """The guest's network attempt must fail before it prints 'connected'."""
    data = run_plugin_source(client, "open_socket.py")

    assert data["status"] in {"error", "denied"}, data
    assert "connected" not in data["stdout"], data
    assert data["stderr"].strip(), data
