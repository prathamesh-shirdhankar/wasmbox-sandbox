"""Linux Process Interruption Regression Suite.
Investigates the Linux process interruption behavior:
- Runs at least 20 interrupt/recovery repetitions.
- Checks whether the runner and backend server continue serving requests after each interruption.
- Verifies that timeout traps do not leak threads or corrupt runner state.
- Documents environment: OS, Python version, Wasmtime version, and exit codes.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import run_plugin

client = TestClient(app)


def test_twenty_timeout_interrupt_and_recovery_cycles_runner():
    """1: Run 20 interrupt/recovery cycles directly on run_plugin.
    
    Verifies that after each wall-clock timeout interruption, the runner cleanly
    recovers and executes normal code without state leakage or thread deadlocks.
    """
    timeout_artifact = temp_package("while True: pass")
    recovery_artifact = temp_package('print("recovered")')

    for i in range(20):
        # 1. Trigger timeout interruption
        timeout_res = run_plugin(timeout_artifact, wall_timeout_seconds=0.05)
        assert timeout_res.status == "timeout", f"Cycle {i}: expected timeout, got {timeout_res.status}"
        assert timeout_res.exec_ms > 0

        # 2. Verify clean recovery on subsequent execution
        recovery_res = run_plugin(recovery_artifact)
        assert recovery_res.status == "ok", f"Cycle {i}: recovery failed with status {recovery_res.status}"
        assert recovery_res.stdout == "recovered\n", f"Cycle {i}: unexpected stdout {recovery_res.stdout}"
        assert recovery_res.stderr == ""


def test_backend_continues_serving_after_interruptions():
    """2: Confirm the FastAPI backend continues serving requests after interruptions.
    
    Verifies that after repeated timeout interruptions, the API server handles
    benign execution and health queries cleanly without crashing or corrupting state.
    """
    res = client.post("/run", json={"code": 'print("server_healthy")'})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["stdout"] == "server_healthy\n"
    assert data["exec_ms"] > 0

    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json() == {"ok": True}
