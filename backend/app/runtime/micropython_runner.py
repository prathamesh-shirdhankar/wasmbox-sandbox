"""Run packaged plugins using a shared Wasmtime Engine and compiled Module.

Each execution receives a fresh Store and Instance. User Python source is
stored in the wasmbox_script custom section and executed by the MicroPython
WASI interpreter.
"""

from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from micropython_wasm import run
from wasmtime import (
    Config,
    Engine,
    ExitTrap,
    Func,
    FuncType,
    Linker,
    Memory,
    MemoryType,
    Module,
    Store,
    Trap,
    ValType,
    WasiConfig,
    WasmtimeError,
)


# Repository-managed interpreter.
INTERPRETER_PATH = (
    Path(__file__).resolve().parent
    / "artifacts"
    / "micropython-wasi.wasm"
)

SECTION_NAME = "wasmbox_script"
ERROR_MARKER = "@@WASMBOX_ERROR@@"

# Reserved WASI guest exit code used internally for MemoryError.
MEMORY_ERROR_EXIT_CODE = 86

# Per-execution limits.
DEFAULT_MEMORY_BYTES = 10 * 1024 * 1024
DEFAULT_FUEL = 30_000_000
DEFAULT_WALL_TIMEOUT_SECONDS = 0.25

# MicroPython Python heap, distinct from Wasmtime linear memory.
MICROPYTHON_HEAP_SIZE = "2M"

# Shared Engine epoch ticker.
TICK_INTERVAL_SECONDS = 0.005
WASM_PAGE_BYTES = 65536
HOST_RESULT_BYTES = 262144

WASM_HEADER = b"\x00asm\x01\x00\x00\x00"


class ArtifactError(ValueError):
    """The artifact is invalid or has no script section."""


@dataclass(frozen=True)
class PluginResult:
    status: str
    stdout: str
    stderr: str
    exec_ms: float = 0.0
    mem_bytes: int = 0


@dataclass
class _Runtime:
    engine: Engine
    module: Module
    define_host_call: Any
    tick_lock: threading.Lock
    stop_event: threading.Event
    ticker_thread: threading.Thread


_RUNTIME: _Runtime | None = None
_RUNTIME_LOCK = threading.Lock()

# Protects wasmtime-py's process-global function allocator.
_RUNNER_LOCK = threading.Lock()


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
    """Extract the script from the wasmbox_script custom WASM section."""
    if not isinstance(artifact, bytes) or not artifact.startswith(WASM_HEADER):
        raise ArtifactError("Not a WASM artifact")

    pos = len(WASM_HEADER)

    while pos < len(artifact):
        section_id = artifact[pos]
        pos += 1

        size, pos = _read_leb128(artifact, pos)
        end = pos + size

        if end > len(artifact):
            raise ArtifactError("Truncated artifact")

        if section_id == 0:
            name_len, name_start = _read_leb128(artifact, pos)
            name_end = name_start + name_len

            if name_end > end:
                raise ArtifactError("Invalid section name")

            if artifact[name_start:name_end] == SECTION_NAME.encode("utf-8"):
                try:
                    return artifact[name_end:end].decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ArtifactError(
                        "Script is not valid UTF-8"
                    ) from exc

        pos = end

    raise ArtifactError("Script section not found")


def _wrap(code: str) -> str:
    """Wrap user code to capture errors safely.

    An uncaught MemoryError is converted into a reserved WASI exit code.
    This avoids writing an error marker or formatting a traceback when the
    MicroPython heap may already be exhausted.
    """
    return (
        "import sys\n"
        "try:\n"
        "    exec(" + repr(code) + ", {'__name__': '__main__'})\n"
        "except MemoryError:\n"
        f"    raise SystemExit({MEMORY_ERROR_EXIT_CODE})\n"
        "except BaseException as e:\n"
        "    sys.stderr.write(" + repr(ERROR_MARKER + "\n") + ")\n"
        "    sys.print_exception(e, sys.stderr)\n"
    )


def _clean_error(stderr: str) -> str:
    text = stderr[len(ERROR_MARKER):].lstrip("\n")
    text = re.sub(
        r'  File "<stdin>", line \d+, in <module>\n',
        "",
        text,
        count=1,
    )
    return text.strip()


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _wasmtime_exception_details(exc: BaseException) -> str:
    """Collect diagnostic details without assuming every error is a Trap."""
    details = [
        f"exception_type={type(exc).__name__}",
        f"exception_str={str(exc)}",
        f"exception_repr={exc!r}",
    ]

    for attribute in ("message", "trap_code"):
        try:
            value = getattr(exc, attribute, None)
        except Exception as attribute_error:
            details.append(
                f"{attribute}_read_error={type(attribute_error).__name__}"
            )
            continue

        if value is not None:
            details.append(f"{attribute}={value!r}")

    try:
        frames = getattr(exc, "frames", None)
    except Exception as frames_error:
        details.append(
            f"frames_read_error={type(frames_error).__name__}"
        )
        frames = None

    if frames:
        for index, frame in enumerate(frames[:5]):
            frame_details = []

            for attribute in (
                "module_name",
                "func_name",
                "func_index",
                "module_offset",
                "func_offset",
            ):
                try:
                    value = getattr(frame, attribute, None)
                except Exception:
                    continue

                if value is not None:
                    frame_details.append(f"{attribute}={value}")

            details.append(
                f"wasm_frame_{index}="
                + ", ".join(frame_details)
            )

    return "\n".join(details)


