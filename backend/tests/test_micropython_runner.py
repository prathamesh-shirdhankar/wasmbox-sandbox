"""Runtime tests. Benign scripts only."""

from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import extract_script, run_plugin


def test_extract_script_roundtrip():
    code = 'print("héllo")\n'
    assert extract_script(temp_package(code)) == code


def test_one_print():
    result = run_plugin(temp_package('print("hi")'))
    assert (result.status, result.stdout, result.stderr) == ("ok", "hi\n", "")
    assert result.exec_ms > 0


def test_two_prints():
    result = run_plugin(temp_package('print("a")\nprint("b")'))
    assert (result.status, result.stdout, result.stderr) == ("ok", "a\nb\n", "")
    assert result.exec_ms > 0


def test_exception_is_readable_error():
    result = run_plugin(temp_package("1/0"))
    assert result.status == "error"
    assert "ZeroDivisionError" in result.stderr
    assert "@@WASMBOX_ERROR@@" not in result.stderr
    assert "<stdin>" not in result.stderr
    assert result.exec_ms > 0


def test_syntax_error_is_readable_error():
    result = run_plugin(temp_package("print("))
    assert result.status == "error"
    assert "SyntaxError" in result.stderr
    assert "@@WASMBOX_ERROR@@" not in result.stderr
    assert "<stdin>" not in result.stderr
    assert result.exec_ms > 0


def test_invalid_artifact_returns_error():
    result = run_plugin(b"not a wasm file")
    assert result.status == "error"
    assert "Invalid plugin artifact" in result.stderr