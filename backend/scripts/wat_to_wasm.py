import sys
from pathlib import Path

from wasmtime import wat2wasm

src = Path(sys.argv[1])
dst = src.with_suffix(".wasm")
dst.write_bytes(wat2wasm(src.read_text()))
print(f"Wrote {dst}")