def _timeout_message(exception_text: str) -> str | None:
    normalized = exception_text.lower()

    if (
        "wasm trap: interrupt" in normalized
        or "epoch deadline" in normalized
        or "trapcode.interrupt" in normalized
        or "all fuel consumed by webassembly" in normalized
        or "out of fuel" in normalized
        or "fuel exhausted" in normalized
        or "trapcode.out_of_fuel" in normalized
    ):
        return (
            "Execution timed out: wall-clock or instruction "
            "fuel limit exceeded."
        )

    return None


def _memory_limit_failure(exception_text: str) -> bool:
    """Recognize memory-limit and verified linear-memory exhaustion failures."""
    normalized = exception_text.lower()

    reliable_markers = (
        "forcing a memory growth failure to be a trap",
        "forcing trap when growing memory",
        "memory size limit exceeded",
        "memory limit exceeded",
    )

    if any(marker in normalized for marker in reliable_markers):
        return True

    # A MEMORY_OUT_OF_BOUNDS trap alone can also indicate an interpreter bug.
    # Require the memory-fault address and out-of-bounds diagnostic as
    # additional context before classifying it as memory exhaustion.
    if (
        "trapcode.memory_out_of_bounds" in normalized
        and "memory fault at wasm address" in normalized
        and "out of bounds memory access" in normalized
    ):
        return True

    return False


def _start_ticker(
    engine: Engine,
    stop_event: threading.Event,
    tick_lock: threading.Lock,
) -> threading.Thread:
    """Advance the shared Engine epoch approximately every 5 milliseconds."""

    def ticker() -> None:
        while not stop_event.is_set():
            time.sleep(TICK_INTERVAL_SECONDS)

            if stop_event.is_set():
                break

            with tick_lock:
                engine.increment_epoch()

    thread = threading.Thread(
        target=ticker,
        name="wasmbox-epoch-ticker",
        daemon=True,
    )
    thread.start()
    return thread


def _get_runtime() -> _Runtime:
    """Lazily initialize one Engine, compiled Module and epoch ticker."""
    global _RUNTIME

    if _RUNTIME is not None:
        return _RUNTIME

    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            return _RUNTIME

        config = Config()
        config.consume_fuel = True
        config.epoch_interruption = True
        config.wasm_exceptions = True
        config.max_wasm_stack = 512 * 1024

        engine = Engine(config)
        module = Module.from_file(engine, str(INTERPRETER_PATH))

        # Reuse the package's existing host-call import implementation.
        # No host functions are exposed to guest scripts.
        define_host_call = run.__globals__.get("_define_host_call")

        if not callable(define_host_call):
            raise RuntimeError(
                "Installed micropython-wasm package does not expose "
                "the expected host-call registration helper."
            )

        tick_lock = threading.Lock()
        stop_event = threading.Event()

        ticker_thread = _start_ticker(
            engine,
            stop_event,
            tick_lock,
        )

        _RUNTIME = _Runtime(
            engine=engine,
            module=module,
            define_host_call=define_host_call,
            tick_lock=tick_lock,
            stop_event=stop_event,
            ticker_thread=ticker_thread,
        )

        return _RUNTIME


def _measure_memory(
    runtime: _Runtime,
    instance: Any,
    store: Store,
) -> int:
    """Return current exported guest linear memory in bytes, not peak memory."""
    total_bytes = 0
    exports = instance.exports(store)

    for export in runtime.module.exports:
        if isinstance(export.type, MemoryType):
            memory = exports[export.name]

            if isinstance(memory, Memory):
                total_bytes += memory.size(store) * WASM_PAGE_BYTES

    return total_bytes


