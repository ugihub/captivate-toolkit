from __future__ import annotations

import argparse
import hashlib
import math
import shutil
import sys
from pathlib import Path

from . import __version__
from .analysis import AnalysisOptions, analyze_video
from .config import load_settings
from .errors import CaptivateError, ConfigError
from .extract import ExtractionLimits, carve_swfs
from .pipeline import (
    add_artifact,
    load_manifest,
    new_manifest,
    save_manifest,
    set_stage,
    unique_job_dir,
)
from .render import RenderOptions, render_swf


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="captivate", description="Extract, render, and analyze Captivate projector files."
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    doctor = sub.add_parser("doctor", help="Check local dependencies and configuration.")
    doctor.add_argument("--ruffle-dir", type=Path)
    doctor.add_argument("--env-file", type=Path)
    doctor.add_argument("--check-api", action="store_true")

    extract = sub.add_parser("extract", help="Extract embedded FWS/CWS SWF files.")
    extract.add_argument("exe", nargs="+")
    extract.add_argument("--out", type=Path, default=Path("output"))
    extract.add_argument("--swf-index", type=int)

    render = sub.add_parser("render", help="Render an extracted SWF to visual MP4.")
    render.add_argument("swf", type=Path)
    render.add_argument("--seconds", type=float, required=True)
    render.add_argument("--ruffle-dir", type=Path, required=True)
    render.add_argument("--out", type=Path, default=Path("rendered"))
    render.add_argument("--startup-timeout", type=float, default=30.0)
    render.add_argument("--headed", action="store_true")

    analyze = sub.add_parser(
        "analyze", help="Analyze an existing MP4 with an OpenAI-compatible API."
    )
    analyze.add_argument("video", type=Path)
    analyze.add_argument("--out", type=Path, default=Path("analysis"))
    analyze.add_argument("--env-file", type=Path)
    analyze.add_argument("--preset", choices=("general", "sap"), default="general")
    analyze.add_argument("--language", choices=("id", "en"), default="id")
    analyze.add_argument("--frame-interval", type=int, default=8)
    analyze.add_argument("--max-frames", type=int, default=12)
    analyze.add_argument("--skip-transcription", action="store_true")

    run = sub.add_parser(
        "run", help="Extract, optionally render, and optionally analyze one or more EXE files."
    )
    run.add_argument("exe", nargs="+")
    run.add_argument("--out", type=Path, default=Path("output"))
    run.add_argument("--seconds", type=float, default=0)
    run.add_argument("--ruffle-dir", type=Path)
    run.add_argument("--headed", action="store_true")
    run.add_argument("--analyze", action="store_true")
    run.add_argument("--env-file", type=Path)
    run.add_argument("--preset", choices=("general", "sap"), default="general")
    run.add_argument("--language", choices=("id", "en"), default="id")
    run.add_argument("--frame-interval", type=int, default=8)
    run.add_argument("--max-frames", type=int, default=12)
    run.add_argument("--skip-transcription", action="store_true")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _output_file(path: Path, stem: str, suffix: str) -> Path:
    return path if path.suffix else path / f"{stem}{suffix}"


def _extract_into_job(source: Path, job: Path, swf_index: int | None = None) -> bool:
    manifest_path = job / "manifest.json"
    manifest = new_manifest(source, {"operation": "extract", "swf_index": swf_index})
    save_manifest(manifest_path, manifest)
    try:
        manifest["input"]["sha256"] = _sha256(source)
        set_stage(manifest, "extract", "running")
        result = carve_swfs(source, job / "swf", limits=ExtractionLimits())
        selected = result.main_swf
        if swf_index is not None:
            if swf_index < 0 or swf_index >= len(result.candidates):
                raise CaptivateError(
                    f"--swf-index di luar rentang 0..{len(result.candidates) - 1}."
                )
            selected = result.candidates[swf_index].path
            shutil.copy2(selected, job / "swf" / "main.swf")
        manifest["candidates"] = [
            {
                "path": str(candidate.path.relative_to(job)),
                "offset": candidate.offset,
                "size": candidate.size,
                "marker_hits": candidate.marker_hits,
                "sha256": candidate.sha256,
            }
            for candidate in result.candidates
        ]
        add_artifact(manifest, selected, root=job)
        set_stage(manifest, "extract", "succeeded", selected=str(selected.relative_to(job)))
        save_manifest(manifest_path, manifest)
        print(f"[ok] {source.name}: {len(result.candidates)} SWF -> {job}")
        return True
    except Exception as exc:
        set_stage(manifest, "extract", "failed", error=str(exc))
        save_manifest(manifest_path, manifest)
        print(f"[error] {source.name}: {exc}", file=sys.stderr)
        return False


