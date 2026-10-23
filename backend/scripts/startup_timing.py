"""Measure startup time of run_plugin. Benign script only."""

import cProfile
import pstats
import statistics
import sys
import time
from pathlib import Path

# Make "app" importable when running from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wasmtime import Engine, Module

from app.runtime.micropython_runner import INTERPRETER_PATH, run_plugin
from app.runtime.packaging import package_plugin

ARTIFACT = package_plugin('print("hi")').wasm_bytes
LATER_RUNS = 10


def timed(fn):
    start = time.perf_counter()
    result = fn()
    return (time.perf_counter() - start) * 1000, result


if "--profile" in sys.argv:
    # Count how many times the module is compiled across 5 runs.
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(5):
        run_plugin(ARTIFACT)
    profiler.disable()
    pstats.Stats(profiler).sort_stats("cumulative").print_stats(
        "from_file|Engine|instantiate|run_plugin"
    )
    sys.exit(0)

first_ms, first = timed(lambda: run_plugin(ARTIFACT))
print("first run_plugin ms:", round(first_ms, 1), first.status, repr(first.stdout))

later = [timed(lambda: run_plugin(ARTIFACT))[0] for _ in range(LATER_RUNS)]
print(
    f"next {LATER_RUNS} run_plugin ms: "
    f"min {min(later):.1f}  median {statistics.median(later):.1f}  max {max(later):.1f}"
)


def compile_once():
    return Module.from_file(Engine(), str(INTERPRETER_PATH))


compile_ms = [timed(compile_once)[0] for _ in range(3)]
print("compile interpreter alone ms:", [round(x, 1) for x in compile_ms])