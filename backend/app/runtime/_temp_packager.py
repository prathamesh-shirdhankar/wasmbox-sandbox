"""TEMPORARY stand-in for package_plugin (Vineet).

Delegates to the real package_plugin now that it is implemented.
"""

from app.runtime.packaging import package_plugin


def temp_package(code: str) -> bytes:
    return package_plugin(code).wasm_bytes