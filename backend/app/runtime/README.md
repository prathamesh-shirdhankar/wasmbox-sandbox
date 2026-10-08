# Runtime

Runs `.wasm` files safely from Python. Owner: Prathamesh

- `wasm_host.py` has `run_wasm_file(path)`. It loads a `.wat` or `.wasm` module, runs its `_start` function and returns what it printed.
- The module is given **no directories and no network** on purpose. We never add a permission. That is the base of our security story.