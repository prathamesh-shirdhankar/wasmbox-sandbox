"""Tests for unusual inputs and edge cases against POST /run.
1. Comments only (# just a comment)
2. Spaces only
3. Multi-byte Unicode characters and emojis
4. Tabs and mixed indentation
5. Single very long line (up to 9,999 chars)
6. Script generating large output (printing 5,000 lines)
"""

import sys
from pathlib import Path

# Ensure backend root is on sys.path for direct pytest invocation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_comments_only_executes_ok():
    """Comments-only input is valid Python code that produces no output."""
    code = "# just a comment\n# another line of comment\n"
    response = client.post("/run", json={"code": code})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stdout"] == ""
    assert data["stderr"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_spaces_only_rejected_as_no_code():
    """Spaces-only input should be rejected before execution."""
    response = client.post("/run", json={"code": "     \n\t   \n  "})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "No code provided" in data["stderr"]
    assert data["stdout"] == ""


def test_unicode_and_emojis():
    """Multi-byte Unicode characters and emojis should be handled correctly."""
    code = 'print("Hello, 🌍! 🚀 नमस्ते 世界")\n'
    response = client.post("/run", json={"code": code})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "Hello, 🌍! 🚀 नमस्ते 世界\n" in data["stdout"]
    assert data["stderr"] == ""


def test_tab_indentation_executes_ok():
    """Valid Python script using tab characters ('\\t') for indentation executes cleanly."""
    code = "def greet(name):\n\tif name:\n\t\treturn 'Hello, ' + name\n\treturn 'Hello, stranger'\nprint(greet('WasmBox'))\n"
    response = client.post("/run", json={"code": code})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stdout"] == "Hello, WasmBox\n"
    assert data["stderr"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_mixed_tabs_and_spaces_indentation_error():
    """
    Mixing tabs and spaces in Python indentation returns an IndentationError / status: error.
    MicroPython parser returns 'IndentationError: unindent doesn't match any outer indent level'
    (standard CPython gives TabError: inconsistent use of tabs and spaces in indentation).
    """
    code = "def foo():\n\tx = 1\n    return x\nprint(foo())\n"
    response = client.post("/run", json={"code": code})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "IndentationError" in data["stderr"] or "TabError" in data["stderr"]
    assert data["stdout"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_indentation_syntax_error():
    """Mismatched/unexpected indentation returns status: error without server crash."""
    code = "def foo():\n  x = 1\n    y = 2\n"
    response = client.post("/run", json={"code": code})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert len(data["stderr"]) > 0
    assert data["stdout"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_single_very_long_line_under_limit():
    """Single very long line up to 9,999 characters under the 10,000 char limit."""
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


def test_script_generating_large_output():
    """
    Script generating 5,000 lines of output executes without crashing the server.
    Accepts either 'ok' (if runner finishes within default wall timeout) or
    'error' (if interrupted by the runner's default 1.0s wall timeout on slower CI runners).
    """
    code = "for i in range(5000):\n    print(i)\n"
    response = client.post("/run", json={"code": code})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "error")
    if data["status"] == "ok":
        lines = data["stdout"].splitlines()
        assert len(lines) == 5000
        assert lines[0] == "0"
        assert lines[-1] == "4999"
        assert data["stderr"] == ""
    else:
        # If the runner timed out on a slow CI machine, verify server remains up and error is graceful
        assert "Execution failed" in data["stderr"] or "timeout" in data["stderr"].lower()
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0
