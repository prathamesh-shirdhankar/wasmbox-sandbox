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


@pytest.mark.skip(reason="Needs real /run (Week 2)")
def test_benign_control_runs_ok():
    # Expect: status "ok", stdout "hello from the control plugin\n"
    pass


@pytest.mark.skip(reason="Needs real /run and the Mid-Project audit")
def test_read_passwd_is_blocked():
    # Expect: status "denied" (or "error"), and "root:" NOT in stdout
    pass


@pytest.mark.skip(reason="Needs real /run and the Mid-Project audit")
def test_open_socket_is_blocked():
    # Expect: status "denied", and "connected" NOT in stdout
    pass


@pytest.mark.skip(reason="Needs the 50 ms timeout (Week 3)")
def test_infinite_loop_times_out():
    # Expect: status "timeout" after about 50 ms
    pass


@pytest.mark.skip(reason="Needs the memory cap (Week 3)")
def test_memory_bomb_is_stopped():
    # Expect: status "memory_exceeded"
    pass