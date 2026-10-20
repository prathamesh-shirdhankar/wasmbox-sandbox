"""TEMPORARY stand-in for package_plugin (Vineet).

Delete this file once the real package_plugin is on main, and point the
demo and tests at it instead.
"""

from app.runtime.micropython_runner import INTERPRETER_PATH, SECTION_NAME


def _leb128(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def temp_package(code: str) -> bytes:
    name = SECTION_NAME.encode("utf-8")
    body = _leb128(len(name)) + name + code.encode("utf-8")
    return INTERPRETER_PATH.read_bytes() + b"\x00" + _leb128(len(body)) + body