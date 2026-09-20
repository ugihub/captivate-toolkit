import struct
import zlib

import pytest

from captivate_toolkit.extract import (
    ExtractionLimits,
    UnsupportedFormatError,
    carve_swfs,
    decode_embedded_swf,
)


def make_fws(body: bytes = b"A" * 32, version: int = 9) -> bytes:
    return b"FWS" + bytes([version]) + struct.pack("<I", len(body) + 8) + body


def make_cws(body: bytes = b"A" * 32, version: int = 9) -> bytes:
    return b"CWS" + bytes([version]) + struct.pack("<I", len(body) + 8) + zlib.compress(body)


def test_cws_decodes_to_equivalent_fws():
    encoded = make_cws()
    assert decode_embedded_swf(encoded, 0, max_swf_bytes=1024) == make_fws()


def test_declared_swf_over_limit_is_rejected():
    encoded = b"FWS" + bytes([9]) + struct.pack("<I", 4096) + b"A" * 32
    assert decode_embedded_swf(encoded, 0, max_swf_bytes=1024) is None


def test_zws_is_reported_as_unsupported():
    with pytest.raises(UnsupportedFormatError):
        decode_embedded_swf(b"ZWS" + bytes([13]) + struct.pack("<I", 32) + b"A" * 24, 0)


def test_carve_uses_full_hash_for_deduplication(tmp_path):
    first = make_fws(b"same-prefix" + b"1" * 100 + b"same-suffix")
    second = make_fws(b"same-prefix" + b"2" * 100 + b"same-suffix")
    source = tmp_path / "lesson.exe"
    source.write_bytes(b"prefix" + first + b"middle" + second)

    result = carve_swfs(source, tmp_path / "out", limits=ExtractionLimits(max_candidates=10))

    assert len(result.candidates) == 2
    assert result.candidates[0].sha256 != result.candidates[1].sha256
