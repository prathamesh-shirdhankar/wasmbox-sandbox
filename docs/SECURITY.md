# Security

How the sandbox protects the server, and the evidence that it works.

## How WASI limits access (Priya)

## What is WASI, and why does it protect us?

A WebAssembly (WASM) module runs within a constrained runtime. It cannot use host capabilities unless the runtime exposes them. WASI (WebAssembly System Interface) defines standard host interactions such as writing bytes to stdout (`fd_write`) or opening a file (`path_open`).

A request for a capability is not itself permission to use it. The host/runtime decides which capabilities are available. A module can access a directory only when the runtime explicitly grants access to it.

The current execution path is `backend/app/runtime/micropython_runner.py`. Its call to `micropython_wasm.run` does not pass `readonly_dir` or `host_functions`. The tests below record the observed outcomes for the two audit plugins. These checks are evidence for these specific attempts, not proof against every possible file or network attack.

Execution timing and resource limits are separate protections. At the time of this audit, `exec_ms` is still returned as `0` and memory usage is not measured. See `docs/SPIKES.md` for recorded startup measurements.

## Audit log

**Audit date:** 2026-10-28

**Test path:** local FastAPI `TestClient` posting the plugin source to `POST /run`
**Tested backend revision:** `db0e0f4` (capture this with `git rev-parse --short HEAD` before applying the audit-test and documentation patch; the runner code was unchanged during the tests.)

| Date | Tested revision | Plugin | Attempt | HTTP response | `status` | `stdout` | Exact exception message | Outcome |
|---|---|---|---|---:|---|---|---|---|
| 2026-10-28 | `db0e0f4` | `read_passwd.py` | Read `/etc/passwd` | 200 | `error` | Empty | `OSError: [Errno 44] ENOENT` | Pass: no `root:` content was returned; file open failed. |
| 2026-10-28 | `db0e0f4` | `open_socket.py` | Import `socket` and connect to `1.1.1.1:80` | 200 | `error` | Empty | `ImportError: no module named 'socket'` | Pass: the socket module could not be imported and `connected` was not printed. |

The exact stderr values captured from the API were:

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

Both observed outcomes were `error`, not `denied`. The HTTP endpoint itself returned `200`, because the execution outcome is represented in the response body.

### What this audit does not prove

- It tests these two attack scripts only; it does not prove every possible host-file or network attack is blocked.
- It does not test timeout enforcement or memory exhaustion. The infinite-loop test remains skipped until the timeout implementation is verified, and the memory-bomb test remains skipped because measured memory enforcement is not established.
- `mem_bytes` is a placeholder (`0`); memory usage is **not measured**.
- `exec_ms` is currently a placeholder (`0`); real API execution timing remains to be implemented.
