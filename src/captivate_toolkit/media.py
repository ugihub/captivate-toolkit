from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import MediaError


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    has_audio: bool
    has_video: bool
    video_codec: str | None
    width: int | None
    height: int | None


def run_command(
    command: Sequence[str],
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise MediaError(f"Dependensi tidak ditemukan: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"Perintah melebihi timeout: {command[0]}") from exc


def _require(command: str) -> str:
    path = shutil.which(command)
    if not path:
        raise MediaError(f"{command} tidak ditemukan di PATH.")
    return path


def probe_media(path: Path) -> MediaInfo:
    path = Path(path)
    if not path.is_file():
        raise MediaError(f"Media tidak ditemukan: {path}")
    result = run_command(
        [
            _require("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        timeout=30,
    )
    if result.returncode != 0:
        raise MediaError(f"ffprobe gagal: {result.stderr[-1000:]}")
    try:
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        return MediaInfo(
            duration=float(payload.get("format", {}).get("duration", 0.0) or 0.0),
            has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
            has_video=video is not None,
            video_codec=video.get("codec_name") if video else None,
            width=int(video["width"]) if video and video.get("width") else None,
            height=int(video["height"]) if video and video.get("height") else None,
        )
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise MediaError("Output ffprobe tidak valid.") from exc


def extract_audio(video_path: Path, audio_path: Path) -> Path | None:
    result = run_command(
        [
            _require("ffmpeg"),
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "mp3",
            str(audio_path),
        ],
        timeout=300,
    )
    if result.returncode != 0 or not audio_path.exists() or audio_path.stat().st_size < 1024:
        raise MediaError(f"FFmpeg gagal mengekstrak audio: {result.stderr[-1000:]}")
    return audio_path


def extract_frames(video_path: Path, frame_dir: Path, interval: int) -> list[Path]:
    if interval <= 0:
        raise MediaError("Interval frame harus lebih besar dari nol.")
    frame_dir.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            _require("ffmpeg"),
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{interval},scale=1280:-2",
            "-q:v",
            "3",
            str(frame_dir / "frame_%04d.jpg"),
        ],
        timeout=600,
    )
    if result.returncode != 0:
        raise MediaError(f"FFmpeg gagal mengambil frame: {result.stderr[-1000:]}")
    return sorted(frame_dir.glob("frame_*.jpg"))
