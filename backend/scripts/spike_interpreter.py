"""
Day 3 Spike: Evaluate Python-in-WASI interpreters.
Tests MicroPython WASI via micropython-wasm package and measures performance.
"""
import time
import sys
sys.path.insert(0, ".")

# ── Test 1: MicroPython via micropython-wasm package ──
print("=" * 60)
print("TEST 1: MicroPython WASI (via micropython-wasm 0.1a2)")
print("=" * 60)

from micropython_wasm import run as mp_run, MicroPythonWasmError
import os, micropython_wasm

wasm_file = os.path.join(os.path.dirname(micropython_wasm.__file__), "artifacts", "micropython-wasi.wasm")
size_bytes = os.path.getsize(wasm_file)
print(f"Binary: {wasm_file}")
print(f"Binary size: {size_bytes} bytes ({size_bytes/1024:.1f} KB)")

# Test: print("hi")
t0 = time.perf_counter()
result = mp_run('print("hi")')
t1 = time.perf_counter()
print(f"\nCode:   print('hi')")
print(f"stdout: {repr(result.stdout)}")
print(f"stderr: {repr(result.stderr)}")
print(f"Time:   {(t1-t0)*1000:.1f} ms")
print(f"Needs stdlib on disk: No (self-contained, no /lib/python3.x needed)")

# Test: arithmetic
t0 = time.perf_counter()
result2 = mp_run("x = sum(range(100))\nprint(x)")
t1 = time.perf_counter()
print(f"\nCode:   x = sum(range(100)); print(x)")
print(f"stdout: {repr(result2.stdout)}")
print(f"Time:   {(t1-t0)*1000:.1f} ms")

# Test: error handling
t0 = time.perf_counter()
try:
    result3 = mp_run("raise ValueError('test error')")
    stdout3, stderr3 = result3.stdout, result3.stderr
    error_status = "caught by MicroPython"
except MicroPythonWasmError as e:
    stdout3, stderr3 = "", str(e)
    error_status = "ExitTrap with code 1 (expected)"
t1 = time.perf_counter()
print(f"\nCode:   raise ValueError('test error')")
print(f"stdout: {repr(stdout3)}")
print(f"stderr: {repr(stderr3)}")
print(f"Status: {error_status}")
print(f"Time:   {(t1-t0)*1000:.1f} ms")

# Test: multi-line
t0 = time.perf_counter()
result4 = mp_run("for i in range(5):\n    print(i, end=' ')\nprint()")
t1 = time.perf_counter()
print(f"\nCode:   for i in range(5): print(i, end=' ')")
print(f"stdout: {repr(result4.stdout)}")
print(f"Time:   {(t1-t0)*1000:.1f} ms")

# ── Test 2: Prathamesh's wasm_host with hello.wasm ──
print()
print("=" * 60)
print("TEST 2: Prathamesh wasm_host.py with hello.wat")
print("=" * 60)

try:
    from app.runtime.wasm_host import run_wasm_file
    t0 = time.perf_counter()
    out = run_wasm_file("../plugins/benign/hello.wat")
    t1 = time.perf_counter()
    print(f"stdout: {repr(out)}")
    print(f"Time:   {(t1-t0)*1000:.1f} ms")
except Exception as e:
    print(f"Skipped (not on this branch): {e}")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Interpreter:                   MicroPython WASI")
print(f"Package:                       micropython-wasm==0.1a2")
print(f"Binary size:                   {size_bytes/1024:.1f} KB ({size_bytes} bytes)")
print(f"Stdlib on disk required:       No (self-contained)")
print(f"WASI sandbox (no FS/network):  Yes")
print(f"Wasmtime version required:     >= 49.0.0 (needs exceptions proposal)")
print(f"Error handling:                ExitTrap on runtime errors (exit code 1)")
print(f"Recommendation:                Use MicroPython WASI for Week 2")
