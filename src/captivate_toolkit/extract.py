from __future__ import annotations

import hashlib
import re
import shutil
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from .errors import ExtractionError, UnsupportedFormatError

CAPTIVATE_MARKERS = (
    b"Adobe Captivate",
    b"rdcmndNextSlide",
    b"cpCmndGotoSlide",
    b"rdinfoCurrentSlide",
    b"Slide0_mc",
)


@dataclass(frozen=True)
class ExtractionLimits:
    max_input_bytes: int = 512 * 1024 * 1024
    max_swf_bytes: int = 128 * 1024 * 1024
    max_total_swf_bytes: int = 512 * 1024 * 1024
    max_candidates: int = 256


@dataclass(frozen=True)
class SwfCandidate:
    path: Path
    offset: int
    size: int
    marker_hits: int
    score: int
    sha256: str


@dataclass(frozen=True)
class ExtractionResult:
    candidates: tuple[SwfCandidate, ...]
    main_swf: Path


def decode_embedded_swf(
    exe_data: bytes,
    offset: int,
    *,
    max_swf_bytes: int = 128 * 1024 * 1024,
) -> bytes | None:
    if offset < 0 or offset >= len(exe_data):
        return None
    sig = exe_data[offset : offset + 3]
    if sig not in (b"FWS", b"CWS", b"ZWS"):
        return None
    if sig == b"ZWS":
        raise UnsupportedFormatError("ZWS/LZMA SWF belum didukung pada v0.1.0.")
    if offset + 8 > len(exe_data):
        return None

    version = exe_data[offset + 3]
    declared_size = struct.unpack_from("<I", exe_data, offset + 4)[0]
    if declared_size < 16 or declared_size > max_swf_bytes:
        return None

    if sig == b"FWS":
        end = offset + declared_size
        if end > len(exe_data):
            return None
        return exe_data[offset:end]

    needed = declared_size - 8
    try:
        dec = zlib.decompressobj()
        body = dec.decompress(exe_data[offset + 8 :], needed)
        if len(body) < needed:
            body += dec.flush()
    except (MemoryError, zlib.error):
        return None
    if len(body) != needed or not dec.eof:
        return None
    return b"FWS" + bytes([version]) + struct.pack("<I", declared_size) + body


def carve_swfs(
    exe_path: Path,
    out_dir: Path,
    *,
    limits: ExtractionLimits | None = None,
) -> ExtractionResult:
    limits = limits or ExtractionLimits()
    exe_path = Path(exe_path)
    if not exe_path.is_file():
        raise ExtractionError(f"File input tidak ditemukan: {exe_path}")
    if exe_path.stat().st_size > limits.max_input_bytes:
        raise ExtractionError(f"Input melebihi batas {limits.max_input_bytes} byte.")

    data = exe_path.read_bytes()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[SwfCandidate] = []
    seen_hashes: set[str] = set()
    total_bytes = 0
    unsupported_seen = False

    for match in re.finditer(rb"(?:FWS|CWS|ZWS)", data):
        if len(candidates) >= limits.max_candidates:
            break
        try:
            swf = decode_embedded_swf(data, match.start(), max_swf_bytes=limits.max_swf_bytes)
        except UnsupportedFormatError:
            unsupported_seen = True
            continue
        if not swf:
            continue
        fingerprint = hashlib.sha256(swf).hexdigest()
        if fingerprint in seen_hashes:
            continue
        if total_bytes + len(swf) > limits.max_total_swf_bytes:
            break
        seen_hashes.add(fingerprint)
        marker_hits = sum(marker in swf for marker in CAPTIVATE_MARKERS)
        path = out_dir / f"embedded_{len(candidates) + 1:02d}_offset_{match.start()}.swf"
        path.write_bytes(swf)
        candidates.append(
            SwfCandidate(
                path=path,
                offset=match.start(),
                size=len(swf),
                marker_hits=marker_hits,
                score=len(swf) + marker_hits * 10_000_000,
                sha256=fingerprint,
            )
        )
        total_bytes += len(swf)

    if not candidates:
        if unsupported_seen:
            raise UnsupportedFormatError(
                "Hanya ZWS/LZMA SWF yang ditemukan; format ini belum didukung."
            )
        raise ExtractionError("Tidak menemukan SWF FWS/CWS valid di dalam input.")

    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    main_swf = out_dir / "main.swf"
    shutil.copy2(candidates[0].path, main_swf)
    return ExtractionResult(candidates=tuple(candidates), main_swf=main_swf)
