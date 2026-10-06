from pathlib import Path

import extism


@extism.host_fn(name="log", namespace="app")
def log(value: int):
    print(f"HOST RECEIVED: {value}")


wasm_path = Path(__file__).with_name("extism_python_host_demo.wasm")
wasm = wasm_path.read_bytes()

print(f"WASM loaded: {len(wasm)} bytes")
print("Creating Extism plugin...")

plugin = extism.Plugin(wasm, functions=[log])

print("Calling WASM...")
plugin.call("run", b"")

print("Completed.")