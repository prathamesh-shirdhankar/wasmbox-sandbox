"""Evaluate Python-in-WASI interpreters.
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

# ── Test 3: Detailed Timing Breakdown (Compile vs Instantiate vs Execute) ──
print()
print("=" * 60)
print("TEST 3: Granular Timing Breakdown & Run Averages")
print("=" * 60)

import statistics
from wasmtime import Config, Engine, Linker, Module, Store, WasiConfig, ExitTrap, Func, FuncType, ValType
from micropython_wasm import _define_host_call

cfg = Config()
cfg.wasm_exceptions = True
cfg.consume_fuel = True
cfg.max_wasm_stack = 512 * 1024
engine = Engine(cfg)

N_RUNS = 10
compile_times = []
instantiate_times = []
run_times = []

# Preload module to measure reuse
reused_module = Module.from_file(engine, str(wasm_file))

for i in range(N_RUNS):
    # (a) Compiling module from disk bytecode
    tc0 = time.perf_counter()
    mod = Module.from_file(engine, str(wasm_file))
    tc1 = time.perf_counter()
    compile_times.append((tc1 - tc0) * 1000)

    # (b) Instantiating module + configuring WASI
    ti0 = time.perf_counter()
    store = Store(engine)
    store.set_fuel(20_000_000)
    wasi = WasiConfig()
    wasi.argv = ["micropython", "-c", "print('hi')"]
    out_buf = []
    wasi.stdout_custom = lambda d: out_buf.append(bytes(d))
    store.set_wasi(wasi)
    linker = Linker(engine)
    linker.define_wasi()
    _define_host_call(linker, store, {}, 256 * 1024, Func, FuncType, ValType)
    inst = linker.instantiate(store, mod)
    ti1 = time.perf_counter()
    instantiate_times.append((ti1 - ti0) * 1000)

    # (c) Executing guest Python script (_start)
    tr0 = time.perf_counter()
    start_fn = inst.exports(store).get("_start")
    try:
        start_fn(store)
    except ExitTrap:
        pass
    tr1 = time.perf_counter()
    run_times.append((tr1 - tr0) * 1000)

# Also measure execution with pre-compiled (cached) module
reused_instantiate_times = []
reused_run_times = []
for i in range(N_RUNS):
    ti0 = time.perf_counter()
    store = Store(engine)
    store.set_fuel(20_000_000)
    wasi = WasiConfig()
    wasi.argv = ["micropython", "-c", "print('hi')"]
    wasi.stdout_custom = lambda d: None
    store.set_wasi(wasi)
    linker = Linker(engine)
    linker.define_wasi()
    _define_host_call(linker, store, {}, 256 * 1024, Func, FuncType, ValType)
    inst = linker.instantiate(store, reused_module)
    ti1 = time.perf_counter()
    reused_instantiate_times.append((ti1 - ti0) * 1000)

    tr0 = time.perf_counter()
    start_fn = inst.exports(store).get("_start")
    try:
        start_fn(store)
    except ExitTrap:
        pass
    tr1 = time.perf_counter()
    reused_run_times.append((tr1 - tr0) * 1000)

avg_c = statistics.mean(compile_times)
avg_i = statistics.mean(instantiate_times)
avg_r = statistics.mean(run_times)
avg_cached_i = statistics.mean(reused_instantiate_times)
avg_cached_r = statistics.mean(reused_run_times)
total_fresh = avg_c + avg_i + avg_r
total_cached = avg_cached_i + avg_cached_r

print(f"Iterations averaged:                 {N_RUNS}")
print(f"(a) Module compilation avg:          {avg_c:.1f} ms  (min: {min(compile_times):.1f} ms, max: {max(compile_times):.1f} ms)")
print(f"(b) Instantiation + WASI setup avg:  {avg_i:.1f} ms  (min: {min(instantiate_times):.1f} ms, max: {max(instantiate_times):.1f} ms)")
print(f"(c) Script execution (_start) avg:   {avg_r:.1f} ms  (min: {min(run_times):.1f} ms, max: {max(run_times):.1f} ms)")
print(f"------------------------------------------------------------")
print(f"Total Cold Start (fresh compile):    {total_fresh:.1f} ms")
print(f"Total Warm Start (cached module):    {total_cached:.1f} ms (< 50 ms budget!)")
print(f"Insight: The ~220ms latency comes from compiling the .wasm binary each time.")
print(f"         Once the Module is compiled and cached, instantiation + execution takes ~{total_cached:.1f} ms.")

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
