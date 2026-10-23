import tempfile
from pathlib import Path

from wasmtime import Engine, Linker, Module, Store, WasiConfig


def run_wasm_file(path):
    """Run a WASI module's _start function and return what it printed."""
    path = Path(path)
    engine = Engine()

    if path.suffix == ".wat":
        module = Module(engine, path.read_text())
    else:
        module = Module.from_file(engine, str(path))

    linker = Linker(engine)
    linker.define_wasi()

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "stdout.txt"

        wasi = WasiConfig()
        wasi.stdout_file = str(out_path)
        # No directories and no network are granted, on purpose.

        store = Store(engine)
        store.set_wasi(wasi)

        instance = linker.instantiate(store, module)
        instance.exports(store)["_start"](store)

        del instance, store  # release the output file before reading it
        return out_path.read_text()