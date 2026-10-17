# Security

How the sandbox protects the server, and the evidence that it works.

## How WASI limits access (Priya)

## What is WASI, and why does it protect us?

A WebAssembly (WASM) module is a sealed box. On its own it can only do maths
inside its own memory. It cannot print, read a file or use the network.

To do anything outside the box it must ask the host, which is our Python
program. WASI (WebAssembly System Interface) is the standard list of those
requests, for example "write these bytes to stdout" (`fd_write`) or "open this
file" (`path_open`).

Asking is not getting. The host decides which requests it will answer. A module
can only reach a folder if the host explicitly shares ("preopens") that folder
with it.

Our runtime, `backend/app/runtime/wasm_host.py`, gives a module only a stdout
file. It never calls `preopen_dir`, so the module has no folders at all, and it
grants no network access. Our `hello.wasm` only uses `fd_write`.

So when a plugin tries to read `/etc/passwd`, there is no folder to find it in
and the request fails. The safe state is the default, and we never add a
permission.

Time and memory limits are a separate protection (Week 3).

**Not yet proven:** this is the design. It becomes evidence only after the
Mid-Project Review audits run the attack plugins and we log the results here.

## Audit log

(to be filled in from the mid-project review)