def _extract_one(source: Path, output_root: Path, swf_index: int | None = None) -> bool:
    return _extract_into_job(source, unique_job_dir(output_root, source), swf_index)


def _doctor(args: argparse.Namespace) -> int:
    checks = {name: bool(shutil.which(name)) for name in ("ffmpeg", "ffprobe")}
    try:
        import playwright  # noqa: F401

        checks["playwright_python"] = True
    except ImportError:
        checks["playwright_python"] = False
    if args.ruffle_dir:
        checks["ruffle.js"] = (args.ruffle_dir / "ruffle.js").is_file()
    for name, present in checks.items():
        print(f"{name}: {'ok' if present else 'missing'}")
    if args.check_api:
        settings = load_settings(args.env_file)
        settings.require_ai()
        from openai import OpenAI

        OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=30.0).models.list()
        print("api: ok")
    return 0 if all(checks.values()) else 1


def _render(args: argparse.Namespace) -> int:
    if args.seconds <= 0 or not math.isfinite(args.seconds):
        raise ConfigError("--seconds harus finite dan lebih besar dari nol.")
    target = _output_file(args.out, args.swf.stem, ".mp4")
    render_swf(
        args.swf,
        target,
        options=RenderOptions(
            args.seconds, args.ruffle_dir, args.startup_timeout, headed=args.headed
        ),
    )
    print(f"[ok] render: {target}")
    return 0


def _analyze(args: argparse.Namespace) -> int:
    settings = load_settings(args.env_file)
    settings.require_ai()
    result = analyze_video(
        args.video,
        args.out,
        settings=settings,
        options=AnalysisOptions(
            args.preset,
            args.language,
            args.frame_interval,
            args.max_frames,
            args.skip_transcription,
        ),
    )
    for warning in result.warnings:
        print(f"[warning] {warning}")
    print(f"[ok] analysis: {result.summary_path}")
    return 0


def _run(args: argparse.Namespace) -> int:
    if args.analyze and args.seconds <= 0:
        raise ConfigError("--analyze memerlukan --seconds lebih besar dari nol.")
    if args.seconds > 0 and not args.ruffle_dir:
        raise ConfigError("--ruffle-dir wajib diisi saat --seconds digunakan.")
    settings = load_settings(args.env_file) if args.analyze else None
    if settings:
        settings.require_ai()
    successes = 0
    for exe in args.exe:
        source = Path(exe)
        job_root = args.out
        job = unique_job_dir(job_root, source)
        ok = _extract_into_job(source, job)
        if not ok:
            continue
        # Locate the most recently created job for this source; unique_job_dir makes it deterministic.
        swf_dirs = sorted(job.glob("swf"))
        if not swf_dirs:
            continue
        main_swf = swf_dirs[0] / "main.swf"
        manifest_path = job / "manifest.json"
        manifest = load_manifest(manifest_path)
        try:
            if args.seconds > 0:
                set_stage(manifest, "render", "running")
                save_manifest(manifest_path, manifest)
                render_swf(
                    main_swf,
                    job / "captivate_render.mp4",
                    options=RenderOptions(args.seconds, args.ruffle_dir, headed=args.headed),
                )
                add_artifact(manifest, job / "captivate_render.mp4", root=job)
                set_stage(manifest, "render", "succeeded")
            if args.analyze:
                set_stage(manifest, "analyze", "running")
                save_manifest(manifest_path, manifest)
                analyze_video(
                    job / "captivate_render.mp4",
                    job / "ai",
                    settings=settings,
                    options=AnalysisOptions(
                        args.preset,
                        args.language,
                        args.frame_interval,
                        args.max_frames,
                        args.skip_transcription,
                    ),
                )
                add_artifact(manifest, job / "ai" / "summary.md", root=job)
                set_stage(manifest, "analyze", "succeeded")
            save_manifest(manifest_path, manifest)
            successes += 1
        except CaptivateError as exc:
            stage = (
                "analyze"
                if args.analyze
                and manifest.get("stages", {}).get("analyze", {}).get("status") == "running"
                else "render"
            )
            if args.seconds <= 0 and not args.analyze:
                stage = "extract"
            set_stage(manifest, stage, "failed", error=str(exc))
            save_manifest(manifest_path, manifest)
            print(f"[error] {source.name}: {exc}", file=sys.stderr)
    return 0 if successes == len(args.exe) else 1


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        if not args.command:
            parser.print_help()
            return 0
        if args.command == "doctor":
            return _doctor(args)
        if args.command == "extract":
            results = [_extract_one(Path(path), args.out, args.swf_index) for path in args.exe]
            return 0 if all(results) else 1
        if args.command == "render":
            return _render(args)
        if args.command == "analyze":
            return _analyze(args)
        if args.command == "run":
            return _run(args)
        return 2
    except CaptivateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except SystemExit as exc:
        return int(exc.code or 0)
