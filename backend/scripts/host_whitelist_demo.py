from pathlib import Path

from wasmtime import Func, FuncType, Instance, Module, Store, ValType


def host_log(x):
    print("host received:", x)


store = Store()
module = Module(store.engine, Path("plugins/benign/host_evil.wat").read_text())

# We only supply "log". The module asked for "delete_everything".
log = Func(store, FuncType([ValType.i32()], []), host_log)

try:
    Instance(store, module, [log])
    print("UNSAFE: module started without its import being satisfied")
except Exception as err:
    print("Blocked as expected:", type(err).__name__, "-", err)