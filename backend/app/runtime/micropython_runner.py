"""Run a packaged plugin with the vendored MicroPython WASI interpreter.

Bundling, not compiling: the user's script is stored in a custom WASM section
and the interpreter executes it at run time (see docs/PIPELINE.md).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from micropython_wasm import MicroPythonWasmError, run

# Always run the repo-managed interpreter, never bytes supplied by a caller.
INTERPRETER_PATH = (
    Path(__file__).resolve().parent / "artifacts" / "micropython-wasi.wasm"
)

# Custom section name matching package_plugin (Vineet).
SECTION_NAME = "wasmbox_script"

# Written to stderr by the wrapper when the user's script raises.
ERROR_MARKER = "@@WASMBOX_ERROR@@"

# Explicit per-run resource limits. The 10 MiB memory ceiling was verified to
# start the interpreter for a benign print("hi") probe on the development host.
DEFAULT_MEMORY_BYTES = 10 * 1024 * 1024
DEFAULT_FUEL = 20_000_000
DEFAULT_WALL_TIMEOUT_SECONDS = 1.0

WASM_HEADER = b"\x00asm\x01\x00\x00\x00"


class ArtifactError(ValueError):
    """The artifact is not a valid WASM file or has no script section."""


@dataclass(frozen=True)
class PluginResult:
    status: str  # "ok", "error", or "timeout"
    stdout: str
    stderr: str
    exec_ms: float = 0.0


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
            if artifact[name_start:name_end] == SECTION_NAME.encode("utf-8"):
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


def _elapsed_ms(started_at: float) -> float:
    """Elapsed wall-clock milliseconds for the runner invocation."""
    return round((time.perf_counter() - started_at) * 1000, 2)


def _timeout_message(exception_text: str) -> str | None:
    """Map the known micropython-wasm trap text to readable timeout reasons."""
    normalized = exception_text.lower()
    if "wasm trap: interrupt" in normalized or "epoch deadline" in normalized:
        return "Execution timed out: wall-clock limit exceeded."
    if (
        "all fuel consumed by webassembly" in normalized
        or "out of fuel" in normalized
        or "fuel exhausted" in normalized
    ):
        return "Execution timed out: instruction fuel exhausted."
    return None


def run_plugin(
    artifact: bytes | Any,
    *,
    memory_bytes: int = DEFAULT_MEMORY_BYTES,
    fuel: int = DEFAULT_FUEL,
    wall_timeout_seconds: float = DEFAULT_WALL_TIMEOUT_SECONDS,
) -> PluginResult:
    """Run a packaged script with explicit WASM limits and elapsed timing.

    ``exec_ms`` measures the call to ``micropython_wasm.run`` and therefore
    includes its per-run engine/module startup. Artifact extraction and API
    request parsing are outside this measurement. Memory usage is not measured.
    """
    if hasattr(artifact, "wasm_bytes"):
        artifact_bytes = artifact.wasm_bytes
    else:
        artifact_bytes = artifact

    try:
        script = extract_script(artifact_bytes)
    except ArtifactError as exc:
        return PluginResult("error", "", f"Invalid plugin artifact: {exc}")

    started_at = time.perf_counter()
    try:
        # No readonly_dir and no host_functions: no files, no network.
        result = run(
            _wrap(script),
            wasm_path=INTERPRETER_PATH,
            memory_bytes=memory_bytes,
            fuel=fuel,
            wall_timeout_seconds=wall_timeout_seconds,
        )
    except MicroPythonWasmError as exc:
        elapsed_ms = _elapsed_ms(started_at)
        text = str(exc).strip()
        timeout_stderr = _timeout_message(text)
        if timeout_stderr:
            return PluginResult("timeout", "", timeout_stderr, elapsed_ms)
        first_line = text.splitlines()[0][:200] if text else "unknown failure"
        return PluginResult(
            "error", "", f"Execution failed: {first_line}", elapsed_ms
        )

    elapsed_ms = _elapsed_ms(started_at)
    # Check stderr only, never stdout, for the marker.
    if result.stderr.startswith(ERROR_MARKER):
        return PluginResult(
            "error", result.stdout, _clean_error(result.stderr), elapsed_ms
        )
    return PluginResult("ok", result.stdout, result.stderr, elapsed_ms)
