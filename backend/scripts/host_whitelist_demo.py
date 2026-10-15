
import sys
from pathlib import Path

from wasmtime import FuncType, Linker, Module, Store, ValType, WasmtimeError


ROOT = Path(__file__).resolve().parents[2]
EVIL_WAT = ROOT / "plugins" / "benign" / "host_evil.wat"
ALLOWED_WAT = ROOT / "plugins" / "benign" / "host_log.wat"


def host_log(value):
    print("host received:", value)


def make_linker(store):
    linker = Linker(store.engine)
    linker.define_func(
        "host",
        "log",
        FuncType([ValType.i32()], []),
        host_log,
    )
    return linker


def main():
    store = Store()

    # Positive control: the registered host.log import should work.
    print("Positive control: testing registered host.log")
    allowed_module = Module(
        store.engine,
        ALLOWED_WAT.read_text(encoding="utf-8"),
    )
    allowed_linker = make_linker(store)

    try:
        allowed_linker.instantiate(store, allowed_module)
    except WasmtimeError as err:
        print("FAIL: registered host.log was rejected:", err)
        return 1

    print("PASS: registered host.log was accepted")

    # Negative control: host.delete_everything is not registered.
    print("Negative control: testing unregistered host.delete_everything")
    evil_module = Module(
        store.engine,
        EVIL_WAT.read_text(encoding="utf-8"),
    )
    evil_linker = make_linker(store)

    try:
        evil_linker.instantiate(store, evil_module)
    except WasmtimeError as err:
        message = str(err)
        if "delete_everything" not in message:
            print("FAIL: unexpected Wasmtime error:", message)
            return 1

        print("PASS: unregistered import was rejected:", message)
        return 0

    print("FAIL: module imported host.delete_everything successfully")
    return 1


if __name__ == "__main__":
    sys.exit(main())
