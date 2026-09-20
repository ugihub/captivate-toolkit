from __future__ import annotations

import base64
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import AnalysisError
from .media import extract_audio, extract_frames, probe_media


@dataclass(frozen=True)
class AnalysisOptions:
    preset: str = "general"
    language: str = "id"
    frame_interval: int = 8
    max_frames: int = 12
    skip_transcription: bool = False


@dataclass(frozen=True)
class AnalysisResult:
    transcript_path: Path | None
    vision_notes_path: Path
    summary_path: Path
    warnings: tuple[str, ...]


def select_frame_indices(total: int, limit: int) -> list[int]:
    if total <= 0 or limit <= 0:
        return []
    if limit == 1:
        return [total // 2]
    count = min(total, limit)
    if count == 1:
        return [0]
    return sorted({round(index * (total - 1) / (count - 1)) for index in range(count)})


def _client(settings: Settings) -> Any:
    settings.require_ai()
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AnalysisError(
            "Install extra AI terlebih dahulu: pip install 'captivate-toolkit[ai]'."
        ) from exc
    return OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=60.0, max_retries=0)


def _retry(operation: Callable[[], Any], attempts: int = 3) -> Any:
    last: Exception | None = None
    for index in range(attempts):
        try:
            return operation()
        except Exception as exc:  # SDK exception types vary across compatible providers.
            last = exc
            status = getattr(exc, "status_code", None)
            if status is not None and status < 500 and status != 429:
                raise
            if index + 1 < attempts:
                time.sleep(2**index)
    raise AnalysisError(f"Provider AI gagal setelah {attempts} percobaan: {last}") from last


def _data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def analyze_video(
    video_path: Path,
    out_dir: Path,
    *,
    settings: Settings,
    options: AnalysisOptions | None = None,
    client: Any | None = None,
) -> AnalysisResult:
    options = options or AnalysisOptions()
    if options.preset not in {"general", "sap"}:
        raise AnalysisError("Preset harus general atau sap.")
    if options.language not in {"id", "en"}:
        raise AnalysisError("Language harus id atau en.")
    if options.frame_interval <= 0 or options.max_frames <= 0:
        raise AnalysisError("Frame interval dan max frames harus lebih besar dari nol.")

    out_dir = Path(out_dir)
    frames_dir = out_dir / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe_media(video_path)
    frames = extract_frames(video_path, frames_dir, options.frame_interval)
    selected = [frames[i] for i in select_frame_indices(len(frames), options.max_frames)]
    client = client or _client(settings)
    prompt = (
        "Analisis frame tutorial secara berurutan. Identifikasi menu, langkah, tombol, istilah, "
        "dan tujuan. Jangan mengarang teks yang tidak terbaca."
        if options.preset == "general"
        else "Analisis frame tutorial SAP/Adobe Captivate secara berurutan. Identifikasi menu, langkah, objek SAP, tombol, istilah, dan tujuan. Jangan mengarang teks yang tidak terbaca."
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for frame in selected:
        content.append(
            {"type": "image_url", "image_url": {"url": _data_url(frame), "detail": "low"}}
        )
    try:
        vision = _retry(
            lambda: client.chat.completions.create(
                model=settings.vision_model, messages=[{"role": "user", "content": content}]
            )
        )
        vision_text = vision.choices[0].message.content or ""
    except Exception as exc:
        raise AnalysisError(f"Analisis visual gagal: {exc}") from exc
    vision_path = out_dir / "vision_notes.txt"
    vision_path.write_text(vision_text, encoding="utf-8")

    warnings: list[str] = []
    transcript_path: Path | None = None
    transcript = ""
    if options.skip_transcription or not info.has_audio:
        warnings.append("Transkripsi dilewati karena audio tidak tersedia atau dinonaktifkan.")
    else:
        audio_path = out_dir / "audio.mp3"
        try:
            audio = extract_audio(video_path, audio_path)
            with audio.open("rb") as handle:
                response = _retry(
                    lambda: client.audio.transcriptions.create(
                        model=settings.transcription_model, file=handle
                    )
                )
            transcript = getattr(response, "text", "") or str(response)
            transcript_path = out_dir / "transcript.txt"
            transcript_path.write_text(transcript, encoding="utf-8")
        except Exception as exc:
            warnings.append(f"Transkripsi gagal: {exc}")

    language = "Bahasa Indonesia" if options.language == "id" else "English"
    summary_prompt = f"Buat ringkasan tutorial dalam {language}. Sertakan Tujuan, Ringkasan Proses, Langkah Utama, dan Kesimpulan. Jangan menambahkan fakta yang tidak ada.\n\nTRANSKRIP:\n{transcript or '(tidak tersedia)'}\n\nANALISIS VISUAL:\n{vision_text or '(tidak tersedia)'}"
    try:
        summary = _retry(
            lambda: client.chat.completions.create(
                model=settings.text_model,
                messages=[
                    {"role": "system", "content": "Anda merangkum tutorial secara akurat."},
                    {"role": "user", "content": summary_prompt},
                ],
            )
        )
        summary_text = summary.choices[0].message.content or ""
    except Exception as exc:
        raise AnalysisError(
            f"Pembuatan ringkasan gagal; notes visual sudah disimpan: {exc}"
        ) from exc
    summary_path = out_dir / "summary.md"
    summary_path.write_text(summary_text, encoding="utf-8")
    return AnalysisResult(transcript_path, vision_path, summary_path, tuple(warnings))
