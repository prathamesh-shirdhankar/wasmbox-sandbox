from pathlib import Path

from wasmtime import Func, FuncType, Instance, Module, Store, ValType


def host_log(x):
    print("host received:", x)


store = Store()
module = Module(store.engine, Path("plugins/benign/host_log.wat").read_text())

log = Func(store, FuncType([ValType.i32()], []), host_log)
instance = Instance(store, module, [log])
instance.exports(store)["run"](store)