def _run_once(
    runtime: _Runtime,
    code: str,
    *,
    memory_bytes: int,
    fuel: int,
    wall_timeout_seconds: float | None,
) -> PluginResult:
    engine = runtime.engine
    module = runtime.module

    store = Store(engine)
    store.set_limits(
        memory_size=memory_bytes,
        instances=1,
        memories=1,
        tables=8,
        table_elements=10000,
    )
    store.set_fuel(fuel)

    stdout_parts: list[bytes] = []
    stderr_parts: list[bytes] = []

    def capture_stdout(data: bytes) -> None:
        stdout_parts.append(bytes(data))

    def capture_stderr(data: bytes) -> None:
        stderr_parts.append(bytes(data))

    wasi = WasiConfig()
    wasi.argv = [
        "micropython",
        "-X",
        f"heapsize={MICROPYTHON_HEAP_SIZE}",
        "-c",
        code,
    ]
    wasi.env = []
    wasi.stdout_custom = capture_stdout
    wasi.stderr_custom = capture_stderr
    store.set_wasi(wasi)

    linker = Linker(engine)
    linker.define_wasi()

    # No filesystem preopens and no network or application host functions.
    runtime.define_host_call(
        linker,
        store,
        {},
        HOST_RESULT_BYTES,
        Func,
        FuncType,
        ValType,
    )

    if wall_timeout_seconds is not None:
        deadline_ticks = max(
            1,
            math.ceil(wall_timeout_seconds / TICK_INTERVAL_SECONDS),
        )

        # Synchronize deadline configuration with epoch increments.
        # Set it BEFORE instantiation because instantiation executes WASM.
        with runtime.tick_lock:
            store.set_epoch_deadline(deadline_ticks)

    started_at = time.perf_counter()
    instance = None
    runtime_error: str | None = None
    memory_exceeded = False

    try:
        instance = linker.instantiate(store, module)
        start_function = instance.exports(store).get("_start")

        if start_function is None or not isinstance(start_function, Func):
            raise RuntimeError("WASI module does not export a callable _start")

        start_function(store)

    except ExitTrap as exc:
        exit_code = getattr(exc, "code", 0)

        if exit_code == MEMORY_ERROR_EXIT_CODE:
            memory_exceeded = True
        elif exit_code not in (0, None):
            runtime_error = f"guest exited with code {exit_code}"

    except (Trap, WasmtimeError) as exc:
        runtime_error = _wasmtime_exception_details(exc)

    except Exception as exc:
        runtime_error = (
            f"exception_type={type(exc).__name__}\n"
            f"exception_str={exc}\n"
            f"exception_repr={exc!r}"
        )

    exec_ms = _elapsed_ms(started_at)

    mem_bytes = 0
    if instance is not None:
        try:
            mem_bytes = _measure_memory(runtime, instance, store)
        except Exception:
            # Do not turn an otherwise completed execution into a failure
            # merely because memory introspection was unavailable.
            mem_bytes = 0

    stdout = b"".join(stdout_parts).decode("utf-8", "replace")
    stderr = b"".join(stderr_parts).decode("utf-8", "replace")

    if memory_exceeded:
        return PluginResult(
            "memory_exceeded",
            stdout,
            "Execution stopped: MicroPython heap limit exceeded.",
            exec_ms,
            mem_bytes,
        )

    if runtime_error is not None:
        timeout_stderr = _timeout_message(runtime_error)

        if timeout_stderr:
            return PluginResult(
                "timeout", stdout, timeout_stderr, exec_ms, mem_bytes
            )

        if _memory_limit_failure(runtime_error):
            return PluginResult(
                "memory_exceeded",
                stdout,
                "Execution stopped: sandbox memory limit exceeded.",
                exec_ms,
                mem_bytes,
            )

        diagnostic_message = " | ".join(
            line.strip()
            for line in runtime_error.strip().splitlines()
            if line.strip()
        )
        diagnostic_message = diagnostic_message[:2000]

        return PluginResult(
            "error",
            stdout,
            f"Execution failed: {diagnostic_message}",
            exec_ms,
            mem_bytes,
        )

    if stderr.startswith(ERROR_MARKER):
        return PluginResult(
            "error",
            stdout,
            _clean_error(stderr),
            exec_ms,
            mem_bytes,
        )

    return PluginResult("ok", stdout, stderr, exec_ms, mem_bytes)


def run_plugin(
    artifact: bytes | Any,
    *,
    memory_bytes: int = DEFAULT_MEMORY_BYTES,
    fuel: int = DEFAULT_FUEL,
    wall_timeout_seconds: float | None = DEFAULT_WALL_TIMEOUT_SECONDS,
) -> PluginResult:
    """Execute a packaged script with fresh per-run Store and Instance.

    Engine and compiled Module initialization is shared and excluded from
    exec_ms. mem_bytes is current guest linear memory, not peak memory.
    """
    if hasattr(artifact, "wasm_bytes"):
        artifact_bytes = artifact.wasm_bytes
    else:
        artifact_bytes = artifact

    try:
        script = extract_script(artifact_bytes)
    except ArtifactError as exc:
        return PluginResult(
            "error",
            "",
            f"Invalid plugin artifact: {exc}",
        )

    if not isinstance(memory_bytes, int) or memory_bytes <= 0:
        return PluginResult("error", "", "Invalid memory limit.")

    if not isinstance(fuel, int) or fuel <= 0:
        return PluginResult("error", "", "Invalid instruction fuel limit.")

    if (
        wall_timeout_seconds is not None
        and wall_timeout_seconds <= 0
    ):
        return PluginResult("error", "", "Invalid wall-clock timeout.")

    try:
        runtime = _get_runtime()
    except Exception as exc:
        first_line = str(exc).strip().splitlines()
        message = first_line[0][:200] if first_line else type(exc).__name__
        return PluginResult(
            "error",
            "",
            f"Runner initialization failed: {message}",
        )

    # Serialize Wasmtime operations within this Python process.
    # Protects host-call registration, execution, and cleanup.
    with _RUNNER_LOCK:
        return _run_once(
            runtime,
            _wrap(script),
            memory_bytes=memory_bytes,
            fuel=fuel,
            wall_timeout_seconds=wall_timeout_seconds,
        )
