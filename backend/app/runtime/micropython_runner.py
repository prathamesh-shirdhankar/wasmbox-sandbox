"""Run a packaged plugin with the vendored MicroPython WASI interpreter.

Bundling, not compiling: the user's script is stored in a custom WASM section
and the interpreter executes it at run time (see docs/PIPELINE.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from micropython_wasm import MicroPythonWasmError, run

# Always run the repo-managed interpreter, never bytes supplied by a caller.
INTERPRETER_PATH = (
    Path(__file__).resolve().parent / "artifacts" / "micropython-wasi.wasm"
)

# Custom section name matching package_plugin (Vineet).
# Supports both 'wasmbox_script' and 'wasmbox.script' for compatibility.
SECTION_NAME = "wasmbox_script"
SUPPORTED_SECTION_NAMES = (b"wasmbox_script", b"wasmbox.script")

# Written to stderr by the wrapper when the user's script raises.
ERROR_MARKER = "@@WASMBOX_ERROR@@"

WASM_HEADER = b"\x00asm\x01\x00\x00\x00"


class ArtifactError(ValueError):
    """The artifact is not a valid WASM file or has no script section."""


@dataclass(frozen=True)
class PluginResult:
    status: str  # "ok" or "error" in Week 2
    stdout: str
    stderr: str


def _read_leb128(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise ArtifactError("Truncated artifact")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 35:
            raise ArtifactError("Invalid length in artifact")


def extract_script(artifact: bytes) -> str:
    """Return the script stored in the artifact's custom section."""
    if not artifact.startswith(WASM_HEADER):
        raise ArtifactError("Not a WASM artifact")

    pos = len(WASM_HEADER)
    while pos < len(artifact):
        section_id = artifact[pos]
        pos += 1
        size, pos = _read_leb128(artifact, pos)
        end = pos + size
        if end > len(artifact):
            raise ArtifactError("Truncated artifact")
        if section_id == 0:  # custom section
            name_len, name_start = _read_leb128(artifact, pos)
            name_end = name_start + name_len
            if name_end > end:
                raise ArtifactError("Invalid section name")
            if artifact[name_start:name_end] in SUPPORTED_SECTION_NAMES:
                try:
                    return artifact[name_end:end].decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ArtifactError("Script is not valid UTF-8") from exc
        pos = end
    raise ArtifactError("Script section not found")


def _wrap(code: str) -> str:
    # package 0.1a2 hides the traceback when a script fails, so catch it here
    # and print it to stderr. Known limits: sys.exit() inside the script is
    # reported as an error, and a script can fake the marker via stderr.
    # This is for readable errors, not a security boundary.
    return (
        "import sys\n"
        "try:\n"
        "    exec(" + repr(code) + ", {'__name__': '__main__'})\n"
        "except BaseException as e:\n"
        "    sys.stderr.write(" + repr(ERROR_MARKER + "\n") + ")\n"
        "    sys.print_exception(e, sys.stderr)\n"
    )


def _clean_error(stderr: str) -> str:
    text = stderr[len(ERROR_MARKER):].lstrip("\n")
    # Drop the frame that points at our wrapper, not at the user's code.
    text = re.sub(r'  File "<stdin>", line \d+, in <module>\n', "", text, count=1)
    return text.strip()


def run_plugin(artifact: bytes | Any) -> PluginResult:
    if hasattr(artifact, "wasm_bytes"):
        artifact_bytes = artifact.wasm_bytes
    else:
        artifact_bytes = artifact

    try:
        script = extract_script(artifact_bytes)
    except ArtifactError as exc:
        return PluginResult("error", "", f"Invalid plugin artifact: {exc}")

    try:
        # No readonly_dir and no host_functions: no files, no network.
        # Package defaults for fuel and timeout stay as they are (Week 3).
        result = run(_wrap(script), wasm_path=INTERPRETER_PATH)
    except MicroPythonWasmError as exc:
        text = str(exc).strip()
        first_line = text.splitlines()[0][:200] if text else "unknown failure"
        return PluginResult("error", "", f"Execution failed: {first_line}")

    # Check stderr only, never stdout, for the marker.
    if result.stderr.startswith(ERROR_MARKER):
        return PluginResult("error", result.stdout, _clean_error(result.stderr))
    return PluginResult("ok", result.stdout, result.stderr)