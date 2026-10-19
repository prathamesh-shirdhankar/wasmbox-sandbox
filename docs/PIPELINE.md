# WasmBox Pipeline

**Scope:** This document describes the current `/run` execution path after the runtime-limits change is merged. The repository source and tests remain authoritative; the security observations below cover the specific attempts tested, not every possible attack.

## 1. Overview

```text
Browser (React)
    | POST /run  {"code": "..."}
    v
FastAPI: validate request and code length
    v
package_plugin(code)
    | append UTF-8 source as a WebAssembly custom section named `wasmbox_script`
    v
run_plugin(artifact)
    | extract script from `wasmbox_script`
    | run repository-managed MicroPython WASI interpreter
    v
JSON response: status, stdout, stderr, exec_ms, mem_bytes
```

The browser sends Python source to `POST http://localhost:8000/run`. The API validates the input, packages the source with the repository-managed interpreter artifact, runs the packaged artifact, and returns the five response fields. A request missing the `code` field is rejected by request validation with HTTP 422 and a different response shape; it does not return the normal five-field body.

## 2. Interpreter artifact

| Item | Value |
|---|---|
| File | `backend/app/runtime/artifacts/micropython-wasi.wasm` |
| Source package | `micropython-wasm` 0.1a2 (upstream: <https://github.com/simonw/micropython-wasm>) |
| Licence | Apache-2.0 (`LICENSE` beside the artifact) |
| Size | 370,907 bytes |
| SHA-256 | `1c054a4d21d4a6589bc568821ebf562889988ddaaf8a17a2e2985a56cf228051` |

`backend/tests/test_interpreter_artifact.py` checks the artifact hash. If the test fails, investigate why the artifact changed before updating the expected hash. The interpreter is a prebuilt MicroPython program compiled to WASI; WasmBox does not compile a separate WASM binary from each user's Python script.

## 3. Packaging: `package_plugin(code)`

Implemented in `backend/app/runtime/packaging.py`.

The function accepts Python source and returns a `PluginArtifact` containing the packaged WASM bytes, source text, custom-section name, and `script_sha256` (SHA-256 of the UTF-8 source text).

The function:

1. Rejects empty or whitespace-only source.
2. Rejects source longer than 10,000 characters.
3. Reads the repository-managed base interpreter artifact and checks its WASM header.
4. Encodes the source as UTF-8 and appends it in a WebAssembly custom section named `wasmbox_script`.
5. Returns the packaged artifact and source hash.

Packaging is deterministic for a fixed base artifact and source because it appends the same custom-section bytes for the same source.

## 4. Custom-section format and extraction

The custom-section name is `wasmbox_script` (constant `CUSTOM_SECTION_NAME` in `packaging.py`; `SECTION_NAME` in `micropython_runner.py`). The custom section is WebAssembly section id `0` and has this layout:

| Part | Meaning |
|---|---|
| Section id `0x00` | Custom section |
| LEB128 size | Byte length of the section payload |
| LEB128 name length + name | UTF-8 section name `wasmbox_script` |
| Remaining payload | The user's Python source encoded as UTF-8 |

`extract_script()` checks the WASM header, walks the sections, finds the custom section with the agreed name, and decodes the payload as UTF-8. It reports malformed, truncated, missing-section, or invalid UTF-8 artifacts as artifact errors.

*Note on LEB128 Encoding (19 October 2026)*: The packaging utility uses standard unsigned LEB128 (`u32`) encoding. Each byte contributes 7 bits of value; the 8th bit (MSB `0x80`) indicates continuation. This ensures variable-length payload sizes are strictly compliant with the official WebAssembly binary specification.

## 5. Execution: `run_plugin(artifact)`

Implemented in `backend/app/runtime/micropython_runner.py`.

1. Accepts the packaged artifact (or an object exposing `wasm_bytes`).
2. Extracts the source from `wasmbox_script`.
3. Runs the source through `micropython_wasm.run()` using the repository-managed `micropython-wasi.wasm` interpreter.
4. Does not provide a `readonly_dir` or `host_functions` to the runner.
5. Captures ordinary Python exceptions via a wrapper so their traceback can be returned as readable stderr; the wrapper is not itself a security boundary.
6. Returns `status`, `stdout`, `stderr`, and elapsed runner time. The API adds `mem_bytes`, which remains an unmeasured placeholder.

The runner uses `ok` for successful execution, `error` for ordinary Python/artifact/other failures, and `timeout` when the wall-clock limit interrupts execution or WebAssembly fuel is exhausted. Observed trap texts from `micropython-wasm` 0.1a2 were:

- Wall-clock interruption: `guest trapped: wasm trap: interrupt`
- Fuel exhaustion: `guest trapped: wasm trap: all fuel consumed by WebAssembly`

The runner converts those resource-limit failures to a readable timeout response. Ordinary errors such as `1/0` remain `error`.

Known wrapper limitations: `sys.exit()` is reported as an error, and script output can spoof the wrapper's stderr marker. The wrapper improves error readability; it is not a security boundary.

## 6. Runtime limits and execution timing

The runtime-limits implementation configures these defaults:

| Setting | Default | Meaning |
|---|---:|---|
| Guest memory ceiling | 10 MiB | Memory allowed to the guest runtime; this is not a measurement of actual usage |
| WebAssembly fuel | 20,000,000 | Instruction-fuel budget |
| Wall-clock timeout | 1.0 second | Maximum time allowed for the interpreter call |

Tests may pass smaller limits to `run_plugin()` without changing these defaults. The `print("hi")` diagnostic completed with a 10 MiB memory setting; that startup test does not prove memory behavior for every script.

`exec_ms` is measured using a monotonic timer around the `micropython_wasm.run()` call. It includes interpreter/module startup and guest execution, but excludes request validation, source packaging, and custom-section extraction. Validation failures that do not execute the guest return `exec_ms: 0`.

Five successful `POST /run` requests for `print("hi")` on one development machine produced these results:

| Run | `exec_ms` |
|---:|---:|
| 1 | 242.43 |
| 2 | 284.23 |
| 3 | 197.51 |
| 4 | 207.61 |
| 5 | 198.75 |
| Median | 207.61 |
| Minimum | 197.51 |
| Maximum | 284.23 |

These five runs are a small measurement on one machine, not a general benchmark. A 50 ms timeout did not allow a benign run to complete because interpreter startup alone is slower than that target. The configured default is 1 second.

`mem_bytes` remains `0` as a placeholder. **Memory usage is not measured**, so the UI and documentation must not describe it as zero bytes of actual usage.

## 7. API response and input rules

A normal `/run` response contains all five fields:

```json
{
  "status": "ok",
  "stdout": "hi\n",
  "stderr": "",
  "exec_ms": 210,
  "mem_bytes": 0
}
```

| Field | Meaning |
|---|---|
| `status` | `ok`, `error`, or `timeout` |
| `stdout` | Captured standard output |
| `stderr` | Captured error text; empty when there is no reported error |
| `exec_ms` | Measured time for the runner call, in milliseconds; includes interpreter startup |
| `mem_bytes` | Placeholder `0`; actual memory usage is not measured |

| Input | Result |
|---|---|
| Empty or whitespace-only source | HTTP 200 with `status: error`, empty stdout, and `stderr: "No code provided"` |
| More than 10,000 characters | HTTP 200 with `status: error` and a code-size message; packaging is not run |
| Missing `code` field | HTTP 422 validation response with a different shape, not the normal five fields |
| Backend is unavailable to the browser | Fetch fails; the frontend should show a friendly “Cannot reach the server” message |

## 8. Bundling is not compiling

This pipeline **bundles** the script; it does not compile the user's Python into WASM instructions.

- The interpreter is a real WebAssembly/WASI program.
- The user's Python source is stored as data in a custom section.
- At runtime, the MicroPython interpreter extracts and executes that source.
- The source itself is not transformed into a separate WASM program.

A requirement for a separately compiled, self-contained WASM binary for every plugin would need a separate investigation; it is not what this pipeline currently does.

## 9. Security observations and limits

The runner uses the repository-managed interpreter and does not supply a `readonly_dir` or `host_functions` to `micropython_wasm.run()`.

In the tested audit cases:

- `plugins/malicious/read_passwd.py` returned `status: error`, empty stdout, and `OSError: [Errno 44] ENOENT`.
- `plugins/malicious/open_socket.py` returned `status: error`, empty stdout, and `ImportError: no module named 'socket'`.

These results show that these specific attempts failed in the tested environment. They do not prove that every conceivable filesystem or network attack is blocked, and the observed status is `error`, not `denied`. See `docs/SECURITY.md` for the audit record and its scope.

The limits and tests provide a basic runtime resource boundary, not a complete security approval. The memory-bomb plugin was intentionally not run. Actual memory use is not measured; the 50 ms target is not met. Preserve these limitations in the demo and project documentation.
