"""Inspect micropython-wasi.wasm imports and exports."""
import os
import micropython_wasm
from wasmtime import Config, Engine, Module

wasm_file = os.path.join(
    os.path.dirname(micropython_wasm.__file__), "artifacts", "micropython-wasi.wasm"
)

cfg = Config()
cfg.wasm_exceptions = True
engine = Engine(cfg)
mod = Module.from_file(engine, wasm_file)


def fmt_functype(t):
    p = " ".join(str(v) for v in t.params)
    r = " ".join(str(v) for v in t.results)
    parts = []
    if p:
        parts.append(f"(param {p})")
    if r:
        parts.append(f"(result {r})")
    return "(func " + " ".join(parts) + ")" if parts else "(func)"


print("=== IMPORTS ===")
for imp in mod.imports:
    t = imp.type
    ts = fmt_functype(t) if hasattr(t, "params") else repr(t)
    print(f"  [{imp.module}]::{imp.name}  {ts}")

print()
print("=== EXPORTS ===")
for exp in mod.exports:
    t = exp.type
    ts = fmt_functype(t) if hasattr(t, "params") else repr(t)
    print(f"  {exp.name}  {ts}")
