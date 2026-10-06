# Scripts

Small helper scripts you run by hand from the repo root. Owner: Prathamesh

| Script | What it does | Example |
|---|---|---|
| `run_wasm.py` | Runs a WASI module and prints what it wrote | `python backend/scripts/run_wasm.py plugins/benign/hello.wasm` |
| `wat_to_wasm.py` | Converts a `.wat` text file to a `.wasm` binary next to it | `python backend/scripts/wat_to_wasm.py plugins/benign/hello.wat` |
| `add_demo.py` | Calls an `add` function inside a tiny WASM module (prints `5`) | `python backend/scripts/add_demo.py` |

Expected output of the first example: `hello from wasm`