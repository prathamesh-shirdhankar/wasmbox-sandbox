
from pathlib import Path

from wasmtime import FuncType, Linker, Module, Store, ValType


def host_log(x):
    print("host received:", x)


# Create the Wasmtime environment.
store = Store()
module = Module(
    store.engine,
    Path("plugins/benign/host_evil.wat").read_text(),
)

# Create a linker that registers host functions by their names.
linker = Linker(store.engine)

# Register only the function named host.log.
# Do NOT register host.delete_everything.
linker.define_func(
    "host",
    "log",
    FuncType([ValType.i32()], []),
    host_log,
)

print("Registered authorized import: host.log")
print("Attempting to load the module requesting host.delete_everything")

try:
    linker.instantiate(store, module)
    print("UNSAFE: module started without authorization")
except Exception as err:
    print("Blocked as expected:", type(err).__name__, "-", err)
