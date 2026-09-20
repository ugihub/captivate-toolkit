from __future__ import annotations

import functools
import http.server
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import RenderError
from .media import probe_media, run_command


@dataclass(frozen=True)
class RenderOptions:
    seconds: float
    ruffle_dir: Path
    startup_timeout: float = 30.0
    ffmpeg_timeout: float | None = None
    headed: bool = False
    width: int = 1024
    height: int = 776


def _ruffle_script(ruffle_dir: Path) -> Path:
    for name in ("ruffle.js", "ruffle-web.js", "ruffle_selfhosted.js"):
        path = Path(ruffle_dir) / name
        if path.is_file():
            return path
    raise RenderError(f"Tidak menemukan ruffle.js di {ruffle_dir}.")


def _create_player(folder: Path) -> None:
    html = """<!doctype html>
<html><head><meta charset="utf-8"><title>Captivate Toolkit</title>
<script>
window.RufflePlayer = window.RufflePlayer || {};
window.RufflePlayer.config = { autoplay: "on", unmuteOverlay: "hidden", allowScriptAccess: false, allowNetworking: "none" };
</script>
<script src="ruffle/ruffle.js"></script></head>
<body style="margin:0;background:#000"><div id="container"></div>
<script>
window.addEventListener("load", async () => {
  try {
    const ruffle = window.RufflePlayer.newest();
    const player = ruffle.createPlayer();
    player.style.width = "100%"; player.style.height = "100%";
    document.getElementById("container").appendChild(player);
    const movie = typeof player.ruffle === "function" ? player.ruffle() : player;
    await movie.load({url: "main.swf", autoplay: "on"});
    window.__ruffleReady = true;
  } catch (error) { window.__ruffleError = String(error); }
});
</script></body></html>"""
    (folder / "player.html").write_text(html, encoding="utf-8")


def render_swf(swf_path: Path, out_mp4: Path, *, options: RenderOptions) -> Path:
    if options.seconds <= 0 or not options.seconds == options.seconds:
        raise RenderError("Durasi render harus berupa angka finite yang lebih besar dari nol.")
    if options.width <= 0 or options.height <= 0:
        raise RenderError("Ukuran viewport harus lebih besar dari nol.")
    swf_path = Path(swf_path)
    if not swf_path.is_file():
        raise RenderError(f"SWF tidak ditemukan: {swf_path}")
    _ruffle_script(options.ruffle_dir)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RenderError(
            "Install extra render: pip install 'captivate-toolkit[render]' lalu playwright install chromium."
        ) from exc

    stage = Path(out_mp4).parent / f".{Path(out_mp4).stem}.render"
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "main.swf").write_bytes(swf_path.read_bytes())
    shutil.copytree(options.ruffle_dir, stage / "ruffle", dirs_exist_ok=True)
    _create_player(stage)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(stage))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    video_path: Path | None = None
    content_offset = 0.0
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(
                    headless=not options.headed, args=["--autoplay-policy=no-user-gesture-required"]
                )
            except Exception as exc:
                raise RenderError(f"Chromium tidak dapat dijalankan: {exc}") from exc
            context = browser.new_context(
                viewport={"width": options.width, "height": options.height},
                record_video_dir=str(stage / "video"),
                record_video_size={"width": options.width, "height": options.height},
            )
            page = context.new_page()
            recording = page.video
            recording_started = time.monotonic()
            try:
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/player.html",
                    wait_until="load",
                    timeout=int(options.startup_timeout * 1000),
                )
                page.wait_for_function(
                    "window.__ruffleReady === true || window.__ruffleError",
                    timeout=int(options.startup_timeout * 1000),
                )
                error = page.evaluate("window.__ruffleError || ''")
                if error:
                    raise RenderError(f"Ruffle gagal memuat SWF: {error}")
                content_offset = max(0.0, time.monotonic() - recording_started)
                page.wait_for_timeout(int(options.seconds * 1000))
            finally:
                page.close()
                context.close()
                video_path = Path(recording.path()) if recording else None
                browser.close()
    except RenderError:
        raise
    except Exception as exc:
        raise RenderError(f"Render browser gagal: {exc}") from exc
    finally:
        server.shutdown()
        server.server_close()

    if not video_path or not video_path.exists():
        raise RenderError("Playwright tidak menghasilkan rekaman video.")
    ffmpeg = "ffmpeg"
    result = run_command(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{content_offset:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{options.seconds:.3f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ],
        timeout=options.ffmpeg_timeout or max(60.0, options.seconds * 2),
    )
    if result.returncode != 0 or not out_mp4.is_file():
        raise RenderError(f"FFmpeg gagal membuat MP4: {result.stderr[-1000:]}")
    try:
        info = probe_media(out_mp4)
    except Exception as exc:
        raise RenderError(f"MP4 hasil render tidak dapat divalidasi: {exc}") from exc
    if not info.has_video:
        raise RenderError("MP4 hasil render tidak memiliki video stream.")
    shutil.rmtree(stage, ignore_errors=True)
    return out_mp4
