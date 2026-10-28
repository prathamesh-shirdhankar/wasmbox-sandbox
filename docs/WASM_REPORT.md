# WasmBox: WebAssembly Design Report

**Date:** 28 October 2026
**Scope:** Architecture, isolation approach, runtime limits, trade-offs, and current evidence.
**Status note:** The runtime-limits and security-audit changes described here have been tested locally and are in pull requests for review; verify their merge status before treating them as part of `main`.

## 1. What WebAssembly and WASI provide

WebAssembly (Wasm) is a portable bytecode format executed by a WebAssembly runtime. Its execution model provides a sandbox boundary: a module cannot directly access arbitrary host resources through ordinary Wasm instructions. Access to external functions and resources depends on interfaces supplied by the embedding runtime. The WebAssembly security overview emphasizes that the embedding environment's policies are part of the effective security model ([WebAssembly security](https://webassembly.org/docs/security/)).

WASI is a system-interface family for WebAssembly programs. Its capability-oriented design makes external access something the runtime explicitly provides instead of assuming unrestricted ambient authority. The general principle is that a guest can use only the capabilities made available through its interfaces ([WASI design principles](https://github.com/WebAssembly/WASI/blob/main/docs/DesignPrinciples.md), [WASI capabilities](https://github.com/WebAssembly/WASI/blob/main/docs/Capabilities.md)). This does not automatically make every Wasm application secure: host configuration, imported functions, mounted directories, resource limits, and the guest program all matter.

WasmBox packages user-written Python as data and executes it using a repository-managed, prebuilt MicroPython WASI interpreter. The user's Python source is stored in a custom section named `wasmbox_script`; the project does **not** compile each submitted Python script into its own WebAssembly module. The request passes through FastAPI input validation, packaging, custom-section extraction, and the interpreter runner.

## 2. Security and capability decisions

The runner uses the repository-managed interpreter artifact and does not pass a `readonly_dir` or `host_functions` argument to `micropython_wasm.run()`. This is intended to avoid granting user scripts extra host directories or custom host functions. File and network access should not be described as universally blocked based on configuration alone; the effective behavior must be tested against the installed runtime and its defaults.

The local audit submitted two representative scripts through the real `/run` API:

| Test | Observed result | What this supports |
|---|---|---|
| Read `/etc/passwd` | HTTP 200, `status: error`, empty `stdout`; stderr contained `OSError: [Errno 44] ENOENT` | This attempted read did not expose file contents in the tested environment. |
| Import `socket` and connect | HTTP 200, `status: error`, empty `stdout`; stderr contained `ImportError: no module named 'socket'` | The tested MicroPython environment could not import `socket`, so this attempt did not report a successful connection. |

These results are evidence for these two attempts, not a complete penetration test or proof that every form of filesystem or network access is impossible. The API returned `status: error`, not `denied`, so the audit records the actual status rather than claiming a dedicated denial status.

## 3. Fuel, wall-clock timeout, and memory

WasmBox configures explicit limits in the runtime runner:

- **Fuel:** 20,000,000 units by default. Fuel is a deterministic budget for instrumented Wasm execution. When exhausted, Wasmtime traps; it is not a count of Python source lines.
- **Wall-clock timeout:** 1.0 second by default. This provides a time-based stop. In this integration, the measured runner call includes engine/module startup as well as guest execution.
- **Guest memory ceiling:** 10 MiB. A benign `print("hi")` diagnostic completed with this setting. That startup check does not prove that every script's memory needs fit within the limit.
- **Reported memory use:** `mem_bytes` remains `0` as an API placeholder. Actual per-run memory consumption is **not measured**; clients and documentation must not present zero as a measured memory result.

Fuel and time are complementary. Fuel helps bound the amount of Wasm work and is deterministic for a given execution configuration. A wall-clock timeout reflects elapsed time and includes overhead such as runtime/module startup in this integration. Wasmtime documents fuel-based and epoch/time-based interruption as different mechanisms with different determinism and overhead properties ([Wasmtime: interrupting Wasm execution](https://docs.wasmtime.dev/examples-interrupting-wasm.html)).

The installed `micropython-wasm` 0.1a2 package produced these observed trap messages:

- Wall-clock interruption: `guest trapped: wasm trap: interrupt`
- Fuel exhaustion: `guest trapped: wasm trap: all fuel consumed by WebAssembly`

The runner maps these resource-limit failures to `status: timeout` with readable messages. Ordinary Python errors, such as division by zero or syntax errors, should remain `status: error`.

## 4. Timing evidence and the 50 ms target

Five successful `POST /run` requests ran `print("hi")` on one Windows development machine. The returned `exec_ms` values were 242.43, 284.23, 197.51, 207.61, and 198.75 ms. The median was **207.61 ms**, with a minimum of **197.51 ms** and maximum of **284.23 ms**.

`exec_ms` is measured using a monotonic timer around `micropython_wasm.run()`. It includes engine/module startup and guest execution, but excludes packaging and custom-section extraction that occur before the timer starts. The 50 ms probe did not allow even a benign `print("hi")` request to complete, so the 50 ms target is **not met** by this runner configuration. These five samples describe one machine and are not a general benchmark.

## 5. What Wizer is—and is not in WasmBox

[Wizer](https://github.com/bytecodealliance/wizer) is a WebAssembly pre-initializer. It runs a module's initialization function ahead of time and snapshots the initialized state into a new Wasm module, potentially reducing repeated startup work ([Wizer project documentation](https://github.com/bytecodealliance/wizer)). It is **not currently part of the WasmBox pipeline**. It is a possible future experiment if startup time becomes a priority, but using it would require checking compatibility with the bundled interpreter, initialization behavior, resource handling, and reproducibility. We should not claim a Wizer speedup without an implementation and measurements.

## 6. Why Wasm can fit serverless work

Short-lived serverless functions often benefit from portable artifacts, explicit host interfaces, and the ability to instantiate isolated workloads without building a full operating-system environment for each function. Wasm can therefore be a useful execution target for small, separately bounded tasks. These are architectural advantages, not a guarantee that every Wasm workload starts or runs faster; runtime choice, language runtime startup, host integration, workload type, and configuration affect the result. WasmBox's observed median of about 208 ms illustrates that the interpreter and host integration remain significant in this project.

## 7. WebAssembly compared with Docker containers

Wasm and Docker solve related but different deployment problems; neither is a universal replacement for the other.

| Consideration | WebAssembly in WasmBox | Docker container |
|---|---|---|
| Main unit | A Wasm module executed by a Wasm runtime | A packaged process environment with filesystem layers and user-space dependencies |
| Host access | Depends on imported interfaces and capabilities supplied by the host | Depends on container configuration, OS permissions, namespaces, mounts, network settings, and runtime policy |
| Best fit | A compact, bounded plugin or function with a narrow interface | Applications needing a fuller Linux userland, multiple processes, or existing container tooling |
| Operational trade-off | Requires compatible Wasm/WASI support; guest-language/runtime limitations still apply | Mature ecosystem and broad compatibility, but images and isolation configuration can be more involved |

This comparison is a design guide rather than a security ranking. Containers can provide strong isolation when correctly configured, and Wasm workloads can also run inside containers. CNCF discusses these technologies as complementary abstractions with different use cases ([CNCF: Components vs. Containers](https://www.cncf.io/blog/2025/04/09/components-vs-containers-fight/)).

## 8. WasmBox design decisions and remaining limits

The current design choices are:

1. Reuse a repository-managed MicroPython WASI interpreter instead of compiling every Python submission to Wasm.
2. Embed source code in the `wasmbox_script` custom section, then extract and execute that source at run time.
3. Validate empty input and enforce a maximum source length of 10,000 characters before packaging.
4. Apply explicit fuel, wall-clock, and guest-memory limits, and report timeout traps using the agreed API status.
5. Return execution time through `exec_ms`, while leaving `mem_bytes` as an explicitly unmeasured placeholder.
6. Keep host filesystem/network capabilities narrow and verify concrete behavior with API-level tests rather than claiming that the word “sandbox” alone proves safety.

Remaining limitations include the unmet 50 ms target, unmeasured memory consumption, a small number of security probes rather than an exhaustive audit, and timing measurements from a single machine. These results support a working prototype and a transparent set of limits; they do not constitute a complete security certification or production-readiness assessment.

## References

1. [WebAssembly security overview](https://webassembly.org/docs/security/)
2. [WASI design principles](https://github.com/WebAssembly/WASI/blob/main/docs/DesignPrinciples.md)
3. [WASI capability model](https://github.com/WebAssembly/WASI/blob/main/docs/Capabilities.md)
4. [Wasmtime: interrupting Wasm execution](https://docs.wasmtime.dev/examples-interrupting-wasm.html)
5. [Wizer: WebAssembly pre-initializer](https://github.com/bytecodealliance/wizer)
6. [CNCF: Components vs. Containers](https://www.cncf.io/blog/2025/04/09/components-vs-containers-fight/)
