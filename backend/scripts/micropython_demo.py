import sys
from pathlib import Path

# Make "app" importable when running from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime._temp_packager import temp_package
from app.runtime.micropython_runner import run_plugin

CASES = [
    ("print", 'print("hi")'),
    ("1/0", "1/0"),
    ("syntax error", "print("),
]

for label, code in CASES:
    result = run_plugin(temp_package(code))
    print(f"=== {label}")
    print("status:", result.status)
    print("stdout:", repr(result.stdout))
    print("stderr:", repr(result.stderr))