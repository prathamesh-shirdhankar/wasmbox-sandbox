
"""Tests for unusual inputs and edge cases against POST /run.

Coverage:
1. Comments only.
2. Spaces only.
3. Multi-byte Unicode characters and emojis.
4. Tabs and mixed indentation.
5. A single very long line under the code-size limit.
6. A script generating large output.
7. Repeated timeout interruptions and recovery.
"""

import sys
from pathlib import Path

# Ensure backend root is on sys.path for direct pytest invocation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_comments_only_executes_ok():
    """Comments-only Python code is valid and produces no output."""
    code = "# just a comment\n# another line of comment\n"

    response = client.post("/run", json={"code": code})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stdout"] == ""
    assert data["stderr"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_spaces_only_rejected_as_no_code():
    """Spaces-only input is rejected before execution."""
    response = client.post(
        "/run",
        json={"code": "     \n\t    \n  "},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "No code provided" in data["stderr"]
    assert data["stdout"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_unicode_and_emojis():
    """Multi-byte Unicode characters and emojis are handled correctly."""
    code = 'print("Hello, 🌍! 🚀 नमस्ते 世界")\n'

    response = client.post("/run", json={"code": code})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Hello, 🌍! 🚀 नमस्ते 世界\n" in data["stdout"]
    assert data["stderr"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_tab_indentation_executes_ok():
    """Valid Python code using tab indentation executes successfully."""
    code = (
        "def greet(name):\n"
        "\tif name:\n"
        "\t\treturn 'Hello, ' + name\n"
        "\treturn 'Hello, stranger'\n"
        "print(greet('WasmBox'))\n"
    )

    response = client.post("/run", json={"code": code})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stdout"] == "Hello, WasmBox\n"
    assert data["stderr"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_mixed_tabs_and_spaces_indentation_error():
    """Mixing tabs and spaces in indentation returns a readable error."""
    code = (
        "def foo():\n"
        "\tx = 1\n"
        "    return x\n"
        "print(foo())\n"
    )

    response = client.post("/run", json={"code": code})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert (
        "IndentationError" in data["stderr"]
        or "TabError" in data["stderr"]
    )
    assert data["stdout"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_indentation_syntax_error():
    """Mismatched indentation returns an error without crashing the server."""
    code = (
        "def foo():\n"
        "  x = 1\n"
        "    y = 2\n"
    )

    response = client.post("/run", json={"code": code})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["stderr"].strip()
    assert data["stdout"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_single_very_long_line_under_limit():
    """A single long line under 10,000 characters executes correctly."""
    prefix = 'x = "'
    suffix = '"\nprint(len(x))\n'
    target_length = 9990

    content_length = target_length - len(prefix) - len(suffix)
    code = prefix + ("a" * content_length) + suffix

    assert len(code) <= 9999

    response = client.post("/run", json={"code": code})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stdout"] == f"{content_length}\n"
    assert data["stderr"] == ""
    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_script_generating_large_output():
    """A script generating 5,000 lines completes or times out safely."""
    code = "for i in range(5000):\n    print(i)\n"

    response = client.post("/run", json={"code": code})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "timeout")

    if data["status"] == "ok":
        lines = data["stdout"].splitlines()
        assert len(lines) == 5000
        assert lines[0] == "0"
        assert lines[-1] == "4999"
        assert data["stderr"] == ""
    else:
        assert "timed out" in data["stderr"].lower()

    assert data["exec_ms"] > 0
    assert data["mem_bytes"] > 0


def test_repeated_timeout_interruptions_leave_server_healthy():
    """Repeated infinite-loop timeouts must not poison the shared Engine."""
    infinite_loop_code = "while True:\n    pass"

    for _ in range(3):
        response = client.post(
            "/run",
            json={"code": infinite_loop_code},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "timeout"
        assert "timed out" in data["stderr"].lower()
        assert data["exec_ms"] > 0

    # A normal execution immediately after the timeouts must still work.
    benign_response = client.post(
        "/run",
        json={"code": "print(42 + 58)"},
    )

    assert benign_response.status_code == 200
    benign_data = benign_response.json()
    assert benign_data["status"] == "ok"
    assert benign_data["stdout"] == "100\n"
    assert benign_data["stderr"] == ""
    assert benign_data["exec_ms"] > 0
    assert benign_data["mem_bytes"] > 0
