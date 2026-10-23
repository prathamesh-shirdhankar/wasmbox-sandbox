"""
Tests for plugin packaging pipeline.
Verifies embedding Python scripts in WebAssembly custom sections.
"""
import hashlib
import sys
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import wasmtime
from app.runtime.packaging import (
    package_plugin,
    extract_script,
    PluginArtifact,
    CUSTOM_SECTION_NAME,
    MAX_CODE_LENGTH,
    encode_u32_leb128,
    decode_u32_leb128,
)


def test_packaging_output_header_and_loads_in_wasmtime():
    """Output begins with WASM header and loads with Wasmtime."""
    source_code = 'print("hello world")'
    artifact = package_plugin(source_code)

    assert isinstance(artifact, PluginArtifact)
    # Check 4-byte WASM magic header (\x00asm) and 4-byte version (\x01\x00\x00\x00)
    assert artifact.wasm_bytes[:4] == b"\x00asm"
    assert artifact.wasm_bytes[4:8] == b"\x01\x00\x00\x00"

    # Verify Wasmtime compiles and validates the resulting binary
    engine = wasmtime.Engine()
    wasmtime.Module.validate(engine, artifact.wasm_bytes)
    module = wasmtime.Module(engine, artifact.wasm_bytes)
    assert module is not None


def test_embedded_script_matches_original_source_exactly():
    """The embedded script matches the original source exactly."""
    complex_script = (
        'import sys\n'
        'def add(a, b):\n'
        '    return a + b\n\n'
        'print("Sum:", add(10, 32))\n'
    )
    artifact = package_plugin(complex_script)
    extracted = extract_script(artifact.wasm_bytes)

    assert extracted == complex_script
    assert artifact.script == complex_script


def test_identical_source_produces_identical_artifact_bytes():
    """Identical source produces identical artifact bytes."""
    source_code = 'print("deterministic artifact")'
    artifact1 = package_plugin(source_code)
    artifact2 = package_plugin(source_code)

    assert artifact1.wasm_bytes == artifact2.wasm_bytes
    assert artifact1.script_sha256 == artifact2.script_sha256


def test_different_source_produces_different_hash():
    """Different source produces a different hash."""
    source1 = 'print("version 1")'
    source2 = 'print("version 2")'
    artifact1 = package_plugin(source1)
    artifact2 = package_plugin(source2)

    assert artifact1.script_sha256 != artifact2.script_sha256
    expected_hash1 = hashlib.sha256(source1.encode("utf-8")).hexdigest()
    expected_hash2 = hashlib.sha256(source2.encode("utf-8")).hexdigest()
    assert artifact1.script_sha256 == expected_hash1
    assert artifact2.script_sha256 == expected_hash2
    assert artifact1.wasm_bytes != artifact2.wasm_bytes


@pytest.mark.parametrize("empty_code", ["", "   ", "\n\t  \n"])
def test_empty_code_is_rejected(empty_code):
    """Empty and whitespace-only input is rejected before packaging."""
    with pytest.raises(ValueError, match="No code provided"):
        package_plugin(empty_code)


def test_oversized_code_is_rejected():
    """Code exceeding 10,000 characters is rejected before packaging."""
    oversized = "a = 1\n" + ("# comment\n" * 1200)
    assert len(oversized) > MAX_CODE_LENGTH

    with pytest.raises(ValueError, match="exceeds maximum allowed size"):
        package_plugin(oversized)


def test_boundary_10k_chars_is_accepted():
    """Boundary test: exactly 10,000 characters packages cleanly."""
    exact_10k = "a = 1\n" + ("#" * (MAX_CODE_LENGTH - 6))
    assert len(exact_10k) == MAX_CODE_LENGTH

    artifact = package_plugin(exact_10k)
    assert len(artifact.script) == MAX_CODE_LENGTH
    assert extract_script(artifact.wasm_bytes) == exact_10k


def test_leb128_roundtrip():
    """Verify LEB128 encoding and decoding for various sizes."""
    test_values = [0, 1, 127, 128, 255, 300, 10000, 65535, 1_000_000]
    for val in test_values:
        encoded = encode_u32_leb128(val)
        decoded, bytes_read = decode_u32_leb128(encoded)
        assert decoded == val
        assert bytes_read == len(encoded)


def test_packaging_uses_micropython_artifact_by_default():
    """Verify package_plugin uses the official MicroPython WASI artifact by default."""
    from app.runtime.packaging import resolve_base_wasm, ARTIFACT_WASM_PATH

    base_path = resolve_base_wasm()
    assert base_path == ARTIFACT_WASM_PATH
    assert base_path.is_file()

    base_bytes = base_path.read_bytes()
    artifact = package_plugin('print("test artifact")')
    assert artifact.wasm_bytes.startswith(base_bytes)
    assert len(artifact.wasm_bytes) > len(base_bytes)


def test_custom_section_binary_layout_matches_pipeline_spec():
    """
    Verify the binary layout matches docs/PIPELINE.md Section 4:
    [0x00] [sec_len LEB128] [name_len LEB128] [name UTF-8] [script UTF-8]
    """
    from app.runtime.packaging import resolve_base_wasm

    script = 'print("pipeline spec test")'
    base_bytes = resolve_base_wasm().read_bytes()
    artifact = package_plugin(script)

    # Custom section immediately follows base wasm bytes
    custom_section_bytes = artifact.wasm_bytes[len(base_bytes):]
    assert custom_section_bytes[0] == 0x00  # Section ID 0 for custom section

    sec_len, sec_leb_bytes = decode_u32_leb128(custom_section_bytes, offset=1)
    payload_start = 1 + sec_leb_bytes
    assert len(custom_section_bytes) == payload_start + sec_len

    payload = custom_section_bytes[payload_start:]
    name_len, name_leb_bytes = decode_u32_leb128(payload, offset=0)
    name_bytes = payload[name_leb_bytes:name_leb_bytes + name_len]
    assert name_bytes.decode("utf-8") == CUSTOM_SECTION_NAME

    extracted_script = payload[name_leb_bytes + name_len:].decode("utf-8")
    assert extracted_script == script


def test_extract_script_raises_if_custom_section_missing():
    """Verify extract_script raises ValueError/ArtifactError if section name is not present."""
    from app.runtime.packaging import resolve_base_wasm

    base_bytes = resolve_base_wasm().read_bytes()
    with pytest.raises(ValueError, match="Script section not found"):
        extract_script(base_bytes)


def test_invalid_base_wasm_header_raises(tmp_path):
    """Verify ValueError is raised if the base WASM has an invalid magic header."""
    corrupted_wasm = tmp_path / "corrupted.wasm"
    corrupted_wasm.write_bytes(b"INVALID_WASM_HEADER")

    with pytest.raises(ValueError, match="Invalid WASM binary header"):
        package_plugin('print("hello")', base_wasm_path=corrupted_wasm)

