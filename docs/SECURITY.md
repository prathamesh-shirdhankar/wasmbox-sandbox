# Security

How the sandbox protects the server, and the evidence that it works.

## How WASI limits access

### What is WASI, and why does it protect us?

A WebAssembly (WASM) module runs within a constrained runtime. It cannot use host capabilities unless the runtime exposes them. WASI (WebAssembly System Interface) defines standard host interactions such as writing bytes to stdout (`fd_write`) or opening a file (`path_open`).

A request for a capability is not itself permission to use it. The host/runtime decides which capabilities are available. A module can access a directory only when the runtime explicitly grants access to it.

The current execution path is `backend/app/runtime/micropython_runner.py`. Its call to `micropython_wasm.run` does not pass `readonly_dir` or `host_functions`. The tests below record the observed outcomes for two audit plugins. These checks are evidence for these specific attempts, not proof against every possible file or network attack.

Execution timing and resource limits are separate protections. The API reports measured `exec_ms` using a monotonic timer around `micropython_wasm.run()`. This includes engine/module startup and guest execution, but excludes artifact packaging and script extraction. `mem_bytes` remains `0` as a placeholder because actual guest memory usage is not measured. See `docs/SPIKES.md` for the timing measurements and their limitations.

## Audit log

### Historical audit

**Audit date:** 2026-10-28

**Test path:** Local FastAPI `TestClient` submitting plugin source to `POST /run`.

**Tested backend revision:** `db0e0f4`

| Date | Tested revision | Plugin | Attempt | HTTP response | `status` | `stdout` | Exact exception message | Outcome |
|---|---|---|---|---:|---|---|---|---|
| 2026-10-28 | `db0e0f4` | `read_passwd.py` | Read `/etc/passwd` | 200 | `error` | Empty | `OSError: [Errno 44] ENOENT` | Pass: no `root:` content was returned; file open failed. |
| 2026-10-28 | `db0e0f4` | `open_socket.py` | Import `socket` and connect to `1.1.1.1:80` | 200 | `error` | Empty | `ImportError: no module named 'socket'` | Pass: the socket module could not be imported and `connected` was not printed. |

The exact stderr values recorded during the historical audit were:

`read_passwd.py`:

```text
Traceback (most recent call last):
  File "<string>", line 4, in <module>
OSError: [Errno 44] ENOENT
```

`open_socket.py`:

```text
Traceback (most recent call last):
  File "<string>", line 4, in <module>
ImportError: no module named 'socket'
```

Both historical execution outcomes were `error`, not `denied`. The HTTP endpoint returned `200` because the execution outcome is represented in the response body.

### Current recheck

**Audit date:** 2026-10-28

**Tested backend revision:** `be0a9c9`

**Test path:** Local FastAPI `TestClient` submitting plugin source to `POST /run`. Both scripts were executed through the WasmBox sandbox, not directly by CPython on the host.

| Date | Tested revision | Plugin | Attempt | HTTP response | `status` | `stdout` | Exact exception message | `exec_ms` | `mem_bytes` | Outcome |
|---|---|---|---|---:|---|---|---|---:|---:|---|
| 2026-10-28 | `be0a9c9` | `read_passwd.py` | Read `/etc/passwd` | 200 | `error` | Empty | `OSError: [Errno 44] ENOENT` | 241.73 | 0 | Pass: no host file content was disclosed. |
| 2026-10-28 | `be0a9c9` | `open_socket.py` | Import `socket` and connect to `1.1.1.1:80` | 200 | `error` | Empty | `ImportError: no module named 'socket'` | 285.13 | 0 | Pass: socket import failed and `connected` was not printed. |

The exact stderr values captured during the current recheck were:

`read_passwd.py`:

```text
Traceback (most recent call last):
  File "<string>", line 4, in <module>
OSError: [Errno 44] ENOENT
```

`open_socket.py`:

```text
Traceback (most recent call last):
  File "<string>", line 4, in <module>
ImportError: no module named 'socket'
```

The current recheck returned `status: error` for both plugins, rather than `denied`. The HTTP status was `200` for both requests. The measured `exec_ms` values include engine/module startup and guest execution; they are not the total HTTP request duration. `mem_bytes: 0` is a placeholder, not a measurement.

### Security test results

On revision `be0a9c9`, the following targeted test command passed:

```powershell
python -m pytest tests/test_security_audit.py tests/test_security_plugins.py -q
```

Observed result:

- 10 passed
- 2 skipped
- 0 failed

The two skipped tests concern the 50 ms timeout target and memory-bomb testing. A Starlette deprecation warning was also reported; it did not cause test failure.

## What this audit does not prove

- It tests two specific attack scripts only. It does not prove that every possible host-file or network attack is blocked.
- The file-reading test demonstrates that the tested `/etc/passwd` attempt failed and did not disclose `root:` content.
- The network test demonstrates that the tested script could not import `socket` and did not print `connected`. It does not prove that every possible network-access path is blocked.
- The 50 ms timeout target remains unmet because engine/module startup alone can exceed that budget.
- The memory-bomb test remains skipped because measured memory enforcement has not been established. The memory-bomb test was intentionally not run during the documented audit.
- `mem_bytes` remains `0`; actual guest memory usage is **not measured**.
- `exec_ms` is measured around `micropython_wasm.run()`. It includes engine/module startup and guest execution but excludes artifact packaging and script extraction. See `docs/SPIKES.md` for five successful API timing measurements.
- The recorded results apply to the specific revisions, scripts, and test conditions listed above. They should not be treated as a complete security certification.
