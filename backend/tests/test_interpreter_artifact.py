"""Check that the vendored MicroPython WASI interpreter has not changed.

If this test fails, the artifact file was edited, replaced, or corrupted.
Do not just update the hash: find out why it changed first, and check it
against the package version recorded in
backend/app/runtime/artifacts/README.md and docs/SPIKES.md.
"""

import hashlib
from pathlib import Path

ARTIFACT = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "runtime"
    / "artifacts"
    / "micropython-wasi.wasm"
)

# micropython-wasm 0.1a2, Apache-2.0 (see artifacts/README.md)
EXPECTED_SHA256 = "1c054a4d21d4a6589bc568821ebf562889988ddaaf8a17a2e2985a56cf228051"


def test_interpreter_artifact_exists():
    assert ARTIFACT.is_file(), f"Interpreter artifact not found at {ARTIFACT}"


def test_interpreter_artifact_sha256_matches():
    actual = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
    assert actual == EXPECTED_SHA256, (
        "Interpreter artifact hash changed.\n"
        f"  expected: {EXPECTED_SHA256}\n"
        f"  actual:   {actual}\n"
        f"  file:     {ARTIFACT}"
    )