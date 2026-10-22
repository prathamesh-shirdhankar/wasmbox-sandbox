"""
Plugin packaging module for WasmBox.
Embeds Python source code into a valid WebAssembly binary as a custom section.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

CUSTOM_SECTION_NAME = "wasmbox_script"
MAX_CODE_LENGTH = 10_000

# Directory references
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
ARTIFACT_WASM_PATH = CURRENT_DIR / "artifacts" / "micropython-wasi.wasm"


@dataclass(frozen=True)
class PluginArtifact:
    """
    Packaged WebAssembly plugin artifact containing an embedded script.
    Identified deterministically by script_sha256.
    """
    wasm_bytes: bytes
    script_sha256: str
    script: str
    section_name: str = CUSTOM_SECTION_NAME

    def __len__(self) -> int:
        return len(self.wasm_bytes)


def encode_u32_leb128(val: int) -> bytes:
    """Encode an unsigned 32-bit integer into WebAssembly LEB128 byte sequence."""
    if val < 0:
        raise ValueError("LEB128 unsigned values must be non-negative")
    res = bytearray()
    while True:
        byte = val & 0x7F
        val >>= 7
        if val != 0:
            byte |= 0x80
        res.append(byte)
        if val == 0:
            break
    return bytes(res)


def decode_u32_leb128(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """
    Decode an unsigned LEB128 integer from bytes at offset.
    Returns (value, bytes_read).
    """
    result = 0
    shift = 0
    bytes_read = 0
    while True:
        if offset + bytes_read >= len(data):
            raise ValueError("Unexpected EOF while decoding LEB128")
        byte = data[offset + bytes_read]
        bytes_read += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result, bytes_read


def resolve_base_wasm(base_wasm_path: Optional[Path | str] = None) -> Path:
    """
    Resolve base WASM binary to embed the script into.
    Prefers user-supplied path, otherwise requires official repository artifact.
    Fails loudly if the official interpreter artifact is missing.
    """
    if base_wasm_path is not None:
        p = Path(base_wasm_path)
        if not p.is_file():
            raise FileNotFoundError(f"Base WASM file not found: {p}")
        return p

    if ARTIFACT_WASM_PATH.is_file():
        return ARTIFACT_WASM_PATH

    raise FileNotFoundError(
        f"Official interpreter artifact not found at {ARTIFACT_WASM_PATH}"
    )


def package_plugin(
    code: str,
    base_wasm_path: Optional[Path | str] = None,
    section_name: str = CUSTOM_SECTION_NAME,
) -> PluginArtifact:
    """
    Package Python code into a valid WebAssembly binary by appending a custom section.
    Rejects empty or oversized code before packaging.
    """
    # 1. Input validation
    if not code or not code.strip():
        raise ValueError("No code provided: empty or whitespace-only input is rejected")

    if len(code) > MAX_CODE_LENGTH:
        raise ValueError(
            f"Code exceeds maximum allowed size of {MAX_CODE_LENGTH} characters "
            f"(received {len(code)} characters)"
        )

    # 2. Deterministic artifact identifier
    script_sha256 = hashlib.sha256(code.encode("utf-8")).hexdigest()

    # 3. Read and validate base WASM
    base_path = resolve_base_wasm(base_wasm_path)
    base_wasm_bytes = base_path.read_bytes()

    if len(base_wasm_bytes) < 8 or base_wasm_bytes[:4] != b"\x00asm":
        raise ValueError(f"Invalid WASM binary header in {base_path}")

    # 4. Construct custom section
    # Section ID 0: Custom section
    # Content format: LEB128(name_length) + name_bytes + script_payload_bytes
    name_bytes = section_name.encode("utf-8")
    script_bytes = code.encode("utf-8")
    sec_payload = encode_u32_leb128(len(name_bytes)) + name_bytes + script_bytes
    custom_section = b"\x00" + encode_u32_leb128(len(sec_payload)) + sec_payload

    # 5. Append custom section to base WASM binary
    packaged_wasm = base_wasm_bytes + custom_section

    return PluginArtifact(
        wasm_bytes=packaged_wasm,
        script_sha256=script_sha256,
        script=code,
        section_name=section_name,
    )


# Re-export extract_script from micropython_runner so single implementation is used across codebase
from app.runtime.micropython_runner import extract_script
