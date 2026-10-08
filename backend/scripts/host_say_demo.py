from pathlib import Path

from wasmtime import Func, FuncType, Instance, Module, Store, ValType


def say(caller, ptr, length):
    memory = caller.get("memory")
    data = memory.read(caller, ptr, ptr + length)
    print("host received:", bytes(data).decode("utf-8"))


store = Store()
module = Module(store.engine, Path("plugins/benign/host_say.wat").read_text())

ty = FuncType([ValType.i32(), ValType.i32()], [])
say_fn = Func(store, ty, say, access_caller=True)
instance = Instance(store, module, [say_fn])
instance.exports(store)["run"](store)