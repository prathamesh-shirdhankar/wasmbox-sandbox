# WasmBox Pipeline

**Status:** Week 2 design. Sections marked *(planned)* describe code that is not merged yet. The repository is the source of truth.

## 1. Overview

```text
Browser (React + Monaco)
    |  POST /run  {"code": "..."}
    v
FastAPI: validate input
    v
package_plugin(code)   -> plugin artifact (.wasm bytes)
    v
run_plugin(artifact)   -> status, stdout, stderr
    v
JSON response with five fields
```

In Week 2, `/run` may still use a fake runner until the real runner is merged.

## 2. The interpreter artifact

| Item | Value |
|---|---|
| File | `backend/app/runtime/artifacts/micropython-wasi.wasm` |
| Source package | `micropython-wasm` 0.1a2 (upstream: https://github.com/simonw/micropython-wasm) |
| Licence | Apache-2.0 (`LICENSE` beside the artifact) |
| Size | 370,907 bytes |
| SHA-256 | `1c054a4d21d4a6589bc568821ebf562889988ddaaf8a17a2e2985a56cf228051` |

`backend/tests/test_interpreter_artifact.py` checks the hash. If it fails, the file changed. Find out why before updating the hash.

The artifact is a prebuilt MicroPython interpreter compiled to WASI. We did not build it ourselves.

## 3. `package_plugin(code)` *(planned, Vineet)*

Input: the user's Python source as a string. Output: the bytes of a valid `.wasm` file that carries the script.

Rules:
1. Reject empty or whitespace-only code, and code longer than 10,000 characters, before packaging.
2. Start from the base interpreter binary.
3. Append the source as a custom section.
4. Identify the artifact by `script_sha256`, the SHA-256 of the source text.
5. The same source must produce identical bytes. Different source must produce a different hash.

## 4. Custom-section format *(planned; confirm the section name against the packaging PR)*

A WebAssembly file is an 8-byte header followed by sections. A **custom section** can be added at the end and is ignored by the engine when it runs the module. Its layout:

| Part | Meaning |
|---|---|
| `0x00` | Section id for "custom" |
| size | Length of the rest, as a LEB128 number |
| name length + name | The section name as UTF-8 text (name: to be agreed) |
| payload | The user's script, UTF-8 |

**Extraction:** read the 8-byte header, then walk the sections one by one (id, size, skip) until a custom section with our name is found. Return its payload as the script.

## 5. `run_plugin(artifact)` *(planned, Prathamesh)*

1. Extract the embedded script from the artifact.
2. Run it with the MicroPython WASI interpreter through the `micropython-wasm` package, using the repository-managed artifact.
3. No directories and no network are granted.
4. Return `status`, `stdout`, `stderr`.
5. Success gives `ok`. Handled failures, including package exceptions, give `error` with readable text.

**Known limitation:** in `micropython-wasm` 0.1a2, `run()` raises an error containing only the exit code when the script fails. The traceback text is not included. The runner must handle this. See `docs/SPIKES.md`.

## 6. Response contract

Every `/run` response contains all five fields:

```json
{
  "status": "ok",
  "stdout": "hi\n",
  "stderr": "",
  "exec_ms": 0,
  "mem_bytes": 0
}
```

In Week 2, `status` is `ok` or `error`. `exec_ms` and `mem_bytes` are always `0`. Real measurements, the 50 ms timeout and the memory cap are Week 3 work.

## 7. Input rules

| Input | Result |
|---|---|
| Empty or whitespace-only code | `status: "error"`, `stderr: "No code provided"` |
| More than 10,000 characters | `status: "error"` with a size-limit message, returned before packaging |

## 8. Bundling is not compiling

This pipeline **bundles** the script. It does not **compile** it.

- The interpreter is a real WASM program.
- The user's script is stored in it as data.
- At run time, the interpreter reads the script and executes it.
- The Python source is never turned into WASM instructions.

If the mentor requires a self-contained compiled binary for every plugin, that needs a separate investigation. It is not covered here. *(Open question: mentor confirmation.)*

## 9. Limits and security notes

- Week 2 proves that the pipeline works. It is not a security approval.
- The package supports memory, fuel and wall-time limits. Their defaults and effect for WasmBox are tested in Week 3.
- In an isolated test, a benign infinite loop was stopped by the wall timeout only when fuel was set very high. With default fuel, fuel ran out first.
- Never run the attack plugins in `plugins/malicious/` through `/run` during Week 2.