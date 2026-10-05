import sys
from pathlib import Path

# Make "app" importable when running this script from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime.wasm_host import run_wasm_file

if len(sys.argv) != 2:
    print("Usage: python backend/scripts/run_wasm.py <file.wat or file.wasm>")
    sys.exit(1)

print(run_wasm_file(sys.argv[1]), end="")